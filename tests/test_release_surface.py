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
    "中转平台的能力清单不作为原生接口的证据": (
        "skills/short-drama-produce/references/adapter-contract.md",
        "A relay's capability listing is not evidence",
    ),
    "Seedance 能绑首尾帧": (
        "skills/short-drama-produce/scripts/provider_adapters.py",
        "SEEDANCE_SINGULAR_ROLES",
    ),
    "不把另一供应商的互斥规则搬给 Seedance": (
        "skills/short-drama-produce/scripts/provider_adapters.py",
        "Do not carry it across",
    ),
    "只写散文的终点很可能不会发生": (
        "skills/short-drama-storyboard/references/shot-craft.md",
        "它很可能不会发生",
    ),
    "分镜可以写收尾关键帧": (
        "skills/short-drama-storyboard/references/shot-craft.md",
        "首尾成对",
    ),
    "收尾关键帧写坏了要报错": (
        "skills/short-drama/scripts/creator_markdown_check.py",
        "收尾关键帧提示词不是唯一且非空",
    ),
    "语音走预置音色，不做克隆": (
        "skills/short-drama-produce/references/providers/minimax-speech.md",
        "Cloning is out of scope",
    ),
    "不硬编码音色清单": (
        "skills/short-drama-produce/scripts/provider_adapters.py",
        "The voice catalogue is deliberately not enumerated",
    ),
    "选预置音色要量不要读名字": (
        "skills/short-drama-assets/references/voice-direction.md",
        "名字不算判据",
    ),
    "参考音频可以由预置音色合成": (
        "skills/short-drama-assets/references/voice-direction.md",
        "参考可以是合成出来的",
    ),
    "瑕疵是抗生成感的材料，不是身份锚点": (
        "skills/short-drama-assets/references/character-and-look.md",
        "认不出来和不像真人是两件事",
    ),
    "负面约束不能禁掉真实世界的常态": (
        "skills/short-drama-image-prompts/references/common-recipe.md",
        "先确认 X 在真实世界里本来存不存在",
    ),
    "写实改动用盲看验证": (
        "skills/short-drama-image-prompts/references/common-recipe.md",
        "不要用纹理统计量做闸门",
    ),
    "人像要写光学口径与真实表面": (
        "skills/short-drama-image-prompts/references/common-recipe.md",
        "光学口径与真实表面",
    ),
    "颗粒是整片一档": (
        "skills/short-drama-edit/references/stage-contract.md",
        "EDT-18",
    ),
    "颗粒必须是动态的": (
        "skills/short-drama-edit/scripts/edit_tool.py",
        "allf=t+u",
    ),
    "容器里参考序号要重新编号": (
        "skills/short-drama-video-prompts/references/seedance-2.5.md",
        "必须重新编号到它上面",
    ),
    "容器不是提升一致性的手段": (
        "skills/short-drama-video-prompts/references/seedance-2.5.md",
        "不是提升跨镜一致性的手段",
    ),
    "Remotion 叠层不使用默认并发": (
        "skills/short-drama-edit/scripts/edit_tool.py",
        "DEFAULT_REMOTION_CONCURRENCY",
    ),
    "Remotion 并发可调": (
        "skills/short-drama-edit/scripts/edit_tool.py",
        "--remotion-concurrency",
    ),
    "Remotion 渲染前等字体就绪": (
        "skills/short-drama-edit/assets/remotion/src/font.ts",
        "document.fonts.ready",
    ),
    "字体族没装上要报错而不是换一款": (
        "skills/short-drama-edit/assets/remotion/src/font.ts",
        "assertFamilyResolves",
    ),
    "Remotion 路线的开销写在明面上": (
        "skills/short-drama-edit/references/sound-and-subtitles.md",
        "每一帧都过一遍无头浏览器",
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
