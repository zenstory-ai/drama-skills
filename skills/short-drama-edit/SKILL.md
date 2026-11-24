---
name: short-drama-edit
description: 将已生成的短剧镜头与配音剪成成片，编写剪辑单并完成渲染验收。用于“剪成成片/套剪”“加字幕/画面文字”“统一响度”“调整成片剪辑节奏、配乐/字幕混音与渲染导出”或导出精修素材；需补素材或改故事时转回上游阶段。
license: MIT
---

# 短剧剪辑与成片

把 `剧集/<EP>/制作成果/` 里的逐镜素材剪辑合成一条成片，并将入出点、镜序、声音、字幕与取舍依据写进 `剧集/<EP>/剪辑单.md`。

## 快速开始

```text
用 short-drama-edit 技能把 EP001 已生产的镜头剪成成片
```

## 入口与边界

- **前置条件**：正式 `check` 与 `render` 需要 `剧集/<EP>/制作成果/` 中已有可读的视频文件（或关键帧图片与配音文件），且本机已安装 `ffmpeg` 与 `ffprobe`（工具会自动回退查找 `~/.local/bin`、`/opt/homebrew/bin`、`/usr/local/bin`，仍缺失时直接报错退出）。**投产前纸面预检**：素材尚未生成前，可先运行 `check --plan-only` 校验剪辑单算术、上游 ID、剧本逐字字幕、画面文字结构、未采用镜头与路径安全，仅将尚未生成的本地素材降级为提醒。**`libass` 说明**：默认 `ffmpeg` 硬字幕与无 Remotion 兜底 `字卡` 均依赖编译进 `libass`（`ass` 滤镜）的 `ffmpeg`（例如 macOS Homebrew 需安装 `ffmpeg-full`）；若当前 `ffmpeg` 不含 `libass`，请改用 `--subtitles remotion`、`--overlay-renderer <cmd>` 或 `--no-subtitles` / `--screen-text-mode off`。同宽高比但分辨率或帧率不同的素材，`check` 给出提醒并由 `render` 自动统一至交付规格；宽高比明显不同（如横屏混入竖屏）时报错拦截，需先用外部工具统一画幅。
- **不反向篡改上游定稿文档**：镜序与镜头作用对照 `分镜.md` 与 `视频提示词.md`，对白、VO、OS、场头时空与 `[画面文字]` 对照 `剧本.md`。剪辑阶段可裁短、删减、调序或用 `--partial` 局部试剪，但不回写上游定稿文档，也不擅自加塞无剧本依据的台词。
- **跨阶段分工**：补拍、重出或换参考图转 `short-drama-produce` 技能；改提示词转 `short-drama-video-prompts` 或 `short-drama-image-prompts` 技能；改台词或剧情转 `short-drama-write` 技能；成片审片交 `short-drama-review` 技能或创作者把关。

## 工作流

1. **标定可用区间**：完整播放每条素材，记下画面可用的起止秒数及区间外的毛病（开头呆立、结尾走样、画面发白、动作回弹、重复动作），见 [素材检视与入出点](references/editing-guide.md#素材检视与入出点)。
2. **定位台词起止与入出点**：带台词的镜头先听准整句字音起止与句间停顿；在可用区间内按起手动作、表情反应或气口定入点，在信息交代完毕且穿帮露头前定出点，逐段写清取舍理由。
3. **排定镜序与接镜调色**：核对相邻镜头的动作衔接、空间方位与揭晓顺序；`render` 默认在同场次内执行自动接镜，需手动微调或跳过校正的段落单写 `画面` 行，见 [镜序、镜头下落与打戏切法](references/editing-guide.md#镜序镜头下落与打戏切法) 与 [接镜调色与颗粒](references/editing-guide.md#接镜调色与颗粒)。
4. **处理声音、字幕与可选图文叠加层**：按需配置 `音效`、`配音`、`环境声`、`字幕` 与可选的 `画面文字`（见 [声音字幕与响度](references/editing-guide.md#声音字幕与响度)）。
5. **保存、渲染与看片验收**：写出或更新 `剧集/<EP>/剪辑单.md`（未改动段落保留原 `CUT-...` 编号）；素材尚未生成时可先运行 `check --plan-only` 做纸面预检，素材到位后依次运行 `check`、`render`、`verify`（试剪单场或前几镜时传 `--partial`），按 [成片看片与交付验收](references/editing-guide.md#成片看片与交付验收) 抽帧看画面、回听切点后再交付。

## 剪辑单概览

每份 `剧集/<EP>/剪辑单.md` 由**开头交付规格**（目标时长、画幅帧率、交付响度、字幕，可选 `接镜匹配`/`颗粒`/`未采用镜头`）与按序排列的**剪辑段**（`## CUT-<EP>-<序号> · <名称>`）组成：

- **视频与静帧段**：每段绑定一个上游来源（视频段 `MOTION-...`/`GROUP-...`，静帧段 `SHOT-...`/`IMG-...`）与真实媒体路径，写清两位小数秒数的 `入点`/`出点`/`时长` 与具体画面 `取舍` 理由（同源视频重叠仅在写明 `- 重放：` 时放行）。
- **声音与字幕**：支持挂载 `音效`、`配音`、`环境声` 与逐字照抄《剧本.md》的 `字幕`（支持整段单句 `- 字幕：<台词>`、单句定时 `- 字幕：<起>-<止> <台词>` 或搭配 `- 字幕时间：<起>-<止>`、以及多句编号 `- 字幕 1：<起>-<止> <台词>`，均支持 `重点` 词高亮）；静帧段支持 `运镜` 参数。
- **可选画面文字叠加层**：`字卡`、`卡片`、`角标` 为通用叠字样式，`系统面板`/`任务面板`（含品阶标签与倒计时）为面向系统流题材预置的**可选模板**，非此类题材无需使用。

完整字段语法、取值范围与标点约定见 [剪辑单格式规范](references/format-spec.md)，成稿示范见 [剪辑单样例](assets/剪辑单.md)。

## 命令与无 Remotion 降级路径

> 下文命令中 `<SKILL_DIR>` 指本 `SKILL.md` 所在目录，`<PYTHON>` 指 Python 3.9+ 解释器（Unix/macOS 用 `python3`，Windows 用 `py -3` 或 `python`）。

命令行工具由 [edit_tool.py](scripts/edit_tool.py) 提供：

```text
<PYTHON> "<SKILL_DIR>/scripts/edit_tool.py" check <剧集/EP001> --project-root <project> [--partial] [--plan-only]
<PYTHON> "<SKILL_DIR>/scripts/edit_tool.py" render <剧集/EP001> --project-root <project> [--partial] [--no-subtitles] [--subtitles ffmpeg|remotion] [--screen-text-mode auto|remotion|ffmpeg|off] [--overlay-renderer <cmd>] [--remotion-workspace <outside-project-dir>] [--remotion-concurrency N]
<PYTHON> "<SKILL_DIR>/scripts/edit_tool.py" verify <剧集/EP001> --project-root <project>
```

- `check`（硬检查与软门禁分离）：
  - **硬阻断（`findings`，退出码 1）**：仅对百分百确定性的结构、安全与媒体缺陷拦截——缺失/不可读素材、越界或符号链接路径、入出点算术或边界错误、奇偶像素不合法、画幅宽高比冲突、同源视频未标 `重放` 的区间重叠、上游来源/剧本原文缺失或语法无效。
  - **软门禁（`提醒`，不阻断渲染）**：需要 Agent 或创作者结合语境复核的经验项——同宽高比分辨率/帧率自动缩放、快闪静帧（`< 0.50s`）、短抢话或标注 `叠音` 的配音交叠、素材修改时间晚于剪辑单、同场运镜突变、目标时长大幅偏差、偏短字幕时间窗及 `--partial` 下的未入片镜头。
  - **纸面预检（`--plan-only`，仅用于 `check`）**：用于音视频素材生成前先审纸面剪辑单。所有确定性文档与安全规则（入出点算术、来源 ID 对照、逐字字幕与画面文字出处、未采用镜头登记、路径越界与符号链接拦截）仍为硬阻断；**仅将尚未生成的本地素材缺失降级为 `提醒`**（无硬错误时退出码 `0`，并在 `未测` 中如实列出缺失素材的实测项）。标准 `check`（不传 `--plan-only`）与 `render` 不受影响，缺素材仍硬阻断。
- `render`：裁切分段、统一同比例分辨率与帧率、生成静帧运镜、同场自动接镜、拼接画面、混音、烧录字幕与可选图文层并统一响度，输出至 `剧集/<EP>/制作成果/成片/` 并保留分段中间文件。默认字幕走 `ffmpeg`（`libass`，**无需 Node/Remotion**），横屏（`width > height`）与竖屏（`9:16`）自动适配字幕底边距与英文按词换行；`--screen-text-mode` 控制 `画面文字` 渲染方式（默认 `auto`）：
  - `auto`（默认）：存在复杂样式（`卡片`/`系统面板`/`任务面板`/`角标`）或本机已安装/显式配置 Remotion 时，走可选的 [Remotion 图文叠加层](assets/remotion/README.md)（默认并发数为 2）；未装 Node/Remotion 且全片仅含普通 `字卡` 时，自动降级为 `ffmpeg` ASS 烧录并在报告中给出提醒。
  - `ffmpeg`：强制用 `ffmpeg` ASS 烧录普通 `字卡`（遇复杂面板样式时报错拦截）。
  - `remotion`：强制走 Remotion 渲染全部 `画面文字` 叠层。
  - `off`：跳过全部 `画面文字` 叠层，其余裁切、混音与字幕烧录照常执行。
  - `--overlay-renderer <cmd>`（外置叠层协议）：可选覆盖内置 Remotion；写出 `叠层.props.json`（含 `width`/`height`/`fps`/`durationInSeconds`/`cues`/`layers`）并调用 `<cmd> --props <props.json> --output <overlay.webm>` 生成透明叠层视频再由 `ffmpeg` 叠合（也支持命令中显式使用 `{props}` / `{output}` 占位符）。
- `verify`（纯测量 + 软提醒，始终退出 0）：实测成片总时长、综合响度与真峰值，列出图文与音轨起止秒数，并在 `提醒`（及 `请逐帧查看` / `请回听`）中汇总响度/真峰偏离、切点亮度跳变、切点音量跳变与疑似坏帧位置，提醒 Agent 与创作者重点抽查，不做粗暴阻断。

**无 Node / Remotion 环境时的降级方案**：

1. **纯 `ffmpeg` 出片（含普通 `字卡`）**：使用默认 `--screen-text-mode auto`（或显式 `--screen-text-mode ffmpeg`）搭配默认 `--subtitles ffmpeg`，无需 Node/Remotion 即可完成裁切、接镜、混音、字幕及普通 `字卡` 烧录。
2. **跳过画面文字直接出片**：剪辑单里带有复杂面板但当前环境未装 Node/Remotion 时，可传 `--screen-text-mode off` 跳过全部 `画面文字` 叠层并保留字幕烧录出片。
3. **交外部剪辑软件精修**：需要复杂画面文字、花字特效或转场但未装 Node/Remotion 时，先用 `--screen-text-mode off`（可按需加 `--no-subtitles`）渲染干净成片并保留分段中间文件，连同 `剧集/<EP>/剪辑单.md`（及 SRT/ASS 字幕）导入剪映、Premiere 或 DaVinci Resolve 叠加图文与精修混音。

## 按需参考

- 完整字段语法与可选图文模板定义：[剪辑单格式规范](references/format-spec.md)
- 入出点、打戏节奏、接镜调色、静帧运镜、声音字幕与看片验收：[短剧剪辑实务指南](references/editing-guide.md)
- 阶段边界与 `EDT-*` 规则表：[阶段职责与规则](references/stage-contract.md)
- 可选 Remotion 叠加层安装与跨平台运行说明：[Remotion 图文叠加层](assets/remotion/README.md)
- 完整剪辑单参考样例：[剪辑单样例](assets/剪辑单.md)
