import importlib.util
import json
import math
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/short-drama-edit/scripts/edit_tool.py"
SPEC = importlib.util.spec_from_file_location("edit_measurements", SCRIPT)
assert SPEC and SPEC.loader
edit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edit)


class EditMeasurementsTests(unittest.TestCase):
    def test_checks_reject_mixed_dimensions_or_fps_before_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cuts = [edit.Cut(f"CUT-{i}", "shot", f"MOTION-{i}", f"{i}.mp4",
                             0, 2, 2, (), {}, i) for i in (1, 2)]
            (root / edit.MOTION_DOCUMENT).write_text("## MOTION-1\n\n## MOTION-2\n")
            for i in (1, 2):
                (root / f"{i}.mp4").touch()
            first = {"width": 1344, "height": 768, "fps": 24, "duration": 5}
            for changes, expected in (({}, 0), ({"width": 1282, "height": 718}, 1),
                                      ({"fps": 30}, 1)):
                with self.subTest(changes=changes), patch.object(
                    edit, "probe_stream", side_effect=[first, {**first, **changes}]
                ):
                    findings = edit.check_cuts(root, cuts, root, probe=True)
                self.assertEqual(len(findings), expected)

    def test_omission_requires_exact_id_and_nonempty_reason(self):
        known = {"MOTION-EP001-001"}
        for note in (
            "MOTION-EP001-0010（理由：重复）",
            "MOTION-EP001-002（理由：已用 MOTION-EP001-001）",
            "MOTION-EP001-001",
            "MOTION-EP001-001（理由： ）",
        ):
            with self.subTest(note=note):
                self.assertTrue(edit._unaccounted_shots(known, [], [note]))
        self.assertEqual(
            edit._unaccounted_shots(known, [], ["MOTION-EP001-001（理由：重复信息）"]), []
        )
        self.assertEqual(
            edit._unaccounted_shots(known, [SimpleNamespace(motion=next(iter(known)))], []), []
        )

    def test_colour_observations_follow_current_cuts_and_report_missing_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            segments = root / edit.SEGMENT_DIRECTORY
            segments.mkdir()
            for name in ("DAY", "NIGHT", "STALE"):
                (segments / f"{name}.mp4").touch()
            cuts = [SimpleNamespace(cut_id=name) for name in ("NIGHT", "MISSING", "DAY")]
            with patch.object(edit, "_segment_colour", side_effect=[(30, 20), (180, -10)]) as measure:
                rows = edit._segment_colours("ffmpeg", root, cuts)
            self.assertEqual([c.args[1].stem for c in measure.call_args_list], ["NIGHT", "DAY"])
            self.assertEqual(rows, [
                {"分段": "NIGHT.mp4", "平均亮度": 30, "蓝减红": 20},
                {"分段": "MISSING.mp4", "测量": "未测（分段缺失或不可读）"},
                {"分段": "DAY.mp4", "平均亮度": 180, "蓝减红": -10},
            ])

    def test_unreadable_colour_sample_is_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / edit.SEGMENT_DIRECTORY).mkdir()
            (root / edit.SEGMENT_DIRECTORY / "BROKEN.mp4").touch()
            with patch.object(edit, "_segment_colour", return_value=None):
                rows = edit._segment_colours("ffmpeg", root, [SimpleNamespace(cut_id="BROKEN")])
            self.assertEqual(rows, [{"分段": "BROKEN.mp4", "测量": "未测（分段缺失或不可读）"}])


STORYBOARD = "## SHOT-1 · 甲\n- 来源：EP001-SC001\n\n## SHOT-2 · 乙\n- 来源：EP001-SC001\n"
S1, S2 = ("EP001-SC001",), ("EP001-SC002",)
SPEC_LINE = "- 画幅与帧率：180×320 · 24fps\n"
EXCUSE_TWO = "- 未采用镜头：SHOT-2（理由：叙事取舍）\n"


def still_block(number, source, extra=(), *, start=0.0, end=2.0):
    return (
        f"## CUT-{number} · 段\n\n- 来源：{source}\n"
        f"- 入点：{start:.2f}\n- 出点：{end:.2f}\n- 时长：{end - start:.2f}\n"
        "- 取舍：入点=起；出点=止\n- 声音：配音\n"
        + "".join(f"{line}\n" for line in extra) + "\n"
    )


class StillProject:
    """An episode whose cuts are keyframes; every file named below exists, empty."""

    def __init__(self, root: Path):
        self.root = root
        self.episode = root / "剧集" / "EP001"
        (self.episode / "media").mkdir(parents=True)
        (self.episode / edit.STORYBOARD_DOCUMENT).write_text(STORYBOARD, encoding="utf-8")
        for name in ("1.png", "2.jpg", "1.mp4", "line.wav", "reply.wav"):
            (self.episode / "media" / name).write_bytes(b"")

    def write(self, *blocks, head=SPEC_LINE):
        (self.episode / edit.CUT_LIST_NAME).write_text(
            "# 剪辑单\n\n" + head + "\n" + "".join(blocks), encoding="utf-8"
        )

    def parse(self):
        return edit.parse_cut_list(self.episode / edit.CUT_LIST_NAME)

    def findings(self, *, sounds=None):
        delivery, cuts, unused = self.parse()
        if sounds is None:
            return edit.check_cuts(self.episode, cuts, self.root, probe=False,
                                   unused=unused, delivery=delivery)
        # The only media fact the voice rules need is where each file is audible.
        with patch.object(edit, "probe_stream", return_value={}), patch.object(
            edit, "probe_audible", side_effect=lambda media: sounds[media.name]
        ):
            return edit.check_cuts(self.episode, cuts, self.root, probe=True,
                                   unused=unused, delivery=delivery)


class StillCutParsingTests(unittest.TestCase):
    def test_keyframe_sources_moves_and_voice_lines_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(
                still_block(1, "SHOT-1 · media/1.png", [
                    "- 运镜：推近 8%",
                    "- 配音 1：0.20 media/line.wav（增益：-3）",
                    "- 配音 2：1.20 media/reply.wav",
                ]),
                still_block(2, "IMG-A · media/2.jpg"),
                still_block(3, "MOTION-3 · media/1.mp4", ["- 配音：0.50 media/line.wav"]),
            )
            _, cuts, _ = project.parse()
        self.assertEqual([cut.still for cut in cuts], [True, True, False])
        self.assertEqual(cuts[0].move, edit.CameraMove("推近", 8))
        self.assertEqual(cuts[1].move, edit.CameraMove("固定", 0))
        self.assertIsNone(cuts[2].move)
        self.assertEqual(cuts[0].voices, (edit.Voice(0.2, "media/line.wav", -3.0),
                                          edit.Voice(1.2, "media/reply.wav", 0.0)))
        # Post-dubbing a video cut is allowed; it is mixed over the original sound.
        self.assertEqual(cuts[2].voices, (edit.Voice(0.5, "media/line.wav", 0.0),))

    def test_malformed_still_lines_are_refused_at_parse(self):
        refused = {
            "video id on an image": ("MOTION-1 · media/1.png", []),
            "still id on a video": ("SHOT-1 · media/1.mp4", []),
            "move on a video cut": ("MOTION-1 · media/1.mp4", ["- 运镜：推近 8%"]),
            "move too far": ("SHOT-1 · media/1.png", ["- 运镜：推近 31%"]),
            "move of nothing": ("SHOT-1 · media/1.png", ["- 运镜：左移 0%"]),
            "unknown move": ("SHOT-1 · media/1.png", ["- 运镜：旋转 10%"]),
            "move without amount": ("SHOT-1 · media/1.png", ["- 运镜：推近"]),
            "rate of nothing": ("SHOT-1 · media/1.png", ["- 运镜：推近 0%/秒"]),
            "rate too fast": ("SHOT-1 · media/1.png", ["- 运镜：推近 12%/秒"]),
            "rate per minute": ("SHOT-1 · media/1.png", ["- 运镜：推近 2.5%/分"]),
            "bed as a window": ("SHOT-1 · media/1.png", ["- 环境声：0.00-2.00 media/line.wav"]),
            "voice as a window": ("SHOT-1 · media/1.png", ["- 配音：0.20-1.40 media/line.wav"]),
            "voice gain too loud": ("SHOT-1 · media/1.png", ["- 配音：0.20 media/line.wav（增益：+9）"]),
            "voice plain and numbered": ("SHOT-1 · media/1.png", [
                "- 配音：0.20 media/line.wav", "- 配音 1：1.20 media/reply.wav"]),
            "voice written twice": ("SHOT-1 · media/1.png", [
                "- 配音：0.20 media/line.wav", "- 配音：1.20 media/reply.wav"]),
        }
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            for name, (source, extra) in refused.items():
                with self.subTest(name):
                    project.write(still_block(1, source, extra))
                    with self.assertRaises(edit.EditError):
                        project.parse()


class StillCutCheckTests(unittest.TestCase):
    def test_a_still_starts_at_zero_lasts_long_enough_and_needs_a_delivery_frame(self):
        cases = {
            "late in-point": (still_block(1, "SHOT-1 · media/1.png", start=0.5, end=2.0), SPEC_LINE),
            "flash-short": (still_block(1, "SHOT-1 · media/1.png", end=0.3), SPEC_LINE),
            "no frame to draw at": (still_block(1, "SHOT-1 · media/1.png"), ""),
        }
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            for name, (block, head) in cases.items():
                with self.subTest(name):
                    project.write(block, head=head + EXCUSE_TWO)
                    self.assertEqual(len(project.findings()), 1, project.findings())
            project.write(still_block(1, "SHOT-1 · media/1.png", end=0.5), head=SPEC_LINE + EXCUSE_TWO)
            self.assertEqual(project.findings(), [])

    def test_ids_resolve_in_their_own_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(still_block(1, "SHOT-9 · media/1.png"), head=SPEC_LINE + EXCUSE_TWO)
            findings = project.findings()
            self.assertTrue(any("SHOT-9" in f and edit.STORYBOARD_DOCUMENT in f for f in findings))
            project.write(still_block(1, "IMG-A · media/1.png"))
            self.assertTrue(any(edit.IMAGE_DOCUMENT in f for f in project.findings()),
                            "图片提示词不存在时必须报无法核对")
            (project.episode / edit.IMAGE_DOCUMENT).write_text("## IMG-A · 甲\n", encoding="utf-8")
            self.assertEqual(project.findings(), [])
            project.write(still_block(1, "IMG-B · media/1.png"))
            self.assertEqual(len(project.findings()), 1)

    def test_every_storyboard_shot_is_in_the_film_or_excused_once_one_is_used_as_a_still(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(still_block(1, "SHOT-1 · media/1.png"))
            (missing,) = project.findings()
            self.assertIn("SHOT-2", missing)
            project.write(still_block(1, "SHOT-1 · media/1.png"), head=SPEC_LINE + EXCUSE_TWO)
            self.assertEqual(project.findings(), [])
            # Image-prompt stills name no storyboard shot, so none is owed.
            (project.episode / edit.IMAGE_DOCUMENT).write_text("## IMG-A · 甲\n", encoding="utf-8")
            project.write(still_block(1, "IMG-A · media/1.png"))
            self.assertEqual(project.findings(), [])

    def test_a_mixed_list_counts_each_shot_once_however_it_reached_the_film(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            (project.episode / edit.STORYBOARD_DOCUMENT).write_text(
                STORYBOARD + "\n## SHOT-3 · 丙\n- 来源：EP001-SC001\n", encoding="utf-8")
            (project.episode / edit.MOTION_DOCUMENT).write_text(
                "## MOTION-1\n- 分镜：SHOT-1\n\n## MOTION-2\n- 分镜：SHOT-2\n\n"
                "## MOTION-3\n- 分镜：SHOT-3\n", encoding="utf-8")
            # SHOT-1 is in as video; SHOT-2 as a still in place of its video.
            blocks = (still_block(1, "MOTION-1 · media/1.mp4"), still_block(2, "SHOT-2 · media/2.jpg"))
            project.write(*blocks)
            findings = project.findings()
            self.assertEqual(len(findings), 2, findings)
            self.assertTrue("MOTION-3" in findings[0] and "SHOT-3" in findings[1], findings)
            # An excused video excuses its shot too; an excused shot leaves its video owed.
            for excused, remaining in (("MOTION-3", 0), ("SHOT-3", 1)):
                with self.subTest(excused):
                    project.write(*blocks, head=SPEC_LINE + f"- 未采用镜头：{excused}（理由：叙事取舍）\n")
                    self.assertEqual(len(project.findings()), remaining, project.findings())

    def test_a_video_only_list_is_held_to_video_prompts_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            (project.episode / edit.MOTION_DOCUMENT).write_text(
                "## MOTION-1\n- 分镜：SHOT-1\n", encoding="utf-8")
            project.write(still_block(1, "MOTION-1 · media/1.mp4"), head="")
            # SHOT-2 has no video prompt and no still: not this list's concern.
            self.assertEqual(project.findings(), [])

    def test_video_beside_stills_must_match_the_delivery_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            (project.episode / edit.MOTION_DOCUMENT).write_text(
                "## MOTION-1\n- 分镜：SHOT-1\n", encoding="utf-8")
            project.write(still_block(1, "MOTION-1 · media/1.mp4"), still_block(2, "SHOT-2 · media/2.jpg"))
            delivery, cuts, unused = project.parse()
            for video, expected in (({"width": 180, "height": 320, "fps": 24.0}, 0),
                                    ({"width": 1080, "height": 1920, "fps": 24.0}, 1)):
                with self.subTest(video), patch.object(
                    edit, "probe_stream", return_value={**video, "duration": 5.0}
                ):
                    findings = edit.check_cuts(project.episode, cuts, project.root, probe=True,
                                               unused=unused, delivery=delivery)
                self.assertEqual(len(findings), expected, findings)

    def test_a_move_can_be_written_as_a_speed_and_is_held_to_its_reach(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(still_block(1, "SHOT-1 · media/1.png", ["- 运镜：推近 2.5%/秒"]),
                          still_block(2, "SHOT-2 · media/2.jpg", ["- 运镜：右移 1.2％／秒"]))
            _, cuts, _ = project.parse()
            self.assertEqual([cut.move for cut in cuts],
                             [edit.CameraMove("推近", 0, 2.5), edit.CameraMove("右移", 0, 1.2)])
            self.assertEqual(project.findings(), [])
            # 10%/s over a 4 s cut is a 40% push: past the 30% a still can take.
            project.write(still_block(1, "SHOT-1 · media/1.png", ["- 运镜：推近 10%/秒"], end=4.0),
                          head=SPEC_LINE + EXCUSE_TWO)
            (finding,) = project.findings()
            self.assertIn("40%", finding)

    def test_a_move_ramps_only_where_it_starts_or_stops_from_rest(self):
        def cut(move, cut_id):
            return edit.Cut(cut_id, "段", "SHOT-1", "a.png", 0.0, 2.0, 2.0, (), {}, 1, move=move)

        rate = lambda kind: edit.CameraMove(kind, 0, 2.5)  # noqa: E731
        cuts = [
            cut(rate("推近"), "A"), cut(rate("推近"), "B"),    # one move through the cut
            cut(rate("左移"), "C"),                            # another direction
            cut(edit.CameraMove("推近", 5), "D"),              # the distance form eases both ends
            cut(edit.CameraMove(), "E"),                       # held
            cut(rate("推近"), "F"), cut(rate("推近"), "G"),    # F ends a scene, G starts the next
            cut(rate("推近"), "H"),                            # no scene known
        ]
        scenes = [S1, S1, S1, S1, S1, S1, S2, None]
        self.assertEqual(edit._move_ease(cuts, scenes), [
            (True, False), (False, True), (True, True), (True, True), (True, True),
            (True, True), (True, True), (True, True),
        ])

    def test_speed_jumps_and_reversals_inside_a_scene_are_noticed_not_refused(self):
        def cut(move, cut_id):
            return edit.Cut(cut_id, "段", "SHOT-1", "a.png", 0.0, 2.0, 2.0, (), {}, 1, move=move)

        rate = lambda kind, speed=2.5: edit.CameraMove(kind, 0, speed)  # noqa: E731
        cases = {
            "steady": ([rate("推近"), rate("推近", 3.0)], [S1, S1], 0),
            "percent at the same speed": ([edit.CameraMove("推近", 5), rate("推近")], [S1, S1], 0),
            "speed jump": ([rate("推近"), rate("推近", 4.0)], [S1, S1], 1),
            "push then pull": ([rate("推近"), rate("拉远")], [S1, S1], 1),
            "left then right": ([edit.CameraMove("左移", 5), edit.CameraMove("右移", 5)], [S1, S1], 1),
            "across a scene change": ([rate("推近"), rate("拉远", 6.0)], [S1, S2], 0),
            "held between": ([rate("推近"), edit.CameraMove(), rate("拉远")], [S1, S1, S1], 0),
        }
        for name, (moves, scenes, expected) in cases.items():
            with self.subTest(name):
                cuts = [cut(move, f"CUT-{i}") for i, move in enumerate(moves, start=1)]
                notices = edit.move_notices(cuts, scenes, [2.0] * len(cuts))
                self.assertEqual(len(notices), expected, notices)
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(still_block(1, "SHOT-1 · media/1.png", ["- 运镜：推近 2%/秒"]),
                          still_block(2, "SHOT-2 · media/2.jpg", ["- 运镜：推近 4%/秒"]))
            argv = ["check", str(project.episode), "--project-root", str(project.root)]
            with patch.object(edit, "_which", return_value=None), patch.object(edit, "_emit") as emit:
                self.assertEqual(edit.main(argv), 0, "提醒不挡渲染")
            payload = emit.call_args.args[0]
            self.assertEqual((payload["findings"], len(payload["提醒"])), ([], 1))

    def test_a_room_bed_runs_from_its_line_to_the_next_one(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(
                still_block(1, "SHOT-1 · media/1.png", ["- 环境声：media/line.wav"]),
                still_block(2, "SHOT-2 · media/2.jpg"),
                still_block(3, "SHOT-1 · media/1.png", ["- 环境声：-0.40 media/reply.wav（增益：+3）"]),
                still_block(4, "SHOT-2 · media/2.jpg", ["- 环境声：0.50 无"]),
            )
            _, cuts, _ = project.parse()
            self.assertEqual([cut.bed for cut in cuts], [
                edit.Bed(0.0, "media/line.wav"), None, edit.Bed(-0.4, "media/reply.wav", 3.0), edit.Bed(0.5, None),
            ])
            self.assertEqual(project.findings(), [])
            beds = edit._placed_beds(cuts, [2.0] * 4)
            # The office runs to CUT-3's start; the next room comes in 0.4 s under it and stops at 6.5 s.
            self.assertEqual([(b.path, round(b.start, 2), round(b.start + b.duration, 2), b.loop) for b in beds],
                             [("media/line.wav", 0.0, 4.0, True), ("media/reply.wav", 3.6, 6.5, True)])
            for name, block in {
                "first cut reaching back": still_block(1, "SHOT-1 · media/1.png", ["- 环境声：-0.20 media/line.wav"]),
                "missing file": still_block(1, "SHOT-1 · media/1.png", ["- 环境声：media/none.wav"]),
            }.items():
                with self.subTest(name):
                    project.write(block, head=SPEC_LINE + EXCUSE_TWO)
                    self.assertEqual(len(project.findings()), 1, project.findings())

    def test_one_keyframe_may_serve_several_cuts(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(still_block(1, "SHOT-1 · media/1.png"), still_block(2, "SHOT-2 · media/1.png"),
                          still_block(3, "SHOT-1 · media/1.png"))
            self.assertEqual(project.findings(), [])

    def test_an_odd_delivery_size_is_refused_when_stills_are_drawn_at_it(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            blocks = (still_block(1, "SHOT-1 · media/1.png"), still_block(2, "SHOT-2 · media/2.jpg"))
            project.write(*blocks, head="- 画幅与帧率：181×321 · 24fps\n")
            (odd,) = project.findings()
            self.assertIn("181×321", odd)
            project.write(*blocks, head="- 画幅与帧率：182×322 · 24fps\n")
            self.assertEqual(project.findings(), [])

    def test_media_outside_the_project_is_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside"
            outside.mkdir()
            (outside / "x.png").write_bytes(b"")
            (outside / "x.wav").write_bytes(b"")
            project = StillProject(Path(directory) / "project")
            cases = {
                "picture up and out": still_block(1, "SHOT-1 · ../../../outside/x.png"),
                "picture by absolute path": still_block(1, f"SHOT-1 · {outside / 'x.png'}"),
                "voice up and out": still_block(1, "SHOT-1 · media/1.png", ["- 配音：0.20 ../../../outside/x.wav"]),
            }
            for name, block in cases.items():
                with self.subTest(name):
                    project.write(block, head=SPEC_LINE + EXCUSE_TWO)
                    (finding,) = project.findings()
                    self.assertIn("不在项目目录内", finding)
            project.write(still_block(1, "SHOT-1 · 剧集/EP001/media/1.png"), head=SPEC_LINE + EXCUSE_TWO)
            self.assertEqual(project.findings(), [], "项目根下的相对路径照常可用")

    def test_without_ffmpeg_the_voice_checks_are_reported_unmeasured(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(still_block(1, "SHOT-1 · media/1.png", ["- 配音：0.20 media/line.wav"]),
                          head=SPEC_LINE + EXCUSE_TWO)
            argv = ["check", str(project.episode), "--project-root", str(project.root)]
            for tools, unmeasured in (({"ffprobe"}, ["配音"]), (set(), ["区间", "配音"])):
                with self.subTest(tools=tools), patch.object(
                    edit, "_which", side_effect=lambda name, tools=tools: name if name in tools else None
                ), patch.object(edit, "probe_stream", return_value={}), patch.object(edit, "_emit") as emit:
                    self.assertEqual(edit.main(argv), 0)
                payload = emit.call_args.args[0]
                self.assertEqual(payload["findings"], [])
                self.assertEqual([item[:2] for item in payload["未测"]], unmeasured)

    def test_voice_lines_are_held_to_the_film_not_to_their_cut(self):
        # Two 2-second stills, a 4-second film. line.wav is heard 0.2-1.2 of
        # its 1.4 s; reply.wav 0.2-0.5 of its 0.8 s.
        sounds = {"line.wav": edit.Audible(1.4, 0.2, 1.2), "reply.wav": edit.Audible(0.8, 0.2, 0.5)}
        cases = {
            "runs on over the next cut": ([" 配音：1.50 media/line.wav"], [], 0),
            "is still talking when the film ends": ([], [" 配音：1.20 media/line.wav"], 1),
            "only its silent tail passes the end": ([], [" 配音：0.80 media/line.wav"], 0),
            "is talked over from the next cut": (
                [" 配音：1.50 media/line.wav"], [" 配音：0.30 media/reply.wav"], 1),
            "sits tight where only the silences overlap": (
                [" 配音 1：0.00 media/line.wav", " 配音 2：1.00 media/reply.wav"], [], 0),
            "starts over the previous cut (J-cut)": ([], [" 配音：-0.50 media/reply.wav"], 0),
            "reaches back past the previous cut": ([], [" 配音：-2.50 media/reply.wav"], 1),
            "reaches back from the first cut": ([" 配音：-0.20 media/reply.wav"], [], 1),
            "starts after its cut": ([" 配音：2.10 media/reply.wav"], [], 1),
            "is pulled earlier by its in-point": (
                [" 配音 1：0.00 media/line.wav", " 配音 2：1.00 media/line.wav（起点：0.20）"], [], 1),
            "starts past everything audible": ([" 配音：0.00 media/line.wav（起点：1.30）"], [], 1),
        }
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            for name, (first, second, expected) in cases.items():
                with self.subTest(name):
                    project.write(
                        still_block(1, "SHOT-1 · media/1.png", ["-" + line for line in first]),
                        still_block(2, "SHOT-2 · media/2.jpg", ["-" + line for line in second]),
                    )
                    findings = project.findings(sounds=sounds)
                    self.assertEqual(len(findings), expected, findings)
            project.write(still_block(1, "SHOT-1 · media/1.png", ["- 配音：0.20 media/none.wav"]),
                          head=SPEC_LINE + EXCUSE_TWO)
            self.assertEqual(len(project.findings()), 1, "缺配音文件必须报")

    def test_a_cross_cut_subtitle_ends_with_its_voice_when_the_cut_rounds_to_the_frame(self):
        # 0.52 s at 24 fps is 12 frames, 0.50 s. The line and its subtitle both run 5 s from there.
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(
                still_block(1, "SHOT-1 · media/1.png",
                            ["- 配音：0.00 media/line.wav", "- 字幕 1：0.00-5.00 可我不懂音乐"], end=0.52),
                still_block(2, "SHOT-2 · media/2.jpg", end=6.0),
            )
            delivery, cuts, _ = project.parse()
            spans = edit._film_spans(cuts, delivery.fps)
            self.assertEqual(spans, [0.5, 6.0])
            (cue,) = edit._subtitle_cues(cuts, spans)
            ((_, voice_end, _, _),) = edit._voice_spans(
                cuts, {"media/line.wav": edit.Audible(5.0, 0.0, 5.0)}, spans)
            self.assertAlmostEqual(cue[1], 5.0)
            self.assertAlmostEqual(cue[1], voice_end)
            self.assertEqual(project.findings(sounds={"line.wav": edit.Audible(5.0, 0.0, 5.0)}), [])

    def test_the_film_end_is_where_the_rounded_cuts_end(self):
        # Ten 0.52 s stills: 5.0 s of film at 24 fps (12 frames each), 5.2 s at 25 fps (13 frames).
        blocks = [still_block(n, "SHOT-1 · media/1.png", ["- 配音：0.00 media/line.wav"] if n == 1 else [],
                              end=0.52) for n in range(1, 11)]
        sounds = {"line.wav": edit.Audible(5.2, 0.0, 5.2)}
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            for rate, expected in ((24, 1), (25, 0)):
                with self.subTest(fps=rate):
                    project.write(*blocks, head=f"- 画幅与帧率：180×320 · {rate}fps\n" + EXCUSE_TWO)
                    findings = project.findings(sounds=sounds)
                    self.assertEqual(len(findings), expected, findings)

    def test_a_subtitle_may_cross_its_cut_but_not_the_film_end_or_another_subtitle(self):
        cases = {
            "runs on over the next cut": (["- 字幕 1：1.50-2.80 可我不懂音乐"], ["- 字幕：无"], 0),
            "runs past the film end": ([], ["- 字幕 1：1.50-2.20 可我不懂音乐"], 1),
            "starts after its own cut": (["- 字幕 1：2.10-2.80 可我不懂音乐"], [], 1),
            "meets the next cut's subtitle": (
                ["- 字幕 1：1.50-2.80 可我不懂音乐"], ["- 字幕 1：0.50-1.00 五天？够了"], 1),
            "meets a whole-cut subtitle": (["- 字幕 1：1.50-2.80 可我不懂音乐"], ["- 字幕：五天？够了"], 1),
            "hands over cleanly": (
                ["- 字幕 1：1.50-2.80 可我不懂音乐"], ["- 字幕 1：0.80-1.60 五天？够了"], 0),
        }
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            for name, (first, second, expected) in cases.items():
                with self.subTest(name):
                    project.write(still_block(1, "SHOT-1 · media/1.png", first),
                                  still_block(2, "SHOT-2 · media/2.jpg", second))
                    self.assertEqual(len(project.findings()), expected, project.findings())

    def test_sound_lines_take_an_in_point_and_a_gain_in_either_order(self):
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            project.write(still_block(1, "SHOT-1 · media/1.png", [
                "- 配音：0.20 media/line.wav（起点：0.15；增益：-3 dB）",
                "- 音效：0.00-0.60 media/reply.wav（增益：+2；起点：1.40）",
            ]), head=SPEC_LINE + EXCUSE_TWO)
            _, cuts, _ = project.parse()
            self.assertEqual(cuts[0].voices, (edit.Voice(0.2, "media/line.wav", -3.0, 0.15),))
            self.assertEqual(cuts[0].sound_effects, (edit.SoundEffect(0.0, 0.6, "media/reply.wav", 2.0, 1.4),))
            for refused in ("（起点：-1）", "（起点：1；起点：2）", "（起点：1 dB）", "（增益：-50）",
                            "（起点：1，增益：2）"):
                with self.subTest(refused):
                    project.write(still_block(1, "SHOT-1 · media/1.png", [
                        f"- 配音：0.20 media/line.wav{refused}"]))
                    with self.assertRaises(edit.EditError):
                        project.parse()

    def test_the_audible_span_skips_padding_and_breath_below_the_floor(self):
        rate = 1000
        samples = [0] * 300 + [1000, -1000] * 250 + [5, -5] * 200
        sound = edit._audible_span(samples, rate)
        self.assertAlmostEqual(sound.duration, 1.2)
        self.assertAlmostEqual(sound.head, 0.30, delta=edit.AUDIBLE_WINDOW)
        self.assertAlmostEqual(sound.tail, 0.80, delta=edit.AUDIBLE_WINDOW)
        self.assertEqual(edit._audible_span([0] * 500, rate), edit.Audible(0.5, 0.0, 0.0))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class StillRenderTests(unittest.TestCase):
    WIDTH, HEIGHT, FPS = 180, 320, 24

    def test_two_moving_stills_and_a_voice_line_render_to_the_delivery_spec(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            media = project.episode / "media"
            # A white square on black grows as the frame pushes in; a frame
            # dark on its left darkens as the camera moves left across it.
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=black:size=300x400", "-vf",
                                    "drawbox=x=75:y=125:w=150:h=150:color=white:t=fill",
                                    "-frames:v", "1", str(media / "1.png")], check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=white:size=400x300", "-vf",
                                    "drawbox=x=0:y=0:w=200:h=300:color=black:t=fill",
                                    "-frames:v", "1", str(media / "2.jpg")], check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=440:duration=0.8",
                                    str(media / "line.wav")], check=True)
            project.write(
                still_block(1, "SHOT-1 · media/1.png", ["- 运镜：推近 20%",
                                                        "- 配音：0.50 media/line.wav"]),
                still_block(2, "SHOT-2 · media/2.jpg", ["- 运镜：左移 12%"]),
                head=SPEC_LINE + "- 交付响度：-16 LUFS\n",
            )
            delivery, cuts, unused = project.parse()
            self.assertEqual(edit.check_cuts(project.episode, cuts, project.root, probe=True,
                                             unused=unused, delivery=delivery), [])
            report = edit.render(project.episode, project.root, cuts, delivery, burn_subtitles=False)
            measured = edit.verify(project.episode, cuts, delivery, project.root)
            film = Path(report["成片"])
            timestamps = json.loads(subprocess.check_output(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
                 "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(film)],
                text=True,
            ))["frames"]
            self.assertEqual(len(timestamps), 4 * self.FPS)
            self.assertAlmostEqual(float(timestamps[0]["best_effort_timestamp_time"]), 0, places=5)
            self.assertAlmostEqual(float(timestamps[2 * self.FPS]["best_effort_timestamp_time"]),
                                   2, places=5)
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(film), "-f", "rawvideo",
                                  "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
            size = self.WIDTH * self.HEIGHT
            luma = [sum(raw[at:at + size]) / size for at in range(0, len(raw), size)]

            def peak(start, length):
                result = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(length), "-i", str(film),
                     "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
                return float(re.search(r"max_volume: (\S+) dB", result.stderr).group(1))

            dubbed, before, after = peak(0.7, 0.4), peak(0.0, 0.4), peak(2.2, 1.6)

        self.assertEqual((measured["画幅是否等于交付规格"], measured["帧率是否等于交付规格"]), (True, True))
        self.assertAlmostEqual(measured["实测时长"], 4.0, delta=0.15)
        self.assertEqual(len(luma), 4 * self.FPS, "每段按交付帧率出足帧数")
        push, pan = luma[:2 * self.FPS], luma[2 * self.FPS:]
        self.assertGreater(push[-1] - push[0], 10, "推近时白方块应变大")
        self.assertGreater(pan[0] - pan[-1], 10, "左移时暗的左半边应进画")
        # Eased: the move is slow at both ends and fastest in the middle.
        middle = abs(push[self.FPS] - push[self.FPS - 1])
        self.assertLess(max(abs(push[1] - push[0]), abs(push[-1] - push[-2])), middle / 2)
        self.assertGreater(dubbed, -20)
        self.assertLess(max(before, after), -60)
        self.assertEqual([row["文件"] for row in measured["配音落点"]], ["media/line.wav"])
        self.assertEqual(set(report["自动接镜"]), {"CUT-1", "CUT-2"}, "同场静帧也参与自动接镜")
        self.assertEqual(measured["疑似坏帧"], [])

    def test_a_voice_line_runs_over_the_next_cut_and_an_effect_starts_inside_its_file(self):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            media = project.episode / "media"
            for name in ("1.png", "2.jpg"):
                subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=gray:size=180x320",
                                        "-frames:v", "1", str(media / name)], check=True)
            # A 1.2 s low voice, and a high beep that sits a second into its file.
            subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=300:duration=1.2",
                                    str(media / "line.wav")], check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=3000:duration=1.3",
                                    "-af", "volume=enable='lt(t,1)':volume=0",
                                    str(media / "reply.wav")], check=True)
            project.write(
                still_block(1, "SHOT-1 · media/1.png", ["- 配音：1.00 media/line.wav"], end=1.5),
                still_block(2, "SHOT-2 · media/2.jpg",
                            ["- 音效：0.80-1.20 media/reply.wav（起点：1.00）"], end=1.5),
            )
            delivery, cuts, unused = project.parse()
            self.assertEqual(edit.check_cuts(project.episode, cuts, project.root, probe=True,
                                             unused=unused, delivery=delivery), [])
            report = edit.render(project.episode, project.root, cuts, delivery, burn_subtitles=False)
            measured = edit.verify(project.episode, cuts, delivery, project.root)
            film = Path(report["成片"])

            def peak(start, length, band):
                # Filtered, then trimmed: cutting a tone mid-cycle before the
                # filter, or seeking the AAC input, clicks across every band.
                result = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-i", str(film), "-af",
                     f"{band},atrim={start}:{start + length},volumedetect", "-f", "null", "-"],
                    capture_output=True, text=True)
                return float(re.search(r"max_volume: (\S+) dB", result.stderr).group(1))

            low, high = "lowpass=f=800,lowpass=f=800", "highpass=f=2000,highpass=f=2000"
            voice_in_second_cut = peak(1.6, 0.5, low)
            voice_after_it_ends = peak(2.65, 0.35, low)
            beep_where_placed = peak(2.35, 0.2, high)
            beep_before = peak(1.6, 0.5, high)

        # The line starts 1.0 s into CUT-1 and is still heard well inside CUT-2.
        self.assertGreater(voice_in_second_cut, -25)
        self.assertLess(voice_after_it_ends, -50)
        # 起点 skipped the beep's silent second: it lands at 1.5 + 0.8, not a second later.
        self.assertGreater(beep_where_placed, -25)
        self.assertLess(beep_before, -50)
        (line,) = measured["配音落点"]
        self.assertEqual((line["段"], line["起"]), ("CUT-1", 1.0))
        self.assertAlmostEqual(line["止"], 2.2, delta=0.05)

    def test_a_silent_video_beside_stills_keeps_every_sound_in_place(self):
        # A clip with no audio track used to shift every sound after it, or,
        # placed first, leave the joined film without sound at all.
        for order in (("still", "video", "still"), ("video", "still")):
            with self.subTest(order=order):
                self.render_with_silent_video(order)

    def render_with_silent_video(self, order):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            media = project.episode / "media"
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=gray:size=180x320", "-frames:v", "1",
                                    str(media / "1.png")], check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=gray:size=180x320:rate=24:duration=2",
                                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(media / "1.mp4")],
                           check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=300:duration=0.8",
                                    str(media / "line.wav")], check=True)
            (project.episode / edit.MOTION_DOCUMENT).write_text("## MOTION-1\n- 分镜：SHOT-9\n", encoding="utf-8")
            blocks, shots = [], iter(("SHOT-1", "SHOT-2"))
            for number, kind in enumerate(order, start=1):
                if kind == "video":
                    video_at = 2.0 * (number - 1)
                    blocks.append(still_block(number, "MOTION-1 · media/1.mp4", ["- 配音：1.00 media/line.wav"]))
                else:
                    blocks.append(still_block(number, f"{next(shots)} · media/1.png"))
            project.write(*blocks, head=SPEC_LINE + "- 交付响度：-16 LUFS\n"
                          + ("" if len(order) == 3 else EXCUSE_TWO))
            delivery, cuts, unused = project.parse()
            self.assertEqual(edit.check_cuts(project.episode, cuts, project.root, probe=True,
                                             unused=unused, delivery=delivery), [])
            film = Path(edit.render(project.episode, project.root, cuts, delivery,
                                    burn_subtitles=False)["成片"])

            def peak(start, length):
                result = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-i", str(film), "-af",
                     f"atrim={start}:{start + length},volumedetect", "-f", "null", "-"],
                    capture_output=True, text=True)
                return float(re.search(r"max_volume: (\S+) dB", result.stderr).group(1))

            quiet_from = max(0.0, video_at - 1.0)
            voiced, before = peak(video_at + 1.2, 0.4), peak(quiet_from, video_at + 0.9 - quiet_from)
            seconds = edit.probe_duration(film)
        self.assertGreater(voiced, -25, "配音应落在无声视频段的 1.0 秒处")
        self.assertLess(before, -50)
        self.assertAlmostEqual(seconds, 2.0 * len(order), delta=0.15)

    def test_a_voice_plays_whole_when_its_cut_rounds_to_the_frame(self):
        # 0.52 s at 24 fps renders as 12 frames, 0.50 s. The voice that starts
        # there and runs 5 s over the next cut must still play all 5 s.
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            media = project.episode / "media"
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=gray:size=180x320", "-frames:v", "1",
                                    str(media / "1.png")], check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=300:duration=5",
                                    str(media / "line.wav")], check=True)
            project.write(
                still_block(1, "SHOT-1 · media/1.png", ["- 配音：0.00 media/line.wav"], end=0.52),
                still_block(2, "SHOT-2 · media/1.png", end=6.0),
            )
            delivery, cuts, unused = project.parse()
            self.assertEqual(edit.check_cuts(project.episode, cuts, project.root, probe=True,
                                             unused=unused, delivery=delivery), [])
            film = Path(edit.render(project.episode, project.root, cuts, delivery,
                                    burn_subtitles=False)["成片"])
            measured = edit.verify(project.episode, cuts, delivery, project.root)
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-i", str(film), "-af", "atrim=4.85:4.95,volumedetect",
                 "-f", "null", "-"], capture_output=True, text=True)
            tail = float(re.search(r"max_volume: (\S+) dB", result.stderr).group(1))
        self.assertGreater(tail, -25, "配音的最后 0.15 秒被按画面取整截掉了")
        (line,) = measured["配音落点"]
        self.assertAlmostEqual(line["止"] - line["起"], 5.0, delta=0.05)

    def test_a_scene_moves_on_through_its_cuts_over_an_unbroken_room(self):
        # Two 2 s stills in one scene, both panning left. The picture is dark on
        # its left, so the frame's mean brightness falls as fast as the pan goes.
        continuous = self.render_pan("- 运镜：左移 5%/秒", bed=True)
        eased = self.render_pan("- 运镜：左移 9%")
        cut = 2 * self.FPS
        for name, (luma, _) in (("rate", continuous), ("percent", eased)):
            steps = [abs(b - a) for a, b in zip(luma, luma[1:])]
            cruise = sum(steps[18:28]) / 10
            near = (sum(steps[cut - 4:cut - 1]) / 3, sum(steps[cut:cut + 3]) / 3)
            with self.subTest(name):
                if name == "rate":
                    self.assertGreater(min(near), 0.6 * cruise, f"切点两侧不该停下来: {near} vs {cruise}")
                else:
                    self.assertLess(max(near), 0.3 * cruise, "百分比写法两头缓停（对照）")
        # The room bed loops a 1 s tone across the cut with no dip.
        levels = continuous[1]
        at_cut = min(levels[195:206])
        self.assertGreater(at_cut, max(levels[50:60]) - 3, f"环境声在切点处掉了: {levels[195:206]}")
        self.assertGreater(levels[350], max(levels[50:60]) - 3, "环境声应循环到第二段")

    def render_pan(self, move, bed=False):
        quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            media = project.episode / "media"
            subprocess.run(quiet + ["-f", "lavfi", "-i", "color=c=white:size=400x300", "-vf",
                                    "drawbox=x=0:y=0:w=200:h=300:color=black:t=fill",
                                    "-frames:v", "1", str(media / "1.png")], check=True)
            # 300 whole cycles: the loop has no seam.
            subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=300:duration=1",
                                    str(media / "line.wav")], check=True)
            project.write(
                still_block(1, "SHOT-1 · media/1.png", [move] + (["- 环境声：media/line.wav"] if bed else [])),
                still_block(2, "SHOT-2 · media/1.png", [move]),
            )
            delivery, cuts, unused = project.parse()
            self.assertEqual(edit.check_cuts(project.episode, cuts, project.root, probe=True,
                                             unused=unused, delivery=delivery), [])
            film = Path(edit.render(project.episode, project.root, cuts, delivery,
                                    burn_subtitles=False)["成片"])
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(film), "-f", "rawvideo",
                                  "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
            size = self.WIDTH * self.HEIGHT
            luma = [sum(raw[at:at + size]) / size for at in range(0, len(raw), size)]
            pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(film), "-ac", "1", "-ar", "8000",
                                  "-f", "s16le", "-"], capture_output=True, check=True).stdout
        samples = [int.from_bytes(pcm[at:at + 2], "little", signed=True) for at in range(0, len(pcm) - 1, 2)]
        # dB per 10 ms window.
        levels = []
        for at in range(0, len(samples) - 80, 80):
            window = samples[at:at + 80]
            power = sum(value * value for value in window) / len(window)
            levels.append(10 * (math.log10(power) if power > 0 else -12))
        return luma, levels
