---
name: short-drama-novel-analyze
description: 把长篇小说、连载网文或多集散稿拆成可追溯的原著分析：章节索引、改编价值快评、逐章功能提取、剧情单元与节奏聚合、人物与设定归并，最后给出改编价值判定与分集候选，交给 $short-drama-develop 立契约。用户说“导入这本小说”“拆这本书”“分析原著”“这本书能不能改短剧”“先看看值不值得拆”“把长篇拆成分集候选”，或直接给出小说文件路径时使用。只做只读的结构化分析，不写剧本、不建资产、不生成媒体，也不替创作者决定改编方案。
license: MIT
---

# 长篇原著分析

从长材料中提取可追溯的戏剧功能，说明各段如何改变角色选择、信息、权力或关系，以及这些功能怎样用于竖屏短剧改编。

分析结果供创作者取舍：保留哪条线、合并哪些人、从哪里开篇，由创作者决定，再交给
`$short-drama-develop` 写成改编契约。本技能不批准自己的产物。

## Quick Start

离线验证章节索引、采样和源文件变更检测：

```bash
python3 {技能目录}/scripts/selftest.py
python3 {技能目录}/scripts/novel_index.py index <原著.txt> --out <chapter-index.json>
```

## 开始前

本技能可独立运行；若当前目录是 `short-drama` 项目且项目工具可用，可读取 `status` 并使用其发布生命周期。完整边界与规则见 [阶段契约](references/stage-contract.md)，无需读取其他技能的文件。

## 材料前提

只分析创作者**合法持有、拥有使用权**的作品。分析是只读的转化性工作：记录 locator、span 与去引用的功能摘要，不把原文成段复制进分析或下游产物；需要证据时只引用最短必要片段。交付包不得带出原始材料。

通俗题材里的暴力、复仇、背叛、情爱张力与黑暗伦理照常做结构化提取。个别片段无法处理时跳过该段并记录范围，不中止整章或整本。

## 先判断入口

1. **只有书名，没有原文**：请创作者提供文件路径或粘贴正文，不凭书名回忆情节。
2. **有原文，未建项目**：建立只读输入目录 `输入/` 与输出目录 `项目开发/source-analysis/_work/`，把原文字节复制到 `输入/` 并记录原始位置，再用 `novel_index.py` 建索引（`$short-drama` 可用时可选用它初始化目录）。
3. **有原文，项目已在**：直接进入管道。
4. **已有部分分析**：读 `项目开发/source-analysis/_progress.md` 从断点续跑，不重跑已完成阶段。

## 管道

`输入/` 只读，全部产出落在 `项目开发/source-analysis/`。S1–S5 的产物均先写到 `source-analysis/_work/`（并发子代理只写 `_work/`），主线程完成本阶段机械检查后再原子替换或通过 `project_tool.py publish` 发布到正式路径。`_progress.md` 跨阶段共用固定 artifact-id `source-analysis:progress`。

| 阶段 | 做什么 | 产出 | 停靠 |
|---|---|---|---|
| S0 | 建章节索引（脚本） | `_index.json`、`_progress.md` | 索引有问题就停 |
| S1 | 改编价值快评（抽样） | `triage.md` | **停靠问创作者** |
| S2 | 逐章功能提取 | `chapters/ch-<N>-extract.md` | 覆盖率不足就停 |
| S3 | 剧情单元与节奏聚合 | `story-units.md`、`rhythm-and-emotion.md` | 阈值不达标就复核 |
| S4 | 人物归并与设定 | `characters.md`、`world.md` | — |
| S5 | 改编价值与分集候选 | `adaptation-value.md`、`episode-candidates.jsonl` | 交接 develop |

### S0 章节索引

各阶段共用 [章节索引脚本](scripts/novel_index.py) 建立的章节边界，不各自重新切分。

```bash
python3 {技能目录}/scripts/novel_index.py index 输入/{原文文件} \
  --out 项目开发/source-analysis/_work/_index.next.json
python3 {技能目录}/scripts/novel_index.py verify \
  项目开发/source-analysis/_work/_index.next.json 输入/{原文文件}
# 项目工具可用时可选：
python3 {core 技能目录}/scripts/project_tool.py publish {项目根} \
  --owner short-drama-novel-analyze --artifact-id source-analysis:index \
  --output 项目开发/source-analysis/_index.json=项目开发/source-analysis/_work/_index.next.json \
  --input 输入/{原文文件}
```

独立运行时，将验证通过的 `_work/_index.next.json` 原子替换到正式的 `_index.json`，再进入 S1。

脚本识别阿拉伯数字与中文数字章号（含 千 / 两），**只认一种编号单位**（按 章、回、节 由粗到细，取最粗且至少出现两次的单位，其余记进 `ignored_heading_units`），只把**短的独立行**当标题（以章号开头的正文段落记进 `long_heading_lines_skipped`），剔除开头目录块并按卷分段校验编号。

`problems` 非空就停下报告，不带错表进 S1。常见五种：章号跳号、同卷内重号、正文极少的章（目录残留或卷首页）、无法解析的章号、第一章前有大段未归属文字（`text_before_first_chapter`，不含目录行；确认是楔子后在 `_work/_index.next.json` 开头手写一行从第 1 行起覆盖，`source_number` 留 `null`，其余 `sequence` 顺延加一再跑 `verify`）。另核对 `chapter_unit` 与 `ignored_heading_units`（防用 `第N章` 分章、`第N节` 分小节的书被反判），以及 `long_heading_lines_skipped`（明显偏大时与创作者确认是否长标题并手写边界）。

原文无章节标题时索引返回空表，与创作者确认切分方式后把边界（含 `sequence` / `line_start` / `line_end`）写入 `_work/_index.next.json`，通过 `verify` 后发布。改了原文必须重建索引（`verify` 查章号与行号覆盖，不查同行数原地改写）。

### S1 改编价值快评

按 [改编价值快评](references/adaptation-triage.md) 用 `novel_index.py sample --count 12` 抽样评估改编密度并写出 `triage.md`（首行写 `coverage_ratio`，结论限于抽样范围）。写完后给出快评与全量拆解预计耗时，**停靠问创作者是否继续**（`_progress.md` 状态写 `paused_after_triage`，断点写「下一步：S2 逐章提取」）；创作者已声明「一次跑完」时仍写 `triage.md` 供 S5 回填对照，但不停靠。

### S2 逐章功能提取

按 [章节提取](references/chapter-extraction.md) 提取每章到 `chapters/ch-<N>-extract.md`（`<N>` 为索引 `sequence`）。能并发子代理则每批 5–8 章并发，否则串行。全部落盘后检查覆盖率：

```bash
python3 {技能目录}/scripts/novel_index.py coverage \
  项目开发/source-analysis/_index.json 项目开发/source-analysis/chapters
```

先修正 `unmatched_files` 中的命名错误，再补跑 `missing` 章。单章连续失败两次先记入 `_progress.md` 继续提取其余章，S2 结束前统一补齐；**仍有缺章时停在 S2 报告缺失范围，不进入 S3**。

### S3 剧情单元与节奏

从逐章提取聚合（事实或指代不清时按定位回查原文，不通读全书）。按 [聚合与实体](references/aggregation-and-entities.md) 先识别故事框架，再产出 `story-units.md` 与 `rhythm-and-emotion.md`（含按观众收益排名的爽点表），最后执行三条阈值自检与散落情节兜底。

### S4 人物与设定

按 [聚合与实体](references/aggregation-and-entities.md) 归并人物（跨章去重、别名归一、分级）并归纳世界规则、力量体系与势力。人物归并条目带 `unresolved` 与来源引用，仅为供 `$short-drama-develop` 决策的**候选**；正式资产身份须等 `$short-drama-write` 写进剧本后由 `$short-drama-assets` 建立。

### S5 改编价值与分集候选

按 [改编价值](references/adaptation-value.md) 产出 `adaptation-value.md`（开头回填对照 S1 快评中印证或推翻的判断）与 `episode-candidates.jsonl`（按爽点分布、当集戏剧结果与精确交接切分，样例见 [分集候选样例](assets/episode-candidate.example.jsonl)）。

### 交接

S5 完成后向创作者汇报拆解章数、跳过范围、候选集数、三处最大改编风险及快评对照结果，再交给 `$short-drama-develop` 生成 `项目开发/adaptation-map.jsonl` 与改编契约。需要独立审查时调用 `$short-drama-review`（范围 `source_analysis`）。

## 产物与边界

本技能只拥有 `项目开发/source-analysis/` 下的阶段产物（见上表），不改写 `输入/`、不写其他技能产物、不签发终审结论；分析产物语言跟随 `short-drama.json#/language`（独立运行时跟随用户语言），详见 [阶段契约](references/stage-contract.md)。

## 按需加载

- **快评读哪些章、写哪六件事、怎么不冒充全量分析**：[改编价值快评](references/adaptation-triage.md)
- **逐章提取写法、白描与叙事框架词的界线、机械自检、并发与串行**：[章节提取](references/chapter-extraction.md)
- **故事框架、剧情单元、节奏情绪、人物归并、阈值与散落兜底**：[聚合与实体](references/aggregation-and-entities.md)
- **改编价值评估、载体替换与分集候选切法**：[改编价值](references/adaptation-value.md)
- **本阶段拥有什么、继承什么、不越权什么**：[阶段契约](references/stage-contract.md)
