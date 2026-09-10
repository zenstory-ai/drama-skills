# 剧本阶段契约

本阶段只拥有 `剧集/<EP>/剧本.md`：场景、动作、对白、画外音、声音事实、画面文字、连续性提示与转场。
它继承项目/分集决定，但不决定人物视觉身份、镜头构图、提示词或媒体生产。

所有来源都用文档中可见的集号与场景 ID 定位；不建立第二份节拍、block、审批或状态文件。格式标签
只负责区分生产语义，不借格式补造剧情。输入明确给出的事实、必须/禁止、题材观看契约与退出状态优先于本表；规则不能补造题面没有的精确数字、记录、资源、程序或机关。

## 本阶段规则

### `SCR`

| ID | Class | Knowledge |
|---|---|---|
| SCR-01 | reviewed_invariant | When a scene is organized around active pursuit or conflict, it has a current agenda, opposing force, directional turn, and exit state. A traceable fact, leverage change, cost, authority, or choice makes the prior strategy fail; an opponent's unexplained silence, inaction, or departure does not substitute for the turn. Atmospheric, ritual, montage, transition, and consequence-processing scenes may instead justify themselves through a necessary change in knowledge, relationship, pressure, rhythm, or production state; they must not manufacture an opponent merely to satisfy this rule. |
| SCR-02 | craft_default | Prefer choices and consequences over coincidence for major turns. |
| SCR-03 | reviewed_invariant | Private thought is expressed through behavior, evidence, or deliberate VO/OS. |
| SCR-04 | craft_default | Dialogue carries agenda, relationship, subtext, and a change—not only information. |
| SCR-05 | structural_invariant | Existing production tags use supported, closed syntax and resolvable references. A continuity tag records a state established by shown action; it cannot establish that an unseen event or contact never occurred. |
| SCR-06 | taste_option | Silence, slang, interruption, narration, and sentence rhythm remain character/style choices. |
| SCR-07 | reviewed_invariant | Story-critical text, VO/OS, SFX, transition, and continuity requirements are not left indistinguishable from ordinary prose. |
| SCR-08 | craft_default | When abstract emotion obscures performance, translate it into character-specific behavior, object handling, distance, silence, or delivery. Dialogue turn length and tactic follow the scene agenda rather than a universal attack-defense cadence. |
| SCR-09 | craft_default | Break a long speech with a visible action beat that changes the speaker's tactic, giving downstream a sourced cut point and the performance a breath; a speech with no internal turn is shortened rather than split. |
| SCR-10 | reviewed_invariant | When the creator marks a beat's realization as replaceable under later pressure, the record separates the dramatic function from the current depiction and names a fallback depiction that delivers the same function: same person proven or changed, downstream payoff refs and next-episode entry state still satisfied, cost not erased, no new setup required. Deleting the beat is never a fallback. An unmarked beat leaves the rule inactive—the suite carries no platform standard, predicts no outcome, and pre-emptive sanding is the more expensive mistake. |
| SCR-11 | craft_default | When sound carries story information, spatial pressure, off-screen presence, a deliberate silence, or a scene bridge, the screenplay identifies the necessary source/event and its dramatic target; it does not prescribe per-shot mixing, add decorative sound to every scene, or use music to replace performance. |
| SCR-12 | craft_default | A crowded scene first makes clear who is contending with whom—by cutting non-essential presence, staggering entrances, splitting the scene so one opponent holds the focus at a time, or handing attention from one character to the next—rather than naming every present character in action paragraphs. Deliberately chaotic ritual, siege, or farce may override this once the disorder is a visible choice and one followable thread remains. |
| SCR-13 | reviewed_invariant | When a beat is framed as a consequential choice, at least two executable values remain live until the character acts, and the screenplay makes the relevant stakes and newly caused cost perceptible. This rule is inactive for ordinary decisions, habits, or single-path pursuits; it must not manufacture a dilemma the episode does not need. |
| SCR-14 | reviewed_invariant | When a belief change hinges on contested evidence, the conclusion stays within what the evidence and any shown test support. If that evidence is a primary episode engine, at least one audience-followable state change changes which explanations remain live or changes the next action; routine photographing, bagging, numbering, or logging does not count by itself. The scene may test the strongest live counter-explanation, preserve uncertainty, or intentionally delay verification; this rule does not require a forensic procedure for uncontested facts, comic misunderstanding, subjective narration, or clues whose ambiguity is the point. |
| SCR-15 | craft_default | A local payoff leaves a legible result or aftereffect without replacing the episode's meaning with a slogan. A cost framed as central pressure has a material exit-state effect rather than automatically resetting once the action succeeds. The result may be plot change, relationship response, irony, stillness, tonal afterimage, or an intentionally open state; a new external event is not mandatory. |
| SCR-16 | reviewed_invariant | When a literal precise deadline is foregrounded and audience-auditable, its action chain fits the stated time and established resources, or the screenplay makes compression, failure, or a changed objective legible. Qualitative urgency is not upgraded into invented minutes, timestamps, notifications, or records. Montage, ellipsis, subjective time, and declared stylization follow their own established convention rather than an automatic real-time test. |
| SCR-17 | reviewed_invariant | When the brief defines a limited number of attempts, turns, breaths, beats, or other units, each unit is counted by its visible end-state. A label, count, request, authorization, preparation step, or cleanup after the boundary does not substitute for the required completion; intentional partial completion or failure remains valid when it is the legible result of that unit. |
| SCR-18 | craft_default | An action paragraph does not open with a noun phrase followed by a full-width colon. `第二格：一只手把杯子推过去。` is byte-for-byte the dialogue form `角色名：台词`, so the indexer can only return `ambiguous_dialogue_or_action` and hand it back for a human read; every such line costs one round trip for nothing. A dash, a comma, or a verb removes the collision. Colons inside a sentence are unaffected — only the start of the line collides. |

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、
`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、
`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。
