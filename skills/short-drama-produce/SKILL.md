---
name: short-drama-produce
description: 在创作者明确确认后，单条或按批次执行短剧项目的图片、视频、TTS/配音或成片配乐生成任务，并把产出文件与运行记录存回项目。用户说“生成这张图/这段视频/这句配音/这段配乐”“开始跑图/跑视频/合成语音/生成音乐”“把定稿提示词送去生成”，或要求批量执行已确认媒体任务时使用；不负责编写提示词、拆镜头、改台词、写歌词或定角色音色设定，也绝不把预览、继续、预算说明或之前的定稿状态当作本次调用付费接口的确认。
license: MIT
---

# 确认后生产

本技能负责把定稿提示词与生成参数发往运行环境配置好的生成接口（adapter）。图片提示词归 `$short-drama-image-prompts`，视频提示词归 `$short-drama-video-prompts`，台词归 `$short-drama-write`，角色音色设定归 `$short-drama-assets`。

## 快速开始

只有在用户明确要求调用接口生成后，才建立临时生成任务单（结果写入 `剧集/<EP>/制作成果/`，任务单本身不作为第六份创作文档留存）：

- **来源提取与条目级校验**：指定 `source` 与 `source_entry`（如 `IMG-*`、`SHOT-*`、`MOTION-*`）时，可省略 `prompt` 与 `reference_bindings`，由工具从该二级标题段落自动提取可复制提示词及已落盘的 `REF-...` 绑定（显式填写时继续逐项核对一致性）。源文档按目标条目段落计算摘要，修改同一文档后续镜头的文字不会连坐作废前序已确认或已生成的镜头。
- **参考绑定与同图多角色**：`reference_bindings` 接收中英文或字母数字标签（如 `女主定妆照`、`USB`、`Lead Hero`），按 `(path, role)` 组合判重（循环镜头可将同一静帧同时绑定为 `first_frame` 与 `last_frame`）。直接从 `分镜.md` 生成 `SHOT-*` 首帧时可跳过未落盘的 `PLAN-...` 项，其余 `REF-...` 保持从 1 连续编号；`MOTION-*` 的角色参考录音排在图片之后（`role: "reference_audio"`，内置 `seedance` 与 `minimax-h3` 默认放行，其他接口见 [生成接口协议规范](references/adapter-contract.md#生成接口配置)）。

多条资产优先走**批次确认工作流**，先汇总预览整批清单，未确认前绝不发起任何外部扣费调用：

```bash
python3 {技能目录}/scripts/production_tool.py prepare-batch <project> --jobs <job-1.json> <job-2.json>
```

## 确认工作流（推荐批次确认，兼容单任务）

1. **建立任务单并预览**：
   - **批次模式（多镜/整集推荐）**：按小批或单集建立一组任务单，运行 `prepare-batch` 一次性汇总展示本批总条数、目标生成接口/模型、时长或尺寸参数与全部输出路径预览。
   - **单任务模式**：单张补图或单条重跑时运行 `prepare` 展示该条完整预览。
2. **创作者一次性确认本批（或单条）预览**：等创作者亲眼看到预览清单后明确回复确认，再运行 `confirm` 写入确认回执（笼统的“继续”“预算够用”、上游已定稿或旧确认码均不算本次确认，严禁代填）。对应条目段落、参考文件、参数或输出路径一旦改动，原确认码自动失效。
3. **执行生成**：运行 `run-batch` 顺序执行已确认批次（或运行 `run` 执行单条）。工具在核销确认码前先完成本地配置与参数预检；若因缺少环境变量等本地预检拦截而未发出任何远端请求，确认码保持有效可直接修复环境后重试。已实际发起远端请求的任务无论成败均核销当次确认码。

## 命令

详细字段与接口协议见 [生成接口协议规范](references/adapter-contract.md)，命令行由 [production_tool.py](scripts/production_tool.py) 提供：

```text
python3 {技能目录}/scripts/production_tool.py prepare-batch <project> --jobs <job-1.json> <job-2.json>
python3 {技能目录}/scripts/production_tool.py confirm <project> --confirmation "CONFIRM BATCH <batch_id> <code>"
python3 {技能目录}/scripts/production_tool.py run-batch <project> --batch-id <batch_id> --adapter-config <outside-project-config.json>

python3 {技能目录}/scripts/production_tool.py prepare <project> --job <job.json>
python3 {技能目录}/scripts/production_tool.py confirm <project> --job-id <id> --confirmation "CONFIRM <id> <code>"
python3 {技能目录}/scripts/production_tool.py run <project> --job-id <id> --adapter-config <outside-project-config.json>
python3 {技能目录}/scripts/production_tool.py status <project> --job-id <id>
python3 {技能目录}/scripts/production_tool.py collect <project> --job-id <id> --adapter-config <outside-project-config.json>
python3 {技能目录}/scripts/production_tool.py audit <project>
```

同一任务单存在未结清的 `running` 记录时，禁止重新执行 `prepare`、`confirm` 或 `run`。

## 输入选择

- **图片（`image`）**：读取 `图片提示词.md` 的 `IMG-*`（角色/场景/道具设定图及状态图，含尾帧）或 `分镜.md` 的 `SHOT-*`（读取 `### 首帧提示词` 生成单镜首帧；内置 `gpt-image-2` 支持单任务产出 1–16 张候选图）。图片落入 `剧集/<EP>/制作成果/images/` 后，分镜技能可将其绑定为 `用途：起始帧` 的 `REF-...`。
- **视频（`video`）**：读取 `视频提示词.md` 的 `MOTION-*`（不直接提交 `GROUP-*` 合生分组）。内置文档解析器只读取参考图片与角色参考音频，因此标着“待续接、不可提交”的 `MOTION-*` 按 `short-drama.json` 中 `creator_authority.production_profile.choices.continuation_route` 分流处理：
  - 尚未设置：请创作者在 `independent_starts`（每段从各自定稿起始帧独立生成）与 `relay_external`（后续段在支持参考视频的外部工具提交，本技能只跑第一段）之间二选一，交 `$short-drama` 写入配置。
  - `independent_starts`：交 `$short-drama-storyboard` 补齐切点起始帧 → 本技能生成该图（或截取上一段尾帧）并经创作者确认 → 交 `$short-drama-video-prompts` 改写为可提交提示词 → 预览确认后生成。
  - `relay_external`：不为后续段建单，直接列出每段需上传的上一段成片与尾帧路径。
- **配音（`tts`）**：从 `剧本.md` 读取台词原句与情绪括注，不改台词正文。支持参考录音的外部语音接口可固定角色定稿参考音频；内置 MiniMax 语音按预设 `voice_id` 与情绪/语速/音量/音高参数合成。
- **音乐（`music`）**：读取 `视频提示词.md` 已确认的成片配乐章节；人声歌曲传定稿 `lyrics`，纯配乐不传歌词。音轨铺入时间线、循环与人声闪避交 `$short-drama-edit` 处理。

批量生产建议按单集（或单集内的首帧、视频镜头）建立 `prepare-batch` 批次，避免把整季几十集塞进同一个确认包。额度有限时按集拆批，一集的镜头全部跑完再建下一集的任务，避免按资产类别横铺多集导致额度中途用完时手里没有能剪的整集。

## 生成接口与凭据安全

生成接口配置存放在项目目录之外，API 密钥只从环境变量或系统凭据库读取，项目文件夹与创作台界面不保存任何密钥。内置零依赖接口详见 [内置生成接口说明](references/builtin-providers.md)（离线模拟脚本 `fixture_adapter.py` 仅供自检测试）：

- [GPT Image 2](references/builtin-providers.md#gpt-image-2)：支持单次 1–16 张输出，无参考图走文生图，带参考图走编辑接口。
- [Seedance](references/builtin-providers.md#seedance)：支持图片、视频、角色参考音频及 2.5 任务类型，画幅与时长环境变量可选收窄。
- [MiniMax H3 视频](references/builtin-providers.md#minimax-h3-视频)：音画同次生成，默认识别 `reference_audio` 与原生 `retention_analysis:` 结构。
- [MiniMax 音乐](references/builtin-providers.md#minimax-音乐)：调用 `music-3.0`，区分带词歌曲与纯配乐。
- [MiniMax 语音](references/builtin-providers.md#minimax-语音)：按预设 `voice_id` 与情绪参数合成角色配音。

## 中断恢复与下游衔接

异步任务拿到供应商返回的任务 ID 后，会在开始轮询前先落盘写入 `handle_path`。中途断网或轮询中断时，先运行 `audit` 检查是否存在 `orphaned_provider_job`（`action: collect_before_retry`），再用 `collect` 直接取回原远端任务结果（不重复扣费，也不消耗新确认码）；仅当远端任务确已失败且无法取回时，才对 `retryable` 任务重新确认重跑。

运行完成后如实汇报产出路径、媒体类型与运行状态；若问题出在提示词或参考素材本身，退回对应上游技能修订。后续套剪成片转 `$short-drama-edit`，成片审片转 `$short-drama-review`。

## 安装与自检

仅在首次安装、升级版本或排查环境故障时运行离线自检：

```bash
python3 {技能目录}/scripts/selftest.py
python3 {技能目录}/scripts/provider_adapters.py --selftest
```
