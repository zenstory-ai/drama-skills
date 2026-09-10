# Remotion 字幕叠层

这是 `$short-drama-edit` 的**可选**字幕渲染路线。默认路线是 ffmpeg + libass，不需要任何外部
依赖；这一条排版更好，代价是要装 Node 依赖。

## 为什么会有第二条路

字幕格式（ASS）把字号写成相对 `PlayRes` 的单位，渲染时再按实际画面缩放一次。这一层间接
每次都要重新推一遍，而推错了看不出来——本套件就发过一版字号被放大到画面高度 12%、
压在画面中央、长句两端切掉的成片。

这里的排版直接写在画面像素里：字号、描边、行距、安全区、折行都是 CSS，改完在
`npx remotion studio` 里当场能看。加粗、描边、入场动画这些竖屏短剧的常见做法，也不用再
绕过字幕格式的限制。

## 装一次

工作区在**项目之外**（默认 `~/.cache/short-drama-edit/remotion`）。`edit_tool.py` 每次运行都会
把本目录的源码同步过去，所以要改排版就改这里的 `src/`，不要改工作区里的副本——它会被覆盖。

```bash
cd ~/.cache/short-drama-edit/remotion && npm install
```

`node_modules` 是几百兆的第三方代码，既不是创作内容也不是技能的一部分，因此不进项目、
也不进本仓库。

## 用

```bash
python3 <本技能目录>/scripts/edit_tool.py render <剧集/EP001> --project-root <project> --subtitles remotion
```

它渲染出一段**透明**的字幕层（VP8 + alpha），再由 ffmpeg 叠到未经改动的画面上。画面本身
不经过浏览器重绘，所以只多一次合成，不多一次画质损失。

## 许可证

Remotion 有自己的许可证：个人与小团队免费，超出规模需要商业授权，条款以
[remotion.dev](https://www.remotion.dev/) 的公告为准。本套件是 MIT，不包含也不代理这项授权；
`edit_tool.py` 不会替你安装它，缺依赖时只报错并给出命令。默认路线不涉及这件事。

## 文件

| 文件 | 作用 |
|---|---|
| `src/schema.ts` | 叠层的输入形状：cues、画幅、fps、字号与安全区比例 |
| `src/Subtitles.tsx` | 排版本身。所有尺寸都是画面高度的比例，同一组数值对 768×1344 和 1080×1920 都成立 |
| `src/Root.tsx` | 合成注册；画幅、帧率、时长由调用方通过 `--props` 传入 |
| `remotion.config.ts` | 固定成带 alpha 的输出，叠层必须透明 |
