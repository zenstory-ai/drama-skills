#!/usr/bin/env python3
"""Rewrite a project tree from expanded upstream references to the compact
``sources`` form, and verify a tree that is already compact.

Expanded form (still accepted everywhere, never rewritten back)::

    {"owner": "...", "artifact": "...", "record_id": "..."}

Compact form::

    {"src": "<sources key>", "record_id": "..."}

with the file declaring each upstream artifact once:

* ``.json``  -> a top-level ``"sources"`` object.
* ``.jsonl`` -> a first-line header record
  ``{"record_type": "sources", "schema_version": "1.0.0", "sources": {...}}``.
  When the file already opens with its own header record whose ``record_type``
  ends in ``_meta`` (``screenplay_index_meta`` is the existing precedent), the
  ``sources`` map is folded into that record instead of adding a second header
  line, so ``records[0]["record_type"]`` keeps its current value.

Usage::

    python3 tools/compact_refs.py <project-dir>              # rewrite in place
    python3 tools/compact_refs.py --migrate <project-dir>    # rewrite in place (explicit)
    python3 tools/compact_refs.py --check <project-dir>      # verify only

Guarantees:

* Deterministic. Source keys, key ordering and serialisation depend only on the
  input bytes.
* Idempotent. Running the tool twice produces identical bytes, because every
  file is first normalised back to the expanded form in memory, then re-compacted.
* Byte-faithful. Nothing outside the reference objects and the ``sources``
  declaration is touched: record order, key order, creative text, IDs and every
  other field survive unchanged, and each file keeps its own indentation and
  trailing-newline convention.
* Fixed point. Files are rewritten in topological order, and a file keeps the
  inline form when declaring ``sources`` would not shrink its byte size. Keys
  ending in ``_locator`` (such as ``target_locator`` for a not-yet-published
  artifact) keep their inline ``{"owner", "artifact"}`` form and are never
  folded into ``sources``.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple, TextIO

# ---------------------------------------------------------------------------
# REFERENCE RESOLVER -- reference implementation.
#
# Each skill checker carries its own copy of this block. The suite has no shared
# library on purpose: a skill must stay runnable after copying only its own
# directory, so duplicating these few lines across skills is the correct shape.
# Copy the block verbatim; do not import it.
# ---------------------------------------------------------------------------

SOURCES_RECORD_TYPE = "sources"
SOURCES_SCHEMA_VERSION = "1.0.0"


class ResolvedRef(NamedTuple):
    """An upstream reference with its owner and artifact resolved, whichever form it used."""

    owner: str
    artifact: str
    record_id: str | None
    field: str | None
    authority: str | None


class RefFinding(NamedTuple):
    """A structural defect in a reference object."""

    code: str
    location: str
    detail: str


def load_sources(document: Any) -> dict[str, dict[str, Any]]:
    """Return the ``sources`` declaration of a parsed file, or ``{}`` if absent.

    Accepts a parsed ``.json`` document (a dict) or the parsed record list of a
    ``.jsonl`` file, whose declaration lives on the first record.
    """
    if isinstance(document, list):
        document = document[0] if document else None
    if not isinstance(document, dict):
        return {}
    declared = document.get("sources")
    if not isinstance(declared, dict):
        return {}
    return {key: value for key, value in declared.items() if isinstance(value, dict)}


def resolve_ref(
    ref: Any, sources: dict[str, dict[str, Any]], location: str
) -> tuple[ResolvedRef | None, RefFinding | None]:
    """Resolve a reference object written in either the compact or expanded form."""
    if not isinstance(ref, dict):
        return None, RefFinding("REF_IS_NOT_AN_OBJECT", location, f"got {type(ref).__name__}")
    src = ref.get("src")
    if isinstance(src, str):
        entry = sources.get(src)
        if entry is None:
            return None, RefFinding(
                "REF_SRC_IS_NOT_DECLARED", location, f"src {src!r} has no sources entry"
            )
        owner, artifact = entry.get("owner"), entry.get("artifact")
        if not (isinstance(owner, str) and isinstance(artifact, str)):
            return None, RefFinding(
                "SOURCE_ENTRY_IS_INCOMPLETE", location, f"sources[{src!r}] needs owner/artifact"
            )
    elif all(isinstance(ref.get(key), str) for key in ("owner", "artifact")):
        owner, artifact = ref["owner"], ref["artifact"]
    else:
        return None, RefFinding(
            "REF_HAS_NO_UPSTREAM_BINDING", location, "needs src, or owner+artifact"
        )
    optional = {
        key: ref[key] for key in ("record_id", "field", "authority") if isinstance(ref.get(key), str)
    }
    return (
        ResolvedRef(
        owner,
        artifact,
            optional.get("record_id"),
            optional.get("field"),
            optional.get("authority"),
        ),
        None,
    )


# ---------------------------------------------------------------------------
# END REFERENCE RESOLVER
# ---------------------------------------------------------------------------

REF_PAIR = ("owner", "artifact")
SOURCES_KEY = "sources"
DATA_SUFFIXES = (".json", ".jsonl")
MAX_KEY_QUALIFIER_DEPTH = 8

# A reference slot is named by convention, so --check can tell a defective
# reference from an ordinary object. ``reviewed_artifacts`` is the one carrier in
# the suite that predates the convention; ``boundary_refs`` holds named refs
# rather than one ref, and is handled as a container below. Keys ending in
# ``_locator`` point at targets that may not be published yet and always stay in
# inline ``{"owner", "artifact"}`` form.
REF_CARRIER_SUFFIXES = ("_ref", "_refs")
EXTRA_REF_CARRIERS = ("reviewed_artifacts",)
LOCATOR_SUFFIX = "_locator"

# (owner, artifact) identifies one upstream artifact.
SourceId = tuple[str, str]


class Finding(NamedTuple):
    """A defect reported by ``--check`` or ``--migrate``."""

    path: str
    code: str
    detail: str


class FileFormat(NamedTuple):
    """The serialisation conventions of one file, detected from its own bytes."""

    is_jsonl: bool
    indent: int | None
    ensure_ascii: bool
    trailing_newline: bool


class LoadedFile(NamedTuple):
    """A parsed data file plus everything needed to write it back unchanged."""

    path: Path
    relative: str
    fmt: FileFormat
    records: list[Any]
    original_bytes: bytes


def emit(line: str, *, stream: TextIO | None = None) -> None:
    """Print a line that may name a path like ``剧集/EP001/…``.

    A Windows console defaults to a legacy codepage that cannot encode those
    names, and the findings worth reporting are exactly the ones carrying a
    project path.
    """
    target = stream if stream is not None else sys.stdout
    try:
        print(line, file=target)
        return
    except UnicodeEncodeError:
        pass
    buffer = getattr(target, "buffer", None)
    if buffer is None:
        encoding = getattr(target, "encoding", "ascii") or "ascii"
        print(line.encode(encoding, "backslashreplace").decode(encoding), file=target)
        return
    target.flush()
    buffer.write(f"{line}\n".encode())
    buffer.flush()


def is_locator_key(key: str) -> bool:
    """True for ``*_locator`` slots, which stay inline and out of ``sources``."""
    return key.endswith(LOCATOR_SUFFIX)


def _is_within(candidate: Path, resolved_root: Path) -> bool:
    """Python 3.9-compatible containment check after resolving symlinks."""
    try:
        candidate.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def _relative_posix(path: Path, root: Path) -> str:
    return PurePosixPath(path.relative_to(root).as_posix()).as_posix()


def _has_symlink_component(root: Path, rel_parts: tuple[str, ...]) -> bool:
    if root.is_symlink():
        return True
    current = root
    for part in rel_parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _scan_tree_safety(root: Path, resolved_root: Path) -> list[Finding]:
    """Report symlinks and root-escaping files among non-hidden project entries."""
    if root.is_symlink():
        return [Finding(".", "SYMLINK_NOT_ALLOWED", "project root may not be a symlink")]
    findings: list[Finding] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirpath_path = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            if dirname.startswith("."):
                continue
            subdir = dirpath_path / dirname
            if subdir.is_symlink():
                findings.append(
                    Finding(
                        _relative_posix(subdir, root),
                        "SYMLINK_NOT_ALLOWED",
                        "symlinked directory is not allowed in project tree",
                    )
                )
                continue
            if not _is_within(subdir.resolve(), resolved_root):
                findings.append(
                    Finding(
                        _relative_posix(subdir, root),
                        "PATH_ESCAPES_ROOT",
                        "directory resolves outside project root",
                    )
                )
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            entry = dirpath_path / filename
            if entry.is_symlink():
                findings.append(
                    Finding(
                        _relative_posix(entry, root),
                        "SYMLINK_NOT_ALLOWED",
                        "symlinked file is not allowed in project tree",
                    )
                )
                continue
            if entry.suffix in DATA_SUFFIXES and not _is_within(entry.resolve(), resolved_root):
                findings.append(
                    Finding(
                        _relative_posix(entry, root),
                        "PATH_ESCAPES_ROOT",
                        "data file resolves outside project root",
                    )
                )
    return findings


def _validate_artifact_target(root: Path, resolved_root: Path, artifact: str) -> str | None:
    """Validate an ``artifact`` path relative to ``root``.

    Returns ``None`` when ``artifact`` names a regular in-project file with no
    symlink components; otherwise returns ``"ESCAPES_ROOT"``, ``"SYMLINK"`` or
    ``"MISSING"``.
    """
    if (
        not artifact
        or "\x00" in artifact
        or "\\" in artifact
        or artifact.startswith("/")
        or Path(artifact).is_absolute()
    ):
        return "ESCAPES_ROOT"
    parts = PurePosixPath(artifact).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return "ESCAPES_ROOT"
    if _has_symlink_component(root, parts):
        return "SYMLINK"
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve()
    except (OSError, ValueError):
        return "ESCAPES_ROOT"
    if not _is_within(resolved, resolved_root):
        return "ESCAPES_ROOT"
    if not resolved.is_file():
        return "MISSING"
    return None


def _ensure_safe_write_target(path: Path, root: Path, resolved_root: Path) -> None:
    """Raise ``ValueError`` if ``path`` or any in-project ancestor is unsafe."""
    if root.is_symlink():
        raise ValueError("project root may not be a symlink")
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError as exc:
        raise ValueError(f"{path} escapes project root {root}") from exc
    if not rel_parts:
        raise ValueError(f"refusing to overwrite project root {root}")
    relative = _relative_posix(path, root)
    if _has_symlink_component(root, rel_parts):
        raise ValueError(f"{relative}: SYMLINK_NOT_ALLOWED: refusing to write unsafe path")
    if not _is_within(path.parent.resolve(), resolved_root) or not _is_within(
        path.resolve(), resolved_root
    ):
        raise ValueError(f"{relative}: PATH_ESCAPES_ROOT: refusing to write outside project root")


def _atomic_write_bytes(path: Path, root: Path, resolved_root: Path, payload: bytes) -> None:
    """Atomically write ``payload`` to ``path`` via a same-directory temp file + ``os.replace``."""
    _ensure_safe_write_target(path, root, resolved_root)
    mode: int | None = None
    try:
        details = os.lstat(path)
    except FileNotFoundError:
        details = None
    if details is not None:
        if stat.S_ISLNK(details.st_mode):
            relative = _relative_posix(path, root)
            raise ValueError(f"{relative}: SYMLINK_NOT_ALLOWED: refusing to overwrite symlink")
        mode = stat.S_IMODE(details.st_mode)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp_path, mode)
        _ensure_safe_write_target(path, root, resolved_root)
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# Reading and writing while preserving each file's conventions
# ---------------------------------------------------------------------------


def detect_format(path: Path, text: str, records: list[Any]) -> FileFormat:
    """Infer indent / escaping / trailing-newline so a round trip is byte-exact."""
    is_jsonl = path.suffix == ".jsonl"
    trailing_newline = text.endswith("\n")
    for ensure_ascii in (False, True):
        for indent in (None, 2, 4) if not is_jsonl else (None,):
            fmt = FileFormat(is_jsonl, indent, ensure_ascii, trailing_newline)
            if render(records, fmt) == text:
                return fmt
    # Unknown layout: fall back to the suite default and normalise on write.
    return FileFormat(is_jsonl, None if is_jsonl else 2, False, trailing_newline)


def render(records: list[Any], fmt: FileFormat) -> str:
    if fmt.is_jsonl:
        lines = [
            json.dumps(record, ensure_ascii=fmt.ensure_ascii, separators=(",", ":"))
            for record in records
        ]
        text = "\n".join(lines)
    else:
        text = json.dumps(records[0], ensure_ascii=fmt.ensure_ascii, indent=fmt.indent)
    return text + "\n" if fmt.trailing_newline else text


def load_file(
    path: Path, root: Path, findings: list[Finding] | None = None
) -> LoadedFile | None:
    if root.is_symlink():
        if findings is not None:
            findings.append(Finding(".", "SYMLINK_NOT_ALLOWED", "project root may not be a symlink"))
        return None
    resolved_root = root.resolve()
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        if findings is not None:
            findings.append(Finding(str(path), "PATH_ESCAPES_ROOT", "file is outside project root"))
        return None
    relative = _relative_posix(path, root)
    if _has_symlink_component(root, rel_parts):
        if findings is not None:
            findings.append(
                Finding(relative, "SYMLINK_NOT_ALLOWED", "symlinked data file is not allowed")
            )
        return None
    if not _is_within(path.resolve(), resolved_root):
        if findings is not None:
            findings.append(
                Finding(relative, "PATH_ESCAPES_ROOT", "data file resolves outside project root")
            )
        return None

    original_bytes = path.read_bytes()
    try:
        text = original_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        if findings is not None:
            findings.append(
                Finding(relative, "INVALID_JSON", f"file is not valid UTF-8 ({exc})")
            )
        return None
    try:
        if path.suffix == ".jsonl":
            records: list[Any] = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            records = [json.loads(text)]
    except json.JSONDecodeError as exc:
        if findings is not None:
            findings.append(
                Finding(relative, "INVALID_JSON", f"invalid JSON ({exc.msg} at line {exc.lineno})")
            )
        return None
    if not records:
        return None
    return LoadedFile(path, relative, detect_format(path, text, records), records, original_bytes)


def iter_data_files(root: Path) -> Iterator[Path]:
    if root.is_symlink() or not root.is_dir():
        return
    resolved_root = root.resolve()
    collected: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirpath_path = Path(dirpath)
        dirnames[:] = [
            dirname
            for dirname in sorted(dirnames)
            if not dirname.startswith(".")
            and not (dirpath_path / dirname).is_symlink()
            and _is_within((dirpath_path / dirname).resolve(), resolved_root)
        ]
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            candidate = dirpath_path / filename
            if candidate.suffix not in DATA_SUFFIXES or candidate.is_symlink():
                continue
            resolved = candidate.resolve()
            if not _is_within(resolved, resolved_root) or not resolved.is_file():
                continue
            collected.append(candidate)
    yield from sorted(collected)


# ---------------------------------------------------------------------------
# Walking references
# ---------------------------------------------------------------------------


def is_expanded_ref(node: Any) -> bool:
    """True for an object carrying both ``owner`` and ``artifact`` as non-empty strings.

    Requiring both keys keeps ``observer`` objects (which carry ``owner`` without
    ``artifact``) out; ``*_locator`` slots also carry ``owner`` and ``artifact``
    for targets that may not exist yet, so callers skip keys ending in
    ``_locator`` before testing ``is_expanded_ref``.
    """
    if not isinstance(node, dict):
        return False
    return all(isinstance(node.get(key), str) and node[key] for key in REF_PAIR)


def is_compact_ref(node: Any) -> bool:
    return isinstance(node, dict) and isinstance(node.get("src"), str)


def expand_refs(
    node: Any, sources: dict[str, dict[str, Any]], *, key_name: str | None = None
) -> Any:
    """Rewrite every compact ref back to inline ``owner`` + ``artifact``, in memory.

    Normalising first is what makes ``--migrate`` idempotent across repeated runs.
    """
    if key_name is not None and is_locator_key(key_name):
        return node
    if isinstance(node, list):
        return [expand_refs(item, sources) for item in node]
    if not isinstance(node, dict):
        return node
    if is_compact_ref(node):
        entry = sources.get(str(node["src"]))
        if entry is not None and all(isinstance(entry.get(key), str) for key in REF_PAIR):
            rest = {
                key: expand_refs(value, sources, key_name=key)
                for key, value in node.items()
                if key != "src"
            }
            return {key: entry[key] for key in REF_PAIR} | rest
    return {key: expand_refs(value, sources, key_name=key) for key, value in node.items()}


def iter_expanded_refs(node: Any, *, key_name: str | None = None) -> Iterator[dict[str, Any]]:
    if key_name is not None and is_locator_key(key_name):
        return
    if isinstance(node, list):
        for item in node:
            yield from iter_expanded_refs(item)
        return
    if not isinstance(node, dict):
        return
    if is_expanded_ref(node):
        yield node
    for key, value in node.items():
        yield from iter_expanded_refs(value, key_name=key)


def compact_refs(
    node: Any, keys: dict[SourceId, str], *, key_name: str | None = None
) -> Any:
    if key_name is not None and is_locator_key(key_name):
        return node
    if isinstance(node, list):
        return [compact_refs(item, keys) for item in node]
    if not isinstance(node, dict):
        return node
    if is_expanded_ref(node):
        source_id = resolved_source_id(node)
        rest = {
            key: compact_refs(value, keys, key_name=key)
            for key, value in node.items()
            if key not in REF_PAIR
        }
        return {"src": keys[source_id]} | rest
    return {key: compact_refs(value, keys, key_name=key) for key, value in node.items()}


def resolved_source_id(ref: dict[str, Any]) -> SourceId:
    """A reference identifies its upstream by owner and artifact."""
    owner, artifact = (str(ref[key]) for key in REF_PAIR)
    return owner, artifact


def slug(text: str) -> str:
    out: list[str] = []
    for char in text.lower():
        if char.isalnum():
            out.append(char)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def _ancestors(artifact: str) -> list[str]:
    """Directory components of an artifact path, nearest parent first."""
    return [part for part in reversed(PurePosixPath(artifact).parent.parts) if part not in (".", "/")]


def _candidate_key(artifact: str, depths: set[int]) -> str:
    stem = slug(PurePosixPath(artifact).stem) or "source"
    ancestors = _ancestors(artifact)
    prefix = [slug(ancestors[depth]) for depth in sorted(depths, reverse=True) if depth < len(ancestors)]
    return "-".join([part for part in prefix if part] + [stem])


def derive_source_keys(source_ids: Iterable[SourceId]) -> dict[SourceId, str]:
    """Map each ``(owner, artifact)`` pair to a short, lowercase, file-unique key.

    The key starts as the artifact's basename. Basenames collide often -- eight
    episodes each own a ``shots.jsonl`` -- so a colliding group is qualified by
    the nearest ancestor directory that actually differs between its members,
    which yields ``ep001-shots`` rather than ``ep001-storyboard-shots``. Pairs
    whose artifact paths still share every qualifier (for instance, two owners
    naming the same path) get a deterministic numeric suffix in sorted order.
    """
    entries = sorted(set(source_ids))
    depths: dict[SourceId, set[int]] = {entry: set() for entry in entries}
    for _ in range(MAX_KEY_QUALIFIER_DEPTH):
        groups: dict[str, list[SourceId]] = defaultdict(list)
        for entry in entries:
            groups[_candidate_key(entry[1], depths[entry])].append(entry)
        colliding = [group for group in groups.values() if len(group) > 1]
        if not colliding:
            break
        progressed = False
        for group in colliding:
            ancestor_lists = {entry: _ancestors(entry[1]) for entry in group}
            depth_limit = max(len(values) for values in ancestor_lists.values())
            for depth in range(depth_limit):
                if depth in depths[group[0]]:
                    continue
                seen = {
                    ancestor_lists[entry][depth] if depth < len(ancestor_lists[entry]) else ""
                    for entry in group
                }
                if len(seen) > 1:
                    for entry in group:
                        depths[entry].add(depth)
                    progressed = True
                    break
        if not progressed:
            break

    keys: dict[SourceId, str] = {}
    taken: dict[str, int] = {}
    for entry in entries:
        base = _candidate_key(entry[1], depths[entry])
        count = taken.get(base, 0)
        taken[base] = count + 1
        keys[entry] = base if count == 0 else f"{base}-{count + 1}"
    return keys


# ---------------------------------------------------------------------------
# Sources declaration placement
# ---------------------------------------------------------------------------


def strip_sources(loaded: LoadedFile) -> tuple[list[Any], str, int]:
    """Remove any existing declaration.

    Returns the payload records, the placement mode used to write a declaration
    back (``"json"``, ``"header"`` or ``"folded"``) and the key position to
    restore inside the carrier object, or ``-1`` to place it first.
    """
    records = [dict(record) if isinstance(record, dict) else record for record in loaded.records]
    if not loaded.fmt.is_jsonl:
        document = records[0]
        position = -1
        if isinstance(document, dict) and SOURCES_KEY in document:
            position = list(document).index(SOURCES_KEY)
            del document[SOURCES_KEY]
        return records, "json", position
    first = records[0]
    if isinstance(first, dict) and first.get("record_type") == SOURCES_RECORD_TYPE:
        return records[1:], "header", -1
    if isinstance(first, dict) and str(first.get("record_type", "")).endswith("_meta"):
        position = -1
        if SOURCES_KEY in first:
            position = list(first).index(SOURCES_KEY)
            del first[SOURCES_KEY]
        return records, "folded", position
    return records, "header", -1


def place_sources(
    records: list[Any], mode: str, position: int, sources: dict[str, dict[str, str]]
) -> list[Any]:
    if not sources:
        return records
    if mode == "header":
        header = {
            "record_type": SOURCES_RECORD_TYPE,
            "schema_version": SOURCES_SCHEMA_VERSION,
            SOURCES_KEY: sources,
        }
        return [header, *records]
    carrier = records[0]
    if not isinstance(carrier, dict):
        return records
    items = list(carrier.items())
    index = position if 0 <= position <= len(items) else (len(items) if mode == "folded" else 0)
    records[0] = dict(items[:index]) | {SOURCES_KEY: sources} | dict(items[index:])
    return records


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------


def build_order(files: dict[str, LoadedFile]) -> list[str]:
    """Topologically order files so an upstream file is rewritten before its consumers."""
    dependencies: dict[str, set[str]] = {relative: set() for relative in files}
    for relative, loaded in files.items():
        sources = load_sources(loaded.records)
        for record in loaded.records:
            for ref in iter_expanded_refs(expand_refs(record, sources)):
                artifact = str(ref["artifact"])
                if artifact in files and artifact != relative:
                    dependencies[relative].add(artifact)

    order: list[str] = []
    done: set[str] = set()
    pending = sorted(files)
    while pending:
        ready = [name for name in pending if dependencies[name] <= done]
        if not ready:
            # A cycle: break it in name order so the run stays deterministic.
            ready = [pending[0]]
            emit(f"warning: reference cycle involving {pending[0]}", stream=sys.stderr)
        for name in ready:
            order.append(name)
            done.add(name)
        pending = [name for name in pending if name not in done]
    return order


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def _verify_file_records(
    relative: str,
    records: list[Any],
    on_disk: set[str],
    root: Path,
    resolved_root: Path,
    *,
    check_unused_sources: bool = True,
) -> list[Finding]:
    """Validate every reference candidate and ``sources`` entry in ``records``."""
    findings: list[Finding] = []
    sources = load_sources(records)
    used: set[str] = set()
    for index, record in enumerate(records, start=1):
        for ref, location in iter_ref_candidates(record, f"{relative}#record{index}"):
            compact = isinstance(ref.get("src"), str)
            if compact:
                used.add(str(ref["src"]))
            resolved, defect = resolve_ref(ref, sources, location)
            if defect is not None:
                detail = f"{defect.location}: {defect.detail}"
                findings.append(Finding(relative, defect.code, detail))
                continue
            # A declared source is checked once below; an inline one is only
            # reachable here.
            if resolved is not None and not compact and resolved.artifact not in on_disk:
                status = _validate_artifact_target(root, resolved_root, resolved.artifact)
                if status == "ESCAPES_ROOT":
                    detail = (
                        f"{location} names {resolved.artifact}, which escapes the project root"
                    )
                    findings.append(Finding(relative, "REF_TARGET_ESCAPES_ROOT", detail))
                elif status == "SYMLINK":
                    detail = (
                        f"{location} names {resolved.artifact}, which is or traverses a symlink"
                    )
                    findings.append(Finding(relative, "REF_TARGET_IS_SYMLINK", detail))
                elif status == "MISSING":
                    detail = (
                        f"{location} names {resolved.artifact}, which is not in this project"
                    )
                    findings.append(Finding(relative, "REF_TARGET_IS_MISSING", detail))
    for key in sorted(sources):
        entry = sources[key]
        artifact = entry.get("artifact")
        if key not in used:
            if check_unused_sources:
                detail = f"sources[{key!r}] is declared but no reference uses it"
                findings.append(Finding(relative, "SOURCE_IS_UNUSED", detail))
            else:
                continue
        if not isinstance(artifact, str) or artifact in on_disk:
            continue
        status = _validate_artifact_target(root, resolved_root, artifact)
        if status == "ESCAPES_ROOT":
            detail = f"sources[{key!r}] names {artifact}, which escapes the project root"
            findings.append(Finding(relative, "SOURCE_TARGET_ESCAPES_ROOT", detail))
        elif status == "SYMLINK":
            detail = f"sources[{key!r}] names {artifact}, which is or traverses a symlink"
            findings.append(Finding(relative, "SOURCE_TARGET_IS_SYMLINK", detail))
        elif status == "MISSING":
            detail = f"sources[{key!r}] names {artifact}, which is not in this project"
            findings.append(Finding(relative, "SOURCE_TARGET_IS_MISSING", detail))
    return findings


def migrate(root: Path) -> int:
    if root.is_symlink():
        emit(".: SYMLINK_NOT_ALLOWED: project root may not be a symlink", stream=sys.stderr)
        return 1
    resolved_root = root.resolve()
    findings: list[Finding] = _scan_tree_safety(root, resolved_root)
    files: dict[str, LoadedFile] = {}
    for path in iter_data_files(root):
        loaded = load_file(path, root, findings=findings)
        if loaded is not None:
            files[loaded.relative] = loaded
    on_disk = set(files)
    for relative in sorted(files):
        findings.extend(
            _verify_file_records(
                relative,
                files[relative].records,
                on_disk,
                root,
                resolved_root,
                check_unused_sources=False,
            )
        )
    if findings:
        for report in findings:
            emit(f"{report.path}: {report.code}: {report.detail}", stream=sys.stderr)
        emit(f"\n{len(findings)} finding(s)", stream=sys.stderr)
        return 1

    planned_writes: list[tuple[LoadedFile, bytes]] = []
    try:
        for relative in build_order(files):
            loaded = files[relative]
            declared = load_sources(loaded.records)
            records, mode, position = strip_sources(loaded)
            records = [expand_refs(record, declared) for record in records]

            source_ids = {
                resolved_source_id(ref)
                for record in records
                for ref in iter_expanded_refs(record)
            }
            keys = derive_source_keys(source_ids)
            sources = {
                keys[source_id]: {"owner": source_id[0], "artifact": source_id[1]}
                for source_id in sorted(source_ids, key=lambda entry: keys[entry])
            }
            compact = place_sources(
                [compact_refs(record, keys) for record in records], mode, position, sources
            )
            compact_payload = render(compact, loaded.fmt).encode("utf-8")
            inline_payload = render(records, loaded.fmt).encode("utf-8")
            # Declaring an upstream artifact once pays off only when something
            # references it more than once. A fan-in manifest naming 104 artifacts
            # once each would grow, so it keeps the inline form.
            use_compact = len(compact_payload) < len(inline_payload)
            chosen_records = compact if use_compact else records
            payload = compact_payload if use_compact else inline_payload

            findings.extend(
                _verify_file_records(
                    relative,
                    chosen_records,
                    on_disk,
                    root,
                    resolved_root,
                    check_unused_sources=True,
                )
            )
            if payload != loaded.original_bytes:
                _ensure_safe_write_target(loaded.path, root, resolved_root)
                planned_writes.append((loaded, payload))
    except (OSError, ValueError) as exc:
        emit(f"error: {exc}", stream=sys.stderr)
        return 1

    if findings:
        for report in findings:
            emit(f"{report.path}: {report.code}: {report.detail}", stream=sys.stderr)
        emit(f"\n{len(findings)} finding(s)", stream=sys.stderr)
        return 1

    written: list[LoadedFile] = []
    try:
        for loaded, payload in planned_writes:
            _atomic_write_bytes(loaded.path, root, resolved_root, payload)
            written.append(loaded)
    except (OSError, ValueError) as exc:
        for previous in reversed(written):
            try:
                _atomic_write_bytes(
                    previous.path, root, resolved_root, previous.original_bytes
                )
            except (OSError, ValueError):
                pass
        emit(f"error: {exc}", stream=sys.stderr)
        return 1

    emit(f"rewrote {len(planned_writes)} of {len(files)} data files under {root}")
    return 0


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def check(root: Path) -> int:
    if root.is_symlink():
        emit(".: SYMLINK_NOT_ALLOWED: project root may not be a symlink")
        emit("\n1 finding(s)", stream=sys.stderr)
        return 1
    resolved_root = root.resolve()
    findings: list[Finding] = _scan_tree_safety(root, resolved_root)
    files: dict[str, LoadedFile] = {}
    for path in iter_data_files(root):
        loaded = load_file(path, root, findings=findings)
        if loaded is not None:
            files[loaded.relative] = loaded
    # References no longer carry bytes, so the strongest local claim is that the
    # artifact a reference names is really there inside the project root.
    # Whether it is *current* is a lifecycle question, answered by project_tool
    # state, not by these files.
    on_disk = set(files)

    for relative in sorted(files):
        findings.extend(
            _verify_file_records(
                relative,
                files[relative].records,
                on_disk,
                root,
                resolved_root,
                check_unused_sources=True,
            )
        )

    if not findings:
        emit(
            f"every reference in {len(files)} data files under {root} names an artifact that exists"
        )
        return 0
    for report in findings:
        emit(f"{report.path}: {report.code}: {report.detail}")
    emit(f"\n{len(findings)} finding(s)", stream=sys.stderr)
    return 1


def is_ref_carrier(key: str) -> bool:
    return key.endswith(REF_CARRIER_SUFFIXES) or key in EXTRA_REF_CARRIERS


def is_ref_container(node: dict[str, Any]) -> bool:
    """True for ``boundary_refs``-style objects that hold several named refs."""
    return bool(node) and all(isinstance(value, dict) for value in node.values())


def iter_ref_candidates(
    node: Any, location: str, in_slot: bool = False
) -> Iterator[tuple[dict[str, Any], str]]:
    """Yield every object used as a reference, with a readable location.

    Objects in either valid form are found structurally. An object sitting in a
    reference slot in *neither* form is yielded too, so ``--check`` reports it
    rather than silently skipping it. Keys ending in ``_locator`` are skipped
    because locators identify targets that may not be published yet.
    """
    if isinstance(node, list):
        for index, item in enumerate(node):
            yield from iter_ref_candidates(item, f"{location}[{index}]", in_slot)
        return
    if not isinstance(node, dict):
        return
    if is_compact_ref(node) or is_expanded_ref(node):
        yield node, location
    elif in_slot:
        if not is_ref_container(node):
            yield node, location
            return
        for key, value in node.items():
            if is_locator_key(key):
                continue
            yield from iter_ref_candidates(value, f"{location}/{key}", True)
        return
    for key, value in node.items():
        if key == SOURCES_KEY or is_locator_key(key):
            continue
        yield from iter_ref_candidates(value, f"{location}/{key}", is_ref_carrier(key))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("project", type=Path, help="project directory to rewrite or verify")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--migrate",
        action="store_true",
        help=(
            "rewrite inline {owner, artifact} references into compact {src} "
            "references with a per-file sources map (default mode; leaves "
            "*_locator fields untouched)"
        ),
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help=(
            "verify that every reference resolves to a regular in-project "
            "artifact and every declared sources entry is used; never write"
        ),
    )
    args = parser.parse_args(argv)
    root: Path = args.project
    if root.is_symlink():
        emit(f"error: {root} may not be a symlink", stream=sys.stderr)
        return 2
    try:
        if not root.is_absolute():
            current = Path(".")
            for part in root.parts:
                if part in ("", "."):
                    continue
                current = current / part
                if current.is_symlink():
                    raise ValueError(f"{root} traverses a symlink")
        if not root.is_dir():
            emit(f"error: {root} is not a directory", stream=sys.stderr)
            return 2
        return check(root) if args.check else migrate(root)
    except (OSError, ValueError) as exc:
        emit(f"error: {exc}", stream=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
