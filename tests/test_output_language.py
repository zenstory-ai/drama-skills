import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama/scripts/project_tool.py"
SPEC = importlib.util.spec_from_file_location("short_drama_project_tool", SCRIPT)
assert SPEC and SPEC.loader
project_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_tool)

CORE = SUITE / "skills/short-drama"


class LanguageTagTests(unittest.TestCase):
    def test_well_formed_tags_are_accepted_and_trimmed(self) -> None:
        for value, expected in (
            ("zh-CN", "zh-CN"),
            (" en ", "en"),
            ("ko", "ko"),
            ("zh-Hant-TW", "zh-Hant-TW"),
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    project_tool.normalize_language_tag(value, field="language"),
                    expected,
                )

    def test_malformed_tag_is_refused_at_init_not_at_use(self) -> None:
        # Nothing downstream re-checks this value, so a bad tag would otherwise
        # propagate into every artifact that claims to follow it.
        for value in ("", "   ", "zh_CN", "中文", "e", "en--US"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    project_tool.normalize_language_tag(value, field="language")


class ProjectLanguageTests(unittest.TestCase):
    def initialize(self, **kwargs: str) -> tuple[Path, dict[str, Any]]:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        root = Path(directory) / "project"
        options: dict[str, str] = {
            "title": "测试项目",
            "language": "zh-CN",
            "aspect_ratio": "9:16",
        }
        options.update(kwargs)
        result = project_tool.initialize_project(root, suite_root=CORE, **options)
        return root, result["project"]

    def test_defaults_split_creator_language_from_prompt_language(self) -> None:
        _, project = self.initialize()
        self.assertEqual(project["language"], "zh-CN")
        self.assertEqual(project["format"]["prompt_language"], "en")

    def test_prompt_language_can_follow_the_project_language_on_request(self) -> None:
        _, project = self.initialize(prompt_language="zh-CN")
        self.assertEqual(project["format"]["prompt_language"], "zh-CN")
        self.assertEqual(project["language"], "zh-CN")

    def test_video_prompt_language_follows_the_target_model_profile(self) -> None:
        root, project = self.initialize(prompt_language="en")
        project["creator_authority"]["production_profile"] = {
            "status": "accepted",
            "choices": {"video_prompt_language": "zh-CN"},
        }
        project_tool.atomic_json(root / project_tool.PROJECT_FILE, project)
        status = project_tool.project_status(root)
        self.assertEqual(status["prompt_language"], "en")
        self.assertEqual(status["video_prompt_language"], "zh-CN")

    def test_status_exposes_prompt_facing_video_model_choices(self) -> None:
        root, project = self.initialize(prompt_language="en")
        choices = {
            "target_video_model": "minimax-h3",
            "video_prompt_dialect": "minimax-h3",
            "video_prompt_language": "en",
            "native_duration_seconds": {"min": 4, "max": 15},
            "supported_generation_modes": ["text", "reference"],
            "audio_generation": "same_pass",
        }
        project["creator_authority"]["production_profile"] = {
            "status": "accepted",
            "choices": choices,
        }
        project_tool.atomic_json(root / project_tool.PROJECT_FILE, project)
        self.assertEqual(
            project_tool.project_status(root)["video_model_profile"], choices
        )

        project["creator_authority"]["production_profile"]["status"] = "unset"
        project_tool.atomic_json(root / project_tool.PROJECT_FILE, project)
        self.assertEqual(
            project_tool.project_status(root)["video_model_profile"], {}
        )

    def test_video_prompt_language_falls_back_to_general_prompt_language(self) -> None:
        root, _ = self.initialize(prompt_language="ko")
        self.assertEqual(project_tool.project_status(root)["video_prompt_language"], "ko")

    def test_creator_language_change_does_not_move_prompt_language(self) -> None:
        # The two fields address different audiences. Writing a project in
        # Korean must not silently change what generators are asked to render.
        _, project = self.initialize(language="ko")
        self.assertEqual(project["language"], "ko")
        self.assertEqual(project["format"]["prompt_language"], "en")

    def test_malformed_language_refuses_initialization(self) -> None:
        for kwargs in ({"language": "zh_CN"}, {"prompt_language": ""}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    self.initialize(**kwargs)

    def test_status_reports_both_languages_so_skills_stop_guessing(self) -> None:
        root, _ = self.initialize(language="ja", prompt_language="en")
        status = project_tool.project_status(root)
        self.assertEqual(status["language"], "ja")
        self.assertEqual(status["prompt_language"], "en")

    def test_status_falls_back_for_projects_created_before_the_field(self) -> None:
        root, _ = self.initialize()
        project_path = root / project_tool.PROJECT_FILE
        project = json.loads(project_path.read_text(encoding="utf-8"))
        del project["format"]["prompt_language"]
        project_path.write_text(
            json.dumps(project, ensure_ascii=False), encoding="utf-8"
        )

        status = project_tool.project_status(root)
        self.assertEqual(
            status["prompt_language"], project_tool.DEFAULT_PROMPT_LANGUAGE
        )

class TemplateTests(unittest.TestCase):
    def test_template_ships_the_documented_default(self) -> None:
        template = json.loads(
            (CORE / "assets/project-template/short-drama.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(template["language"], "zh-CN")
        self.assertEqual(template["format"]["prompt_language"], "en")


# The stages that hand a prompt body to a generator. Each must say which of its
# outputs follows which field, because these are exactly the artifacts where the
# creator-facing language and the generator-facing language disagree.
PROMPT_AUTHORING_SKILLS = (
    "short-drama-image-prompts",
    "short-drama-video-prompts",
    "short-drama-storyboard",
)
# A language named as a literal default in skill prose. The contract says the
# project field decides, so a skill that spells one of these out has re-created
# the guess the field exists to remove.
HARDCODED_LANGUAGE_RE = re.compile(
    r"(默认使用创作者的?语言|中文项目使用中文|中文项目的[^\n]{0,40}使用中文)"
)


class SkillWiringTests(unittest.TestCase):
    """The contract is only landed if the stages that render text read it.

    Declaring the fields in the core contract while every prompt-authoring
    stage keeps its own hardcoded default is the failure this guards: the
    default would then apply to nothing, and `status` would report a value no
    one consumes.
    """

    def skill_text(self, skill: str) -> str:
        return (SUITE / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")

    def test_prompt_authoring_skills_bind_prompt_bodies_to_prompt_language(
        self,
    ) -> None:
        for skill in PROMPT_AUTHORING_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn("#/format/prompt_language", self.skill_text(skill))

    def test_no_skill_hardcodes_a_creator_facing_language(self) -> None:
        for path in sorted((SUITE / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                found = HARDCODED_LANGUAGE_RE.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(found, [], f"{path.parent.name} hardcodes a language")


# The copyable prompt body, named as a concrete language. A template is what a
# model actually copies, so a language spelled out here overrides the contract
# no matter what SKILL.md says about `#/format/prompt_language`.
HARDCODED_PROMPT_BODY_RE = re.compile(
    r"(自然中文正文|中文正文|翻译成自然中文|自然中文[，。]|natural Chinese|in Chinese)"
)


class ShippedPromptTemplateTests(unittest.TestCase):
    """The template decides the language, because the template is what gets copied.

    `SkillWiringTests` above reads `SKILL.md` and nothing else. Meanwhile the
    image-prompt template said `<自然中文正文…>` unconditionally, so a project
    declaring `prompt_language: en` produced seven accepted Chinese artifacts and
    every test stayed green -- none of them had opened `assets/`.
    """

    def shipped_markdown(self, skill: str) -> list[Path]:
        root = SUITE / "skills" / skill
        return sorted(
            path
            for directory in ("assets", "references")
            for path in (root / directory).rglob("*.md")
        )

    def test_no_shipped_template_fixes_the_prompt_body_language(self) -> None:
        for skill in PROMPT_AUTHORING_SKILLS:
            for path in self.shipped_markdown(skill):
                with self.subTest(path=str(path.relative_to(SUITE))):
                    found = HARDCODED_PROMPT_BODY_RE.findall(
                        path.read_text(encoding="utf-8")
                    )
                    self.assertEqual(
                        found,
                        [],
                        f"{path.relative_to(SUITE)} fixes the prompt-body language; "
                        "it must defer to #/format/prompt_language",
                    )


CHECKER_SCRIPT = SUITE / "skills/short-drama/scripts/creator_markdown_check.py"
CHECKER_SPEC = importlib.util.spec_from_file_location(
    "short_drama_creator_markdown_check", CHECKER_SCRIPT
)
assert CHECKER_SPEC and CHECKER_SPEC.loader
checker = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(checker)


class CheckerLanguageAndDialogueTests(unittest.TestCase):
    def _write_episode(
        self,
        root: Path,
        *,
        prompt_language: str,
        character_name: str,
        prompt_text: str,
        declare_in_basis: bool = True,
    ) -> Path:
        project_tool.initialize_project(
            root,
            suite_root=CORE,
            title="Language Check",
            language="en",
            prompt_language=prompt_language,
            aspect_ratio="9:16",
        )
        ep = root / "剧集/EP001"
        ep.mkdir(parents=True)
        (ep / "剧本.md").write_text(
            "# EP001 · Night Watch\n\n"
            "## EP001-SC001 外 · Pier · 夜\n\n"
            f"{character_name}： Stay right there.\n",
            encoding="utf-8",
        )
        (ep / "视觉设定.md").write_text(
            "# EP001 视觉设定\n"
            "- 制作形态：真人写实。\n"
            "- 时代背景：当下。\n\n"
            f"## 人物 · {character_name}\n"
            "- 外观特征：dark wool coat, calm gaze。\n\n"
            "## 地点 · Pier\n"
            "- 外观特征：wet wooden pier under fog lamps。\n",
            encoding="utf-8",
        )
        basis = (
            f"《视觉设定.md》·人物「{character_name}」（控制：外貌、服装）；地点「Pier」（控制：空间）"
            if declare_in_basis
            else "《视觉设定.md》·地点「Pier」（控制：空间）"
        )
        (ep / "分镜.md").write_text(
            "# EP001 分镜\n\n"
            "## SHOT-EP001-001 · Stand Still\n"
            "- 来源：EP001-SC001\n"
            "- 时长：3 秒\n"
            "- 目的：立住人物对峙\n"
            "- 景别/机位：近景 · 平视\n"
            "- 运镜：固定\n"
            "- 起点：人物站在码头灯下\n"
            "- 动作：目光锁定前方\n"
            "- 终点：嘴角绷紧\n"
            f"- 声音：{character_name}：「Stay right there.」\n"
            "- 画面文字：无\n"
            f"- 出场设定：{basis}\n"
            "- 图片提示词项：无\n"
            "- 输入参考图：无（纯文生视频）\n\n"
            "### 首帧提示词\n"
            f"> {prompt_text}\n",
            encoding="utf-8",
        )
        return ep

    def test_english_character_heading_passes_without_designator_in_english_prompts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "en_project"
            ep = self._write_episode(
                root,
                prompt_language="en",
                character_name="Elena Vance",
                prompt_text="9:16 vertical still, Elena Vance stands on the wet wooden Pier in a dark wool coat.",
            )
            self.assertEqual(
                checker.validate_episode(ep, root, partial=True), []
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "en_missing_basis"
            ep = self._write_episode(
                root,
                prompt_language="en",
                character_name="Elena Vance",
                prompt_text="9:16 vertical still, Elena Vance stands on the wet wooden Pier in a dark wool coat.",
                declare_in_basis=False,
            )
            errors = checker.validate_episode(ep, root, partial=True)
            self.assertTrue(
                any("Elena Vance" in err and "出场设定" in err for err in errors),
                errors,
            )

    def test_cross_language_character_headings_require_prompt_designator(self) -> None:
        cases = (
            (
                "zh_name_in_en_prompt",
                "en",
                "陈予安",
                "9:16 vertical still, a figure stands on the wet wooden pier.",
            ),
            (
                "en_name_in_zh_prompt",
                "zh-CN",
                "Elena Vance",
                "9:16 竖屏静帧，码头雾灯下穿深色呢大衣的女子驻足凝视。",
            ),
        )
        for label, prompt_lang, name, prompt_text in cases:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory) / label
                    ep = self._write_episode(
                        root,
                        prompt_language=prompt_lang,
                        character_name=name,
                        prompt_text=prompt_text,
                    )
                    errors = checker.validate_episode(ep, root, partial=True)
                    self.assertTrue(
                        any(
                            f"人物「{name}」缺少提示词名称" in err
                            for err in errors
                        ),
                        errors,
                    )

    def test_fullwidth_colon_allows_optional_horizontal_whitespace_in_dialogue(
        self,
    ) -> None:
        screenplay = (
            "# EP001 · Test\n\n"
            "## EP001-SC001 内 · 走廊 · 夜\n\n"
            "Elena Vance： 站在那别动。\n\n"
            "陈予安（压低声音）：\t别回头。\n\n"
            "[VO] Elena Vance (whisper)： 我们来晚了。\n"
        )
        lines = checker._screenplay_dialogue(screenplay)
        self.assertEqual(
            [(item.scene, item.speaker, item.key) for item in lines],
            [
                ("EP001-SC001", "Elena Vance", "站在那别动"),
                ("EP001-SC001", "陈予安", "别回头"),
                ("EP001-SC001", "Elena Vance", "我们来晚了"),
            ],
        )
        english = checker.SCREENPLAY_DIALOGUE_RE.fullmatch(
            "Elena Vance： Stay right there."
        )
        self.assertIsNotNone(english)
        assert english is not None
        self.assertEqual(
            (english.group("speaker"), english.group("text")),
            ("Elena Vance", "Stay right there."),
        )


if __name__ == "__main__":
    unittest.main()
