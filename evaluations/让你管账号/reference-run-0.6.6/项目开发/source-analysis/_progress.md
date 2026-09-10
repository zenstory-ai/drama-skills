# 原著分析进度

- **原著**：`输入/长篇-让你管账号，你高燃混剪炸全网.txt`
- **章节总数**：20（`chapter_unit: 章`，索引与 `verify` 均无 problems）
- **状态**：`completed`（S0–S5 全部完成，等待创作者确认与 `$short-drama-develop` 接手）
- **断点**：下一步：交接 `$short-drama-develop`，由它把候选变成 `项目开发/adaptation-map.jsonl` 与改编契约

## 阶段

| 阶段 | 状态 | 产出 | 闸门结果 |
|---|---|---|---|
| S0 章节索引 | 完成 | `_index.json` | index/verify 均 `problems: []` |
| S1 改编价值快评 | 完成 | `triage.md` | 抽样 12/20，`coverage_ratio 0.6` |
| S2 逐章功能提取 | 完成 | `chapters/ch-1..20-extract.md` | `coverage complete: true`，`missing: []`，`unmatched_files: []`；20/20 章机械自检一次通过 |
| S3 剧情单元与节奏 | 完成 | `story-units.md`、`rhythm-and-emotion.md` | 归属置信 ≈0.90、覆盖率 100%（触发小体量例外条款）、重叠率 ≈9% |
| S4 人物与设定 | 完成 | `characters.md`、`world.md` | — |
| S5 改编价值与分集候选 | 完成 | `adaptation-value.md`、`episode-candidates.jsonl` | 12 条候选，全部 `creator_acceptance: pending` |

## 失败与跳过记录

**无。** 20 章全部提取成功，无重试、无跳过章。因此所有聚合产物均不含缺章声明。

## 备注

- 创作者已声明「一次跑完」，S1 写出 `triage.md` 后未停靠等待，直接进入 S2。
- S5 已回填快评：六段中五段被印证，一段（制作负担里的空间数量）被推翻，
  原因写在 `adaptation-value.md` 开头。
- 全部 Agent 创作产物先写 `_work/`，机械检查通过后由主线程用 `project_tool.py publish`
  发布到正式路径；`_work/` 不进入交付包。
