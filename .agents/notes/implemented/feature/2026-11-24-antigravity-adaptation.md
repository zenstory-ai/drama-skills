# Agent Note: 适配 Google Antigravity（agy CLI / IDE / App）

Status: implemented

## Problem

仓库此前只在安装说明、贡献指南、设计文档与创作指南中写明 Claude Code（`~/.claude/skills/`、`/short-drama`）与 Codex（`${CODEX_HOME:-$HOME/.codex}/skills/`、`$short-drama`），尚未给出 Google Antigravity（CLI `agy`、IDE、App）的发现路径、安装方式与调用写法；同时直接打开本仓库副本时，Antigravity 不会自动从仓库根目录的 `skills/` 发现这 12 个公共技能。

## Decision

按 Antigravity 的官方自定义发现规范（`agy-customizations` 与 Antigravity 官方文档）补齐一等支持，同时守住仓库既有硬规则（技能自包含、`VERSION` 单一版本源、不向创作者分发 `maintainers/skills/short-drama-knowhow`）：

1. **新增仓库工作区技能清单 `.agents/skills.json`**：声明 `entries: [{ "path": "skills" }]`。在 Antigravity（CLI、IDE、App）中打开本仓库副本时，系统按工作区根目录相对路径单层扫描 `skills/`，自动发现全部 12 个公共技能，且不会扫入 `maintainers/skills/short-drama-knowhow`。`.agents/` 已在 `.release/policy.json` 的 `excludePaths` 中，不影响发布归档与 ClawHub 单技能包指纹。
2. **保持 12 个 `skills/*/SKILL.md` 不变**：自 `v0.13.0` 起全部公共技能已统一使用宿主中立的技能名（如 `short-drama-write`），且 YAML frontmatter（`name`、`description`、`license: MIT`）已原生符合 Antigravity 技能规范，实测 `agy plugin validate` 对全部 12 个技能无报错无警告；无需改动 `skills/` 目录，避免无意义改动 `.clawhub/publish.json` 包指纹。
3. **不新增 `GEMINI.md`**：Antigravity 原生按目录向上发现 `AGENTS.md` 与 `GEMINI.md`（与 Claude Code 需要 `CLAUDE.md` 的 `@AGENTS.md` 转发不同），根目录已有的 `AGENTS.md` 直接生效。
4. **同步安装与调用文档**：
   - `README.md` 与 `README_EN.md`：`npx skills add zenstory-ai/drama-skills -y -g` 已原生支持 `antigravity` / `antigravity-cli`（全局写入 `~/.gemini/config/skills/`、工作区写入 `.agents/skills/`）；手动软链段新增 Antigravity 全局链接命令（`$HOME/.gemini/config/skills/`）、项目级 `.agents/skills/` 说明、仓库副本 `.agents/skills.json` 自动加载说明及 `agy` TUI 的 `/skills reload` 刷新命令；调用前缀与创作台启动段补齐 Antigravity 使用 `/short-drama`（与 Claude Code 一致）及自然语言自动激活的说明。
   - `CONTRIBUTING.md` 与 `DESIGN.md`：维护者专用 `maintainers/skills/short-drama-knowhow` 的 `SKILLS_DIR` 列表补上 Antigravity（`"$HOME/.gemini/config/skills"`），宿主中立技能名约定与创作台入口说明同步补齐 Antigravity。
   - `docs/` 下七份提及宿主调用写法的创作指南（含 `docs/comic-drama-workflow.md` 及六份专题/流程指南）同步补上 Antigravity；`docs/open-source-ai-short-drama-tools.md` 为带明确核对日期（2026-10-30）的横向快照文，保持原样。
5. **行为回归测试**：在 `tests/test_installation_resolution.py` 中新增两项行为测试——按 Antigravity 单层扫描规则解析 `.agents/skills.json` 并验证发现结果严格等于 `EXPECTED_SKILLS`（不含 `short-drama-knowhow`），以及验证 `short-drama` 链接到 `~/.gemini/config/skills/short-drama` 与 `<workspace>/.agents/skills/short-drama` 后 `project_tool.py` 能从无关工作目录正常初始化与查询项目（不支持符号链接的平台自动退回目录复制，保持 Windows CI 可跑）。

## Alternatives considered

- **在仓库根目录新增 `.antigravity-plugin/plugin.json` 以支持 `agy plugin install https://github.com/zenstory-ai/drama-skills`**。最强理由：用户不用装 Node.js / `npx`，一条原生 `agy` 命令即可安装并支持 `agy plugin list/enable/disable`。被否：实测 `agy plugin install` 会把整个仓库根目录（含 `maintainers/skills/short-drama-knowhow`、`tests/`、`evaluations/`、`examples/`、`.git/` 与 `AGENTS.md`）整份复制到 `~/.gemini/config/plugins/drama-skills/`，违背 `CONTRIBUTING.md`「维护者技能不向普通创作者分发」的边界；同时 `agy plugin validate --strict` 会报两条警告——根目录 `AGENTS.md` 被判定为未放在 `rules/` 下而永不加载（但它属于仓库贡献规范而非用户插件规则），以及缺失 `version`（若在 `plugin.json` 里再写一份版本号，则与 `AGENTS.md`「版本号只写在 `VERSION`」冲突）。与仓库同样不发布 `.claude-plugin/plugin.json` 保持一致。
- **在仓库根目录新增 `GEMINI.md`（写 `@AGENTS.md`）**。最强理由：视觉上与 `CLAUDE.md` 对称。被否：Antigravity 原生读取 `AGENTS.md` 并对多路径规则去重，多建一层转发文件没有功能增量。
- **把 `skills/*` 复制或符号链接进 `.agents/skills/`**。最强理由：不依赖 `skills.json`。被否：跨平台（尤其 Windows）提交仓库内符号链接维护脆弱，复制目录则制造双份真相；`.agents/skills.json` 是 Antigravity 官方推荐的仓库共享方式，零冗余。
- **在 12 个 `skills/*/SKILL.md` 内补写 Antigravity 专属的 `/short-drama-*` 前缀或说明**。最强理由：让 Antigravity 用户打开单个 `SKILL.md` 时也能看到 `/` 前缀。被否：Antigravity 按技能名和描述匹配技能，不要求正文写 `/`；且违背 `CONTRIBUTING.md`「所有 `SKILL.md` 统一使用宿主中立技能名、各宿主前缀统一在 README 说明」的约定，还会触发全部 ClawHub 包指纹变更。

## Consequences

- **收益**：Antigravity（CLI `agy`、IDE、App）用户在 `npx skills`、手动全局/工作区链接和直接打开仓库副本三种场景下都有准确可执行的路径与命令，全仓文档调用写法与实际行为一致，并有自动化测试守住 `.agents/skills.json` 发现集合与 symlink 布局运行行为。
- **代价**：暂不支持通过 `agy plugin install <repo-url>` 直接安装整仓；未来如果决定向 Antigravity Marketplace 发布独立插件包，应在独立打包流程中只装配公共 `skills/` 并由发布脚本从 `VERSION` 注入清单版本，而不是把插件清单直接挂在含 `maintainers/` 与 `tests/` 的仓库根上。

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v` 全量通过。
- `ruff check --no-cache .`、`python3 tools/sync_shared.py --check` 与 Python 3.9 下限回归通过。
- 隔离临时目录验证全局 `~/.gemini/config/skills/` 与项目级 `.agents/skills/` 符号链接布局下 `short-drama/scripts/project_tool.py` 的 `init` 与 `status` 正常执行。
