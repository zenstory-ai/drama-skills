import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.media_require import has_ffmpeg


SKILL = Path(__file__).resolve().parents[1] / "skills/short-drama-edit"
SPEC = importlib.util.spec_from_file_location("edit_screen_text", SKILL / "scripts/edit_tool.py")
assert SPEC and SPEC.loader
edit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edit)
RULES = SKILL / "assets/remotion/src/rules.mjs"

SCREENPLAY = """# EP001

## EP001-SC001 内 · 办公室 · 日

[画面文字] 主号 2　小号 1　短视频 0

周团：十几个号，粉丝加起来，没号多。

[画面文字] 新任务：军宣新星　5 天内粉丝破 1,000,000

[画面文字] 剩余 4 天 23:59:58

[VO] 系统：发布任务，军宣新星。

江晨：五天，一百万？
"""


def cut_block(number, extra, *, media=None, start=0.0, end=3.0):
    return (
        f"## CUT-EP001-{number:03d} · 段\n\n"
        f"- 来源：MOTION-EP001-{number:03d} · {media or f'media/{number}.mp4'}\n"
        f"- 入点：{start:.2f}\n- 出点：{end:.2f}\n- 时长：{end - start:.2f}\n"
        "- 取舍：入点=起；出点=止\n- 声音：保留原声\n"
        + "".join(f"{line}\n" for line in extra)
        + "\n"
    )


class Project:
    def __init__(self, root: Path, blocks):
        self.episode = root / "剧集" / "EP001"
        (self.episode / "media").mkdir(parents=True)
        (self.episode / "剧本.md").write_text(SCREENPLAY, encoding="utf-8")
        headings = "".join(f"## MOTION-EP001-{i:03d}\n\n" for i in range(1, len(blocks) + 1))
        (self.episode / "视频提示词.md").write_text(headings, encoding="utf-8")
        for i in range(1, len(blocks) + 1):
            (self.episode / "media" / f"{i}.mp4").write_bytes(b"")
        self.root = root
        self.write(blocks)

    def write(self, blocks):
        body = "# 剪辑单\n\n" + "".join(
            cut_block(i, lines) for i, lines in enumerate(blocks, start=1)
        )
        (self.episode / "剪辑单.md").write_text(body, encoding="utf-8")

    def parse(self):
        return edit.parse_cut_list(self.episode / "剪辑单.md")[1]

    def findings(self):
        return edit.check_cuts(self.episode, self.parse(), self.root, probe=False)


class ScreenTextParsingTests(unittest.TestCase):
    def test_lines_parse_into_style_items_and_countdown(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 画面文字 1：0.00-1.40 卡片 主号 2｜小号 1",
                "- 画面文字 2：1.50-3.00 任务面板 军宣新星｜5 天内粉丝破 1,000,000（倒计时：431998）",
                "- 画面文字 3：1.50-3.00 角标 剩余（倒计时：接续）",
            ]])
            texts = project.parse()[0].screen_texts
            self.assertEqual([t.style for t in texts], ["卡片", "任务面板", "角标"])
            self.assertEqual(texts[0].items, ("主号 2", "小号 1"))
            self.assertEqual((texts[1].countdown, texts[1].resume), (431998.0, False))
            self.assertEqual((texts[2].countdown, texts[2].resume), (None, True))
            self.assertEqual(project.findings(), [])

    def test_malformed_lines_are_refused_at_parse(self):
        refused = {
            "same slot overlaps": [
                "- 画面文字 1：0.00-2.00 卡片 主号 2",
                "- 画面文字 2：1.50-3.00 系统面板 军宣新星",
            ],
            "countdown on a card": ["- 画面文字：0.00-2.00 卡片 主号 2（倒计时：60）"],
            "unknown style": ["- 画面文字：0.00-2.00 弹幕 主号 2"],
            "empty item": ["- 画面文字：0.00-2.00 卡片 主号 2｜｜小号 1"],
            "numbering gap": [
                "- 画面文字 1：0.00-1.00 卡片 主号 2",
                "- 画面文字 3：1.00-2.00 卡片 小号 1",
            ],
            "plain and numbered": [
                "- 画面文字：0.00-1.00 卡片 主号 2",
                "- 画面文字 1：1.00-2.00 卡片 小号 1",
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[]])
            for name, lines in refused.items():
                with self.subTest(name):
                    project.write([lines])
                    with self.assertRaises(edit.EditError):
                        project.parse()

    def test_a_field_written_twice_in_one_cut_is_refused(self):
        repeated = {
            "subtitle": ["- 字幕：五天，一百万？", "- 字幕：发布任务，军宣新星。"],
            "screen text": ["- 画面文字：0.00-1.00 卡片 主号 2", "- 画面文字：1.00-2.00 卡片 小号 1"],
            "sound effect": ["- 音效：0.00-1.00 media/1.mp4", "- 音效：1.00-2.00 media/1.mp4"],
            "same number": ["- 字幕 1：0.00-1.00 五天，一百万？", "- 字幕 1：1.00-2.00 五天，一百万？"],
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[]])
            for name, lines in repeated.items():
                with self.subTest(name):
                    project.write([lines])
                    with self.assertRaises(edit.EditError):
                        project.parse()
            # The same fields in two different cuts are two cuts, not a repeat.
            project.write([[line] for line in repeated["subtitle"]])
            self.assertEqual(len(project.parse()), 2)

    def test_a_panel_and_the_corner_chip_may_share_a_moment(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 画面文字 1：0.00-2.00 任务面板 军宣新星（倒计时：60）",
                "- 画面文字 2：0.50-3.00 角标 剩余（倒计时：接续）",
            ]])
            self.assertEqual(len(project.parse()[0].screen_texts), 2)

    def test_check_reports_range_trace_and_orphan_countdown(self):
        cases = {
            "past the cut": "- 画面文字：1.00-3.50 卡片 主号 2",
            "reversed": "- 画面文字：2.00-1.00 卡片 主号 2",
            # Dialogue is in the screenplay, but not on a [画面文字] line.
            "dialogue, not screen text": "- 画面文字：0.00-1.00 卡片 粉丝加起来",
            "invented": "- 画面文字：0.00-1.00 卡片 主号 200",
            "resume with nothing before": "- 画面文字：0.00-1.00 角标 剩余（倒计时：接续）",
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[]])
            for name, line in cases.items():
                with self.subTest(name):
                    project.write([[line]])
                    self.assertEqual(len(project.findings()), 1, project.findings())
            project.write([["- 画面文字：0.00-1.00 卡片 主号 2｜小号 1"]])
            self.assertEqual(project.findings(), [])

    def test_resume_is_satisfied_by_a_countdown_in_an_earlier_cut(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [
                ["- 画面文字：0.00-3.00 任务面板 军宣新星（倒计时：431998）"],
                ["- 画面文字：0.00-3.00 角标 剩余（倒计时：接续）"],
            ])
            self.assertEqual(project.findings(), [])
            project.write([
                ["- 画面文字：0.00-3.00 角标 剩余（倒计时：接续）"],
                ["- 画面文字：0.00-3.00 任务面板 军宣新星（倒计时：431998）"],
            ])
            self.assertEqual(len(project.findings()), 1)

    def test_caption_style_traces_to_screen_text_or_scene_heading_and_places_as_caption(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 画面文字 1：0.00-1.20 字卡 办公室 · 日",
                "- 画面文字 2：1.30-2.80 字卡 日 · 办公室",
            ]])
            cuts = project.parse()
            self.assertEqual([t.style for t in cuts[0].screen_texts], ["字卡", "字卡"])
            self.assertEqual(project.findings(), [])
            layers = edit._screen_text_layers(cuts, [3.0])
            self.assertEqual([layer["style"] for layer in layers], ["caption", "caption"])

            # Invented location/time still fails traceability.
            project.write([["- 画面文字：0.00-1.20 字卡 三年后 · 纽约"]])
            self.assertEqual(len(project.findings()), 1)

    def test_comma_and_slash_normalization_matches_progress_and_thousands(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[]])
            (project.episode / "剧本.md").write_text(
                SCREENPLAY + "\n[画面文字] 当前粉丝：2　目标进度：2／1000000\n",
                encoding="utf-8",
            )
            project.write([[
                "- 画面文字 1：0.00-1.20 字卡 5 天内粉丝破 1000000",
                "- 画面文字 2：1.30-2.80 任务面板 军宣新星｜2 / 1,000,000",
            ]])
            self.assertEqual(project.findings(), [])

    def test_caption_rejects_rarity_and_countdown_and_shares_upper_slot_with_system_panel(self):
        refused = {
            "caption with rarity": ["- 画面文字：0.00-1.50 字卡 办公室 · 日（传说）"],
            "caption with countdown": ["- 画面文字：0.00-1.50 字卡 办公室 · 日（倒计时：60）"],
            "caption colliding with upper-slot system panel": [
                "- 画面文字 1：0.00-2.00 字卡 办公室 · 日",
                "- 画面文字 2：1.50-2.80 系统面板 军宣新星",
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[]])
            for name, lines in refused.items():
                with self.subTest(name):
                    project.write([lines])
                    with self.assertRaises(edit.EditError):
                        project.parse()

    def test_fullwidth_slash_progress_normalizes_in_python_and_parses_in_remotion_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 画面文字：0.00-2.00 任务面板 军宣新星｜2／1,000,000",
            ]])
            cuts = project.parse()
            self.assertEqual(cuts[0].screen_texts[0].items, ("军宣新星", "2/1,000,000"))
            self.assertEqual(project.findings(), [])
            layers = edit._screen_text_layers(cuts, [3.0])
            self.assertEqual(
                layers[0]["items"],
                [
                    {"text": "军宣新星", "rarity": None},
                    {"text": "2/1,000,000", "rarity": None},
                ],
            )


class ScreenTextPlacementTests(unittest.TestCase):
    def blocks(self):
        return [
            ["- 画面文字：0.50-2.50 卡片 主号 2｜小号 1"],
            [
                "- 画面文字 1：1.00-2.00 任务面板 军宣新星（倒计时：431998）",
                "- 画面文字 2：2.00-3.00 角标 剩余（倒计时：接续）",
            ],
            ["- 画面文字：0.00-1.50 角标 剩余（倒计时：接续）"],
        ]

    def test_props_carry_screen_text_in_output_time(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), self.blocks())
            cuts = project.parse()
            # Rendered segments land on frame boundaries and run long; the
            # second one here by 0.06 s, which must push everything after it.
            spans = [3.0, 3.06, 3.0]
            layers = edit._screen_text_layers(cuts, spans)
            workspace = Path(directory) / "workspace"
            manifest = json.loads((edit.REMOTION_SOURCE / "package.json").read_text(encoding="utf-8"))
            for name in manifest["dependencies"]:
                (workspace / "node_modules" / name).mkdir(parents=True)
                (workspace / "node_modules" / name / "package.json").write_text("{}")
            captured = {}

            def fake_run(command, **_):
                props = next(arg for arg in command if arg.startswith("--props="))
                captured.update(json.loads(Path(props.split("=", 1)[1]).read_text(encoding="utf-8")))
                Path(command[4]).write_bytes(b"webm")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(edit, "_which", return_value="npx"), \
                    patch.object(edit.subprocess, "run", side_effect=fake_run):
                edit._render_remotion_overlay(
                    Path(directory), [], layers, {"width": 720, "height": 1280, "fps": 30},
                    sum(spans), workspace, needed_for="画面文字",
                )

        placed = [(t["style"], t["start"], t["end"], t["countdown"]) for t in captured["screenTexts"]]
        scale = 3.06 / 3.0
        self.assertEqual(placed, [
            ("card", 0.5, 2.5, None),
            ("task", round(3.0 + 1.0 * scale, 3), round(3.0 + 2.0 * scale, 3), 431998.0),
            # The chip continues the task's clock, and its piece in the next
            # cut is the same chip, extended rather than entering again.
            ("corner", round(3.0 + 2.0 * scale, 3), 6.06 + 1.5, round(431998.0 - scale, 3)),
        ])
        self.assertEqual(captured["cues"], [])
        self.assertEqual((captured["width"], captured["height"], captured["fps"]), (720, 1280, 30))

    def test_rarity_travels_with_its_item_and_is_not_part_of_the_text(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 画面文字：0.00-2.00 任务面板 军宣新星｜5 天内粉丝破 1,000,000（传说）",
            ]])
            layers = edit._screen_text_layers(project.parse(), [3.0])
            self.assertEqual(layers[0]["items"], [
                {"text": "军宣新星", "rarity": None},
                {"text": "5 天内粉丝破 1,000,000", "rarity": "传说"},
            ])
            # Traced without the suffix, so it is found in the [画面文字] line.
            self.assertEqual(project.findings(), [])
            project.write([["- 画面文字：0.00-2.00 卡片 主号 2（传说）"]])
            with self.assertRaises(edit.EditError):
                project.parse()

    def test_missing_remotion_fails_with_the_install_command(self):
        layer = {"start": 0.0, "end": 1.0, "style": "card",
                 "items": [{"text": "主号 2", "rarity": None}], "countdown": None}
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            # Nothing installed, and then Remotion without the font packages.
            for installed in ((), ("remotion", "@remotion/cli", "react", "react-dom")):
                for name in installed:
                    (workspace / "node_modules" / name).mkdir(parents=True, exist_ok=True)
                    (workspace / "node_modules" / name / "package.json").write_text("{}")
                with self.subTest(installed=installed), \
                        self.assertRaises(edit.EditError) as raised:
                    edit._render_remotion_overlay(
                        Path(directory), [], [layer], {}, 1.0, workspace, needed_for="画面文字"
                    )
                self.assertIn(f'cd "{workspace.resolve()}"\n  npm install', str(raised.exception))
                self.assertNotIn("&&", str(raised.exception))
                self.assertIn("@fontsource/noto-sans-sc", str(raised.exception))
            self.assertFalse((Path(directory) / "叠层.webm").exists())

    def test_ffmpeg_subtitles_are_burned_over_the_remotion_screen_text(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 字幕 1：0.20-1.40 十几个号，粉丝加起来，没号多。",
                "- 字幕 2：1.50-2.90 发布任务，军宣新星。（重点：军宣新星）",
                "- 画面文字：0.00-1.40 卡片 主号 2",
            ]])
            cuts = project.parse()
            commands = []
            overlay_calls = []

            def fake_overlay(output_root, cues, layers, *args, **kwargs):
                overlay_calls.append((list(cues), list(layers)))
                return output_root / "叠层.webm"

            with patch.object(edit, "_require", return_value="ffmpeg"), \
                    patch.object(edit, "_has_ffmpeg_filter", return_value=True), \
                    patch.object(edit, "_run", side_effect=commands.append), \
                    patch.object(edit, "probe_duration", return_value=3.0), \
                    patch.object(edit, "probe_audio", return_value=(48000, "stereo")), \
                    patch.object(edit, "probe_stream",
                                 return_value={"width": 720, "height": 1280, "fps": 30}), \
                    patch.object(edit, "_render_remotion_overlay", side_effect=fake_overlay):
                edit.render(project.episode, project.root, cuts,
                            edit.Delivery(None, None, True, None, None, None),
                            burn_subtitles=True, renderer="ffmpeg")
                ass = (project.episode / edit.OUTPUT_DIRECTORY / "字幕.ass").read_text(encoding="utf-8")

        self.assertEqual(len(overlay_calls), 1)
        self.assertEqual(overlay_calls[0][0], [], "ffmpeg 路线的字幕不该再进 Remotion")
        self.assertEqual(len(overlay_calls[0][1]), 1)
        final = commands[-1]
        graph = final[final.index("-filter_complex") + 1]
        self.assertLess(graph.index("overlay="), graph.index("ass="))
        dialogue = [row for row in ass.splitlines() if row.startswith("Dialogue")]
        # Dialogue in the style's white; the system voice cyan, its keyword yellow.
        self.assertTrue(dialogue[0].endswith(",十几个号　粉丝加起来　没号多"), dialogue)
        self.assertTrue(dialogue[1].endswith(
            ",{\\c&H00FFE03F&}发布任务　{\\c&H0000D4FF&}军宣新星{\\c&H00FFE03F&}"), dialogue)


class VerifyPlacementTests(unittest.TestCase):
    def test_verify_lists_where_screen_text_and_effects_landed(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [
                ["- 画面文字：0.00-3.00 任务面板 军宣新星（倒计时：60）"],
                ["- 画面文字：0.50-1.00 卡片 主号 2", "- 音效：0.50-1.00 media/1.mp4"],
            ])
            cuts = project.parse()
        self.assertEqual(
            edit._placements_for_sampling(cuts, None)["画面文字落点"],
            "未测（分段缺失，无法换算成片时间）",
        )
        placed = edit._placements_for_sampling(cuts, [3.1, 3.0])
        self.assertEqual([(p["起"], p["止"]) for p in placed["画面文字落点"]], [(0.0, 3.1), (3.6, 4.1)])
        self.assertEqual([(p["起"], p["止"]) for p in placed["音效落点"]], [(3.6, 4.1)])


    def test_verify_reports_an_orphan_resume_instead_of_stopping(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [["- 画面文字：0.00-1.00 角标 剩余（倒计时：接续）"]])
            cuts = project.parse()
        placed = edit._placements_for_sampling(cuts, [3.0])
        self.assertTrue(placed["画面文字落点"].startswith("未测"), placed)
        frames = [bytes([100]) * 16] * 30
        self.assertEqual(edit._frame_report(frames, 10.0, cuts, [3.0], [None])["疑似坏帧"], [])


class SubtitleDisplayTests(unittest.TestCase):
    def test_burned_text_drops_closing_marks_spaces_pauses_and_keeps_questions(self):
        cases = {
            "十几个号，粉丝加起来，没号多。": "十几个号　粉丝加起来　没号多",
            "五天，一百万？": "五天　一百万？",
            "上辈子，我手里十几个百万大号。死在公司上市前一个月。":
                "上辈子　我手里十几个百万大号　死在公司上市前一个月",
            "粉丝破 1,000,000！": "粉丝破 1,000,000！",
            "你刚唱的什么？！": "你刚唱的什么？！",
            "伴奏《亮剑》": "伴奏《亮剑》",
            "嗯……": "嗯",
        }
        for line, shown in cases.items():
            with self.subTest(line):
                self.assertEqual(edit._display_line(line), shown)
        cues = edit._display_cues([(0, 1, "……", ()), (1, 2, "走。", ())])
        self.assertEqual([(c.start, c.end, c.text) for c in cues], [(1, 2, "走")])

    def test_long_lines_split_at_pauses_into_timed_one_line_cues(self):
        line = "上辈子，我手里十几个百万大号。死在公司上市前一个月。"
        cues = edit._display_cues([(10.0, 16.0, line, ("百万大号",))])
        self.assertEqual([c.text for c in cues], ["上辈子", "我手里十几个百万大号", "死在公司上市前一个月"])
        self.assertTrue(all(edit._visible(c.text) <= edit.SUBTITLE_MAX_VISIBLE for c in cues))
        # Back to back across the window, each share by its character count.
        self.assertAlmostEqual(cues[0].start, 10.0)
        self.assertAlmostEqual(cues[-1].end, 16.0)
        self.assertAlmostEqual(cues[0].end, cues[1].start)
        self.assertAlmostEqual(cues[0].end - cues[0].start, 6.0 * 3 / 23)
        self.assertEqual([c.keys for c in cues], [(), ("百万大号",), ()])
        # Short phrases are packed back together while they fit.
        self.assertEqual(edit._split_display("发布任务　军宣新星　五天　一百万？"),
                         ["发布任务　军宣新星　五天", "一百万？"])
        # A phrase with no pause in it is cut into near-equal one-line parts.
        unbroken = edit._split_display("一二三四五六七八九十甲乙丙丁戊己庚辛")
        self.assertEqual(unbroken, ["一二三四五六七八九", "十甲乙丙丁戊己庚辛"])
        # A short line with a question inside stays whole.
        self.assertEqual(edit._split_display("五天　一百万？"), ["五天　一百万？"])

    def test_a_highlighted_word_is_never_split_and_matches_its_burned_form(self):
        cases = {
            # The even split would fall between 看不 and 起.
            "split point": ("我要让所有看不起我的人都后悔。", "看不起", "看不起"),
            # The pause inside the word is burned as a full-width space.
            "pause inside": ("给你十万，现金。", "十万，现金", "十万　现金"),
            # A pause inside the word is not a place to break the line either.
            "pause at the break": ("上辈子我手里有十几个百万大号，死在公司上市前一个月。",
                                   "百万大号，死在", "百万大号　死在"),
        }
        for name, (line, word, burned) in cases.items():
            with self.subTest(name):
                cues = edit._display_cues([(0.0, 3.0, line, (word,))])
                self.assertTrue(all(edit._visible(c.text) <= edit.SUBTITLE_MAX_VISIBLE for c in cues))
                self.assertEqual("　".join(c.text for c in cues).replace("　", ""),
                                 edit._display_line(line).replace("　", ""))
                self.assertEqual([c.keys for c in cues if c.keys], [(burned,)])
                self.assertIn(burned, next(c.text for c in cues if c.keys))
        with self.assertRaises(edit.EditError):
            edit._display_cues([(0.0, 1.0, "五天，一百万？", ("一千万",))])

    def test_colour_kind_comes_from_the_screenplay_line_quoted(self):
        screenplay = (
            "周团：十几个号，粉丝加起来，没号多。\n"
            "[VO] 江晨：我不懂音乐。\n"
            "[VO] 系统：绑定成功。\n"
            "[OS] 船员：关窗，水进来了！\n"
            "[画面文字] 系统：绑定中\n"
        )
        cases = {"粉丝加起来": "line", "我不懂音乐": "vo", "绑定成功": "system",
                 "关窗": "line", "绑定中": "line", "剧本里没有": "line"}
        for text, kind in cases.items():
            with self.subTest(text):
                cue = edit._display_cues([(0.0, 1.0, text, ())], screenplay)[0]
                self.assertEqual(cue.kind, kind)

    def test_keywords_must_occur_in_their_line(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [["- 字幕：五天，一百万？（重点：一百万｜五天）"]])
            subtitle = project.parse()[0].subtitles[0]
            self.assertEqual((subtitle[2], subtitle[3]), ("五天，一百万？", ("一百万", "五天")))
            self.assertEqual(project.findings(), [])
            for stray in ("一千万", "，"):
                with self.subTest(stray):
                    project.write([[f"- 字幕：五天，一百万？（重点：{stray}）"]])
                    with self.assertRaises(edit.EditError):
                        project.parse()

    def test_the_cut_list_still_quotes_the_screenplay_with_its_punctuation(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [["- 字幕：五天，一百万？"]])
            self.assertEqual(project.parse()[0].subtitles[0][2], "五天，一百万？")
            self.assertEqual(project.findings(), [])


class SoundEffectTests(unittest.TestCase):
    def test_parse_and_check(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [["- 音效 1：1.50-2.10 media/chime.wav（增益：-12）"]])
            effect = project.parse()[0].sound_effects[0]
            self.assertEqual((effect.start, effect.end, effect.path, effect.gain_db),
                             (1.5, 2.1, "media/chime.wav", -12.0))
            self.assertEqual(len(project.findings()), 1, "缺文件必须报")
            (project.episode / "media" / "chime.wav").write_bytes(b"")
            self.assertEqual(project.findings(), [])
            project.write([["- 音效：2.50-3.40 media/chime.wav"]])
            self.assertEqual(len(project.findings()), 1, "越过本段必须报")
            project.write([["- 音效：0.50-1.00 media/chime.wav（增益：+20）"]])
            with self.assertRaises(edit.EditError):
                project.parse()

    @unittest.skipUnless(has_ffmpeg(), "needs ffmpeg")
    def test_effect_is_heard_in_its_window_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            film, chime, mixed = root / "film.mp4", root / "chime.wav", root / "mixed.mp4"
            quiet = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
            subprocess.run(quiet + [
                "-f", "lavfi", "-i", "color=c=gray:size=64x64:rate=10:duration=4",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(film),
            ], check=True)
            subprocess.run(quiet + ["-f", "lavfi", "-i", "sine=frequency=1760:duration=2",
                                    str(chime)], check=True)
            subprocess.run(edit._sound_effect_command(
                "ffmpeg", film, [(1.5, 0.6, chime, -6.0, 0.0)], mixed), check=True)

            def level(media, start, length, band="highpass=f=1200,highpass=f=1200"):
                result = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(length), "-i", str(media),
                     "-af", f"{band},volumedetect", "-f", "null", "-"],
                    capture_output=True, text=True)
                return float(re.search(r"mean_volume: (\S+) dB", result.stderr).group(1))

            before, during, after = (level(mixed, 0.5, 0.8), level(mixed, 1.6, 0.4),
                                     level(mixed, 2.4, 0.8))
            # The film's own sound keeps its level; adding an effect must not duck it.
            original, kept = (level(media, 0.5, 0.8, "lowpass=f=600") for media in (film, mixed))
        self.assertGreater(during - before, 20)
        self.assertGreater(during - after, 20)
        self.assertLess(abs(original - kept), 1.0)


@unittest.skipUnless(shutil.which("node"), "needs node")
class OverlayRulesTests(unittest.TestCase):
    """The composition's font and countdown decisions, run by Node on the shipped module."""

    def run_rules(self, script: str):
        program = f"import * as rules from {json.dumps(RULES.as_uri())};\n{script}"
        result = subprocess.run(["node", "--input-type=module", "-e", program],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_family_check_on_a_machine_whose_cjk_fallback_is_the_requested_font(self):
        # A model of the browser: each character takes the first installed face
        # in the stack that has it; generic tails map to concrete faces, and CJK
        # falls back to PingFang whatever the tail. Widths differ per face.
        verdicts = self.run_rules(r"""
const installed = {
  "PingFang SC": { latin: true, cjk: true, w: 11 },
  "Times": { latin: true, cjk: false, w: 7 },
  "Courier": { latin: true, cjk: false, w: 9 },
  "Times New Roman": { latin: true, cjk: false, w: 7 },
};
const generic = { serif: "Times", "sans-serif": "PingFang SC", monospace: "Courier" };
const measure = (stack, text) => {
  const faces = stack.split(",").map((s) => s.trim().replace(/^"|"$/g, ""))
    .map((s) => generic[s] || s).filter((s) => installed[s]);
  let width = 0;
  for (const ch of text) {
    const cjk = ch > "⺀";
    const face = faces.find((f) => installed[f][cjk ? "cjk" : "latin"])
      || (cjk ? "PingFang SC" : "Times");
    width += installed[face].w * (1 + (ch.charCodeAt(0) % 3) / 10);
  }
  return width;
};
const sample = "十几个号粉丝加起来";
const stacks = [
  '"PingFang SC", "Noto Sans CJK SC", sans-serif',
  '"PingFang SC"',
  '"Times New Roman"',
  '"__no_such_family__", sans-serif',
  '"Missing A", "Missing B"',
  'sans-serif',
];
console.log(JSON.stringify(stacks.map((s) => rules.familyIsMissing(measure, s, sample))));
""")
        self.assertEqual(verdicts, [False, False, False, True, True, False])

    def test_countdown_is_a_pure_function_of_the_frame(self):
        shown = self.run_rules(r"""
const at = (countdown, frame, fps) => rules.formatCountdown(rules.secondsLeft(countdown, frame / fps));
console.log(JSON.stringify({
  first: at(431998, 0, 30), lastOfFirstSecond: at(431998, 29, 30), tick: at(431998, 30, 30),
  again: at(431998, 30, 30), hours: at(3725, 0, 24), minutes: at(42, 0, 24),
  end: at(2, 200, 24), fractional: at(431996.5, 0, 30),
}));
""")
        self.assertEqual(shown, {
            "first": "4天 23:59:58", "lastOfFirstSecond": "4天 23:59:58", "tick": "4天 23:59:57",
            "again": "4天 23:59:57", "hours": "01:02:05", "minutes": "00:42", "end": "00:00",
            "fractional": "4天 23:59:57",
        })

    def test_every_drawn_character_is_loaded_for_the_face_that_draws_it(self):
        plan = self.run_rules(r"""
const cues = [{ text: "五天　一百万？" }];
const screenTexts = [{ items: [{ text: "军宣新星" }, { text: "2 / 1,000,000" }] }];
console.log(JSON.stringify(rules.fontLoadPlan(cues, screenTexts)));
""")
        faces = {entry["font"]: set(entry["text"]) for entry in plan}
        sans = {face: chars for face, chars in faces.items() if "Noto Sans SC" in face}
        self.assertEqual({face.split()[0] for face in sans}, {"700", "900"})
        drawn = set("五天　一百万？军宣新星2 / 1,000,000【系统提示】【新任务】进度传说史诗稀有")
        for face, chars in sans.items():
            self.assertLessEqual(drawn, chars, face)
        mono = next(chars for face, chars in faces.items() if "JetBrains Mono" in face)
        self.assertLessEqual(set("0123456789:/, "), mono)

    def test_a_face_that_is_undeclared_late_or_unfinished_stops_the_render(self):
        verdicts = self.run_rules(r"""
const plan = [{ font: "900 16px A", text: "字" }, { font: "800 16px B", text: "1" }];
const ok = () => true;
console.log(JSON.stringify({
  ready: rules.fontLoadProblem(plan, [[{}], [{}]], ok),
  undeclared: rules.fontLoadProblem(plan, [[{}], []], ok),
  late: rules.fontLoadProblem(plan, rules.TIMED_OUT, ok),
  failed: rules.fontLoadProblem(plan, new Error("404"), ok),
  pending: rules.fontLoadProblem(plan, [[{}], [{}]], (font) => font.includes("A")),
}));
""")
        self.assertIsNone(verdicts.pop("ready"))
        for name, problem in verdicts.items():
            with self.subTest(name):
                self.assertIsInstance(problem, str)
        self.assertIn("800 16px B", verdicts["undeclared"])
        self.assertNotIn("900 16px A", verdicts["undeclared"])
        self.assertIn("800 16px B", verdicts["pending"])

    def test_font_wait_is_bounded_and_never_passes_off_a_timeout_as_success(self):
        outcome = self.run_rules(r"""
const started = Date.now();
const hung = await rules.settleWithin(new Promise(() => {}), 50);
const waited = Date.now() - started;
const quick = await rules.settleWithin(Promise.resolve([1]), 5000);
const failed = await rules.settleWithin(Promise.reject(new Error("no")), 5000);
console.log(JSON.stringify({ hung, waited, quick, failed: failed instanceof Error }));
""")
        self.assertEqual(outcome["hung"], "timed out")
        self.assertGreaterEqual(outcome["waited"], 45)
        self.assertLess(outcome["waited"], 2000)
        self.assertEqual(outcome["quick"], [1])
        self.assertTrue(outcome["failed"])

    def test_typing_progress_and_pulse_are_pure_functions_of_time(self):
        values = self.run_rules(r"""
console.log(JSON.stringify({
  typed: [0, 0.14, 0.15, 0.184, 0.186, 1.0].map((t) => rules.typedLength(t, 0.15)),
  progress: ["2 / 1,000,000", "1,000,001/1,000,000", "2 天", "3 / 0"].map(rules.parseProgress),
  pulse: [0, 0.1, 0.5, 1.0].map((t) => Math.round(rules.sinceTick(431998, t) * 100) / 100),
  // A resumed clock starts mid-second; its digit still changes on the whole second.
  resumed: [0, 0.5, 0.6].map((t) => Math.round(rules.sinceTick(431996.5, t) * 100) / 100),
  ems: rules.lineEms("五天　一百万？ok"),
  cjkPunctuationEms: rules.lineEms("——……“”‘’"),
}));
""")
        self.assertEqual(values["typed"], [0, 0, 0, 0, 1, 24])
        self.assertEqual(values["progress"][0], {"done": 2, "total": 1000000, "ratio": 2e-06})
        self.assertEqual(values["progress"][1]["ratio"], 1)
        self.assertEqual(values["progress"][2:], [None, None])
        # The digit changes at each whole second; the pulse restarts there.
        self.assertEqual(values["pulse"], [0.0, 0.1, 0.5, 0.0])
        self.assertEqual(values["resumed"], [0.5, 0.0, 0.1])
        self.assertAlmostEqual(values["ems"], 7 + 2 * 0.58)
        self.assertEqual(values["cjkPunctuationEms"], 8)

    def test_emoji_and_supplementary_plane_characters_fall_back_without_stopping_font_check(self):
        verdict = self.run_rules(r"""
const cues = [{ text: "冲上热搜🔥🎬⏰⭐⭕1️⃣\n" }];
const screenTexts = [{ items: [{ text: "粉丝暴涨🚀✨👨‍💻⏳" }, { text: "2 ／ 1,000,000" }] }];
const plan = rules.fontLoadPlan(cues, screenTexts);
const fwProgress = rules.parseProgress("2 ／ 1,000,000");
const strictBmpFontCheck = (_font, text) => {
  for (const ch of text) {
    const cp = ch.codePointAt(0);
    if (
      cp > 0xffff
      || cp < 0x20
      || (cp >= 0x2300 && cp <= 0x23ff)
      || (cp >= 0x2600 && cp <= 0x27bf)
      || cp === 0x2b50
      || cp === 0x2b55
      || cp === 0x200d
      || cp === 0x20e3
      || (cp >= 0xfe00 && cp <= 0xfe0f)
    ) {
      return false;
    }
  }
  return true;
};
const problem = rules.fontLoadProblem(plan, plan.map(() => [{}]), strictBmpFontCheck);
console.log(JSON.stringify({ plan, problem, fwProgress }));
""")
        self.assertIsNone(verdict["problem"])
        self.assertEqual(
            verdict["fwProgress"], {"done": 2, "total": 1000000, "ratio": 2e-06}
        )
        all_checked = "".join(entry["text"] for entry in verdict["plan"])
        for bmp_char in "冲上热搜粉丝暴涨":
            self.assertIn(bmp_char, all_checked)
        for excluded in ("🔥", "🎬", "🚀", "✨", "⏰", "⏳", "⭐", "⭕", "\u20e3", "／", "\n", "\u200d", "\ufe0f"):
            self.assertNotIn(excluded, all_checked)

    def test_is_checkable_bmp_glyph_keeps_ascii_digits_and_excludes_bmp_emoji(self):
        verdict = self.run_rules(r"""
const asciiKeep = ["#", "*", "0", "1", "9", "A", "z", "中"];
const emojiSkip = ["☀️", "☀", "❤️", "❤", "⚡", "✅", "㊗", "🎉"];
const plan = rules.fontLoadPlan(
  [{ text: "排名#1*9 ☀️❤️⚡✅㊗🎉" }],
  [{ items: [{ text: "3 ／ 10" }] }],
);
console.log(JSON.stringify({
  kept: asciiKeep.map((ch) => [ch, rules.isCheckableBmpGlyph(ch)]),
  skipped: emojiSkip.map((ch) => [ch, rules.isCheckableBmpGlyph(ch)]),
  heavyText: plan[0].text,
}));
""")
        for ch, allowed in verdict["kept"]:
            self.assertTrue(allowed, ch)
        for ch in ("#", "*", "1", "9", "3", "0", "/"):
            self.assertIn(ch, verdict["heavyText"])
        for ch, allowed in verdict["skipped"]:
            self.assertFalse(allowed, ch)
        for excluded in ("☀", "❤", "⚡", "✅", "㊗", "🎉", "／", "\ufe0f"):
            self.assertNotIn(excluded, verdict["heavyText"])

    def test_two_item_task_panel_extracts_progress_and_persistent_badge_joins_across_panel_cut(
        self,
    ):
        split_result = self.run_rules(r"""
const twoItem = rules.splitTaskItems([{ text: "军宣新星" }, { text: "0 / 100" }]);
const threeItem = rules.splitTaskItems([
  { text: "军宣新星" },
  { text: "五天破百万" },
  { text: "25 / 100" },
]);
const withReward = rules.splitTaskItems([
  { text: "军宣新星" },
  { text: "五天破百万" },
  { text: "50 / 100" },
  { text: "奖励：S级唱功" },
]);
console.log(JSON.stringify({ twoItem, threeItem, withReward }));
""")
        self.assertIsNone(split_result["twoItem"]["goal"])
        self.assertEqual(split_result["twoItem"]["rewards"], [])
        self.assertEqual(
            split_result["twoItem"]["progress"],
            {"done": 0, "total": 100, "ratio": 0},
        )
        self.assertEqual(split_result["threeItem"]["goal"], {"text": "五天破百万"})
        self.assertEqual(split_result["threeItem"]["rewards"], [])
        self.assertEqual(
            split_result["threeItem"]["progress"],
            {"done": 25, "total": 100, "ratio": 0.25},
        )
        self.assertEqual(split_result["withReward"]["goal"], {"text": "五天破百万"})
        self.assertEqual(
            split_result["withReward"]["rewards"], [{"text": "奖励：S级唱功"}]
        )
        self.assertEqual(
            split_result["withReward"]["progress"],
            {"done": 50, "total": 100, "ratio": 0.5},
        )

        # Persistent corner badge in CUT-1 + CUT-2 joins seamlessly even when a TaskPanel
        # sharing the same countdown clock appeared mid-way through CUT-1.
        with tempfile.TemporaryDirectory() as directory:
            project = Project(
                Path(directory),
                [
                    [
                        "- 画面文字 1：0.00-3.00 角标 剩余（倒计时：60）",
                        "- 画面文字 2：0.50-2.00 任务面板 新任务：军宣新星｜5 天内粉丝破 1,000,000（倒计时：59.5）",
                    ],
                    [
                        "- 画面文字：0.00-3.00 角标 剩余（倒计时：接续）",
                    ],
                ],
            )
            cuts = project.parse()
            layers = edit._screen_text_layers(cuts, [3.0, 3.0])

        self.assertEqual(len(layers), 2, layers)
        badge = next(item for item in layers if item["style"] == "corner")
        panel = next(item for item in layers if item["style"] == "task")
        self.assertAlmostEqual(badge["start"], 0.0)
        self.assertAlmostEqual(badge["end"], 6.0)
        self.assertAlmostEqual(badge["countdown"], 60.0)
        self.assertAlmostEqual(panel["start"], 0.5)
        self.assertAlmostEqual(panel["end"], 2.0)
        self.assertAlmostEqual(panel["countdown"], 59.5)

    def test_multi_word_english_speaker_vo_is_classified_as_vo_for_subtitles(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(
                Path(directory),
                [
                    [
                        "- 字幕 1：0.20-1.40 五天之内拿下百万粉丝。",
                        "- 字幕 2：1.50-2.80 任务现在开始。",
                    ]
                ],
            )
            (project.episode / "剧本.md").write_text(
                "# EP001\n\n"
                "## EP001-SC001 内 · 实验室 · 夜\n\n"
                "[VO] Dr. Lin：五天之内拿下百万粉丝。\n\n"
                "[VO] Mary Jane Watson（压低声音）：任务现在开始。\n",
                encoding="utf-8",
            )
            cuts = project.parse()
            cues = edit._display_cues(
                edit._subtitle_cues(cuts, [3.0]),
                edit._screenplay_text(project.episode),
            )
            self.assertEqual([cue.kind for cue in cues], ["vo", "vo"])
            vo_colour = edit._ass_colour(edit.SUBTITLE_COLOURS["vo"])
            ass = edit._build_ass(cues, 720, 1280)
            dialogue = [row for row in ass.splitlines() if row.startswith("Dialogue:")]
            self.assertEqual(len(dialogue), 2)
            self.assertTrue(all(f"{{\\c{vo_colour}}}" in row for row in dialogue), dialogue)

    def test_screenplay_html_comments_multiline_vo_paragraphs_and_interleaved_countdowns(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(
                Path(directory),
                [
                    [
                        "- 字幕 1：0.10-0.90 五天，一百万？",
                        "- 字幕 2：1.00-1.90 23:59：系统即将关闭。",
                        "- 字幕 3：2.00-2.90 这一世绝不重蹈覆辙。",
                        "- 画面文字 1：0.00-3.00 角标 剩余（倒计时：60）",
                        "- 画面文字 2：0.50-2.00 任务面板 军宣新星（倒计时：10）",
                    ],
                    [
                        "- 画面文字 1：0.00-3.00 角标 剩余（倒计时：接续）",
                        "- 画面文字 2：0.50-2.00 任务面板 军宣新星（倒计时：接续）",
                    ],
                ],
            )
            (project.episode / "剧本.md").write_text(
                "\ufeff# EP001\r\n\r\n"
                "## EP001-SC001 内 · 办公室 · 夜\r\n\r\n"
                "<!-- [VO] 系统：五天，一百万？ -->\r\n"
                "<!-- 江晨：删掉的废稿台词。 -->\r\n"
                "<!-- [画面文字] 废弃面板 999 -->\r\n\r\n"
                "[画面文字] 剩余 4 天 23:59:58　军宣新星\r\n\r\n"
                "江晨：五天，一百万？\r\n\r\n"
                "[VO] 系统：\r\n"
                "发布任务，军宣新星。\r\n"
                "23:59：系统即将关闭。\r\n\r\n"
                "[VO] 江晨（内心独白）：\r\n"
                "上辈子死在上市前夜。\r\n"
                "这一世绝不重蹈覆辙。\r\n",
                encoding="utf-8",
            )
            cuts = project.parse()
            self.assertEqual(project.findings(), [])

            cues = edit._display_cues(
                edit._subtitle_cues(cuts, [3.0, 3.0]),
                edit._screenplay_text(project.episode),
            )
            # Commented-out `[VO] 系统：五天，一百万？` must not hijack 江晨's spoken line;
            # multiline `[VO] 系统：` with `23:59：` clock line stays `system`; multiline VO stays `vo`.
            self.assertEqual([cue.kind for cue in cues], ["line", "system", "vo"])

            # Interleaved 角标 (60s clock) and 任务面板 (10s clock) track per-position countdowns independently.
            layers = edit._screen_text_layers(cuts, [3.0, 3.0])
            corners = [layer for layer in layers if layer["style"] == "corner"]
            tasks = [layer for layer in layers if layer["style"] == "task"]
            self.assertEqual(len(corners), 1, corners)
            self.assertAlmostEqual(corners[0]["start"], 0.0)
            self.assertAlmostEqual(corners[0]["end"], 6.0)
            self.assertAlmostEqual(corners[0]["countdown"], 60.0)
            self.assertEqual(len(tasks), 2, tasks)
            self.assertAlmostEqual(tasks[0]["countdown"], 10.0)
            self.assertAlmostEqual(tasks[1]["start"], 3.5)
            self.assertAlmostEqual(tasks[1]["countdown"], 7.0)

            # Commented-out dialogue and commented-out [画面文字] must fail check_cuts.
            project.write([["- 字幕：删掉的废稿台词。"], []])
            self.assertEqual(len(project.findings()), 1)
            project.write([["- 画面文字：0.00-1.00 卡片 废弃面板 999"], []])
            self.assertEqual(len(project.findings()), 1)


class ScreenTextFallbackAndAssTests(unittest.TestCase):
    def test_auto_mode_falls_back_to_ffmpeg_ass_for_caption_when_remotion_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 字幕：十几个号，粉丝加起来，没号多。",
                "- 字幕时间：0.20-1.40",
                "- 画面文字：0.00-1.20 字卡 办公室 · 日",
            ]])
            cuts = project.parse()
            commands = []

            def fail_if_remotion_called(*args, **kwargs):
                raise AssertionError("Remotion should not be invoked when auto falls back to ffmpeg")

            with patch.object(edit, "_require", return_value="ffmpeg"), \
                    patch.object(edit, "_remotion_available", return_value=False), \
                    patch.object(edit, "_has_ffmpeg_filter", return_value=True), \
                    patch.object(edit, "_run", side_effect=commands.append), \
                    patch.object(edit, "probe_duration", return_value=3.0), \
                    patch.object(edit, "probe_audio", return_value=(48000, "stereo")), \
                    patch.object(
                        edit, "probe_stream",
                        return_value={"width": 720, "height": 1280, "fps": 30},
                    ), \
                    patch.object(edit, "_render_remotion_overlay", side_effect=fail_if_remotion_called):
                report = edit.render(
                    project.episode,
                    project.root,
                    cuts,
                    edit.Delivery(None, None, True, None, None, None),
                    burn_subtitles=True,
                    renderer="ffmpeg",
                    screen_text_mode="auto",
                )
                screen_ass = (
                    project.episode / edit.OUTPUT_DIRECTORY / "画面文字.ass"
                ).read_text(encoding="utf-8")
                sub_ass = (
                    project.episode / edit.OUTPUT_DIRECTORY / "字幕.ass"
                ).read_text(encoding="utf-8")

        self.assertEqual(report["画面文字"], 1)
        self.assertEqual(report["画面文字渲染"], "ffmpeg")
        self.assertIsNone(report["叠层"])
        self.assertIsNotNone(report["压制画面文字"])
        self.assertTrue(any("兜底" in note for note in report.get("提醒", [])), report)
        self.assertIn("PlayResX: 720", screen_ass)
        self.assertIn("PlayResY: 1280", screen_ass)
        self.assertIn("办公室 · 日", screen_ass)
        self.assertIn("十几个号　粉丝加起来　没号多", sub_ass)
        final = commands[-1]
        vf = final[final.index("-vf") + 1]
        self.assertLess(vf.index("screen_text.ass"), vf.index("subtitles.ass"))

    def test_ffmpeg_mode_renders_caption_without_remotion_and_rejects_complex_panels(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 画面文字：0.00-1.50 字卡 办公室｜日",
            ]])
            cuts = project.parse()
            commands = []

            def fail_if_remotion_called(*args, **kwargs):
                raise AssertionError("Remotion must not run under --screen-text-mode ffmpeg")

            with patch.object(edit, "_require", return_value="ffmpeg"), \
                    patch.object(edit, "_remotion_available", return_value=True), \
                    patch.object(edit, "_has_ffmpeg_filter", return_value=True), \
                    patch.object(edit, "_run", side_effect=commands.append), \
                    patch.object(edit, "probe_duration", return_value=3.0), \
                    patch.object(edit, "probe_audio", return_value=(48000, "stereo")), \
                    patch.object(
                        edit, "probe_stream",
                        return_value={"width": 1080, "height": 1920, "fps": 24},
                    ), \
                    patch.object(edit, "_render_remotion_overlay", side_effect=fail_if_remotion_called):
                report = edit.render(
                    project.episode,
                    project.root,
                    cuts,
                    edit.Delivery(None, None, False, None, None, None),
                    burn_subtitles=False,
                    screen_text_mode="ffmpeg",
                )
                screen_ass = (
                    project.episode / edit.OUTPUT_DIRECTORY / "画面文字.ass"
                ).read_text(encoding="utf-8")

            self.assertEqual(report["画面文字渲染"], "ffmpeg")
            self.assertIn("办公室\\N{", screen_ass)
            self.assertIn("日", screen_ass)

            # Complex panels are refused in explicit ffmpeg mode with a clear error.
            project.write([["- 画面文字：0.00-2.00 系统面板 军宣新星"]])
            complex_cuts = project.parse()
            with patch.object(edit, "_require", return_value="ffmpeg"), \
                    self.assertRaises(edit.EditError) as raised:
                edit.render(
                    project.episode,
                    project.root,
                    complex_cuts,
                    edit.Delivery(None, None, False, None, None, None),
                    burn_subtitles=False,
                    screen_text_mode="ffmpeg",
                )
            self.assertIn("仅支持无框「字卡」", str(raised.exception))
            self.assertIn("系统面板", str(raised.exception))

        # Escaping braces/backslashes in screen text ASS prevents libass override injection.
        escaped_ass = edit._build_screen_text_ass(
            [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "style": "caption",
                    "items": [
                        {"text": "{地点}\\N教室", "rarity": None},
                        {"text": "次行{备注}", "rarity": None},
                    ],
                    "countdown": None,
                }
            ],
            720,
            1280,
        )
        dialogue = next(line for line in escaped_ass.splitlines() if line.startswith("Dialogue:"))
        self.assertIn("\\{地点\\}\\\u2060N教室", dialogue)
        self.assertNotIn("地点\\}\\N教室", dialogue)
        self.assertIn("次行\\{备注\\}", dialogue)

    def test_off_mode_skips_screen_text_overlays_while_still_burning_subtitles(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 字幕：五天，一百万？",
                "- 字幕时间：0.20-1.40",
                "- 画面文字 1：0.00-2.00 任务面板 军宣新星（倒计时：60）",
                "- 画面文字 2：0.50-2.50 角标 剩余（倒计时：接续）",
            ]])
            cuts = project.parse()
            commands = []

            def fail_if_remotion_called(*args, **kwargs):
                raise AssertionError("Remotion must not run under --screen-text-mode off")

            with patch.object(edit, "_require", return_value="ffmpeg"), \
                    patch.object(edit, "_has_ffmpeg_filter", return_value=True), \
                    patch.object(edit, "_run", side_effect=commands.append), \
                    patch.object(edit, "probe_duration", return_value=3.0), \
                    patch.object(edit, "probe_audio", return_value=(48000, "stereo")), \
                    patch.object(
                        edit, "probe_stream",
                        return_value={"width": 720, "height": 1280, "fps": 30},
                    ), \
                    patch.object(edit, "_render_remotion_overlay", side_effect=fail_if_remotion_called):
                report = edit.render(
                    project.episode,
                    project.root,
                    cuts,
                    edit.Delivery(None, None, True, None, None, None),
                    burn_subtitles=True,
                    renderer="ffmpeg",
                    screen_text_mode="off",
                )
                self.assertTrue((project.episode / edit.OUTPUT_DIRECTORY / "字幕.srt").is_file())
                self.assertTrue((project.episode / edit.OUTPUT_DIRECTORY / "字幕.ass").is_file())
                self.assertFalse((project.episode / edit.OUTPUT_DIRECTORY / "画面文字.ass").exists())

        self.assertEqual(report["画面文字"], 0)
        self.assertEqual(report["画面文字渲染"], "off")
        self.assertIsNone(report["叠层"])
        self.assertIsNone(report["压制画面文字"])
        self.assertTrue(any("--screen-text-mode off" in note for note in report.get("提醒", [])), report)
        final = commands[-1]
        self.assertIn("-vf", final)
        self.assertIn("subtitles.ass", final[final.index("-vf") + 1])

    @unittest.skipUnless(has_ffmpeg(require_ass=True), "needs ffmpeg with libass")
    def test_cli_renders_plain_caption_without_node_or_remotion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = Project(root, [[
                "- 字幕：五天，一百万？",
                "- 字幕时间：0.10-0.90",
                "- 画面文字：0.00-0.80 字卡 办公室 · 日",
            ]])
            cut_list = (project.episode / "剪辑单.md").read_text(encoding="utf-8")
            (project.episode / "剪辑单.md").write_text(
                cut_list.replace("- 出点：3.00\n- 时长：3.00", "- 出点：1.00\n- 时长：1.00"),
                encoding="utf-8",
            )
            media = project.episode / "media" / "1.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=0x223344:size=320x568:rate=24:duration=1.5",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(media),
                ],
                check=True,
            )

            real_which = shutil.which

            def which_without_npx(name):
                return None if name == "npx" else real_which(name)

            with patch.object(edit, "_which", side_effect=which_without_npx):
                exit_code = edit.main([
                    "render", str(project.episode),
                    "--project-root", str(root),
                    "--screen-text-mode", "auto",
                ])

            self.assertEqual(exit_code, 0)
            out = project.episode / edit.OUTPUT_DIRECTORY
            self.assertTrue((out / "成片.mp4").is_file())
            self.assertTrue((out / "画面文字.ass").is_file())
            self.assertTrue((out / "字幕.srt").is_file())
            self.assertTrue((out / "字幕.ass").is_file())
            self.assertFalse((out / "叠层.webm").exists())

    def test_subtitle_ass_geometry_escaping_and_measured_timing(self):
        width, height = 768, 1344
        line = "他念出来：{姓名}，请签字。"
        escaped = edit._ass_text(line)
        self.assertIn("\\{", escaped)
        self.assertIn("\\}", escaped)
        self.assertIn("姓名", escaped)
        for seq in ("\\N", "\\n", "\\h"):
            with self.subTest(seq=seq):
                neutralized = edit._ass_text(f"反斜杠 {seq} 不是控制符")
                self.assertNotIn(seq, neutralized)
                self.assertIn("\\\u2060" + seq[1], neutralized)

        ass = edit._build_ass([edit.DisplayCue(1.0, 2.0, line)], width, height)
        self.assertIn(f"PlayResX: {width}", ass)
        self.assertIn(f"PlayResY: {height}", ass)
        style = next(row for row in ass.splitlines() if row.startswith("Style:"))
        fields = style.split(":", 1)[1].split(",")
        font_size = float(fields[2])
        margin_h = float(fields[19])
        margin_v = float(fields[21])
        self.assertGreaterEqual(font_size, height * 0.02)
        self.assertLessEqual(font_size, height * 0.06)
        self.assertGreater(margin_v, height * 0.15)
        self.assertLess(margin_v, height * 0.30)
        self.assertGreater(margin_h, 0)
        dialogue = next(row for row in ass.splitlines() if row.startswith("Dialogue:"))
        self.assertTrue(dialogue.endswith(escaped), dialogue)

        # Cues shift by exact measured segment overrun, and numbered subtitles validate cleanly.
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [
                ["- 字幕：无"],
                ["- 字幕：五天，一百万？"],
            ])
            cuts = project.parse()
            declared = [cut.end - cut.start for cut in cuts]
            measured = [span + 0.04 for span in declared]
            drifting = edit._subtitle_cues(cuts, declared)
            shifted = edit._subtitle_cues(cuts, measured)
            self.assertEqual(len(shifted), 1)
            self.assertAlmostEqual(shifted[0][0], drifting[0][0] + 0.04, places=6)

            for label, bad_lines in (
                (
                    "numbering gap",
                    ["- 字幕 1：0.10-0.60 五天，一百万？", "- 字幕 3：1.00-1.50 五天，一百万？"],
                ),
                (
                    "overlapping cues",
                    ["- 字幕 1：0.10-1.00 五天，一百万？", "- 字幕 2：0.80-1.40 五天，一百万？"],
                ),
                (
                    "untimed multi-subtitle",
                    ["- 字幕 1：五天，一百万？", "- 字幕 2：0.80-1.40 五天，一百万？"],
                ),
            ):
                with self.subTest(label):
                    project.write([bad_lines])
                    with self.assertRaises(edit.EditError):
                        project.parse()

    def test_remotion_source_manifest_matches_shipped_files_and_passes_concurrency_flag(self):
        on_disk = {
            path.relative_to(edit.REMOTION_SOURCE).as_posix()
            for path in edit.REMOTION_SOURCE.rglob("*")
            if path.is_file()
            and path.suffix in {".ts", ".tsx", ".mjs", ".json"}
            and "node_modules" not in path.parts
        }
        listed = set(edit.REMOTION_SOURCE_FILES)
        self.assertEqual(on_disk, listed)
        self.assertGreaterEqual(edit.DEFAULT_REMOTION_CONCURRENCY, 1)

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            manifest = json.loads((edit.REMOTION_SOURCE / "package.json").read_text(encoding="utf-8"))
            for name in manifest["dependencies"]:
                (workspace / "node_modules" / name).mkdir(parents=True)
                (workspace / "node_modules" / name / "package.json").write_text("{}")
            invoked = []

            def fake_run(command, **_):
                invoked.append(command)
                Path(command[4]).write_bytes(b"webm")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(edit, "_which", return_value="npx"), \
                    patch.object(edit.subprocess, "run", side_effect=fake_run):
                edit._render_remotion_overlay(
                    Path(directory), [], [], {"width": 720, "height": 1280, "fps": 24},
                    1.0, workspace, concurrency=3, needed_for="字幕",
                )
        self.assertIn("--concurrency=3", invoked[0])

    def test_bold_colon_inside_emphasis_parses_identically_across_all_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = root / "剧集" / "EP001"
            (episode / "media").mkdir(parents=True)
            for name in ("1.mp4", "sfx.wav", "voice.wav"):
                (episode / "media" / name).write_bytes(b"")
            (episode / "剧本.md").write_text(SCREENPLAY, encoding="utf-8")
            (episode / "视频提示词.md").write_text(
                "## MOTION-EP001-001\n- **分镜：** SHOT-1\n\n## MOTION-EP001-002\n- **分镜：** SHOT-2\n",
                encoding="utf-8",
            )
            (episode / "分镜.md").write_text(
                "## SHOT-1\n- **来源：** EP001-SC001\n\n## SHOT-2\n- **来源：** EP001-SC001\n",
                encoding="utf-8",
            )
            cut_list_path = episode / "剪辑单.md"
            cut_list_path.write_text(
                "# EP001 剪辑单\n\n"
                "- **成片目标时长：** 3.00 秒\n"
                "- **画幅与帧率：** 16:9 · 1920×1080 · 24fps\n"
                "- **交付响度：** -16 LUFS\n"
                "- **未采用镜头：** MOTION-EP001-002（理由：删减）\n\n"
                "## CUT-EP001-001 · 冒号在加粗内\n\n"
                "- **来源：** MOTION-EP001-001 · media/1.mp4\n"
                "- **入点：** 0.00\n"
                "- **出点：** 3.00\n"
                "- **时长：** 3.00\n"
                "- **取舍：** 入点=起；出点=止\n"
                "- **声音：** 保留原声\n"
                "- **字幕：** 五天，一百万？（重点：一百万）\n"
                "- **画面文字：** 0.20-1.50 卡片 主号 2｜小号 1\n"
                "- **音效：** 0.40-1.00 media/sfx.wav（增益：-6）\n"
                "- **配音：** 0.10 media/voice.wav（增益：-3）\n",
                encoding="utf-8",
            )
            delivery, cuts, unused = edit.parse_cut_list(cut_list_path)
            self.assertEqual(delivery.target_seconds, 3.0)
            self.assertEqual(delivery.frame_size, (1920, 1080))
            self.assertEqual(delivery.fps, 24.0)
            self.assertEqual(delivery.loudness_lufs, -16.0)
            self.assertEqual(unused, ["MOTION-EP001-002（理由：删减）"])
            self.assertEqual(len(cuts), 1)
            cut = cuts[0]
            self.assertEqual(cut.subtitles, ((None, None, "五天，一百万？", ("一百万",)),))
            self.assertEqual(len(cut.screen_texts), 1)
            self.assertEqual(cut.screen_texts[0].items, ("主号 2", "小号 1"))
            self.assertEqual(len(cut.sound_effects), 1)
            self.assertEqual(cut.sound_effects[0].gain_db, -6.0)
            self.assertEqual(len(cut.voices), 1)
            self.assertEqual(cut.voices[0].gain_db, -3.0)
            self.assertEqual(
                edit._scene_keys(episode, cuts), [("EP001-SC001",)]
            )
            self.assertEqual(
                edit.check_cuts(
                    episode, cuts, root, probe=False, unused=unused, delivery=delivery
                ),
                [],
            )

            # Plain form, bold-outside-colon, italic-inside-colon, and ASCII colon all match identically.
            cut_list_path.write_text(
                "# EP001 剪辑单\n\n"
                "- __未采用镜头:__ MOTION-EP001-002（理由：删减）\n\n"
                "## CUT-EP001-001 · 多种强调\n\n"
                "- *来源:* MOTION-EP001-001 · media/1.mp4\n"
                "- _入点：_ 0.00\n"
                "- **出点**：3.00\n"
                "- 时长：3.00\n"
                "- **字幕 1:** 0.10-1.20 五天，一百万？\n"
                "- __画面文字 1：__ 0.20-1.00 字卡 办公室 · 日\n"
                "- *音效 1：* 0.40-0.90 media/sfx.wav\n"
                "- _配音 1:_ 0.10 media/voice.wav\n",
                encoding="utf-8",
            )
            _, alt_cuts, alt_unused = edit.parse_cut_list(cut_list_path)
            self.assertEqual(alt_unused, ["MOTION-EP001-002（理由：删减）"])
            self.assertEqual(alt_cuts[0].subtitles, ((0.1, 1.2, "五天，一百万？", ()),))
            self.assertEqual(alt_cuts[0].screen_texts[0].style, "字卡")
            self.assertEqual(len(alt_cuts[0].sound_effects), 1)
            self.assertEqual(len(alt_cuts[0].voices), 1)

    def test_english_subtitles_wrap_on_word_boundaries_without_chopping_words(self):
        short_line = "I need to talk to you right now."
        short_cues = edit._display_cues([(0.0, 2.5, short_line, ())])
        self.assertEqual([c.text for c in short_cues], ["I need to talk to you right now"])

        long_line = "Dr. Lin, the security footage from 11:30 is missing."
        long_cues = edit._display_cues([(0.0, 4.0, long_line, ("security footage",))])
        pieces = [c.text for c in long_cues]
        self.assertGreaterEqual(len(pieces), 2)
        self.assertTrue(all(len(piece) <= edit.SUBTITLE_MAX_LATIN for piece in pieces), pieces)
        self.assertEqual(" ".join(pieces), "Dr. Lin, the security footage from 11:30 is missing")
        for intact in ("Dr.", "Lin,", "security", "footage", "11:30", "missing"):
            self.assertTrue(any(intact in piece.split(" ") for piece in pieces), (intact, pieces))
        self.assertTrue(any("security footage" in c.keys for c in long_cues), long_cues)

        # Even an over-length single token is never chopped mid-word.
        giant = "SupercalifragilisticexpialidociousIdentifierToken"
        self.assertEqual(edit._split_display(giant), [giant])

    def test_landscape_ass_margin_overlapping_keywords_and_english_system_speaker(self):
        # Landscape (16:9) margin_v is ~8-10%, portrait (9:16) stays 24%.
        cue = edit.DisplayCue(0.0, 2.0, "给你十万元现金", "line", ("十万", "十万元"))
        landscape_ass = edit._build_ass([cue], 1920, 1080)
        portrait_ass = edit._build_ass([cue], 1080, 1920)
        landscape_margin_v = float(
            next(r for r in landscape_ass.splitlines() if r.startswith("Style:"))
            .split(":", 1)[1].split(",")[21]
        )
        portrait_margin_v = float(
            next(r for r in portrait_ass.splitlines() if r.startswith("Style:"))
            .split(":", 1)[1].split(",")[21]
        )
        self.assertGreaterEqual(landscape_margin_v, 1080 * 0.08)
        self.assertLessEqual(landscape_margin_v, 1080 * 0.10)
        self.assertAlmostEqual(portrait_margin_v, round(1920 * 0.24))

        # Overlapping keywords at the same start index choose the longest match ("十万元" beats "十万").
        yellow = edit._ass_colour(edit.SUBTITLE_KEYWORD_COLOUR)
        white = edit._ass_colour(edit.SUBTITLE_COLOURS["line"])
        rendered = edit._ass_line(cue)
        self.assertIn(f"{{\\c{yellow}}}十万元{{\\c{white}}}", rendered)

        # Case-insensitive English System VO speaker classifies as `system`.
        screenplay = (
            "[VO] System: Mission accepted.\n"
            "[VO] AI SYSTEM: Warning detected.\n"
            "[VO] Systematic: This is normal narration.\n"
        )
        self.assertEqual(edit._line_kind("Mission accepted.", screenplay), "system")
        self.assertEqual(edit._line_kind("Warning detected.", screenplay), "system")
        self.assertEqual(edit._line_kind("This is normal narration.", screenplay), "vo")

    def test_external_overlay_renderer_protocol_with_mock_python_script(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = Project(root, [[
                "- 字幕：五天，一百万？",
                "- 字幕时间：0.20-1.40",
                "- 画面文字：0.10-1.20 卡片 主号 2｜小号 1",
            ]])
            cuts = project.parse()
            mock_script = root / "mock_overlay_renderer.py"
            received_copy = root / "received_props.json"
            mock_script.write_text(
                "import argparse, json, pathlib\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--props', required=True)\n"
                "p.add_argument('--output', required=True)\n"
                "args = p.parse_args()\n"
                "data = json.loads(pathlib.Path(args.props).read_text(encoding='utf-8'))\n"
                f"pathlib.Path({str(received_copy)!r}).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')\n"
                "pathlib.Path(args.output).write_bytes(b'MOCK_WEBM_ALPHA')\n",
                encoding="utf-8",
            )
            commands = []
            cmd_str = f'"{edit.sys.executable}" "{mock_script}"'
            with patch.object(edit, "_require", return_value="ffmpeg"), \
                    patch.object(edit, "_has_ffmpeg_filter", return_value=True), \
                    patch.object(edit, "_probe_video_codec", return_value="vp8"), \
                    patch.object(edit, "_run", side_effect=commands.append), \
                    patch.object(edit, "probe_duration", return_value=3.0), \
                    patch.object(edit, "probe_audio", return_value=(48000, "stereo")), \
                    patch.object(
                        edit, "probe_stream",
                        return_value={"width": 1920, "height": 1080, "fps": 24},
                    ), \
                    patch.object(
                        edit, "_render_remotion_overlay",
                        side_effect=AssertionError("Remotion must not run when --overlay-renderer is set"),
                    ):
                report = edit.render(
                    project.episode,
                    project.root,
                    cuts,
                    edit.Delivery(None, None, True, None, None, None),
                    burn_subtitles=True,
                    renderer="ffmpeg",
                    screen_text_mode="auto",
                    overlay_renderer=cmd_str,
                )

            self.assertEqual(report["画面文字渲染"], "external")
            self.assertEqual(report["字幕渲染"], "ffmpeg")
            self.assertTrue(Path(report["叠层"]).is_file())
            received = json.loads(received_copy.read_text(encoding="utf-8"))
            self.assertEqual((received["width"], received["height"], received["fps"]), (1920, 1080, 24))
            self.assertEqual(received["cues"], [])
            self.assertEqual(len(received["layers"]), 1)
            self.assertEqual(received["layers"], received["screenTexts"])
            self.assertEqual(received["layers"][0]["style"], "card")
            final = commands[-1]
            self.assertIn("-filter_complex", final)
            self.assertIn("overlay=0:0:format=auto", final[final.index("-filter_complex") + 1])

            # Non-zero exit from external renderer raises EditError.
            failing_script = root / "fail_renderer.py"
            failing_script.write_text("import sys; sys.stderr.write('boom'); sys.exit(3)\n", encoding="utf-8")
            with self.assertRaisesRegex(edit.EditError, "外部叠层渲染失败"):
                edit._render_external_overlay(
                    f'"{edit.sys.executable}" "{failing_script}"',
                    root, [], received["layers"], {"width": 1920, "height": 1080, "fps": 24}, 3.0,
                )

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_remotion_rules_landscape_geometry_multilingual_fallback_and_english_card_rows(self):
        program = (
            f"import * as rules from {json.dumps(RULES.as_uri())};\n"
            r"""
const out = {
  bottomLandscape: rules.subtitleBottomU(1920, 1080),
  bottomPortrait: rules.subtitleBottomU(1080, 1920),
  cardLandscape: rules.panelWidth(1920, 1080, 0.8, 0.72),
  cardPortrait: rules.panelWidth(1080, 1920, 0.8, 0.72),
  sysLandscape: rules.panelWidth(1920, 1080, 0.82, 0.72),
  taskLandscape: rules.panelWidth(1920, 1080, 0.86, 0.76),
  otherScripts: ["П", "م", "안", "ส"].map((ch) => rules.isCheckableBmpGlyph(ch)),
  cjkAscii: ["中", "A", "9", "·", "—"].map((ch) => rules.isCheckableBmpGlyph(ch)),
  planWithOtherScripts: rules.fontLoadPlan(
    [{ text: "Привет مرحبا 안녕하세요 สวัสดี Hello" }],
    [{ items: [{ text: "Total Revenue $500" }] }],
  )[0].text,
  rows: {
    englishMulti: rules.splitCardRow("Total Revenue $500"),
    englishThree: rules.splitCardRow("Monthly Active Users 12,400"),
    chineseUnit: rules.splitCardRow("本月 订单 128"),
    chineseTwo: rules.splitCardRow("主号 2"),
    single: rules.splitCardRow("Summary"),
  },
};
console.log(JSON.stringify(out));
"""
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["bottomLandscape"], 9)
        self.assertEqual(data["bottomPortrait"], 24)
        self.assertAlmostEqual(data["cardLandscape"], 1080 * 0.72)
        self.assertAlmostEqual(data["cardPortrait"], 1080 * 0.8)
        self.assertAlmostEqual(data["sysLandscape"], 1080 * 0.72)
        self.assertAlmostEqual(data["taskLandscape"], 1080 * 0.76)
        self.assertEqual(data["otherScripts"], [False, False, False, False])
        self.assertEqual(data["cjkAscii"], [True, True, True, True, True])
        for ch in ("П", "م", "안", "ส"):
            self.assertNotIn(ch, data["planWithOtherScripts"])
        self.assertIn("H", data["planWithOtherScripts"])
        self.assertEqual(
            data["rows"]["englishMulti"], {"name": "Total Revenue", "unit": "", "value": "$500"}
        )
        self.assertEqual(
            data["rows"]["englishThree"],
            {"name": "Monthly Active Users", "unit": "", "value": "12,400"},
        )
        self.assertEqual(
            data["rows"]["chineseUnit"], {"name": "本月", "unit": "订单", "value": "128"}
        )
        self.assertEqual(
            data["rows"]["chineseTwo"], {"name": "主号", "unit": "", "value": "2"}
        )
        self.assertEqual(
            data["rows"]["single"], {"name": "Summary", "unit": "", "value": ""}
        )


if __name__ == "__main__":
    unittest.main()
