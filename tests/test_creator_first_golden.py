"""Small regression for the creator-first authoring surface and native example."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "examples/creator-first/EP001"
EXPECTED = {
    "剧本.md",
    "视觉设定.md",
    "分镜.md",
    "图片提示词.md",
    "视频提示词.md",
}
CREATOR_SKILLS = (
    "short-drama",
    "short-drama-write",
    "short-drama-assets",
    "short-drama-image-prompts",
    "short-drama-storyboard",
    "short-drama-video-prompts",
)
ACTIVE_CREATOR_SKILLS = (*CREATOR_SKILLS, "short-drama-review")
CREATOR_DOCUMENTS = ROOT / "skills/short-drama/references/creator-documents.md"
EXPLICIT_TEXT_TO_VIDEO = "无（文生视频）。"
# The shipped example's one continuity lock, and the shots it is scoped to.
LOCK_SCOPE = (
    "（镜头：SHOT-EP001-002、SHOT-EP001-003、SHOT-EP001-007、SHOT-EP001-010、"
    "SHOT-EP001-012、SHOT-EP001-015、SHOT-EP001-017、SHOT-EP001-018、"
    "SHOT-EP001-019、SHOT-EP001-020、SHOT-EP001-021；"
)
LOCK_DECLARATION = (
    "- 连戏锁：LOCK-JIANGCHEN-DRESS《江晨松枝绿常服》"
    + LOCK_SCOPE
    + "图片提示词项：IMG-JIANGCHEN-SHEET）· 锁定词：pine-green lapel service jacket"
)
DURATION_SPEC = importlib.util.spec_from_file_location(
    "creator_first_duration_estimate",
    ROOT / "skills/short-drama-write/scripts/duration_estimate.py",
)
assert DURATION_SPEC and DURATION_SPEC.loader
duration_estimate = importlib.util.module_from_spec(DURATION_SPEC)
DURATION_SPEC.loader.exec_module(duration_estimate)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "creator_markdown_check",
    ROOT / "skills/short-drama/scripts/creator_markdown_check.py",
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
creator_markdown_check = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(creator_markdown_check)


def text(name: str) -> str:
    return (EPISODE / name).read_text(encoding="utf-8")


def heading_ids(document: str, prefix: str) -> list[str]:
    return re.findall(rf"^## ({prefix}[A-Z0-9-]+)\b", document, flags=re.MULTILINE)


def headings(document: str, level: int) -> list[str]:
    marker = "#" * level
    return re.findall(rf"^{marker} (.+)$", document, flags=re.MULTILINE)


def frozen_prompt(document: str, shot_id: str) -> str:
    section = document.split(f"## {shot_id}", 1)[1].split("\n## ", 1)[0]
    return section.split("### 首帧提示词", 1)[1]


def sections(document: str, prefix: str) -> dict[str, str]:
    matches = list(re.finditer(rf"^## ({prefix}[A-Z0-9-]+)\b", document, re.MULTILINE))
    return {
        match.group(1): document[
            match.start() : matches[index + 1].start()
            if index + 1 < len(matches)
            else None
        ]
        for index, match in enumerate(matches)
    }


def bullet_fields(document: str) -> dict[str, str]:
    return dict(re.findall(r"^- ([^：\n]+)：(.+)$", document, re.MULTILINE))


def image_prompt_references(value: str) -> list[tuple[str, str, str]]:
    return re.findall(
        r"\b(IMG-[A-Z0-9-]+)《([^》]+)》（控制：([^）]+)）",
        value,
    )


def input_image_references(value: str) -> list[tuple[str, str, str, str, str, str, str]]:
    return re.findall(
        r"(REF-[A-Z0-9-]+)（顺序：([1-9]\d*)）· "
        r"([^；]+?\.(?:png|jpe?g|webp))《([^》]+)》"
        r"（用途：([^；）]+)；控制：([^；）]+)；不得控制：([^）]+)）",
        value,
        re.IGNORECASE,
    )


def is_portable_project_relative_path(value: str) -> bool:
    if not value or "\\" in value or re.match(r"^[A-Za-z]:", value):
        return False
    components = value.split("/")
    if any(component in {"", ".", ".."} for component in components):
        return False
    return not PurePosixPath(value).is_absolute()


def reachable_markdown(start: Path, root: Path) -> set[Path]:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
    seen: set[Path] = set()
    pending = [start.resolve()]
    root = root.resolve()

    while pending:
        current = pending.pop()
        if current in seen or not current.is_file():
            continue
        seen.add(current)
        for raw_target in link_pattern.findall(current.read_text(encoding="utf-8")):
            target = unquote(raw_target.split("#", 1)[0])
            resolved = (current.parent / target).resolve()
            if resolved == root or root in resolved.parents:
                pending.append(resolved)
    return seen


class CreatorFirstGoldenTests(unittest.TestCase):
    def test_episode_exposes_exactly_five_markdown_documents(self) -> None:
        files = {path.name for path in EPISODE.iterdir() if path.is_file()}
        self.assertEqual(files, EXPECTED)
        self.assertFalse(list(EPISODE.rglob("*.json")))
        self.assertFalse(list(EPISODE.rglob("*.jsonl")))

    def test_documents_follow_the_creator_markdown_contract(self) -> None:
        for name in EXPECTED:
            document = text(name)
            with self.subTest(document=name):
                self.assertEqual(len(headings(document, 1)), 1)
                self.assertGreater(len(headings(document, 2)), 0)

        screenplay = text("剧本.md")
        scene_ids = re.findall(
            r"^## (EP001-SC\d+) (?:内|外|内外) · \S.* · \S.*$",
            screenplay,
            re.MULTILINE,
        )
        self.assertGreaterEqual(len(scene_ids), 2)
        self.assertEqual(len(scene_ids), len(set(scene_ids)))

        visual = text("视觉设定.md")
        visual_entries = [heading.split(" · ", 1) for heading in headings(visual, 2)]
        self.assertTrue(all(len(entry) == 2 and all(entry) for entry in visual_entries))
        self.assertEqual(
            {entry[0] for entry in visual_entries}, {"人物", "地点", "道具"}
        )
        self.assertEqual(
            len(re.findall(r"^- 外观特征：\S.+$", visual, re.MULTILINE)),
            len(visual_entries),
        )

    def test_storyboard_and_motion_cover_the_same_unique_shots(self) -> None:
        storyboard = text("分镜.md")
        video = text("视频提示词.md")
        shot_ids = heading_ids(storyboard, "SHOT-")
        motion_ids = heading_ids(video, "MOTION-")
        motion_shots = re.findall(r"^- 分镜：(SHOT-[A-Z0-9-]+)$", video, re.MULTILINE)

        self.assertGreater(len(shot_ids), 0)
        self.assertEqual(len(shot_ids), len(set(shot_ids)))
        self.assertEqual(len(motion_ids), len(set(motion_ids)))
        self.assertEqual(motion_shots, shot_ids)
        self.assertEqual(headings(storyboard, 3), ["首帧提示词"] * len(shot_ids))
        self.assertEqual(headings(video, 3), ["可复制提示词"] * len(shot_ids))

        storyboard_durations = {
            shot_id: int(re.search(r"^- 时长：(\d+)s$", body, re.MULTILINE).group(1))
            for shot_id, body in sections(storyboard, "SHOT-").items()
        }
        motion_durations = {
            re.search(r"^- 分镜：(SHOT-[A-Z0-9-]+)$", body, re.MULTILINE).group(1): int(
                re.search(r"^- 时长：(\d+)s$", body, re.MULTILINE).group(1)
            )
            for body in sections(video, "MOTION-").values()
        }
        self.assertEqual(motion_durations, storyboard_durations)

        screenplay_scenes = set(heading_ids(text("剧本.md"), "EP001-SC"))
        storyboard_scenes = {
            match.group(1)
            for body in sections(storyboard, "SHOT-").values()
            if (match := re.search(r"^- 来源：(EP001-SC\d+)$", body, re.MULTILINE))
        }
        self.assertEqual(storyboard_scenes, screenplay_scenes)

    def test_each_storyboard_image_prompt_id_has_a_matching_heading(self) -> None:
        image_headings = dict(
            re.findall(
                r"^## (IMG-[A-Z0-9-]+) · (.+)$",
                text("图片提示词.md"),
                re.MULTILINE,
            )
        )
        for shot_id, body in sections(text("分镜.md"), "SHOT-").items():
            with self.subTest(shot=shot_id):
                fields = bullet_fields(body)
                references = image_prompt_references(fields["图片提示词项"])
                referenced = {item[0] for item in references}
                self.assertTrue(referenced)
                self.assertLessEqual(referenced, image_headings.keys())
                for image_id, label, _ in references:
                    self.assertEqual(label, image_headings[image_id])

    def test_storyboard_image_prompt_references_explain_labels_and_scope(self) -> None:
        for shot_id, body in sections(text("分镜.md"), "SHOT-").items():
            with self.subTest(shot=shot_id):
                fields = bullet_fields(body)
                value = fields["图片提示词项"]
                references = image_prompt_references(value)
                self.assertEqual(
                    len(references),
                    len(re.findall(r"\bIMG-[A-Z0-9-]+\b", value)),
                )
                for _, label, scope in references:
                    self.assertRegex(label, r"[\u4e00-\u9fff]")
                    self.assertRegex(scope, r"[\u4e00-\u9fff]")

    def test_storyboard_reference_contract_supports_independent_state_axes(
        self,
    ) -> None:
        contract = CREATOR_DOCUMENTS.read_text(encoding="utf-8")
        markdown_examples = re.findall(r"```markdown\n(.*?)```", contract, re.DOTALL)
        reference_states = [
            fields
            for example in markdown_examples
            if {
                "图片提示词项",
                "输入参考图",
            }.issubset(fields := bullet_fields(example))
        ]

        prompt_without_image = [
            state
            for state in reference_states
            if image_prompt_references(state["图片提示词项"])
            and re.fullmatch(r"无(?:（[^）]+）)?。?", state["输入参考图"])
        ]
        self.assertEqual(len(prompt_without_image), 1)

        fallback_states = [
            state
            for state in reference_states
            if state["图片提示词项"] == "无"
            and re.fullmatch(r"无(?:（[^）]+）)?。?", state["输入参考图"])
            and "出场设定" in state
        ]
        self.assertEqual(len(fallback_states), 1)
        fallback = fallback_states[0]
        self.assertRegex(fallback["输入参考图"], r"^无(?:（[^）]+）)?$")
        self.assertNotRegex(fallback["输入参考图"], r"\bIMG-[A-Z0-9-]+\b")
        self.assertRegex(fallback["出场设定"], r"《视觉设定\.md》")
        self.assertRegex(fallback["出场设定"], r"（控制：[^）]+）")

        image_without_prompt = [
            state
            for state in reference_states
            if state["图片提示词项"] == "无"
            and input_image_references(state["输入参考图"])
        ]
        self.assertEqual(len(image_without_prompt), 1)

        prompt_with_image = [
            state
            for state in reference_states
            if image_prompt_references(state["图片提示词项"])
            and input_image_references(state["输入参考图"])
        ]
        self.assertEqual(len(prompt_with_image), 1)

        for state in (*image_without_prompt, *prompt_with_image):
            input_field = state["输入参考图"]
            self.assertNotRegex(input_field, r"\bIMG-[A-Z0-9-]+\b")
            references = input_image_references(input_field)
            slots = [reference[0] for reference in references]
            orders = [int(reference[1]) for reference in references]
            self.assertEqual(len(slots), len(set(slots)))
            self.assertEqual(len(orders), len(set(orders)))
            for _, _, raw_path, label, purpose, scope, excluded_scope in references:
                self.assertTrue(is_portable_project_relative_path(raw_path))
                self.assertRegex(label, r"[\u4e00-\u9fff]")
                self.assertIn(purpose, creator_markdown_check.REF_PURPOSES)
                self.assertRegex(scope, r"[\u4e00-\u9fff]")
                self.assertRegex(excluded_scope, r"[\u4e00-\u9fff]")

        for unsafe_path in (
            "",
            r"..\secret.jpg",
            r"C:\Users\me\portrait.jpg",
            r"\\server\share\portrait.jpg",
            "../secret.jpg",
            "/absolute/portrait.jpg",
            "input//portrait.jpg",
            "input/./portrait.jpg",
            "input/../portrait.jpg",
        ):
            with self.subTest(unsafe_path=unsafe_path):
                self.assertFalse(is_portable_project_relative_path(unsafe_path))

        for shot_id, body in sections(text("分镜.md"), "SHOT-").items():
            with self.subTest(shot=shot_id):
                fields = bullet_fields(body)
                self.assertEqual(fields["输入参考图"], EXPLICIT_TEXT_TO_VIDEO)

    def test_reference_discovery_contract_prevents_silent_text_fallback(self) -> None:
        for skill_name in ("short-drama-storyboard", "short-drama-video-prompts"):
            skill_md = ROOT / "skills" / skill_name / "SKILL.md"
            raw = skill_md.read_text(encoding="utf-8")
            match = re.match(r"^---\n([\s\S]+?)\n---\n([\s\S]+)$", raw)
            self.assertIsNotNone(match, f"{skill_name}/SKILL.md missing YAML frontmatter")
            assert match is not None
            frontmatter, body = match.groups()
            fields = {
                key.strip(): value.strip()
                for line in frontmatter.splitlines()
                if ":" in line
                for key, value in [line.split(":", 1)]
            }
            self.assertEqual(fields.get("name"), skill_name)
            self.assertTrue(fields.get("description"))
            self.assertGreaterEqual(len(re.findall(r"^##\s+\S+", body, re.MULTILINE)), 2)

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            real_image = project / "剧集/EP001/制作成果/role.png"
            real_image.parent.mkdir(parents=True, exist_ok=True)
            real_image.write_bytes(b"\x89PNG\r\n\x1a\n")

            prose_errors: list[str] = []
            creator_markdown_check._references(
                "暂未指定参考图，先按文字生成", "SHOT-EP001-001", project, prose_errors
            )
            self.assertTrue(prose_errors, "prose fallback in 输入参考图 must be rejected")

            slash_errors: list[str] = []
            creator_markdown_check._references(
                "REF-1（顺序：1）· 剧集/EP001/制作成果/role.png《江晨》"
                "（用途：外貌 / 控制：五官 / 不得控制：构图）",
                "SHOT-EP001-001",
                project,
                slash_errors,
            )
            self.assertTrue(slash_errors, "`/` separator inside REF scope must be rejected")

            missing_file_errors: list[str] = []
            creator_markdown_check._references(
                "REF-1（顺序：1）· 剧集/EP001/制作成果/missing.png《江晨》"
                "（用途：外貌；控制：五官；不得控制：构图）",
                "SHOT-EP001-001",
                project,
                missing_file_errors,
            )
            self.assertTrue(missing_file_errors, "REF naming a missing file must be rejected")

            valid_errors: list[str] = []
            kinds = creator_markdown_check._references(
                "PLAN-1（顺序：1）· IMG-JIANGCHEN-SHEET《江晨角色设定图》"
                "（用途：外貌；控制：五官与发型；不得控制：机位与构图）；待补参考图：江晨角色图。",
                "SHOT-EP001-001",
                project,
                valid_errors,
            )
            self.assertEqual(valid_errors, [])
            self.assertEqual(kinds, frozenset({"PLAN"}))

            t2v_errors: list[str] = []
            t2v_kinds = creator_markdown_check._references(
                EXPLICIT_TEXT_TO_VIDEO, "SHOT-EP001-001", project, t2v_errors
            )
            self.assertEqual(t2v_errors, [])
            self.assertEqual(t2v_kinds, frozenset())

    def test_source_quotes_do_not_force_offscreen_tags(
        self,
    ) -> None:
        """`来源` quotes locate screenplay beats without forcing `；画外：`."""

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project),
                [],
                "现有样例不该报错",
            )

            path = episode / "分镜.md"
            document = path.read_text(encoding="utf-8")
            visual = (episode / "视觉设定.md").read_text(encoding="utf-8")
            people = re.findall(r"^## 人物 · (.+?)\s*$", visual, re.M)
            self.assertTrue(len(people) >= 2, people)

            first = re.search(r"^- 来源：(.+)$", document, re.M)
            self.assertIsNotNone(first)
            basis = re.search(r"^- 出场设定：(.+)$", document, re.M)
            self.assertIsNotNone(basis)
            outsider = next(p for p in people if p not in basis.group(1))
            path.write_text(
                document.replace(
                    first.group(0),
                    f"{first.group(0)}「{outsider}：先把稿子拿过来。」",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

    def test_loop_shot_allows_same_image_for_start_and_end_frames_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            loop_img = project / "输入/参考图/loop.png"
            loop_img.parent.mkdir(parents=True)
            loop_img.write_bytes(b"png")

            loop_ref = (
                "REF-LOOP-START（顺序：1）· 输入/参考图/loop.png《循环锚点首帧》"
                "（用途：起始帧；控制：起始构图、人物外貌；不得控制：中段动作）；"
                "REF-LOOP-END（顺序：2）· 输入/参考图/loop.png《循环锚点尾帧》"
                "（用途：结束帧；控制：收尾构图、人物外貌；不得控制：中段动作）"
            )
            video_path = episode / "视频提示词.md"
            original_video = video_path.read_text(encoding="utf-8")
            m1 = sections(original_video, "MOTION-")["MOTION-EP001-001"]
            patched_m1 = m1.replace(
                "- 生成方式：文生视频\n- 输入参考图：无（文生视频）。",
                f"- 生成方式：图生视频\n- 输入参考图：{loop_ref}",
            )
            video_path.write_text(original_video.replace(m1, patched_m1, 1), encoding="utf-8")
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

            loop_plan = (
                "PLAN-LOOP-START（顺序：1）· SHOT-EP001-001《攥紧的茶杯首帧》"
                "（用途：起始帧；控制：起始构图；不得控制：中段动作）；"
                "PLAN-LOOP-END（顺序：2）· SHOT-EP001-001《攥紧的茶杯尾帧》"
                "（用途：结束帧；控制：收尾构图；不得控制：中段动作）"
            )
            video_path.write_text(
                original_video.replace(
                    m1,
                    m1.replace(
                        "- 生成方式：文生视频\n- 输入参考图：无（文生视频）。",
                        f"- 生成方式：图生视频\n- 输入参考图：{loop_plan}",
                    ),
                    1,
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

            bad_ref = loop_ref.replace("用途：结束帧", "用途：造型状态")
            video_path.write_text(
                original_video.replace(
                    m1,
                    m1.replace(
                        "- 生成方式：文生视频\n- 输入参考图：无（文生视频）。",
                        f"- 生成方式：图生视频\n- 输入参考图：{bad_ref}",
                    ),
                    1,
                ),
                encoding="utf-8",
            )
            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertTrue(
                any("REF 同一张图只能占一个槽位: 输入/参考图/loop.png" in err for err in errors),
                errors,
            )

    def test_a_stray_line_in_a_prompt_block_is_named_rather_than_hinted_at(self) -> None:
        """One non-`>` line voids the whole block, and the block still looks right.

        A separator, an HTML comment or a note between the heading and the
        quote is invisible as a defect: the prompt is sitting there in full, so
        "缺少唯一且非空的可复制提示词" reads as the checker being wrong and the
        author goes looking anywhere but at that line. Three separate runs lost
        time to exactly this, so the error has to quote the line.
        """

        for intruder in ("---", "<!-- 待确认 -->"):
            with self.subTest(intruder=intruder), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                episode = project / "剧集/EP001"
                shutil.copytree(EPISODE, episode)
                path = episode / "图片提示词.md"
                document = path.read_text(encoding="utf-8")
                marker = "### 可复制提示词\n"
                self.assertIn(marker, document)
                path.write_text(
                    document.replace(marker, f"### 可复制提示词\n\n{intruder}\n", 1),
                    encoding="utf-8",
                )
                errors = creator_markdown_check.validate_episode(episode, project)
                reported = [
                    error
                    for error in errors
                    if "缺少唯一且非空的可复制提示词" in error
                ]
                self.assertEqual(len(reported), 1, errors)
                self.assertIn(intruder, reported[0])
                self.assertIn("不以 `>` 开头", reported[0])

    def test_a_bold_field_name_is_the_same_field(self) -> None:
        """`- **参考**：…` is ordinary Markdown, not a different field.

        Reading the emphasis as part of the key produced 缺少参考字段 while the
        author was looking straight at a 参考 line, which is the least
        actionable form the message could take.
        """

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            path = episode / "图片提示词.md"
            document = path.read_text(encoding="utf-8")
            self.assertIn("\n- 参考：", document)
            path.write_text(
                document.replace("\n- 参考：", "\n- **参考**："), encoding="utf-8"
            )
            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertEqual(
                [error for error in errors if "缺少参考字段" in error], [], errors
            )

    def test_a_bare_category_heading_groups_entries_instead_of_failing(self) -> None:
        """`## 人物` is a section divider, not an entry someone wrote wrong.

        A malformed entry always tries to name something. Rejecting the bare
        category word left 视觉设定.md with no way to group its entries at all.
        """

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            path = episode / "视觉设定.md"
            document = path.read_text(encoding="utf-8")
            first = document.index("\n## 人物 · ")
            path.write_text(
                document[:first] + "\n## 人物\n" + document[first:], encoding="utf-8"
            )
            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertEqual(
                [error for error in errors if "条目标题必须写成" in error], [], errors
            )
            # A heading that does try to name something is still rejected.
            path.write_text(
                document[:first] + "\n## 人物·江晨\n" + document[first:],
                encoding="utf-8",
            )
            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertTrue(
                [error for error in errors if "条目标题必须写成" in error], errors
            )

    def test_validator_catches_a_motion_duration_that_drifts_from_its_shot(self) -> None:
        """时长 is what reaches the generator; a stale copy must not pass silently.

        Every other cross-document check compares text. Duration is a number the
        execution end acts on and VID-04/VID-13 arithmetic is built from, so a
        视频提示词 that still carries a superseded shot length is a real defect
        even though the document parses and every string still matches.
        """
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project),
                [],
                "fixture must start clean",
            )
            video = episode / "视频提示词.md"
            document = video.read_text(encoding="utf-8")
            original = re.search(r"- 时长：(\S+)", document)
            self.assertIsNotNone(original, "视频提示词 must declare a duration")
            video.write_text(
                document.replace(original.group(0), "- 时长：99 秒", 1),
                encoding="utf-8",
            )

            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertTrue(
                any("与视频提示词" in error and "不一致" in error for error in errors),
                errors,
            )

    def test_validator_blocks_pending_or_implicit_text_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            for name in ("分镜.md", "视频提示词.md"):
                path = episode / name
                document = path.read_text(encoding="utf-8")
                path.write_text(
                    document.replace(
                        f"- 输入参考图：{EXPLICIT_TEXT_TO_VIDEO}",
                        "- 输入参考图：无。",
                        1,
                    ),
                    encoding="utf-8",
                )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

        for label, (replacement, expected) in {
            "pending references": (
                "无（待补参考图：江晨身份、办公室地理）。",
                "仍有待补参考图",
            ),
            "implicit fallback": (
                "无（暂时不挂图）。",
                "不能擅自改成文生视频",
            ),
        }.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                episode = project / "剧集/EP001"
                shutil.copytree(EPISODE, episode)
                for name in ("分镜.md", "视频提示词.md"):
                    path = episode / name
                    document = path.read_text(encoding="utf-8")
                    self.assertIn(f"- 输入参考图：{EXPLICIT_TEXT_TO_VIDEO}", document)
                    path.write_text(
                        document.replace(
                            f"- 输入参考图：{EXPLICIT_TEXT_TO_VIDEO}",
                            f"- 输入参考图：{replacement}",
                            1,
                        ),
                        encoding="utf-8",
                    )

                errors = creator_markdown_check.validate_episode(episode, project)
                self.assertTrue(
                    any(expected in error for error in errors),
                    errors,
                )

    def test_validator_blocks_partially_ready_references_before_final_prompt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            reference = project / "输入/参考图/江晨定妆.png"
            reference.parent.mkdir(parents=True)
            reference.write_bytes(b"structural fixture")
            declaration = (
                "REF-JIANGCHEN-LOOK（顺序：1）· 输入/参考图/江晨定妆.png"
                "《江晨定妆照》（用途：外貌；控制：脸型、体态；不得控制：场景地理、构图、动作）"
                "；待补参考图：办公室地理、本镜起始构图。"
            )
            for name in ("分镜.md", "视频提示词.md"):
                path = episode / name
                document = path.read_text(encoding="utf-8")
                path.write_text(
                    document.replace(
                        f"- 输入参考图：{EXPLICIT_TEXT_TO_VIDEO}",
                        f"- 输入参考图：{declaration}",
                        1,
                    ),
                    encoding="utf-8",
                )
            video = episode / "视频提示词.md"
            video.write_text(
                video.read_text(encoding="utf-8").replace(
                    "- 生成方式：文生视频", "- 生成方式：图生视频", 1
                ),
                encoding="utf-8",
            )

            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertTrue(
                any("仍有待补参考图，不能生成最终视频提示词" in error for error in errors),
                errors,
            )
            self.assertFalse(
                any("输入参考图必须使用完整 REF 语法" in error for error in errors),
                errors,
            )

    def test_visual_basis_resolves_against_the_visual_setting_document(self) -> None:
        entry = "人物「江晨」（控制：外貌、手部无针孔无淤青）"
        for label, original, replacement, expected in (
            (
                "unknown entry",
                entry,
                "人物「不存在的人」（控制：身份）",
                "出场设定指向不存在的《视觉设定.md》条目: 人物「不存在的人」",
            ),
            (
                "wrong category",
                entry,
                "道具「江晨」（控制：身份）",
                "出场设定指向不存在的《视觉设定.md》条目: 道具「江晨」",
            ),
            (
                "free prose",
                f"《视觉设定.md》·{entry}",
                "江晨",
                "出场设定必须使用完整语法",
            ),
        ):
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                episode = project / "剧集/EP001"
                shutil.copytree(EPISODE, episode)
                storyboard = episode / "分镜.md"
                document = storyboard.read_text(encoding="utf-8")
                self.assertIn(original, document)
                storyboard.write_text(
                    document.replace(original, replacement, 1), encoding="utf-8"
                )

                errors = creator_markdown_check.validate_episode(episode, project)
                self.assertTrue(
                    any(expected in error for error in errors), errors
                )

    def test_every_shot_declares_a_visual_basis_and_a_frozen_keyframe(self) -> None:
        storyboard = text("分镜.md")
        shots = sections(storyboard, "SHOT-")
        self.assertTrue(shots)
        for shot_id, body in shots.items():
            with self.subTest(shot=shot_id):
                basis = bullet_fields(body)["出场设定"]
                self.assertRegex(basis, r"^《视觉设定\.md》·")
                self.assertRegex(
                    basis, r"(?:人物|造型|地点|道具)「[^」]+」（控制：[^）]+）"
                )
                self.assertIn("### 首帧提示词", body)

        # Deleting the keyframe must not become the cheap way to satisfy the
        # coverage check.
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            path = episode / "分镜.md"
            document = path.read_text(encoding="utf-8")
            marker = "### 首帧提示词\n> 9:16 vertical extreme close-up of a heavy"
            self.assertIn(marker, document)
            path.write_text(
                document.replace(
                    marker, "### 首帧提示词\n\n### 备注\n> 9:16 vertical extreme close-up of a heavy", 1
                ),
                encoding="utf-8",
            )
            errors = creator_markdown_check.validate_episode(episode, project)
            # The message now carries why, so match the claim and read the cause.
            reported = [
                error
                for error in errors
                if error.startswith(
                    "SHOT-EP001-001: 缺少唯一且非空的首帧提示词"
                )
            ]
            self.assertEqual(len(reported), 1, errors)
            self.assertIn("首帧提示词", reported[0])

    def test_a_closing_keyframe_is_optional_but_never_half_written(self) -> None:
        """Most shots end where they began, so absence is not a defect.

        A heading that is present and malformed is, though: it reads as a shot
        that has a closing anchor while nothing downstream can bind one.
        """

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            path = episode / "分镜.md"
            baseline = path.read_text(encoding="utf-8")

            # Absence is silent.
            self.assertNotIn("### 尾帧提示词", baseline)
            self.assertFalse(
                [
                    error
                    for error in creator_markdown_check.validate_episode(episode, project)
                    if "尾帧提示词" in error
                ]
            )

            # An empty one is not.
            marker = "### 首帧提示词"
            self.assertIn(marker, baseline)
            path.write_text(
                baseline.replace(
                    marker, "### 尾帧提示词\n\n" + marker, 1
                ),
                encoding="utf-8",
            )
            reported = [
                error
                for error in creator_markdown_check.validate_episode(episode, project)
                if "尾帧提示词不是唯一且非空" in error
            ]
            self.assertEqual(len(reported), 1, reported)

    def test_screen_name_makes_a_foreign_language_keyframe_checkable(self) -> None:
        """The prompt body is English while 视觉设定.md is Chinese.

        `画面代称` is the only declared bridge between them, so an English-prompt
        project must reach a stated conclusion for every character rather than
        letting an omission quietly switch the coverage check off.
        """
        visual = text("视觉设定.md")
        self.assertIn("- 提示词名称：Jiangchen", visual)
        self.assertIn("- 提示词名称：Zhoubosen", visual)

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            document = episode / "视觉设定.md"
            document.write_text(
                document.read_text(encoding="utf-8").replace(
                    "- 提示词名称：Zhoubosen\n", "", 1
                ),
                encoding="utf-8",
            )
            # Omitting it is a soft warning (AST-13 reviewed_invariant), not a
            # hard script error, reported alongside any structural pass.
            result = creator_markdown_check.validate_episode_with_warnings(
                episode, project
            )
            self.assertEqual(result.errors, [])
            self.assertIn(
                "视觉设定.md: 人物「周薄森」缺少提示词名称；"
                "提示词正文不是中文时，写「提示词名称：<正文里的拼写>」，"
                "正文从不点名时写「提示词名称：无」",
                result.warnings,
            )

            # Declaring 无 is the honest opt-out for a body that never names the
            # entry, and it silences name matching for that entry only.
            document.write_text(
                document.read_text(encoding="utf-8").replace(
                    "- 外观特征：方脸、重下颌、灰白板寸、三道额纹、宽肩厚腰；说话和气，压力只从皱眉、停顿和端冷茶显出来。",
                    "- 外观特征：方脸、重下颌、灰白板寸、三道额纹、宽肩厚腰；说话和气，压力只从皱眉、停顿和端冷茶显出来。\n- 提示词名称：无",
                    1,
                ),
                encoding="utf-8",
            )
            storyboard = episode / "分镜.md"
            storyboard.write_text(
                storyboard.read_text(encoding="utf-8").replace(
                    "；人物「周薄森」（控制：外貌、体态、本集造型）", "", 1
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

    def test_reference_slots_declare_one_purpose_from_the_closed_set(self) -> None:
        cases = {
            "missing purpose": (
                "REF-A（顺序：1）· 输入/a.png《人物参考》（控制：脸型；不得控制：动作）",
                "REF 缺少用途: REF-A",
            ),
            "unknown purpose": (
                "REF-A（顺序：1）· 输入/a.png《人物参考》"
                "（用途：全参考；控制：脸型；不得控制：动作）",
                "REF 用途不在允许集合内: REF-A（全参考）",
            ),
            "two start frames": (
                "REF-A（顺序：1）· 输入/a.png《起始帧》"
                "（用途：起始帧；控制：起始构图；不得控制：动作）；"
                "REF-B（顺序：2）· 输入/b.png《另一张起始帧》"
                "（用途：起始帧；控制：姿态；不得控制：动作）",
                "同一条目只能有一张起始帧参考图",
            ),
            "end frame without a start frame": (
                "REF-A（顺序：1）· 输入/a.png《结束帧》"
                "（用途：结束帧；控制：终点构图；不得控制：新结果）",
                "绑定结束帧参考图时必须同时绑定起始帧",
            ),
        }
        for label, (declaration, expected) in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                episode = project / "剧集/EP001"
                shutil.copytree(EPISODE, episode)
                for name in ("a.png", "b.png"):
                    reference = project / "输入" / name
                    reference.parent.mkdir(parents=True, exist_ok=True)
                    reference.write_bytes(b"structural fixture")
                for name in ("分镜.md", "视频提示词.md"):
                    path = episode / name
                    document = path.read_text(encoding="utf-8")
                    path.write_text(
                        document.replace(
                            f"- 输入参考图：{EXPLICIT_TEXT_TO_VIDEO}",
                            f"- 输入参考图：{declaration}",
                            1,
                        ),
                        encoding="utf-8",
                    )
                video = episode / "视频提示词.md"
                video.write_text(
                    video.read_text(encoding="utf-8").replace(
                        "- 生成方式：文生视频", "- 生成方式：图生视频", 1
                    ),
                    encoding="utf-8",
                )

                errors = creator_markdown_check.validate_episode(episode, project)
                self.assertTrue(
                    any(expected in error for error in errors), errors
                )

    def test_pending_gap_list_reports_its_own_separator(self) -> None:
        """A ；-joined gap list used to be reported as broken REF syntax.

        The obvious repair for that diagnostic is deleting the gap clause, which
        reinstates exactly the silent text-to-video downgrade #92 reported.
        """
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            reference = project / "输入/参考图/江晨定妆.png"
            reference.parent.mkdir(parents=True)
            reference.write_bytes(b"structural fixture")
            declaration = (
                "REF-JIANGCHEN-LOOK（顺序：1）· 输入/参考图/江晨定妆.png"
                "《江晨定妆照》（用途：外貌；控制：脸型、体态；不得控制：构图、动作）"
                "；待补参考图：办公室地理；本镜起始帧"
            )
            path = episode / "分镜.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    f"- 输入参考图：{EXPLICIT_TEXT_TO_VIDEO}",
                    f"- 输入参考图：{declaration}",
                    1,
                ),
                encoding="utf-8",
            )

            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertTrue(
                any("缺口之间只用、分隔" in error for error in errors), errors
            )

    def test_repeating_the_document_name_before_each_entry_is_accepted(self) -> None:
        """A real skill run wrote it this way; it says the same thing.

        Rejecting a readable, unambiguous variant costs the creator a round trip
        and teaches nothing.
        """
        entries = [
            creator_markdown_check.VisualEntry(category, name, [name])
            for category, name in (("人物", "小宇"), ("地点", "家庭书房"), ("人物", "妈妈"))
        ]
        prefix = creator_markdown_check.VISUAL_BASIS_PREFIX
        for label, value in {
            "prefix once": f"{prefix}人物「小宇」（控制：外貌）；地点「家庭书房」（控制：灯位）。",
            "prefix repeated": (
                f"{prefix}人物「小宇」（控制：外貌）；{prefix}地点「家庭书房」（控制：灯位）。"
            ),
            "repeated plus offscreen": (
                f"{prefix}人物「小宇」（控制：外貌）；{prefix}地点「家庭书房」（控制：灯位）"
                f"；画外：{prefix}人物「妈妈」。"
            ),
        }.items():
            with self.subTest(case=label):
                errors: list[str] = []
                creator_markdown_check._visual_basis(
                    value, "SHOT-EP001-001", entries, {}, errors
                )
                self.assertEqual(errors, [])

    def test_a_named_subject_that_is_not_in_frame_is_recorded_rather_than_claimed(
        self,
    ) -> None:
        """SHT-22 excludes offscreen subjects, so the field needs a way to say so.

        Without it the only way to silence a name the frame mentions but does not
        show is to declare an absent subject as present — the opposite of the rule.
        """
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            storyboard = episode / "分镜.md"
            document = storyboard.read_text(encoding="utf-8")
            document = document.replace(
                "；人物「周薄森」（控制：外貌、体态、本集造型）", "", 1
            )
            self.assertIn(
                "；道具「玻璃泡茶杯」（控制：双层玻璃杯身、沉底茶叶）。", document
            )
            storyboard.write_text(
                document.replace(
                    "；道具「玻璃泡茶杯」（控制：双层玻璃杯身、沉底茶叶）。",
                    "；道具「玻璃泡茶杯」（控制：双层玻璃杯身、沉底茶叶）"
                    "；画外：人物「周薄森」。",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

    def test_a_character_used_by_a_shot_is_nameable_in_the_prompt_language(
        self,
    ) -> None:
        """Omitting 画面代称 must not be a silent opt-out of the coverage check.

        The keyframe body defaults to `en` while `视觉设定.md` is Chinese, which is
        exactly the shape issue #94 reported.
        """
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            visual = episode / "视觉设定.md"
            visual.write_text(
                visual.read_text(encoding="utf-8").replace(
                    "- 提示词名称：Zhoubosen\n", "", 1
                ),
                encoding="utf-8",
            )
            result = creator_markdown_check.validate_episode_with_warnings(
                episode, project
            )
            self.assertEqual(result.errors, [])
            self.assertIn(
                "视觉设定.md: 人物「周薄森」缺少提示词名称；"
                "提示词正文不是中文时，写「提示词名称：<正文里的拼写>」，"
                "正文从不点名时写「提示词名称：无」",
                result.warnings,
            )

            (project / "short-drama.json").write_text(
                '{"format": {"prompt_language": "zh-CN"}}', encoding="utf-8"
            )
            zh_result = creator_markdown_check.validate_episode_with_warnings(
                episode, project
            )
            self.assertEqual(
                [
                    item
                    for item in (*zh_result.errors, *zh_result.warnings)
                    if "提示词名称" in item
                ],
                [],
            )

    def test_a_broken_visual_basis_reports_only_its_own_syntax(self) -> None:
        """A parse failure must not also report every entry as uncovered."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            storyboard = episode / "分镜.md"
            document = storyboard.read_text(encoding="utf-8")
            original = (
                "《视觉设定.md》·人物「江晨」（控制：外貌、体态、本集造型）"
                "；人物「周薄森」（控制：外貌、体态、本集造型）"
            )
            self.assertIn(original, document)
            storyboard.write_text(
                document.replace(original, f"{original}；", 1), encoding="utf-8"
            )
            errors = creator_markdown_check.validate_episode(episode, project)
            self.assertEqual(
                [error for error in errors if "SHOT-EP001-002" in error],
                ["SHOT-EP001-002: 出场设定必须使用完整语法："
                 "《视觉设定.md》·<人物|造型|地点|道具>「<名称>」（控制：<范围>），多项用；连接"],
            )

    def test_prose_mentioning_the_field_is_not_a_malformed_declaration(self) -> None:
        errors: list[str] = []
        creator_markdown_check._visual_entries(
            "## 人物 · 甲\n\n- 外观特征：长脸。\n\n本集条目的提示词名称都按英文正文填写。\n",
            errors,
        )
        self.assertEqual(errors, [])

    def test_a_misspelled_screen_name_line_is_not_silently_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            visual = episode / "视觉设定.md"
            visual.write_text(
                visual.read_text(encoding="utf-8").replace(
                    "- 提示词名称：Zhoubosen", "  提示词名称：Zhoubosen", 1
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                any(
                    "提示词名称必须写成" in error
                    for error in creator_markdown_check.validate_episode(
                        episode, project
                    )
                )
            )

    def test_every_shipped_ref_slot_grammar_declares_a_purpose(self) -> None:
        """No shipped document may teach a REF slot the validator will reject.

        `用途` was added to the grammar in one file and mandated "逐字" in
        another; a string-containment test on the file that was updated proves
        nothing about the file that was not.
        """
        slot = re.compile(
            r"REF-[^（\n]{1,80}（顺序：[^）\n]{1,24}）· [^\n]{1,240}?"
            r"（(?P<scope>[^）\n]{1,240})）"
        )
        offenders = []
        for path in sorted(ROOT.rglob("*.md")):
            if ".git" in path.parts or "excerpt-chain" in path.parts:
                continue
            for match in slot.finditer(path.read_text(encoding="utf-8")):
                scope = match.group("scope")
                if "控制：" in scope and not scope.startswith("用途："):
                    offenders.append(
                        f"{path.relative_to(ROOT)}: {match.group(0)[:90]}"
                    )
        self.assertEqual(offenders, [])

    def test_visual_basis_grammar_in_the_spec_is_what_the_validator_accepts(
        self,
    ) -> None:
        """Every 视觉依据 line the spec shows must validate as written."""
        entries = [
            creator_markdown_check.VisualEntry(category, name, [name])
            for category, name in (
                ("人物", "许棠"),
                ("造型", "许棠—深灰旧西装"),
                ("地点", "旧走廊"),
                ("地点", "教室"),
                ("道具", "旧书包"),
                ("人物", "小明"),
            )
        ]
        shown = re.findall(
            r"^- 出场设定：(.+)$",
            CREATOR_DOCUMENTS.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        self.assertTrue(shown)
        for value in shown:
            with self.subTest(value=value):
                errors: list[str] = []
                creator_markdown_check._visual_basis(
                    value, "SPEC", entries, {}, errors
                )
                self.assertEqual(errors, [])

    def test_documented_shot_and_motion_pair_satisfies_the_pairing_rules(self) -> None:
        # A creator copies this pair as the starting shape; if the checker
        # rejects it, the contract contradicts its own validator.
        contract = CREATOR_DOCUMENTS.read_text(encoding="utf-8")
        examples = re.findall(r"```markdown\n(.*?)```", contract, re.DOTALL)
        shot = next(e for e in examples if e.startswith("## SHOT-EP001-001"))
        motion = next(e for e in examples if e.startswith("## MOTION-EP001-001"))
        shot_input = bullet_fields(shot)["输入参考图"]
        motion_fields = bullet_fields(motion)
        self.assertEqual(
            creator_markdown_check._plain(shot_input),
            creator_markdown_check._plain(motion_fields["输入参考图"]),
        )
        self.assertFalse(creator_markdown_check._has_pending_references(shot_input))
        if creator_markdown_check._is_explicit_text_to_video(shot_input):
            self.assertEqual(motion_fields["生成方式"], "文生视频")
            self.assertNotIn("SHOT-", motion_fields["起始帧"])

    def test_creator_markdown_validator_accepts_the_golden_episode(self) -> None:
        self.assertEqual(creator_markdown_check.validate_episode(EPISODE, ROOT), [])

    def test_validator_cli_survives_a_non_utf8_stdout_encoding(self) -> None:
        """回归：CLI 用 print(f"...") 直接写 stdout，而诊断与剧集路径都是中文。

        stdout 重定向到文件或管道时 Windows 用 ANSI 代码页，默认的 strict 处理器
        在打印那一步抛 UnicodeEncodeError：一份完全合格的剧集退出码从 0 变成 1，
        不合格的剧集则只剩一段 traceback，创作者看不到到底哪里不对。stderr 早已
        是 backslashreplace，所以只有 stdout 会这样。POSIX 上用 PYTHONIOENCODING
        能走到同一个 TextIOWrapper，这条在开发机上就会红。
        """

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            episode.parent.mkdir(parents=True)
            shutil.copytree(EPISODE, episode)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "skills/short-drama/scripts/creator_markdown_check.py"),
                    str(episode),
                    "--project-root",
                    str(project),
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "ascii"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("OK: "), result.stdout)

    def test_creator_markdown_validator_accepts_a_real_ref_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            reference = project / "输入/参考图/江晨定妆.png"
            reference.parent.mkdir(parents=True)
            reference.write_bytes(b"not decoded by the structural validator")
            scene_reference = project / "剧集/EP001/制作成果/images/办公室.png"
            scene_reference.parent.mkdir(parents=True)
            scene_reference.write_bytes(b"not decoded by the structural validator")
            unrelated_reference = project / "剧集/EP001/制作成果/images/海边.png"
            unrelated_reference.parent.mkdir(parents=True, exist_ok=True)
            unrelated_reference.write_bytes(b"must not be bound merely because it exists")
            declaration = (
                "REF-JIANGCHEN-LOOK（顺序：1）· 输入/参考图/江晨定妆.png"
                "《江晨定妆照》（用途：外貌；控制：脸型、体态；不得控制：构图、动作、表情）"
                "；REF-OFFICE-GEOGRAPHY（顺序：2）· 剧集/EP001/制作成果/images/办公室.png"
                "《办公室场景图》（用途：空间布局；控制：空间地理、光向；不得控制：人物身份、动作、表情）"
            )
            self.assertNotIn("海边.png", declaration)
            for name in ("分镜.md", "视频提示词.md"):
                path = episode / name
                document = path.read_text(encoding="utf-8")
                path.write_text(
                    document.replace(
                        "- 输入参考图：无（文生视频）。", f"- 输入参考图：{declaration}", 1
                    ),
                    encoding="utf-8",
                )
            video = episode / "视频提示词.md"
            video.write_text(
                video.read_text(encoding="utf-8").replace(
                    "- 生成方式：文生视频", "- 生成方式：图生视频", 1
                ),
                encoding="utf-8",
            )
            image_prompts = episode / "图片提示词.md"
            image_prompts.write_text(
                image_prompts.read_text(encoding="utf-8").replace(
                    "- 参考：无外部参考；三视图必须保持同一脸型、身高比例和服装细节。",
                    f"- 参考：{declaration}",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

    def test_creator_markdown_validator_rejects_cross_document_contract_breaks(
        self,
    ) -> None:
        mutations = {
            "missing IMG": (
                "分镜.md",
                "IMG-JIANGCHEN-SHEET《江晨角色板》",
                "IMG-NOT-DEFINED《江晨角色板》",
                "IMG 标题不存在",
            ),
            "missing motion": (
                "视频提示词.md",
                "- 分镜：SHOT-EP001-001",
                "- 分镜：SHOT-EP001-999",
                "SHOT 与 MOTION 未一一对应",
            ),
            "reference mode mismatch": (
                "视频提示词.md",
                "- 输入参考图：无（文生视频）。",
                "- 输入参考图：REF-X（顺序：1）· 输入/x.png《参考图》（用途：外貌；控制：脸型；不得控制：动作）",
                "生成方式应为图生视频",
            ),
            "missing static anchor": (
                "视频提示词.md",
                "- 开场画面：A clean young East Asian man's right hand rests palm-down",
                "- 开场画面：无\n- 删除字段：A clean young East Asian man's right hand rests palm-down",
                "文生视频缺少开场画面",
            ),
            "duplicate reference field": (
                "视频提示词.md",
                "- 输入参考图：无（文生视频）。",
                "- 输入参考图：无（文生视频）。\n- 输入参考图：无（文生视频）。",
                "字段重复: 输入参考图",
            ),
            "hidden REF in no-input marker": (
                "视频提示词.md",
                "- 输入参考图：无（文生视频）。",
                "- 输入参考图：无（ref-HERO）",
                "完整 REF 语法",
            ),
            "malformed image prompt item": (
                "分镜.md",
                "IMG-JIANGCHEN-SHEET《江晨角色板》（控制：外貌、体态、本集常服）",
                "IMG-JIANGCHEN-SHEET",
                "图片提示词项语法不完整",
            ),
            "missing IMG copyable prompt": (
                "图片提示词.md",
                "### 可复制提示词",
                "### 普通说明",
                "缺少唯一且非空的可复制提示词",
            ),
            "unquoted IMG prompt content": (
                "图片提示词.md",
                "### 可复制提示词",
                "### 可复制提示词\nTHIS CRITICAL LINE IS NOT QUOTED",
                "缺少唯一且非空的可复制提示词",
            ),
            "invalid image reference declaration": (
                "图片提示词.md",
                "- 参考：无外部参考；三视图必须保持同一脸型、身高比例和服装细节。",
                "- 参考：随便写，不是无，也不是完整 REF",
                "参考必须声明无外部参考或使用完整 REF 语法",
            ),
            "hidden REF after no-reference prefix": (
                "图片提示词.md",
                "- 参考：无外部参考；三视图必须保持同一脸型、身高比例和服装细节。",
                "- 参考：无外部参考；REF-X（顺序：1）· 输入/x.png"
                "《人物参考》（控制：身份；不得控制：动作）",
                "完整 REF 语法",
            ),
            "a star-bulleted continuity lock is not silently dropped": (
                "视觉设定.md",
                LOCK_DECLARATION,
                "* 连戏锁：把常服固定住",
                "连戏锁必须使用完整语法",
            ),
            "malformed continuity lock names the offending line": (
                "视觉设定.md",
                LOCK_DECLARATION,
                "- 连戏锁：把常服的立领固定住，别再变了",
                "连戏锁必须使用完整语法: - 连戏锁：把常服的立领固定住，别再变了",
            ),
            "continuity lock without a surface": (
                "视觉设定.md",
                "）· 锁定词：pine-green lapel service jacket",
                "）· 锁定词：",
                "连戏锁必须使用完整语法",
            ),
            "continuity lock naming an unknown shot": (
                "视觉设定.md",
                LOCK_SCOPE,
                "（镜头：SHOT-EP001-099；",
                "LOCK-JIANGCHEN-DRESS: 连戏锁指向不存在的镜头: SHOT-EP001-099",
            ),
            "continuity lock naming an unknown image entry": (
                "视觉设定.md",
                "图片提示词项：IMG-JIANGCHEN-SHEET",
                "图片提示词项：IMG-NOT-DEFINED",
                "连戏锁指向不存在的 IMG 条目: IMG-NOT-DEFINED",
            ),
            "duplicate continuity lock id": (
                "视觉设定.md",
                LOCK_DECLARATION,
                LOCK_DECLARATION + "\n" + LOCK_DECLARATION,
                "LOCK-JIANGCHEN-DRESS: 连戏锁 ID 重复",
            ),
            "continuity lock mixing 全集 with named shots": (
                "视觉设定.md",
                LOCK_SCOPE,
                "（镜头：全集、SHOT-EP001-002；",
                "不能把全集与具体镜头混写",
            ),
        }
        for label, (name, old, new, expected) in mutations.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                episode = project / "剧集/EP001"
                shutil.copytree(EPISODE, episode)
                path = episode / name
                document = path.read_text(encoding="utf-8")
                self.assertIn(old, document)
                path.write_text(document.replace(old, new, 1), encoding="utf-8")
                errors = creator_markdown_check.validate_episode(episode, project)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_creator_markdown_validator_rejects_missing_and_reordered_ref_files(
        self,
    ) -> None:
        bad_declarations = {
            "missing file": (
                "REF-A（顺序：1）· 输入/不存在.png《人物参考》（用途：外貌；控制：脸型；不得控制：动作）",
                "REF 文件不存在",
            ),
            "duplicate order": (
                "REF-A（顺序：1）· 输入/a.png《人物参考》（用途：外貌；控制：脸型；不得控制：动作）；"
                "REF-B（顺序：1）· 输入/b.png《场景参考》（用途：空间布局；控制：空间地理；不得控制：人物身份）",
                "REF 顺序必须唯一",
            ),
            "missing separator": (
                "REF-A（顺序：1）· 输入/a.png《人物参考》（用途：外貌；控制：脸型；不得控制：动作）"
                "REF-B（顺序：2）· 输入/b.png《场景参考》（用途：空间布局；控制：空间地理；不得控制：人物身份）",
                "完整 REF 语法",
            ),
            "duplicate path": (
                "REF-A（顺序：1）· 输入/a.png《人物参考》（用途：外貌；控制：脸型；不得控制：动作）；"
                "REF-B（顺序：2）· 输入/a.png《同一张图的第二个身份槽位》（用途：外貌；控制：体态；不得控制：构图）",
                "REF 同一张图只能占一个槽位: 输入/a.png",
            ),
            # Production binds each file once, so a second 用途 on the same file
            # is a declaration no job can match.
            "same path with a second purpose": (
                "REF-A（顺序：1）· 输入/a.png《本镜起始画面》（用途：起始帧；控制：起始构图；不得控制：终态）；"
                "REF-B（顺序：2）· 输入/a.png《同一张图的造型槽位》（用途：造型状态；控制：本集造型；不得控制：构图）",
                "REF 同一张图只能占一个槽位: 输入/a.png",
            ),
            "conflicting scope": (
                "REF-A（顺序：1）· 输入/a.png《人物参考》（用途：外貌；控制：身份；不得控制：身份）",
                "控制与不得控制范围冲突",
            ),
        }
        for label, (declaration, expected) in bad_declarations.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                errors = self._errors_with_reference_declaration(Path(directory), declaration)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_one_picture_doing_two_jobs_passes_as_one_slot(self) -> None:
        """The repair the duplicate-path error asks for is itself accepted."""
        declaration = (
            "REF-A（顺序：1）· 输入/a.png《本镜起始画面》"
            "（用途：起始帧；控制：起始构图、本集造型；不得控制：终态）"
        )
        with tempfile.TemporaryDirectory() as directory:
            errors = self._errors_with_reference_declaration(Path(directory), declaration)
        self.assertEqual(errors, [])

    @staticmethod
    def _errors_with_reference_declaration(project: Path, declaration: str) -> list[str]:
        episode = project / "剧集/EP001"
        shutil.copytree(EPISODE, episode)
        (project / "输入").mkdir()
        (project / "输入/a.png").write_bytes(b"a")
        (project / "输入/b.png").write_bytes(b"b")
        for name in ("分镜.md", "视频提示词.md"):
            path = episode / name
            document = path.read_text(encoding="utf-8")
            path.write_text(
                document.replace(
                    "- 输入参考图：无（文生视频）。", f"- 输入参考图：{declaration}", 1
                ),
                encoding="utf-8",
            )
        video = episode / "视频提示词.md"
        video.write_text(
            video.read_text(encoding="utf-8").replace(
                "- 生成方式：文生视频", "- 生成方式：图生视频", 1
            ),
            encoding="utf-8",
        )
        return creator_markdown_check.validate_episode(episode, project)

    def test_a_lock_written_with_any_list_marker_still_validates(self) -> None:
        """A lock must never become a no-op because of how its bullet is typed."""
        declaration = LOCK_DECLARATION
        for label, written in {
            "indented": "  " + declaration,
            "full-width space": declaration.replace("- 连戏锁", "-\u3000连戏锁", 1),
            "star marker": declaration.replace("- ", "* ", 1),
            "plus marker": declaration.replace("- ", "+ ", 1),
        }.items():
            with self.subTest(marker=label), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                episode = project / "剧集/EP001"
                shutil.copytree(EPISODE, episode)
                visual = episode / "视觉设定.md"
                document = visual.read_text(encoding="utf-8")
                self.assertIn(declaration, document)
                visual.write_text(
                    document.replace(declaration, written, 1), encoding="utf-8"
                )
                # Written this way it must still pass on the correct episode...
                self.assertEqual(
                    creator_markdown_check.validate_episode(episode, project), []
                )
                # ...and still catch an unknown shot ID referenced by the lock.
                visual.write_text(
                    document.replace(
                        declaration,
                        written.replace(LOCK_SCOPE, "（镜头：SHOT-EP001-099；", 1),
                        1,
                    ),
                    encoding="utf-8",
                )
                self.assertTrue(
                    any(
                        "LOCK-JIANGCHEN-DRESS: 连戏锁指向不存在的镜头: SHOT-EP001-099" in err
                        for err in creator_markdown_check.validate_episode(episode, project)
                    )
                )

    def test_a_locked_surface_survives_a_hard_wrapped_prompt(self) -> None:
        """The copyable prompt renders as one paragraph; its source line breaks
        are not part of the text the creator wrote."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            images = episode / "图片提示词.md"
            document = images.read_text(encoding="utf-8")
            self.assertIn("pine-green lapel service jacket buttoned", document)
            images.write_text(
                document.replace(
                    "pine-green lapel service jacket buttoned",
                    "pine-green lapel\n> service jacket buttoned",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

    def test_continuity_locks_are_optional(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            episode = project / "剧集/EP001"
            shutil.copytree(EPISODE, episode)
            visual = episode / "视觉设定.md"
            visual.write_text(
                "\n".join(
                    line
                    for line in visual.read_text(encoding="utf-8").splitlines()
                    if "连戏锁" not in line
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                creator_markdown_check.validate_episode(episode, project), []
            )

    def test_frozen_keyframes_are_copyable_markdown_blocks(self) -> None:
        storyboard = text("分镜.md")
        for shot_id in heading_ids(storyboard, "SHOT-"):
            with self.subTest(shot=shot_id):
                self.assertRegex(frozen_prompt(storyboard, shot_id), r"^\s*>\s*\S")

    def test_screenplay_is_accepted_by_the_duration_estimator(self) -> None:
        blocks, summary = duration_estimate.parse_script_blocks(
            (EPISODE / "剧本.md").read_bytes(),
            speakers={"江晨", "周薄森", "上级", "其他军团的人"},
        )
        self.assertEqual(summary["review_status"], "clean")
        self.assertEqual(summary["source_issue_count"], 0)
        self.assertGreater(len(blocks), 0)

    def test_image_prompts_are_copyable_and_bounded(self) -> None:
        prompts = text("图片提示词.md")
        ids = heading_ids(prompts, "IMG-")
        self.assertGreater(len(ids), 0)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(headings(prompts, 3), ["可复制提示词"] * len(ids))
        for image_id, body in sections(prompts, "IMG-").items():
            with self.subTest(prompt=image_id):
                prompt_headings = headings(body, 3)
                self.assertEqual(prompt_headings, ["可复制提示词"])
                self.assertRegex(body.split("### ", 1)[1], r"\n>\s*\S")

    def test_every_creator_knowledge_reference_is_reachable(self) -> None:
        for skill_name in sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir() and (p / "references").is_dir()):
            skill_root = ROOT / "skills" / skill_name
            references = {
                path.resolve() for path in (skill_root / "references").rglob("*.md")
            }
            reachable = reachable_markdown(skill_root / "SKILL.md", skill_root)
            with self.subTest(skill=skill_name):
                self.assertEqual(
                    references - reachable,
                    set(),
                    "knowledge kept on disk but unreachable from the skill",
                )

    def test_creator_rule_catalogs_keep_blocking_invariants_only(self) -> None:
        row_re = re.compile(
            r"^\|\s*`?([A-Z]{3}-\d{2})`?\s*\|\s*`?([a-z_]+)`?\s*\|", re.MULTILINE
        )
        for skill_name in ACTIVE_CREATOR_SKILLS:
            contract_path = ROOT / "skills" / skill_name / "references/stage-contract.md"
            if not contract_path.is_file():
                continue
            rows = row_re.findall(contract_path.read_text(encoding="utf-8"))
            tiers = {tier for _, tier in rows}
            with self.subTest(skill=skill_name):
                self.assertTrue(rows, f"{skill_name} stage-contract.md should declare blocking rules")
                self.assertLessEqual(
                    tiers, {"structural_invariant", "reviewed_invariant"}
                )


if __name__ == "__main__":
    unittest.main()
