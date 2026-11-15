---
name: short-drama
description: 创建或继续本地短剧、漫剧项目，围绕五份核心创作文档衔接各创作环节，提供本地短剧创作台（Dashboard）、全局配置更新、制作形态选型与视觉风格定调（Look Development）。用户提出“创建/继续短剧项目”“看进度/下一步”“做视觉风格定调 / Look Development”“打开 dashboard/短剧创作台”“打包/导出制作资料”，或任务跨多个创作环节时使用；明确的写作、设定、提示词、分镜、剪辑或审查请求由对应子技能直接处理。
license: MIT
---

# 短剧创作路由

本技能负责项目初始化与全局配置、跨环节路由、制作形态选型、交付打包与本地短剧创作台（Dashboard）。

## 快速开始

每集按需直接维护五份核心 Markdown 文档（`剧本.md`、`视觉设定.md`、`分镜.md`、`图片提示词.md`、`视频提示词.md`），不另存重复的结构化副本；具体格式、阶段归属与输出语言规则见 [五份创作文档](references/creator-documents.md)。安装或排障时运行自检（需 Python 3.9+）：

```bash
python3 {技能目录}/scripts/selftest.py
```

## 环节分工与路由

| 用户要做什么 | 负责技能与产出 |
|---|---|
| 开发创意、核心看点、改编方案与分集大纲 | `$short-drama-develop` |
| 拆解长篇原著、抽样快评与分集候选 | `$short-drama-novel-analyze` → `项目开发/source-analysis/` |
| 拆解对标剧、同尺比对差距、成片还原 | `$short-drama-breakdown` → `项目开发/对标拆解.md` |
| 写或改单集剧本 | `$short-drama-write` → `剧集/<EP>/剧本.md` |
| 整理人物、造型、地点、道具与声线设定 | `$short-drama-assets` → `剧集/<EP>/视觉设定.md` |
| 写静态设定图提示词 | `$short-drama-image-prompts` → `剧集/<EP>/图片提示词.md` |
| 做分镜与首尾帧提示词 | `$short-drama-storyboard` → `剧集/<EP>/分镜.md` |
| 写视频动态提示词或配乐提示词 | `$short-drama-video-prompts` → `剧集/<EP>/视频提示词.md` |
| 调用外部模型生成图、视频、配音或配乐 | `$short-drama-produce`（先看预览，确认后执行） |
| 编排剪辑单并渲染成片 | `$short-drama-edit` → `剧集/<EP>/剪辑单.md` 与 `制作成果/成片/` |
| 独立审稿或出片问题归因 | `$short-drama-review`（按需启用） |
| 初始化与修改全局配置、打开创作台、导出或打包 | 本技能 |

## 执行与写入约定

1. **按需切入与连续推进**：优先使用用户指定的目录，只读取当前任务直接用到的输入文件，不预建空白前序文档。用户交代做到哪一步就完整做到哪一步；分批处理只用于控制单次篇幅，跑通一批直接继续。
2. **合并补问（最多一次）**：立项或配置缺省时先用合理默认值建项推进；仅在缺少关键信息且不同选法会明显改变剧情走向或画面风格时，在单轮内合并提出不超过 1 次精简补问。下一步要调用外部模型生成素材时，必须先展示预览并等创作者明确确认。
3. **安全保存与跨文档检查**：直接读写 Markdown 时采用原子保存，若发现文件刚被外部编辑器或创作台修改，先重读合并再写入；`.short-drama/`、`输入/` 中的内部记录与密钥绝不写入创作正文。每完成一份文档运行 `creator_markdown_check.py <剧集目录> --partial`，五份齐备后跑全量检查。
4. **参考图挂接分流**：项目内已有匹配图片时挂 `REF-...`；尚无现成图片且创作者未要求暂停等图时，默认按 `PLAN-...` 写出外部挂图计划，或按创作者意图直接写 `- 输入参考图：无` 走文生视频；仅在创作者明确要求等图进项目时写 `无（待补参考图：……）` 并暂停。

## 项目初始化与全局配置

创建项目时将已知参数一次传入，未定项直接留默认（不反复追问）：

```bash
python3 {技能目录}/scripts/project_tool.py init ./my-drama --title "示例短剧" --aspect-ratio 9:16
```

后续在对话中确定或修改画幅、集数、单集时长、语言、语速、视觉方向、目标视频模型配置（`production_profile`）或节奏目标（`rhythm_profile`）时，直接用 `configure` 增量写入 `short-drama.json` 并标记为已确认（无需手写中间台账文件）：

```bash
python3 {技能目录}/scripts/project_tool.py configure <project> \
  --aspect-ratio 16:9 --episode-count 24 --target-seconds 90 \
  --pacing-json '{"spoken_characters_per_second":4.2,"seconds_per_action_paragraph":2.5}' \
  --production-profile-json '{"target_video_model":"seedance-2.5","video_prompt_language":"zh-CN","native_duration_seconds":{"min":4,"max":15},"supported_generation_modes":["text","first_frame","reference"],"audio_generation":"same_pass"}' \
  --rhythm-profile-json '{"form":"国漫二次元","first_hook_seconds":5}'
```

- **模型配置（`--production-profile-json`）**：用户在对话中点名目标视频模型（如 Seedance 2.5、MiniMax H3）时，先用 `configure` 写入模型参数、提示词语言、是否启用多镜合生（`multi_shot_containers`）及接力路线（`continuation_route`），再开展下游提示词编写。
- **节奏目标（`--rhythm-profile-json`）**：支持实拍、二维动态漫、风格化三维、水墨笔触、Q 版表达、国漫二次元等全部制作形态名称，按需填写已敲定的部分指标即可，不必凑齐全部字段。可用 `status` 查看当前生效配置。

## 短剧创作台（Dashboard）

用户要求打开创作台时运行：

```bash
python3 {技能目录}/scripts/dashboard_server.py --workspace <workspace> --port 0 --detach --open
python3 {技能目录}/scripts/dashboard_server.py --workspace <workspace> --status
python3 {技能目录}/scripts/dashboard_server.py --workspace <workspace> --stop
```

`--detach` 在后台运行并把会话信息记入 `<workspace>/.short-drama/dashboard.json`（更换端口或令牌加 `--restart`）。创作台以只读卡片展示五份文档、素材与成片，可在「编辑原文」中直接保存 Markdown。

## 导出与交付打包

```bash
python3 {技能目录}/scripts/project_tool.py export <project> --out <项目外目录>
python3 {技能目录}/scripts/project_tool.py package <project> --episode EP001
python3 {技能目录}/scripts/project_tool.py verify <project> --episode EP001
```

- `export`：将各集现有创作文档、`剪辑单.md` 与 `制作成果/` 备份到项目外目录（可选 `--episode EP001`、`--no-media`、`--overwrite`）。
- `package` / `verify`：直接按集打包项目当前的创作者文档与有效交付文件（也可用 `--include` 指定子集），生成 `交付/<EP>/manifest.json` 与 `checksums.sha256`（不含 `输入/` 与 `.short-drama/`，自动拦截符号链接与越界路径；旧式台账项目需强核审稿状态时可加 `--strict-ledger`）。

## 按问题查阅参考文档

- 阶段问题路由与四级规则说明：[规则与路由索引](references/knowhow-index.md)
- 五份文档格式、文档归属与输出语言：[五份创作文档](references/creator-documents.md)
- 六种制作形态差异与视觉风格定调（Look Development）试片：[制作形态](references/production-form-profiles.md)
- 参考图十种用途（含原生多模态 `主体` 参考）与控制边界：[参考图用途](references/reference-roles.md)
- 按悬念类型交代遮挡与揭晓动作：[信息揭晓时机](references/audience-reveal.md)
- 母版、局部补拍与替代版的返工归属：[母版、补拍与替代版](references/pickup-and-alternate.md)
