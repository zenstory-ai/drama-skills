# Agent Note: 技能可移植性治理、脚本瘦身与规则表减负分波次方案

Status: proposed

## Problem

在完成 [全量精简技能指令中的人类培训说教、低频分支、空泛套话与重复规则](../../implemented/simplification/2026-11-07-prune-redundant-and-low-signal-skill-instructions.md)、[松绑过严脚本与流程门禁、重定级阶段规则并归并碎片化参考文档](../../implemented/simplification/2026-11-14-relax-gates-consolidate-references-and-recalibrate-rules.md) 与 [统一 7 脚本创作文档解析边界并以契约测试锁死跨技能规则一致性](../../implemented/architecture/2026-11-14-align-cross-script-markdown-parsers-and-contract-tests.md) 之后，对全仓 13 个技能（12 个公开 `skills/*` 与 1 个 `maintainers/skills/short-drama-knowhow`）的全面审计暴露出三类尚未根治的结构性问题：

1. **宿主锁定、分发清单失准与跨技能调用泄露**：
   - 40 份 Markdown 文档中存在 145 处 Codex 专属 `$short-drama-*` 语法（并已泄露进 `short-drama-novel-analyze/SKILL.md` 的 YAML `description`）；`maintainers/skills/short-drama-knowhow` 仅在 OpenAI 专属的 `agents/openai.yaml` 里设置禁止隐式触发，且 `CONTRIBUTING.md` 仅给出 `CODEX_HOME` 安装命令。
   - 技能文档内脚本路径占位符分裂为 `{技能目录}` 与 `<本技能目录>`，夹杂 63 处 POSIX 倾向的 `python3` 调用与 `/opt/studio/provider_adapters.py` 硬编码路径；`short-drama-storyboard` 与 `short-drama-breakdown` 正文直接指令执行 `short-drama` 目录下的脚本，违背 [每个技能自包含](../../implemented/architecture/2026-07-26-self-contained-skills.md)。
   - `.clawhub/publish.json` 中 `short-drama-assets`、`short-drama-develop`、`short-drama-novel-analyze` 保留了对 `short-drama@1.0.38` 的循环且陈旧兄弟依赖；5 个零脚本纯文档技能（`assets`、`image-prompts`、`review`、`storyboard`、`video-prompts`）仍误标 `bin:python>=3.9`；`short-drama-edit` 遗漏可选 Remotion 图文叠加层所需的 `node`/`npm`/`npx` 依赖声明。
   - `README_EN.md` 未如实说明「语言无关的创作指导层」与「目前绑定标准中文五文档文件名及 Markdown 结构的自动化脚本层」之间的边界。
2. **文档漂移、触发描述碰撞与规则编号膨胀**：
   - 存在三处实锤漂移：`creator-documents.md` 仍使用旧字段 `- 本集造型：`/`- 状态变化：` 且把服装连戏锁挂在 `人物` 下，与 `assets`/`storyboard` 要求冲突；`CON-05`/`CON-07` 在三份 `stage-contract.md` 正文已漂移；`video-prompts` 引用了单技能安装时不存在的跨技能规则号 `SHT-25`/`SHT-26`。
   - 13 份 YAML `description` 合计 2,226 字符，存在 5 组触发词重叠（如 `novel-analyze` 与 `develop`、`short-drama` 与 `image-prompts`、`storyboard` 与 `review` 等）。
   - 10 份 `stage-contract.md` 累计 215 条规则行（205 个唯一 ID），其中 94 条 `craft_default` 也被编入正式规则编号并牵动跨文件同步测试；部分核心 `SKILL.md` 为迁就正则脚本将复杂全角标点微语法压成 300–600 字单行墙。
3. **随包代码过度膨胀、僵尸代码滞留与 NLP 启发式越界**：
   - 13 个技能的知识文档（`SKILL.md` + `references/`）共 5,186 行，而随技能分发的代码高达 32,511 行（20 个 Python 脚本 27,901 行、Dashboard 前端 3,435 行、Remotion 1,175 行），并伴随 31,204 行 `tests/*.py`（含 `tests/legacy/` 共 34,586 行），代码/知识比超过 6:1，持续拉偏 [规则四级分级与脚本边界](../../implemented/architecture/2026-07-16-rule-tiers-and-script-boundary.md)。
   - 7 个带脚本技能仍随包分发 1,428 行 `selftest.py` 与 77 行 `fixture_adapter.py`（而 [旧 JSON 检查器移出技能](../../implemented/simplification/2026-10-20-retire-legacy-json-checkers.md) 已将 5 个无脚本技能的 `selftest.py` 移出）。
   - `project_tool.py` 仍保留全仓技能文档零引用的 v0.5 台账子命令（`publish`/`accept`/`review`/`set-authority`），`screenplay_index.py` 仍保留旧 JSONL 路径——但它们被发布门禁 `tests/test_workflow_evaluation.py` 与 `tests/test_golden_project.py` 等历史夹具锁死，无法在未迁夹具前直接删除。
   - `creator_markdown_check.py`（否定/对白/正文锁词等 NLP 启发式正则）、`duration_estimate.py`（动词黑名单）与 `edit_tool.py`（网文系统流面板关键词硬语法）仍把创作语义或垂直题材约定写死在确定性脚本中。

## Proposal

按风险隔离与测试依赖顺序分三个波次推进治理，每波次独立合流并通过全量测试与 lint 验证：

### Wave 1：跨宿主可移植性、文档去漂移与分发清单修正（不改动脚本行为与规则编号）

1. **宿主中立化**：
   - 将全部 13 个技能的 `SKILL.md`（含 YAML `description`）与 `references/*.md` 中的 `$short-drama-*` 统一替换为宿主中立技能名（如 `` `short-drama-write` 技能 ``），仅在 `README.md` / `README_EN.md` 中保留各平台调用前缀说明（Codex `$`、Claude Code `/`、其他宿主按技能名或自然语言触发）。
   - 在 `maintainers/skills/short-drama-knowhow/SKILL.md` 正文与 frontmatter 中补齐维护者显式触发限制，不再仅依赖 `agents/openai.yaml`；将 `CONTRIBUTING.md` 中的维护技能链接指引泛化为通用 `$SKILLS_DIR`，并新增技能文档 `<SKILL_DIR>` 与跨平台 Python 3.9+ 编写约定。
2. **消除真实漂移、触发碰撞与跨技能脚本泄露**：
   - 修正 `creator-documents.md` 字段与连戏锁挂点，同步 `storyboard`/`assets`/`video-prompts` 三份 `CON-05`/`CON-07` 正文，清理 `video-prompts` 对未定义 `SHT-25`/`SHT-26` 的悬空引用。
   - 重写 13 份 YAML `description` 为互斥、无 `$` 语法且 ≤150 字符的清晰边界描述。
   - 统一技能文档脚本调用路径为 `<SKILL_DIR>/scripts/...`、Python 为跨平台 3.9+ 约定、外部适配器路径为 `<ADAPTER_SCRIPT>`，撤下 `SKILL.md` 中的 `selftest.py` 使用说明；移除子技能直接执行其他技能目录脚本的指令，改为按技能名移交（独立安装时跳过外部脚本改由 Agent 自检）。
3. **分发清单与 README 边界澄清**：
   - 修正 `.clawhub/publish.json`：移除 `short-drama-assets`、`short-drama-develop`、`short-drama-novel-analyze` 上循环且陈旧的 `skill:worldwonderer/short-drama@1.0.38` 依赖；移除 5 个零脚本纯文档技能的 `bin:python>=3.9`；为 `short-drama-edit` 补齐 Remotion 叠加层所涉及的 `bin:node`、`bin:npm`、`bin:npx` 依赖记录（遵循 [ClawHub 分发采用显式清单和单一写入器](../../implemented/process/2026-10-03-clawhub-distribution.md)，版本号与 `packageDigest` 在治理合流发版时由中央 `clawhub_release.py lock` 统一重锁）。
   - 在 `README.md` 与 `README_EN.md` 如实说明语言无关创作指导层与标准中文自动化脚本层的边界，并补充 `short-drama-edit` 可选 Remotion 叠加层的 Node.js/npm/npx 说明。

### Wave 2：评估夹具迁移、脚本瘦身、测试资产外移与规则表减负

1. **先迁评估夹具，再退役 v0.5 僵尸代码**：
   - 将 `tests/test_workflow_evaluation.py`、`tests/test_golden_project.py`、`tests/test_simple_lifecycle.py` 等发布门禁与历史回归迁移到 [每集只保留至多五份创作者文档](../../implemented/architecture/2026-08-22-creator-first-five-documents.md) 基线，解除 [旧 JSON 检查器移出技能](../../implemented/simplification/2026-10-20-retire-legacy-json-checkers.md) 遗留的旧格式耦合。
   - 迁移完成后，从 `project_tool.py` 剥离零引用的 v0.5 台账子命令（`publish`/`accept`/`review`/`set-authority`）并清理 `screenplay_index.py` 旧 JSONL 路径。
2. **随包测试代码移出 `skills/`**：
   - 将剩余 7 个带脚本技能的 `scripts/selftest.py` 与 `short-drama-produce/scripts/fixture_adapter.py` 移入仓库 `tests/`，不再随创作者安装分发；保留 `tests/test_installation_resolution.py` 在独立隔离目录与无关 cwd 下验证每个技能脚本的闭环。
3. **脚本回归纯确定性边界并拆解压行墙**：
   - 从 `creator_markdown_check.py` 剥离越界的 NLP 启发式正则（否定词/对白归属/正文语义锁词），从 `duration_estimate.py` 移除动词黑名单，从 `edit_tool.py` 剥离网文系统流面板硬语法，只保留 ID 引用、算术、结构与媒体实测等确定性校验；同步更新相关单元测试。
   - 拆解 `storyboard`/`video-prompts`/`edit`/`review` 中超长单行 DSL 为清晰示例，并为轻量或局部创作任务提供免全套五文档 DSL 的快速路径说明。
4. **规则表减负**：
   - 将各技能 `references/stage-contract.md` 收窄为有明确验证或阻断价值的 `structural_invariant` 与 `reviewed_invariant`；将 94 条 `craft_default` 与 `taste_option` 下沉回各阶段做法文档的自然语言说明，不再维持庞大的正式规则编号与历史规则数门槛断言。

### Wave 3：可选深化——模板/语言解耦与技能拓扑评估

1. **多语言与非 Remotion 环境解耦**：
   - 为 `novel_index.py` / `episode_intake.py` 补齐 `Chapter N` / `Episode N` 等非中文切分识别；将 Remotion 叠加层的中文系统流常量与稀有度配置化，并在无 Node.js / Remotion 环境或仅需简单 `字卡` 时提供 `ffmpeg` 降级或「仅导出剪辑单 + SRT/ASS 字幕」的显式退出路径。
2. **技能拓扑独立评估（不预判结论）**：
   - 在 Wave 2 瘦身完成后，基于实际代码量、测试耦合面与 ClawHub 既有 slug 兼容性，另行评估两项高影响拓扑改动：是否将本地创作台（`dashboard_server.py`、`creator_views.py`、`assets/dashboard/`）从 `short-drama` 拆分为独立技能或可选工具，以及是否合并颗粒度偏细的 `short-drama-assets` 与 `short-drama-image-prompts`。若决定变更，另立决策笔记实施。

## Alternatives considered

1. **一步到位抽取跨技能共享 Python 解析库并同步合并/拆分技能目录**
   - 最强理由：可一次性消除 7 套重复的 Markdown 正则解析器（202 条 `re.compile`）并大幅压缩总代码行数。
   - 为何不用：直接违背硬规则 1（[每个技能自包含](../../implemented/architecture/2026-07-26-self-contained-skills.md)），会破坏 ClawHub 与单目录 symlink 安装闭包；在未完成 v0.5 评估夹具迁移与测试耦合盘点前同步改动拓扑，会把高风险行为变化与纯文档通用化混在一次提交里，难以定位回归与回退。
2. **仅修正文档错漏，保留全部随包 `selftest.py`、v0.5 僵尸代码、NLP 启发式与 205 条编号规则**
   - 最强理由：几乎不触碰 `tests/`，短期合并成本最低，不会产生测试迁移工作量。
   - 为何不用：审计已证明 6:1 的代码/知识比与脚本对 Markdown 正文的过度解析正是压行墙、全角标点 DSL 仪式感与跨文件漂移的根因；只修表面文案不收窄脚本与规则表，后续维护摩擦只会继续累积。
3. **在 Wave 1 直接删除 `agents/openai.yaml` 并顺手重算 `.clawhub/publish.json` 的 `version` / `packageDigest`**
   - 最强理由：一次性去掉所有 vendor 文件并让分发清单指纹保持最新。
   - 为何不用：`agents/openai.yaml` 仍承担 Codex 宿主展示元数据并受 `test_installation_resolution.py` 校验，保留它作为宿主适配层、同时把核心规则收回宿主中立 `SKILL.md` 更平滑；Wave 1/2 涉及多作者并行修改多个技能目录，提前手工改动 `packageDigest` 会在合流后立即失效，应严格按 `.clawhub/README.md` 在合流发版时通过中央 `clawhub_release.py lock` 一次锁定。

## Consequences

- **收益**：
  - Wave 1 即刻消除跨宿主语法锁定、5 组触发词碰撞、3 处真实文档语义漂移与 `.clawhub/publish.json` 的循环/错误依赖，同时给中英文创作者诚实透明的脚本能力边界。
  - Wave 2 显著降低随技能分发的代码体积与测试维护负担，真正落地「知识与做法优先」和「脚本只守确定性结构」原则，并把发布门禁彻底迁移到当前 creator-first 五文档路径。
  - Wave 3 将高风险拓扑决策与低风险语言/环境解耦隔离，避免在缺乏 Wave 2 基线数据时盲目破坏 ClawHub 分发身份。
- **代价与风险**：
  - 分波次落地意味着 Wave 1 与 Wave 2 之间需做一次集中测试对齐（涉及耦合 `$short-drama-*`、`selftest.py`、规则数门槛、v0.5 台账子命令与 NLP 正则的既有测试）。
  - 下沉 `craft_default` 规则编号后，审查无法再按 ID 机械逐条核对常规手艺项，需要通过高质量的 rubric 与阶段指南维持审查信噪比。
  - 在 Wave 3 拓扑评估落地前，Dashboard 仍暂驻 `skills/short-drama/`，`short-drama` 单技能包体积在 Wave 1 阶段尚不会大幅下降。
