# Remotion 叠层

用于渲染剪辑单中的**画面文字**（唯一路线）及**可选的**字幕排版（默认字幕路线为 `ffmpeg` + `libass`；两条字幕路线的尺寸口径见 [声音、字幕与音乐](../../references/sound-and-subtitles.md)）。

## 安装与运行

工作区位于项目外（默认 `~/.cache/short-drama-edit/remotion`）。`edit_tool.py` 每次运行都会把本目录源码同步过去，修改样式只改本目录 `src/`：

```bash
cd ~/.cache/short-drama-edit/remotion && npm install
```

剪辑单含 `画面文字` 时 `render` 自动调用 Remotion；仅切换字幕排版时显式传入 `--subtitles remotion`：

```bash
python3 <本技能目录>/scripts/edit_tool.py render <剧集/EP001> --project-root <project> --subtitles remotion
```

Remotion 渲染出透明叠层（VP8 + alpha）后由 `ffmpeg` 合成到画面上；字幕走 `ffmpeg` 路线时烧录在画面文字之上。

## 字体、性能与许可证

- **打包字体**：随 `npm install` 安装 `@fontsource/noto-sans-sc`（700/900）与 `@fontsource/jetbrains-mono`（800，SIL OFL 1.1），渲染前校验全部字重就绪，超时或回退到系统兜底字体即直接报错退出。
- **逐帧开销與并发**：无头浏览器按整片帧数逐帧截屏并编码透明通道。`edit_tool.py` 默认传 `--concurrency=2` 防内存耗尽；调高前先运行 `cd ~/.cache/short-drama-edit/remotion && npx remotion benchmark`。
- **许可证**：使用前按 [官方许可证](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) 核对 Remotion 授权；本套件 MIT 许可证不覆盖 Remotion。

## 源码结构

| 文件 | 作用 |
|---|---|
| `src/schema.ts` | 叠层输入结构（字幕、画面文字、画幅、fps） |
| `src/Overlay.tsx` / `src/Root.tsx` | 字体就绪校验、图层顺序（画面文字在下、字幕在上）与合成注册 |
| `src/Subtitles.tsx` | 按画面高度比例计算的字幕排版 |
| `src/screen/ScreenText.tsx` / `tokens.ts` / `chrome.tsx` | 画面文字时间分派、共用色板/动效 token 与系统面板框体组件 |
| `src/screen/Card.tsx` 等 | `卡片`、`系统面板`、`任务面板`、`角标` 四种样式组件 |
| `src/rules.mjs` / `src/font.ts` | 字体加载校验、打字机进度、进度条与帧号倒计时纯函数 |
| `remotion.config.ts` | 固定透明 alpha 输出配置 |
