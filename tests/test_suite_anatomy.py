import json
import re
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
CORE = SUITE / "skills/short-drama"

EXPECTED_SKILLS = {
    "short-drama",
    "short-drama-novel-analyze",
    "short-drama-develop",
    "short-drama-write",
    "short-drama-assets",
    "short-drama-image-prompts",
    "short-drama-storyboard",
    "short-drama-video-prompts",
    "short-drama-produce",
    "short-drama-edit",
    "short-drama-review",
}


# A reference now names its upstream; bytes are no longer carried in the
# authoring chain, so the canonical pair is owner+artifact.
REF_PAIR = {"owner", "artifact"}
FENCED_RECORD = re.compile(r"```jsonl?\n(\{.*?\})\n```", re.S)

# A ``*.fragment.json`` is pasted into a host record, so its ``src`` keys are
# declared by the host file rather than by the fragment itself.
FRAGMENT_SUFFIX = ".fragment.json"


LINK_RE = re.compile(r"\[[^]]+\]\(([^)#]+)(?:#([^)]+))?\)")


def local_markdown_targets(markdown: Path) -> list[str]:
    text = markdown.read_text(encoding="utf-8")
    return [
        target for target, _fragment in LINK_RE.findall(text) if "://" not in target
    ]


def local_markdown_anchors(markdown: Path) -> list[tuple[str, str]]:
    """(target, fragment) for every local link that names a heading."""

    text = markdown.read_text(encoding="utf-8")
    return [
        (target, fragment)
        for target, fragment in LINK_RE.findall(text)
        if fragment and "://" not in target
    ]


def heading_anchors(markdown: Path) -> set[str]:
    """GitHub-style anchors for a file's headings.

    Lowercased, spaces to hyphens, punctuation dropped. CJK headings keep their
    characters, which is how a link to a Chinese heading is written.
    """

    anchors: set[str] = set()
    for line in markdown.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            continue
        title = line.lstrip("#").strip()
        slug = "".join(
            character
            for character in title.lower().replace(" ", "-")
            if character.isalnum() or character in {"-", "_"}
        )
        if slug:
            anchors.add(slug)
    return anchors


def shipped_records(path: Path) -> list[Any]:
    """Every JSON document a shipped file carries.

    One document per ``.json`` file, one per ``.jsonl`` line, one per fenced
    record in a Markdown template.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if path.suffix == ".json":
        return [json.loads(text)]
    return [json.loads(block) for block in FENCED_RECORD.findall(text)]


def declared_sources(records: list[Any]) -> dict[str, Any]:
    """The upstream snapshots a file declares, gathered from all of its records."""
    sources: dict[str, Any] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("sources"), dict):
                sources.update(node["sources"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    for record in records:
        walk(record)
    return sources


def expand_refs(node: Any, sources: dict[str, Any]) -> Any:
    """Replace every compact reference with the snapshot its file declares.

    Assertions downstream then read ``owner``/``artifact``/``hash`` off any
    reference without caring which form the file was written in, and a ``src``
    naming nothing stays compact so the shape check can report it.
    """
    if isinstance(node, list):
        return [expand_refs(item, sources) for item in node]
    if not isinstance(node, dict):
        return node
    rest = {key: expand_refs(value, sources) for key, value in node.items() if key != "src"}
    src = node.get("src")
    if isinstance(src, str):
        entry = sources.get(src)
        if isinstance(entry, dict) and REF_PAIR.issubset(entry):
            return {key: entry[key] for key in ("owner", "artifact")} | rest
        return dict(node)
    return rest


def resolved_records(path: Path) -> list[Any]:
    """A shipped file's records with every reference resolved to its snapshot."""
    records = shipped_records(path)
    sources = declared_sources(records)
    return [expand_refs(record, sources) for record in records]


def record_with(path: Path, key: str) -> dict[str, Any]:
    """The one resolved record in ``path`` that carries ``key``.

    Selecting by content rather than by line number keeps these assertions
    stable when a file gains or loses a leading declaration record.
    """
    for record in resolved_records(path):
        if isinstance(record, dict) and key in record:
            return record
    raise AssertionError(f"{path}: no record carries {key!r}")


def is_declaration(record: Any) -> bool:
    """True for a record that only declares upstream snapshots."""
    return isinstance(record, dict) and set(record) <= {
        "record_type",
        "schema_version",
        "sources",
    }


def fenced_json(path: Path) -> dict[str, Any]:
    """The first fenced record of a Markdown template, references resolved.

    A template opens with its ``sources`` declaration; the record the callers
    want is the first fenced block after it.
    """
    for record in resolved_records(path):
        if isinstance(record, dict) and not is_declaration(record):
            return record
    raise AssertionError(f"{path}: missing fenced JSON object")


def resolve_json_pointer(document: object, pointer: str) -> object:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"not an RFC 6901 pointer: {pointer}")
    current = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif (
            isinstance(current, list)
            and re.fullmatch(r"(?:0|[1-9][0-9]*)", token) is not None
            and int(token) < len(current)
        ):
            current = current[int(token)]
        else:
            raise KeyError(pointer)
    return current


class SuiteAnatomyTests(unittest.TestCase):
    def test_exact_public_skill_set(self) -> None:
        actual = {path.name for path in (SUITE / "skills").iterdir() if path.is_dir()}
        self.assertEqual(actual, EXPECTED_SKILLS)

    def test_markdown_links_resolve_one_hop(self) -> None:
        for markdown in (SUITE / "skills").glob("*/SKILL.md"):
            for target in local_markdown_targets(markdown):
                self.assertTrue((markdown.parent / target).is_file(), f"{markdown}: {target}")

    def test_markdown_link_anchors_name_a_real_heading(self) -> None:
        """The fragment was stripped before checking, so anchors never resolved.

        `short-drama/SKILL.md` linked `contract-and-ownership.md#输出语言契约`
        from the day that file was written; the file is in English and its
        heading is `## Output language contract`. The link resolved to the file
        and landed nowhere.
        """

        for markdown in sorted((SUITE / "skills").rglob("*.md")):
            for target, fragment in local_markdown_anchors(markdown):
                destination = markdown.parent / target
                if not destination.is_file() or destination.suffix != ".md":
                    continue
                with self.subTest(source=str(markdown.relative_to(SUITE)), link=target):
                    self.assertIn(
                        fragment.lower(),
                        heading_anchors(destination),
                        f"{markdown.relative_to(SUITE)} links #{fragment} in "
                        f"{target}, which has no such heading",
                    )

    def test_deterministic_validators_are_linked_from_their_owning_skills(self) -> None:
        # Creator-first authoring skills operate directly on the five Markdown
        # documents. Only tools that remain part of the public workflow belong
        # in SKILL.md; historical JSON fixtures are still exercised separately.
        expected = {
            "short-drama-novel-analyze": {"scripts/novel_index.py"},
            "short-drama-produce": {"scripts/production_tool.py"},
            "short-drama-edit": {"scripts/edit_tool.py"},
        }
        for skill, validator_links in expected.items():
            skill_md = SUITE / "skills" / skill / "SKILL.md"
            linked_targets = set(local_markdown_targets(skill_md))
            self.assertTrue(
                validator_links <= linked_targets,
                f"{skill}: unlinked validators {sorted(validator_links - linked_targets)}",
            )

    def test_directly_linked_markdown_has_no_broken_second_hop(self) -> None:
        for skill_md in (SUITE / "skills").glob("*/SKILL.md"):
            for target in local_markdown_targets(skill_md):
                first_hop = (skill_md.parent / target).resolve()
                if first_hop.suffix.lower() != ".md":
                    continue
                for nested_target in local_markdown_targets(first_hop):
                    self.assertTrue(
                        (first_hop.parent / nested_target).is_file(),
                        f"{first_hop}: {nested_target}",
                    )

    def test_shipping_json_is_valid(self) -> None:
        for path in SUITE.rglob("*.json"):
            with self.subTest(path=path):
                json.loads(path.read_text(encoding="utf-8"))

    def test_structured_artifact_refs_use_one_canonical_shape(self) -> None:
        """Cross-layer stale propagation needs one parseable pointer contract.

        A reference either names a snapshot its own file declares under
        ``sources``, or inlines ``owner``/``artifact``/``hash``. Records are
        resolved before the check, so a ``src`` that no declaration covers
        arrives here still compact and fails.
        """

        legacy_keys = {"artifact_hash", "field_pointer", "accepted_snapshot_hash"}
        # Hand-maintained byte digests. Nothing verifies them, so they are a
        # second copy of lifecycle state that goes stale in silence; a template
        # carrying one hands that maintenance to every project built from it.
        retired_digest_keys = {
            "content_sha256",
            "input_hashes",
            "index_sha256",
            "map_sha256",
            "observed_media_sha256",
            "production_profile_hash",
            "prompt_or_spec_hashes",
            "record_hashes",
            "reference_slot_set_hash",
            "rendered_hash",
            "source_end_hash",
            "source_sha256",
            "target_hashes",
        }

        def check(document: object, path: Path, declares: bool, cursor: str = "") -> None:
            def canonical(reference: object) -> bool:
                if not isinstance(reference, dict):
                    return False
                # A fragment is pasted into a host record, so it carries a key
                # the host declares rather than a declaration of its own.
                if not declares and isinstance(reference.get("src"), str):
                    return True
                return REF_PAIR.issubset(reference)

            if isinstance(document, dict):
                self.assertFalse(
                    legacy_keys.intersection(document),
                    f"{path}:{cursor} uses a legacy reference alias",
                )
                self.assertFalse(
                    retired_digest_keys.intersection(document),
                    f"{path}:{cursor} carries a hand-maintained byte digest",
                )
                for key, value in document.items():
                    if (
                        key != "boundary_refs"
                        and (key.endswith("_ref") or key.endswith("_refs"))
                        and value is not None
                    ):
                        references = value if isinstance(value, list) else [value]
                        for reference in references:
                            self.assertIsInstance(reference, dict, f"{path}:{cursor}/{key}")
                            self.assertTrue(
                                canonical(reference),
                                f"{path}:{cursor}/{key} is not a canonical ArtifactRef",
                            )
                    if key == "boundary_refs":
                        self.assertIsInstance(value, dict, f"{path}:{cursor}/{key}")
                        for reference in value.values():
                            self.assertTrue(
                                canonical(reference),
                                f"{path}:{cursor}/{key} contains a noncanonical ref",
                            )
                    check(value, path, declares, f"{cursor}/{key}")
            elif isinstance(document, list):
                for index, value in enumerate(document):
                    check(value, path, declares, f"{cursor}/{index}")

        shipped = [
            path
            for path in (SUITE / "skills").rglob("*")
            if path.is_file() and path.suffix in {".json", ".jsonl"}
        ]
        shipped += sorted((SUITE / "skills").glob("*/assets/*.md"))
        for path in shipped:
            declares = not path.name.endswith(FRAGMENT_SUFFIX)
            for document in resolved_records(path):
                check(document, path, declares)

    def test_no_shipped_markdown_reintroduces_a_retired_digest_key(self) -> None:
        """The reference docs are where a retired key can come back unseen.

        `test_structured_artifact_refs_use_one_canonical_shape` parses JSON, so it
        only reaches `*.json`, `*.jsonl` and `*/assets/*.md`. A fenced block in a
        `references/*.md` slipped through — which is how `derivation` carried 196
        stale digests across several releases. A literal-token scan closes it
        without parsing anything.
        """
        retired = (
            "content_sha256",
            "index_sha256",
            "input_hashes",
            "map_sha256",
            "observed_media_sha256",
            "production_profile_hash",
            "prompt_or_spec_hashes",
            "record_hashes",
            "reference_slot_set_hash",
            "rendered_hash",
            "source_end_hash",
            "source_sha256",
            "target_hashes",
        )
        for path in sorted((SUITE / "skills").rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            for key in retired:
                with self.subTest(path=str(path.relative_to(SUITE)), key=key):
                    self.assertNotIn(key, text)

    def test_cross_template_json_pointers_resolve(self) -> None:
        project = resolved_records(CORE / "assets/project-template/short-drama.json")[0]
        shot = record_with(
            SUITE / "skills/short-drama-storyboard/assets/shot-template.jsonl", "shot_id"
        )
        documents = {
            "delivery_container": fenced_json(
                SUITE
                / "skills/short-drama-video-prompts/assets/delivery-container.jsonl.md"
            ),
            "motion": fenced_json(
                SUITE
                / "skills/short-drama-video-prompts/assets/motion-spec.jsonl.md"
            ),
            "shot": shot,
            "keyframe": record_with(
                SUITE / "skills/short-drama-storyboard/assets/keyframe-template.jsonl",
                "keyframe_id",
            ),
            "coverage": resolved_records(
                SUITE / "skills/short-drama-storyboard/assets/coverage-template.json"
            )[0],
        }
        targets = {
            "short-drama.json": project,
            "剧集/<EP>/storyboard/shots.jsonl": shot,
        }
        for path in sorted(
            (SUITE / "skills/short-drama-assets/assets").glob("*.jsonl")
        ):
            for example in resolved_records(path):
                destination = example.get("destination")
                if isinstance(destination, str):
                    targets.setdefault(destination, example)

        for path in sorted((SUITE / "skills").glob("*/assets/*.md")):
            for index, document in enumerate(resolved_records(path)):
                documents.setdefault(f"{path.relative_to(SUITE)}:{index}", document)

        expected_refs = [
            (
                "delivery_container",
                ("members", 0, "accepted_duration_ref"),
                "short-drama-storyboard",
                "剧集/<EP>/storyboard/shots.jsonl",
                "/duration_seconds",
            ),
            (
                "delivery_container",
                ("members", 0, "location_binding_ref"),
                "short-drama-storyboard",
                "剧集/<EP>/storyboard/shots.jsonl",
                "/location_binding",
            ),
            (
                "delivery_container",
                ("members", 0, "asset_bindings_ref"),
                "short-drama-storyboard",
                "剧集/<EP>/storyboard/shots.jsonl",
                "/asset_bindings",
            ),
            (
                "shot",
                ("delivery_surface_ref",),
                "short-drama",
                "short-drama.json",
                "/creator_authority/delivery_surface",
            ),
            (
                "keyframe",
                ("delivery_surface_ref",),
                "short-drama",
                "short-drama.json",
                "/creator_authority/delivery_surface",
            ),
            (
                "coverage",
                ("episode_duration", "target_ref"),
                "short-drama",
                "short-drama.json",
                "/format/target_seconds_per_episode",
            ),
            (
                "keyframe",
                ("boundary_ref",),
                "short-drama-storyboard",
                "剧集/<EP>/storyboard/shots.jsonl",
                "/start_boundary | /end_boundary",
            ),
        ]

        for source, ref_path, owner, artifact, field in expected_refs:
            value: object = documents[source]
            for token in ref_path:
                if isinstance(token, int):
                    if not isinstance(value, list):
                        self.fail(f"{source}{ref_path}: expected list at {token}")
                    value = value[token]
                else:
                    if not isinstance(value, dict):
                        self.fail(f"{source}{ref_path}: expected object at {token}")
                    value = value[token]
            if not isinstance(value, dict):
                self.fail(f"{source}{ref_path}: expected artifact reference")
            self.assertEqual(value.get("owner"), owner)
            self.assertEqual(value.get("artifact"), artifact)
            self.assertEqual(value.get("field"), field)

        def check(value: object) -> None:
            if isinstance(value, dict):
                artifact = value.get("artifact")
                field = value.get("field")
                if (
                    isinstance(artifact, str)
                    and artifact in targets
                    and isinstance(field, str)
                ):
                    for pointer in (part.strip() for part in field.split("|")):
                        with self.subTest(artifact=artifact, pointer=pointer):
                            resolve_json_pointer(targets[artifact], pointer)
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)

        for document in documents.values():
            check(document)

    def test_delivery_container_and_motion_refs_are_acyclic(self) -> None:
        templates = {
            "剧集/<EP>/storyboard/delivery-containers.jsonl": fenced_json(
                SUITE
                / "skills/short-drama-video-prompts/assets/delivery-container.jsonl.md"
            ),
            "剧集/<EP>/storyboard/motion-specs.jsonl": fenced_json(
                SUITE
                / "skills/short-drama-video-prompts/assets/motion-spec.jsonl.md"
            ),
        }
        edges: dict[str, set[str]] = {source: set() for source in templates}

        def collect(source: str, value: object) -> None:
            if isinstance(value, dict):
                artifact = value.get("artifact")
                if isinstance(artifact, str) and artifact in templates:
                    edges[source].add(artifact)
                for child in value.values():
                    collect(source, child)
            elif isinstance(value, list):
                for child in value:
                    collect(source, child)

        for source, document in templates.items():
            collect(source, document)

        container_file = "剧集/<EP>/storyboard/delivery-containers.jsonl"
        motion_file = "剧集/<EP>/storyboard/motion-specs.jsonl"
        self.assertIn(motion_file, edges[container_file])

        def visit(node: str, active: tuple[str, ...], complete: set[str]) -> None:
            if node in active:
                self.fail("reference cycle: " + " -> ".join((*active, node)))
            if node in complete:
                return
            for target in edges[node]:
                visit(target, (*active, node), complete)
            complete.add(node)

        complete: set[str] = set()
        for source in templates:
            visit(source, (), complete)

    def test_asset_template_derivation_graph_has_no_self_ref_or_cycle(self) -> None:
        """Derivation must be a DAG; cross-naming between peers need not be.

        Edges come from ``sources`` -- the artifacts a file was built from --
        not from every artifact a record happens to mention. An occurrence may
        name the decision it feeds while that decision names the occurrence it
        consumes: with byte digests gone from the chain there is nothing
        impossible about two peers naming each other, only about one being
        derived from the other in both directions.
        """
        templates = SUITE / "skills/short-drama-assets/assets"
        edges: set[tuple[str, str]] = set()
        for path in templates.glob("*.jsonl"):
            for document in resolved_records(path):
                source = document.get("destination")
                if not isinstance(source, str):
                    continue
                for entry in (document.get("sources") or {}).values():
                    artifact = entry.get("artifact") if isinstance(entry, dict) else None
                    if not isinstance(artifact, str):
                        continue
                    self.assertNotEqual(
                        artifact,
                        source,
                        f"{path.name} declares itself as its own source",
                    )
                    if artifact.startswith(("设定集/", "剧集/", "bible/", "episodes/")):
                        edges.add((source, artifact))

        graph: dict[str, set[str]] = {}
        for source, target in edges:
            graph.setdefault(source, set()).add(target)

        def visit(node: str, active: tuple[str, ...], complete: set[str]) -> None:
            if node in active:
                cycle = " -> ".join((*active, node))
                self.fail(f"derivation cycle: {cycle}")
            if node in complete:
                return
            for target in graph.get(node, set()):
                visit(target, (*active, node), complete)
            complete.add(node)

        complete: set[str] = set()
        for node in graph:
            visit(node, (), complete)

    def test_candidate_templates_distinguish_inputs_from_same_publication_refs(self) -> None:
        templates: list[tuple[Path, dict[str, Any]]] = []
        for relative in (
            "skills/short-drama-storyboard/assets/coverage-template.json",
            "skills/short-drama-storyboard/assets/shot-template.jsonl",
            "skills/short-drama-storyboard/assets/keyframe-template.jsonl",
        ):
            path = SUITE / relative
            templates.append((path, record_with(path, "status")))
        for relative in (
            "skills/short-drama-image-prompts/assets/image-prompt-spec.jsonl.md",
            "skills/short-drama-video-prompts/assets/motion-spec.jsonl.md",
        ):
            path = SUITE / relative
            templates.append((path, fenced_json(path)))

        candidate_ref_owners = {
            "coverage-template.json": {"short-drama-storyboard"},
            "shot-template.jsonl": set(),
            "keyframe-template.jsonl": {"short-drama-storyboard"},
            "image-prompt-spec.jsonl.md": set(),
            "motion-spec.jsonl.md": set(),
        }
        for path, document in templates:
            self.assertEqual(document.get("status"), "candidate", path)

            observed_candidate_owners: set[str] = set()

            def check(value: object, cursor: str = "") -> None:
                if isinstance(value, dict):
                    if {"owner", "artifact"}.issubset(value):
                        authority = value.get("authority")
                        self.assertIn(authority, {None, "candidate"}, f"{path}:{cursor}")
                        if authority == "candidate":
                            observed_candidate_owners.add(str(value["owner"]))
                    for key, child in value.items():
                        check(child, f"{cursor}/{key}")
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        check(child, f"{cursor}/{index}")

            check(document)

            self.assertEqual(
                observed_candidate_owners,
                candidate_ref_owners[path.name],
                f"{path}: candidate authority is only for co-published targets",
            )

        project = json.loads(
            (SUITE / "skills/short-drama/assets/project-template/short-drama.json")
            .read_text(encoding="utf-8")
        )
        authority = project["creator_authority"]
        self.assertEqual(authority["decisions_artifact"], "创作者决策/")
        self.assertEqual(authority["visual_direction"]["status"], "unset")
        self.assertEqual(authority["production_profile"]["status"], "unset")
        self.assertTrue(
            (SUITE / "skills/short-drama/assets/creator-decision.example.jsonl").is_file()
        )

    def test_review_templates_bind_evidence_targets_and_verdict_snapshot(self) -> None:
        finding = record_with(
            SUITE / "skills/short-drama-review/assets/finding-template.jsonl", "target_ref"
        )
        self.assertGreaterEqual(len(finding["evidence_refs"]), 2)
        self.assertTrue(REF_PAIR.issubset(finding["target_ref"]))
        verdict = resolved_records(
            SUITE / "skills/short-drama-review/assets/verdict-template.json"
        )[0]
        self.assertTrue(verdict["reviewed_artifacts"])
        self.assertTrue(REF_PAIR.issubset(verdict["findings_ref"]))
        self.assertEqual(verdict["open_blocker_count"], 0)
        self.assertEqual(verdict["review_method"], "uninvolved_reviewer | self_check")
        self.assertIsInstance(verdict["reviewer"], str)
        self.assertEqual(verdict["structural_validation"], "not_run")
        self.assertEqual(verdict["verdict"], "PROVISIONAL")

    def test_template_field_refs_resolve_to_owned_example_fields(self) -> None:
        keyframe = record_with(
            SUITE / "skills/short-drama-storyboard/assets/keyframe-template.jsonl",
            "light_projection",
        )
        view = record_with(
            SUITE / "skills/short-drama-assets/assets/location-view.example.jsonl",
            "state_differences",
        )
        light_ref = keyframe["light_projection"]["source_ref"]
        self.assertEqual(light_ref["artifact"], "设定集/location-views.jsonl")
        self.assertEqual(light_ref["field"], "/state_differences/light")
        self.assertIn("light", view["state_differences"])

        image_spec = fenced_json(
            SUITE / "skills/short-drama-image-prompts/assets/image-prompt-spec.jsonl.md"
        )
        policy_ref = image_spec["text_handling"]["source_policy_ref"]
        prop = record_with(
            SUITE / "skills/short-drama-assets/assets/prop-state.example.jsonl",
            "text_policy",
        )
        self.assertEqual(policy_ref["artifact"], "设定集/props.jsonl")
        self.assertEqual(policy_ref["field"], "/text_policy")
        self.assertIn("text_policy", prop)

if __name__ == "__main__":
    unittest.main()


class DiagnosticCatalogueTests(unittest.TestCase):
    """Every public checker code must appear in its skill's public guidance.

    Retired JSON fixture checkers remain executable for maintainer regression,
    but creator-first SKILL.md files must not advertise their diagnostics.
    """

    CODE_RE = re.compile(r'_finding\(\s*"([A-Z][A-Z0-9]*_[A-Z0-9_]+)"')

    def emitted_codes(self, scripts: set[Path]) -> set[str]:
        codes: set[str] = set()
        for script in sorted(scripts):
            codes |= set(self.CODE_RE.findall(script.read_text(encoding="utf-8")))
        return codes

    def test_every_emitted_code_is_catalogued(self) -> None:
        for skill in sorted((SUITE / "skills").iterdir()):
            if not skill.is_dir():
                continue
            skill_md = skill / "SKILL.md"
            linked_scripts = {
                (skill / target).resolve()
                for target in local_markdown_targets(skill_md)
                if target.endswith(".py") and (skill / target).is_file()
            }
            emitted = self.emitted_codes(linked_scripts)
            if not emitted:
                continue
            catalogue = "\n".join(
                path.read_text(encoding="utf-8") for path in sorted(skill.rglob("*.md"))
            )
            missing = sorted(code for code in emitted if code not in catalogue)
            with self.subTest(skill=skill.name):
                self.assertEqual(
                    missing,
                    [],
                    f"{skill.name} emits codes no reference document lists",
                )


class MarkdownBoldRunTests(unittest.TestCase):
    """A bold run must actually render as bold on GitHub.

    CommonMark closes `**` only when the run is right-flanking: a `**` preceded
    by punctuation must be followed by whitespace or punctuation. `**文本。**后续`
    fails both halves of that -- preceded by `。`, followed by a letter -- so the
    markers render literally. It reads fine in an editor and breaks on the
    release page, which is where the v0.5.0 notes were caught.

    The fix is to put the punctuation outside the run: `**文本**。后续`.
    """

    # Delimiters are paired in document order rather than matched by a regex:
    # a pattern spanning `**A**。 prose：**B**` reads the close of one run and the
    # open of the next as a pair and reports a false positive.
    CLOSING_PUNCTUATION = "。：；？！"
    SAFE_AFTER = set(" \t\n*，。、；：？！）】」』`）")

    # Recorded creator prose, not shipped documentation. The reference run is a
    # record of what one run produced; its wording is not this suite's to edit.
    EXCLUDED = ("evaluations/让你管账号/reference-run",)

    def shipped_markdown(self) -> list[Path]:
        files = [
            SUITE / name
            for name in (
                "README.md", "README_EN.md", "CHANGELOG.md",
                "CONTRIBUTING.md", "DESIGN.md",
            )
        ]
        for root in ("skills", "evaluations", "examples", "docs", "maintainers"):
            files.extend(sorted((SUITE / root).rglob("*.md")))
        return [
            path
            for path in files
            if path.is_file()
            and not any(part in str(path) for part in self.EXCLUDED)
        ]

    def unclosable_runs(self, text: str) -> list[str]:
        broken: list[str] = []
        for line in text.splitlines():
            positions = []
            index = line.find("**")
            while index != -1:
                positions.append(index)
                index = line.find("**", index + 2)
            # Even positions open a run, odd positions close it.
            for opening, closing in zip(positions[::2], positions[1::2]):
                content = line[opening + 2:closing]
                after = line[closing + 2:closing + 3]
                if (
                    content
                    and content[-1] in self.CLOSING_PUNCTUATION
                    and after
                    and after not in self.SAFE_AFTER
                ):
                    broken.append(line[opening:closing + 8])
        return broken

    def test_no_shipped_document_carries_an_unclosable_bold_run(self) -> None:
        for path in self.shipped_markdown():
            broken = self.unclosable_runs(path.read_text(encoding="utf-8"))
            with self.subTest(path=str(path.relative_to(SUITE))):
                self.assertEqual(
                    broken,
                    [],
                    f"{path.relative_to(SUITE)}: a bold run ends with punctuation "
                    f"inside the markers, so it renders literally on GitHub; move "
                    f"the punctuation outside",
                )
