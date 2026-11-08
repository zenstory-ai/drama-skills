# 原著分析阶段契约

## 所有权边界

- **本阶段拥有**：`项目开发/source-analysis/` 下的章节索引、改编价值快评、逐章提取、剧情单元、节奏情绪、人物与设定候选、改编价值评估与分集候选。
- **本阶段继承**：创作者提供的原始材料与授权说明、项目语言、已接受的形式约束与制作形态。
- **本阶段不越权**：不改写 `输入/`；不写改编契约、创作简报、故事引擎或 `adaptation-map.jsonl`（`$short-drama-develop` 拥有）；不建资产身份；不写场景、台词、分镜与提示词；不生成媒体；不批准自己的产物。

## 本阶段规则

### `NVA`

| ID | Class | Knowledge |
|---|---|---|
| NVA-01 | structural_invariant | All stages slice the source through one chapter index built from that source; `verify` blocks on a chapter set whose numbering, ordering or line spans do not cover that source. An edited source still invalidates the index and everything derived from it, but only a changed line count or numbering is reported — a same-line-count rewrite in place is not, so whoever edits the source re-indexes it. |
| NVA-02 | structural_invariant | Every extracted claim carries a source locator and span; a claim with no span cannot be cited downstream. |
| NVA-03 | structural_invariant | Aggregation may not start while chapter coverage is incomplete; missing chapters are named in every aggregate that inherits the gap. |
| NVA-04 | structural_invariant | Analysis records de-quoted function summaries, never copied source paragraphs. |
| NVA-05 | structural_invariant | A sampled stage states its own coverage and confines every claim to the chapters it read. |
| NVA-06 | reviewed_invariant | A function summary states what a passage does to character choice, information, power or relationship, not what happens in it. |
| NVA-07 | reviewed_invariant | Hard facts — levels, counts, distances, who said what, which chapters a character appears in — trace back to a description line or the source; an unsupported one is written as unstated, never filled in by plausibility. |
| NVA-08 | reviewed_invariant | Character merges preserve dramatic role, knowledge scope, relational position and causal bridge. Proper names, nicknames and name-plus-title forms may merge with evidence of shared identity; generic descriptors or titles alone never establish identity. |
| NVA-09 | reviewed_invariant | Adaptation value distinguishes what the screen can show from what only prose can deliver, and names the new carrier for each function it keeps. |
| NVA-10 | reviewed_invariant | Episode candidates are cut on local dramatic result and precise handoff, not on chapter count or word budget. |
| NVA-11 | craft_default | Triage a deterministic spread of chapters across the whole book and stop for the creator before committing to a full pass. |
| NVA-12 | taste_option | Where to open, which line to keep and which ending to promise remain creator choices; analysis may argue but never blocks. |
| NVA-13 | craft_default | Before cutting episode candidates, rank the book's plot points by audience payoff — face-slap, spectacle, reversal, identity reveal, reward delivered, crisis — counting payoffs a bystander or crowd delivers; candidates follow the payoff distribution rather than one chapter per episode and cite the payoffs they carry. The opening replacement point is the strongest payoff that can also establish the protagonist's identity, crisis and goal, and a stronger later peak is reported as a cold-open option. |
