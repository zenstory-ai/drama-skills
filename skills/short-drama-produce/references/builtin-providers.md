# 内置生成接口说明

内置脚本 `<SKILL_DIR>/scripts/provider_adapters.py` 仅使用 Python 3.9+ 标准库与供应商公开 HTTP 接口通信，通用输入输出协议与参考素材体积限制见 [生成接口协议规范](adapter-contract.md)（离线模拟测试夹具仅保存在仓库测试目录中，不随技能包分发）。

> 跨平台说明：将下文示例中的 `<SKILL_DIR>` 替换为本技能实际安装目录；Windows 下可将 `"python3"` 替换为 `"py", "-3"` 或 `"python"`。

## OpenAI 图片（GPT Image）

```json
{"command": ["python3", "<SKILL_DIR>/scripts/provider_adapters.py", "openai-image"], "timeout_seconds": 600}
```

- **必填环境变量**：`OPENAI_API_KEY`；模型 ID 须由 `parameters.model` 或 `OPENAI_IMAGE_MODEL` 显式配置（如 `gpt-image-2.6`，代码不硬编码任何模型版本；旧子命令 `"gpt-image-2"` 仅作向后兼容别名保留）。
- **可选环境变量**：`OPENAI_BASE_URL`（HTTPS 地址覆盖，默认 `https://api.openai.com/v1`）。
- **任务与路由**：`modality` 为 `image`，单次支持产出 1–16 张同格式图片（`.png`、`.jpg`/`.jpeg` 或 `.webp`），自动按 `n = len(outputs)` 请求并逐张解码 `b64_json` 写入临时中转目录。无参考图时调用 `POST /images/generations`；带 1–16 张参考图时调用 `POST /images/edits`（`image[]` 表单上传）。模型解析优先级为 `parameters.model` > `OPENAI_IMAGE_MODEL`（均缺失时在请求前安全失败）。
- **支持参数**：`model`（必填，或在环境变量 `OPENAI_IMAGE_MODEL` 中配置）、`width` + `height`（自动拼成 `size`）或直接传 `size`，另支持 `quality`、`background`（`auto` / `opaque` / `transparent`，按实际所选模型能力透传）与 `moderation`。

官方文档：[图片生成接口](https://developers.openai.com/api/reference/resources/images/methods/generate)、[图片编辑接口](https://developers.openai.com/api/reference/resources/images/methods/edit)。

## Seedance

```json
{"command": ["python3", "<SKILL_DIR>/scripts/provider_adapters.py", "seedance"], "timeout_seconds": 3600}
```

- **必填环境变量**：`ARK_API_KEY`、`SEEDANCE_MODEL`（账号已开通的模型或接入点 Endpoint ID）。
- **可选环境变量**：`SEEDANCE_BASE_URL`（默认 `https://ark.cn-beijing.volces.com/api/v3`）、`SEEDANCE_POLL_INTERVAL`（默认 `5` 秒）、`SEEDANCE_TIMEOUT_SECONDS`（默认 `1800` 秒）；`SEEDANCE_ALLOWED_RATIOS`、`SEEDANCE_MIN_DURATION` 与 `SEEDANCE_MAX_DURATION` 用于按当前接入点收窄画幅与时长范围（须成对配置起止秒数；未配置时回退内置合法全集 `16:9,4:3,1:1,3:4,9:16,21:9,adaptive` 与 `1–30` 秒）。
- **任务与多模态参考**：`modality` 为 `video`，单次产出 1 个 `.mp4`。可选传 `duration`（`duration: -1` 用于自适应时长或 2.5 `edit` 沿用原视频时长）、`ratio`、`generate_audio` 与 `omni_reference_task_type`（`reference|edit|extend|auto`）。当接口配置未显式填写 `reference_roles` 时，内置默认放行 `first_frame`、`last_frame`（各最多 1 张）、`reference_image`、`reference_video` 与 `reference_audio`；当提示词尚未逐项声明 `@图片N` / `@视频N` / `@音频N` 槽位时自动追加参考范围说明，已完整声明时不再重复追加尾巴。提交后轮询 `GET /contents/generations/tasks/{id}` 并下载 `content.video_url`。

官方文档：[火山引擎视频生成 API](https://www.volcengine.com/docs/82379/1520757)。

## MiniMax H3 视频

```json
{"command": ["python3", "<SKILL_DIR>/scripts/provider_adapters.py", "minimax-h3"], "timeout_seconds": 3600}
```

- **必填环境变量**：`MINIMAX_API_KEY`、`MINIMAX_VIDEO_MODEL`（账号已开通的模型 ID）。
- **可选环境变量**：`MINIMAX_VIDEO_BASE_URL`（默认海外站 `https://api.minimax.io/v2`；国内站账号请将域名改为 `api.minimaxi.com` 并保留 `/v2` 路径）、`MINIMAX_VIDEO_POLL_INTERVAL`（默认 `5` 秒）、`MINIMAX_VIDEO_TIMEOUT_SECONDS`（默认 `1800` 秒）；`MINIMAX_VIDEO_ALLOWED_RESOLUTIONS`（兼容 `MINIMAX_VIDEO_RESOLUTIONS`）、`MINIMAX_VIDEO_ALLOWED_RATIOS`（兼容 `MINIMAX_VIDEO_RATIOS`）、`MINIMAX_VIDEO_MIN_DURATION` 与 `MINIMAX_VIDEO_MAX_DURATION` 用于按模型档位收窄校验（未配置时回退内置合法全集 `480P,768P,2K`、`adaptive,1:1,3:4,4:3,9:16,16:9,21:9` 与 `1–30` 秒）。
- **参数与多模态 `content`**：`modality` 为 `video`，单次产出 1 个 `.mp4`（支持音画同次生成）；`duration` 与 `resolution` 必填，纯文生视频必填非 `adaptive` 的 `ratio`。当接口配置未显式填写 `reference_roles` 时，内置默认放行 `first_frame` / `last_frame`（首尾帧模式）或 `reference_image` ≤ 9、`reference_video` ≤ 3、`reference_audio` ≤ 3（全参考模式，两模式互斥）。提示词正文上限 7000 字符；已包含 `retention_analysis:` 原生结构或已显式写出全部 `<Picture N>` 等槽位时不再追加参考尾巴。提交 `POST {base}/video_generation` 后轮询 `GET {base}/query/video_generation/{task_id}` 下载成片。

官方文档：[MiniMax 视频生成 API](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)。

## MiniMax 音乐

```json
{"command": ["python3", "<SKILL_DIR>/scripts/provider_adapters.py", "minimax-music"], "timeout_seconds": 600}
```

- **环境变量**：`MINIMAX_API_KEY`（必填）；模型 ID 须由 `parameters.model` 或 `MINIMAX_MUSIC_MODEL` 显式配置（代码不硬编码模型版本）；`MINIMAX_BASE_URL`（可选 HTTPS 地址覆盖，默认海外站 `https://api.minimax.io/v1`；国内站账号请将域名改为 `api.minimaxi.com` 并保留 `/v1` 路径）。
- **任务与调用**：`modality` 为 `music`，单次产出 1 个与 `format` 一致的 `.mp3` 或 `.wav`。`prompt` 填曲风、配器与情绪描述；支持 `model`（必填，解析优先级：`parameters.model` > `MINIMAX_MUSIC_MODEL`，均缺失时在请求前安全失败）、`lyrics`、`is_instrumental`、`sample_rate`、`bitrate` 与 `format`（不启用 `lyrics_optimizer` 自动改词：人声歌曲传定稿 `lyrics`，纯配乐不传歌词）。以 `output_format: "hex"` 调用 `POST /music_generation` 并解码 `data.audio`。

官方文档：[MiniMax 音乐生成 API](https://platform.minimax.io/docs/api-reference/music-generation)。

## MiniMax 语音

```json
{"command": ["python3", "<SKILL_DIR>/scripts/provider_adapters.py", "minimax-speech"], "timeout_seconds": 600}
```

- **环境变量**：`MINIMAX_API_KEY`（必填）；`MINIMAX_BASE_URL`（可选 HTTPS 地址覆盖，默认海外站 `https://api.minimax.io/v1`；国内站账号请将域名改为 `api.minimaxi.com` 并保留 `/v1` 路径）。
- **任务与调用**：`modality` 为 `tts`，单次产出 1 个与 `format` 一致的 `.mp3` 或 `.wav`。`prompt` 只放纯台词原文；必填 `model` 与预设 `voice_id`（取自 `short-drama-assets` 技能在《视觉设定.md》登记的角色声线设定），可选 `emotion`（`happy`、`sad`、`angry`、`fearful`、`disgusted`、`surprised`、`neutral`）、`speed`、`vol`、`pitch`、`sample_rate`、`bitrate` 与 `format`。本内置接口使用预设 `voice_id` 调用 `POST /t2a_v2` 合成；需上传角色参考录音做音色绑定的场景请走支持 `reference_audio` 的视频生成接口或自定义语音接口。

官方文档：[MiniMax 语音合成 API](https://platform.minimax.io/docs/api-reference/speech-t2a-http)。

## MiniMax 国内站与海外站地址说明

内置默认值面向海外站（`.minimax.io`）：`MINIMAX_BASE_URL` 默认 `https://api.minimax.io/v1`（音乐/语音），`MINIMAX_VIDEO_BASE_URL` 默认 `https://api.minimax.io/v2`（视频）。
若使用 MiniMax **国内站**账号与 API Key，请在运行环境中将上述两个变量的主机名从 `api.minimax.io` 覆盖为 `api.minimaxi.com`（协议仍为 HTTPS，路径分别保持 `/v1` 与 `/v2`，且不要混用国内站与海外站 Key）：

- `MINIMAX_BASE_URL`：指向国内站主机 `api.minimaxi.com` 的 `/v1` 接口
- `MINIMAX_VIDEO_BASE_URL`：指向国内站主机 `api.minimaxi.com` 的 `/v2` 接口

## v2.0 适配器外置路线图（Externalization Roadmap）

- **v1.x（当前）**：`provider_adapters.py` 继续随技能内置，保持零第三方依赖与开箱即用；同时 `production_tool.py` 已优先读取配置文件中的 `reference_roles` / `audio_capable` 能力声明，不再把能力判断绑定在 `provider_adapters.py` 文件名上。
- **v2.0（规划）**：随供应商接口与模型版本快速迭代，各供应商具体 HTTP 适配器计划拆分为独立发行的外置工具包（`drama-providers`），本技能核心保留协议稳定的 `production_tool.py` 与确认/断点/审计机制。
- **外置包安全红线**：接入外置 `drama-providers` 时，**务必锁定精确版本**（如 `drama-providers==X.Y.Z`）或使用明确核验过的本地脚本路径；**严禁**在携带真实付费 API Key 时运行未锁版本的浮动远端包。
