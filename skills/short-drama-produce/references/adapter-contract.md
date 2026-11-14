# 生成接口协议规范

内置文档解析器从五份创作文档读取提示词、参考图片与角色参考音频，暂不直接解析参考视频；需续接上一段视频的镜头按 `SKILL.md` 中的 `continuation_route`（`independent_starts` 或 `relay_external`）分流处理。

## 任务单格式（Job JSON）

```json
{
  "schema_version": "1.0",
  "job_id": "EP001-MOTION001-video",
  "modality": "video",
  "adapter": "studio-video",
  "source": "剧集/EP001/视频提示词.md",
  "source_entry": "MOTION-EP001-001",
  "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-001.mp4"],
  "parameters": {"duration": 5, "ratio": "9:16", "prompt_language": "zh-CN"},
  "overwrite": false
}
```

- `modality`：必填，取值为 `image`、`video`、`tts`（单句角色配音）或 `music`（单段成片配乐或主题曲）。
- `source` 与 `source_entry`：指向 `剧集|episodes/<EP>/` 下的创作文档时，`图片提示词.md` 选 `IMG-*`（`image`），`视频提示词.md` 选 `MOTION-*`（`video`），`分镜.md` 选 `SHOT-*`（`image`，读取 `### 首帧提示词`）；`music` 任务读取 `视频提示词.md` 配乐章节，不填 `MOTION-*`。
  - **自动提取与一致性核对**：指定有效 `source` + `source_entry` 时，若省略 `prompt` 或 `reference_bindings`，`prepare` / `prepare-batch` 会从目标二级标题段落自动提取可复制提示词及已落盘的 `REF-...` 绑定（按文档 `用途` 自动映射 `first_frame` / `last_frame` / `reference_image` / `reference_video` 及 `reference_audio`）；显式填写时逐项核对与源条目完全一致。
  - **条目级摘要**：带 `source_entry` 的 Markdown 源文档按该二级标题段落计算字节摘要，修改同一文档中其他条目的内容不会令当前条目的确认码失效，也不会在 `audit` 中把其他已完成镜头标为 `job_inputs_changed`；无 `source_entry` 的源文档与所有媒体参考文件按整文件字节摘要核验。
- `reference_bindings`：0–16 条按序排列的参考素材绑定，每条包含 `slot_id`、从 1 连续递增的 `order`、项目相对路径 `path`、非空名称 `label`（支持中文、英文或字母数字标签，如 `女主定妆照`、`USB`、`Lead Hero`）、接口角色 `role`，以及互不重叠的非空列表 `may_control` 与 `must_not_control`。
  - 唯一性按 `(path, role)` 组合校验：允许循环镜头将同一静帧同时绑定为 `first_frame` 与 `last_frame`，禁止同一 `(path, role)` 重复绑定。
  - `MOTION-*` 条目下的 `参考音频` 排在图片绑定之后写入，`role` 固定填 `"reference_audio"`，`character` 原字照抄文档里的 `角色` 名。
  - 从 `分镜.md` 生成 `SHOT-*` 首帧图时，允许跳过尚未落盘的 `PLAN-...` 项，其余 `REF-...` 仍须从 1 连续编号。
- `references`：0–16 条项目相对文件路径；省略时按 `reference_bindings` 顺序逐槽位推导（循环镜同图不同用途保留对应槽位顺序），显式填写时须与 `reference_bindings` 槽位路径顺序（或按序去重结果）一致。
- `outputs`：1–16 条不重复的输出路径，落在项目根目录 `production/` 或 `剧集|episodes/<EP>/制作成果|production/` 下，扩展名与 `modality` 匹配。
- `parameters`：生成参数对象（凡疑似密钥、Token 的键名一律拦截）。图片与视频任务填入 `prompt_language`（该字段仅供请求拼装器使用，不转发给供应商接口）。
- `overwrite`：目标路径已有同名文件时，仅显式设为 `true` 才允许覆盖。

## 批次预览与确认（Batch Workflow）

- `prepare-batch <project> --jobs <job1.json> <job2.json> ...`：逐条校验任务单并生成批次清单（写入 `.short-drama/production/batches/<hash>.json`），返回本批条数、目标 `adapter` / 模型汇总、时长与画幅/尺寸摘要、全部 `outputs` 预览以及整批一次性确认口令 `"CONFIRM BATCH <batch_id> <code>"`。
- `confirm <project> --confirmation "CONFIRM BATCH <batch_id> <code>"`（或 `confirm-batch`）：核验整批任务单与各自输入摘要未变动后，一次性为批内全部任务写入确认回执。
- `run-batch <project> --batch-id <batch_id> --adapter-config <config.json>`（或传 `--job-ids`）：按批内顺序依次执行各条已确认任务并返回汇总状态。

## 生成接口配置

将接口配置文件存放在项目目录之外：

```json
{
  "adapters": {
    "studio-image": {
      "command": ["python3", "/opt/studio/image_adapter.py"],
      "timeout_seconds": 600
    }
  }
}
```

- `command`：参数数组（直接进程调用，严禁拼成 shell 字符串）；`timeout_seconds`：允许范围 `1–3600` 秒。API 密钥只从环境变量或系统凭据库读取，严禁写进配置文件。
- `reference_roles`（可选列表）：声明当前接口支持的参考 `role`，未列出的 `role` 会在核销确认码前拦截。当 `command` 调用内置 `provider_adapters.py` 的 `seedance` 或 `minimax-h3` 且未显式填写 `reference_roles` 时，默认放行 `first_frame`、`last_frame`、`reference_image`、`reference_video` 与 `reference_audio`；自定义外部接口若需接收 `reference_audio`，仍须在 `reference_roles` 中显式列出。

## 标准输入协议（stdin）

生成接口进程从 `sys.stdin.buffer` 读取 UTF-8 JSON，除已确认任务单字段外还包含：

- `run_id`：单次运行请求的唯一标识（`collect` 时沿用原 `run_id`）。
- `project_root`：`run` 专属临时只读快照目录（含已确认的 `source` 与 `references` 副本，结束后自动清理）。
- `output_root`：当次运行的临时中转目录，产出文件须直接写成该目录下的普通文件。
- `handle_path`：异步接口拿到远端任务号后，必须在**开始轮询之前**先原子写入 `{"provider_job_id": "<id>"}`，以便断连后通过 `collect` 找回结果。
- `collect_provider_job_id`：仅在 `collect` 时传入；只查询下载该既有远端任务结果，严禁重新提交生成请求。

内置请求拼装器会在核验文件头签名与体积上限（单图 30MB、单视频 50MB、单音频 15MB、Base64 合计 64MB）后编码本地参考素材；当提示词正文尚未完整声明原生参考槽位（且不含 H3 `retention_analysis:` 原生结构）时，按 `parameters.prompt_language` 自动追加参考素材用途说明，已完整写出槽位时不再重复追加。

## 标准输出协议（stdout）

生成成功时，向标准输出打印 UTF-8 JSON：

```json
{
  "outputs": [
    {
      "target": "剧集/EP001/制作成果/images/SHOT001.png",
      "source": "/opt/studio/staging/result.png"
    }
  ],
  "provider_job_id": "optional-public-id"
}
```

`outputs` 的 `target` 顺序须与确认任务单完全一致；`source` 须为 `output_root` 下直接生成的普通文件（禁止符号链接）。

生成失败时，只允许向标准输出打印白名单内的脱敏错误摘要（严禁包含密钥、请求头、长响应报文、提示词原文或本机绝对路径）：

```json
{
  "error": {
    "provider": "studio-video",
    "category": "invalid_request",
    "code": "invalid_job_parameter",
    "http_status": null,
    "request_id": null,
    "retryable": false,
    "submitted": false,
    "detail": "SEEDANCE_MODEL is required"
  }
}
```

- `detail`（可选字符串）：仅限单行简短参数或配置错误说明（不超过 160 字符，且已剔除任何密钥/Token、Authorization 头、URL 与本机路径），帮助定位缺了哪个参数或环境变量。
- `submitted`（可选布尔值）：当接口在本地参数/环境变量预检阶段即报错返回 `submitted: false`（且未产生 `http_status` 与 `handle_path`）时，`run` 不会烧毁当次确认回执，修复本地配置后可直接重跑；一旦远端请求已发出，确认码立即核销。

## 运行记录核查（audit）

运行 `production_tool.py audit <project>` 会核查本地运行记录、任务输入摘要与产出文件字节，报告失败记录、未取回的远端任务 `orphaned_provider_job`（`action: collect_before_retry`）、运行中请求 `running_attempt`、重复内容 `repeated_content`、已被新结果替代的 `superseded`、输入已变更 `job_inputs_changed` 以及产出缺失或手工改动，并返回 `quality_verdict: not_assessed`。
