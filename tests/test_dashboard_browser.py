"""Real-browser regressions for creator-facing Dashboard behaviour."""

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover - exercised by dependency-free local runs
    if os.environ.get("DASHBOARD_BROWSER_REQUIRED") == "1":
        raise
    expect = sync_playwright = None

from tests.test_dashboard_server import create_server, make_project


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class DashboardBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.workspace = Path(cls.temporary.name)
        cls.project = cls.workspace / "alpha"
        make_project(cls.project, "ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMN")
        long_text = "# 长正文\n\n" + "\n\n".join(
            f"## 第 {index} 节\n" + "正文" * 120 for index in range(1, 180)
        )
        (cls.project / "剧本.md").write_text(long_text, encoding="utf-8")
        (cls.project / "短文.md").write_text("# 短文\n\n只有一段。", encoding="utf-8")
        (cls.project / "带注释.md").write_text(
            "# 带注释\n\n"
            "<!-- 改编取舍：\n     番号一律虚构。 -->\n\n"
            "第一段正文。\n\n"
            "第二段正文 <!-- 行内备注 --> 后半句。\n\n"
            "```md\n<!-- 代码块里的注释要保留 -->\n```\n\n"
            "<!-- 这条没有闭合\n还有一行\n",
            encoding="utf-8",
        )
        empty = cls.workspace / "empty"
        make_project(empty, "空项目")

        cls.server = create_server(cls.workspace, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address[:2]
        cls.url = f"http://{host}:{port}/#{cls.server.access_token}"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temporary.cleanup()

    def setUp(self) -> None:
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
        )
        self.page = self.context.new_page()
        self.page.goto(self.url)
        expect(self.page.locator("#message")).to_contain_text("已载入")

    def tearDown(self) -> None:
        self.context.close()

    def content_button(self, label: str):
        return self.page.locator(".content-link", has_text=label).first

    def test_preserves_reading_progress_when_toggling_edit_mode(self) -> None:
        stage = self.page.locator(".content-stage")
        stage.evaluate("node => node.scrollTop = node.scrollHeight * 0.6")
        before = stage.evaluate(
            "node => node.scrollTop / (node.scrollHeight - node.clientHeight)"
        )

        self.page.click("#editMode")
        editor_progress = self.page.locator("#editor").evaluate(
            "node => node.scrollTop / (node.scrollHeight - node.clientHeight)"
        )
        self.page.click("#editMode")
        after = stage.evaluate(
            "node => node.scrollTop / (node.scrollHeight - node.clientHeight)"
        )

        self.assertAlmostEqual(editor_progress, before, delta=0.02)
        self.assertAlmostEqual(after, before, delta=0.02)

    def test_starts_each_newly_opened_file_at_the_top(self) -> None:
        self.page.set_viewport_size({"width": 861, "height": 650})
        stage = self.page.locator(".content-stage")
        stage.evaluate("node => node.scrollTop = node.scrollHeight")
        self.content_button("短文").evaluate("node => node.click()")
        expect(self.page.locator("#filename")).to_have_text("短文")
        expect(self.page.locator("#message")).to_contain_text("已载入")

        self.assertEqual(stage.evaluate("node => node.scrollTop"), 0)

    def test_creator_notes_in_markdown_comments_stay_out_of_the_reading_pane(
        self,
    ) -> None:
        """剧本 format sanctions comments for creator notes; the pane showed them.

        A screenplay legitimately opens with several lines of adaptation notes,
        and they were rendered as body text — so the first thing the creator read
        in the one pane meant for reading the screenplay was their own scratch
        notes. The same rule says unrecognised Markdown is preserved rather than
        quietly "fixed", so an unterminated comment must still render.
        """

        self.content_button("带注释").evaluate("node => node.click()")
        expect(self.page.locator("#filename")).to_have_text("带注释")
        body = self.page.locator(".content-stage").inner_text()

        self.assertIn("第一段正文。", body)
        self.assertNotIn("改编取舍", body)
        self.assertNotIn("番号一律虚构", body)
        # An inline comment loses only itself, not the sentence around it.
        self.assertIn("第二段正文", body)
        self.assertIn("后半句", body)
        self.assertNotIn("行内备注", body)
        # A fenced block is copied verbatim, comments included.
        self.assertIn("代码块里的注释要保留", body)
        # Unterminated: preserved, not swallowed along with the rest.
        self.assertIn("这条没有闭合", body)
        self.assertIn("还有一行", body)

    def test_long_project_title_never_creates_horizontal_page_scroll(self) -> None:
        for width in (861, 860, 620, 390, 360):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 700})
                dimensions = self.page.evaluate(
                    "() => [document.documentElement.scrollWidth, "
                    "document.documentElement.clientWidth]"
                )
                overflow = self.page.evaluate(
                    "() => [...document.querySelectorAll('*')].filter(node => "
                    "node.getBoundingClientRect().right > document.documentElement.clientWidth + 1)"
                    ".slice(0, 8).map(node => [node.tagName, node.id, node.className, "
                    "node.getBoundingClientRect().right])"
                )
                self.assertEqual(dimensions[0], dimensions[1], overflow)

    def test_empty_project_finishes_with_an_idle_status_message(self) -> None:
        value = self.page.locator("#projects option", has_text="空项目").get_attribute(
            "value"
        )
        self.page.select_option("#projects", value)
        expect(self.page.locator("#filename")).to_have_text("暂无创作内容")

        self.assertNotIn("正在", self.page.locator("#message").inner_text())
        self.assertIsNone(self.page.locator("#documentPane").get_attribute("aria-busy"))

    def test_invalid_projects_payload_shows_creator_safe_chinese_error(self) -> None:
        context = self.browser.new_context(viewport={"width": 861, "height": 650})
        page = context.new_page()

        def invalid_projects(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"projects": None}),
            )

        page.route("**/api/projects", invalid_projects)
        page.goto(self.url)
        expect(page.locator("#notices")).to_contain_text("无效")
        notice = page.locator("#notices").inner_text()
        context.close()

        self.assertNotIn("Cannot read properties", notice)


if __name__ == "__main__":
    unittest.main()
