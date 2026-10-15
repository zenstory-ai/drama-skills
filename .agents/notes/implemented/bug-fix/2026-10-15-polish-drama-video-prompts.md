# Agent Note: 视频提示词说明与既有契约对齐

Status: implemented

## Problem

视频提示词参考资料仍有几处与既有契约不一致的说明：`motion-recipe.md` 把通用字数与并行通道写成检查门槛；H3 参考字段把续接所需的实际尾帧误写成实际音频；结构化模板的 sources 说明重复字段，且容器校验清单没有准确区分脚本执行与人工核对。普通 creator-first 与结构化模板的边界需要保留。

## Decision

按 AGENTS.md 的四级规则和 `stage-contract.md` 修正说明，保留已接受起止状态、逐字对白、模型时长与素材模式。并行通道只在本镜实际存在时写，提示词长度按内容和目标模型上限决定，不设通用字数质量门槛。

容器校验清单准确标出 `container_check.py` 按 `shot_ref.record_id` 比较镜长，不解析 `accepted_duration_ref`；来源与字段仍由审查者核对。运动模板用真实字段 `end_report` 描述终点比较，并按既有终镜示例说明未解析的 `next_start_locator` 不证明连续性。H3 连续段说明改回实际视频与实际尾帧，Wan 默认禁字幕指令保留获准画内文字。

既有 fenced 示例保持原字节；动作链合成例未明说从压膝姿态起身，块外明确提示该省略须补足。此修订沿用 `2026-07-16-rule-tiers-and-script-boundary.md` 的既有决定，不改变规则分级。

## Alternatives considered

- 保留原措辞：改动最少，也能保留写作提示的紧凑感；但统一字数门槛、必填并行通道与已声明规则冲突，容易导致删掉必要动作或补造背景运动，故不采用。
- 扩展校验脚本以兑现说明：能自动检查更多引用；本次目标是精修文档，现有工作流没有授权新增运行时行为，故先准确标明现有校验与审查的分工。

## Consequences

规则与参考说明保持同一约束力，模板使用者能分清机器检查与内容审查。代价是仍需审查者核对容器引用源和字段；本次不增加自动校验能力，也不重新验证供应商模型规格。

## Validation

- 视频技能自测 10 项通过。
- `tests.test_structural_validators`、`tests.test_creator_first_golden` 与 `tests.test_installation_resolution` 共 93 项通过。
- 本技能 41 个既有 fenced block 与基线逐块一致；未改运行时脚本、JSON 资产与模型能力数字。
- 不执行付费生成或供应商调用，不声称本次重新验证供应商规格。

独立复核补充：已修container清单夸大脚本能力；按creator_markdown_check一对一关系说明同镜仅一正式MOTION及正文、独立补拍先新增SHOT，候选差异留普通说明。

最终复核：最终review按既有五文档迁移决定补四份历史模板只读/锁版边界。按production_tool来源选择器与本地prepare复现明确creator-first尚不能绑定续接视频，后续段保留路线并停提交；编译器支持角色不等于主流程可提交。Wan外部人类指导中的无字幕范围按VID22保留画内已接受文字，非badcase/配对示例。
