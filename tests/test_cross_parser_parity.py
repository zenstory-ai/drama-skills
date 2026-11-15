"""Cross-script Markdown parser parity and cross-skill rule tier parity tests.

Exercises all seven creator-Markdown scripts against a single episode carrying
HTML comments outside code fences, emphasized bullet field keys, trailing and
interleaved non-entry ``## `` headings, compact/``内外`` scene headings, clock
action prefixes, multi-word Latin ``[VO]`` speakers, unitless shot durations,
and quoted scene IDs inside ``来源``. Also verifies that every rule ID and tier
referenced across skills resolves consistently to ``stage-contract.md``.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]


def _load_script(module_name: str, relative_path: str) -> Any:
    path = SUITE / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


creator_check = _load_script(
    "parity_creator_markdown_check",
    "skills/short-drama/scripts/creator_markdown_check.py",
)
creator_views = _load_script(
    "parity_creator_views",
    "skills/short-drama/scripts/creator_views.py",
)
screenplay_index = _load_script(
    "parity_screenplay_index",
    "skills/short-drama-write/scripts/screenplay_index.py",
)
duration_estimate = _load_script(
    "parity_duration_estimate",
    "skills/short-drama-write/scripts/duration_estimate.py",
)
breakdown_tool = _load_script(
    "parity_breakdown_tool",
    "skills/short-drama-breakdown/scripts/breakdown_tool.py",
)
production_tool = _load_script(
    "parity_production_tool",
    "skills/short-drama-produce/scripts/production_tool.py",
)
edit_tool = _load_script(
    "parity_edit_tool",
    "skills/short-drama-edit/scripts/edit_tool.py",
)


SCREENPLAY_MD = """\
# EP001 · 夜班读数

<!--
## EP001-SC999 内 · 假场次 · 夜
幽灵：这段注释里的假场次与假台词绝不能进入任何解析器。
-->

人物：许棠、Dr. Lin

## EP001-SC001 内·监控室·夜

12:00，操作台指示灯忽然熄灭。

许棠：是谁关了电闸？

##  EP001-SC002 内外 · 走廊 · 夜

冷白应急灯照亮半开放连廊，雨水打在北端玻璃防火门外。

[VO] Dr. Lin (low voice)：记录第二次读数。

## EP001-SC003 外·天台·夜

狂风吹动天台铁门。
"""

SETTINGS_MD = """\
# EP001 视觉设定

- **制作形态**：写实竖屏短剧，9:16。
- **时代背景**：当下（2020 年代）；设备：液晶监视器；制服：深灰工装夹克；照明：冷白应急灯。

<!--
## 人物 · 幽灵
- 外观特征：绝不该被解析出来的注释人物。
-->

## 人物 · 许棠

- 26 岁东亚女性，行事干脆。
- **外观特征**：齐耳短黑发、深灰工装夹克。
- **提示词名称**：Xutang
- **角色声线**：冷清女中音；不允许娇嗔气声
- **连戏锁**：LOCK-XUTANG-JACKET《许棠深灰工装》（镜头：SHOT-EP001-001；图片提示词项：IMG-XUTANG-SHEET）· 锁定词：charcoal utility jacket

## 人物 · Dr. Lin

- 42 岁男性研究员（本集仅画外音）。
- **外观特征**：银边眼镜、白大褂。
- **提示词名称**：无
* *角色声线*: 沉稳低男中音；不允许激昂喊叫

## 地点 · 监控室

- 紧凑监控隔间，一排液晶监视器。
- **外观特征**：黑色操作台、液晶监视器阵列、冷蓝余光。

## 地点 · 走廊

- 半开放连廊，一侧通向室外雨夜。
- **外观特征**：水泥墙面、头顶冷白应急灯、玻璃防火门。

## 备注

- **外观特征**：本段属于自由备注章节，不应并入「走廊」设定条目。
"""

IMAGE_PROMPTS_MD = """\
# EP001 图片提示词

<!--
## IMG-DECOY · 假设定板
- 参考：REF-BROKEN
-->

## IMG-XUTANG-SHEET · 许棠角色板

- **用途**：固定许棠五官脸型与深灰工装夹克。
- **参考**：无外部参考；三视图保持同一脸型与服装细节。

### 可复制提示词
> 9:16 character turnaround sheet of Xutang, a 26-year-old East Asian woman with chin-length short black hair wearing a charcoal utility jacket, front and side views on neutral grey backdrop, no text.

## 导出说明

> 本段导出说明属于独立二级标题，不应拼入 IMG-XUTANG-SHEET 的可复制提示词。
"""

STORYBOARD_MD = """\
# EP001 分镜

- **未拍场次**：EP001-SC003（理由：顺延至下集冷开场）

<!--
## SHOT-EP001-999 · 假镜头
- 时长：99s
-->

## 场景站位 · EP001-SC001 · 监控室

- **方位约定**：黑色操作台在北侧，隔间门在南侧。
- **人物落位**：许棠站操作台前朝北。

## SHOT-EP001-001 · 电闸熄灭

- **来源**：EP001-SC001「12:00，操作台指示灯忽然熄灭。许棠：是谁关了电闸？屏幕闪过 EP001-SC003」
- **时长**：4
- **景别**：近景
- **运镜**：固定
- **出场设定**：《视觉设定.md》·人物「许棠」（控制：外貌、服装）；《视觉设定.md》·地点「监控室」（控制：空间布局、光线）
- **输入参考图**：无（文生首帧）。
- **画面与动作**：操作台指示灯骤灭，许棠抬头追问“是谁关了电闸？”。

### 首帧提示词
> 9:16 medium close-up of Xutang in a charcoal utility jacket standing before a black control console with dark LCD monitors in a compact control room, cold blue residual glow on her face, no text.

## 场景站位 · EP001-SC002 · 走廊

- **方位约定**：连廊南北向延伸，玻璃防火门在北端。
- **人物落位**：空镜无人物入画。

## SHOT-EP001-002 · 走廊读数

- **来源**：EP001-SC002「[VO] Dr. Lin (low voice)：记录第二次读数。」
- **时长**：3
- **景别**：中景
- **运镜**：缓慢前推
- **出场设定**：《视觉设定.md》·地点「走廊」（控制：空间布局、应急灯光）
- **输入参考图**：无（文生首帧）。
- **画面与动作**：冷白应急灯照亮空荡连廊，画外传来 Dr. Lin 的记录声。

### 首帧提示词
> 9:16 medium shot down a semi-open concrete corridor lit by cold-white overhead emergency light toward a glass fire door against rain outside, no people, no text.
"""

VIDEO_PROMPTS_MD = """\
# EP001 视频提示词

<!--
## MOTION-EP001-999 · 假动态
- 分镜：SHOT-EP001-999
- 时长：99
-->

## MOTION-EP001-001 · 电闸熄灭

- **分镜**：SHOT-EP001-001
- **时长**：4
- **生成方式**：文生视频
- **输入参考图**：无（文生视频）。
- **开场画面**：Xutang in a charcoal utility jacket stands before a black control console with LCD monitors in a dark control room.
- **起始帧**：指示灯刚灭，许棠扶住黑色操作台。
- **动作过程**：指示灯熄灭 → 许棠猛抬头环顾并低声发问
- **终点**：许棠目光停在门边暗处。

### 可复制提示词
> Xutang in a charcoal utility jacket stands before a black control console with LCD monitors in a dark control room. Indicator lights go dark; she looks up sharply and asks in Chinese, “是谁关了电闸？”. Static camera. No subtitles, no text.

## MOTION-EP001-002 · 走廊读数

<!--
## MOTION-EP001-002 · 旧版草稿
- 输入参考图：REF-BROKEN
-->
- **分镜**：SHOT-EP001-002
- **时长**：3
- **生成方式**：文生视频
* *输入参考图*: 无（文生视频）。
- **开场画面**：Empty semi-open concrete corridor lit by cold-white overhead emergency light with a glass fire door ahead.
- **起始帧**：冷白应急灯亮着，半开放连廊空无一人。
- **动作过程**：镜头沿走廊缓慢前推 → 画外男声沉稳播报读数
- **终点**：镜头逼近北端玻璃防火门。

### 可复制提示词
> Empty semi-open concrete corridor lit by cold-white overhead emergency light with a glass fire door ahead. Slow push-in along the corridor while an off-screen calm male voice-over says in Chinese, “记录第二次读数。”. No subtitles, no text.

## 生产批次备注

> 本段批次备注属于独立二级标题，不应拼入 MOTION-EP001-002 的可复制提示词。
"""

CUT_LIST_MD = """\
# EP001 剪辑单

- **成片目标时长**：7.00 秒
- **交付响度**：-14 LUFS
- **画幅与帧率**：1080×1920 30fps
- **颗粒**：2
- **接镜匹配**：开

<!--
## CUT-EP001-999 · 假剪辑段
- 来源：MOTION-EP001-999 · 剧集/EP001/制作成果/ghost.mp4
- 入点：0.00
- 出点：99.00
- 时长：99.00
-->

## CUT-EP001-001 · 电闸熄灭

- **来源**：MOTION-EP001-001 · 剧集/EP001/制作成果/shot-001.mp4
- **入点**：0.00
- **出点**：4.00
- **时长**：4.00
- **字幕**：是谁关了电闸？

## CUT-EP001-002 · 走廊读数

- **来源**：MOTION-EP001-002 · 剧集/EP001/制作成果/shot-002.mp4
- **入点**：0.00
- **出点**：3.00
- **时长**：3.00
- **字幕**：记录第二次读数。

## 导出备注

- **时长**：999.00
"""

REVIEW_MD = """\
# EP001 审查报告

- **结论**：PROVISIONAL
- **范围**：分镜与提示词联审

<!--
## blocker · REV-EP001-999 · 假阻断项
- 修改要求：注释里的假条目不应进入审查结果
-->

## major · REV-EP001-001 · 走廊尾帧光比待实拍复核

- **规则**：SHT-10
- **位置**：分镜.md · SHOT-EP001-002
- **证据**：前推终点靠近玻璃防火门时需确认雨夜反光不遮挡门框细节。
- **修改要求**：补齐走廊尾帧光比核验

## 被删的强钩子

- 原稿集尾天台铁门硬断（EP001-SC003）已顺延至 EP002 冷开场。
"""


class CrossScriptMarkdownParserParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.project = Path(self._tmpdir.name)
        (self.project / "short-drama.json").write_text(
            json.dumps(
                {
                    "schema_version": "2.0",
                    "project_id": "parity-demo",
                    "title": "夜班读数",
                    "format": {"target_seconds_per_episode": 60},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.episode = self.project / "剧集/EP001"
        self.episode.mkdir(parents=True)
        (self.episode / "剧本.md").write_text(SCREENPLAY_MD, encoding="utf-8")
        (self.episode / "视觉设定.md").write_text(SETTINGS_MD, encoding="utf-8")
        (self.episode / "图片提示词.md").write_text(IMAGE_PROMPTS_MD, encoding="utf-8")
        (self.episode / "分镜.md").write_text(STORYBOARD_MD, encoding="utf-8")
        (self.episode / "视频提示词.md").write_text(VIDEO_PROMPTS_MD, encoding="utf-8")
        (self.episode / "剪辑单.md").write_text(CUT_LIST_MD, encoding="utf-8")
        media_dir = self.episode / "制作成果"
        media_dir.mkdir()
        (media_dir / "shot-001.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        (media_dir / "shot-002.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        review_dir = self.project / "审查"
        review_dir.mkdir()
        (review_dir / "EP001-审查.md").write_text(REVIEW_MD, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_all_seven_scripts_agree_on_shared_episode_markdown(self) -> None:
        # 1. Core creator-document validator accepts the episode with zero false positives.
        errors = creator_check.validate_episode(self.episode, self.project)
        self.assertEqual(errors, [])

        # 2. Screenplay scenes, speakers, clock action lines, and HTML comments align.
        spoken_lines = creator_check._screenplay_dialogue(SCREENPLAY_MD)
        check_speakers = [(line.scene, line.speaker) for line in spoken_lines]
        self.assertEqual(
            check_speakers,
            [("EP001-SC001", "许棠"), ("EP001-SC002", "Dr. Lin")],
        )

        view_sp = creator_views.parse_screenplay(SCREENPLAY_MD)
        view_scene_ids = [scene["id"] for scene in view_sp["scenes"]]
        self.assertEqual(
            view_scene_ids,
            ["EP001-SC001", "EP001-SC002", "EP001-SC003"],
        )
        self.assertEqual(view_sp["scenes"][1]["space"], "内外")
        view_dialogue = [
            (block["who"], block.get("tag") or "on_camera")
            for scene in view_sp["scenes"]
            for block in scene["blocks"]
            if block["k"] == "line"
        ]
        self.assertEqual(
            view_dialogue,
            [("许棠", "on_camera"), ("Dr. Lin", "VO")],
        )

        index_path = self.project / "剧集/EP001/screenplay-index.jsonl"
        sp_summary = screenplay_index.build_index(
            self.episode / "剧本.md",
            index_path,
            speakers=["许棠", "Dr. Lin"],
            no_previous=True,
        )
        self.assertEqual(sp_summary["source_issue_count"], 0)
        self.assertEqual(sp_summary["review_status"], "clean")
        index_rows = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        index_scene_ids = [
            row["scene_id"]
            for row in index_rows
            if row.get("record_type") == "block" and row.get("kind") == "scene_heading"
        ]
        index_speakers = [
            (row["speaker"], row.get("tag") or "on_camera")
            for row in index_rows
            if row.get("record_type") == "block" and row.get("speaker")
        ]
        self.assertEqual(index_scene_ids, view_scene_ids)
        self.assertEqual(index_speakers, [("许棠", "on_camera"), ("Dr. Lin", "VO")])

        de_blocks, de_meta = duration_estimate.parse_script_blocks(
            SCREENPLAY_MD.encode("utf-8")
        )
        self.assertEqual(de_meta["review_status"], "clean")
        self.assertEqual(de_meta["source_issue_count"], 0)
        de_scene_ids = [
            block["scene_id"] for block in de_blocks if block["kind"] == "scene_heading"
        ]
        de_speakers = [
            (block["speaker"], block.get("tag") or "on_camera")
            for block in de_blocks
            if block.get("speaker")
        ]
        self.assertEqual(de_scene_ids, view_scene_ids)
        self.assertEqual(de_speakers, [("许棠", "on_camera"), ("Dr. Lin", "VO")])

        bt_speakers = breakdown_tool.screenplay_speakers(SCREENPLAY_MD)
        self.assertEqual(bt_speakers, {"许棠", "Dr. Lin"})
        bt_plan = breakdown_tool.plan_episode(self.episode)
        self.assertEqual(bt_plan["shot_seconds"], [4.0, 3.0])
        self.assertAlmostEqual(bt_plan["duration"], 7.0)

        # 3. Settings, interleaved scene blocking, unitless shot durations, and trailing ## cutoff align.
        view_settings = creator_views.parse_settings(SETTINGS_MD)
        setting_names = [(item["cat"], item["name"]) for item in view_settings["items"]]
        self.assertEqual(
            setting_names,
            [
                ("人物", "许棠"),
                ("人物", "Dr. Lin"),
                ("地点", "监控室"),
                ("地点", "走廊"),
            ],
        )
        corridor = next(
            item for item in view_settings["items"] if item["name"] == "走廊"
        )
        self.assertNotIn("自由备注章节", json.dumps(corridor, ensure_ascii=False))
        xutang = next(
            item for item in view_settings["items"] if item["name"] == "许棠"
        )
        self.assertEqual(xutang["designators"], ["Xutang"])
        self.assertEqual(len(xutang["locks"]), 1)
        self.assertEqual(xutang["locks"][0]["id"], "LOCK-XUTANG-JACKET")

        blockings = creator_views.parse_scene_blocking(STORYBOARD_MD)
        self.assertEqual(
            [item["scene"] for item in blockings],
            ["EP001-SC001", "EP001-SC002"],
        )
        view_sb = creator_views.parse_storyboard(STORYBOARD_MD)
        self.assertEqual(
            [(shot["id"], shot["sec"]) for shot in view_sb["shots"]],
            [("SHOT-EP001-001", 4.0), ("SHOT-EP001-002", 3.0)],
        )

        # 4. Prompt copyable blocks exclude trailing non-entry ## sections in both views and production_tool.
        img_prompt, img_bindings = production_tool._extract_markdown_source_defaults(
            self.project,
            source="剧集/EP001/图片提示词.md",
            source_entry="IMG-XUTANG-SHEET",
        )
        self.assertEqual(img_bindings, [])
        self.assertIn("charcoal utility jacket", img_prompt)
        self.assertNotIn("导出说明", img_prompt)

        vid_prompt, vid_bindings = production_tool._extract_markdown_source_defaults(
            self.project,
            source="剧集/EP001/视频提示词.md",
            source_entry="MOTION-EP001-002",
        )
        self.assertEqual(vid_bindings, [])
        self.assertIn("记录第二次读数", vid_prompt)
        self.assertNotIn("批次备注", vid_prompt)

        view_imgs = creator_views.parse_image_prompts(IMAGE_PROMPTS_MD)
        self.assertEqual([item["id"] for item in view_imgs], ["IMG-XUTANG-SHEET"])
        self.assertEqual(view_imgs[0]["prompt"], img_prompt)

        view_vids = creator_views.parse_video_prompts(VIDEO_PROMPTS_MD)
        self.assertEqual(
            [item["id"] for item in view_vids],
            ["MOTION-EP001-001", "MOTION-EP001-002"],
        )
        self.assertEqual(view_vids[1]["prompt"], vid_prompt)

        # 5. Cut list and quote-stripped scene coverage align between edit_tool and creator_views.
        delivery, cuts, unused = edit_tool.parse_cut_list(self.episode / "剪辑单.md")
        self.assertEqual([cut.cut_id for cut in cuts], ["CUT-EP001-001", "CUT-EP001-002"])
        self.assertAlmostEqual(delivery.target_seconds or 0.0, 7.0)
        self.assertAlmostEqual(delivery.grain or 0.0, 2.0)
        self.assertTrue(delivery.shot_match)
        cut_findings = edit_tool.check_cuts(
            self.episode,
            cuts,
            self.project,
            probe=False,
            unused=unused,
            delivery=delivery,
        )
        self.assertEqual(cut_findings, [])

        view_cuts = creator_views.parse_cut_list(
            CUT_LIST_MD,
            {"MOTION-EP001-001": "SHOT-EP001-001", "MOTION-EP001-002": "SHOT-EP001-002"},
        )
        self.assertEqual(
            [item["id"] for item in view_cuts["cuts"]],
            ["CUT-EP001-001", "CUT-EP001-002"],
        )
        self.assertEqual(view_cuts["grain"], 2.0)
        self.assertTrue(view_cuts["shot_match"])

        # 6. Review verdict PROVISIONAL, 修改要求, HTML comment stripping, and 被删的强钩子 align.
        view_rev = creator_views.parse_review(REVIEW_MD)
        self.assertEqual(view_rev["verdict"], "待补材料复核")
        self.assertEqual(view_rev["verdictTone"], "warn")
        self.assertEqual(
            [item["id"] for item in view_rev["findings"]],
            ["REV-EP001-001"],
        )
        self.assertEqual(view_rev["findings"][0]["fix"], "补齐走廊尾帧光比核验")
        self.assertEqual(len(view_rev["deleted_hooks"]), 1)
        self.assertIn("EP001-SC003", view_rev["deleted_hooks"][0])

    def test_fenced_html_comments_stay_intact_across_comment_strippers(self) -> None:
        sample = (
            "# 标题\n"
            "<!--\n"
            "## SHOT-EP001-999 · 注释镜头\n"
            "-->\n"
            "```markdown\n"
            "<!-- 代码围栏内的注释必须原样保留 -->\n"
            "```\n"
            "~~~\n"
            "<!-- 波浪线围栏内的注释也必须原样保留 -->\n"
            "~~~\n"
            "正文行<!-- 行内注释 -->结尾\n"
        )
        for name, stripper in (
            ("creator_markdown_check", creator_check._strip_html_comments),
            ("breakdown_tool", breakdown_tool._strip_html_comments),
            ("production_tool", production_tool._strip_html_comments),
            ("edit_tool", edit_tool._strip_html_comments),
        ):
            with self.subTest(script=name):
                cleaned = stripper(sample)
                self.assertEqual(cleaned.count("\n"), sample.count("\n"))
                self.assertNotIn("SHOT-EP001-999", cleaned)
                self.assertNotIn("行内注释", cleaned)
                self.assertIn("<!-- 代码围栏内的注释必须原样保留 -->", cleaned)
                self.assertIn("<!-- 波浪线围栏内的注释也必须原样保留 -->", cleaned)
                self.assertIn("正文行结尾", cleaned)

    def test_crlf_bom_cast_opus_group_and_inline_backtick_parity(self) -> None:
        # 1. Inline backtick `<!--` never swallows subsequent sections across all 4 strippers.
        backtick_sample = (
            "# 标题\r\n"
            "说明：请勿手写裸 `<!--` 起始符。\r\n"
            "## SHOT-EP001-001 · 真镜头\r\n"
            "- 时长：4s（含半拍停顿）\r\n"
        )
        for name, stripper in (
            ("creator_markdown_check", creator_check._strip_html_comments),
            ("breakdown_tool", breakdown_tool._strip_html_comments),
            ("production_tool", production_tool._strip_html_comments),
            ("edit_tool", edit_tool._strip_html_comments),
        ):
            with self.subTest(script=name):
                cleaned = stripper(backtick_sample)
                self.assertIn("SHOT-EP001-001", cleaned)
                self.assertIn("时长：4s", cleaned)

        # 2. End-to-end CRLF + UTF-8 BOM + scene-head cast + known ASCII-colon speaker
        #    + curly quotes in 来源 + .opus voice ref + GROUP-* across all 7 scripts.
        voice_dir = self.project / "输入/声音"
        voice_dir.mkdir(parents=True)
        opus_bytes = (
            b"OggS\x00\x02"
            + b"\x00" * 20
            + b"\x01\x13OpusHead\x01\x02\x38\x01\x80\xbb\x00\x00\x00\x00\x00"
        )
        (voice_dir / "xutang.opus").write_bytes(opus_bytes)
        (self.episode / "制作成果/group-01.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")

        def to_bom_crlf(text: str) -> bytes:
            return ("\ufeff" + text.replace("\r\n", "\n").replace("\n", "\r\n")).encode("utf-8")

        screenplay_r4 = (
            "# EP001·夜班读数<!-- 场记尾注 -->\n\n"
            "## EP001-SC001 内 · 监控室 · 夜\n"
            "人物：许棠（女主、值班员）、Dr. Lin（顾问/研究员）。\n"
            "许棠：是谁关了电闸？\n\n"
            "Dr. Lin: Hold the line.\n\n"
            "## EP001-SC002 外 · 天台 · 夜\n\n"
            "狂风吹动天台铁门。\n"
        )
        settings_r4 = (
            "# EP001 视觉设定\n\n"
            "- **制作形态**：写实竖屏短剧，9:16。\n"
            "- **时代背景**：当下（2020 年代）；设备：液晶监视器；制服：深灰工装夹克；照明：冷白应急灯。\n\n"
            "## 人物 · 许棠\n\n"
            "- **外观特征**：齐耳短黑发、深灰工装夹克。\n"
            "- **提示词名称**：Xutang\n"
            "- **角色声线**：冷清女中音；不允许娇嗔气声\n"
            "- **声音参考**：输入/声音/xutang.opus（用途：音色；控制：音色、音区；不得控制：情绪、录音混响；状态：创作者已说明）\n"
            "- **连戏锁**：LOCK-XUTANG-JACKET《许棠深灰工装》（镜头：入画；图片提示词项：IMG-XUTANG-SHEET）· 锁定词：charcoal utility jacket\n\n"
            "## 人物 · Dr. Lin\n\n"
            "- **外观特征**：银边眼镜、白大褂。\n"
            "- **提示词名称**：Dr. Lin\n"
            "- **角色声线**：沉稳低男中音；不允许激昂喊叫\n\n"
            "## 地点 · 监控室\n\n"
            "- **外观特征**：黑色操作台、液晶监视器阵列、冷蓝余光。\n"
        )
        storyboard_r4 = (
            "# EP001 分镜\n\n"
            "- **未拍场次**：EP001-SC002（理由：顺延至下集冷开场）\n\n"
            "## SHOT-EP001-001 · 电闸熄灭\n\n"
            "- **来源**：EP001-SC001 “许棠：是谁关了电闸？屏幕闪过 EP001-SC002”\n"
            "- **时长**：4s（含半拍停顿）\n"
            "- **景别**：近景\n"
            "- **运镜**：固定\n"
            "- **出场设定**：《视觉设定.md》·人物「许棠」（控制：外貌、服装）；《视觉设定.md》·地点「监控室」（控制：空间布局）\n"
            "- **输入参考图**：无（文生首帧）。\n"
            "- **画面与动作**：许棠抬头追问是谁关了电闸。\n\n"
            "### 首帧提示词\n"
            "> 9:16 medium close-up of Xutang in a charcoal utility jacket before dark LCD monitors in a compact control room, no text.\n\n"
            "## SHOT-EP001-002 · 顾问回应\n\n"
            "- **来源**：EP001-SC001 “Dr. Lin: Hold the line.”\n"
            "- **时长**：3s\n"
            "- **景别**：近景\n"
            "- **运镜**：缓慢前推\n"
            "- **出场设定**：《视觉设定.md》·人物「Dr. Lin」（控制：外貌）；《视觉设定.md》·地点「监控室」（控制：空间布局）\n"
            "- **输入参考图**：无（文生首帧）。\n"
            "- **画面与动作**：Dr. Lin 沉声回应稳住阵脚。\n\n"
            "### 首帧提示词\n"
            "> 9:16 medium close-up of Dr. Lin in silver-rimmed glasses and a white lab coat inside the dark control room, no text.\n"
        )
        video_r4 = (
            "# EP001 视频提示词\n\n"
            "## MOTION-EP001-001 · 电闸熄灭\n\n"
            "- **分镜**：SHOT-EP001-001\n"
            "- **时长**：4\n"
            "- **生成方式**：文生视频\n"
            "- **输入参考图**：无（文生视频）。\n"
            "- **参考音频**：REF-VOICE-XT（顺序：1）· 输入/声音/xutang.opus《许棠音色》（用途：音色；角色：许棠；控制：音色、音区；不得控制：情绪、混响）\n"
            "- **开场画面**：Xutang in a charcoal utility jacket stands before dark LCD monitors.\n"
            "- **起始帧**：指示灯熄灭瞬间。\n"
            "- **动作过程**：许棠抬头追问\n"
            "- **终点**：许棠盯住门口。\n\n"
            "### 可复制提示词\n"
            "> Xutang in a charcoal utility jacket stands before dark LCD monitors in the control room and asks in Chinese, “是谁关了电闸？”. Static camera, no text.\n\n"
            "## MOTION-EP001-002 · 顾问回应\n\n"
            "- **分镜**：SHOT-EP001-002\n"
            "- **时长**：3\n"
            "- **生成方式**：文生视频\n"
            "- **输入参考图**：无（文生视频）。\n"
            "- **开场画面**：Dr. Lin in silver-rimmed glasses stands beside the console.\n"
            "- **起始帧**：Dr. Lin 抬手示意。\n"
            "- **动作过程**：沉声开口回应\n"
            "- **终点**：目光落在屏幕。\n\n"
            "### 可复制提示词\n"
            "> Dr. Lin in silver-rimmed glasses and a white lab coat stands in the dark control room and says in English, “Hold the line.”. Slow push-in, no text.\n\n"
            "## GROUP-EP001-01 · 监控室问答连拍\n\n"
            "- **成员**：MOTION-EP001-001、MOTION-EP001-002\n"
            "- **时长**：7s\n"
            "- **参考音频**：REF-VOICE-XT（顺序：1）· 输入/声音/xutang.opus《许棠音色》（用途：音色；角色：许棠；控制：音色、音区；不得控制：情绪、混响）\n"
            "- **理由**：同场紧邻对白一气呵成。\n\n"
            "### 可复制提示词\n"
            "> Shot 1 (0-4s): Xutang in a charcoal utility jacket before dark LCD monitors asks in Chinese, “是谁关了电闸？”. Shot 2 (4-7s): Cut to Dr. Lin in silver-rimmed glasses in the same control room saying in English, “Hold the line.”. No text.\n"
        )
        cuts_r4 = (
            "# EP001 剪辑单\n\n"
            "- **成片目标时长**：7.00 秒\n"
            "- **交付响度**：-14 LUFS\n"
            "- **画幅与帧率**：1080×1920 30fps\n\n"
            "## CUT-EP001-001 · 监控室问答连拍\n\n"
            "- **来源**：GROUP-EP001-01 · 剧集/EP001/制作成果/group-01.mp4\n"
            "- **入点**：0.00\n"
            "- **出点**：7.00\n"
            "- **时长**：7.00\n"
            "- **字幕 1**：0.20-3.50 是谁关了电闸？\n"
            "- **字幕 2**：4.10-6.80 Hold the line.\n"
        )

        (self.episode / "剧本.md").write_bytes(to_bom_crlf(screenplay_r4))
        (self.episode / "视觉设定.md").write_bytes(to_bom_crlf(settings_r4))
        (self.episode / "图片提示词.md").write_bytes(to_bom_crlf(IMAGE_PROMPTS_MD))
        (self.episode / "分镜.md").write_bytes(to_bom_crlf(storyboard_r4))
        (self.episode / "视频提示词.md").write_bytes(to_bom_crlf(video_r4))
        (self.episode / "剪辑单.md").write_bytes(to_bom_crlf(cuts_r4))

        self.assertEqual(creator_check.validate_episode(self.episode, self.project), [])

        docs_map = {
            name: (self.episode / name).read_text(encoding="utf-8")
            for name in (
                "剧本.md",
                "视觉设定.md",
                "分镜.md",
                "图片提示词.md",
                "视频提示词.md",
                "剪辑单.md",
            )
        }
        ep_view = creator_views.read_episode("EP001", docs_map, None)
        self.assertEqual(ep_view["problems"], [])
        self.assertEqual(
            [b["who"] for b in ep_view["script"]["scenes"][0]["blocks"] if b["k"] == "line"],
            ["许棠", "Dr. Lin"],
        )
        self.assertEqual([g["id"] for g in ep_view["videoGroups"]], ["GROUP-EP001-01"])
        self.assertEqual(ep_view["cutlist"]["cuts"][0]["motion"], "GROUP-EP001-01")
        self.assertEqual(ep_view["cutlist"]["cuts"][0]["shot"], "SHOT-EP001-001")
        self.assertEqual(
            ep_view["cutlist"]["cuts"][0]["group_shots"],
            ["SHOT-EP001-001", "SHOT-EP001-002"],
        )

        idx_out = self.episode / "r4-index.jsonl"
        sp_meta = screenplay_index.build_index(
            self.episode / "剧本.md",
            idx_out,
            no_previous=True,
        )
        self.assertEqual(sp_meta["review_status"], "clean")

        de_blocks, de_meta = duration_estimate.parse_script_blocks(
            (self.episode / "剧本.md").read_bytes()
        )
        self.assertEqual(de_meta["review_status"], "clean")
        self.assertEqual(
            [b["speaker"] for b in de_blocks if b.get("speaker")],
            ["许棠", "Dr. Lin"],
        )

        self.assertEqual(
            breakdown_tool.screenplay_speakers(
                (self.episode / "剧本.md").read_text(encoding="utf-8")
            ),
            {"许棠", "Dr. Lin"},
        )
        self.assertEqual(breakdown_tool.plan_episode(self.episode)["shot_seconds"], [4.0, 3.0])

        grp_prompt, grp_bindings = production_tool._extract_markdown_source_defaults(
            self.project,
            source="剧集/EP001/视频提示词.md",
            source_entry="GROUP-EP001-01",
        )
        self.assertIn("Hold the line.", grp_prompt)
        self.assertEqual(len(grp_bindings), 1)
        self.assertEqual(grp_bindings[0]["role"], production_tool.AUDIO_REFERENCE_ROLE)
        self.assertTrue(grp_bindings[0]["path"].endswith("xutang.opus"))

        delivery, cuts, unused = edit_tool.parse_cut_list(self.episode / "剪辑单.md")
        self.assertEqual(
            edit_tool.check_cuts(
                self.episode,
                cuts,
                self.project,
                probe=False,
                unused=unused,
                delivery=delivery,
            ),
            [],
        )


class CrossSkillRuleTierParityTests(unittest.TestCase):
    TIERS = {
        "structural_invariant",
        "reviewed_invariant",
        "craft_default",
        "taste_option",
    }
    RULE_ROW_RE = re.compile(
        r"^\|\s*`?([A-Z]{3}-\d{2})`?\s*\|\s*`?([a-z_]+)`?\s*\|",
        re.MULTILINE,
    )
    INLINE_TIER_RE = re.compile(
        r"\b([A-Z]{3}-\d{2})\b(?:\s*[·:：]\s*|\s*[（(]\s*)"
        r"`?(structural_invariant|reviewed_invariant|craft_default|taste_option)`?"
    )

    def _stage_contract_registry(self) -> dict[str, tuple[str, list[str]]]:
        registry: dict[str, tuple[str, list[str]]] = {}
        for path in sorted((SUITE / "skills").glob("*/references/stage-contract.md")):
            rel = str(path.relative_to(SUITE))
            for rule_id, tier in self.RULE_ROW_RE.findall(
                path.read_text(encoding="utf-8")
            ):
                self.assertIn(
                    tier,
                    self.TIERS,
                    f"{rel}: {rule_id} uses unknown rule tier {tier!r}",
                )
                if rule_id in registry:
                    existing_tier, owners = registry[rule_id]
                    self.assertTrue(
                        rule_id.startswith("CON-"),
                        f"{rule_id} declared in multiple stage contracts: {owners + [rel]}",
                    )
                    self.assertEqual(
                        tier,
                        existing_tier,
                        f"{rule_id} tier conflict between {owners} ({existing_tier}) and {rel} ({tier})",
                    )
                    owners.append(rel)
                else:
                    registry[rule_id] = (tier, [rel])
        return registry

    def test_every_referenced_rule_id_and_tier_matches_stage_contracts(self) -> None:
        registry = self._stage_contract_registry()
        self.assertGreaterEqual(len(registry), 180)
        prefixes = sorted({rule_id.split("-")[0] for rule_id in registry})
        rule_token_re = re.compile(
            r"(?<![A-Z0-9-])((?:" + "|".join(prefixes) + r")-\d{2})(?![A-Z0-9-])"
        )

        undefined_mentions: list[str] = []
        tier_mismatches: list[str] = []

        for path in sorted((SUITE / "skills").rglob("*.md")):
            rel = str(path.relative_to(SUITE))
            text = path.read_text(encoding="utf-8")

            for match in rule_token_re.finditer(text):
                rule_id = match.group(1)
                if rule_id not in registry:
                    undefined_mentions.append(f"{rel}: {rule_id}")

            for rule_id, tier in self.RULE_ROW_RE.findall(text):
                if tier in self.TIERS and rule_id in registry:
                    expected_tier = registry[rule_id][0]
                    if tier != expected_tier:
                        tier_mismatches.append(
                            f"{rel}: table row {rule_id} has {tier}, expected {expected_tier}"
                        )

            for match in self.INLINE_TIER_RE.finditer(text):
                rule_id, tier = match.group(1), match.group(2)
                if rule_id in registry:
                    expected_tier = registry[rule_id][0]
                    if tier != expected_tier:
                        tier_mismatches.append(
                            f"{rel}: inline {match.group(0)!r} has {tier}, expected {expected_tier}"
                        )

        self.assertEqual(undefined_mentions, [])
        self.assertEqual(tier_mismatches, [])


if __name__ == "__main__":
    unittest.main()
