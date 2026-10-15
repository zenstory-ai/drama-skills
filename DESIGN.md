# Short Drama Creator Workspace Design

## Status

- **Status:** Active
- **Primary surface:** `$short-drama dashboard`
- **Audience:** writers, directors, and independent short-drama creators

## Product principle

Creators move between project and episode views inside one local workspace:

```text
项目标题与状态
阶段导航 | 当前视图
待办提示与导出提示
```

The project overview leads to episode views for the script, settings, storyboard, prompts,
film and review. Structured views are read-only; “编辑原文” opens the owning Markdown document
for editing. Runtime records and integrity evidence stay outside product navigation.

## Goals

- Answer within ten seconds: which project, which episode, current work, next action.
- Organize work by project, episode, scene, character, and shot instead of files.
- Let creators read and edit story content without understanding its storage format.
- Keep save semantics explicit: saving persists the current Markdown and does not launch production.
- Explain problems in terms of audience or production impact.
- Export production materials by purpose.

## Core authoring groups

```text
短剧创作台
├── 当前项目与一句状态说明
├── 内容目录
│   ├── 全剧
│   └── EP001
│       ├── 故事与剧本
│       ├── 人物场景
│       ├── 分镜画面
│       └── 生成文案
├── 当前视图（概况、剧本、设定、分镜、提示词、成片或审查）
└── 待办提示 / 导出提示
```

Episode navigation follows creative stages. Documents appear as formatted text, cards or
media previews; a shot detail drawer supplies focused inspection. Project files remain
accessible through a separate content list, and hash routes support back navigation and bookmarks.

### Creator-facing progress

Infer progress from the five visible documents and media, without a separate lifecycle file:

- 未开始
- 创作中
- 提示词就绪
- 已有媒体

The project overview and episode stage bar summarize available documents, media and review work.
Actions that need writing, production or rendering copy a request for the assistant; creators complete
them in conversation.

## Interaction rules

### Save

- Save persists the current edit.
- The interface shows saved, saving, unsaved, and conflict states in plain language.
- Save does not confirm or launch external production.

### Revise or continue

- The creator reads and edits the current document in place.
- Requests to revise, continue, review, export, or produce return to the conversation.

### Problems

Problem cards contain:

1. the scene or shot;
2. the audience or production impact;
3. the intended result;
4. a direct action.

Do not display internal severity names, reviewer identities, storage paths, or protocol
states.

## Visual language

- Use the shared ZenStory tokens: warm paper with navy ink in light mode, navy surfaces
  with cream text in dark mode, and cyan for focus and current position.
- Use the signal color for next actions and required changes; keep success, warning and
  error colors paired with words and icons.
- System sans-serif for controls and a readable local serif stack for screenplay content.
- Use the content rail and paper-like reading area as the defining visual motif.
- Avoid metric-card walls, decorative gradients, and code-editor styling.

## Accessibility and responsive behavior

- Native buttons, labels, headings, and live status regions.
- Visible keyboard focus and Cmd/Ctrl+S support.
- No state depends on color alone.
- Desktop uses a compact content rail plus one permanent content canvas.
- Narrow layouts stack navigation and content with 44px touch targets.
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
│       └── 视频提示词.md
├── 审查/
│   └── EP001-审查.md
└── 交付/
```

The Dashboard classifies the five Chinese document names into story, settings, storyboard
and prompt groups. The episode overview links to available work; editing and review may add
`剪辑单.md` and review documents without creating another source for the five core texts.

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
