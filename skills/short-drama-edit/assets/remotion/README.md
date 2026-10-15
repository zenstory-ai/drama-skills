# Remotion 叠层

`$short-drama-edit` 用它画两样东西：剪辑单里的**画面文字**（只有这一条路线），以及**可选的**
字幕排版（默认字幕路线是 ffmpeg + libass，无需 Node 依赖）。两者在同一遍里渲进一段透明叠层。
使用前需安装 Node 依赖；逐帧渲染的时间与内存开销见「代价」。

## 为什么走这条路

这里用 CSS 调整字号、描边、行距、安全区和折行，可在 `npx remotion studio` 中预览。
系统面板、逐条入场和倒计时分别由组件维护；两条字幕路线的尺寸口径见[声音、字幕与音乐](../../references/sound-and-subtitles.md)。

## 装一次

工作区在**项目之外**（默认 `~/.cache/short-drama-edit/remotion`）。`edit_tool.py` 每次运行都会
把本目录的源码同步过去，所以要改排版就改这里的 `src/`，不要改工作区里的副本——它会被覆盖。

```bash
cd ~/.cache/short-drama-edit/remotion && npm install
```

`node_modules` 不进项目也不进本仓库。字体也在这一步装上：`@fontsource/noto-sans-sc`
（思源黑体，用 700 与 900）和 `@fontsource/jetbrains-mono`（数字，用 800）。升级本技能后
`package.json` 多了依赖时，render 会点名缺的包并给出同一条命令。

## 用

剪辑单里有画面文字时，`render` 自动走这一遍。只想换字幕排版时：

```bash
python3 <本技能目录>/scripts/edit_tool.py render <剧集/EP001> --project-root <project> --subtitles remotion
```

它渲染出一段**透明**叠层（VP8 + alpha），再由 ffmpeg 合成到画面上；浏览器只绘制叠层，不解码或重绘视频。
字幕走 ffmpeg 路线时，Remotion 只画画面文字，字幕在合成后烧在上面。

## 画面文字的样式

每种样式是 `src/screen/` 里的一个组件，接收同样的 `{ text }`；颜色、入场、淡出、
面板位置这些共用的值在 `src/screen/tokens.ts`，系统类面板共用的框与部件在 `src/screen/chrome.tsx`。换一种样式的外观只改它自己的文件，
不碰剪辑单解析与时间换算。所有尺寸以画面高度的百分之一为单位。

倒计时由帧号直接算出：同一帧每次渲染显示同样的数字。

## 字体

字体随叠层打包，不依赖本机。字体按字符区段拆成许多小文件，浏览器只在排到某段文字时才去取，
那时这一帧可能已经截走了。所以叠层挂载时先按整部片子要画的字逐个字重调用
`document.fonts.load`，全部就绪、组件树提交之后才放出第一帧；十秒内没加载完、某个字重没有声明、
或加载后仍未就绪，渲染直接报错。等待按挂载注册并设上限。

画每段字之前再测一次宽：把字体栈分别接在 `serif` 与 `monospace` 两个兜底之前，与只有兜底时的
宽度相比，两边都一样才算字体没到位，这时同样报错，不悄悄换字体出片。

## 代价

叠层**逐帧**渲，长度等于整部成片：一分钟竖屏片一千多帧 1080×1920，每帧一次无头浏览器
截图，没字的帧照渲。透明还要求 PNG 抓帧加 VP8 编码，Remotion 的性能文档把这两样都列为
慢环节；实际耗时取决于成片时长、画幅和机器性能。

每个浏览器实例都占用内存，按 CPU 核数提高并发可能耗尽内存。`edit_tool.py` 显式传入
`--concurrency`，默认 2；提高前先在本机测量：

```bash
cd ~/.cache/short-drama-edit/remotion && npx remotion benchmark
```

## 许可证

使用 Remotion 前，按其[官方许可证](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)
核对适用授权；本套件的 MIT 许可证不覆盖 Remotion。剪辑单没有画面文字且字幕走默认路线时，无需安装 Remotion。

思源黑体（Noto Sans SC）与 JetBrains Mono 都是 SIL Open Font License 1.1：可以随成片使用、
嵌入和再分发，不能单独出售字体文件。许可证文本在各自的 `node_modules/@fontsource/*/LICENSE`。

## 文件

| 文件 | 作用 |
|---|---|
| `src/schema.ts` | 叠层的输入形状：字幕（文字、来源、重点词）、画面文字（各项与稀有度）、画幅、fps |
| `src/Overlay.tsx` | 合成本身：引入字体、等字体就绪，画面文字在下，字幕在上 |
| `src/Subtitles.tsx` | 字幕排版。所有尺寸都是画面高度的比例，同一组数值对 768×1344 和 1080×1920 都成立 |
| `src/screen/ScreenText.tsx` | 把每条画面文字放到成片时间上，按样式分派 |
| `src/screen/tokens.ts` | 字幕与各样式共用的字体、颜色、稀有度色、入场、淡出与位置 |
| `src/screen/chrome.tsx` | 系统类面板共用的框、角标括号、扫描线、标题行、打字机与奖励行 |
| `src/screen/Card.tsx` 等 | 每种样式一个组件：卡片、系统面板、任务面板、角标 |
| `src/rules.mjs` | 不需要浏览器的判断：要加载的字、加载结果是否可用、字体族是否缺失、打字进度、进度条、倒计时读数与脉冲。纯 JavaScript，测试直接用 Node 跑 |
| `src/font.ts` | 在渲染页里执行上面的字体判断 |
| `src/Root.tsx` | 合成注册；画幅、帧率、时长由调用方通过 `--props` 传入 |
| `remotion.config.ts` | 固定成带 alpha 的输出，叠层必须透明 |
