import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama-breakdown/scripts/breakdown_tool.py"
SPEC = importlib.util.spec_from_file_location("breakdown_tool", SCRIPT)
assert SPEC and SPEC.loader
breakdown = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(breakdown)


def episode(number, duration, shots, lines):
    return {
        "episode": number,
        "duration": duration,
        "shot_seconds": shots,
        "segments": [{"s": start, "e": end, "t": text} for start, end, text in lines],
    }


class TranscriptTests(unittest.TestCase):
    def test_srt_vtt_and_json_give_the_same_segments(self):
        srt = "1\n00:00:01,000 --> 00:00:02,500\n把钥匙交出来\n\n2\n00:00:03,000 --> 00:00:04,000\n不交\n"
        vtt = "WEBVTT\n\n00:01.000 --> 00:02.500\n把钥匙交出来\n\n00:03.000 --> 00:04.000\n不交\n"
        payload = json.dumps({"segments": [
            {"start": 1.0, "end": 2.5, "text": "把钥匙交出来"},
            {"start": 3.0, "end": 4.0, "text": "不交"},
        ]}, ensure_ascii=False)
        expected = [{"s": 1.0, "e": 2.5, "t": "把钥匙交出来"}, {"s": 3.0, "e": 4.0, "t": "不交"}]
        self.assertEqual(breakdown.parse_transcript(srt, ".srt"), expected)
        self.assertEqual(breakdown.parse_transcript(vtt, ".vtt"), expected)
        self.assertEqual(breakdown.parse_transcript(payload, ".json"), expected)

    def test_a_cue_that_ends_before_it_starts_is_refused(self):
        for start, end in ((6, 2), (-1, 2), ("nan", 2)):
            with self.subTest(start=start, end=end), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(
                breakdown.BreakdownError
            ):
                breakdown.parse_transcript(json.dumps([{"start": start, "end": end, "text": "甲"}]), ".json")

    def test_isolated_dirty_cues_are_skipped_with_stderr_notice(self):
        srt = (
            "1\n00:00:01,000 --> 00:00:02,000\n正常首句\n\n"
            "2\n00:00:02,500 --> 00:00:02,500\n零时长脏行\n\n"
            "3\n00:00:05,000 --> 00:00:04,000\n倒挂脏行\n\n"
            "4\n00:00:06,000 --> 00:00:07,500\n正常尾句\n"
        )
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            segments = breakdown.parse_transcript(srt, ".srt")
        self.assertEqual(
            segments,
            [{"s": 1.0, "e": 2.0, "t": "正常首句"}, {"s": 6.0, "e": 7.5, "t": "正常尾句"}],
        )
        self.assertIn("2.5–2.5", err.getvalue())
        self.assertIn("5.0–4.0", err.getvalue())

        json_err = io.StringIO()
        payload = json.dumps(
            [
                {"start": -0.3, "end": 1.0, "text": "负数脏行"},
                {"start": 1.2, "end": 1.2, "text": "零长脏行"},
                {"start": 2.0, "end": 3.5, "text": "有效台词"},
            ],
            ensure_ascii=False,
        )
        with contextlib.redirect_stderr(json_err):
            json_segments = breakdown.parse_transcript(payload, ".json")
        self.assertEqual(json_segments, [{"s": 2.0, "e": 3.5, "t": "有效台词"}])
        self.assertTrue(json_err.getvalue().strip())

        all_dirty_srt = "1\n00:00:03,000 --> 00:00:03,000\n全脏\n"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(breakdown.BreakdownError):
            breakdown.parse_transcript(all_dirty_srt, ".srt")

    def test_a_file_without_timings_is_refused(self):
        with self.assertRaises(breakdown.BreakdownError):
            breakdown.parse_transcript("只有文字，没有时间\n", ".srt")


class SpeechTimingTests(unittest.TestCase):
    def test_overlapping_cues_count_occupied_time_once(self):
        record = episode(1, 10.0, [10.0], [(0.0, 8.0, "甲"), (2.0, 10.0, "乙")])
        numbers = breakdown.episode_numbers(record)
        self.assertEqual(numbers["speech_share"], 1.0)
        self.assertEqual(numbers["longest_silence"], 0.0)

    def test_silence_at_either_end_counts_toward_the_longest_silence(self):
        numbers = breakdown.episode_numbers(episode(1, 10.0, [10.0], [(6.0, 7.0, "甲")]))
        self.assertEqual(numbers["longest_silence"], 6.0)

    def test_a_multi_line_action_paragraph_takes_one_action_slot(self):
        pacing = {"characters": 4.0, "words": None, "action": 3.0}
        timeline = breakdown.script_timeline("他推门。\n门轴吱了一声。\n<!-- 备注 -->\n\n韩冬：走。\n", pacing, speakers={"韩冬"})
        self.assertEqual(timeline["duration"], 3.25)

    def test_english_lines_are_timed_by_word(self):
        pacing = {"characters": None, "words": 2.0, "action": 3.0}
        timeline = breakdown.script_timeline("Mara: There are 2026 tickets.\n", pacing, speakers={"Mara"})
        self.assertEqual(timeline["duration"], 2.0)
        self.assertIsNone(breakdown.script_timeline("韩冬：走。\n", pacing, speakers={"韩冬"}))

    def test_a_colon_inside_a_one_off_action_line_is_not_dialogue(self):
        pacing = {"characters": 4.0, "words": None, "action": 3.0}
        text = "他写下两个字：军宣。\n\n韩冬（低声）：走。\n\n检验员：合格。\n"
        timeline = breakdown.script_timeline(text, pacing)
        self.assertEqual([segment["t"] for segment in timeline["segments"]], ["走。", "合格。"])
        self.assertEqual(timeline["duration"], 3.75)

    def test_a_long_speaker_name_counts_once_it_is_named(self):
        pacing = {"characters": None, "words": 2.0, "action": 3.0}
        text = "StationCommanderOfTheNorthGate: Open the gate.\n"
        self.assertEqual(breakdown.script_timeline(text, pacing, speakers={"StationCommanderOfTheNorthGate"})["duration"],
                         1.5)

    def test_a_scene_written_straight_under_its_heading_is_kept(self):
        pacing = {"characters": 4.0, "words": None, "action": 3.0}
        text = "## EP001-SC001 内 · 车间 · 日\n韩冬：走。\n"
        self.assertEqual(breakdown.script_timeline(text, pacing, speakers={"韩冬"})["duration"], 0.25)

    def test_speech_units_follow_the_script_of_each_word(self):
        pacing = {"characters": 4.0, "words": 2.0, "action": 3.0}
        cases = {"Mara: Naïve café.": 1.0, "Mara: I have 2 cats.": 2.0, "Mara: Привет, мир.": 1.0,
                 "Mara: こんにちは。": 1.25, "Mara: OK，走吧。": 1.0}
        for line, seconds in cases.items():
            with self.subTest(line=line):
                self.assertEqual(breakdown.script_timeline(line, pacing, speakers={"Mara"})["duration"], seconds)

    def test_on_screen_text_takes_its_declared_reading_time(self):
        pacing = {"characters": 4.0, "words": None, "action": 3.0, "reading": 2.0}
        timeline = breakdown.script_timeline("[画面文字] 招牌：城中村修车铺\n\n韩冬：走走走走。\n", pacing,
                                             speakers={"韩冬"})
        self.assertEqual(timeline["duration"], 5.0)
        del pacing["reading"]
        self.assertEqual(breakdown.script_timeline("[画面文字] 招牌：城中村修车铺\n\n韩冬：走走走走。\n", pacing,
                                                   speakers={"韩冬"})["duration"], 1.0)

    def test_transcript_density_counts_letters_of_any_script(self):
        numbers = breakdown.episode_numbers(episode(1, 10.0, [10.0], [(0.0, 2.0, "こんにちは、ミラ。")]))
        self.assertEqual(numbers["chars_per_speech_second"], 3.5)

    def test_a_note_inside_a_line_is_not_spoken(self):
        pacing = {"characters": 4.0, "words": None, "action": 3.0}
        timeline = breakdown.script_timeline("顾远：走。（压低声音）\n", pacing, speakers={"顾远"})
        self.assertEqual(timeline["duration"], 0.25)

    def test_speech_that_exactly_fills_the_storyboard_leaves_no_silence(self):
        pacing = {"characters": 4.0, "words": None, "action": 3.0}
        timeline = breakdown.script_timeline("他推门。\n\n顾远：一二三四五六七八。\n", pacing, 2.0, {"顾远"})
        self.assertEqual(timeline["segments"][0]["s"], 0.0)
        self.assertEqual(timeline["duration"], 2.0)

    def test_speech_longer_than_the_storyboard_is_reported_not_squeezed(self):
        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory) / "剧集" / "EP001"
            ep.mkdir(parents=True)
            (Path(directory) / "short-drama.json").write_text(json.dumps({"format": {"pacing": {
                "spoken_characters_per_second": 4.0, "seconds_per_action_paragraph": 3}}}), encoding="utf-8")
            (ep / "分镜.md").write_text("## SHOT-EP001-001 · 甲\n\n- 时长：1s\n", encoding="utf-8")
            (ep / "剧本.md").write_text("韩冬（急）：快把门关上别让他进来。\n", encoding="utf-8")
            record = breakdown.plan_episode(ep)
        self.assertIn("plan_problem", record)
        self.assertIsNone(record["segments"])


class EpisodeNumberTests(unittest.TestCase):
    def test_a_marked_episode_number_wins_over_other_digits(self):
        for stem, expected in (("E001_5550001234567890123", 1), ("2026短剧第3集", 3),
                               ("ep12-final", 12), ("片段07", 7), ("Love2026_EP002", 2),
                               ("夏夜第1季第2集", 2), ("Season1-E05", 5), ("第4话", 4)):
            with self.subTest(stem=stem):
                self.assertEqual(breakdown.episode_number(stem), expected)


class ProfileTests(unittest.TestCase):
    def test_opening_episodes_are_reported_apart_from_later_ones(self):
        records = [episode(1, 150.0, [3.0] * 50, [(0.0, 2.0, "你被开除了")])]
        records += [episode(n, 50.0, [2.5] * 20, [(0.2, 1.5, "第几集"), (48.0, 49.8, "收尾")])
                    for n in range(2, 9)]
        result = breakdown.profile(records, opening=1)
        self.assertEqual(result["opening"]["duration"], 150.0)
        self.assertEqual(result["later"]["duration"], 50.0)
        self.assertEqual(result["later"]["avg_shot"], 2.5)
        self.assertTrue(result["length_regime"]["later_fixed_length"])

    def test_speech_numbers_come_from_the_timed_transcript(self):
        record = episode(1, 10.0, [5.0, 5.0], [(1.0, 3.0, "一二三四"), (6.0, 9.0, "五六七八九十")])
        numbers = breakdown.episode_numbers(record)
        self.assertEqual(numbers["speech_share"], 0.5)
        self.assertEqual(numbers["chars_per_speech_second"], 2.0)
        self.assertEqual(numbers["first_line_at"], 1.0)
        self.assertEqual(numbers["tail_after_last_line"], 1.0)
        self.assertEqual(numbers["longest_silence"], 3.0)

    def test_an_opening_that_replays_the_last_ending_is_counted(self):
        replay = [
            episode(1, 40.0, [4.0] * 10, [(36.0, 39.0, "你今天走出这个门就别回来")]),
            episode(2, 40.0, [4.0] * 10, [(0.5, 3.0, "你今天走出这个门就别回来"), (37.0, 39.5, "门关上了")]),
            episode(3, 40.0, [4.0] * 10, [(0.3, 2.0, "第二天一早"), (37.0, 39.5, "完")]),
        ]
        self.assertEqual(breakdown.profile(replay, opening=1)["reprise_pairs"], {"checked": 2, "replayed": 1})


class PlanTests(unittest.TestCase):
    def test_a_plan_is_measured_in_the_same_shape_as_footage(self):
        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory) / "剧集" / "EP002"
            ep.mkdir(parents=True)
            (ep / "分镜.md").write_text(
                "## SHOT-EP002-001 · 推门\n\n- 时长：2s\n\n## SHOT-EP002-002 · 对视\n\n- 时长：4秒\n",
                encoding="utf-8",
            )
            (ep / "剧本.md").write_text(
                "## EP002-SC001 内 · 走廊 · 夜\n\n[画面文字] 三天后\n\n顾远（压低声）：别出声。\n\n"
                "[VO] 顾远：她还活着。\n\n[OS] 门外的人：开门！\n",
                encoding="utf-8",
            )
            out = Path(directory) / "measure"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(breakdown.main(["plan", directory, "--out", str(out)]), 0)
            record = json.loads((out / f"EP002{breakdown.MEASURE_SUFFIX}").read_text(encoding="utf-8"))
        self.assertEqual(record["episode"], 2)
        self.assertEqual(record["shot_seconds"], [2.0, 4.0])
        self.assertEqual(record["spoken_characters"], 3 + 4 + 2)
        numbers = breakdown.episode_numbers(record)
        self.assertEqual(numbers["avg_shot"], 3.0)
        # VO share counts punctuation, as the rhythm profile defines it: 5 of 4 + 5 + 3.
        self.assertEqual(numbers["vo_share"], 0.42)

    def test_shot_headings_without_matching_durations_leave_shot_length_unmeasured(self):
        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory)
            (ep / "分镜.md").write_text("## SHOT-EP001-001 · 甲\n\n- 时长：2s\n\n## SHOT-EP001-002 · 乙\n",
                                       encoding="utf-8")
            record = breakdown.plan_episode(ep)
        self.assertIsNone(record["shot_seconds"])
        self.assertIn("plan_problem", record)

    def test_plan_extracts_emphasized_and_halfwidth_colon_durations_per_shot_ignoring_preamble(self):
        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory) / "EP003"
            ep.mkdir()
            (ep / "分镜.md").write_text(
                "# EP003 分镜\n"
                "- 时长：60 秒\n\n"
                "## 场景站位 · EP003-SC001 · 走廊\n"
                "- 时长：15 秒\n\n"
                "## SHOT-EP003-001 · 推门\n"
                "- **时长**：2.5 秒\n\n"
                "## SHOT-EP003-002 · 对视\n"
                "- *时长*: 3.5s\n\n"
                "## 备注\n"
                "- 时长：10 秒\n",
                encoding="utf-8",
            )
            record = breakdown.plan_episode(ep)
        self.assertEqual(record["shot_seconds"], [2.5, 3.5])
        self.assertEqual(record["duration"], 6.0)
        self.assertNotIn("plan_problem", record)

    def test_duplicate_duration_in_one_shot_cannot_mask_missing_duration_in_another(self):
        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory) / "EP004"
            ep.mkdir()
            (ep / "分镜.md").write_text(
                "## SHOT-EP004-001 · 甲\n- 时长：2s\n- 时长：3s\n\n"
                "## SHOT-EP004-002 · 乙\n- 景别/机位：近景\n",
                encoding="utf-8",
            )
            record = breakdown.plan_episode(ep)
        self.assertIsNone(record["shot_seconds"])
        self.assertIn("plan_problem", record)


class PlanTimelineTests(unittest.TestCase):
    def write_project(self, root, episodes, pacing=True):
        if pacing:
            (root / "short-drama.json").write_text(json.dumps({"format": {"pacing": {
                "spoken_characters_per_second": 4.0, "seconds_per_action_paragraph": 3}}}), encoding="utf-8")
        for name, (screenplay, storyboard) in episodes.items():
            ep = root / "剧集" / name
            ep.mkdir(parents=True)
            (ep / "剧本.md").write_text(screenplay, encoding="utf-8")
            if storyboard:
                (ep / "分镜.md").write_text(storyboard, encoding="utf-8")

    def test_silent_time_stretches_to_the_storyboard_and_speech_keeps_its_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {"EP001": (
                "## EP001-SC001 内 · 车间 · 日\n\n他把扳手拍在台面上。\n\n韩冬（冷）：这台车今天修不好。\n",
                "## SHOT-EP001-001 · 拍扳手\n\n- 时长：6s\n\n## SHOT-EP001-002 · 开口\n\n- 时长：4s\n",
            )})
            record = breakdown.plan_episode(root / "剧集" / "EP001")
        numbers = breakdown.episode_numbers(record)
        self.assertEqual(record["duration"], 10.0)
        self.assertEqual(numbers["chars_per_speech_second"], 4.0)
        self.assertEqual(numbers["first_line_at"], 8.0)
        self.assertEqual(numbers["speech_share"], 0.2)

    def test_without_a_storyboard_the_script_estimate_gives_the_length(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {"EP002": ("林夏推门。\n\n林夏（平静）：我来拿回我的东西。\n", None)})
            record = breakdown.plan_episode(root / "剧集" / "EP002")
        self.assertEqual(record["duration"], 5.0)
        self.assertEqual(record["duration_source"], "script_estimate")

    def test_a_replayed_action_beat_counts_as_a_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {
                "EP001": ("韩冬：滚。\n\n老卡车猛地往前一冲，停在他膝前一拳处。\n", None),
                "EP002": ("老卡车猛地往前一冲，停在他膝前一拳处。\n\n他往后一跳。\n", None),
                "EP003": ("第二天一早，车间门口排起了队。\n", None),
            })
            records = [breakdown.plan_episode(root / "剧集" / name) for name in ("EP001", "EP002", "EP003")]
        self.assertEqual(breakdown.profile(records, opening=1)["reprise_pairs"], {"checked": 2, "replayed": 1})

    def test_a_replayed_off_screen_line_counts_as_a_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {
                "EP001": ("韩冬关上车间的门。\n\n[OS] 门外的人：你今天走不了。\n", None),
                "EP002": ("[OS] 门外的人：你今天走不了。\n\n韩冬抄起扳手。\n", None),
            })
            records = [breakdown.plan_episode(root / "剧集" / name) for name in ("EP001", "EP002")]
        self.assertEqual(breakdown.profile(records, opening=1)["reprise_pairs"], {"checked": 1, "replayed": 1})

    def test_lines_sharing_only_a_speaker_and_a_note_are_not_a_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {
                "EP001": ("顾远（压低声音）：开门。\n", None),
                "EP002": ("顾远（压低声音）：离开。\n", None),
            })
            records = [breakdown.plan_episode(root / "剧集" / name) for name in ("EP001", "EP002")]
        self.assertEqual(breakdown.profile(records, opening=1)["reprise_pairs"], {"checked": 1, "replayed": 0})

    def test_a_repeated_english_line_counts_as_a_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "short-drama.json").write_text(json.dumps({"format": {"pacing": {
                "spoken_words_per_second": 2.5, "seconds_per_action_paragraph": 3}}}), encoding="utf-8")
            for name, screenplay in {
                "EP001": "Mara slams the door.\n\nMara: You will never set foot in this house again.\n",
                "EP002": "Mara: You will never set foot in this house again.\n\nShe walks away.\n",
            }.items():
                ep = root / "剧集" / name
                ep.mkdir(parents=True)
                (ep / "剧本.md").write_text(screenplay, encoding="utf-8")
            records = [breakdown.plan_episode(root / "剧集" / name) for name in ("EP001", "EP002")]
        self.assertEqual(breakdown.profile(records, opening=1)["reprise_pairs"], {"checked": 1, "replayed": 1})

    def test_an_episode_without_lines_counts_as_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {"EP001": ("他推门。\n\n门外空无一人。\n", None)})
            record = breakdown.plan_episode(root / "剧集" / "EP001")
        numbers = breakdown.episode_numbers(record)
        self.assertEqual(numbers["speech_share"], 0.0)
        self.assertEqual(numbers["longest_silence"], 6.0)

    def test_commented_out_lines_are_not_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {"EP001": (
                "顾远：走。\n\n<!--\n[VO] 顾远：这一句已经删掉了不再演。\n-->\n", None)})
            record = breakdown.plan_episode(root / "剧集" / "EP001")
        self.assertEqual(record["spoken_characters"], 1)
        self.assertEqual(record["vo_characters"], 0)

    def test_a_project_without_pacing_reports_no_speech_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_project(root, {"EP001": ("韩冬：滚。\n", None)}, pacing=False)
            record = breakdown.plan_episode(root / "剧集" / "EP001")
        self.assertIsNone(record["segments"])
        self.assertIsNone(record["duration"])

    def test_spaced_foreign_speaker_with_ascii_parenthetical_cue_is_timed_as_speech(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "short-drama.json").write_text(
                json.dumps(
                    {
                        "format": {
                            "pacing": {
                                "spoken_words_per_second": 2.5,
                                "seconds_per_action_paragraph": 3,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            ep = root / "剧集" / "EP001"
            ep.mkdir(parents=True)
            (ep / "剧本.md").write_text(
                "## EP001-SC001 内 · 档案室 · 夜\n\n"
                "She steps back.\n\n"
                "Dr. Lin (whispering)：Stay back from the door.\n",
                encoding="utf-8",
            )
            record = breakdown.plan_episode(ep)
        numbers = breakdown.episode_numbers(record)
        self.assertEqual(record["duration"], 5.0)
        self.assertEqual(record["duration_source"], "script_estimate")
        self.assertEqual(len(record["segments"]), 1)
        self.assertEqual(record["segments"][0]["t"], "Stay back from the door.")
        self.assertEqual(numbers["speech_share"], 0.4)


class TranscriptOverrunTests(unittest.TestCase):
    def test_speech_past_the_end_of_the_picture_is_flagged_and_not_counted(self):
        record = episode(4, 10.0, [5.0, 5.0], [(1.0, 3.0, "一二三四"), (8.0, 14.0, "五六七八")])
        self.assertTrue(breakdown.transcript_overrun(record))
        self.assertEqual(breakdown.episode_numbers(record)["speech_share"], 0.2)
        self.assertEqual(breakdown.profile([record], opening=1)["transcript_overruns"], [4])

    def test_a_cue_wholly_after_the_picture_is_not_speech(self):
        numbers = breakdown.episode_numbers(episode(1, 10.0, [10.0], [(1.0, 3.0, "一二"), (10.1, 10.4, "三")]))
        self.assertEqual(numbers["speech_share"], 0.2)

    def test_a_closing_cue_that_runs_into_the_last_seconds_is_compared(self):
        phrase = "你今天走出这个门就别回来"
        records = [
            episode(1, 40.0, [40.0], [(27.0, 39.9, phrase)]),
            episode(2, 40.0, [40.0], [(0.5, 3.0, phrase)]),
        ]
        self.assertEqual(breakdown.profile(records, opening=1)["reprise_pairs"], {"checked": 1, "replayed": 1})

    def test_footage_whose_transcript_has_no_speech_counts_as_silent(self):
        silent = dict(episode(1, 10.0, [10.0], []), transcript_source="E001.json")
        voiced = dict(episode(2, 10.0, [10.0], [(0.0, 10.0, "一二三")]), transcript_source="E002.json")
        untranscribed = dict(episode(3, 10.0, [10.0], []), segments=None)
        self.assertEqual(breakdown.episode_numbers(silent)["speech_share"], 0.0)
        self.assertNotIn("speech_share", breakdown.episode_numbers(untranscribed))
        later = breakdown.profile([silent, voiced, untranscribed], opening=0)
        self.assertEqual(later["later"]["speech_share"], 0.5)

    def test_cues_past_the_picture_cannot_make_a_replay(self):
        phrase = "你今天走出这个门就别回来"
        records = [
            episode(1, 40.0, [40.0], [(30.0, 35.0, "第一集的真结尾"), (39.0, 60.0, phrase)]),
            episode(2, 40.0, [40.0], [(0.0, 50.0, phrase), (1.0, 3.0, "第二集开场")]),
        ]
        self.assertEqual(breakdown.profile(records, opening=1)["reprise_pairs"], {"checked": 1, "replayed": 0})


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class MeasureTests(unittest.TestCase):
    def test_a_same_length_replacement_cut_does_not_keep_the_old_transcript(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, out = root / "E009.avi", root / "measure"
            subtitles = root / "E009.srt"
            subtitles.write_text("1\n00:00:00,500 --> 00:00:01,500\n站住\n", encoding="utf-8")
            sizes = []
            for colour in ("red", "blue"):
                subprocess.run(quiet + ["-f", "lavfi", "-i", f"color=c={colour}:size=64x36:rate=12:d=2",
                                        "-c:v", "rawvideo", "-pix_fmt", "yuv420p", str(video)], check=True)
                sizes.append(video.stat().st_size)
                subprocess.run([sys.executable, str(SCRIPT), "measure", str(video), "--out", str(out), "--no-sheet"],
                               capture_output=True, check=True)
                if colour == "red":
                    subprocess.run([sys.executable, str(SCRIPT), "transcript",
                                    str(out / f"E009{breakdown.MEASURE_SUFFIX}"), str(subtitles)],
                                   capture_output=True, check=True)
            record = json.loads((out / f"E009{breakdown.MEASURE_SUFFIX}").read_text(encoding="utf-8"))
        self.assertEqual(sizes[0], sizes[1])
        self.assertIsNone(record["segments"])

    def test_every_measurement_reads_the_first_video_track(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second, video = root / "first.mp4", root / "second.mp4", root / "E003.mp4"
            # A cut at two seconds on the first track; a larger static track
            # after it, the one ffmpeg would choose on its own.
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=red:size=160x90:rate=24:d=2",
                                    "-f", "lavfi", "-i", "color=c=blue:size=160x90:rate=24:d=2",
                                    "-filter_complex", "[0][1]concat=n=2:v=1", "-pix_fmt", "yuv420p", str(first)],
                           check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=white:size=640x360:rate=24:d=4",
                                    "-pix_fmt", "yuv420p", str(second)], check=True)
            subprocess.run(quiet + ["-i", str(first), "-i", str(second), "-map", "0:v", "-map", "1:v",
                                    "-c", "copy", str(video)], check=True)
            cuts = breakdown.detect_cuts(video, 0.28)
            shown = breakdown.probe(video)
        self.assertEqual((shown["width"], shown["height"]), (160, 90))
        self.assertEqual(len(cuts), 1)
        self.assertAlmostEqual(cuts[0], 2.0, delta=0.1)

    def test_a_rotated_phone_clip_reports_the_picture_as_shown(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            plain, rotated = Path(directory) / "plain.mp4", Path(directory) / "rotated.mp4"
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=red:size=160x90:rate=24:d=1",
                                    "-pix_fmt", "yuv420p", str(plain)], check=True)
            made = subprocess.run(quiet + ["-display_rotation", "90", "-i", str(plain), "-c", "copy", str(rotated)],
                                  capture_output=True, check=False)
            if made.returncode != 0:
                self.skipTest("this ffmpeg cannot write a display rotation")
            shown = breakdown.probe(rotated)
        self.assertEqual((shown["width"], shown["height"]), (90, 160))

    def test_cuts_between_flat_colour_shots_are_found(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = []
            for index, (colour, seconds) in enumerate((("red", 2.0), ("blue", 1.5), ("white", 2.5))):
                part = root / f"{index}.mp4"
                subprocess.run(quiet + ["-f", "lavfi", "-i", f"color=c={colour}:size=160x90:rate=24:d={seconds}",
                                        "-pix_fmt", "yuv420p", str(part)], check=True)
                parts.append(part)
            listing = root / "list.txt"
            listing.write_text("".join(f"file '{part}'\n" for part in parts), encoding="utf-8")
            video = root / "E007.mp4"
            subprocess.run(quiet + ["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(video)],
                           check=True)
            out = root / "measure"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "measure", str(video), "--out", str(out)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((out / f"E007{breakdown.MEASURE_SUFFIX}").read_text(encoding="utf-8"))
            self.assertTrue((out / "E007.sheet.jpg").is_file())
            # Re-measuring with another threshold keeps the attached transcript.
            subtitles = root / "E007.srt"
            subtitles.write_text("1\n00:00:00,500 --> 00:00:01,500\n站住\n", encoding="utf-8")
            measured = out / f"E007{breakdown.MEASURE_SUFFIX}"
            for arguments in (["transcript", str(measured), str(subtitles)],
                              ["measure", str(video), "--out", str(out), "--no-sheet", "--scene-threshold", "0.4"]):
                subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, check=True)
            remeasured = json.loads(measured.read_text(encoding="utf-8"))
            # A replaced cut under the same name does not inherit the old transcript.
            shutil.copyfile(parts[0], video)
            subprocess.run([sys.executable, str(SCRIPT), "measure", str(video), "--out", str(out), "--no-sheet"],
                           capture_output=True, check=True)
            replaced = json.loads(measured.read_text(encoding="utf-8"))
        self.assertIsNone(replaced["segments"])
        self.assertNotIn("transcript_source", replaced)
        self.assertEqual(remeasured["scene_threshold"], 0.4)
        self.assertEqual(remeasured["transcript_source"], "E007.srt")
        self.assertEqual(record["episode"], 7)
        self.assertEqual(len(record["cuts"]), 2)
        for found, expected in zip(record["cuts"], (2.0, 3.5)):
            self.assertAlmostEqual(found, expected, delta=0.1)
        self.assertAlmostEqual(sum(record["shot_seconds"]), record["duration"], delta=0.05)


class AudioLogTests(unittest.TestCase):
    def test_voiced_time_is_what_silence_detection_leaves(self):
        log = ("[silencedetect @ 0x1] silence_start: 1.0\n[silencedetect @ 0x1] silence_end: 2.5 | silence_duration: 1.5\n"
               "[silencedetect @ 0x1] silence_start: 5.2\n")
        self.assertEqual(breakdown.voiced_intervals(log, 6.0), [[0.0, 1.0], [2.5, 5.2]])
        self.assertEqual(breakdown.voiced_intervals("", 6.0), [[0.0, 6.0]])
        # A silence already running at the start of the track.
        self.assertEqual(breakdown.voiced_intervals("silence_end: 0.8 | silence_duration: 0.8\n", 3.0), [[0.8, 3.0]])

    def test_loudness_comes_from_the_summary_not_the_frame_log(self):
        log = ("[Parsed_ebur128_1] t: 0.1 TARGET:-23 LUFS M: -30.0 S: -40.0 I: -50.0 LUFS LRA: 0.0 LU\n"
               "[Parsed_ebur128_1] Summary:\n  Integrated loudness:\n    I:         -16.5 LUFS\n"
               "  Loudness range:\n    LRA:         6.5 LU\n  True peak:\n    Peak:       -2.0 dBFS\n")
        self.assertEqual(breakdown.loudness_summary(log),
                         {"integrated_lufs": -16.5, "loudness_range_lu": 6.5, "true_peak_dbfs": -2.0})
        self.assertEqual(breakdown.loudness_summary("no summary")["integrated_lufs"], None)


class SubtitleEventTests(unittest.TestCase):
    PIXELS = 100

    def test_a_subtitle_runs_until_it_disappears_or_its_glyphs_change(self):
        first, second = (1 << 20) - 1, ((1 << 20) - 1) << 40
        masks = [0, first, first, first, second, second, 0, 0]
        events = breakdown.subtitle_events(masks, self.PIXELS, 10.0, 0.8, 0.04, 0.5, 0.15)
        self.assertEqual([(event["id"], event["start"], event["end"]) for event in events],
                         [("T001", 0.1, 0.4), ("T002", 0.4, 0.6)])

    def test_a_small_shift_of_the_same_glyphs_is_the_same_subtitle(self):
        glyphs = (1 << 30) - 1
        masks = [glyphs, glyphs, glyphs << 2, glyphs << 2]
        events = breakdown.subtitle_events(masks, self.PIXELS, 10.0, 0.4, 0.04, 0.5, 0.15)
        self.assertEqual([(event["start"], event["end"]) for event in events], [(0.0, 0.4)])

    def test_flickers_shorter_than_the_minimum_are_dropped(self):
        glyphs = (1 << 30) - 1
        events = breakdown.subtitle_events([0, glyphs, 0, 0], self.PIXELS, 10.0, 0.4, 0.04, 0.5, 0.15)
        self.assertEqual(events, [])

    def test_a_subtitle_exactly_at_the_minimum_is_kept_wherever_it_starts(self):
        glyphs = (1 << 30) - 1
        for masks in ([glyphs, glyphs, 0, 0], [0, glyphs, glyphs, 0]):
            events = breakdown.subtitle_events(masks, self.PIXELS, 10.0, 0.4, 0.04, 0.5, 0.2)
            self.assertEqual(len(events), 1, masks)

    def test_only_bright_pixels_beside_a_dark_outline_count_as_glyphs(self):
        # One row: an outlined stroke, then a flat lit area whose inside has no outline.
        row = bytes([0, 0, 250, 250, 0, 0] + [250] * 6)
        mask = breakdown.glyph_masks(row, len(row), 225, 80, 2)[0]
        self.assertEqual(format(mask, f"0{len(row)}b"), "001100110000")

    def test_with_a_colour_plane_the_glyph_is_where_the_colour_is_not_where_it_is_bright(self):
        # Grey row: a mid-grey stroke (a yellow glyph) and a white one, both outlined.
        grey = bytes([0, 0, 190, 190, 0, 0, 250, 250, 0, 0])
        hue = bytes([0, 0, 255, 255, 0, 0, 0, 0, 0, 0])
        by_brightness = breakdown.glyph_masks(grey, len(grey), 225, 80, 2)[0]
        by_colour = breakdown.glyph_masks(grey + hue, len(grey), 225, 80, 2, hue=True)[0]
        self.assertEqual(format(by_brightness, "010b"), "0000001100")
        self.assertEqual(format(by_colour, "010b"), "0011000000")

    def test_a_colour_must_be_six_hex_digits(self):
        self.assertEqual(breakdown.parse_color("#ffd400"), (255, 212, 0))
        for text in ("FFD4", "yellow", "GGGGGG"):
            with self.subTest(text=text), self.assertRaises(breakdown.BreakdownError):
                breakdown.parse_color(text)

    def test_shared_time_between_two_sets_of_spans(self):
        self.assertAlmostEqual(breakdown.overlap_seconds([[0, 2], [5, 6]], [(1, 5.5)]), 1.5)
        self.assertEqual(breakdown.overlap_seconds([[0, 1]], []), 0)


class SubtitleRowTests(unittest.TestCase):
    WIDTH = 100

    def test_subtitle_rows_show_and_change_a_watermark_only_shows(self):
        mark = (1 << 10) - 1
        frames = []
        for step in range(4):
            line = mark << (step % 2) * 40  # the subtitle row alternates between two lines
            frames += [mark, 0, 0, line]      # rows: watermark, empty, empty, subtitle
        profile, totals = breakdown.row_profile(frames, 4, self.WIDTH, bands=4, min_share=0.05)
        shown = [band["shown"] for band in profile]
        changed = [band["changed"] for band in profile]
        self.assertEqual(shown, [1.0, 0.0, 0.0, 1.0])
        self.assertEqual(changed, [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(totals, [20, 20, 20, 20])

    def test_frames_with_most_text_are_picked_apart_and_blank_episodes_still_give_frames(self):
        totals = [0, 9, 8, 0, 0, 0, 5, 0]
        self.assertEqual(breakdown.pick_frames(totals, fps=1.0, count=2, spacing=3.0), [1, 6])
        self.assertEqual(breakdown.pick_frames([0] * 8, fps=1.0, count=2, spacing=3.0), [2, 6])


class CandidateRunTests(unittest.TestCase):
    def test_flickering_candidates_merge_and_lone_ones_stay_apart(self):
        runs = breakdown.candidate_runs([5.1, 2.0, 5.2, 5.35, 9.0])
        self.assertEqual(runs, [{"at": 2.0, "until": 2.0, "frames": 1},
                                {"at": 5.1, "until": 5.35, "frames": 3},
                                {"at": 9.0, "until": 9.0, "frames": 1}])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class AudioAndShotTests(unittest.TestCase):
    def make_clip(self, root: Path) -> Path:
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        video = root / "E004.mp4"
        # Red for 2 s then blue for 2 s; a tone with one second of silence in the middle.
        subprocess.run(quiet + [
            "-f", "lavfi", "-i", "color=c=red:size=320x180:rate=24:d=2",
            "-f", "lavfi", "-i", "color=c=blue:size=320x180:rate=24:d=2",
            "-f", "lavfi", "-i", "aevalsrc='if(between(t,1.5,2.5),0,0.5*sin(2*PI*440*t))':s=48000:d=4",
            "-filter_complex", "[0][1]concat=n=2:v=1[v]", "-map", "[v]", "-map", "2:a",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)], check=True)
        return video

    def test_audio_stops_counting_voice_where_a_short_track_ends(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E009.mp4"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", "color=c=red:size=160x90:rate=24:d=4",
                            "-f", "lavfi", "-i", "sine=f=440:d=2", "-map", "0:v", "-map", "1:a",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True)
            record = json.loads(breakdown.measure_audio(video, root / "out", -35.0, 0.3).read_text(encoding="utf-8"))
        self.assertAlmostEqual(record["duration"], 4.0, delta=0.1)
        self.assertEqual(len(record["voiced"]), 1, record["voiced"])
        self.assertAlmostEqual(record["voiced"][0][1], 2.0, delta=0.1)
        self.assertAlmostEqual(record["voiced_share"], 0.5, delta=0.05)

    def test_audio_reports_voiced_intervals_and_loudness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = self.make_clip(root)
            measure_dir = root / "measure"
            subprocess.run([sys.executable, str(SCRIPT), "measure", str(video), "--out", str(measure_dir),
                            "--no-sheet"], capture_output=True, check=True)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "audio", str(video), "--measure",
                 str(measure_dir / f"E004{breakdown.MEASURE_SUFFIX}")],
                capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((measure_dir / f"E004{breakdown.AUDIO_SUFFIX}").read_text(encoding="utf-8"))
            silent = root / "silent.mp4"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            "color=c=red:size=160x90:rate=24:d=1", "-pix_fmt", "yuv420p", str(silent)], check=True)
            mute = json.loads(breakdown.measure_audio(silent, root / "out", -35.0, 0.3).read_text(encoding="utf-8"))
        self.assertTrue(record["has_audio"])
        self.assertEqual(record["evidence"], "measured")
        self.assertEqual(len(record["voiced"]), 2, record["voiced"])
        self.assertAlmostEqual(record["voiced"][0][1], 1.5, delta=0.1)
        self.assertAlmostEqual(record["voiced"][1][0], 2.5, delta=0.1)
        self.assertAlmostEqual(record["voiced_share"], 0.75, delta=0.05)
        self.assertIsNotNone(record["integrated_lufs"])
        self.assertFalse(mute["has_audio"])
        self.assertEqual((mute["voiced"], mute["voiced_share"]), ([], 0.0))

    def test_shots_cuts_one_clip_and_three_frames_per_measured_shot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "REF-A"
            root.mkdir()
            video = self.make_clip(root)
            measure_dir = root / "measure"
            subprocess.run([sys.executable, str(SCRIPT), "measure", str(video), "--out", str(measure_dir),
                            "--no-sheet"], capture_output=True, check=True)
            measure = measure_dir / f"E004{breakdown.MEASURE_SUFFIX}"
            completed = subprocess.run([sys.executable, str(SCRIPT), "shots", str(video), str(measure)],
                                       capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            folder = root / "shots" / "E004"
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            files = {path.name for path in folder.iterdir()}
            first_clip = breakdown.probe(folder / "S01.mp4")
            other = root / "other.mp4"
            shutil.copyfile(video, other)
            with open(other, "ab") as handle:
                handle.write(b"\0")
            with self.assertRaises(breakdown.BreakdownError):
                breakdown.cut_shots(other, measure, root / "elsewhere")
        self.assertEqual([shot["id"] for shot in manifest["shots"]], ["S01", "S02"])
        self.assertAlmostEqual(manifest["shots"][0]["end"], 2.0, delta=0.1)
        self.assertEqual(manifest["evidence"], "measured")
        for shot in manifest["shots"]:
            self.assertIn(shot["clip"], files)
            self.assertEqual(set(shot["frames"]), {"first", "mid", "last"})
            self.assertTrue(set(shot["frames"].values()) <= files)
        self.assertTrue(all(shot["candidate_cuts"] == [] for shot in manifest["shots"]))
        self.assertEqual((first_clip["width"], first_clip["height"]), (320, 180))
        self.assertAlmostEqual(first_clip["duration"], 2.0, delta=0.15)

    @staticmethod
    def mean_rgb(image: Path):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(image), "-vf", "scale=1:1", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return tuple(raw[:3])

    def test_the_last_frame_belongs_to_its_own_shot_at_a_low_frame_rate(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E007.mp4"
            # 12 fps red then blue, with an audio track that outlasts the picture.
            subprocess.run(quiet + [
                "-f", "lavfi", "-i", "color=c=red:size=320x180:rate=12:d=2",
                "-f", "lavfi", "-i", "color=c=blue:size=320x180:rate=12:d=2",
                "-f", "lavfi", "-i", "sine=f=440:d=4.4",
                "-filter_complex", "[0][1]concat=n=2:v=1[v]", "-map", "[v]", "-map", "2:a",
                "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True)
            measure = breakdown.measure_video(video, root / "measure", 0.28, False)
            manifest = json.loads(breakdown.cut_shots(video, measure, root / "shots").read_text(encoding="utf-8"))
            colours = {shot["id"]: {name: self.mean_rgb(root / "shots" / frame) if frame else None
                                    for name, frame in shot["frames"].items()} for shot in manifest["shots"]}
        self.assertEqual(sorted(colours), ["S01", "S02"])
        for shot, (dominant, other) in {"S01": (0, 2), "S02": (2, 0)}.items():
            for name, colour in colours[shot].items():
                self.assertIsNotNone(colour, f"{shot} {name}")
                self.assertGreater(colour[dominant], colour[other] + 100, f"{shot} {name} {colour}")

    def test_a_soft_change_inside_a_shot_is_listed_as_one_candidate(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E008.mp4"
            # The same pattern, then slightly darker: below the measure threshold, above the inner one.
            subprocess.run(quiet + [
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:d=2",
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:d=2",
                "-filter_complex", "[1]eq=brightness=-0.05[d];[0][d]concat=n=2:v=1[v]", "-map", "[v]",
                "-pix_fmt", "yuv420p", str(video)], check=True)
            measure = breakdown.measure_video(video, root / "measure", 0.28, False)
            record = json.loads(measure.read_text(encoding="utf-8"))
            manifest = json.loads(breakdown.cut_shots(video, measure, root / "shots").read_text(encoding="utf-8"))
        self.assertEqual(record["cuts"], [])
        runs = manifest["shots"][0]["candidate_cuts"]
        self.assertEqual(len(runs), 1, runs)
        self.assertAlmostEqual(runs[0]["at"], 2.0, delta=0.1)

    def test_a_digitally_silent_track_writes_strict_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E009.mp4"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", "color=c=red:size=160x90:rate=24:d=1",
                            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "1",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True)
            text = breakdown.measure_audio(video, root / "out", -35.0, 0.3).read_text(encoding="utf-8")
            refused = subprocess.run([sys.executable, str(SCRIPT), "audio", str(video), str(video),
                                      "--measure", str(root / "x.measure.json")],
                                     capture_output=True, text=True, check=False)
        record = json.loads(text, parse_constant=lambda name: self.fail(f"non-standard JSON {name}"))
        self.assertTrue(record["has_audio"])
        self.assertEqual(record["voiced"], [])
        self.assertEqual(refused.returncode, 2)

    def test_shots_refuse_to_write_into_the_source_folder_and_keep_the_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = self.make_clip(root).rename(root / "S01E01.mp4")
            measure = breakdown.measure_video(video, root / "measure", 0.28, False)
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            completed = subprocess.run([sys.executable, str(SCRIPT), "shots", str(video), str(measure),
                                        "--out", str(root)], capture_output=True, text=True, check=False)
            kept = (video.is_file(), (root / "manifest.json").is_file())
            other = root / "shots"
            other.mkdir()
            unrelated = other / "S01E02-notes.mp4"
            unrelated.write_bytes(b"x")
            breakdown.cut_shots(video, measure, other)
            survived = unrelated.is_file()
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(kept, (True, True))
        self.assertTrue(survived)

    def test_shot_clips_keep_the_short_side_at_most_720(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E005.mp4"
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=red:size=1080x1920:rate=12:d=1",
                                    "-pix_fmt", "yuv420p", str(video)], check=True)
            measure = breakdown.measure_video(video, root / "measure", 0.28, False)
            manifest = breakdown.cut_shots(video, measure, root / "shots")
            clip = breakdown.probe(manifest.parent / "S01.mp4")
        self.assertEqual((clip["width"], clip["height"]), (720, 1280))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class SubtitleScanTests(unittest.TestCase):
    def test_burned_in_lines_are_timed_and_cropped_and_a_lit_background_is_not_a_line(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E006.mp4"
            # A white frame, then two different striped "lines", then black.
            subprocess.run(quiet + [
                "-f", "lavfi", "-i", "color=c=black:size=640x360:rate=24:d=5", "-vf",
                "drawbox=c=white:t=fill:enable='between(t,0,0.99)',"
                "drawgrid=x=0:y=0:w=8:h=4000:t=2:c=white:enable='between(t,1.5,2.49)',"
                "drawgrid=x=4:y=0:w=8:h=4000:t=2:c=white:enable='between(t,2.5,3.5)'",
                "-pix_fmt", "yuv420p", str(video)], check=True)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "subtitles", str(video), "--out", str(root / "subs"),
                 "--band", "0,0,1,1"], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((root / "subs" / f"E006{breakdown.SUBTITLE_SUFFIX}").read_text(encoding="utf-8"))
            crops = [(root / "subs" / event["crop"]).is_file() for event in record["events"]]
            refused = subprocess.run(
                [sys.executable, str(SCRIPT), "subtitles", str(video), "--out", str(root / "subs"),
                 "--band", "0.9,0,0.1,1"], capture_output=True, text=True, check=False)
        self.assertEqual(record["evidence"], "measured")
        self.assertEqual(len(record["events"]), 2, record["events"])
        for event, (start, end) in zip(record["events"], [(1.5, 2.5), (2.5, 3.5)]):
            self.assertAlmostEqual(event["start"], start, delta=0.15)
            self.assertAlmostEqual(event["end"], end, delta=0.15)
        self.assertEqual(crops, [True, True])
        self.assertEqual(refused.returncode, 2)

    def test_amber_lines_need_their_colour_and_voiced_time_is_checked_against_them(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E007.mp4"
            # Amber stripes from 1 s to 3 s: too dim for the brightness test.
            subprocess.run(quiet + [
                "-f", "lavfi", "-i", "color=c=black:size=640x360:rate=24:d=4", "-vf",
                "drawgrid=x=0:y=0:w=16:h=4000:t=6:c=0xFFB000:enable='between(t,1,2.99)'",
                "-pix_fmt", "yuv444p", str(video)], check=True)
            audio = root / "audio"
            audio.mkdir()
            (audio / f"E007{breakdown.AUDIO_SUFFIX}").write_text(
                json.dumps({"voiced": [[0.0, 2.0]]}), encoding="utf-8")
            runs = {}
            for name, extra in (("grey", []), ("amber", ["--color", "FFB000", "--audio", str(audio)])):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT), "subtitles", str(video), "--out", str(root / name),
                     "--band", "0,0,1,1", "--no-crops", *extra], capture_output=True, text=True, check=False)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                runs[name] = json.loads((root / name / f"E007{breakdown.SUBTITLE_SUFFIX}").read_text(encoding="utf-8"))
        self.assertEqual(runs["grey"]["events"], [])
        self.assertEqual(len(runs["amber"]["events"]), 1, runs["amber"]["events"])
        self.assertAlmostEqual(runs["amber"]["events"][0]["start"], 1.0, delta=0.15)
        self.assertAlmostEqual(runs["amber"]["shown_seconds"], 2.0, delta=0.2)
        self.assertAlmostEqual(runs["amber"]["voiced_shown_share"], 0.5, delta=0.1)
        self.assertIsNone(runs["grey"]["voiced_shown_share"])

    def test_the_calibration_sheet_points_at_the_band_where_lines_come_and_go(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "E008.mp4"
            # Stripes over the whole frame, blacked out except a strip at 0.80–0.90
            # height; their phase flips every second, like successive lines.
            stripes = ",".join(
                f"drawgrid=x={offset}:y=0:w=16:h=4000:t=3:c=white:enable='eq(mod(floor(t),2),{phase})'"
                for phase, offset in ((0, 0), (1, 8)))
            subprocess.run(quiet + [
                "-f", "lavfi", "-i", "color=c=black:size=640x360:rate=24:d=8", "-vf",
                f"{stripes},drawbox=x=0:y=0:w=iw:h=ih*0.8:c=black:t=fill,"
                "drawbox=x=0:y=ih*0.9:w=iw:h=ih*0.1:c=black:t=fill",
                "-pix_fmt", "yuv420p", str(video)], check=True)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "subtitle-sheet", str(video), "--out", str(root / "cal"),
                 "--frames", "2"], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((root / "cal" / "subtitle-rows.json").read_text(encoding="utf-8"))
            sheet_kept = (root / "cal" / record["sheet"]).is_file()
        rows = record["videos"][0]["rows"]
        lit = [band for band in rows if band["shown"] > 0.5]
        self.assertTrue(sheet_kept)
        self.assertEqual(len(record["videos"][0]["frames_at"]), 2)
        self.assertTrue(lit)
        self.assertTrue(all(0.78 <= band["top"] and band["bottom"] <= 0.92 for band in lit), lit)
        self.assertTrue(any(band["changed"] > 0 for band in lit), lit)


class RoundThreePlanAndSpeakerTests(unittest.TestCase):
    def test_optional_and_case_insensitive_duration_units_and_malformed_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory) / "EP005"
            ep.mkdir()
            (ep / "分镜.md").write_text(
                "<!--\n## SHOT-EP005-000 · 已注释镜\n- 时长：9s\n-->\n"
                "## SHOT-EP005-001 · 甲\n- 时长：4\n\n"
                "## SHOT-EP005-002 · 乙\n- 时长：2.5S\n\n"
                "## SHOT-EP005-003 · 丙\n- 时长：3.5秒\n",
                encoding="utf-8",
            )
            valid = breakdown.plan_episode(ep)
            self.assertEqual(valid["shot_seconds"], [4.0, 2.5, 3.5])
            self.assertEqual(valid["duration"], 10.0)
            self.assertNotIn("plan_problem", valid)

            for bad_duration in ("...s", "1.2.3s"):
                with self.subTest(bad_duration=bad_duration):
                    (ep / "分镜.md").write_text(
                        f"## SHOT-EP005-001 · 甲\n- 时长：{bad_duration}\n",
                        encoding="utf-8",
                    )
                    broken = breakdown.plan_episode(ep)
                    self.assertIsNone(broken["shot_seconds"])
                    self.assertIn("plan_problem", broken)

    def test_plan_resolves_dot_and_relative_episode_dirs_and_finds_project_pacing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "short-drama.json").write_text(
                json.dumps(
                    {
                        "format": {
                            "pacing": {
                                "spoken_characters_per_second": 4.0,
                                "seconds_per_action_paragraph": 2,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            ep = root / "剧集" / "EP001"
            ep.mkdir(parents=True)
            (ep / "剧本.md").write_text(
                "## EP001-SC001 内 · 走廊 · 夜\n\n许棠：站住别动。\n",
                encoding="utf-8",
            )
            out_dot = root / "measure_dot"
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "plan", ".", "--out", str(out_dot)],
                cwd=str(ep),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse((out_dot / ".measure.json").exists())
            dot_record = json.loads((out_dot / "EP001.measure.json").read_text(encoding="utf-8"))
            self.assertEqual(dot_record["source"], "EP001")
            self.assertEqual(dot_record["episode"], 1)
            self.assertEqual(dot_record["duration"], 1.0)
            self.assertEqual(dot_record["duration_source"], "script_estimate")

            out_rel = root / "measure_rel"
            completed_rel = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "plan", "EP001", "--out", str(out_rel)],
                cwd=str(root / "剧集"),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed_rel.returncode, 0, completed_rel.stderr)
            rel_record = json.loads((out_rel / "EP001.measure.json").read_text(encoding="utf-8"))
            self.assertEqual(rel_record["episode"], 1)
            self.assertEqual(rel_record["duration"], 1.0)

    def test_preamble_cast_clock_and_six_char_or_two_word_latin_speakers(self):
        script = (
            "# EP001 雨夜重逢\n\n"
            "人物：许棠、沈砚\n\n"
            "一句话梗概：前情备注：不计入正片。\n\n"
            "## EP001-SC001 内外 · 门厅 · 夜\n\n"
            "人物：许棠\n\n"
            "12:30 监控屏幕亮起。\n\n"
            "爱新觉罗玄烨：平身吧。\n\n"
            "Elena Vance: Stay back.\n"
        )
        speakers = breakdown.screenplay_speakers(script)
        self.assertNotIn("人物", speakers)
        self.assertNotIn("一句话梗概", speakers)
        self.assertNotIn("12", speakers)
        self.assertIn("爱新觉罗玄烨", speakers)
        self.assertIn("Elena Vance", speakers)

        pacing = {"characters": 3.0, "words": 2.0, "action": 3.0}
        timeline = breakdown.script_timeline(script, pacing)
        self.assertIsNotNone(timeline)
        self.assertEqual(
            [seg["t"] for seg in timeline["segments"]],
            ["平身吧。", "Stay back."],
        )
        # 1 action block (3.0s) + 3 Chinese chars (1.0s) + 2 English words (1.0s) = 5.0s
        self.assertEqual(timeline["duration"], 5.0)

    def test_plan_problems_accumulate_surface_in_profile_and_reject_non_finite_pacing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "short-drama.json").write_text(
                json.dumps(
                    {
                        "format": {
                            "pacing": {
                                "spoken_words_per_second": 2.0,
                                "seconds_per_action_paragraph": 2,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            ep = root / "剧集" / "EP001"
            ep.mkdir(parents=True)
            (ep / "分镜.md").write_text("## SHOT-EP001-001 · 甲\n", encoding="utf-8")
            (ep / "剧本.md").write_text(
                "## EP001-SC001 内 · 走廊 · 夜\n\n许棠：站住。\n",
                encoding="utf-8",
            )
            record = breakdown.plan_episode(ep)
            self.assertIn("分镜.md", record["plan_problem"])
            self.assertIn("剧本里有项目没声明语速单位", record["plan_problem"])
            self.assertIn("；", record["plan_problem"])

            prof = breakdown.profile([record], opening=3)
            self.assertEqual(prof["plan_problems"], {"1": record["plan_problem"]})
            rendered = breakdown.render_table({"PLAN": prof})
            self.assertIn("计划缺口", rendered)
            self.assertIn("第1集", rendered)

            (root / "short-drama.json").write_text(
                '{"format": {"pacing": {"spoken_characters_per_second": NaN, "seconds_per_action_paragraph": 2}}}',
                encoding="utf-8",
            )
            self.assertIsNone(breakdown.project_pacing(ep))

    def test_crlf_bom_cast_scoping_parenthetical_notes_and_section_scoped_duration(self):
        script_crlf_bom = (
            "\ufeff# EP001 · 夜奔\r\n\r\n"
            "- **人物：**许棠（女主，24岁，冷面）、顾沉(男主;西装)、【待定】、待定、暂无、无、TBD、待补。\r\n\r\n"
            "## EP001-SC001 内 · 走廊 · 夜\r\n"
            "人物：林叔（门卫，老年）。\r\n"
            "许棠：\u3000站住。\r\n\r\n"
            "桌上压着一张旧便条，第二行写着\r\n"
            "人物：假角色不应被计入说话人。\r\n\r\n"
            "[OS] 顾沉：\u3000别回头。\r\n"
        )
        speakers = breakdown.screenplay_speakers(script_crlf_bom)
        self.assertEqual(speakers, {"许棠", "顾沉", "林叔"})

        lines = breakdown.spoken_lines(script_crlf_bom, speakers)
        self.assertEqual(lines, [(None, "站住。"), ("OS", "别回头。")])

        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory) / "EP001"
            ep.mkdir()
            (ep / "剧本.md").write_bytes(script_crlf_bom.encode("utf-8"))
            board_crlf_bom = (
                "\ufeff# EP001 分镜\r\n"
                "- 备注：保留行内 `<!-- 字面量` 代码片段。\r\n\r\n"
                "## SHOT-EP001-001 · 起步\r\n"
                "- **时长：**\u30003.5s（含尾韵）\r\n"
                "### 首帧提示词\r\n"
                "> - 时长：99s\r\n\r\n"
                "##\u3000SHOT-EP001-002 · 停步\r\n"
                "- ***时长***：2.5 秒(定格)\r\n"
                "<!-- 未闭合尾部注释\r\n"
            )
            (ep / "分镜.md").write_bytes(board_crlf_bom.encode("utf-8"))
            planned = breakdown.plan_episode(ep)
            self.assertEqual(planned["shot_seconds"], [3.5, 2.5])
            self.assertEqual(planned["duration"], 6.0)
            self.assertNotIn("plan_problem", planned)

            # Fenced code blocks in 剧本.md and 分镜.md must not leak fake speakers or shots.
            fenced_script = (
                "# EP001\n\n"
                "```markdown\n"
                "人物：示例角色\n\n"
                "## EP001-SC099 内 · 示例场景 · 日\n\n"
                "示例角色：这段代码块台词不应计入。\n"
                "```\n\n"
                "## EP001-SC001 内 · 走廊 · 夜\n\n"
                "许棠：只算这一句。\n"
            )
            self.assertEqual(breakdown.screenplay_speakers(fenced_script), {"许棠"})
            self.assertEqual(
                breakdown.spoken_lines(fenced_script, {"许棠", "示例角色"}),
                [(None, "只算这一句。")],
            )
            (ep / "剧本.md").write_text(fenced_script, encoding="utf-8")
            (ep / "分镜.md").write_text(
                "```markdown\n"
                "## SHOT-EP001-999 · 代码块示例镜\n"
                "- 时长：88s\n"
                "```\n\n"
                "## SHOT-EP001-001 · 真实镜头\n"
                "- 时长：4s\n",
                encoding="utf-8",
            )
            fenced_plan = breakdown.plan_episode(ep)
            self.assertEqual(fenced_plan["shot_seconds"], [4.0])
            self.assertEqual(fenced_plan["duration"], 4.0)
            self.assertNotIn("plan_problem", fenced_plan)


if __name__ == "__main__":
    unittest.main()
