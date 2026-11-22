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
from unittest import mock


SUITE = Path(__file__).resolve().parents[1]
CORE_SCRIPT = SUITE / "skills/short-drama/scripts/project_tool.py"
PRODUCTION_SCRIPT = SUITE / "skills/short-drama-produce/scripts/production_tool.py"
FIXTURE_ADAPTER = SUITE / "tests/fixtures/fixture_adapter.py"
CREATOR_VALIDATOR = SUITE / "skills/short-drama/scripts/creator_markdown_check.py"
CREATOR_EXAMPLE = SUITE / "examples/creator-first/EP001"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


project_tool = load_module("production_core", CORE_SCRIPT)
production_tool = load_module("confirmed_production", PRODUCTION_SCRIPT)
creator_markdown_check = load_module("creator_markdown_check", CREATOR_VALIDATOR)


class ConfirmedProductionTests(unittest.TestCase):
    def make_project(self, directory: str) -> Path:
        root = Path(directory) / "project"
        project_tool.initialize_project(
            root,
            title="投产测试",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SUITE / "skills/short-drama",
        )
        source = root / "剧集/EP001/制作规格.md"
        source.parent.mkdir(parents=True)
        source.write_text("当前提示词来源\n", encoding="utf-8")
        reference = root / "输入/reference.png"
        reference.write_bytes(b"reference")
        return root

    def write_job(
        self,
        root: Path,
        *,
        modality: str = "image",
        job_id: str = "EP001-SHOT001",
        prompt: str = "一名角色站在雨夜门口",
        output: str | None = None,
        overwrite: bool = False,
        parameters: dict | None = None,
    ) -> Path:
        extensions = {"image": "png", "video": "mp4", "tts": "wav", "music": "wav"}
        output = output or (
            f"剧集/EP001/制作成果/{modality}/{job_id}.{extensions[modality]}"
        )
        path = root / "job.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "job_id": job_id,
                    "modality": modality,
                    "adapter": "fixture",
                    "prompt": prompt,
                    "source": "剧集/EP001/制作规格.md",
                    "references": ["输入/reference.png"],
                    "outputs": [output],
                    "parameters": parameters or {"count": 1},
                    "overwrite": overwrite,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def write_creator_video_job(
        self,
        root: Path,
        *,
        prompt: str = "The same woman turns toward the door.",
        reference_path: str = "输入/reference.png",
        may_control: list[str] | None = None,
        must_not_control: list[str] | None = None,
    ) -> Path:
        source = root / "剧集/EP001/视频提示词.md"
        source.write_text(
            "# EP001 视频提示词\n\n"
            "## MOTION-EP001-001 · 回头\n\n"
            "- 分镜：SHOT-EP001-001\n"
            "- 输入参考图：REF-HERO（顺序：1）· "
            "输入/reference.png《女主定妆照》"
            "（控制：身份、造型；不得控制：构图、动作）\n\n"
            "### 可复制提示词\n"
            "> The same woman turns toward the door.\n",
            encoding="utf-8",
        )
        path = root / "creator-video-job.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "job_id": "EP001-MOTION001",
                    "modality": "video",
                    "adapter": "fixture",
                    "prompt": prompt,
                    "source": "剧集/EP001/视频提示词.md",
                    "source_entry": "MOTION-EP001-001",
                    "reference_bindings": [
                        {
                            "slot_id": "REF-HERO",
                            "order": 1,
                            "path": reference_path,
                            "label": "女主定妆照",
                            "role": "identity_and_look",
                            "may_control": (
                                ["身份", "造型"]
                                if may_control is None
                                else may_control
                            ),
                            "must_not_control": (
                                ["构图", "动作"]
                                if must_not_control is None
                                else must_not_control
                            ),
                        }
                    ],
                    "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-001.mp4"],
                    "parameters": {},
                    "overwrite": False,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def write_creator_image_job(
        self,
        root: Path,
        *,
        reference_declaration: str = "无外部参考；保持人物年龄与造型一致。",
        include_binding: bool = False,
    ) -> Path:
        prompt = "A young East Asian woman stands beside a rain-dark door."
        source = root / "剧集/EP001/图片提示词.md"
        source.write_text(
            "# EP001 图片提示词\n\n"
            "## IMG-EP001-HERO · 女主角色板\n\n"
            f"- 参考：{reference_declaration}\n\n"
            "### 可复制提示词\n"
            f"> {prompt}\n",
            encoding="utf-8",
        )
        document: dict[str, object] = {
            "schema_version": "1.0",
            "job_id": "EP001-IMG-HERO",
            "modality": "image",
            "adapter": "fixture",
            "prompt": prompt,
            "source": "剧集/EP001/图片提示词.md",
            "source_entry": "IMG-EP001-HERO",
            "outputs": ["剧集/EP001/制作成果/image/IMG-EP001-HERO.png"],
            "parameters": {},
            "overwrite": False,
        }
        if include_binding:
            document["reference_bindings"] = [
                {
                    "slot_id": "REF-HERO",
                    "order": 1,
                    "path": "输入/reference.png",
                    "label": "女主定妆照",
                    "role": "identity_and_look",
                    "may_control": ["身份", "造型"],
                    "must_not_control": ["构图", "动作"],
                }
            ]
        path = root / "creator-image-job.json"
        path.write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8"
        )
        return path

    def adapter_config(
        self, directory: str, *, fail: bool = False, submit_then_fail: bool = False
    ) -> Path:
        command = [sys.executable, str(FIXTURE_ADAPTER)]
        if fail:
            command.append("--fail")
        if submit_then_fail:
            command.append("--submit-then-fail")
        path = Path(directory) / "adapters.json"
        path.write_text(
            json.dumps(
                {
                    "adapters": {
                        "fixture": {
                            "command": command,
                            "timeout_seconds": 30,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return path

    def prepare_and_confirm(self, root: Path, job: Path) -> dict:
        preview = production_tool.prepare_job(root, job)
        production_tool.confirm_job(
            root,
            job_id=preview["job_id"],
            confirmation=preview["confirmation"],
        )
        return preview

    def test_prepare_only_returns_a_complete_preview_and_creates_no_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = production_tool.prepare_job(root, job)

            self.assertEqual(preview["state"], "needs_confirmation")
            self.assertEqual(preview["count"], 1)
            self.assertEqual(preview["prompt"], "一名角色站在雨夜门口")
            self.assertEqual(preview["adapter"], "fixture")
            self.assertTrue(preview["confirmation"].startswith("CONFIRM EP001-SHOT001 "))
            self.assertFalse((root / preview["outputs"][0]).exists())
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "needs_confirmation",
            )

    def test_creator_source_entry_binds_prompt_and_reference_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            preview = production_tool.prepare_job(
                root, self.write_creator_video_job(root)
            )

            self.assertEqual(preview["source_entry"], "MOTION-EP001-001")
            self.assertEqual(preview["references"], ["输入/reference.png"])
            self.assertEqual(
                preview["reference_bindings"],
                [
                    {
                        "slot_id": "REF-HERO",
                        "order": 1,
                        "path": "输入/reference.png",
                        "label": "女主定妆照",
                        "role": "identity_and_look",
                        "may_control": ["身份", "造型"],
                        "must_not_control": ["构图", "动作"],
                    }
                ],
            )

    def test_creator_image_source_entry_supports_no_ref_and_real_ref(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            preview = production_tool.prepare_job(
                root, self.write_creator_image_job(root)
            )
            self.assertEqual(preview["source_entry"], "IMG-EP001-HERO")
            self.assertEqual(preview["references"], [])

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            declaration = (
                "REF-HERO（顺序：1）· 输入/reference.png《女主定妆照》"
                "（控制：身份、造型；不得控制：构图、动作）"
            )
            preview = production_tool.prepare_job(
                root,
                self.write_creator_image_job(
                    root,
                    reference_declaration=declaration,
                    include_binding=True,
                ),
            )
            self.assertEqual(preview["references"], ["输入/reference.png"])

    def test_source_entry_rejects_unbound_refs_wrong_kind_and_ambiguous_markdown(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            document = json.loads(job.read_text(encoding="utf-8"))
            document.pop("source_entry")
            document["prompt"] = "NOT canonical"
            job.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires source_entry"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            document = json.loads(job.read_text(encoding="utf-8"))
            document["references"] = ["输入/reference.png"]
            job.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must match reference_bindings"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            document = json.loads(job.read_text(encoding="utf-8"))
            document["source_entry"] = "MOTION-EP001-001"
            job.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match the job modality"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            document = json.loads(job.read_text(encoding="utf-8"))
            canonical = root / "剧集/EP001/图片提示词.md"
            arbitrary = root / "剧集/EP001/任意.md"
            arbitrary.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
            document["source"] = "剧集/EP001/任意.md"
            job.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "canonical creator Markdown path"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            source = root / "剧集/EP001/图片提示词.md"
            source.write_text(
                source.read_text(encoding="utf-8")
                + "\n## IMG-EP001-HERO · 重复条目\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicated"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            source = root / "剧集/EP001/图片提示词.md"
            source.write_text(
                source.read_text(encoding="utf-8")
                + "\n### 可复制提示词\n> duplicate\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate copyable prompts"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            source = root / "剧集/EP001/图片提示词.md"
            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    "> A young East Asian woman stands beside a rain-dark door.",
                    "> A young East Asian woman stands beside a rain-dark door.\n"
                    "THIS CRITICAL LINE IS NOT QUOTED",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unquoted content"):
                production_tool.prepare_job(root, job)

    def test_music_timeline_and_noncanonical_same_name_sources_remain_supported(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            source = root / "剧集/EP001/视频提示词.md"
            source.write_text("# 时间线音乐\n\n压低对白下的配乐。\n", encoding="utf-8")
            job = self.write_job(root, modality="music", job_id="EP001-MUSIC")
            document = json.loads(job.read_text(encoding="utf-8"))
            document["source"] = "剧集/EP001/视频提示词.md"
            document["references"] = []
            job.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

            preview = production_tool.prepare_job(root, job)

            self.assertEqual(preview["modality"], "music")
            self.assertIsNone(preview["source_entry"])

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            source = root / "输入/图片提示词.md"
            source.write_text("非 creator 的结构化规格\n", encoding="utf-8")
            job = self.write_job(root)
            document = json.loads(job.read_text(encoding="utf-8"))
            document["source"] = "输入/图片提示词.md"
            job.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

            preview = production_tool.prepare_job(root, job)

            self.assertIsNone(preview["source_entry"])

    def test_source_entry_requires_ref_separators_and_non_conflicting_scopes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_video_job(root)
            source = root / "剧集/EP001/视频提示词.md"
            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    "- 输入参考图：REF-HERO（顺序：1）· "
                    "输入/reference.png《女主定妆照》"
                    "（控制：身份、造型；不得控制：构图、动作）",
                    "- 输入参考图：无（ref-HERO）",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "declaration is invalid"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            declaration = (
                "无外部参考；ref-HERO（顺序：1）· 输入/reference.png"
                "《女主定妆照》（控制：身份；不得控制：动作）"
            )
            job = self.write_creator_image_job(
                root, reference_declaration=declaration, include_binding=True
            )
            with self.assertRaisesRegex(ValueError, "declaration is invalid"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            declaration = (
                "REF-HERO（顺序：1）· 输入/reference.png《女主定妆照》"
                "（控制：身份；不得控制：动作）"
                "REF-LOOK（顺序：2）· 输入/second.png《服装参考》"
                "（控制：造型；不得控制：构图）"
            )
            (root / "输入/second.png").write_bytes(b"second")
            job = self.write_creator_image_job(
                root, reference_declaration=declaration, include_binding=True
            )
            document = json.loads(job.read_text(encoding="utf-8"))
            document["reference_bindings"].append(
                {
                    "slot_id": "REF-LOOK",
                    "order": 2,
                    "path": "输入/second.png",
                    "label": "服装参考",
                    "role": "look",
                    "may_control": ["造型"],
                    "must_not_control": ["构图"],
                }
            )
            job.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "declaration is invalid"):
                production_tool.prepare_job(root, job)

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_video_job(
                root, may_control=["身份"], must_not_control=["身份"]
            )
            with self.assertRaisesRegex(ValueError, "must not overlap"):
                production_tool.prepare_job(root, job)

    def test_pre_contract_stored_jobs_remain_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            preview = production_tool.prepare_job(root, self.write_job(root))
            path = production_tool._job_path(root, preview["job_id"])
            document = json.loads(path.read_text(encoding="utf-8"))
            document.pop("source_entry")
            document.pop("reference_bindings")
            execution = {
                key: document[key]
                for key in production_tool.LEGACY_STORED_EXECUTION_KEYS
            }
            document["fingerprint"] = production_tool.sha256_bytes(
                production_tool._canonical(execution)
            )
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

            restored = production_tool._read_job(root, preview["job_id"])

            self.assertIsNone(restored["source_entry"])
            self.assertEqual(restored["reference_bindings"], [])

    def test_creator_source_entry_rejects_prompt_or_reference_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            with self.assertRaisesRegex(ValueError, "prompt does not match"):
                production_tool.prepare_job(
                    root,
                    self.write_creator_video_job(root, prompt="A different prompt."),
                )

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            wrong = root / "输入/wrong.png"
            wrong.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "bindings do not match"):
                production_tool.prepare_job(
                    root,
                    self.write_creator_video_job(root, reference_path="输入/wrong.png"),
                )

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            with self.assertRaisesRegex(ValueError, "bindings do not match"):
                production_tool.prepare_job(
                    root,
                    self.write_creator_video_job(root, must_not_control=["背景"]),
                )

    def test_reference_bindings_require_bounded_may_and_must_not_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_video_job(root, must_not_control=[])
            with self.assertRaisesRegex(ValueError, "must_not_control"):
                production_tool.prepare_job(root, job)

    def test_run_requires_the_exact_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            config = self.adapter_config(directory)
            preview = production_tool.prepare_job(root, job)

            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.confirm_job(
                    root,
                    job_id="EP001-SHOT001",
                    confirmation="yes, generate it",
                )

            production_tool.confirm_job(
                root,
                job_id="EP001-SHOT001",
                confirmation=preview["confirmation"],
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "confirmed",
            )

    def test_changed_job_invalidates_a_previous_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root, prompt="版本一")
            preview = self.prepare_and_confirm(root, job)
            self.write_job(root, prompt="版本二")
            changed = production_tool.prepare_job(root, job)

            self.assertNotEqual(preview["confirmation"], changed["confirmation"])
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )

    def test_stored_job_tampering_cannot_reuse_an_old_confirmation(self) -> None:
        mutations = {
            "prompt": lambda document: document.update(prompt="未确认的新提示词"),
            "output": lambda document: document.update(
                outputs=["production/unconfirmed.png"]
            ),
            "parameters": lambda document: document.update(parameters={"count": 9}),
        }
        for label, mutate in mutations.items():
            with self.subTest(field=label), tempfile.TemporaryDirectory() as directory:
                root = self.make_project(directory)
                job = self.write_job(root)
                preview = self.prepare_and_confirm(root, job)
                stored_path = production_tool._job_path(root, preview["job_id"])
                document = json.loads(stored_path.read_text(encoding="utf-8"))
                original_fingerprint = document["fingerprint"]
                mutate(document)
                self.assertEqual(document["fingerprint"], original_fingerprint)
                stored_path.write_text(
                    json.dumps(document, ensure_ascii=False), encoding="utf-8"
                )

                with self.assertRaisesRegex(ValueError, "fingerprint"):
                    production_tool.run_job(
                        root,
                        job_id=preview["job_id"],
                        adapter_config=self.adapter_config(directory),
                    )
                receipt = json.loads(
                    production_tool._confirmation_path(
                        root, preview["job_id"]
                    ).read_text(encoding="utf-8")
                )
                self.assertIsNone(receipt["consumed_at"])
                audit = production_tool.audit_project(root)
                self.assertEqual(audit["status"], "attention")
                self.assertEqual(
                    audit["problems"],
                    [
                        {
                            "code": "invalid_job_record",
                            "record": stored_path.name,
                            "action": "repair_production_metadata",
                        }
                    ],
                )

    def test_metadata_parent_symlinks_cannot_escape_the_project(self) -> None:
        def link_directory(link: Path, target: Path) -> None:
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")

        with self.subTest(directory="jobs"), tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            outside = Path(directory) / "outside-jobs"
            outside.mkdir()
            jobs = root / ".short-drama/production/jobs"
            jobs.parent.mkdir(parents=True)
            link_directory(jobs, outside)

            with self.assertRaisesRegex(ValueError, "metadata directory"):
                production_tool.prepare_job(root, self.write_job(root))
            self.assertEqual(list(outside.iterdir()), [])

        with self.subTest(directory="confirmations"), tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = production_tool.prepare_job(root, job)
            outside = Path(directory) / "outside-confirmations"
            outside.mkdir()
            confirmations = root / ".short-drama/production/confirmations"
            link_directory(confirmations, outside)

            with self.assertRaisesRegex(ValueError, "metadata directory"):
                production_tool.confirm_job(
                    root,
                    job_id=preview["job_id"],
                    confirmation=preview["confirmation"],
                )
            self.assertEqual(list(outside.iterdir()), [])

        with self.subTest(directory="runs"), tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)
            outside = Path(directory) / "outside-runs"
            outside.mkdir()
            runs = root / ".short-drama/production/runs"
            link_directory(runs, outside)

            with self.assertRaisesRegex(ValueError, "metadata directory"):
                production_tool.run_job(
                    root,
                    job_id=preview["job_id"],
                    adapter_config=self.adapter_config(directory),
                )
            receipt = json.loads(
                production_tool._confirmation_path(root, preview["job_id"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertIsNone(receipt["consumed_at"])
            self.assertEqual(list(outside.iterdir()), [])

    def test_changed_input_requires_prepare_and_confirmation_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            (root / "剧集/EP001/制作规格.md").write_text(
                "提示词来源已改\n", encoding="utf-8"
            )

            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "needs_reconfirmation",
            )
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )

    def test_fixture_executes_every_supported_media_job(self) -> None:
        signatures = {
            "image": b"\x89PNG",
            "video": b"\x00\x00\x00\x18ftypisom",
            "tts": b"RIFF",
            "music": b"RIFF",
        }
        for modality, signature in signatures.items():
            with self.subTest(modality=modality), tempfile.TemporaryDirectory() as directory:
                root = self.make_project(directory)
                job_id = f"EP001-{modality}"
                job = self.write_job(root, modality=modality, job_id=job_id)
                preview = self.prepare_and_confirm(root, job)
                result = production_tool.run_job(
                    root,
                    job_id=job_id,
                    adapter_config=self.adapter_config(directory),
                )

                target = root / preview["outputs"][0]
                self.assertTrue(target.read_bytes().startswith(signature))
                self.assertEqual(result["state"], "succeeded")
                self.assertEqual(result["outputs"][0]["path"], preview["outputs"][0])
                self.assertGreater(result["outputs"][0]["bytes"], 0)
                status = production_tool.job_status(root, job_id=job_id)
                self.assertEqual(status["state"], "succeeded")
                self.assertNotIn("command", json.dumps(status))

    def test_a_shot_keyframe_is_a_producible_image_source(self) -> None:
        """Without this, `用途：起始帧` points at a file no stage can render.

        The frozen keyframe lives only in `分镜.md`, which was not a production
        source, so issue #92's "which storyboard image do I send" had no answer
        that the suite itself could produce.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            storyboard = root / "剧集/EP001/分镜.md"
            storyboard.write_text(
                "# EP001 分镜\n\n## SHOT-EP001-001 · 门外停步\n"
                "- 输入参考图：无（文生视频）。\n\n"
                "### 首帧提示词\n> A hand resting on a glass desktop.\n",
                encoding="utf-8",
            )
            job = root / "keyframe-job.json"

            def write(**overrides: object) -> Path:
                document = {
                    "schema_version": "1.0",
                    "job_id": "EP001-SHOT001-KEYFRAME",
                    "modality": "image",
                    "adapter": "fixture",
                    "prompt": "A hand resting on a glass desktop.",
                    "source": "剧集/EP001/分镜.md",
                    "source_entry": "SHOT-EP001-001",
                    "outputs": ["剧集/EP001/制作成果/images/SHOT-EP001-001.png"],
                    "parameters": {"width": 1080, "height": 1920},
                    "overwrite": False,
                }
                document.update(overrides)
                job.write_text(
                    json.dumps(document, ensure_ascii=False), encoding="utf-8"
                )
                return job

            preview = production_tool.prepare_job(root, write())
            self.assertEqual(preview["source_entry"], "SHOT-EP001-001")
            self.assertEqual(
                preview["outputs"], ["剧集/EP001/制作成果/images/SHOT-EP001-001.png"]
            )

            with self.assertRaisesRegex(ValueError, "does not match the job modality"):
                production_tool.prepare_job(
                    root, write(source_entry="MOTION-EP001-001")
                )
            with self.assertRaisesRegex(ValueError, "does not match the selected"):
                production_tool.prepare_job(root, write(prompt="A different frame."))

    def test_creator_episode_runs_through_validation_confirmation_and_adapter(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            episode = root / "剧集/EP001"
            shutil.rmtree(episode)
            shutil.copytree(CREATOR_EXAMPLE, episode)
            reference = root / "输入/女主定妆.png"
            reference.write_bytes(b"structural reference")
            declaration = (
                "REF-HERO（顺序：1）· 输入/女主定妆.png《女主定妆照》"
                "（用途：外貌；控制：脸型、体态；不得控制：构图、动作）"
            )
            for name in ("分镜.md", "视频提示词.md"):
                path = episode / name
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "- 输入参考图：无（文生视频）。",
                        f"- 输入参考图：{declaration}",
                        1,
                    ),
                    encoding="utf-8",
                )
            video_path = episode / "视频提示词.md"
            video_path.write_text(
                video_path.read_text(encoding="utf-8").replace(
                    "- 生成方式：文生视频", "- 生成方式：图生视频", 1
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, root), []
            )

            document = video_path.read_text(encoding="utf-8")
            section_match = re.search(
                r"^## MOTION-EP001-001\b(?P<body>.*?)(?=^## |\Z)",
                document,
                re.MULTILINE | re.DOTALL,
            )
            self.assertIsNotNone(section_match)
            assert section_match is not None
            prompt = "\n".join(
                line[1:].lstrip()
                for line in section_match.group("body").splitlines()
                if line.startswith(">")
            ).strip()
            self.assertTrue(prompt)
            job = root / "creator-e2e-job.json"
            job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-MOTION001-E2E",
                        "modality": "video",
                        "adapter": "fixture",
                        "prompt": prompt,
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "MOTION-EP001-001",
                        "reference_bindings": [
                            {
                                "slot_id": "REF-HERO",
                                "order": 1,
                                "path": "输入/女主定妆.png",
                                "label": "女主定妆照",
                                "role": "identity_and_look",
                                "may_control": ["脸型", "体态"],
                                "must_not_control": ["构图", "动作"],
                            }
                        ],
                        "outputs": [
                            "剧集/EP001/制作成果/video/SHOT-EP001-001.mp4"
                        ],
                        "parameters": {},
                        "overwrite": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            preview = self.prepare_and_confirm(root, job)
            result = production_tool.run_job(
                root,
                job_id=preview["job_id"],
                adapter_config=self.adapter_config(directory),
            )

            output = root / preview["outputs"][0]
            self.assertEqual(result["state"], "succeeded")
            self.assertTrue(
                output.read_bytes().startswith(b"\x00\x00\x00\x18ftypisom")
            )

    def test_failed_started_adapter_consumes_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            config = self.adapter_config(directory, fail=True)

            with self.assertRaisesRegex(production_tool.AdapterError, "code 7"):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "failed",
            )
            error = production_tool.job_status(
                root, job_id="EP001-SHOT001"
            )["latest_run"]["error"]
            self.assertEqual(error["code"], "adapter_exit_7")
            self.assertNotIn("message", error)
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )

    def test_an_interrupted_attempt_is_collected_rather_than_paid_for_twice(self) -> None:
        """A video task is billed at submission, not at collection.

        If the adapter dies after submitting — killed, disconnected, the machine
        sleeps — the provider's task is alive and already charged. Without a
        durable handle the only way forward is to submit again, so an
        interruption costs the creator a second charge for the same shot.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            interrupted = self.adapter_config(directory, submit_then_fail=True)

            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=interrupted
                )

            # The failed record keeps the handle instead of dropping it.
            failed = production_tool.job_status(root, job_id="EP001-SHOT001")
            self.assertEqual(failed["state"], "failed")
            self.assertEqual(failed["latest_run"]["provider_job_id"], "fixture-task-1")

            # audit names it and says what to do about it.
            report = production_tool.audit_project(root)
            orphans = [
                finding
                for finding in report["problems"]
                if finding["code"] == "orphaned_provider_job"
            ]
            self.assertEqual(len(orphans), 1, report["problems"])
            self.assertEqual(orphans[0]["provider_job_id"], "fixture-task-1")
            self.assertEqual(orphans[0]["action"], "collect_before_retry")

            # Collecting needs no new confirmation, because it spends nothing.
            collected = production_tool.collect_job(
                root,
                job_id="EP001-SHOT001",
                adapter_config=self.adapter_config(directory),
            )
            self.assertTrue(collected["collected"])
            self.assertEqual(collected["provider_job_id"], "fixture-task-1")
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "succeeded",
            )
            self.assertEqual(
                [output["path"] for output in collected["outputs"]],
                ["剧集/EP001/制作成果/image/EP001-SHOT001.png"],
            )
            self.assertTrue(
                (root / "剧集/EP001/制作成果/image/EP001-SHOT001.png").is_file()
            )
            # And the orphan is gone from audit once it has been collected.
            after = production_tool.audit_project(root)
            self.assertEqual(
                [f for f in after["problems"] if f["code"] == "orphaned_provider_job"],
                [],
            )

    def test_collect_does_not_overwrite_an_attempt_that_finished_on_its_own(self) -> None:
        """A live attempt and a dead one both sit at `running`.

        `audit` cannot tell them apart, so it reports a healthy in-flight
        attempt as an orphan too. Following that advice must not let two writers
        race onto the same output bytes and the same run record — collecting
        re-reads the record before writing and backs off if the attempt
        completed while the adapter was being called.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            interrupted = self.adapter_config(directory, submit_then_fail=True)
            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=interrupted
                )

            # The original attempt finishes *while the collect adapter is being
            # called* — the window `collect_job` leaves open on purpose, because
            # the adapter must not hold the project lock for minutes.
            original = production_tool._run_adapter

            def finish_then_answer(
                command, timeout, payload, adapter_root, *, consumes_confirmation=True
            ):
                history = production_tool._read_run_history(root, "EP001-SHOT001")
                finished = dict(history[-1])
                finished["status"] = "succeeded"
                finished["outputs"] = []
                production_tool._write_run(root, "EP001-SHOT001", finished)
                return original(
                    command,
                    timeout,
                    payload,
                    adapter_root,
                    consumes_confirmation=consumes_confirmation,
                )

            production_tool._run_adapter = finish_then_answer
            self.addCleanup(setattr, production_tool, "_run_adapter", original)

            with self.assertRaisesRegex(RuntimeError, "已经自己完成"):
                production_tool.collect_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )
            after = production_tool._read_run_history(root, "EP001-SHOT001")[-1]
            self.assertEqual(after["status"], "succeeded")
            self.assertNotIn("collected", after)

    def test_collect_refuses_when_no_attempt_carries_a_provider_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            config = self.adapter_config(directory, fail=True)
            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )
            with self.assertRaisesRegex(RuntimeError, "nothing to collect"):
                production_tool.collect_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )

    def test_structured_provider_failure_is_preserved_without_response_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            failure = Path(directory) / "safe_failure.py"
            failure.write_text(
                "import json, sys\n"
                "json.dump({'error': {'provider': 'fixture', "
                "'category': 'rate_limit', 'code': 'rate_limit_exceeded', "
                "'http_status': 429, 'request_id': 'req_safe_123', "
                "'retryable': True}}, sys.stdout)\n"
                "print('provider secret body', file=sys.stderr)\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            config = Path(directory) / "structured-adapters.json"
            config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(failure)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )
            latest = production_tool.job_status(
                root, job_id="EP001-SHOT001"
            )["latest_run"]
            self.assertEqual(
                latest["error"],
                {
                    "provider": "fixture",
                    "category": "rate_limit",
                    "code": "rate_limit_exceeded",
                    "http_status": 429,
                    "request_id": "req_safe_123",
                    "retryable": True,
                },
            )
            self.assertNotIn("secret", json.dumps(latest))

    def test_audit_reconciles_retries_and_current_output_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)

            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root,
                    job_id=preview["job_id"],
                    adapter_config=self.adapter_config(directory, fail=True),
                )

            production_tool.confirm_job(
                root,
                job_id=preview["job_id"],
                confirmation=preview["confirmation"],
            )
            production_tool.run_job(
                root,
                job_id=preview["job_id"],
                adapter_config=self.adapter_config(directory),
            )

            audit = production_tool.audit_project(root)
            self.assertEqual(audit["status"], "pass")
            self.assertEqual(audit["quality_verdict"], "not_assessed")
            self.assertEqual(audit["jobs"]["total"], 1)
            self.assertEqual(audit["attempts"]["total"], 2)
            self.assertEqual(audit["attempts"]["failed"], 1)
            self.assertEqual(audit["attempts"]["succeeded"], 1)
            self.assertEqual(audit["attempts"]["repeated_content"], 1)
            self.assertEqual(audit["jobs"]["recovered"], 1)
            self.assertEqual(audit["outputs"]["verified"], 1)
            self.assertEqual(audit["problems"], [])

            (root / preview["outputs"][0]).write_bytes(b"changed after production")
            changed = production_tool.audit_project(root)
            self.assertEqual(changed["status"], "attention")
            self.assertEqual(changed["outputs"]["modified"], 1)
            self.assertEqual(
                [problem["code"] for problem in changed["problems"]],
                ["output_digest_mismatch"],
            )

    def test_audit_routes_terminal_retryable_failure_without_claiming_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)
            failure = Path(directory) / "retryable_failure.py"
            failure.write_text(
                "import json, sys\n"
                "json.dump({'error': {'provider': 'fixture', "
                "'category': 'rate_limit', 'code': 'rate_limit_exceeded', "
                "'http_status': 429, 'retryable': True}}, sys.stdout)\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            config = Path(directory) / "retryable-config.json"
            config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(failure)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root, job_id=preview["job_id"], adapter_config=config
                )

            audit = production_tool.audit_project(root)
            self.assertEqual(audit["status"], "attention")
            self.assertEqual(audit["quality_verdict"], "not_assessed")
            self.assertEqual(audit["jobs"]["terminal_failed"], 1)
            self.assertEqual(audit["jobs"]["retryable_terminal_failed"], 1)
            self.assertEqual(
                audit["problems"],
                [
                    {
                        "code": "terminal_retryable_failure",
                        "job_id": preview["job_id"],
                        "run_id": audit["problems"][0]["run_id"],
                        "action": "inspect_then_reconfirm_retry",
                    }
                ],
            )

    def test_running_attempt_blocks_reconfirmation_and_stays_visible_to_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)
            stored = production_tool._read_job(root, preview["job_id"])
            run_id = "run-still-active"
            production_tool._write_run(
                root,
                preview["job_id"],
                {
                    "schema_version": "1.0",
                    "run_id": run_id,
                    "job_id": preview["job_id"],
                    "fingerprint": stored["fingerprint"],
                    "status": "running",
                    "started_at": "2026-08-16T08:00:00Z",
                    "finished_at": None,
                    "outputs": [],
                },
            )

            with self.assertRaisesRegex(RuntimeError, "already running"):
                production_tool.prepare_job(root, job)
            with self.assertRaisesRegex(RuntimeError, "already running"):
                production_tool.confirm_job(
                    root,
                    job_id=preview["job_id"],
                    confirmation=preview["confirmation"],
                )
            with self.assertRaisesRegex(RuntimeError, "already running"):
                production_tool.run_job(
                    root,
                    job_id=preview["job_id"],
                    adapter_config=self.adapter_config(directory),
                )

            audit = production_tool.audit_project(root)
            self.assertEqual(audit["status"], "attention")
            self.assertEqual(audit["jobs"]["running"], 1)
            self.assertEqual(audit["attempts"]["running"], 1)
            self.assertEqual(audit["jobs"]["terminal_failed"], 0)
            self.assertEqual(
                audit["problems"],
                [
                    {
                        "code": "running_attempt",
                        "job_id": preview["job_id"],
                        "run_id": run_id,
                        "action": "wait_or_investigate_running_attempt",
                    }
                ],
            )

    def test_audit_orders_terminal_state_and_recovery_by_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            preview = production_tool.prepare_job(root, self.write_job(root))
            stored = production_tool._read_job(root, preview["job_id"])
            target = root / preview["outputs"][0]
            target.parent.mkdir(parents=True)
            content = b"completed success"
            target.write_bytes(content)
            production_tool._write_run(
                root,
                preview["job_id"],
                {
                    "schema_version": "1.0",
                    "run_id": "run-slow-failure",
                    "job_id": preview["job_id"],
                    "fingerprint": stored["fingerprint"],
                    "status": "failed",
                    "started_at": "2026-08-16T08:00:00Z",
                    "finished_at": "2026-08-16T08:03:00Z",
                    "outputs": [],
                },
            )
            production_tool._write_run(
                root,
                preview["job_id"],
                {
                    "schema_version": "1.0",
                    "run_id": "run-fast-success",
                    "job_id": preview["job_id"],
                    "fingerprint": stored["fingerprint"],
                    "status": "succeeded",
                    "started_at": "2026-08-16T08:01:00Z",
                    "finished_at": "2026-08-16T08:02:00Z",
                    "outputs": [
                        {
                            "path": preview["outputs"][0],
                            "media_type": "image/png",
                            "bytes": len(content),
                            "sha256": production_tool.sha256_bytes(content),
                        }
                    ],
                },
            )

            audit = production_tool.audit_project(root)
            self.assertEqual(audit["status"], "attention")
            self.assertEqual(audit["jobs"]["recovered"], 0)
            self.assertEqual(audit["jobs"]["terminal_failed"], 1)
            self.assertEqual(audit["outputs"]["verified"], 1)
            self.assertEqual(audit["problems"][0]["code"], "terminal_failure")
            self.assertEqual(
                production_tool.job_status(root, job_id=preview["job_id"])["state"],
                "failed",
            )

    def test_audit_uses_latest_completed_successful_output_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            preview = production_tool.prepare_job(root, self.write_job(root))
            stored = production_tool._read_job(root, preview["job_id"])
            target = root / preview["outputs"][0]
            target.parent.mkdir(parents=True)
            early_content = b"completed first"
            late_content = b"completed last"
            target.write_bytes(late_content)
            for run_id, started_at, finished_at, content in (
                (
                    "run-started-first",
                    "2026-08-16T08:00:00Z",
                    "2026-08-16T08:04:00Z",
                    late_content,
                ),
                (
                    "run-started-second",
                    "2026-08-16T08:01:00Z",
                    "2026-08-16T08:03:00Z",
                    early_content,
                ),
            ):
                production_tool._write_run(
                    root,
                    preview["job_id"],
                    {
                        "schema_version": "1.0",
                        "run_id": run_id,
                        "job_id": preview["job_id"],
                        "fingerprint": stored["fingerprint"],
                        "status": "succeeded",
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "outputs": [
                            {
                                "path": preview["outputs"][0],
                                "media_type": "image/png",
                                "bytes": len(content),
                                "sha256": production_tool.sha256_bytes(content),
                            }
                        ],
                    },
                )

            audit = production_tool.audit_project(root)
            self.assertEqual(audit["status"], "pass")
            self.assertEqual(audit["outputs"]["verified"], 1)
            self.assertEqual(audit["outputs"]["modified"], 0)
            self.assertEqual(audit["problems"], [])

    def test_audit_rejects_a_success_claim_for_an_unconfirmed_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            preview = production_tool.prepare_job(root, self.write_job(root))
            stored = production_tool._read_job(root, preview["job_id"])
            unauthorized = "production/unconfirmed.png"
            content = b"not a confirmed target"
            target = root / unauthorized
            target.parent.mkdir(parents=True)
            target.write_bytes(content)
            production_tool._write_run(
                root,
                preview["job_id"],
                {
                    "schema_version": "1.0",
                    "run_id": "run-invalid-output-claim",
                    "job_id": preview["job_id"],
                    "fingerprint": stored["fingerprint"],
                    "status": "succeeded",
                    "started_at": "2026-08-16T08:00:00Z",
                    "finished_at": "2026-08-16T08:01:00Z",
                    "outputs": [
                        {
                            "path": unauthorized,
                            "media_type": "image/png",
                            "bytes": len(content),
                            "sha256": production_tool.sha256_bytes(content),
                        }
                    ],
                },
            )

            audit = production_tool.audit_project(root)
            self.assertEqual(audit["status"], "attention")
            self.assertEqual(audit["outputs"]["claimed_current"], 0)
            self.assertEqual(
                audit["problems"],
                [
                    {
                        "code": "invalid_succeeded_output_record",
                        "job_id": preview["job_id"],
                        "run_id": "run-invalid-output-claim",
                        "action": "repair_production_metadata",
                    }
                ],
            )

    def test_adapter_reads_a_private_confirmed_input_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            config = self.adapter_config(directory)
            original = (root / "输入/reference.png").read_bytes()
            staged_output_root: Path | None = None

            def inspect_snapshot(command, timeout, payload, cwd):
                nonlocal staged_output_root
                snapshot_root = Path(payload["project_root"])
                staged_output_root = Path(payload["output_root"])
                self.assertNotEqual(snapshot_root, root)
                self.assertEqual(
                    (snapshot_root / "输入/reference.png").read_bytes(), original
                )
                live = root / "输入/reference.png"
                live.write_bytes(b"changed after confirmation consumption")
                self.assertEqual(
                    (snapshot_root / "输入/reference.png").read_bytes(), original
                )
                adapter_output = staged_output_root / "adapter-output.png"
                adapter_output.write_bytes(b"fixture output")
                return {
                    "outputs": [
                        {
                            "target": payload["outputs"][0],
                            "source": str(adapter_output),
                        }
                    ]
                }

            with mock.patch.object(
                production_tool, "_run_adapter", side_effect=inspect_snapshot
            ):
                result = production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=config,
                )
            self.assertEqual(result["state"], "succeeded")
            self.assertIsNotNone(staged_output_root)
            self.assertFalse(staged_output_root.exists())

    def test_output_created_during_provider_run_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)
            target = root / preview["outputs"][0]

            def stage_then_race(command, timeout, payload, cwd):
                source = Path(payload["output_root"]) / "adapter-output.png"
                source.write_bytes(b"generated bytes")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"creator bytes during long provider run")
                return {
                    "outputs": [
                        {"target": payload["outputs"][0], "source": str(source)}
                    ]
                }

            with mock.patch.object(
                production_tool, "_run_adapter", side_effect=stage_then_race
            ), self.assertRaisesRegex(FileExistsError, "appeared"):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )
            self.assertEqual(
                target.read_bytes(), b"creator bytes during long provider run"
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "failed",
            )

    def test_existing_output_requires_explicit_overwrite_without_consuming(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)
            target = root / preview["outputs"][0]
            target.parent.mkdir(parents=True)
            target.write_bytes(b"existing")

            with self.assertRaisesRegex(FileExistsError, "overwrite is false"):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "confirmed",
            )

    def test_job_rejects_secrets_wrong_extensions_and_unsafe_outputs(self) -> None:
        cases = (
            ({"api_key": "not-allowed"}, None, "credentials"),
            ({}, "剧集/EP001/制作成果/image/result.mp4", "extension"),
            ({}, "剧集/EP001/result.png", "production"),
            ({}, "输入/production/stolen.png", "production"),
            ({}, "交付/production/result.png", "production"),
            ({}, "../result.png", "unsafe"),
        )
        for parameters, output, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = self.make_project(directory)
                job = self.write_job(root, parameters=parameters, output=output)
                with self.assertRaisesRegex(ValueError, message):
                    production_tool.prepare_job(root, job)

    def test_adapter_config_must_be_external_and_use_argv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            inside = root / "adapter.json"
            inside.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": f"{sys.executable} {FIXTURE_ADAPTER}",
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "outside"):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=inside
                )

            outside = Path(directory) / "bad-config.json"
            outside.write_bytes(inside.read_bytes())
            with self.assertRaisesRegex(ValueError, "string list"):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=outside
                )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "confirmed",
            )

    def test_cli_runs_prepare_confirm_execute_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            config = self.adapter_config(directory)

            prepared = subprocess.run(
                [sys.executable, str(PRODUCTION_SCRIPT), "prepare", str(root), "--job", str(job)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            preview = json.loads(prepared.stdout)
            confirmed = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "confirm",
                    str(root),
                    "--job-id",
                    preview["job_id"],
                    "--confirmation",
                    preview["confirmation"],
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
            executed = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "run",
                    str(root),
                    "--job-id",
                    preview["job_id"],
                    "--adapter-config",
                    str(config),
                ],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONIOENCODING": "cp1252"},
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["state"], "succeeded")
            status = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "status",
                    str(root),
                    "--job-id",
                    preview["job_id"],
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["state"], "succeeded")

    def test_entry_level_digest_isolates_unrelated_sections_in_shared_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            video_md = root / "剧集/EP001/视频提示词.md"
            video_md.write_text(
                "# EP001 视频提示词\n\n"
                "## MOTION-EP001-001 · 开门\n\n"
                "- 分镜：SHOT-EP001-001\n"
                "- 输入参考图：无\n\n"
                "### 可复制提示词\n"
                "> First shot prompt.\n\n"
                "## MOTION-EP001-002 · 回头\n\n"
                "- 分镜：SHOT-EP001-002\n"
                "- 输入参考图：无\n\n"
                "### 可复制提示词\n"
                "> Second shot prompt.\n\n"
                "## MOTION-EP001-030 · 远景\n\n"
                "- 分镜：SHOT-EP001-030\n"
                "- 输入参考图：无\n\n"
                "### 可复制提示词\n"
                "> Thirtieth shot original prompt.\n",
                encoding="utf-8",
            )
            config = self.adapter_config(directory)
            jobs = []
            for idx in (1, 2):
                job_file = root / f"motion-{idx}.json"
                job_file.write_text(
                    json.dumps(
                        {
                            "schema_version": "1.0",
                            "job_id": f"EP001-MOTION00{idx}",
                            "modality": "video",
                            "adapter": "fixture",
                            "source": "剧集/EP001/视频提示词.md",
                            "source_entry": f"MOTION-EP001-00{idx}",
                            "outputs": [
                                f"剧集/EP001/制作成果/video/SHOT-EP001-00{idx}.mp4"
                            ],
                            "parameters": {},
                            "overwrite": False,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                jobs.append(job_file)

            self.prepare_and_confirm(root, jobs[0])
            self.prepare_and_confirm(root, jobs[1])
            first_run = production_tool.run_job(
                root, job_id="EP001-MOTION001", adapter_config=config
            )
            self.assertEqual(first_run["state"], "succeeded")

            # Editing shot 30 must neither invalidate confirmed shot 2 nor mark shot 1 stale in audit.
            video_md.write_text(
                video_md.read_text(encoding="utf-8").replace(
                    "Thirtieth shot original prompt.",
                    "Thirtieth shot revised prompt with extra camera notes.",
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-MOTION002")["state"],
                "confirmed",
            )
            audit_before = production_tool.audit_project(root)
            self.assertEqual(
                [p for p in audit_before["problems"] if p["code"] == "job_inputs_changed"],
                [],
            )
            second_run = production_tool.run_job(
                root, job_id="EP001-MOTION002", adapter_config=config
            )
            self.assertEqual(second_run["state"], "succeeded")
            audit_after = production_tool.audit_project(root)
            self.assertEqual(audit_after["status"], "pass")

            # Editing shot 2 itself must flag job_inputs_changed and require reconfirmation.
            video_md.write_text(
                video_md.read_text(encoding="utf-8").replace(
                    "Second shot prompt.",
                    "Second shot changed prompt.",
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-MOTION002")["state"],
                "needs_reconfirmation",
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-MOTION001")["state"],
                "succeeded",
            )
            audit_changed = production_tool.audit_project(root)
            self.assertEqual(
                [p["job_id"] for p in audit_changed["problems"] if p["code"] == "job_inputs_changed"],
                ["EP001-MOTION002"],
            )

    def test_alphanumeric_labels_and_same_file_multi_role_bindings_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            usb_img = root / "输入/usb.png"
            usb_img.write_bytes(b"usb-frame")
            video_md = root / "剧集/EP001/视频提示词.md"
            video_md.write_text(
                "# EP001 视频提示词\n\n"
                "## MOTION-EP001-001 · 循环镜头\n\n"
                "- 分镜：SHOT-EP001-001\n"
                "- 输入参考图：REF-START（顺序：1）· 输入/usb.png《USB》"
                "（用途：起始帧；控制：首帧构图；不得控制：中段运镜）；"
                "REF-END（顺序：2）· 输入/usb.png《Lead Hero》"
                "（用途：结束帧；控制：尾帧落幅；不得控制：中段运镜）\n\n"
                "### 可复制提示词\n"
                "> Seamless loop returning to the USB close-up.\n",
                encoding="utf-8",
            )
            job = root / "loop-job.json"
            job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-LOOP",
                        "modality": "video",
                        "adapter": "fixture",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "MOTION-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-001.mp4"],
                        "parameters": {},
                        "overwrite": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            preview = self.prepare_and_confirm(root, job)
            self.assertEqual(
                [(b["label"], b["role"]) for b in preview["reference_bindings"]],
                [("USB", "first_frame"), ("Lead Hero", "last_frame")],
            )
            result = production_tool.run_job(
                root,
                job_id="EP001-LOOP",
                adapter_config=self.adapter_config(directory),
            )
            self.assertEqual(result["state"], "succeeded")

            # Identical (path, role) pair is still rejected.
            dup_job = root / "dup-role-job.json"
            dup_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-DUP",
                        "modality": "video",
                        "adapter": "fixture",
                        "prompt": "Loop.",
                        "reference_bindings": [
                            {
                                "slot_id": "REF-A",
                                "order": 1,
                                "path": "输入/usb.png",
                                "label": "USB",
                                "role": "first_frame",
                                "may_control": ["首帧"],
                                "must_not_control": ["运镜"],
                            },
                            {
                                "slot_id": "REF-B",
                                "order": 2,
                                "path": "输入/usb.png",
                                "label": "USB 2",
                                "role": "first_frame",
                                "may_control": ["首帧"],
                                "must_not_control": ["运镜"],
                            },
                        ],
                        "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-002.mp4"],
                        "parameters": {},
                        "overwrite": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, r"\(path, role\)"):
                production_tool.prepare_job(root, dup_job)

    def test_source_markdown_auto_extracts_prompt_and_reference_bindings_including_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            voice = root / "输入/hero_voice.wav"
            voice.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
            storyboard = root / "剧集/EP001/分镜.md"
            storyboard.write_text(
                "# EP001 分镜\n\n"
                "## SHOT-EP001-001 · 雨夜门口\n\n"
                "- 场次：EP001-SC001\n"
                "- 输入参考图：REF-HERO（顺序：1）· 输入/reference.png《女主定妆》"
                "（用途：外貌；控制：五官、服装；不得控制：构图）；"
                "PLAN-START（顺序：2）· SHOT-EP001-001《起始帧计划》"
                "（用途：起始帧；控制：构图；不得控制：人物替换）\n\n"
                "### 首帧提示词\n"
                "> Rain-soaked doorway medium close-up.\n",
                encoding="utf-8",
            )
            shot_job = root / "shot-auto.json"
            shot_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-SHOT001-KEYFRAME",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/分镜.md",
                        "source_entry": "SHOT-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/image/SHOT-EP001-001.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            shot_preview = self.prepare_and_confirm(root, shot_job)
            self.assertEqual(shot_preview["prompt"], "Rain-soaked doorway medium close-up.")
            self.assertEqual(len(shot_preview["reference_bindings"]), 1)
            self.assertEqual(shot_preview["reference_bindings"][0]["slot_id"], "REF-HERO")
            self.assertEqual(shot_preview["reference_bindings"][0]["role"], "reference_image")
            # Ensure stored job round-trips through status/run without prefix mismatch on 分镜.md.
            self.assertEqual(
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001-KEYFRAME",
                    adapter_config=self.adapter_config(directory),
                )["state"],
                "succeeded",
            )

            video_md = root / "剧集/EP001/视频提示词.md"
            video_md.write_text(
                "# EP001 视频提示词\n\n"
                "## MOTION-EP001-001 · 开口质问\n\n"
                "- 分镜：SHOT-EP001-001\n"
                "- 输入参考图：REF-START（顺序：1）· "
                "剧集/EP001/制作成果/image/SHOT-EP001-001.png《雨夜首帧》"
                "（用途：起始帧；控制：首帧构图；不得控制：口型）\n"
                "- 参考音频：REF-VOICE（顺序：1）· 输入/hero_voice.wav《女主音色样音》"
                "（用途：音色；角色：沈知意；控制：音色、咬字；不得控制：台词、语气、情绪）\n\n"
                "### 可复制提示词\n"
                "> She steps forward and speaks calmly.\n",
                encoding="utf-8",
            )
            provider_stub = Path(directory) / "provider_adapters.py"
            provider_stub.write_text(
                "import json, pathlib, sys\n"
                "payload = json.load(sys.stdin)\n"
                "out = pathlib.Path(payload['output_root']) / 'out.mp4'\n"
                "out.write_bytes(b'\\x00\\x00\\x00\\x18ftypisom')\n"
                "json.dump({'outputs': [{'target': payload['outputs'][0], 'source': str(out)}]}, sys.stdout)\n",
                encoding="utf-8",
            )
            builtin_like_cfg = Path(directory) / "builtin-seedance.json"
            builtin_like_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "seedance": {
                                "command": [sys.executable, str(provider_stub), "seedance"],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            motion_job = root / "motion-auto.json"
            motion_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-MOTION001-VOICE",
                        "modality": "video",
                        "adapter": "seedance",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "MOTION-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-001.mp4"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            motion_preview = self.prepare_and_confirm(root, motion_job)
            self.assertEqual(
                [(b["slot_id"], b["role"], b.get("character")) for b in motion_preview["reference_bindings"]],
                [
                    ("REF-START", "first_frame", None),
                    ("REF-VOICE", "reference_audio", "沈知意"),
                ],
            )
            # Built-in seedance profile permits reference_audio without manual reference_roles.
            ran = production_tool.run_job(
                root,
                job_id="EP001-MOTION001-VOICE",
                adapter_config=builtin_like_cfg,
            )
            self.assertEqual(ran["state"], "succeeded")

    def test_unsubmitted_preflight_error_keeps_confirmation_reusable_and_surfaces_safe_detail(self) -> None:
        provider_script = SUITE / "skills/short-drama-produce/scripts/provider_adapters.py"
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = root / "seedance-job.json"
            job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-PREFLIGHT",
                        "modality": "video",
                        "adapter": "seedance",
                        "prompt": "A calm close-up shot.",
                        "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-001.mp4"],
                        "parameters": {"ratio": "9:16", "duration": 5},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.prepare_and_confirm(root, job)
            bad_cfg = Path(directory) / "real-seedance.json"
            bad_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "seedance": {
                                "command": [sys.executable, str(provider_script), "seedance"],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            clean_env = {
                k: v
                for k, v in os.environ.items()
                if k not in {"ARK_API_KEY", "SEEDANCE_MODEL"}
            }
            with mock.patch.dict(os.environ, clean_env, clear=True):
                with self.assertRaisesRegex(
                    production_tool.AdapterError, "ARK_API_KEY"
                ):
                    production_tool.run_job(
                        root, job_id="EP001-PREFLIGHT", adapter_config=bad_cfg
                    )
            # Confirmation token was NOT burned because no remote task was submitted!
            status_after = production_tool.job_status(root, job_id="EP001-PREFLIGHT")
            self.assertEqual(status_after["state"], "confirmed")

            # Fixing adapter config lets the creator run immediately without re-confirming.
            good_cfg = Path(directory) / "fixture-seedance.json"
            good_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "seedance": {
                                "command": [sys.executable, str(FIXTURE_ADAPTER)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            succeeded = production_tool.run_job(
                root, job_id="EP001-PREFLIGHT", adapter_config=good_cfg
            )
            self.assertEqual(succeeded["state"], "succeeded")

    def test_batch_prepare_confirm_and_run_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            config = self.adapter_config(directory)
            job_paths = []
            for idx in (1, 2, 3):
                path = root / f"batch-job-{idx}.json"
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": "1.0",
                            "job_id": f"EP001-BATCH-00{idx}",
                            "modality": "image",
                            "adapter": "fixture",
                            "prompt": f"Batch keyframe {idx}",
                            "outputs": [
                                f"剧集/EP001/制作成果/image/BATCH-00{idx}.png"
                            ],
                            "parameters": {"size": "1024x1536"},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                job_paths.append(str(path))

            prepared = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "prepare-batch",
                    str(root),
                    "--jobs",
                    *job_paths,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            batch_preview = json.loads(prepared.stdout)
            self.assertEqual(batch_preview["job_count"], 3)
            self.assertTrue(
                batch_preview["confirmation"].startswith("CONFIRM BATCH ")
            )

            # Running batch before confirmation must fail without writing any outputs.
            premature = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "run-batch",
                    str(root),
                    "--batch-id",
                    batch_preview["batch_id"],
                    "--adapter-config",
                    str(config),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(premature.returncode, 0)
            for idx in (1, 2, 3):
                self.assertFalse(
                    (root / f"剧集/EP001/制作成果/image/BATCH-00{idx}.png").exists()
                )

            confirmed = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "confirm",
                    str(root),
                    "--confirmation",
                    batch_preview["confirmation"],
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
            self.assertEqual(json.loads(confirmed.stdout)["state"], "confirmed")

            executed = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "run-batch",
                    str(root),
                    "--batch-id",
                    batch_preview["batch_id"],
                    "--adapter-config",
                    str(config),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)
            payload = json.loads(executed.stdout)
            self.assertEqual(payload["state"], "succeeded")
            self.assertEqual(len(payload["succeeded"]), 3)
            for idx in (1, 2, 3):
                self.assertTrue(
                    (root / f"剧集/EP001/制作成果/image/BATCH-00{idx}.png").is_file()
                )

    def test_shot_keyframe_strips_leading_middle_plan_slots_pending_notes_and_nested_empty_parens(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            (root / "输入/room.png").write_bytes(b"room-ref")
            storyboard = root / "剧集/EP001/分镜.md"
            storyboard.write_text(
                "# EP001 分镜\n\n"
                "## SHOT-EP001-001 · 雨夜门口\n\n"
                "- 输入参考图："
                "PLAN-PROP（顺序：1）· IMG-PROP-01《旧伞设定》（用途：道具参考；控制：伞骨；不得控制：人物）；"
                "REF-HERO（顺序：2）· 输入/reference.png《女主定妆照》（用途：人物参考；控制：身份；不得控制：构图）；"
                "PLAN-COAT（顺序：3）· IMG-CHAR-02《风衣设定》（用途：服装参考；控制：外衣；不得控制：表情）；"
                "REF-ROOM（顺序：4）· 输入/room.png《玄关场景》（用途：场景参考；控制：门框空间；不得控制：人物）；"
                "待补参考图：许棠配饰图（IMG-PROP-02）。\n\n"
                "### 首帧提示词\n"
                "> Doorway keyframe with rain on the threshold.\n\n"
                "## SHOT-EP001-002 · 空镜\n\n"
                "- 输入参考图：无（待补参考图：许棠人物图（IMG-CHAR-01））。\n\n"
                "### 首帧提示词\n"
                "> Empty corridor with wet floor reflections.\n",
                encoding="utf-8",
            )
            shot1_job = root / "shot1.json"
            shot1_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-SHOT001-RENUM",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/分镜.md",
                        "source_entry": "SHOT-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/image/SHOT-EP001-001.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            preview1 = self.prepare_and_confirm(root, shot1_job)
            self.assertEqual(
                [(b["slot_id"], b["order"], b["role"]) for b in preview1["reference_bindings"]],
                [
                    ("REF-HERO", 1, "reference_image"),
                    ("REF-ROOM", 2, "reference_image"),
                ],
            )
            self.assertEqual(
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001-RENUM",
                    adapter_config=self.adapter_config(directory),
                )["state"],
                "succeeded",
            )

            shot2_job = root / "shot2.json"
            shot2_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-SHOT002-EMPTY-NESTED",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/分镜.md",
                        "source_entry": "SHOT-EP001-002",
                        "outputs": ["剧集/EP001/制作成果/image/SHOT-EP001-002.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            preview2 = self.prepare_and_confirm(root, shot2_job)
            self.assertEqual(preview2["reference_bindings"], [])

    def test_run_batch_partial_failure_modes_and_preflight_guards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            failing_adapter = Path(directory) / "fail_adapter.py"
            failing_adapter.write_text(
                "import json, sys\n"
                "json.dump({'error': {'provider': 'flaky', 'category': 'server', "
                "'code': 'upstream_500', 'http_status': 500, 'retryable': True, 'submitted': True}}, sys.stdout)\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            config = Path(directory) / "mixed-adapters.json"
            config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(FIXTURE_ADAPTER)],
                                "timeout_seconds": 30,
                            },
                            "flaky": {
                                "command": [sys.executable, str(failing_adapter)],
                                "timeout_seconds": 30,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            def write_batch_jobs(overwrite: bool = False) -> list[Path]:
                specs = [
                    ("EP001-B1", "fixture", "Prompt 1", "剧集/EP001/制作成果/image/B1.png"),
                    ("EP001-B2", "flaky", "Prompt 2", "剧集/EP001/制作成果/image/B2.png"),
                    ("EP001-B3", "fixture", "Prompt 3", "剧集/EP001/制作成果/image/B3.png"),
                ]
                paths: list[Path] = []
                for jid, adapter, prompt, output in specs:
                    p = root / f"{jid}.json"
                    p.write_text(
                        json.dumps(
                            {
                                "schema_version": "1.0",
                                "job_id": jid,
                                "modality": "image",
                                "adapter": adapter,
                                "prompt": prompt,
                                "outputs": [output],
                                "overwrite": overwrite,
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    paths.append(p)
                return paths

            job_files = write_batch_jobs()
            batch1 = production_tool.prepare_batch(root, job_files)
            production_tool.confirm_batch(
                root,
                batch_id=batch1["batch_id"],
                confirmation=batch1["confirmation"],
            )
            stopped = production_tool.run_batch(
                root, adapter_config=config, batch_id=batch1["batch_id"], stop_on_error=True
            )
            self.assertEqual(stopped["state"], "failed")
            self.assertEqual([item["job_id"] for item in stopped["succeeded"]], ["EP001-B1"])
            self.assertEqual([item["job_id"] for item in stopped["failed"]], ["EP001-B2"])
            self.assertEqual(stopped["remaining"], ["EP001-B3"])
            self.assertFalse((root / "剧集/EP001/制作成果/image/B3.png").exists())

            job_files = write_batch_jobs(overwrite=True)
            batch2 = production_tool.prepare_batch(root, job_files)
            production_tool.confirm_batch(
                root,
                batch_id=batch2["batch_id"],
                confirmation=batch2["confirmation"],
            )
            continued_cli = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "run-batch",
                    str(root),
                    "--batch-id",
                    batch2["batch_id"],
                    "--adapter-config",
                    str(config),
                    "--continue-on-error",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(continued_cli.returncode, 0)
            continued = json.loads(continued_cli.stdout)
            self.assertEqual([item["job_id"] for item in continued["succeeded"]], ["EP001-B1", "EP001-B3"])
            self.assertEqual([item["job_id"] for item in continued["failed"]], ["EP001-B2"])
            self.assertEqual(continued["remaining"], [])
            self.assertTrue((root / "剧集/EP001/制作成果/image/B3.png").is_file())

            # Re-preparing one job after prepare_batch must fail closed with batch_inputs_changed.
            job_files = write_batch_jobs(overwrite=True)
            batch3 = production_tool.prepare_batch(root, job_files)
            production_tool.confirm_batch(
                root,
                batch_id=batch3["batch_id"],
                confirmation=batch3["confirmation"],
            )
            mutated = json.loads(job_files[0].read_text(encoding="utf-8"))
            mutated["prompt"] = "Mutated after prepare-batch"
            job_files[0].write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
            reprepared = production_tool.prepare_job(root, job_files[0])
            production_tool.confirm_job(
                root, job_id="EP001-B1", confirmation=reprepared["confirmation"]
            )
            with self.assertRaisesRegex(
                production_tool.ConfirmationRequiredError, "batch_inputs_changed"
            ):
                production_tool.run_batch(
                    root, adapter_config=config, batch_id=batch3["batch_id"]
                )

            # Explicit job_ids reject duplicate job_ids and colliding outputs before running job 1.
            with self.assertRaisesRegex(ValueError, "duplicate job_id"):
                production_tool.run_batch(
                    root, adapter_config=config, job_ids=["EP001-B1", "EP001-B1"]
                )
            collide_a = root / "collide-a.json"
            collide_b = root / "collide-b.json"
            for jid, path in (("EP001-CA", collide_a), ("EP001-CB", collide_b)):
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": "1.0",
                            "job_id": jid,
                            "modality": "image",
                            "adapter": "fixture",
                            "prompt": f"Collide {jid}",
                            "outputs": ["剧集/EP001/制作成果/image/SHARED.png"],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                self.prepare_and_confirm(root, path)
            with self.assertRaisesRegex(ValueError, "duplicate output path"):
                production_tool.run_batch(
                    root, adapter_config=config, job_ids=["EP001-CA", "EP001-CB"]
                )
            self.assertFalse((root / "剧集/EP001/制作成果/image/SHARED.png").exists())

    def test_safe_error_detail_redacts_secrets_urls_and_local_paths(self) -> None:
        self.assertEqual(
            production_tool._safe_error_detail("  SEEDANCE_MODEL   is required "),
            "SEEDANCE_MODEL is required",
        )
        for unsafe in (
            "Authorization: Bearer tok-secret-123",
            "invalid key sk-abcdefghijkl123456",
            "api_key=my-secret-value",
            "upstream https://api.example.com/v1/tasks failed",
            "failed reading /Users/alice/private/config.json",
            r"failed reading C:\Users\alice\secret.json",
        ):
            with self.subTest(unsafe=unsafe):
                self.assertIsNone(production_tool._safe_error_detail(unsafe))
                parsed = production_tool._parse_public_adapter_error(
                    json.dumps(
                        {
                            "error": {
                                "provider": "seedance",
                                "category": "invalid_request",
                                "code": "bad_config",
                                "retryable": False,
                                "submitted": False,
                                "detail": unsafe,
                            }
                        }
                    ).encode("utf-8"),
                    profile="seedance",
                    returncode=1,
                )
                self.assertNotIn("detail", parsed)

    def test_job_status_prioritizes_running_and_resets_after_reprepare(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            config = self.adapter_config(directory)
            job_file = root / "status-reprepare.json"
            payload = {
                "schema_version": "1.0",
                "job_id": "EP001-STATUS-REPREP",
                "modality": "image",
                "adapter": "fixture",
                "prompt": "Initial portrait",
                "outputs": ["剧集/EP001/制作成果/image/STATUS-REPREP.png"],
                "overwrite": True,
            }
            job_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            preview = production_tool.prepare_job(root, job_file)
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-STATUS-REPREP")["state"],
                "needs_confirmation",
            )
            production_tool.confirm_job(
                root,
                job_id="EP001-STATUS-REPREP",
                confirmation=preview["confirmation"],
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-STATUS-REPREP")["state"],
                "confirmed",
            )
            production_tool.run_job(
                root, job_id="EP001-STATUS-REPREP", adapter_config=config
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-STATUS-REPREP")["state"],
                "succeeded",
            )

            # Re-preparing the same job_id with a new prompt changes the fingerprint
            # and must reset status to needs_confirmation instead of stale succeeded.
            payload["prompt"] = "Updated portrait after creative revision"
            payload["references"] = ["输入/reference.png"]
            job_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            production_tool.prepare_job(root, job_file)
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-STATUS-REPREP")["state"],
                "needs_confirmation",
            )

            # An active running record takes precedence even if an input changes on disk.
            stored_job = production_tool._read_job(root, "EP001-STATUS-REPREP")
            production_tool._write_run(
                root,
                "EP001-STATUS-REPREP",
                {
                    "schema_version": "1.0",
                    "run_id": "run-live-check",
                    "job_id": "EP001-STATUS-REPREP",
                    "fingerprint": stored_job["fingerprint"],
                    "status": "running",
                    "started_at": production_tool.utc_now(),
                    "finished_at": None,
                    "outputs": [],
                },
            )
            (root / "输入/reference.png").write_bytes(b"mutated-while-running")
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-STATUS-REPREP")["state"],
                "running",
            )

    def test_crlf_markdown_sources_heading_whitespace_and_symlink_guards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            lf_text = (
                "# EP001 图片提示词\n\n"
                "## IMG-EP001-001 · 雨夜设定\n\n"
                "- 参考：REF-HERO（顺序：1）· 输入/reference.png《女主定妆照》"
                "（用途：人物参考；控制：身份；不得控制：构图）\n\n"
                "### 可复制提示词\n"
                "> Cinematic rain portrait.\n"
                "> Moody key light.\n\n"
                "## IMG-EP001-002 · 后镜\n\n"
                "- 参考：无\n\n"
                "### 可复制提示词\n"
                "> Empty street.\n"
            )
            md_path = root / "剧集/EP001/图片提示词.md"
            md_path.write_bytes(lf_text.encode("utf-8"))
            job_file = root / "crlf-job.json"
            job_file.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-CRLF-001",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/图片提示词.md",
                        "source_entry": "IMG-EP001-001",
                        "prompt": "Cinematic rain portrait.\nMoody key light.",
                        "outputs": ["剧集/EP001/制作成果/image/CRLF-001.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            lf_preview = production_tool.prepare_job(root, job_file)

            # Converting the Markdown file to CRLF must keep the section hash and
            # confirmation valid without invalidating the prepared job.
            md_path.write_bytes(lf_text.replace("\n", "\r\n").encode("utf-8"))
            production_tool.confirm_job(
                root,
                job_id="EP001-CRLF-001",
                confirmation=lf_preview["confirmation"],
            )
            ran = production_tool.run_job(
                root,
                job_id="EP001-CRLF-001",
                adapter_config=self.adapter_config(directory),
            )
            self.assertEqual(ran["state"], "succeeded")

            # Horizontal whitespace only: `##\nIMG-...` must not match as a heading.
            with self.assertRaisesRegex(ValueError, "missing from Markdown"):
                production_tool._markdown_section(
                    "##\nIMG-EP001-009\n### 可复制提示词\n> Prompt\n",
                    "IMG-EP001-009",
                )
            with self.assertRaisesRegex(ValueError, "no copyable prompt"):
                production_tool._copyable_prompt("###\n可复制提示词\n> Prompt\n")

            # Symlinked Markdown sources must be rejected by _read_project_input_bytes.
            outside = Path(directory) / "outside.md"
            outside.write_text(lf_text, encoding="utf-8")
            md_path.unlink()
            try:
                md_path.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            symlink_job = root / "symlink-md.json"
            symlink_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-SYMLINK-MD",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/图片提示词.md",
                        "source_entry": "IMG-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/image/SYM.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "symlink|unsafe job input path"):
                production_tool.prepare_job(root, symlink_job)

    def test_batch_resume_skips_succeeded_jobs_and_status_supports_batch_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            counter_file = Path(directory) / "counts.json"
            flag_file = Path(directory) / "fail_second.flag"
            flag_file.write_text("fail", encoding="utf-8")
            counting_adapter = Path(directory) / "counting_adapter.py"
            counting_adapter.write_text(
                "import json, pathlib, sys\n"
                f"counts_path = pathlib.Path({str(counter_file)!r})\n"
                f"flag_path = pathlib.Path({str(flag_file)!r})\n"
                "payload = json.load(sys.stdin)\n"
                "jid = payload['job_id']\n"
                "counts = json.loads(counts_path.read_text('utf-8')) if counts_path.exists() else {}\n"
                "counts[jid] = counts.get(jid, 0) + 1\n"
                "counts_path.write_text(json.dumps(counts), 'utf-8')\n"
                "if jid == 'EP001-R2' and flag_path.exists():\n"
                "    json.dump({'error': {'provider': 'counting', 'category': 'server', "
                "'code': 'upstream_502', 'http_status': 502, 'retryable': True, 'submitted': True}}, sys.stdout)\n"
                "    raise SystemExit(1)\n"
                "out = pathlib.Path(payload['output_root']) / 'result.png'\n"
                "out.write_bytes(b'\\x89PNG\\r\\n\\x1a\\n' + jid.encode('ascii'))\n"
                "json.dump({'outputs': [{'target': payload['outputs'][0], 'source': str(out)}]}, sys.stdout)\n",
                encoding="utf-8",
            )
            config = Path(directory) / "counting-config.json"
            config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "counting": {
                                "command": [sys.executable, str(counting_adapter)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            job_files: list[Path] = []
            for jid in ("EP001-R1", "EP001-R2", "EP001-R3"):
                path = root / f"{jid}.json"
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": "1.0",
                            "job_id": jid,
                            "modality": "image",
                            "adapter": "counting",
                            "prompt": f"Render {jid}",
                            "outputs": [f"剧集/EP001/制作成果/image/{jid}.png"],
                            "overwrite": False,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                job_files.append(path)

            preview = production_tool.prepare_batch(root, job_files)
            for summary in preview["jobs"]:
                self.assertTrue(
                    summary["confirmation"].startswith(f"CONFIRM {summary['job_id']} ")
                )
            initial_status = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "status",
                    str(root),
                    "--batch-id",
                    preview["batch_id"],
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(initial_status.returncode, 0, initial_status.stderr)
            self.assertEqual(json.loads(initial_status.stdout)["state"], "needs_confirmation")

            production_tool.confirm_batch(
                root,
                batch_id=preview["batch_id"],
                confirmation=preview["confirmation"],
            )
            self.assertEqual(
                production_tool.batch_status(root, batch_id=preview["batch_id"])["state"],
                "confirmed",
            )

            first_run = production_tool.run_batch(
                root, adapter_config=config, batch_id=preview["batch_id"]
            )
            self.assertEqual(first_run["state"], "failed")
            self.assertEqual([item["job_id"] for item in first_run["succeeded"]], ["EP001-R1"])
            self.assertEqual([item["job_id"] for item in first_run["failed"]], ["EP001-R2"])
            self.assertEqual(first_run["remaining"], ["EP001-R3"])
            self.assertEqual(
                production_tool.batch_status(root, batch_id=preview["batch_id"])["state"],
                "failed",
            )

            # Fix R2, reconfirm only R2 with its per-job confirmation token from prepare_batch,
            # and resume run-batch: R1 must be skipped without re-invoking the adapter or failing overwrite=False.
            flag_file.unlink()
            production_tool.confirm_job(
                root,
                job_id="EP001-R2",
                confirmation=preview["jobs"][1]["confirmation"],
            )
            self.assertEqual(
                production_tool.batch_status(root, batch_id=preview["batch_id"])["state"],
                "confirmed",
            )
            resumed = production_tool.run_batch(
                root, adapter_config=config, batch_id=preview["batch_id"]
            )
            self.assertEqual(resumed["state"], "succeeded")
            self.assertEqual(resumed["skipped"], ["EP001-R1"])
            self.assertEqual(
                [item["job_id"] for item in resumed["succeeded"]],
                ["EP001-R1", "EP001-R2", "EP001-R3"],
            )
            counts = json.loads(counter_file.read_text(encoding="utf-8"))
            self.assertEqual(counts, {"EP001-R1": 1, "EP001-R2": 2, "EP001-R3": 1})
            self.assertEqual(
                production_tool.batch_status(root, batch_id=preview["batch_id"])["state"],
                "succeeded",
            )

    def test_superseded_failed_provider_handle_is_not_orphaned_or_recollected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            fail_flag = Path(directory) / "fail_first.flag"
            fail_flag.write_text("1", encoding="utf-8")
            recoverable_adapter = Path(directory) / "recoverable_adapter.py"
            recoverable_adapter.write_text(
                "import json, pathlib, sys\n"
                f"flag = pathlib.Path({str(fail_flag)!r})\n"
                "payload = json.load(sys.stdin)\n"
                "if flag.exists():\n"
                "    hp = pathlib.Path(payload['handle_path'])\n"
                "    hp.parent.mkdir(parents=True, exist_ok=True)\n"
                "    hp.write_text("
                "json.dumps({'provider_job_id': 'remote-attempt-1'}), 'utf-8')\n"
                "    json.dump({'error': {'provider': 'rec', 'category': 'timeout', "
                "'code': 'task_poll_timeout', 'retryable': True, 'submitted': True}}, sys.stdout)\n"
                "    raise SystemExit(1)\n"
                "out = pathlib.Path(payload['output_root']) / 'ok.mp4'\n"
                "out.write_bytes(b'\\x00\\x00\\x00\\x18ftypmp42\\x00\\x00\\x00\\x00mp42isom')\n"
                "json.dump({'outputs': [{'target': payload['outputs'][0], 'source': str(out)}], "
                "'provider_job_id': 'remote-attempt-2'}, sys.stdout)\n",
                encoding="utf-8",
            )
            config = Path(directory) / "rec-config.json"
            config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "rec": {
                                "command": [sys.executable, str(recoverable_adapter)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            job_file = root / "rec-job.json"
            job_file.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-ORPHAN-SUPERSEDED",
                        "modality": "video",
                        "adapter": "rec",
                        "prompt": "Push in through rain.",
                        "outputs": ["剧集/EP001/制作成果/video/ORPHAN.mp4"],
                        "overwrite": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            preview = self.prepare_and_confirm(root, job_file)
            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root, job_id="EP001-ORPHAN-SUPERSEDED", adapter_config=config
                )
            audit_before = production_tool.audit_project(root)
            self.assertIn(
                "orphaned_provider_job",
                {item["code"] for item in audit_before["problems"]},
            )

            # Reconfirm and succeed under the exact same job fingerprint.
            fail_flag.unlink()
            production_tool.confirm_job(
                root,
                job_id="EP001-ORPHAN-SUPERSEDED",
                confirmation=preview["confirmation"],
            )
            second = production_tool.run_job(
                root, job_id="EP001-ORPHAN-SUPERSEDED", adapter_config=config
            )
            self.assertEqual(second["state"], "succeeded")

            audit_after = production_tool.audit_project(root)
            self.assertEqual(audit_after["problems"], [])
            with self.assertRaisesRegex(RuntimeError, "nothing to collect"):
                production_tool.collect_job(
                    root, job_id="EP001-ORPHAN-SUPERSEDED", adapter_config=config
                )

    def test_motion_empty_reference_accepts_only_explicit_t2v_and_rejects_pending_or_unsubmittable(
        self,
    ) -> None:
        for valid_empty in ("无", "无。", "无（文生视频）", "无（文生视频）。"):
            with self.subTest(valid_empty=valid_empty):
                with tempfile.TemporaryDirectory() as directory:
                    root = self.make_project(directory)
                    job = self.write_creator_video_job(root)
                    source = root / "剧集/EP001/视频提示词.md"
                    source.write_text(
                        source.read_text(encoding="utf-8").replace(
                            "- 输入参考图：REF-HERO（顺序：1）· "
                            "输入/reference.png《女主定妆照》"
                            "（控制：身份、造型；不得控制：构图、动作）",
                            f"- 输入参考图：{valid_empty}",
                        ),
                        encoding="utf-8",
                    )
                    document = json.loads(job.read_text(encoding="utf-8"))
                    document["reference_bindings"] = []
                    job.write_text(
                        json.dumps(document, ensure_ascii=False), encoding="utf-8"
                    )
                    preview = production_tool.prepare_job(root, job)
                    self.assertEqual(preview["reference_bindings"], [])

        for blocked in (
            "无（待补参考图：IMG-EP001-001）",
            "无（待续接上一段视频，不可提交）",
            "无（待补参考图：女主角图（IMG-EP001-HERO））。",
            "REF-HERO（顺序：1）· 输入/reference.png《女主定妆照》"
            "（控制：身份、造型；不得控制：构图、动作）；待补参考图：IMG-EP001-002",
        ):
            with self.subTest(blocked=blocked):
                with tempfile.TemporaryDirectory() as directory:
                    root = self.make_project(directory)
                    job = self.write_creator_video_job(root)
                    source = root / "剧集/EP001/视频提示词.md"
                    source.write_text(
                        source.read_text(encoding="utf-8").replace(
                            "- 输入参考图：REF-HERO（顺序：1）· "
                            "输入/reference.png《女主定妆照》"
                            "（控制：身份、造型；不得控制：构图、动作）",
                            f"- 输入参考图：{blocked}",
                        ),
                        encoding="utf-8",
                    )
                    document = json.loads(job.read_text(encoding="utf-8"))
                    if not blocked.startswith("REF-HERO"):
                        document["reference_bindings"] = []
                    job.write_text(
                        json.dumps(document, ensure_ascii=False), encoding="utf-8"
                    )
                    with self.assertRaisesRegex(
                        ValueError, "pending or unsubmittable"
                    ):
                        production_tool.prepare_job(root, job)

        # SHOT-* in 分镜.md renders its own keyframe image, so pending input notes remain allowed there.
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            storyboard = root / "剧集/EP001/分镜.md"
            shot_prompt = "Medium close-up of a woman standing in rain light."
            storyboard.write_text(
                "# EP001 分镜\n\n"
                "## SHOT-EP001-001 · 雨门前\n\n"
                "- 输入参考图：无（待补参考图：IMG-EP001-HERO）\n\n"
                "### 首帧提示词\n"
                f"> {shot_prompt}\n",
                encoding="utf-8",
            )
            shot_job = root / "shot-job.json"
            shot_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-SHOT001-KEYFRAME",
                        "modality": "image",
                        "adapter": "fixture",
                        "prompt": shot_prompt,
                        "source": "剧集/EP001/分镜.md",
                        "source_entry": "SHOT-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/image/SHOT-001.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            shot_preview = production_tool.prepare_job(root, shot_job)
            self.assertEqual(shot_preview["source_entry"], "SHOT-EP001-001")

        # Strict creator section heading & copyable prompt heading alignment.
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_creator_image_job(root)
            img_doc = root / "剧集/EP001/图片提示词.md"
            original = img_doc.read_text(encoding="utf-8")
            img_doc.write_text(
                original.replace("### 可复制提示词", "### 可复制通用提示词"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no copyable prompt"):
                production_tool.prepare_job(root, job)

            img_doc.write_text(
                original.replace(
                    "## IMG-EP001-HERO · 女主角色板",
                    "## `IMG-EP001-HERO` · 女主角色板",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing from Markdown"):
                production_tool.prepare_job(root, job)

    def test_run_job_does_not_clobber_run_already_succeeded_by_collect_job(
        self,
    ) -> None:
        for adapter_outcome in ("raises_after_collect", "returns_stale_after_collect"):
            with self.subTest(adapter_outcome=adapter_outcome):
                with tempfile.TemporaryDirectory() as directory:
                    root = self.make_project(directory)
                    config = Path(directory) / "race-config.json"
                    config.write_text(
                        json.dumps(
                            {
                                "adapters": {
                                    "fixture": {
                                        "command": [sys.executable, str(FIXTURE_ADAPTER)],
                                        "timeout_seconds": 30,
                                    }
                                }
                            }
                        ),
                        encoding="utf-8",
                    )
                    job_file = self.write_job(
                        root,
                        job_id="EP001-RACE",
                        modality="image",
                        overwrite=True,
                    )
                    self.prepare_and_confirm(root, job_file)
                    collected_bytes = b"\x89PNG\r\n\x1a\ncollected-winner"
                    stale_bytes = b"\x89PNG\r\n\x1a\nstale-runner"

                    def fake_run_adapter(
                        command,
                        timeout,
                        payload,
                        project_root,
                        *,
                        consumes_confirmation=True,
                        _collected_bytes=collected_bytes,
                        _stale_bytes=stale_bytes,
                        _root=root,
                        _config=config,
                        _adapter_outcome=adapter_outcome,
                    ):
                        out_dir = Path(payload["output_root"])
                        target_rel = payload["outputs"][0]
                        if payload.get("collect_provider_job_id"):
                            collected_src = out_dir / "collected.png"
                            collected_src.write_bytes(_collected_bytes)
                            return {
                                "outputs": [
                                    {"target": target_rel, "source": str(collected_src)}
                                ],
                                "provider_job_id": payload["collect_provider_job_id"],
                            }
                        handle_path = Path(payload["handle_path"])
                        handle_path.parent.mkdir(parents=True, exist_ok=True)
                        handle_path.write_text(
                            json.dumps({"provider_job_id": "remote-race-handle"}),
                            encoding="utf-8",
                        )
                        collected = production_tool.collect_job(
                            _root, job_id="EP001-RACE", adapter_config=_config
                        )
                        self.assertEqual(collected["state"], "succeeded")
                        if _adapter_outcome == "raises_after_collect":
                            raise production_tool.AdapterError(
                                "poll timed out after collect already finished",
                                public_error={
                                    "provider": "race",
                                    "category": "timeout",
                                    "code": "task_poll_timeout",
                                    "retryable": True,
                                    "submitted": True,
                                },
                            )
                        stale_src = out_dir / "stale.png"
                        stale_src.write_bytes(_stale_bytes)
                        return {
                            "outputs": [{"target": target_rel, "source": str(stale_src)}],
                            "provider_job_id": "remote-race-handle",
                        }

                    with mock.patch.object(
                        production_tool, "_run_adapter", side_effect=fake_run_adapter
                    ):
                        expected_exc = (
                            production_tool.AdapterError
                            if adapter_outcome == "raises_after_collect"
                            else RuntimeError
                        )
                        with self.assertRaises(expected_exc):
                            production_tool.run_job(
                                root, job_id="EP001-RACE", adapter_config=config
                            )

                    status = production_tool.job_status(root, job_id="EP001-RACE")
                    self.assertEqual(status["state"], "succeeded")
                    history = production_tool._read_run_history(root, "EP001-RACE")
                    self.assertEqual(len(history), 1)
                    self.assertEqual(history[0]["status"], "succeeded")
                    output_file = root / "剧集/EP001/制作成果/image/EP001-RACE.png"
                    self.assertEqual(output_file.read_bytes(), collected_bytes)
                    self.assertEqual(production_tool.audit_project(root)["problems"], [])

    def test_collect_job_preflights_all_output_targets_before_adapter_and_before_disk_write(
        self,
    ) -> None:
        for stage in ("before_adapter", "during_adapter"):
            with self.subTest(stage=stage):
                with tempfile.TemporaryDirectory() as directory:
                    root = self.make_project(directory)
                    config = Path(directory) / "multi-collect-config.json"
                    config.write_text(
                        json.dumps(
                            {
                                "adapters": {
                                    "fixture": {
                                        "command": [sys.executable, str(FIXTURE_ADAPTER)],
                                        "timeout_seconds": 30,
                                    }
                                }
                            }
                        ),
                        encoding="utf-8",
                    )
                    out1 = "剧集/EP001/制作成果/image/MULTI-1.png"
                    out2 = "剧集/EP001/制作成果/image/MULTI-2.png"
                    job_file = root / "multi-collect-job.json"
                    job_file.write_text(
                        json.dumps(
                            {
                                "schema_version": "1.0",
                                "job_id": "EP001-MULTI-COLLECT",
                                "modality": "image",
                                "adapter": "fixture",
                                "prompt": "Two frames",
                                "outputs": [out1, out2],
                                "overwrite": False,
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    self.prepare_and_confirm(root, job_file)

                    def fail_with_handle(command, timeout, payload, project_root):
                        hp = Path(payload["handle_path"])
                        hp.parent.mkdir(parents=True, exist_ok=True)
                        hp.write_text(
                            json.dumps({"provider_job_id": "remote-multi-1"}),
                            encoding="utf-8",
                        )
                        raise production_tool.AdapterError(
                            "interrupted",
                            public_error={
                                "provider": "fixture",
                                "category": "timeout",
                                "code": "task_poll_timeout",
                                "retryable": True,
                                "submitted": True,
                            },
                        )

                    with mock.patch.object(
                        production_tool, "_run_adapter", side_effect=fail_with_handle
                    ):
                        with self.assertRaises(production_tool.AdapterError):
                            production_tool.run_job(
                                root,
                                job_id="EP001-MULTI-COLLECT",
                                adapter_config=config,
                            )

                    out2_path = root / out2
                    out2_path.parent.mkdir(parents=True, exist_ok=True)
                    if stage == "before_adapter":
                        out2_path.write_bytes(b"\x89PNG\r\n\x1a\nexisting-second")

                    adapter_calls = 0

                    def collect_adapter(
                        command,
                        timeout,
                        payload,
                        project_root,
                        *,
                        consumes_confirmation=True,
                        _stage=stage,
                        _out2_path=out2_path,
                        _out1=out1,
                        _out2=out2,
                    ):
                        nonlocal adapter_calls
                        adapter_calls += 1
                        out_dir = Path(payload["output_root"])
                        s1 = out_dir / "1.png"
                        s2 = out_dir / "2.png"
                        s1.write_bytes(b"\x89PNG\r\n\x1a\nnew-first")
                        s2.write_bytes(b"\x89PNG\r\n\x1a\nnew-second")
                        if _stage == "during_adapter":
                            _out2_path.write_bytes(b"\x89PNG\r\n\x1a\nappeared-mid-collect")
                        return {
                            "outputs": [
                                {"target": _out1, "source": str(s1)},
                                {"target": _out2, "source": str(s2)},
                            ],
                            "provider_job_id": "remote-multi-1",
                        }

                    with mock.patch.object(
                        production_tool, "_run_adapter", side_effect=collect_adapter
                    ):
                        with self.assertRaises(FileExistsError):
                            production_tool.collect_job(
                                root,
                                job_id="EP001-MULTI-COLLECT",
                                adapter_config=config,
                            )

                    if stage == "before_adapter":
                        self.assertEqual(adapter_calls, 0)
                    else:
                        self.assertEqual(adapter_calls, 1)
                    self.assertFalse(
                        (root / out1).exists(),
                        "第一个输出文件不应在第二个输出冲突时被半途写入磁盘",
                    )

    def test_cli_batch_id_and_confirm_batch_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job1 = self.write_job(root, job_id="EP001-CLI-B1")
            job2_doc = json.loads(job1.read_text(encoding="utf-8"))
            job2_doc["job_id"] = "EP001-CLI-B2"
            job2_doc["outputs"] = ["剧集/EP001/制作成果/image/EP001-CLI-B2.png"]
            job2 = root / "job2.json"
            job2.write_text(
                json.dumps(job2_doc, ensure_ascii=False), encoding="utf-8"
            )

            def run_cli(*args: str) -> dict:
                proc = subprocess.run(
                    [sys.executable, "-B", str(PRODUCTION_SCRIPT), *args],
                    capture_output=True,
                    text=True,
                    check=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                return json.loads(proc.stdout)

            prepared = run_cli(
                "prepare-batch",
                str(root),
                "--jobs",
                str(job1),
                str(job2),
                "--batch-id",
                "batch-cli-round3",
            )
            self.assertEqual(prepared["batch_id"], "batch-cli-round3")

            confirmed = run_cli(
                "confirm-batch",
                str(root),
                "--batch-id",
                "batch-cli-round3",
                "--confirmation",
                prepared["confirmation"],
            )
            self.assertEqual(confirmed["state"], "confirmed")

            # `confirm --batch-id` also accepts the batch confirmation token via the single-command alias.
            prepared2 = run_cli(
                "prepare-batch",
                str(root),
                "--jobs",
                str(job1),
                str(job2),
                "--batch-id",
                "batch-cli-alias",
            )
            confirmed2 = run_cli(
                "confirm",
                str(root),
                "--batch-id",
                "batch-cli-alias",
                "--confirmation",
                prepared2["confirmation"],
            )
            self.assertEqual(confirmed2["state"], "confirmed")

    def test_custom_adapter_profile_preserves_structured_error_and_keeps_confirmation(
        self,
    ) -> None:
        provider_script = SUITE / "skills/short-drama-produce/scripts/provider_adapters.py"
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            config = Path(directory) / "custom-profile-config.json"
            pre_json_script = Path(directory) / "pre_json_fail.py"
            pre_json_script.write_text(
                "import json, sys\n"
                'print(json.dumps({"error": {"provider": "seedance", "category": "configuration", '
                '"code": "missing_api_key", "retryable": False, "submitted": False, '
                '"detail": "Missing API key before stdin"}}))\n'
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "my-seedance-profile": {
                                "command": [
                                    sys.executable,
                                    str(provider_script),
                                    "seedance",
                                ],
                                "timeout_seconds": 30,
                            },
                            "my-prejson-profile": {
                                "command": [
                                    sys.executable,
                                    str(pre_json_script),
                                    "--provider",
                                    "seedance",
                                ],
                                "timeout_seconds": 30,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            clean_env = {
                k: v
                for k, v in os.environ.items()
                if k not in {"ARK_API_KEY", "VOLC_ARK_API_KEY", "SEEDANCE_API_KEY"}
            }
            for profile, job_id in (
                ("my-seedance-profile", "EP001-CUSTOM-PROF-1"),
                ("my-prejson-profile", "EP001-CUSTOM-PROF-2"),
            ):
                with self.subTest(profile=profile):
                    job_file = root / f"{job_id}.json"
                    job_file.write_text(
                        json.dumps(
                            {
                                "schema_version": "1.0",
                                "job_id": job_id,
                                "modality": "video",
                                "adapter": profile,
                                "prompt": "vertical close-up",
                                "outputs": [f"剧集/EP001/制作成果/video/{job_id}.mp4"],
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    self.prepare_and_confirm(root, job_file)
                    with mock.patch.dict(os.environ, clean_env, clear=True):
                        with self.assertRaises(production_tool.AdapterError) as ctx:
                            production_tool.run_job(
                                root, job_id=job_id, adapter_config=config
                            )
                    self.assertIsNotNone(ctx.exception.public_error)
                    assert ctx.exception.public_error is not None
                    self.assertEqual(ctx.exception.public_error["provider"], profile)
                    self.assertFalse(ctx.exception.public_error["submitted"])
                    self.assertEqual(
                        production_tool.job_status(root, job_id=job_id)["state"],
                        "confirmed",
                    )

    def test_collect_terminal_failure_unlocks_interrupted_running_job_and_clears_audit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            config = self.adapter_config(directory)
            job_file = self.write_job(root, job_id="EP001-COLLECT-TERM", modality="video")
            self.prepare_and_confirm(root, job_file)

            def interrupt_after_submit(
                command, timeout, payload, adapter_root, *, consumes_confirmation=True
            ):
                hp = Path(payload["handle_path"])
                hp.parent.mkdir(parents=True, exist_ok=True)
                hp.write_text(
                    json.dumps({"provider_job_id": "remote-term-99"}), encoding="utf-8"
                )
                raise KeyboardInterrupt("simulated operator ctrl-c")

            with mock.patch.object(
                production_tool, "_run_adapter", side_effect=interrupt_after_submit
            ):
                with self.assertRaises(KeyboardInterrupt):
                    production_tool.run_job(
                        root, job_id="EP001-COLLECT-TERM", adapter_config=config
                    )

            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-COLLECT-TERM")["state"],
                "running",
            )

            terminal_script = Path(directory) / "terminal_collect.py"
            terminal_script.write_text(
                "import json, sys\n"
                "job = json.load(sys.stdin)\n"
                'print(json.dumps({"error": {"provider": job["adapter"], "category": "provider_task", '
                '"code": "task_failed", "retryable": False, "submitted": True, '
                '"request_id": job["collect_provider_job_id"], '
                '"detail": "Remote generation rejected"}}))\n'
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            term_config = Path(directory) / "term-config.json"
            term_config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(terminal_script)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(production_tool.AdapterError) as ctx:
                production_tool.collect_job(
                    root, job_id="EP001-COLLECT-TERM", adapter_config=term_config
                )
            self.assertIn("confirmation was not required", str(ctx.exception))
            self.assertNotIn("confirmation was consumed", str(ctx.exception))

            status = production_tool.job_status(root, job_id="EP001-COLLECT-TERM")
            self.assertEqual(status["state"], "failed")
            last_run = production_tool._read_run_history(root, "EP001-COLLECT-TERM")[-1]
            self.assertEqual(last_run["status"], "failed")
            self.assertTrue(last_run["collected"])
            self.assertEqual(last_run["provider_job_id"], "remote-term-99")
            audit_codes = [
                item["code"] for item in production_tool.audit_project(root)["problems"]
            ]
            self.assertNotIn("orphaned_provider_job", audit_codes)
            self.assertNotIn("running_attempt", audit_codes)
            self.assertEqual(audit_codes, ["terminal_failure"])

            # Job is unlocked: creator can re-prepare, confirm, and run cleanly.
            self.prepare_and_confirm(root, job_file)
            rerun = production_tool.run_job(
                root, job_id="EP001-COLLECT-TERM", adapter_config=config
            )
            self.assertEqual(rerun["state"], "succeeded")
            self.assertEqual(production_tool.audit_project(root)["problems"], [])

    def test_group_source_entries_opus_audio_refs_and_pending_ref_guards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            opus_bytes = b"OggS" + b"\x00" * 24 + b"OpusHead" + b"\x01\x02\x00\x00"
            (root / "输入/voice.opus").write_bytes(opus_bytes)
            video_md = root / "剧集/EP001/视频提示词.md"
            video_md.write_text(
                "# EP001 视频提示词\n\n"
                "## MOTION-EP001-001 · 首镜\n"
                "- 分镜：SHOT-EP001-001\n"
                "- 输入参考图：无（文生视频）\n\n"
                "### 可复制提示词\n"
                "> 镜头1\n\n"
                "## GROUP-EP001-01 · 双镜合拍（省输入参考图 + opus 参考音频）\n"
                "- 成员：MOTION-EP001-001\n"
                "- 时长：5s\n"
                "- 参考音频：REF-VOICE-01（顺序：1）· 输入/voice.opus《男主音色》（用途：声音参考；角色：江晨；控制：音色；不得控制：台词）\n\n"
                "### 可复制提示词\n"
                "> 镜头1：江晨低声开口。\n\n"
                "## GROUP-EP001-02 · 带输入参考图的合拍\n"
                "- 成员：MOTION-EP001-001\n"
                "- 输入参考图：REF-HERO-01（顺序：1）· 输入/reference.png《定妆》（用途：主体；控制：外貌；不得控制：动作）\n\n"
                "### 可复制提示词\n"
                "> 镜头1：江晨转身。\n\n"
                "## GROUP-EP001-03 · 待补参考图的合拍\n"
                "- 成员：MOTION-EP001-001\n"
                "- 输入参考图：无；待补参考图：等首帧定稿\n\n"
                "### 可复制提示词\n"
                "> 镜头1：草稿。\n",
                encoding="utf-8",
            )

            g1_job = root / "g1.json"
            g1_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-GROUP-01",
                        "modality": "video",
                        "adapter": "fixture",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "GROUP-EP001-01",
                        "outputs": ["剧集/EP001/制作成果/video/GROUP-01.mp4"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            prepared_g1 = production_tool.prepare_job(root, g1_job)
            stored_g1 = production_tool._read_job(root, "EP001-GROUP-01")
            self.assertEqual(len(stored_g1["reference_bindings"]), 1)
            self.assertEqual(
                stored_g1["reference_bindings"][0]["path"], "输入/voice.opus"
            )
            self.assertEqual(
                stored_g1["reference_bindings"][0]["role"], "reference_audio"
            )
            production_tool.confirm_job(
                root,
                job_id="EP001-GROUP-01",
                confirmation=prepared_g1["confirmation"],
            )
            audio_cfg = Path(directory) / "audio-adapters.json"
            audio_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(FIXTURE_ADAPTER)],
                                "timeout_seconds": 30,
                                "reference_roles": ["reference_audio", "reference_image"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            ran_g1 = production_tool.run_job(
                root, job_id="EP001-GROUP-01", adapter_config=audio_cfg
            )
            self.assertEqual(ran_g1["state"], "succeeded")

            g2_job = root / "g2.json"
            g2_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-GROUP-02",
                        "modality": "video",
                        "adapter": "fixture",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "GROUP-EP001-02",
                        "outputs": ["剧集/EP001/制作成果/video/GROUP-02.mp4"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            production_tool.prepare_job(root, g2_job)
            stored_g2 = production_tool._read_job(root, "EP001-GROUP-02")
            self.assertEqual(len(stored_g2["reference_bindings"]), 1)

            g3_job = root / "g3.json"
            g3_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-GROUP-03",
                        "modality": "video",
                        "adapter": "fixture",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "GROUP-EP001-03",
                        "outputs": ["剧集/EP001/制作成果/video/GROUP-03.mp4"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "pending or unsubmittable"):
                production_tool.prepare_job(root, g3_job)

            # IMG-* `- 参考：无；待补参考图：…` must also be blocked rather than returning [].
            img_md = root / "剧集/EP001/图片提示词.md"
            img_md.write_bytes(
                (
                    "\ufeff# EP001 图片提示词\r\n\r\n"
                    "## IMG-EP001-001 · 正常条目\r\n"
                    "- 参考：无（纯文生图（首版））\r\n\r\n"
                    "### 可复制提示词\r\n"
                    "> Keep literal `<!-- tag -->` in prompt\r\n"
                    "#### 附注\r\n"
                    "<!-- unclosed trailing comment\r\n"
                ).encode("utf-8")
            )
            img_ok_job = root / "img-ok.json"
            img_ok_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-IMG-BOM-CRLF",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/图片提示词.md",
                        "source_entry": "IMG-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/image/IMG-001.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            prepared_img = production_tool.prepare_job(root, img_ok_job)
            self.assertTrue(prepared_img["confirmation"])
            stored_img = production_tool._read_job(root, "EP001-IMG-BOM-CRLF")
            self.assertEqual(
                stored_img["prompt"], "Keep literal `<!-- tag -->` in prompt"
            )

            img_md.write_text(
                "# EP001 图片提示词\n\n"
                "## IMG-EP001-002 · 待补条目\n"
                "- 参考：无；待补参考图：等外景参考\n\n"
                "### 可复制提示词\n"
                "> Pending ref prompt\n",
                encoding="utf-8",
            )
            img_pending_job = root / "img-pending.json"
            img_pending_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-IMG-PENDING",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/图片提示词.md",
                        "source_entry": "IMG-EP001-002",
                        "outputs": ["剧集/EP001/制作成果/image/IMG-002.png"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "pending or unsubmittable"):
                production_tool.prepare_job(root, img_pending_job)

    def test_prepare_enforces_input_budget_and_multi_output_commit_rolls_back_atomically(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job_file = self.write_job(root, job_id="EP001-BUDGET")
            with mock.patch.object(production_tool, "MAX_TOTAL_INPUT_BYTES", 8):
                with self.assertRaisesRegex(ValueError, "exceed the production size limit"):
                    production_tool.prepare_job(root, job_file)

            out1 = "剧集/EP001/制作成果/image/STAGE-1.png"
            out2 = "剧集/EP001/制作成果/image/STAGE-2.png"
            multi_job = root / "stage-multi.json"
            multi_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-STAGE-MULTI",
                        "modality": "image",
                        "adapter": "fixture",
                        "prompt": "Two outputs",
                        "outputs": [out1, out2],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.prepare_and_confirm(root, multi_job)

            bad_multi_script = Path(directory) / "bad_multi.py"
            bad_multi_script.write_text(
                "import json, pathlib, sys\n"
                "job = json.load(sys.stdin)\n"
                "out = pathlib.Path(job['output_root'])\n"
                "s1 = out / 'good.png'\n"
                "s2 = out / 'bad_dir_output'\n"
                "s1.write_bytes(b'\\x89PNG\\r\\n\\x1a\\ngood')\n"
                "s2.mkdir()\n"
                "print(json.dumps({'outputs': [\n"
                "  {'target': job['outputs'][0], 'source': str(s1)},\n"
                "  {'target': job['outputs'][1], 'source': str(s2)},\n"
                "]}))\n",
                encoding="utf-8",
            )
            bad_multi_cfg = Path(directory) / "bad-multi-cfg.json"
            bad_multi_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(bad_multi_script)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(production_tool.AdapterError, "unsafe"):
                production_tool.run_job(
                    root,
                    job_id="EP001-STAGE-MULTI",
                    adapter_config=bad_multi_cfg,
                )
            self.assertFalse((root / out1).exists())
            self.assertFalse((root / out2).exists())
            out_dir = (root / out1).parent
            if out_dir.exists():
                self.assertEqual(list(out_dir.glob(".short-drama-tmp-*")), [])

    def test_resumed_batch_consumes_reusable_job_receipt_and_marks_batch_succeeded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            j1 = self.write_job(root, job_id="EP001-RESUME-1", overwrite=True)
            j2_doc = json.loads(j1.read_text(encoding="utf-8"))
            j2_doc["job_id"] = "EP001-RESUME-2"
            j2_doc["outputs"] = ["剧集/EP001/制作成果/image/EP001-RESUME-2.png"]
            j2 = root / "resume-2.json"
            j2.write_text(json.dumps(j2_doc, ensure_ascii=False), encoding="utf-8")

            flaky_marker = Path(directory) / "fail-once.flag"
            flaky_marker.write_text("fail", encoding="utf-8")
            flaky_adapter = Path(directory) / "flaky_adapter.py"
            flaky_adapter.write_text(
                "import json, pathlib, sys\n"
                "job = json.load(sys.stdin)\n"
                f"flag = pathlib.Path({str(flaky_marker)!r})\n"
                "if job['job_id'] == 'EP001-RESUME-2' and flag.exists():\n"
                "    flag.unlink()\n"
                "    print(json.dumps({'error': {'provider': 'fixture', 'category': 'remote',\n"
                "        'code': 'upstream_500', 'retryable': True, 'submitted': True}}))\n"
                "    raise SystemExit(1)\n"
                "out = pathlib.Path(job['output_root']) / 'ok.png'\n"
                "out.write_bytes(b'\\x89PNG\\r\\n\\x1a\\nok')\n"
                "print(json.dumps({'outputs': [{'target': job['outputs'][0], 'source': str(out)}]}))\n",
                encoding="utf-8",
            )
            cfg = Path(directory) / "flaky-cfg.json"
            cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(flaky_adapter)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            prepared = production_tool.prepare_batch(
                root, [j1, j2], batch_id="batch-resume"
            )
            production_tool.confirm_batch(
                root, confirmation=prepared["confirmation"], batch_id="batch-resume"
            )
            first = production_tool.run_batch(
                root, adapter_config=cfg, batch_id="batch-resume"
            )
            self.assertEqual(first["state"], "failed")
            self.assertEqual([item["job_id"] for item in first["succeeded"]], ["EP001-RESUME-1"])
            self.assertEqual([item["job_id"] for item in first["failed"]], ["EP001-RESUME-2"])

            # Re-confirm batch to retry the failed job while reusing EP001-RESUME-1.
            production_tool.confirm_batch(
                root, confirmation=prepared["confirmation"], batch_id="batch-resume"
            )
            second = production_tool.run_batch(
                root, adapter_config=cfg, batch_id="batch-resume"
            )
            self.assertEqual(second["state"], "succeeded")
            self.assertEqual(second["skipped"], ["EP001-RESUME-1"])
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-RESUME-1")["state"],
                "succeeded",
            )
            self.assertEqual(
                production_tool.batch_status(root, batch_id="batch-resume")["state"],
                "succeeded",
            )
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root, job_id="EP001-RESUME-1", adapter_config=cfg
                )

    def test_bold_colon_inside_emphasis_fields_never_drops_refs_or_voice(self) -> None:
        # Colon INSIDE emphasis (`- **输入参考图：** REF-...`, `- **参考音频：** REF-...`,
        # `- **生成方式：** ...`, `* *参考:* ...`, `- **_输入参考图：_** ...`) must parse
        # identically to `- **字段**：...` and `- 字段：...`, especially on GROUP-* where
        # `输入参考图` is optional and would otherwise be silently dropped.
        self.assertEqual(
            production_tool._unwrap_field_key_value("**输入参考图", "** REF-1"),
            ("输入参考图", "REF-1"),
        )
        self.assertEqual(
            production_tool._unwrap_field_key_value("**输入参考图**", "**保留值加粗**"),
            ("输入参考图", "**保留值加粗**"),
        )
        self.assertEqual(
            production_tool._unwrap_field_key_value("**_输入参考图", "_** REF-1"),
            ("输入参考图", "REF-1"),
        )
        self.assertEqual(
            production_tool._unwrap_field_key_value("***生成方式", "*** 图生视频"),
            ("生成方式", "图生视频"),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            (root / "输入/voice.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
            video_md = root / "剧集/EP001/视频提示词.md"
            video_md.write_text(
                "# EP001 视频提示词\n\n"
                "## MOTION-EP001-001 · 冒号在加粗内\n"
                "- **分镜：** SHOT-EP001-001\n"
                "- **生成方式：** 图生视频\n"
                "- **输入参考图：** REF-HERO（顺序：1）· 输入/reference.png《女主定妆照》"
                "（用途：起始帧；控制：首帧构图；不得控制：动作）\n"
                "- **参考音频：** REF-VOICE（顺序：1）· 输入/voice.wav《女主音色》"
                "（用途：音色；角色：江晨；控制：音色；不得控制：台词）\n\n"
                "### 可复制提示词\n"
                "> She speaks softly in the rain.\n\n"
                "## GROUP-EP001-01 · 合拍冒号在加粗内\n"
                "- **成员：** MOTION-EP001-001\n"
                "- **输入参考图：** REF-HERO（顺序：1）· 输入/reference.png《女主定妆照》"
                "（用途：主体；控制：外貌；不得控制：动作）\n"
                "* *参考音频:* REF-VOICE（顺序：1）· 输入/voice.wav《女主音色》"
                "（用途：音色；角色：江晨；控制：音色；不得控制：台词）\n\n"
                "### 可复制提示词\n"
                "> Multi-shot group sequence.\n\n"
                "## GROUP-EP001-02 · 合拍待补参考图不得静默放过\n"
                "- **成员：** MOTION-EP001-001\n"
                "- **输入参考图：** 无；待补参考图：等首帧定稿\n\n"
                "### 可复制提示词\n"
                "> Draft group.\n",
                encoding="utf-8",
            )
            for job_id, entry, expected_roles in (
                ("EP001-BOLD-MOTION", "MOTION-EP001-001", ["first_frame", "reference_audio"]),
                ("EP001-BOLD-GROUP", "GROUP-EP001-01", ["reference_image", "reference_audio"]),
            ):
                with self.subTest(entry=entry):
                    job_file = root / f"{job_id}.json"
                    job_file.write_text(
                        json.dumps(
                            {
                                "schema_version": "1.0",
                                "job_id": job_id,
                                "modality": "video",
                                "adapter": "fixture",
                                "source": "剧集/EP001/视频提示词.md",
                                "source_entry": entry,
                                "outputs": [f"剧集/EP001/制作成果/video/{job_id}.mp4"],
                                "parameters": {"prompt_language": "zh-CN"},
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    preview = production_tool.prepare_job(root, job_file)
                    self.assertEqual(
                        [b["role"] for b in preview["reference_bindings"]],
                        expected_roles,
                    )
                    self.assertEqual(
                        [b["path"] for b in preview["reference_bindings"]],
                        ["输入/reference.png", "输入/voice.wav"],
                    )

            pending_group = root / "pending-group.json"
            pending_group.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-BOLD-PENDING",
                        "modality": "video",
                        "adapter": "fixture",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "GROUP-EP001-02",
                        "outputs": ["剧集/EP001/制作成果/video/GROUP-02.mp4"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "pending or unsubmittable"):
                production_tool.prepare_job(root, pending_group)

            img_md = root / "剧集/EP001/图片提示词.md"
            img_md.write_text(
                "# EP001 图片提示词\n\n"
                "## IMG-EP001-01 · 冒号在加粗内\n"
                "- __参考：__ REF-HERO（顺序：1）· 输入/reference.png《女主定妆照》"
                "（用途：外貌；控制：脸型；不得控制：构图）\n\n"
                "### 可复制提示词\n"
                "> Vertical portrait of heroine.\n",
                encoding="utf-8",
            )
            img_job = root / "bold-img.json"
            img_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-BOLD-IMG",
                        "modality": "image",
                        "adapter": "fixture",
                        "source": "剧集/EP001/图片提示词.md",
                        "source_entry": "IMG-EP001-01",
                        "outputs": ["剧集/EP001/制作成果/image/IMG-01.png"],
                        "parameters": {"prompt_language": "zh-CN"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            img_preview = production_tool.prepare_job(root, img_job)
            self.assertEqual(img_preview["references"], ["输入/reference.png"])

    def test_music_source_entry_extracts_prompt_and_isolates_hash_from_video_shots(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            config = self.adapter_config(directory)
            video_md = root / "剧集/EP001/视频提示词.md"
            video_md.write_text(
                "# EP001 视频提示词\n\n"
                "## MOTION-EP001-001 · 开场镜头\n"
                "- 分镜：SHOT-EP001-001\n"
                "- 输入参考图：无（文生视频）\n\n"
                "### 可复制提示词\n"
                "> Original video shot prompt.\n\n"
                "## MUSIC-EP001-01 · 夜雨悬疑主题\n"
                "- 纯音乐：是\n"
                "- 情绪：克制悬疑\n\n"
                "### 可复制提示词\n"
                "> Restrained minimalist piano and low cello pulse, 84 BPM, suspenseful urban night.\n\n"
                "### 备注\n"
                "> 供剪辑铺底。\n",
                encoding="utf-8",
            )
            music_job = root / "music-entry.json"
            music_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-MUSIC-01",
                        "modality": "music",
                        "adapter": "fixture",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "MUSIC-EP001-01",
                        "outputs": ["剧集/EP001/制作成果/music/MUSIC-01.wav"],
                        "parameters": {"is_instrumental": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            preview = self.prepare_and_confirm(root, music_job)
            self.assertEqual(preview["source_entry"], "MUSIC-EP001-01")
            self.assertEqual(
                preview["prompt"],
                "Restrained minimalist piano and low cello pulse, 84 BPM, suspenseful urban night.",
            )
            self.assertEqual(preview["warnings"], [])

            # Editing a video shot in the same 视频提示词.md must NOT invalidate MUSIC-EP001-01!
            video_md.write_text(
                video_md.read_text(encoding="utf-8").replace(
                    "Original video shot prompt.",
                    "Revised video shot prompt with slow dolly.",
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-MUSIC-01")["state"],
                "confirmed",
            )
            ran = production_tool.run_job(
                root, job_id="EP001-MUSIC-01", adapter_config=config
            )
            self.assertEqual(ran["state"], "succeeded")
            self.assertEqual(production_tool.audit_project(root)["status"], "pass")

            # Editing the MUSIC-EP001-01 section itself MUST invalidate confirmation / flag audit.
            video_md.write_text(
                video_md.read_text(encoding="utf-8").replace("84 BPM", "92 BPM"),
                encoding="utf-8",
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-MUSIC-01")["state"],
                "needs_reconfirmation",
            )

            # Standalone music Markdown document with MUSIC-* source_entry also works end-to-end.
            standalone_md = root / "剧集/EP001/配乐提示词.md"
            standalone_md.write_text(
                "# EP001 配乐\n\n"
                "## MUSIC-EP001-THEME · 片尾曲\n\n"
                "### 可复制提示词\n"
                "> Warm acoustic guitar ballad with soft female vocal.\n",
                encoding="utf-8",
            )
            standalone_job = root / "standalone-music.json"
            standalone_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-MUSIC-THEME",
                        "modality": "music",
                        "adapter": "fixture",
                        "source": "剧集/EP001/配乐提示词.md",
                        "source_entry": "MUSIC-EP001-THEME",
                        "outputs": ["剧集/EP001/制作成果/music/THEME.wav"],
                        "parameters": {"is_instrumental": False, "lyrics": "[Verse]\n夜色渐深"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            st_preview = self.prepare_and_confirm(root, standalone_job)
            self.assertEqual(
                st_preview["prompt"],
                "Warm acoustic guitar ballad with soft female vocal.",
            )
            self.assertEqual(
                production_tool.run_job(
                    root, job_id="EP001-MUSIC-THEME", adapter_config=config
                )["state"],
                "succeeded",
            )

            # Backward compatibility: music job on 视频提示词.md WITHOUT source_entry still prepares
            # and emits a soft-gate `music_whole_file_hash` warning.
            legacy_music_job = root / "legacy-music.json"
            legacy_music_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-MUSIC-LEGACY",
                        "modality": "music",
                        "adapter": "fixture",
                        "prompt": "Manual music prompt.",
                        "source": "剧集/EP001/视频提示词.md",
                        "outputs": ["剧集/EP001/制作成果/music/LEGACY.wav"],
                        "parameters": {"is_instrumental": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            legacy_preview = production_tool.prepare_job(root, legacy_music_job)
            self.assertIsNone(legacy_preview["source_entry"])
            self.assertEqual(
                [w["code"] for w in legacy_preview["warnings"]],
                ["music_whole_file_hash"],
            )

            # Wrong entry prefix (`MOTION-*`) or wrong canonical doc (`图片提示词.md`) is rejected.
            bad_prefix_job = root / "bad-music-prefix.json"
            bad_prefix_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-MUSIC-BAD-PREFIX",
                        "modality": "music",
                        "adapter": "fixture",
                        "source": "剧集/EP001/视频提示词.md",
                        "source_entry": "MOTION-EP001-001",
                        "outputs": ["剧集/EP001/制作成果/music/BAD.wav"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "does not match the job modality"):
                production_tool.prepare_job(root, bad_prefix_job)

            (root / "剧集/EP001/图片提示词.md").write_text(
                "## MUSIC-EP001-01\n### 可复制提示词\n> Wrong file.\n",
                encoding="utf-8",
            )
            bad_file_job = root / "bad-music-file.json"
            bad_file_job.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-MUSIC-BAD-FILE",
                        "modality": "music",
                        "adapter": "fixture",
                        "source": "剧集/EP001/图片提示词.md",
                        "source_entry": "MUSIC-EP001-01",
                        "outputs": ["剧集/EP001/制作成果/music/BAD2.wav"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "does not match the job modality"):
                production_tool.prepare_job(root, bad_file_job)

    def test_explicit_adapter_capabilities_and_soft_gate_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            (root / "输入/voice.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
            job_file = root / "custom-audio-job.json"
            job_file.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-CAP-AUDIO",
                        "modality": "video",
                        "adapter": "custom-video",
                        "prompt": "Character speaks under rain.",
                        "reference_bindings": [
                            {
                                "slot_id": "REF-LOOK",
                                "order": 1,
                                "path": "输入/reference.png",
                                "label": "女主定妆照",
                                "role": "identity_and_look",
                                "may_control": ["外貌"],
                                "must_not_control": ["构图"],
                            },
                            {
                                "slot_id": "REF-VOICE",
                                "order": 2,
                                "path": "输入/voice.wav",
                                "label": "女主音色",
                                "role": "reference_audio",
                                "character": "江晨",
                                "may_control": ["音色"],
                                "must_not_control": ["台词"],
                            },
                        ],
                        "outputs": ["剧集/EP001/制作成果/video/CAP-AUDIO.mp4"],
                        "overwrite": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            # Pre-create existing output to verify `overwrite_existing_output` + `missing_prompt_language` soft warnings.
            existing_out = root / "剧集/EP001/制作成果/video/CAP-AUDIO.mp4"
            existing_out.parent.mkdir(parents=True, exist_ok=True)
            existing_out.write_bytes(b"prior-take")
            preview = self.prepare_and_confirm(root, job_file)
            self.assertEqual(
                sorted(w["code"] for w in preview["warnings"]),
                ["missing_prompt_language", "overwrite_existing_output"],
            )

            # 1. Explicit `audio_capable: false` overrides even a script named `provider_adapters.py seedance`.
            builtin_stub = Path(directory) / "provider_adapters.py"
            builtin_stub.write_text(
                "import json, pathlib, sys\n"
                "payload = json.load(sys.stdin)\n"
                "out = pathlib.Path(payload['output_root']) / 'out.mp4'\n"
                "out.write_bytes(b'\\x00\\x00\\x00\\x18ftypisom')\n"
                "json.dump({'outputs': [{'target': payload['outputs'][0], 'source': str(out)}]}, sys.stdout)\n",
                encoding="utf-8",
            )
            disabled_cfg = Path(directory) / "disabled-audio.json"
            disabled_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "custom-video": {
                                "command": [sys.executable, str(builtin_stub), "seedance"],
                                "timeout_seconds": 30,
                                "audio_capable": False,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "reference_audio; nothing was submitted"):
                production_tool.run_job(
                    root, job_id="EP001-CAP-AUDIO", adapter_config=disabled_cfg
                )
            # Confirmation remains valid because rejection happened pre-submission.
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-CAP-AUDIO")["state"],
                "confirmed",
            )

            # 2. Contradictory config (`audio_capable: false` + `reference_audio` in `reference_roles`) fails closed.
            conflict_cfg = Path(directory) / "conflict.json"
            conflict_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "custom-video": {
                                "command": [sys.executable, str(FIXTURE_ADAPTER)],
                                "timeout_seconds": 30,
                                "reference_roles": ["identity_and_look", "reference_audio"],
                                "audio_capable": False,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "conflict"):
                production_tool.run_job(
                    root, job_id="EP001-CAP-AUDIO", adapter_config=conflict_cfg
                )

            # 3. Custom adapter (NOT named provider_adapters.py) with `audio_capable: true` succeeds!
            custom_cfg = Path(directory) / "custom-audio-capable.json"
            custom_cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "custom-video": {
                                "command": [sys.executable, str(FIXTURE_ADAPTER)],
                                "timeout_seconds": 30,
                                "audio_capable": True,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            ran = production_tool.run_job(
                root, job_id="EP001-CAP-AUDIO", adapter_config=custom_cfg
            )
            self.assertEqual(ran["state"], "succeeded")

            # 4. Soft-gate check for unpinned vs version-pinned external package runners.
            self.assertEqual(
                [
                    w["code"]
                    for w in production_tool._adapter_command_warnings(
                        ["uvx", "drama-providers", "seedance"]
                    )
                ],
                ["unpinned_remote_adapter"],
            )
            self.assertEqual(
                production_tool._adapter_command_warnings(
                    ["uvx", "--from", "drama-providers==1.2.3", "drama-providers", "seedance"]
                ),
                [],
            )
            self.assertEqual(
                [
                    w["code"]
                    for w in production_tool._adapter_command_warnings(
                        ["npx", "drama-providers@latest"]
                    )
                ],
                ["unpinned_remote_adapter"],
            )
            self.assertEqual(
                production_tool._adapter_command_warnings(
                    ["npx", "drama-providers@1.2.3"]
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
