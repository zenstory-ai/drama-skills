---
name: short-drama-produce
description: 在创作者明确确认后，执行短剧项目的图片、视频、TTS/配音或时间线音乐生产任务，并把结果与精简运行记录存回项目。用户说“生成这张图/这段视频/这句配音/这段配乐”“开始跑图/跑视频/合成语音/生成音乐”“把已确认提示词送去生产”，或要求批量执行已确认媒体任务时使用；不负责创作提示词、镜头、台词、歌词或声音身份，也绝不把预览、继续、预算说明或既有接受状态当作本次付费生产确认。
license: MIT
---

# 确认后生产

本技能把已经写好的生产规格送到运行环境配置的 adapter。图片提示词归
`$short-drama-image-prompts`，视频提示词归 `$short-drama-video-prompts`，台词归
`$short-drama-write`，声音身份归 `$short-drama-assets`。

## Quick Start

只在用户明确要求实际生成后，从当前创作文档取出提示词建立有边界的临时 job（不是第六份创作文档），输出落于 `剧集/<EP>/制作成果/`：

- **来源与参考绑定**：`source` 指向拥有该提示词的文档，`source_entry` 点名对应二级标题（见下节「输入选择」）；`reference_bindings` 逐张填写真实参考图的槽位、从 1 连续的顺序、唯一项目相对路径、中文名、允许/禁止控制范围，以及按文档 `用途` 映射的供应商 `role`（带参考但无绑定直接失败）。`MOTION-*` 的「参考音频」排在图片之后进入 `reference_bindings`（`role: "reference_audio"`，`character` 照抄 `角色`；adapter 未声明接受 `reference_audio` 时 `run` 在提交前失败，见 [adapter-contract.md](references/adapter-contract.md#adapter-config)）。
- **PLAN 槽位与路径唯一性**：把 `PLAN-...` 作为生成输入前，必须先将真实文件放入项目并由上游改写为 `REF-...`。直接从 `分镜.md` 生成该 `SHOT-*` 自身首帧时可跳过 `PLAN-...` 槽位，但剩余 `REF-...` 顺序仍须从 1 连续；若出现断号或同一路径占多个槽位，先交文档负责技能修订源声明，不在 job 中擅自重编号、合并或漏槽。

```bash
python3 {技能目录}/scripts/production_tool.py prepare <project> --job <临时-job.json>
```

先展示 `prepare` 的完整预览；此时不会调用供应商。

## 硬闸门

每次生产必须按顺序走完四步，不可合并：

1. 建立单一 modality、明确数量、完整 prompt/spec、参考绑定、参数、输出路径和 adapter profile 的 job。图片/视频 job 的 `parameters.prompt_language` 跟随当前可复制正文的提示词语言。
2. 运行 `prepare` 并向创作者展示完整预览（数量、prompt、`source_entry`、`reference_bindings`、`references`、`outputs`、`overwrite`、adapter）。`prepare` 机械核对可复制提示词与参考绑定；任一漂移均 fail closed。
3. 等创作者**看到预览后**明确同意当前任务，才运行 `confirm`。“继续”“都做完”“预算没问题”、上游已接受或旧版确认都不算本次确认，不得代填。
4. 运行 `run`（启动 adapter 前消费确认；成功或失败后重跑均须重新确认）。

job、prompt、参数、输出路径或参考文件任一变化，旧确认立即失效。当前已确认 job 是本轮唯一工作单元；运行结束后回报结果并交还控制权，不自动回填分镜、不自动准备下一批或启动剪辑与审查。

## 命令

格式与契约见 [adapter-contract.md](references/adapter-contract.md)，CLI 由 [production_tool.py](scripts/production_tool.py) 提供：

```text
python3 {技能目录}/scripts/production_tool.py prepare <project> --job <job.json>
python3 {技能目录}/scripts/production_tool.py confirm <project> --job-id <id> --confirmation "CONFIRM <id> <code>"
python3 {技能目录}/scripts/production_tool.py run <project> --job-id <id> --adapter-config <outside-project-config.json>
python3 {技能目录}/scripts/production_tool.py status <project> --job-id <id>
python3 {技能目录}/scripts/production_tool.py collect <project> --job-id <id> --adapter-config <outside-project-config.json>
python3 {技能目录}/scripts/production_tool.py audit <project>
```

同一 job 存在未决 `running` attempt 时禁止重新 `prepare`、`confirm` 或 `run`。

## 输入选择

- **image**：取 `图片提示词.md` 的 `IMG-*`（资产板/状态图，含尾帧）或 `分镜.md` 的 `SHOT-*`（取 `### 冻结关键帧提示词` 单镜首帧），两者不互替。产出落入 `剧集/<EP>/制作成果/images/` 后，分镜 owner 才可将其绑为 `用途：起始帧` 的 `REF-...`。
- **video**：取 `视频提示词.md` 的 `MOTION-*`（不支持直接提交 `GROUP-*` 多镜分组或拿单镜代替整组）。当前选择器只解析图片与角色参考音频，不能绑定上一段视频，故标着“待续接、不可提交”的 `MOTION-*` 按 `short-drama.json` 中 `creator_authority.production_profile.choices.continuation_route` 处理：
  - 未设置：请创作者二选一并由 `$short-drama` 写入档案——`independent_starts`（每段从各自已接受起始帧独立生成）或 `relay_external`（后续段由创作者在支持绑定上一段视频与尾帧的外部工具提交，本技能只生成首段）。
  - `independent_starts`：依次交 `$short-drama-storyboard` 补切点图或起始帧槽位 → 本技能生成该图（或取上一段实际视频尾帧）并经创作者接受 → 交 `$short-drama-video-prompts` 改写为从已接受起点出发的可提交正文 → 建 job 预览并确认。
  - `relay_external`：不为后续段建 job，直接向创作者列出每段所需的上一段实际视频与尾帧路径。
- **tts**：从 `剧本.md` 读取原句与括注表演要求，不改词。外部执行端支持表演指令或参考音色时，可在台词前附简短语气说明并固定同一角色的已接受参考录音；内置 MiniMax Speech 将 `prompt` 逐字作为台词，只传原句，以已选 `voice_id` 固定角色音色，并将表演要求映射为情绪、语速、音量和音调参数。
- **music**：读取 `视频提示词.md` 已确认的时间线音乐章节；主题曲带已确认歌词，纯配乐不带歌词。源音轨的落点、循环、淡入淡出与对白 ducking 交 `$short-drama-edit`。

大批量任务拆成数量与成本边界清晰的小 job，不把整季塞进一次确认。

## Adapter 边界

adapter 配置保存在项目外，凭据只从运行环境或系统凭据存储读取；项目文件与 Dashboard 不保存密钥。输入输出协议与引用语义追加规则见 [adapter-contract.md](references/adapter-contract.md)。

可选内置 stdlib adapter（离线自检夹具 `fixture_adapter.py` 仅供测试）：

- [Seedance](references/providers/seedance.md)：显式配置模型/Endpoint ID，支持图片、视频和音频参考 role。
- [GPT Image 2](references/providers/gpt-image-2.md)：无参考图走 generation，有参考图走 edit，校验尺寸与透明背景限制。
- [MiniMax Music](references/providers/minimax-music.md)：固定 `music-3.0`，区分主题曲与纯配乐。
- [MiniMax 语音](references/providers/minimax-speech.md)：`tts` 模态，显式要求模型与预置 `voice_id`，不做声音克隆。
- [MiniMax H3 视频](references/providers/minimax-h3-video.md)：显式配置模型 ID、分辨率集合与时长区间，声画同次生成。

## 中断恢复与复核

异步任务拿到供应商任务 ID 后会在首次轮询前写入 `handle_path`。轮询或下载中断不等于未执行：先运行 `audit` 检查是否存在 `orphaned_provider_job`（`action: collect_before_retry`），再用 `collect` 取回原任务结果（不重新提交、不消费新确认）；确认原任务已终态失败且无法取回后，才按 `retryable` 重新确认并重投。

成功后回报实际输出路径、媒体类型与运行状态，不把技术成功或哈希一致写成媒体质量结论。若失败证据指向提示词、参考图或音频缺陷，将证据交回对应负责技能修订并经创作者接受后再重建 job；本技能不得擅自改写动作或台词。后续剪辑路由 `$short-drama-edit`，质量复核路由 `$short-drama-review`。

## 安装维护

只有安装、升级或排障时运行离线自检：

```bash
python3 {技能目录}/scripts/selftest.py
python3 {技能目录}/scripts/provider_adapters.py --selftest
```
