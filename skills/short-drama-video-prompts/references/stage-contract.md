# 视频提示词阶段契约

本阶段只拥有 `剧集/<EP>/视频提示词.md` 中的 `MOTION-...`、`GROUP-...` 项与按需的时间线音乐章节。它继承分镜的起点、终点、时长、对白和冻结关键帧，不回写分镜边界或视觉设定（参考准备中由分镜 owner 原地刷新「输入参考图」「视觉依据」除外）；不另建隐藏 JSON/QA 记录。

## 本阶段规则

### `VID`

| ID | Class | Knowledge |
|---|---|---|
| VID-01 | structural_invariant | Motion reads but cannot rewrite shot start/end/duration/dialogue and next-shot state; the `时长` declared by a `MOTION` must equal its `SHOT` duration. |
| VID-02 | craft_default | Write start anchor, ordered subject motion, camera behavior, timing, and end report; add performance change and environment/audio only when this shot actually carries them. |
| VID-03 | structural_invariant | Choose image-to-video only when the storyboard's reference set (`REF-...` and/or `PLAN-...`) is complete and copied unchanged; choose text-to-video only after explicit creator consent and carry a non-empty static visual anchor in the copyable text; withhold final output when `待补参考图` remains. |
| VID-04 | structural_invariant | Explicit non-overlapping segment timings sum(or union for declared overlaps) exactly to the shot's accepted duration, with neither overrun nor unallocated remainder. |
| VID-05 | reviewed_invariant | Untimed action load must be feasible enough to preserve the intended performance and story change. |
| VID-06 | structural_invariant | Locked and moving camera instructions cannot govern the same interval without an explicit transition. |
| VID-07 | taste_option | Camera may be locked or moving; audio/lip-sync detail follows the chosen production profile. |
| VID-08 | reviewed_invariant | Structured motion names this shot's exact subjects, actions, contacts, and results rather than reusable placeholders. |
| VID-09 | structural_invariant | The next start names an existing `SHOT-...` or is explicitly unresolved; never invent a hidden source key, record or hash. |
| VID-10 | craft_default | Resolve one accepted production profile for the current delivery scope; local variants may coexist when their range and precedence are explicit. |
| VID-11 | reviewed_invariant | A selective transform names its trigger, exact target scope, end geometry/state, and preserve set so non-target people, props, text surfaces, and spatial anchors do not change with it. |
| VID-12 | reviewed_invariant | A pickup or alternate names stable `MOTION-...` IDs and maps each source requirement to this version, the master, another pickup, or a requested storyboard revision; it never silently replaces the master. |
| VID-13 | structural_invariant | A multi-shot delivery group (`GROUP-...`) contains contiguous shots from one scene with one geography/asset chain, its duration equals the sum of member shots, and grouping preserves shot boundaries and per-shot reviewability. |
| VID-14 | craft_default | Music intent may be annotated per shot as relative entry/exit/duck, but realization belongs to the timeline layer; deliverables carry no baked-in music bed unless accepted or diegetic. |
| VID-15 | structural_invariant | Within one episode a shot belongs to at most one delivery group; grouped and loose shots account for the visible shot set exactly once. |
| VID-16 | reviewed_invariant | Multi-character motion differentiates the actors who actually carry performance change and keeps each signal readable in the accepted framing without duplicating one emotion across the cast. |
| VID-17 | reviewed_invariant | Multiple references use stable visible IDs and an explicit order, so reordering cannot silently change which reference controls which property. |
| VID-18 | reviewed_invariant | Readiness is reported from current visible inputs and real blocking gaps, never claiming generated identity, performance, lip-sync, mix, or edit quality from text alone. |
| VID-19 | reviewed_invariant | When the creator profile declares required literal trigger tokens for a delivery route, the delivery text preserves them byte-for-byte outside the verbatim-dialogue fence. |
| VID-20 | reviewed_invariant | Packing routes change delivery granularity only (long-form multi-shot generation is billed under VID-13/VID-15); continuation routes start from an observed prior result (`generated_result` + tail frame) while keeping the accepted shot start boundary as sole authority. |
| VID-21 | craft_default | For generated imagery, actions are written as high-frequency whole-body or single-limb movements; precise interception, invisible internal states, negative actions, and 3+ step two-handed choreography are rewritten into common-action combinations without changing shot boundaries or screenplay facts. |
| VID-22 | reviewed_invariant | Copyable text describes only the intended image, action, sound, and constraints (no IDs, workflow status, hashes, or file paths), prohibiting non-diegetic subtitles/captions by default while preserving approved in-scene text. |
| VID-23 | reviewed_invariant | For same-pass audio-video models, specify a closed timeline of dialogue, VO, OS, vocalizations, effects, ambience, and silence with source, speaker, language, and verbatim dialogue boundaries. |
| VID-24 | structural_invariant | An image-to-video shot copies the storyboard's `REF-...` and `PLAN-...` slots unchanged with their `用途`; reference mode (first frame, first/last frame, or multi-slot reference) is read from the `用途` combination and translated by the target model dialect. |
| VID-25 | structural_invariant | Every run of four or more Han characters inside `<d>` or quotation marks in a copyable body resolves (ignoring punctuation/spacing) to text in `剧本.md`, `视觉设定.md`, or `分镜.md`. |
| VID-26 | craft_default | Absent a director's choice, performance intensity follows form and genre: outward whole-body/whole-face poses at motion-comic and wish-fulfilment peaks, subtler realism with one readable peak beat in AI live action. |
| VID-27 | structural_invariant | A voice reference is bound on its own `参考音频` line of a `MOTION-...` entry (`用途：音色`), pointing to the speaking character's `声音参考` path in `视觉设定.md`, and numbering audio `顺序` from 1 separately from pictures. |
| VID-28 | craft_default | Fight shots follow the storyboard's exchange order as timed segments with one attacker per segment, stating strike path, receiver reaction along the line of force, character-relative limbs, set-anchor directions, and start/end weapon ownership. |

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

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。
