# Agent Note: 全仓消除 AI 黑话与五份创作文档字段破坏性重命名

Status: implemented

## Problem

尽管 [技能说明消解翻译腔与案例文案短剧质感润色](./2026-11-05-idiomatic-chinese-and-short-drama-examples-polish.md) 已清理了一批早期生造词并润色了随仓案例，逐文件通读全仓 218 个面向创作者与 Agent 上下文的文件后，仍存在四类系统性的 AI 味黑话与契约层遗留问题：

1. **五份核心创作文档与参考图槽位的校验字段仍保留生硬直译与工程黑话**：`视觉设定.md`、`分镜.md`、`视频提示词.md` 的核心字段名（`时代锚点`、`识别锚点`、`画面代称`、`连续性锁 / 锁面`、`固定锚点`、`唯一动作`、`视觉依据`、`冻结关键帧提示词`、`收尾关键帧提示词`、`静态视觉锚点`、`状态链`、`无（创作者已明确选择文生视频）`）以及参考图槽位用途枚举（`用途：身份`、`用途：地理`）由早期英文概念直译而来，不仅创作者理解费力，也迫使各技能说明反复解释字面含义。
2. **15 份核心规则与审查母表仍为英文或半英半中杂糅**：10 个技能的 `references/stage-contract.md`、`short-drama-review` 的 `review-method.md` 与 3 份 `rubric-*.md`（含 `Every shot's 运镜 line`、`is listed in 视觉依据` 等半英半中句）以及 `short-drama-produce/references/adapter-contract.md` 未中文化，下游中文参考文档在对齐母表时不断衍生出误译与生造词（如把 `economy pass` 译为「经济性遍」、`reference roles` 译为易混同人物角色的「参考角色」、`voice direction` 译为「声音方向」、`contact sheet` 译为「联系表」、`color grading` 译为「分级」、`sell a hit` 译为「把打击卖出去」、`creator-overridable` 译为有歧义的「可覆盖」）。
3. **软件工程、状态机与 NLP 术语渗入创作指导与公开文档**：如 `creator-first`、`唯一落盘`、`信息权限 / 本镜权限`、`活跃铺垫债务`、`单调递增`、`同指`、`受管道具`、`多镜容器 / 容器算术`、`前提装置`、`门槛集` 等工程黑话，以及抽象七词排比公式、「不是 X，而是 Y」机械对立句、括号套括号的防杠长句，还有给 Agent 立规矩的禁令外溢到面向人类读者的 `docs/` 教程。
4. **4 处内部黑话漏入喂给生图/视频模型的提示词正文**：`provider_adapters.py` 在中文提示词末尾直接拼接内部英文枚举 `用途 {role}`；`short-drama-video-prompts`、`short-drama-storyboard` 与 `examples/excerpt-chain` 的提示词正例中混入「已接受起点」「只是空间锚点」「固定建筑锚点」等模型无法按画面执行的内部黑话；此外存在 `generated-media-review.md` 死引用、已废弃 `attention_handoffs[]` 字段残留及 6 处繁简/日文汉字错字。

项目当前仍处于早期阶段，维护者明确决定直接做干净的破坏性重命名，不保留新旧字段双认兼容层。

## Decision

全仓统一清理 AI 黑话、硬译词与机械句式（保留场次、景别、机位、轴线、越轴、正反打、过肩镜、定场镜头、空镜、走位、站位、调度、VO/OS、SFX、转场、硬切、跳切、J-cut/L-cut、声桥、蒙太奇、留白、潜台词、钩子、反转、伏笔、铺垫、高潮、爽点、打脸、卡点集、角色设定、三视图、服化道、色温、调色、首尾帧、关键帧、运镜、参考图、定调图/Lookdev、LUFS/dBTP、烧录字幕、名条、全模态参考等标准影视后期与 AIGC 行业术语），并同步落地五份创作文档字段的破坏性重命名：

1. **五份创作文档、参考图槽位与创作台字段破坏性重命名（不设旧名别名兼容）**：
   - `视觉设定.md`：`时代锚点` 改为 `时代背景`；`识别锚点` 改为 `外观特征`；`画面代称` 改为 `提示词名称`；`连续性锁：LOCK-... · 锁面：...` 改为 `连戏锁：LOCK-... · 锁定词：...`。
   - `分镜.md`：场景站位 `固定锚点` 改为 `固定陈设`（`working side` 改为 `机位侧`）；`唯一动作` 改为 `动作`；`视觉依据` 改为 `出场设定`；`输入参考图：无（创作者已明确选择文生视频）` 改为 `输入参考图：无（文生视频）`；`### 冻结关键帧提示词` 改为 `### 首帧提示词`；`### 收尾关键帧提示词` 改为 `### 尾帧提示词`。
   - `视频提示词.md`：`静态视觉锚点` 改为 `开场画面`；`状态链` 改为 `动作过程`；`GROUP-...` 检查诊断中的 `交付分组 / 一次交付` 改为 `合生分组 / 一次合生`。
   - 参考图槽位 `REF_PURPOSES`：`身份` 改为 `外貌`；`地理` 改为 `空间布局`，并新增 `主体`（完整十项枚举为 `外貌`、`主体`、`造型状态`、`空间布局`、`构图`、`尺度`、`效果`、`起始帧`、`结束帧`、`风格`）。
   - 创作台 `FILE_LABELS`：`story-engine.md` 显示名改为「核心设定」；可复制提示词标题集合使用 `可复制提示词`、`首帧提示词`、`尾帧提示词`；全部 `skills/*/SKILL.md` 的快速开始小节标题统一为 `## 快速开始`。
   - [creator_markdown_check.py](../../../../skills/short-drama/scripts/creator_markdown_check.py)、[creator_views.py](../../../../skills/short-drama/scripts/creator_views.py)、[app.js](../../../../skills/short-drama/assets/dashboard/app.js)、[production_tool.py](../../../../skills/short-drama-produce/scripts/production_tool.py) 及对应回归测试只校验和提取新字段名。相关早期设计见 [每集只保留至多五份创作者文档](../architecture/2026-08-22-creator-first-five-documents.md)、[创作台分集进度与提示词复制](../feature/2026-09-26-dashboard-progress-first-screen-copy.md) 与 [局部核对、交付分组与「入画」锁范围](../feature/2026-10-20-partial-check-groups-in-frame-locks.md)。
2. **修复模型提示词黑话外泄与文档缺陷**：
   - `provider_adapters.py` 的 `_prompt_with_reference_contract` 在中文提示词中按 `ZH_ROLE_LABELS` 输出中文用途名（如 `首帧`、`尾帧`、`参考图`、`外貌`、`造型状态`、`空间布局`、`前序接戏视频`、`前镜实际尾帧`），英文提示词保留英文枚举。
   - 清理技能与示例提示词正例中的「已接受起点」「只是空间锚点」「固定建筑锚点」等内部黑话；修正 `short-drama-review/references/stage-contract.md` 指向 `generated-media.md` 的文件名引用、移除 `rubric-visual-motion.md` 中废弃的 `attention_handoffs[]`，修正 6 处繁简与日文汉字混用。
3. **15 份英文母表全面汉化与全仓 12 个公开技能、维护者技能、公开文档及示例去黑话**：
   - 10 份 `stage-contract.md`、4 份审查方法与评分表、1 份生产适配器契约改为中文表达（保留规则编号与 `structural_invariant` / `reviewed_invariant` / `craft_default` / `taste_option` 四档分级名）。
   - 按统一术语表消除误译词、软件工程/NLP 黑话、抽象排比公式、机械对立句式与括号套括号长句，清理 `docs/` 中面向 Agent 的系统禁令残留，并同步更新 `examples/creator-first/` 与 `examples/excerpt-chain/`（冻结评估目录 `evaluations/让你管账号/reference-run/` 与旧版只读历史归档 `examples/golden-project/` 保持原状）。

## Alternatives considered

- **解析器与创作台做新旧字段双认兼容（同时接受 `视觉依据` 与 `出场设定`、`连续性锁` 与 `连戏锁` 等）**：
  - 最强理由：已有早期测试项目或外部草稿无需改字段名即可继续通过 `creator_markdown_check.py` 与创作台解析。
  - 不用：双认兼容会让正则、报错信息、创作台字段提取与测试长期背负两套命名，Agent 在上下文看到旧项目时仍会模仿旧黑话；项目尚处早期，一次性切干净并给出升级对照表，维护成本最低。
- **只润色散文说明，保留五份创作文档现有的校验字段名与 `REF_PURPOSES` 不动**：
  - 最强理由：零脚本改动、零破坏性变更，不会触碰测试夹具。
  - 不用：`视觉依据`、`画面代称`、`连续性锁 / 锁面`、`冻结关键帧提示词`、`静态视觉锚点`、`用途：地理 / 身份` 正是创作者每集必读写、出现频率最高的核心界面词；保留它们等于把最刺眼的翻译腔钉死在每一集产物里。

## Consequences

- **收益**：五份创作文档字段、创作台界面、15 份规则审查表、全套技能说明、公开文档与模型提示词统一为自然准确的中文影视与短剧行业表达；消除了内部枚举和工程黑话漏入生图/生视频提示词的问题。
- **代价**：破坏性变更——旧项目的 `视觉设定.md`、`分镜.md`、`图片提示词.md`、`视频提示词.md` 需按 `CHANGELOG.md` 的升级对照表替换字段名与参考图用途词，才能通过新版 `creator_markdown_check.py` 校验并在创作台完整展示结构视图。
