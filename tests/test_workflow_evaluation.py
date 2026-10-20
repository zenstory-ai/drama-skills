"""The main-workflow evaluation: one real novel, run end to end, checked here.

`evaluations/让你管账号/reference-run` is the recorded output of the documented
workflow against a 147 KB novel. Why it exists alongside `examples/` -- and what
it deliberately carries that the hand-shaped samples do not -- is in
`evaluations/README.md`; this module is the gate that holds it to that bar.

It asserts that the checkers still pass and that the derived layers still
reproduce from their sources. Whether the episode is any good as drama is a
creative review, and the procedure for that is in the same README.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"
EVAL = SUITE / "evaluations/让你管账号"
RUN = EVAL / "reference-run"
NOVEL = RUN / "输入/长篇-让你管账号，你高燃混剪炸全网.txt"
EPISODE = RUN / "剧集/EP001"


def script(relative: str) -> Path:
    return SKILLS / relative


def legacy_script(relative: str) -> Path:
    """A retired JSON checker kept only to validate this historical run."""
    return SUITE / "tests/legacy" / relative


def run_json(args: list[str]) -> dict[str, Any]:
    """Run a checker exactly as a creator would, and read its report."""
    completed = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=RUN,
    )
    payload = completed.stdout.strip() or completed.stderr.strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:  # pragma: no cover - only on a broken checker
        raise AssertionError(f"{args[0]} did not print a JSON report:\n{payload}")


def records(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class SourceMaterialTests(unittest.TestCase):
    def test_the_novel_is_present_and_whole(self) -> None:
        self.assertTrue(NOVEL.is_file(), "the evaluation input is missing")
        data = NOVEL.read_bytes()
        self.assertEqual(len(data), 147010, "the evaluation input changed size")

    def test_the_chapter_index_still_reproduces_from_the_novel(self) -> None:
        """S0 is the single slicing truth; a drifting index moves every stage."""

        recorded = json.loads(
            (RUN / "项目开发/source-analysis/_index.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            rebuilt_path = Path(directory) / "index.json"
            report = run_json(
                [
                    str(script("short-drama-novel-analyze/scripts/novel_index.py")),
                    "index",
                    str(NOVEL),
                    "--out",
                    str(rebuilt_path),
                ]
            )
            rebuilt = json.loads(rebuilt_path.read_text(encoding="utf-8"))

        self.assertEqual(report["problems"], [])
        self.assertEqual(report["chapter_count"], 20)
        self.assertEqual(
            [chapter["sequence"] for chapter in rebuilt["chapters"]],
            [chapter["sequence"] for chapter in recorded["chapters"]],
        )
        self.assertEqual(
            [chapter["line_start"] for chapter in rebuilt["chapters"]],
            [chapter["line_start"] for chapter in recorded["chapters"]],
        )


class CheckerSweepTests(unittest.TestCase):
    """Every checker the documented workflow runs, over the recorded output.

    Kept as one table so adding a stage means adding a row, not another method
    that differs only in its argv.
    """

    # (label, argv, expected status, keys that must come back empty)
    CHECKS = (
        (
            "asset bible",
            [
                "short-drama-assets/scripts/asset_check.py",
                "--characters", "设定集/characters.jsonl",
                "--looks", "设定集/looks.jsonl",
            ],
            "valid",
            (),
        ),
        (
            "image prompts",
            [
                "short-drama-image-prompts/scripts/image_prompt_check.py",
                "剧集/EP001/assets/image-prompt-specs.jsonl",
            ],
            "valid",
            (),
        ),
        (
            "storyboard coverage",
            [
                "short-drama-storyboard/scripts/storyboard_check.py",
                "剧集/EP001/storyboard/coverage.json",
                "--shots", "剧集/EP001/storyboard/shots.jsonl",
                "--keyframes", "剧集/EP001/storyboard/keyframes.jsonl",
                "--screenplay-index", "剧集/EP001/screenplay-index.jsonl",
                "--project", "short-drama.json",
            ],
            "pass",
            ("findings",),
        ),
        (
            "delivery containers",
            [
                "short-drama-video-prompts/scripts/container_check.py",
                "剧集/EP001/storyboard/delivery-containers.jsonl",
                "--shots", "剧集/EP001/storyboard/shots.jsonl",
            ],
            "pass",
            ("findings", "loose_shots", "unmeasured_shots"),
        ),
        (
            "motion timing",
            [
                "short-drama-video-prompts/scripts/motion_timing_check.py",
                "剧集/EP001/storyboard/motion-specs.jsonl",
                "--shots", "剧集/EP001/storyboard/shots.jsonl",
            ],
            "pass",
            ("findings", "unmeasured_specs"),
        ),
        (
            "music specs",
            [
                "short-drama-video-prompts/scripts/music_spec_check.py",
                "剧集/EP001/storyboard/music-specs.jsonl",
            ],
            "valid",
            (),
        ),
    )

    def test_every_checker_passes(self) -> None:
        for label, argv, status, empty in self.CHECKS:
            with self.subTest(checker=label):
                report = run_json([str(legacy_script(argv[0])), *argv[1:]])
                self.assertEqual(report["status"], status)
                for key in empty:
                    self.assertEqual(report[key], [], f"{label}: {key}")


class CanonicalPathTests(unittest.TestCase):
    """The recorded historical evaluation must remain internally complete.

    This fixture exercises retired deterministic validators. It is not public
    creator-first workflow guidance, so active SKILL.md files must not advertise
    its JSON/JSONL filenames merely to keep the fixture discoverable.
    """

    # (path under the episode/project root, owning skill)
    CANONICAL = (
        ("剧集/EP001/screenplay.md", "short-drama-write"),
        ("剧集/EP001/screenplay-index.jsonl", "short-drama-write"),
        ("剧集/EP001/episode-card.json", "short-drama-write"),
        ("剧集/EP001/beats.jsonl", "short-drama-write"),
        ("剧集/EP001/voice-record-sheet.jsonl", "short-drama-write"),
        ("剧集/EP001/storyboard/shots.jsonl", "short-drama-storyboard"),
        ("剧集/EP001/storyboard/coverage.json", "short-drama-storyboard"),
        ("剧集/EP001/storyboard/keyframes.jsonl", "short-drama-storyboard"),
        ("剧集/EP001/storyboard/motion-specs.jsonl", "short-drama-video-prompts"),
        ("剧集/EP001/storyboard/delivery-containers.jsonl", "short-drama-video-prompts"),
        ("剧集/EP001/storyboard/music-specs.jsonl", "short-drama-video-prompts"),
        ("项目开发/episode-map.jsonl", "short-drama-develop"),
        ("项目开发/adaptation-map.jsonl", "short-drama-develop"),
        ("项目开发/source-analysis/episode-candidates.jsonl", "short-drama-novel-analyze"),
        ("设定集/characters.jsonl", "short-drama-assets"),
        ("设定集/props.jsonl", "short-drama-assets"),
    )

    def test_the_fixture_contains_every_input_its_checker_sweep_uses(self) -> None:
        for relative, _owner in self.CANONICAL:
            with self.subTest(path=relative):
                self.assertTrue(
                    (RUN / relative).is_file(),
                    f"{relative} is missing from the reference run",
                )


class VoiceOverCoverageTests(unittest.TestCase):
    """Voice-over: eight lines here, none anywhere in `examples/`.

    Two defects lived without a failing test because no sample exercised this
    path -- voice-over timed at zero seconds, and a voice sheet that could not
    project a voice-over block.
    """

    def test_the_episode_actually_exercises_voice_over(self) -> None:
        blocks = [
            record
            for record in records(EPISODE / "screenplay-index.jsonl")
            if record.get("record_type") == "block"
        ]
        voiced = [b for b in blocks if b.get("tag") in {"VO", "OS"}]
        self.assertGreaterEqual(
            len(voiced), 5, "the evaluation stopped covering the voice-over path"
        )
        for block in voiced:
            self.assertTrue(
                block.get("speaker"),
                "a voice tag must name its speaker; the index enforces that grammar",
            )

    def test_voice_over_is_timed_as_speech(self) -> None:
        """The recorded run's length is asserted as a number, not as not-None.

        `assertIsNotNone` was the whole assertion here once, and it held while
        the estimate was wrong by thirty seconds. A concrete figure is the only
        form of this test that a mis-measurement can fail.
        """

        report = run_json(
            [
                str(script("short-drama-write/scripts/duration_estimate.py")),
                "剧集/EP001/screenplay.md",
                "--index",
                "剧集/EP001/screenplay-index.jsonl",
                "--project",
                "short-drama.json",
            ]
        )
        self.assertNotIn(
            "incomplete",
            report,
            "the index left part of the recorded screenplay unclassified",
        )
        self.assertEqual(report["counts"]["dialogue_lines"], 18)
        self.assertEqual(report["counts"]["dialogue_characters"], 274)
        self.assertEqual(report["counts"]["action_paragraphs"], 16)
        self.assertEqual(report["seconds"], 94.8)
        self.assertLessEqual(
            abs(report["delta_ratio"]),
            0.15,
            "the episode left the declared tolerance; a voice-over regression "
            "shows up here first, as a large negative delta",
        )

    def test_the_voice_sheet_covers_every_spoken_line(self) -> None:
        report = run_json(
            [
                str(legacy_script("short-drama-write/scripts/voice_sheet_check.py")),
                "剧集/EP001/voice-record-sheet.jsonl",
                "--index",
                "剧集/EP001/screenplay-index.jsonl",
                "--screenplay",
                "剧集/EP001/screenplay.md",
            ]
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["uncovered_dialogue_blocks"],
            [],
            "the recording list is missing spoken lines",
        )
        self.assertEqual(report["lines"], report["dialogue_blocks"])


class DerivedLayerTests(unittest.TestCase):
    def test_the_screenplay_index_reproduces_from_the_screenplay(self) -> None:
        """Rebuilt against itself, every block keeps its ID and its bytes."""

        screenplay = EPISODE / "screenplay.md"
        recorded = EPISODE / "screenplay-index.jsonl"
        speakers: set[str] = {
            record["speaker"]
            for record in records(recorded)
            if record.get("record_type") == "block" and record.get("speaker")
        }
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / "screenplay-index.jsonl"
            args = [
                str(script("short-drama-write/scripts/screenplay_index.py")),
                str(screenplay),
                "--output",
                str(rebuilt),
                "--source-ref",
                "剧集/EP001/screenplay.md",
                "--previous-index",
                str(recorded),
                "--previous-source",
                str(screenplay),
            ]
            for speaker in sorted(speakers):
                args += ["--speaker", speaker]
            report = run_json(args)
            rebuilt_blocks = [
                record
                for record in records(rebuilt)
                if record.get("record_type") == "block"
            ]

        self.assertEqual(report["review_status"], "clean")
        recorded_blocks = [
            record
            for record in records(recorded)
            if record.get("record_type") == "block"
        ]
        self.assertEqual(
            [block["block_id"] for block in rebuilt_blocks],
            [block["block_id"] for block in recorded_blocks],
            "an unchanged screenplay produced different block IDs",
        )
        for block in rebuilt_blocks:
            self.assertEqual(block["mapping"]["status"], "reused")

    def test_every_artifact_is_accepted(self) -> None:
        """A reference run ships in the state a creator would hand downstream."""

        report = run_json(
            [str(script("short-drama/scripts/project_tool.py")), "status", "."]
        )
        self.assertEqual(
            {state for state in report["artifacts"].values()},
            {"accepted"},
            f"artifact states: {report['artifact_states']}",
        )


if __name__ == "__main__":
    unittest.main()


class PromptLanguageTests(unittest.TestCase):
    """The copyable prompt body follows the language the project declared.

    The recorded run declares `prompt_language: en` and shipped seven accepted
    Chinese prompt bodies, because the shipped template said `<自然中文正文…>`
    unconditionally and a template is what gets copied. `test_output_language`
    stayed green throughout: it read `SKILL.md` and never opened `assets/`.

    Only `generic_prompt` is bound to this field. The spec's other fields are
    read by the creator and follow `#/language`, and readable text inside the
    image follows the accepted text policy -- which is why the two phone props
    legitimately keep Chinese on their screens.
    """

    def test_prompt_bodies_are_in_the_declared_prompt_language(self) -> None:
        project = json.loads((RUN / "short-drama.json").read_text(encoding="utf-8"))
        self.assertEqual(project["format"]["prompt_language"], "en")

        readable_text = {"剩余", "天", "失败", "撤销授予", "解除绑定"}
        specs = [
            record
            for record in records(EPISODE / "assets/image-prompt-specs.jsonl")
            if record.get("record_type") != "sources"
        ]
        self.assertEqual(len(specs), 7)
        for spec in specs:
            with self.subTest(spec_id=spec["spec_id"]):
                body = spec["generic_prompt"]
                for phrase in readable_text:
                    body = body.replace(phrase, "")
                stray = [
                    character for character in body if "一" <= character <= "鿿"
                ]
                self.assertEqual(
                    stray,
                    [],
                    "the prompt body carries prose in a language the project did "
                    "not declare; only readable in-image text may differ",
                )
