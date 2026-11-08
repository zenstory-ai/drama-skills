# 原著分析审查表

审查 `项目开发/source-analysis/` 下由 `$short-drama-novel-analyze` 发布的产物（`_index.json`、`triage.md`、`chapters/*.md`、`story-units.md`、`rhythm-and-emotion.md`、`characters.md`、`world.md`、`adaptation-value.md`、`episode-candidates.jsonl`），按 `NVA-xx` 规则编号定位问题。

## 1. 先跑结构校验（`NVA-01`、`NVA-03`）

```bash
python3 {novel-analyze 技能目录}/scripts/novel_index.py verify \
  项目开发/source-analysis/_index.json 输入/{原文文件}
python3 {novel-analyze 技能目录}/scripts/novel_index.py coverage \
  项目开发/source-analysis/_index.json 项目开发/source-analysis/chapters
```

- `verify` 失败（`NVA-01`）或 `_index.json` 的 `problems` 非空却进入后续阶段：阻断并要求先修索引。
- `coverage` 的 `missing` 非空而聚合产物已生成（`NVA-03`），或 `unmatched_files` 非空：阻断并点名缺失章节与未匹配文件名（不得将其他阶段文件改名充数）。
- 对照原文抽查 `_index.json` 的 `chapter_unit` 与 `ignored_heading_units` 是否切准章节边界（如按 `第N章` 分章的书误选 `节`）。

## 2. 抽样声明与事实溯源（`NVA-02`、`NVA-05`、`NVA-07`）

- **`triage.md` 抽样边界（`NVA-05`）**：首行须写明覆盖率与样本章号，三类判定比例分母须为抽样章数，不得断言未抽样章节的事实，也不得越权产出 `episode-candidates.jsonl`。
- **两层溯源与防串用（`NVA-02`、`NVA-07`）**：抽查 `characters.md`、`world.md`、`adaptation-value.md` 中的等级、数值、距离、势力数、台词归属与出场章号，逐条回查引用的逐章白描与原文。回查不到却写成确定事实的判 `reviewed_invariant` 缺陷（须改为「原文未明确」或删除）；同时排查坐骑/骑手等级混安、A/B 台词串记、相邻章数字互换。

## 3. 功能提取与归并质量（`NVA-06`、`NVA-08`）

- **逐章提取（`chapters/ch-<N>-extract.md`，`NVA-06`）**：概要须回答“谁的处境、认知或筹码变了”；情节点白描须为可观察事实（禁把“通过对话得知”“展现了实力”“感到愤怒”等结论词当证据）；每条须写明改变了权力/信息/关系/暴露/资源/时间/代价中的哪一项，且填齐载体记录与通道栏。
- **人物与单元归并（`NVA-08`）**：`characters.md` 不得仅凭描述性称谓（「红衣女子」）或泛指头衔（「护卫队长」）合并人物，绰号或姓氏+头衔合并须有明确同指证据，每条保留戏剧作用、知识范围、关系位置、`unresolved` 与来源引用。`story-units.md` 须写出归属置信、覆盖率与重叠率自检结果，重叠率超线无复核说明时点名具体单元对。

## 4. 改编判定与候选集（`NVA-09`、`NVA-10`、`NVA-12`、`NVA-13`）

- **三类判定与载体转换（`NVA-09`）**：逐单元落定三类判定；`needs_carrier` 必须写齐原载体、新载体、保住项及改变/失去项（将改变/失去写为「无」视为未写完）；禁止将 `prose_only` 改写为仍需旁白才成立的 `needs_carrier`。
- **单集候选集（`NVA-10`、`NVA-13`）**：按戏剧结果与交接切分（非按章号或字数均切），每条回答四问（进入认知、兑现哪项承诺、出去压力、下集继承项），相邻候选进出状态闭合，`prose_only`/跳章/散落清单记入交接摘要，`adaptation-value.md` 开头含快评回填对照，爽点表与候选集按观众收益引用并考虑后文强冷开（`NVA-13`）。
- **边界（`NVA-12`）**：从何处开篇、保留哪条支线、合并哪些人物及总集数归创作者与 `$short-drama-develop` 决定，不作为分析层阻断项。
