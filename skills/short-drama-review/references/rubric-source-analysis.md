# 原著与对标拆解核查清单

用于审查 `项目开发/source-analysis/` 下由 `$short-drama-novel-analyze` 产出的原著拆解文档（`_index.json`、`triage.md`、`chapters/*.md`、`story-units.md`、`rhythm-and-emotion.md`、`characters.md`、`world.md`、`adaptation-value.md`、`episode-candidates.jsonl`），以及由 `$short-drama-breakdown` 产出的 `项目开发/对标拆解.md`。

## 1. 章节索引与授权拆解范围核对（`NVA-01`、`NVA-03`）

通过 `$short-drama-novel-analyze` 的索引覆盖核查（或直接对照 `_index.json`、`chapters/` 与原文行号）核验章节切分与拆解覆盖边界：

- **索引结构核验（`NVA-01 · structural_invariant`）**：`$short-drama-novel-analyze` 的索引覆盖核查报错（如未识别到章节、索引序号断号或行区间未能连续覆盖原文）时判结构阻断，退回 `$short-drama-novel-analyze` 重建索引；网文原文常见的作者跳章号、重章号或过短过渡章仅归入提醒，**不因原文跳号提醒直接判阻断**。抽查 `_index.json` 的章节切分尺寸，防止把章内小节误切成独立章。
- **支持按创作者授权章节范围拆解（`NVA-03 · structural_invariant`）**：创作者指定只拆解授权章节区间（如前 50 章、第一卷或选定篇章）时，只要 `chapters/` 完整覆盖了**创作者本次划定的目标章节范围**，且汇总文档显眼注明了所覆盖的起止章号范围，即视为合规通过，**绝不拿“未拆完全书所有章节”一刀切判不过**。只有既未声明局部拆解范围、又无故漏拆目标区间内章节或混入无关凑数文件时，才报覆盖缺漏。

## 2. 抽样快评守界、概括提炼与原文对账（`NVA-02`、`NVA-04`、`NVA-05`、`NVA-07`）

- **`triage.md` 抽样范围守界（`NVA-05 · reviewed_invariant`）**：开头须写明抽读比例与实际抽读章号，评估统计仅基于已读抽样章节，不凭空推断未读章节，快评阶段也不提前越界产出 `episode-candidates.jsonl`。
- **提炼概括与引文克制（`NVA-04 · reviewed_invariant`）**：核查拆解文档是否以提炼后的剧情作用概括为主，必要佐证仅摘取最短关键短语，不整段照搬抄录原著句子。
- **回查原文防脑补与串行（`NVA-02 · reviewed_invariant`、`NVA-07 · reviewed_invariant`）**：抽查 `characters.md`、`world.md`、`adaptation-value.md` 中的等级体系、数额距离、关键台词归属与首次出场章号是否附有原文位置与起止行号（`NVA-02 · reviewed_invariant`）并能回查印证（`NVA-07 · reviewed_invariant`）。原著未写明却被脑补成确定事实的，退回 `$short-drama-novel-analyze` 改为「原文未明确」或删去；重点排查把甲的台词安到乙头上或抄串相邻章节数字。

## 3. 逐章提炼、人物归并与影视化切集（`NVA-06`、`NVA-08`–`NVA-13`）

- **逐章提炼与同人合并（`NVA-06 · reviewed_invariant`、`NVA-08 · craft_default`）**：逐章情节点须写出具体动作或交锋如何改变了人物抉择、信息差、强弱势地位或人物关系（`NVA-06 · reviewed_invariant`），不拿“展现了惊人实力”“心中愤怒”充数；`characters.md` 不得单凭泛称（“红衣女子”“护卫统领”）草率合并人物，合并绰号与本名须有原文证据（`NVA-08 · craft_default`）。
- **影视化改法与切集依据（`NVA-09 · reviewed_invariant`、`NVA-10 · reviewed_invariant`、`NVA-12 · taste_option`、`NVA-13 · craft_default`）**：原著纯心理或背景说明若保留入戏，须写明改用什么可见动作、物证或场面表现，不能换汤不换药全推给大段旁白（`NVA-09 · reviewed_invariant`）；分集候选先按爽感与看点强度标注看点（`NVA-13 · craft_default`），再按单集阶段进展与集尾悬念切分而非按固定章数字数机械平分（`NVA-10 · reviewed_invariant`）。正式从哪章开篇、留哪条支线与总集数由创作者与 `$short-drama-develop` 拍板，拆书审查不拿创作取舍卡死流程（`NVA-12 · taste_option`）。

## 4. 本地对标拆解审查边界（`项目开发/对标拆解.md`）

审查 `$short-drama-breakdown` 产出的本地对标学习报告、差距表与还原项目时，严守以下边界：

- **对标登记、授权用途与外传边界（`BRK-01 · reviewed_invariant`）**：核查每部对标作品开测前是否登记了 `REF-ID`、素材位置、授权用途（`study`、`owned` 或附有依据的 `licensed`）及是否允许上传外部模型服务；未获准外传的作品只允许运行本机离线测量脚本。
- **本地私有拆解允许写真实参考剧片名但禁抄逐字台词（`BRK-02 · reviewed_invariant`）**：`项目开发/对标拆解.md` 属于创作者本地私有的研究与学习记录，**允许直接写明真实参考剧片名、集数与平台出处**以便创作者直观核对，不因本地拆解报告写了真实剧名判违规（仅在对外公开发布或入库公开示例时才要求脱敏）；**但本地 `对标拆解.md` 自身仍不得照抄受版权保护的逐字台词**。
- **主项目脱敏边界、统计口径、规律提炼与职责转交（`BRK-02`–`BRK-04`、`BRK-06`–`BRK-08`）**：核查移交主项目的 `creative-brief.md`、`story-engine.md`、《剧本.md》《视觉设定.md》及各类提示词是否只提炼了节奏结构与视听手法，**严禁将学习用途对标剧的真实剧名、专有角色名、独有世界观名词、原句台词或受保护的独创桥段带入主项目文档**（`BRK-02 · reviewed_invariant`）；核对拆解结论是否区分实测与画面事实、作用分析和待确认盲区，引用统计数字是否注明样本集范围、切镜阈值与字幕转写来源（`BRK-03 · reviewed_invariant`）；核对每条可借鉴手法是否写明了在几部独立故事中出现过、解决了什么观看问题及何时失灵，单部作品做法是否如实标为单部个例（`BRK-04 · reviewed_invariant`）；核对同尺差距表是否标清了纸面估算（`plan`）与成片实测（`measure`）两种计算方式（`BRK-06 · reviewed_invariant`），未把外部对标均值硬当成卡死本项目的强制门槛（`BRK-07 · reviewed_invariant`），且对标技能未直接动手改写其他技能负责的文档——需补强的差距附实测依据转交对应负责技能，疑似有意取舍的差异单列供创作者定夺（`BRK-08 · reviewed_invariant`）。
- **`还原/` 独立隔离、版权准入与实测还原守真（`BRK-11 · reviewed_invariant`、`BRK-12 · reviewed_invariant`）**：核查 `输入/对标/<REF-ID>/还原/` 是否与主项目严格隔离——主项目各创作环节不得读取 `还原/` 充当素材，单集还原文件严禁直接混入外层主项目的剧集目录；仅当明确登记为自有（`owned`）或已获授权（`licensed`）并写明依据时，才能整套复制成独立项目或在其内部迭代开发（`BRK-11 · reviewed_invariant`）。同时核查还原稿中切镜时间是否以脚本实测为准、有烧录字幕的台词起止是否以字幕扫描为准，无烧录字幕台词时间、未点破姓名和看不清细节是否标为推断，模型报出但未与实测候选吻合的镜内切点是否单列交人工判断，缺乏名条、字幕或台词称呼实锤的角色是否改用身份称呼而未编造人名（`BRK-12 · reviewed_invariant`）。
- **视频反推剧本的台词校对、正文洁净度与跨集接缝（`BRK-13`–`BRK-16 · craft_default`）**：审查从视频反推的 `还原/剧集/EPxxx/剧本.md` 与 `还原/审查/还原核对.md` 时，核查：（1）硬字幕避敏字、消音打码词、同音错字或同音专名异写、配音漏字、残留第三人称小说旁白及配乐人声采样是否已结合音画校对并在 `还原核对.md` 记下依据（`BRK-13`）；（2）同场当面交谈切向反应特写时是否未误标 `[OS]`，闭口心声与跨镜声桥是否按实际说话人标 `[VO]`（`BRK-14`）；（3）篇首 `人物：` 行是否列全零台词的关键在场人物，物证/面板上的局部生成错字与原片无意穿帮是否已在正文写顺、核对说明归入 `还原核对.md`，未把 `[待核实]` 等工作标注留在《剧本.md》正文里（`BRK-15`）；（4）集尾 `END` 帧与低阈值切点场次、闪回段落及定长硬切跨集对话是否衔接清楚（`BRK-16`）。以上 `craft_default` 偏离只记 `minor` 或 `note`，不单独触发 `REVISE`（正文中残留非法工作标记或违背实测边界时，按 `SCR-05` 或 `BRK-12` 定级）。
