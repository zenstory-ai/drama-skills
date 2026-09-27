# 开发阶段契约

## 目录

- [独立运行与项目集成](#独立运行与项目集成)
- [所有权边界](#所有权边界)
- [制作形态需要什么](#制作形态需要什么)
- [本阶段规则](#本阶段规则)

本文件是本技能的自包含契约：预检、所有权、形态输入与规则表都在这里，
不需要读取其他技能的文件。

## 独立运行与项目集成

本技能可以单独安装并运行；下面几条说明项目工具存在时怎样集成。

1. **读取直接输入**：只读取用户明确提供或当前任务实际需要的文件，不批量加载整个项目。
2. **可选项目集成**：若存在 `short-drama.json` 且 core 项目工具可用，可以运行
   `python3 <core>/scripts/project_tool.py status <project>`，使用返回的目录布局和语言设置；
   core 不可用时，直接基于已提供输入产出本阶段文件。
3. **可选发布生命周期**：项目工具可用时，用 `publish` 原子发布并用 `--input <path>`
   声明直接输入；`accept`、`review` 与 `package` 继续承担确认、复核与交付。
4. **保持职责分离**：创作者确认、内容修订和复核是不同动作；reviewer 提修改要求，负责人改文件。

## 所有权边界

- **本阶段拥有**：系列承诺、冲突引擎、弧线、已规划的单集契约；已规划的知识/目标/关系/
  交接状态；改编取舍与题材选择。
- **本阶段继承**：创作者已接受的方向、约束、题材与受众承诺。
- **本阶段不越权**：不写逐镜事实，不指定供应商字段，不代替剧本决定场景怎么演。剧本环节
  只投影本契约，不复制它；契约变化时由本阶段发出修订，让下游刷新引用。

## 制作形态需要什么

视觉风格不是贴在提示词前面的标签。创作者已接受的视觉方向与制作形态由项目层决定并传入，
**本技能不加载形态卡，也不自行选择形态**；本节只说明本阶段需要形态回答什么、以及拿到
答案后投影成哪些字段。

形态决定属于 `craft_default`：创作者说明理由即可覆盖。形态不能创造新的
`structural_invariant`，也不能改写身份、地理、持物归属与可读文字政策。审查者不得单凭
形态偏好阻断交付。

不要用“加一句风格前缀”处理形态差异。前缀只改变检索标签；形态改变的是**必须出现和
可以省略的字段**，只有后者会被执行，也只有后者能被审查。

本阶段要向形态决定问四件事，答案写进创作简报，不写进剧本：

- **叙事职责**：这种形态要帮观众更快看懂什么、感到什么——不能只写“高级”“电影感”。
- **运动预算**：哪些段落必须全动作，哪些可以靠保持姿态、局部循环、视差或剪辑完成。
  这直接决定分集地图里哪些场面写得起、哪些要换写法。
- **未决试验**：哪些形态能力还没验证过，需要先做小样。
- **节奏起点**：这种形态的项目节奏档案从哪组默认值起步（`STY-26`）。

本阶段新增：叙事职责、形态假设、运动预算、未决试验与节奏档案候选。不产出形、材质、光或镜头层字段。

## 本阶段规则

### `STY`

| ID | Class | Knowledge |
|---|---|---|
| STY-01 | craft_default | State the promise as protagonist, pursuit, costly opposition, and recurring payoff. |
| STY-02 | craft_default | Build a repeatable conflict engine whose pressure can change power, knowledge, relationship, exposure, cost, or time. |
| STY-03 | reviewed_invariant | A beat/episode escalation must change a story state rather than repeat the same pressure louder. |
| STY-04 | craft_default | Enter with pressure active and deliver part of the promised payoff before the outgoing hook. |
| STY-05 | structural_invariant | Incoming/setup/payoff references resolve to known records or are explicitly unresolved. |
| STY-06 | taste_option | Hook form, arc shape, episode count, and climax position follow the creator's format; how many seconds before the first hook and between emotional beats comes from the accepted rhythm profile, not from this rule. |
| STY-07 | reviewed_invariant | Every adaptation treatment—merge, carrier change, compression, reordering, or addition—preserves each core source character's stance toward the protagonist and way of acting, the core relationships, and the main line, and contradicts no source fact, unless the creator has accepted that change; a proposed change of stance or relationship keeps its actual disposition, names the change in `lost_or_changed`, and stays at `creator_acceptance.status` `pending` until then. Character/scene merges also preserve dramatic function, knowledge permissions, relationship position, and causal bridges. |
| STY-08 | craft_default | Translate exposition through consequential behavior, evidence, spatial pressure, or dialogue strategy before adding neutral explanation. |
| STY-09 | reviewed_invariant | A reveal/reversal grows from established facts and changes a plan, explanation, relationship, or costly choice. |
| STY-10 | craft_default | Establish the recurring-payoff promise once the opening pressure makes it legible; an opening may imply, delay, or state it according to genre and creator intent. Plan each outgoing hook from the episode's local result rather than repeating a type by quota. |
| STY-11 | craft_default | Build only the prior-world reservoir needed to predict present choices, then enter where pressure is already active; the moment an established strategy begins to create visible cost is one candidate, weighed for the first episode against the payoff and cold-open entries of STY-25. |
| STY-12 | reviewed_invariant | Claimed character progression cites a pressure test, choice or retreat, local result, cost, and changed visible strategy. It is recorded once per character in the story engine, not restated in every episode record; the episode carries only the local result and the outgoing pressure it produced. |
| STY-13 | reviewed_invariant | Each episode produces a local dramatic result before its outgoing hook; serialization cannot rely only on pausing an unfinished action. |
| STY-14 | craft_default | Maintain compact serial memory for character strategy/state, relationships, information permissions, setup debt, rhythm, and exact handoff. |
| STY-15 | reviewed_invariant | Calibrate each information release to what its visible carrier directly supports, while keeping unproved identity, cause, motive, or mechanism explicit as unresolved inference. |
| STY-16 | craft_default | Before scene work, estimate each planned episode's shot and duration magnitude from the project's own accepted ratios, and resolve order-of-magnitude outliers in the map; the estimate informs the creator and never blocks delivery. |
| STY-17 | reviewed_invariant | A premise device separates its creator-accepted contract (scope, failure conditions, cost, whether its own declarations are reliable) from in-fiction disclosure; the contract is accepted before the device first takes effect, while disclosure may lag, stay partial, or be misstated by a character or the device itself. Every later device ability or exemption traces to a contract clause—an untraceable one is retroactive widening—and the audience not yet knowing every boundary is never itself a defect. |
| STY-18 | structural_invariant | A multi-episode source is read through an exact-byte episode index that `verify` checks against the current source — total length, span validity, ordering, and line/byte agreement — so an edit that changes any length is reported. A same-length rewrite in place is not, and source drift still invalidates every old span, so whoever edits the source re-indexes it. Resume derives missing IDs from the current episode map rather than a last-completed guess. |
| STY-19 | craft_default | For a multi-episode source, the Agent chooses each batch from this file's measured episode spans, semantic complexity, and available context, then reads only the current slices and compact accepted handoff; no fixed episode quota substitutes for that judgment. |
| STY-20 | craft_default | Name each unit's repeating mechanism, the payoff the audience can expect from every run of it, and the condition under which the loop ends; the first run demonstrates the mechanism in full so later runs pay off on recognition, and each further run changes the opponent's knowledge, the execution difficulty, the mechanism's scope, who is now aware, or which retreat is closed. |
| STY-21 | craft_default | Retire a loop deliberately—close it, remake one of its premises, or hand it to another character—before opening the next one, and carry the stake, deadline, and exit cost forward instead of rebuilding urgency from zero; a new loop opened alongside an unsettled one weakens both. |
| STY-22 | craft_default | When returning to a long source for detail while writing downstream, retrieve with an event anchor—character plus place/object plus the current action or conflict—rather than a recurring concept term; read back the matched span instead of writing from the search summary; and before use, check the excerpt's knowledge state against the episode's entry state, treating anything ahead of it as reference only. Recall fills in detail for an accepted contract; pulling a later source beat forward is legitimate adaptation, done as a `move_earlier` or `cold_open` revision of the episode map rather than while writing an episode. |
| STY-23 | reviewed_invariant | A source fact the brief registers as unchangeable is either realized on screen inside the episodes this round covers—named in the episode record and present in that episode's screenplay—or explicitly deferred to a named episode. A visible carrier an episode record declares must actually appear in that episode's screenplay; a carrier that only works as a comparison needs both of its halves staged. Registering a fact is not paying it off. World-setting facts in particular may be deferred to the episode where they first change a choice; the first episode owes only the rules its own conflict uses. The suite runs no mechanical check for this; the reviewer cites the brief and the episode record against the screenplay. |
| STY-24 | reviewed_invariant | Each episode's directional turn and its payoff inside that episode name one concrete visible action -- who did what -- rather than only the function or state change it achieves; an opposing force's leverage is likewise written as something it has done or will do. The suite runs no mechanical check; the reviewer cites the function against the visible action that carries it, and a function with no such action is the defect. It does not require a full scene. |
| STY-25 | craft_default | Choose the first episode's entry from at least three candidates, one of which moves a later climax forward as a cold open. Score every candidate on the same two counts: the single image the viewer sees in the opening frame and the question it raises on its own, without reading on-screen text or knowing who anyone is; and the episode's payoff. Prefer an entry whose opening image is itself a hook, with a strong payoff, that lets the episode establish the protagonist's identity, crisis and goal before it ends, and state the big goal early and concretely enough to check. |
| STY-26 | craft_default | Propose a project rhythm profile (`creator_authority.rhythm_profile`) from the production form, starting from the per-form defaults in episode-design, for the creator to accept or edit. The defaults are starting points, never a suite-level threshold; later stages check only arithmetic against an accepted profile, and a missing or unaccepted profile means nothing is checked. |
| STY-27 | craft_default | When the creator declares paywall episodes, place each before an undelivered payoff and stop one beat before the reveal, with a line hook or an image hook pointing at what the audience already awaits; the episode still delivers its own local result first. Episode numbers are the creator's and the suite supplies no default position; common ranges are offered as examples only when the creator has declared paywalls and asks for placement. |
| STY-28 | craft_default | Compress an adaptation by keeping the source's hottest plot points first, then cutting subplots and merging duplicate-function characters; episode count follows the payoff distribution rather than one chapter per episode. |
| STY-29 | reviewed_invariant | An adaptation mapping marked `move_earlier` or `cold_open` states the setup it depends on and where and through which carrier that setup appears first, or how the viewer is oriented in time, and what happens at the beat's original position. The reviewer checks the mapping against the episode record and screenplay; a moved beat that lands before the audience has the facts it needs is the defect. |
| STY-30 | craft_default | Material the source does not contain—a new character, an invented scene, a new or replaced opponent—is registered as its own `add` mapping stating the function it serves, why existing source characters and events cannot carry that function, and which source facts were checked against it, and it is listed in the brief for the creator to confirm. Opposition an episode needs is drawn first from source characters and what they actually do; where the source has none, the rhythm-profile deviation is reported instead of hardening an ally or inventing an opponent. |

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、
`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、
`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。
