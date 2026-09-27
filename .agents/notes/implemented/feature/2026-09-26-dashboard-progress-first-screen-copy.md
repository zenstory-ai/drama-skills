# Agent Note: 创作台分集进度按五文档计算、正文回到首屏、提示词可一键复制

Status: implemented

首屏概览带与手机阅读栏已被 [按阶段分视图](2026-09-27-dashboard-v2-stage-views.md) 取代。

## Problem

对标提案（已删除，第 4–7 项见 [按阶段分视图](2026-09-27-dashboard-v2-stage-views.md)）第 1–3 项实测到的缺陷：

- `episodePresentation` 只认旧的 `shots.jsonl` / `keyframes.jsonl`，给出的下一步是错的。
- `slice(0, 6)` 让第 7 集起不可达。
- `fileLabel` 把 `SHOT-EP001-001.png` 改写成「shot ep001 001.png」。
- `审查/EP001-审查.md` 被放进「全剧」组。
- 项目有媒体时，阅读区顶端在 1440×900 下是 994px，375×812 下是 2068px，违背[单页创作台](2026-08-06-single-page-creator-dashboard.md)「始终可见的当前正文」。
- 可复制提示词只能手选。

## Decision

**分集进度**（`skills/short-drama/assets/dashboard/app.js`）

- `EPISODE_DOCUMENTS` 按顺序列出 `剧本.md`、`视觉设定.md`、`分镜.md`、`图片提示词.md`、`视频提示词.md`。
  只算直接位于 `剧集/<EP>/` 下的文件。
- `episodePresentation` 返回 `steps`（五个布尔值）、`label`（如 `3/5`）、`next`（第一份缺失文档）、`media`（`制作成果/` 的媒体数）与 `review`。
  只有图片提示词的一集，下一步是「剧本」。
- 一份五文档都没有、却有 `screenplay.md`、`*-prompts.md` 或 `shots/keyframes.jsonl` 的分集，按 v0.5 只读项目处理：沿用旧标签，不显示五点。
- 分集卡显示五个点、`N/5`、下一步，以及「N 项成果」「有审查意见」。

**分集条**：去掉 `slice(0, 6)`，改成单行横向滚动。每张卡带 `data-episode`。

**文件名**：`fileLabel` 先查 `FILE_LABELS`，没有就原样显示，只去掉 `.md/.json/.jsonl/.txt`，媒体扩展名保留。

**审查归集**：`episodeName` 把 `审查/<EP>-审查.md`（以及 `reviews/`）归到该集。EP 须符合 `project_tool.py` 的 `EPISODE_ID_RE`，所以 `审查/<主题>-审查.md` 仍在「全剧」。`collectEpisodes` 改用 `episodeName`。

**首屏**（`index.html`、`styles.css`）

- 概览是一条紧凑带：标题、四个数字、「阅读当前剧本」、分集条。
- 「已有制作成果」画廊移到正文与辅助卡之后。
- ≤620px 隐藏概览说明句，数字排成一行四格，目录列表最高 10rem。
- ≤420px 页头收成两行：品牌与状态一行，项目选择一行。
- 两种尺寸下，打开项目时 `#documentPane` 的顶端都在视口内。

**手机阅读栏**

- 文件名所在的 `.reading-bar` 同时放一个「目录」按钮（`#jumpToContents`）。
- ≤860px 时 `.document-toolbar` 设为 `display: contents`，阅读栏 `position: sticky; top: 0`，修改/保存按钮一行随正文滚走。
- 「目录」把 `#contentNav` 滚入视口，列表滚到当前条目并把焦点放上去。
- 宽屏不显示这个按钮。它不是抽屉，也不是标签页。

**复制按钮**（`renderMarkdown`）

- 最近一个标题是 `可复制提示词` 或 `冻结关键帧提示词` 时，其下的引用块与围栏代码块包进 `.copy-block`，并带「复制」按钮。
- 按钮的 `data-copy-text` 是源文本：引用去掉 `>` 与一个空格后按换行拼接；围栏逐字保留，包括 Markdown 记号。
- 复制时先用 `navigator.clipboard.writeText`，失败再走 `execCommand("copy")`。仍失败就选中该块，并提示按 ⌘/Ctrl + C。
- 只写剪贴板，不连任何服务。

**测试**

- `tests/test_dashboard_server.py` 的 node 用例：五文档组合与 legacy 回退、审查归集与主题审查、ID 原样、复制文本与 `examples/creator-first/EP001/视频提示词.md` 逐字一致，并覆盖多行、围栏和非提示词块。
- `tests/test_dashboard_browser.py` 的 `CreatorFirstDashboardBrowserTests`：8 集、3 张图、1 份审查的项目。
  - 两种尺寸都首屏可见，且无横向滚动。
  - 8 张卡都在，最后一张可打开。
  - 吸顶栏与目录跳转。
  - 授权剪贴板后读回复制内容。
- 以上都已对照改动前的代码确认会红。

## Alternatives considered

- **分集卡用可换行的网格**
  - 最强理由：所有集一眼看全，不用横向滚动。
  - 不用：高度随集数增长，50 集的项目又会把正文挤出首屏，与本次要修的问题相同。
- **把画廊做成概览里的折叠行**
  - 最强理由：媒体留在页首。提案把它列为两种做法之一。
  - 不用：折叠状态本身就是隐藏模式。提案已否「概览可折叠」，理由同样适用。
- **手机上让整条文档工具栏吸顶**
  - 最强理由：不新增元素。
  - 不用：窄屏工具栏连同修改/保存按钮约 130px，占掉阅读区近五分之一。
- **`fileLabel` 连媒体扩展名一起去掉**（提案原话「只去掉扩展名」）
  - 最强理由：更短。
  - 不用：同一镜的 `.png` 与 `.mp4` 会显示成同一个名字，而目录副标题只写「画面预览」，无法区分。
- **legacy 分集也按五文档打分**
  - 最强理由：只有一条代码路径。
  - 不用：v0.5 项目永远不会有五文档，这样会让创作者去写一份已经以旧格式存在的剧本。
- **所有围栏代码块都给复制按钮**
  - 最强理由：旧版 `*-prompts.md` 用围栏写提示词，却没有这两个标题。
  - 不用：说明性的代码示例也会带按钮。按钮范围跟随 `creator-documents.md` 的格式约定。

## Consequences

- **收益**：
  - 分集卡给出的下一步与五文档一致，所有集都可达。
  - ID 可以拿去正文里搜。
  - 阅读区在两种尺寸下打开即见：1440×900 约 310px，375×812 约 700px。
  - 手机读到一半一键回目录。
  - 提示词整段复制，不会漏行。
- **代价**：
  - `app.js` 从 1263 行增至 1420 行。
  - 手机上概览说明句不显示，≤420px 的页头布局也变了。
  - ≤860px 依赖 `display: contents` 让阅读栏成为文档面板的直接网格项。
  - 「第一份缺失文档」不看创作者声明的起点：有意只做提示词的一集，仍会提示下一步写剧本。
- **已知上限**：
  - 提案第 3 项测试写的是「`视频提示词.md` 的多行引用」，但示例里每条都是单行。多行情形改用合成的 H3 片段覆盖。
  - 本地没有 Playwright 自带的 Chromium 时，浏览器用例在 `setUpClass` 报错。CI 的 `dashboard-browser` job 会安装它。
