---
name: short-drama-novel-analyze
description: 把小说、连载网文或多集散稿拆成有据可查的原著拆解：支持全书或按创作者指定章节范围（如前 100 章、第一季）分批完成章节索引、改编价值快评、逐章情节提取、剧情单元与爽点梳理、人物与设定跨卷演进整理，给出结合目标制作形态的改编取舍建议与分集候选，移交 $short-drama-develop 定改编方案。用户说“导入这本小说”“拆这本书”“先拆前一百章”“分析原著”“这本书能不能改短剧”“把小说拆成分集候选”，或直接给出小说文件路径时使用。
license: MIT
---

# 原著拆解分析

从小说原文中拆出有据可查的剧情作用，看每一段戏推动了谁的抉择、揭开了什么秘密、或是扭转了人物强弱关系，并结合目标制作形态评估怎样落进短剧或漫剧改编。支持整本拆解，也支持按创作者指定的章节范围（如前 100 章、第一卷、第一季）分批完整拆解。

## 快速开始

离线验证章节索引、抽样和原文变更检测：

```bash
python3 {技能目录}/scripts/selftest.py
python3 {技能目录}/scripts/novel_index.py index <原著.txt> --out <chapter-index.json>
```

## 开始前与材料前提

- 本技能可独立运行；完整职责范围与规则见 [阶段规范](references/stage-contract.md)。
- 只拆解创作者合法持有、拥有使用权的作品。`输入/` 只读，拆解时不改原文、不整段照抄原句（只记章节位置、起止行号和剧情作用概括，必要佐证只摘最短词句），交付文件不夹带原始全文。
- 通俗题材里的暴力、复仇、背叛、情感拉扯与暗黑冲突照常提取剧情作用；个别片段无法处理时跳过并记明行号范围，不中断整章或整批拆解。

## 先判断入口

1. **只有书名，没有原文**：请创作者提供文件路径或粘贴正文，不凭书名回忆情节。
2. **有原文，未建目录**：建立只读输入目录 `输入/` 与工作目录 `项目开发/source-analysis/_work/`，把原文复制到 `输入/` 后用 `novel_index.py` 建索引。
3. **已有部分拆解结果**：读 `项目开发/source-analysis/_progress.md` 从上次进度接着跑（分批拆解新区间时直接续跑新增章节）。

## 拆解流程

全部产出落在 `项目开发/source-analysis/`（先写进 `_work/` 核对无误后再整份替换写入正式路径，若项目启用了台账也可配合 `project_tool.py`）。

| 阶段 | 做什么 | 产出 | 停顿条件 |
|---|---|---|---|
| S0 | 建章节索引（脚本） | `_index.json`、`_progress.md` | 仅零章节或索引损坏时停 |
| S1 | 改编价值快评（长篇未定范围时抽样） | `triage.md` | 短篇或已指定范围**不暂停** |
| S2 | 目标区间逐章情节提取 | `chapters/ch-<N>-extract.md` | 目标区间缺章时补齐 |
| S3 | 剧情单元汇总与爽点梳理 | `story-units.md`、`rhythm-and-emotion.md` | — |
| S4 | 人物合并与设定跨卷演进整理 | `characters.md`、`world.md` | — |
| S5 | 结合制作形态的改编取舍与分集候选 | `adaptation-value.md`、`episode-candidates.jsonl` | 移交 `$short-drama-develop` |

### S0 章节索引

各阶段共用 [章节索引脚本](scripts/novel_index.py) 建立的章节边界，不各自重新切分：

```bash
python3 {技能目录}/scripts/novel_index.py index 输入/{原文文件} \
  --out 项目开发/source-analysis/_work/_index.next.json
python3 {技能目录}/scripts/novel_index.py verify \
  项目开发/source-analysis/_work/_index.next.json 输入/{原文文件}
```

校验通过后将 `_work/_index.next.json` 写入正式 `_index.json`。脚本支持可选 Markdown 标题前缀（`#`–`######`）、阿拉伯与中文数字章号，按 `章 / 回 / 集 / 话 / 話 / 幕 / 节` 由粗到细自动选定主编号单位（其余记入 `ignored_heading_units`，也可传 `--unit` 指定），剔除开头目录块并分卷核对。

- **区分致命错误与源书常见瑕疵**：网文源书常见的作者跳章号、重章号或简短卷首语归入输出 JSON 的 `warnings` 提醒，脚本保持退出码 `0` 正常放行；只有完全识别不到章节（无章标题散稿，可与创作者约定切分后手写 `sequence` / `line_start` / `line_end` 再过 `verify`）、第一章前遗漏大段楔子正文（可在索引开头补一条 `source_number: null` 记录覆盖第 1 行起的正文），或索引自身断号、行区间断裂时，`problems` 非空并返回非零退出码拦截。原文一旦修改须重建索引。

### S1 改编价值快评

按 [改编价值快评](references/adaptation-triage.md) 执行：
- **短篇小说（如 30 章以内）或创作者已指定拆解范围（如前 100 章 / 第一季）、明确要求直接拆完**：**不在 S1 暂停等待拍板**，直接推进 S2（短篇无需单独停步交快评）。
- **未划定范围的超长篇**：用 `novel_index.py sample --count 12` 等距抽样写出 `triage.md`（首行标明 `coverage_ratio`，结合目标制作形态评估对话与心理描写转化负担），汇报建议拆解范围并请创作者确认。

### S2 逐章情节提取

按 [逐章提取与人物设定整理](references/chapter-extraction.md) 将本批目标区间内的每章拆进 `chapters/ch-<N>-extract.md`（支持并行子任务时每批 5–8 章）。写完后核对覆盖情况：

```bash
python3 {技能目录}/scripts/novel_index.py coverage \
  项目开发/source-analysis/_index.json 项目开发/source-analysis/chapters
```

全书拆解时要求 `complete: true`；按创作者指定章节区间（如 `sequence` 1–100）分批拆解时，核实 `chapters/` 已完整覆盖本次目标区间且无 `unmatched_files` 错名文件即可进入 S3。

### S3 剧情单元与爽点梳理

基于 S2 提取结果（细节不清时按行号回查原文），按 [改编价值与分集候选](references/adaptation-value.md#故事框架与剧情单元) 写出 `story-units.md` 与 `rhythm-and-emotion.md`（含 [爽点表](references/adaptation-value.md#爽点表) 相对先后排序），并在文件开头注明本批覆盖的起止章号范围。

### S4 人物与世界观设定

按 [逐章提取与人物设定整理](references/chapter-extraction.md#人物合并与设定质变记录) 合并有原文实据的同人异名，记录人物立场身份与世界观规则、战力体系的**跨卷质变节点**及首次出场章号（未明确处写「原文未明确」），产出候选名单 `characters.md` 与 `world.md`。

### S5 改编取舍与分集候选

按 [改编价值与分集候选](references/adaptation-value.md#三类判定) 结合目标制作形态评估各剧情单元（区分实拍与动态漫/漫剧对心理吐槽及密集对话的不同承载力），写出 `adaptation-value.md` 与轻量级 `episode-candidates.jsonl`，完成后汇报本批覆盖章数、预计可改集数与主要改编注意点，移交 `$short-drama-develop`（如需独立把关可调 `$short-drama-review` 的 `source_analysis` 范围）。

## 按需加载

- **何时做抽样快评、短篇与指定范围免停规则**：[改编价值快评](references/adaptation-triage.md)
- **单章提取格式、载体记录、同人合并与人物设定跨卷质变记录**：[逐章提取与人物设定整理](references/chapter-extraction.md)
- **故事框架、剧情单元、爽点表、结合制作形态的三类判定与分集候选切法**：[改编价值与分集候选](references/adaptation-value.md)
- **本阶段职责边界与 `NVA` 规则分级**：[阶段规范](references/stage-contract.md)
