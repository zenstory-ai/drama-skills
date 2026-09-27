"""The three invariants that were classified structural but ran on trust.

`SHT-16`, `SHT-17`, and `VID-15` are arithmetic and set comparisons. Leaving
them to a reviewer costs judgment on work a script does exactly, and the
failures they catch are precisely the ones that look fine to a reader: a
coverage list missing one shot ID reads identically to a complete one.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"


def _module(name: str, relative: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SKILLS / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


storyboard_check = _module(
    "sd_storyboard_check", "short-drama-storyboard/scripts/storyboard_check.py"
)
container_check = _module(
    "sd_container_check", "short-drama-video-prompts/scripts/container_check.py"
)
voice_sheet_check = _module(
    "sd_voice_sheet_check", "short-drama-write/scripts/voice_sheet_check.py"
)
duration_estimate = _module(
    "sd_duration_estimate", "short-drama-write/scripts/duration_estimate.py"
)
screenplay_index = _module(
    "sd_screenplay_index", "short-drama-write/scripts/screenplay_index.py"
)


def shot_ref(shot_id: str) -> dict[str, Any]:
    return {
        "owner": "short-drama-storyboard",
        "artifact": "episodes/EP001/storyboard/shots.jsonl",
        "record_id": shot_id,
    }


def coverage(**duration: Any) -> dict[str, Any]:
    return {
        "episode_id": "EP001",
        "dispositions": [
            {
                "block_id": "BLK-1",
                "status": "covered",
                "shot_refs": [shot_ref("SHOT-1"), shot_ref("SHOT-2"), shot_ref("SHOT-3")],
            }
        ],
        "episode_duration": {
            "shot_seconds_total": 6.0,
            "counted_shot_ids": ["SHOT-1", "SHOT-2"],
            "unresolved_durations": ["SHOT-3"],
            "target_seconds": None,
            "delta_seconds": None,
            "disposition": "no_target_declared",
            **duration,
        },
    }


SHOTS = [
    {"shot_id": "SHOT-1", "duration_seconds": 3.5},
    {"shot_id": "SHOT-2", "duration_seconds": 2.5},
    {"shot_id": "SHOT-3"},
]


def codes(findings: list[dict[str, Any]]) -> set[str]:
    return {finding["code"] for finding in findings}


class EpisodeDurationCheckTests(unittest.TestCase):
    def run_check(self, cov: dict[str, Any], target: float | None = None) -> set[str]:
        return codes(storyboard_check.check_episode_duration(cov, SHOTS, target))

    def test_a_correct_ledger_passes_with_a_shot_still_suspended(self) -> None:
        self.assertEqual(self.run_check(coverage()), set())

    def test_a_shot_that_silently_leaves_the_total_is_caught(self) -> None:
        """This is the failure the rule exists for: the ledger still adds up."""

        self.assertIn(
            "SHT16_SHOT_LEFT_THE_TOTAL",
            self.run_check(coverage(unresolved_durations=[])),
        )

    def test_a_wrong_total_is_caught(self) -> None:
        self.assertIn(
            "SHT16_TOTAL_IS_NOT_THE_SUM",
            self.run_check(coverage(shot_seconds_total=7.0)),
        )

    def test_a_shot_cannot_be_counted_and_suspended_at_once(self) -> None:
        self.assertIn(
            "SHT16_SHOT_COUNTED_AND_UNRESOLVED",
            self.run_check(
                coverage(
                    counted_shot_ids=["SHOT-1", "SHOT-2", "SHOT-3"],
                    unresolved_durations=["SHOT-3"],
                )
            ),
        )

    def test_a_counted_shot_must_actually_carry_a_duration(self) -> None:
        self.assertIn(
            "SHT16_COUNTED_SHOT_HAS_NO_DURATION",
            self.run_check(
                coverage(
                    counted_shot_ids=["SHOT-1", "SHOT-2", "SHOT-3"],
                    unresolved_durations=[],
                )
            ),
        )

    def test_a_suspended_shot_that_already_has_a_duration_is_caught(self) -> None:
        self.assertIn(
            "SHT16_SUSPENDED_SHOT_HAS_A_DURATION",
            self.run_check(
                coverage(counted_shot_ids=["SHOT-2"], unresolved_durations=["SHOT-1", "SHOT-3"])
            ),
        )

    def test_a_declared_target_needs_a_correct_delta_and_a_disposition(self) -> None:
        self.assertEqual(
            self.run_check(coverage(), target=5.0),
            {"SHT16_DELTA_MISSING", "SHT16_DISPOSITION_MISSING"},
        )
        self.assertEqual(
            self.run_check(
                coverage(
                    target_seconds=5.0,
                    delta_seconds=1.0,
                    disposition="within_creator_tolerance",
                ),
                target=5.0,
            ),
            set(),
        )
        self.assertIn(
            "SHT16_DELTA_IS_WRONG",
            self.run_check(
                coverage(
                    target_seconds=5.0,
                    delta_seconds=9.0,
                    disposition="within_creator_tolerance",
                ),
                target=5.0,
            ),
        )

    def test_the_delta_alone_never_becomes_a_finding(self) -> None:
        """A target is a plan, not a quality gate; only bad arithmetic fails."""

        self.assertEqual(
            self.run_check(
                coverage(
                    target_seconds=1.0,
                    delta_seconds=5.0,
                    disposition="creator_accepted_overrun",
                ),
                target=1.0,
            ),
            set(),
        )


class KeyframeBoundaryCheckTests(unittest.TestCase):
    def keyframe(self, **overrides: Any) -> dict[str, Any]:
        record = {
            "keyframe_id": "KEY-1",
            "boundary_role": "start",
            "boundary_ref": {
                "owner": "short-drama-storyboard",
                "artifact": "episodes/EP001/storyboard/shots.jsonl",
                "record_id": "SHOT-1",
                "field": "/start_boundary",
            },
        }
        record.update(overrides)
        return record

    def run_check(self, *keyframes: dict[str, Any]) -> set[str]:
        return codes(storyboard_check.check_keyframe_boundaries(list(keyframes), SHOTS))

    def test_a_start_and_an_end_frame_on_one_shot_are_both_allowed(self) -> None:
        end = self.keyframe(
            keyframe_id="KEY-2",
            boundary_role="end",
            boundary_ref={
                "owner": "short-drama-storyboard",
                "artifact": "episodes/EP001/storyboard/shots.jsonl",
                "record_id": "SHOT-1",
                "field": "/end_boundary",
            },
        )
        self.assertEqual(self.run_check(self.keyframe(), end), set())

    def test_an_undeclared_role_is_caught(self) -> None:
        record = self.keyframe()
        del record["boundary_role"]
        self.assertIn("SHT17_BOUNDARY_ROLE_MISSING", self.run_check(record))

    def test_a_role_that_disagrees_with_its_field_is_caught(self) -> None:
        """An end frame pointing at /start_boundary is the drift this prevents."""

        self.assertIn(
            "SHT17_BOUNDARY_REF_DISAGREES_WITH_ROLE",
            self.run_check(self.keyframe(boundary_role="end")),
        )

    def test_two_frames_on_the_same_boundary_are_caught(self) -> None:
        self.assertIn(
            "SHT17_DUPLICATE_BOUNDARY_KEYFRAME",
            self.run_check(self.keyframe(), self.keyframe(keyframe_id="KEY-2")),
        )

    def test_a_frame_bound_to_no_real_shot_is_caught(self) -> None:
        record = self.keyframe()
        record["boundary_ref"]["record_id"] = "SHOT-404"
        self.assertIn("SHT17_BOUNDARY_REF_UNRESOLVABLE", self.run_check(record))

    def test_a_shot_with_no_keyframe_is_not_a_finding(self) -> None:
        """One frame per shot is a default, never a quota."""

        self.assertEqual(self.run_check(self.keyframe()), set())


class ContainerReconciliationTests(unittest.TestCase):
    MEASURED = [
        {"shot_id": "SHOT-1", "duration_seconds": 3.5},
        {"shot_id": "SHOT-2", "duration_seconds": 2.5},
        {"shot_id": "SHOT-3", "duration_seconds": 1.0},
    ]

    DURATION_OF = {"SHOT-1": 3.5, "SHOT-2": 2.5, "SHOT-3": 1.0}

    def container(self, container_id: str, shot_ids: list[str], seconds: float) -> dict[str, Any]:
        """A container that satisfies the record's own documented shape.

        `membership_basis` and per-member `accepted_duration` are part of that
        shape; the fixture omitted both while nothing checked them.
        """

        return {
            "container_id": container_id,
            "members": [
                {
                    "order": index,
                    "shot_ref": shot_ref(shot_id),
                    "accepted_duration": self.DURATION_OF.get(shot_id, 0.0),
                }
                for index, shot_id in enumerate(shot_ids, start=1)
            ],
            "membership_basis": {
                "source_order_contiguous": True,
                "binding_chain_equal": True,
                "scene_boundary_not_crossed": True,
            },
            "unresolved": [],
            "container_duration": seconds,
        }

    def test_a_loose_shot_reconciles_and_is_reported_not_blamed(self) -> None:
        result = container_check.reconcile(
            [self.container("CONT-1", ["SHOT-1", "SHOT-2"], 6.0)], self.MEASURED
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["loose_shots"], ["SHOT-3"])
        self.assertEqual(result["packed_seconds"], 6.0)
        self.assertEqual(result["loose_seconds"], 1.0)

    def test_a_shot_packed_into_two_containers_is_caught(self) -> None:
        """Invisible from inside either container; the episode is billed twice."""

        result = container_check.reconcile(
            [
                self.container("CONT-1", ["SHOT-1", "SHOT-2"], 6.0),
                self.container("CONT-2", ["SHOT-2", "SHOT-3"], 3.5),
            ],
            self.MEASURED,
        )
        self.assertIn("VID15_SHOT_PACKED_TWICE", codes(result["findings"]))

    def test_a_container_duration_that_is_not_the_sum_is_caught(self) -> None:
        result = container_check.reconcile(
            [self.container("CONT-1", ["SHOT-1", "SHOT-2"], 9.0)], self.MEASURED
        )
        self.assertIn(
            "VID15_CONTAINER_DURATION_IS_NOT_THE_SUM", codes(result["findings"])
        )

    def test_a_member_from_another_episode_is_caught(self) -> None:
        result = container_check.reconcile(
            [self.container("CONT-1", ["SHOT-1", "SHOT-99"], 3.5)], self.MEASURED
        )
        self.assertIn("VID15_MEMBER_IS_NOT_AN_EPISODE_SHOT", codes(result["findings"]))

    def test_an_open_duration_upstream_is_held_out_rather_than_blamed(self) -> None:
        """Work in progress must not be indistinguishable from work done wrong."""

        result = container_check.reconcile(
            [self.container("CONT-1", ["SHOT-1", "SHOT-2"], 6.0)], SHOTS
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["unmeasured_shots"], ["SHOT-3"])
        self.assertEqual(result["loose_seconds"], 0.0)

    def test_a_packed_shot_must_already_have_a_duration(self) -> None:
        result = container_check.reconcile(
            [self.container("CONT-1", ["SHOT-1", "SHOT-3"], 3.5)], SHOTS
        )
        self.assertIn("VID15_MEMBER_SHOT_HAS_NO_DURATION", codes(result["findings"]))


class SpokenDurationTests(unittest.TestCase):
    """The estimate reads the index; it has no reader of its own.

    Two readers of one format give two answers. This script used to carry its
    own, and it timed `[VO]` at zero, billed a Markdown comment as speech, read
    an action paragraph as dialogue whenever it contained a colon, and counted
    one multi-line paragraph once per line. Every case below is measured through
    `screenplay_index`, because that is the only way the two cannot disagree.
    """

    PROJECT = {"format": {"pacing": {
        "spoken_characters_per_second": 5.0, "seconds_per_action_paragraph": 2.5}}}

    def measure(
        self,
        body: str,
        speakers: list[str] | None = None,
        project: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenplay = root / "screenplay.md"
            index_path = root / "screenplay-index.jsonl"
            screenplay.write_text(
                "# EP001\n\n## EP001-SC001 内 · 值班室 · 夜\n\n" + body,
                encoding="utf-8",
            )
            screenplay_index.build_index(
                screenplay,
                index_path,
                source_ref="剧集/EP001/screenplay.md",
                speakers=speakers or ["葛晴", "船员"],
            )
            records = [
                json.loads(line)
                for line in index_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            source = screenplay.read_bytes()
            blocks, review = duration_estimate.index_blocks(records, source)
            return duration_estimate.estimate(
                source, blocks, project or self.PROJECT, review
            )

    def test_a_voice_over_line_is_timed_as_speech(self) -> None:
        report = self.measure("[VO] 葛晴：十二个字的台词在这里。\n")
        self.assertEqual(report["counts"]["dialogue_lines"], 1)
        self.assertEqual(report["counts"]["production_tag_lines"], 0)
        self.assertEqual(report["counts"]["dialogue_characters"], 11)

    def test_an_off_screen_line_is_timed_as_speech(self) -> None:
        report = self.measure("[OS] 船员：关窗，水进来了！\n")
        self.assertEqual(report["counts"]["dialogue_lines"], 1)
        self.assertEqual(report["counts"]["dialogue_characters"], 8)

    def test_tags_that_are_not_speech_still_carry_no_duration(self) -> None:
        report = self.measure(
            "[SFX] 远处传来一声短促汽笛。\n\n"
            "[画面文字] 票面日期：11月6日\n\n"
            "[连续性] 钥匙交到左手。\n"
        )
        self.assertEqual(report["counts"]["dialogue_lines"], 0)
        self.assertEqual(report["counts"]["production_tag_lines"], 3)

    def test_one_action_paragraph_is_one_paragraph_however_many_lines(self) -> None:
        """`screenplay-format.md` lets an action paragraph run several lines.

        Counting per line inflated every such paragraph by its own line count,
        at 2.5 seconds a line.
        """

        report = self.measure("他站起来，\n走到窗边，\n把窗帘拉开。\n")
        self.assertEqual(report["counts"]["action_paragraphs"], 1)
        self.assertEqual(report["seconds"], 2.5)

    def test_a_colon_line_is_never_guessed_into_dialogue(self) -> None:
        """The index checks the speaker against the roster instead of guessing.

        `screenplay-format.md` §3.2 is explicit that the tooling does not infer a
        speaker from a colon prefix. The private parser did, and turned an action
        paragraph into three characters of speech. The index refuses either
        reading and raises it for review, so nothing is billed on a guess.
        """

        report = self.measure("他在纸上写下两个字：军宣。\n")
        self.assertEqual(report["counts"]["dialogue_lines"], 0)
        self.assertEqual(report["counts"]["dialogue_characters"], 0)
        self.assertIn("incomplete", report)

    def test_a_comment_is_not_production_content(self) -> None:
        """A Markdown comment matched the dialogue grammar and billed as speech."""

        report = self.measure("<!-- 待确认：这一段的转场是否保留。 -->\n")
        self.assertEqual(report["counts"]["dialogue_lines"], 0)
        self.assertEqual(report["counts"]["dialogue_characters"], 0)
        self.assertEqual(report["counts"]["action_paragraphs"], 0)

    def test_material_the_index_could_not_classify_is_reported(self) -> None:
        """An estimate over part of a screenplay must not read as the whole.

        A `[VO]` line with no speaker is a source issue, not a block. Timing what
        is left and staying silent would report a short episode as a fact.
        """

        report = self.measure("[VO] 没有说话人的一行字\n")
        self.assertIn("incomplete", report)
        self.assertEqual(report["incomplete"]["source_issue_count"], 1)
        self.assertEqual(report["incomplete"]["index_review_status"], "review_required")

    VO_HEAVY = "[VO] 葛晴：我知道他在撒谎。\n\n葛晴：你走吧。\n"

    def with_rhythm_profile(self, status: str, ceiling: Any = 0.3) -> dict[str, Any]:
        project = json.loads(json.dumps(self.PROJECT))
        project["creator_authority"] = {
            "rhythm_profile": {"status": status, "vo_share_max": ceiling}
        }
        return project

    def test_an_accepted_vo_ceiling_is_compared_against_the_vo_share(self) -> None:
        """Eight of twelve spoken characters are [VO]: over an accepted 0.3 cap."""

        report = self.measure(
            self.VO_HEAVY, project=self.with_rhythm_profile("accepted")
        )
        self.assertEqual(report["counts"]["voiceover_characters"], 8)
        self.assertEqual(report["vo_share"]["share"], round(8 / 12, 3))
        self.assertTrue(report["vo_share"]["over_max"])

    def test_a_proposed_or_missing_profile_compares_nothing(self) -> None:
        proposed = self.measure(
            self.VO_HEAVY, project=self.with_rhythm_profile("proposed")
        )
        self.assertNotIn("vo_share", proposed)
        self.assertNotIn("vo_share", self.measure(self.VO_HEAVY))

    def test_a_ceiling_that_is_not_a_share_compares_nothing(self) -> None:
        """A hand edit can put NaN or 5 where a share belongs; neither is a cap."""

        for ceiling in (float("nan"), 5, float("inf"), -0.1):
            with self.subTest(ceiling=ceiling):
                report = self.measure(
                    self.VO_HEAVY, project=self.with_rhythm_profile("accepted", ceiling)
                )
                self.assertNotIn("vo_share", report)

    def test_an_off_screen_line_is_speech_but_not_voice_over(self) -> None:
        """[OS] is in-scene dialogue from off frame, not narration or inner voice."""

        report = self.measure(
            "[OS] 船员：关窗，水进来了！\n\n[VO] 葛晴：我知道他在撒谎。\n",
            project=self.with_rhythm_profile("accepted"),
        )
        self.assertEqual(report["counts"]["dialogue_characters"], 16)
        self.assertEqual(report["counts"]["voiceover_characters"], 8)
        self.assertEqual(report["vo_share"]["share"], 0.5)

    def test_an_index_built_from_other_bytes_is_refused(self) -> None:
        """Stale spans land on text the index never classified."""

        stale = [{"record_type": "screenplay_index_meta", "source_byte_length": 10}]
        with self.assertRaises(duration_estimate.StaleIndex):
            duration_estimate.index_blocks(stale, b"a much longer screenplay")


class VoiceSheetCheckTests(unittest.TestCase):
    SCREENPLAY = (
        "## EP001-SC001 内 · 值班室 · 夜\n\n"
        "他推开门。\n\n"
        "葛晴（压着嗓子）：你把本子放下。\n"
    )

    def build(self, screenplay: str | None = None) -> tuple[list[dict[str, Any]], bytes, str]:
        source = (screenplay or self.SCREENPLAY).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screenplay.md"
            path.write_bytes(source)
            index_path = Path(directory) / "index.jsonl"
            with contextlib.redirect_stdout(io.StringIO()):
                screenplay_index.main(
                    [
                        str(path),
                        "--output",
                        str(index_path),
                        "--source-ref",
                        "episodes/EP001/screenplay.md",
                        "--speaker",
                        "葛晴",
                    ]
                )
            index = [
                json.loads(line)
                for line in index_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        block_id = next(
            record["block_id"] for record in index if record.get("kind") == "dialogue"
        )
        return index, source, block_id

    def line(self, block_id: str, **overrides: Any) -> dict[str, Any]:
        record = {
            "line_id": "VLINE-1",
            "speaker": "CHAR-GE",
            "speaker_display": "葛晴",
            "line_text": "你把本子放下。",
            "channel": "sync",
            "source_ref": {
                "owner": "short-drama-write",
                "artifact": "episodes/EP001/screenplay-index.jsonl",
                "record_id": block_id,
            },
        }
        record.update(overrides)
        return record

    def test_a_faithful_sheet_passes(self) -> None:
        index, source, block_id = self.build()
        result = voice_sheet_check.check([self.line(block_id)], index, source)
        self.assertEqual(result["status"], "pass")

    def test_a_line_edited_in_the_sheet_is_caught(self) -> None:
        """The sheet is a projection; changing a word here forks the wording."""

        index, source, block_id = self.build()
        result = voice_sheet_check.check(
            [self.line(block_id, line_text="你把本子放下吧。")], index, source
        )
        self.assertIn("VOICE_LINE_TEXT_DIVERGED", codes(result["findings"]))

    def test_a_speaker_that_disagrees_with_the_index_is_caught(self) -> None:
        index, source, block_id = self.build()
        result = voice_sheet_check.check(
            [self.line(block_id, speaker_display="别人")], index, source
        )
        self.assertIn("VOICE_SPEAKER_DIVERGED", codes(result["findings"]))

    def test_a_line_pointing_at_an_action_block_is_caught(self) -> None:
        index, source, _block_id = self.build()
        action = next(
            record["block_id"] for record in index if record.get("kind") == "action"
        )
        result = voice_sheet_check.check([self.line(action)], index, source)
        self.assertIn("VOICE_SOURCE_IS_NOT_DIALOGUE", codes(result["findings"]))

    VOICE_OVER = (
        "## EP001-SC001 内 · 值班室 · 夜\n\n"
        "他推开门。\n\n"
        "葛晴（压着嗓子）：你把本子放下。\n\n"
        "[VO] 葛晴：我那时还不知道，本子是空的。\n"
    )

    def test_a_voice_over_line_can_be_recorded(self) -> None:
        """The VO channel the schema offers has to be reachable."""

        index, source, _block_id = self.build(self.VOICE_OVER)
        vo = next(
            record["block_id"]
            for record in index
            if record.get("kind") == "production_tag" and record.get("tag") == "VO"
        )
        result = voice_sheet_check.check(
            [
                self.line(
                    vo,
                    line_id="VLINE-VO",
                    channel="VO",
                    line_text="我那时还不知道，本子是空的。",
                )
            ],
            index,
            source,
        )
        self.assertEqual(result["status"], "pass")

    def test_an_unrecorded_voice_over_line_shows_as_uncovered(self) -> None:
        """A sheet missing the voice-over must not read as complete."""

        index, source, block_id = self.build(self.VOICE_OVER)
        result = voice_sheet_check.check([self.line(block_id)], index, source)
        self.assertEqual(result["dialogue_blocks"], 2)
        self.assertEqual(len(result["uncovered_dialogue_blocks"]), 1)

    def test_a_partial_sheet_reports_coverage_without_failing(self) -> None:
        """Splitting a sheet per actor or per scene is ordinary practice."""

        index, source, _block_id = self.build()
        result = voice_sheet_check.check([], index, source)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["uncovered_dialogue_blocks"]), 1)


if __name__ == "__main__":
    unittest.main()
