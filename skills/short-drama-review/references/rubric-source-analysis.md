# 原著与对标拆解核查清单

用于审查 `项目开发/source-analysis/`（路由 → `short-drama-novel-analyze`）与 `项目开发/对标拆解.md` 及 `输入/对标/<REF-ID>/`（路由 → `short-drama-breakdown`）。

## 1. 原著拆解核查（路由 → `short-drama-novel-analyze`）

- **索引结构与授权拆解范围（`NVA-01`、`NVA-03` · `structural_invariant`）**：
  - 仅当未识别到章节、索引序号断号、行区间未连续覆盖原文，或未声明局部范围却无故漏拆目标区间章节时判结构阻断；
  - **防误杀**：网文常见的作者跳章号/重章号/短卷首语警告**不判阻断**；创作者指定授权章节区间（如前 50 章或第一卷）且汇总显眼标明覆盖章号时，**绝不拿“未拆完全书”一刀切判不过**。抽查 `_index.json` 防章内小节被误切成独立章。
- **抽样守界、提炼概括与原文实据**：
  - `triage.md` 标明抽样比例与实际章号、不越界推断未读章节或提前产出 `episode-candidates.jsonl`（`NVA-05 · reviewed_invariant`）；
  - 拆解以剧情作用概括为主、不整段照搬原著（`NVA-04 · reviewed_invariant`），且概括写清对抉择、信息差、强弱势或关系的实质改变（`NVA-06 · reviewed_invariant`）；
  - 等级、数额、台词归属与出场章号均附原文位置与行号（`NVA-02 · reviewed_invariant`）并可回查核实，原文未写明处标「原文未明确」防脑补串行（`NVA-07 · reviewed_invariant`）；
  - 改编取舍结合目标制作形态写清纯心理/背景的视听改法（`NVA-09 · reviewed_invariant`），分集候选按阶段进展与集尾悬念而非固定章数硬切（`NVA-10 · reviewed_invariant`）。
- **非阻断项**：同人异名归并细节、爽点相对排序属 `craft_default`（最高记 `minor` / `note`）；从哪章开篇、留哪条支线与总集数由创作者与 `short-drama-develop` 拍板（`taste_option`），拆书审查不卡死流程。

## 2. 本地对标拆解与还原核查（路由 → `short-drama-breakdown`）

- **授权登记、脱敏边界与 `还原/` 隔离**：
  - 开测前登记 `REF-ID`、素材位置、授权用途与外传权限，未获准外传仅跑离线脚本（`BRK-01 · reviewed_invariant`）；
  - **防误杀（本地私有 vs 主项目/公开）**：创作者本地私有的 `项目开发/对标拆解.md` **允许写明真实参考剧片名、集数与平台出处**（不因此判违规，仅禁止照抄受版权保护的逐字台词）；但移交主项目的创作文档及公开材料严禁混入 `study` 对标剧的真实剧名、专有角色名、逐字台词或独有桥段（`BRK-02 · reviewed_invariant`）；
  - `输入/对标/<REF-ID>/还原/` 与主项目严格隔离，仅 `owned` / `licensed` 并附依据时才可整套复制为独立项目，严禁把单集还原文件混入主项目剧集目录（`BRK-11 · reviewed_invariant`）。
- **证据口径、可借鉴规律与职责边界**：
  - 拆解结论区分事实、作用分析与盲区，统计注明样本范围、阈值与转写来源（`BRK-03 · reviewed_invariant`）；可借鉴手法注明独立故事数、解决问题与失效条件，单部做法标为个例（`BRK-04 · reviewed_invariant`）；
  - 同尺差距表标清 `plan` 与 `measure` 口径（`BRK-06 · reviewed_invariant`），不把外部对标均值当成卡死交付的门槛（`BRK-07 · reviewed_invariant`），不直接改写其他技能文档（`BRK-08 · reviewed_invariant`）。
- **视频反推还原核查**：
  - 切镜以实测为准、硬字幕台词起止以扫描为准、缺依据项标推断、未点破姓名改身份称呼不编造、非实测吻合的镜内切点单列交人工（`BRK-12 · reviewed_invariant`）；
  - 避敏字/同音错字校对、同场切反应镜不误标 `[OS]`、篇首 `人物：` 补全、原片穿帮归入 `还原核对.md` 与跨集硬切接缝处理属 `craft_default`，偏离仅记 `minor` / `note`，不单独触发 `REVISE`（若《剧本.md》正文残留非法制作标记或违背实测守真边界，按 `SCR-05 · structural_invariant` 或 `BRK-12 · reviewed_invariant` 定级）。
