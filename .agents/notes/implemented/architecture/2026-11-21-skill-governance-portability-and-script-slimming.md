# Agent Note: 技能可移植性治理、脚本瘦身与规则表减负

Status: implemented

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
   - 10 份 `stage-contract.md` 累计 215 条规则行（205 个唯一 ID），其中 94 条 `craft_default` 与 12 条 `taste_option` 行也被编入正式规则编号并牵动跨文件同步测试；部分 `structural_invariant` 混入无法由确定性脚本判定的创作语义。
3. **随包代码过度膨胀、僵尸代码滞留与 NLP 启发式越界**：
   - 随技能分发的 Python 脚本达 20 个、共 27,901 行，其中包括 7 个技能自带的 1,428 行 `selftest.py`、77 行 `fixture_adapter.py` 与 1,500 行 `screenplay_index.py`。
   - `project_tool.py` 仍保留全仓技能文档零引用的 v0.5 台账子命令（`publish`/`accept`/`review`/`set-authority`）；`breakdown_tool.py` 保留基于剧本估时与 `difflib` 启发式的 `plan`/`reprise` 路径。
   - `creator_markdown_check.py`（否定词、对白引文归属、正文语义锁词等 NLP 正则）与 `duration_estimate.py`（动作/说话人启发式黑名单）仍把创作语义写死在确定性脚本中；`novel_index.py` / `episode_intake.py` 仅支持中文标题，`edit_tool.py` 缺少无 Node/Remotion 时普通 `字卡` 的降级渲染路径。

## Decision

分两波次完成全仓可移植性治理、脚本瘦身、多语言/无 Remotion 解耦与规则表减负，现已全部落地：

### 1. 跨宿主可移植性、文档去漂移与分发清单修正（Wave 1）

- **宿主中立化**：全部 13 个技能的 `SKILL.md`（含 YAML `description`）与 `references/*.md` 统一使用宿主中立技能名（如 `` `short-drama-write` 技能 ``），不再使用 Codex 专属 `$short-drama-*` 语法；各平台调用前缀说明收归 `README.md` / `README_EN.md`。`maintainers/skills/short-drama-knowhow/SKILL.md` 在正文与 frontmatter 显式声明维护者触发边界，`CONTRIBUTING.md` 改为通用 `$SKILLS_DIR` 并明确 `<SKILL_DIR>` 与跨平台 Python 3.9+ 约定。
- **消除漂移、触发碰撞与跨技能脚本泄露**：修复 `creator-documents.md` 字段与连戏锁挂点；同步三份 `stage-contract.md` 的共享 `CON-*` 正文；清理 `video-prompts` 对未定义规则号的悬空引用；重写 13 份 YAML `description` 为清晰互斥边界；统一技能文档命令路径为 `<SKILL_DIR>/scripts/...` 与 `<ADAPTER_SCRIPT>`，撤下 `selftest.py` 说明，移除子技能直接执行其他技能目录脚本的指令。
- **分发清单与 README 边界澄清**：`.clawhub/publish.json` 移除 3 处陈旧循环依赖与 5 个纯文档技能上的 `bin:python>=3.9`，为 `short-drama-edit` 补齐可选 Remotion 依赖（`bin:node`/`npm`/`npx`），并递增 12 个受改动技能的补丁版本、使用固定 `control_ref`（`b8dbd133b557dce5143c18902a887ddca9d4cdf0`）的 `clawhub_release.py lock` 锁定 `packageDigest` 且通过离线校验；`README.md` 与 `README_EN.md` 如实说明语言无关创作指导层与标准中文自动化脚本层边界。

### 2. 脚本瘦身、测试资产外移与多语言/无 Remotion 解耦（Wave 2）

随技能分发的 Python 脚本从 **20 个文件 / 27,901 行** 精简至 **11 个文件 / 23,279 行**（净减 **9 个文件、4,622 行 / -16.6%**）：

- **测试代码移出分发目录**：删除全部 7 个带脚本技能的 `scripts/selftest.py`（-1,428 行）；`short-drama-produce/scripts/fixture_adapter.py`（77 行）迁至 `tests/fixtures/fixture_adapter.py` 并移除 `provider_adapters.py` 的 `--selftest`（-91 行）；`short-drama-write/scripts/screenplay_index.py`（1,500 行）迁至 `tests/legacy/short-drama-write/scripts/screenplay_index.py`。`tests/test_standalone_skill_tooling.py` 改为在隔离目录与无关 `cwd` 下对全部 7 个带脚本技能的主业务脚本执行 `--help` 与最小确定性冒烟校验。
- **`short-drama` 核心脚本回归确定性**：`creator_markdown_check.py`（2,767 → 2,185 行，-582 行）剥离否定词、对白引文归属与正文语义锁词等 NLP 正则（`_named_entries`、`_check_named_coverage`、`_check_spoken_lines`、`_quote_speakers`、`_carries_surface` 等），保留全部 ID、语法、路径、槽位顺序、音轨绑定与算术校验；`project_tool.py`（3,435 → 2,701 行，-734 行）移除零引用的 v0.5 台账子命令（`publish`/`accept`/`review`/`set-authority`/`--strict-ledger`），完整保留 `init`/`configure`/`status`/`export`/`package`/`verify` 与 Dashboard 契约。
- **`write` / `breakdown` / `develop` / `novel-analyze` 瘦身与英文扩展**：`duration_estimate.py`（1,378 行）内联内存剧本解析器（暴露 `parse_screenplay` / `parse_script_blocks`）并移除动作/说话人启发式黑名单与已废弃 `--index` 路径；`breakdown_tool.py`（2,436 → 1,630 行，单文件 -806 行；连同移除随包 `selftest.py` 102 行合计 -908 行）保留全部 `ffmpeg` 确定性媒体测量子命令，移除 `plan`/`reprise` 启发式并同步清理 `short-drama-breakdown` 文档引用；`novel_index.py` 扩展支持英文 `Chapter`、英文数词与罗马数字章节；`episode_intake.py` 扩展支持 `Episode N` 等英文集标题。
- **`edit_tool.py` 无 Remotion 降级路径**：`render` 新增 `--screen-text-mode auto|remotion|ffmpeg|off`（默认 `auto`）。复杂面板样式仍走可选 Remotion；未安装 Node/Remotion 且全片仅含普通 `字卡` 时自动降级为 `ffmpeg` ASS 烧录并写明提醒；`ffmpeg` 强制纯 `字卡` 直出；`off` 跳过全部 `画面文字` 叠层并照常烧录字幕成片。同步记录于 `skills/short-drama-edit/SKILL.md`。

### 3. 规则表减负与审查清单瘦身（Wave 2）

- 10 份 `skills/*/references/stage-contract.md` 规则表从 **205 个唯一 ID（215 行：32 `structural_invariant`、77 `reviewed_invariant`、94 `craft_default`、12 `taste_option`）** 收窄为 **105 个唯一 ID（111 行：30 `structural_invariant`、81 `reviewed_invariant`、0 `craft_default`、0 `taste_option`）**，由 `tests/test_cross_parser_parity.py` 锁死规则表仅注册阻断级不变量。
- 全部 92 个唯一 `craft_default` 与 10 个唯一 `taste_option` 下沉为各技能参考文档的自然语言手艺建议；校正 6 条混合语义 `structural_invariant`（拆分 `SCR-05`/`SCR-25`、`VID-01`/`VID-29`，降级 `AST-10`、`VID-24`，收窄 `SHT-05`、`VID-13`）；共享 `CON-01`/`CON-02`/`CON-07` 在三份合约逐字一致；同步瘦身 `short-drama-review` 四份 rubric 消除退化区间。

## Alternatives considered

1. **一步到位抽取跨技能共享 Python 解析库**
   - 最强理由：可一次性消除多套重复的 Markdown 正则解析器，进一步压缩总代码行数。
   - 为何不用：直接违背硬规则 1（[每个技能自包含](../../implemented/architecture/2026-07-26-self-contained-skills.md)），会破坏 ClawHub 与单目录 symlink 独立安装闭包；各技能脚本内联精简后的解析器并用 `tests/test_cross_parser_parity.py` 锁死边界一致性，既保自包含又防漂移。
2. **在本轮直接合并 `short-drama-assets` 与 `short-drama-image-prompts`，并将 Dashboard 从 `skills/short-drama` 拆分为独立技能**
   - 最强理由：可合并颗粒度偏细的资产/生图提示词技能，同时把 3,400+ 行 Dashboard 前端与服务端移出核心路由技能 `short-drama`，显著减小主技能包体积。
   - 为何不用：ClawHub v1.x 已按现有 12 个公开 slug 发布与锁定分发，合并或重命名现有 slug 属于破坏性接口变更，会打断既有安装脚本与下游引用；同时把 Dashboard 拆出 `skills/short-drama` 若仍复用 `project_tool.py` / `creator_views.py` 会触犯硬规则 1（技能自包含），复制一份又会引入双份维护。因此将这两项高影响拓扑调整有意延后到未来大版本（v2.0+）单独评估并另立决策笔记实施。
3. **仅修正文档错漏，保留全部随包 `selftest.py`、v0.5 台账子命令、NLP 启发式与 205 条编号规则**
   - 最强理由：几乎不触碰 `tests/`，短期合并成本最低。
   - 为何不用：审计已证明过重的随包脚本、越界 NLP 正则与庞大的常规手艺编号表正是维护摩擦、假阳性报错与跨文件漂移的根因；只改文案不瘦身脚本与规则表，长期维护成本会持续攀升。
4. **直接删除 `agents/openai.yaml`（放弃 Codex 适配层）**
   - 最强理由：一次性去掉所有 vendor 专属适配文件，让目录完全中立。
   - 为何不用：`agents/openai.yaml` 仍承担 Codex 宿主展示元数据并受安装解析测试校验，保留作轻量适配层同时将核心规则收回宿主中立 `SKILL.md` 更平稳。至于 `.clawhub/publish.json`，因 PR 门禁 `validate-clawhub.yml` 强制核对 `packageDigest` 与相对 `origin/main` 的版本递增，本轮直接通过固定 `control_ref` 的中央 `clawhub_release.py lock` 统一锁定并通过离线校验。

## Consequences

- **收益**：
  - 全套 13 个技能摆脱 Codex 专属语法锁定，跨宿主可移植、触发边界互斥清晰，`.clawhub/publish.json` 依赖声明与 README 能力边界诚实准确。
  - 随技能分发脚本净减 9 个文件、4,622 行（-16.6%），所有随包脚本回归纯确定性职责，彻底移除越界 NLP 正则、零引用 v0.5 台账命令与随包测试脚本。
  - `stage-contract.md` 规则表减负近半（205 → 105 个唯一 ID），阻断级不变量与常规手艺建议清晰分层，且跨技能规则引用与分级由自动化测试持续守住。
  - 原著/分集解析补齐英文 `Chapter` / `Episode` 识别，剪辑工具在无 Node/Remotion 环境下具备纯 `ffmpeg` `字卡` 渲染与 `--screen-text-mode off` 显式降级路径。
- **代价与风险**：
  - 撤掉正文 NLP 语义锁词、对白引文归属与主体覆盖正则后，对应语义一致性改为由创作者与 `short-drama-review` 按 `reviewed_invariant` 与 rubric 把关，脚本不再拦截纯文案级漂移。
  - 历史 `examples/golden-project` 与 `evaluations/让你管账号/reference-run` 仍依赖迁入 `tests/legacy/` 的旧版 `screenplay_index.py` 做历史归档回归验证。
  - 在未来大版本拓扑评估落地前，本地创作台仍保留在 `skills/short-drama/`，`short-drama-assets` 与 `short-drama-image-prompts` 维持现有 12 个 ClawHub 公开 slug 不变。
