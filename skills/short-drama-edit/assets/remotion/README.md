# Remotion 叠层

`$short-drama-edit` 用它画两样东西：剪辑单里的**画面文字**（只有这一条路线），以及**可选的**
字幕排版（默认字幕路线是 ffmpeg + libass，零依赖）。两者在同一遍里渲进一段透明叠层。
它要装 Node 依赖，而且慢得多、吃内存——先看下面的「代价」。

## 为什么走这条路

ASS 的字号是相对 `PlayRes` 的单位，渲染时再缩放一次，这层间接每次都要重推一遍，推错了
在数字上看不出来（见[声音、字幕与音乐](../../references/sound-and-subtitles.md)）。这里字号、
描边、行距、安全区、折行都是 CSS，写的是画面像素，改完在 `npx remotion studio` 当场能看。
面板、发光、逐条入场和逐秒走动的倒计时是版面，不是字幕样式，ASS 画不了。

## 装一次

工作区在**项目之外**（默认 `~/.cache/short-drama-edit/remotion`）。`edit_tool.py` 每次运行都会
把本目录的源码同步过去，所以要改排版就改这里的 `src/`，不要改工作区里的副本——它会被覆盖。

```bash
cd ~/.cache/short-drama-edit/remotion && npm install
```

`node_modules` 不进项目也不进本仓库。

## 用

剪辑单里有画面文字时，`render` 自动走这一遍。只想换字幕排版时：

```bash
python3 <本技能目录>/scripts/edit_tool.py render <剧集/EP001> --project-root <project> --subtitles remotion
```

它渲染出一段**透明**的叠层（VP8 + alpha），再由 ffmpeg 叠到未经改动的画面上。画面本身
不经过浏览器重绘，所以不多一次画质损失。字幕走 ffmpeg 路线时，这一遍只画画面文字，
字幕在合成后烧在它上面。

## 画面文字的样式

每种样式是 `src/screen/` 里的一个组件，接收同样的 `{ text, fontFamily }`；颜色、入场、淡出、
面板位置这些共用的值在 `src/screen/tokens.ts`。换一种样式的外观只改它自己的文件，
不碰剪辑单解析与时间换算。所有尺寸以画面高度的百分之一为单位。

倒计时由帧号直接算出：同一帧每次渲染显示同样的数字。

## 字体

只用本机已装的字体族，不注册网络字体，也就不在渲染前等待字体加载——在带视频的渲染页里，
那次等待曾挂住整个渲染直到超时。字体族是否真的装上，由逐字体族测宽判断：把字体栈分别接在
`serif` 与 `monospace` 两个兜底之前，与只有兜底时的宽度相比，两边都一样才算一个都没装上，
这时渲染直接报错，不悄悄换字体出片。测宽样本里带拉丁字母，因为本机的中文兜底可能恰好就是
所要的字体。

## 代价

叠层**逐帧**渲，长度等于整部成片：一分钟竖屏片一千多帧 1080×1920，每帧一次无头浏览器
截图，没字的帧照渲。透明还要求 PNG 抓帧加 VP8 编码，Remotion 的性能文档把这两样都列为
慢环节。默认字幕路线是一次滤镜的事，这条是分钟级。

内存才是会出事的地方。Remotion 默认按 CPU 核数开浏览器实例，每个各持一整帧——10 核 8 GB
的机器上内存打满，整机停止响应，本套件就这么卡死过一次。所以 `edit_tool.py` 固定传
`--concurrency`，默认 2。要提高先量本机，别凭核数拍：

```bash
cd ~/.cache/short-drama-edit/remotion && npx remotion benchmark
```

## 许可证

Remotion 个人与小团队免费，超出规模需商业授权，条款以 [remotion.dev](https://www.remotion.dev/)
为准。本套件是 MIT，不包含也不代理这项授权，也不会替你安装它——缺依赖时只报错并给出命令。
剪辑单里没有画面文字、字幕走默认路线时，不涉及这件事。

## 文件

| 文件 | 作用 |
|---|---|
| `src/schema.ts` | 叠层的输入形状：字幕、画面文字、画幅、fps、字号与安全区比例 |
| `src/Overlay.tsx` | 合成本身：画面文字在下，字幕在上 |
| `src/Subtitles.tsx` | 字幕排版。所有尺寸都是画面高度的比例，同一组数值对 768×1344 和 1080×1920 都成立 |
| `src/screen/ScreenText.tsx` | 把每条画面文字放到成片时间上，按样式分派 |
| `src/screen/tokens.ts` | 各样式共用的颜色、入场、淡出与位置 |
| `src/screen/Card.tsx` 等 | 每种样式一个组件：卡片、系统面板、任务面板、角标 |
| `src/rules.mjs` | 不需要浏览器的判断：字体族是否缺失、是否要等字体、倒计时读数。纯 JavaScript，测试直接用 Node 跑 |
| `src/font.ts` | 在渲染页里执行上面的字体判断 |
| `src/Root.tsx` | 合成注册；画幅、帧率、时长由调用方通过 `--props` 传入 |
| `remotion.config.ts` | 固定成带 alpha 的输出，叠层必须透明 |
