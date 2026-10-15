# Agent Note: 生产文档对齐当前适配器与创作交接

Status: implemented

## Problem

本轮逐份精修发现，生产入口仍写内置 H3、Seedance 没有可信上传时拒绝本地参考文件，但实际 runtime 已从项目快照读取文件并编码为 data URI。入口和 adapter 契约还把 Seedance role 限为三种 `reference_*`，漏掉编译器已接受的 `first_frame`、`last_frame`。`PLAN-...` 的说明没有区分需要发送参考图的任务和直接绘制 SHOT 自身首帧的豁免；输入快照说明漏列了已经支持的 `分镜.md`。

失败指引让生产技能直接把命中人物的动作改成挥空，超出生产所有权。TTS 的自然语言语气和参考音色方法没有限定执行端能力，容易被套到只把 prompt 当原句朗读、只接预置 `voice_id` 的内置 MiniMax 路径。现有语气方法的归属笔记为 `2026-09-28-voice-delivery-and-model-choice.md`；本次保留该方法，补清适用的执行端。

## Decision

- 逐份执行语言、冗余、消歧、事实与交接五步，只修改本技能的人类说明；所有既有 fenced 命令、JSON、示例和引文保持原文。
- 让本地参考文件、role 词表、SHOT 首帧和 PLAN 的说明服从当前脚本；不增加远程 URL job 接口，不改变 schema。
- 保留外部执行端的自然语言语气与声音参考方法；内置 MiniMax Speech 明确只把原台词送入 `prompt`，用已选 `voice_id` 和支持的参数表达表演要求。
- 输入被拒时交回负责技能与创作者决定，再为更新的当前文档重新 prepare、确认、run；生产者不自行改动作、台词或声音身份。已提交但未取回的异步任务先 collect。

## Alternatives considered

- **按现有段落继续把上传当成运行前置条件**：最强理由是与旧部署环境相容；不用，因为当前内置 runtime 已发送 data URI，这会阻断正常任务。
- **在生产失败时直接改成更易通过的动作**：最强理由是能快速再次提交；不用，因为这改变上游来源动作，预览本身不能替代创作所有权与接受过程。
- **删除自然语言语气和参考音色方法**：最强理由是内置语音适配器不接受这些输入；不用，因为外部执行端仍可支持，正确做法是明示能力边界。

## Consequences

- 收益：入口、适配器事实和当前文档来源一致；恢复不会无意变成重投；生产失败不再授权生产技能改写创作内容。
- 代价：执行端能力仍需部署方核实；本轮不增加远程 URL 输入，也不验证账号权限或生成质量。
- 未修代码问题：`provider_adapters.py` 的 inline 超限错误建议绑定 HTTPS URL，但 `production_tool.py` 的参考输入仍是项目内文件。本轮仅澄清文档，不修改 runtime。

离线验证：本技能 selftest 8 项通过，provider adapter 编译自检通过；12 个既有 fenced 块逐字节保留，没有发出真实生成请求。

最终复核：独立review与本地prepare复现补来源接口的实际边界：creator-first续接视频无法声明；跳过PLAN后剩余REF顺序仍须从1连续；同一路径双槽当前不可提交。保留创作职责，先交负责技能与创作者处理，不通过删selector、改job编号或静默漏槽绕过。
