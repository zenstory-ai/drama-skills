"""Source-relative editorial selection must not change generation duration."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.test_creator_first_golden import EPISODE, creator_markdown_check


class EditorialRangeTests(unittest.TestCase):
    def check(self, shot=None, motion=None, shot_duration="5s", motion_duration="5s"):
        with tempfile.TemporaryDirectory() as directory:
            episode = Path(directory) / "EP001"
            shutil.copytree(EPISODE, episode)
            for name, selection, duration in (
                ("分镜.md", shot, shot_duration),
                ("视频提示词.md", motion, motion_duration),
            ):
                path = episode / name
                content = path.read_text(encoding="utf-8")
                metadata = "" if duration is None else f"- 时长：{duration}\n"
                if selection is not None:
                    metadata += f"- 入剪区间：{selection}\n"
                content = re.sub(r"^- 时长：[^\n]+\n", lambda _: metadata,
                                 content, count=1, flags=re.MULTILINE)
                path.write_text(content, encoding="utf-8")
            return creator_markdown_check.validate_episode(episode, episode)

    def test_legacy_and_valid_numeric_selections(self):
        for shot, motion in ((None, None), ("0-5s", "0.0-5.00s"),
                             ("0.5-2s", "0.50-2.0s"),
                             ("0-0.0001s", "0.0000-0.00010s")):
            with self.subTest(shot=shot, motion=motion):
                self.assertEqual(self.check(shot, motion), [])

    def test_invalid_selection_is_rejected_on_either_side(self):
        for value in ("", "-1-2s", "2-2s", "3-2s", "0-5.01s", "NaN-2s",
                      "0-Infinitys", "0-2e0s", "0-2", "start-end", "0-2s trailing"):
            for side in ("shot", "motion"):
                with self.subTest(value=value, side=side):
                    args = {"shot": "0-2s", "motion": "0-2s", side: value}
                    self.assertTrue(self.check(**args))

    def test_ranges_must_be_paired_and_equal(self):
        for shot, motion in ((None, "0-2s"), ("0-2s", None), ("0-2s", "1-3s")):
            with self.subTest(shot=shot, motion=motion):
                self.assertTrue(self.check(shot, motion))

    def test_source_duration_is_required_positive_and_equal_when_selecting(self):
        for duration in (None, "", "0s", "-1s", "NaNs", "Infinitys", "5", "5e0s", "6s"):
            for side in ("shot_duration", "motion_duration"):
                with self.subTest(duration=duration, side=side):
                    self.assertTrue(self.check("0-2s", "0-2s", **{side: duration}))
        self.assertEqual(self.check("0-2s", "0-2s", "5.0s", "5.00s"), [])

    def test_duplicate_timing_fields_are_ambiguous(self):
        for value in ("0-2s\n- 入剪区间：0-2s", "\n- 入剪区间：0-2s",
                      "0-2s\n- 时长：5s", "0-2s\n- 时长："):
            for side in ("shot", "motion"):
                with self.subTest(value=value, side=side):
                    args = {"shot": "0-2s", "motion": "0-2s", side: value}
                    self.assertTrue(self.check(**args))
