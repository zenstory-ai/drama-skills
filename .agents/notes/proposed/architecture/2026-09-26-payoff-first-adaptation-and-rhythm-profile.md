# Agent Note: 爽点先行的改编与项目节奏档案

Status: proposed

## Problem

维护者看完一集按本套件实跑出来的样片，结论是：选了原著最平淡的一段，改编生硬，分镜机械，没有短剧/漫剧的节奏。对 `evaluations/让你管账号/reference-run` 的诊断显示问题出在规则上，不在模型：

- **选段按时序 1:1 拉长**：20 章切出 24 个分集候选，全书第一个爽点落到 EP004。开篇替换点的判据要求「主角第一次做出会付出代价的选择」，旁观者完成的打脸因此被排除；倒叙只允许用于家庭、悬疑、关系戏；改编映射的 disposition 枚举里没有「提前」或「冷开」。
- **节奏没有 owner**：[规则分级](../../implemented/architecture/2026-07-16-rule-tiers-and-script-boundary.md) 否掉了通用节拍配额，并规定「数值只作为项目档案」，但没有任何阶段提出或承载这份项目档案。审查又被禁止拿数字比较，于是首钩时间、爽点密度、每分钟镜头数都无人负责。EP001 前 70 秒没有爽点，4 个反转里 3 个挤在最后 25 秒，没有人形对手。
- **类型契约被通用剧作理论覆盖**：「代价是唯一的张力来源」「先建立回报会被花掉的场合」压过了爽文的奖励先行；题材卡没有系统流、重生、逆袭。原著的奖励清单和喜剧吐槽被删，换成一条焦虑条款。
- **说而不演**：VO 占台词 57%，同一件事先演一遍、旁白再说一遍。
- **分镜不会切**：镜长由剧本字数折算而来（这个算法任何技能都没定义），平均 4.7 秒，每分钟 12.7 镜；没有反应镜和正反打，70% 是固定机位；SHT-08 禁止同一动作跨镜重复，也就禁掉了冲击剪辑。
- **表演偏微动作**：规则只允许「一两个细微信号」，还把「停留」推荐为最容易生成的表演。
- **默认示例示范了平淡**：`examples/creator-first/EP001` 同样是静止开场，平均镜长 6.25 秒。

外部资料给出的做法与此相反：

- 平台官方编剧教程：第 1 集从危机开始，不从原著第一章开始，第 1 集结束前交代身份、危机、目标；倒叙放在集中段，用来解释眼前的危机；每 20–30 秒一个情绪触点。
- 一组 13,087 镜的实测：真人爆款平均镜长 2.5 秒，每分钟约 23 镜，特写加近景约占一半。
- 两篇论文：LLM 剧本偏平的原因可以用专设的开场、结尾、中段反转审查加以抵消。

## Proposal

1. **爽点表先行（novel-analyze、develop）**
   - 选段前先按观众收益给全书情节点排名。打脸、奇观、反转、身份揭露、奖励兑现都算，主角不在场也算。
   - 开篇替换点改为「观众在此处最强的收益」。EP001 至少给出 3 个入口，其中一个是把后文高潮提前做冷开。
   - disposition 枚举增加 `move_earlier`、`cold_open`，并定义它们的因果补偿义务。
   - 集数与章数的压缩关系由爽点分布决定，不按章 1:1 切分。
2. **项目节奏档案 `creator_authority.rhythm_profile`**
   - 由 develop 按制作形态提出默认值，创作者接受或修改后，write、storyboard、review 只做已接受数值上的算术核对。
   - 字段：首钩秒数、情绪触点间隔上限、每集至少几次有对手的反转、集尾停在峰值前、下集开头接上集最后一拍、VO 占比上限、目标平均镜长、特写与近景占比、全书第一个大爽点最迟第几集。
   - 真人短剧与漫剧各给一套默认值，属于 `craft_default`。这正是 07-16 决定留下的「项目档案」位置，并不推翻那次决定。
3. **类型契约**：新增系统流、重生、逆袭题材卡（奖励先行、反派压迫到位、保留喜剧吐槽），并把「代价是唯一张力」收窄为适用于部分题材。STY-23 允许世界设定延后兑现。
4. **剧本**：能演的不说。VO 不复述已经演出的信息，VO 占比服从节奏档案。痛点落成具体场景；台词写完再删三分之一。
5. **分镜**
   - 镜长由目标平均镜长和声音事件共同决定，不再按字数折算。
   - 一句台词一个镜头，默认给听者或反应镜。
   - 允许冲击重复，这是对 SHT-08 的收窄。
   - 快切优先装进多切容器生成，剪辑时掐掉起势与余量。
6. **表演**：按形态和题材决定表演强度，漫剧与爽文的关键姿态和表情可以外放；「停留」不再是默认推荐。
7. **审查**：增加三个只看局部的检查，分别看开场钩子（只读第一段）、结尾悬念（只读最后一段）、中段反转密度。修改只打补丁，不整体重写；被润色删掉的强钩子要记录下来，可以捞回。
8. **示例**：用新规则重做 `examples/creator-first/EP001`，或者换成一集高节奏的样例。

**验证**：
- 纯文本 A/B：新旧规则各改编一次《让你管账号》EP001–003，比较首个爽点所在集数与秒数、每集有对手的反转数、VO 占比，再做盲评。
- 真实视频 A/B：新旧分镜各生成同一集，测量平均镜长；节奏观感由维护者看片判定。

## Alternatives considered

- **把节奏数字写成套件级硬门槛** — 最强理由：实现最简单，审查最容易执行。不用：07-16 已经否掉，而且不同题材和形态的合理节奏差异很大。这里改为项目档案，创作者说明理由即可改。
- **只改示例，不改规则** — 最强理由：改动最小，示例本身的示范力很强。不用：诊断里的前三个根因都是规则直接要求 agent 那样做，只换示例挡不住规则。
- **在 write 阶段加快节奏，不动改编** — 最强理由：只动一个技能。不用：第一个爽点在第 4 集，是选段造成的，剧本阶段「召回只补细节，不新增剧情」，拿不回后文的高光。

## Consequences

- **收益**：选段、单集节奏、分镜密度都有了 owner 和可核对的数值；把高光提前有了合法的词汇；题材契约回到爽文本位。
- **代价**：
  - 改动横跨 novel-analyze、develop、write、storyboard、video-prompts、review 六个技能和示例，需要迁移说明。
  - 已按旧规则跑完的项目没有 `rhythm_profile`，只能回退为「未声明，不核对」。
  - 默认数值来自有限的公开实测，需要用维护者提供的爆款样片再校准。
  - 更快的剪辑密度会增加生成次数，这部分靠多切容器抵消。

## Implementation log (part 1)

档案的写入、校验与提出，爽点先行的改编，题材契约。

- `skills/short-drama/scripts/project_tool.py`：`set-authority` 写 `/creator_authority/rhythm_profile` 时校验类型与范围（十个字段必须齐全，`form` 限两种，秒数为正，占比在 0–1，计数为非负整数，集号 ≥ 1，拒绝未知字段），旧清单没有槽位时首次写入自动建立；`status` 新增 `rhythm_profile`，只返回已接受的档案。
- `skills/short-drama/SKILL.md`：档案的写入路径与「未声明不核对」语义。`references/knowhow-index.md`：新增爽点排名、项目节奏档案两条路由，并替 part 2 登记写作、分镜、视频提示词、审查的新主题。
- `skills/short-drama-novel-analyze/`：`rhythm-and-emotion.md` 新增爽点表（`aggregation-and-entities.md`，NVA-13）；开篇替换点改为「观众收益最强且能交代身份、危机、目标」并报告冷开候选（`adaptation-triage.md`）；候选集按爽点分布切、引用 `payoffs`（`adaptation-value.md`、`episode-candidate.example.jsonl`、`SKILL.md`、`stage-contract.md`）。
- `skills/short-drama-develop/references/episode-design.md`：倒叙与结果预演不限题材；§4.3 门槛集给出起点区间与停法（STY-27）；§4.4 首集入口（STY-25）；§10 项目节奏档案与两套默认值（STY-26）；STY-06 指向档案。
- `skills/short-drama-develop/references/adaptation-craft.md`：按爽点压缩（STY-28）；召回与「提前后文」分开；误删一段改写；`move_earlier`、`cold_open` 及因果补偿（STY-29）；世界设定可延后。`assets/adaptation-map.example.jsonl`：枚举与 `causal_compensation`。
- `skills/short-drama-develop/references/genre-cards/系统流.md`、`重生穿越.md`、`逆袭.md`：新题材卡；`genre-cards.md` 登记并改写装置与题材的分层、节拍数量一条；`复仇打脸.md` 让出「逆袭」别名。
- `skills/short-drama-develop/references/premise-devices.md`、`story-craft.md`：「代价是唯一张力」「先建场合再给能力」收窄为部分题材。`genre-and-hook-playbook.md`：爽文一行、开场选择改为收益入口并指向档案。`serial-character-and-memory.md`：STY-11 与首集入口对齐。
- `skills/short-drama-develop/SKILL.md`、`assets/creative-brief.md`、`references/stage-contract.md`：档案候选与首集入口的落点；登记 STY-25–29，改写 STY-06、STY-11、STY-22、STY-23。
- `tests/test_simple_lifecycle.py`：档案缺字段、越界、错形态、未知字段都不落盘；完整档案写入后可单改一个值；`proposed` 不算已声明。删掉校验、槽位创建、状态过滤或占比范围任一处都会红。

## Implementation log (part 2)

write、storyboard、video-prompts、review 四个技能读取已接受的 `rhythm_profile`，只做算术核对，从不写入。

- `skills/short-drama-write/references/script-craft.md`：§1 改为数值只对已接受档案有效；新增 §4.4 能演的不说（SCR-20）、§6.5 项目节奏档案（SCR-19）；§8.1、§8.2 的开场与收束形态让位于已接受档案。
- `skills/short-drama-write/SKILL.md`：对白初稿读后删约三分之一（SCR-21）；按需知识加两条入口；时长估算说明 `vo_share`。
- `skills/short-drama-write/references/dialogue-craft.md`：比例不证明质量一句，注明 VO 占比上限是唯一例外。
- `skills/short-drama-write/references/stage-contract.md`：登记 SCR-19、SCR-20、SCR-21。
- `skills/short-drama-write/scripts/duration_estimate.py`：新增 `voiceover_characters` 计数；档案已接受时报告 `vo_share` 与是否超过 `vo_share_max`，只报告不阻断。
- `skills/short-drama-storyboard/references/shot-craft.md`：SHT-08 允许峰值处声明过的冲击重复；近景类占比下限；固定机位不再是默认，峰值强调手段；对白估时改为长台词拆到说话者与听者；新增镜长推导（SHT-28）与对白覆盖默认（SHT-29）。
- `skills/short-drama-storyboard/SKILL.md`：读取节奏档案；短于原生下限的镜头默认装进多切容器，一镜一生成时才保持终点；SHT-08 例外指针。
- `skills/short-drama-storyboard/references/production-shot-grammar.md`：删掉每 4–8 秒一切的带宽，改指向镜长推导。
- `skills/short-drama-storyboard/references/blocking-playbooks.md`：群戏调度顺序的最后一步改指向对白覆盖默认。
- `skills/short-drama-storyboard/references/stage-contract.md`：SHT-04、SHT-08 改写；登记 SHT-28、SHT-29。
- `skills/short-drama-video-prompts/references/motion-recipe.md`：表演处理从“一两个细微信号”改为一个读得出的信号；新增按形态与题材的表演强度（VID-26）。未动量级相关行。
- `skills/short-drama-video-prompts/references/generability.md`：推断性内心状态改写为可见表情；“停留”只替换精细操作，不替换表演。
- `skills/short-drama-video-prompts/references/target-model-profile.md`：原生时长一行与多切容器默认对齐。
- `skills/short-drama-video-prompts/references/stage-contract.md`：登记 VID-26。
- `skills/short-drama-review/references/rubric-story-script.md`：数值只核对已接受档案；新增档案核对表（REV-12）与三个局部检查（REV-13）。
- `skills/short-drama-review/references/rubric-visual-motion.md`：平均镜长与近景类占比的核对。
- `skills/short-drama-review/references/review-method.md`：修订只打补丁，被润色删掉的强钩子记录可捞回（REV-14）。
- `skills/short-drama-review/SKILL.md`、`references/stage-contract.md`：路由说明；登记 REV-12、REV-13、REV-14。
- `tests/test_creator_first_golden.py`：规则目录范围扩到新 ID。`tests/test_structural_validators.py`：VO 占比在已接受档案下报告、未接受时不报告，三处变异都会红。

