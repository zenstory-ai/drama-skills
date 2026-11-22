---
name: short-drama-novel-analyze
description: 拆解长篇小说、连载网文或多章原著，完成章节索引、改编价值评估、情节提取、爽点与人物演进梳理及分集候选，移交 short-drama-develop 定改编方案。用户说“导入/拆这本小说”“分析原著”“先拆前N章”或给小说文件时使用；不写立项简报或剧本。
license: MIT
---

# 原著拆解分析

从小说原文梳理有据可查的剧情推进：看每段戏改变了谁的抉择、揭开了什么秘密、怎样扭转人物强弱关系，并结合目标制作形态评估如何改成短剧或漫剧。支持整本拆解，也支持按创作者指定的章节范围（如前 100 章、第一卷、第一季）分批完整拆解。

## 快速开始

> 下文命令中 `<SKILL_DIR>` 指本 `SKILL.md` 所在目录，`<PYTHON>` 指 Python 3.9+ 解释器（Unix/macOS 用 `python3`，Windows 用 `py -3` 或 `python`）。

为长篇原著建立章节索引：

```bash
<PYTHON> "<SKILL_DIR>/scripts/novel_index.py" index <原著.txt> --out <chapter-index.json>
```

> **无终端 / 无 Python 兜底**：若当前对话环境不支持执行本地脚本，短篇或指定章数可直接由用户分批粘贴正文在对话中完成拆解与汇总；超长篇建议切分章节文件后分批上传读取。

## 开始前与材料前提

- 本技能可独立运行；完整职责范围与规则见 [阶段规范](references/stage-contract.md)。
- 只拆解创作者合法持有、拥有使用权的作品。`输入/` 只读，拆解时不改原文、不整段照抄原句（只记章节位置、起止行号和剧情作用概括，必要佐证只摘最短词句），交付文件不夹带原始全文。
- 通俗题材里的暴力、复仇、背叛、情感拉扯与暗黑冲突照常提取剧情作用；个别片段无法处理时跳过并记明行号范围，不中断整章或整批拆解。

## 先判断入口（三条路径）

1. **短篇直读（≤5 章）**：直接通读原文，在当前对话中给出精炼的改编可行性评估、核心看点与爽点、主要改编难点及简明分集/节拍思路，**无需建立 `输入/`、索引文件或 S0–S5 全套档案**。
2. **长篇快速可行性评估（>5 章，先判断值不值得改）**：无需落盘完整拆解目录，直接用临时索引搭配 `sample --count 12` 抽样阅读，给出改编可行性快评与建议拆解区间（见 [改编价值快评](references/adaptation-triage.md)），待创作者拍板后再决定是否进入完整拆解。
3. **完整拆解档案（S0–S5，整本或指定区间）**：只有书名无原文时请创作者提供文件或粘贴正文，不凭书名回忆情节；已有长篇原文时建立只读 `输入/` 与 `项目开发/source-analysis/_work/`，用 `novel_index.py` 建索引后按 S0–S5 推进（已有部分拆解结果时，读 `项目开发/source-analysis/_progress.md` 从上次进度续跑）。

## 拆解流程

全部产出落在 `项目开发/source-analysis/`（先写进 `_work/` 核对无误后再整份替换写入正式路径；若项目已安装 `short-drama` 技能并启用了项目台账，交由 `short-drama` 技能登记进度，独立运行时直接按目录约定落盘，不跨技能调用其他技能的脚本）。

| 阶段 | 做什么 | 产出 | 停顿条件 |
|---|---|---|---|
| S0 | 建章节索引（脚本） | `_index.json`、`_progress.md` | 仅零章节或索引损坏时停 |
| S1 | 改编价值快评（长篇未定范围时抽样） | `triage.md` | 短篇或已指定范围**不暂停** |
| S2 | 目标区间逐章情节提取 | `chapters/ch-<N>-extract.md` | 目标区间缺章时补齐 |
| S3 | 剧情单元汇总与爽点梳理 | `story-units.md`、`rhythm-and-emotion.md` | — |
| S4 | 人物合并与设定跨卷演进整理 | `characters.md`、`world.md` | — |
| S5 | 结合制作形态的改编取舍与分集候选 | `adaptation-value.md`、`episode-candidates.jsonl` | 移交 `short-drama-develop` 技能 |

### S0 章节索引

各阶段共用 [章节索引脚本](scripts/novel_index.py) 建立的章节边界，不各自重新切分：

```bash
<PYTHON> "<SKILL_DIR>/scripts/novel_index.py" index 输入/<原文文件> --out 项目开发/source-analysis/_work/_index.next.json
<PYTHON> "<SKILL_DIR>/scripts/novel_index.py" verify 项目开发/source-analysis/_work/_index.next.json 输入/<原文文件>
```

校验通过后将 `_work/_index.next.json` 写入正式 `_index.json`。脚本支持可选 Markdown 标题前缀（`#`–`######`）、阿拉伯与中文数字章号，按 `章 / 回 / 集 / 话 / 話 / 幕 / 节` 由粗到细自动选定主编号单位（其余记入 `ignored_heading_units`，也可传 `--unit` 指定），剔除开头目录块并分卷核对。

- **软门禁提醒（退出码 `0`）**：网文源书常见的作者跳章号、重章号或简短卷首语仅归入输出 JSON 的 `warnings` 提醒，脚本正常放行，供 Agent 复核。
- **确定性硬拦截（非零退出码）**：仅在以下情况拦截——完全识别不到章节（无章标题散稿可与创作者约定切分后手写 `sequence` / `line_start` / `line_end` 再过 `verify`）、第一章前遗漏大段楔子正文（可在索引开头补一条 `source_number: null` 覆盖第 1 行起的正文），或索引自身断号、行区间断裂。原文一旦修改须重建索引。

### S1 改编价值快评

未定范围的超长篇按 [改编价值快评](references/adaptation-triage.md) 跑 `sample --count 12` 写出 `triage.md`，汇报建议拆解区间并请创作者确认；短篇作品、创作者已指定拆解范围或明确要求直接拆完时，**不在 S1 暂停等拍板**，直接进入 S2。

### S2 逐章情节提取

按 [逐章提取与人物设定整理](references/chapter-extraction.md) 将本批目标区间内的每章拆进 `chapters/ch-<N>-extract.md`（支持并行子任务时每批 5–8 章）。写完后核对覆盖情况：

```bash
<PYTHON> "<SKILL_DIR>/scripts/novel_index.py" coverage 项目开发/source-analysis/_index.json 项目开发/source-analysis/chapters [--start <起> --end <止>]
```

全书拆解时直接跑 `coverage`，按创作者指定区间（如 `sequence` 1–100）分批拆解时传 `--start 1 --end 100`；确认返回 `complete: true`（目标章齐全且无 `unmatched_files` 错名文件）即可进入 S3。

### S3 剧情单元与爽点梳理

基于 S2 提取结果（细节不清时按行号回查原文），按 [改编价值与分集候选](references/adaptation-value.md#故事框架与剧情单元) 写出 `story-units.md` 与 `rhythm-and-emotion.md`（含 [爽点表](references/adaptation-value.md#爽点表) 相对先后排序），并在文件开头注明本批覆盖的起止章号范围。

### S4 人物与世界观设定

按 [逐章提取与人物设定整理](references/chapter-extraction.md#人物合并与设定质变记录) 合并有原文实据的同人异名，记录人物立场身份与世界观规则、战力体系的**跨卷质变节点**及首次出场章号（未明确处写「原文未明确」），产出候选名单 `characters.md` 与 `world.md`。

### S5 改编取舍与分集候选

按 [改编价值与分集候选](references/adaptation-value.md#三类判定) 结合目标制作形态评估各剧情单元（区分实拍与动态漫/漫剧对心理吐槽及密集对话的不同承载力），写出 `adaptation-value.md` 与轻量级 `episode-candidates.jsonl`，完成后汇报本批覆盖章数、预计可改集数与主要改编注意点，移交 `short-drama-develop` 技能（如需独立把关可交 `short-drama-review` 技能做 `source_analysis` 范围审查）。

## 按需加载

- **何时做抽样快评、短篇与指定范围免停规则**：[改编价值快评](references/adaptation-triage.md)
- **单章提取格式、载体记录、同人合并与人物设定跨卷质变记录**：[逐章提取与人物设定整理](references/chapter-extraction.md)
- **故事框架、剧情单元、爽点表、结合制作形态的三类判定与分集候选切法**：[改编价值与分集候选](references/adaptation-value.md)
- **本阶段职责边界与 `NVA` 规则分级**：[阶段规范](references/stage-contract.md)
