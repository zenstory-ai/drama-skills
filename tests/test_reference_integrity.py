"""Semantic references must name something that is actually there.

A reference that names a real file can still point at nothing: ``field`` can
name a key the target record does not carry, ``projected_fields`` can name a
contract field that was removed, and ``source_step_pointer`` can name a causal
step that no longer exists. None of that is caught by checking that the
*artifact* exists, which is all the reference resolver does.

This is not hypothetical. Shrinking the episode map removed the single-step
``causal_escalation`` field and left eight episode cards pointing at
``/causal_escalation/0``. Every existing test stayed green; the dangling
pointers were found by reading. This module is the test that would have caught
them.

It runs over the golden project because that is the one complete, fully
resolvable project in the repository. Templates point at ``剧集/<EP>/...``
placeholders that resolve to nothing by design, so they are out of scope here.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
GOLDEN = SUITE / "examples/golden-project"

# Keys whose value is a JSON pointer into the artifact the same object (or its
# enclosing record) references.
POINTER_KEYS = ("field", "source_step_pointer", "motion_field")
POINTER_LIST_KEYS = ("projected_fields", "source_contract_fields")


def documents(path: Path) -> list[Any]:
    """Every JSON document a file carries; empty for non-JSON artifacts.

    References legitimately name Markdown targets such as ``screenplay.md``.
    Those carry no records, so a ``record_id`` against them is checked only for
    file existence.
    """
    if path.suffix not in {".json", ".jsonl"}:
        return []
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return [json.loads(text)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def data_records(path: Path) -> list[Any]:
    return [
        record
        for record in documents(path)
        if not (isinstance(record, dict) and record.get("record_type") == "sources")
    ]


def declared_sources(docs: list[Any]) -> dict[str, dict[str, Any]]:
    """The ``sources`` block, in either shape the suite writes.

    JSONL files open with a dedicated ``record_type: sources`` record; ``.json``
    files put the same object at the top level. Accepting only the first shape
    made every ``.json`` artifact resolve to zero declared sources, so its
    pointers were skipped in silence -- which is how a shipped template kept six
    pointers into fields that no longer exist.
    """
    for document in docs:
        if isinstance(document, dict) and document.get("record_type") == "sources":
            sources = document.get("sources")
            if isinstance(sources, dict):
                return sources
    for document in docs:
        if isinstance(document, dict) and document.get("record_type") is None:
            sources = document.get("sources")
            if isinstance(sources, dict):
                return sources
    return {}


def resolve_reference(reference: Any, sources: dict[str, Any]) -> dict[str, Any] | None:
    """The artifact a reference names, in either the compact or expanded form."""
    if not isinstance(reference, dict):
        return None
    src = reference.get("src")
    if isinstance(src, str):
        entry = sources.get(src)
        if not isinstance(entry, dict):
            return None
        merged = dict(entry)
        merged.update({k: v for k, v in reference.items() if k != "src"})
        return merged
    if isinstance(reference.get("artifact"), str):
        return dict(reference)
    return None


def identity_key(records: list[Any]) -> set[str]:
    """The key that identifies a record, as opposed to one that points elsewhere.

    Records carry several ``*_id`` fields: an occurrence has ``occurrence_id``
    but also ``episode_id`` and ``scene_id``, and an acceptance has
    ``decision_id`` alongside ``artifact_id``. Matching any ``*_id`` would let a
    reference resolve against some other record's *foreign key* and report a
    dangling reference as fine -- the exact failure this module exists to catch.

    An identity key is unique among the records that carry it. Foreign keys
    repeat -- many occurrences share one ``episode_id`` -- so they are excluded.
    A file may hold more than one record type (a screenplay index opens with a
    meta record and continues with blocks), so candidates are gathered from
    every record rather than from the first one.

    Limitation worth knowing: a foreign key that happens to be unique *and*
    present on every record of its type is indistinguishable from a co-identity
    without a schema. Acceptance records are the real case -- each decision is
    about exactly one artifact, so ``artifact_id`` is unique and total. Treating
    it as an identity is right there; if a genuine foreign key ever acquires
    that shape, this resolver would accept a reference to it.
    """
    rows = [record for record in records if isinstance(record, dict)]
    keys = {key for row in rows for key in row if key.endswith("_id")}
    identities = set()
    for key in keys:
        carriers = [row for row in rows if isinstance(row.get(key), str)]
        if not carriers:
            continue
        values = [row[key] for row in carriers]
        if len(set(values)) != len(values):
            continue  # repeats, so it points at something else
        # A key carried by only some records of a type is a foreign key on those
        # records, not the identity of the type.
        same_shape = [row for row in rows if row.get("record_type") == carriers[0].get("record_type")]
        if len(carriers) == len(same_shape):
            identities.add(key)
    return identities


def record_by_id(records: list[Any], record_id: str) -> Any:
    identities = identity_key(records)
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in identities:
            if record.get(key) == record_id:
                return record
    return None


def pointer_resolves(document: Any, pointer: str) -> bool:
    """RFC-6901 style traversal, enough for the pointers this suite writes."""
    if pointer in {"", "/"}:
        return True
    node = document
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                return False
            node = node[token]
        elif isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node):
                return False
            node = node[int(token)]
        else:
            return False
    return True


def iter_pointer_claims(path: Path):
    """Yield (location, target_artifact, record_id, pointer) for one file.

    A pointer is resolved against the artifact its own object references when it
    has one, and otherwise against the nearest enclosing reference -- which is
    how ``projected_fields`` and ``source_contract_fields`` are written.
    """
    docs = documents(path)
    sources = declared_sources(docs)

    def document_default(document: Any) -> dict[str, Any] | None:
        """The reference a whole document is written against, if it declares one.

        An episode card puts its contract reference under ``contract_authority``
        and its pointers under ``execution_plan`` -- siblings, not ancestors, so
        inheriting only downward would leave those pointers unchecked. That is
        exactly the shape that shipped eight dangling pointers.
        """
        if not isinstance(document, dict):
            return None
        authority = document.get("contract_authority")
        if isinstance(authority, dict):
            return resolve_reference(authority.get("source_ref"), sources)
        return None

    def walk(node: Any, cursor: str, inherited: dict[str, Any] | None) -> None:
        if isinstance(node, dict):
            here = resolve_reference(node, sources) or inherited
            for key in POINTER_KEYS:
                pointer = node.get(key)
                if isinstance(pointer, str) and here is not None:
                    yield_target(f"{cursor}/{key}", here, pointer)
            for key in POINTER_LIST_KEYS:
                values = node.get(key)
                if isinstance(values, list) and here is not None:
                    for index, pointer in enumerate(values):
                        if isinstance(pointer, str):
                            yield_target(f"{cursor}/{key}/{index}", here, pointer)
            for key, child in node.items():
                walk(child, f"{cursor}/{key}", here)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{cursor}/{index}", inherited)

    claims: list[tuple[str, str, Any, str]] = []

    def yield_target(location: str, reference: dict[str, Any], pointer: str) -> None:
        artifact = reference.get("artifact")
        if isinstance(artifact, str):
            claims.append((location, artifact, reference.get("record_id"), pointer))

    for index, document in enumerate(docs):
        walk(document, f"#doc{index}", document_default(document))
    return claims


class ReferenceIntegrityTests(unittest.TestCase):
    def test_every_semantic_pointer_resolves_in_its_target(self) -> None:
        checked = 0
        for path in sorted(GOLDEN.rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
                continue
            for location, artifact, record_id, pointer in iter_pointer_claims(path):
                target = GOLDEN / artifact
                where = f"{path.relative_to(GOLDEN)}:{location} -> {artifact}"
                self.assertTrue(target.is_file(), f"{where}: target file is missing")
                records = data_records(target)
                if record_id is not None and not records:
                    continue
                if record_id is not None:
                    document = record_by_id(records, str(record_id))
                    self.assertIsNotNone(document, f"{where}#{record_id}: no such record")
                elif len(records) == 1:
                    document = records[0]
                else:
                    # A pointer into a multi-record file without naming the
                    # record cannot be checked; the reference itself is the
                    # defect, and the shape tests already report it.
                    continue
                checked += 1
                self.assertTrue(
                    pointer_resolves(document, pointer),
                    f"{where}{'#' + str(record_id) if record_id else ''}: "
                    f"{pointer} names nothing in the target",
                )
        self.assertGreater(checked, 0, "no semantic pointers were checked")

    def test_every_record_id_reference_names_a_real_record(self) -> None:
        checked = 0
        for path in sorted(GOLDEN.rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
                continue
            docs = documents(path)
            sources = declared_sources(docs)

            def walk(node: Any, cursor: str) -> None:
                nonlocal checked
                if isinstance(node, dict):
                    resolved = resolve_reference(node, sources)
                    record_id = node.get("record_id")
                    if resolved and isinstance(record_id, str):
                        artifact = resolved.get("artifact")
                        if isinstance(artifact, str):
                            target = GOLDEN / artifact
                            where = f"{path.relative_to(GOLDEN)}:{cursor} -> {artifact}"
                            self.assertTrue(target.is_file(), f"{where}: missing target")
                            records = data_records(target)
                            if not records:
                                return
                            checked += 1
                            self.assertIsNotNone(
                                record_by_id(records, record_id),
                                f"{where}#{record_id}: no such record",
                            )
                    for key, child in node.items():
                        walk(child, f"{cursor}/{key}")
                elif isinstance(node, list):
                    for index, child in enumerate(node):
                        walk(child, f"{cursor}/{index}")

            for index, document in enumerate(docs):
                walk(document, f"#doc{index}")
        self.assertGreater(checked, 0, "no record references were checked")


# Artifact basename -> the repository sample that defines its schema.
# Samples may be current skill assets or test-only authoring records. The
# episode path is a placeholder, but its schema remains checkable by basename.
# A target with no row is reported rather than skipped.
SCHEMA_TEMPLATES = {
    "episode-map.jsonl": "short-drama-develop/assets/episode-map.jsonl",
    "short-drama.json": "short-drama/assets/project-template/short-drama.json",
    "shots.jsonl": "../tests/fixtures/authoring-records/shot-template.jsonl",
    "props.jsonl": "../tests/fixtures/authoring-records/prop-state.example.jsonl",
    "location-views.jsonl": "../tests/fixtures/authoring-records/location-view.example.jsonl",
    # Creator decisions are named after the artifact they accept, so they are
    # matched by their directory rather than by a fixed basename.
    "创作者决策/": "short-drama/assets/creator-decision.example.jsonl",
}
# A second source of truth for the same artifacts: a real, accepted project.
# Several of these files legitimately hold more than one record shape -- a
# shipped example shows one of them -- so a pointer valid against the other
# shape would read as removed if the template were consulted alone. A field
# present in neither the template nor a real accepted artifact is what a
# genuinely removed field looks like.
REAL_PROJECT = SUITE / "evaluations/让你管账号/reference-run"
REAL_ARTIFACTS = {
    "episode-map.jsonl": "项目开发/episode-map.jsonl",
    "short-drama.json": "short-drama.json",
    "shots.jsonl": "剧集/EP001/storyboard/shots.jsonl",
    "props.jsonl": "设定集/props.jsonl",
    "location-views.jsonl": "设定集/location-views.jsonl",
    "创作者决策/": "创作者决策/decisions.jsonl",
}
# Targets that genuinely have no shipped schema: they are produced by a script
# rather than copied from a template, so there is nothing here to check against.
GENERATED_TARGETS = {
    "screenplay-index.jsonl",
    "<project-relative-text-artifact>",
}


class ShippedTemplateReferenceTests(unittest.TestCase):
    """Templates that name a real schema path must resolve against it.

    The golden-project tests skip templates because their ``剧集/<EP>/...``
    references are placeholders that resolve to nothing by design. That excuse
    does not cover the schema those placeholders point into, which is fixed and
    ships in this repository. SKILL.md tells the writer to copy the template, so
    a pointer naming a removed field is not a placeholder, it is an instruction
    to produce a dangling reference.

    This was written for one artifact and hard-coded its name, leaving every
    other shipped pointer unchecked -- four of which were then shown to be
    breakable with the whole suite green.
    """

    def top_level_keys(self, relative: str) -> set[str]:
        """Every key the template shows, across all of its record variants.

        Reading only the first record misses the others: the creator-decision
        example carries an acceptance variant on a later line, and a pointer
        into it read as naming a removed field.
        """

        path = SUITE / "skills" / relative
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            return set(json.loads(text))
        found: set[str] = set()
        for line in text.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("record_type") == "sources":
                continue
            found |= set(record)
        if not found:
            self.fail(f"{relative} carries no record")
        return found

    def schema_name(self, artifact: str) -> str | None:
        """Which schema row an artifact belongs to, by basename or directory."""

        name = artifact.rsplit("/", 1)[-1]
        if name in SCHEMA_TEMPLATES:
            return name
        for key in SCHEMA_TEMPLATES:
            if key.endswith("/") and artifact.startswith(key):
                return key
        return None

    def real_documents(self, name: str) -> list[Any]:
        relative = REAL_ARTIFACTS.get(name)
        path = REAL_PROJECT / relative if relative else None
        if path is None or not path.is_file():
            return []
        return data_records(path)

    def real_keys(self, name: str) -> set[str]:
        relative = REAL_ARTIFACTS.get(name)
        path = REAL_PROJECT / relative if relative else None
        if path is None or not path.is_file():
            return set()
        found: set[str] = set()
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            return set(json.loads(text))
        for line in text.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("record_type") == "sources":
                continue
            found |= set(record)
        return found

    def test_shipped_templates_do_not_project_removed_fields(self) -> None:
        keys = {
            name: self.top_level_keys(relative) | self.real_keys(name)
            for name, relative in SCHEMA_TEMPLATES.items()
        }
        real = {name: self.real_documents(name) for name in SCHEMA_TEMPLATES}
        template_docs = {
            name: data_records(SUITE / "skills" / relative)
            for name, relative in SCHEMA_TEMPLATES.items()
        }
        checked = 0
        unknown: set[str] = set()
        paths = sorted((SUITE / "skills").rglob("assets/*"))
        paths += [
            SUITE / "tests/fixtures/authoring-records" / name
            for name in (
                "coverage-template.json", "shot-template.jsonl", "keyframe-template.jsonl",
                "episode-card.json", "episode-card-standalone.json", "beats.jsonl",
            )
        ]
        for path in paths:
            if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
                continue
            for location, artifact, _record_id, pointer in iter_pointer_claims(path):
                if artifact.rsplit("/", 1)[-1] in GENERATED_TARGETS:
                    continue
                name = self.schema_name(artifact)
                if name is None:
                    unknown.add(f"{path.relative_to(SUITE)}:{location} -> {artifact}")
                    continue
                # A template may offer a menu -- `/start_boundary | /end_boundary`
                # -- so every alternative is checked rather than the whole
                # string being treated as one pointer.
                for alternative in pointer.split("|"):
                    target = alternative.strip()
                    head = target.lstrip("/").split("/")[0]
                    if not head:
                        continue
                    checked += 1
                    # Where a real accepted artifact exists, the whole pointer is
                    # walked: checking only the first segment let a broken leaf
                    # such as `/creator_authority/visual_direction_GONE` pass.
                    # Either source may legitimately lack the other's records:
                    # the shipped example shows one variant, and the reference
                    # run only exercises the features that run used. A pointer
                    # resolving in neither is what a removed field looks like.
                    concrete = real[name] + template_docs[name]
                    if concrete:
                        self.assertTrue(
                            any(
                                pointer_resolves(document, target)
                                for document in concrete
                            ),
                            f"{path.relative_to(SUITE)}:{location}: {target} "
                            f"resolves in no {name} record, in the shipped "
                            f"template or in the reference run",
                        )
                        continue
                    self.assertIn(
                        head,
                        keys[name],
                        f"{path.relative_to(SUITE)}:{location}: {target} "
                        f"names a field {name} no longer carries",
                    )
        self.assertEqual(
            unknown,
            set(),
            "a shipped pointer names an artifact with no entry in "
            "SCHEMA_TEMPLATES; add its schema there rather than leaving the "
            "pointer unchecked",
        )
        self.assertGreater(checked, 0, "no template pointers were checked")


if __name__ == "__main__":
    unittest.main()
