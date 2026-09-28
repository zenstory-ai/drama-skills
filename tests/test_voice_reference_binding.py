"""A MOTION binds its speaking character's accepted voice as reference audio."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
EXAMPLE = SUITE / "examples/creator-first/EP001"
FIXTURE_ADAPTER = SUITE / "skills/short-drama-produce/scripts/fixture_adapter.py"


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, SUITE / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_module("voice_checker", "skills/short-drama/scripts/creator_markdown_check.py")
project_tool = load_module("voice_project_tool", "skills/short-drama/scripts/project_tool.py")
production_tool = load_module(
    "voice_production_tool", "skills/short-drama-produce/scripts/production_tool.py"
)
provider_adapters = load_module(
    "voice_provider_adapters", "skills/short-drama-produce/scripts/provider_adapters.py"
)

VOICE_PATH = "输入/声音/江晨音色.wav"
PICTURE_PATH = "输入/参考图/江晨定妆.png"
VOICE_RECORD = (
    f"- 声音参考：{VOICE_PATH}（用途：音色；控制：音色、音区；"
    "不得控制：情绪、录音空间；状态：creator_described）"
)
PICTURE_SLOT = (
    f"REF-JIANGCHEN-LOOK（顺序：1）· {PICTURE_PATH}《江晨定妆照》"
    "（用途：身份；控制：脸型、体态；不得控制：构图、动作）"
)
AUDIO_LINE = (
    f"- 参考音频：REF-VOICE-JIANGCHEN（顺序：1）· {VOICE_PATH}《江晨音色参考》"
    "（用途：音色；角色：江晨；控制：音色、音区；不得控制：台词、语气、情绪）"
)
TEXT_TO_VIDEO = "- 输入参考图：无（创作者已明确选择文生视频）。"
# MOTION-EP001-012 delivers 江晨's 「下周榜首，是我们团。」; 周薄森 is silent in it.
MOTION = "MOTION-EP001-012"
SHOT = "SHOT-EP001-012"


def _edit_section(path: Path, entry: str, old: str, new: str) -> None:
    document = path.read_text(encoding="utf-8")
    match = re.search(rf"^## {entry}\b.*?(?=^## |\Z)", document, re.MULTILINE | re.DOTALL)
    assert match is not None and old in match.group(0), (entry, old)
    section = match.group(0).replace(old, new, 1)
    path.write_text(
        document[: match.start()] + section + document[match.end() :], encoding="utf-8"
    )


def bound_episode(
    root: Path, *, audio_line: str = AUDIO_LINE, voice_path: str = VOICE_PATH
) -> Path:
    """The shipped episode with one picture and 江晨's voice bound on one MOTION."""
    audio_line = audio_line.replace(VOICE_PATH, voice_path)
    episode = root / "剧集/EP001"
    if episode.exists():
        shutil.rmtree(episode)
    shutil.copytree(EXAMPLE, episode)
    for relative, content in ((voice_path, b"RIFF voice"), (PICTURE_PATH, b"picture")):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(content)
    _edit_section(
        episode / "视觉设定.md",
        "人物 · 江晨",
        "- 画面代称：Jiangchen\n",
        f"- 画面代称：Jiangchen\n{VOICE_RECORD.replace(VOICE_PATH, voice_path)}\n",
    )
    _edit_section(episode / "分镜.md", SHOT, TEXT_TO_VIDEO, f"- 输入参考图：{PICTURE_SLOT}")
    video = episode / "视频提示词.md"
    _edit_section(video, MOTION, "- 生成方式：文生视频", "- 生成方式：图生视频")
    _edit_section(video, MOTION, TEXT_TO_VIDEO, f"- 输入参考图：{PICTURE_SLOT}\n{audio_line}")
    return episode


class CheckerTests(unittest.TestCase):
    def test_a_speaking_characters_recorded_voice_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(checker.validate_episode(bound_episode(root), root), [])

    def test_voice_scope_and_unique_record_are_required(self) -> None:
        for scope in ("构图", "台词、语气", "台词、情绪", "语气、情绪"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                episode = bound_episode(root, audio_line=AUDIO_LINE.replace("台词、语气、情绪", scope))
                errors = checker.validate_episode(episode, root)
                self.assertTrue(any("不得控制至少包含" in error for error in errors), errors)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = bound_episode(root)
            visual = episode / "视觉设定.md"
            visual.write_text(visual.read_text(encoding="utf-8").replace(
                VOICE_RECORD, VOICE_RECORD + "\n- 声音参考：输入/声音/另一个.wav"), encoding="utf-8")
            errors = checker.validate_episode(episode, root)
            self.assertTrue(any("声音参考重复" in error for error in errors), errors)

    def test_a_recorded_path_with_a_space_is_still_the_characters_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = bound_episode(root, voice_path="输入/声音/voice sample.wav")
            self.assertEqual(checker.validate_episode(episode, root), [])

    def test_a_voice_binding_that_breaks_the_contract_is_named(self) -> None:
        cases = {
            "character is not a 人物 entry": (
                AUDIO_LINE.replace("角色：江晨", "角色：路人甲"),
                "不是《视觉设定.md》里的人物条目",
            ),
            "character is silent in this shot": (
                AUDIO_LINE.replace("角色：江晨", "角色：周薄森"),
                "没有说出《剧本.md》记在其名下的台词",
            ),
            "file is not in the project": (
                AUDIO_LINE.replace(VOICE_PATH, "输入/声音/不存在.wav"),
                "REF 文件不存在",
            ),
            "purpose is not 音色": (
                AUDIO_LINE.replace("用途：音色", "用途：身份"),
                "参考音频用途只能是音色",
            ),
            "audio numbering continues the pictures": (
                AUDIO_LINE.replace("顺序：1", "顺序：2"),
                "参考音频顺序必须唯一且从 1 连续编号",
            ),
        }
        for name, (line, expected) in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                errors = checker.validate_episode(bound_episode(root, audio_line=line), root)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_dialogue_is_read_the_way_the_screenplay_index_reads_it(self) -> None:
        # 江晨's line as written in 剧本.md, and whether screenplay_index.py
        # would emit it as his dialogue block.
        line = "江晨：下周榜首，是我们团。"
        cases = {
            "wrapped onto a second line": ("江晨：下周榜首，\n是我们团。", True),
            "tagged VO, wrapped": ("[VO] 江晨：下周榜首，\n是我们团。", True),
            "right after a multiline comment": (f"<!-- 备注\n还没定 -->\n{line}", True),
            "inside a comment, between blank lines": (f"<!--\n\n{line}\n\n-->", False),
            "after a comment that never closes": (f"<!-- 备注\n\n{line}", False),
            "missing the separator before a tag": (f"{line}\n[SFX] 茶杯轻响", False),
            "missing the separator before ASCII dialogue": (f"{line}\nNote: 旁注", False),
        }
        for name, (written, speaks) in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                episode = bound_episode(root)
                screenplay = episode / "剧本.md"
                screenplay.write_text(
                    screenplay.read_text(encoding="utf-8").replace(line, written, 1),
                    encoding="utf-8",
                )
                errors = checker.validate_episode(episode, root)
                silent = [e for e in errors if "人物「江晨」在本镜可复制提示词里没有说出" in e]
                self.assertEqual(bool(silent), not speaks, errors)

    def test_a_line_two_people_share_is_attributed_or_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = bound_episode(root)
            screenplay = episode / "剧本.md"
            screenplay.write_text(
                screenplay.read_text(encoding="utf-8").replace(
                    "江晨：下周榜首，是我们团。",
                    "江晨：下周榜首，是我们团。\n\n周薄森：下周榜首，是我们团。",
                    1,
                ),
                encoding="utf-8",
            )
            errors = checker.validate_episode(episode, root)
            self.assertTrue(
                any("也是周薄森的台词" in error for error in errors), errors
            )

            # Naming the speaker in the clause that introduces the quote
            # attributes it: 江晨 speaks, and 周薄森 does not.
            video = episode / "视频提示词.md"
            _edit_section(
                video,
                MOTION,
                "He says in Chinese, steady and forceful,",
                "Jiangchen says in Chinese, steady and forceful,",
            )
            self.assertEqual(checker.validate_episode(episode, root), [])
            _edit_section(video, MOTION, "角色：江晨", "角色：周薄森")
            errors = checker.validate_episode(episode, root)
            self.assertTrue(
                any(
                    "人物「周薄森」在本镜可复制提示词里没有说出" in error
                    for error in errors
                ),
                errors,
            )

    def test_the_binding_must_match_the_characters_recorded_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = bound_episode(root)
            other = "输入/声音/另一条.wav"
            (root / other).write_bytes(b"RIFF other")
            visual = episode / "视觉设定.md"
            visual.write_text(
                visual.read_text(encoding="utf-8").replace(VOICE_PATH, other),
                encoding="utf-8",
            )
            errors = checker.validate_episode(episode, root)
            self.assertTrue(any("登记的声音参考" in error for error in errors), errors)

            visual.write_text(
                visual.read_text(encoding="utf-8").replace(
                    VOICE_RECORD.replace(VOICE_PATH, other) + "\n", ""
                ),
                encoding="utf-8",
            )
            errors = checker.validate_episode(episode, root)
            self.assertTrue(any("没有声音参考行" in error for error in errors), errors)

    def test_audio_in_the_picture_field_points_at_the_audio_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = bound_episode(root, audio_line="- 参考音频：无")
            audio_slot = AUDIO_LINE.removeprefix("- 参考音频：").replace("顺序：1", "顺序：2")
            for name, entry in (("分镜.md", SHOT), ("视频提示词.md", MOTION)):
                _edit_section(episode / name, entry, PICTURE_SLOT, f"{PICTURE_SLOT}；{audio_slot}")
            errors = checker.validate_episode(episode, root)
            self.assertTrue(any("输入参考图只收图片" in error for error in errors), errors)


class ProductionTests(unittest.TestCase):
    def project(self, directory: str, *, audio_line: str = AUDIO_LINE) -> Path:
        root = Path(directory) / "project"
        project_tool.initialize_project(
            root,
            title="音色绑定",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SUITE / "skills/short-drama",
        )
        bound_episode(root, audio_line=audio_line)
        return root

    def job(self, root: Path, *, include_audio: bool = True) -> Path:
        section = re.search(
            rf"^## {MOTION}\b.*?(?=^## |\Z)",
            (root / "剧集/EP001/视频提示词.md").read_text(encoding="utf-8"),
            re.MULTILINE | re.DOTALL,
        )
        assert section is not None
        prompt = "\n".join(
            line[1:].lstrip() for line in section.group(0).splitlines() if line.startswith(">")
        )
        bindings = [
            {
                "slot_id": "REF-JIANGCHEN-LOOK",
                "order": 1,
                "path": PICTURE_PATH,
                "label": "江晨定妆照",
                "role": "reference_image",
                "may_control": ["脸型", "体态"],
                "must_not_control": ["构图", "动作"],
            }
        ]
        if include_audio:
            bindings.append(
                {
                    "slot_id": "REF-VOICE-JIANGCHEN",
                    "order": 2,
                    "path": VOICE_PATH,
                    "label": "江晨音色参考",
                    "role": "reference_audio",
                    "character": "江晨",
                    "may_control": ["音色", "音区"],
                    "must_not_control": ["台词", "语气", "情绪"],
                }
            )
        path = root / "voice-job.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "job_id": "EP001-MOTION012",
                    "modality": "video",
                    "adapter": "studio-video",
                    "prompt": prompt,
                    "source": "剧集/EP001/视频提示词.md",
                    "source_entry": MOTION,
                    "reference_bindings": bindings,
                    "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-012.mp4"],
                    "parameters": {"prompt_language": "zh-CN"},
                    "overwrite": False,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def adapter_config(self, directory: str, roles: list[str] | None) -> Path:
        profile: dict = {"command": [sys.executable, str(FIXTURE_ADAPTER)], "timeout_seconds": 30}
        if roles is not None:
            profile["reference_roles"] = roles
        path = Path(directory) / "adapters.json"
        path.write_text(json.dumps({"adapters": {"studio-video": profile}}), encoding="utf-8")
        return path

    def test_the_voice_compiles_to_reference_audio_after_the_pictures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(directory)
            # The preview is the confirmed job the adapter receives.
            preview = production_tool.prepare_job(root, self.job(root))
            body = provider_adapters.compile_seedance_payload(
                preview,
                model="configured-model",
                reference_urls=["https://example.test/look.png", "https://example.test/voice.wav"],
                reference_roles=[binding["role"] for binding in preview["reference_bindings"]],
            )

            media = body["content"][1:]
            self.assertEqual(
                [(item["type"], item["role"]) for item in media],
                [("image_url", "reference_image"), ("audio_url", "reference_audio")],
            )
            # Audio is numbered on its own: the first voice is @音频1, not @音频2.
            self.assertIn("参考 @音频1（江晨音色参考）", body["content"][0]["text"])
            self.assertIn("参考 @图片1（江晨定妆照）", body["content"][0]["text"])

    def test_character_binding_survives_a_misleading_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(directory, audio_line=AUDIO_LINE.replace("江晨音色参考", "周薄森音色参考"))
            path = self.job(root)
            job = json.loads(path.read_text(encoding="utf-8"))
            job["reference_bindings"][1]["label"] = "周薄森音色参考"
            path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
            preview = production_tool.prepare_job(root, path)
            self.assertEqual(preview["reference_bindings"][1]["character"], "江晨")
            body = provider_adapters.compile_seedance_payload(
                preview, model="configured-model",
                reference_urls=["https://example.test/look.png", "https://example.test/voice.wav"],
                reference_roles=["reference_image", "reference_audio"],
            )
            compiled = body["content"][0]["text"]
            self.assertIn("@音频1（江晨音色参考）", compiled)
            self.assertNotIn("周薄森音色参考", compiled)
            for wrong in (None, "周薄森"):
                with self.subTest(character=wrong):
                    if wrong is None:
                        job["reference_bindings"][1].pop("character", None)
                    else:
                        job["reference_bindings"][1]["character"] = wrong
                    path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "do not match the selected source entry"):
                        production_tool.prepare_job(root, path)

    def test_a_declared_voice_cannot_be_dropped_from_the_job(self) -> None:
        # `- **参考音频**：` is the same field to the checker, so production must
        # read it too, or it would accept the job that drops the voice.
        bold = AUDIO_LINE.replace("- 参考音频：", "- **参考音频**：", 1)
        for name, line in (("plain", AUDIO_LINE), ("bold field name", bold)):
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                root = self.project(directory, audio_line=line)
                self.assertEqual(
                    checker.validate_episode(root / "剧集/EP001", root), []
                )
                with self.assertRaisesRegex(
                    ValueError, "do not match the selected source entry"
                ):
                    production_tool.prepare_job(root, self.job(root, include_audio=False))
                preview = production_tool.prepare_job(root, self.job(root))
                self.assertEqual(
                    [binding["role"] for binding in preview["reference_bindings"]],
                    ["reference_image", "reference_audio"],
                )

    def test_a_model_without_reference_audio_fails_before_submission(self) -> None:
        for roles in (None, ["reference_image"]):
            with self.subTest(roles=roles), tempfile.TemporaryDirectory() as directory:
                root = self.project(directory)
                preview = production_tool.prepare_job(root, self.job(root))
                production_tool.confirm_job(
                    root, job_id=preview["job_id"], confirmation=preview["confirmation"]
                )
                with self.assertRaisesRegex(ValueError, "reference_audio; nothing was submitted"):
                    production_tool.run_job(
                        root,
                        job_id=preview["job_id"],
                        adapter_config=self.adapter_config(directory, roles),
                    )
                # No attempt started and the confirmation is still unspent.
                self.assertEqual(
                    production_tool.job_status(root, job_id=preview["job_id"])["state"],
                    "confirmed",
                )
                result = production_tool.run_job(
                    root,
                    job_id=preview["job_id"],
                    adapter_config=self.adapter_config(
                        directory, ["reference_image", "reference_audio"]
                    ),
                )
                self.assertEqual(result["state"], "succeeded")


if __name__ == "__main__":
    unittest.main()
