import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama-write/scripts/screenplay_index.py"
SPEC = importlib.util.spec_from_file_location("short_drama_screenplay_index", SCRIPT)
assert SPEC and SPEC.loader
screenplay_index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(screenplay_index)


DURATION_SCRIPT = SUITE / "skills/short-drama-write/scripts/duration_estimate.py"
DURATION_SPEC = importlib.util.spec_from_file_location(
    "short_drama_duration_estimate", DURATION_SCRIPT
)
assert DURATION_SPEC and DURATION_SPEC.loader
duration_estimate = importlib.util.module_from_spec(DURATION_SPEC)
DURATION_SPEC.loader.exec_module(duration_estimate)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def blocks(path: Path) -> list[dict[str, Any]]:
    return [row for row in read_jsonl(path) if row["record_type"] == "block"]


class RebuildGuardTests(unittest.TestCase):
    """Rebuilding over an existing index must not renumber blocks in silence.

    Without a previous version the IDs are handed out by position, so a rewritten
    block can reclaim the ID its predecessor retired. Every downstream reference
    to that ID then resolves -- to different content. Nothing downstream can see
    it, because a resolvable reference is exactly what a correct one looks like.
    """

    REVISED = (
        "# EP001\n\n"
        "## EP001-SC001 内 · 门厅 · 夜\n\n"
        "她把伞收起来。\n\n"
        "她把伞靠在墙边，没有回头。\n"
    )
    ORIGINAL = (
        "# EP001\n\n"
        "## EP001-SC001 内 · 门厅 · 夜\n\n"
        "她把伞收起来。\n"
    )

    def test_rebuilding_over_an_existing_index_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text(self.ORIGINAL, encoding="utf-8")
            screenplay_index.build_index(source, output)

            source.write_text(self.REVISED, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already holds an index"):
                screenplay_index.build_index(source, output)

    def test_the_refusal_names_the_file_and_both_ways_forward(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text(self.ORIGINAL, encoding="utf-8")
            screenplay_index.build_index(source, output)
            with self.assertRaises(ValueError) as caught:
                screenplay_index.build_index(source, output)

        message = str(caught.exception)
        self.assertIn(str(output), message)
        self.assertIn("--previous-index", message)
        self.assertIn("--no-previous", message)

    def test_an_explicit_renumber_is_still_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text(self.ORIGINAL, encoding="utf-8")
            screenplay_index.build_index(source, output)
            source.write_text(self.REVISED, encoding="utf-8")
            summary = screenplay_index.build_index(source, output, no_previous=True)

        self.assertEqual(summary["review_status"], "clean")

    def test_the_documented_path_retires_a_rewritten_block_id(self) -> None:
        """The whole point: a rewritten block must not reclaim its own ID."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            source.write_text(self.ORIGINAL, encoding="utf-8")
            screenplay_index.build_index(source, first)
            before = {row["block_id"] for row in blocks(first)}
            previous_source = root / "previous.md"
            previous_source.write_text(self.ORIGINAL, encoding="utf-8")

            source.write_text(
                self.ORIGINAL.replace("她把伞收起来。", "她把伞丢在门口。"),
                encoding="utf-8",
            )
            screenplay_index.build_index(
                source,
                second,
                previous_index_path=first,
                previous_source_path=previous_source,
            )
            after = {row["block_id"] for row in blocks(second)}

        rewritten = before - after
        self.assertTrue(
            rewritten,
            "the rewritten block kept its ID, so a stale reference would still resolve",
        )


class ScreenplayIndexTests(unittest.TestCase):
    def test_speaker_roster_rejects_non_text_and_empty_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text("# EP001\n\n## EP001-SC001 内 · 门厅 · 夜\n", encoding="utf-8")

            for speakers in ([123], ["   "]):
                with self.subTest(speakers=speakers):
                    with self.assertRaisesRegex(ValueError, "speaker names"):
                        screenplay_index.build_index(source, output, speakers=speakers)

    def test_portable_source_ref_rejects_empty_backslash_and_drive_letter_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "剧本.md"
            output = root / "screenplay-index.jsonl"
            source.write_text("# EP001\n\n## EP001-SC001 内 · 门厅 · 夜\n", encoding="utf-8")

            for bad_ref in (
                "",
                ".",
                "./",
                "./剧本.md",
                "..",
                "剧集/./剧本.md",
                "剧集/../剧本.md",
                "剧集//剧本.md",
                "剧集/剧本.md/",
                "/剧集/剧本.md",
                r"剧集\EP001\剧本.md",
                "C:/project/剧本.md",
                r"D:\剧本.md",
            ):
                with self.subTest(source_ref=bad_ref):
                    with self.assertRaisesRegex(ValueError, "portable project-relative path"):
                        screenplay_index.build_index(source, output, source_ref=bad_ref)

    def test_whitespace_after_fullwidth_colon_parses_in_dialogue_and_voice_tags(self) -> None:
        text = (
            "# EP001 夜班\n\n"
            "## EP001-SC001 内 · 档案室 · 夜\n\n"
            "林岚： 我回来了。\n\n"
            "Dr. Lin (quietly)：\tStay back.\n\n"
            "[VO] 林岚： 先别出声。\n\n"
            "[OS] 船员（隔着门）： 关窗！\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "剧本.md"
            output = root / "index.jsonl"
            source.write_text(text, encoding="utf-8")

            summary = screenplay_index.build_index(
                source, output, speakers={"林岚", "Dr. Lin", "船员"}
            )
            self.assertEqual(summary["review_status"], "clean")
            parsed = blocks(output)
            self.assertEqual(
                [row["kind"] for row in parsed],
                ["scene_heading", "dialogue", "dialogue", "production_tag", "production_tag"],
            )
            counts = duration_estimate.measure(source.read_bytes(), parsed)
            self.assertNotIn("unreadable_blocks", counts)
            self.assertEqual(counts["dialogue_lines"], 4)
            self.assertEqual(counts["voiced_characters"], 10)
            self.assertEqual(counts["voiced_words"], 2)

    def test_candidate_preview_marks_every_source_ref_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text(
                "# EP001\n\n## EP001-SC001 内 · 门厅 · 夜\n\n她关上门。\n",
                encoding="utf-8",
            )

            screenplay_index.build_index(
                source,
                output,
                source_ref="episodes/EP001/screenplay.md",
                authority="candidate",
            )

            records = read_jsonl(output)
            refs = [record["source_ref"] for record in records if "source_ref" in record]
            self.assertTrue(refs)
            self.assertTrue(all(ref["authority"] == "candidate" for ref in refs))

    def test_stable_rerun_preserves_ids_offsets_hash_and_source_bytes(self) -> None:
        source_bytes = (
            "# EP001 夜班\r\n\r\n"
            "## EP001-SC001 内 · 档案室 · 夜\r\n\r\n"
            "林岚把复检记录压在桌角。\r\n\r\n"
            "林岚（压低声音）：你看见日期了吗？\r\n\r\n"
            "[SFX] 门外脚步停住。\r\n"
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "中文 项目"
            root.mkdir()
            source = root / "第一集 剧本.md"
            source.write_bytes(source_bytes)
            first = root / "旧 索引.jsonl"
            second = root / "新 索引.jsonl"

            screenplay_index.build_index(source, first, speakers={"林岚"})
            screenplay_index.build_index(
                source,
                second,
                previous_index_path=first,
                previous_source_path=source,
                speakers={"林岚"},
            )

            self.assertEqual(source.read_bytes(), source_bytes)
            first_blocks = blocks(first)
            second_blocks = blocks(second)
            self.assertEqual(
                [row["block_id"] for row in first_blocks],
                [row["block_id"] for row in second_blocks],
            )
            self.assertTrue(
                all(row["mapping"]["status"] == "reused" for row in second_blocks)
            )
            meta = read_jsonl(second)[0]
            # The index declares its screenplay once and every reference names
            # it by key. A rerun over the same bytes is the same snapshot, so
            # the previous source resolves to that one declaration too.
            self.assertEqual(meta["source_ref"], {"src": "screenplay"})
            self.assertEqual(meta["previous_source_ref"], {"src": "screenplay"})
            self.assertEqual(
                meta["sources"],
                {
                    "screenplay": {
                        "owner": "short-drama-write",
                        "artifact": "第一集 剧本.md",
                    }
                },
            )
            self.assertNotIn("source_sha256", meta)
            self.assertNotIn("previous_source_sha256", meta)
            self.assertTrue(all("source_sha256" not in row for row in read_jsonl(second)))
            self.assertEqual(meta["newline_style"], "crlf")

    def test_previous_index_blocks_must_still_match_parsed_source_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            previous_index = root / "previous.jsonl"
            next_index = root / "next.jsonl"
            source.write_text(
                "# EP001\n\n## EP001-SC001 内 · 门厅 · 夜\n\ndoor opens.\n",
                encoding="utf-8",
            )
            screenplay_index.build_index(source, previous_index)
            records = read_jsonl(previous_index)
            action = next(row for row in records if row.get("kind") == "action")
            action["byte_start"] += 1
            previous_index.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not resolve against previous source"):
                screenplay_index.build_index(
                    source,
                    next_index,
                    previous_index_path=previous_index,
                    previous_source_path=source,
                )

    def test_nearby_insertion_reuses_unchanged_block_ids(self) -> None:
        old_text = """# EP001 夜班

## EP001-SC001 内 · 档案室 · 夜

林岚把记录压在桌角。

周野：不是我签的。
"""
        new_text = """# EP001 夜班

## EP001-SC001 内 · 档案室 · 夜

门锁在他们身后扣上。

林岚把记录压在桌角。

周野：不是我签的。
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_source = root / "old.md"
            new_source = root / "new.md"
            old_index = root / "old.jsonl"
            new_index = root / "new.jsonl"
            old_source.write_bytes(old_text.encode("utf-8"))
            new_source.write_bytes(new_text.encode("utf-8"))
            screenplay_index.build_index(old_source, old_index, speakers={"周野"})
            screenplay_index.build_index(
                new_source,
                new_index,
                previous_index_path=old_index,
                previous_source_path=old_source,
                speakers={"周野"},
            )

            old_ids = {row["block_id"] for row in blocks(old_index)}
            new_rows = blocks(new_index)
            reused = [row for row in new_rows if row["mapping"]["status"] == "reused"]
            self.assertEqual(len(reused), 3)
            for row in reused:
                self.assertIn(row["block_id"], old_ids)
                self.assertEqual(row["mapping"]["previous_block_ids"], [row["block_id"]])
            inserted = [row for row in new_rows if row["mapping"]["status"] == "new"]
            self.assertEqual(len(inserted), 1)
            self.assertNotIn(inserted[0]["block_id"], old_ids)

    def test_split_and_merge_are_unresolved_instead_of_guessed(self) -> None:
        cases = {
            "split": (
                "她推开门。又把灯关掉。",
                "她推开门。\n\n又把灯关掉。",
            ),
            "merge": (
                "她推开门。\n\n又把灯关掉。",
                "她推开门。又把灯关掉。",
            ),
        }
        for name, (old_action, new_action) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                old_source = root / "old.md"
                new_source = root / "new.md"
                old_index = root / "old.jsonl"
                new_index = root / "new.jsonl"
                shell = "# EP001 夜班\n\n## EP001-SC001 内 · 门厅 · 夜\n\n{}\n"
                old_source.write_text(shell.format(old_action), encoding="utf-8")
                new_source.write_text(shell.format(new_action), encoding="utf-8")
                screenplay_index.build_index(old_source, old_index)
                screenplay_index.build_index(
                    new_source,
                    new_index,
                    previous_index_path=old_index,
                    previous_source_path=old_source,
                )

                old_action_id = next(
                    row["block_id"] for row in blocks(old_index) if row["kind"] == "action"
                )
                new_actions = [row for row in blocks(new_index) if row["kind"] == "action"]
                self.assertTrue(new_actions)
                self.assertTrue(
                    all(row["mapping"]["status"] == "unresolved" for row in new_actions)
                )
                self.assertNotIn(old_action_id, {row["block_id"] for row in new_actions})
                requests = [
                    row
                    for row in read_jsonl(new_index)
                    if row["record_type"] == "mapping_review_request"
                ]
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]["reason"], name)
                self.assertIn(old_action_id, requests[0]["previous_block_ids"])

    def test_large_split_and_merge_are_unresolved_without_an_arbitrary_width_cap(self) -> None:
        parts = [f"她推开第{number}扇门。" for number in range(1, 10)]
        cases = {
            "split": ("".join(parts), "\n\n".join(parts)),
            "merge": ("\n\n".join(parts), "".join(parts)),
        }
        for name, (old_action, new_action) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                old_source = root / "old.md"
                new_source = root / "new.md"
                old_index = root / "old.jsonl"
                new_index = root / "new.jsonl"
                shell = "# EP001 夜班\n\n## EP001-SC001 内 · 门厅 · 夜\n\n{}\n"
                old_source.write_text(shell.format(old_action), encoding="utf-8")
                new_source.write_text(shell.format(new_action), encoding="utf-8")
                screenplay_index.build_index(old_source, old_index)

                summary = screenplay_index.build_index(
                    new_source,
                    new_index,
                    previous_index_path=old_index,
                    previous_source_path=old_source,
                )

                requests = [
                    row
                    for row in read_jsonl(new_index)
                    if row["record_type"] == "mapping_review_request"
                ]
                self.assertEqual(summary["review_status"], "review_required")
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]["reason"], name)
                current_actions = [
                    row for row in blocks(new_index) if row["kind"] == "action"
                ]
                self.assertTrue(current_actions)
                self.assertTrue(
                    all(row["mapping"]["status"] == "unresolved" for row in current_actions)
                )

    def test_previous_dialogue_is_loaded_independently_of_current_speaker_roster(self) -> None:
        old_text = """# EP001 夜班

## EP001-SC001 内 · 门厅 · 夜

林岚：这句话会在修订中删除。
"""
        new_text = """# EP001 夜班

## EP001-SC001 内 · 门厅 · 夜

周野：现在只剩我在场。
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_source = root / "old.md"
            new_source = root / "new.md"
            old_index = root / "old.jsonl"
            new_index = root / "new.jsonl"
            old_source.write_text(old_text, encoding="utf-8")
            new_source.write_text(new_text, encoding="utf-8")
            screenplay_index.build_index(old_source, old_index, speakers={"林岚"})

            summary = screenplay_index.build_index(
                new_source,
                new_index,
                previous_index_path=old_index,
                previous_source_path=old_source,
                speakers={"周野"},
            )

            self.assertEqual(summary["review_status"], "clean")
            dialogue = next(row for row in blocks(new_index) if row["kind"] == "dialogue")
            self.assertEqual(dialogue["speaker"], "周野")

    def test_moved_duplicate_exact_blocks_require_explicit_mapping(self) -> None:
        old_text = """# EP001 夜班

## EP001-SC001 内 · 门厅 · 夜

门外传来两声敲门。

林岚：谁？

门外传来两声敲门。
"""
        new_text = old_text.replace("\n\n门外传来两声敲门。", "\n\n灯先灭了。\n\n门外传来两声敲门。", 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_source = root / "old.md"
            new_source = root / "new.md"
            old_index = root / "old.jsonl"
            new_index = root / "new.jsonl"
            old_source.write_text(old_text, encoding="utf-8")
            new_source.write_text(new_text, encoding="utf-8")
            screenplay_index.build_index(old_source, old_index, speakers={"林岚"})
            screenplay_index.build_index(
                new_source,
                new_index,
                previous_index_path=old_index,
                previous_source_path=old_source,
                speakers={"林岚"},
            )

            body = new_source.read_bytes()
            repeated = [
                row
                for row in blocks(new_index)
                if body[row["byte_start"] : row["byte_end"]].decode() == "门外传来两声敲门。"
            ]
            self.assertEqual(len(repeated), 2)
            self.assertTrue(
                all(row["mapping"]["status"] == "unresolved" for row in repeated)
            )
            requests = [
                row
                for row in read_jsonl(new_index)
                if row["record_type"] == "mapping_review_request"
            ]
            self.assertEqual(requests[0]["reason"], "duplicate_exact_match")

    def test_invalid_heading_and_labels_are_reported_not_parsed_as_action(self) -> None:
        text = """# EP001 夜班

## EP001-SC001 室内 - 档案室 - 夜

不应归到上一场的文字。

## EP001-SC002 内 · 走廊 · 夜

[BGM] 紧张音乐。

林岚: 这不是受支持的全角对白格式。

[SFX 门外脚步停住。
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text(text, encoding="utf-8")
            summary = screenplay_index.build_index(source, output, speakers={"周野"})

            rows = read_jsonl(output)
            issues = [row for row in rows if row["record_type"] == "source_issue"]
            codes = {row["issue_code"] for row in issues}
            self.assertIn("invalid_scene_heading", codes)
            self.assertIn("content_outside_scene", codes)
            self.assertIn("unsupported_production_tag", codes)
            self.assertIn("invalid_dialogue_syntax", codes)
            self.assertIn("malformed_production_tag", codes)
            self.assertEqual(summary["review_status"], "review_required")
            self.assertEqual(
                [row["kind"] for row in rows if row["record_type"] == "block"],
                ["scene_heading"],
            )

    def test_season_scoped_scene_ids_index_like_the_cross_document_checker_reads_them(
        self,
    ) -> None:
        # creator_markdown_check accepts `S01-EP001-SC001`; the writing stage
        # must not reject a heading the later check calls valid.
        text = "# EP001 夜班\n\n## S01-EP001-SC001 内 · 档案室 · 夜\n\n林岚推开门。\n"
        mismatched = "# EP002 夜班\n\n## S01-EP001-SC001 内 · 档案室 · 夜\n\n林岚推开门。\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text(text, encoding="utf-8")
            summary = screenplay_index.build_index(source, output, speakers={"林岚"})
            self.assertEqual(summary["review_status"], "clean")
            heading = blocks(output)[0]
            self.assertEqual(heading["scene_id"], "S01-EP001-SC001")

            other = root / "other.md"
            other_output = root / "other-index.jsonl"
            other.write_text(mismatched, encoding="utf-8")
            screenplay_index.build_index(other, other_output, speakers={"林岚"})
            codes = {
                row["issue_code"]
                for row in read_jsonl(other_output)
                if row["record_type"] == "source_issue"
            }
            self.assertIn("episode_scene_mismatch", codes)

    def test_colon_action_requires_owner_resolution_instead_of_speaker_guessing(self) -> None:
        cases = {
            "single_line": "手机屏幕显示：密码错误。",
            "second_line": "她抬头看向墙面。\n墙上写着：闲人免进。",
        }
        for name, action in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "screenplay.md"
                output = root / "screenplay-index.jsonl"
                source.write_text(
                    "# EP001 夜班\n\n"
                    "## EP001-SC001 内 · 档案室 · 夜\n\n"
                    f"{action}\n",
                    encoding="utf-8",
                )

                summary = screenplay_index.build_index(source, output)
                rows = read_jsonl(output)

                self.assertEqual(summary["review_status"], "review_required")
                self.assertIn(
                    "ambiguous_dialogue_or_action",
                    {
                        row["issue_code"]
                        for row in rows
                        if row["record_type"] == "source_issue"
                    },
                )
                self.assertFalse(
                    any(
                        row.get("kind") == "dialogue"
                        for row in rows
                        if row["record_type"] == "block"
                    )
                )

    def test_missing_separator_before_dialogue_requires_review(self) -> None:
        text = """# EP001 夜班

## EP001-SC001 内 · 档案室 · 夜

林岚把复检记录压在桌角。
周野：日期不是我改的。
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            output = root / "screenplay-index.jsonl"
            source.write_text(text, encoding="utf-8")

            summary = screenplay_index.build_index(source, output, speakers={"周野"})
            rows = read_jsonl(output)

            self.assertEqual(summary["review_status"], "review_required")
            self.assertIn(
                "missing_block_separator",
                {
                    row["issue_code"]
                    for row in rows
                    if row["record_type"] == "source_issue"
                },
            )
            self.assertEqual(
                [row["kind"] for row in rows if row["record_type"] == "block"],
                ["scene_heading"],
            )

    def test_cli_handles_space_paths_without_modifying_source(self) -> None:
        source_bytes = (
            "# EP001 夜班\n\n"
            "## EP001-SC001 内 · 档案室 · 夜\n\n"
            "<!-- 待确认：门锁年份。 -->\n\n"
            "林岚：签字不是我的。\n"
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "项目 有空格"
            root.mkdir()
            source = root / "剧本 源.md"
            output = root / "派生 索引.jsonl"
            source.write_bytes(source_bytes)

            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    str(source),
                    "--output",
                    str(output),
                    "--speaker",
                    "林岚",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertEqual(source.read_bytes(), source_bytes)
            parsed = json.loads(result.stdout)
            self.assertEqual(parsed["review_status"], "clean")
            self.assertEqual(
                [row["kind"] for row in blocks(output)],
                ["scene_heading", "comment", "dialogue"],
            )

    def test_cli_summary_survives_a_non_utf8_stdout_encoding(self) -> None:
        """回归：成功摘要曾用 ensure_ascii=False 打印，而摘要里带着输出路径。

        stdout 重定向到文件或管道时，Windows 用的是 ANSI 代码页而不是 UTF-8；
        本仓库的路径含中文，于是索引已经写完落盘之后，进程才在打印那一步抛
        UnicodeEncodeError，退出码从 0 变成 1，后面的 --fail-on-review 判定也
        不再执行——调用方据退出码判断，会把做完的活当成失败。POSIX 上用
        PYTHONIOENCODING 能触发同一个 TextIOWrapper 路径，所以这条在开发机上
        就会红，不必等 Windows runner。
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "剧集"
            root.mkdir()
            source = root / "剧本.md"
            source.write_bytes(
                (
                    "# EP001 夜班\n\n"
                    "## EP001-SC001 内 · 档案室 · 夜\n\n"
                    "林岚：签字不是我的。\n"
                ).encode()
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    str(source),
                    "--output",
                    str(root / "索引.jsonl"),
                    "--speaker",
                    "林岚",
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "ascii"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["review_status"], "clean")

    def test_fullwidth_dialect_tag_is_diagnosed_without_dropping_its_block(self) -> None:
        """The diagnosis must not renumber block IDs downstream artifacts cite."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "screenplay.md"
            source.write_text(
                "# EP001 测试\n\n"
                "## EP001-SC001 内 · 会议室 · 日\n\n"
                "【特写】墙上的钟停在三点。\n\n"
                "角色甲：这是我的决定。\n",
                encoding="utf-8",
            )
            output = root / "index.jsonl"
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), str(source),
                 "--output", str(output), "--speaker", "角色甲"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            rows = read_jsonl(output)
            codes = [r["issue_code"] for r in rows if r["record_type"] == "source_issue"]
            self.assertIn("unsupported_production_tag", codes)
            # The paragraph still occupies a block, so later IDs keep their numbers.
            self.assertEqual(
                [row["kind"] for row in blocks(output)],
                ["scene_heading", "action", "dialogue"],
            )
            self.assertEqual(
                [row["block_id"] for row in blocks(output)][1:],
                ["BLK-EP001-SC001-A01", "BLK-EP001-SC001-D01"],
            )

    def test_dialect_dialogue_is_not_mistaken_for_a_production_tag(self) -> None:
        """production-format-dialect writes the cue with ASCII parens."""

        for line in ("【萧尘渊】(目光坚定)：我不会退。", "【周野】（冷）：你来了。"):
            with self.subTest(line=line), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "screenplay.md"
                source.write_text(
                    "# EP001 测试\n\n"
                    "## EP001-SC001 内 · 会议室 · 日\n\n"
                    f"{line}\n",
                    encoding="utf-8",
                )
                output = root / "index.jsonl"
                subprocess.run(
                    [sys.executable, "-B", str(SCRIPT), str(source), "--output", str(output)],
                    check=True, capture_output=True, text=True,
                )
                codes = [
                    row["issue_code"]
                    for row in read_jsonl(output)
                    if row["record_type"] == "source_issue"
                ]
                self.assertIn("ambiguous_dialogue_or_action", codes)
                self.assertNotIn("unsupported_production_tag", codes)


class EpisodeIdentifierAgreementTests(unittest.TestCase):
    """The screenplay heading and the project directory must admit one spelling.

    They diverged once already: the lifecycle tool accepted `EP[0-9]{3,}` while
    the indexer required exactly three digits, so `EP1000` was a legal
    directory and an illegal heading. Nothing asserted they agreed, so the
    divergence was invisible until someone shipped a 1000-episode series.
    """

    def project_tool(self):
        import importlib.util

        script = SUITE / "skills/short-drama/scripts/project_tool.py"
        spec = importlib.util.spec_from_file_location("pt_for_ep_agreement", script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_both_enforcers_accept_and_reject_the_same_episode_ids(self) -> None:
        episode_re = self.project_tool().EPISODE_ID_RE
        for candidate, legal in [
            ("EP001", True),
            ("EP999", True),
            ("EP1000", True),
            ("EP12345", True),
            ("EP0001", False),
            ("EP1", False),
            ("ep001", False),
            ("EP01", False),
            ("EPabc", False),
        ]:
            with self.subTest(candidate=candidate):
                heading = screenplay_index.EPISODE_HEADING_RE.fullmatch(f"# {candidate}")
                self.assertEqual(
                    heading is not None,
                    legal,
                    msg=f"heading grammar disagrees on {candidate}",
                )
                self.assertEqual(
                    episode_re.fullmatch(candidate) is not None,
                    legal,
                    msg=f"lifecycle path rule disagrees on {candidate}",
                )

    def test_scene_ids_do_not_admit_full_width_digits(self) -> None:
        # `\d` is Unicode-aware, so EP001-SC００１ and EP001-SC001 would be two
        # spellings of one scene inside the durable BLK- identity namespace.
        for scene_token, legal in (
            ("EP001-SC001", True),
            ("EP001-SC999", True),
            ("EP001-SC1000", True),
            ("EP1000-SC1000", True),
            ("S01-EP1000-SC12345", True),
            ("EP001-SC01", False),
            ("EP001-SC1", False),
            ("EP001-SC0001", False),
            ("EP001-SC００１", False),
        ):
            with self.subTest(scene_token=scene_token):
                match = screenplay_index.SCENE_HEADING_RE.fullmatch(
                    f"## {scene_token} 内 · 房间 · 日"
                )
                self.assertEqual(match is not None, legal)

class RetiredIdsStayRetiredTests(unittest.TestCase):
    """A retired block ID must never be handed to different content.

    Retirement was one generation deep: the counter was seeded from the previous
    index alone, so once every block of one kind in a scene was gone, the next
    revision restarted numbering at 01 and reissued an ID that used to mean
    something else. Downstream artifacts cite these IDs bare, so the stale
    reference resolves cleanly and silently points at new content -- resolving
    cleanly is exactly what is supposed to rule that out.
    """

    HEAD = "# EP001\n\n## EP001-SC001 内 · 房间 · 日\n\n"

    def revise(self, root: Path, name: str, body: str, previous: "str | None") -> "list[str]":
        source = root / f"{name}.md"
        source.write_text(self.HEAD + body, encoding="utf-8")
        index_path = root / f"{name}.jsonl"
        screenplay_index.build_index(
            source,
            index_path,
            source_ref="剧集/EP001/screenplay.md",
            speakers=["甲"],
            previous_index_path=root / f"{previous}.jsonl" if previous else None,
            previous_source_path=root / f"{previous}.md" if previous else None,
            no_previous=previous is None,
        )
        return [
            record["block_id"]
            for record in read_jsonl(index_path)
            if record.get("kind") == "dialogue"
        ]

    def test_an_id_is_not_reissued_after_its_whole_kind_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.revise(root, "v1", "甲：第一句。\n\n甲：第二句。\n", None)
            self.revise(root, "v2", "甲：完全不同的台词。\n", "v1")
            self.revise(root, "v3", "他关上门。\n", "v2")
            last = self.revise(root, "v4", "他关上门。\n\n甲：全新的一句话。\n", "v3")

        self.assertEqual(len(first), 2)
        self.assertEqual(len(last), 1)
        self.assertNotIn(
            last[0],
            first,
            f"{last[0]} was retired in an earlier revision and has been reissued "
            f"to different content",
        )

    def test_the_high_water_mark_survives_a_revision_that_uses_none_of_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.revise(root, "v1", "甲：第一句。\n\n甲：第二句。\n", None)
            self.revise(root, "v2", "他关上门。\n", "v1")
            meta = read_jsonl(root / "v2.jsonl")[0]

        self.assertEqual(meta["block_id_high_water"].get("EP001-SC001|D"), 2)


class LoosenedGrammarAndDirectEstimateTests(unittest.TestCase):
    def test_foreign_spaced_speakers_ascii_cues_and_colon_action_prose(self) -> None:
        long_speaker = "Inspector Alexander Hamilton-Wright"
        self.assertEqual(screenplay_index.MAX_SPEAKER_LENGTH, 40)
        self.assertEqual(duration_estimate.MAX_SPEAKER_LENGTH, 40)
        text = (
            "# EP001 Night Shift\n\n"
            "## EP001-SC001 内·档案室·夜\n\n"
            "他推开虚掩的木门，借着走廊微光看见桌上留着一张字条：今晚九点渡口见。\n\n"
            "Dr. Lin (quietly)：Stay back from the cabinet.\n\n"
            "[OS] Agent K (over radio)：Copy that, moving in.\n\n"
            f"{long_speaker} (calmly)：Seal the exit.\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "剧本.md"
            output = root / "index.jsonl"
            source.write_text(text, encoding="utf-8")

            summary = screenplay_index.build_index(
                source,
                output,
                speakers={"Dr. Lin", "Agent K", long_speaker},
            )
            self.assertEqual(summary["review_status"], "clean")
            parsed_blocks = blocks(output)
            self.assertEqual(
                [row["kind"] for row in parsed_blocks],
                ["scene_heading", "action", "dialogue", "production_tag", "dialogue"],
            )
            self.assertEqual(parsed_blocks[0]["location"], "档案室")
            self.assertEqual(parsed_blocks[2]["speaker"], "Dr. Lin")
            self.assertEqual(parsed_blocks[2]["performance_cue"], "quietly")
            self.assertEqual(parsed_blocks[3]["speaker"], "Agent K")
            self.assertEqual(parsed_blocks[3]["performance_cue"], "over radio")
            self.assertEqual(parsed_blocks[4]["speaker"], long_speaker)
            self.assertEqual(parsed_blocks[4]["performance_cue"], "calmly")

            counts = duration_estimate.measure(source.read_bytes(), parsed_blocks)
            self.assertNotIn("unreadable_blocks", counts)
            self.assertEqual(counts["action_paragraphs"], 1)
            self.assertEqual(counts["dialogue_lines"], 3)
            self.assertEqual(counts["voiced_words"], 12)

    def test_duration_estimate_script_flag_runs_in_memory_without_index_file(self) -> None:
        script_text = (
            "# EP001 夜班\n\n"
            "## EP001-SC001 内·客厅·夜\n\n"
            "陈予安推开门。\n\n"
            "陈予安 (压低声音)：关窗。\n\n"
            "Dr. Lin (quietly)：Stay back.\n\n"
            "[VO] 陈予安：不能让他看见。\n"
        )
        project = {
            "format": {
                "target_seconds_per_episode": 20,
                "pacing": {
                    "spoken_characters_per_second": 4.0,
                    "spoken_words_per_second": 2.0,
                    "seconds_per_action_paragraph": 3.0,
                },
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "剧本.md"
            project_path = root / "short-drama.json"
            source.write_text(script_text, encoding="utf-8")
            project_path.write_text(json.dumps(project), encoding="utf-8")

            direct = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(DURATION_SCRIPT),
                    "--script",
                    str(source),
                    "--project",
                    str(project_path),
                    "--target-seconds",
                    "15",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(direct.returncode, 0, direct.stderr)
            self.assertEqual(list(root.glob("*.jsonl")), [])
            direct_report = json.loads(direct.stdout)
            self.assertNotIn("incomplete", direct_report)
            self.assertEqual(direct_report["counts"]["action_paragraphs"], 1)
            self.assertEqual(direct_report["counts"]["dialogue_lines"], 3)
            self.assertEqual(direct_report["counts"]["voiced_characters"], 8)
            self.assertEqual(direct_report["counts"]["voiced_words"], 2)
            self.assertEqual(direct_report["seconds"], 6.0)
            self.assertEqual(direct_report["target_seconds"], 15.0)

            index_path = root / "index.jsonl"
            screenplay_index.build_index(
                source, index_path, speakers={"陈予安", "Dr. Lin"}
            )
            legacy = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(DURATION_SCRIPT),
                    str(source),
                    "--index",
                    str(index_path),
                    "--project",
                    str(project_path),
                    "--target-seconds",
                    "15",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(legacy.returncode, 0, legacy.stderr)
            self.assertEqual(json.loads(legacy.stdout), direct_report)

    def test_duration_estimate_script_flags_colon_action_and_panels_while_honoring_cast_and_speakers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for label, body in (
                ("colon_action", "他写下两个字：军宣。\n\n他写下两个字：必胜。\n"),
                ("panel_label", "第二格：许棠猛地回头。\n\n第三格：走廊灯灭。\n"),
                ("bracket_tag", "【音效：雷声】\n"),
            ):
                with self.subTest(case=label):
                    source = root / f"{label}.md"
                    source.write_text(
                        "# EP001 测试\n\n## EP001-SC001 内 · 办公室 · 夜\n\n" + body,
                        encoding="utf-8",
                    )
                    completed = subprocess.run(
                        [sys.executable, "-B", str(DURATION_SCRIPT), "--script", str(source)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    report = json.loads(completed.stdout)
                    self.assertEqual(report["counts"]["dialogue_lines"], 0)
                    self.assertIn("incomplete", report)
                    self.assertTrue(report["incomplete"]["needs_human_review"])
                    self.assertEqual(
                        report["incomplete"]["index_review_status"], "review_required"
                    )

            # Recurring speaker (>=2 lines) without 人物： or --speaker is auto-enrolled cleanly.
            recurring = root / "recurring.md"
            recurring.write_text(
                "# EP001 测试\n\n## EP001-SC001 内 · 走廊 · 夜\n\n"
                "门外的人：开门。\n\n门外的人：别装不在。\n",
                encoding="utf-8",
            )
            rec_blocks, rec_review = duration_estimate.parse_script_blocks(
                recurring.read_bytes()
            )
            rec_report = duration_estimate.estimate(
                recurring.read_bytes(), rec_blocks, None, rec_review
            )
            self.assertNotIn("incomplete", rec_report)
            self.assertEqual(rec_report["counts"]["dialogue_lines"], 2)

            # When 人物： or --speaker is present, ONLY that union is accepted as speakers.
            cast_script = (
                "# EP001 测试\n\n"
                "人物：林岚、Dr. Lin\n\n"
                "## EP001-SC001 内 · 档案室 · 夜\n\n"
                "林岚：门锁被人动过。\n\n"
                "Dr. Lin (quietly)：Stay back.\n\n"
                "Agent K：Clear the hall.\n"
            )
            cast_path = root / "cast.md"
            cast_path.write_text(cast_script, encoding="utf-8")

            without_extra = subprocess.run(
                [sys.executable, "-B", str(DURATION_SCRIPT), "--script", str(cast_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            unresolved_report = json.loads(without_extra.stdout)
            self.assertIn("incomplete", unresolved_report)
            self.assertTrue(unresolved_report["incomplete"]["needs_human_review"])
            self.assertIn(
                "ambiguous_dialogue_or_action",
                unresolved_report["incomplete"]["issue_codes"],
            )

            with_speaker_flag = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(DURATION_SCRIPT),
                    "--script",
                    str(cast_path),
                    "--speaker",
                    "Agent K",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            resolved_report = json.loads(with_speaker_flag.stdout)
            self.assertNotIn("incomplete", resolved_report)
            self.assertEqual(resolved_report["counts"]["dialogue_lines"], 3)

    def test_auto_speaker_accepts_names_alphanumeric_roles_and_latin_phrases_while_blocking_action(
        self,
    ) -> None:
        valid_script = (
            "# EP001 测试\n\n"
            "## EP001-SC001 内 · 门厅 · 夜\n\n"
            "林落：到了。\n\n"
            "周显：进来说。\n\n"
            "拉姆：等等。\n\n"
            "李有才：账本在这。\n\n"
            "看门大爷：谁啊？\n\n"
            "保镖1：退后。\n\n"
            "007：收到。\n\n"
            "Agent 47：Target acquired.\n\n"
            "Agent Smith：Stay where you are.\n"
        ).encode("utf-8")
        parsed_blocks, review = duration_estimate.parse_script_blocks(valid_script)
        report = duration_estimate.estimate(valid_script, parsed_blocks, None, review)
        self.assertEqual(review["review_status"], "clean")
        self.assertNotIn("incomplete", report)
        self.assertEqual(report["counts"]["dialogue_lines"], 9)

        for label, line in (
            ("pronoun_action", "他写下两个字：军宣。"),
            ("screen_display", "手机屏幕显示：密码错误。"),
            ("wall_writing", "墙上写着：闲人免进。"),
            ("bare_number", "1：推门进去。"),
            ("time_measure", "10分钟后：众人散去。"),
        ):
            with self.subTest(case=label):
                raw = (
                    "# EP001 测试\n\n## EP001-SC001 内 · 门厅 · 夜\n\n" + line + "\n"
                ).encode("utf-8")
                bad_blocks, bad_review = duration_estimate.parse_script_blocks(raw)
                bad_report = duration_estimate.estimate(raw, bad_blocks, None, bad_review)
                self.assertEqual(bad_review["review_status"], "review_required")
                self.assertIn("incomplete", bad_report)
                self.assertEqual(bad_report["counts"]["dialogue_lines"], 0)

    def test_cast_declaration_lines_are_accepted_in_screenplay_index_and_placeholder_cast_falls_back(
        self,
    ) -> None:
        script_text = (
            "# EP001 夜班\n\n"
            "人物：许棠、周叙\n"
            "- 人物: 林岚\n\n"
            "## EP001-SC001 内 · 档案室 · 夜\n\n"
            "- 人物：待定\n\n"
            "许棠：门没锁。\n\n"
            "林岚：进来再说。\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cast_clean.md"
            output = root / "cast_clean.jsonl"
            source.write_text(script_text, encoding="utf-8")

            summary = screenplay_index.build_index(
                source, output, speakers={"许棠", "周叙", "林岚"}
            )
            self.assertEqual(summary["review_status"], "clean")
            self.assertEqual(summary["source_issue_count"], 0)
            self.assertEqual(
                [row["kind"] for row in blocks(output)],
                ["scene_heading", "dialogue", "dialogue"],
            )

            # Mid-scene `人物：...` after scene body has started is still flagged unless
            # "人物" was explicitly named as a speaker.
            mid_scene = root / "mid_scene_cast.md"
            mid_scene_idx = root / "mid_scene_cast.jsonl"
            mid_scene.write_text(
                "# EP001 夜班\n\n## EP001-SC001 内 · 档案室 · 夜\n\n"
                "许棠推开门。\n\n人物：不该出现在场中段。\n",
                encoding="utf-8",
            )
            mid_summary = screenplay_index.build_index(
                mid_scene, mid_scene_idx, speakers={"许棠"}
            )
            self.assertEqual(mid_summary["review_status"], "review_required")

            # `人物：待定` / `人物：无` falls back to auto-discovery instead of zeroing dialogue.
            for placeholder in ("人物：待定", "- 人物：无", "人物: 待定、无"):
                with self.subTest(placeholder=placeholder):
                    raw = (
                        f"# EP001 夜班\n\n{placeholder}\n\n"
                        "## EP001-SC001 内 · 档案室 · 夜\n\n"
                        "许棠：门没锁。\n\n"
                        "周叙：别开灯。\n"
                    ).encode("utf-8")
                    parsed_blocks, review = duration_estimate.parse_script_blocks(raw)
                    report = duration_estimate.estimate(raw, parsed_blocks, None, review)
                    self.assertEqual(review["review_status"], "clean")
                    self.assertNotIn("incomplete", report)
                    self.assertEqual(report["counts"]["dialogue_lines"], 2)

    def test_extra_speaker_unions_while_speaker_replaces_auto_discovery(self) -> None:
        script_text = (
            "# EP001 夜班\n\n"
            "## EP001-SC001 内 · 走廊 · 夜\n\n"
            "许棠：谁在外面？\n\n"
            "周叙：别出声。\n\n"
            "门外送货的老张：放门口了。\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "rare_speaker.md"
            source.write_text(script_text, encoding="utf-8")

            # Without --extra-speaker, the 7-char one-off label with "的" is held for review.
            default_run = subprocess.run(
                [sys.executable, "-B", str(DURATION_SCRIPT), "--script", str(source)],
                check=False,
                capture_output=True,
                text=True,
            )
            default_report = json.loads(default_run.stdout)
            self.assertIn("incomplete", default_report)
            self.assertEqual(default_report["counts"]["dialogue_lines"], 2)

            # --extra-speaker unions onto auto-discovered 许棠 and 周叙.
            extra_run = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(DURATION_SCRIPT),
                    "--script",
                    str(source),
                    "--extra-speaker",
                    "门外送货的老张",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(extra_run.returncode, 0, extra_run.stderr)
            extra_report = json.loads(extra_run.stdout)
            self.assertNotIn("incomplete", extra_report)
            self.assertEqual(extra_report["counts"]["dialogue_lines"], 3)

            # --speaker alone replaces auto-discovery with an explicit whitelist.
            override_run = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(DURATION_SCRIPT),
                    "--script",
                    str(source),
                    "--speaker",
                    "门外送货的老张",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            override_report = json.loads(override_run.stdout)
            self.assertIn("incomplete", override_report)
            self.assertEqual(override_report["counts"]["dialogue_lines"], 1)

    def test_numeric_clock_prefixes_parse_as_action_prose(self) -> None:
        script_text = (
            "# EP001 夜班\n\n"
            "## EP001-SC001 内 · 走廊 · 夜\n\n"
            "12:00，走廊灯灭了。\n\n"
            "09:30 会议室门被推开。\n\n"
            "12：00，远处钟声响起。\n\n"
            "林岚抬手看表。\n23:59，电梯停在负一层。\n\n"
            "林岚：时间到了。\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clock.md"
            output = root / "clock.jsonl"
            source.write_text(script_text, encoding="utf-8")

            summary = screenplay_index.build_index(source, output, speakers={"林岚"})
            self.assertEqual(summary["review_status"], "clean")
            self.assertEqual(
                [row["kind"] for row in blocks(output)],
                ["scene_heading", "action", "action", "action", "action", "dialogue"],
            )

            raw = source.read_bytes()
            direct_blocks, direct_review = duration_estimate.parse_script_blocks(raw)
            report = duration_estimate.estimate(raw, direct_blocks, None, direct_review)
            self.assertEqual(direct_review["review_status"], "clean")
            self.assertNotIn("incomplete", report)
            self.assertEqual(report["counts"]["action_paragraphs"], 4)
            self.assertEqual(report["counts"]["dialogue_lines"], 1)

    def test_voiced_units_excludes_unicode_symbols_and_estimate_validates_target_seconds(
        self,
    ) -> None:
        self.assertEqual(duration_estimate._voiced_units("Pay $100000 now."), (0, 3))
        self.assertEqual(duration_estimate._voiced_units(" Wire €500 + $20° now! "), (0, 4))
        self.assertEqual(duration_estimate._voiced_units("付了$100元。"), (6, 0))

        raw = (
            "# EP001 Deals\n\n"
            "## EP001-SC001 内 · 办公室 · 夜\n\n"
            "Agent K：Pay $100000 now.\n"
        ).encode("utf-8")
        parsed_blocks, review = duration_estimate.parse_script_blocks(raw)
        word_only_project = {
            "format": {
                "pacing": {
                    "spoken_words_per_second": 3.0,
                    "seconds_per_action_paragraph": 2.0,
                }
            }
        }
        english_report = duration_estimate.estimate(
            raw, parsed_blocks, word_only_project, review
        )
        self.assertNotIn("untimed_speech", english_report)
        self.assertEqual(english_report["counts"]["voiced_characters"], 0)
        self.assertEqual(english_report["counts"]["voiced_words"], 3)
        self.assertEqual(english_report["seconds"], 1.0)

        for bad_target in (True, False, 0, -5, math.nan, math.inf, -math.inf):
            with self.subTest(bad_target=bad_target):
                project_with_bad = {
                    "format": {
                        "target_seconds_per_episode": bad_target,
                        "pacing": {
                            "spoken_words_per_second": 3.0,
                            "seconds_per_action_paragraph": 2.0,
                        },
                    }
                }
                by_project = duration_estimate.estimate(
                    raw, parsed_blocks, project_with_bad, review
                )
                self.assertIsNone(by_project["target_seconds"])
                self.assertNotIn("delta_seconds", by_project)

                by_arg = duration_estimate.estimate(
                    raw,
                    parsed_blocks,
                    word_only_project,
                    review,
                    target_seconds=bad_target,  # type: ignore[arg-type]
                )
                self.assertIsNone(by_arg["target_seconds"])
                self.assertNotIn("delta_seconds", by_arg)

    def test_selftest_runs_cleanly_under_isolated_sys_path(self) -> None:
        selftest = SUITE / "skills/short-drama-write/scripts/selftest.py"
        cmd = (
            [sys.executable, "-B", "-P", str(selftest)]
            if sys.version_info >= (3, 11)
            else [
                sys.executable,
                "-B",
                "-c",
                (
                    "import pathlib, runpy, sys; "
                    "script_dir = str(pathlib.Path(sys.argv[1]).resolve().parent); "
                    "sys.path[:] = [p for p in sys.path if p not in ('', script_dir)]; "
                    "runpy.run_path(sys.argv[1], run_name='__main__')"
                ),
                str(selftest),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                cmd,
                cwd=directory,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class R4ParserAndDurationHardeningTests(unittest.TestCase):
    def test_cast_line_head_scope_emphasis_parenthetical_roles_and_placeholders(
        self,
    ) -> None:
        # Head-level cast line with colon inside emphasis, parenthetical role notes
        # containing inner separators, and trailing Chinese full stop.
        raw_head = (
            "# EP001 试音\n\n"
            "- **人物：**许棠（女主、歌手）、周薄森（副团长/教官）。\n\n"
            "## EP001-SC001 内 · 排练厅 · 夜\n\n"
            "许棠: 先把伴奏停掉。\n\n"
            "周薄森: 再来一遍。\n"
        ).encode("utf-8")
        parsed_blocks, review = duration_estimate.parse_script_blocks(raw_head)
        self.assertEqual(review["review_status"], "clean")
        self.assertEqual(
            [(b["kind"], b.get("speaker")) for b in parsed_blocks],
            [
                ("scene_heading", None),
                ("dialogue", "许棠"),
                ("dialogue", "周薄森"),
            ],
        )

        # Mid-scene ``人物：...`` after action/dialogue must NOT be treated as a
        # cast declaration header or suppressed from issues.
        raw_mid_scene = (
            "# EP001\n\n"
            "## EP001-SC001 内 · 档案室 · 夜\n\n"
            "她翻开旧登记册。\n\n"
            "人物：林岚、赵野\n\n"
            "林岚: 别动那页。\n"
        ).encode("utf-8")
        _, mid_review = duration_estimate.parse_script_blocks(raw_mid_scene)
        self.assertEqual(mid_review["review_status"], "review_required")
        self.assertGreater(mid_review["source_issue_count"], 0)

        # Placeholder cast line must not populate a bogus speaker or disable
        # automatic speaker discovery.
        for placeholder in ("【待定】", "待定", "暂无", "无", "TBD", "待补", "N/A"):
            with self.subTest(placeholder=placeholder):
                raw_placeholder = (
                    f"# EP001\n\n人物：{placeholder}\n\n"
                    "## EP001-SC001 内 · 走廊 · 日\n\n"
                    "许棠：快把门关上。\n"
                ).encode("utf-8")
                ph_blocks, ph_review = duration_estimate.parse_script_blocks(
                    raw_placeholder
                )
                self.assertEqual(ph_review["review_status"], "clean")
                report = duration_estimate.estimate(
                    raw_placeholder, ph_blocks, None, ph_review
                )
                self.assertEqual(report["counts"]["dialogue_lines"], 1)

    def test_rate_floor_float_overflow_nan_rejection_and_malformed_project_guard(
        self,
    ) -> None:
        raw = (
            "# EP001\n\n## EP001-SC001 内 · 房间 · 夜\n\n"
            "许棠：一二三四。\n\n"
            "她退后半步。\n"
        ).encode("utf-8")
        parsed_blocks, review = duration_estimate.parse_script_blocks(raw)

        # Sub-threshold, bool, non-finite rates are rejected; 0.0 action rate stays valid.
        zero_action_project = {
            "format": {
                "pacing": {
                    "spoken_characters_per_second": 4.0,
                    "seconds_per_action_paragraph": 0.0,
                }
            }
        }
        zero_action_report = duration_estimate.estimate(
            raw, parsed_blocks, zero_action_project, review
        )
        self.assertTrue(zero_action_report["rates"]["declared"])
        self.assertEqual(zero_action_report["seconds"], 1.0)

        for bad_rate in (True, False, 0, -1.0, 1e-4, 1e-308, math.nan, math.inf):
            with self.subTest(bad_rate=bad_rate):
                bad_project = {
                    "format": {
                        "pacing": {
                            "spoken_characters_per_second": bad_rate,
                            "seconds_per_action_paragraph": 2.0,
                        }
                    }
                }
                bad_report = duration_estimate.estimate(
                    raw, parsed_blocks, bad_project, review
                )
                self.assertFalse(bad_report["rates"]["declared"])
                self.assertIsNone(bad_report["seconds"])

        # Overflowing valid huge finite rate must degrade cleanly without Infinity/NaN.
        overflow_project = {
            "format": {
                "pacing": {
                    "spoken_characters_per_second": 4.0,
                    "seconds_per_action_paragraph": 1e308,
                }
            }
        }
        many_actions = (
            "# EP001\n\n## EP001-SC001 内 · 房间 · 夜\n\n"
            + "\n\n".join(f"动作第{i}拍。" for i in range(1, 12))
            + "\n"
        ).encode("utf-8")
        action_blocks, action_review = duration_estimate.parse_script_blocks(many_actions)
        overflow_report = duration_estimate.estimate(
            many_actions, action_blocks, overflow_project, action_review
        )
        self.assertIsNone(overflow_report["seconds"])
        encoded = json.dumps(overflow_report, allow_nan=False)
        self.assertNotIn("Infinity", encoded)
        self.assertNotIn("NaN", encoded)

        # Malformed nested structures in project dicts do not raise AttributeError.
        for malformed in (
            {"format": "9:16"},
            {"format": {"pacing": ["bad"]}},
            {"creator_authority": "none"},
            {"creator_authority": {"rhythm_profile": 123}},
        ):
            with self.subTest(malformed=malformed):
                safe = duration_estimate.estimate(
                    raw, parsed_blocks, malformed, review  # type: ignore[arg-type]
                )
                self.assertIsNone(safe["seconds"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script_path = root / "剧本.md"
            script_path.write_bytes(raw)
            bad_proj_path = root / "short-drama.json"
            for content in ("{not json", '["not-an-object"]'):
                bad_proj_path.write_text(content, encoding="utf-8")
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(DURATION_SCRIPT),
                        "--script",
                        str(script_path),
                        "--project",
                        str(bad_proj_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(proc.returncode, 0)

    def test_utf8_bom_crlf_fenced_blocks_and_html_comment_edge_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "剧本.md"
            output = root / "screenplay-index.jsonl"
            raw_text = (
                "\ufeff# EP001·雨夜 <!-- 集备注 -->\r\n\r\n"
                "## EP001-SC001 内 · 调度室 · 雨夜 <!-- 场备注 -->\r\n\r\n"
                "```markdown\r\n"
                "## EP001-SC999 外 · 假场次 · 日\r\n"
                "许棠：代码块里的示例台词不计入正片。\r\n"
                "```\r\n\r\n"
                "~~~\r\n"
                "另一段波浪线围栏。\r\n"
                "~~~\r\n\r\n"
                "许棠：你好。<!-- TODO -->\r\n"
            )
            raw_bytes = raw_text.encode("utf-8")
            source.write_bytes(raw_bytes)

            summary = screenplay_index.build_index(source, output, speakers={"许棠"})
            self.assertEqual(summary["review_status"], "clean")
            indexed = blocks(output)
            self.assertEqual(
                [b["kind"] for b in indexed],
                ["scene_heading", "code_fence", "code_fence", "dialogue"],
            )
            self.assertEqual(indexed[0]["scene_id"], "EP001-SC001")
            self.assertEqual(indexed[0]["time_weather"], "雨夜")
            self.assertFalse(indexed[1]["production"])
            self.assertFalse(indexed[2]["production"])
            for row in indexed:
                sliced = raw_bytes[row["byte_start"] : row["byte_end"]]
                self.assertTrue(sliced.decode("utf-8"))

            idx_rows = read_jsonl(output)
            est_blocks, est_review = duration_estimate.index_blocks(idx_rows, raw_bytes)
            report = duration_estimate.estimate(raw_bytes, est_blocks, None, est_review)
            self.assertEqual(report["counts"]["dialogue_lines"], 1)
            self.assertEqual(report["counts"]["dialogue_characters"], 3)
            self.assertEqual(report["counts"]["voiced_characters"], 2)
            self.assertEqual(report["counts"]["voiced_words"], 0)
            self.assertEqual(report["counts"]["action_paragraphs"], 0)

            # Degenerate HTML comment ``<!-->`` without a real closing ``-->`` is malformed.
            degen = root / "degen.md"
            degen_out = root / "degen-index.jsonl"
            degen.write_text(
                "# EP001\n\n## EP001-SC001 内 · 走廊 · 夜\n\n<!-->\n",
                encoding="utf-8",
            )
            degen_summary = screenplay_index.build_index(degen, degen_out)
            self.assertEqual(degen_summary["review_status"], "review_required")
            degen_codes = {
                r["issue_code"]
                for r in read_jsonl(degen_out)
                if r["record_type"] == "source_issue"
            }
            self.assertIn("malformed_comment", degen_codes)

            # Live dialogue sandwiched between two inline comments on one line must
            # NEVER be silently swallowed as a clean comment.
            sandwiched = root / "sandwiched.md"
            sandwiched_out = root / "sandwiched-index.jsonl"
            sandwiched.write_text(
                "# EP001\n\n## EP001-SC001 内 · 走廊 · 夜\n\n"
                "<!-- c1 --> 许棠：快走！ <!-- c2 -->\n",
                encoding="utf-8",
            )
            sw_summary = screenplay_index.build_index(
                sandwiched, sandwiched_out, speakers={"许棠"}
            )
            self.assertEqual(sw_summary["review_status"], "review_required")
            sw_codes = {
                r["issue_code"]
                for r in read_jsonl(sandwiched_out)
                if r["record_type"] == "source_issue"
            }
            self.assertIn("mixed_comment_content", sw_codes)

    def test_cross_parser_ascii_colon_clock_voice_tag_fullwidth_space_and_headings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bilingual.md"
            output = root / "bilingual-index.jsonl"
            raw = (
                "# EP001——跨境来电\n\n"
                "人物：\u3000许棠\u3000\n\n"
                "## EP001-SC001 内 · 值班室 · 夜\n\n"
                "[VO] Elena: Stay on the line.\n\n"
                "[OS] 江晨\u3000（低声）:\u3000门锁了。\n\n"
                "许棠\u3000（抬头）：\u3000谁在外面？\n\n"
                "Agent K: Hold your fire.\n\n"
                "Agent K: Move now.\n\n"
                "https://example.com/status\n"
            ).encode("utf-8")
            source.write_bytes(raw)

            # In screenplay_index: Agent K is known when passed in speakers; unknown
            # ASCII-colon speaker still triggers invalid_dialogue_syntax.
            unknown_out = root / "unknown-index.jsonl"
            unknown_summary = screenplay_index.build_index(source, unknown_out)
            self.assertEqual(unknown_summary["review_status"], "review_required")
            unknown_codes = {
                r["issue_code"]
                for r in read_jsonl(unknown_out)
                if r["record_type"] == "source_issue"
            }
            self.assertIn("invalid_dialogue_syntax", unknown_codes)

            known_summary = screenplay_index.build_index(
                source, output, speakers={"许棠", "Agent K"}
            )
            self.assertEqual(known_summary["review_status"], "clean")

            # Auto-discovery without 人物： discovers >=2 ASCII-colon speaker while
            # ignoring URL schemes and clock prefixes.
            auto_raw = (
                "# EP001·夜巡\n\n"
                "## EP001-SC001 外 · 码头 · 夜\n\n"
                "Elena: Check the gate.\n\n"
                "Elena: All clear.\n\n"
                "12:00 sharp at the pier.\n\n"
                "https://example.com/gate\n\n"
                "https://example.com/pier\n"
            ).encode("utf-8")
            auto_blocks, auto_review = duration_estimate.parse_script_blocks(auto_raw)
            self.assertEqual(auto_review["review_status"], "clean")
            auto_report = duration_estimate.estimate(
                auto_raw, auto_blocks, None, auto_review
            )
            self.assertEqual(auto_report["counts"]["dialogue_lines"], 2)
            self.assertEqual(auto_report["counts"]["action_paragraphs"], 3)

            # ``[VO] 12：00，...`` clock prefix is rejected as malformed voice tag in both parsers.
            clock_vo = (
                "# EP001\n\n## EP001-SC001 内 · 房间 · 夜\n\n"
                "[VO] 12：00，走廊灯熄灭。\n"
            ).encode("utf-8")
            _, clock_review = duration_estimate.parse_script_blocks(clock_vo)
            self.assertEqual(clock_review["review_status"], "review_required")
            self.assertIn("invalid_voice_tag_syntax", clock_review["issue_codes"])

    def test_numeric_currency_tokens_cf_stripping_and_index_mode_speaker_flags(
        self,
    ) -> None:
        self.assertEqual(duration_estimate._voiced_units("$100!"), (0, 1))
        self.assertEqual(duration_estimate._voiced_units("$1,000.50!"), (0, 1))
        self.assertEqual(duration_estimate._voiced_units("24/7"), (0, 2))
        self.assertEqual(
            duration_estimate._voiced_units("Hello\u200b world.\ufeff"), (0, 2)
        )

        raw = (
            "# EP001\n\n## EP001-SC001 内 · 交易室 · 夜\n\n"
            "Alex: $100!\n\n"
            "Alex: 24/7\u200b!\n"
        ).encode("utf-8")
        word_project = {
            "format": {
                "pacing": {
                    "spoken_words_per_second": 3.0,
                    "seconds_per_action_paragraph": 2.0,
                }
            }
        }
        parsed_blocks, review = duration_estimate.parse_script_blocks(raw)
        self.assertEqual(review["review_status"], "clean")
        report = duration_estimate.estimate(raw, parsed_blocks, word_project, review)
        self.assertNotIn("untimed_speech", report)
        self.assertEqual(report["counts"]["voiced_characters"], 0)
        self.assertEqual(report["counts"]["voiced_words"], 3)
        self.assertEqual(report["seconds"], 1.0)
        self.assertEqual(report["speech_seconds"], 1.0)

        # --extra-speaker and --speaker work in --index mode via CLI.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script_path = root / "剧本.md"
            index_path = root / "screenplay-index.jsonl"
            script_path.write_text(
                "# EP001\n\n## EP001-SC001 内 · 走廊 · 夜\n\n"
                "许棠：先别开门。\n\n"
                "Guest: Wait outside.\n",
                encoding="utf-8",
            )
            screenplay_index.build_index(
                script_path, index_path, speakers={"许棠"}
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(DURATION_SCRIPT),
                    str(script_path),
                    "--index",
                    str(index_path),
                    "--extra-speaker",
                    "Guest",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            cli_report = json.loads(proc.stdout)
            self.assertNotIn("incomplete", cli_report)
            self.assertEqual(cli_report["counts"]["dialogue_lines"], 2)

    def test_previous_index_verifies_byte_length_and_preserves_previous_artifact_ref(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prev_source = root / "old-draft.md"
            prev_index = root / "old-index.jsonl"
            curr_source = root / "剧本.md"
            curr_index = root / "screenplay-index.jsonl"

            prev_source.write_text(
                "# EP001\n\n## EP001-SC001 内 · 客厅 · 夜\n\n她推开门。\n",
                encoding="utf-8",
            )
            screenplay_index.build_index(
                prev_source,
                prev_index,
                source_ref="输入/old-draft.md",
            )
            curr_source.write_text(
                "# EP001\n\n## EP001-SC001 内 · 客厅 · 夜\n\n她推开门。\n\n她把灯打开。\n",
                encoding="utf-8",
            )
            screenplay_index.build_index(
                curr_source,
                curr_index,
                previous_index_path=prev_index,
                previous_source_path=prev_source,
                source_ref="剧集/EP001/剧本.md",
            )
            meta = read_jsonl(curr_index)[0]
            self.assertEqual(
                meta["sources"]["screenplay"]["artifact"], "剧集/EP001/剧本.md"
            )
            self.assertEqual(
                meta["previous_source_ref"], {"src": "previous-screenplay"}
            )
            self.assertEqual(
                meta["sources"]["previous-screenplay"]["artifact"],
                "输入/old-draft.md",
            )

            # Tampering previous index's source_byte_length must be rejected.
            tampered_rows = read_jsonl(prev_index)
            tampered_rows[0]["source_byte_length"] = 99999
            tampered_index = root / "tampered-prev.jsonl"
            tampered_index.write_text(
                "\n".join(json.dumps(r) for r in tampered_rows) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "source_byte_length"):
                screenplay_index.build_index(
                    curr_source,
                    root / "out2.jsonl",
                    previous_index_path=tampered_index,
                    previous_source_path=prev_source,
                    source_ref="剧集/EP001/剧本.md",
                )


if __name__ == "__main__":
    unittest.main()
