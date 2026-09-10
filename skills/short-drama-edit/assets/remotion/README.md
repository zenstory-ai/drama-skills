# Remotion 字幕叠层

`$short-drama-edit` 的**可选**字幕渲染路线。默认路线是 ffmpeg + libass，零依赖；这一条排版
更好，但要装 Node 依赖，而且慢得多、吃内存——先看下面的「代价」。

## 为什么会有第二条路

ASS 的字号是相对 `PlayRes` 的单位，渲染时再缩放一次，这层间接每次都要重推一遍，推错了
在数字上看不出来（见[声音、字幕与音乐](../../references/sound-and-subtitles.md)）。这里字号、
描边、行距、安全区、折行都是 CSS，写的是画面像素，改完在 `npx remotion studio` 当场能看。

## 装一次

工作区在**项目之外**（默认 `~/.cache/short-drama-edit/remotion`）。`edit_tool.py` 每次运行都会
把本目录的源码同步过去，所以要改排版就改这里的 `src/`，不要改工作区里的副本——它会被覆盖。

```bash
cd ~/.cache/short-drama-edit/remotion && npm install
```

`node_modules` 不进项目也不进本仓库。

## 用

```bash
python3 <本技能目录>/scripts/edit_tool.py render <剧集/EP001> --project-root <project> --subtitles remotion
```

它渲染出一段**透明**的字幕层（VP8 + alpha），再由 ffmpeg 叠到未经改动的画面上。画面本身
不经过浏览器重绘，所以不多一次画质损失。

## 代价

叠层**逐帧**渲，长度等于整部成片：一分钟竖屏片一千多帧 1080×1920，每帧一次无头浏览器
截图，没字幕的帧照渲。透明还要求 PNG 抓帧加 VP8 编码，Remotion 的性能文档把这两样都列为
慢环节。默认路线是一次滤镜的事，这条是分钟级。

内存才是会出事的地方。Remotion 默认按 CPU 核数开浏览器实例，每个各持一整帧——10 核 8 GB
的机器上内存打满，整机停止响应，本套件就这么卡死过一次。所以 `edit_tool.py` 固定传
`--concurrency`，默认 2。要提高先量本机，别凭核数拍：

```bash
cd ~/.cache/short-drama-edit/remotion && npx remotion benchmark
```

## 许可证

Remotion 个人与小团队免费，超出规模需商业授权，条款以 [remotion.dev](https://www.remotion.dev/)
为准。本套件是 MIT，不包含也不代理这项授权，也不会替你安装它——缺依赖时只报错并给出命令。
默认路线不涉及这件事。

## 文件

| 文件 | 作用 |
|---|---|
| `src/schema.ts` | 叠层的输入形状：cues、画幅、fps、字号与安全区比例 |
| `src/Subtitles.tsx` | 排版本身。所有尺寸都是画面高度的比例，同一组数值对 768×1344 和 1080×1920 都成立 |
| `src/Root.tsx` | 合成注册；画幅、帧率、时长由调用方通过 `--props` 传入 |
| `src/font.ts` | 渲染前等字体就绪，并验证字体族真的存在——装不上时报错，而不是悄悄换一款字体出片 |
| `remotion.config.ts` | 固定成带 alpha 的输出，叠层必须透明 |
