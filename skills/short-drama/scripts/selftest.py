#!/usr/bin/env python3
"""Offline self-test for the standalone project lifecycle."""

from __future__ import annotations

import json
import tempfile
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

from project_tool import initialize_project, project_status, publish_candidate

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.9 or newer")

SKILL_ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_DECISION_RECORDS = [
    {
        "record_type": "sources",
        "schema_version": "1.0.0",
        "sources": {"short-drama": {"owner": "short-drama", "artifact": "short-drama.json"}},
    },
    {
        "decision_id": "CD-VISUAL-001",
        "decision_kind": "visual_direction",
        "status": "accepted",
        "target_locators": [{"src": "short-drama", "field": "/creator_authority/visual_direction"}],
    },
]

# ---------------------------------------------------------------------------
# REFERENCE RESOLVER -- reference implementation.
#
# Each skill carries its own copy of this block. The suite has no shared
# library on purpose: a skill must stay runnable after copying only its own
# directory, so duplicating these few lines across skills is the correct shape.
# Copy the block verbatim; do not import it.
# ---------------------------------------------------------------------------

SOURCES_RECORD_TYPE = "sources"
SOURCES_SCHEMA_VERSION = "1.0.0"


class ResolvedRef(NamedTuple):
    """An upstream reference with its snapshot resolved, whichever form it used."""

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
                "SOURCE_ENTRY_IS_INCOMPLETE",
                location,
                f"sources[{src!r}] needs owner/artifact",
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

# A reference lives under a slot named by convention. `target_locators` is the
# creator-decision carrier that predates the suffix rule.
REF_CARRIER_SUFFIXES = ("_ref", "_refs")
EXTRA_REF_CARRIERS = ("target_locators",)


def is_ref_carrier(key: str) -> bool:
    return key.endswith(REF_CARRIER_SUFFIXES) or key in EXTRA_REF_CARRIERS


def iter_refs(node: Any, location: str) -> Iterator[tuple[Any, str]]:
    """Yield every reference object carried anywhere inside a record."""
    if isinstance(node, list):
        for index, item in enumerate(node):
            yield from iter_refs(item, f"{location}[{index}]")
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        where = f"{location}/{key}"
        if is_ref_carrier(key) and value is not None:
            if isinstance(value, list):
                for index, ref in enumerate(value):
                    yield ref, f"{where}[{index}]"
            else:
                yield value, where
            continue
        yield from iter_refs(value, where)


def read_records(path: Path) -> list[Any]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def check_records(records: list[Any], name: str) -> tuple[int, list[RefFinding]]:
    """Resolve every reference in a .jsonl file through its own declaration."""
    sources = load_sources(records)
    resolved = 0
    findings: list[RefFinding] = []
    for number, record in enumerate(records, 1):
        if isinstance(record, dict) and record.get("record_type") == SOURCES_RECORD_TYPE:
            continue
        for ref, where in iter_refs(record, f"{name}:{number}"):
            found, finding = resolve_ref(ref, sources, where)
            if finding is not None:
                findings.append(finding)
            if found is not None:
                resolved += 1
    return resolved, findings


CHECKS = 0


def require(condition: bool, message: str) -> None:
    global CHECKS
    if not condition:
        raise AssertionError(message)
    CHECKS += 1


def main() -> int:
    declared = load_sources(SYNTHETIC_DECISION_RECORDS)
    require(bool(declared), "synthetic decision records declare upstream snapshots")
    resolved, findings = check_records(SYNTHETIC_DECISION_RECORDS, "synthetic-decision.jsonl")
    require(not findings, f"synthetic decision reference findings: {findings}")
    require(resolved > 0, "synthetic decision records carry at least one resolvable reference")

    sources = {"screenplay": {"owner": "short-drama-write", "artifact": "a.md", "hash": "0" * 64}}
    _, undeclared = resolve_ref({"src": "missing", "record_id": "BLK-1"}, sources, "synthetic")
    require(
        undeclared is not None and undeclared.code == "REF_SRC_IS_NOT_DECLARED",
        "a src without a sources entry is a structural finding",
    )
    _, unbound = resolve_ref({"record_id": "BLK-1"}, sources, "synthetic")
    require(
        unbound is not None and unbound.code == "REF_HAS_NO_UPSTREAM_BINDING",
        "a reference binding neither way is a structural finding",
    )
    expanded, finding = resolve_ref(
        {
            "owner": "short-drama-write",
            "artifact": "剧集/EP001/screenplay-index.jsonl",
            "hash": "a" * 64,
            "record_id": "BLK-EP001-SC001-A01",
        },
        {},
        "synthetic",
    )
    require(
        finding is None and expanded is not None and expanded.record_id == "BLK-EP001-SC001-A01",
        "a project written before the declaration still resolves",
    )

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        created = initialize_project(
            root,
            title="Self-test",
            language="zh-CN",
            prompt_language="en",
            aspect_ratio="9:16",
        )
        require(created["project"]["title"] == "Self-test", "project title")
        require(
            project_status(root)["project_id"] == created["project"]["project_id"],
            "project discovery",
        )

        published = publish_candidate(
            root,
            owner="selftest",
            artifact_id="SELFTEST-001",
            outputs={"剧集/EP001/screenplay.md": "# EP001\n"},
        )
        require(published["state"] == "needs_confirmation", "publication state")

        header = json.dumps(
            {
                "record_type": SOURCES_RECORD_TYPE,
                "schema_version": SOURCES_SCHEMA_VERSION,
                "sources": {
                    "screenplay": {
                        "owner": "short-drama-write",
                        "artifact": "剧集/EP001/screenplay.md",
                        "hash": "a" * 64,
                    }
                },
            },
            ensure_ascii=False,
        )
        record = json.dumps(
            {"shot_id": "SHOT-001", "source_ref": {"src": "screenplay", "record_id": "BLK-1"}},
            ensure_ascii=False,
        )
        declared_publication = publish_candidate(
            root,
            owner="selftest",
            artifact_id="SELFTEST-002",
            outputs={"剧集/EP001/storyboard/shots.jsonl": f"{header}\n{record}\n"},
        )
        require(
            declared_publication["state"] == "needs_confirmation",
            "a file declaring its upstream snapshots publishes",
        )

        try:
            publish_candidate(
                root,
                owner="selftest",
                artifact_id="SELFTEST-UNSAFE",
                outputs={"../escape.md": "unsafe"},
            )
        except ValueError:
            rejected = True
        else:
            rejected = False
        require(rejected, "unsafe publication path was accepted")

    print(f"{CHECKS} self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
