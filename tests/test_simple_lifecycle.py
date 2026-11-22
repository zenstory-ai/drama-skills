from __future__ import annotations

import hashlib
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
from unittest import mock


SUITE = Path(__file__).resolve().parents[1]
SKILL = SUITE / "skills/short-drama"
SCRIPT = SKILL / "scripts/project_tool.py"
SPEC = importlib.util.spec_from_file_location("simple_lifecycle", SCRIPT)
assert SPEC and SPEC.loader
project_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_tool)


class SimpleLifecycleTests(unittest.TestCase):
    def make_project(self, directory: str, *, chinese: bool = True) -> Path:
        root = Path(directory) / "project"
        project_tool.initialize_project(
            root,
            title="轻量短剧",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SKILL,
        )
        if not chinese:
            state_path = root / ".short-drama/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["project_layout_mode"] = "legacy"
            project_tool.atomic_json(state_path, state)
        return root

    def write_episode_file(
        self, root: Path, relative: str = "剧集/EP001/剧本.md", text: str = "# 第一集\n"
    ) -> Path:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def test_init_creates_small_state_and_creator_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            state = json.loads((root / ".short-drama/state.json").read_text(encoding="utf-8"))
            project = json.loads((root / "short-drama.json").read_text(encoding="utf-8"))
            self.assertEqual(state["schema_version"], "2.0")
            self.assertEqual(state["artifacts"], {})
            self.assertNotIn("current_checkpoint", project)
            self.assertNotIn("current_checkpoint", project_tool.project_status(root))
            self.assertNotIn("active_transaction", state)
            self.assertNotIn("blocked_transactions", state)
            for relative in ("输入", "项目开发", "设定集", "剧集", "交付", "创作者决策", "审查"):
                self.assertTrue((root / relative).is_dir(), relative)
            self.assertFalse((root / ".short-drama/transactions").exists())

    def test_init_keeps_confirmed_episode_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            result = project_tool.initialize_project(
                root,
                title="一分钟短剧",
                language="zh-CN",
                aspect_ratio="9:16",
                episode_count=1,
                target_seconds_per_episode=60,
                suite_root=SKILL,
            )
            self.assertEqual(result["project"]["format"]["episode_count"], 1)
            self.assertEqual(
                result["project"]["format"]["target_seconds_per_episode"], 60
            )

    def test_cli_exposes_only_active_creator_first_commands(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0)
        choices_match = re.search(r"\{([^}]+)\}", result.stdout)
        self.assertIsNotNone(choices_match, result.stdout)
        assert choices_match is not None
        commands = set(choices_match.group(1).split(","))
        self.assertEqual(
            commands,
            {"init", "configure", "scaffold-episode", "status", "package", "verify", "export"},
        )
        for retired in ("publish", "accept", "review", "set-authority", "recover"):
            self.assertNotIn(retired, commands)
        for removed_api in (
            "publish_candidate",
            "record_creator_acceptance",
            "record_review",
            "set_creator_authority",
            "record_independent_review",
            "project_layout",
        ):
            self.assertFalse(hasattr(project_tool, removed_api), removed_api)

    def test_cli_prints_readable_chinese_and_survives_a_non_utf8_stdout(self) -> None:
        # 创作者在终端里直接读 init/status 的输出；控制台编码不了中文时退成转义，JSON 仍可解析。
        for encoding, readable in (("utf-8", True), ("ascii", False)):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "项目"
                for args in (["init", str(root), "--title", "镖箱错账"], ["status", str(root)]):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), *args],
                        check=False,
                        capture_output=True,
                        encoding="utf-8",
                        env={**os.environ, "PYTHONIOENCODING": encoding},
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    payload = json.loads(result.stdout)
                    title = payload.get("title") or payload["project"]["title"]
                    self.assertEqual(title, "镖箱错账")
                    self.assertEqual("镖箱错账" in result.stdout, readable)

    def test_package_rejects_path_aliases_and_unsafe_episode_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            for relative in (
                "剧集/EP001/storyboard /shots.jsonl",
                "剧集/EP001/storyboard./shots.jsonl",
                "剧集/EP001/CON.json",
                "剧集/EP001/notes\nextra.md",
                "剧集/EP001/a:b.json",
            ):
                with self.subTest(relative=relative):
                    with self.assertRaisesRegex(ValueError, "unsafe project-relative path"):
                        project_tool.build_delivery_package(
                            root,
                            episode="EP001",
                            includes=[relative],
                        )

            with self.assertRaises(project_tool.NonPortablePathError):
                project_tool.build_delivery_package(
                    root,
                    episode="EP001",
                    includes=[
                        "剧集/EP001/notes.md",
                        "剧集/EP001/NOTES.md",
                    ],
                )

            composed = "剧集/EP001/caf\N{LATIN SMALL LETTER E WITH ACUTE}.md"
            decomposed = "剧集/EP001/cafe\N{COMBINING ACUTE ACCENT}.md"
            with self.assertRaisesRegex(
                project_tool.NonPortablePathError, "portable aliases"
            ):
                project_tool.build_delivery_package(
                    root,
                    episode="EP001",
                    includes=[composed, decomposed],
                )

            for bad_episode in ("1", "EP1", "../EP001", "第一集"):
                with self.subTest(bad_episode=bad_episode):
                    with self.assertRaisesRegex(ValueError, "EP001-style"):
                        project_tool.build_delivery_package(
                            root,
                            episode=bad_episode,
                            includes=["剧集/EP001/剧本.md"],
                        )
                    with self.assertRaisesRegex(ValueError, "EP001-style"):
                        project_tool.verify_delivery_package(root, episode=bad_episode)

    def test_package_rejects_cross_episode_includes_and_omissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.write_episode_file(root, "剧集/EP002/剧本.md", "# 第二集\n")
            with self.assertRaisesRegex(ValueError, "belong to EP001"):
                project_tool.build_delivery_package(
                    root,
                    episode="EP001",
                    includes=["剧集/EP002/剧本.md"],
                )

            self.write_episode_file(root, "剧集/EP001/剧本.md", "# 第一集\n")
            with self.assertRaisesRegex(ValueError, "belong to EP001"):
                project_tool.build_delivery_package(
                    root,
                    episode="EP001",
                    includes=["剧集/EP001/剧本.md"],
                    omissions={"剧集/EP002/notes.md": "not requested"},
                )

    def test_package_writes_the_same_bytes_it_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            initial = b"# first version\n"
            source = self.write_episode_file(root, "剧集/EP001/剧本.md", "")
            source.write_bytes(initial)
            real_sha256_bytes = project_tool.sha256_bytes

            def mutate_after_hash(content: bytes) -> str:
                digest = real_sha256_bytes(content)
                source.write_bytes(b"race bytes\n")
                return digest

            with mock.patch.object(
                project_tool, "sha256_bytes", side_effect=mutate_after_hash
            ):
                result = project_tool.build_delivery_package(
                    root,
                    episode="EP001",
                    includes=["剧集/EP001/剧本.md"],
                )
            delivered = root / result["delivery_root"] / "artifacts/剧集/EP001/剧本.md"
            self.assertEqual(delivered.read_bytes(), initial)

    def test_package_and_verify_selected_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.write_episode_file(root, "剧集/EP001/剧本.md")
            result = project_tool.build_delivery_package(
                root,
                episode="EP001",
                includes=["剧集/EP001/剧本.md"],
            )
            delivery = root / result["delivery_root"]
            self.assertTrue((delivery / "manifest.json").is_file())
            self.assertTrue((delivery / "checksums.sha256").is_file())
            self.assertTrue((delivery / "artifacts/剧集/EP001/剧本.md").is_file())
            verified = project_tool.verify_delivery_package(root, episode="EP001")
            self.assertEqual(verified, {"episode": "EP001", "status": "verified", "problems": []})

    def test_verify_detects_tamper_and_unlisted_addition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.write_episode_file(root, "剧集/EP001/剧本.md")
            result = project_tool.build_delivery_package(
                root, episode="EP001", includes=["剧集/EP001/剧本.md"]
            )
            delivery = root / result["delivery_root"]
            (delivery / "artifacts/剧集/EP001/剧本.md").write_text(
                "tampered", encoding="utf-8"
            )
            (delivery / "extra.md").write_text("extra", encoding="utf-8")
            verified = project_tool.verify_delivery_package(root, episode="EP001")
            self.assertEqual(verified["status"], "tampered")
            self.assertTrue(any("checksum mismatch" in item for item in verified["problems"]))
            self.assertTrue(any("unexpected delivery file" in item for item in verified["problems"]))

    def test_verify_checks_manifest_file_hashes_even_if_checksums_are_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.write_episode_file(root, "剧集/EP001/剧本.md")
            result = project_tool.build_delivery_package(
                root, episode="EP001", includes=["剧集/EP001/剧本.md"]
            )
            delivery = root / result["delivery_root"]
            artifact = delivery / "artifacts/剧集/EP001/剧本.md"
            artifact.write_text("laundered bytes", encoding="utf-8")
            members = [delivery / "manifest.json", artifact]
            checksums = "".join(
                f"{project_tool.sha256_file(path)}  {path.relative_to(delivery).as_posix()}\n"
                for path in members
            )
            (delivery / "checksums.sha256").write_text(checksums, encoding="utf-8")

            verified = project_tool.verify_delivery_package(root, episode="EP001")
            self.assertEqual(verified["status"], "tampered")
            self.assertTrue(
                any("manifest hash mismatch" in item for item in verified["problems"])
            )

    def test_verify_rejects_a_symlinked_delivery_parent(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            external = Path(directory) / "external-delivery"
            package = external / "EP001"
            package.mkdir(parents=True)
            (package / "checksums.sha256").write_text("", encoding="utf-8")
            (root / "交付").rmdir()
            try:
                (root / "交付").symlink_to(external, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            with self.assertRaisesRegex(
                project_tool.ProjectConflictError, "delivery root"
            ):
                project_tool.verify_delivery_package(root, episode="EP001")

    def test_package_replaces_a_previous_package_as_one_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.write_episode_file(root, "剧集/EP001/剧本.md", "# 第一集\n")
            project_tool.build_delivery_package(
                root, episode="EP001", includes=["剧集/EP001/剧本.md"]
            )
            self.write_episode_file(root, "剧集/EP001/剧本.md", "# 第一集\n第二版\n")
            project_tool.build_delivery_package(
                root, episode="EP001", includes=["剧集/EP001/剧本.md"]
            )
            delivered = root / "交付/EP001/artifacts/剧集/EP001/剧本.md"
            self.assertIn("第二版", delivered.read_text(encoding="utf-8"))
            self.assertFalse(any((root / "交付").glob(".EP001.*.old")))

    def test_package_records_explicit_omissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.write_episode_file(root, "剧集/EP001/剧本.md")
            project_tool.build_delivery_package(
                root,
                episode="EP001",
                includes=["剧集/EP001/剧本.md"],
                omissions={"剧集/EP001/notes.md": "not requested"},
            )
            manifest = json.loads((root / "交付/EP001/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["omitted"],
                [{"reason": "not requested", "source": "剧集/EP001/notes.md"}],
            )

    def test_status_never_exposes_hashes_or_creative_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.write_episode_file(root, "剧集/EP001/剧本.md", "秘密台词")
            serialized = json.dumps(project_tool.project_status(root), ensure_ascii=False)
            self.assertNotIn("秘密台词", serialized)
            self.assertIsNone(re.search(r"[0-9a-f]{64}", serialized))

    def test_coordinated_edit_rejects_an_old_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            target = root / "notes.md"
            target.write_text("one", encoding="utf-8")
            with self.assertRaisesRegex(project_tool.ProjectConflictError, "changed"):
                with project_tool.coordinated_project_text_edit(
                    root, "notes.md", hashlib.sha256(b"old").hexdigest()
                ):
                    pass
            if os.name != "nt":
                descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    with self.assertRaisesRegex(project_tool.ProjectConflictError, "changed"):
                        with project_tool.coordinated_project_text_edit_at(
                            descriptor, "notes.md", hashlib.sha256(b"old").hexdigest()
                        ):
                            pass
                finally:
                    os.close(descriptor)

    def test_cli_runs_init_configure_status_export_package_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cli-show"
            out = Path(directory) / "handover"
            init_cmd = [
                "init",
                str(root),
                "--title",
                "CLI 全链路",
                "--aspect-ratio",
                "9:16",
            ]
            result = subprocess.run(
                [sys.executable, str(SCRIPT), *init_cmd],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.write_episode_file(root, "剧集/EP001/剧本.md", "# 第一集\n")
            commands = [
                [
                    "configure",
                    str(root),
                    "--episode-count",
                    "12",
                    "--target-seconds",
                    "90",
                    "--pacing-json",
                    json.dumps(
                        {
                            "spoken_characters_per_second": 4.5,
                            "seconds_per_action_paragraph": 2.5,
                        }
                    ),
                ],
                ["status", str(root)],
                ["export", str(root), "--out", str(out)],
                ["package", str(root), "--episode", "EP001", "--include", "剧集/EP001/剧本.md"],
                ["verify", str(root), "--episode", "EP001"],
            ]
            for command in commands:
                res = subprocess.run(
                    [sys.executable, str(SCRIPT), *command],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertIsInstance(json.loads(res.stdout), dict)

    def test_configure_pacing_and_hand_edit_reporting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            project_tool.configure_project(
                root,
                pacing={
                    "spoken_characters_per_second": 5.0,
                    "seconds_per_action_paragraph": 2.5,
                },
            )
            manifest = root / "short-drama.json"
            written = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(written["format"]["pacing"]["spoken_characters_per_second"], 5.0)
            self.assertEqual(
                project_tool.project_status(root)["authority"], {"/format/pacing": "bound"}
            )

            edited = json.loads(manifest.read_text(encoding="utf-8"))
            edited["format"]["pacing"]["spoken_characters_per_second"] = 6.5
            project_tool.atomic_json(manifest, edited)
            self.assertEqual(
                project_tool.project_status(root)["authority"],
                {"/format/pacing": "hand_edited"},
            )

    def test_an_english_project_declares_only_a_word_rate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            project_tool.configure_project(root, target_seconds_per_episode=90)
            self.assertEqual(len(project_tool.project_status(root)["profile_notes"]), 1)
            project_tool.configure_project(
                root,
                pacing={
                    "spoken_words_per_second": 3.0,
                    "seconds_per_action_paragraph": 2.5,
                    "on_screen_text_characters_per_second": 5.0,
                },
            )
            self.assertEqual(project_tool.project_status(root)["profile_notes"], [])
            with self.assertRaisesRegex(ValueError, "positive number"):
                project_tool.configure_project(
                    root,
                    pacing={"on_screen_text_characters_per_second": 0},
                )
            with self.assertRaisesRegex(ValueError, "positive number"):
                project_tool.configure_project(
                    root,
                    pacing={"spoken_words_per_second": 0},
                )

    def test_episode_count_and_aspect_ratio_validation_via_configure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            project_tool.configure_project(root, episode_count=16, aspect_ratio="16:9")
            fmt = project_tool.project_status(root)["format"]
            self.assertEqual(fmt["episode_count"], 16)
            self.assertEqual(fmt["aspect_ratio"], "16:9")
            with self.assertRaisesRegex(ValueError, "positive integer"):
                project_tool.configure_project(root, episode_count=0)
            for bad in ("16/9", "0:9", "横屏"):
                with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "width:height"):
                    project_tool.configure_project(root, aspect_ratio=bad)
            self.assertEqual(project_tool.project_status(root)["format"]["aspect_ratio"], "16:9")

    def test_status_names_settings_that_cannot_hold_together(self) -> None:
        profile = {
            "form": "ai_live_action",
            "first_hook_seconds": 5,
            "beat_interval_seconds_max": 30,
            "opposed_reversals_per_episode_min": 1,
            "end_on_peak": True,
            "reprise_previous_last_beat": True,
            "vo_share_max": 0.3,
            "target_avg_shot_seconds": 2.5,
            "close_shot_share_min": 0.45,
            "first_major_payoff_by_episode": 1,
        }
        model = {
            "target_video_model": "seedance-2.0",
            "video_prompt_dialect": "seedance-2.0",
            "video_prompt_language": "zh-CN",
            "native_duration_seconds": {"min": 4, "max": 15},
            "supported_generation_modes": ["text"],
            "audio_generation": "same_pass",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.assertEqual(project_tool.project_status(root)["profile_notes"], [])
            project_tool.configure_project(
                root,
                rhythm_profile=profile,
                production_profile=model,
                target_seconds_per_episode=90,
            )
            notes = project_tool.project_status(root)["profile_notes"]
            self.assertEqual(len(notes), 2, notes)
            self.assertIn("2.5", notes[0])
            self.assertIn("format.pacing", notes[1])
            project_tool.configure_project(
                root,
                pacing={"spoken_characters_per_second": 4.5, "seconds_per_action_paragraph": 3},
            )
            self.assertEqual(len(project_tool.project_status(root)["profile_notes"]), 1)

    def test_choosing_multi_shot_containers_answers_the_shot_length_note(self) -> None:
        def manifest(containers: object) -> dict:
            choices: dict[str, object] = {"native_duration_seconds": {"min": 4, "max": 15}}
            if containers is not None:
                choices["multi_shot_containers"] = containers
            return {
                "creator_authority": {
                    "production_profile": {"status": "accepted", "choices": choices},
                    "rhythm_profile": {
                        "status": "accepted",
                        "form": "ai_live_action",
                        "first_hook_seconds": 5,
                        "beat_interval_seconds_max": 30,
                        "opposed_reversals_per_episode_min": 1,
                        "end_on_peak": True,
                        "reprise_previous_last_beat": True,
                        "vo_share_max": 0.3,
                        "target_avg_shot_seconds": 2.5,
                        "close_shot_share_min": 0.45,
                        "first_major_payoff_by_episode": 1,
                    },
                }
            }

        self.assertEqual(len(project_tool.profile_notes(manifest(None))), 1)
        self.assertEqual(project_tool.profile_notes(manifest(True)), [])

    def test_continuation_route_choice_is_recorded_and_read_back(self) -> None:
        model = {"target_video_model": "studio-video", "video_prompt_language": "en"}
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            project_tool.configure_project(root, production_profile=model)
            self.assertNotIn(
                "continuation_route", project_tool.project_status(root)["video_model_profile"]
            )
            project_tool.configure_project(
                root, production_profile={"continuation_route": "independent_starts"}
            )
            self.assertEqual(
                project_tool.project_status(root)["video_model_profile"],
                {**model, "continuation_route": "independent_starts"},
            )

    def test_pacing_with_zero_action_seconds_still_counts_as_declared(self) -> None:
        manifest = {
            "format": {
                "target_seconds_per_episode": 90,
                "pacing": {
                    "spoken_characters_per_second": 4.5,
                    "seconds_per_action_paragraph": 0,
                },
            }
        }
        self.assertEqual(project_tool.profile_notes(manifest), [])

    def test_rhythm_profile_accepts_partial_fields_and_rejects_bad_values(self) -> None:
        profile = {
            "form": "motion_comic",
            "first_hook_seconds": 5,
            "beat_interval_seconds_max": 30,
            "opposed_reversals_per_episode_min": 1,
            "end_on_peak": True,
            "reprise_previous_last_beat": True,
            "vo_share_max": 0.3,
            "target_avg_shot_seconds": 3.0,
            "close_shot_share_min": 0.45,
            "first_major_payoff_by_episode": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            manifest = root / "short-drama.json"
            self.assertEqual(project_tool.project_status(root)["rhythm_profile"], {})
            before = manifest.read_bytes()
            for bad, reason in (
                ({**profile, "vo_share_max": 1.5}, "vo_share_max must be a share"),
                ({**profile, "close_shot_share_min": float("nan")}, "close_shot_share_min must be a share"),
                ({**profile, "target_avg_shot_seconds": float("inf")}, "target_avg_shot_seconds must be a positive"),
                ({**profile, "first_hook_seconds": True}, "first_hook_seconds must be a positive"),
                ({**profile, "opposed_reversals_per_episode_min": 1.5}, "opposed_reversals_per_episode_min must be a whole"),
                ({**profile, "form": "spreadsheet"}, "form must be"),
                ({**profile, "hooks_per_minute": 4}, "no field hooks_per_minute"),
            ):
                with self.subTest(reason=reason):
                    with self.assertRaisesRegex(ValueError, reason):
                        project_tool.configure_project(root, rhythm_profile=bad)
                    self.assertEqual(manifest.read_bytes(), before)

            project_tool.configure_project(
                root, rhythm_profile={"form": "国漫二次元", "first_hook_seconds": 5}
            )
            self.assertEqual(
                project_tool.project_status(root)["rhythm_profile"],
                {"form": "国漫二次元", "first_hook_seconds": 5},
            )
            project_tool.configure_project(root, rhythm_profile={"form": "anime"})
            self.assertEqual(
                project_tool.project_status(root)["rhythm_profile"],
                {"form": "anime", "first_hook_seconds": 5},
            )
            project_tool.configure_project(root, rhythm_profile=profile)
            self.assertEqual(project_tool.project_status(root)["rhythm_profile"], profile)

    def test_status_declares_no_rhythm_profile_when_an_accepted_one_is_invalid(self) -> None:
        profile = {
            "status": "accepted",
            "form": "ai_live_action",
            "first_hook_seconds": 5,
            "beat_interval_seconds_max": 30,
            "opposed_reversals_per_episode_min": 1,
            "end_on_peak": True,
            "reprise_previous_last_beat": True,
            "vo_share_max": 0.3,
            "target_avg_shot_seconds": 2.5,
            "close_shot_share_min": 0.45,
            "first_major_payoff_by_episode": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            manifest = root / "short-drama.json"
            project = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(project["creator_authority"]["rhythm_profile"], {"status": "unset"})
            self.assertEqual(project_tool.project_status(root)["rhythm_profile"], {})
            for field, value in (
                (None, None),
                ("vo_share_max", "x"),
                ("first_hook_seconds", True),
            ):
                with self.subTest(field=field):
                    edited = dict(profile)
                    if field is not None:
                        edited[field] = value
                    project["creator_authority"]["rhythm_profile"] = edited
                    project_tool.atomic_json(manifest, project)
                    status = project_tool.project_status(root)
                    if field is None:
                        expected = {k: v for k, v in profile.items() if k != "status"}
                        self.assertEqual(status["rhythm_profile"], expected)
                        self.assertEqual(status["rhythm_profile_problems"], [])
                    else:
                        self.assertEqual(status["rhythm_profile"], {})
                        self.assertEqual(len(status["rhythm_profile_problems"]), 1)
                        self.assertIn(field, status["rhythm_profile_problems"][0])

    def test_project_discovery_languages_and_windows_portability_guards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.assertEqual(project_tool.find_project(root / "剧集"), root.resolve())
            status = project_tool.project_status(root)
            self.assertEqual(status["language"], "zh-CN")
            self.assertEqual(status["prompt_language"], "en")
            for bad_path in ("剧集/EP001/\x1fname.md", "剧集/EP001/\x7fname.md", "剧集/EP001/a\nb.md"):
                with self.subTest(bad_path=repr(bad_path)):
                    self.assertFalse(project_tool._is_portable_windows_path(bad_path))


class CreatorExportTests(unittest.TestCase):
    DOCUMENTS = (
        "剧本.md",
        "视觉设定.md",
        "分镜.md",
        "图片提示词.md",
        "视频提示词.md",
    )

    def make_project(self, directory: str, *, episodes: tuple[str, ...] = ("EP001",)) -> Path:
        root = Path(directory) / "project"
        project_tool.initialize_project(
            root,
            title="导出验证",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SKILL,
        )
        for episode in episodes:
            episode_root = root / "剧集" / episode
            episode_root.mkdir(parents=True)
            for name in self.DOCUMENTS:
                (episode_root / name).write_text(f"# {episode} {name}\n", encoding="utf-8")
            media = episode_root / "制作成果"
            media.mkdir()
            (media / f"SHOT-{episode}-001.mp4").write_bytes(b"rendered bytes")
        inputs = root / "输入"
        inputs.mkdir(exist_ok=True)
        (inputs / "私有素材.txt").write_text("private source\n", encoding="utf-8")
        return root

    def test_export_copies_current_documents_and_produced_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory, episodes=("EP001", "EP002"))
            out = Path(directory) / "handover"
            result = project_tool.build_creator_export(root, out=out)
            self.assertEqual(result["episodes"], ["EP001", "EP002"])
            self.assertEqual(result["missing_documents"], {})
            for episode in ("EP001", "EP002"):
                for name in self.DOCUMENTS:
                    self.assertTrue((out / "剧集" / episode / name).is_file())
                self.assertTrue(
                    (out / "剧集" / episode / "制作成果" / f"SHOT-{episode}-001.mp4").is_file()
                )
            self.assertTrue((out / "short-drama.json").is_file())

    def test_export_leaves_private_inputs_and_operational_state_behind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            out = Path(directory) / "handover"
            project_tool.build_creator_export(root, out=out)
            copied = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
            self.assertFalse(any(name.startswith("输入/") for name in copied), copied)
            self.assertFalse(any(".short-drama" in name for name in copied), copied)

    def test_export_manifest_does_not_assert_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            out = Path(directory) / "handover"
            project_tool.build_creator_export(root, out=out)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "creator_export")
            self.assertFalse(manifest["asserts_approval"])
            self.assertEqual(
                manifest["project_id"],
                json.loads((root / "short-drama.json").read_text(encoding="utf-8"))["project_id"],
            )

    def test_export_checksums_cover_every_exported_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            out = Path(directory) / "handover"
            project_tool.build_creator_export(root, out=out)
            recorded = {}
            for line in (out / "checksums.sha256").read_text(encoding="utf-8").splitlines():
                digest, relative = line.split("  ", 1)
                recorded[relative] = digest
            present = {
                path.relative_to(out).as_posix()
                for path in out.rglob("*")
                if path.is_file() and path.name != "checksums.sha256"
            }
            self.assertEqual(set(recorded), present)
            for relative, digest in recorded.items():
                self.assertEqual(
                    hashlib.sha256((out / relative).read_bytes()).hexdigest(), digest
                )

    def test_export_can_select_one_episode_and_skip_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory, episodes=("EP001", "EP002"))
            out = Path(directory) / "handover"
            result = project_tool.build_creator_export(
                root, out=out, episodes=["EP002"], include_media=False
            )
            self.assertEqual(result["episodes"], ["EP002"])
            self.assertFalse((out / "剧集/EP001").exists())
            self.assertFalse((out / "剧集/EP002/制作成果").exists())
            self.assertTrue((out / "剧集/EP002/剧本.md").is_file())

    def test_export_reports_documents_the_project_has_not_written_yet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            (root / "剧集/EP001/视频提示词.md").unlink()
            out = Path(directory) / "handover"
            result = project_tool.build_creator_export(root, out=out)
            self.assertEqual(result["missing_documents"], {"EP001": ["视频提示词.md"]})
            self.assertFalse((out / "剧集/EP001/视频提示词.md").exists())

    def test_export_refuses_a_destination_inside_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            for candidate in (root, root / "交付/handover"):
                with self.subTest(destination=str(candidate)):
                    with self.assertRaises(ValueError):
                        project_tool.build_creator_export(root, out=candidate)

    def test_export_refuses_a_destination_that_contains_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            keepsake = root.parent / "irreplaceable.txt"
            keepsake.write_text("do not delete\n", encoding="utf-8")
            for destination in (root.parent, root.parent.parent, root):
                with self.subTest(destination=str(destination)):
                    with self.assertRaises(ValueError):
                        project_tool.build_creator_export(
                            root, out=destination, overwrite=True
                        )
            self.assertTrue(keepsake.is_file())
            self.assertTrue((root / "short-drama.json").is_file())
            self.assertTrue((root / "剧集/EP001/剧本.md").is_file())

    def test_export_refuses_a_destination_spelled_as_the_same_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            alias = Path(directory) / "alias"
            os.symlink(root, alias, target_is_directory=True)
            with self.assertRaises(ValueError):
                project_tool.build_creator_export(root, out=alias, overwrite=True)
            self.assertTrue((root / "剧集/EP001/剧本.md").is_file())

    def test_export_only_overwrites_a_directory_it_produced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            documents = Path(directory) / "Documents"
            (documents / "照片").mkdir(parents=True)
            (documents / "报税.pdf").write_text("tax\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                project_tool.build_creator_export(root, out=documents, overwrite=True)
            self.assertTrue((documents / "报税.pdf").is_file())
            self.assertTrue((documents / "照片").is_dir())
            handover = Path(directory) / "handover"
            project_tool.build_creator_export(root, out=handover)
            project_tool.build_creator_export(root, out=handover, overwrite=True)
            self.assertTrue((handover / "manifest.json").is_file())

    def test_export_manifest_names_what_it_actually_left_behind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            (root / "设定集").mkdir(exist_ok=True)
            (root / "设定集/角色圣经.md").write_text("# 角色圣经\n", encoding="utf-8")
            out = Path(directory) / "handover"
            result = project_tool.build_creator_export(root, out=out)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("设定集", manifest["excluded"])
            self.assertIn("输入", manifest["excluded"])
            self.assertEqual(result["excluded"], manifest["excluded"])
            self.assertEqual(
                manifest["selection"],
                {"episodes": "all", "available_episodes": ["EP001"], "include_media": True},
            )

    def test_export_records_a_partial_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory, episodes=("EP001", "EP002"))
            out = Path(directory) / "handover"
            project_tool.build_creator_export(
                root, out=out, episodes=["EP002"], include_media=False
            )
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["selection"],
                {
                    "episodes": ["EP002"],
                    "available_episodes": ["EP001", "EP002"],
                    "include_media": False,
                },
            )

    def test_export_fails_closed_on_names_it_cannot_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            try:
                (root / "剧集/EP001/制作成果/bad\nname.mp4").write_bytes(b"v")
            except OSError:
                self.skipTest("this filesystem rejects newlines in filenames")
            out = Path(directory) / "handover"
            with self.assertRaises(project_tool.ProjectConflictError):
                project_tool.build_creator_export(root, out=out)
            self.assertFalse(out.exists())

    def test_export_fails_closed_on_a_symlinked_media_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory, episodes=("EP001", "EP002"))
            media = root / "剧集/EP002/制作成果"
            shutil.rmtree(media)
            try:
                media.symlink_to(root / "剧集/EP001/制作成果", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("this platform cannot create symlinks")
            out = Path(directory) / "handover"
            with self.assertRaises(project_tool.ProjectConflictError):
                project_tool.build_creator_export(root, out=out)
            self.assertFalse(out.exists())

    def test_export_reports_names_that_cannot_be_unpacked_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            (root / "剧集/EP001/制作成果/con.mp4").write_bytes(b"v")
            out = Path(directory) / "handover"
            result = project_tool.build_creator_export(root, out=out)
            self.assertEqual(
                result["windows_unsafe_paths"], ["剧集/EP001/制作成果/con.mp4"]
            )

    def test_export_refuses_an_existing_destination_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            out = Path(directory) / "handover"
            project_tool.build_creator_export(root, out=out)
            with self.assertRaises(FileExistsError):
                project_tool.build_creator_export(root, out=out)
            (out / "剧集/EP001/剧本.md").write_text("# 已改\n", encoding="utf-8")
            project_tool.build_creator_export(root, out=out, overwrite=True)
            self.assertEqual(
                (out / "剧集/EP001/剧本.md").read_text(encoding="utf-8"),
                "# EP001 剧本.md\n",
            )

    def test_export_rejects_unknown_or_malformed_episode_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            out = Path(directory) / "handover"
            with self.assertRaises(FileNotFoundError):
                project_tool.build_creator_export(root, out=out, episodes=["EP404"])
            with self.assertRaises(ValueError):
                project_tool.build_creator_export(root, out=out, episodes=["第一集"])

    def test_export_fails_closed_on_a_symlinked_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            secret = Path(directory) / "outside.md"
            secret.write_text("outside the project\n", encoding="utf-8")
            document = root / "剧集/EP001/剧本.md"
            document.unlink()
            try:
                document.symlink_to(secret)
            except (OSError, NotImplementedError):
                self.skipTest("this platform cannot create symlinks")
            out = Path(directory) / "handover"
            with self.assertRaises(project_tool.ProjectConflictError):
                project_tool.build_creator_export(root, out=out)
            self.assertFalse(out.exists())

    def test_export_command_line_prints_the_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            out = Path(directory) / "handover"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "export",
                    str(root),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["kind"], "creator_export")
            self.assertEqual(payload["episodes"], ["EP001"])


class ActiveConfigureAndDashboardContractTests(unittest.TestCase):
    """Active configure/package behavior and Dashboard read-only state parity."""

    def make_tracked_project(self, directory: str, *, decision: str = "accepted", review: dict | None = None) -> Path:
        root = Path(directory) / "project"
        project_tool.initialize_project(
            root,
            title="轻量短剧",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SKILL,
        )
        screenplay = root / "剧集/EP001/screenplay.md"
        screenplay.parent.mkdir(parents=True, exist_ok=True)
        screenplay.write_text("# 第一集\n", encoding="utf-8")
        digest = hashlib.sha256(screenplay.read_bytes()).hexdigest()
        state_path = root / ".short-drama/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["artifacts"]["EP001:script"] = {
            "owner": "short-drama-write",
            "outputs": ["剧集/EP001/screenplay.md"],
            "inputs": {},
            "acceptance": {
                "decision": decision,
                "outputs": {"剧集/EP001/screenplay.md": digest},
            },
            "review": review,
        }
        project_tool.atomic_json(state_path, state)
        return root

    def test_dashboard_path_and_fd_readers_agree_on_live_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_tracked_project(directory)
            screenplay = root / "剧集/EP001/screenplay.md"
            state_path = root / ".short-drama/state.json"

            def both() -> tuple[str, str]:
                record = json.loads(state_path.read_text(encoding="utf-8"))[
                    "artifacts"
                ]["EP001:script"]
                if os.name == "nt":
                    state = project_tool._artifact_state(root, record)
                    return state, state
                directory_fd = os.open(root, os.O_RDONLY)
                try:
                    return (
                        project_tool._artifact_state(root, record),
                        project_tool._artifact_state_at(directory_fd, record),
                    )
                finally:
                    os.close(directory_fd)

            self.assertEqual(both(), ("accepted", "accepted"))
            screenplay.write_text("# 第一集\n\n改过了。\n", encoding="utf-8")
            self.assertEqual(both(), ("update_needed", "update_needed"))
            screenplay.unlink()
            self.assertEqual(both(), ("update_needed", "update_needed"))

    def test_configure_updates_manifest_and_accepts_authority_without_ledger_ceremony(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "configured"
            project_tool.initialize_project(
                root,
                title="初版剧名",
                language="zh-CN",
                aspect_ratio="9:16",
            )
            result = project_tool.configure_project(
                root,
                title="终版剧名",
                prompt_language="zh-CN",
                aspect_ratio="16:9",
                episode_count=20,
                target_seconds_per_episode=90,
                pacing={
                    "spoken_characters_per_second": 4.2,
                    "seconds_per_action_paragraph": 2.0,
                },
                visual_direction={"look_development": "ink_wash_trial_v1"},
                production_profile={
                    "target_video_model": "studio-video-v2",
                    "video_prompt_language": "zh-CN",
                    "native_duration_seconds": {"min": 4, "max": 15},
                    "supported_generation_modes": ["text", "first_frame", "reference"],
                },
                rhythm_profile={"form": "水墨笔触", "first_hook_seconds": 4.5},
            )
            status = result["status"]
            self.assertEqual(status["title"], "终版剧名")
            self.assertEqual(status["language"], "zh-CN")
            self.assertEqual(status["prompt_language"], "zh-CN")
            self.assertEqual(status["video_prompt_language"], "zh-CN")
            self.assertEqual(
                status["format"],
                {
                    "aspect_ratio": "16:9",
                    "episode_count": 20,
                    "target_seconds_per_episode": 90,
                },
            )
            self.assertEqual(
                status["rhythm_profile"],
                {"form": "水墨笔触", "first_hook_seconds": 4.5},
            )
            self.assertEqual(
                status["video_model_profile"]["target_video_model"], "studio-video-v2"
            )
            for value in status["authority"].values():
                self.assertEqual(value, "bound")

            cli = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "configure",
                    str(root),
                    "--json",
                    json.dumps(
                        {
                            "language": "en",
                            "rhythm_profile": {"target_avg_shot_seconds": 5.0},
                        }
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(cli.returncode, 0, cli.stderr)
            updated = json.loads(cli.stdout)["status"]
            self.assertEqual(updated["language"], "en")
            self.assertEqual(
                updated["rhythm_profile"],
                {
                    "form": "水墨笔触",
                    "first_hook_seconds": 4.5,
                    "target_avg_shot_seconds": 5.0,
                },
            )

    def test_creator_first_direct_package_and_security_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside.md"
            outside.write_text("# secret\n", encoding="utf-8")
            root = Path(directory) / "creator-first"
            episode_dir = root / "剧集/EP001"
            episode_dir.mkdir(parents=True)
            (episode_dir / "剧本.md").write_text("# 第一集\n", encoding="utf-8")
            (episode_dir / "视觉设定.md").write_text("# 视觉设定\n", encoding="utf-8")
            (root / ".short-drama").mkdir(parents=True, exist_ok=True)
            (root / ".short-drama/internal.json").write_text("{}", encoding="utf-8")

            cli = subprocess.run(
                [sys.executable, str(SCRIPT), "package", str(root), "--episode", "EP001"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(cli.returncode, 0, cli.stderr)
            packaged = json.loads(cli.stdout)
            self.assertEqual(
                [entry["source"] for entry in packaged["files"]],
                ["剧集/EP001/剧本.md", "剧集/EP001/视觉设定.md"],
            )
            verified = project_tool.verify_delivery_package(root, episode="EP001")
            self.assertEqual(verified["status"], "verified")
            self.assertFalse((root / "交付/EP001/artifacts/.short-drama").exists())

            with self.assertRaises(ValueError):
                project_tool.build_delivery_package(
                    root, episode="EP001", includes=["../outside.md"]
                )
            with self.assertRaises(ValueError):
                project_tool.build_delivery_package(
                    root, episode="EP001", includes=[".short-drama/internal.json"]
                )

            link_path = episode_dir / "分镜.md"
            try:
                link_path.symlink_to(outside)
            except OSError:
                return
            with self.assertRaises(project_tool.ProjectConflictError):
                project_tool.build_delivery_package(root, episode="EP001")

    def test_configure_partial_pacing_q_form_aspect_ratio_and_production_profile_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for bad_ratio in ("vertical", "0:16"):
                with self.subTest(bad_ratio=bad_ratio), self.assertRaises(ValueError):
                    project_tool.initialize_project(
                        Path(directory) / f"bad-{bad_ratio.replace(':', '-')}",
                        title="坏画幅",
                        language="zh-CN",
                        aspect_ratio=bad_ratio,
                        suite_root=SKILL,
                    )

            root = Path(directory) / "q-project"
            project_tool.initialize_project(
                root,
                title="Q版测试",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SKILL,
            )
            configured = project_tool.configure_project(
                root,
                rhythm_profile={"form": "Q 版表达", "first_hook_seconds": 3},
            )
            self.assertEqual(
                configured["status"]["rhythm_profile"]["form"], "Q 版表达"
            )

            # Seed a legacy child leaf pointer under rhythm_profile and verify configure prunes it.
            state_path = root / ".short-drama/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["authority"]["/creator_authority/rhythm_profile/first_hook_seconds"] = "unbound"
            project_tool.atomic_json(state_path, state)

            # Partial pacing update (with init's None placeholder on the untouched rate) succeeds.
            updated = project_tool.configure_project(
                root,
                pacing={"spoken_characters_per_second": 4.2},
                rhythm_profile={"first_hook_seconds": 4.0},
            )
            self.assertNotIn(
                "/creator_authority/rhythm_profile/first_hook_seconds",
                updated["status"]["authority"],
            )
            self.assertEqual(
                updated["status"]["authority"]["/creator_authority/rhythm_profile"],
                "bound",
            )
            project_tool.configure_project(
                root, pacing={"seconds_per_action_paragraph": 0}
            )

            with self.assertRaises(ValueError):
                project_tool.configure_project(root, aspect_ratio="portrait")
            with self.assertRaises(ValueError):
                project_tool.configure_project(root, pacing={"unknown_rate": 1.0})
            with self.assertRaises(ValueError):
                project_tool.configure_project(
                    root, pacing={"spoken_characters_per_second": 0}
                )
            with self.assertRaises(ValueError):
                project_tool.configure_project(
                    root, production_profile={"unknown_choice": "x"}
                )
            with self.assertRaises(ValueError):
                project_tool.configure_project(
                    root, production_profile={"video_prompt_language": "123"}
                )
            with self.assertRaises(ValueError):
                project_tool.configure_project(
                    root,
                    production_profile={"native_duration_seconds": {"min": 8, "max": 4}},
                )

    def test_legacy_artifact_state_remains_readable_in_status_without_blocking_package(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_tracked_project(directory, decision="rejected")
            status = project_tool.project_status(root)
            self.assertEqual(status["artifacts"].get("EP001:script"), "revise")
            packaged = project_tool.build_delivery_package(root, episode="EP001")
            self.assertIn(
                "剧集/EP001/screenplay.md",
                [item["source"] for item in packaged["files"]],
            )

    def test_configure_supports_json_file_and_at_path_for_windows_shells(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "win-json"
            project_tool.initialize_project(
                root,
                title="跨平台配置",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SKILL,
            )
            cfg_file = Path(directory) / "config.json"
            # Write with UTF-8 BOM to mimic Windows PowerShell Set-Content -Encoding UTF8.
            cfg_file.write_bytes(
                "\ufeff".encode("utf-8")
                + json.dumps(
                    {
                        "title": "文件配置剧名",
                        "episode_count": 10,
                        "target_seconds_per_episode": 75,
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            cli = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "configure",
                    str(root),
                    "--json-file",
                    str(cfg_file),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(cli.returncode, 0, cli.stderr)
            status = json.loads(cli.stdout)["status"]
            self.assertEqual(status["title"], "文件配置剧名")
            self.assertEqual(status["format"]["episode_count"], 10)
            self.assertEqual(status["format"]["target_seconds_per_episode"], 75)

            pacing_file = Path(directory) / "pacing.json"
            pacing_file.write_text(
                json.dumps(
                    {
                        "spoken_characters_per_second": 4.4,
                        "seconds_per_action_paragraph": 2.0,
                    }
                ),
                encoding="utf-8",
            )
            cli_at = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "configure",
                    str(root),
                    "--pacing-json",
                    f"@{pacing_file}",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(cli_at.returncode, 0, cli_at.stderr)
            self.assertEqual(json.loads(cli_at.stdout)["status"]["profile_notes"], [])

            conflict = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "configure",
                    str(root),
                    "--json",
                    '{"title":"a"}',
                    "--json-file",
                    str(cfg_file),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(conflict.returncode, 2)

    def test_scaffold_episode_creates_skeletons_without_clobbering_and_reports_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fresh-project"
            result = project_tool.scaffold_episode(
                root, episode="EP001", title="第一集试拍", suite_root=SKILL
            )
            self.assertTrue(result["project_initialized"])
            self.assertEqual(set(result["created_files"]), set(project_tool.CREATOR_DOCUMENTS))
            self.assertEqual(result["existing_files"], [])
            gap_kinds = {item["kind"] for item in result["gaps"]}
            self.assertEqual(
                gap_kinds,
                {"missing_scenes", "missing_visual_entries", "missing_shots", "missing_motions"},
            )

            # Write a real scene and one shot referencing a missing IMG and missing MOTION.
            ep_dir = root / "剧集/EP001"
            (ep_dir / "剧本.md").write_text(
                "# EP001 · 试拍\n\n## EP001-SC001 内 · 走廊 · 夜\n\n许棠推门。\n\n## EP001-SC002 外 · 天台 · 夜\n\n风吹衣角。\n",
                encoding="utf-8",
            )
            (ep_dir / "分镜.md").write_text(
                "# EP001 分镜\n\n"
                "## SHOT-EP001-001 · 推门\n"
                "- 来源：EP001-SC001\n"
                "- 时长：3s\n"
                "- 图片提示词项：IMG-XT-SHEET《许棠设定图》（控制：人物外貌）\n"
                "- 输入参考图：无（文生视频）。\n"
                "- 出场设定：无\n",
                encoding="utf-8",
            )
            second = subprocess.run(
                [sys.executable, str(SCRIPT), "scaffold-episode", str(root), "EP001"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            report = json.loads(second.stdout)
            self.assertFalse(report["project_initialized"])
            self.assertEqual(report["created_files"], [])
            self.assertEqual(report["inventory"]["scenes"], ["EP001-SC001", "EP001-SC002"])
            self.assertEqual(report["inventory"]["shots"], ["SHOT-EP001-001"])
            gaps_by_kind = {(item["kind"], item.get("id")) for item in report["gaps"]}
            self.assertIn(("unclaimed_scene", "EP001-SC002"), gaps_by_kind)
            self.assertIn(("missing_keyframe_prompt", "SHOT-EP001-001"), gaps_by_kind)
            self.assertIn(("missing_image_prompt", "IMG-XT-SHEET"), gaps_by_kind)
            self.assertIn(("missing_motion_for_shot", "SHOT-EP001-001"), gaps_by_kind)

            # Complete valid episode yields zero gaps and leaves files byte-for-byte untouched.
            golden_root = Path(directory) / "golden-project"
            project_tool.initialize_project(
                golden_root, title="样例", language="zh-CN", aspect_ratio="9:16", suite_root=SKILL
            )
            shutil.copytree(SUITE / "examples/creator-first/EP001", golden_root / "剧集/EP001")
            before = {
                name: (golden_root / "剧集/EP001" / name).read_bytes()
                for name in project_tool.CREATOR_DOCUMENTS
            }
            clean = project_tool.scaffold_episode(golden_root, episode="EP001", suite_root=SKILL)
            self.assertEqual(clean["created_files"], [])
            self.assertEqual(clean["gaps"], [])
            self.assertEqual(clean["checker_errors"], [])
            self.assertEqual(clean["checker_warnings"], [])
            for name, raw in before.items():
                self.assertEqual((golden_root / "剧集/EP001" / name).read_bytes(), raw)

    def test_export_manifest_direct_verify_security_and_package_deprecation_notice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            project_tool.initialize_project(
                root, title="导出校验", language="zh-CN", aspect_ratio="9:16", suite_root=SKILL
            )
            ep_dir = root / "剧集/EP001"
            ep_dir.mkdir(parents=True)
            for name in project_tool.CREATOR_DOCUMENTS:
                (ep_dir / name).write_text(f"# EP001 {name}\n", encoding="utf-8")
            out = Path(directory) / "handover"

            exp = subprocess.run(
                [sys.executable, str(SCRIPT), "export", str(root), "--out", str(out), "--manifest"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(exp.returncode, 0, exp.stderr)
            exp_payload = json.loads(exp.stdout)
            self.assertEqual(exp_payload["manifest"], "manifest.json")
            self.assertEqual(exp_payload["checksums"], "checksums.sha256")

            ver = subprocess.run(
                [sys.executable, str(SCRIPT), "verify", str(out)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(ver.returncode, 0, ver.stdout + ver.stderr)
            ver_payload = json.loads(ver.stdout)
            self.assertEqual(ver_payload["status"], "verified")
            self.assertEqual(ver_payload["episodes"], ["EP001"])

            # Detect tampered file + unexpected file.
            script_copy = out / "剧集/EP001/剧本.md"
            original_script = script_copy.read_bytes()
            script_copy.write_text("# tampered\n", encoding="utf-8")
            (out / "extra.txt").write_text("sneaky\n", encoding="utf-8")
            tampered = subprocess.run(
                [sys.executable, str(SCRIPT), "verify", str(out)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(tampered.returncode, 1)
            tampered_payload = json.loads(tampered.stdout)
            self.assertEqual(tampered_payload["status"], "tampered")
            self.assertTrue(any("checksum mismatch" in p for p in tampered_payload["problems"]))
            self.assertTrue(any("unexpected export file" in p for p in tampered_payload["problems"]))

            # Symlink rejection inside export directory and on export root.
            script_copy.write_bytes(original_script)
            (out / "extra.txt").unlink()
            if hasattr(os, "symlink"):
                outside = Path(directory) / "outside.txt"
                outside.write_text("secret\n", encoding="utf-8")
                try:
                    (out / "leak.md").symlink_to(outside)
                    linked_root = Path(directory) / "linked-handover"
                    linked_root.symlink_to(out, target_is_directory=True)
                except OSError:
                    pass
                else:
                    sym_report = project_tool.verify_export_directory(out)
                    self.assertEqual(sym_report["status"], "tampered")
                    self.assertTrue(any("symlink is not allowed" in p for p in sym_report["problems"]))
                    with self.assertRaises(project_tool.ProjectConflictError):
                        project_tool.verify_export_directory(linked_root)

                    # Intermediate symlink directory must NOT be traversed as an external hash oracle.
                    (out / "leak.md").unlink()
                    outside_dir = Path(directory) / "outside_dir"
                    outside_dir.mkdir()
                    (outside_dir / "secret.txt").write_text("top-secret\n", encoding="utf-8")
                    (out / "sub").symlink_to(outside_dir, target_is_directory=True)
                    checksums_file = out / "checksums.sha256"
                    orig_checksums = checksums_file.read_text(encoding="utf-8")
                    bogus_hash = "0" * 64
                    checksums_file.write_text(
                        orig_checksums + f"{bogus_hash}  sub/secret.txt\n",
                        encoding="utf-8",
                    )
                    traversal_report = project_tool.verify_export_directory(out)
                    self.assertEqual(traversal_report["status"], "tampered")
                    self.assertTrue(
                        any("symlink is not allowed: sub" in p for p in traversal_report["problems"]),
                        traversal_report["problems"],
                    )
                    self.assertFalse(
                        any("checksum mismatch: sub/secret.txt" in p for p in traversal_report["problems"]),
                        traversal_report["problems"],
                    )
                    self.assertFalse(
                        any("manifest hash mismatch" in p for p in traversal_report["problems"]),
                        traversal_report["problems"],
                    )
                    checksums_file.write_text(orig_checksums, encoding="utf-8")
                    (out / "sub").unlink()

            # Package CLI stays functional and prints a gentle deprecation notice to stderr.
            pkg = subprocess.run(
                [sys.executable, str(SCRIPT), "package", str(root), "--episode", "EP001"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(pkg.returncode, 0, pkg.stderr)
            self.assertIn("DEPRECATION", pkg.stderr)
            self.assertEqual(json.loads(pkg.stdout)["episode"], "EP001")


if __name__ == "__main__":
    unittest.main()
