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
FIXTURE_ADAPTER = SUITE / "skills/short-drama-produce/scripts/fixture_adapter.py"
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
                "- 输入参考图：无（创作者已明确选择文生视频）。\n\n"
                "### 冻结关键帧提示词\n> A hand resting on a glass desktop.\n",
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
                "（用途：身份；控制：脸型、体态；不得控制：构图、动作）"
            )
            for name in ("分镜.md", "视频提示词.md"):
                path = episode / name
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "- 输入参考图：无（创作者已明确选择文生视频）。",
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

            def finish_then_answer(command, timeout, payload, adapter_root):
                history = production_tool._read_run_history(root, "EP001-SHOT001")
                finished = dict(history[-1])
                finished["status"] = "succeeded"
                finished["outputs"] = []
                production_tool._write_run(root, "EP001-SHOT001", finished)
                return original(command, timeout, payload, adapter_root)

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


if __name__ == "__main__":
    unittest.main()
