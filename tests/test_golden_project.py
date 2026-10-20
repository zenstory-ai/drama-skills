from __future__ import annotations

import importlib.util
import io
import json
import re
import shutil
import tempfile
import unicodedata
import unittest
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Iterator


SUITE = Path(__file__).resolve().parents[1]
EXAMPLES = SUITE / "examples"
GOLDEN = SUITE / "examples/golden-project"
CREATOR_FIRST = SUITE / "examples/creator-first"
CORE = SUITE / "skills/short-drama"


def load_module(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SUITE / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


project_tool = load_module("golden_project_tool", "skills/short-drama/scripts/project_tool.py")
screenplay_index = load_module(
    "golden_screenplay_index", "skills/short-drama-write/scripts/screenplay_index.py"
)
asset_check = load_module(
    "golden_asset_check", "tests/legacy/short-drama-assets/scripts/asset_check.py"
)
image_prompt_check = load_module(
    "golden_image_prompt_check",
    "tests/legacy/short-drama-image-prompts/scripts/image_prompt_check.py",
)
storyboard_check = load_module(
    "golden_storyboard_check",
    "tests/legacy/short-drama-storyboard/scripts/storyboard_check.py",
)
motion_timing_check = load_module(
    "golden_motion_timing_check",
    "tests/legacy/short-drama-video-prompts/scripts/motion_timing_check.py",
)
review_check = load_module(
    "golden_review_check", "tests/legacy/short-drama-review/scripts/review_check.py"
)
compact_refs = load_module("golden_compact_refs", "tools/compact_refs.py")


EPISODES = [f"EP{number:03d}" for number in range(1, 9)]
SHOT_COUNTS = [5, 3, 5, 4, 4, 5, 6, 5]
TEXT_SUFFIXES = {".json", ".jsonl", ".md"}
MEDIA_SUFFIXES = {
    ".aac",
    ".avi",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".pdf",
    ".png",
    ".wav",
    ".webm",
    ".webp",
    ".zip",
}
SENSITIVE_KEYS = {
    "_id",
    "created_at",
    "key",
    "model",
    "remote_id",
    "seed",
    "source_id",
    "task_id",
    "uid",
    "updated_at",
    "url",
    "userId",
}
SENSITIVE_TEXT = (
    "mongodb://",
    "http://",
    "https://",
    "/Users/",
    "C:\\Users\\",
)
# Byte digests the authoring chain used to carry by hand. Nothing ever verified
# them, so they were a second copy of lifecycle state that went stale in silence:
# `1313c97` removed the chain from references and missed `derivation`, which then
# shipped 196 rotten values for several releases. Tool-maintained byte records
# (lifecycle state, delivery checksums, source-drift digests) are unaffected.
RETIRED_DIGEST_KEYS = {
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
IPV4_LITERAL = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
LONG_DECIMAL_LITERAL = re.compile(r"(?<![A-Za-z0-9])\d{6,}(?![A-Za-z0-9])")


# A reference names its upstream. Bytes are no longer carried in the authoring
# chain, so identity is the owner/artifact pair.
REF_PAIR = ("owner", "artifact")
SOURCES_RECORD_TYPE = "sources"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def read_documents(path: Path) -> list[Any]:
    if path.suffix == ".jsonl":
        return list(read_jsonl(path))
    return [json.loads(path.read_text(encoding="utf-8"))]


def sources_of(documents: list[Any]) -> dict[str, Any]:
    """The upstream snapshots a file declares.

    A ``.json`` file declares them at the top level; a ``.jsonl`` file on its
    first record, either a dedicated ``sources`` header or its own ``_meta``
    record.
    """
    head = documents[0] if documents else None
    if isinstance(head, dict) and isinstance(head.get("sources"), dict):
        return head["sources"]
    return {}


def data_records(path: Path) -> list[dict[str, Any]]:
    """A file's records with any standalone ``sources`` declaration dropped.

    A declaration folded into an existing ``_meta`` record stays, because that
    record carries the file's own data too.
    """
    return [
        record
        for record in read_jsonl(path)
        if record.get("record_type") != SOURCES_RECORD_TYPE
    ]


def resolve_ref(reference: Any, sources: dict[str, Any]) -> dict[str, Any] | None:
    """The snapshot a reference names, in either the compact or expanded form.

    Returns ``None`` when the reference names nothing resolvable -- an undeclared
    ``src``, or neither form.
    """
    if not isinstance(reference, dict):
        return None
    src = reference.get("src")
    if isinstance(src, str):
        entry = sources.get(src)
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(key), str) for key in REF_PAIR
        ):
            return None
        return {key: entry[key] for key in REF_PAIR} | {
            key: value for key, value in reference.items() if key != "src"
        }
    if all(isinstance(reference.get(key), str) for key in REF_PAIR):
        return dict(reference)
    return None


def iter_refs(document: Any) -> Iterator[dict[str, Any]]:
    """Every upstream reference in a document, in either form.

    The ``sources`` declaration itself is skipped: its entries name snapshots
    but are not references, and counting them would hide a missing one.
    """
    if isinstance(document, list):
        for item in document:
            yield from iter_refs(item)
        return
    if not isinstance(document, dict):
        return
    if isinstance(document.get("src"), str) or all(
        isinstance(document.get(key), str) and document[key] for key in REF_PAIR
    ):
        yield document
        return
    for key, value in document.items():
        if key != "sources":
            yield from iter_refs(value)


def walk_values(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)


def record_with_id(records: list[dict[str, Any]], record_id: str) -> dict[str, Any] | None:
    for record in records:
        if record_id in record.values():
            return record
    return None


def resolve_pointer(value: Any, pointer: str) -> Any:
    current = value
    for raw in pointer.lstrip("/").split("/") if pointer != "/" else [""]:
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(pointer)
    return current


class GoldenProjectTests(unittest.TestCase):
    def test_has_exactly_eight_complete_episode_chains(self) -> None:
        episode_root = GOLDEN / "剧集"
        self.assertEqual([path.name for path in sorted(episode_root.iterdir())], EPISODES)
        required = {
            "episode-card.json",
            "beats.jsonl",
            "screenplay.md",
            "screenplay-index.jsonl",
            "assets/occurrences.jsonl",
            "assets/decisions.jsonl",
            "assets/continuity.jsonl",
            "assets/image-prompt-specs.jsonl",
            "assets/image-prompts.md",
            "storyboard/shots.jsonl",
            "storyboard/coverage.json",
            "storyboard/keyframes.jsonl",
            "storyboard/keyframe-prompts.md",
            "storyboard/motion-specs.jsonl",
            "storyboard/video-prompts.md",
        }
        for episode, shot_count in zip(EPISODES, SHOT_COUNTS):
            with self.subTest(episode=episode):
                root = episode_root / episode
                actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
                self.assertEqual(actual, required)
                shots = data_records(root / "storyboard/shots.jsonl")
                self.assertEqual(len(shots), shot_count)
                self.assertTrue(all(shot["duration_seconds"] == 15 for shot in shots))
                self.assertEqual(sum(shot["duration_seconds"] for shot in shots), [75, 45, 75, 60, 60, 75, 90, 75][EPISODES.index(episode)])

    def test_fixture_is_portable_utf8_text_and_json_only(self) -> None:
        for path in GOLDEN.rglob("*"):
            relative = path.relative_to(GOLDEN).as_posix()
            with self.subTest(path=relative):
                self.assertFalse(path.is_symlink())
                self.assertEqual(relative, unicodedata.normalize("NFC", relative))
                self.assertNotIn("..", PurePosixPath(relative).parts)
                if not path.is_file():
                    continue
                self.assertIn(path.suffix, TEXT_SUFFIXES)
                text = path.read_bytes().decode("utf-8")
                self.assertNotIn("\x00", text)
                if path.suffix == ".json":
                    self.assertIsInstance(json.loads(text), dict)
                elif path.suffix == ".jsonl":
                    self.assertTrue(read_jsonl(path), relative)

    def test_fixture_contains_no_sensitive_fields_placeholders_or_media(self) -> None:
        placeholder = re.compile(r"<[^>\n]+>")
        for path in EXAMPLES.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(EXAMPLES).as_posix()
            with self.subTest(path=relative):
                self.assertNotIn(path.suffix.casefold(), MEDIA_SUFFIXES)
                text = path.read_text(encoding="utf-8")
                for needle in SENSITIVE_TEXT:
                    self.assertNotIn(needle, text)
                self.assertNotRegex(text, IPV4_LITERAL)
                self.assertNotRegex(text, LONG_DECIMAL_LITERAL)
                self.assertNotRegex(text, placeholder)
                if path.suffix == ".json":
                    documents = [json.loads(text)]
                elif path.suffix == ".jsonl":
                    documents = read_jsonl(path)
                else:
                    documents = []
                for value in walk_values(documents):
                    if isinstance(value, dict):
                        self.assertFalse(SENSITIVE_KEYS.intersection(value), relative)
                        self.assertFalse(
                            RETIRED_DIGEST_KEYS.intersection(value),
                            f"{relative} carries a hand-maintained byte digest",
                        )

    def test_screenplay_indexes_are_clean_and_byte_for_byte_rebuildable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            for episode in EPISODES:
                with self.subTest(episode=episode):
                    root = GOLDEN / f"剧集/{episode}"
                    existing = root / "screenplay-index.jsonl"
                    meta = read_jsonl(existing)[0]
                    self.assertEqual(meta["review_status"], "clean")
                    speakers = json.loads((root / "episode-card.json").read_text(encoding="utf-8"))["speaker_roster"]
                    rebuilt = output_root / f"{episode}.jsonl"
                    screenplay_index.build_index(
                        root / "screenplay.md",
                        rebuilt,
                        source_ref=f"剧集/{episode}/screenplay.md",
                        speakers=speakers,
                    )
                    self.assertEqual(rebuilt.read_bytes(), existing.read_bytes())

    def test_every_direct_reference_resolves_to_a_real_file(self) -> None:
        """Every reference names a real file that really exists.

        References are compact: the file declares each upstream snapshot once
        under ``sources`` and each reference names it by key. Resolving here
        rather than reading ``owner``/``artifact`` off the reference is what
        makes an undeclared ``src`` a failure instead of a skipped record.
        """
        checked = 0
        for source in GOLDEN.rglob("*"):
            if not source.is_file() or source.suffix not in {".json", ".jsonl"}:
                continue
            documents = read_documents(source)
            sources = sources_of(documents)
            for reference in iter_refs(documents):
                value = resolve_ref(reference, sources)
                self.assertIsNotNone(value, f"{source}: unresolvable reference {reference}")
                assert value is not None
                checked += 1
                artifact = PurePosixPath(value["artifact"])
                self.assertFalse(artifact.is_absolute(), source)
                self.assertNotIn("..", artifact.parts, source)
                target = GOLDEN / artifact
                self.assertTrue(target.is_file(), f"{source}: {artifact}")
                record: Any = None
                if target.suffix == ".jsonl" and "record_id" in value:
                    record = record_with_id(data_records(target), value["record_id"])
                    self.assertIsNotNone(record, f"{source}: {artifact}#{value['record_id']}")
                elif target.suffix == ".json":
                    record = json.loads(target.read_text(encoding="utf-8"))
                    if "record_id" in value:
                        self.assertIn(value["record_id"], list(walk_values(record)))
                elif target.suffix == ".md" and "record_id" in value:
                    self.assertIn(
                        value["record_id"],
                        target.read_text(encoding="utf-8"),
                        f"{source}: {artifact}#{value['record_id']}",
                    )
                if "field" in value and record is not None:
                    try:
                        resolve_pointer(record, value["field"])
                    except (KeyError, IndexError, TypeError, ValueError) as error:
                        self.fail(f"{source}: unresolved field {artifact}{value['field']}: {error}")
        # Well above the ~570 declared snapshots, so a walk that found only the
        # declarations and none of the references could not pass this.
        self.assertGreater(checked, 2000)

    def assert_every_checker_passes(self, project: Path) -> None:
        assets = asset_check.validate_files(
            project / "设定集/characters.jsonl", project / "设定集/looks.jsonl"
        )
        self.assertEqual(assets["status"], "valid")
        for episode in EPISODES:
            with self.subTest(episode=episode):
                root = project / f"剧集/{episode}"
                self.assertEqual(
                    image_prompt_check.validate_file(root / "assets/image-prompt-specs.jsonl")["status"],
                    "valid",
                )
                # The screenplay index is passed on purpose: it turns on the
                # block-coverage check, so every shipped episode proves that
                # each screenplay block is filmed exactly once. Leaving it off
                # is how a coverage checker built on the wrong field once
                # looked healthy against a project it could not actually read.
                storyboard = storyboard_check.check(
                    root / "storyboard/coverage.json",
                    root / "storyboard/shots.jsonl",
                    root / "storyboard/keyframes.jsonl",
                    project / "short-drama.json",
                    root / "screenplay-index.jsonl",
                )
                self.assertEqual(storyboard["status"], "pass", storyboard.get("findings"))
                motion = motion_timing_check.check(
                    motion_timing_check._load_jsonl(root / "storyboard/motion-specs.jsonl"),
                    motion_timing_check._load_jsonl(root / "storyboard/shots.jsonl"),
                )
                self.assertEqual(motion["status"], "pass")
                self.assertEqual(motion["explicit_checked"], SHOT_COUNTS[EPISODES.index(episode)])
        review = review_check.validate_files(
            project / "审查/findings.jsonl", project / "审查/verdict.json"
        )
        self.assertEqual(review["verdict"], "APPROVE_WITH_NOTES")
        self.assertEqual(review["open_blockers"], 0)

    def test_each_skill_checker_accepts_its_own_golden_artifacts(self) -> None:
        self.assert_every_checker_passes(GOLDEN)

    def test_each_skill_checker_accepts_the_legacy_expanded_reference_form(self) -> None:
        """Projects published before the compact form still exist on creators' disks.

        Their references inline ``owner``/``artifact``/``hash`` and their files
        declare no ``sources``. Every checker must keep reading them, so the
        golden project is rewritten back to that form and re-checked.
        """
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / "legacy"
            shutil.copytree(GOLDEN, legacy)
            expanded = 0
            for path in compact_refs.iter_data_files(legacy):
                loaded = compact_refs.load_file(path, legacy)
                if loaded is None:
                    continue
                declared = compact_refs.load_sources(loaded.records)
                if not declared:
                    continue
                records, _mode, _position = compact_refs.strip_sources(loaded)
                records = [compact_refs.expand_refs(record, declared) for record in records]
                path.write_bytes(compact_refs.render(records, loaded.fmt).encode("utf-8"))
                expanded += 1
            self.assertGreater(expanded, 50)
            for path in compact_refs.iter_data_files(legacy):
                self.assertNotIn('"src"', path.read_text(encoding="utf-8"), path)
            self.assert_every_checker_passes(legacy)

    def test_migrating_an_already_compact_project_changes_nothing(self) -> None:
        """The migration is idempotent, and the shipped tree is its fixed point.

        ``--check`` is the gate a creator runs: it fails on a reference that
        still inlines a snapshot, on a ``src`` no declaration covers, and on a
        declared hash that no longer matches the bytes it names.
        """
        self.assertEqual(compact_refs.check(GOLDEN), 0)
        with tempfile.TemporaryDirectory() as directory:
            again = Path(directory) / "again"
            shutil.copytree(GOLDEN, again)
            compact_refs.migrate(again)
            for path in sorted(GOLDEN.rglob("*")):
                if path.is_file():
                    relative = path.relative_to(GOLDEN)
                    self.assertEqual(
                        (again / relative).read_bytes(), path.read_bytes(), relative
                    )

    def test_a_reference_naming_an_undeclared_source_is_reported(self) -> None:
        """A ``src`` with no ``sources`` entry must fail loudly, not resolve to nothing."""
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken"
            shutil.copytree(GOLDEN, broken)
            keyframes = broken / "剧集/EP001/storyboard/keyframes.jsonl"
            keyframes.write_text(
                keyframes.read_text(encoding="utf-8").replace(
                    '"boundary_ref":{"src":"', '"boundary_ref":{"src":"undeclared-'
                ),
                encoding="utf-8",
            )
            result = storyboard_check.check(
                broken / "剧集/EP001/storyboard/coverage.json",
                broken / "剧集/EP001/storyboard/shots.jsonl",
                keyframes,
                broken / "short-drama.json",
            )
            self.assertEqual(result["status"], "fail")
            self.assertIn(
                "REF_SRC_IS_NOT_DECLARED",
                {finding["code"] for finding in result["findings"]},
            )
            self.assertEqual(compact_refs.check(broken), 1)

    def test_findings_print_on_a_console_that_cannot_encode_project_paths(self) -> None:
        """Windows CI caught this: reporting a finding crashed instead of reporting it.

        Every path worth naming in a finding contains characters like 剧集, and a
        Windows console defaults to cp1252, so `print` raised UnicodeEncodeError
        from inside the reporting loop — the tool died on exactly the trees it
        existed to diagnose.
        """
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        compact_refs.emit("剧集/EP001/storyboard/keyframes.jsonl: REF_SRC_IS_NOT_DECLARED", stream=stream)
        stream.flush()
        written = stream.buffer.getvalue().decode("utf-8")  # type: ignore[attr-defined]
        self.assertIn("剧集/EP001/storyboard/keyframes.jsonl", written)

    def test_approved_review_is_bound_to_creator_accepted_artifacts_and_text_policy(self) -> None:
        acceptance_path = GOLDEN / "创作者决策/golden-production-acceptance.jsonl"
        decisions = data_records(acceptance_path)
        acceptance_sources = sources_of(read_jsonl(acceptance_path))
        self.assertEqual(len(decisions), 9)
        self.assertTrue(all(item["status"] == "accepted" for item in decisions))
        accepted = set()
        for decision in decisions:
            for reference in decision["accepted_artifact_refs"]:
                snapshot = resolve_ref(reference, acceptance_sources)
                self.assertIsNotNone(snapshot, f"{acceptance_path}: {reference}")
                assert snapshot is not None
                accepted.add(tuple(snapshot[key] for key in REF_PAIR))

        verdict_path = GOLDEN / "审查/verdict.json"
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        verdict_sources = sources_of([verdict])
        self.assertEqual(len(verdict["acceptance_refs"]), 9)
        for reference in verdict["reviewed_artifacts"]:
            snapshot = resolve_ref(reference, verdict_sources)
            self.assertIsNotNone(snapshot, f"{verdict_path}: {reference}")
            assert snapshot is not None
            with self.subTest(artifact=snapshot["artifact"]):
                self.assertEqual(snapshot.get("authority"), "accepted")
                self.assertIn(tuple(snapshot[key] for key in REF_PAIR), accepted)
                if snapshot["artifact"].endswith("motion-specs.jsonl"):
                    self.assertEqual(snapshot["owner"], "short-drama-video-prompts")

        props = {item["prop_id"]: item for item in data_records(GOLDEN / "设定集/props.jsonl")}
        for episode in EPISODES:
            specs = data_records(
                GOLDEN / f"剧集/{episode}/assets/image-prompt-specs.jsonl"
            )
            prop_spec = next(item for item in specs if item["purpose"] == "prop_plate")
            prop_id = prop_spec["asset_binding"]["identity_ref"]["record_id"]
            handling = prop_spec["text_handling"]
            with self.subTest(episode=episode, prop=prop_id):
                self.assertEqual(handling["source_mode"], props[prop_id]["text_policy"]["mode"])
                expected_render = (
                    "postproduction"
                    if handling["source_mode"] == "exact_readable"
                    else "blank"
                )
                self.assertEqual(handling["render_treatment"]["mode"], expected_render)

    def test_storyboard_states_and_motion_follow_their_source_blocks(self) -> None:
        states = {
            item["state_id"]: item
            for item in data_records(GOLDEN / "设定集/prop-states.jsonl")
        }
        characters = {
            item["display_name"]: item["character_id"]
            for item in data_records(GOLDEN / "设定集/characters.jsonl")
        }
        for episode in EPISODES:
            root = GOLDEN / f"剧集/{episode}"
            index = {
                item["block_id"]: item
                for item in read_jsonl(root / "screenplay-index.jsonl")
                if item.get("record_type") == "block"
            }
            shots = data_records(root / "storyboard/shots.jsonl")
            keyframes = data_records(root / "storyboard/keyframes.jsonl")
            motions = data_records(root / "storyboard/motion-specs.jsonl")
            by_boundary = {
                (item["boundary_ref"]["record_id"], item["boundary_role"]): item
                for item in keyframes
            }
            for position, (shot, motion) in enumerate(zip(shots, motions)):
                with self.subTest(episode=episode, shot=shot["shot_id"]):
                    transition = shot["state_transition"]
                    start_states = shot["start_boundary"]["visible_state"]
                    end_states = shot["end_boundary"]["visible_state"]
                    self.assertEqual(start_states, [] if transition["from"] is None else [transition["from"]])
                    self.assertEqual(end_states, [] if transition["to"] is None else [transition["to"]])
                    if position:
                        self.assertEqual(shots[position - 1]["state_transition"]["to"], transition["from"])
                    if transition["to"] != transition["from"] and transition["to"] is not None:
                        valid_from = states[transition["to"]]["validity"]["from"]
                        cause = valid_from.rsplit("/", 1)[-1]
                        self.assertIn(cause, {item["record_id"] for item in shot["source_refs"]})

                    for role, state_id in (("start", transition["from"]), ("end", transition["to"])):
                        frame = by_boundary[(shot["shot_id"], role)]
                        prop_variants = [
                            item["variant_ref"]["record_id"]
                            for item in frame["asset_bindings"]
                            if item["identity_ref"]["record_id"].startswith("PROP-")
                        ]
                        self.assertEqual(prop_variants, [] if state_id is None else [state_id])

                    shot_actors = {
                        item["identity_ref"]["record_id"]
                        for item in shot["asset_bindings"]
                        if item["identity_ref"]["record_id"].startswith("CHAR-")
                    }
                    motion_actors = {item["actor"] for item in motion["ordered_subject_motion"]}
                    self.assertTrue(motion_actors)
                    self.assertTrue(motion_actors.issubset(shot_actors))
                    source_ids = {item["record_id"] for item in shot["source_refs"]}
                    actions = []
                    for item in motion["ordered_subject_motion"]:
                        actions.append(item["action"])
                        self.assertNotIn(" / [", item["action"])
                        self.assertTrue(item["source_refs"])
                        self.assertTrue(
                            all(
                                index[source_ref["record_id"]]["kind"]
                                in {"action", "dialogue"}
                                for source_ref in item["source_refs"]
                            )
                        )
                        self.assertTrue(
                            {
                                source_ref["record_id"]
                                for source_ref in item["source_refs"]
                            }.issubset(source_ids)
                        )
                    self.assertTrue(
                        all(
                            "perform the shot's single visible story action" not in item["action"]
                            for item in motion["ordered_subject_motion"]
                        )
                    )
                    self.assertEqual(len(actions), len(set(actions)))

                    if shot["shot_id"] == "SHOT-EP001-05":
                        self.assertEqual(
                            {
                                item["actor"]: item["action"]
                                for item in motion["ordered_subject_motion"]
                            },
                            {
                                "CHAR-CHEN-YUAN": "陈予安在账本上写下一行。",
                                "CHAR-LIANG-FENG": "梁锋慢慢放下配送箱，双手捧住热碗。",
                            },
                        )

                    expected_dialogue = {
                        item["record_id"] for item in shot["dialogue_audio_refs"]
                    }
                    actual_dialogue = {
                        item["source_ref"]["record_id"]
                        for item in motion["audio"]
                        if item["kind"] == "dialogue"
                    }
                    self.assertEqual(actual_dialogue, expected_dialogue)
                    dialogue_actors = {
                        characters[index[block_id]["speaker"]]
                        for block_id in expected_dialogue
                    }
                    self.assertTrue(dialogue_actors.issubset(motion_actors))
                    for item in motion["audio"]:
                        if item["kind"] != "dialogue":
                            continue
                        block = index[item["source_ref"]["record_id"]]
                        self.assertEqual(
                            item["speaker_ref"]["record_id"], characters[block["speaker"]]
                        )
                        self.assertTrue(item["exact_text"])
                    if shot["shot_id"] == "SHOT-EP007-05":
                        self.assertEqual(
                            motion_actors,
                            {"CHAR-CHEN-YUAN", "CHAR-ZHOU-HAIPING"},
                        )

    def test_golden_files_complete_the_core_lifecycle_without_installing_every_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            project_tool.initialize_project(
                root,
                title="善意不结账",
                language="zh-CN",
                prompt_language="en",
                aspect_ratio="9:16",
                suite_root=CORE,
            )
            for name in ("输入", "项目开发", "设定集", "剧集", "创作者决策", "审查"):
                shutil.copytree(GOLDEN / name, root / name, dirs_exist_ok=True)

            outputs = {
                "剧集/EP001/screenplay.md": (GOLDEN / "剧集/EP001/screenplay.md").read_bytes(),
                "剧集/EP001/screenplay-index.jsonl": (GOLDEN / "剧集/EP001/screenplay-index.jsonl").read_bytes(),
            }
            result = project_tool.publish_candidate(
                root,
                owner="short-drama-write",
                artifact_id="EP001:script",
                outputs=outputs,
                inputs=["项目开发/episode-map.jsonl"],
            )
            self.assertEqual(result["state"], "needs_confirmation")
            project_tool.record_creator_acceptance(
                root, artifact_id="EP001:script", decision="accepted"
            )
            reviewed = project_tool.record_review(
                root,
                artifact_id="EP001:script",
                verdict="approve_with_notes",
                reviewer="golden fixture lifecycle",
                note="Exact readable text remains a postproduction task.",
            )
            self.assertEqual(reviewed["state"], "approved")
            package = project_tool.build_delivery_package(
                root,
                episode="EP001",
                includes=list(outputs),
            )
            self.assertEqual(len(package["files"]), 2)
            self.assertEqual(
                project_tool.verify_delivery_package(root, episode="EP001"),
                {"episode": "EP001", "status": "verified", "problems": []},
            )


if __name__ == "__main__":
    unittest.main()
