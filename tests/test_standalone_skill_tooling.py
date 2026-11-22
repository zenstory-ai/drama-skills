import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"


def _minimal_png(width: int = 16, height: int = 28) -> bytes:
    """Build a valid tiny RGB PNG using only the Python standard library."""
    raw = b"".join(b"\x00" + b"\x20\x40\x60" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class StandaloneSkillToolingTests(unittest.TestCase):
    SCRIPTED_SKILLS = {
        "short-drama",
        "short-drama-breakdown",
        "short-drama-develop",
        "short-drama-edit",
        "short-drama-novel-analyze",
        "short-drama-produce",
        "short-drama-write",
    }

    def run_in_isolated_copy(
        self,
        root: Path,
        name: str,
        *arguments: str,
        optimize: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        skill = root / f"isolated {name}"
        if not skill.exists():
            shutil.copytree(SKILLS / name, skill)
        outside = root / "unrelated cwd"
        outside.mkdir(exist_ok=True)
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

    def run_in_copy(
        self, name: str, *arguments: str, optimize: bool = False
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            return self.run_in_isolated_copy(
                Path(directory), name, *arguments, optimize=optimize
            )

    def test_no_skill_ships_bundled_selftest_scripts(self) -> None:
        bundled = sorted(
            str(path.relative_to(SUITE))
            for path in SKILLS.glob("*/scripts/selftest.py")
        )
        self.assertEqual(bundled, [])

    def test_every_scripted_skill_runs_business_smoke_when_copied_alone(self) -> None:
        with self.subTest(skill="short-drama"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "smoke-project"
            init_run = self.run_in_isolated_copy(
                root,
                "short-drama",
                "scripts/project_tool.py",
                "init",
                str(project),
                "--title",
                "孤立冒烟",
                "--language",
                "zh-CN",
                "--aspect-ratio",
                "9:16",
                optimize=True,
            )
            self.assertEqual(init_run.returncode, 0, init_run.stderr)
            status_run = self.run_in_isolated_copy(
                root,
                "short-drama",
                "scripts/project_tool.py",
                "status",
                str(project),
                optimize=True,
            )
            self.assertEqual(status_run.returncode, 0, status_run.stderr)
            status = json.loads(status_run.stdout)
            self.assertEqual(status["title"], "孤立冒烟")
            for helper in ("scripts/creator_markdown_check.py", "scripts/dashboard_server.py"):
                help_run = self.run_in_isolated_copy(root, "short-drama", helper, "--help", optimize=True)
                self.assertEqual(help_run.returncode, 0, help_run.stderr)

        with self.subTest(skill="short-drama-novel-analyze"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            novel = root / "novel.txt"
            novel.write_text(
                "第一章 雨夜\n" + "雨水打在旧码头的铁门上。" * 10 + "\n"
                "第二章 船票\n" + "售票窗里透出昏黄灯光。" * 10 + "\n",
                encoding="utf-8",
            )
            out = root / "_index.json"
            run = self.run_in_isolated_copy(
                root,
                "short-drama-novel-analyze",
                "scripts/novel_index.py",
                "index",
                str(novel),
                "--out",
                str(out),
                optimize=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["chapter_count"], 2)

        with self.subTest(skill="short-drama-develop"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episodes = root / "episodes.txt"
            episodes.write_text(
                "第1集 雨夜渡口\n售票窗熄了灯。\n\n第2集 末班船\n汽笛在雾里响起。\n",
                encoding="utf-8",
            )
            out_dir = root / "intake"
            run = self.run_in_isolated_copy(
                root,
                "short-drama-develop",
                "scripts/episode_intake.py",
                "index",
                str(episodes),
                "--out",
                str(out_dir),
                optimize=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["episode_count"], 2)

        with self.subTest(skill="short-drama-write"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script_path = root / "剧本.md"
            script_path.write_text(
                "# EP001 冒烟\n\n人物：许棠\n\n## EP001-SC001 内 · 监控室 · 夜\n\n"
                "监视器画面忽然闪烁。\n\n许棠：把电源切回备用线路。\n",
                encoding="utf-8",
            )
            run = self.run_in_isolated_copy(
                root,
                "short-drama-write",
                "scripts/duration_estimate.py",
                "--script",
                str(script_path),
                optimize=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["counts"]["dialogue_lines"], 1)

        with self.subTest(skill="short-drama-produce"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "prod-project"
            project.mkdir()
            (project / "short-drama.json").write_text(
                json.dumps({"title": "冒烟", "format": {"aspect_ratio": "9:16"}}),
                encoding="utf-8",
            )
            audit_run = self.run_in_isolated_copy(
                root,
                "short-drama-produce",
                "scripts/production_tool.py",
                "audit",
                str(project),
                optimize=True,
            )
            self.assertEqual(audit_run.returncode, 0, audit_run.stderr)
            audit = json.loads(audit_run.stdout)
            self.assertIn("jobs", audit)
            adapter_help = self.run_in_isolated_copy(
                root,
                "short-drama-produce",
                "scripts/provider_adapters.py",
                "--help",
                optimize=True,
            )
            self.assertEqual(adapter_help.returncode, 0, adapter_help.stderr)

        with self.subTest(skill="short-drama-edit"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "edit-project"
            ep = project / "剧集/EP001"
            media = ep / "制作成果/frames"
            media.mkdir(parents=True)
            (media / "shot1.png").write_bytes(_minimal_png(16, 28))
            (ep / "分镜.md").write_text(
                "# EP001 分镜\n\n## SHOT-EP001-001 · 开场定格\n- 时长：2s\n",
                encoding="utf-8",
            )
            (ep / "剪辑单.md").write_text(
                "# EP001 剪辑单\n\n"
                "- 目标时长：2s\n"
                "- 画幅与帧率：16×28 · 24fps\n"
                "- 交付响度：-16 LUFS，真峰值不超过 -1 dBTP\n"
                "- 字幕：无\n\n"
                "## CUT-EP001-001 · 开场定格\n"
                "- 来源：SHOT-EP001-001 · 剧集/EP001/制作成果/frames/shot1.png\n"
                "- 入点：0.00\n"
                "- 出点：2.00\n"
                "- 时长：2.00\n"
                "- 取舍：冒烟验证静帧剪辑单解析。\n",
                encoding="utf-8",
            )
            check_run = self.run_in_isolated_copy(
                root,
                "short-drama-edit",
                "scripts/edit_tool.py",
                "check",
                str(ep),
                "--project-root",
                str(project),
                "--partial",
                optimize=True,
            )
            self.assertEqual(check_run.returncode, 0, check_run.stderr)

        with self.subTest(skill="short-drama-breakdown"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            measure_dir = root / "measure"
            measure_dir.mkdir()
            (measure_dir / "EP001.measure.json").write_text(
                json.dumps(
                    {
                        "source": "EP001.mp4",
                        "duration": 60.0,
                        "width": 1080,
                        "height": 1920,
                        "fps": 24.0,
                        "shots": [{"index": 1, "start": 0.0, "end": 60.0, "duration": 60.0}],
                    }
                ),
                encoding="utf-8",
            )
            profile_run = self.run_in_isolated_copy(
                root,
                "short-drama-breakdown",
                "scripts/breakdown_tool.py",
                "profile",
                f"REF={measure_dir}",
                "--json",
                optimize=True,
            )
            self.assertEqual(profile_run.returncode, 0, profile_run.stderr)
            profile = json.loads(profile_run.stdout)
            self.assertIn("REF", profile)

    def test_quick_starts_expose_only_local_commands(self) -> None:
        script_ref_re = re.compile(r"\b((?:scripts|tools)/[A-Za-z0-9_/-]+\.py)\b")
        for name in sorted(self.SCRIPTED_SKILLS):
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
                    help_run = self.run_in_copy(name, rel_script, "--help")
                    self.assertEqual(help_run.returncode, 0, help_run.stderr)

    def test_skill_docs_only_reference_registered_cli_subcommands(self) -> None:
        command_re = re.compile(
            r"<PYTHON>\s+<SKILL_DIR>/(scripts/[A-Za-z0-9_/-]+\.py)\s+([a-z][a-z0-9-]*)\b"
        )
        probe_code = (
            "import argparse, contextlib, io, json, runpy, sys\n"
            "found = []\n"
            "orig_add = argparse._SubParsersAction.add_parser\n"
            "def spy_sub(self, name, *a, **kw):\n"
            "    found.append(name)\n"
            "    for alias in kw.get('aliases', ()):\n"
            "        found.append(alias)\n"
            "    return orig_add(self, name, *a, **kw)\n"
            "argparse._SubParsersAction.add_parser = spy_sub\n"
            "orig_arg = argparse.ArgumentParser.add_argument\n"
            "def spy_arg(self, *a, **kw):\n"
            "    if a and not str(a[0]).startswith('-') and kw.get('choices') and not found:\n"
            "        found.extend(str(c) for c in kw['choices'])\n"
            "    return orig_arg(self, *a, **kw)\n"
            "argparse.ArgumentParser.add_argument = spy_arg\n"
            "script = sys.argv[1]\n"
            "sys.argv = [script, '--help']\n"
            "with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):\n"
            "    try:\n"
            "        runpy.run_path(script, run_name='__main__')\n"
            "    except SystemExit:\n"
            "        pass\n"
            "print(json.dumps(sorted(set(found))))\n"
        )
        registered_cache: dict[Path, set[str]] = {}
        checked_pairs = 0
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            skill_dir = skill_md.parent
            body = skill_md.read_text(encoding="utf-8")
            documented = sorted(set(command_re.findall(body)))
            for rel_script, subcommand in documented:
                script_path = skill_dir / rel_script
                self.assertTrue(
                    script_path.is_file(),
                    f"{skill_md.relative_to(SUITE)} references missing script {rel_script}",
                )
                if script_path not in registered_cache:
                    env = os.environ.copy()
                    env["PYTHONDONTWRITEBYTECODE"] = "1"
                    run = subprocess.run(
                        [sys.executable, "-c", probe_code, str(script_path)],
                        env=env,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    registered_cache[script_path] = set(json.loads(run.stdout))
                with self.subTest(
                    skill=skill_dir.name, script=rel_script, subcommand=subcommand
                ):
                    self.assertIn(
                        subcommand,
                        registered_cache[script_path],
                        f"{skill_md.relative_to(SUITE)} documents unknown subcommand "
                        f"{subcommand!r} for {rel_script} "
                        f"(registered: {sorted(registered_cache[script_path])})",
                    )
                    checked_pairs += 1
        self.assertGreater(
            checked_pairs, 0, "expected SKILL.md CLI subcommands to be verified"
        )


if __name__ == "__main__":
    unittest.main()
