# Remotion 图文叠加层

用于渲染剪辑单中的**画面文字**（唯一渲染路线）以及**可选的**动态字幕排版（默认字幕路线为 `ffmpeg` + `libass`；两条字幕路线的字号与边距标准见 [声音字幕与响度](../../references/editing-guide.md#声音字幕与响度)）。

## 安装与运行

运行工作区位于项目目录之外（默认 `~/.cache/short-drama-edit/remotion`）。`edit_tool.py` 每次渲染都会把本目录源码同步过去，调整样式只需修改本目录下的 `src/`：

```bash
cd ~/.cache/short-drama-edit/remotion && npm install
```

剪辑单含有 `画面文字` 时，`render` 会自动调用 Remotion；若只需切换字幕渲染路线，显式传入 `--subtitles remotion`：

```bash
python3 <本技能目录>/scripts/edit_tool.py render <剧集/EP001> --project-root <project> --subtitles remotion
```

Remotion 先渲染出带透明通道的视频层（VP8 + alpha），再由 `ffmpeg` 叠合到成片画面上；字幕走默认 `ffmpeg` 路线时，烧录层级位于画面文字之上。

## 字体、性能与许可证

- **内置字体包**：随 `npm install` 安装 `@fontsource/noto-sans-sc`（700/900 字重）与 `@fontsource/jetbrains-mono`（800 字重，SIL OFL 1.1），开渲前对常规汉字、拉丁字母与标点逐一核验所需内置字重已加载就绪（加载失败立即报错退出），Emoji 等超出 BMP 的补充平面符号则自然回退系统字体渲染，不再中断整片导出。
- **逐帧开销与并发**：无头浏览器按整片总帧数逐帧截屏并编码透明通道。`edit_tool.py` 默认传 `--concurrency=2` 防止撑爆内存；调高并发数前先运行 `cd ~/.cache/short-drama-edit/remotion && npx remotion benchmark` 实测本机负载。
- **许可证**：正式使用前请对照 [官方许可证](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) 核对 Remotion 商用与授权条款；本套件的 MIT 许可证不涵盖 Remotion 本身。

## 源码结构

| 文件 | 作用 |
|---|---|
| `src/schema.ts` | 图文层输入参数结构（字幕、画面文字、画幅尺寸、帧率） |
| `src/Overlay.tsx` / `src/Root.tsx` | 字体就绪校验、图层上下关系（画面文字在下、字幕在上）与工程注册 |
| `src/Subtitles.tsx` | 按画面高度比例自适应排版的字幕组件 |
| `src/screen/ScreenText.tsx` / `tokens.ts` / `chrome.tsx` | 画面文字时间段分发、共用配色与动效参数及系统面板外框组件 |
| `src/screen/Caption.tsx` / `Card.tsx` 等 | `字卡`、`卡片`、`系统面板`、`任务面板`、`角标` 五种画面文字组件 |
| `src/rules.mjs` / `src/font.ts` | 字体加载检查、打字机逐字进度、进度条与按帧倒计时纯函数 |
| `remotion.config.ts` | 透明 alpha 通道输出配置 |
