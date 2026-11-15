import os
import re
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
        "short-drama-breakdown",
        "short-drama-develop",
        "short-drama-edit",
        "short-drama-novel-analyze",
        "short-drama-produce",
        "short-drama-write",
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

    def test_every_skill_runs_a_selftest_when_copied_alone(self) -> None:
        for name in sorted(self.SELFTEST_SKILLS):
            with self.subTest(skill=name):
                selftest = self.run_in_copy(
                    name, "scripts/selftest.py", optimize=True
                )
                self.assertEqual(selftest.returncode, 0, selftest.stderr)
                self.assertIn("self-tests passed", selftest.stdout)

    def test_quick_starts_expose_only_local_commands(self) -> None:
        script_ref_re = re.compile(r"\b((?:scripts|tools)/[A-Za-z0-9_/-]+\.py)\b")
        for name in sorted(self.SELFTEST_SKILLS):
            with self.subTest(skill=name):
                skill_dir = SKILLS / name
                document = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
                match = re.match(r"^---\n([\s\S]+?)\n---\n([\s\S]+)$", document)
                self.assertIsNotNone(match, f"{name}/SKILL.md missing YAML frontmatter")
                assert match is not None
                frontmatter, body = match.groups()
                fields = {
                    key.strip(): value.strip()
                    for line in frontmatter.splitlines()
                    if ":" in line
                    for key, value in [line.split(":", 1)]
                }
                self.assertEqual(fields.get("name"), name)
                self.assertTrue(fields.get("description"))
                self.assertTrue(re.findall(r"^##\s+\S+", body, re.MULTILINE))

                referenced_scripts = sorted(set(script_ref_re.findall(body)))
                self.assertTrue(
                    referenced_scripts,
                    f"{name}/SKILL.md exposes no local script commands",
                )
                for rel_script in referenced_scripts:
                    self.assertTrue(
                        (skill_dir / rel_script).is_file(),
                        f"{name}/SKILL.md references non-local command {rel_script}",
                    )
                    if rel_script != "scripts/selftest.py":
                        help_run = self.run_in_copy(name, rel_script, "--help")
                        self.assertEqual(help_run.returncode, 0, help_run.stderr)


if __name__ == "__main__":
    unittest.main()
