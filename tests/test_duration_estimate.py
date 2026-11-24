"""Behavioral tests for duration_estimate.py partial-speech and tag-count consistency."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama-write/scripts/duration_estimate.py"
SPEC = importlib.util.spec_from_file_location("duration_estimate_unit", SCRIPT)
assert SPEC and SPEC.loader
duration_estimate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(duration_estimate)


class LoanwordPartialSpeechTests(unittest.TestCase):
    """Chinese scripts with occasional Latin loanwords must keep priced speech timing."""

    ZH_ONLY_PROJECT: dict[str, Any] = {
        "format": {
            "pacing": {
                "spoken_characters_per_second": 4.0,
                "seconds_per_action_paragraph": 2.0,
            }
        }
    }

    def _estimate(
        self,
        body: str,
        project: dict[str, Any] | None = None,
        speakers: list[str] | None = None,
    ) -> dict[str, Any]:
        raw = ("# EP001\n\n## EP001-SC001 内 · 办公区 · 日\n\n" + body).encode("utf-8")
        blocks, review = duration_estimate.parse_script_blocks(
            raw, speakers=speakers or ["许棠", "齐曼"]
        )
        return duration_estimate.estimate(
            raw, blocks, project if project is not None else self.ZH_ONLY_PROJECT, review
        )

    def test_chinese_script_with_latin_loanwords_keeps_speech_seconds_and_share(self) -> None:
        # 1 action paragraph (2.0s) + 16 voiced Chinese chars (4.0s) + 3 unpriced Latin loanwords.
        body = (
            "许棠合上电脑推到桌角。\n\n"
            "许棠：这份offer和PPT今天必须交。\n\n"
            "齐曼：那你先去找VIP签字吧。\n"
        )
        report = self._estimate(body)
        self.assertEqual(report["counts"]["voiced_characters"], 16)
        self.assertEqual(report["counts"]["voiced_words"], 3)
        self.assertEqual(report["seconds"], 6.0)
        self.assertEqual(report["speech_seconds"], 4.0)
        self.assertEqual(report["speech_share"], round(4.0 / 6.0, 2))
        self.assertTrue(report["speech_partial"])
        self.assertEqual(report["untimed_speech"]["counts"], {"voiced_words": 3})

    def test_loanwords_with_word_rate_declared_report_full_speech_without_partial_flag(
        self,
    ) -> None:
        project = {
            "format": {
                "pacing": {
                    "spoken_characters_per_second": 4.0,
                    "spoken_words_per_second": 3.0,
                    "seconds_per_action_paragraph": 2.0,
                }
            }
        }
        body = (
            "许棠合上电脑推到桌角。\n\n"
            "许棠：这份offer和PPT今天必须交。\n\n"
            "齐曼：那你先去找VIP签字吧。\n"
        )
        report = self._estimate(body, project=project)
        self.assertEqual(report["speech_seconds"], 5.0)
        self.assertEqual(report["seconds"], 7.0)
        self.assertEqual(report["speech_share"], round(5.0 / 7.0, 2))
        self.assertNotIn("speech_partial", report)
        self.assertNotIn("untimed_speech", report)

    def test_all_unpriced_speech_still_omits_speech_seconds_and_share(self) -> None:
        body = "许棠合上电脑推到桌角。\n\n许棠：Send the offer now.\n"
        report = self._estimate(body)
        self.assertEqual(report["counts"]["voiced_characters"], 0)
        self.assertEqual(report["counts"]["voiced_words"], 4)
        self.assertEqual(report["seconds"], 2.0)
        self.assertIn("untimed_speech", report)
        self.assertNotIn("speech_seconds", report)
        self.assertNotIn("speech_share", report)
        self.assertNotIn("speech_partial", report)

    def test_cli_reports_partial_speech_for_zh_script_with_loanwords(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "剧本.md"
            project = root / "short-drama.json"
            script.write_text(
                "# EP001\n\n## EP001-SC001 内 · 办公区 · 日\n\n"
                "许棠：这份offer我接了。\n\n"
                "许棠：明天先把CEO签字拿回来。\n",
                encoding="utf-8",
            )
            project.write_text(json.dumps(self.ZH_ONLY_PROJECT), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "--script",
                    str(script),
                    "--project",
                    str(project),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["counts"]["voiced_words"], 2)
            self.assertTrue(report["speech_partial"])
            self.assertGreater(report["speech_seconds"], 0.0)
            self.assertEqual(report["speech_share"], 1.0)


class UntimedTagConsistencyTests(unittest.TestCase):
    """counts.untimed_tag_lines and untimed.tag_lines must stay consistent."""

    def test_declared_on_screen_text_rate_removes_screen_text_from_both_untimed_maps(
        self,
    ) -> None:
        project = {
            "format": {
                "pacing": {
                    "spoken_characters_per_second": 4.0,
                    "seconds_per_action_paragraph": 2.0,
                    "on_screen_text_characters_per_second": 5.0,
                }
            }
        }
        raw = (
            "# EP001\n\n## EP001-SC001 内 · 售票室 · 夜\n\n"
            "[画面文字] 停航通知：今晚十点\n\n"
            "[SFX] 江面传来短促汽笛。\n"
        ).encode("utf-8")
        blocks, review = duration_estimate.parse_script_blocks(raw)
        report = duration_estimate.estimate(raw, blocks, project, review)
        self.assertEqual(report["untimed"]["tag_lines"], {"SFX": 1})
        self.assertEqual(report["counts"]["untimed_tag_lines"], {"SFX": 1})
        self.assertEqual(report["counts"]["on_screen_text_characters"], 8)
        self.assertEqual(report["on_screen_text_seconds"], 1.6)

    def test_only_on_screen_text_with_declared_rate_clears_both_untimed_entries(self) -> None:
        project = {
            "format": {
                "pacing": {
                    "spoken_characters_per_second": 4.0,
                    "seconds_per_action_paragraph": 2.0,
                    "on_screen_text_characters_per_second": 5.0,
                }
            }
        }
        raw = (
            "# EP001\n\n## EP001-SC001 内 · 售票室 · 夜\n\n"
            "[画面文字] 停航通知：今晚十点\n"
        ).encode("utf-8")
        blocks, review = duration_estimate.parse_script_blocks(raw)
        report = duration_estimate.estimate(raw, blocks, project, review)
        self.assertNotIn("untimed", report)
        self.assertNotIn("untimed_tag_lines", report["counts"])
        self.assertEqual(report["on_screen_text_seconds"], 1.6)

    def test_undeclared_pacing_keeps_screen_text_untimed_in_both_maps(self) -> None:
        project = {
            "format": {
                "pacing": {
                    "on_screen_text_characters_per_second": 5.0,
                }
            }
        }
        raw = (
            "# EP001\n\n## EP001-SC001 内 · 售票室 · 夜\n\n"
            "[画面文字] 停航通知：今晚十点\n"
        ).encode("utf-8")
        blocks, review = duration_estimate.parse_script_blocks(raw)
        report = duration_estimate.estimate(raw, blocks, project, review)
        self.assertIsNone(report["seconds"])
        self.assertEqual(report["untimed"]["tag_lines"], {"画面文字": 1})
        self.assertEqual(report["counts"]["untimed_tag_lines"], {"画面文字": 1})


if __name__ == "__main__":
    unittest.main()
