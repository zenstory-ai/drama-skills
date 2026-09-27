# Evidence-Based Review Method

## Rule classification

- `structural_invariant`: objectively checkable integrity; validators may block it.
- `reviewed_invariant`: semantic integrity that needs cited evidence.
- `craft_default`: a recommended method that may change for a stated reason.
- `taste_option`: a creator choice that remains non-blocking.

## Governing know-how

- `REV-01` — Run mechanical checks before spending attention on taste.
- `REV-02` — Every finding names a bounded target, evidence, impact, required outcome, owner and severity.
- `REV-03` — A semantic-invention finding pairs the authoritative fact with the conflicting downstream fact.
- `REV-04` — Prefer a reviewer who did not author the version; disclose self-review and keep owner editing separate.
- `REV-05` — Diagnose repeated/generic mechanisms at exact locations rather than applying an “AI-ish” label.
- `REV-06` — Alternative preferences remain notes unless the current choice violates an accepted constraint.
- `REV-07` — An end-to-end drafting request does not imply creator acceptance.

## Review scope

Start from the current creator-visible files and the constraints the creator has explicitly chosen. Prefer an
uninvolved reviewer or isolated context when available; otherwise perform an honest self-check and say so in the
review Markdown. A reviewer label is disclosure, not authenticated identity.

If a target changes during review, reread that target before recording the verdict. Do not recursively invalidate
unrelated findings.

## Mechanical before taste

Mechanical examples:

- missing or duplicate Markdown IDs, broken links or unresolved references;
- unknown asset variants or contradictory camera flags;
- explicit segments not matching their declared duration;
- readable text conflicting with the accepted text policy;
- a stage document silently taking over facts owned by another document;
- delivery containing private or unapproved material.

Semantic examples:

- downstream action changes story meaning;
- a scene has no opposition or turn;
- a keyframe implies several moments;
- action load crowds out performance;
- escalation repeats the same mechanism;
- a prompt preserves the wrong identity.

## Finding anatomy

A useful finding contains:

1. stable diagnostic/rule ID when one exists;
2. project-relative file plus heading ID, line number or shot when useful;
3. bounded quotation or conflicting facts;
4. audience, continuity or production impact;
5. required outcome and preserve set, not ghostwritten replacement prose;
6. owner, severity and open/closed status.

“The dialogue is weak” is invalid. A finding should identify the exact exchange, say what fails to change, and tell
the write owner what outcome must be restored.

The review Markdown cites the current file name, heading ID, line number or a necessary short quotation directly.
It does not copy upstream snapshots, invent record IDs or create another version of the source material.

## Cross-layer synthesis

Trace important moves end to end: story fact, asset decision, shot boundary, keyframe, motion and next-shot state.
Resolve upstream meaning first; do not polish prompt wording when the shot or asset binding is wrong.

## Revision and re-review

Group duplicate findings and route them to the owning skill. A revision request states the target outcome, preserve
set and review scope to rerun.

`REV-14`: a revision request is a patch, not a rewrite. It names the smallest change at a cited location; local
findings never add up to a request to rewrite the episode. When the review compares a revision with the version before
it, any strong hook, payoff line, or comic beat that polishing removed is listed under `## 被删的强钩子` with its prior
location and a short quote, so the owner can restore it. The reviewer lists it; the owner decides. On a later explicit re-review request, read the current version, confirm the finding is addressed, check the
preserve set and close or retain each affected finding. A different reviewer is useful but not mechanically required.

## Anti-template review

Do not use a banned-word list. Look for repeated mechanisms, interchangeable character voices, abstract intensity
without playable behavior, generic quality adjectives burying identity, automatic reaction close-ups and decorative
camera movement. Cite location and impact while preserving deliberate genre rhythm.
