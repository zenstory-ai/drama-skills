import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/short-drama-edit/scripts/edit_tool.py"
SPEC = importlib.util.spec_from_file_location("edit_plan_and_subtitle", SCRIPT)
assert SPEC and SPEC.loader
edit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edit)


SCREENPLAY = """# EP001 · 夜班交接

## EP001-SC001 内 · 接待台 · 夜

[画面文字] 值班室 · 23:40

林安：请先坐下。

周明：合同放在桌上了。
"""

STORYBOARD = """# EP001 分镜

## SHOT-EP001-001 · 接待台入镜
- 来源：EP001-SC001

## SHOT-EP001-002 · 合同特写
- 来源：EP001-SC001
"""

VIDEO_PROMPTS = """# EP001 视频提示词

## MOTION-EP001-001 · 接待台对话
- 分镜：SHOT-EP001-001

## MOTION-EP001-002 · 合同推进
- 分镜：SHOT-EP001-002
"""


def _write_paper_episode(root: Path, cut_list: str, *, create_media: bool = False) -> Path:
    episode = root / "剧集" / "EP001"
    episode.mkdir(parents=True, exist_ok=True)
    (episode / "剧本.md").write_text(SCREENPLAY, encoding="utf-8")
    (episode / "分镜.md").write_text(STORYBOARD, encoding="utf-8")
    (episode / "视频提示词.md").write_text(VIDEO_PROMPTS, encoding="utf-8")
    (episode / "剪辑单.md").write_text(cut_list, encoding="utf-8")
    if create_media:
        video_dir = episode / "制作成果" / "video"
        audio_dir = episode / "制作成果" / "audio"
        image_dir = episode / "制作成果" / "images"
        video_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        image_dir.mkdir(parents=True, exist_ok=True)
        for name in ("001.mp4", "002.mp4"):
            (video_dir / name).write_bytes(b"")
        for name in ("002.png",):
            (image_dir / name).write_bytes(b"")
        for name in ("sfx.wav", "voice.wav", "room.wav"):
            (audio_dir / name).write_bytes(b"")
    return episode


class UnnumberedTimedSubtitleTests(unittest.TestCase):
    def test_unnumbered_inline_timed_subtitle_parses_aligns_verbatim_and_supports_bold_colon(self):
        variants = (
            ("- 字幕：0.20-1.40 请先坐下。", "- 字幕：0.40-2.20 合同放在桌上了。（重点：合同）"),
            ("- **字幕：** 0.20-1.40 请先坐下。", "- **字幕**：0.40-2.20 合同放在桌上了。（重点：合同）"),
            ("- *字幕:* 0.20-1.40 请先坐下。", "- _字幕：_ 0.40~2.20 合同放在桌上了。（重点：合同）"),
        )
        for sub1, sub2 in variants:
            with self.subTest(sub1=sub1), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cut_list = (
                    "# EP001 剪辑单\n\n"
                    "- 成片目标时长：6.00 秒\n"
                    "- 画幅与帧率：1080×1920 · 24fps\n"
                    "- 交付响度：-16 LUFS\n\n"
                    "## CUT-EP001-001 · 开场\n\n"
                    "- 来源：MOTION-EP001-001 · 制作成果/video/001.mp4\n"
                    "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                    "- 取舍：入点=抬头；出点=落座\n"
                    "- 声音：保留原声\n"
                    f"{sub1}\n\n"
                    "## CUT-EP001-002 · 合同\n\n"
                    "- 来源：MOTION-EP001-002 · 制作成果/video/002.mp4\n"
                    "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                    "- 取舍：入点=推近；出点=定格\n"
                    "- 声音：保留原声\n"
                    f"{sub2}\n"
                )
                episode = _write_paper_episode(root, cut_list, create_media=True)
                delivery, cuts, unused = edit.parse_cut_list(episode / "剪辑单.md")
                self.assertEqual(cuts[0].subtitles, ((0.2, 1.4, "请先坐下。", ()),))
                self.assertEqual(cuts[1].subtitles, ((0.4, 2.2, "合同放在桌上了。", ("合同",)),))
                findings, notices = edit._inspect_cuts(
                    episode, cuts, root, probe=False, unused=unused, delivery=delivery
                )
                self.assertEqual(findings, [])
                self.assertEqual(notices, [])
                cues = edit._subtitle_cues(cuts, [3.0, 3.0])
                self.assertEqual(len(cues), 2)
                self.assertAlmostEqual(cues[0][0], 0.2)
                self.assertAlmostEqual(cues[0][1], 1.4)
                self.assertEqual(cues[0][2:], ("请先坐下。", ()))
                self.assertAlmostEqual(cues[1][0], 3.4)
                self.assertAlmostEqual(cues[1][1], 5.2)
                self.assertEqual(cues[1][2:], ("合同放在桌上了。", ("合同",)))

    def test_backward_compatible_subtitle_window_and_untimed_subtitles_keep_working(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cut_list = (
                "# EP001 剪辑单\n\n"
                "- 画幅与帧率：1080×1920 · 24fps\n\n"
                "## CUT-EP001-001 · 兼容独立时间\n\n"
                "- 来源：MOTION-EP001-001 · 制作成果/video/001.mp4\n"
                "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                "- **字幕：** 请先坐下。\n"
                "- **字幕时间：** 0.30-1.50\n\n"
                "## CUT-EP001-002 · 整段字幕\n\n"
                "- 来源：MOTION-EP001-002 · 制作成果/video/002.mp4\n"
                "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                "- 字幕：合同放在桌上了。\n"
            )
            episode = _write_paper_episode(root, cut_list, create_media=True)
            delivery, cuts, unused = edit.parse_cut_list(episode / "剪辑单.md")
            self.assertEqual(cuts[0].subtitles, ((0.3, 1.5, "请先坐下。", ()),))
            self.assertEqual(cuts[1].subtitles, ((None, None, "合同放在桌上了。", ()),))
            self.assertEqual(
                edit.check_cuts(episode, cuts, root, probe=False, unused=unused, delivery=delivery),
                [],
            )

    def test_unnumbered_dialogue_starting_with_integer_range_is_not_misparsed_as_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cut_list = (
                "# EP001 剪辑单\n\n"
                "- 画幅与帧率：1080×1920 · 24fps\n\n"
                "## CUT-EP001-001 · 整数区间整段台词\n\n"
                "- 来源：MOTION-EP001-001 · 制作成果/video/001.mp4\n"
                "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                "- 字幕：3-5 天内交货\n\n"
                "## CUT-EP001-002 · 整数区间搭配独立时间\n\n"
                "- 来源：MOTION-EP001-002 · 制作成果/video/002.mp4\n"
                "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                "- 字幕：10-15 minutes left\n"
                "- 字幕时间：0.20-1.80\n"
            )
            episode = _write_paper_episode(root, cut_list, create_media=True)
            (episode / "剧本.md").write_text(
                "# EP001 · 交期\n\n"
                "## EP001-SC001 内 · 接待台 · 夜\n\n"
                "林安：3-5 天内交货\n\n"
                "周明：10-15 minutes left\n",
                encoding="utf-8",
            )
            delivery, cuts, unused = edit.parse_cut_list(episode / "剪辑单.md")
            self.assertEqual(cuts[0].subtitles, ((None, None, "3-5 天内交货", ()),))
            self.assertEqual(cuts[1].subtitles, ((0.2, 1.8, "10-15 minutes left", ()),))
            self.assertEqual(
                edit.check_cuts(episode, cuts, root, probe=False, unused=unused, delivery=delivery),
                [],
            )

    def test_contradictory_or_malformed_subtitle_timing_is_rejected(self):
        parse_error_cases = {
            "inline timed plus subtitle window": [
                "- 字幕：0.20-1.40 请先坐下。",
                "- 字幕时间：0.20-1.40",
            ],
            "numbered plus subtitle window": [
                "- 字幕 1：0.20-1.40 请先坐下。",
                "- 字幕时间：0.20-1.40",
            ],
            "subtitle none plus subtitle window": [
                "- 字幕：无",
                "- 字幕时间：0.20-1.40",
            ],
            "dangling subtitle window without subtitle": [
                "- 字幕时间：0.20-1.40",
            ],
            "malformed decimal in subtitle window": [
                "- 字幕：请先坐下。",
                "- 字幕时间：1..2-2.00",
            ],
            "malformed decimal in numbered subtitle": [
                "- 字幕 1：1..2-2.00 请先坐下。",
            ],
        }
        for label, extra_lines in parse_error_cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cut_list = (
                    "# EP001 剪辑单\n\n"
                    "- 未采用镜头：MOTION-EP001-002（理由：删减）\n\n"
                    "## CUT-EP001-001 · 冲突\n\n"
                    "- 来源：MOTION-EP001-001 · 制作成果/video/001.mp4\n"
                    "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                    + "".join(f"{line}\n" for line in extra_lines)
                )
                episode = _write_paper_episode(root, cut_list, create_media=True)
                with self.assertRaises(edit.EditError):
                    edit.parse_cut_list(episode / "剪辑单.md")

    def test_unnumbered_timed_subtitle_range_and_verbatim_defects_fail_check(self):
        cases = {
            "inverted range": ("- 字幕：2.10-0.80 请先坐下。", "字幕时间要从本段内开始"),
            "zero-width range": ("- 字幕：1.20-1.20 请先坐下。", "字幕时间要从本段内开始"),
            "starts after cut": ("- 字幕：3.20-3.80 请先坐下。", "字幕时间要从本段内开始"),
            "ends past film end": ("- 字幕：0.50-3.80 请先坐下。", "字幕时间要从本段内开始"),
            "verbatim mismatch": ("- 字幕：0.20-1.40 这句台词不在剧本里。", "找不到原文"),
        }
        for label, (sub_line, expected_fragment) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cut_list = (
                    "# EP001 剪辑单\n\n"
                    "- 未采用镜头：MOTION-EP001-002（理由：删减）\n\n"
                    "## CUT-EP001-001 · 检验\n\n"
                    "- 来源：MOTION-EP001-001 · 制作成果/video/001.mp4\n"
                    "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                    f"{sub_line}\n"
                )
                episode = _write_paper_episode(root, cut_list, create_media=True)
                delivery, cuts, unused = edit.parse_cut_list(episode / "剪辑单.md")
                findings = edit.check_cuts(
                    episode, cuts, root, probe=False, unused=unused, delivery=delivery
                )
                self.assertTrue(
                    any(expected_fragment in item for item in findings),
                    (label, findings),
                )


class PlanOnlyPreCheckTests(unittest.TestCase):
    def _paper_cut_list(self) -> str:
        return (
            "# EP001 剪辑单\n\n"
            "- 成片目标时长：5.00 秒\n"
            "- 画幅与帧率：1080×1920 · 24fps\n"
            "- 交付响度：-16 LUFS\n\n"
            "## CUT-EP001-001 · 接待台入镜\n\n"
            "- 来源：MOTION-EP001-001 · 制作成果/video/001.mp4\n"
            "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
            "- 取舍：入点=抬头；出点=落座\n"
            "- 声音：保留原声\n"
            "- 字幕：0.20-1.50 请先坐下。\n"
            "- 画面文字：0.10-1.60 字卡 值班室 · 23:40\n"
            "- 音效：0.40-1.00 制作成果/audio/sfx.wav（增益：-6）\n"
            "- 环境声：0.00 制作成果/audio/room.wav（增益：-18）\n\n"
            "## CUT-EP001-002 · 合同特写\n\n"
            "- 来源：SHOT-EP001-002 · 制作成果/images/002.png\n"
            "- 入点：0.00\n- 出点：2.00\n- 时长：2.00\n"
            "- 取舍：入点=定格；出点=收尾\n"
            "- 声音：配音\n"
            "- 配音：0.10 制作成果/audio/voice.wav\n"
            "- 字幕：0.10-1.60 合同放在桌上了。\n"
        )

    def test_plan_only_passes_with_missing_media_warnings_while_standard_check_and_render_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = _write_paper_episode(root, self._paper_cut_list(), create_media=False)
            base_argv = [str(episode), "--project-root", str(root)]

            with patch.object(edit, "_emit") as emit:
                plan_rc = edit.main(["check", "--plan-only", *base_argv])
            self.assertEqual(plan_rc, 0)
            payload = emit.call_args.args[0]
            self.assertEqual(payload["模式"], "plan-only")
            self.assertEqual(payload["findings"], [])
            notices = payload.get("提醒", [])
            for expected_path in (
                "制作成果/video/001.mp4",
                "制作成果/audio/sfx.wav",
                "制作成果/audio/room.wav",
                "制作成果/images/002.png",
                "制作成果/audio/voice.wav",
            ):
                self.assertTrue(
                    any(expected_path in item and "尚未生成" in item for item in notices),
                    (expected_path, notices),
                )
            self.assertTrue(
                any("纸面预检" in item for item in payload.get("未测", [])),
                payload,
            )

            # Standard check WITHOUT --plan-only still hard-fails on every missing file.
            with patch.object(edit, "_emit") as emit:
                strict_rc = edit.main(["check", *base_argv])
            self.assertEqual(strict_rc, 1)
            strict_payload = emit.call_args.args[0]
            self.assertNotIn("模式", strict_payload)
            self.assertEqual(len(strict_payload["findings"]), 5, strict_payload["findings"])

            # Standard render still hard-fails on missing media.
            with patch.object(edit, "_emit") as emit:
                render_rc = edit.main(["render", *base_argv])
            self.assertEqual(render_rc, 1)
            self.assertFalse(emit.call_args.args[0]["已渲染"])

            # --plan-only is refused on render and verify.
            for cmd in ("render", "verify"):
                with self.subTest(cmd=cmd):
                    stderr = io.StringIO()
                    with contextlib.redirect_stderr(stderr):
                        rc = edit.main([cmd, "--plan-only", *base_argv])
                    self.assertEqual(rc, 2)
                    self.assertIn("--plan-only", stderr.getvalue())

    def test_plan_only_still_hard_fails_on_paper_document_defects(self):
        base = self._paper_cut_list()
        defect_cases = {
            "bad duration arithmetic": (
                base.replace("- 时长：3.00", "- 时长：2.50", 1),
                "与「时长",
            ),
            "unknown upstream source ID": (
                base.replace("MOTION-EP001-001", "MOTION-EP001-999"),
                "MOTION-EP001-999",
            ),
            "subtitle verbatim mismatch": (
                base.replace("请先坐下。", "请先站起来。"),
                "找不到原文",
            ),
            "screen text not in screenplay": (
                base.replace("值班室 · 23:40", "假地点 · 00:00"),
                "画面文字在《剧本.md》",
            ),
            "unaccounted upstream shot": (
                base.split("## CUT-EP001-002")[0],
                "MOTION-EP001-002",
            ),
            "same-source video overlap without replay": (
                base.replace(
                    "SHOT-EP001-002 · 制作成果/images/002.png",
                    "MOTION-EP001-002 · 制作成果/video/001.mp4",
                ),
                "区间重叠",
            ),
        }
        for label, (mutated, expected_fragment) in defect_cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                episode = _write_paper_episode(root, mutated, create_media=False)
                with patch.object(edit, "_emit") as emit:
                    rc = edit.main(["check", "--plan-only", str(episode), "--project-root", str(root)])
                self.assertEqual(rc, 1, emit.call_args.args[0])
                findings = emit.call_args.args[0]["findings"]
                self.assertTrue(
                    any(expected_fragment in item for item in findings),
                    (label, findings),
                )

    def test_plan_only_combines_cleanly_with_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            partial_list = self._paper_cut_list().split("## CUT-EP001-002")[0]
            episode = _write_paper_episode(root, partial_list, create_media=False)
            with patch.object(edit, "_emit") as emit:
                rc = edit.main([
                    "check", "--plan-only", "--partial",
                    str(episode), "--project-root", str(root),
                ])
            self.assertEqual(rc, 0, emit.call_args.args[0])
            payload = emit.call_args.args[0]
            self.assertEqual(payload["findings"], [])
            notices = payload.get("提醒", [])
            self.assertTrue(any("MOTION-EP001-002" in item for item in notices), notices)
            self.assertTrue(any("制作成果/video/001.mp4" in item for item in notices), notices)

    def test_plan_only_still_enforces_path_boundary_and_symlink_security(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            outside = workspace / "outside"
            outside.mkdir()
            (outside / "secret.mp4").write_bytes(b"")
            root = workspace / "project"
            base = self._paper_cut_list()

            # Non-existent traversal and absolute paths must still be hard errors under --plan-only.
            unsafe_paths = (
                ("parent traversal", "../../../outside/never_created.mp4"),
                ("absolute path", str(outside / "never_created.mp4")),
                ("sfx traversal", None),
            )
            for label, bad_video in unsafe_paths:
                with self.subTest(label):
                    if bad_video is not None:
                        mutated = base.replace("制作成果/video/001.mp4", bad_video)
                    else:
                        mutated = base.replace("制作成果/audio/sfx.wav", "../../../outside/sfx.wav")
                    episode = _write_paper_episode(root, mutated, create_media=False)
                    with patch.object(edit, "_emit") as emit:
                        rc = edit.main([
                            "check", "--plan-only", str(episode), "--project-root", str(root)
                        ])
                    self.assertEqual(rc, 1, emit.call_args.args[0])
                    findings = emit.call_args.args[0]["findings"]
                    self.assertTrue(
                        any("不在项目目录内" in item for item in findings),
                        (label, findings),
                    )

            # Symlinks (existing target, broken target, or symlinked parent dir) must be hard errors.
            if hasattr(os, "symlink"):
                episode = _write_paper_episode(root, base, create_media=False)
                video_dir = episode / "制作成果" / "video"
                video_dir.mkdir(parents=True, exist_ok=True)
                try:
                    (video_dir / "001.mp4").symlink_to(outside / "secret.mp4")
                except OSError:
                    return
                with patch.object(edit, "_emit") as emit:
                    rc = edit.main([
                        "check", "--plan-only", str(episode), "--project-root", str(root)
                    ])
                self.assertEqual(rc, 1, emit.call_args.args[0])
                self.assertTrue(
                    any("001.mp4" in item and "不在项目目录内" in item for item in emit.call_args.args[0]["findings"])
                )

                # Broken symlink pointing to a non-existent file outside the project.
                (video_dir / "001.mp4").unlink()
                (video_dir / "001.mp4").symlink_to(outside / "dangling.mp4")
                with patch.object(edit, "_emit") as emit:
                    rc = edit.main([
                        "check", "--plan-only", str(episode), "--project-root", str(root)
                    ])
                self.assertEqual(rc, 1, emit.call_args.args[0])
                self.assertTrue(
                    any("001.mp4" in item and "不在项目目录内" in item for item in emit.call_args.args[0]["findings"])
                )

                # Symlinked intermediate directory with non-existent leaf file.
                (video_dir / "001.mp4").unlink()
                video_dir.rmdir()
                video_dir.symlink_to(outside, target_is_directory=True)
                with patch.object(edit, "_emit") as emit:
                    rc = edit.main([
                        "check", "--plan-only", str(episode), "--project-root", str(root)
                    ])
                self.assertEqual(rc, 1, emit.call_args.args[0])
                self.assertTrue(
                    any("001.mp4" in item and "不在项目目录内" in item for item in emit.call_args.args[0]["findings"])
                )

    def test_symlink_bypass_via_nonexistent_parent_and_sibling_path_safety(self):
        if not hasattr(os, "symlink"):
            self.skipTest("platform does not support symlinks")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            outside = workspace / "outside"
            outside.mkdir()
            (outside / "secret.mp4").write_bytes(b"")
            root = workspace / "project"
            base = self._paper_cut_list()
            episode = _write_paper_episode(root, base, create_media=False)
            (root / "short-drama.json").write_text("{}", encoding="utf-8")

            media_root = episode / "制作成果"
            video_dir = media_root / "video"
            video_dir.mkdir(parents=True, exist_ok=True)
            try:
                (video_dir / "link_inside.mp4").symlink_to(root / "short-drama.json")
                (video_dir / "dangling_out.mp4").symlink_to(outside / "dangling.mp4")
                (media_root / "link_out").symlink_to(outside, target_is_directory=True)
                # Unrelated symlink outside project_root matching sibling episode name.
                (workspace / "EP002").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks cannot be created in this environment")

            # 1-3: `nonexistent/../<symlink>` must NEVER bypass symlink scanning.
            bypass_paths = (
                "nonexistent/../制作成果/video/link_inside.mp4",
                "nonexistent/../制作成果/video/dangling_out.mp4",
                "nonexistent/../制作成果/link_out/future.mp4",
            )
            for rel in bypass_paths:
                with self.subTest(bypass=rel):
                    self.assertEqual(
                        edit._inspect_media_path(episode, root, rel),
                        (None, "unsafe"),
                    )
                    mutated = base.replace("制作成果/video/001.mp4", rel)
                    (episode / "剪辑单.md").write_text(mutated, encoding="utf-8")
                    with patch.object(edit, "_emit") as emit:
                        rc = edit.main([
                            "check", "--plan-only", str(episode), "--project-root", str(root)
                        ])
                    self.assertEqual(rc, 1, emit.call_args.args[0])
                    self.assertTrue(
                        any("不在项目目录内" in item for item in emit.call_args.args[0]["findings"]),
                        emit.call_args.args[0]["findings"],
                    )

            # 4: Legitimate sibling path `../EP002/video.mp4` stays valid under episode
            # even when `project_root.parent / "EP002"` is an unrelated symlink.
            self.assertEqual(
                edit._inspect_media_path(episode, root, "../EP002/video.mp4"),
                (None, "missing"),
            )
            sibling_file = root / "剧集" / "EP002" / "video.mp4"
            sibling_file.parent.mkdir(parents=True, exist_ok=True)
            sibling_file.write_bytes(b"")
            self.assertEqual(
                edit._inspect_media_path(episode, root, "../EP002/video.mp4"),
                (sibling_file.resolve(), "ok"),
            )

    def test_plan_only_still_probes_existing_media_while_warning_on_missing_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cut_list = (
                "# EP001 剪辑单\n\n"
                "- 画幅与帧率：1080×1920 · 24fps\n\n"
                "## CUT-EP001-001 · 已生成片段\n\n"
                "- 来源：MOTION-EP001-001 · 制作成果/video/001.mp4\n"
                "- 入点：0.00\n- 出点：3.00\n- 时长：3.00\n"
                "- 字幕：0.20-1.50 请先坐下。\n\n"
                "## CUT-EP001-002 · 待生成片段\n\n"
                "- 来源：MOTION-EP001-002 · 制作成果/video/002.mp4\n"
                "- 入点：0.00\n- 出点：2.00\n- 时长：2.00\n"
                "- 字幕：0.10-1.50 合同放在桌上了。\n"
            )
            episode = _write_paper_episode(root, cut_list, create_media=False)
            (episode / "制作成果" / "video").mkdir(parents=True, exist_ok=True)
            (episode / "制作成果" / "video" / "001.mp4").write_bytes(b"")
            delivery, cuts, unused = edit.parse_cut_list(episode / "剪辑单.md")
            # Existing 001.mp4 is only 2.0s long while cut.end is 3.0s -> still caught as hard finding!
            with patch.object(
                edit,
                "probe_stream",
                return_value={"width": 1080, "height": 1920, "fps": 24.0, "duration": 2.0},
            ):
                findings, notices = edit._inspect_cuts(
                    episode, cuts, root, probe=True, unused=unused, delivery=delivery, plan_only=True
                )
            self.assertEqual(len(findings), 1, findings)
            self.assertIn("超过素材实际时长", findings[0])
            self.assertTrue(any("002.mp4" in item and "尚未生成" in item for item in notices), notices)


if __name__ == "__main__":
    unittest.main()
