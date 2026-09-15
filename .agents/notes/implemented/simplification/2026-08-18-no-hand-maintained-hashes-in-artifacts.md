# Agent Note: 产物里不写任何人工维护的哈希

Status: implemented

## Problem

产物引用曾是 owner + artifact + hash 三元组，`derivation`、`end_report`、验收记录里还各带一批 sha256。Golden Sample 里 2470 个引用对象解析到 571 个快照，`sources` 一项就有 729 个手工维护的哈希；清点时样例里 331 个此类值全部与字节对不上，而 `asset_check` / `image_prompt_check` / `review_check` 只校验哈希的格式，从不重算。效果是：改一行上游要重算整条下游链（一次 episode-map 缩表引发 17 处重绑），漏算不报错，样例始终以 accepted 的姿态呈现自己。

## Decision

创作产物——JSON、JSONL、Markdown 模板与样例——never 携带由人填写的字节摘要。引用形状是 `owner + artifact`，或文件级声明一次的 `{"src": ..., "record_id": ...}`；`sources` 只记录派生来源，派生关系 must 无环，同层互相指名合法。退役键名（`content_sha256`、`input_hashes`、`rendered_hash`、`record_hashes`、`target_hashes` 等）列在 `tests/test_golden_project.py` 的 `RETIRED_DIGEST_KEYS`，三条断言分别覆盖样例 JSON/JSONL、技能 JSON/JSONL 与 `assets/*.md`、按字面扫描 `skills/**/*.md`；加回任何一个键直接红。

工具自己维护、自己比对、不进产物的哈希保留：生命周期状态里的字节记录（`update_needed` 靠它）、交付包 `checksums.sha256`（`verify` 靠它）、生产任务的输入指纹。判据只有一条：是否有脚本回头核对它。

来源：61dc22e、d960676、9be5544、1313c97、0270ca3、de51d04、3d647a5、e79c809、1301caf、fd8528a、42696db

## Alternatives considered

- **保留哈希链，每次上游改动重新绑定** — 最强理由：验收记录钉住的是被接受时的字节，这是「以当前形态被接受过」的唯一证明。被否：手工重算等于改写历史，且让迁移不再幂等（d960676），于是同一天 revert（9be5544）；而不重算就永远卡住编辑。两条路都走过一遍。
- **每文件声明一次快照、引用只带 record_id（#39，55f5c1e）** — 剧集目录字节减少 23.7%，模型要抄的 64 位十六进制从 510 降到 8。但哈希仍要人维护、仍无人核对，两天后连同整条链一起删除。
- **只删消费端、保留生产端写入** — `build_index` 仍往 `sources` 写哈希，签入的索引与构建器产出不一致（de51d04），两端都删。

## Consequences

- **收益**：编辑上游的下游代价为零——同一处 episode-map 改动在删链后 `compact_refs` 零重写、verdict 绑定不受影响（927e3b8 实测）。
- **代价（逐条实跑核对，1301caf）**：创作者验收不再钉字节；剧本索引按内容保 ID 改由 `--previous-index` 与 `block_id_high_water` 承担；原著漂移检测退化为长度与行号核对，同长度原地改写不报；`VOICE_INDEX_IS_STALE_AGAINST_SCREENPLAY` 诊断码不存在。
- **重访信号**：要恢复某项能力时先实跑确认它真的丢了，不要按字段名想象——CHANGELOG 曾把损失写大，下一个人会为「恢复」一个没丢的能力把哈希加回来。
