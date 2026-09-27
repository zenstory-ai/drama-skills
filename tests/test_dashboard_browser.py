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
            "嵌套 <!<!-- 内层 -->-- 外层 --> 之后。\n\n"
            "<!-- 跨行备注\n     第二行 --> 终止符后面的正文。\n\n"
            "<!-- 注释里的围栏\n```md\n围栏里的内容不该出现\n```\n-->\n\n"
            "围栏之后的正文。\n\n"
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
        # The filename changes before the fetch; the body only after it.
        expect(self.page.locator("#message")).to_contain_text("已载入")
        body = self.page.locator(".content-stage").inner_text()

        self.assertIn("第一段正文。", body)
        self.assertNotIn("改编取舍", body)
        self.assertNotIn("番号一律虚构", body)
        # An inline comment loses only itself, not the sentence around it.
        self.assertIn("第二段正文", body)
        self.assertIn("后半句", body)
        self.assertNotIn("行内备注", body)
        # Removing the inner comment must not leave a fresh `<!--` behind.
        self.assertIn("嵌套", body)
        self.assertIn("之后。", body)
        self.assertNotIn("外层", body)
        # A fenced block is copied verbatim, comments included.
        self.assertIn("代码块里的注释要保留", body)
        # Text after the terminator on a closing line is body text.
        self.assertIn("终止符后面的正文。", body)
        self.assertNotIn("跨行备注", body)
        self.assertNotIn("第二行", body)
        # A fence inside a comment is commented out, not a code block.
        self.assertNotIn("围栏里的内容不该出现", body)
        self.assertNotIn("注释里的围栏", body)
        self.assertIn("围栏之后的正文。", body)
        # Unterminated: preserved, not swallowed along with the rest.
        self.assertIn("这条没有闭合", body)
        self.assertIn("还有一行", body)
        # ...and preserved once. A line that closes one comment and opens an
        # unterminated one must not render its prefix twice.
        self.assertEqual(body.count("嵌套"), 1)

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


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/creator-first/EP001"
DOCUMENTS = ["剧本.md", "视觉设定.md", "分镜.md", "图片提示词.md", "视频提示词.md"]
# A 1×1 PNG: enough for the gallery to have real media to show.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63789862030003ab018271b1e22c0000000049454e44ae426082"
)


def make_creator_first_project(root: Path) -> None:
    """Eight episodes from the creator-first example, with media and a review."""

    make_project(root, "让你管账号")
    for number in range(1, 9):
        episode = f"EP{number:03d}"
        folder = root / "剧集" / episode
        folder.mkdir(parents=True)
        for name in DOCUMENTS[: 1 + number % 5]:
            text = (EXAMPLE / name).read_text(encoding="utf-8")
            (folder / name).write_text(text.replace("EP001", episode), encoding="utf-8")
    for name in DOCUMENTS:
        (root / "剧集/EP001" / name).write_text(
            (EXAMPLE / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    images = root / "剧集/EP001/制作成果/images"
    images.mkdir(parents=True)
    for number in range(1, 4):
        (images / f"SHOT-EP001-00{number}.png").write_bytes(PIXEL)
    (root / "审查").mkdir(exist_ok=True)
    (root / "审查/EP001-审查.md").write_text(
        "# EP001 审查意见\n\n- 第 3 镜的笑意来得太早。\n", encoding="utf-8"
    )


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class CreatorFirstDashboardBrowserTests(unittest.TestCase):
    """A real creator-first project: more episodes than fit, media, a review."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        make_creator_first_project(workspace / "creator")
        cls.server = create_server(workspace, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address[:2]
        cls.origin = f"http://{host}:{port}"
        cls.url = f"{cls.origin}/#{cls.server.access_token}"
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

    def open(self, width: int, height: int, **options):
        context = self.browser.new_context(
            viewport={"width": width, "height": height}, reduced_motion="reduce", **options
        )
        self.addCleanup(context.close)
        page = context.new_page()
        page.goto(self.url)
        expect(page.locator("#message")).to_contain_text("已载入")
        return page

    def test_the_current_document_starts_on_the_first_screen(self) -> None:
        # With media in the project the reading pane began at 995px on a
        # laptop and 2065px on a phone, below an overview that grew with it.
        for width, height in ((1440, 900), (375, 812)):
            with self.subTest(width=width):
                page = self.open(width, height)
                top = page.locator("#documentPane").evaluate(
                    "node => node.getBoundingClientRect().top"
                )
                scroll = page.evaluate(
                    "() => [document.documentElement.scrollWidth, "
                    "document.documentElement.clientWidth]"
                )
                self.assertLess(top, height)
                self.assertEqual(scroll[0], scroll[1])

    def test_every_episode_is_reachable_from_the_overview(self) -> None:
        # The strip stopped at six cards under a heading that promised eight.
        page = self.open(1440, 900)
        cards = page.locator(".episode-card")
        self.assertEqual(
            cards.evaluate_all("nodes => nodes.map(node => node.dataset.episode)"),
            [f"EP{number:03d}" for number in range(1, 9)],
        )
        cards.last.click()
        expect(page.locator("#fileKind")).to_contain_text("EP008")

    def test_reading_bar_stays_in_view_and_leads_back_to_the_contents(self) -> None:
        page = self.open(375, 812)
        page.click("#openScreenplay")
        expect(page.locator("#message")).to_contain_text("已载入")
        page.evaluate("() => scrollTo(0, document.body.scrollHeight / 2)")
        bar = page.locator(".reading-bar")
        self.assertEqual(bar.evaluate("node => node.getBoundingClientRect().top"), 0)
        expect(bar.locator("#filename")).to_have_text("剧本")

        page.click("#jumpToContents")
        nav_top = page.locator("#contentNav").evaluate(
            "node => node.getBoundingClientRect().top"
        )
        self.assertGreaterEqual(nav_top, 0)
        self.assertLess(nav_top, 812 / 2)
        self.assertTrue(
            page.evaluate(
                "() => document.activeElement.classList.contains('content-link') "
                "&& document.activeElement.classList.contains('active')"
            )
        )

    def test_copy_button_puts_the_prompt_on_the_clipboard(self) -> None:
        page = self.open(1440, 900)
        page.context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=self.origin
        )
        page.locator(".content-link", has_text="视频提示词").first.click()
        expect(page.locator("#filename")).to_have_text("视频提示词")
        source = (EXAMPLE / "视频提示词.md").read_text(encoding="utf-8").split("\n")
        first_prompt = source[source.index("### 可复制提示词") + 1][2:]

        copy = page.locator(".copy-button").first
        copy.click()
        expect(copy).to_have_text("已复制")

        self.assertEqual(
            page.evaluate("() => navigator.clipboard.readText()"), first_prompt
        )


if __name__ == "__main__":
    unittest.main()
