# Remotion 图文叠加层（可选）

本模块为 `short-drama-edit` 的**可选**图形渲染扩展，仅用于两类可选场景：渲染剪辑单中的 `画面文字` 图文层（含通用 `字卡`/`卡片`/`角标`，以及可选的系统流题材模板 `系统面板`/`任务面板`），或按需替代默认 `ffmpeg` 路线输出动态字幕排版。

> 常规剪辑、接镜调色、混音与默认字幕烧录（`ffmpeg` + `libass`）**不依赖 Node.js 或 Remotion**（两条字幕路线的字号与边距标准见 [声音字幕与响度](../../references/editing-guide.md#声音字幕与响度)）。

## 无 Node / Remotion 时的降级方案

若本机未安装 Node.js/npm，或处于受限无头环境无法启动无头浏览器：

1. **走 `ffmpeg` 渲染纯 `字卡` 或跳过画面文字**：`--screen-text-mode auto`（默认）在未装 Remotion 且全片仅含无框 `字卡` 时自动降级为 `ffmpeg` ASS 烧录并给出提醒（也可显式传 `--screen-text-mode ffmpeg`）；若剪辑单含复杂面板样式但当前环境无 Remotion，可传 `--screen-text-mode off` 跳过全部 `画面文字` 叠层（无需删改剪辑单），其余裁切、混音与字幕烧录（或 `--no-subtitles`）照常执行。
2. **接入外部透明叠层渲染器**：如需使用自定义图形管线替代 Remotion，可传 `--overlay-renderer <cmd>`，工具会写出 `叠层.props.json` 并调用外部命令生成透明叠层视频再由 `ffmpeg` 叠合。
3. **导出给外部 NLE 精修**：保留 `剧集/<EP>/剪辑单.md` 作为剪辑决策表，用 `--screen-text-mode off`（可按需加 `--no-subtitles`）输出干净母版与分段中间文件，配合 SRT/ASS 字幕交外部剪辑软件（剪映、Premiere、DaVinci Resolve 等）添加标题字卡与动效层。

## 跨平台安装与运行

运行工作区位于项目目录之外，默认为用户主目录下的 `.cache/short-drama-edit/remotion`（也可用 `--remotion-workspace <自定义项目外目录>` 指定其他路径）。`edit_tool.py` 每次渲染会自动同步本目录源码，调整样式只需修改本目录下的 `src/`。

**1. 安装依赖（需 Node.js 与 npm）**

- macOS / Linux：
  ```bash
  mkdir -p ~/.cache/short-drama-edit/remotion && cd ~/.cache/short-drama-edit/remotion && npm install
  ```
- Windows PowerShell：
  ```powershell
  New-Item -ItemType Directory -Force "$HOME\.cache\short-drama-edit\remotion" | Out-Null
  Set-Location "$HOME\.cache\short-drama-edit\remotion"
  npm install
  ```
  （首次未同步 `package.json` 时，先运行一次 `edit_tool.py render` 或手动把本目录 `package.json` 复制到工作区后再执行 `npm install`。）

**2. 触发渲染**

> 下文命令中 `<SKILL_DIR>` 指 `short-drama-edit` 技能目录，`<PYTHON>` 指 Python 3.9+ 解释器（macOS/Linux 用 `python3`，Windows 用 `py -3` 或 `python`）。

`--screen-text-mode auto|remotion|ffmpeg|off` 控制 `画面文字` 渲染路线（默认 `auto`：含复杂面板或本机已装 Remotion 时调用 Remotion，无 Remotion 且仅含普通 `字卡` 时自动降级为 `ffmpeg` ASS）；如需强制走 Remotion 或切换动态字幕路线，显式传入对应参数：

```bash
<PYTHON> "<SKILL_DIR>/scripts/edit_tool.py" render <剧集/EP001> --project-root <project> --screen-text-mode auto --subtitles remotion
```

Remotion 先渲染带透明通道的视频层（VP8 + alpha），再由 `ffmpeg` 叠合到成片画面；字幕走默认 `ffmpeg` 路线时，烧录层级位于画面文字之上。

## 字体、性能与许可证

- **内置字体包**：随 `npm install` 安装 `@fontsource/noto-sans-sc`（700/900 字重）与 `@fontsource/jetbrains-mono`（800 字重，SIL OFL 1.1），开渲前对常规汉字、拉丁字母与标点逐一核验内置字重已加载就绪（加载失败立即报错退出），Emoji 与特殊图形符号自然回退系统字体，不中断整片导出。
- **逐帧开销与并发**：无头浏览器按整片总帧数逐帧截屏并编码透明通道。`edit_tool.py` 默认传 `--concurrency=2` 防止撑爆内存；调高并发数前先在工作区运行 `npx remotion benchmark` 实测本机负载。
- **许可证**：正式使用前请对照 [官方许可证](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) 核对 Remotion 商用与授权条款；本套件的 MIT 许可证不涵盖 Remotion 本身。

## 源码结构

| 文件 | 作用 |
|---|---|
| `src/schema.ts` | 图文层输入参数结构（字幕、画面文字、画幅尺寸、帧率） |
| `src/Overlay.tsx` / `src/Root.tsx` | 字体就绪校验、图层上下关系（画面文字在下、字幕在上）与工程注册 |
| `src/Subtitles.tsx` | 按画面高度比例自适应排版的字幕组件 |
| `src/screen/ScreenText.tsx` / `tokens.ts` / `chrome.tsx` | 画面文字时间段分发、共用配色与动效参数及可选面板外框组件 |
| `src/screen/Caption.tsx` / `Card.tsx` 等 | 通用样式（`字卡`、`卡片`、`角标`）与可选系统流模板（`系统面板`、`任务面板`）组件 |
| `src/rules.mjs` / `src/font.ts` | 字体加载检查、打字机逐字进度、进度条与按帧倒计时纯函数 |
| `remotion.config.ts` | 透明 alpha 通道输出配置 |
