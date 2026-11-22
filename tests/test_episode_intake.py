from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama-develop/scripts/episode_intake.py"
SPEC = importlib.util.spec_from_file_location("episode_intake", SCRIPT)
assert SPEC and SPEC.loader
episode_intake = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(episode_intake)

def serial(count: int, newline: bytes = b"\n", body_lines: int = 2) -> bytes:
    return newline.join(
        (
            f"第{number}集\n"
            + "\n".join(
                f"本集正文 {number}-{line}: 人物在场景中做出选择并承担后果。"
                for line in range(1, body_lines + 1)
            )
        )
        .encode("utf-8")
        .replace(b"\n", newline)
        for number in range(1, count + 1)
    ) + newline


def run_cli(*args: str | Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *(str(arg) for arg in args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


class EpisodeIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "用户 输入 完整剧本.txt"
        self.index_path = self.root / "分集 index.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def build(self, data: bytes | None = None) -> dict:
        self.source.write_bytes(data if data is not None else serial(54))
        document = episode_intake.build_index(self.source)
        episode_intake.write_index(self.index_path, document)
        return document

    def test_indexes_54_episodes_without_embedding_body(self) -> None:
        document = self.build(serial(54, body_lines=44))
        self.assertEqual(document["episode_count"], 54)
        self.assertEqual(document["problems"], [])
        self.assertEqual(document["source_byte_length"], len(self.source.read_bytes()))
        self.assertGreater(document["source_byte_length"], 80_000)
        self.assertEqual([e["episode_id"] for e in document["episodes"]], [f"EP{i:03d}" for i in range(1, 55)])
        encoded = json.dumps(document, ensure_ascii=False)
        self.assertNotIn("本集正文", encoded)
        for row in document["episodes"]:
            self.assertIn("byte_start", row)
            self.assertIn("byte_end", row)
            self.assertEqual(row["byte_length"], row["byte_end"] - row["byte_start"])
        self.assertEqual(document["source_ref"], self.source.name)

    def test_chinese_numbers_and_markdown_ep_headings(self) -> None:
        document = self.build("第一集 起点\n甲\n第二集：转折\n乙\n# EP 3 收束\n丙\n".encode())
        self.assertEqual([e["episode_id"] for e in document["episodes"]], ["EP001", "EP002", "EP003"])
        self.assertEqual(document["problems"], [])

    def test_markdown_prefixed_colon_and_positional_chinese_headings_ignore_scene_headings(
        self,
    ) -> None:
        raw = (
            "# 第1集 开端\n"
            "## EP001-SC001 内 · 客厅 · 夜\n"
            "甲推开门。\n"
            "## 第二集：承接\n"
            "## EP002-SC001\n"
            "乙转身。\n"
            "# EP003：中段\n"
            "丙落座。\n"
            "## EP 4 转向\n"
            "丁开口。\n"
            "### 第二零集：分卷跳集\n"
            "戊出招。\n"
            "第一零一集 破局\n"
            "己反击。\n"
            "## 第一〇八集：收束\n"
            "庚收场。\n"
        ).encode("utf-8")
        document = self.build(raw)
        self.assertEqual(document["problems"], [])
        self.assertEqual(
            [row["episode_id"] for row in document["episodes"]],
            ["EP001", "EP002", "EP003", "EP004", "EP020", "EP101", "EP108"],
        )
        first_slice = episode_intake.slice_episode(self.index_path, self.source, "EP001")
        self.assertIn("## EP001-SC001 内 · 客厅 · 夜".encode("utf-8"), first_slice)
        second_slice = episode_intake.slice_episode(self.index_path, self.source, "EP002")
        self.assertIn(b"## EP002-SC001\n", second_slice)

    def test_english_episode_headings_index_verify_and_slice_cleanly(self) -> None:
        raw = (
            "Episode 1\n"
            "Mara steps into the hallway.\n"
            "Episode 02: The Locked Drawer\n"
            "She checks the ledger.\n"
            "EPISODE 3\n"
            "The alarm rings.\n"
            "# Episode 004 - Aftermath\n"
            "Episodes 1-3 recap line is prose, not a heading.\n"
            "Episode 1-Episode 2 range is not a heading.\n"
            "EP001.mp4 clip filename is not a heading.\n"
            "## EPISODE 5. The Deal\n"
            "They sign the contract.\n"
            "Episode 6:\n"
            "Fade out.\n"
        ).encode("utf-8")
        document = self.build(raw)
        self.assertEqual(document["problems"], [])
        self.assertEqual(
            [row["episode_id"] for row in document["episodes"]],
            ["EP001", "EP002", "EP003", "EP004", "EP005", "EP006"],
        )
        self.assertTrue(episode_intake.verify_index(self.index_path, self.source)["verified"])
        ep2 = episode_intake.slice_episode(self.index_path, self.source, "EP002").decode("utf-8")
        self.assertTrue(ep2.startswith("Episode 02: The Locked Drawer\n"))
        ep4 = episode_intake.slice_episode(self.index_path, self.source, "EP004").decode("utf-8")
        self.assertIn("Episodes 1-3 recap line", ep4)
        self.assertIn("Episode 1-Episode 2 range", ep4)
        self.assertIn("EP001.mp4", ep4)
        self.assertIsNone(episode_intake._heading_number_from_text("Episode 0: Prologue"))

    def test_manual_episode_ids_use_the_project_canonical_spelling(self) -> None:
        self.source.write_text("第一幕\n甲\n", encoding="utf-8")
        for episode_id in ("EP000", "EP0001"):
            with self.subTest(episode_id=episode_id):
                with self.assertRaisesRegex(ValueError, "invalid episode_id"):
                    episode_intake.make_manual_index(
                        self.source,
                        [(episode_id, 0, len(self.source.read_bytes()))],
                    )

    def test_utf8_bom_is_preserved_inside_the_first_exact_slice(self) -> None:
        raw = b"\xef\xbb\xbf" + serial(2, b"\r\n")
        document = self.build(raw)
        self.assertEqual(document["problems"], [])
        first = episode_intake.slice_episode(self.index_path, self.source, "EP001")
        self.assertTrue(first.startswith(b"\xef\xbb\xbf"))

    def test_crlf_offsets_are_exact_and_slice_is_isolated(self) -> None:
        document = self.build(serial(3, b"\r\n"))
        row = document["episodes"][1]
        raw = self.source.read_bytes()
        self.assertEqual(raw[row["byte_start"]:row["byte_end"]], episode_intake.slice_episode(self.index_path, self.source, "EP002"))
        sliced = episode_intake.slice_episode(self.index_path, self.source, "EP002")
        self.assertIn("本集正文 2".encode(), sliced)
        self.assertNotIn("本集正文 1".encode(), sliced)
        self.assertNotIn("本集正文 3".encode(), sliced)
        self.assertIn(b"\r\n", sliced)

    def test_verify_rejects_changed_source_and_slice_does_not_overwrite(self) -> None:
        self.build(serial(3))
        destination = self.root / "EP002.txt"
        destination.write_bytes(b"keep")
        self.source.write_bytes(b"changed\n" + self.source.read_bytes())
        result = episode_intake.verify_index(self.index_path, self.source)
        self.assertFalse(result["verified"])
        with self.assertRaises(ValueError):
            episode_intake.slice_episode(self.index_path, self.source, "EP002", destination)
        self.assertEqual(destination.read_bytes(), b"keep")

    def test_out_of_order_duplicates_and_empty_episodes_are_detected(self) -> None:
        for data, fragment in (
            ("第三集\n丙\n第二集\n乙\n".encode(), "out of source order"),
            ("第一集\n甲\n第一集\n乙\n".encode(), "duplicate"),
            ("第一集\n第二集\n乙\n".encode(), "empty"),
        ):
            with self.subTest(fragment=fragment):
                self.source.write_bytes(data)
                result = episode_intake.build_index(self.source)
                self.assertTrue(any(fragment in p for p in result["problems"]), result["problems"])

    def test_non_one_start_and_gapped_episodes_index_and_verify_cleanly(self) -> None:
        raw = "第5集 中段切入\n戊\n第6集 承接\n己\n第10集 高潮试写\n癸\n".encode()
        document = self.build(raw)
        self.assertEqual(document["problems"], [])
        self.assertEqual(
            [row["episode_id"] for row in document["episodes"]],
            ["EP005", "EP006", "EP010"],
        )
        self.assertTrue(episode_intake.verify_index(self.index_path, self.source)["verified"])
        self.assertEqual(
            episode_intake.slice_episode(self.index_path, self.source, "EP010"),
            "第10集 高潮试写\n癸\n".encode(),
        )

    def test_agent_authored_index_with_nonstandard_boundaries_verifies_and_slices(self) -> None:
        raw = "开篇\n【上集】\n甲\n【下集】\n乙\n".encode()
        self.source.write_bytes(raw)
        first = raw.index("【上集】".encode())
        second = raw.index("【下集】".encode())
        document = episode_intake.make_manual_index(
            self.source,
            [("EP001", first, second), ("EP002", second, len(raw))],
        )
        episode_intake.write_index(self.index_path, document)
        self.assertTrue(episode_intake.verify_index(self.index_path, self.source)["verified"])
        self.assertEqual(episode_intake.slice_episode(self.index_path, self.source, "EP002"), raw[second:])

    def test_agent_can_supply_line_boundaries_without_calculating_bytes(self) -> None:
        raw = "前言\r\n【上集】\r\n甲\r\n【下集】\r\n乙\r\n".encode()
        self.source.write_bytes(raw)
        boundaries = self.root / "agent boundaries.jsonl"
        boundaries.write_text(
            '{"episode_id":"EP001","line_start":2}\n'
            '{"episode_id":"EP002","line_start":4,"line_end":5}\n',
            encoding="utf-8",
        )
        document = episode_intake.build_manual_index(
            self.source,
            boundaries,
            source_ref="素材/完整 剧本.txt",
        )
        episode_intake.write_index(self.index_path, document)
        self.assertEqual(document["source_ref"], "素材/完整 剧本.txt")
        self.assertEqual(document["episodes"][0]["line_end"], 3)
        self.assertEqual(document["episodes"][0]["byte_start"], len("前言\r\n".encode()))
        self.assertEqual(document["unmapped_spans"][0]["byte_start"], 0)
        self.assertEqual(
            document["unmapped_spans"][0]["byte_end"],
            len("前言\r\n".encode()),
        )
        self.assertTrue(episode_intake.verify_index(self.index_path, self.source)["verified"])


class ProgressAndMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "full.txt"
        self.source.write_bytes(serial(8))
        self.index = self.root / "index.json"
        episode_intake.write_index(self.index, episode_intake.build_index(self.source))
        self.map = self.root / "episode-map.jsonl"
        self.next_map = self.root / "episode-map.next.jsonl"
        self.checkpoint = self.root / "checkpoint.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def batch(self, name: str, records: list[dict]) -> Path:
        path = self.root / name
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        return path

    def test_progress_handles_noncontiguous_completion_and_is_byte_idempotent(self) -> None:
        self.map.write_text('{"episode_id":"EP001"}\n{"episode_id":"EP004"}\n', encoding="utf-8")
        first = episode_intake.progress(self.index, self.source, self.map, self.checkpoint, batch_size=3)
        before = self.checkpoint.read_bytes()
        second = episode_intake.progress(self.index, self.source, self.map, self.checkpoint, batch_size=3)
        self.assertEqual(before, self.checkpoint.read_bytes())
        self.assertEqual(first, second)
        self.assertEqual(first["completed"], ["EP001", "EP004"])
        self.assertEqual(first["next_batch"], ["EP002", "EP003", "EP005"])
        self.assertEqual(first["pending"], ["EP002", "EP003", "EP005", "EP006", "EP007", "EP008"])

    def test_merge_is_atomic_sorted_and_replay_is_noop(self) -> None:
        initial = self.batch("initial.jsonl", [{"episode_id": "EP004", "beat": "丁"}])
        episode_intake.merge_batch(
            self.index,
            self.source,
            initial,
            self.map,
            self.next_map,
            self.checkpoint,
            batch_size=3,
        )
        self.map.write_bytes(self.next_map.read_bytes())
        batch = self.batch("batch.jsonl", [{"episode_id": "EP002", "beat": "乙"}, {"episode_id": "EP001", "beat": "甲"}])
        episode_intake.merge_batch(
            self.index,
            self.source,
            batch,
            self.map,
            self.next_map,
            self.checkpoint,
            batch_size=3,
        )
        map_before = self.next_map.read_bytes()
        checkpoint_before = self.checkpoint.read_bytes()
        replay = self.root / "episode-map.replay.jsonl"
        result = episode_intake.merge_batch(
            self.index,
            self.source,
            batch,
            self.next_map,
            replay,
            self.checkpoint,
            batch_size=3,
        )
        self.assertEqual(map_before, replay.read_bytes())
        self.assertEqual(checkpoint_before, self.checkpoint.read_bytes())
        self.assertEqual(result["added"], [])
        self.assertEqual(
            [
                json.loads(line)["episode_id"]
                for line in replay.read_text(encoding="utf-8").splitlines()
            ],
            ["EP001", "EP002", "EP004"],
        )

    def test_merge_updates_existing_episode_records_in_place(self) -> None:
        initial = self.batch(
            "one.jsonl",
            [{"episode_id": "EP003", "beat": "丙"}, {"episode_id": "EP001", "beat": "old"}],
        )
        episode_intake.merge_batch(
            self.index,
            self.source,
            initial,
            self.map,
            self.next_map,
            self.checkpoint,
            batch_size=2,
        )
        revision = self.batch("revision.jsonl", [{"episode_id": "EP001", "beat": "new"}])
        result = episode_intake.merge_batch(
            self.index,
            self.source,
            revision,
            self.next_map,
            self.map,
            self.checkpoint,
            batch_size=2,
        )
        self.assertEqual(result["added"], [])
        self.assertEqual(result["updated"], ["EP001"])
        self.assertEqual(result["progress"]["completed"], ["EP001", "EP003"])
        merged = [
            json.loads(line)
            for line in self.map.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            merged,
            [{"episode_id": "EP001", "beat": "new"}, {"episode_id": "EP003", "beat": "丙"}],
        )

    def test_merge_oversized_or_unknown_episode_batch_does_not_overwrite(self) -> None:
        initial = self.batch("one.jsonl", [{"episode_id": "EP001", "beat": "old"}])
        episode_intake.merge_batch(
            self.index,
            self.source,
            initial,
            self.map,
            self.next_map,
            self.checkpoint,
            batch_size=2,
        )
        before_map = self.next_map.read_bytes()
        before_checkpoint = self.checkpoint.read_bytes()
        unknown = self.batch("unknown.jsonl", [{"episode_id": "EP999", "beat": "outside"}])
        with self.assertRaisesRegex(ValueError, "outside the index"):
            episode_intake.merge_batch(
                self.index,
                self.source,
                unknown,
                self.next_map,
                self.map,
                self.checkpoint,
                batch_size=2,
            )
        self.assertFalse(self.map.exists())
        self.assertEqual(self.next_map.read_bytes(), before_map)
        self.assertEqual(self.checkpoint.read_bytes(), before_checkpoint)
        too_many = self.batch("large.jsonl", [{"episode_id": f"EP{i:03d}"} for i in range(2, 8)])
        with self.assertRaises(ValueError):
            episode_intake.merge_batch(
                self.index,
                self.source,
                too_many,
                self.next_map,
                self.map,
                self.checkpoint,
                batch_size=5,
            )
        self.assertFalse(self.map.exists())
        self.assertEqual(self.next_map.read_bytes(), before_map)

    def test_multi_volume_progress_and_merge_preserve_other_volumes_sorted_numerically(
        self,
    ) -> None:
        vol_source = self.root / "vol2.txt"
        vol_index = self.root / "vol2-index.json"
        vol_source.write_text(
            "# 第5集 分卷起\n戊\n# 第6集 分卷承\n己\n# 第8集 分卷合\n辛\n",
            encoding="utf-8",
        )
        episode_intake.write_index(vol_index, episode_intake.build_index(vol_source))
        self.map.write_text(
            '{"episode_id":"EP1000","beat":"终章"}\n'
            '{"episode_id":"EP002","beat":"卷一乙"}\n'
            '{"episode_id":"EP999","beat":"前夜"}\n'
            '{"episode_id":"EP006","beat":"卷二旧稿"}\n'
            '{"episode_id":"EP001","beat":"卷一甲"}\n',
            encoding="utf-8",
        )
        status = episode_intake.progress(
            vol_index, vol_source, self.map, self.checkpoint, batch_size=2
        )
        self.assertEqual(status["completed"], ["EP006"])
        self.assertEqual(status["pending"], ["EP005", "EP008"])
        self.assertEqual(status["next_batch"], ["EP005", "EP008"])

        outside_batch = self.batch("outside_vol.jsonl", [{"episode_id": "EP001", "beat": "越界"}])
        with self.assertRaisesRegex(ValueError, "outside the index"):
            episode_intake.merge_batch(
                vol_index,
                vol_source,
                outside_batch,
                self.map,
                self.next_map,
                self.checkpoint,
                batch_size=2,
            )

        vol_batch = self.batch(
            "vol2_batch.jsonl",
            [
                {"episode_id": "EP008", "beat": "卷二辛"},
                {"episode_id": "EP005", "beat": "卷二戊"},
            ],
        )
        merged = episode_intake.merge_batch(
            vol_index,
            vol_source,
            vol_batch,
            self.map,
            self.next_map,
            self.checkpoint,
            batch_size=2,
        )
        self.assertEqual(merged["added"], ["EP005", "EP008"])
        self.assertTrue(merged["progress"]["complete"])
        merged_rows = [
            json.loads(line)
            for line in self.next_map.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            [row["episode_id"] for row in merged_rows],
            ["EP001", "EP002", "EP005", "EP006", "EP008", "EP999", "EP1000"],
        )

        bad_map = self.root / "bad-map.jsonl"
        for content, pattern in (
            ('{"episode_id":"EP01"}\n', "invalid episode_id"),
            ('{"episode_id":"EP001"}\n{"episode_id":"EP001"}\n', "duplicate episode_id"),
        ):
            with self.subTest(pattern=pattern):
                bad_map.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, pattern):
                    episode_intake.progress(vol_index, vol_source, bad_map, batch_size=2)


class CliTests(unittest.TestCase):
    def test_unicode_space_paths_end_to_end_and_error_preserves_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "完整 剧本 中文.txt"
            index = root / "索引 文件.json"
            output = root / "分集 二.txt"
            source.write_bytes(serial(3, b"\r\n"))
            result = run_cli("index", source, "--out", index)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = run_cli("slice", index, source, "EP002", "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("本集正文 2".encode(), output.read_bytes())
            gapped = root / "gapped.txt"
            gapped_index = root / "gapped-index.json"
            gapped.write_text("第五集\n戊\n第八集\n辛\n", encoding="utf-8")
            result = run_cli("index", gapped, "--out", gapped_index)
            self.assertEqual(result.returncode, 0, result.stderr)
            bad = root / "bad.txt"
            bad.write_text("第三集\n丙\n第一集\n甲\n", encoding="utf-8")
            result = run_cli("index", bad, "--out", index)
            self.assertNotEqual(result.returncode, 0)
            candidate = json.loads(index.read_text(encoding="utf-8"))
            self.assertTrue(any("out of source order" in problem for problem in candidate["problems"]))

    def test_manual_index_cli_accepts_agent_line_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "非标准 剧本.txt"
            source.write_text("说明\n第一幕\n甲\n第二幕\n乙\n", encoding="utf-8")
            boundaries = root / "边界.jsonl"
            boundaries.write_text(
                '{"episode_id":"EP001","line_start":2}\n'
                '{"episode_id":"EP002","line_start":4}\n',
                encoding="utf-8",
            )
            index = root / "手工 index.json"
            result = run_cli(
                "manual-index",
                source,
                boundaries,
                "--out",
                index,
                "--source-ref",
                "输入/非标准 剧本.txt",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(index.read_text(encoding="utf-8"))
            self.assertEqual(document["source_ref"], "输入/非标准 剧本.txt")
            self.assertEqual(document["episodes"][1]["line_start"], 4)

    def test_unreadable_source_does_not_replace_existing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bad.txt"
            source.write_bytes(b"\xff\xfe")
            index = root / "index.json"
            index.write_bytes(b"keep")
            result = run_cli("index", source, "--out", index)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(index.read_bytes(), b"keep")

    def test_cli_requires_explicit_context_and_output_bounds(self) -> None:
        commands = (
            ["progress", "index.json", "source.txt", "map.jsonl"],
            [
                "merge",
                "index.json",
                "source.txt",
                "batch.jsonl",
                "map.jsonl",
                "--out",
                "next.jsonl",
            ],
            ["slice", "index.json", "source.txt", "EP001"],
        )
        for command in commands:
            with self.subTest(command=command[0]):
                result = run_cli(*command)
                self.assertNotEqual(result.returncode, 0)
                required = "--out" if command[0] == "slice" else "--batch-size"
                self.assertIn(required, result.stderr)


class WorkflowContractTests(unittest.TestCase):
    def test_cli_workflow_emits_only_mechanical_fields_and_selftest_runs_isolated(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "episodes.txt"
            index = root / "intake-index.json"
            sliced = root / "ep001.txt"
            batch = root / "batch.jsonl"
            episode_map = root / "episode-map.jsonl"
            merged_map = root / "episode-map.merged.jsonl"
            checkpoint = root / "checkpoint.json"
            source.write_bytes(serial(2))
            batch.write_text('{"episode_id":"EP001","title":"起"}\n', encoding="utf-8")

            self.assertEqual(run_cli("index", source, "--out", index).returncode, 0)
            self.assertEqual(run_cli("verify", index, source).returncode, 0)
            self.assertEqual(
                run_cli("slice", index, source, "EP001", "--out", sliced).returncode, 0
            )
            self.assertEqual(
                run_cli(
                    "progress",
                    index,
                    source,
                    episode_map,
                    "--checkpoint",
                    checkpoint,
                    "--batch-size",
                    "1",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_cli(
                    "merge",
                    index,
                    source,
                    batch,
                    episode_map,
                    "--out",
                    merged_map,
                    "--checkpoint",
                    checkpoint,
                    "--batch-size",
                    "1",
                ).returncode,
                0,
            )

            index_doc = json.loads(index.read_text(encoding="utf-8"))
            for creative_field in (
                "hook",
                "turn",
                "local_dramatic_result",
                "outgoing_pressure",
            ):
                self.assertNotIn(creative_field, index_doc)
                for row in index_doc["episodes"]:
                    self.assertNotIn(creative_field, row)

            episode_script = SUITE / "skills/short-drama-develop/scripts/episode_intake.py"
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            smoke_source = root / "isolated-episodes.md"
            smoke_index = root / "isolated-index.json"
            smoke_slice = root / "isolated-ep002.md"
            smoke_source.write_text(
                "第1集 开端\n行动一。\n第2集 反转\n行动二。\n", encoding="utf-8"
            )

            def run_isolated(*cli_args: str) -> subprocess.CompletedProcess[str]:
                cmd = (
                    [sys.executable, "-B", "-P", str(episode_script), *cli_args]
                    if sys.version_info >= (3, 11)
                    else [
                        sys.executable,
                        "-B",
                        "-c",
                        (
                            "import pathlib, runpy, sys; "
                            "script = sys.argv[1]; "
                            "script_dir = str(pathlib.Path(script).resolve().parent); "
                            "sys.path[:] = [p for p in sys.path if p not in ('', script_dir)]; "
                            "sys.argv = [script, *sys.argv[2:]]; "
                            "runpy.run_path(script, run_name='__main__')"
                        ),
                        str(episode_script),
                        *cli_args,
                    ]
                )
                return subprocess.run(
                    cmd,
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            self.assertEqual(
                run_isolated("index", str(smoke_source), "--out", str(smoke_index)).returncode,
                0,
            )
            self.assertEqual(
                run_isolated("verify", str(smoke_index), str(smoke_source)).returncode,
                0,
            )
            self.assertEqual(
                run_isolated(
                    "slice", str(smoke_index), str(smoke_source), "EP002", "--out", str(smoke_slice)
                ).returncode,
                0,
            )
            self.assertTrue(smoke_slice.read_bytes().startswith("第2集".encode("utf-8")))
            smoke_source.write_text(
                smoke_source.read_text(encoding="utf-8") + "变更。\n", encoding="utf-8"
            )
            self.assertNotEqual(
                run_isolated("verify", str(smoke_index), str(smoke_source)).returncode,
                0,
            )


class UnmappedSpanScopeTests(unittest.TestCase):
    """What `unmapped_spans` can and cannot report, asserted rather than assumed.

    The reference document promised it would mark inter-episode notes and end
    matter. It cannot: episode spans run from one heading to the next, so no gap
    exists between them for such material to fall into. The promise is now
    written to match, and this test holds both halves in place -- the half that
    works, and the boundary that makes the other half impossible.
    """

    SOURCE = (
        "前言：这是一份说明，不属于任何一集。\n\n"
        "第1集 开场\n\n正文一。\n\n"
        "—— 集间说明：以下为第二部分。 ——\n\n"
        "第2集 反转\n\n正文二。\n\n"
        "尾注：全剧终。\n"
    )

    def index(self) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "episodes.md"
            source.write_text(self.SOURCE, encoding="utf-8")
            return episode_intake.build_index(source)

    def test_material_before_the_first_episode_is_reported(self) -> None:
        spans = self.index()["unmapped_spans"]
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["line_start"], 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "episodes.md"
            index_path = root / "index.json"
            source.write_text(self.SOURCE, encoding="utf-8")
            result = run_cli("index", source, "--out", index_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(any("unmapped" in w for w in summary.get("warnings", [])), summary)

    def test_episode_spans_leave_no_gap_for_anything_else_to_land_in(self) -> None:
        """The mechanical reason the other half of the promise was unkeepable."""

        episodes = self.index()["episodes"]
        self.assertEqual(len(episodes), 2)
        self.assertEqual(episodes[0]["byte_end"], episodes[1]["byte_start"])


class HardenedValidationTests(unittest.TestCase):
    def test_empty_trailing_colon_headings_index_and_slice_cleanly(self) -> None:
        raw = (
            "第1集：\n甲推门。\n"
            "第 2 集:\n乙回头。\n"
            "# EP003：\n丙落座。\n"
            "EP 4:   \n丁离场。\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "colon-headings.md"
            index = root / "index.json"
            source.write_bytes(raw)
            document = episode_intake.build_index(source)
            self.assertEqual(document["problems"], [])
            self.assertEqual(
                [row["episode_id"] for row in document["episodes"]],
                ["EP001", "EP002", "EP003", "EP004"],
            )
            episode_intake.write_index(index, document)
            self.assertTrue(episode_intake.verify_index(index, source)["verified"])
            self.assertEqual(
                episode_intake.slice_episode(index, source, "EP001"),
                "第1集：\n甲推门。\n".encode("utf-8"),
            )

    def test_chinese_to_int_parses_positional_and_strict_unit_numerals(self) -> None:
        valid_cases = {
            "12": 12,
            "一": 1,
            "十": 10,
            "十五": 15,
            "二十": 20,
            "二十三": 23,
            "二零": 20,
            "一零一": 101,
            "一〇八": 108,
            "两零八": 208,
            "一二": 12,
            "一百": 100,
            "一百零二": 102,
            "一百一十": 110,
            "一百二十三": 123,
            "一千零五": 1005,
            "一千零一十": 1010,
            "一千零十五": 1015,
            "一千二百零三": 1203,
        }
        for numeral, expected in valid_cases.items():
            with self.subTest(valid=numeral):
                self.assertEqual(episode_intake.chinese_to_int(numeral), expected)

        invalid_cases = (
            "",
            "一两三",
            "十十",
            "十百",
            "百千",
            "百十",
            "二十一十",
            "一二百",
            "二三十",
            "二十零",
            "一百零",
            "十零",
            "二十零三",
            "一百零二十",
            "一百零零二",
            "一百二",
            "一千二",
            "一千二十",
            "一千二百三",
            "零十",
            "零一百",
        )
        for numeral in invalid_cases:
            with self.subTest(invalid=numeral):
                self.assertIsNone(episode_intake.chinese_to_int(numeral))

    def test_verify_index_and_cli_reject_missing_non_string_and_dot_source_refs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "episodes.txt"
            index = root / "index.json"
            source.write_bytes(serial(2))
            base = episode_intake.build_index(source)

            missing_ref = dict(base)
            missing_ref.pop("source_ref")
            episode_intake.write_index(index, missing_ref)
            self.assertFalse(episode_intake.verify_index(index, source)["verified"])

            for bad_ref in (
                None,
                "",
                True,
                False,
                123,
                ".",
                "./",
                "./episodes.txt",
                "输入/./episodes.txt",
                "输入//episodes.txt",
                "输入/episodes.txt/",
                "../episodes.txt",
                "/episodes.txt",
            ):
                with self.subTest(source_ref=bad_ref):
                    tampered = dict(base, source_ref=bad_ref)
                    episode_intake.write_index(index, tampered)
                    verdict = episode_intake.verify_index(index, source)
                    self.assertFalse(verdict["verified"], verdict)
                    if isinstance(bad_ref, str):
                        cli = run_cli(
                            "index", source, "--out", index, "--source-ref", bad_ref
                        )
                        self.assertNotEqual(cli.returncode, 0)

    def test_boolean_values_cannot_masquerade_as_integer_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "one.txt"
            index = root / "index.json"
            # Preamble is 1 byte ('x' is invalid heading, 2 bytes with '\n') plus 1 episode
            # so episode_count == 1, source_number == 1, line_start == 1 when no preamble.
            source.write_text("第1集\n甲\n", encoding="utf-8")
            base = episode_intake.build_index(source)
            episode_intake.write_index(index, base)
            self.assertTrue(episode_intake.verify_index(index, source)["verified"])

            for top_field in ("episode_count", "source_byte_length"):
                with self.subTest(top_field=top_field):
                    tampered = json.loads(json.dumps(base))
                    tampered[top_field] = True
                    episode_intake.write_index(index, tampered)
                    self.assertFalse(
                        episode_intake.verify_index(index, source)["verified"]
                    )

            for row_field, bad_bool in (
                ("source_number", True),
                ("line_start", True),
                ("line_end", True),
                ("byte_start", False),
                ("byte_end", True),
                ("byte_length", True),
            ):
                with self.subTest(row_field=row_field):
                    tampered = json.loads(json.dumps(base))
                    tampered["episodes"][0][row_field] = bad_bool
                    episode_intake.write_index(index, tampered)
                    self.assertFalse(
                        episode_intake.verify_index(index, source)["verified"]
                    )
                    self.assertTrue(
                        episode_intake._structural_problems(
                            tampered["episodes"], source.read_bytes()
                        )
                    )

            # Unmapped span boolean fields must not compare equal to 0/1 ints.
            preamble_source = root / "preamble.txt"
            preamble_source.write_bytes(b"!\n" + "第1集\n甲\n".encode("utf-8"))
            with_unmapped = episode_intake.build_index(preamble_source)
            self.assertEqual(with_unmapped["unmapped_spans"][0]["line_start"], 1)
            self.assertEqual(with_unmapped["unmapped_spans"][0]["byte_start"], 0)
            for span_field, bad_bool in (("line_start", True), ("byte_start", False)):
                with self.subTest(unmapped_field=span_field):
                    tampered = json.loads(json.dumps(with_unmapped))
                    tampered["unmapped_spans"][0][span_field] = bad_bool
                    episode_intake.write_index(index, tampered)
                    self.assertFalse(
                        episode_intake.verify_index(index, preamble_source)["verified"]
                    )

            with self.assertRaises(ValueError):
                episode_intake.make_manual_index(
                    source, [("EP001", False, len(source.read_bytes()))]
                )
            episode_intake.write_index(index, base)
            with self.assertRaises(ValueError):
                episode_intake.progress(
                    index, source, root / "map.jsonl", batch_size=True
                )

    def test_manual_index_accepts_single_line_and_trailing_blank_episodes_while_rejecting_blank_spans(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "single-line-outline.txt"
            boundaries = root / "boundaries.jsonl"
            index = root / "manual-index.json"
            sliced = root / "ep001.txt"
            source.write_bytes(
                "EP01：许棠在后台拒签假合同。\n\nEP02：周薄森当场截住录音笔。\n".encode(
                    "utf-8"
                )
            )
            boundaries.write_text(
                '{"episode_id":"EP001","line_start":1,"line_end":2}\n'
                '{"episode_id":"EP002","line_start":3,"line_end":3}\n',
                encoding="utf-8",
            )
            cli = run_cli("manual-index", source, boundaries, "--out", index)
            self.assertEqual(cli.returncode, 0, cli.stderr)
            self.assertEqual(run_cli("verify", index, source).returncode, 0)
            self.assertEqual(
                run_cli("slice", index, source, "EP001", "--out", sliced).returncode, 0
            )
            self.assertEqual(
                sliced.read_bytes().decode("utf-8"),
                "EP01：许棠在后台拒签假合同。\n\n",
            )
            self.assertEqual(
                episode_intake.slice_episode(index, source, "EP002").decode("utf-8"),
                "EP02：周薄森当场截住录音笔。\n",
            )

            # A whitespace-only manual span is still flagged as empty.
            blank_source = root / "blank-manual.txt"
            blank_source.write_bytes("   \n\n正文第二集。\n".encode("utf-8"))
            blank_doc = episode_intake.make_manual_index(
                blank_source,
                [
                    ("EP001", 0, len(b"   \n\n")),
                    ("EP002", len(b"   \n\n"), len(blank_source.read_bytes())),
                ],
            )
            self.assertIn("empty episode: EP001", blank_doc["problems"])

    def test_build_index_skips_comments_and_code_fences_and_accepts_extended_separators(
        self,
    ) -> None:
        raw = (
            "<!--\n"
            "# EP099 注释里的废弃集标题\n"
            "第88集 注释里的中文集标题\n"
            "-->```markdown\n"
            "# EP077 代码块里的示例集标题\n"
            "第66集 代码块示例\n"
            "```\n"
            "<!--> # EP098 退化注释包裹的假标题 -->\n"
            "~~~text\n"
            "# EP055 波浪线代码块示例\n"
            "~~~\n"
            "<!--\n"
            "跨行前置备注\n"
            "--># EP001·夜班 <!-- 行尾备注 -->\n"
            "甲推门进来。\n"
            "# EP002—转折\n"
            "乙转身按住门把。\n"
            "# EP003——对峙\n"
            "丙亮出工牌。\n"
            "# EP004-尾声\n"
            "Episode 1-3: Arc summary\n"
            "EP01-03 recap\n"
            "Episode 1 - 3 overview\n"
            "丁把钥匙放在桌上。\n"
            "第5集·余波\n"
            "戊合上账本。\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fenced-and-commented.md"
            index = root / "index.json"
            source.write_bytes(raw)
            document = episode_intake.build_index(source)
            self.assertEqual(document["problems"], [])
            self.assertEqual(
                [row["episode_id"] for row in document["episodes"]],
                ["EP001", "EP002", "EP003", "EP004", "EP005"],
            )
            episode_intake.write_index(index, document)
            self.assertTrue(episode_intake.verify_index(index, source)["verified"])
            ep1 = episode_intake.slice_episode(index, source, "EP001").decode("utf-8")
            self.assertIn("# EP001·夜班", ep1.splitlines()[0])

    def test_manual_index_and_verify_reject_invalid_utf8_bytes_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid_source = root / "source.txt"
            boundaries = root / "boundaries.jsonl"
            index = root / "index.json"
            valid_source.write_text("第一幕\n甲出场。\n", encoding="utf-8")
            boundaries.write_text('{"episode_id":"EP001","line_start":1}\n', encoding="utf-8")
            doc = episode_intake.build_manual_index(valid_source, boundaries)
            episode_intake.write_index(index, doc)
            self.assertTrue(episode_intake.verify_index(index, valid_source)["verified"])

            # Replace source with invalid UTF-8 bytes of the exact same byte length.
            bad_bytes = b"\xff\xfe\n" + b"a" * (len(valid_source.read_bytes()) - 3)
            self.assertEqual(len(bad_bytes), len(valid_source.read_bytes()))
            valid_source.write_bytes(bad_bytes)

            verdict = episode_intake.verify_index(index, valid_source)
            self.assertFalse(verdict["verified"])
            self.assertTrue(verdict["problems"])

            cli_verify = run_cli("verify", index, valid_source)
            self.assertEqual(cli_verify.returncode, 1)
            self.assertFalse(json.loads(cli_verify.stderr)["verified"])

            out_manual = root / "bad-manual.json"
            cli_manual = run_cli("manual-index", valid_source, boundaries, "--out", out_manual)
            self.assertEqual(cli_manual.returncode, 1)
            self.assertIn("error", json.loads(cli_manual.stderr))
            self.assertFalse(out_manual.exists())

    def test_line_number_bisect_resolves_boundaries_and_rejects_mid_line_or_bool_offsets(
        self,
    ) -> None:
        _, offsets = episode_intake._line_table("甲\r\n乙丙\r\n丁\n".encode("utf-8"))
        self.assertEqual(episode_intake._line_number(offsets, 0), 1)
        self.assertEqual(episode_intake._line_number(offsets, offsets[1], end=True), 1)
        self.assertEqual(episode_intake._line_number(offsets, offsets[1]), 2)
        self.assertEqual(episode_intake._line_number(offsets, offsets[-1], end=True), 3)
        for bad_offset in (-1, 1, offsets[-1] + 1, True, False):
            with self.subTest(bad_offset=bad_offset):
                with self.assertRaises(ValueError):
                    episode_intake._line_number(offsets, bad_offset)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
