---
name: short-drama-produce
description: 在创作者明确确认后，单条或按批调用已配置接口执行图片、视频、配音或配乐生成并保存产物与运行记录。用于“生成图/视频/配音/音乐”“开始跑图/跑视频”“把定稿提示词送去生成”；不写提示词、不改台词，不把预览或定稿当扣费确认。
license: MIT
---

# 确认后生产

本技能负责在创作者明确确认后，把定稿提示词与生成参数发往运行环境配置好的生成接口（adapter），并将产物与运行记录落入 `剧集/<EP>/制作成果/`。图片提示词归 `short-drama-image-prompts` 技能，视频提示词归 `short-drama-video-prompts` 技能，台词归 `short-drama-write` 技能，角色音色设定归 `short-drama-assets` 技能。

## 快速开始

只有在用户明确要求调用接口生成后，才建立临时生成任务单（任务单本身不作为第六份创作文档留存）：

- **来源提取与参考绑定**：指定 `source` 与 `source_entry`（`IMG-*`、`SHOT-*`、`MOTION-*` 或 `GROUP-*`）时，工具自动从该二级标题段落提取可复制提示词与已落盘 `REF-...` 绑定，并按条目段落计算摘要（修改后续镜头不会连坐作废前序确认码）；详细字段规则见 [生成接口协议规范](references/adapter-contract.md#任务单格式job-json)。

> 下文命令中 `<SKILL_DIR>` 指本 `SKILL.md` 所在目录，`<PYTHON>` 指 Python 3.9+ 解释器（Unix/macOS 用 `python3`，Windows 用 `py -3` 或 `python`）。

多条资产优先走**批次确认工作流**，先汇总预览整批清单，未确认前绝不发起任何外部扣费调用：

```bash
<PYTHON> <SKILL_DIR>/scripts/production_tool.py prepare-batch <project> --jobs <job-1.json> <job-2.json>
```

## 确认工作流（推荐批次确认，兼容单任务）

1. **建立任务单并预览**：
   - **批次模式（多镜/整集推荐）**：按小批或单集建立一组任务单，运行 `prepare-batch` 一次性汇总展示本批总条数、目标接口/模型、时长或尺寸参数与全部输出路径预览。
   - **单任务模式**：单张补图或单条重跑时运行 `prepare` 展示该条完整预览。
2. **创作者一次性确认本批（或单条）预览**：等创作者亲眼看到预览清单后明确回复确认，再运行 `confirm` 写入确认回执（笼统的“继续”“预算够用”、上游已定稿或旧确认码均不算本次确认，严禁代填）。对应条目段落、参考文件、参数或输出路径一旦改动，原确认码自动失效。
3. **执行生成**：运行 `run-batch` 顺序执行已确认批次（指定 `--batch-id` 断点续跑时自动跳过当前指纹下已成功且本地产物完好的条目，可选 `--continue-on-error` 遇错继续执行剩余项；单条运行 `run`）。工具在核销确认码前先完成本地配置与参数预检；若因缺少环境变量等本地预检拦截而未发出任何远端请求，确认码保持有效可直接修复环境后重试。已实际发起远端请求的任务无论成败均核销当次确认码。

## 命令

详细字段与接口协议见 [生成接口协议规范](references/adapter-contract.md)，命令行由 [production_tool.py](scripts/production_tool.py) 提供：

```text
<PYTHON> <SKILL_DIR>/scripts/production_tool.py prepare-batch <project> --jobs <job-1.json> <job-2.json> [--batch-id <batch_id>]
<PYTHON> <SKILL_DIR>/scripts/production_tool.py confirm <project> [--batch-id <batch_id>] --confirmation "CONFIRM BATCH <batch_id> <code>"
<PYTHON> <SKILL_DIR>/scripts/production_tool.py confirm-batch <project> [--batch-id <batch_id>] --confirmation "CONFIRM BATCH <batch_id> <code>"
<PYTHON> <SKILL_DIR>/scripts/production_tool.py run-batch <project> (--batch-id <batch_id> | --job-ids <id>...) --adapter-config <outside-project-config.json> [--continue-on-error]

<PYTHON> <SKILL_DIR>/scripts/production_tool.py prepare <project> --job <job.json>
<PYTHON> <SKILL_DIR>/scripts/production_tool.py confirm <project> --job-id <id> --confirmation "CONFIRM <id> <code>"
<PYTHON> <SKILL_DIR>/scripts/production_tool.py run <project> --job-id <id> --adapter-config <outside-project-config.json>
<PYTHON> <SKILL_DIR>/scripts/production_tool.py status <project> (--job-id <id> | --batch-id <batch_id>)
<PYTHON> <SKILL_DIR>/scripts/production_tool.py collect <project> --job-id <id> --adapter-config <outside-project-config.json>
<PYTHON> <SKILL_DIR>/scripts/production_tool.py audit <project>
```

同一任务单存在未结清的 `running` 记录时，禁止重新执行 `prepare`、`confirm` 或 `run`。

## 输入选择

- **图片（`image`）**：读取 `图片提示词.md` 的 `IMG-*`（角色/场景/道具设定图及状态图，含尾帧）或 `分镜.md` 的 `SHOT-*`（读取 `### 首帧提示词` 生成单镜首帧；支持多候选图的接口可单任务产出 1–16 张候选图）。图片落入 `剧集/<EP>/制作成果/images/` 后，`short-drama-storyboard` 技能可将其绑定为 `用途：起始帧` 的 `REF-...`。
- **视频（`video`）**：读取 `视频提示词.md` 的 `MOTION-*` 或多镜合生分组 `GROUP-*`（`GROUP-*` 组级 `输入参考图` 可选，写出时按同规则核验并拦截 `待补参考图`，同样支持可选 `参考音频`；多镜合生时直接指定 `GROUP-*`，勿拿单个成员 `MOTION-*` 代替整组）。内置文档解析器仅读取参考图片与角色参考音频，标着“待续接、不可提交”的 `MOTION-*` 按 `short-drama.json` 中 `continuation_route` 分流：
  - 尚未设置：请创作者在 `independent_starts`（每段从各自定稿起始帧独立生成）与 `relay_external`（后续段在支持参考视频的外部工具提交，本技能只跑第一段）之间二选一，交 `short-drama` 技能写入配置。
  - `independent_starts`：交 `short-drama-storyboard` 技能补齐切点起始帧 → 本技能生成该图（或截取上一段尾帧）并经创作者确认 → 交 `short-drama-video-prompts` 技能改写为可提交提示词 → 预览确认后生成。
  - `relay_external`：不为后续段建单，直接列出每段需上传的上一段成片与尾帧路径。
- **配音（`tts`）**：从 `剧本.md` 读取台词原句与情绪括注，不改台词正文。支持参考录音的语音接口可固定角色定稿参考音频；使用预设音色 ID 的接口按《视觉设定.md》登记的声线与情绪/语速参数合成。
- **音乐（`music`）**：读取 `视频提示词.md` 已确认的成片配乐章节；人声歌曲传定稿 `lyrics`，纯配乐不传歌词。音轨铺入时间线、循环与人声闪避交 `short-drama-edit` 技能处理。

批量生产建议按单集（或单集内的首帧、视频镜头）建立 `prepare-batch` 批次，避免把整季几十集塞进同一个确认包。额度有限时按集拆批，一集的镜头全部跑完再建下一集，避免按资产类别横铺多集导致额度中途用完时手里没有能剪的整集。

## 生成接口与凭据安全

- **配置与密钥隔离**：生成接口配置文件存放在项目目录之外，API 密钥只从环境变量或系统凭据库读取，项目文件夹与创作台界面绝不保存任何密钥。
- **通用协议与内置接口**：任何符合标准输入输出协议的自定义脚本均可接入（见 [生成接口协议规范](references/adapter-contract.md)）；开箱即用的内置零依赖图片、视频、音乐与语音接口清单、环境变量及各供应商特有参数详见 [内置生成接口说明](references/builtin-providers.md)。

## 中断恢复与下游衔接

异步任务拿到供应商返回的任务 ID 后，会在开始轮询前先落盘写入 `handle_path`。中途断网或轮询中断时，先运行 `audit` 检查是否存在 `orphaned_provider_job`（`action: collect_before_retry`），再用 `collect` 直接取回原远端任务结果（不重复扣费，也不消耗新确认码）；仅当远端任务确已失败且无法取回时，才对 `retryable` 任务重新确认重跑。

运行完成后如实汇报产出路径、媒体类型与运行状态；若问题出在提示词或参考素材本身，退回对应上游技能修订。后续套剪成片转 `short-drama-edit` 技能，成片审片转 `short-drama-review` 技能。
