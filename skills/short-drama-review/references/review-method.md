# Evidence-Based Review Method

## Mechanical before semantic and taste (`REV-01`–`REV-07`)

1. **Mechanical checks first (`REV-01`)**: verify missing/duplicate Markdown IDs, broken links, unresolved `REF-...`/`IMG-...` bindings, contradictory camera flags, explicit segment durations not summing to shot duration, text-policy conflicts, cross-stage ownership overreach, and private/credential leaks.
2. **Semantic checks (`REV-03`)**: pair the authoritative upstream fact with the conflicting downstream text whenever a stage drops or invents story meaning, opposition/turn, single-instant keyframe state, feasible action load, or asset identity.
3. **Taste boundaries (`REV-06`, `REV-07`)**: alternative preferences remain `note` unless they violate an accepted creator constraint. An end-to-end drafting request never implies creator acceptance.

## Finding anatomy and revision patches (`REV-02`, `REV-14`)

- **Finding fields (`REV-02`)**: follow the 6-item finding format in `SKILL.md` (rule ID + class, file + heading/line/shot ID, bounded quote/conflicting facts, impact, required outcome + `preserve_set`, and owner + severity + status).
- **Smallest bounded patch (`REV-14`)**: group duplicate findings by owning skill. A revision request specifies the smallest change at the cited location, the `preserve_set`, and the review scope to rerun; local findings never authorize a whole-episode rewrite.
- **Logging removed hooks (`## 被删的强钩子`)**: when comparing a revision against the prior version, list any strong hook, payoff line, or comic beat removed during polishing under `## 被删的强钩子` with its prior location and short quote so the owner can decide whether to restore it.
- **Explicit re-review**: when asked to re-review, reread the updated target, verify both the required outcome and `preserve_set`, and close or retain each affected finding without invalidating unrelated findings.
