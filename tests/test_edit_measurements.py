import importlib.util
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

    def findings(self, *, voice_seconds=None):
        delivery, cuts, unused = self.parse()
        if voice_seconds is None:
            return edit.check_cuts(self.episode, cuts, self.root, probe=False,
                                   unused=unused, delivery=delivery)
        # The only media fact the voice rules need is each file's length.
        with patch.object(edit, "probe_stream", return_value={}), patch.object(
            edit, "probe_duration", side_effect=lambda media: voice_seconds[media.name]
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

    def test_voice_lines_end_inside_their_cut_and_never_overlap(self):
        lengths = {"line.wav": 1.2, "reply.wav": 0.6}
        cases = {
            "fits": (["- 配音：0.80 media/line.wav"], 0),
            "within the 0.05 s allowance": (["- 配音：0.84 media/line.wav"], 0),
            "runs past the cut": (["- 配音：0.90 media/line.wav"], 1),
            "talks over the first": (["- 配音 1：0.00 media/line.wav", "- 配音 2：1.00 media/reply.wav"], 1),
            "one after the other": (["- 配音 1：0.00 media/line.wav", "- 配音 2：1.30 media/reply.wav"], 0),
            "starts after the cut": (["- 配音：2.10 media/reply.wav"], 2),
        }
        with tempfile.TemporaryDirectory() as directory:
            project = StillProject(Path(directory))
            head = SPEC_LINE + EXCUSE_TWO
            for name, (lines, expected) in cases.items():
                with self.subTest(name):
                    project.write(still_block(1, "SHOT-1 · media/1.png", lines), head=head)
                    findings = project.findings(voice_seconds=lengths)
                    self.assertEqual(len(findings), expected, findings)
            project.write(still_block(1, "SHOT-1 · media/1.png", ["- 配音：0.20 media/none.wav"]), head=head)
            self.assertEqual(len(project.findings()), 1, "缺配音文件必须报")


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
