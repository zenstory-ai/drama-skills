"""Partial checks, in-frame lock scope and delivery groups in creator_markdown_check.

Each case starts from the shipped creator-first episode, which passes the full
check, and changes one thing.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
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
        return check._copyable_prompt(check._sections(board, "SHOT")[shot_id], heading="冻结关键帧提示词")


class PartialCheckTests(EpisodeCase):
    def test_default_still_requires_all_five_documents(self) -> None:
        self.drop("视频提示词.md")
        self.assertEqual(self.errors(), ["缺少创作文档: 视频提示词.md"])

    def test_storyboard_defects_surface_before_video_prompts_exist(self) -> None:
        # The coverage rule (SHT-26) used to be reachable only once the last
        # document was written; a storyboard-stage run now sees it.
        self.drop("视频提示词.md")
        self.assertEqual(self.errors(partial=True), [])
        self.edit("分镜.md", "·人物「江晨」（控制：身份、体态、本集造型）；人物「周薄森」", "·人物「周薄森」")
        errors = self.errors(partial=True)
        self.assertTrue(any("SHOT-EP001-002" in error and "江晨" in error for error in errors), errors)
        self.assertFalse(any("MOTION" in error for error in errors), errors)

    def test_asset_stage_checks_image_prompts_against_locks(self) -> None:
        self.drop("分镜.md", "视频提示词.md")
        self.assertEqual(self.errors(partial=True), [])
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        locked = re.search(r"连续性锁：LOCK-JIANGCHEN-DRESS[^\n]*图片提示词项：(IMG-[A-Z0-9-]+)", visual)
        assert locked
        self.edit("图片提示词.md", SURFACE, "olive field jacket")
        errors = self.errors(partial=True)
        self.assertIn(f"LOCK-JIANGCHEN-DRESS: {locked.group(1)} 可复制提示词缺少锁面", errors)

    def test_missing_upstream_is_skipped_rather_than_reported(self) -> None:
        # Without 剧本.md the shots' scene ids and quotes cannot be resolved;
        # that is not the same as being wrong.
        self.drop("剧本.md", "视频提示词.md")
        self.assertEqual(self.errors(partial=True), [])

    def test_motion_rules_still_run_without_a_storyboard(self) -> None:
        self.drop("分镜.md")
        self.edit("视频提示词.md", "- 输入参考图：无（创作者已明确选择文生视频）。", "- 输入参考图：REF-BROKEN", 1)
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

    def test_a_quote_from_a_missing_source_is_not_called_invented(self) -> None:
        board = (self.episode / "分镜.md").read_text(encoding="utf-8")
        line = re.search(r"^- 画面文字：([^\n]+)$", board, re.MULTILINE)
        assert line
        quote = re.search(r"[\u4e00-\u9fff]{4,}", line.group(1))
        assert quote
        self.edit("视频提示词.md", "No subtitles", f"屏幕上写着“{quote.group(0)}” No subtitles")
        self.assertEqual(self.errors(), [])
        self.drop("分镜.md")
        self.assertFalse(any("引文" in error for error in self.errors(partial=True)))

    def test_video_lock_checks_survive_a_missing_storyboard(self) -> None:
        self.drop("分镜.md")
        self.edit("视频提示词.md", SURFACE, "olive field jacket", count=-1)
        errors = self.errors(partial=True)
        self.assertTrue(any(error.startswith("LOCK-JIANGCHEN-DRESS: MOTION-") for error in errors), errors)

    def test_text_only_validation_does_not_guess_the_prompt_language(self) -> None:
        texts = {name: (self.episode / name).read_text(encoding="utf-8") for name in check.REQUIRED_DOCUMENTS}
        texts["视觉设定.md"] = re.sub(r"^- 画面代称：[^\n]*\n", "", texts["视觉设定.md"], flags=re.MULTILINE)
        self.assertFalse(any("画面代称" in error for error in check.validate_documents(texts, None)))

    def test_nothing_to_check_is_an_error(self) -> None:
        for name in check.REQUIRED_DOCUMENTS:
            (self.episode / name).unlink()
        self.assertEqual(self.errors(partial=True), ["没有可核对的创作文档"])


class InFrameLockTests(EpisodeCase):
    def use_in_frame_scope(self) -> None:
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        visual = re.sub(r"（镜头：SHOT-EP001-002[^；]*；", "（镜头：入画；", visual, count=1)
        (self.episode / "视觉设定.md").write_text(visual, encoding="utf-8")

    def test_scope_follows_the_shots_that_list_the_entry(self) -> None:
        self.use_in_frame_scope()
        flagged = {
            match.group(1)
            for error in self.errors()
            for match in [re.search(r"(SHOT-EP001-\d+) 冻结关键帧提示词缺少锁面", error)]
            if match
        }
        board = (self.episode / "分镜.md").read_text(encoding="utf-8")
        listing = {
            shot_id
            for shot_id, body in check._sections(board, "SHOT").items()
            if "人物「江晨」" in body
        }
        self.assertTrue(flagged)
        self.assertLessEqual(flagged, listing)
        for shot_id in flagged:
            self.assertNotIn(SURFACE, self.shot_keyframe(shot_id))
        for shot_id in listing - flagged:
            self.assertIn(SURFACE, self.shot_keyframe(shot_id))

    def test_a_misspelled_scope_is_caught_at_the_asset_stage(self) -> None:
        self.drop("分镜.md", "视频提示词.md")
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        visual = re.sub(r"（镜头：SHOT-EP001-002[^；]*；", "（镜头：入化；", visual, count=1)
        (self.episode / "视觉设定.md").write_text(visual, encoding="utf-8")
        self.assertTrue(any("入化" in error for error in self.errors(partial=True)))

    def test_in_frame_lock_outside_an_entry_is_rejected(self) -> None:
        visual = (self.episode / "视觉设定.md").read_text(encoding="utf-8")
        line = re.search(r"^- 连续性锁：LOCK-JIANGCHEN-DRESS[^\n]*$", visual, re.MULTILINE)
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
        line = re.search(r"^- 连续性锁：LOCK-JIANGCHEN-DRESS[^\n]*$", visual, re.MULTILINE)
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

    def test_the_submitted_body_answers_to_the_quote_rule(self) -> None:
        self.add_group(body="他说：“这句台词剧本里没有出现过”")
        self.assertTrue(any(error.startswith("GROUP-EP001-01: 可复制提示词的引文") for error in self.errors()))

    def test_the_submitted_body_carries_locks_of_its_members(self) -> None:
        body = self.body_of("MOTION-EP001-002").replace(SURFACE, "olive jacket")
        self.add_group(body=f"镜头1：{self.body_of('MOTION-EP001-001')} 镜头2：{body}")
        self.assertIn("LOCK-JIANGCHEN-DRESS: GROUP-EP001-01 可复制提示词缺少锁面", self.errors())

    def test_a_repeated_member_is_reported_not_collapsed(self) -> None:
        self.add_group(members="MOTION-EP001-001、MOTION-EP001-001、MOTION-EP001-002")
        self.assertIn("GROUP-EP001-01: 成员重复；一次交付里每个镜头只出现一次", self.errors())

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


if __name__ == "__main__":
    unittest.main()
