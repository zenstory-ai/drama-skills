"""Every rule and mechanism this release claims is actually present.

A merge can silently drop a hunk. During this release three fixes were lost that
way — the branches touched neighbouring lines, git resolved it without a
conflict, and the tests that covered them lived on the branch that lost. Each
entry here is one shipped promise, checked against the file that has to keep it,
so the loss shows up as a failing test rather than as a defect a reader finds
later in a rendered film.
"""

import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]

# label -> (file, substring that must be present)
SHIPPED = {
    "SCR-18 行首冒号与对白语法相撞": (
        "skills/short-drama-write/references/stage-contract.md",
        "SCR-18",
    ),
    "Seedance 2.5 任务类型有承载字段": (
        "skills/short-drama-video-prompts/references/seedance-2.5.md",
        "任务类型：reference",
    ),
    "Seedance 2.5 散文秒数不是控时": (
        "skills/short-drama-video-prompts/references/seedance-2.5.md",
        "不构成时间控制",
    ),
    "produce 记录供应商任务句柄": (
        "skills/short-drama-produce/scripts/production_tool.py",
        "_read_provider_handle",
    ),
    "produce 可以取回已付费的任务": (
        "skills/short-drama-produce/scripts/production_tool.py",
        "def collect_job",
    ),
    "produce 写回前做 compare-and-set": (
        "skills/short-drama-produce/scripts/production_tool.py",
        "def _run_status",
    ),
    "audit 报出孤儿任务": (
        "skills/short-drama-produce/scripts/production_tool.py",
        "orphaned_provider_job",
    ),
    "adapter 在轮询前写句柄": (
        "skills/short-drama-produce/scripts/provider_adapters.py",
        "_record_handle",
    ),
    "adapter 支持只取回不提交": (
        "skills/short-drama-produce/scripts/provider_adapters.py",
        "collect_provider_job_id",
    ),
    "EDT-16 接镜校正": (
        "skills/short-drama-edit/references/stage-contract.md",
        "EDT-16",
    ),
    "EDT-17 重出后字幕时间作废": (
        "skills/short-drama-edit/references/stage-contract.md",
        "EDT-17",
    ),
    "一镜可以有多句字幕": (
        "skills/short-drama-edit/scripts/edit_tool.py",
        "SUBTITLE_FIELD",
    ),
    "ASS 正文转义": (
        "skills/short-drama-edit/scripts/edit_tool.py",
        "def _ass_text",
    ),
    "饱和度按真实上下界": (
        "skills/short-drama-edit/scripts/edit_tool.py",
        '"saturation": (0.0, 2.0)',
    ),
    "素材比剪辑单新要报": (
        "skills/short-drama-edit/scripts/edit_tool.py",
        "_stale_window_findings",
    ),
    "SHT-26 来源引文覆盖": (
        "skills/short-drama-storyboard/references/stage-contract.md",
        "SHT-26",
    ),
    "SHT-27 承受者也要有一镜": (
        "skills/short-drama-storyboard/references/stage-contract.md",
        "SHT-27",
    ),
    "来源引文按条目本名核对": (
        "skills/short-drama/scripts/creator_markdown_check.py",
        "by_entry_name",
    ),
    "粗体字段名是同一个字段": (
        "skills/short-drama/scripts/creator_markdown_check.py",
        "\\*\\*|__|\\*|_",
    ),
    "报错说出取不到提示词的原因": (
        "skills/short-drama/scripts/creator_markdown_check.py",
        "_copyable_prompt_cause",
    ),
    "创作台注释判断先于围栏": (
        "skills/short-drama/assets/dashboard/app.js",
        "Before the fence test",
    ),
    "创作台保留终止符后的正文": (
        "skills/short-drama/assets/dashboard/app.js",
        "closeAt + 3",
    ),
    "创作台只保存还开着的注释": (
        "skills/short-drama/assets/dashboard/app.js",
        "stripped.slice(openAt)",
    ),
    "剪辑单随交接导出": (
        "skills/short-drama/scripts/project_tool.py",
        "POST_PRODUCTION_DOCUMENTS",
    ),
    "剪辑技能已注册到创作台": (
        "skills/short-drama/assets/dashboard/app.js",
        '"short-drama-edit"',
    ),
}


class ReleaseSurfaceTests(unittest.TestCase):
    def test_every_shipped_mechanism_is_still_present(self) -> None:
        missing = []
        for label, (relative, needle) in SHIPPED.items():
            path = SUITE / relative
            with self.subTest(promise=label):
                self.assertTrue(path.is_file(), f"{relative} 不存在")
                if needle not in path.read_text(encoding="utf-8"):
                    missing.append(f"{label} — {relative} 里找不到 {needle!r}")
        self.assertEqual(
            missing,
            [],
            "以下已发布的机制在文件里消失了（多半是一次合并静默丢掉的）：\n"
            + "\n".join(missing),
        )
