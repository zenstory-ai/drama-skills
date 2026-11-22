# Agent Note: CI 加固、路径门控、媒体测试 fail-closed 与 Remotion 类型检查

Status: Implemented

## Problem

既有 CI（`.github/workflows/ci.yml`）存在六类高价值缺口与浪费：

1. **32 项 `ffmpeg` / `ffprobe` / `libass` 测试在 CI 静默跳过**：Ubuntu runner 未装 `ffmpeg`，`test_breakdown_tool.py`、`test_edit_measurements.py`、`test_edit_cut_continuity.py`、`test_edit_screen_text.py` 的 `@unittest.skipUnless` 在 CI 全部悄悄跳过，视频测量、接镜色度、音频无缝拼接与无 Remotion 字卡降级路径从未在 CI 实跑。
2. **矩阵冗余与纯文档 PR 跑满全套重任务**：`py3.10` 夹在声明下限 `3.9` 与最新 `3.14` 之间无增量信号；仅改 Markdown / 清单的 PR 也要跑完 3 个 Python 矩阵 + Playwright Chromium 全量下载 + Windows runner；缺少统一的 `ci-gate` 汇总门禁，分支保护被迫绑定具体子任务名。
3. **Windows 回归覆盖不全且硬编码测试方法名**：`windows-install` 缺少 Node 20（跳过 JS 逻辑回归），且硬编码两条 `test_simple_lifecycle` 方法名，同时漏掉 `test_confirmed_production`（含 5 处 `nt`/`msvcrt` 分支）、`test_provider_adapters`、`test_shipping_boundaries`、`test_cross_parser_parity` 与 `test_creator_first_golden`。
4. **Remotion 15 份 `.ts/.tsx` 源码零类型检查**：`lint` 只用 `node --check` 检过 `rules.mjs`，从未运行 `tsc --noEmit`。
5. **`ruff` 仅跑默认子集、`mypy` 依赖硬编码 17 文件清单**：新脚本可能漏入类型检查；`skills/*/scripts/*.py` 未开启严格注解与 `Any` 返回检查；`SKILL.md` 文档命令与脚本实际 argparse 子命令之间缺少自动对账；`tests/test_voice_direction.py` 仅做单行文档字符串断言，违反「测试证明行为，不钉死文案」。
6. **工作流权限与定时卫生**：`release.yml` 顶层默认给了 `contents: write`；部分作业缺 `timeout-minutes` 或 `concurrency`；`publish-clawhub.yml` 每 12 小时全量对账频率过高且未升级至新版 `zenstory-ai/.github` 控制平面（含无差异短路与 exit 2 摘要）。

## Decision

1. **激活全部媒体测试并 fail-closed**：
   - 新增 `tests/media_require.py`（`has_ffmpeg(require_ass=..., include_local_bin=...)`），对齐 `DASHBOARD_BROWSER_REQUIRED=1` 模式：未设 `FFMPEG_REQUIRED=1` 时本地无 `ffmpeg` 仍优雅跳过；设 `FFMPEG_REQUIRED=1` 时若缺失 `ffmpeg`、`ffprobe` 或 `libass`（`ass` 滤镜）直接抛 `RuntimeError`。
   - `ci.yml` 的 `test` 矩阵在 `py3.9` 与 `py3.14` 上安装 Ubuntu `ffmpeg`、核验 `ass` 滤镜存在，并以 `FFMPEG_REQUIRED=1` 运行全量 `unittest`。
2. **矩阵收敛、路径门控、Playwright 缓存与 `ci-gate`**：
   - Python 矩阵收敛为 `["3.9", "3.14"]`（保留下限与最新运行时）。
   - 新增 `changes` 作业（仅用内置 `git diff --name-only "$BASE_SHA...HEAD"`，不引入外部未审核 action）：`push` 到 `main` 始终全量运行以满足 `.release/policy.json` 的 `source_release.py ci-proof`；纯文档 PR（无 `.py/.js/.mjs/.ts/.tsx/.css/.html`、非代码目录 `.json/.jsonl`、`pyproject.toml` 或 `ci.yml` 改动）走快速 `docs-checks`（覆盖安装链接、发货边界、套件解剖、引用完整性、独立工具链、输出语种、上游追溯、黄金样例与工作流评估），跳过重型浏览器/Windows/媒体任务。
   - `dashboard-browser` 使用固定 SHA 的 `actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830`（v4）缓存 `~/.cache/ms-playwright`，命中时仅补装系统依赖 `playwright install-deps chromium`。
   - 新增 `if: always()` 的 `ci-gate` 汇总作业，强制校验 `changes` 成功、无任何上游作业 `failure`/`cancelled` 且至少运行了一项验证作业；同步更新 `.release/policy.json` `ciWorkflows`（保留 `push` 到 `main` 全量运行的 7 个精确作业名，含 `Remotion typecheck` 与 `ci-gate`）。
3. **扩展 Windows 回归并移除硬编码方法名**：
   - `windows-install` 引入固定 SHA 的 `actions/setup-node`（Node 20），改为按模块整跑 `test_installation_resolution`、`test_shipping_boundaries`、`test_standalone_skill_tooling`、`test_episode_intake`、`test_golden_project`、`test_simple_lifecycle`、`test_dashboard_server`、`test_confirmed_production`、`test_provider_adapters`、`test_cross_parser_parity`、`test_creator_first_golden`。
4. **独立目录的 Remotion TypeScript 类型检查**：
   - 新增仓内测试专用目录 `tests/remotion-typecheck/`（`package.json`、`package-lock.json`、`tsconfig.json` 与 `types/remotion.d.ts`），仅依赖 `typescript` 与 `@types/react`（3 个包、4KB lockfile），指向 `../../skills/short-drama-edit/assets/remotion/{remotion.config.ts,src/**/*}` 做 `strict: true` 的 `tsc --noEmit`，避免把 lockfile 或 `node_modules` 塞进随包发布的 `skills/short-drama-edit/`。
   - `ci.yml` 新增 `Remotion typecheck` 作业，在 Remotion 相关路径、`ci.yml`/`pyproject.toml` 改动及 `push` 到 `main` 时运行。
5. **最小 `pyproject.toml` 与自动发现严格 `mypy`**：
   - 新增 `pyproject.toml`，配置 `target-version = "py39"` 与 `[tool.ruff.lint]`（`E4`, `E7`, `E9`, `F`, `B`, `C4`, `PIE`, `S310`, `S108`, `SIM`，忽略 `B905`、`SIM115`，测试目录忽略 `S108`、`SIM117`）；修复脚本与测试中的全部 lint 命中（含 `B904` 异常链、`B023` 循环闭包绑定、`SIM105`/`C420`/`SIM114` 等，对已校验 HTTPS 的 `provider_adapters.py`、`darwin` 系统软链检查及跨平台 `msvcrt` `getattr` 显式标注 `# noqa`）。
   - `lint` 作业改为自动发现 `skills/*/scripts/*.py`，在 `mypy==2.3.0 --python-version 3.10` 与 `mypy==1.19.1 --python-version 3.9` 上均启用 `--disallow-untyped-defs --warn-return-any --disallow-any-generics --warn-unused-ignores`，并自动发现 `tests/legacy/*/scripts/*.py`、`evaluations/content_quality_gate.py` 与 `tools/compact_refs.py`；修复 `skills/*/scripts/*.py` 中 22 处及 `storyboard_check.py` 中 1 处类型问题。
6. **`SKILL.md` CLI 子命令契约测试与删除冗余文案测试**：
   - 在 `tests/test_standalone_skill_tooling.py` 新增 `test_skill_docs_only_reference_registered_cli_subcommands`，解析所有 `skills/*/SKILL.md` 中的 `<PYTHON> <SKILL_DIR>/scripts/<script>.py <subcommand>`，通过子进程探针核对每个子命令确实注册在对应脚本的 `argparse` 子解析器中。
   - 删除仅断言单行文档字符串的 `tests/test_voice_direction.py`。
7. **工作流权限收紧、定时收敛与控制平面升级**：
   - `release.yml` 顶层 `permissions` 收紧为 `contents: read`（由各作业按需申请写权限）；全工作流补齐 `timeout-minutes` 与 `validate-clawhub.yml` 的 `concurrency`；`publish-clawhub.yml` 定时对账改为每周一次（`17 3 * * 1`）；`validate-clawhub.yml` 与 `publish-clawhub.yml` 的中央控制平面 pin 同步升级至 `c3fe6ce840b369b4535121a6283dde24e486c2bc`。
   - 对本次涉及类型与 lint 修订的技能同步升级 `.clawhub/publish.json` patch 版本并重新生成 `packageDigest`。

## Alternatives considered

1. **在 `skills/short-drama-edit/assets/remotion/` 内直接提交 `package-lock.json` 并安装 `remotion` 跑 `tsc`**：
   - 最强理由：直接使用真实 `remotion` 类型包，无需维护 `remotion.d.ts`。
   - 为何不用：`skills/short-drama-edit` 是 ClawHub 独立发布包，随包塞入大型 `package-lock.json` 会膨胀发布体积并引入维护噪音，且安装 `@remotion/cli` 会拉取跨平台原生二进制包；独立的 `tests/remotion-typecheck/` 仅 3 个包即可在 2 秒内完成严格 `tsc --noEmit`，同时保持技能包干净。
2. **使用第三方 `dorny/paths-filter` action 做路径过滤**：
   - 最强理由：YAML 规则语法直观。
   - 为何不用：会引入新的外部第三方 action 供应链审查面；本仓 `changes` 作业仅需 ~35 行内置 `git diff --name-only "$BASE_SHA...HEAD"` + `grep -Eq`，零额外依赖且完全透明。
3. **只放 `ci-gate` 进 `.release/policy.json`**：
   - 最强理由：配置最短。
   - 为何不用：`source_release.py ci-proof` 校验的是 `push` 到 `main` 的 CI 运行，在 `.release/policy.json` 保留全量 7 个精确作业名可确保发版时 `py3.9`、`py3.14`、Playwright、Windows、lint、Remotion 与 `ci-gate` 全部逐项有据可查，而分支保护只需绑定 `ci-gate` 即可让纯文档 PR 走快路径不死锁。

## Consequences

- **收益**：32 项媒体测试在 `py3.9` / `py3.14` 上 fail-closed 实跑；纯文档 PR CI 从数分钟降至 ~20 秒；Windows 覆盖全部关键平台敏感测试模块；15 份 Remotion `.ts/.tsx` 纳入严格类型检查；`ruff` 与自动发现严格 `mypy` 拦截更多静态缺陷；`SKILL.md` CLI 文档与脚本子命令 drift 自动报错；分支保护统一收敛到 `ci-gate`，后续调整子矩阵不再死锁。
- **代价**：`skills/short-drama-edit/assets/remotion/` 若引入新的 `remotion` 导出符号，需同步补充 `tests/remotion-typecheck/types/remotion.d.ts`；改动 `skills/*/scripts/*.py` 需保持严格类型注解与 `pyproject.toml` 中的 `ruff` 规则。
