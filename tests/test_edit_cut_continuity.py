import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/short-drama-edit/scripts/edit_tool.py"
SPEC = importlib.util.spec_from_file_location("edit_cut_continuity", SCRIPT)
assert SPEC and SPEC.loader
edit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edit)

S1 = ("EP001-SC001",)
S2 = ("EP001-SC002",)


def cut(cut_id, picture=None, untouched=False, screen_texts=()):
    return edit.Cut(cut_id, "段", f"MOTION-{cut_id}", f"{cut_id}.mp4", 0.0, 1.0, 1.0, (),
                    picture or {}, 1, screen_texts, (), untouched)


def stats(mean, spread):
    return edit.ChannelStats((mean,) * 3, (spread,) * 3)


def frame(level, size=64):
    return bytes([level]) * size


class ShotMatchTests(unittest.TestCase):
    def test_each_cut_moves_seventy_percent_toward_the_scene_median(self):
        cuts = [cut("A"), cut("B"), cut("C")]
        measured = {"A": stats(100, 40), "B": stats(120, 50), "C": stats(150, 60)}
        plan = edit._plan_shot_match(cuts, [S1, S1, S1], lambda c: measured[c.cut_id])

        self.assertEqual(set(plan), {"A", "B", "C"})
        # A: mean 100 → 114, spread 40 → 47, so gain 47/40 and offset 114 − gain·100.
        self.assertAlmostEqual(plan["A"].gains[0], 1.175)
        self.assertAlmostEqual(plan["A"].offsets[0], -3.5)
        # The median cut is left as it is.
        self.assertAlmostEqual(plan["B"].gains[0], 1.0)
        self.assertAlmostEqual(plan["B"].offsets[0], 0.0)
        for cut_id, before in measured.items():
            match = plan[cut_id]
            after_mean = before.mean[0] * match.gains[0] + match.offsets[0]
            self.assertAlmostEqual(after_mean, before.mean[0] + 0.7 * (120 - before.mean[0]))
        # Gains and offsets are on the 0-255 scale they were measured on, so the
        # lookup has to run on 8-bit RGB whatever the source's bit depth.
        self.assertTrue(edit._auto_match_filter(plan["A"]).startswith(
            "format=rgb24,lutrgb=r='val*1.1750-3.500'"))

    def test_gain_is_held_to_a_plausible_grade_for_a_flat_clip(self):
        cuts = [cut("A"), cut("B")]
        measured = {"A": stats(10, 2), "B": stats(120, 60)}
        plan = edit._plan_shot_match(cuts, [S1, S1], lambda c: measured[c.cut_id])
        self.assertEqual(plan["A"].gains[0], edit.SHOT_MATCH_GAIN_LIMITS[1])

    def test_stated_correction_and_untouched_cuts_are_neither_matched_nor_counted(self):
        cuts = [cut("A"), cut("B", picture={"brightness": 0.05}), cut("C", untouched=True), cut("D")]
        measured = {"A": stats(100, 50), "B": stats(250, 50), "C": stats(5, 50), "D": stats(140, 50)}
        filters, plan = edit._picture_plan(
            cuts, [S1] * 4, lambda c: measured[c.cut_id], enabled=True
        )
        self.assertEqual(set(plan), {"A", "D"})
        # The median is of A and D alone: 120.
        self.assertAlmostEqual(plan["A"].offsets[0], 0.7 * 20)
        self.assertEqual(filters[1], "eq=brightness=0.05")
        self.assertEqual(filters[2], "")
        self.assertTrue("lutrgb=" in filters[0] and "lutrgb=" in filters[3])

        off, plan = edit._picture_plan(cuts, [S1] * 4, lambda c: measured[c.cut_id], enabled=False)
        self.assertEqual(plan, {})
        self.assertEqual(off, ["", "eq=brightness=0.05", "", ""])

    def test_only_consecutive_cuts_of_one_scene_are_matched_together(self):
        cuts = [cut(name) for name in "ABCDEF"]
        measured = {"A": stats(100, 50), "B": stats(120, 50), "C": stats(20, 50),
                    "D": stats(40, 50), "E": stats(200, 50), "F": stats(10, 50)}
        read = []

        def measure(c):
            read.append(c.cut_id)
            return measured[c.cut_id]

        plan = edit._plan_shot_match(cuts, [S1, S1, S2, S2, None, S1], measure)
        self.assertEqual(set(plan), {"A", "B", "C", "D"})
        # A cut with no neighbour from its scene is never decoded.
        self.assertEqual(read, ["A", "B", "C", "D"])
        self.assertAlmostEqual(plan["A"].offsets[0], 0.7 * 10)
        self.assertAlmostEqual(plan["C"].offsets[0], 0.7 * 10)
        self.assertEqual(edit._plan_shot_match(
            cuts[:3], [S1, S2, S1], lambda c: measured[c.cut_id]), {})

    def test_scene_is_traced_from_motion_through_storyboard_source(self):
        with tempfile.TemporaryDirectory() as directory:
            episode = Path(directory)
            (episode / edit.MOTION_DOCUMENT).write_text(
                "## MOTION-1 · 甲\n- 分镜：SHOT-1\n\n## MOTION-2 · 乙\n- 分镜：SHOT-2\n\n"
                "## MOTION-3 · 丙\n- 分镜：SHOT-3\n\n## MOTION-4 · 丁\n- 时长：3s\n",
                encoding="utf-8",
            )
            (episode / edit.STORYBOARD_DOCUMENT).write_text(
                "## SHOT-1 · 甲\n- 来源：EP001-SC001 周团推材料\n\n"
                "## SHOT-2 · 乙\n- 来源：EP001-SC001\n\n"
                "## SHOT-3 · 丙\n- 来源：EP001-SC001、EP001-SC002\n",
                encoding="utf-8",
            )
            cuts = [edit.Cut(f"CUT-{i}", "段", f"MOTION-{i}", "x.mp4", 0, 1, 1, (), {}, 1)
                    for i in (1, 2, 3, 4)]
            keys = edit._scene_keys(episode, cuts)
        self.assertEqual(keys, [S1, S1, ("EP001-SC001", "EP001-SC002"), None])

    def test_cut_list_turns_the_match_off_or_keeps_one_cut_as_generated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / edit.CUT_LIST_NAME
            block = ("## CUT-{n} · 段\n- 来源：MOTION-{n} · a.mp4\n- 入点：0\n- 出点：1\n"
                     "- 时长：1\n- 画面：{picture}\n\n")
            body = block.format(n=1, picture="无") + block.format(n=2, picture="不校")
            path.write_text("# 剪辑单\n\n" + body, encoding="utf-8")
            delivery, cuts, _ = edit.parse_cut_list(path)
            self.assertTrue(delivery.shot_match)
            self.assertEqual([(c.picture, c.untouched) for c in cuts], [({}, False), ({}, True)])

            path.write_text("# 剪辑单\n\n- 接镜匹配：无\n\n" + body, encoding="utf-8")
            self.assertFalse(edit.parse_cut_list(path)[0].shot_match)


class FrameReportTests(unittest.TestCase):
    def test_one_frame_unlike_both_neighbours_is_flagged(self):
        frames = [frame(100)] * 6 + [bytes([255]) * 16 + bytes([100]) * 48] + [frame(100)] * 6
        self.assertEqual([hit[0] for hit in edit._suspect_frames(frames)], [6])

    def test_smooth_motion_flicker_and_hard_cuts_are_not_flagged(self):
        cases = {
            "fast steady change": [frame(10 * i) for i in range(20)],
            "sub-threshold wobble": [frame(100)] * 5 + [frame(105)] + [frame(100)] * 5,
            "hard cut": [frame(40)] * 6 + [frame(160)] * 6,
        }
        for name, frames in cases.items():
            with self.subTest(name):
                self.assertEqual(edit._suspect_frames(frames), [])

    def test_cut_luma_changes_are_reported_and_large_ones_listed_for_a_look(self):
        frames = [frame(level + i) for level in (100, 140, 145) for i in range(10)]
        cuts = [cut("A"), cut("B"), cut("C")]
        report = edit._frame_report(frames, 10.0, cuts, [1.0, 1.0, 1.0], [S1, S1, S2])
        self.assertEqual(
            [(row["切点秒"], row["前段"], row["后段"], row["亮度变化"], row["场景"])
             for row in report["切点亮度变化"]],
            [(1.0, "A", "B", 31.0, "同场"), (2.0, "B", "C", -4.0, "换场")],
        )
        self.assertEqual(report["疑似坏帧"], [])
        self.assertEqual(len(report["请逐帧查看"]), 1)
        self.assertIn("A", report["请逐帧查看"][0])

    def test_a_suspect_frame_at_a_panel_entrance_is_labelled_as_one(self):
        entering = edit.ScreenText(0.5, 0.9, "系统面板", ("认证通过",))
        cuts = [cut("A", screen_texts=(entering,))]
        frames = [frame(100)] * 5 + [frame(160)] + [frame(100)] * 4 + [frame(160)] + [frame(100)] * 4
        report = edit._frame_report(frames, 10.0, cuts, [1.0], [S1])
        self.assertEqual(
            [(row["帧"], row["画面文字入场"]) for row in report["疑似坏帧"]],
            [(5, True), (10, False)],
        )
        self.assertEqual(len(report["请逐帧查看"]), 2)

    def test_unreadable_film_is_reported_unmeasured(self):
        report = edit._frame_report(None, 30.0, [cut("A")], [1.0], [S1])
        self.assertTrue(report["疑似坏帧"].startswith("未测"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class RenderedMatchTests(unittest.TestCase):
    def test_render_narrows_a_within_scene_jump_and_verify_measures_it(self):
        # A 10-bit source must be corrected by the same amount as an 8-bit one.
        for pixel_format in ("yuv420p", "yuv420p10le"):
            with self.subTest(pixel_format):
                self.render_and_measure(pixel_format)

    def render_and_measure(self, pixel_format):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = root / "剧集" / "EP001"
            (episode / "media").mkdir(parents=True)
            for index, level in ((1, "0x505050"), (2, "0x8C8C8C")):
                made = subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                     "-i", f"color=c={level}:size=90x160:rate=10:duration=1",
                     "-pix_fmt", pixel_format, str(episode / "media" / f"{index}.mp4")],
                    check=False,
                )
                if made.returncode != 0:
                    self.skipTest(f"this ffmpeg cannot write {pixel_format}")
            (episode / edit.MOTION_DOCUMENT).write_text(
                "## MOTION-1\n- 分镜：SHOT-1\n\n## MOTION-2\n- 分镜：SHOT-2\n", encoding="utf-8"
            )
            (episode / edit.STORYBOARD_DOCUMENT).write_text(
                "## SHOT-1\n- 来源：EP001-SC001\n\n## SHOT-2\n- 来源：EP001-SC001\n", encoding="utf-8"
            )
            cuts = [edit.Cut(f"CUT-{i}", "段", f"MOTION-{i}", f"media/{i}.mp4", 0, 1, 1, (), {}, 1)
                    for i in (1, 2)]
            delivery = edit.Delivery(None, None, False, None, None, None)
            report = edit.render(episode, root, cuts, delivery, burn_subtitles=False)
            measured = edit.verify(episode, cuts, delivery)

        self.assertEqual(set(report["自动接镜"]), {"CUT-1", "CUT-2"})
        (jump,) = measured["切点亮度变化"]
        # 60 apart before; each side moves 70% toward the middle, leaving 30%.
        self.assertAlmostEqual(jump["亮度变化"], 0.3 * 60, delta=3)
        self.assertEqual(measured["疑似坏帧"], [])


if __name__ == "__main__":
    unittest.main()
