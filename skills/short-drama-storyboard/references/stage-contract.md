# 分镜阶段契约

本阶段只拥有 `剧集/<EP>/分镜.md` 中的 `SHOT-...`、镜头职责、来源、时长、起止边界、声音、三条依据和冻结关键帧。它继承剧本事实与视觉设定，不改写剧情或资产身份；场次视觉计划、拍法比选与调度推演留在上下文，不另建隐藏记录文件。

## 本阶段规则

### `SHT`

| ID | Class | Knowledge |
|---|---|---|
| SHT-01 | structural_invariant | Every production-relevant scene action, line, sound and on-screen text is carried by a shot or explicitly omitted on the `未拍场次` line with a creative reason. Each shot's `来源` names scene IDs that exist in `剧本.md`. |
| SHT-02 | reviewed_invariant | Each shot has a single dramatic/viewing purpose and preserves its source meaning. |
| SHT-03 | craft_default | Keep a short shot focused on the smallest action/reaction unit that carries its purpose; combine or split according to performance, information, and continuity rather than a fixed count. |
| SHT-04 | craft_default | Change framing/camera because attention, pressure, alignment, reveal, or rhythm changes. Each shot states its camera behavior, start/stop, and reason (including lock-offs); short push-ins, freeze frames, and white flashes are reserved for peaks. |
| SHT-05 | structural_invariant | A keyframe projects one shot boundary and the shot's declared visual basis. Any `IMG-...` used is an existing image-prompt heading, not a claim that generated media exists; when none is suitable, write `无`. |
| SHT-06 | reviewed_invariant | A keyframe is one freezeable instant, not an ordered action chain. |
| SHT-07 | taste_option | Lens vocabulary, tempo, and locked/handheld/formal style follow visual direction. |
| SHT-08 | reviewed_invariant | Each authoritative source action is realized once; repeated coverage adds reaction/detail/recontextualization, except for a declared peak impact repetition (`冲击重复：SHOT-...`) where every repeat runs from the same before-state to the same after-state. |
| SHT-09 | reviewed_invariant | Exact Location/View orientation and visible anchors match the camera side used by the shot. |
| SHT-10 | reviewed_invariant | Rendered keyframe prose contains only facts from the boundary that keyframe declares (start or end); neither frame borrows the other's facts. |
| SHT-11 | craft_default | When information changes another person's power, relationship, knowledge, or choice, preserve that reception visibly; shot count, framing, and duration follow the consequence and project profile. |
| SHT-12 | reviewed_invariant | Each audience-visibility fact binds its exact source, carrier, permission, trigger, and protection method; framing neither reveals that fact early nor hides the carrier this shot must communicate. |
| SHT-13 | reviewed_invariant | Multi-character blocking projects sourced, directed relationships into compatible positions, gaze, distance, and action lines for the current boundary. |
| SHT-14 | reviewed_invariant | A contested moving object preserves ownership, trajectory, direction, time/round state, and end location across cuts unless an authorized ellipsis says otherwise. |
| SHT-15 | reviewed_invariant | When delivery-surface overlay regions are declared, essential visual information (face/gaze, readable evidence text, decisive hand action) does not sit only inside those regions. An undeclared surface leaves the rule inactive. |
| SHT-16 | structural_invariant | The episode duration is the arithmetic sum of visible shot durations; an unresolved duration stays visibly unresolved, and a target delta is reported rather than used as a quality gate. |
| SHT-17 | structural_invariant | A keyframe declares which boundary it freezes (`起点` by default; optional `终点` only when consumed downstream). Handing over a start/end pair delegates intermediate motion to interpolation, so a decisive action cannot rest on that gap alone. |
| SHT-18 | craft_default | For a key scene where directing choice materially changes audience knowledge, alignment, spatial pressure, or landing, a scene visual plan may bridge project direction and shots in context without owning screenplay facts or shot boundaries. |
| SHT-19 | reviewed_invariant | When a coverage audition is used, its approaches genuinely differ by knowledge timing, alignment, performance space, strongest image, landing, or production fit; the selected approach is stated before formal shots are written. |
| SHT-20 | reviewed_invariant | Shot revision identity follows directing responsibility: reorder preserves IDs, insertion creates one, split/merge retires replaced IDs and creates successors, and downstream refs are reconciled before delivery. |
| SHT-21 | reviewed_invariant | A keyframe's copyable text carries only what will be visible; IDs, workflow notes, file paths and craft commentary stay outside the prompt. |
| SHT-22 | structural_invariant | Each shot carries a required `视觉依据` field written after the frozen keyframe, listing every visible character, place, or prop whose identity, Look, or geography must remain recognizable and resolving to an existing `视觉设定.md` entry. |
| SHT-23 | structural_invariant | An omitted reference choice is not consent to text-to-video. After reference discovery, each shot binds verified real images as `REF-...`, declares creator-attached pictures as `PLAN-...` (`IMG-...` or `SHOT-...`), records `待补参考图` when the creator asked to wait for files, or records explicit text-to-video consent. |
| SHT-24 | reviewed_invariant | A visual basis describes this frame, not the episode's cast list. Each declared `控制` scope stays within what this frame can carry, and a binding is not carried forward merely because the subject remains in the scene. |
| SHT-25 | structural_invariant | Every reference slot declares one `用途` from `身份/造型状态/地理/构图/尺度/效果/起始帧/结束帧/风格`. At most one `起始帧` and one `结束帧` per shot, and `结束帧` requires `起始帧`. |
| SHT-26 | structural_invariant | Every `视觉设定.md` entry called by name in a shot's `来源` quote is either covered in this shot's `视觉依据` or declared `画外` there, unless the entry opted out with `画面代称：无`. |
| SHT-27 | reviewed_invariant | When understanding a beat requires seeing its effect on a character, provide a readable reaction or consequence via a separate shot, shared staging, sound, or object state. |
| SHT-28 | craft_default | Shot durations come from the scene's sound-event timeline and accepted `target_avg_shot_seconds` (never word/paragraph counts); close-range shots meet `close_shot_share_min` when a rhythm profile is accepted. Sub-minimum shots propose a multi-shot container or hold their end state to the native minimum. |
| SHT-29 | craft_default | Dialogue coverage defaults to one turn/beat per shot, listener reaction on landing lines, shot/reverse-shot on the working side, medium talk framings with close-ups reserved for landing beats, no empty filler shots, and inserts as rhythm tools. |
| SHT-30 | craft_default | Blocking is recorded in two layers: a scene-level `场景站位` and per-shot `起点/终点` against fixed set anchors from `视觉设定.md`, then translated into camera-relative foreground/background, facing, occlusion, and screen side in keyframe/video prompts. |
| SHT-31 | craft_default | Fights are cut by exchanges (attacker → answer → result), using multi-shot containers or shortest native duration per exchange; misses/blocks read side-on, body hits sell via same-side occlusion or off-frame impact close-ups plus reaction, and one attacker acts per exchange. |

### `CON`

| ID | Class | Knowledge |
|---|---|---|
| CON-01 | structural_invariant | Linked end and next start states match or have an explicit owner revision. |
| CON-02 | reviewed_invariant | Knowledge, injury, ownership, weather, light, or physical state does not teleport/regress without story cause. |
| CON-03 | craft_default | Track downstream-relevant deltas, not the whole 设定集 in every shot. |
| CON-04 | structural_invariant | A continuity change states before, after, cause/source scene, effective range, and affected visible IDs. |
| CON-05 | taste_option | Declared montage, ellipsis, dream, or subjective imagery may intentionally break ordinary continuity. |
| CON-06 | structural_invariant | A continuity change names every existing downstream document it affects; future work is described, not pre-created. |
| CON-07 | structural_invariant | A continuity lock declared in `视觉设定.md` fixes one verbatim surface plus its shot and image scope; every in-scope frozen keyframe, motion prompt, and named image prompt carries that surface unchanged. |

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、
`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、
`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。
