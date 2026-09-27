import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL = Path(__file__).resolve().parents[1] / "skills/short-drama-edit"
SPEC = importlib.util.spec_from_file_location("edit_screen_text", SKILL / "scripts/edit_tool.py")
assert SPEC and SPEC.loader
edit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edit)
RULES = SKILL / "assets/remotion/src/rules.mjs"

SCREENPLAY = """# EP001

## EP001-SC001 内 · 办公室 · 日

[画面文字] 微博 2　破站 1　短视频 0

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
                "- 画面文字 1：0.00-1.40 卡片 微博 2｜破站 1",
                "- 画面文字 2：1.50-3.00 任务面板 军宣新星｜5 天内粉丝破 1,000,000（倒计时：431998）",
                "- 画面文字 3：1.50-3.00 角标 剩余（倒计时：接续）",
            ]])
            texts = project.parse()[0].screen_texts
            self.assertEqual([t.style for t in texts], ["卡片", "任务面板", "角标"])
            self.assertEqual(texts[0].items, ("微博 2", "破站 1"))
            self.assertEqual((texts[1].countdown, texts[1].resume), (431998.0, False))
            self.assertEqual((texts[2].countdown, texts[2].resume), (None, True))
            self.assertEqual(project.findings(), [])

    def test_malformed_lines_are_refused_at_parse(self):
        refused = {
            "same slot overlaps": [
                "- 画面文字 1：0.00-2.00 卡片 微博 2",
                "- 画面文字 2：1.50-3.00 系统面板 军宣新星",
            ],
            "countdown on a card": ["- 画面文字：0.00-2.00 卡片 微博 2（倒计时：60）"],
            "unknown style": ["- 画面文字：0.00-2.00 弹幕 微博 2"],
            "empty item": ["- 画面文字：0.00-2.00 卡片 微博 2｜｜破站 1"],
            "numbering gap": [
                "- 画面文字 1：0.00-1.00 卡片 微博 2",
                "- 画面文字 3：1.00-2.00 卡片 破站 1",
            ],
            "plain and numbered": [
                "- 画面文字：0.00-1.00 卡片 微博 2",
                "- 画面文字 1：1.00-2.00 卡片 破站 1",
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[]])
            for name, lines in refused.items():
                with self.subTest(name):
                    project.write([lines])
                    with self.assertRaises(edit.EditError):
                        project.parse()

    def test_a_panel_and_the_corner_chip_may_share_a_moment(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 画面文字 1：0.00-2.00 任务面板 军宣新星（倒计时：60）",
                "- 画面文字 2：0.50-3.00 角标 剩余（倒计时：接续）",
            ]])
            self.assertEqual(len(project.parse()[0].screen_texts), 2)

    def test_check_reports_range_trace_and_orphan_countdown(self):
        cases = {
            "past the cut": "- 画面文字：1.00-3.50 卡片 微博 2",
            "reversed": "- 画面文字：2.00-1.00 卡片 微博 2",
            # Dialogue is in the screenplay, but not on a [画面文字] line.
            "dialogue, not screen text": "- 画面文字：0.00-1.00 卡片 粉丝加起来",
            "invented": "- 画面文字：0.00-1.00 卡片 微博 200",
            "resume with nothing before": "- 画面文字：0.00-1.00 角标 剩余（倒计时：接续）",
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[]])
            for name, line in cases.items():
                with self.subTest(name):
                    project.write([[line]])
                    self.assertEqual(len(project.findings()), 1, project.findings())
            project.write([["- 画面文字：0.00-1.00 卡片 微博 2｜破站 1"]])
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


class ScreenTextPlacementTests(unittest.TestCase):
    def blocks(self):
        return [
            ["- 画面文字：0.50-2.50 卡片 微博 2｜破站 1"],
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
            project.write([["- 画面文字：0.00-2.00 卡片 微博 2（传说）"]])
            with self.assertRaises(edit.EditError):
                project.parse()

    def test_missing_remotion_fails_with_the_install_command(self):
        layer = {"start": 0.0, "end": 1.0, "style": "card",
                 "items": [{"text": "微博 2", "rarity": None}], "countdown": None}
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
                self.assertIn(f"cd {workspace.resolve()} && npm install", str(raised.exception))
                self.assertIn("@fontsource/noto-sans-sc", str(raised.exception))
            self.assertFalse((Path(directory) / "叠层.webm").exists())

    def test_ffmpeg_subtitles_are_burned_over_the_remotion_screen_text(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Project(Path(directory), [[
                "- 字幕 1：0.20-1.40 十几个号，粉丝加起来，没号多。",
                "- 字幕 2：1.50-2.90 发布任务，军宣新星。（重点：军宣新星）",
                "- 画面文字：0.00-1.40 卡片 微博 2",
            ]])
            cuts = project.parse()
            commands = []
            overlay_calls = []

            def fake_overlay(output_root, cues, layers, *args, **kwargs):
                overlay_calls.append((list(cues), list(layers)))
                return output_root / "叠层.webm"

            with patch.object(edit, "_require", return_value="ffmpeg"), \
                    patch.object(edit, "_run", side_effect=commands.append), \
                    patch.object(edit, "probe_duration", return_value=3.0), \
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
                ["- 画面文字：0.50-1.00 卡片 微博 2", "- 音效：0.50-1.00 media/1.mp4"],
            ])
            cuts = project.parse()
        self.assertEqual(
            edit._placements_for_sampling(cuts, None)["画面文字落点"],
            "未测（分段缺失，无法换算成片时间）",
        )
        placed = edit._placements_for_sampling(cuts, [3.1, 3.0])
        self.assertEqual([(p["起"], p["止"]) for p in placed["画面文字落点"]], [(0.0, 3.1), (3.6, 4.1)])
        self.assertEqual([(p["起"], p["止"]) for p in placed["音效落点"]], [(3.6, 4.1)])


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
            project.write([["- 字幕：五天，一百万？（重点：一千万）"]])
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

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
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
                "ffmpeg", film, [(1.5, 0.6, chime, -6.0)], mixed), check=True)

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


if __name__ == "__main__":
    unittest.main()
