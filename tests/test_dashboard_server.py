import contextlib
import concurrent.futures
import hashlib
import http.client
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch

SUITE = Path(__file__).resolve().parents[1]
SKILL = SUITE / "skills/short-drama"
SCRIPT = SKILL / "scripts/dashboard_server.py"
SPEC = importlib.util.spec_from_file_location("short_drama_dashboard_server", SCRIPT)
assert SPEC and SPEC.loader
dashboard_server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dashboard_server)
DashboardError = dashboard_server.DashboardError
ProjectStore = dashboard_server.ProjectStore
create_server = dashboard_server.create_server


def run_node(script: str) -> "subprocess.CompletedProcess[str]":
    """Run one Node snippet and read its output as UTF-8.

    Without an explicit encoding Windows decodes the child's pipe with the ANSI
    code page. The creator-facing Chinese these assertions are about then comes
    back as mojibake, or fails outright on the bytes cp1252 leaves undefined.
    The snippet goes through a file, not ``node -e``: a snippet that embeds an
    example document outgrows the Windows command-line limit.
    """

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "snippet.js"
        path.write_text(script, encoding="utf-8")
        return subprocess.run(
            ["node", str(path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


def redirect_directory(link: Path, target: Path) -> bool:
    """Point ``link`` at ``target``, however this platform can.

    A symlink needs Developer Mode or an elevated shell on Windows; a junction
    needs neither and redirects just as well, which is why the traversal checks
    must reject both.
    """

    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        if os.name != "nt":
            return False
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
    )
    return completed.returncode == 0 and link.exists()


def make_project(root: Path, title: str = "测试短剧") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "short-drama.json").write_text(
        json.dumps(
            {"project_id": "test", "title": title, "current_checkpoint": "draft"}
        ),
        encoding="utf-8",
    )


class ProjectStoreTests(unittest.TestCase):
    def store(self, workspace: Path, **limits: int) -> ProjectStore:
        canonical = dashboard_server.load_project_tool(SKILL)
        # Expose exactly what the active backend declares it needs, so a
        # backend that quietly reached past its own contract fails here.
        tool = SimpleNamespace(
            **{
                name: getattr(canonical, name)
                for name in dashboard_server.directory_backend().contract
            }
        )
        return ProjectStore(workspace, tool, **limits)

    def require_descriptor_pinning(self) -> None:
        if dashboard_server.directory_backend() is not (
            dashboard_server._DescriptorDirectory
        ):
            self.skipTest("this behaviour is specific to descriptor pinning")

    def test_rejects_a_project_tool_without_the_dashboard_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Dashboard contract"):
                ProjectStore(
                    Path(directory), SimpleNamespace(project_status=lambda _root: {})
                )

    def test_discovers_manifests_without_following_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            make_project(workspace / "alpha", "甲项目")
            make_project(workspace / "nested/beta", "乙项目")
            try:
                (workspace / "linked").symlink_to(
                    workspace / "nested", target_is_directory=True
                )
            except OSError:
                pass

            projects, warnings = self.store(workspace).discover()

            self.assertEqual(
                [item["path"] for item in projects], ["alpha", "nested/beta"]
            )
            self.assertEqual(
                [item["title"] for item in projects], ["甲项目", "乙项目"]
            )
            self.assertEqual(warnings, [])
            self.assertEqual(len({item["id"] for item in projects}), 2)

    def test_concurrent_discovery_has_an_independent_directory_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            make_project(workspace / "show")
            store = self.store(workspace)
            expected = store.discover()[0]

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(lambda _: store.discover()[0], range(96)))

            self.assertTrue(all(result == expected for result in results))

    def test_discovery_uses_creator_safe_title_for_a_malformed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "internal-folder-name"
            make_project(project)
            (project / "short-drama.json").write_text("[]", encoding="utf-8")

            projects, warnings = self.store(Path(directory)).discover()

            self.assertEqual(projects[0]["title"], "未命名短剧")
            self.assertEqual(warnings, [])

    def test_concurrent_root_project_requests_have_independent_cursors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            make_project(workspace)
            (workspace / "notes.md").write_text("root project", encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]
            expected_tree = store.tree(project_id)
            expected_status = store.status(project_id)

            def read(index: int):
                if index % 2:
                    return "status", store.status(project_id)
                return "tree", store.tree(project_id)

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(read, range(96)))

            for kind, result in results:
                expected = expected_tree if kind == "tree" else expected_status
                self.assertEqual(result, expected)

    def test_tree_enforces_node_depth_and_size_limits_with_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            (project / "large.md").write_text("12345", encoding="utf-8")
            (project / "deep/a/b").mkdir(parents=True)
            (project / "deep/a/b/hidden.md").write_text("x", encoding="utf-8")
            store = self.store(workspace, max_depth=1, max_nodes=20, max_file_bytes=4)
            project_id = store.discover()[0][0]["id"]

            result = store.tree(project_id)

            files = []
            stack = list(result["tree"])
            while stack:
                item = stack.pop()
                files.append(item)
                stack.extend(item.get("children", []))
            large = next(item for item in files if item.get("path") == "large.md")
            self.assertTrue(large["oversize"])
            self.assertTrue(
                any("深度上限" in warning for warning in result["warnings"])
            )
            self.assertTrue(
                any("大小上限" in warning for warning in result["warnings"])
            )
            with self.assertRaises(DashboardError) as caught:
                store.read_text(project_id, "large.md")
            self.assertEqual(caught.exception.status, 413)

    def test_read_write_versions_conflicts_and_atomic_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            script = project / "episodes/EP001/script.md"
            script.parent.mkdir(parents=True)
            script.write_text("第一版", encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]

            opened = store.read_text(project_id, "episodes/EP001/script.md")
            self.assertEqual(
                opened["version"], hashlib.sha256("第一版".encode()).hexdigest()
            )
            result = store.write_text(
                project_id, "episodes/EP001/script.md", "第二版", opened["version"]
            )

            self.assertTrue(result["saved"])
            self.assertEqual(script.read_text(encoding="utf-8"), "第二版")
            self.assertFalse(any(script.parent.glob(".script.md.*.tmp")))
            with self.assertRaises(DashboardError) as caught:
                store.write_text(
                    project_id,
                    "episodes/EP001/script.md",
                    "旧客户端",
                    opened["version"],
                )
            self.assertEqual(caught.exception.status, 409)
            self.assertEqual(script.read_text(encoding="utf-8"), "第二版")

    def test_reads_and_saves_unicode_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "中文工程"
            make_project(project)
            target = project / "设定集/角色.jsonl"
            target.parent.mkdir(parents=True)
            target.write_text('{"姓名":"顾霖"}\n', encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]

            opened = store.read_text(project_id, "设定集/角色.jsonl")
            result = store.write_text(
                project_id,
                "设定集/角色.jsonl",
                '{"姓名":"顾霖","身份":"佛子"}\n',
                opened["version"],
            )

            self.assertTrue(result["saved"])
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                '{"姓名":"顾霖","身份":"佛子"}\n',
            )

    def test_subtitle_sources_are_editable_project_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "字幕工程"
            make_project(project)
            target = project / "剧集/EP001/storyboard/预演.srt"
            target.parent.mkdir(parents=True)
            target.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\n第一句\n",
                encoding="utf-8",
            )
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]

            opened = store.read_text(project_id, "剧集/EP001/storyboard/预演.srt")
            result = store.write_text(
                project_id,
                "剧集/EP001/storyboard/预演.srt",
                "1\n00:00:00,000 --> 00:00:01,200\n第一句\n",
                opened["version"],
            )

            self.assertTrue(result["saved"])
            self.assertIn("01,200", target.read_text(encoding="utf-8"))

    def test_structured_text_save_rejects_invalid_json_without_modifying_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            json_file = project / "episode.json"
            jsonl_file = project / "shots.jsonl"
            json_file.write_text('{"episode": 1}\n', encoding="utf-8")
            jsonl_file.write_text('{"shot": 1}\n{"shot": 2}\n', encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]

            json_version = store.read_text(project_id, "episode.json")["version"]
            with self.assertRaisesRegex(DashboardError, "JSON is invalid") as caught:
                store.write_text(project_id, "episode.json", "{", json_version)
            self.assertEqual(caught.exception.status, 400)
            self.assertEqual(json_file.read_text(encoding="utf-8"), '{"episode": 1}\n')

            jsonl_version = store.read_text(project_id, "shots.jsonl")["version"]
            with self.assertRaisesRegex(DashboardError, "JSONL line 2") as caught:
                store.write_text(
                    project_id,
                    "shots.jsonl",
                    '{"shot": 1}\nnot-json\n',
                    jsonl_version,
                )
            self.assertEqual(caught.exception.status, 400)
            self.assertEqual(
                jsonl_file.read_text(encoding="utf-8"),
                '{"shot": 1}\n{"shot": 2}\n',
            )

    def test_concurrent_writes_cannot_both_use_one_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            target = project / "notes.txt"
            target.write_text("base", encoding="utf-8")
            target = target.resolve()
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]
            version = store.read_text(project_id, "notes.txt")["version"]
            barrier = threading.Barrier(3)
            outcomes = []

            def write(content: str) -> None:
                barrier.wait()
                try:
                    store.write_text(project_id, "notes.txt", content, version)
                    outcomes.append("saved")
                except DashboardError as exc:
                    outcomes.append(exc.status)

            writers = [
                threading.Thread(target=write, args=(content,))
                for content in ("client-a", "client-b")
            ]
            for writer in writers:
                writer.start()
            barrier.wait()
            for writer in writers:
                writer.join(timeout=2)

            self.assertCountEqual(outcomes, ["saved", 409])

    def test_two_stores_cannot_both_save_one_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            target = project / "notes.txt"
            target.write_text("base", encoding="utf-8")
            target = target.resolve()
            stores = [self.store(workspace), self.store(workspace)]
            project_id = stores[0].discover()[0][0]["id"]
            version = stores[0].read_text(project_id, "notes.txt")["version"]
            # Two stores each load their own project-tool module instance, so the
            # project's file lock must cover the compare-and-replace operation.
            barrier = threading.Barrier(3)
            outcomes = []

            def write(store: ProjectStore, content: str) -> None:
                barrier.wait()
                try:
                    store.write_text(project_id, "notes.txt", content, version)
                    outcomes.append("saved")
                except DashboardError as exc:
                    outcomes.append(exc.status)

            writers = [
                threading.Thread(target=write, args=(store, f"client-{index}"))
                for index, store in enumerate(stores)
            ]
            for writer in writers:
                writer.start()
            barrier.wait()
            for writer in writers:
                writer.join(timeout=5)

            self.assertFalse(any(writer.is_alive() for writer in writers))
            self.assertCountEqual(outcomes, ["saved", 409])
            self.assertIn(target.read_text(encoding="utf-8"), {"client-0", "client-1"})

    def test_rejects_traversal_symlinks_and_protected_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            (project / ".short-drama").mkdir()
            (project / ".short-drama/state.json").write_text("{}", encoding="utf-8")
            (project / "delivery").mkdir()
            (project / "delivery/result.txt").write_text("locked", encoding="utf-8")
            (project / "交付").mkdir()
            (project / "交付/result.txt").write_text("locked", encoding="utf-8")
            (project / "notes.txt").write_text("ok", encoding="utf-8")
            outside = workspace / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]

            for unsafe in ("../outside.txt", "/etc/passwd", "a/../../outside.txt"):
                with self.subTest(unsafe=unsafe), self.assertRaises(DashboardError):
                    store.read_text(project_id, unsafe)
            for internal in (".short-drama/state.json", ".Short-Drama/state.json"):
                with self.subTest(internal=internal), self.assertRaises(DashboardError) as caught:
                    store.read_text(project_id, internal)
                self.assertEqual(caught.exception.status, 403)
            try:
                (project / "link.txt").symlink_to(outside)
            except OSError:
                pass
            else:
                with self.assertRaises(DashboardError) as caught:
                    store.read_text(project_id, "link.txt")
                self.assertEqual(caught.exception.status, 403)

            for protected in (
                "short-drama.json",
                "delivery/result.txt",
                "交付/result.txt",
            ):
                opened = store.read_text(project_id, protected)
                self.assertFalse(opened["writable"])
                with self.assertRaises(DashboardError) as caught:
                    store.write_text(
                        project_id, protected, "changed", opened["version"]
                    )
                self.assertEqual(caught.exception.status, 403)

            tree = store.tree(project_id)
            visible_paths = []
            pending = list(tree["tree"])
            while pending:
                item = pending.pop()
                visible_paths.append(item["path"])
                pending.extend(item.get("children", []))
            self.assertFalse(
                any(path.startswith(".short-drama") for path in visible_paths)
            )
            self.assertIn("short-drama.json", visible_paths)
            self.assertIn("delivery/result.txt", visible_paths)
            self.assertIn("交付/result.txt", visible_paths)

    def test_stale_discovery_cannot_resolve_a_project_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            container = Path(directory)
            workspace = container / "workspace"
            project = workspace / "show"
            outside = container / "outside"
            make_project(project, "原项目")
            make_project(outside, "外部项目")
            store = self.store(workspace)
            discovered = store.discover()
            project_id = discovered[0][0]["id"]

            shutil.rmtree(project)
            try:
                project.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks are unavailable")

            with patch.object(store, "discover", return_value=discovered):
                with self.assertRaises(DashboardError) as caught:
                    store.status(project_id)

            self.assertEqual(caught.exception.status, 403)

    def test_status_and_tree_read_from_a_pinned_project_root(self) -> None:
        # A descriptor keeps reading the directory it pinned even after the
        # name is repointed. Path pinning cannot promise that -- it fails the
        # request instead, which the path-backend test below asserts.
        self.require_descriptor_pinning()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            project = workspace / "show"
            outside = Path(directory) / "outside"
            make_project(project, "原项目")
            make_project(outside, "外部项目")
            (project / "inside.md").write_text("inside", encoding="utf-8")
            (outside / "outside-secret.md").write_text("outside", encoding="utf-8")
            digest = hashlib.sha256(b"inside").hexdigest()
            (project / ".short-drama").mkdir()
            (project / ".short-drama/state.json").write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "artifacts": {
                            "inside": {
                                "outputs": ["inside.md"],
                                "inputs": {},
                                "acceptance": {
                                    "decision": "accepted",
                                    "outputs": {"inside.md": digest},
                                },
                                "review": {
                                    "verdict": "approve",
                                    "outputs": {"inside.md": digest},
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            store = ProjectStore(
                workspace, dashboard_server.load_project_tool(SKILL)
            )
            project_id = store.discover()[0][0]["id"]

            def swap_while(call):
                entered = threading.Event()
                proceed = threading.Event()
                original = call[0]

                def delayed(*args, **kwargs):
                    entered.set()
                    self.assertTrue(proceed.wait(timeout=3))
                    return original(*args, **kwargs)

                call[1](delayed)
                result: list[object] = []
                thread = threading.Thread(target=lambda: result.append(call[2]()))
                thread.start()
                self.assertTrue(entered.wait(timeout=3))
                saved = workspace / "show-original"
                project.rename(saved)
                project.symlink_to(outside, target_is_directory=True)
                proceed.set()
                thread.join(timeout=3)
                project.unlink()
                saved.rename(project)
                self.assertFalse(thread.is_alive())
                return result[0]

            original_status = store.project_tool.project_status_at
            status = swap_while(
                (
                    original_status,
                    lambda replacement: setattr(
                        store.project_tool, "project_status_at", replacement
                    ),
                    lambda: store.status(project_id),
                )
            )
            store.project_tool.project_status_at = original_status
            self.assertEqual(status["title"], "原项目")
            self.assertEqual(status["artifacts"], {"inside": "approved"})

            original_tree = store._tree_from_root
            tree = swap_while(
                (
                    original_tree,
                    lambda replacement: setattr(
                        store, "_tree_from_root", replacement
                    ),
                    lambda: store.tree(project_id),
                )
            )
            store._tree_from_root = original_tree
            visible = json.dumps(tree, ensure_ascii=False)
            self.assertIn("inside.md", visible)
            self.assertNotIn("outside-secret.md", visible)
            store.close()

    def test_dashboard_edit_invalidates_tracked_lifecycle_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            tool = dashboard_server.load_project_tool(SKILL)
            tool.initialize_project(
                project,
                title="状态测试",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SKILL,
            )
            target = project / "剧集/EP001/screenplay.md"
            target.parent.mkdir(parents=True)
            target.write_text("旧版本\n", encoding="utf-8")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            state_path = project / ".short-drama/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["artifacts"]["EP001:script"] = {
                "owner": "short-drama-write",
                "candidate_targets": {"剧集/EP001/screenplay.md": digest},
                "accepted_targets": {"剧集/EP001/screenplay.md": digest},
                "build_state": "materialized",
                "validation_state": "pass",
                "creator_acceptance": "accepted",
                "independent_review": "approve",
                "delivery_gate": "ready",
            }
            tool.atomic_json(state_path, state)
            store = ProjectStore(workspace, tool)
            project_id = store.discover()[0][0]["id"]
            opened = store.read_text(project_id, "剧集/EP001/screenplay.md")

            store.write_text(
                project_id,
                "剧集/EP001/screenplay.md",
                "新版本\n",
                opened["version"],
            )

            status = store.status(project_id)
            self.assertEqual(
                status["lifecycle"]["artifact_state"], {"update_needed": 1}
            )
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                persisted["artifacts"]["EP001:script"]["build_state"],
                "materialized",
            )

    def test_status_overlays_live_hash_drift_after_an_external_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            tool = dashboard_server.load_project_tool(SKILL)
            tool.initialize_project(
                project,
                title="状态测试",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SKILL,
            )
            target = project / "剧集/EP001/screenplay.md"
            target.parent.mkdir(parents=True)
            target.write_text("已确认\n", encoding="utf-8")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            state_path = project / ".short-drama/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["artifacts"]["EP001:script"] = {
                "accepted_targets": {"剧集/EP001/screenplay.md": digest},
                "build_state": "materialized",
                "validation_state": "pass",
                "creator_acceptance": "accepted",
                "independent_review": "approve",
                "delivery_gate": "ready",
            }
            tool.atomic_json(state_path, state)
            target.write_text("磁盘外部改动\n", encoding="utf-8")
            store = ProjectStore(workspace, tool)
            project_id = store.discover()[0][0]["id"]

            status = store.status(project_id)

            self.assertEqual(
                status["lifecycle"]["artifact_state"], {"update_needed": 1}
            )

    def test_status_treats_a_tracked_symlink_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            tool = dashboard_server.load_project_tool(SKILL)
            tool.initialize_project(
                project,
                title="状态测试",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SKILL,
            )
            target = project / "剧集/EP001/screenplay.md"
            target.parent.mkdir(parents=True)
            target.write_text("已确认\n", encoding="utf-8")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            state_path = project / ".short-drama/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["artifacts"]["EP001:script"] = {
                "accepted_targets": {"剧集/EP001/screenplay.md": digest},
                "build_state": "materialized",
                "validation_state": "pass",
                "creator_acceptance": "accepted",
                "independent_review": "approve",
                "delivery_gate": "ready",
            }
            tool.atomic_json(state_path, state)
            outside = workspace / "outside.md"
            outside.write_text("外部内容\n", encoding="utf-8")
            target.unlink()
            try:
                target.symlink_to(outside)
            except OSError:
                self.skipTest("symbolic links are unavailable")
            store = ProjectStore(workspace, tool)
            project_id = store.discover()[0][0]["id"]

            status = store.status(project_id)

            self.assertEqual(
                status["lifecycle"]["artifact_state"], {"update_needed": 1}
            )

    def test_parent_directory_swap_cannot_redirect_a_text_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            inside = project / "inside"
            inside.mkdir()
            target = inside / "notes.txt"
            target.write_text("project", encoding="utf-8")
            outside = workspace / "outside"
            outside.mkdir()
            outside_target = outside / "notes.txt"
            outside_target.write_text("outside", encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]
            version = store.read_text(project_id, "inside/notes.txt")["version"]
            swapped = False

            original_open_parent = dashboard_server._open_parent_directory

            @contextlib.contextmanager
            def swap_parent(root, relative: PurePosixPath):
                nonlocal swapped
                if relative.as_posix() == "inside/notes.txt" and not swapped:
                    inside.rename(project / "inside-original")
                    if not redirect_directory(inside, outside):
                        (project / "inside-original").rename(inside)
                        self.skipTest("directory redirection is unavailable")
                    swapped = True
                with original_open_parent(root, relative) as opened:
                    yield opened

            with patch.object(
                dashboard_server, "_open_parent_directory", swap_parent
            ):
                with self.assertRaises(DashboardError) as caught:
                    store.write_text(
                        project_id, "inside/notes.txt", "redirected", version
                    )

            self.assertEqual(caught.exception.status, 403)
            self.assertEqual(outside_target.read_text(encoding="utf-8"), "outside")
            self.assertEqual(
                (project / "inside-original/notes.txt").read_text(encoding="utf-8"),
                "project",
            )

    def test_parent_directory_swap_cannot_redirect_media_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            storyboard = project / "episodes/EP001/storyboard"
            storyboard.mkdir(parents=True)
            (storyboard / "clip.mp4").write_bytes(b"PROJECT-MEDIA")
            outside = workspace / "outside"
            outside.mkdir()
            outside_target = outside / "clip.mp4"
            outside_target.write_bytes(b"OUTSIDE-SECRET")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]
            swapped = False

            original_open_parent = dashboard_server._open_parent_directory

            @contextlib.contextmanager
            def swap_parent(root, relative: PurePosixPath):
                nonlocal swapped
                if relative.as_posix() == "episodes/EP001/storyboard/clip.mp4" and not swapped:
                    storyboard.rename(project / "storyboard-original")
                    if not redirect_directory(storyboard, outside):
                        (project / "storyboard-original").rename(storyboard)
                        self.skipTest("directory redirection is unavailable")
                    swapped = True
                with original_open_parent(root, relative) as opened:
                    yield opened

            with patch.object(
                dashboard_server, "_open_parent_directory", swap_parent
            ):
                with self.assertRaises(DashboardError) as caught:
                    store.open_media(project_id, "episodes/EP001/storyboard/clip.mp4")

            self.assertEqual(caught.exception.status, 403)
            self.assertEqual(outside_target.read_bytes(), b"OUTSIDE-SECRET")

    def test_a_platform_without_descriptors_serves_the_same_content(self) -> None:
        # The path backend is a whole dashboard, not a degraded one: same tree,
        # same reads, same saves, same previews.
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            (project / "notes.txt").write_text("文本", encoding="utf-8")
            (project / "clip.mp4").write_bytes(b"media")

            with patch.object(dashboard_server, "SECURE_DIR_FD", False):
                store = self.store(workspace)
                self.assertIs(store.backend, dashboard_server._PathDirectory)
                project_id = store.discover()[0][0]["id"]
                self.assertEqual(store.status(project_id)["title"], "测试短剧")
                names = {node["path"] for node in store.tree(project_id)["tree"]}
                self.assertEqual(
                    names, {"short-drama.json", "notes.txt", "clip.mp4"}
                )

                opened = store.read_text(project_id, "notes.txt")
                self.assertEqual(opened["content"], "文本")
                saved = store.write_text(
                    project_id, "notes.txt", "改写", opened["version"]
                )
                self.assertTrue(saved["saved"])
                self.assertEqual(
                    (project / "notes.txt").read_bytes(), "改写".encode("utf-8")
                )

                handle, _path, content_type, size = store.open_media(
                    project_id, "clip.mp4"
                )
                with handle:
                    self.assertEqual(handle.read(), b"media")
                self.assertEqual(content_type, "video/mp4")
                self.assertEqual(size, 5)
                store.close()

    def test_path_pinning_fails_a_project_root_swapped_mid_request(self) -> None:
        # The descriptor backend keeps reading the directory it pinned; path
        # pinning cannot, so it must fail the request rather than follow the
        # name to wherever it now points.
        with tempfile.TemporaryDirectory() as directory:
            container = Path(directory)
            workspace = container / "workspace"
            project = workspace / "show"
            outside = container / "outside"
            make_project(project, "原项目")
            make_project(outside, "外部项目")
            (outside / "outside-secret.md").write_text("secret", encoding="utf-8")

            with patch.object(dashboard_server, "SECURE_DIR_FD", False):
                store = self.store(workspace)
                discovered = store.discover()
                project_id = discovered[0][0]["id"]
                shutil.rmtree(project)
                if not redirect_directory(project, outside):
                    self.skipTest("directory redirection is unavailable")
                with patch.object(store, "discover", return_value=discovered):
                    for call in (
                        lambda: store.status(project_id),
                        lambda: store.tree(project_id),
                        lambda: store.read_text(project_id, "outside-secret.md"),
                    ):
                        with self.assertRaises(DashboardError) as caught:
                            call()
                        self.assertEqual(caught.exception.status, 403)
                store.close()

    def test_both_link_predicates_agree_on_what_must_not_be_walked(self) -> None:
        # The dashboard and the project tool each own a copy of this predicate,
        # and nothing else would notice if they drifted.
        canonical = dashboard_server.load_project_tool(SKILL)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plain_file = root / "plain.txt"
            plain_file.write_text("x", encoding="utf-8")
            plain_dir = root / "dir"
            plain_dir.mkdir()
            expected = {plain_file: False, plain_dir: False}
            link = root / "link"
            if redirect_directory(link, plain_dir):
                expected[link] = True
            for candidate, must_reject in expected.items():
                details = os.lstat(candidate)
                self.assertEqual(
                    dashboard_server._is_link_or_reparse(details),
                    must_reject,
                    candidate.name,
                )
                self.assertEqual(
                    canonical._is_link_or_reparse(details),
                    must_reject,
                    candidate.name,
                )

    def test_a_save_refused_by_a_file_holder_says_so(self) -> None:
        # Windows refuses the replace while anything else holds the file open,
        # the most ordinary way a save fails there. Reporting it as an unsafe
        # path would send a creator after the wrong problem.
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            (project / "notes.txt").write_text("base", encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]
            version = store.read_text(project_id, "notes.txt")["version"]

            def refuse(self, source: str, target: str) -> None:
                raise PermissionError(13, "used by another process")

            with patch.object(store.backend, "replace", refuse):
                with self.assertRaises(DashboardError) as caught:
                    store.write_text(project_id, "notes.txt", "改写", version)

            self.assertEqual(caught.exception.status, 409)
            self.assertEqual(
                caught.exception.message, "file is locked or not writable"
            )
            self.assertEqual(
                (project / "notes.txt").read_text(encoding="utf-8"), "base"
            )
            # The refused replace must still take its temporary file with it.
            self.assertEqual(
                [item.name for item in project.iterdir() if ".tmp" in item.name],
                [],
            )

    def test_a_redirected_operations_directory_cannot_hold_the_lock(self) -> None:
        # The project lock is what makes the version check and the replace one
        # operation. Taken through a redirected `.short-drama`, two dashboards
        # would each believe they held it.
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            (project / "notes.txt").write_text("base", encoding="utf-8")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]
            version = store.read_text(project_id, "notes.txt")["version"]
            outside = workspace / "outside"
            outside.mkdir()
            if not redirect_directory(project / ".short-drama", outside):
                self.skipTest("directory redirection is unavailable")

            with self.assertRaises(DashboardError) as caught:
                store.write_text(project_id, "notes.txt", "改写", version)

            self.assertEqual(caught.exception.status, 403)
            self.assertEqual(
                (project / "notes.txt").read_text(encoding="utf-8"), "base"
            )
            self.assertEqual([item.name for item in outside.iterdir()], [])

    def test_media_has_an_independent_preview_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            (project / "poster.png").write_bytes(b"123456")
            (project / "clip.mp4").write_bytes(b"123456789")
            store = self.store(workspace, max_file_bytes=2, max_media_bytes=8)
            project_id = store.discover()[0][0]["id"]

            handle, _, content_type, size = store.open_media(project_id, "poster.png")
            with handle:
                self.assertEqual(handle.read(), b"123456")
            self.assertEqual(content_type, "image/png")
            self.assertEqual(size, 6)
            tree = store.tree(project_id)
            media_nodes = {
                node["path"]: node for node in tree["tree"] if node["type"] == "media"
            }
            self.assertFalse(media_nodes["poster.png"]["oversize"])
            self.assertTrue(media_nodes["clip.mp4"]["oversize"])

            with self.assertRaises(DashboardError) as caught:
                store.open_media(project_id, "clip.mp4")
            self.assertEqual(caught.exception.status, 413)

    def test_audio_outputs_are_browsable_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "show"
            make_project(project)
            voice = project / "剧集/EP001/制作成果/tts/LINE001.wav"
            voice.parent.mkdir(parents=True)
            voice.write_bytes(b"RIFFvoice")
            store = self.store(workspace)
            project_id = store.discover()[0][0]["id"]

            tree = store.tree(project_id)
            files = {}

            def collect(nodes: list[dict]) -> None:
                for node in nodes:
                    if node["type"] == "directory":
                        collect(node["children"])
                    else:
                        files[node["path"]] = node

            collect(tree["tree"])
            self.assertEqual(files["剧集/EP001/制作成果/tts/LINE001.wav"]["type"], "media")
            self.assertEqual(store.media_info(project_id, "剧集/EP001/制作成果/tts/LINE001.wav")["kind"], "audio")


class PathPinnedProjectStoreTests(ProjectStoreTests):
    """Run every store test again through the backend Windows must use.

    The backend is chosen by platform, so without this the path half would be
    exercised only on the Windows runner. Tests that assert descriptor-specific
    behaviour skip themselves through ``require_descriptor_pinning``.
    """

    def setUp(self) -> None:
        super().setUp()
        patcher = patch.object(dashboard_server, "SECURE_DIR_FD", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_path_backend_is_the_one_under_test(self) -> None:
        self.assertIs(
            dashboard_server.directory_backend(), dashboard_server._PathDirectory
        )


class ArtifactOwnershipTests(unittest.TestCase):
    """Status carries which stage produced each file, so readers stop guessing.

    Grouping by filename means every reader keeps its own list of names, and a
    stage added later shows up as unrecognised until someone remembers to update
    that list. The novel-analysis stage sat unlabelled in the dashboard for two
    releases for exactly that reason.
    """

    def status_for(self, root: Path) -> dict:
        canonical = dashboard_server.load_project_tool(SKILL)
        return canonical.project_status(root)

    def start_project(self, root: Path):
        canonical = dashboard_server.load_project_tool(SKILL)
        canonical.initialize_project(
            root,
            title="测试短剧",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SKILL,
        )
        return canonical

    def test_status_reports_the_owner_of_every_published_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            canonical = self.start_project(root)
            canonical.publish_candidate(
                root,
                owner="short-drama-write",
                artifact_id="EP001:script",
                outputs={"剧集/EP001/screenplay.md": "# 一句正文\n"},
            )
            status = self.status_for(root)

        self.assertEqual(
            status["ownership"].get("剧集/EP001/screenplay.md"),
            "short-drama-write",
        )

    def test_ownership_is_empty_for_a_project_with_nothing_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.start_project(root)
            self.assertEqual(self.status_for(root)["ownership"], {})


class DashboardSectionVocabularyTests(unittest.TestCase):
    """Every stage that can own a file must map to a place to show it.

    This is the half that keeps the grouping self-maintaining: add a stage skill
    and this fails until the dashboard knows where its outputs belong, instead of
    quietly dropping them into 其他内容.
    """

    APP = SKILL / "assets/dashboard/app.js"

    def owner_sections(self) -> dict[str, str]:
        source = self.APP.read_text(encoding="utf-8")
        block = source[source.index("const OWNER_SECTIONS = {"):]
        block = block[: block.index("};")]
        return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block))

    def test_every_stage_skill_has_a_section(self) -> None:
        mapped = self.owner_sections()
        stages = {
            path.name
            for path in (SUITE / "skills").iterdir()
            if path.is_dir() and path.name.startswith("short-drama")
        }
        # The review stage records verdicts rather than owning creative files.
        stages.discard("short-drama-review")
        missing = sorted(stages - set(mapped))
        self.assertEqual(
            missing,
            [],
            f"dashboard OWNER_SECTIONS has no home for {missing}; their outputs "
            f"would fall into 其他内容",
        )

    def test_every_section_it_names_is_a_real_section(self) -> None:
        source = self.APP.read_text(encoding="utf-8")
        order = re.search(r"const SECTION_ORDER = \[(.*?)\];", source, re.S).group(1)
        known = set(re.findall(r'"([^"]+)"', order))
        for owner, section in self.owner_sections().items():
            with self.subTest(owner=owner):
                self.assertIn(section, known)


class DashboardSessionTests(unittest.TestCase):
    """The dashboard has to outlive the shell that started it, and say so."""

    def make_workspace(self, directory: str) -> Path:
        workspace = Path(directory) / "workspace"
        (workspace / "剧集").mkdir(parents=True)
        (workspace / "short-drama.json").write_text(
            json.dumps({"project_id": "SD-TEST", "title": "面板项目"}),
            encoding="utf-8",
        )
        return workspace

    def run_dashboard(self, *arguments: str) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_a_detached_dashboard_survives_its_launching_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(directory)
            session_path = workspace / ".short-drama/dashboard.json"
            started = self.run_dashboard(
                "--workspace", str(workspace), "--port", "0", "--detach"
            )
            self.addCleanup(
                self.run_dashboard, "--workspace", str(workspace), "--stop"
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            session = dashboard_server.read_session(session_path)
            self.assertIsNotNone(session)
            assert session is not None
            self.assertNotEqual(session["pid"], os.getpid())
            # The launching process is long gone; the server still holds its lock.
            self.assertTrue(dashboard_server.session_is_live(session_path))
            self.assertIn(session["url"], started.stdout)

            status = self.run_dashboard("--workspace", str(workspace), "--status")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["url"], session["url"])

            again = self.run_dashboard(
                "--workspace", str(workspace), "--port", "0", "--detach"
            )
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn(session["url"], again.stdout)
            self.assertEqual(
                dashboard_server.read_session(session_path)["pid"], session["pid"]
            )

            stopped = self.run_dashboard("--workspace", str(workspace), "--stop")
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            self.assertFalse(session_path.exists())
            self.assertFalse(dashboard_server.session_is_live(session_path))

    def test_a_detached_start_that_never_records_a_session_reports_the_log(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(directory)
            session_path = workspace / ".short-drama/dashboard.json"
            # Hold the serving lock so the spawned child exits without recording.
            with dashboard_server.hold_session_lock(session_path) as held:
                self.assertTrue(held)
                started = self.run_dashboard(
                    "--workspace", str(workspace), "--port", "0", "--detach"
                )
            self.assertEqual(started.returncode, 1)
            self.assertIn("dashboard.log", started.stderr)
            self.assertNotIn("Traceback", started.stderr)

    def test_an_unwritable_workspace_cannot_record_but_is_not_fatal(self) -> None:
        """Serving never depended on the session record. A workspace the creator
        can read but not write must still open, the way it did before sessions
        existed -- so the failure is a typed signal main() can degrade on, not an
        uncaught OSError, and liveness answers "no" instead of raising."""
        if os.name == "nt" or os.geteuid() == 0:
            self.skipTest("this platform cannot make a directory unwritable here")
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(directory)
            session_path = workspace / ".short-drama/dashboard.json"
            os.chmod(workspace, 0o555)
            try:
                with self.assertRaises(dashboard_server.SessionUnavailable):
                    with dashboard_server.hold_session_lock(session_path):
                        pass
                self.assertFalse(dashboard_server.session_is_live(session_path))
            finally:
                os.chmod(workspace, 0o755)

    def test_a_read_only_workspace_still_serves(self) -> None:
        if os.name == "nt" or os.geteuid() == 0:
            self.skipTest("this platform cannot make a directory unwritable here")
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(directory)
            os.chmod(workspace, 0o555)
            try:
                server = create_server(workspace, port=0)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = http.client.HTTPConnection(
                        *server.server_address[:2], timeout=5
                    )
                    connection.request("GET", "/")
                    self.assertEqual(connection.getresponse().status, 200)
                    connection.close()
                finally:
                    server.shutdown()
                    thread.join(5)
                    server.server_close()
            finally:
                os.chmod(workspace, 0o755)

    def test_a_record_for_another_workspace_is_not_this_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mine = self.make_workspace(directory)
            theirs = Path(directory) / "elsewhere"
            theirs.mkdir()
            record = {
                "schema_version": dashboard_server.SESSION_SCHEMA,
                "fingerprint": dashboard_server.workspace_fingerprint(theirs),
                "workspace": str(theirs),
            }
            self.assertFalse(dashboard_server.session_matches(record, mine))
            self.assertTrue(dashboard_server.session_matches(record, theirs))

    def test_a_missing_workspace_is_refused_instead_of_created_and_served(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "typo"
            result = self.run_dashboard(
                "--workspace", str(missing), "--port", "0", "--detach"
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("not an existing directory", result.stderr)
            self.assertFalse(missing.exists())

    def test_the_server_stops_when_its_workspace_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(directory)
            server = create_server(workspace, port=0)
            self.addCleanup(server.server_close)
            stopped = threading.Event()

            class Recorder:
                def shutdown(self) -> None:
                    stopped.set()

            dashboard_server.watch_workspace(Recorder(), workspace, interval=0.05)
            shutil.rmtree(workspace)
            self.assertTrue(
                stopped.wait(10), "watchdog did not stop a server whose workspace is gone"
            )

    def test_status_reports_nothing_running_without_a_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(directory)
            status = self.run_dashboard("--workspace", str(workspace), "--status")
            self.assertEqual(status.returncode, 1)
            payload = json.loads(status.stdout)
            self.assertFalse(payload["running"])
            self.assertNotIn("url", payload)

    def test_the_session_file_is_only_readable_by_its_owner(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX permission bits do not apply on this platform")
        with tempfile.TemporaryDirectory() as directory:
            session_path = Path(directory) / ".short-drama/dashboard.json"
            dashboard_server.write_session(
                session_path,
                {"schema_version": dashboard_server.SESSION_SCHEMA, "token": "secret"},
            )
            self.assertEqual(session_path.stat().st_mode & 0o777, 0o600)

    def test_a_record_without_a_serving_process_is_not_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_path = Path(directory) / ".short-drama/dashboard.json"
            dashboard_server.write_session(
                session_path,
                {
                    "schema_version": dashboard_server.SESSION_SCHEMA,
                    "host": "127.0.0.1",
                    "port": 8765,
                    "fingerprint": "0" * 16,
                    "token": "irrelevant",
                    "url": "http://127.0.0.1:8765/#irrelevant",
                    "pid": 999999,
                },
            )
            self.assertIsNotNone(dashboard_server.read_session(session_path))
            self.assertFalse(dashboard_server.session_is_live(session_path))

    def test_liveness_follows_the_serving_lock_not_the_recorded_pid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_path = Path(directory) / ".short-drama/dashboard.json"
            with dashboard_server.hold_session_lock(session_path) as held:
                self.assertTrue(held)
                self.assertTrue(dashboard_server.session_is_live(session_path))
                with dashboard_server.hold_session_lock(session_path) as second:
                    self.assertFalse(second)
            self.assertFalse(dashboard_server.session_is_live(session_path))

    def test_each_workspace_has_its_own_serving_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mine = Path(directory) / "a/.short-drama/dashboard.json"
            theirs = Path(directory) / "b/.short-drama/dashboard.json"
            with dashboard_server.hold_session_lock(mine) as held:
                self.assertTrue(held)
                self.assertTrue(dashboard_server.session_is_live(mine))
                self.assertFalse(dashboard_server.session_is_live(theirs))

    def test_a_corrupt_or_foreign_session_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(dashboard_server.read_session(path))
            path.write_text(json.dumps({"schema_version": "9.9"}), encoding="utf-8")
            self.assertIsNone(dashboard_server.read_session(path))
            path.write_text(
                json.dumps({"schema_version": dashboard_server.SESSION_SCHEMA}),
                encoding="utf-8",
            )
            self.assertIsNone(dashboard_server.read_session(path))


class DashboardEntrypointTests(unittest.TestCase):
    def test_static_assets_and_project_tool_resolve_inside_installed_skill(
        self,
    ) -> None:
        self.assertEqual(
            dashboard_server.STATIC_ROOT,
            SKILL / "assets/dashboard",
        )
        self.assertTrue((dashboard_server.STATIC_ROOT / "index.html").is_file())
        project_tool = dashboard_server.load_project_tool(SKILL)
        self.assertTrue(callable(project_tool.project_status))

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_supports_simple_and_legacy_creator_statuses(self) -> None:
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
const logic = require({json.dumps(str(app))});
const result = {{
  draft: logic.creatorStatus(null),
  pending: logic.creatorStatus({{creator_acceptance: "pending"}}),
  pendingBlocked: logic.creatorStatus({{
    creator_acceptance: "pending",
    independent_review: "provisional",
    delivery_gate: "blocked"
  }}),
  rejected: logic.creatorStatus({{creator_acceptance: "rejected"}}),
  revise: logic.creatorStatus({{independent_review: "revise"}}),
  stale: logic.creatorStatus({{build_state: "stale"}}),
  accepted: logic.creatorStatus({{creator_acceptance: "accepted"}}),
  ready: logic.creatorStatus({{
    creator_acceptance: "accepted",
    independent_review: "approve",
    delivery_gate: "ready"
  }}),
  mixedDelivery: logic.creatorStatus({{
    build_state: {{materialized: 3}},
    validation_state: {{pass: 3}},
    creator_acceptance: {{accepted: 3}},
    independent_review: {{approve: 3}},
    delivery_gate: {{ready: 1, blocked: 2}}
  }}),
  failed: logic.creatorStatus({{
    build_state: {{failed: 1}},
    validation_state: {{not_run: 1}},
    creator_acceptance: {{not_requested: 1}},
    independent_review: {{not_requested: 1}},
    delivery_gate: {{blocked: 1}}
  }}),
  recovery: logic.creatorStatus({{
    build_state: "materialized",
    validation_state: "pass",
    creator_acceptance: "accepted",
    independent_review: "approve",
    delivery_gate: "ready"
  }}, {{needed: true}}),
  typedDuringSave: logic.savedContentIsCurrent("sent", "sent plus more")
}};
process.stdout.write(JSON.stringify(result));
"""
        completed = run_node(script)
        result = json.loads(completed.stdout)

        self.assertEqual(result["draft"], ["创作中", "neutral"])
        self.assertEqual(result["pending"], ["待你确认", "warning"])
        self.assertEqual(result["pendingBlocked"], ["待你确认", "warning"])
        self.assertEqual(result["rejected"], ["需要修改", "danger"])
        self.assertEqual(result["revise"], ["需要修改", "danger"])
        self.assertEqual(result["stale"], ["需要更新", "warning"])
        self.assertEqual(result["accepted"], ["已采用", "success"])
        self.assertEqual(result["ready"], ["可以导出", "success"])
        self.assertEqual(result["mixedDelivery"], ["已采用", "neutral"])
        self.assertEqual(result["failed"], ["需要修改", "danger"])
        self.assertEqual(result["recovery"], ["需要更新", "warning"])
        self.assertFalse(result["typedDuringSave"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_hides_machine_files_and_groups_creator_content(self) -> None:
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
const logic = require({json.dumps(str(app))});
const paths = [
  "short-drama.json",
  "README.md",
  "输入/original-source.txt",
  "inputs/original-source.txt",
  "项目开发/story-engine.md",
  "development/story-engine.md",
  "剧集/EP001/screenplay.md",
  "episodes/EP001/screenplay.md",
  "设定集/characters.jsonl",
  "剧集/EP001/assets/image-prompts.md",
  "剧集/EP001/storyboard/shots.jsonl",
  "剧集/EP001/制作成果/image/SHOT001.png",
  "剧集/EP001/storyboard/coverage.json",
  "剧集/EP001/storyboard/delivery-containers.jsonl",
  "创作者决策/EP001-script.json",
  "审查/EP001-findings.jsonl",
  "交付/EP001/manifest.json"
];
process.stdout.write(JSON.stringify(paths.map((path) => logic.creatorSection(path))));
"""
        completed = run_node(script)

        self.assertEqual(
            json.loads(completed.stdout),
            [
                None,
                "project",
                "sources",
                "sources",
                "project",
                "project",
                "story",
                "story",
                "cast",
                "prompts",
                "storyboard",
                "production",
                None,
                None,
                None,
                None,
                None,
            ],
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_structured_projection_removes_machine_fields(self) -> None:
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
const logic = require({json.dumps(str(app))});
const projected = logic.creatorProjection({{
  name: "林夏",
  description: "克制、敏锐",
  sources: {{screenplay: {{owner: "short-drama-assets", artifact: "剧集/EP001/screenplay.md", hash: "a".repeat(64)}}}},
  source_ref: {{src: "screenplay"}},
  owner: "short-drama-assets",
  schema_version: "1.0",
  appearance: {{costume: "浅灰风衣", shape: "窄肩长款", shadow_direction: "右后方", evidence_hash: "b".repeat(64)}},
  empathy: "嘴硬心软",
  notes: [
    "保留旧木盒",
    "参考 剧集/EP001/screenplay.md 第三场",
    {{path: "设定集/props.jsonl", value: "木盒", revision: "c".repeat(40)}}
  ],
  lifecycle: {{status: "candidate"}},
  local_file: "/Users/creator/project/notes",
}});
process.stdout.write(JSON.stringify(projected));
"""
        completed = run_node(script)
        visible = completed.stdout
        projected = json.loads(visible)

        self.assertEqual(projected["name"], "林夏")
        self.assertEqual(projected["description"], "克制、敏锐")
        self.assertEqual(
            projected["appearance"],
            {"costume": "浅灰风衣", "shape": "窄肩长款", "shadow_direction": "右后方"},
        )
        self.assertEqual(projected["empathy"], "嘴硬心软")
        self.assertIn("第三场", projected["notes"][1])
        for forbidden in (
            "source_ref",
            "sources",
            "src",
            "artifact",
            "hash",
            "owner",
            "schema_version",
            "short-drama-assets",
            "剧集/EP001/screenplay.md",
            "设定集/props.jsonl",
            "candidate",
            "/Users/creator/project/notes",
            "c" * 40,
        ):
            self.assertNotIn(forbidden, visible)

    def test_open_flag_is_opt_in(self) -> None:
        class FakeServer:
            server_address = ("127.0.0.1", 43210)
            access_token = "test-capability"
            workspace_fingerprint = "0123456789abcdef"

            def shutdown(self) -> None:
                pass

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

            def server_close(self) -> None:
                pass

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(
                    dashboard_server, "create_server", return_value=FakeServer()
                ),
                patch.object(dashboard_server.webbrowser, "open") as browser,
            ):
                self.assertEqual(
                    dashboard_server.main(["--workspace", directory]),
                    0,
                )
                browser.assert_not_called()

                self.assertEqual(
                    dashboard_server.main(["--workspace", directory, "--open"]),
                    0,
                )
                browser.assert_called_once_with(
                    "http://127.0.0.1:43210/#test-capability"
                )

    def test_ipv6_loopback_is_rejected_until_the_server_supports_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "IPv4 loopback"):
                create_server(Path(directory), host="::1", port=0)

    def test_each_server_uses_a_distinct_session_path_and_cookie(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = create_server(Path(directory), port=0)
            second = create_server(Path(directory), port=0)
            try:
                self.assertNotEqual(first.api_prefix, second.api_prefix)
                self.assertNotEqual(first.session_cookie, second.session_cookie)
            finally:
                first.server_close()
                second.server_close()


    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_preserves_creator_content_the_projection_used_to_delete(self) -> None:
        # A look's validity range reads like a path but is a creator id. Deleting
        # it left the row as "—", so the creator saw no validity range at all.
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
const logic = require({json.dumps(str(app))});
const projected = logic.creatorProjection({{
  validity: {{ from: "EP003/SC004/BLK-EP003-SC004-A01", until: "EP003/SC006/BLK-EP003-SC006-A03" }},
  source: "\u5267\u96c6/EP001/storyboard/shots.jsonl",
}});
process.stdout.write(JSON.stringify([
  projected.validity?.from ?? null,
  Object.prototype.hasOwnProperty.call(projected, "source"),
  logic.friendlyKey("look_id") !== logic.friendlyKey("base_look_id"),
]));
"""
        completed = run_node(script)
        self.assertEqual(
            json.loads(completed.stdout),
            ["EP003/SC004/BLK-EP003-SC004-A01", False, True],
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_editable_suffixes_match_the_server(self) -> None:
        # The client must not shadow the server with a narrower allowlist: that
        # silently removed subtitle editing, a shipped feature.
        app = dashboard_server.STATIC_ROOT / "app.js"
        editable = sorted(dashboard_server.TEXT_EXTENSIONS)
        script = f"""
const logic = require({json.dumps(str(app))});
const suffixes = {json.dumps(editable)};
process.stdout.write(JSON.stringify(
  suffixes.map((suffix) => logic.creatorEditable({{ writable: true, path: `a/b${{suffix}}` }})),
));
"""
        completed = run_node(script)
        self.assertEqual(json.loads(completed.stdout), [True] * len(editable))

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_keeps_unexpected_creator_files_reachable(self) -> None:
        # The workspace is the only UI, so a file it refuses to list is a file the
        # creator cannot open at all. Machine and lifecycle roots stay hidden.
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
const logic = require({json.dumps(str(app))});
const paths = [
  "\u5907\u5fd8.md",
  "\u53c2\u8003\u8d44\u6599/topic.md",
  "short-drama.json",
  "\u5ba1\u67e5/EP001-findings.jsonl",
  "\u4ea4\u4ed8/EP001/manifest.json",
];
process.stdout.write(JSON.stringify(paths.map((path) => logic.creatorSection(path))));
"""
        completed = run_node(script)
        self.assertEqual(
            json.loads(completed.stdout),
            ["other", "other", None, None, None],
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_preview_survives_one_malformed_record(self) -> None:
        # An interrupted agent run leaves a truncated line. The records around it
        # must still render, or the file becomes unreadable and unrepairable.
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
const logic = require({json.dumps(str(app))});
const rows = logic.readJsonLines('{{"a":1}}\\n{{broken\\n{{"c":3}}');
process.stdout.write(JSON.stringify(rows.map((row) => (row.error ? "error" : "record"))));
"""
        completed = run_node(script)
        self.assertEqual(json.loads(completed.stdout), ["record", "error", "record"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_markdown_preserves_structure_and_treats_html_as_text(
        self,
    ) -> None:
        # Generated prompts are meant to be selected and copied as one block, and
        # numbered shot order must not read as unrelated sentences. Creator text
        # must also stay text: project files are untrusted input to this renderer.
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
class N {{
  constructor(tag) {{ this.tagName = (tag || "").toUpperCase(); this.children = []; this.textContent = ""; this.className = ""; this.dataset = {{}}; }}
  set innerHTML(_value) {{ throw new Error("unsafe HTML sink"); }}
  append(...kids) {{ for (const kid of kids) this.children.push(kid); }}
  get text() {{ return this.textContent || this.children.map((kid) => (kid.text !== undefined ? kid.text : String(kid.data ?? ""))).join(""); }}
}}
const logic = require({json.dumps(str(app))});
globalThis.document = {{
  createElement: (tag) => new N(tag),
  createTextNode: (data) => ({{ data, text: String(data) }}),
  createDocumentFragment: () => new N("#fragment"),
  getElementById: () => null,
}};
const rendered = logic.renderMarkdown("```\\nopen the door, 9:16\\n# camera: dolly in\\n```\\n\\n1. near\\n2. mid\\n\\n- note");
const block = rendered.children.find((node) => node.tagName === "PRE");
const attack = `<img src=x onerror="globalThis.projectTextExecuted=true">`;
const escaped = logic.renderMarkdown(attack);
process.stdout.write(JSON.stringify([
  rendered.children.map((node) => node.tagName),
  Boolean(block && block.text.includes("# camera: dolly in")),
  escaped.text === attack && globalThis.projectTextExecuted === undefined,
]));
"""
        completed = run_node(script)
        tags, fence_kept, html_kept_as_text = json.loads(completed.stdout)
        self.assertEqual(tags, ["PRE", "OL", "UL"])
        self.assertTrue(fence_kept)
        self.assertTrue(html_kept_as_text)

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_renders_one_copyable_prompt_as_one_block(self) -> None:
        # A MiniMax H3 reference body is six `>` lines that go into one request.
        # Rendering each as its own bordered box made one prompt look like six,
        # and a creator asked which of them to copy (#97).
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
class N {{
  constructor(tag) {{ this.tagName = (tag || "").toUpperCase(); this.children = []; this.textContent = ""; this.className = ""; this.dataset = {{}}; }}
  set innerHTML(_value) {{ throw new Error("unsafe HTML sink"); }}
  append(...kids) {{ for (const kid of kids) this.children.push(kid); }}
  get text() {{ return this.textContent || this.children.map((kid) => (kid.text !== undefined ? kid.text : String(kid.data ?? ""))).join(""); }}
}}
const logic = require({json.dumps(str(app))});
globalThis.document = {{
  createElement: (tag) => new N(tag),
  createTextNode: (data) => ({{ data, text: String(data) }}),
  createDocumentFragment: () => new N("#fragment"),
  getElementById: () => null,
}};
const prompt = [
  "### \u53ef\u590d\u5236\u63d0\u793a\u8bcd",
  "> subject_definitions: <Picture 1> is the storyboard keyframe.",
  "> summary: Create one shot from the ordered picture references.",
  "> retention_analysis: Retain the composition from <Picture 1>.",
  "> detailed_description: [Shot 1] Overhead night study desk.",
  "> overall_soundscape: 0-1s black silence, then low war drums.",
  "> non_diegetic_music: N/A",
].join("\\n");
const walk = (node, out = []) => {{
  for (const kid of node.children || []) {{ out.push(kid); walk(kid, out); }}
  return out;
}};
const one = logic.renderMarkdown(prompt);
const quotes = walk(one).filter((node) => node.tagName === "BLOCKQUOTE");
const split = logic.renderMarkdown("> first paragraph\\n\\n> second paragraph");
process.stdout.write(JSON.stringify([
  quotes.length,
  quotes.length === 1 && quotes[0].text.includes("subject_definitions")
    && quotes[0].text.includes("non_diegetic_music"),
  quotes.length === 1
    && quotes[0].children.filter((kid) => kid.tagName === "BR").length,
  walk(split).filter((node) => node.tagName === "BLOCKQUOTE").length,
]));
"""
        completed = run_node(script)
        boxes, keeps_every_section, breaks, split_by_blank_line = json.loads(
            completed.stdout
        )
        self.assertEqual(boxes, 1)
        self.assertTrue(keeps_every_section)
        self.assertEqual(breaks, 5)
        # A blank line still separates two quotes, as Markdown says it does.
        self.assertEqual(split_by_blank_line, 2)

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_labels_keep_ids_as_written(self) -> None:
        # IDs are how the documents cite each other; `shot ep001 001.png` cannot
        # be searched for in 分镜.md.
        app = dashboard_server.STATIC_ROOT / "app.js"
        paths = [
            "剧集/EP001/制作成果/images/SHOT-EP001-001.png",
            "审查/EP001-审查.md",
            "剧集/EP001/Scene_Notes.md",
            "剧集/EP001/分镜.md",
            "项目开发/story-engine.md",
        ]
        script = f"""
const logic = require({json.dumps(str(app))});
process.stdout.write(JSON.stringify({json.dumps(paths)}.map(logic.fileLabel)));
"""
        self.assertEqual(
            json.loads(run_node(script).stdout),
            ["SHOT-EP001-001.png", "EP001-审查", "Scene_Notes", "分镜", "故事引擎"],
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_copy_buttons_carry_the_prompt_as_written(self) -> None:
        app = dashboard_server.STATIC_ROOT / "app.js"
        example = SUITE / "examples/creator-first/EP001/视频提示词.md"
        source = example.read_text(encoding="utf-8")
        h3 = [
            "subject_definitions: <Picture 1> is the storyboard keyframe.",
            "summary: Create one shot from the ordered picture references.",
            "non_diegetic_music: N/A",
        ]
        extra = "\n".join(
            [
                "## 说明",
                "> 这段引用只是说明，不是提示词。",
                "### 可复制提示词",
                f"> {h3[0]}",
                "",
                *[f"> {line}" for line in h3[1:]],
                "### 冻结关键帧提示词",
                "```text",
                "Frozen frame, `raw` **as typed**",
                "```",
                "## 下一项",
                "```text",
                "not a prompt",
                "```",
            ]
        )
        script = f"""
class N {{
  constructor(tag) {{ this.tagName = (tag || "").toUpperCase(); this.children = []; this.textContent = ""; this.className = ""; this.dataset = {{}}; }}
  append(...kids) {{ for (const kid of kids) this.children.push(kid); }}
}}
const logic = require({json.dumps(str(app))});
globalThis.document = {{
  createElement: (tag) => new N(tag),
  createTextNode: (data) => ({{ data }}),
  createDocumentFragment: () => new N("#fragment"),
  getElementById: () => null,
}};
const walk = (node, out = []) => {{
  for (const kid of node.children || []) {{ out.push(kid); walk(kid, out); }}
  return out;
}};
const copies = (text) => walk(logic.renderMarkdown(text))
  .filter((node) => node.className === "copy-button")
  .map((node) => node.dataset.copyText);
process.stdout.write(JSON.stringify({{
  example: copies({json.dumps(source)}),
  extra: copies({json.dumps(extra)}),
}}));
"""
        result = json.loads(run_node(script).stdout)

        expected = []
        lines = source.split("\n")
        for index, line in enumerate(lines):
            if line.strip() == "### 可复制提示词":
                quote = []
                for following in lines[index + 1 :]:
                    if not following.startswith(">"):
                        break
                    quote.append(following[2:] if following.startswith("> ") else following[1:])
                expected.append("\n".join(quote))
        self.assertTrue(expected)
        self.assertEqual(result["example"], expected)
        # A multi-line prompt copies as one request, line breaks intact, even
        # across a blank line; a fence
        # copies verbatim, Markdown marks and all; neither a plain quote nor a
        # fence under an ordinary heading gets a button.
        self.assertEqual(
            result["extra"], ["\n".join(h3), "Frozen frame, `raw` **as typed**"]
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_frontend_translates_server_protocol_messages(self) -> None:
        # The server's English protocol strings were reaching the creator UI raw.
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"""
const logic = require({json.dumps(str(app))});
process.stdout.write(JSON.stringify([
  logic.friendlyFailure("file changed since it was opened"),
  logic.friendlyFailure("file is locked or not writable"),
  logic.friendlyFailure("an unmapped message"),
  logic.creatorTitle({{ zh: "\u6d4b\u8bd5" }}),
  logic.creatorTitle("\u9006\u5149\u544a\u767d"),
]));
"""
        completed = run_node(script)
        translated, busy, passthrough, guarded, kept = json.loads(completed.stdout)
        self.assertNotIn("file changed", translated)
        self.assertNotIn("not writable", busy)
        self.assertEqual(passthrough, "an unmapped message")
        self.assertEqual(guarded, "未命名短剧")
        self.assertEqual(kept, "逆光告白")


class DashboardHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.project = self.workspace / "show"
        make_project(self.project, "HTTP 项目")
        (self.project / "notes.md").write_text("hello", encoding="utf-8")
        self.server = create_server(self.workspace, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address[:2]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, method: str, path: str, *, headers=None, body=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        request_headers = {"Host": f"127.0.0.1:{self.port}"}
        if "/api/" in path.split("?", 1)[0]:
            request_headers["X-Short-Drama-Token"] = self.server.access_token
        request_headers.update(headers or {})
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_headers, data

    def test_api_requires_a_per_launch_session_capability(self) -> None:
        status, _, _ = self.request(
            "GET", "/api/projects", headers={"X-Short-Drama-Token": ""}
        )
        self.assertEqual(status, 401)
        status, _, _ = self.request(
            "GET", "/api/projects", headers={"X-Short-Drama-Token": "wrong"}
        )
        self.assertEqual(status, 401)

        status, headers, body = self.request("POST", "/api/session")
        self.assertEqual(status, 200)
        session = json.loads(body)
        self.assertEqual(session["status"], "ready")
        self.assertEqual(session["apiBase"], self.server.api_prefix)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertIn(f"Path={self.server.api_prefix}/", headers["Set-Cookie"])
        status, _, _ = self.request(
            "GET",
            f"{session['apiBase']}/api/projects",
            headers={"X-Short-Drama-Token": "", "Cookie": cookie},
        )
        self.assertEqual(status, 200)

    def test_a_non_ascii_capability_is_answered_not_dropped(self) -> None:
        # hmac.compare_digest raises TypeError on a str holding a codepoint
        # above U+007F, and header bytes arrive decoded as iso-8859-1. Raised
        # from _security_ok, which runs outside every handler's try block, that
        # closed the socket with no status line at all — pre-authentication.
        # Only latin-1-encodable values reach the header at all; every byte
        # from 0x80 up decodes to a codepoint compare_digest refused.
        for token in ("\xff\xfe", "é", "\x80"):
            with self.subTest(token=token):
                status, _, _ = self.request(
                    "GET", "/api/projects", headers={"X-Short-Drama-Token": token}
                )
                self.assertEqual(status, 401)

    def test_a_malformed_project_manifest_is_reported_not_dropped(self) -> None:
        # Valid JSON that is not an object reached project.get() and raised
        # AttributeError, which no handler's except tuple listed.
        broken = self.workspace / "broken"
        make_project(broken)
        (broken / "short-drama.json").write_text("[]", encoding="utf-8")
        try:
            status, _, body = self.request("GET", "/api/projects")
            self.assertEqual(status, 200)
            identifier = next(
                item["id"]
                for item in json.loads(body)["projects"]
                if item["path"] == "broken"
            )
            status, _, body = self.request("GET", f"/api/status?project={identifier}")
            self.assertEqual(status, 500)
            self.assertIn("error", json.loads(body))
        finally:
            shutil.rmtree(broken)

    def project_id(self) -> str:
        status, _, body = self.request("GET", "/api/projects")
        self.assertEqual(status, 200)
        return json.loads(body)["projects"][0]["id"]

    def test_serves_frontend_and_calls_real_project_status(self) -> None:
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertTrue(body)
        self.assertIn("Content-Security-Policy", headers)
        status, _, body = self.request("GET", "/app.js")
        self.assertEqual(status, 200)
        self.assertTrue(body)

        project_id = self.project_id()
        status, _, body = self.request("GET", f"/api/status?project={project_id}")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["title"], "HTTP 项目")
        self.assertIn("lifecycle", payload)

    def test_rejects_non_loopback_bind_host_and_untrusted_headers(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            create_server(self.workspace, host="0.0.0.0", port=0, suite_root=SUITE)

        status, _, _ = self.request(
            "GET", "/api/projects", headers={"Host": "evil.example"}
        )
        self.assertEqual(status, 403)
        status, _, _ = self.request(
            "GET",
            "/api/projects",
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(status, 403)
        status, _, _ = self.request(
            "GET",
            "/api/projects",
            headers={"Host": f"evil@127.0.0.1:{self.port}"},
        )
        self.assertEqual(status, 403)

    def test_http_put_requires_version_and_returns_conflict(self) -> None:
        project_id = self.project_id()
        path = f"/api/file?project={project_id}&path=notes.md"
        status, _, body = self.request("GET", path)
        opened = json.loads(body)
        self.assertEqual(status, 200)

        missing_version = json.dumps({"content": "new"}).encode()
        status, _, _ = self.request(
            "PUT",
            path,
            headers={"Content-Type": "application/json"},
            body=missing_version,
        )
        self.assertEqual(status, 400)
        good = json.dumps(
            {"content": "new", "expectedVersion": opened["version"]}
        ).encode()
        status, _, body = self.request(
            "PUT", path, headers={"Content-Type": "application/json"}, body=good
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.project.joinpath("notes.md").read_text(), "new")
        status, _, _ = self.request(
            "PUT", path, headers={"Content-Type": "application/json"}, body=good
        )
        self.assertEqual(status, 409)

    def test_http_put_allows_json_escaping_within_the_file_limit(self) -> None:
        project_id = self.project_id()
        path = f"/api/file?project={project_id}&path=notes.md"
        status, _, body = self.request("GET", path)
        self.assertEqual(status, 200)
        opened = json.loads(body)
        content = "\x00" * 370_000
        payload = json.dumps(
            {"content": content, "expectedVersion": opened["version"]}
        ).encode()
        self.assertGreater(len(payload), 2 * 1024 * 1024 + 64 * 1024)

        status, _, _ = self.request(
            "PUT", path, headers={"Content-Type": "application/json"}, body=payload
        )

        self.assertEqual(status, 200)
        self.assertEqual(self.project.joinpath("notes.md").stat().st_size, len(content))

    def test_media_endpoint_serves_complete_image_with_safe_headers(self) -> None:
        media = self.project / "episodes/EP001/assets/poster.png"
        media.parent.mkdir(parents=True)
        image = b"\x89PNG\r\n\x1a\npreview-bytes"
        media.write_bytes(image)
        project_id = self.project_id()
        status, _, body = self.request(
            "GET", f"/api/media?project={project_id}&path=episodes%2FEP001%2Fassets%2Fposter.png"
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["readOnly"])
        self.assertEqual(payload["contentType"], "image/png")
        self.assertIn("/api/media/content?", payload["contentUrl"])

        status, headers, body = self.request("GET", payload["contentUrl"])
        self.assertEqual(status, 200)
        self.assertEqual(body, image)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(headers["Content-Length"], str(len(image)))
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

        status, headers, body = self.request("HEAD", payload["contentUrl"])
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Length"], str(len(image)))

    def test_video_content_supports_single_byte_ranges(self) -> None:
        media = self.project / "episodes/EP001/storyboard/demo.mp4"
        media.parent.mkdir(parents=True)
        video = b"0123456789"
        media.write_bytes(video)
        project_id = self.project_id()
        path = f"/api/media/content?project={project_id}&path=episodes%2FEP001%2Fstoryboard%2Fdemo.mp4"

        status, headers, body = self.request(
            "GET", path, headers={"Range": "bytes=2-5"}
        )
        self.assertEqual(status, 206)
        self.assertEqual(body, b"2345")
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertEqual(headers["Content-Length"], "4")
        self.assertEqual(headers["Content-Range"], "bytes 2-5/10")

        status, headers, body = self.request("GET", path, headers={"Range": "bytes=-3"})
        self.assertEqual(status, 206)
        self.assertEqual(body, b"789")
        self.assertEqual(headers["Content-Range"], "bytes 7-9/10")

        status, headers, body = self.request(
            "GET", path, headers={"Range": "bytes=50-60"}
        )
        self.assertEqual(status, 416)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Range"], "bytes */10")

    def test_media_content_reuses_path_and_request_security_boundaries(self) -> None:
        outside = self.workspace / "outside.png"
        outside.write_bytes(b"outside")
        linked = self.project / "episodes/EP001/assets/linked.png"
        linked.parent.mkdir(parents=True)
        try:
            linked.symlink_to(outside)
        except OSError:
            self.skipTest("symbolic links unavailable")
        project_id = self.project_id()

        status, _, _ = self.request(
            "GET",
            f"/api/media/content?project={project_id}&path=episodes%2FEP001%2Fassets%2Flinked.png",
        )
        self.assertEqual(status, 403)
        status, _, _ = self.request(
            "GET",
            f"/api/media/content?project={project_id}&path=..%2Foutside.png",
        )
        self.assertEqual(status, 400)
        status, _, _ = self.request(
            "GET",
            f"/api/media/content?project={project_id}&path=episodes%2FEP001%2Fassets%2Flinked.png",
            headers={"Origin": "http://evil.example"},
        )
        self.assertEqual(status, 403)


class PathPinnedDashboardHTTPTests(DashboardHTTPTests):
    """Serve the same HTTP surface through the backend Windows must use.

    The store tests cover the backend directly; this covers what reaches a
    creator -- byte ranges, conditional saves, media headers -- over a socket.
    """

    def setUp(self) -> None:
        patcher = patch.object(dashboard_server, "SECURE_DIR_FD", False)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.assertIs(
            self.server.store.backend, dashboard_server._PathDirectory
        )


# ------------------------------------------------------------------ v2 views

EXAMPLE = SUITE / "examples/creator-first/EP001"
DOCUMENTS = ("剧本.md", "视觉设定.md", "分镜.md", "图片提示词.md", "视频提示词.md")
views = dashboard_server.views
RHYTHM = {
    "status": "accepted",
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
# A cut list written the way the edit stage documents it: numbered and plain
# subtitles, highlighted words, every overlay style, countdowns, rarities and
# sound effects with and without gain.
CUT_LIST = """# EP001 剪辑单

- 成片目标时长：9.00 秒
- 画幅与帧率：9:16 · 1080×1920 · 24fps
- 交付响度：-16 LUFS
- 字幕：硬字幕
- 未采用镜头：MOTION-EP001-003（理由：文件缺失——尚未生产）；MOTION-EP001-004（理由：质量不可用）

## CUT-EP001-001 · 攥紧的茶杯

- 来源：MOTION-EP001-001 · 制作成果/videos/cup.mp4
- 入点：0.30
- 出点：3.30
- 时长：3.00
- 取舍：入点=起势删掉；出点=动作落定
- 声音：保留原声
- 字幕 1：0.10-1.40 火箭军？（重点：火箭军）
- 字幕 2：1.50-2.90 四个号，加起来四个粉吧。
- 画面文字 1：0.00-1.00 卡片 主号 粉丝 2｜小号 1
- 画面文字 2：1.20-2.80 角标 剩余 4 天（倒计时：431999）
- 音效 1：0.90-1.40 制作成果/音效/cup-knock.wav（增益：-10）
- 音效 2：2.00-2.20 制作成果/音效/tick.wav

## CUT-EP001-002 · 四个号，四个粉

- 来源：MOTION-EP001-002 · 制作成果/videos/laugh.mp4
- 入点：0.00
- 出点：4.00
- 时长：4.00
- 取舍：入点=哄笑起；出点=推到脸
- 声音：保留原声
- 字幕：都听见了。
- 字幕时间：0.40-2.00
- 画面文字：0.50-3.50 系统面板 系统绑定成功｜创作者认证（史诗）｜全站第 1 位（传说）

## CUT-EP001-003 · 倒计时接着走

- 来源：MOTION-EP001-005 · 制作成果/videos/tick.mp4
- 入点：1.00
- 出点：3.00
- 时长：2.00
- 取舍：入点=抬眼；出点=笑僵
- 声音：保留原声
- 字幕：无
- 画面文字：0.00-2.00 任务面板 任务：五天内｜0 / 1000000（倒计时：接续）
"""
# The static route beside a video cut: keyframes from the storyboard and the
# image prompts, camera moves, and voice lines numbered, plain and with gain.
STILL_CUT_LIST = """# EP001 剪辑单

- 画幅与帧率：1080×1920 · 24fps

## CUT-EP001-001 · 攥紧的茶杯

- 来源：MOTION-EP001-001 · 制作成果/videos/cup.mp4
- 入点：0.30
- 出点：3.30
- 时长：3.00
- 取舍：入点=起势删掉；出点=动作落定
- 声音：保留原声
- 配音：0.40 制作成果/audio/L03.mp3

## CUT-EP001-002 · 四个号，四个粉

- 来源：SHOT-EP001-002 · 制作成果/images/002.png
- 入点：0.00
- 出点：2.50
- 时长：2.50
- 取舍：入点=起；出点=止
- 声音：配音
- 运镜：推近 6%
- 字幕 1：0.10-1.20 火箭军？（重点：火箭军）
- 配音 1：0.10 制作成果/audio/L01.mp3（增益：-2）
- 配音 2：1.30 制作成果/audio/L02.mp3
- 音效：0.00-1.00 制作成果/audio/S_laugh.mp3

## CUT-EP001-003 · 办公室

- 来源：IMG-OFFICE-PLATE · 制作成果/images/office.jpg
- 入点：0.00
- 出点：1.50
- 时长：1.50
- 取舍：入点=起；出点=止
- 声音：环境
"""
REVIEW = """# EP001 审查

- 范围：剧本、分镜、剪辑单
- 结论：REVISE
- 复核方式：独立 reviewer

## Blocker · REV-001 · 「空白才好」落地时看不到对手的判断
- 位置：剧本.md / EP001-SC001；分镜.md / SHOT-EP001-010、SHOT-EP001-011
- 证据：中间没有他听到这句话的反应。
- 影响：反转的力量减半。
- 修订结果：先给周薄森半拍停顿。
- 规则：STY-14 · reviewed_invariant

## Minor · REV-002 · 字幕和面板同时出现
- 位置：剪辑单.md / CUT-EP001-002
- 证据：重叠。
- 影响：容易扫过去。
- 修订结果：字幕推后。
- 规则：EDT-03 · craft_default
"""
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63789862030003ab018271b1e22c0000000049454e44ae426082"
)


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def example(name: str) -> str:
    return (EXAMPLE / name).read_text(encoding="utf-8")


def make_creator_project(root: Path, *, rhythm: bool = True) -> None:
    """EP001 from the example, a cut list and a review; EP002 with a screenplay only."""

    root.mkdir(parents=True)
    manifest = {
        "project_id": "creator", "title": "让你管账号", "current_checkpoint": "draft",
        "format": {"episode_count": 8, "target_seconds_per_episode": 60, "aspect_ratio": "9:16"},
    }
    if rhythm:
        manifest["creator_authority"] = {"rhythm_profile": RHYTHM}
    (root / "short-drama.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    episode = root / "剧集/EP001"
    episode.mkdir(parents=True)
    for name in DOCUMENTS:
        (episode / name).write_text(example(name), encoding="utf-8")
    board = example("分镜.md")
    # SHOT-001 binds a first frame that exists; SHOT-002 one that does not.
    for number, image in (("001", "001.png"), ("002", "missing.png")):
        slot = (
            f"REF-START-{number}（顺序：1）· 剧集/EP001/制作成果/images/{image}《起始帧》"
            "（用途：起始帧；控制：构图；不得控制：动作）。"
        )
        head, _, rest = board.partition(f"## SHOT-EP001-{number}")
        rest = rest.replace("- 输入参考图：无（创作者已明确选择文生视频）。", f"- 输入参考图：{slot}", 1)
        board = f"{head}## SHOT-EP001-{number}{rest}"
    (episode / "分镜.md").write_text(board, encoding="utf-8")
    (episode / "剪辑单.md").write_text(CUT_LIST, encoding="utf-8")
    (episode / "制作成果/images").mkdir(parents=True)
    (episode / "制作成果/images/001.png").write_bytes(PIXEL)
    (episode / "制作成果/videos").mkdir(parents=True)
    (episode / "制作成果/videos/cup.mp4").write_bytes(b"\x00" * 64)
    # Named like the shot it would be, but no 来源 line points at it.
    (episode / "制作成果/videos/SHOT-EP001-002.mp4").write_bytes(b"\x00" * 64)
    (episode / "制作成果/成片").mkdir(parents=True)
    (episode / "制作成果/成片/成片.mp4").write_bytes(b"\x00" * 64)
    (root / "剧集/EP002").mkdir(parents=True)
    (root / "剧集/EP002/剧本.md").write_text(
        example("剧本.md").replace("EP001", "EP002").replace("四个号，四个粉", "五天一百万", 1),
        encoding="utf-8",
    )
    (root / "审查").mkdir()
    (root / "审查/EP001-审查.md").write_text(REVIEW, encoding="utf-8")


class CreatorViewsTests(unittest.TestCase):
    """The readers the dashboard shows, held to the checker and to each stage's own parser."""

    def episode(self, **documents: str) -> dict:
        texts = {name: example(name) for name in DOCUMENTS}
        texts.update(documents)
        return views.read_episode("EP001", texts, REVIEW)

    def test_the_example_episode_reads_as_its_storyboard_says(self) -> None:
        episode = self.episode()
        metrics = episode["metrics"]
        self.assertEqual(episode["problems"], [])
        self.assertEqual(episode["title"], "四个号，四个粉")
        self.assertEqual((metrics["shots"], metrics["seconds"]), (22, 62))
        self.assertEqual(metrics["close"], 0.5)
        self.assertEqual(metrics["unsized"], 1)
        shots = {shot["id"]: shot for shot in episode["board"]["shots"]}
        self.assertEqual(shots["SHOT-EP001-006"]["scale"], "")
        self.assertEqual(shots["SHOT-EP001-001"]["refState"], "t2v")
        self.assertEqual([scene["id"] for scene in episode["script"]["scenes"]], ["EP001-SC001", "EP001-SC002"])

    def test_the_storyboard_is_read_by_the_checkers_own_functions(self) -> None:
        # Change what the checker thinks a duration is and the dashboard follows;
        # a second parser would keep answering 62.
        with patch.object(views.check, "_declared_seconds", lambda _value: 1.0):
            metrics = self.episode()["metrics"]
        self.assertEqual(metrics["seconds"], 22)

    def test_shot_scale_reads_the_first_rung_whole(self) -> None:
        self.assertEqual(views.shot_scale("过肩中近景，桌面高度"), "中近景")
        self.assertEqual(views.shot_scale("手与茶杯大特写"), "大特写")
        self.assertEqual(views.shot_scale("江晨近景，三分之四侧"), "近景")
        self.assertEqual(views.shot_scale("越过右肩看屏幕"), "")
        self.assertNotIn("中近景", views.CLOSE_SCALES)

    def test_screenplay_blocks_match_the_write_stage_index(self) -> None:
        index = load_script(
            "parity_screenplay_index", SUITE / "skills/short-drama-write/scripts/screenplay_index.py"
        )
        estimate = load_script(
            "parity_duration_estimate", SUITE / "skills/short-drama-write/scripts/duration_estimate.py"
        )
        text = example("剧本.md")
        ours = views.parse_screenplay(text)
        speakers = frozenset(
            block["who"] for scene in ours["scenes"] for block in scene["blocks"] if block["k"] == "line"
        )
        blocks, issues = index._parse_screenplay(text.encode("utf-8"), speakers)
        self.assertEqual(issues, [])

        def canonical(block: dict) -> tuple:
            if block["kind"] == "dialogue":
                return ("line", "", block["speaker"])
            if block["kind"] == "production_tag" and block["tag"] in ("VO", "OS"):
                return ("line", block["tag"], block["speaker"])
            if block["kind"] == "production_tag":
                return ("tag", block["tag"], "")
            return (block["kind"], "", "")

        theirs = [canonical(block) for block in blocks if block["kind"] not in ("scene_heading", "comment")]
        mine = [
            (block["k"], block.get("tag", ""), block.get("who", ""))
            for scene in ours["scenes"]
            for block in scene["blocks"]
        ]
        self.assertEqual(mine, theirs)
        # Same order, same words: every block's text (and any parenthetical) sits in the indexed block's source.
        indexed = [block["_text"] for block in blocks if block["kind"] not in ("scene_heading", "comment")]
        shown = [block for scene in ours["scenes"] for block in scene["blocks"]]
        for block, source in zip(shown, indexed):
            with self.subTest(text=block["text"]):
                self.assertTrue(block["text"])
                self.assertIn(block["text"], source)
                self.assertIn(block.get("paren", ""), source)
        counts = estimate.measure(text.encode("utf-8"), [dict(block, record_type="block") for block in blocks])
        shares = views.voice_share(ours)
        self.assertEqual(shares["spoken"], counts["dialogue_characters"])
        self.assertEqual(shares["vo"], counts["voiceover_characters"])

    def test_cut_list_matches_the_edit_tool(self) -> None:
        edit = load_script("parity_edit_tool", SUITE / "skills/short-drama-edit/scripts/edit_tool.py")
        for name, document in (("video", CUT_LIST), ("stills", STILL_CUT_LIST)):
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "剪辑单.md"
                path.write_text(document, encoding="utf-8")
                delivery, cuts, unused = edit.parse_cut_list(path)
                self.assert_cut_list_parity(views.parse_cut_list(document), delivery, cuts, unused, edit)

    def assert_cut_list_parity(self, ours, delivery, cuts, unused, edit) -> None:
        self.assertEqual(
            (ours["target"], ours["lufs"], ours["burn"], tuple(ours["frame"]), ours["fps"]),
            (delivery.target_seconds, delivery.loudness_lufs, delivery.burn_subtitles, delivery.frame_size, delivery.fps),
        )
        self.assertEqual(ours["unused"], unused)
        placed = edit._timeline(cuts, [cut.declared for cut in cuts])
        self.assertEqual(len(ours["cuts"]), len(cuts))
        for mine, (cut, at, _scale) in zip(ours["cuts"], placed):
            with self.subTest(cut=cut.cut_id):
                self.assertEqual(
                    (mine["id"], mine["title"], mine["motion"], mine["media"], mine["in"], mine["out"], mine["sec"], mine["at"]),
                    (cut.cut_id, cut.title, cut.motion, cut.media, cut.start, cut.end, cut.declared, round(at, 3)),
                )
                self.assertEqual(
                    [(sub["s"], sub["e"], sub["text"], tuple(sub["keys"])) for sub in mine["subs"]],
                    [tuple(sub) for sub in cut.subtitles],
                )
                self.assertEqual(
                    [(t["s"], t["e"], t["style"], tuple(t["items"]), t["countdown"], t["resume"], tuple(t["rarities"])) for t in mine["texts"]],
                    [(t.start, t.end, t.style, t.items, t.countdown, t.resume, t.rarities) for t in cut.screen_texts],
                )
                self.assertEqual(
                    [(x["s"], x["e"], x["path"], x["gain"]) for x in mine["sfx"]],
                    [(x.start, x.end, x.path, x.gain_db) for x in cut.sound_effects],
                )
                self.assertEqual(mine["still"], cut.still)
                self.assertEqual(
                    None if mine["move"] is None else (mine["move"]["kind"], mine["move"]["amount"]),
                    None if cut.move is None else tuple(cut.move),
                )
                self.assertEqual(
                    [(v["s"], v["path"], v["gain"]) for v in mine["voices"]],
                    [tuple(voice) for voice in cut.voices],
                )

    def test_a_still_cut_links_its_storyboard_shot_and_an_image_prompt_still_links_none(self) -> None:
        cuts = views.parse_cut_list(STILL_CUT_LIST)["cuts"]
        self.assertEqual([cut["shot"] for cut in cuts], ["SHOT-EP001-001", "SHOT-EP001-002", None])
        self.assertEqual([cut["at"] for cut in cuts], [0, 3.0, 5.5])

    def test_a_document_that_does_not_parse_falls_back_instead_of_failing(self) -> None:
        broken_cut = CUT_LIST.replace("- 来源：MOTION-EP001-001 · 制作成果/videos/cup.mp4\n", "")
        episode = self.episode(**{"分镜.md": "# EP001 分镜\n\n随手记的几句。\n", "剪辑单.md": broken_cut})
        self.assertIsNone(episode["board"])
        self.assertEqual([cut["id"] for cut in episode["cutlist"]["cuts"]], ["CUT-EP001-002", "CUT-EP001-003"])
        self.assertTrue(any("分镜.md" in problem for problem in episode["problems"]))
        # Nothing else is lost because one document is unreadable.
        self.assertIsNotNone(episode["script"])
        self.assertEqual(episode["metrics"]["shots"], 0)

    def test_review_keeps_what_to_change_and_drops_reviewer_internals(self) -> None:
        review = views.parse_review(REVIEW)
        self.assertEqual(review["verdict"], "需要修改")
        self.assertTrue(review["independent"])
        self.assertEqual([item["sev"] for item in review["findings"]], ["must", "could"])
        self.assertEqual(
            review["findings"][0]["targets"], ["EP001-SC001", "SHOT-EP001-010", "SHOT-EP001-011"]
        )
        visible = json.dumps(review, ensure_ascii=False)
        for internal in ("STY-14", "EDT-03", "reviewed_invariant", "craft_default", "Blocker"):
            self.assertNotIn(internal, visible)
        # A review not written in the suggested structure is shown as text.
        self.assertEqual(views.parse_review("# EP001 审查意见\n\n- 第 3 镜的笑意来得太早。\n")["findings"], [])

    def test_visual_settings_keep_the_era_locks_and_overlay_entries(self) -> None:
        settings = views.parse_settings(example("视觉设定.md"))
        self.assertEqual(settings["era"]["period"], "当下（2020 年代）")
        self.assertIn("制服", [facet["k"] for facet in settings["era"]["facets"]])
        items = {item["name"]: item for item in settings["items"]}
        self.assertEqual(items["江晨"]["lock"]["surface"], "pine-green lapel service jacket")
        self.assertEqual(len(items["江晨"]["lock"]["shots"]), 11)
        self.assertEqual([name for name, item in items.items() if item["overlay"]], ["系统面板"])

    def test_the_episode_id_spelling_is_the_project_tools(self) -> None:
        tool = dashboard_server.load_project_tool(SKILL)
        for candidate in ("EP001", "EP1000", "EP01", "EP0100", "EP1", "ep001"):
            with self.subTest(candidate=candidate):
                self.assertEqual(
                    bool(views.EPISODE_ID_RE.fullmatch(candidate)),
                    bool(tool.EPISODE_ID_RE.fullmatch(candidate)),
                )

    def test_search_finds_lines_shots_and_settings(self) -> None:
        rows = views.search_entries(self.episode())
        groups = {hit["g"] for hit in views.search(rows, "茶杯")}
        self.assertTrue({"镜头", "剧本动作", "设定"} <= groups)
        line = views.search(rows, "空白才好")
        self.assertIn(("台词", "script", "EP001-SC001"), {(hit["g"], hit["view"], hit["arg"]) for hit in line})
        self.assertEqual(views.search(rows, "   "), [])


class StatusFormatTests(unittest.TestCase):
    def test_status_reports_only_a_well_formed_episode_shape(self) -> None:
        tool = dashboard_server.load_project_tool(SKILL)
        self.assertEqual(
            tool.project_format({"format": {"episode_count": 8, "target_seconds_per_episode": 60, "aspect_ratio": "9:16", "pacing": {"x": 1}}}),
            {"episode_count": 8, "target_seconds_per_episode": 60, "aspect_ratio": "9:16"},
        )
        self.assertEqual(
            tool.project_format({"format": {"episode_count": True, "target_seconds_per_episode": -1, "aspect_ratio": " "}}),
            {},
        )
        self.assertEqual(tool.project_format({}), {})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            make_creator_project(root)
            status = tool.project_status_from_root(root, project_root=str(root))
            self.assertEqual(status["format"]["target_seconds_per_episode"], 60)


class DashboardViewEndpointTests(unittest.TestCase):
    """GET /api/series, /api/episode and /api/search over a real socket."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.project = self.workspace / "creator"
        make_creator_project(self.project)
        self.server = create_server(self.workspace, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address[:2]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, path: str, *, headers=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        request_headers = {"Host": f"127.0.0.1:{self.port}", "X-Short-Drama-Token": self.server.access_token}
        request_headers.update(headers or {})
        connection.request("GET", path, headers=request_headers)
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, body

    def get(self, path: str):
        status, body = self.request(path)
        self.assertEqual(status, 200, body)
        return json.loads(body), body.decode("utf-8")

    def project_id(self) -> str:
        return self.get("/api/projects")[0]["projects"][0]["id"]

    def test_series_summarises_every_episode_without_internals(self) -> None:
        series, raw = self.get(f"/api/series?project={self.project_id()}")
        self.assertEqual(set(series), {"title", "format", "rhythm", "lifecycle", "episodes", "cast"})
        self.assertEqual(series["format"]["target_seconds_per_episode"], 60)
        self.assertEqual(series["rhythm"]["close_shot_share_min"], 0.45)
        first, second = series["episodes"]
        self.assertEqual((first["id"], first["title"], first["shots"], first["seconds"]), ("EP001", "四个号，四个粉", 22, 62))
        self.assertTrue(all(first["has"].values()))
        self.assertEqual(first["review"], {"must": 1, "should": 0, "could": 1})
        self.assertEqual([item["id"] for item in first["must"]], ["REV-001"])
        self.assertEqual(first["cutSeconds"], 9)
        self.assertEqual({key for key, value in second["has"].items() if value}, {"script"})
        self.assertEqual([person["name"] for person in series["cast"]], ["江晨", "周薄森"])
        for internal in (str(self.workspace), "project_root", "authority", "ownership", "STY-14", ".short-drama"):
            self.assertNotIn(internal, raw)

    def test_an_unaccepted_rhythm_profile_is_not_compared_against(self) -> None:
        manifest = json.loads((self.project / "short-drama.json").read_text(encoding="utf-8"))
        manifest["creator_authority"]["rhythm_profile"]["status"] = "proposed"
        (self.project / "short-drama.json").write_text(json.dumps(manifest), encoding="utf-8")
        series, _ = self.get(f"/api/series?project={self.project_id()}")
        self.assertIsNone(series["rhythm"])

    def test_media_is_bound_only_through_the_documents(self) -> None:
        episode, _ = self.get(f"/api/episode?project={self.project_id()}&ep=EP001")
        media = episode["media"]
        # The 起始帧 that exists is shown; the one written but absent is not.
        self.assertEqual(media["frames"], {"SHOT-EP001-001": "剧集/EP001/制作成果/images/001.png"})
        # A clip comes from a 来源 line, resolved against the episode first;
        # SHOT-EP001-002.mp4 sits in the folder but no line names it.
        self.assertEqual(media["clips"], {"CUT-EP001-001": "剧集/EP001/制作成果/videos/cup.mp4"})
        self.assertEqual(media["film"], "剧集/EP001/制作成果/成片/成片.mp4")
        self.assertEqual(episode["docs"]["review"], "审查/EP001-审查.md")
        self.assertEqual(episode["docs"]["分镜.md"], "剧集/EP001/分镜.md")

    def test_episode_endpoint_refuses_what_it_cannot_serve(self) -> None:
        project = self.project_id()
        self.assertEqual(self.request(f"/api/episode?project={project}&ep=..%2FEP001")[0], 400)
        self.assertEqual(self.request(f"/api/episode?project={project}&ep=EP009")[0], 404)
        self.assertEqual(self.request(f"/api/episode?project={project}")[0], 400)
        self.assertEqual(self.request(f"/api/episode?project={project}&ep=EP001", headers={"X-Short-Drama-Token": "wrong"})[0], 401)
        self.assertEqual(self.request(f"/api/series?project={project}", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(
            self.request(f"/api/search?project={project}&q=a&scope=series", headers={"Origin": "http://evil.example"})[0], 403
        )

    def test_linked_episodes_and_media_are_not_followed(self) -> None:
        outside = self.workspace / "outside"
        outside.mkdir()
        (outside / "剧本.md").write_text(example("剧本.md").replace("EP001", "EP009"), encoding="utf-8")
        (outside / "frame.png").write_bytes(PIXEL)
        if not redirect_directory(self.project / "剧集/EP009", outside):
            self.skipTest("directory links unavailable")
        images = self.project / "剧集/EP001/制作成果/images"
        (images / "001.png").unlink()
        try:
            (images / "001.png").symlink_to(outside / "frame.png")
        except OSError:
            (images / "001.png").write_bytes(PIXEL)
            linked_media = False
        else:
            linked_media = True
        project = self.project_id()
        series, _ = self.get(f"/api/series?project={project}")
        self.assertEqual([row["id"] for row in series["episodes"]], ["EP001", "EP002"])
        self.assertEqual(self.request(f"/api/episode?project={project}&ep=EP009")[0], 404)
        if linked_media:
            episode, _ = self.get(f"/api/episode?project={project}&ep=EP001")
            self.assertEqual(episode["media"]["frames"], {})

    def test_search_covers_one_episode_or_the_series(self) -> None:
        project = self.project_id()
        within, _ = self.get(f"/api/search?project={project}&q=%E7%A9%BA%E7%99%BD&scope=ep&ep=EP001")
        self.assertEqual({hit["ep"] for hit in within["hits"]}, {"EP001"})
        across, _ = self.get(f"/api/search?project={project}&q=%E7%A9%BA%E7%99%BD&scope=series")
        self.assertEqual({hit["ep"] for hit in across["hits"]}, {"EP001", "EP002"})
        hit = next(item for item in within["hits"] if item["g"] == "台词")
        self.assertEqual(hit["snippet"][hit["at"]:hit["at"] + hit["len"]], "空白")
        self.assertEqual(self.request(f"/api/search?project={project}&q={'a' * 81}&scope=series")[0], 400)
        self.assertEqual(self.request(f"/api/search?project={project}&q=a&scope=ep")[0], 400)
        empty, _ = self.get(f"/api/search?project={project}&q=&scope=series")
        self.assertEqual(empty["hits"], [])


class PathPinnedDashboardViewEndpointTests(DashboardViewEndpointTests):
    """The same read-only views through the backend Windows must use."""

    def setUp(self) -> None:
        patcher = patch.object(dashboard_server, "SECURE_DIR_FD", False)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.assertIs(self.server.store.backend, dashboard_server._PathDirectory)


class FrontendLogicTests(unittest.TestCase):
    """Pure frontend decisions, run in Node against the shipped app.js."""

    def run_app(self, body: str):
        if not shutil.which("node"):
            self.skipTest("Node.js is unavailable")
        app = dashboard_server.STATIC_ROOT / "app.js"
        script = f"const logic = require({json.dumps(str(app))});\n{body}"
        return json.loads(run_node(script).stdout)

    def test_next_steps_put_must_fix_before_writing_before_editing(self) -> None:
        empty = {"script": False, "settings": False, "board": False, "imgp": False, "vidp": False, "cut": False, "film": False, "review": False}
        rows = [
            {"id": "EP001", "has": {**empty, "script": True, "settings": True, "board": True, "imgp": True, "vidp": True}, "review": {"must": 0}, "must": []},
            {"id": "EP002", "has": {**empty, "script": True}, "review": {"must": 0}, "must": []},
            {"id": "EP003", "has": dict(empty), "review": {"must": 0}, "must": []},
            {"id": "EP004", "has": {**empty, "script": True, "review": True}, "review": {"must": 2}, "must": [{"id": "REV-001", "title": "开场慢"}, {"id": "REV-002", "title": "旁白多"}]},
            {"id": "EP005", "has": {key: True for key in empty}, "review": {"must": 0}, "must": []},
        ]
        result = self.run_app(
            f"const rows = {json.dumps(rows, ensure_ascii=False)};\n"
            "process.stdout.write(JSON.stringify({todos: logic.seriesTodos(rows).map((t) => [t.row.id, t.next.kind, t.next.ask]),"
            " done: logic.nextFor(rows[4]).kind}));"
        )
        self.assertEqual([item[:2] for item in result["todos"]], [["EP004", "fix"], ["EP002", "write"], ["EP001", "cut"]])
        self.assertIn("REV-001、REV-002", result["todos"][0][2])
        self.assertIn("视觉设定.md", result["todos"][1][2])
        self.assertEqual(result["done"], "done")

    def test_routes_address_every_view(self) -> None:
        result = self.run_app(
            "const r = (h) => { const x = logic.parseRoute(h); return [x.page, x.ep, x.view, x.arg, x.q.get('scene')]; };\n"
            "process.stdout.write(JSON.stringify([r('#/'), r('#/EP001'), r('#/EP001/board/SHOT-EP001-011?scene=EP001-SC002'),"
            " r('#/EP1000/settings/%E6%B1%9F%E6%99%A8'), r('#/files'), r('#/edit?path=x'), r('#abc'),"
            " logic.viewForPath('剧集/EP001/分镜.md'), logic.viewForPath('审查/EP001-审查.md'), logic.viewForPath('项目开发/brief.md')]));"
        )
        self.assertEqual(result[0], ["overview", None, "", None, None])
        self.assertEqual(result[1], ["episode", "EP001", "", None, None])
        self.assertEqual(result[2], ["episode", "EP001", "board", "SHOT-EP001-011", "EP001-SC002"])
        self.assertEqual(result[3], ["episode", "EP1000", "settings", "江晨", None])
        self.assertEqual([result[4][0], result[5][0], result[6][0]], ["files", "edit", "overview"])
        self.assertEqual(result[7:], ["#/EP001/board", "#/EP001/review", "#/"])

    def test_rhythm_checks_compare_only_against_an_accepted_profile(self) -> None:
        metrics = {"shots": 22, "seconds": 62, "avg": 2.82, "close": 0.5, "vo": 0.35}
        result = self.run_app(
            f"const m = {json.dumps(metrics)}; const p = {json.dumps(RHYTHM)};\n"
            "process.stdout.write(JSON.stringify([logic.rhythmChecks(m, p, 60).map((c) => [c.key, c.ok]), logic.rhythmChecks(m, null, null)]));"
        )
        # Seconds and average shot length have a target but no tolerance in the profile, so they carry no verdict.
        self.assertEqual(result[0], [["seconds", None], ["avg", None], ["close", True], ["vo", False]])
        self.assertEqual(result[1], [])

    def test_component_styles_take_colours_and_type_only_from_tokens(self) -> None:
        # tokens.css is shared verbatim with another dashboard; a raw colour or
        # font stack in styles.css would fork the design language silently.
        styles = (dashboard_server.STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
        stray = re.findall(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(|PingFang|Songti|Menlo|Consolas", styles)
        self.assertEqual(stray, [])
        tokens = (dashboard_server.STATIC_ROOT / "tokens.css").read_text(encoding="utf-8")
        declared = set(re.findall(r"(--zs-[a-z0-9-]+)\s*:", tokens))
        used = set(re.findall(r"var\((--zs-[a-z0-9-]+)\)", styles))
        self.assertEqual(sorted(used - declared), [])

    def test_a_line_links_to_a_shot_only_through_the_cut_list(self) -> None:
        cuts = [{"shot": "SHOT-EP001-010", "subs": [{"text": "空白才好。"}], "texts": [{"items": ["系统绑定成功"]}]}]
        result = self.run_app(
            f"const map = logic.lineShots({json.dumps(cuts, ensure_ascii=False)});\n"
            "process.stdout.write(JSON.stringify([logic.lineShot(map, '空白才好。'), logic.lineShot(map, '系统绑定成功'), logic.lineShot(map, '空白')]));"
        )
        self.assertEqual(result, ["SHOT-EP001-010", "SHOT-EP001-010", None])


if __name__ == "__main__":
    unittest.main()
