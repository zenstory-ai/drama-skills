"""Real-browser regressions for creator-facing Dashboard behaviour."""

import json
import os
import re
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover - exercised by dependency-free local runs
    if os.environ.get("DASHBOARD_BROWSER_REQUIRED") == "1":
        raise
    expect = sync_playwright = None

from tests.test_dashboard_server import (
    EXAMPLE,
    PIXEL,
    STILL_CUT_LIST,
    create_server,
    make_creator_project,
    make_project,
)

NO_OVERFLOW = """() => {
  const width = document.documentElement.clientWidth;
  const escaped = [...document.querySelectorAll('body *')].filter((node) => {
    const box = node.getBoundingClientRect();
    if (!box.width || box.right <= width + 1) return false;
    for (let parent = node.parentElement; parent; parent = parent.parentElement) {
      if (['auto', 'hidden', 'scroll'].includes(getComputedStyle(parent).overflowX)) return false;
    }
    return true;
  });
  return [document.documentElement.scrollWidth - width, escaped.slice(0, 5).map((node) => node.tagName + '.' + node.className)];
}"""


class Browser:
    """One server over a temporary workspace and one Chromium, shared by a test class."""

    @classmethod
    def start(cls, workspace: Path) -> None:
        cls.server = create_server(workspace, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address[:2]
        cls.origin = f"http://{host}:{port}"
        cls.url = f"{cls.origin}/#{cls.server.access_token}"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def stop(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def open(self, width: int = 1440, height: int = 900, route: str = "#/", **options):
        context = self.browser.new_context(
            viewport={"width": width, "height": height}, reduced_motion="reduce", **options
        )
        self.addCleanup(context.close)
        page = context.new_page()
        page.goto(self.url)
        expect(page.locator("#view")).to_have_attribute("data-state", "ready")
        if route != "#/":
            self.go(page, route)
        return page

    @staticmethod
    def go(page, route: str) -> None:
        page.evaluate("(hash) => { location.hash = hash; }", route)
        page.wait_for_function(
            "(hash) => { const v = document.querySelector('#view'); return v.dataset.route === hash && v.dataset.state === 'ready'; }",
            arg=route,
        )

    def assertNoHorizontalOverflow(self, page) -> None:
        extra, escaped = page.evaluate(NO_OVERFLOW)
        self.assertEqual((extra, escaped), (0, []))


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class CreatorDeskBrowserTests(Browser, unittest.TestCase):
    """The stage views over a creator-first project with a cut list, media and a review."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        cls.project = workspace / "creator"
        make_creator_project(cls.project)
        for number in range(3, 9):
            (cls.project / f"剧集/EP{number:03d}").mkdir()
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_overview_lists_every_episode_and_leads_with_what_must_change(self) -> None:
        page = self.open()
        rows = page.locator(".matrix tbody tr")
        self.assertEqual(
            rows.evaluate_all("nodes => nodes.map((node) => node.dataset.episode)"),
            [f"EP{number:03d}" for number in range(1, 9)],
        )
        first = rows.first
        self.assertEqual(
            first.locator(".pip[data-on='1']").evaluate_all("nodes => nodes.map((node) => node.dataset.stage)"),
            ["script", "settings", "board", "imgp", "vidp", "cut", "film", "review"],
        )
        todos = page.locator("#nextSteps .todo")
        self.assertEqual(
            todos.evaluate_all("nodes => nodes.map((node) => node.dataset.ep)"), ["EP001", "EP002", "EP003"]
        )
        expect(todos.first).to_contain_text("必须改")
        rows.nth(1).click()
        page.wait_for_function("() => location.hash === '#/EP002'")

    def test_copy_to_assistant_puts_a_request_on_the_clipboard_instead_of_producing(self) -> None:
        page = self.open()
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.origin)
        page.locator("#nextSteps .todo").first.get_by_role("button", name="复制给助手").click()
        expect(page.locator("#toast")).to_contain_text("已复制")
        self.assertEqual(
            page.evaluate("() => navigator.clipboard.readText()"),
            "请按 EP001 的审查意见，先改必须改的 1 条（REV-001）。",
        )

    def test_the_stage_bar_is_the_episodes_progress(self) -> None:
        page = self.open(route="#/EP001")
        tabs = page.locator("#stagebar .tab")
        self.assertEqual(
            tabs.evaluate_all("nodes => nodes.map((node) => node.querySelector('.lbl').textContent)"),
            ["概况", "剧本", "设定", "分镜", "提示词", "成片", "审查"],
        )
        expect(page.locator('#stagebar [data-stage="board"] .meta')).to_have_text("22 镜")
        expect(page.locator('#stagebar [data-stage="review"] .dot')).to_have_class("dot warn")
        page.locator('#stagebar [data-stage="script"]').click()
        page.wait_for_function("() => location.hash === '#/EP001/script'")
        expect(page.locator('#stagebar [aria-current="page"]')).to_have_attribute("data-stage", "script")
        self.go(page, "#/EP002")
        expect(page.locator('#stagebar [data-stage="board"] .meta')).to_have_text("未写")

    def test_rhythm_strip_is_proportional_and_metrics_follow_the_profile(self) -> None:
        page = self.open(route="#/EP001/board")
        bars = page.locator(".strip-bars .sb")
        expect(bars).to_have_count(22)
        widths = bars.evaluate_all("nodes => nodes.map((node) => node.getBoundingClientRect().width)")
        # SHOT-002 is 4 s and SHOT-003 is 2 s: twice the width, less the gap.
        self.assertAlmostEqual(widths[1] / widths[2], 2, delta=0.15)
        expect(page.locator('.sb[data-shot="SHOT-EP001-006"]')).to_have_class(re.compile(r"\bunsized\b"))
        expect(page.locator(".sb .cl")).to_have_count(11)
        cards = page.locator("#boardMetrics .gauge")
        # A target without a tolerance is reported as a distance, not judged.
        expect(cards.nth(0)).to_contain_text(re.compile(r"目标 60 秒 · (多|少) [\d.]+ 秒"))
        expect(cards.nth(0).locator(".status")).to_have_count(0)
        expect(cards.nth(2)).to_contain_text("50%")
        expect(cards.nth(3)).to_contain_text("留意")
        # The one bound start frame is shown; the others are shot-size diagrams.
        expect(page.locator(".shot .thumb img")).to_have_count(1)

    def test_the_shot_drawer_follows_the_strip_and_the_keyboard(self) -> None:
        page = self.open(route="#/EP001/board")
        page.locator('.sb[data-shot="SHOT-EP001-004"]').click()
        page.wait_for_function("() => location.hash === '#/EP001/board/SHOT-EP001-004'")
        drawer = page.locator("#inspector")
        expect(drawer).to_be_visible()
        expect(drawer.locator(".ins-head .t")).to_have_text("没有针眼的手")
        expect(page.locator(".sb.sel")).to_have_attribute("data-shot", "SHOT-EP001-004")
        page.keyboard.press("ArrowRight")
        page.wait_for_function("() => location.hash === '#/EP001/board/SHOT-EP001-005'")
        expect(drawer.locator(".ins-head .id")).to_have_text("SHOT-EP001-005")
        page.keyboard.press("Escape")
        page.wait_for_function("() => location.hash === '#/EP001/board'")
        expect(drawer).to_be_hidden()

    def test_script_reads_as_a_screenplay_with_links_from_the_cut_list(self) -> None:
        page = self.open(route="#/EP001/script")
        expect(page.locator(".slug")).to_have_count(2)
        expect(page.locator(".dlg")).to_have_count(12)
        expect(page.locator(".dlg.vo").first).to_contain_text("上辈子，我死在病床上。")
        expect(page.locator(".onscreen")).to_have_count(5)
        # A line links to a shot only where the cut list quotes it as a subtitle.
        quoted = page.locator('.dlg[data-line="都听见了。新媒体这摊子，本来就是空白。"] .shotref')
        expect(quoted).to_have_attribute("href", "#/EP001/board/SHOT-EP001-002")
        expect(page.locator('.dlg[data-line="空白才好。"] .shotref')).to_have_count(0)
        expect(page.locator('.dlg .shotref[href$="SHOT-EP001-001"]')).to_have_count(1)
        page.locator(".slug .go").first.click()
        page.wait_for_function("() => location.hash === '#/EP001/board?scene=EP001-SC001'")
        expect(page.locator(".shot")).to_have_count(13)

    def test_settings_cards_show_locks_and_filter_the_storyboard(self) -> None:
        page = self.open(route="#/EP001/settings")
        card = page.locator('.asset[data-entry="江晨"]')
        expect(card.locator(".lock .surface")).to_have_text("pine-green lapel service jacket")
        expect(card.locator(".pstrip i")).to_have_count(22)
        expect(card.locator(".pstrip i.lk")).to_have_count(11)
        expect(page.locator(".era .p")).to_have_text("当下（2020 年代）")
        card.get_by_role("link", name="在分镜里筛出").click()
        page.wait_for_function("() => location.hash.startsWith('#/EP001/board?entity=')")
        expect(page.locator(".filter-note")).to_contain_text("江晨")
        expect(page.locator(".shot")).to_have_count(13)

    def test_prompts_copy_verbatim_and_count_what_was_copied(self) -> None:
        page = self.open(route="#/EP001/prompts/video")
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.origin)
        source = (EXAMPLE / "视频提示词.md").read_text(encoding="utf-8").split("\n")
        first = source[source.index("### 可复制提示词") + 1][2:]
        expect(page.locator("#copyProgress")).to_have_text("0 / 22")
        page.locator(".copybar").get_by_role("button", name="复制下一条").click()
        expect(page.locator("#copyProgress")).to_have_text("1 / 22")
        self.assertEqual(page.evaluate("() => navigator.clipboard.readText()"), first)
        expect(page.locator('.pcard[data-key="MOTION-EP001-001"]')).to_have_class(re.compile(r"\bcopied\b"))
        page.get_by_role("button", name="清除标记").click()
        expect(page.locator("#copyProgress")).to_have_text("0 / 22")

    def test_film_view_lays_the_cut_list_on_a_timeline(self) -> None:
        page = self.open(route="#/EP001/film")
        expect(page.locator(".tl-cut")).to_have_count(3)
        expect(page.locator(".tl-sub")).to_have_count(3)
        expect(page.locator(".tl-txt")).to_have_count(4)
        expect(page.locator(".tl-sfx")).to_have_count(2)
        expect(page.locator("#film")).to_have_count(1)
        widths = page.locator(".tl-cut").evaluate_all("nodes => nodes.map((node) => node.getBoundingClientRect().width)")
        self.assertAlmostEqual(widths[1] / widths[2], 2, delta=0.1)
        page.locator("#r-CUT-EP001-002").click()
        expect(page.locator("#r-CUT-EP001-002")).to_have_class(re.compile(r"\bon\b"))
        expect(page.locator("#nowCut")).to_contain_text("四个号，四个粉")
        # Clips come only from 来源: SHOT-002 has a file named after it, and still waits.
        self.go(page, "#/EP001/film/clips")
        tiles = page.locator("[data-shot-tile]")
        self.assertEqual(tiles.evaluate_all("nodes => nodes.filter((node) => node.dataset.hasClip === '1').map((node) => node.dataset.shotTile)"), ["SHOT-EP001-001"])

    def test_film_view_marks_still_cuts_and_lays_voice_lines_on_their_own_track(self) -> None:
        episode = self.project / "剧集/EP003"
        (episode / "剪辑单.md").write_text(STILL_CUT_LIST, encoding="utf-8")
        (episode / "制作成果/images").mkdir(parents=True)
        (episode / "制作成果/images/002.png").write_bytes(PIXEL)
        self.addCleanup(lambda: (episode / "剪辑单.md").unlink())
        page = self.open(route="#/EP003/film")
        expect(page.locator(".tl-cut")).to_have_count(3)
        self.assertEqual(
            page.locator(".tl-cut").evaluate_all("nodes => nodes.map((node) => node.classList.contains('still'))"),
            [False, True, True],
        )
        expect(page.locator(".tl-voice")).to_have_count(3)
        expect(page.locator(".tl-sfx:not(.tl-voice)")).to_have_count(1)
        lefts = page.locator(".tl-voice").evaluate_all("nodes => nodes.map((node) => node.getBoundingClientRect().left)")
        self.assertEqual(lefts, sorted(lefts))
        expect(page.locator("#r-CUT-EP001-002")).to_contain_text("静帧 · 推近 6%")
        expect(page.locator("#r-CUT-EP001-003")).to_contain_text("静帧 · 固定")
        expect(page.locator("#r-CUT-EP001-002")).to_contain_text("L02.mp3")

    def test_review_findings_link_to_where_they_are(self) -> None:
        page = self.open(route="#/EP001/review")
        finding = page.locator("#f-REV-001")
        expect(finding).to_contain_text("先给周薄森半拍停顿")
        self.assertNotIn("STY-14", page.locator("#view").inner_text())
        finding.get_by_role("link", name="镜 011").click()
        page.wait_for_function("() => location.hash === '#/EP001/board/SHOT-EP001-011'")
        expect(page.locator("#inspector .refstate.must")).to_contain_text("空白才好")
        self.go(page, "#/EP001/review")
        page.locator('[data-rf="could"]').click()
        expect(page.locator(".finding")).to_have_count(1)

    def test_search_jumps_to_the_line_it_found(self) -> None:
        page = self.open(route="#/EP001/board")
        page.keyboard.press("Control+k")
        expect(page.locator("#palette")).to_be_visible()
        page.fill("#palq", "空白才好")
        expect(page.locator(".pal-item").first).to_be_visible()
        expect(page.locator(".pal-item mark").first).to_have_text("空白才好")
        page.locator(".pal-item", has_text="江晨").first.click()
        page.wait_for_function("() => location.hash === '#/EP001/script/EP001-SC001'")
        expect(page.locator(".dlg.hl")).to_contain_text("空白才好")
        page.keyboard.press("/")
        page.locator('[data-scope="series"]').click()
        page.fill("#palq", "空白才好")
        expect(page.locator(".pal-item .w", has_text="EP002").first).to_be_visible()

    def test_editing_saves_markdown_and_refuses_to_overwrite_a_newer_file(self) -> None:
        page = self.open(route="#/EP001/board/SHOT-EP001-011")
        page.get_by_role("link", name="在分镜.md 里编辑这一镜").click()
        expect(page.locator("#editState")).to_have_text("已载入")
        editor = page.locator("#editor")
        caret = editor.evaluate("node => node.value.slice(node.selectionStart, node.selectionStart + 18)")
        self.assertEqual(caret, "## SHOT-EP001-011 ")
        path = self.project / "剧集/EP001/分镜.md"
        original = path.read_text(encoding="utf-8")
        self.addCleanup(path.write_text, original, encoding="utf-8")
        editor.evaluate("node => { node.value = node.value.replace('## SHOT-EP001-011 · 冷茶', '## SHOT-EP001-011 · 凉茶'); node.dispatchEvent(new Event('input')); }")
        path.write_text(original + "\n<!-- 别处的修改 -->\n", encoding="utf-8")
        page.keyboard.press("Control+s")
        expect(page.locator("#saveError")).to_have_attribute("data-conflict", "1")
        self.assertIn("别处的修改", path.read_text(encoding="utf-8"))
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="载入最新版本").click()
        expect(page.locator("#editState")).to_have_text("已载入")
        editor.evaluate("node => { node.value = node.value.replace('## SHOT-EP001-011 · 冷茶', '## SHOT-EP001-011 · 凉茶'); node.dispatchEvent(new Event('input')); }")
        page.get_by_role("button", name="保存").click()
        expect(page.locator("#editState")).to_contain_text("已保存")
        saved = path.read_text(encoding="utf-8")
        self.assertIn("## SHOT-EP001-011 · 凉茶", saved)
        self.assertIn("别处的修改", saved)
        # The structured view reads the saved Markdown.
        self.go(page, "#/EP001/board/SHOT-EP001-011")
        expect(page.locator("#inspector .ins-head .t")).to_have_text("凉茶")

    def test_phone_width_keeps_every_view_inside_the_screen(self) -> None:
        page = self.open(390, 844)
        for route in (
            "#/", "#/EP001", "#/EP001/script", "#/EP001/settings", "#/EP001/board",
            "#/EP001/board/SHOT-EP001-004", "#/EP001/prompts/video", "#/EP001/film",
            "#/EP001/review", "#/files",
        ):
            with self.subTest(route=route):
                self.go(page, route)
                self.assertNoHorizontalOverflow(page)
        self.go(page, "#/EP001/board/SHOT-EP001-004")
        box = page.locator("#inspector").bounding_box()
        self.assertEqual((box["x"], box["width"]), (0, 390))
        self.go(page, "#/EP001/review")
        current = page.locator('#stagebar [aria-current="page"]').bounding_box()
        self.assertLessEqual(current["x"] + current["width"], 390)
        self.go(page, "#/")
        expect(page.locator(".ep-cards")).to_be_visible()
        expect(page.locator(".matrix-wrap")).to_be_hidden()


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class PlainProjectBrowserTests(Browser, unittest.TestCase):
    """Projects outside the five documents still open, and raw text stays text."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        project = workspace / "alpha"
        make_project(project, "ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMN")
        (project / "带注释.md").write_text(
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
        make_project(workspace / "empty", "空项目")
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_creator_notes_in_markdown_comments_stay_out_of_the_reading_view(self) -> None:
        page = self.open(route=f"#/file?path={quote('带注释.md')}")
        body = page.locator("[data-raw] .doc")
        expect(body).to_contain_text("第一段正文。")
        text = body.inner_text()
        for kept in ("第一段正文。", "第二段正文", "后半句", "嵌套", "之后。", "代码块里的注释要保留",
                     "终止符后面的正文。", "围栏之后的正文。", "这条没有闭合", "还有一行"):
            self.assertIn(kept, text)
        for dropped in ("改编取舍", "番号一律虚构", "行内备注", "外层", "跨行备注", "第二行",
                        "围栏里的内容不该出现", "注释里的围栏"):
            self.assertNotIn(dropped, text)
        self.assertEqual(text.count("嵌套"), 1)

    def test_long_project_title_never_creates_horizontal_page_scroll(self) -> None:
        page = self.open()
        for width in (1440, 861, 760, 620, 390, 360):
            with self.subTest(width=width):
                page.set_viewport_size({"width": width, "height": 700})
                self.assertNoHorizontalOverflow(page)

    def test_projects_switch_and_an_empty_one_says_what_to_do(self) -> None:
        page = self.open()
        value = page.locator("#projectSelect option", has_text="空项目").get_attribute("value")
        page.select_option("#projectSelect", value)
        expect(page.locator(".matrix-wrap, .empty").first).to_contain_text("还没有分集")
        expect(page.locator("#view")).to_have_attribute("data-state", "ready")

    def test_invalid_projects_payload_shows_creator_safe_chinese_error(self) -> None:
        context = self.browser.new_context(viewport={"width": 861, "height": 650})
        self.addCleanup(context.close)
        page = context.new_page()
        page.route(
            "**/api/projects",
            lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"projects": None})),
        )
        page.goto(self.url)
        expect(page.locator("#notices")).to_contain_text("无效")
        self.assertNotIn("Cannot read properties", page.locator("#notices").inner_text())


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class PlantedMarkupBrowserTests(Browser, unittest.TestCase):
    """Project text is shown as text in every view, never parsed as markup."""

    MARK = '<img id="pwn" src="x">'

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        project = workspace / "creator"
        make_creator_project(project)
        episode = project / "剧集/EP001"
        # Free-text fields only: IDs, durations and sources stay parseable, so each view renders its structure.
        free = "运镜|起点|终点|目的|景别/机位|声音|唯一动作|画面文字|用途|识别锚点|画面代称|本集造型|连续性锁|时代锚点|生成方式|状态链"
        for path in [*episode.glob("*.md"), *project.glob("审查/*.md")]:
            text = path.read_text(encoding="utf-8")
            text = re.sub(rf"^(## .+ · .+|- (?:{free})：.+|[^#\-\n\[].+)$", lambda m: m.group(1) + cls.MARK, text, flags=re.M)
            path.write_text(text, encoding="utf-8")
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_no_view_turns_project_text_into_elements(self) -> None:
        page = self.open()
        for route in (
            "#/", "#/EP001", "#/EP001/script", "#/EP001/settings", "#/EP001/board", "#/EP001/board/SHOT-EP001-004",
            "#/EP001/prompts/video", "#/EP001/prompts/image", "#/EP001/prompts/keyframe", "#/EP001/film",
            "#/EP001/review",
        ):
            with self.subTest(route=route):
                self.go(page, route)
                self.assertEqual(page.locator("#pwn").count(), 0)
        self.go(page, "#/EP001/board")
        expect(page.locator(".shot")).to_have_count(22)
        expect(page.locator("#view")).to_contain_text('<img id="pwn"')
        self.go(page, "#/EP001/prompts/video")
        expect(page.locator("#view")).to_contain_text('文生视频<img id="pwn"')
        page.keyboard.press("/")
        page.fill("#palq", "没有针眼")
        expect(page.locator(".pal-item").first).to_be_visible()
        self.assertEqual(page.locator("#pwn").count(), 0)


if __name__ == "__main__":
    unittest.main()
