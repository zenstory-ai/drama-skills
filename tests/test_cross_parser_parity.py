"""Cross-script Markdown parser parity and cross-skill rule tier parity tests.

Exercises all active creator-Markdown scripts against a single episode carrying
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
duration_estimate = _load_script(
    "parity_duration_estimate",
    "skills/short-drama-write/scripts/duration_estimate.py",
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
        self.assertEqual(
            creator_check._screenplay_dialogue(SCREENPLAY_MD),
            {"许棠", "Dr. Lin"},
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

        parsed_blocks, parsed_issues = duration_estimate.parse_screenplay(
            SCREENPLAY_MD.encode("utf-8"), frozenset({"许棠", "Dr. Lin"})
        )
        self.assertEqual(parsed_issues, [])
        parsed_scene_ids = [
            block["scene_id"]
            for block in parsed_blocks
            if block["kind"] == "scene_heading"
        ]
        parsed_speakers = [
            (block["speaker"], block.get("tag") or "on_camera")
            for block in parsed_blocks
            if block.get("speaker")
        ]
        self.assertEqual(parsed_scene_ids, view_scene_ids)
        self.assertEqual(parsed_speakers, [("许棠", "on_camera"), ("Dr. Lin", "VO")])

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

        de_blocks, de_meta = duration_estimate.parse_script_blocks(
            (self.episode / "剧本.md").read_bytes()
        )
        self.assertEqual(de_meta["review_status"], "clean")
        self.assertEqual(
            [b["speaker"] for b in de_blocks if b.get("speaker")],
            ["许棠", "Dr. Lin"],
        )

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

    def test_post_blockquote_comments_do_not_revive_sections_and_unused_splits_respect_parens(
        self,
    ) -> None:
        doc = (
            "## SHOT-EP001-001 · 开场\n"
            "- 时长：4s\n\n"
            "### 首帧提示词\n"
            "> 屏幕上保留字面量 <!-- keep --> 代码片段。\n\n"
            "<!--\n"
            "## SHOT-EP001-999 · 已注释废镜\n"
            "- 时长：99s\n"
            "-->\n\n"
            "## SHOT-EP001-002 · 收尾\n"
            "- 时长：3s\n\n"
            "### 首帧提示词\n"
            "> 走廊尽头定格。\n"
            "<!-- 本集完 -->\n"
        )
        for strip_fn in (
            lambda s: creator_check._strip_html_comments(s, preserve_copyable=True),
            lambda s: production_tool._strip_html_comments(s, preserve_copyable=True),
            lambda s: edit_tool._strip_html_comments(s, preserve_copyable=True),
        ):
            stripped = strip_fn(doc)
            self.assertIn("<!-- keep -->", stripped)
            self.assertNotIn("SHOT-EP001-999", stripped)
            self.assertNotIn("本集完", stripped)

        _, unclosed = creator_check._scan_html_comments(
            doc + "<!-- 未闭合尾注\n", preserve_copyable=True
        )
        self.assertTrue(unclosed)

        cut_md = (
            "# EP001 剪辑单\n\n"
            "- 未采用镜头：MOTION-EP001-002（景别过近；改用反应镜）；"
            "MOTION-EP001-003(时长不足;留作备选)\n\n"
            "## CUT-001 · 主镜\n"
            "- 来源：MOTION-EP001-001 · 剧集/EP001/制作成果/video/group01.mp4\n"
            "- 入点：0.00\n"
            "- 出点：4.00\n"
            "- 时长：4.00\n"
            "- 取舍：保留开门动作。\n"
        )
        view_cuts = creator_views.parse_cut_list(cut_md)
        self.assertEqual(
            view_cuts["unused"],
            [
                "MOTION-EP001-002（景别过近；改用反应镜）",
                "MOTION-EP001-003(时长不足;留作备选)",
            ],
        )

    def test_bold_colon_inside_emphasis_parity_across_all_four_parsers(self) -> None:
        """All four Markdown parsers treat `- **字段：** 值` identically to `- **字段**：值`."""
        img_dir = self.project / "输入/参考图"
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / "xutang.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        voice_dir = self.project / "输入/声音"
        voice_dir.mkdir(parents=True, exist_ok=True)
        (voice_dir / "xutang.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")

        settings_bold = (
            "# EP001 视觉设定\n\n"
            "- **制作形态：** 写实竖屏短剧，9:16。\n"
            "- **时代背景：** 当下（2020 年代）；设备：液晶监视器。\n\n"
            "## 人物 · 许棠\n\n"
            "- **外观特征：** 齐耳短黑发、深灰工装夹克。\n"
            "- **提示词名称：** Xutang\n"
            "- **角色声线：** 冷清女中音；不允许娇嗔气声\n"
            "- **声音参考：** 输入/声音/xutang.wav（用途：音色；控制：音色、音区；不得控制：情绪、混响；状态：创作者已说明）\n\n"
            "## 人物 · Dr. Lin\n\n"
            "- **外观特征：** 银边眼镜、白大褂。\n"
            "- **提示词名称：** 无\n"
            "* *角色声线:* 沉稳低男中音\n\n"
            "## 地点 · 监控室\n\n"
            "- **外观特征：** 黑色操作台、液晶监视器阵列。\n\n"
            "## 地点 · 走廊\n\n"
            "- **外观特征：** 水泥墙面、冷白应急灯。\n"
        )
        storyboard_bold = (
            "# EP001 分镜\n\n"
            "- **未拍场次：** EP001-SC003（理由：顺延至下集）\n\n"
            "## SHOT-EP001-001 · 电闸熄灭\n\n"
            "- **来源：** EP001-SC001「许棠：是谁关了电闸？」\n"
            "- **时长：** 4s\n"
            "- **景别：** 近景\n"
            "- **运镜：** 固定\n"
            "- **出场设定：** 《视觉设定.md》·人物「许棠」（控制：外貌）；《视觉设定.md》·地点「监控室」（控制：空间布局）\n"
            "- **输入参考图：** REF-XUTANG（顺序：1）· 输入/参考图/xutang.png《许棠定妆》（用途：外貌；控制：脸型、服装；不得控制：动作、构图）\n"
            "- **画面与动作：** 许棠抬头追问。\n\n"
            "### 首帧提示词\n"
            "> 9:16 close-up of Xutang before dark monitors, no text.\n\n"
            "## SHOT-EP001-002 · 走廊读数\n\n"
            "- **来源：** EP001-SC002「[VO] Dr. Lin：记录第二次读数。」\n"
            "- **时长：** 3s\n"
            "- **景别：** 中景\n"
            "- **运镜：** 缓慢前推\n"
            "- **出场设定：** 《视觉设定.md》·地点「走廊」（控制：空间布局）\n"
            "* *输入参考图:* 无（文生首帧）。\n"
            "- **画面与动作：** 空镜走廊前推。\n\n"
            "### 首帧提示词\n"
            "> 9:16 medium shot down a concrete corridor, no people, no text.\n"
        )
        video_bold = (
            "# EP001 视频提示词\n\n"
            "## MOTION-EP001-001 · 电闸熄灭\n\n"
            "- **分镜：** SHOT-EP001-001\n"
            "- **时长：** 4s\n"
            "- **生成方式：** 图生视频\n"
            "- **输入参考图：** REF-XUTANG（顺序：1）· 输入/参考图/xutang.png《许棠定妆》（用途：外貌；控制：脸型、服装；不得控制：动作、构图）\n"
            "- **参考音频：** REF-VOICE-XT（顺序：1）· 输入/声音/xutang.wav《许棠音色》（用途：音色；角色：许棠；控制：音色、音区；不得控制：情绪、混响）\n"
            "- **起始帧：** 许棠扶住操作台。\n"
            "- **动作过程：** 抬头追问\n"
            "- **终点：** 目光停在门口。\n\n"
            "### 可复制提示词\n"
            "> Xutang looks up sharply and asks in Chinese, “是谁关了电闸？”. Static camera, no text.\n\n"
            "## MOTION-EP001-002 · 走廊读数\n\n"
            "- **分镜：** SHOT-EP001-002\n"
            "- **时长：** 3s\n"
            "- **生成方式：** 文生视频\n"
            "* *输入参考图:* 无（文生视频）。\n"
            "- **开场画面：** Empty concrete corridor lit by cold emergency light.\n"
            "- **起始帧：** 走廊空无一人。\n"
            "- **动作过程：** 缓慢前推\n"
            "- **终点：** 靠近防火门。\n\n"
            "### 可复制提示词\n"
            "> Slow push-in down empty corridor while voice-over says in Chinese, “记录第二次读数。”. No text.\n"
        )
        cuts_bold = (
            "# EP001 剪辑单\n\n"
            "- **成片目标时长：** 7.00 秒\n"
            "- **交付响度：** -14 LUFS\n"
            "- **画幅与帧率：** 1080×1920 30fps\n"
            "- **未采用镜头：** MOTION-EP001-002（测试备选）\n\n"
            "## CUT-EP001-001 · 电闸熄灭\n\n"
            "- **来源：** MOTION-EP001-001 · 剧集/EP001/制作成果/shot-001.mp4\n"
            "- **入点：** 0.00\n"
            "- **出点：** 4.00\n"
            "- **时长：** 4.00\n"
            "- **字幕：** 是谁关了电闸？\n"
            "- **画面文字：** 0.50-2.50 字卡 00:00 断电\n"
        )

        (self.episode / "视觉设定.md").write_text(settings_bold, encoding="utf-8")
        (self.episode / "分镜.md").write_text(storyboard_bold, encoding="utf-8")
        (self.episode / "视频提示词.md").write_text(video_bold, encoding="utf-8")
        (self.episode / "剪辑单.md").write_text(cuts_bold, encoding="utf-8")

        # 1. creator_markdown_check
        self.assertEqual(creator_check.validate_episode(self.episode, self.project), [])

        # 2. creator_views
        view_settings = creator_views.parse_settings(settings_bold)
        self.assertEqual(view_settings["form"], "写实竖屏短剧，9:16")
        self.assertEqual(view_settings["items"][0]["designators"], ["Xutang"])
        view_vids = creator_views.parse_video_prompts(video_bold)
        self.assertEqual(view_vids[0]["shot"], "SHOT-EP001-001")
        self.assertEqual(view_vids[0]["mode"], "图生视频")
        self.assertEqual(view_vids[0]["chain"], "抬头追问")
        self.assertEqual(view_vids[0]["sec"], 4.0)
        view_cuts = creator_views.parse_cut_list(cuts_bold)
        self.assertEqual(view_cuts["target"], 7.0)
        self.assertEqual(view_cuts["unused"], ["MOTION-EP001-002（测试备选）"])
        self.assertEqual(len(view_cuts["cuts"]), 1)
        self.assertEqual(view_cuts["cuts"][0]["subs"][0]["text"], "是谁关了电闸？")

        # 3. production_tool (must NOT drop REF-XUTANG or REF-VOICE-XT!)
        prompt_text, bindings = production_tool._extract_markdown_source_defaults(
            self.project,
            source="剧集/EP001/视频提示词.md",
            source_entry="MOTION-EP001-001",
        )
        self.assertIn("是谁关了电闸", prompt_text)
        self.assertEqual(len(bindings), 2)
        self.assertEqual(
            {b["path"] for b in bindings},
            {"输入/参考图/xutang.png", "输入/声音/xutang.wav"},
        )

        # 4. edit_tool
        delivery, cuts, unused = edit_tool.parse_cut_list(self.episode / "剪辑单.md")
        self.assertAlmostEqual(delivery.target_seconds or 0.0, 7.0)
        self.assertEqual(unused, view_cuts["unused"])
        self.assertEqual(len(cuts), 1)
        self.assertEqual(cuts[0].cut_id, "CUT-EP001-001")
        self.assertEqual(cuts[0].subtitles[0][2], "是谁关了电闸？")
        self.assertEqual(cuts[0].screen_texts[0].style, "字卡")

    def test_vendored_shared_helpers_stay_in_sync(self) -> None:
        """Build-time vendored helpers in skills/*/scripts match src/_shared/ verbatim."""
        sync_shared = _load_script("parity_sync_shared", "tools/sync_shared.py")
        self.assertEqual(sync_shared.check_sync(SUITE), [])

        canonical = _load_script("parity_shared_cn_num", "src/_shared/cn_num.py")
        novel_index = _load_script(
            "parity_novel_index",
            "skills/short-drama-novel-analyze/scripts/novel_index.py",
        )
        episode_intake = _load_script(
            "parity_episode_intake",
            "skills/short-drama-develop/scripts/episode_intake.py",
        )
        cases = (
            ("一", 1),
            ("十五", 15),
            ("两百零三", 203),
            ("两零八", 208),
            ("一千零十五", 1015),
            ("二十零三", None),
            ("一百零二十", None),
            ("一两三", None),
        )
        for token, expected in cases:
            self.assertEqual(canonical.chinese_to_int(token), expected)
            self.assertEqual(novel_index.chinese_to_int(token), expected)
            self.assertEqual(episode_intake.chinese_to_int(token), expected)


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
    RULE_DETAIL_ROW_RE = re.compile(
        r"^\|\s*`?([A-Z]{3}-\d{2})`?\s*\|\s*`?([a-z_]+)`?\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    INLINE_TIER_RE = re.compile(
        r"\b([A-Z]{3}-\d{2})\b(?:\s*[·:：]\s*|\s*[（(]\s*)"
        r"`?(structural_invariant|reviewed_invariant|craft_default|taste_option)`?"
    )
    VERBATIM_SHARED_CON_RULES = frozenset({"CON-01", "CON-02", "CON-07"})

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

    def _stage_contract_descriptions(
        self,
    ) -> dict[str, dict[str, tuple[str, str]]]:
        contracts: dict[str, dict[str, tuple[str, str]]] = {}
        for path in sorted((SUITE / "skills").glob("*/references/stage-contract.md")):
            skill = path.relative_to(SUITE / "skills").parts[0]
            rows: dict[str, tuple[str, str]] = {}
            for rule_id, tier, desc in self.RULE_DETAIL_ROW_RE.findall(
                path.read_text(encoding="utf-8")
            ):
                rows[rule_id] = (tier, " ".join(desc.split()))
            contracts[skill] = rows
        return contracts

    def test_shared_continuity_rules_keep_canonical_text_across_stage_contracts(
        self,
    ) -> None:
        contracts = self._stage_contract_descriptions()
        shared_skills = (
            "short-drama-assets",
            "short-drama-storyboard",
            "short-drama-video-prompts",
        )
        for skill in shared_skills:
            self.assertIn(skill, contracts)

        con_sets = {
            skill: {rid for rid in contracts[skill] if rid.startswith("CON-")}
            for skill in shared_skills
        }
        canonical_ids = con_sets[shared_skills[0]]
        self.assertTrue(canonical_ids)
        for skill in shared_skills[1:]:
            self.assertEqual(
                con_sets[skill],
                canonical_ids,
                f"{skill} CON-* rule ID set differs from {shared_skills[0]}",
            )

        for rule_id in sorted(canonical_ids):
            tier_map = {skill: contracts[skill][rule_id][0] for skill in shared_skills}
            self.assertEqual(
                len(set(tier_map.values())),
                1,
                f"{rule_id} tier mismatch across shared contracts: {tier_map}",
            )
            tier = next(iter(tier_map.values()))
            if rule_id in self.VERBATIM_SHARED_CON_RULES or tier == "structural_invariant":
                desc_map = {
                    skill: contracts[skill][rule_id][1] for skill in shared_skills
                }
                self.assertEqual(
                    len(set(desc_map.values())),
                    1,
                    f"{rule_id} description text drifted across stage contracts: {desc_map}",
                )

    def test_every_referenced_rule_id_and_tier_matches_stage_contracts(self) -> None:
        registry = self._stage_contract_registry()
        self.assertGreaterEqual(len(registry), 100)
        blocking_tiers = {"structural_invariant", "reviewed_invariant"}
        non_blocking = [
            f"{rule_id} ({tier} in {owners})"
            for rule_id, (tier, owners) in sorted(registry.items())
            if tier not in blocking_tiers
        ]
        self.assertEqual(
            non_blocking,
            [],
            "stage-contract.md tables may declare only blocking invariants",
        )
        prefixes = sorted({rule_id.split("-")[0] for rule_id in registry})
        rule_token_re = re.compile(
            r"(?<![A-Z0-9-])((?:" + "|".join(prefixes) + r")-\d{2})(?![A-Z0-9-])"
        )
        skill_owned_rules: dict[str, set[str]] = {}
        for rule_id, (_, owners) in registry.items():
            for owner in owners:
                skill_name = Path(owner).parts[1]
                skill_owned_rules.setdefault(skill_name, set()).add(rule_id)

        undefined_mentions: list[str] = []
        foreign_mentions: list[str] = []
        tier_mismatches: list[str] = []

        for path in sorted((SUITE / "skills").rglob("*.md")):
            rel = str(path.relative_to(SUITE))
            skill_name = path.relative_to(SUITE / "skills").parts[0]
            text = path.read_text(encoding="utf-8")

            for match in rule_token_re.finditer(text):
                rule_id = match.group(1)
                if rule_id not in registry:
                    undefined_mentions.append(f"{rel}: {rule_id}")
                elif (
                    skill_name != "short-drama-review"
                    and rule_id not in skill_owned_rules.get(skill_name, set())
                ):
                    foreign_mentions.append(f"{rel}: {rule_id}")

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
        self.assertEqual(foreign_mentions, [])
        self.assertEqual(tier_mismatches, [])

    def test_review_references_cover_all_upstream_blocking_rules_with_matching_tiers(
        self,
    ) -> None:
        """short-drama-review/references/ covers 100% of upstream blocking rules with matching tiers."""
        registry = self._stage_contract_registry()
        upstream = {
            rule_id: tier
            for rule_id, (tier, owners) in registry.items()
            if any(Path(owner).parts[1] != "short-drama-review" for owner in owners)
        }
        self.assertEqual(len(upstream), 100)

        rule_token_re = re.compile(r"(?<![A-Z0-9-])([A-Z]{3}-\d{2})(?![A-Z0-9-])")
        tier_re = re.compile(
            r"`?(structural_invariant|reviewed_invariant|craft_default|taste_option)`?"
        )
        grouped_re = re.compile(
            r"((?:`?[A-Z]{3}-\d{2}`?(?:\s*[、,/]\s*|\s+))*`?[A-Z]{3}-\d{2}`?)"
            r"\s*(?:·|[:：]|，均为|均为)\s*"
            r"`?(structural_invariant|reviewed_invariant|craft_default|taste_option)`?"
        )

        covered_tiers: dict[str, set[str]] = {}
        tier_mismatches: list[str] = []

        review_refs = sorted(
            path
            for path in (SUITE / "skills/short-drama-review/references").glob("*.md")
            if path.name != "stage-contract.md"
        )
        self.assertTrue(review_refs)

        for path in review_refs:
            rel = str(path.relative_to(SUITE))
            current_group_tier: str | None = None
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("- "):
                    heading = re.match(r"^- \*\*([^*]+)\*\*", line)
                    tiers = tier_re.findall(heading.group(1)) if heading else []
                    unique_tiers = set(tiers)
                    if len(unique_tiers) == 1 and next(iter(unique_tiers)) in {
                        "structural_invariant",
                        "reviewed_invariant",
                    }:
                        current_group_tier = next(iter(unique_tiers))
                    else:
                        current_group_tier = None
                elif not line.startswith("  "):
                    current_group_tier = None

                for rules_blob, tier in grouped_re.findall(line):
                    for rule_id in rule_token_re.findall(rules_blob):
                        if rule_id in upstream:
                            covered_tiers.setdefault(rule_id, set()).add(tier)
                            if tier != upstream[rule_id]:
                                tier_mismatches.append(
                                    f"{rel}: {rule_id} declares {tier}, expected {upstream[rule_id]}"
                                )

                if current_group_tier and line.startswith("  - "):
                    for rule_id in rule_token_re.findall(line):
                        if rule_id in upstream:
                            covered_tiers.setdefault(rule_id, set()).add(
                                current_group_tier
                            )
                            if current_group_tier != upstream[rule_id]:
                                tier_mismatches.append(
                                    f"{rel}: {rule_id} under {current_group_tier}, expected {upstream[rule_id]}"
                                )

        missing = sorted(set(upstream) - set(covered_tiers))
        self.assertEqual(
            missing,
            [],
            f"Upstream blocking rules missing from short-drama-review/references/: {missing}",
        )
        self.assertEqual(tier_mismatches, [])


if __name__ == "__main__":
    unittest.main()
