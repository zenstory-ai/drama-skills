# Agent Note: 技能参考资料的示例与评估原著保持无关

Status: implemented

## Problem

主工作流实跑用的固定原著是《让你管账号》，公开示例 `examples/creator-first/` 也改编自它。v0.9.1 发布前的实跑里，三个阶段的 agent 分别指出技能参考资料里标为“合成”的示例几乎就是这本书的情节：develop 的转折示例（群里被问是不是急了的内部人士、只发一条链接、喊举报的人点开视频、申请表被推回来）、改编原则里“温和护短、只是不看好主角的上级成为第一个被打脸的人”、系统流题材卡的对手压迫、资产时代锚点的“部队宣传部门办公室”，以及 v0.9.1 新写的场景站位示例直接用了示例里的人名和地点。参考资料等于提前给了答案，实跑结果会偏乐观；这也不符合“示例一律合成改写”的约定。

## Decision

把这些示例改写成与评估原著无关的合成内容，教的要点不变：

- `short-drama-develop/references/episode-design.md` §6.1 转折示例改为村里讨债、房契、车间调岗；
- `adaptation-craft.md` 的立场示例改为“嘴硬心软、不信徒弟能成的老师傅”；
- `genre-cards/系统流.md` 的对手压迫改为饭局扔菜单、划掉参赛名单、“拿不到名次就别回来”；
- `short-drama-assets/references/era-anchors.md` 合成例改为城郊外卖站点；
- `short-drama-storyboard/references/blocking-playbooks.md` 场景站位示例改用文件里已有的沈一舟、赵经理与财务室；`shot-craft.md` 的运镜例句改为“这单我接了”；
- `short-drama-video-prompts/references/seedance-2.5.md` 的音色参考例句改用沈一舟；`short-drama-edit/SKILL.md` 卡片样式示例改为订单数。

`examples/creator-first/`、`docs/` 与测试夹具保持不变：它们是公开示例与回归数据，不是技能执行时读到的指引。

## Alternatives considered

- **换一本评估原著**：参考资料不用改。未采用：示例和 README 都围绕这本书，换书要重做整套公开示例；而参考资料与示例同源的问题换书后仍会再次出现。
- **只在评估时屏蔽这些段落**：实跑结果不受影响。未采用：创作者实际使用时读到的也是这些段落，屏蔽只让评估与真实使用分叉。

## Consequences

- **收益**：主工作流实跑不再从参考资料里直接拿到这本书的情节与人名，结果更能代表陌生原著；示例回到合成改写的约定。
- **代价**：以后新增示例时要避开示例与评估原著；这里没有机械检查，靠写作与审查时留意。
