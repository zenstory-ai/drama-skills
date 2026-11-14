# Agent Note: 松绑过严脚本与流程门禁、重定级阶段规则并归并碎片化参考文档

Status: implemented

## Problem

在完成全仓去黑话与契约中文化（见 [全仓消除 AI 黑话与五份创作文档字段破坏性重命名](./2026-11-14-eliminate-ai-jargon-and-breaking-field-renames.md)）后，对 13 个技能共 194 个指令、模板与脚本文件的逐文件审查暴露出四类系统性负担：

1. **旧版台账仪式与机械字面门禁残留**：
   - `$short-drama` 的 `project_tool.py` 修改项目配置（画幅、集数、制作形态、节奏目标）仍要求绕行 `输入/*.jsonl -> publish -> accept -> set-authority` 四步流程，`package` 仍要求所有文件走完 `publish + accept + review approve`，与创作者直接编辑五份 Markdown、按需送审的主工作流脱节；
   - `creator_markdown_check.py` 将多项创作层或双语特定探针写成了无条件报错（缺 `short-drama.json` 时硬绑 `"en"` 逼填 `- 提示词名称：`、扫描 `SHOT.来源` 台词引文逼标 `；画外：`、引号内 `>=4` 个汉字一律判幻觉台词、强制 `MOTION.开场画面` 原字子串粘贴进提示词、强制已挂起始帧的图生视频也原字粘贴全身静态 `LOCK-...`、禁止正反打复用同一预留首帧、强制条目标题含汉字与无对白角色必填声线）；
   - `$short-drama-produce` 的 `production_tool.py` 对整份 Markdown 文件算 SHA-256（改第 30 镜一字导致前 29 镜任务连坐失效），限制单次单输出确认，且 `provider_adapters.py` 在未设可选环境变量时直接报错、与文档默认值表冲突；
   - `$short-drama-write` 估时需手搓三步临时目录备份、`novel_index.py` 因网文作者跳章直接返回非零退出码、`episode_intake.py` 拒绝非第 1 集起步或更新已有集、`edit_tool.py` 与 `rules.mjs` 因 `<0.50s` 快闪静帧、抢话叠音、`st_mtime` 变动、进度条 `,/` 字符或单个 Emoji 就硬阻断渲染。
2. **规则分级膨胀与下游审稿越级判死**：10 份 `stage-contract.md` 的 199 条规则中，大量无确定性脚本支撑的语义要求被标为 `structural_invariant`，普通爽剧/视听默认手艺被标为阻断级的 `reviewed_invariant`，并残留 `CON-04/06`、`REV-11`、`BRK-09`、`VID-09/18`、`EDT-15` 等旧版台账或重复口号；`$short-drama-review` 又把上游固定镜头、画风前缀位置与日常旧化材质词私自升格为“直接判不过”。
3. **五层跨文件复读与碎片化微参考文件**：同一规则在 `knowhow-index.md`、`stage-contract.md`、`SKILL.md`、`references/*.md`、`rubric-*.md` 中重复维护多遍；大量 `references/*.md` 不足 40 行，并残留零引用的孤立样例文件。
4. **过拟合绝对化教条、浅显常识与维护者枷锁**：如封杀拿已确认首帧改图派生同机位连戏镜头、`minimax-h3.md` 强制跨两镜说话角色切入禁用首帧的 `full-reference`、把英语语法套给所有外语、15 张题材卡将单一网文桥段写死为铁律、本地私有 `对标拆解.md` 禁写真实参考剧名、反复刷屏诚实性套话与极端稻草人反例，以及 `$short-drama-knowhow` 要求连降级/删除坏规则都必须重跑双盲评测与维护死哈希台账。

本决定部分翻转并更新以下早期笔记中的局部决定：
- [规则四级分级与脚本边界](../architecture/2026-07-16-rule-tiers-and-script-boundary.md)、[每集只保留至多五份创作者文档](../architecture/2026-08-22-creator-first-five-documents.md) 与 [私有 knowhow 技能与受保护发布门禁留在公共树之外](../process/2026-07-21-private-knowhow-and-protected-release-gate.md)（落实脚本边界原则，撤回越界脚本拦截、错标等级、无前置审核不可打包的限制与过重的维护者台账门禁）
- [跨文档检查支持局部核对、交付分组与「入画」锁范围](../feature/2026-10-20-partial-check-groups-in-frame-locks.md)、[缺参考图时默认写 PLAN 挂图计划](../feature/2026-10-29-plan-slots-by-default.md)、[视频提示词绑定角色参考音频](../feature/2026-09-28-voice-reference-binding.md)、[出片实测沉淀：空间、音色与切点](../feature/2026-11-06-generation-continuity-learnings.md) 与 [出片实测复盘（二）：比例、共用段落、镜内切、电话声与按集拆批](../feature/2026-11-10-generation-learnings-scale-and-shared-blocks.md)（保留核心结构能力，松绑 `来源` 台词引文连坐、无引导词引号拦截、`开场画面` 子串粘贴、图生视频强制贴静态 `LOCK`、`PLAN-...` 跨镜复用限制、`参考音频` 控制范围词表死锁与 H3 锁音色一刀切，并同步归并参考文件）
- [剪辑单的静帧段、运镜与配音](../feature/2026-09-28-edit-still-cuts.md)、[配音与字幕跨切点、有声区间与起点](../feature/2026-09-28-edit-voice-across-cuts.md)、[剪辑把反应压在台词上，群戏不再一人一句地轮流](../feature/2026-10-29-edit-reaction-overlap.md)、[对标拆解技能，以及 9 部 App 连播漫剧实测带来的补强](../feature/2026-11-03-benchmark-breakdown-skill.md) 与 [对标拆解增加还原层——一集或多集还原成剧本、物料与提示词](../feature/2026-11-04-breakdown-private-reconstruction.md)（松绑短静帧与短尾音抢话交叠拦截、本地私有 `对标拆解.md` 参考剧名记录及 `BRK` 规则分级）
- [全量精简技能指令中的人类培训说教、低频分支、空泛套话与重复规则](./2026-11-07-prune-redundant-and-low-signal-skill-instructions.md)（在其单文件去重基础上进一步推进跨层去重与同技能内微文件归并）

## Decision

1. **脚本与工具链门禁松绑（回归确定性结构服务）**：
   - `creator_markdown_check.py`：未建 `short-drama.json` 时按去引文后的提示词正文实际汉字/拉丁字母比例推断语言（回退已有中文文档）而非硬绑 `"en"`；允许纯外文条目标题与参考名称；无台词角色免强制填写 `角色声线`；不再扫描 `SHOT.来源` 台词引文逼标 `；画外：`（仅核对首尾帧提示词与文生开场画面实际点名的设定对象）；`图片提示词项` 改为可选；允许未垫图阶段简写 `- 输入参考图：无` 及正反打复用已存在的 `PLAN-...` 镜头首帧；参考图去重键改为 `(path, role)` 以支持首尾同帧循环镜同时挂 `起始帧 + 结束帧`；放宽 `- 参考音频：` 的 `控制/不得控制` 固定词集合死锁；允许 `MOTION.输入参考图` 在分镜基础上按视频生成需要增减；`LOCK-...` 仅强制覆盖静态图片提示词、首帧提示词与**未绑定 `起始帧` 或 `主体` 参考图的文生视频** `MOTION`/`GROUP`；移除 `开场画面` 逐字子串粘贴检查，并将台词一致性检查收窄到带说话引导词或 `<d>` 标签的显式角色对白。
   - `project_tool.py`：新增 `configure` 子命令直接增量写入 `short-drama.json`（支持语言、画幅、集数、制作形态与可选节奏目标），`package` 直接打包五份创作 Markdown 与 JSON/JSONL 文本产物，不强制前置 `publish/accept/review` 仪式（不打包 `.mp4` 等成片媒体）；将纯测试用 `creator-decision.example.jsonl` 迁入 `tests/fixtures/authoring-records/`，清理孤立的观测样例 JSONL。
   - `production_tool.py` 与 `provider_adapters.py`：存在 `source_entry` 时改为计算对应 Markdown 二级标题段落的**条目级 SHA-256**（改单镜不再连坐作废整集）；新增 `prepare-batch` 与 `run-batch` 批次模式，将本地参数预检前置到核销确认码之前；取消参考标签必含汉字限制，将输入参考去重粒度由 `path` 改为 `(path, role)`（与 `creator_markdown_check.py` 一致，支持首尾同帧循环镜把同一张图同时绑为 `起始帧 + 结束帧`），支持从源 Markdown 自动提取提示词与参考绑定；生图单任务输出上限 `max_outputs` 放宽至 `1..16`，可选环境变量未设时回退内置合法范围，内置识别 `seedance` 与 `minimax-h3` 的 `reference_audio` 能力，且不在已有原生参考槽位的提示词末尾暗拼重复说明尾巴。
   - 阶段辅助脚本：`duration_estimate.py` 新增 `--script <剧本.md>` 单命令直跑并支持含空格外文人名、半角括号与 40 字说话人上限；`novel_index.py` 支持 Markdown `#` 章节头与 `集/话/幕`，将作者跳章、重号与短章移入 `warnings` 并返回退出码 `0`；`episode_intake.py` 支持非 `EP001` 起步、跳集与 `merge` 更新已有集，移除模板重复状态数组；`breakdown_tool.py` 跳过外部 SRT 中 `start >= end` 废行并输出告警；`edit_tool.py` 与 `rules.mjs` 新增无框 `字卡` 图层、`--partial` 局部试剪与 `- 重放：<理由>` 显式复用豁免，允许短尾音抢话交叠，同宽高比不同分辨率/帧率素材自动缩放对齐，补齐 `,/` 归一化，将 `<0.50s` 静帧与 `st_mtime` 变动降为 `提醒`，并过滤非 BMP Emoji 及对齐 `—…‘’“”` 宽度防止字体渲染崩溃。
2. **规则重定级与审稿对齐**：
   - 清理 10 份 `stage-contract.md` 中的旧版台账与重复僵尸项（移除 `AST-04`、`CON-04/06`、`IMG-12/14`、`SHT-27`、`VID-09/18`、`REV-11`、`BRK-09`、`EDT-15` 及英文枚举残留），将无脚本支撑的伪 `structural_invariant` 与过严剧作技法分别回调至 `reviewed_invariant` 与 `craft_default`。
   - 撤回 `$short-drama-review` 在 `rubric-*.md` 中对 `运镜：固定`、日常旧化材质词（`worn/dusty/斑驳`）与 `IMG-02` 画风前缀位置的越级自动判死，新增成片审查 `major` 严重度缓冲档。
3. **跨层去重与技能内微文件归并**：
   - 将 `knowhow-index.md` 压缩为纯阶段问题路由表，不再抄写各技能内部细则。
   - 在各技能目录内部归并碎片微文件与孤立模板（`short-drama` 10→6、`short-drama-novel-analyze` 5→4、`short-drama-develop` 13→10、`short-drama-write` 8→5、`short-drama-assets` 11→4、`short-drama-image-prompts` 10→3、`short-drama-storyboard` 13→6、`short-drama-video-prompts` 13→9、`short-drama-review` 10→7、`short-drama-produce` 5 个供应商子文件归并为 `builtin-providers.md`、`short-drama-edit` 5 个微文件归并为 `editing-guide.md`），严格保持单技能自包含。
4. **去教条化、去浅显填充与维护者技能松绑**：
   - 允许同机位微小表情/状态镜头用图生图编辑器基于已确认首帧派生，补齐 `minimax-h3` 首尾帧锁构图与全参考锁音色的二选一权衡，将 SVO 代词检查限定在英语提示词，允许本地私有 `对标拆解.md` 写明参考剧名，将 15 张题材卡与 6 张形态卡从硬性禁令改写为条件化创作建议，清理诚实性套话与极端稻草人反例。
   - `$short-drama-knowhow` 删除 `promotion-ledger.md` 与 `prompt-production-learning.md`，精简 `cards-and-coverage.md`，规定 `craft_default` 默认不捆绑审稿 rubric，降级或删除过严旧规则免跑双盲评测。

## Alternatives considered

1. **只改 Markdown 指令文案，不动 `creator_markdown_check.py`、`production_tool.py`、`edit_tool.py` 等脚本代码**。
   - 最强理由：改动面仅限文档，不会触碰现有单元测试中的脚本断言，实施风险最低。
   - 为何不用：文档中的繁琐门禁（如 `；画外：`、强制 `无（文生视频）`、引号 4 字拦截、逐资产单次确认、三步估时备份命令）恰恰是为了迎合脚本硬拦截才写进 `SKILL.md` 的；只删文档不松绑脚本会导致 Agent 按精简后的指令落盘时被脚本报错打回，形成表文死锁。
2. **保留全部 110 个 `references/*.md` 独立文件名，只删减每个文件内部行数**。
   - 最强理由：`EXPECTED_KNOWHOW` 与 `ALLOWED_PROVIDER_URLS` 无需改路径，历史笔记里的文件名引用完全不变。
   - 为何不用：40 余个不足 40 行（甚至 7～15 行）的碎片文件迫使 Agent 为完成同一阶段任务连续读取 8～12 个小文件，切碎了同一创作主题的上下文，也诱发每个小文件各自补一段开头背景而反复滋生冗余。

## Consequences

- **收益**：
  - 创作者与 Agent 从立项配置、剧本估时、分镜提示词校验、批量资产生成到局部试剪的阻断摩擦显著下降，单镜修改不再连坐作废整集生产记录。
  - 规则分级名实相符，多元题材（悬疑、生活流、规则怪谈、漫剧快切、多语种项目）不再被单一网文爽剧配方或小样本模型禁令误伤。
  - 全仓归并并移除 40 余个碎片参考文件与孤立模板，指令上下文信噪比与维护一致性显著提高。
- **代价**：
  - 属于破坏性精简：依赖旧版被归并参考文件路径、孤儿 `.example.jsonl`、全文件生产哈希或过严 `creator_markdown_check.py` 报错字面的测试与外部自动化脚本需同步迁移。
