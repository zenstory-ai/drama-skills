"""Partial checks, in-frame lock scope and delivery groups in creator_markdown_check.

Each case starts from the shipped creator-first episode, which passes the full
check, and changes one thing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "examples/creator-first/EP001"
SPEC = importlib.util.spec_from_file_location(
    "partial_creator_markdown_check",
    ROOT / "skills/short-drama/scripts/creator_markdown_check.py",
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

SURFACE = "pine-green lapel service jacket"


class EpisodeCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.project = Path(self._directory.name)
        self.episode = self.project / "剧集/EP001"
        shutil.copytree(EPISODE, self.episode)

    def tearDown(self) -> None:
        self._directory.cleanup()

    def edit(self, name: str, old: str, new: str, count: int = 1) -> None:
        path = self.episode / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, count), encoding="utf-8")

    def drop(self, *names: str) -> None:
        for name in names:
            (self.episode / name).unlink()

    def errors(self, partial: bool = False) -> list[str]:
        return check.validate_episode(self.episode, self.project, partial=partial)

    def shot_keyframe(self, shot_id: str) -> str:
        board = (self.episode / "分镜.md").read_text(encoding="utf-8")
        return check._copyable_prompt(check._sections(board, "SHOT")[shot_id], heading="首帧提示词")


class PartialCheckTests(EpisodeCase):
    def test_default_still_requires_all_five_documents(self) -> None:
        self.drop("视频提示词.md")
        self.assertEqual(self.errors(), ["缺少创作文档: 视频提示词.md"])

    def test_storyboard_defects_surface_before_video_prompts_exist(self) -> None:
        # Storyboard cross-document structural checks run before video prompts exist.
        self.drop("视频提示词.md")
        self.assertEqual(self.errors(partial=True), [])
        self.edit("分镜.md", "·人物「江晨」（控制：外貌、体态、本集造型）", "·人物「不存在角色」（控制：外貌）")
        errors = self.errors(partial=True)
        self.assertTrue(any("SHOT-EP001-002" in error and "不存在角色" in error for error in errors), errors)
        self.assertFalse(any("MOTION" in error for error in errors), errors)

    def test_asset_stage_checks_image_prompts_against_locks(self) -> None:
        self.drop("分镜.md", "视频提示词.md")
        self.assertEqual(self.errors(partial=True), [])
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        locked = re.search(r"连戏锁：LOCK-JIANGCHEN-DRESS[^\n]*图片提示词项：(IMG-[A-Z0-9-]+)", visual)
        assert locked
        self.edit("视觉设定.md", locked.group(1), "IMG-MISSING-REF")
        errors = self.errors(partial=True)
        self.assertIn("LOCK-JIANGCHEN-DRESS: 连戏锁指向不存在的 IMG 条目: IMG-MISSING-REF", errors)

    def test_missing_upstream_is_skipped_rather_than_reported(self) -> None:
        # Without 剧本.md the shots' scene ids and quotes cannot be resolved;
        # that is not the same as being wrong.
        self.drop("剧本.md", "视频提示词.md")
        self.assertEqual(self.errors(partial=True), [])

    def test_motion_rules_still_run_without_a_storyboard(self) -> None:
        self.drop("分镜.md")
        self.edit("视频提示词.md", "- 输入参考图：无（文生视频）。", "- 输入参考图：REF-BROKEN", 1)
        errors = self.errors(partial=True)
        self.assertTrue(any(error.startswith("MOTION-EP001-001:") for error in errors), errors)

    def test_bound_voice_is_not_rejected_for_a_missing_upstream(self) -> None:
        from tests import test_voice_reference_binding as voice

        episode = voice.bound_episode(self.project)
        self.assertEqual(check.validate_episode(episode, self.project), [])
        for name in ("剧本.md", "视觉设定.md"):
            with self.subTest(missing=name):
                shutil.rmtree(episode)
                episode = voice.bound_episode(self.project)
                (episode / name).unlink()
                errors = check.validate_episode(episode, self.project, partial=True)
                self.assertFalse(any("参考音频" in error or "声音参考" in error for error in errors), errors)

    def test_text_only_validation_does_not_guess_the_prompt_language(self) -> None:
        texts = {name: (self.episode / name).read_text(encoding="utf-8") for name in check.REQUIRED_DOCUMENTS}
        texts["视觉设定.md"] = re.sub(r"^- 提示词名称：[^\n]*\n", "", texts["视觉设定.md"], flags=re.MULTILINE)
        self.assertFalse(any("提示词名称" in error for error in check.validate_documents(texts, None)))

    def test_a_partial_check_before_any_document_has_nothing_to_fail(self) -> None:
        for name in check.REQUIRED_DOCUMENTS:
            (self.episode / name).unlink()
        self.assertEqual(self.errors(partial=True), [])
        self.assertEqual(self.errors(), [f"缺少创作文档: {', '.join(check.REQUIRED_DOCUMENTS)}"])


class InFrameLockTests(EpisodeCase):
    def use_in_frame_scope(self) -> None:
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        visual = re.sub(r"（镜头：SHOT-EP001-002[^；]*；", "（镜头：入画；", visual, count=1)
        (self.episode / "视觉设定.md").write_text(visual, encoding="utf-8")

    def test_lock_checks_validate_references_without_prose_substring_scanning(self) -> None:
        # Paraphrased lock wording in free prompt prose is left to semantic review,
        # while explicit nonexistent SHOT-/IMG- targets remain deterministic errors.
        self.use_in_frame_scope()
        self.edit("分镜.md", SURFACE, "tailored dark-green service coat", count=-1)
        self.edit("视频提示词.md", SURFACE, "tailored dark-green service coat", count=-1)
        self.assertEqual(self.errors(), [])

        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        bad_shot = visual.replace("（镜头：入画；", "（镜头：SHOT-EP001-999；", 1)
        (self.episode / "视觉设定.md").write_text(bad_shot, encoding="utf-8")
        self.assertIn(
            "LOCK-JIANGCHEN-DRESS: 连戏锁指向不存在的镜头: SHOT-EP001-999",
            self.errors(),
        )

    def test_a_misspelled_scope_is_caught_at_the_asset_stage(self) -> None:
        self.drop("分镜.md", "视频提示词.md")
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        visual = re.sub(r"（镜头：SHOT-EP001-002[^；]*；", "（镜头：入化；", visual, count=1)
        (self.episode / "视觉设定.md").write_text(visual, encoding="utf-8")
        self.assertTrue(any("入化" in error for error in self.errors(partial=True)))

    def test_in_frame_lock_outside_an_entry_is_rejected(self) -> None:
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        line = re.search(r"^- 连戏锁：LOCK-JIANGCHEN-DRESS[^\n]*$", visual, re.MULTILINE)
        assert line
        moved = visual.replace(line.group(0) + "\n", "")
        heading = re.search(r"^## ", moved, re.MULTILINE)
        assert heading
        scoped = re.sub(r"（镜头：SHOT-EP001-002[^；]*；", "（镜头：入画；", line.group(0))
        moved = moved[: heading.start()] + scoped + "\n\n" + moved[heading.start() :]
        (self.episode / "视觉设定.md").write_text(moved, encoding="utf-8")
        self.assertTrue(any("入画" in error and "条目下" in error for error in self.errors()))


GROUP = """
## GROUP-EP001-01 · 茶杯到双人
- 成员：MOTION-EP001-001、MOTION-EP001-002
- 时长：{seconds}
- 理由：同场连续，同一办公室地理。

### 可复制提示词
> {body}
"""


class LockOwnerTests(EpisodeCase):
    def test_an_in_frame_lock_under_a_note_section_belongs_to_no_entry(self) -> None:
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        line = re.search(r"^- 连戏锁：LOCK-JIANGCHEN-DRESS[^\n]*$", visual, re.MULTILINE)
        assert line
        scoped = re.sub(r"（镜头：SHOT-EP001-002[^；]*；", "（镜头：入画；", line.group(0))
        moved = visual.replace(line.group(0) + "\n", "") + "\n## 本集备注\n\n" + scoped + "\n"
        (self.episode / "视觉设定.md").write_text(moved, encoding="utf-8")
        self.assertTrue(any("入画" in error and "条目下" in error for error in self.errors()))


class DeliveryGroupTests(EpisodeCase):
    def body_of(self, motion_id: str) -> str:
        video = (self.episode / "视频提示词.md").read_text(encoding="utf-8")
        prompt = check._copyable_prompt(check._sections(video, "MOTION")[motion_id])
        assert prompt
        return prompt

    def add_group(self, seconds: str = "7s", body: str = "", members: str = "") -> None:
        text = GROUP.format(
            seconds=seconds,
            body=body or f"镜头1：{self.body_of('MOTION-EP001-001')} 镜头2：{self.body_of('MOTION-EP001-002')}",
        )
        if members:
            text = text.replace("MOTION-EP001-001、MOTION-EP001-002", members)
        path = self.episode / "视频提示词.md"
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def test_a_well_formed_group_passes(self) -> None:
        self.add_group()
        self.assertEqual(self.errors(), [])

    def test_group_length_is_the_sum_of_its_members(self) -> None:
        self.add_group(seconds="8s")
        self.assertTrue(any("不等于成员时长之和 7 秒" in error for error in self.errors()))

    def test_members_must_be_adjacent_and_in_one_group(self) -> None:
        self.add_group(members="MOTION-EP001-001、MOTION-EP001-003")
        self.assertTrue(any("按顺序相邻" in error for error in self.errors()))

    def test_a_scene_named_inside_a_source_quote_is_not_carried(self) -> None:
        """A quote may mention another scene; only the leading ids are carried.

        A real run's shot quoted a continuity note naming an earlier scene, and
        its group was rejected as crossing scenes it never filmed.
        """

        self.edit(
            "分镜.md",
            "- 来源：EP001-SC001\n",
            "- 来源：EP001-SC001「[连续性] 与 EP001-SC002 同一张桌」\n",
        )
        self.add_group()
        self.assertEqual([e for e in self.errors() if "跨场次" in e], [])

    def test_a_repeated_member_is_reported_not_collapsed(self) -> None:
        self.add_group(members="MOTION-EP001-001、MOTION-EP001-001、MOTION-EP001-002")
        self.assertIn("GROUP-EP001-01: 成员重复；一次合生里每个镜头只出现一次", self.errors())

    def test_an_unreadable_member_duration_is_reported(self) -> None:
        self.edit("视频提示词.md", "- 时长：3s", "- 时长：未知")
        self.add_group(seconds="999s")
        self.assertTrue(any("没有可解析的时长" in error and error.startswith("GROUP") for error in self.errors()))

    def test_a_repeated_group_id_cannot_hide_a_second_body(self) -> None:
        self.add_group()
        self.add_group(seconds="99s", body="他说：“这句台词剧本里没有出现过”")
        self.assertIn("视频提示词.md: GROUP 标题 ID 重复", self.errors())

    def test_a_trailing_section_is_not_read_as_the_last_motion(self) -> None:
        path = self.episode / "视频提示词.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n## 本集报告\n- 时长：62s\n", encoding="utf-8"
        )
        self.assertEqual(self.errors(), [])


class RelaxedGateContractTests(EpisodeCase):
    def test_chinese_prompts_without_manifest_do_not_force_english_screen_names(self) -> None:
        files = {
            "剧本.md": (
                "# EP001 茶杯\n\n"
                "## EP001-SC001 内 · 办公室 · 日\n\n"
                "江晨把玻璃茶杯放到办公桌上。\n\n"
                "江晨：先把名单收好。\n"
            ),
            "视觉设定.md": (
                "# EP001 视觉设定\n\n"
                "## 人物 · 江晨\n"
                "- 外观特征：二十五岁青年，短发，松枝绿常服外套。\n\n"
                "## 地点 · 办公室\n"
                "- 外观特征：百叶窗透光的简洁办公室，木质办公桌。\n"
            ),
            "图片提示词.md": (
                "# EP001 图片提示词\n\n"
                "## IMG-JC-SHEET · 江晨人物设定图\n"
                "- 用途：人物基准\n"
                "- 参考：无外部参考。\n\n"
                "### 可复制提示词\n"
                "> 9:16 竖幅人物三视图，江晨身穿松枝绿常服外套，神情克制。\n"
            ),
            "分镜.md": (
                "# EP001 分镜\n\n"
                "## SHOT-EP001-001 · 放下茶杯\n"
                "- 来源：EP001-SC001\n"
                "- 时长：3s\n"
                "- 景别/机位：近景，桌面平视\n"
                "- 图片提示词项：IMG-JC-SHEET《江晨人物设定图》（控制：人物外貌、服装）\n"
                "- 输入参考图：无（文生视频）。\n"
                "- 出场设定：《视觉设定.md》·人物「江晨」（控制：外貌、服装）；地点「办公室」（控制：桌面陈设）\n\n"
                "### 首帧提示词\n"
                "> 9:16 竖幅近景，办公室木桌前，江晨右手扶着玻璃茶杯，百叶窗侧光清晰。\n"
            ),
            "视频提示词.md": (
                "# EP001 视频提示词\n\n"
                "## MOTION-EP001-001 · 放下茶杯\n"
                "- 分镜：SHOT-EP001-001\n"
                "- 时长：3s\n"
                "- 生成方式：文生视频\n"
                "- 输入参考图：无（文生视频）。\n"
                "- 开场画面：办公室木桌前，江晨右手扶着玻璃茶杯。\n\n"
                "### 可复制提示词\n"
                "> 9:16 竖幅近景，办公室里江晨把玻璃茶杯稳稳放在木桌上，低声说：“先把名单收好。”\n"
            ),
        }
        for name, content in files.items():
            (self.episode / name).write_text(content, encoding="utf-8")
        self.assertTrue(check._copyable_prompt(files["图片提示词.md"]))
        self.assertTrue(check._copyable_prompt(files["分镜.md"], heading="首帧提示词"))
        self.assertTrue(check._copyable_prompt(files["视频提示词.md"]))
        self.assertEqual(self.errors(), [])

        english_video = files["视频提示词.md"].replace(
            "> 9:16 竖幅近景，办公室里江晨把玻璃茶杯稳稳放在木桌上，低声说：“先把名单收好。”\n",
            "> 9:16 vertical close-up in the office as a young man sets the glass cup onto the wooden desk.\n",
        )
        (self.episode / "视频提示词.md").write_text(english_video, encoding="utf-8")
        result = check.validate_episode_with_warnings(self.episode, self.project)
        self.assertEqual(result.errors, [])
        self.assertTrue(
            any("江晨" in warn and "提示词名称" in warn for warn in result.warnings),
            result.warnings,
        )

    def test_mixed_en_keyframes_and_zh_video_prompts_warn_for_screen_names(self) -> None:
        manifest = {
            "format": {"prompt_language": "en"},
            "creator_authority": {
                "production_profile": {
                    "status": "accepted",
                    "choices": {"video_prompt_language": "zh-CN"},
                }
            },
        }
        (self.project / "short-drama.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        visual_no_names = re.sub(r"^- 提示词名称：[^\n]*\n", "", visual, flags=re.MULTILINE)
        (self.episode / "视觉设定.md").write_text(visual_no_names, encoding="utf-8")
        result = check.validate_episode_with_warnings(self.episode, self.project)
        self.assertEqual(result.errors, [])
        self.assertTrue(any("提示词名称" in warn for warn in result.warnings), result.warnings)

    def test_multiword_speakers_and_duplicate_motion_fields_without_nlp_false_positives(
        self,
    ) -> None:
        # Multi-word speaker with ASCII performance cue in 剧本.md is parsed cleanly.
        screenplay_path = self.episode / "剧本.md"
        screenplay_path.write_text(
            screenplay_path.read_text(encoding="utf-8")
            + "\nDr. Lin (whispering)：先把名单收好。\n",
            encoding="utf-8",
        )
        speakers = check._screenplay_dialogue(screenplay_path.read_text(encoding="utf-8"))
        self.assertIn("Dr. Lin", speakers)
        visual_path = self.episode / "视觉设定.md"
        visual_path.write_text(
            visual_path.read_text(encoding="utf-8")
            + "\n## 人物 · Dr. Lin\n- 提示词名称：Dr. Lin\n- 外观特征：戴细框眼镜的顾问。\n",
            encoding="utf-8",
        )
        # Quoted prose and signage in copyable body do not trigger brittle NLP heuristics.
        self.edit(
            "视频提示词.md",
            "The camera does not move.",
            '墙上挂着“严谨求实团结奋进”的标语牌，他低声说：“即兴补充的一句环境人声。” The camera does not move.',
            count=1,
        )
        self.assertEqual(self.errors(), [])

        # Duplicate field on MOTION is reported once, and missing 输入参考图 does not cascade into REF syntax error.
        video_text = (self.episode / "视频提示词.md").read_text(encoding="utf-8")
        video_text = video_text.replace(
            "- 时长：3s\n- 生成方式：文生视频\n- 输入参考图：无（文生视频）。",
            "- 时长：3s\n- 时长：3s\n- 生成方式：文生视频",
            1,
        )
        (self.episode / "视频提示词.md").write_text(video_text, encoding="utf-8")
        dup_errors = self.errors()
        self.assertEqual(dup_errors.count("MOTION-EP001-001: 字段重复: 时长"), 1)
        self.assertIn("MOTION-EP001-001: 缺少输入参考图字段", dup_errors)
        self.assertFalse(any("完整 REF 语法" in err for err in dup_errors), dup_errors)

    def test_foreign_entry_titles_and_optional_shot_image_field_pass(self) -> None:
        self.edit("分镜.md", "## SHOT-EP001-001 · 攥紧的茶杯", "## SHOT-EP001-001 · Tight Grip Mug")
        self.edit("视频提示词.md", "## MOTION-EP001-001 · 攥紧的茶杯", "## MOTION-EP001-001 · Tight Grip Mug")
        board = (self.episode / "分镜.md").read_text(encoding="utf-8")
        board = re.sub(r"^- 图片提示词项：[^\n]*\n", "", board, count=1, flags=re.MULTILINE)
        (self.episode / "分镜.md").write_text(board, encoding="utf-8")
        self.assertEqual(self.errors(), [])

    def test_zero_dialogue_character_is_exempt_from_role_voice_when_voice_direction_is_used(self) -> None:
        visual_path = self.episode / "视觉设定.md"
        visual = visual_path.read_text(encoding="utf-8")
        visual = visual.replace(
            "## 人物 · 江晨\n",
            "## 人物 · 江晨\n\n- 角色声线：青年男中音，克制沉稳。\n",
        )
        visual = visual.replace(
            "## 人物 · 周薄森\n",
            "## 人物 · 周薄森\n\n- 角色声线：中年浑厚男低音，干脆利落。\n",
        )
        visual += (
            "\n## 人物 · 门岗哨兵\n"
            "- 提示词名称：无\n"
            "- 外貌：年轻战士，沉默站岗。\n"
        )
        visual_path.write_text(visual, encoding="utf-8")
        self.assertEqual(self.errors(), [])

        missing_speaker = visual.replace("- 角色声线：中年浑厚男低音，干脆利落。\n", "")
        visual_path.write_text(missing_speaker, encoding="utf-8")
        errors = self.errors()
        self.assertTrue(any("周薄森" in err and "角色声线" in err for err in errors), errors)

    def test_source_quote_naming_offscreen_character_does_not_require_offscreen_tag(self) -> None:
        self.edit(
            "分镜.md",
            "- 来源：EP001-SC001\n",
            "- 来源：EP001-SC001「江晨听着周薄森在门外说话」\n",
        )
        self.assertEqual(self.errors(), [])

    def test_bare_none_input_ref_reusable_plan_slot_and_non_substring_opening_frame_pass(self) -> None:
        self.edit("分镜.md", "- 输入参考图：无（文生视频）。", "- 输入参考图：无", count=1)
        self.edit("视频提示词.md", "- 输入参考图：无（文生视频）。", "- 输入参考图：无", count=1)
        self.edit(
            "视频提示词.md",
            "- 开场画面：A heavy middle-aged hand",
            "- 开场画面：Extreme close-up of a pine-green service-jacket cuff and hand gripping a glass tea tumbler on the desk.",
            count=1,
        )
        plan_line = (
            "- 输入参考图：PLAN-ABA-01（顺序：1）· SHOT-EP001-001《攥紧的茶杯》"
            "（用途：起始帧；控制：构图、光线；不得控制：人物动作）"
        )
        board = (self.episode / "分镜.md").read_text(encoding="utf-8")
        s3 = check._sections(board, "SHOT")["SHOT-EP001-003"]
        board = board.replace(
            s3,
            s3.replace("- 输入参考图：无（文生视频）。", plan_line),
        )
        (self.episode / "分镜.md").write_text(board, encoding="utf-8")
        self.assertEqual(self.errors(), [])

    def test_audio_reference_allows_flexible_control_subset(self) -> None:
        from tests import test_voice_reference_binding as voice

        flexible_line = voice.AUDIO_LINE.replace(
            "控制：音色、音区；不得控制：台词、语气、情绪",
            "控制：音色、语气、语速；不得控制：画面构图",
        )
        episode = voice.bound_episode(self.project, audio_line=flexible_line)
        self.assertEqual(check.validate_episode(episode, self.project), [])

    def test_image_reference_rejects_plan_and_pending_tokens_while_allowing_benign_notes(self) -> None:
        base_img = (self.episode / "图片提示词.md").read_text(encoding="utf-8")
        # Baseline example already has benign `无外部参考；三视图…` notes.
        self.assertEqual(self.errors(), [])

        for bad_ref in (
            "- 参考：PLAN-ABA-01（顺序：1）· SHOT-EP001-001《攥紧的茶杯》（用途：外貌；控制：外貌；不得控制：动作）",
            "- 参考：无（待补参考图：定妆照）",
            "- 参考：无外部参考；待补参考图：角色定妆照",
            "- 参考：无外部参考;待补参考图: 角色定妆照",
            "- 参考：ref-low-01（顺序：1）· 输入/参考/定妆.png《定妆》（用途：外貌；控制：外貌；不得控制：动作）",
        ):
            with self.subTest(bad_ref=bad_ref):
                mutated = base_img.replace(
                    "- 参考：无外部参考；三视图必须保持同一脸型、身高比例和服装细节。",
                    bad_ref,
                    1,
                )
                (self.episode / "图片提示词.md").write_text(mutated, encoding="utf-8")
                errs = self.errors()
                self.assertTrue(errs, f"expected errors for {bad_ref}")
        (self.episode / "图片提示词.md").write_text(base_img, encoding="utf-8")

    def test_delivery_group_enforces_pending_ref_gate_and_validates_audio_references(self) -> None:
        from tests import test_voice_reference_binding as voice

        opus_rel = "输入/声音/江晨音色.opus"
        episode = voice.bound_episode(self.project, voice_path=opus_rel)
        opus_voice = self.project / opus_rel
        opus_voice.write_bytes(b"OggS")
        self.assertEqual(check.validate_episode(episode, self.project), [])

        videos_path = episode / "视频提示词.md"
        base_videos = videos_path.read_text(encoding="utf-8")
        group_with_pending = (
            base_videos
            + "\n## GROUP-EP001-01 · 双镜测试\n"
            + "- 成员：MOTION-EP001-011、MOTION-EP001-012\n"
            + "- 时长：5s\n"
            + "- 输入参考图：无（待补参考图：走廊实拍图）\n"
            + f"- 参考音频：REF-VOICE-G1（顺序：1）· {opus_rel}《江晨声线》"
            "（用途：音色；角色：江晨；控制：音色；不得控制：台词）\n\n"
            + "### 可复制提示词\n"
            + '> @音频1 Jiangchen in a pine-green lapel service jacket presses his index finger onto the closed laptop and says, “下周榜首，是我们团。”\n'
        )
        videos_path.write_text(group_with_pending, encoding="utf-8")
        partial_errors = check.validate_episode(episode, self.project, partial=True)
        self.assertEqual(partial_errors, [])
        full_errors = check.validate_episode(episode, self.project, partial=False)
        self.assertTrue(
            any("GROUP-EP001-01" in err and "待补参考图" in err for err in full_errors),
            full_errors,
        )

        group_resolved = group_with_pending.replace(
            "- 输入参考图：无（待补参考图：走廊实拍图）\n",
            "- 输入参考图：PLAN-G1-01（顺序：1）· SHOT-EP001-011《冷茶》（用途：起始帧；控制：构图；不得控制：动作）\n",
        )
        videos_path.write_text(group_resolved, encoding="utf-8")
        self.assertEqual(check.validate_episode(episode, self.project, partial=False), [])

        group_bad_audio = group_resolved.replace(opus_rel, "输入/声音/不存在.opus")
        videos_path.write_text(group_bad_audio, encoding="utf-8")
        audio_errors = check.validate_episode(episode, self.project, partial=False)
        self.assertTrue(
            any("GROUP-EP001-01" in err and "不存在.opus" in err for err in audio_errors),
            audio_errors,
        )

    def test_html_comments_emphasized_keys_per_scene_blocking_and_screenplay_grammar(self) -> None:
        # Per-scene blocking between SHOT sections + HTML comment outside fences + trailing ## 备注
        board_path = self.episode / "分镜.md"
        board = board_path.read_text(encoding="utf-8")
        board = "<!--\n## SHOT-EP001-999 · 废弃镜头\n- 来源：EP999-SC999\n-->\n" + board
        board = board.replace(
            "## SHOT-EP001-002",
            "## 场景站位 · EP001-SC001 · 茶水间补充\n- 站位：门内对峙\n- 轴线：南北向\n- 视线：互视\n\n## SHOT-EP001-002",
            1,
        )
        board_path.write_text(board, encoding="utf-8")

        visual_path = self.episode / "视觉设定.md"
        visual = visual_path.read_text(encoding="utf-8")
        visual = visual.replace("- 提示词名称：", "- **提示词名称**：", 1)
        visual = visual.replace("- 连戏锁：", "- **连戏锁**：", 1)
        visual += "\n## 备注\n这里写审片备忘，不应并入上一条设定。\n"
        visual_path.write_text(visual, encoding="utf-8")

        script_path = self.episode / "剧本.md"
        base_script = script_path.read_text(encoding="utf-8")
        # `内外` scene space is valid
        script_path.write_text(
            base_script.replace("EP001-SC001 内 ·", "EP001-SC001 内外 ·", 1),
            encoding="utf-8",
        )
        self.assertEqual(self.errors(), [])

        # Malformed `## EP001-SC...` heading is caught with `内外` in diagnostic
        script_path.write_text(
            base_script + "\n## EP001-SC099 走廊夜戏\n\n江晨：谁？\n",
            encoding="utf-8",
        )
        bad_heading_errors = self.errors()
        self.assertTrue(
            any("EP001-SC099" in err and "内外" in err for err in bad_heading_errors),
            bad_heading_errors,
        )
        script_path.write_text(base_script, encoding="utf-8")

        # Strict `### 可复制提示词` heading rejects `### 可复制通用提示词`
        videos_path = self.episode / "视频提示词.md"
        base_videos = videos_path.read_text(encoding="utf-8")
        videos_path.write_text(
            base_videos.replace("### 可复制提示词", "### 可复制通用提示词", 1),
            encoding="utf-8",
        )
        heading_errors = self.errors()
        self.assertTrue(
            any("可复制提示词" in err for err in heading_errors),
            heading_errors,
        )

        # ASCII-colon foreign dialogue is recognized in `_screenplay_dialogue`
        speakers = check._screenplay_dialogue(
            "<!-- 场记注释 -->\n## EP001-SC001 外 · Pier · 夜\n\nElena: Stay back.\n\n12:30 灯亮。\n"
        )
        self.assertEqual(speakers, {"Elena"})

    def test_crlf_and_utf8_bom_normalize_across_all_episode_documents_and_helpers(self) -> None:
        videos_path = self.episode / "视频提示词.md"
        videos_path.write_text(
            videos_path.read_text(encoding="utf-8")
            + "\n## GROUP-EP001-01 · 双镜测试\n"
            + "- 成员：MOTION-EP001-011、MOTION-EP001-012\n"
            + "- 时长：5s\n"
            + "- 输入参考图：PLAN-G1-01（顺序：1）· SHOT-EP001-011《冷茶》（用途：起始帧；控制：构图；不得控制：动作）\n\n"
            + "### 可复制提示词\n"
            + '> Jiangchen in a pine-green lapel service jacket presses his index finger onto the closed laptop and says, “下周榜首，是我们团。”\n',
            encoding="utf-8",
        )
        for name in ("剧本.md", "视觉设定.md", "分镜.md", "图片提示词.md", "视频提示词.md"):
            path = self.episode / name
            crlf_bom = "\ufeff" + path.read_text(encoding="utf-8").replace("\n", "\r\n")
            path.write_bytes(crlf_bom.encode("utf-8"))
        self.assertEqual(self.errors(), [])

        raw_visual = (self.episode / "视觉设定.md").read_bytes().decode("utf-8")
        helper_errs: list[str] = []
        entries = check._visual_entries(raw_visual, helper_errs)
        locks = check._continuity_locks(raw_visual, helper_errs)
        self.assertEqual(helper_errs, [])
        self.assertTrue(any(entry.name == "江晨" for entry in entries))
        self.assertTrue(any(lock.lock_id == "LOCK-JIANGCHEN-DRESS" for lock in locks))

    def test_inside_resolves_relative_and_symlinked_project_roots(self) -> None:
        from tests import test_voice_reference_binding as voice

        episode = voice.bound_episode(self.project)
        with tempfile.TemporaryDirectory() as link_parent:
            symlink_root = Path(link_parent) / "linked_project"
            try:
                symlink_root.symlink_to(self.project, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            self.assertEqual(
                check.validate_episode(symlink_root / "剧集/EP001", symlink_root),
                [],
            )

        previous_cwd = Path.cwd()
        try:
            os.chdir(self.project)
            self.assertEqual(
                check.validate_episode(Path("剧集/EP001"), Path(".")),
                [],
            )
        finally:
            os.chdir(previous_cwd)

        with tempfile.TemporaryDirectory() as outside_dir:
            outside_file = Path(outside_dir) / "outside.png"
            outside_file.write_bytes(b"PNG")
            escaped_link = self.project / "输入/参考图/越界软链.png"
            try:
                escaped_link.symlink_to(outside_file)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            board_path = episode / "分镜.md"
            board_path.write_text(
                board_path.read_text(encoding="utf-8").replace(
                    voice.PICTURE_PATH, "输入/参考图/越界软链.png", 1
                ),
                encoding="utf-8",
            )
            escape_errors = check.validate_episode(episode, self.project)
            self.assertTrue(
                any("越出项目根目录" in err for err in escape_errors), escape_errors
            )

    def test_cast_lines_in_screenplay_do_not_swallow_dialogue_or_create_fake_speaker(self) -> None:
        raw = (
            "# EP001\n\n"
            "人物：许棠、顾沉\n\n"
            "## EP001-SC001 内 · 走廊 · 夜\n"
            "- **人物：**许棠、顾沉\n"
            "许棠：站住。\n"
        )
        speakers = check._screenplay_dialogue(raw)
        self.assertEqual(speakers, {"许棠"})

        script_path = self.episode / "剧本.md"
        base = script_path.read_text(encoding="utf-8")
        injected = "人物：江晨、周薄森\n\n" + base.replace(
            "## EP001-SC001 内 · 副团长办公室 · 日\n",
            "## EP001-SC001 内 · 副团长办公室 · 日\n- **人物：**江晨、周薄森\n",
            1,
        )
        script_path.write_text(injected, encoding="utf-8")
        self.assertEqual(self.errors(), [])

    def test_scene_heading_spacing_unclosed_comments_inline_code_and_emphasized_fields(self) -> None:
        script_path = self.episode / "剧本.md"
        base_script = script_path.read_text(encoding="utf-8")

        # Missing separator between SC001 and 内 is rejected.
        script_path.write_text(
            base_script.replace("EP001-SC001 内 ·", "EP001-SC001内 ·", 1),
            encoding="utf-8",
        )
        self.assertTrue(any("场景标题必须写成" in err for err in self.errors()))

        # Malformed H2 in 剧本.md without SC<digits> is rejected instead of slipping through.
        script_path.write_text(base_script + "\n## 幕间过渡\n\n走廊灯暗。\n", encoding="utf-8")
        self.assertTrue(any("幕间过渡" in err and "场景标题必须写成" in err for err in self.errors()))
        script_path.write_text(base_script, encoding="utf-8")

        # Inline backtick code span containing `<!--` does not strip subsequent sections,
        # while an unclosed `<!--` outside fences/copyable blocks reports a clear error.
        visual_path = self.episode / "视觉设定.md"
        base_visual = visual_path.read_text(encoding="utf-8")
        visual_with_code = (
            base_visual.replace(
                "- 提示词名称：Jiangchen",
                "- ***提示词名称***：\u3000Jiangchen",
                1,
            ).replace(
                "- 提示词名称：Zhoubosen",
                "- **提示词名称：**Zhoubosen",
                1,
            )
            + "\n## 备注\n- 说明：保留行内 `` `<!-- 字面量` `` 标记。\n- 12:00 走廊换灯。\n"
        )
        visual_path.write_text(visual_with_code, encoding="utf-8")
        self.assertEqual(self.errors(), [])

        field_errs: list[str] = []
        parsed_fields = check._fields(
            "- **甲**与**乙**：并列项\n- 12:00 准点打卡\n- ***标识***：OK\n",
            owner="TEST",
            errors=field_errs,
        )
        self.assertEqual(field_errs, [])
        self.assertEqual(parsed_fields.get("**甲**与**乙**"), "并列项")
        self.assertEqual(parsed_fields.get("标识"), "OK")
        self.assertNotIn("12", parsed_fields)

        visual_path.write_text(visual_with_code + "\n<!-- 未闭合注释\n", encoding="utf-8")
        unclosed_errors = self.errors()
        self.assertTrue(
            any("视觉设定.md" in err and "未闭合的 HTML 注释" in err for err in unclosed_errors),
            unclosed_errors,
        )

    def test_soft_gate_cli_prints_warnings_and_exits_zero_without_hard_errors(self) -> None:
        visual_path = self.episode / "视觉设定.md"
        visual_path.write_text(
            re.sub(r"^- 提示词名称：[^\n]*\n", "", visual_path.read_text(encoding="utf-8"), flags=re.MULTILINE),
            encoding="utf-8",
        )
        result = check.validate_episode_with_warnings(self.episode, self.project)
        self.assertEqual(result.errors, [])
        self.assertTrue(result.warnings)
        texts = {name: (self.episode / name).read_text(encoding="utf-8") for name in check.REQUIRED_DOCUMENTS}
        self.assertEqual(check.collect_warnings(texts, self.project), result.warnings)

        cli = subprocess.run(
            [
                sys.executable,
                str(ROOT / "skills/short-drama/scripts/creator_markdown_check.py"),
                str(self.episode),
                "--project-root",
                str(self.project),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertIn("WARNING:", cli.stdout)
        self.assertIn("OK:", cli.stdout)

    def test_image_reference_accepts_parenthetical_none_and_tail_frame_catches_extra_spaces(self) -> None:
        base_img = (self.episode / "图片提示词.md").read_text(encoding="utf-8")
        for ok_ref in (
            "- 参考：无（纯文生图）",
            "- 参考：无（纯文生图）。",
            "- 参考：无外部参考（首次建卡）",
            "- 参考：无外部参考（首次建卡）；三视图保持同一脸型。",
            "- 参考：无(pure t2i)",
        ):
            with self.subTest(ok_ref=ok_ref):
                mutated = base_img.replace(
                    "- 参考：无外部参考；三视图必须保持同一脸型、身高比例和服装细节。",
                    ok_ref,
                    1,
                )
                (self.episode / "图片提示词.md").write_text(mutated, encoding="utf-8")
                self.assertEqual(self.errors(), [])
        (self.episode / "图片提示词.md").write_text(base_img, encoding="utf-8")

        base_board = (self.episode / "分镜.md").read_text(encoding="utf-8")
        for heading in ("###  尾帧提示词", "###\u3000尾帧提示词", "###\t尾帧提示词"):
            with self.subTest(heading=repr(heading)):
                mutated_board = base_board.replace(
                    "## SHOT-EP001-002",
                    f"{heading}\n\n## SHOT-EP001-002",
                    1,
                )
                (self.episode / "分镜.md").write_text(mutated_board, encoding="utf-8")
                errs = self.errors()
                self.assertTrue(
                    any("SHOT-EP001-001" in err and "尾帧提示词" in err for err in errs),
                    errs,
                )

    def test_music_sections_validate_cleanly_and_dead_helpers_are_removed(self) -> None:
        for removed in ("_HTML_COMMENT_RE", "_han_key", "_LEADING_LANG_TAG_RE", "_dialogue_key", "SpokenLine", "VisualBasis"):
            self.assertFalse(hasattr(check, removed), removed)

        videos_path = self.episode / "视频提示词.md"
        base_video = videos_path.read_text(encoding="utf-8")
        music_section = (
            "\n## MUSIC-EP001-01 · 办公室悬念铺底\n"
            "- 用途：对峙铺底\n"
            "- 区间：SHOT-EP001-001 至 SHOT-EP001-005\n"
            "- 时长：15s\n\n"
            "### 可复制提示词\n"
            "> Minimalist tense cello pulse, dry room resonance, no vocals.\n"
        )
        videos_path.write_text(base_video + music_section, encoding="utf-8")
        self.assertEqual(self.errors(), [])

        videos_path.write_text(base_video + music_section + music_section, encoding="utf-8")
        self.assertIn("视频提示词.md: MUSIC 标题 ID 重复", self.errors())

        videos_path.write_text(
            base_video + "\n## MUSIC-EP001-02 · 空提示词\n- 用途：过场\n\n### 可复制提示词\n\n",
            encoding="utf-8",
        )
        errs = self.errors()
        self.assertTrue(any("MUSIC-EP001-02" in err and "可复制提示词" in err for err in errs), errs)


if __name__ == "__main__":
    unittest.main()
