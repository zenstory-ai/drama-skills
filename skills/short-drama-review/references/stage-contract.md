# 审查阶段契约

本阶段只拥有审查结论与修订要求，不改写 owner 来源。需要落盘时使用创作者可读 Markdown，引用当前
文件名、标题 ID、行号或短引文；不建立 JSON/JSONL、来源快照、哈希或接受状态。

审查可以由独立 reviewer 或明确标注的自检完成。媒体不可见时保持未知；外部生产仍需要自己的显式确认。

## 本阶段规则

### `REV`

| ID | Class | Knowledge |
|---|---|---|
| REV-01 | structural_invariant | Run mechanical checks before spending creative review attention. |
| REV-02 | structural_invariant | A finding names a visible file and heading/shot/prompt ID, and includes evidence, impact, required fix, owner, severity and status. |
| REV-03 | reviewed_invariant | Semantic invention cites the source fact and conflicting downstream fact. |
| REV-04 | craft_default | Prefer a reviewer who did not author the current targets; disclose self-review, and keep reviewer findings separate from owner edits. |
| REV-05 | craft_default | Diagnose repeated structure or generic language with location and impact; do not label output merely "AI-ish". |
| REV-06 | taste_option | Alternatives remain notes unless they violate an accepted creator constraint. |
| REV-07 | structural_invariant | An end-to-end drafting request cannot impersonate creator acceptance; preview chains remain provisional and undeliverable. |
| REV-08 | craft_default | When authorized text notes report production defects, trace text/subtitle residue, music-boundary violations, wardrobe drift, axis breaks, or lip-sync mismatch to the exact prompt/spec text and keep unobserved outcomes unknown. |
| REV-09 | reviewed_invariant | After prompt revision or repackaging, recheck source coverage and every applicable accepted directive; correct asset bindings alone do not prove compliance. |
| REV-10 | reviewed_invariant | A project-calibration finding distinguishes input-reference from generated-result observation, binds the exact project, the prompt/spec records it observed, stable reference slots, production configuration, method and limits, and—when its disposition calls for a change (see REV-11)—proposes the smallest owner-routed one with a preserve set; it does not generalize across projects or infer quality from task state. |
| REV-11 | reviewed_invariant | A calibration finding carries `disposition` (keep, post_production, targeted_edit, resubmit, rewrite) and `disposition_rationale` before any revision text, justified by whether the defect is text-controllable and whether it has already recurred. Dispositions that call for no change leave `required_change` empty rather than inventing one. Resubmitting identical text and appending quality adjectives are not repairs; a recurring defect routes to a structural change instead. Findings outside project calibration use `not_applicable`. |
| REV-12 | craft_default | When the project's rhythm profile has status `accepted`, review checks the episode against it by arithmetic on the accepted values only and reports a deviation as a non-blocking finding citing field, accepted value, measured value, and location; the creator may keep the episode with a stated reason. A missing or proposed profile leaves the check inactive, and no finding compares against another project's or a suite-wide number. |
| REV-13 | craft_default | Beyond the whole-episode read, three local passes each read one part only: an opening-hook pass on the first segment, which also reads the first beat alone as the image of the first three seconds, an ending-suspense pass on the last segment, and a reversal-density pass on the middle. |
| REV-14 | craft_default | A revision request is a patch at a cited location with a preserve set, never a whole-episode rewrite; a strong hook, payoff line, or comic beat removed by polishing is logged with its prior location and quote so the owner can restore it. |

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、
`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、
`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。
