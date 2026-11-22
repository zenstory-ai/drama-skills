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
- `source` 与 `source_entry`：指向 `剧集|episodes/<EP>/` 下的创作文档时，`图片提示词.md` 选 `IMG-*`（`image`），`视频提示词.md` 选 `MOTION-*` 或 `GROUP-*`（`video`；`GROUP-*` 的组级 `输入参考图` 可省略，一旦写出则与 `MOTION-*` 按同一规则校验并拦截 `待补参考图`），`分镜.md` 选 `SHOT-*`（`image`，读取 `### 首帧提示词`）。
  - **`music` 条目提取（可选 `MUSIC-*`）**：`music` 任务读取 `视频提示词.md` 或独立配乐 Markdown 文档时，可选指定 `source_entry: "MUSIC-..."`（对应 `## MUSIC-...` 二级标题下的 `### 可复制提示词`），自动提取配乐提示词并启用条目级摘要，使编辑视频镜头不再作废已确认配乐任务；省略 `source_entry` 时仍保持整文件摘要向后兼容（不可填 `MOTION-*` 或 `GROUP-*`）。
  - **自动提取与一致性核对**：指定有效 `source` + `source_entry` 时，若省略 `prompt` 或 `reference_bindings`，`prepare` / `prepare-batch` 会从目标二级标题段落自动提取可复制提示词及项目内已有的 `REF-...` 绑定（按文档 `用途` 自动转为 `first_frame` / `last_frame` / `reference_image` 及 `reference_audio`；`reference_video` 仅用于手动填写的任务单；`MUSIC-*` 条目无参考绑定）；手动填写时逐项核对与源条目完全一致。
  - **条目级摘要**：带 `source_entry` 的 Markdown 源文档按该二级标题段落计算字节摘要，修改同一文档中其他条目的内容不会令当前条目的确认码失效，也不会在 `audit` 中把其他已完成镜头标为 `job_inputs_changed`；无 `source_entry` 的源文档与所有媒体参考文件按整文件字节摘要核验。
- `reference_bindings`：0–16 条按序排列的参考素材绑定，每条包含 `slot_id`、从 1 连续递增的 `order`、项目相对路径 `path`、非空名称 `label`（支持中文、英文或字母数字标签，如 `女主定妆照`、`USB`、`Lead Hero`）、接口角色 `role`，以及互不重叠的非空列表 `may_control` 与 `must_not_control`。
  - 唯一性按 `(path, role)` 组合校验：允许循环镜头将同一静帧同时绑定为 `first_frame` 与 `last_frame`，禁止同一 `(path, role)` 重复绑定。
  - `MOTION-*` 与 `GROUP-*` 条目下的 `参考音频` 排在图片绑定之后写入，`role` 固定填 `"reference_audio"`，`character` 原字照抄文档里的 `角色` 名。
  - 从 `分镜.md` 生成 `SHOT-*` 首帧图时，允许跳过尚未生成文件的 `PLAN-...` 项，其余 `REF-...` 仍须从 1 连续编号。
- `references`：0–16 条项目相对文件路径；省略时按 `reference_bindings` 顺序逐槽位推导（循环镜同图不同用途保留对应槽位顺序），手动填写时须与 `reference_bindings` 槽位路径顺序（或按序去重结果）一致。
- `outputs`：1–16 条不重复的输出路径，落在项目根目录 `production/` 或 `剧集|episodes/<EP>/制作成果|production/` 下，扩展名与 `modality` 匹配。
- `parameters`：生成参数对象（凡疑似密钥、Token 的键名一律拦截）。图片与视频任务填入 `prompt_language`（该字段仅供请求拼装器使用，不转发给供应商接口）。
- `overwrite`：目标路径已有同名文件时，仅明确设为 `true` 才允许覆盖。

## 批次预览与确认

- `prepare-batch <project> --jobs <job1.json> <job2.json> ... [--batch-id <batch_id>]`：逐条校验任务单并生成批次清单（写入 `.short-drama/production/batches/<hash>.json`），返回本批条数、目标 `adapter` / 模型汇总、时长与画幅/尺寸摘要、全部 `outputs` 预览以及整批一次性确认口令 `"CONFIRM BATCH <batch_id> <code>"`。
- `confirm <project> [--batch-id <batch_id>] --confirmation "CONFIRM BATCH <batch_id> <code>"`（或 `confirm-batch <project> [--batch-id <batch_id>] --confirmation "CONFIRM BATCH <batch_id> <code>"`）：核验整批任务单与各自输入摘要未变动后，一次性为批内全部任务写入确认回执。
- `run-batch <project> (--batch-id <batch_id> | --job-ids <id>...) --adapter-config <config.json> [--continue-on-error]`：按顺序依次执行各条已确认任务并返回汇总状态；默认遇错即停，传 `--continue-on-error` 时继续执行剩余项；指定 `--batch-id` 中断重跑时，自动跳过当前任务指纹下已成功且本地产出完好的条目。
- `status <project> (--job-id <id> | --batch-id <batch_id>)`：查询单条任务或整批任务汇总状态。

## 生成接口配置

将接口配置文件存放在项目目录之外（将 `<ADAPTER_SCRIPT>` 替换为项目外的自定义适配器脚本路径或 `<SKILL_DIR>/scripts/provider_adapters.py`；Windows 下可将 `"python3"` 替换为 `"py", "-3"` 或 `"python"`）：

```json
{
  "adapters": {
    "studio-image": {
      "command": ["python3", "<ADAPTER_SCRIPT>"],
      "timeout_seconds": 600
    },
    "studio-video": {
      "command": ["python3", "<ADAPTER_SCRIPT>"],
      "timeout_seconds": 3600,
      "audio_capable": true,
      "reference_roles": [
        "first_frame",
        "last_frame",
        "reference_image",
        "reference_video",
        "reference_audio"
      ]
    }
  }
}
```

- `command`：参数数组（直接进程调用，严禁拼成 shell 字符串）；`timeout_seconds`：允许范围 `1–3600` 秒。API 密钥只从环境变量或系统凭据库读取，严禁写进配置文件。
- **能力声明优先（`reference_roles` 与 `audio_capable`）**：`production_tool.py` **优先**读取配置文件中的显式能力声明，不再要求自定义或外置适配器脚本命名为 `provider_adapters.py`：
  - `reference_roles`（可选字符串列表）：显式白名单，声明该配置接受的全部参考 `role`，未列出的 `role` 会在核销确认码前拦截。
  - `audio_capable`（可选布尔值）：显式声明该配置是否接受 `reference_audio`。未配置 `reference_roles` 时，设 `"audio_capable": true` 即可放行 `reference_audio`（不限制视觉自定义 `role`）；设 `"audio_capable": false` 则显式禁用 `reference_audio`（覆盖内置默认）。若同时写 `reference_roles` 与 `audio_capable: false` 且列表里含 `reference_audio`，会被视为配置冲突并在提交前拦截。
  - v1.x 向后兼容回退：仅当 `reference_roles` 与 `audio_capable` 均未显式声明时，内置 `provider_adapters.py` 的 `seedance` / `minimax-h3` 命令继续沿用默认视频能力集（详见 [内置生成接口说明](builtin-providers.md)）。
- **外置适配器安全规则（严禁未锁版本运行）**：接入独立外置适配器包（例如规划中的 `drama-providers`）时，**必须锁定精确版本**（如 `["uvx", "--from", "drama-providers==1.2.3", "drama-providers", "seedance"]` 或先安装锁定版本 `pip install drama-providers==1.2.3`）或直接指定经过核验的本地脚本路径。**严禁**在配置了真实付费 API 密钥的环境中使用未锁版本的浮动远端包（如裸 `uvx drama-providers` 或 `@latest`），防止上游漂移或供应链劫持直接接触生产密钥。

## 硬门禁与软门禁边界

- **硬门禁（阻断执行，提交前失败且不核销确认码）**：仅保留 100% 确定性的财务与安全约束——精确确认码与指纹校验、项目路径/符号链接/工作区边界、密钥键名拦截、输出扩展名与覆写保护、待补参考图拦截、以及 `reference_roles` / `audio_capable` 能力核验。
- **软门禁（`warnings` 数组提醒 Agent 核查，不阻断）**：启发式与提示性检查通过结构化 `warnings` 返回，提醒 Agent 重点确认后再推进，包括 `overwrite_existing_output`（`overwrite: true` 且目标文件已存在）、`music_whole_file_hash`（`music` 读取 `视频提示词.md` 但未指定 `MUSIC-*` 条目）、`missing_prompt_language`（含参考绑定但未传 `prompt_language`）以及 `unpinned_remote_adapter`（检测到 `uvx`/`pipx`/`npx` 未锁定精确版本号）。

## 标准输入协议（stdin）

生成接口进程从 `sys.stdin.buffer` 读取 UTF-8 JSON，除已确认任务单字段外还包含：

- `run_id`：单次运行请求的唯一标识（`collect` 时沿用原 `run_id`）。
- `project_root`：`run` 专属临时只读快照目录（含已确认的 `source` 与 `references` 副本，结束后自动清理）。
- `output_root`：当次运行的临时中转目录，产出文件须直接写成该目录下的普通文件。
- `handle_path`：异步接口拿到远端任务号后，必须在**开始轮询之前**先原子写入 `{"provider_job_id": "<id>"}`，以便断连后通过 `collect` 找回结果。
- `collect_provider_job_id`：仅在 `collect` 时传入；只查询下载该既有远端任务结果，严禁重新提交生成请求。

内置请求拼装器会在核验文件头签名与体积上限（单图 30MB、单视频 50MB、单音频 15MB、Base64 合计 64MB）后编码本地参考素材；当提示词正文尚未完整声明目标接口的原生参考槽位（或原生多段参考结构，各内置接口判定细则见 [内置生成接口说明](builtin-providers.md)）时，按 `parameters.prompt_language` 自动追加参考素材用途说明，已完整声明时不再重复追加。

## 标准输出协议（stdout）

生成成功时，向标准输出打印 UTF-8 JSON：

```json
{
  "outputs": [
    {
      "target": "剧集/EP001/制作成果/images/SHOT001.png",
      "source": "<OUTPUT_ROOT>/result.png"
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
    "detail": "PROVIDER_MODEL is required"
  }
}
```

- `detail`（可选字符串）：仅限单行简短参数或配置错误说明（不超过 160 字符，且已剔除任何密钥/Token、Authorization 头、URL 与本机路径），帮助定位缺了哪个参数或环境变量。
- `submitted`（可选布尔值）：当接口在本地参数/环境变量预检阶段即报错返回 `submitted: false`（且未产生 `http_status` 与 `handle_path`）时，`run` 不会作废当次确认回执，修复本地配置后可直接重跑；一旦远端请求已发出，确认码立即核销。

## 运行记录核查（audit）

运行 `production_tool.py audit <project>` 会核查本地运行记录、任务输入摘要与产出文件字节，报告失败记录、未取回的远端任务 `orphaned_provider_job`（`action: collect_before_retry`）、运行中请求 `running_attempt`、重复内容 `repeated_content`、已被新结果替代的 `superseded`、输入已变更 `job_inputs_changed` 以及产出缺失或手工改动，并返回 `quality_verdict: not_assessed`。
