# AGENTS.md

短剧技能套件：一组把小说或创意做成短剧、漫剧的 agent skill，覆盖拆原著、写剧本、视觉设定、
分镜、图片与视频提示词、生产、剪辑、审查和本地创作台（Dashboard）。本文件是 agent 改这个
仓库时的约定；细则与理由见 [CONTRIBUTING.md](CONTRIBUTING.md)、[DESIGN.md](DESIGN.md) 和
`.agents/notes/`。

## 仓库结构

- `skills/*`：面向创作者的技能，每个目录是独立安装单元（`SKILL.md`、`references/`、
  `scripts/` 等）。`skills/short-drama` 负责项目初始化、跨阶段路由和 Dashboard。
- `maintainers/skills/short-drama-knowhow`：维护者专用技能，故意不放在 `skills/`，不要移动。
- `tests/`：unittest 测试；`evaluations/`：主工作流评估与人工实跑做法；`examples/`：合成示例。
- `.release/policy.json`：发布策略；`.clawhub/`：ClawHub 分发清单，说明见 `.clawhub/README.md`。

## 改动前

- 读 CONTRIBUTING.md；改创作台（`skills/short-drama/assets/dashboard/`、
  `skills/short-drama/scripts/dashboard_server.py`）先读 DESIGN.md。
- 非平凡改动先搜决策笔记，见下文「重要改动必须留笔记」。

## 硬规则

1. **技能自包含**：改一个技能，改动只落在它自己的目录。技能内 Markdown 相对链接解析后必须
   仍在本目录（`tests/test_installation_resolution.py` 检查）；跨技能只按技能名路由
   （如 `$short-drama-review`），不链对方的文件。
2. **知识与做法优先**：新能力先写进 `SKILL.md` 工作流或 `references/`；脚本只做稳定索引、
   结构校验、清单这类确定性工作，不把创作判断写成规则代码。
3. **规则分级**：每条规范归入 `structural_invariant` / `reviewed_invariant` /
   `craft_default` / `taste_option`；不得把统一的字数、比例、数量配方设为质量门槛。
4. **所有权与审查分离**：每个产物只有一个负责技能；修订不能冒充审查 verdict，自检要如实标注。
5. **来源边界**：不得提交非公开项目内容、内部标识、私有网址、供应商任务或媒体文件，
   示例一律合成改写；私有词表、扫描命中和私有来源指纹不得提交或写入公共日志。
6. **测试证明行为，不钉死文案**：不得新增只断言文档或源码包含/不包含某个字符串的测试。
7. **Python 下限 3.9**：`skills/*/scripts/*.py` 不得使用高于下限的标准库 API；下限同时写在
   各脚本的 `MINIMUM_PYTHON` 与两份 README，测试核对三处一致。
8. **创作台**：只用 Python 标准库服务端与原生 HTML/CSS/JS，不加依赖；仅回环访问、Host/Origin
   校验、路径约束、拒绝符号链接、原子保存与并发编辑保护都不得去掉；不把项目 HTML 注入 DOM；
   每个 server action 要有单元与 HTTP 测试。

## 验证

每次改动后必跑：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
ruff check --no-cache .
```

- 改了 `skills/*/scripts/` 时，按 CONTRIBUTING.md「Python 版本下限」在 3.9 解释器上再跑一次。
- CI（`.github/workflows/ci.yml`）另跑 3.9/3.10/3.14 测试矩阵、固定版本的 ruff 与 mypy、
  Dashboard 真实浏览器回归（`tests.test_dashboard_browser`，需 Playwright）和 Windows 回归。
- 发布候选另跑 `python3 -m unittest tests.test_workflow_evaluation`，并按
  [evaluations/README.md](evaluations/README.md) 在固定提交上人工实跑一次。
- 受保护发布检查（仓库外私有词表、fail-closed）见 CONTRIBUTING.md；普通开发不能声称已做过。

## 版本与发布

- 版本号遵循语义化版本，只写在根目录 `VERSION`（`.release/policy.json` 的 `versionFiles`
  唯一一项）。ClawHub 各技能的版本在 `.clawhub/publish.json` 单独维护，何时更新见
  `.clawhub/README.md`。
- `CHANGELOG.md`：待发布改动写进 `## [Unreleased]`；版本节为 `## [X.Y.Z] - YYYY-MM-DD`，
  小节只用 `Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`，正文中文；
  底部每个版本一行 compare 链接；历史小节不回头改写。归类判据见 CONTRIBUTING.md「更新日志」。
- 发版走 PR：`release: vX.Y.Z — 主题`，改 `VERSION` 与 CHANGELOG；合并后在 main 上打
  `vX.Y.Z` tag，由 `.github/workflows/release.yml` 建 Source release 并交接 ClawHub。
  打 tag 是单独的发布操作，只在维护者明确要求时做。
- 提交信息沿用 `feat(edit): …`、`fix: …`、`docs(readme): …` 的格式，描述用中文，说明
  哪个技能的哪类知识或确定性工作变了。

## 重要改动必须留笔记

决策笔记放在 `.agents/notes/{proposed,implemented,rejected}/{feature,bug-fix,simplification,architecture,process,testing}/yyyy-mm-dd-topic.md`，沿用 DeepSeek Harness 的 agent-notes 约定（方法见 https://github.com/czm15053/write-notes-like-deepseek）。正文中文，小节标题保留英文。

1. 非平凡改动（改了行为、架构、跨文件或跨 skill 契约、流程与工具链、测试策略、落盘格式）动手前，先在 `.agents/notes/` 里搜同主题旧笔记：有归属就地更新事实；没有就先写 `proposed/`，落地时随同代码改动在同一次提交里转 `implemented/`。纯机械改动（排版、改名、版本号、不改行为的补丁、常规 CRUD）直接提交，不写。
2. 笔记开头是 `# Agent Note: <标题>`、空行、`Status: <状态>`。每篇必有 `## Problem`、`## Decision`（现在时，只写已落地事实）或 `## Proposal`、`## Alternatives considered`（每个被否方案先写它最强的理由再写为何不用，没考虑过的不要编）、`## Consequences`（收益和代价都写）。
3. 禁止把一篇笔记改写成相反的决定：事实（路径、名字、默认值）就地改；决定翻转就另开一篇并互链。
4. 不建 `INDEX.md`，目录位置就是状态；检索用 `rg --hidden .agents/notes/`。
