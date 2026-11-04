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
                               ("ep12-final", 12), ("片段07", 7)):
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
        self.assertEqual(numbers["vo_share"], 0.44)

    def test_shot_headings_without_matching_durations_leave_shot_length_unmeasured(self):
        with tempfile.TemporaryDirectory() as directory:
            ep = Path(directory)
            (ep / "分镜.md").write_text("## SHOT-EP001-001 · 甲\n\n- 时长：2s\n\n## SHOT-EP001-002 · 乙\n",
                                       encoding="utf-8")
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


class TranscriptOverrunTests(unittest.TestCase):
    def test_speech_past_the_end_of_the_picture_is_flagged_and_not_counted(self):
        record = episode(4, 10.0, [5.0, 5.0], [(1.0, 3.0, "一二三四"), (8.0, 14.0, "五六七八")])
        self.assertTrue(breakdown.transcript_overrun(record))
        self.assertEqual(breakdown.episode_numbers(record)["speech_share"], 0.2)
        self.assertEqual(breakdown.profile([record], opening=1)["transcript_overruns"], [4])

    def test_cues_past_the_picture_cannot_make_a_replay(self):
        phrase = "你今天走出这个门就别回来"
        records = [
            episode(1, 40.0, [40.0], [(30.0, 35.0, "第一集的真结尾"), (39.0, 60.0, phrase)]),
            episode(2, 40.0, [40.0], [(0.0, 50.0, phrase), (1.0, 3.0, "第二集开场")]),
        ]
        self.assertEqual(breakdown.profile(records, opening=1)["reprise_pairs"], {"checked": 1, "replayed": 0})


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class MeasureTests(unittest.TestCase):
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
        self.assertEqual(remeasured["scene_threshold"], 0.4)
        self.assertEqual(remeasured["transcript_source"], "E007.srt")
        self.assertEqual(record["episode"], 7)
        self.assertEqual(len(record["cuts"]), 2)
        for found, expected in zip(record["cuts"], (2.0, 3.5)):
            self.assertAlmostEqual(found, expected, delta=0.1)
        self.assertAlmostEqual(sum(record["shot_seconds"]), record["duration"], delta=0.05)


if __name__ == "__main__":
    unittest.main()
