import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"


class StandaloneSkillToolingTests(unittest.TestCase):
    SELFTEST_SKILLS = {
        "short-drama",
        "short-drama-assets",
        "short-drama-develop",
        "short-drama-edit",
        "short-drama-image-prompts",
        "short-drama-novel-analyze",
        "short-drama-produce",
        "short-drama-review",
        "short-drama-storyboard",
        "short-drama-video-prompts",
        "short-drama-write",
    }
    CASES = {
        "short-drama-assets": {
            "checker": "asset_check.py",
            "args": [
                "--characters",
                "examples/minimal/characters.jsonl",
                "--looks",
                "examples/minimal/looks.jsonl",
            ],
        },
        "short-drama-image-prompts": {
            "checker": "image_prompt_check.py",
            "args": ["examples/minimal-image-prompt-specs.jsonl"],
        },
        "short-drama-review": {
            "checker": "review_check.py",
            "args": [
                "--findings",
                "examples/minimal-findings.jsonl",
                "--verdict",
                "examples/minimal-verdict.json",
            ],
        },
        "short-drama-video-prompts": {
            "checker": "music_spec_check.py",
            "args": ["examples/minimal-music-specs.jsonl"],
        },
    }

    def run_in_copy(
        self, name: str, *arguments: str, optimize: bool = False
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "isolated skill"
            shutil.copytree(SKILLS / name, skill)
            outside = root / "unrelated cwd"
            outside.mkdir()
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            script, *script_arguments = arguments
            return subprocess.run(
                [
                    sys.executable,
                    *(["-O"] if optimize else []),
                    str(skill / script),
                    *script_arguments,
                ],
                cwd=outside,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

    def test_each_skill_runs_its_checker_and_selftest_when_copied_alone(self) -> None:
        for name, case in self.CASES.items():
            with self.subTest(skill=name):
                skill = SKILLS / name
                checker = skill / "scripts" / case["checker"]
                result = self.run_in_copy(
                    name,
                    str(Path("scripts") / case["checker"]),
                    *case["args"],
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                summary = json.loads(result.stdout)
                self.assertEqual(summary["status"], "valid")

                self.assertTrue(checker.is_file())

    def test_every_skill_runs_a_selftest_when_copied_alone(self) -> None:
        for name in sorted(self.SELFTEST_SKILLS):
            with self.subTest(skill=name):
                selftest = self.run_in_copy(
                    name, "scripts/selftest.py", optimize=True
                )
                self.assertEqual(selftest.returncode, 0, selftest.stderr)
                self.assertIn("self-tests passed", selftest.stdout)

    def test_quick_starts_expose_only_local_commands(self) -> None:
        for name in sorted(self.SELFTEST_SKILLS):
            with self.subTest(skill=name):
                document = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("## Quick Start", document)
                self.assertIn("scripts/selftest.py", document)
                self.assertNotIn("tools/verify_suite.py", document)


if __name__ == "__main__":
    unittest.main()
