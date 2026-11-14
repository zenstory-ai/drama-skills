# 内置生成接口说明

内置脚本 `scripts/provider_adapters.py` 仅使用 Python 标准库与供应商公开 HTTP 接口通信，通用输入输出与参考素材体积限制见 [生成接口协议规范](adapter-contract.md)。

## GPT Image 2

```json
{"command": ["python3", "/opt/studio/provider_adapters.py", "gpt-image-2"], "timeout_seconds": 600}
```

- **环境变量**：`OPENAI_API_KEY`（必填）；`OPENAI_BASE_URL`（可选 HTTPS 地址覆盖，默认 `https://api.openai.com/v1`）。
- **任务与路由**：`modality` 为 `image`，单次支持产出 1–16 张同格式图片（`.png`、`.jpeg` 或 `.webp`），自动按 `n = len(outputs)` 请求并逐张解码 `b64_json` 写入临时中转目录。无参考图时调用 `POST /images/generations`；带 1–16 张参考图时调用 `POST /images/edits`（`image[]` 表单上传，固定 `model: "gpt-image-2"`）。
- **支持参数**：`width` + `height`（自动拼成 `size`）或直接传 `size`，另支持 `quality`、`background`（不支持透明背景）与 `moderation`。

官方文档：[GPT Image 2 模型说明](https://developers.openai.com/api/docs/models/gpt-image-2)、[图片生成接口](https://developers.openai.com/api/reference/resources/images/methods/generate)、[图片编辑接口](https://developers.openai.com/api/reference/resources/images/methods/edit)。

## Seedance

```json
{"command": ["python3", "/opt/studio/provider_adapters.py", "seedance"], "timeout_seconds": 3600}
```

- **必填环境变量**：`ARK_API_KEY`、`SEEDANCE_MODEL`（账号已开通的模型或接入点 Endpoint ID）。
- **可选环境变量**：`SEEDANCE_BASE_URL`（默认 `https://ark.cn-beijing.volces.com/api/v3`）、`SEEDANCE_POLL_INTERVAL`（默认 `5` 秒）、`SEEDANCE_TIMEOUT_SECONDS`（默认 `1800` 秒）；`SEEDANCE_ALLOWED_RATIOS`、`SEEDANCE_MIN_DURATION` 与 `SEEDANCE_MAX_DURATION` 用于按当前接入点收窄画幅与时长范围（须成对配置起止秒数；未配置时回退内置合法全集 `16:9,4:3,1:1,3:4,9:16,21:9,adaptive` 与 `1–30` 秒）。
- **任务与多模态参考**：`modality` 为 `video`，单次产出 1 个 `.mp4`。可选传 `duration`（`duration: -1` 用于自适应时长或 2.5 `edit` 沿用原视频时长）、`ratio`、`generate_audio` 与 `omni_reference_task_type`（`reference|edit|extend|auto`）。内置默认支持 `first_frame`、`last_frame`（各最多 1 张）、`reference_image`、`reference_video` 与 `reference_audio`（生成接口配置无需重复手写 `reference_roles`）；当提示词尚未逐项声明 `@图片N` / `@视频N` / `@音频N` 槽位时自动追加参考范围说明，已完整声明时不再重复追加尾巴。提交后轮询 `GET /contents/generations/tasks/{id}` 并下载 `content.video_url`。

官方文档：[火山引擎视频生成 API](https://www.volcengine.com/docs/82379/1520757)。

## MiniMax H3 视频

```json
{"command": ["python3", "/opt/studio/provider_adapters.py", "minimax-h3"], "timeout_seconds": 3600}
```

- **必填环境变量**：`MINIMAX_API_KEY`、`MINIMAX_VIDEO_MODEL`（账号已开通的模型 ID）。
- **可选环境变量**：`MINIMAX_VIDEO_BASE_URL`（默认 `https://api.minimax.io/v2`）、`MINIMAX_VIDEO_POLL_INTERVAL`（默认 `5` 秒）、`MINIMAX_VIDEO_TIMEOUT_SECONDS`（默认 `1800` 秒）；`MINIMAX_VIDEO_ALLOWED_RESOLUTIONS`（兼容 `MINIMAX_VIDEO_RESOLUTIONS`）、`MINIMAX_VIDEO_ALLOWED_RATIOS`（兼容 `MINIMAX_VIDEO_RATIOS`）、`MINIMAX_VIDEO_MIN_DURATION` 与 `MINIMAX_VIDEO_MAX_DURATION` 用于按模型档位收窄校验（未配置时回退内置合法全集 `480P,768P,2K`、`adaptive,1:1,3:4,4:3,9:16,16:9,21:9` 与 `1–30` 秒）。
- **参数与多模态 `content`**：`modality` 为 `video`，单次产出 1 个 `.mp4`；`duration` 与 `resolution` 必填，纯文生视频必填非 `adaptive` 的 `ratio`。内置默认支持 `first_frame` / `last_frame`（首尾帧模式）或 `reference_image` ≤ 9、`reference_video` ≤ 3、`reference_audio` ≤ 3（全参考模式，两模式互斥；配置无需重复手写 `reference_roles`）。提示词正文上限 7000 字符；已包含 `retention_analysis:` 原生结构或已显式写出全部 `<Picture N>` 等槽位时不再追加参考尾巴。提交 `POST {base}/video_generation` 后轮询 `GET {base}/query/video_generation/{task_id}` 下载成片。

官方文档：[MiniMax 视频生成 API](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)。

## MiniMax 音乐

```json
{"command": ["python3", "/opt/studio/provider_adapters.py", "minimax-music"], "timeout_seconds": 600}
```

- **环境变量**：`MINIMAX_API_KEY`（必填）；`MINIMAX_BASE_URL`（可选 HTTPS 地址覆盖，默认 `https://api.minimax.io/v1`）。
- **任务与调用**：`modality` 为 `music`，单次产出 1 个与 `format` 一致的 `.mp3` 或 `.wav`。`prompt` 填曲风、配器与情绪描述；支持 `lyrics`、`is_instrumental`、`sample_rate`、`bitrate` 与 `format`（不启用 `lyrics_optimizer` 自动改词：人声歌曲传定稿 `lyrics`，纯配乐不传歌词）。以 `model: "music-3.0"` 与 `output_format: "hex"` 调用 `POST /music_generation` 并解码 `data.audio`。

官方文档：[MiniMax 音乐生成 API](https://platform.minimax.io/docs/api-reference/music-generation)。

## MiniMax 语音

```json
{"command": ["python3", "/opt/studio/provider_adapters.py", "minimax-speech"], "timeout_seconds": 600}
```

- **环境变量**：`MINIMAX_API_KEY`（必填）；`MINIMAX_BASE_URL`（可选 HTTPS 地址覆盖，默认 `https://api.minimax.io/v1`）。
- **任务与调用**：`modality` 为 `tts`，单次产出 1 个与 `format` 一致的 `.mp3` 或 `.wav`。`prompt` 只放纯台词原文；必填 `model` 与预设 `voice_id`（取自 `$short-drama-assets` 在《视觉设定.md》登记的角色声线设定），可选 `emotion`（`happy`、`sad`、`angry`、`fearful`、`disgusted`、`surprised`、`neutral`）、`speed`、`vol`、`pitch`、`sample_rate`、`bitrate` 与 `format`。本内置接口使用预设 `voice_id` 调用 `POST /t2a_v2` 合成；需上传角色参考录音做音色绑定的场景请走支持 `reference_audio` 的视频生成接口或自定义语音接口。

官方文档：[MiniMax 语音合成 API](https://platform.minimax.io/docs/api-reference/speech-t2a-http)。
