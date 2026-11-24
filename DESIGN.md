# Short Drama Creator Workspace Design

## Status

- **Status:** Active
- **Primary surface:** `short-drama dashboard` (invoked with your agent host prefix, e.g. `/short-drama dashboard` in Claude Code / Antigravity or `$short-drama dashboard` in Codex)
- **Audience:** writers, directors, and independent short-drama creators

## Product principle

Creators move between series and episode stage views inside one local workspace:

```text
#topbar   场 · 项目切换 · 分集切换（上一集 / EP001 / 下一集） · 全局搜索（⌘K） · 亮暗主题
#stagebar 概况 · 剧本 · 设定 · 分镜 · 提示词 · 成片 · 审查
#view     当前阶段画布（分镜阶段右侧停靠 #inspector 单镜详情抽屉）
```

The series overview (`#/`) leads into episode stage views (`#/EP001` and
`#/EP001/{script,settings,board,prompts,film,review}`), while `#/files` serves as a secondary
all-files browser grouped by `全剧` and episode. Structured views are read-only; `编辑原文` opens
`#/edit?path=…&at=…` on the owning Markdown document and jumps to the relevant section. Runtime
records and integrity evidence stay outside product navigation.

## Goals

- Answer within ten seconds: which project, which episode, current stage, next action.
- Organize work by series, episode, creative stage, scene, character, and shot instead of raw files.
- Let creators read and edit story content without understanding its storage format.
- Keep save semantics explicit: saving persists the current Markdown and does not launch production.
- Explain problems in terms of audience or production impact.
- Hand off writing, generation, rendering, review, and export steps with copyable assistant prompts.

## Information architecture

```text
短剧创作台（Dashboard v2）
├── 顶栏 #topbar：品牌回首页（#/） · 项目面包屑/切换 · 分集菜单与前后集切换 · 搜索面板（#palette） · 主题切换
├── 阶段栏 #stagebar（分集内常驻横排 7 个标签）
│   └── 概况 · 剧本 · 设定 · 分镜 · 提示词 · 成片 · 审查
├── 主画布 #view
│   ├── 全剧总览（#/）：项目状态与 4 项指标 · 下一步待办（最多 3 条） · 8 格分集进度矩阵 · 节奏目标 · 人物卡 · 项目文件入口
│   ├── 本集阶段视图（#/EP001/…）：纸面剧本、视觉设定卡、分镜节奏条与卡片/表格、可复制提示词、9:16 成片与五轨剪辑时间线、分级审查卡
│   └── 次级页面：全部文件目录（#/files） · 原文阅读（#/file?path=…） · 原文编辑（#/edit?path=…&at=…）
└── 镜头抽屉 #inspector：在分镜视图右侧查看起始帧、成片片段、台词、出场设定、提示词与关联审查意见
```

Episode navigation lives in the horizontal `#topbar` + `#stagebar` chrome rather than a permanent
left file tree, keeping full horizontal width for scripts, storyboards, timelines, and drawers.
Hash routes support browser history, deep links to a specific asset/shot/finding, and bookmarks.

### Creator-facing progress and next actions

For modern creator-first projects, series status badges derive four plain-Chinese states directly
from episode progress and review findings (`创作中`、`需要修改`、`待你确认`、`可以导出`); `已采用`
and `需要更新` remain as legacy lifecycle compatibility fallbacks for older projects with tracked
artifact/lifecycle records. Episode progress is inferred directly from the five authoring
documents, post-production outputs, and review findings across **8 progress pips**:

`剧本 · 设定 · 分镜 · 图片词 · 视频词 · 剪辑 · 成片 · 审查`

Each episode's `nextFor()` action names the concrete next task instead of abstract readiness states:

- `未开始`（五份创作文档均未建立时在进度表弱化显示）
- `处理 N 条必须改的审查意见`（存在 `必须改` 审查项时最高优先）
- `写剧本` / `写视觉设定` / `写分镜` / `写图片提示词` / `写视频提示词`（按缺口顺序推进；已有视频提示词、剪辑单或成片时不再回头催补图片提示词）
- `出片后写剪辑单` / `按剪辑单渲染成片` / `审查这一集`
- `可以导出`（五份文档、剪辑单、成片与通过且无阻塞的审查齐全；旧版目录回退为 `旧版格式，按原文阅读`）

Actions that need writing, image/video generation, rendering, review, or export provide a
`复制给助手` button so creators confirm and execute them in conversation.

## Interaction rules

### Save

- Save persists the current edit (`Cmd/Ctrl+S` or button).
- The interface shows saved, saving, unsaved, and conflict states in plain language.
- Save does not confirm or launch external production.

### Revise or continue

- Structured stage views stay read-only; `编辑原文` opens the owning Markdown file at the matching heading or ID.
- Requests to write, revise, review, render, or export copy a clear Chinese instruction to send in conversation.

### Problems

Review finding cards (`必须改` / `建议改` / `可以更好`) present:

1. where it happens (`在哪`, linked to the scene, asset, or shot);
2. what is visible and why it hurts audience or production continuity (`看到了什么` / `为什么要改`);
3. the concrete target change (`改成什么样`);
4. a direct action (`复制修改请求`, alongside stage-level `编辑原文`).

Do not display internal severity tokens, reviewer identities, storage paths, hashes, or protocol states.

## Visual language

- Use the shared ZenStory tokens (`tokens.css`): warm paper (`#faf5ea` / `#fdfbf5` / `#f2ebdc`) with navy ink
  (`#081431`) in light mode, deep navy surfaces (`#081431` / `#0d1a3a` / `#15254d`) with cream text (`#f7edd8`)
  in dark mode, and cyan (`#0891b2` / `#22d3ee`) for focus rings and current stage/selection.
- Use the signal vermilion (`#c2412b` / `#e5694c`) for next-step callouts and danger (`#b3302a` / `#ec7a70`) for
  `必须改` items; keep success, warning, and danger colors paired with words and icons.
- System sans-serif for controls, a readable local serif stack for screenplay paper, monospace for
  episode/scene/shot IDs, and `tabular-nums` for durations and counts.
- Use the sticky stage header, paper-like screenplay sheet, framing thumbnails, and rhythm/timeline
  strips as the defining visual motifs.
- Avoid metric-card walls, decorative gradients, and code-editor styling.

## Accessibility and responsive behavior

- Native buttons, labels, headings, ARIA tab/dialog semantics, and live status regions.
- Visible keyboard focus plus `Cmd/Ctrl+S` save, `⌘K` / `/` search palette, `←/→` or `j/k` shot
  drawer stepping, and `Esc` dismissal.
- No state depends on color alone: stage dots, progress pips, rhythm checks, and review severities
  pair icons and text labels with color.
- Desktop uses the sticky `#topbar` + `#stagebar` header above a full-width `#view` canvas, with
  contextual rails where helpful (scene/speaker rails in `剧本`, sticky right `#inspector` drawer
  in `分镜`, sticky 9:16 player beside the five-track timeline in `成片`).
- Narrow viewports (`<=1280px` / `<=900px` / `<=760px`) progressively stack multi-column views,
  collapse the 8-column episode matrix into `.ep-cards`, convert `#inspector` into a full-width
  overlay sheet, keep `#stagebar` horizontally scrollable (`44px` tab bar height at `<=760px`),
  and size controls compactly (`28px` `.btn.sm` / `.step-btn` / `.seg` items, `32px` `.btn`, `34px` `.icon-btn`).
- Honor `prefers-reduced-motion`.

## Creator-visible files

The core authoring handoff is:

```text
项目/
├── 输入/
├── 剧集/
│   └── EP001/
│       ├── 剧本.md
│       ├── 视觉设定.md
│       ├── 分镜.md
│       ├── 图片提示词.md
│       ├── 视频提示词.md
│       └── 剪辑单.md
├── 审查/
│   └── EP001-审查.md
└── 交付/
```

Each episode stage view parses its owning Markdown document (`剧本.md`, `视觉设定.md`, `分镜.md`,
`图片提示词.md` + `视频提示词.md`, `剪辑单.md`, and `审查/EP001-审查.md`) alongside generated
keyframes, clips, audio, and rendered film media, while `#/files` lists all creator-visible project
and episode files by purpose without creating a second source of truth.

## Implementation constraints

- Python standard-library server and vanilla HTML/CSS/JS; no new dependency.
- Loopback-only session, Host/Origin validation, path containment, symlink refusal,
  atomic save, and concurrent-edit protection remain mandatory.
- Never inject project HTML into the DOM.
- The browser submits creator actions and content identifiers; it does not submit hashes,
  manifests, or arbitrary output paths.
- Every server action needs unit and HTTP coverage.
- Every visual change needs desktop and narrow-layout inspection.

## Maintaining the workspace

Routes and stage views are defined in `skills/short-drama/assets/dashboard/app.js`; read-only
document parsing lives in that skill's `scripts/creator_views.py` and `scripts/dashboard_server.py`. Keep structured views aligned with
the owning document parsers and save through the existing version-checked Markdown path.
See the [stage-view decision](.agents/notes/implemented/feature/2026-09-27-dashboard-v2-stage-views.md)
for the accepted architecture and tradeoffs.
