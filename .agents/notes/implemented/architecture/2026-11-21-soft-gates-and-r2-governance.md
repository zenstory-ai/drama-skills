# Agent Note: 确立软门禁原则、修复跨脚本解析盲区与演进桥接层

Status: implemented

## Problem

在完成 [技能可移植性治理、脚本瘦身与规则表减负](2026-11-21-skill-governance-portability-and-script-slimming.md) 后，面向真实创作者与多语言/多平台生产流的第二轮全仓深审暴露出四类紧迫问题：

1. **硬门禁与软提醒边界尚未彻底澄清，仍有“伪 `structural_invariant`”**：
   - `stage-contract.md` 中仍有 7 条规则被标为 `structural_invariant`，但其判断本质属于语义审稿或已在首轮移出脚本正则（`AST-13`、`IMG-13`、`SHT-16`、`SHT-26`、`VID-04`、`VID-25`、`CON-07`），另有 `VID-03`、`VID-27` 的条文残留已删除正则描述；
   - 各脚本在遇到「确定性失败」之外的可疑异常（如缺少跨语种 `提示词名称`、剪辑时长大幅偏差/短字幕窗口/响度偏移、生产覆盖已有成片/整文件音乐哈希/未钉死远端适配器、分集未映射区间、对标重复集号）时，要么直接 `ERROR` 阻断、要么静默吞并，缺少统一的 **软门禁（`WARNING` / `提醒`，exit 0）** 机制。
2. **高危解析盲区、跨语种/横屏缺陷与 Dashboard 竞态**：
   - **P0 冒号入粗体丢字段**：`production_tool.py` 与 `edit_tool.py` 无法识别普通 Markdown 写法 `- **输入参考图：** REF-...` / `- **参考音频：** ...` / `- **字幕：** ...`，导致 `GROUP-*` 等可选参考图或剪辑字段被静默丢弃；
   - **P0 英文断词与 16:9 横屏**：`edit_tool.py` 按 12 字符硬切英文句子导致单词拦腰截断；横屏下字幕安全区沿用竖屏 24% 高度且 Remotion 面板无最大宽限；Remotion 字体探针对西里尔/阿拉伯/韩/泰语硬报错、`splitCardRow` 拆碎多词英文标签；
   - **P0 过期文档示例与跨平台命令**：`README.md` / `docs/real-outputs.md` 中的校验示例仍演示已在首轮移除的「删掉 `周薄森`」报错；`short-drama/SKILL.md` 与 `breakdown/SKILL.md` 仍残留 POSIX `\` 续行和单引号 JSON；
   - **P1/P2 工具链缺陷**：`breakdown_tool.py` 漏认 `Season2_Episode03`、BOM/CRLF 导致 `json.loads` 失败、重复集号被字典覆盖静默吞并；`novel_index.py` 与 `episode_intake.py` 的 `chinese_to_int` 存在漂移；`duration_estimate.py` 仍残留 499 行旧字节偏移行表与 `BLK-0001` 脚手架；`provider_adapters.py` 硬编码中文「音色参考」与固定模型名；`dashboard_server.py` 扫描 `.git`/`node_modules` 触发 5000 节点截断；`app.js` 存在项目/集切换异步竞态、新建 creator-first 项目状态徽章误显草稿及时间轴零宽除零。
3. **长文档冗余、多音乐条目耦合与脚本跨技能维护摩擦**：
   - `short-drama-develop/references/` 四份高重叠文档（25,033 字符）与 45 键嵌套 `episode-map.jsonl` 带来显著上下文税；`short-drama-image-prompts/SKILL.md` 内联 326 字符 DSL；
   - `MUSIC-*` 配乐提示词缺少独立条目规范与条目级哈希，改动同文件视频镜头会连带令配乐任务缓存失效；
   - 跨技能共用纯逻辑（如 `chinese_to_int`）手工复制两份易再度漂移，单集快速起稿缺少一键建骨架与缺口巡检；
   - `short-drama-produce` 适配器能力检测仍耦合文件名 `provider_adapters.py`、`short-drama-edit` 画面文字叠层与内置 Remotion 耦合、`project_tool.py` 同时维护 `export` 与重复的 `package` 归档流程。

## Decision

围绕「**硬门禁守确定性底线、软门禁出提醒不阻断、桥接层为未来演进铺路而不破坏 v1.x 自包含契约**」完成全仓治理，现已全部落地：

### 1. 确立软门禁原则与 100% 规则契约闭环（`B5-d`）

- 在 `AGENTS.md`、`short-drama/SKILL.md`、`knowhow-index.md`、`short-drama-review/SKILL.md` 与维护者技能中明确定义 **Hard Gate（仅 100% 确定性结构/引用/路径/算术/财务安全失败才阻断） vs Soft Gate（可疑风险与工艺提醒一律走 `WARNING` / `提醒`，exit 0）**。
- 将 `AST-13`、`IMG-13`、`SHT-16`、`SHT-26`、`VID-04`、`VID-25`、`CON-07` 重定级为 `reviewed_invariant`（三份 `CON-07` 逐字一致），收窄 `VID-03`、`VID-27` 为纯确定性检查；`creator_markdown_check.py` 新增 `ValidationResult(errors, warnings)` 与 `validate_*_with_warnings`，CLI 仅存在 `warnings` 时打印 `WARNING:` 并返回 `0`；`production_tool.py`、`edit_tool.py`、`breakdown_tool.py`、`episode_intake.py` 同步落地软提醒而不削弱任何确定性安全或格式硬门禁。
- 在 `tests/test_cross_parser_parity.py` 落盘永久断言（`B5-d`）：验证 `short-drama-review/references/` 100% 覆盖全部 9 份上游 `stage-contract.md` 的 100 条阻断级规则且分级完全一致。

### 2. 修复全仓 P0/P1/P2 缺陷与跨解析器一致性

- **冒号入粗体四端统一**：`production_tool.py` 与 `edit_tool.py` 补齐 `- **字段：** 值` / `* *字段:* 值` 解析，与 `creator_markdown_check.py`、`creator_views.py` 完全一致，并在 `tests/test_cross_parser_parity.py` 新增四端回归测试永久防回退。
- **剪辑与 Remotion 国际化 / 横屏适配**：`edit_tool.py` 实现拉丁语系按词边界平衡换行（`SUBTITLE_MAX_LATIN = 40`）与横屏 9% 字幕边距，修复 `ffmpeg`/`ffprobe` PATH 回退、`libass` `\N`/`\n`/`\h` 转义（`\u2060`）、跨平台 `npm install` 提示与最长关键词优先匹配；Remotion 端加入 `subtitleBottomU` 与 `panelWidth` 横屏保护、放行非声明语系系统字体回退与多词英文标签。
- **上游工具链与生产适配修复**：`breakdown_tool.py` 支持 `Season2_Episode03` 识别、UTF-8 BOM/CRLF 归一化与重复集号保留（`ep#1`/`ep#2` + 软警告）；`duration_estimate.py` 移除 499 行旧字节偏移与 `BLK-0001` 死脚手架；`provider_adapters.py` 按 `prompt_language` 输出英文 `voice reference` 并支持 `parameters.model` 与环境变量覆盖默认模型；`creator_markdown_check.py` 放行 `- 参考：无（纯文生图）` 并收紧 `### 尾帧提示词` 全角/多空格匹配；`novel_index.py`、`short-drama.json` 模板与 `adaptation-map.example.jsonl` 统一 `schema_version` 为 `"1.0.0"`。
- **Dashboard 与文档修复**：`dashboard_server.py` 跳过 `.git`/`node_modules`/`.venv`/`__pycache__`/`.short-drama`；`app.js` 为 `loadProject`/`loadEpisode`/`refreshProject` 加序列/标识防竞态守卫，按单集实际进度推导剧集徽章并修复时长列、提示词兜底与时间轴零宽保护；替换 `README.md`/`README_EN.md`/`docs/real-outputs*.md` 过期校验示例，补齐 `project_tool.py configure --json-file` / `@<path>` 跨平台传参、无 shell 回退指引及全部 12 份 `agents/openai.yaml` 同步。

### 3. 克制落盘构建期共享与架构桥接（`B4-a`/`B4-b`/`B5-b`/`B5-c`/`B2-prep`/`B3-prep`/`B5-e-prep`）

- **`B4-a` 构建期共享 vendoring 试点**：新增 `src/_shared/cn_num.py` 与 `tools/sync_shared.py`（`--write` / `--check`），通过 `# BEGIN SHARED: cn_num` / `# END SHARED: cn_num` 标记区将权威 `chinese_to_int` 同步进 `novel_index.py` 与 `episode_intake.py`，并在 `tests/test_cross_parser_parity.py` 强制 `--check` 校验。技能目录零新增文件、零跨目录 `import`，100% 保持单文件零依赖独立运行与 ClawHub 闭包。同步在 `.github/workflows/ci.yml` 中将 `src/**` 与 `tools/**` 纳入路径过滤与 `mypy` 校验。
- **`B4-b` 单集起稿脚手架**：`project_tool.py` 新增 `scaffold-episode`，按需初始化最小单集目录与缺失骨架（绝不覆盖已有文件）并输出确定性缺口清单与校验结果。
- **`B5-b` 配乐条目一级公民**：规范 `## MUSIC-... · <名称>` 条目，打通 `creator_markdown_check.py`、`creator_views.py` 与 `production_tool.py`（支持 `source_entry: "MUSIC-..."` 条目级提取与哈希，视频镜头改动不再使配乐任务失效）。
- **`B5-c` `short-drama-develop` 文档合并瘦身**：将 4 份高重叠参考文档合并为正交的 `story-and-character-craft.md` 与 `episode-architecture.md`（-53.4% 字符），并将 `episode-map.jsonl` 模板从 45 嵌套键精简为 12 扁平核心键（-83.0% 字符）；同步将 `image-prompts` 的内联格式 DSL 迁入 `references/format-spec.md`。
- **`B2-prep` / `B3-prep` / `B5-e-prep` 非破坏性演进桥接**：`production_tool.py` 优先按适配器显式声明的 `reference_roles` / `audio_capable` 判定能力（不再绑定文件名），并补充外置供应商包精确锁版本安全指引；`edit_tool.py render` 新增可选 `--overlay-renderer <cmd>` 协议外置图文叠加渲染；`project_tool.py export` 默认附带 `--manifest`（可 `--no-manifest`）且 `verify <dir>` 直接校验导出目录，`package` 保持完全可用并输出温和弃用提醒。

## Alternatives considered

1. **立即落地 B1：将脚本拆分为独立 PyPI 包（`drama-skills-core`）供各技能运行时 `import`**
   - **最强理由**：可从根本上消除跨脚本解析器与工具函数重复，统一版本管理，并把脚本代码彻底移出技能目录。
   - **为何不用**：当前套件的核心分发承诺是「零外部依赖、仅需 Python 3.9+ 标准库、每个 `skills/*` 目录可单独 symlink 或通过 ClawHub 独立安装并离线直接运行」（见 [每个技能自包含](2026-07-26-self-contained-skills.md)）。在未建立成熟包发布流水线前强推 PyPI 运行时依赖，会立刻破坏离线/受限环境开箱即用体验与单技能安装闭包。本轮改为以 `B4-a` 构建期 `src/_shared/` + `tools/sync_shared.py --check` 消除共享算法漂移，把运行时拆包留待未来大版本（v2.0+）再做独立评估。
2. **立即落地 B5-a：将 `short-drama-assets` 与 `short-drama-image-prompts` 合并为单一技能**
   - **最强理由**：视觉设定与生图提示词在工作流中紧密相邻，合并后可减少一次跨技能路由交接和一份 `SKILL.md` / `stage-contract.md` 维护面。
   - **为何不用**：ClawHub v1.x 已按现有 12 个公开 slug 发布并被创作者安装脚本、评估基线与下游文档直接引用，合并或废弃 slug 属于破坏性接口变更；且两阶段分别对应「纯文字设定与连戏锁建模」和「面向生图模型的视觉提示词编译」，各自仍有清晰独立使用场景（如已有设定表单独补出 Lookdev/变体生图提示词）。因此明确拒绝在 v1.x 内强行合并，保留现行 12 技能拓扑，仅将同类项冗余在单技能内收敛（如 `B5-c` 合并 `develop` 内部 4 份参考文档与抽离 `image-prompts/references/format-spec.md`）。
3. **一步把全部 Markdown 字段解析器也纳入 `src/_shared/` 构建期 vendoring**
   - **最强理由**：可把 `creator_markdown_check`、`production_tool`、`edit_tool` 的字段行解析实现统一成一份源码。
   - **为何不用**：三个脚本各自上下文约束不同（`creator_markdown_check` 需排除时钟前缀并做重复键诊断，`edit_tool` 需处理编号字段与未采用镜头行，`production_tool` 仅提取多值字段），强行抽成同一段大代码块反而增加每个脚本的冗余依赖与阅读负担。试点阶段仅对高度纯函数化的 `cn_num` 启用构建期同步，而用 `tests/test_cross_parser_parity.py` 的行为契约测试锁住四端解析器等价性，收益与复杂度平衡最优。

## Consequences

- **收益**：
  - 全仓 100 条阻断级不变量与 `short-drama-review` 清单实现 100% 自动对账，`structural_invariant` 不再包含不可判定的语义约束，脚本软门禁既提示风险又不误伤创作者工作流。
  - 修复冒号入粗体静默丢字段、英文断词、16:9 横屏排版、Remotion 非拉丁/CJK 字体崩溃、Dashboard 竞态与 `.git` 截断、过期文档示例等一批真实使用痛点。
  - 消除 `cn_num` 双份漂移，单集起稿、配乐条目、`export --manifest` 校验、外置适配器能力声明与外置 overlay 渲染均以 100% 向后兼容的方式落地，`develop` 参考与模板净省 14,644 字符。
- **代价与风险**：
  - 引入 `src/_shared/` 与 `tools/sync_shared.py` 后，修改 `chinese_to_int` 需先改权威源并执行 `python3 tools/sync_shared.py --write`（由测试与 CI 自动兜底，不会静默漂移）。
  - `creator_markdown_check.py` 与 `production_tool.py` / `edit_tool.py` 新增软警告输出，外部若按「stdout 必须完全为空」解析 CLI 输出需注意区分 `ERROR:` 与 `WARNING:`（退出码仍严格按硬错误 `0` / 非 `0` 区分）。
  - B1 运行时拆包与 B5-a 跨 slug 合并继续延后，技能目录内仍有部分跨脚本解析器以行为契约测试而非代码共享维持一致。
