# Story And Script Rubric

## Story promise, episode shape, and serial memory

- **Promise & engine (`STY-01`–`STY-06`)**: protagonist, active pursuit, costly opposition, and recurring audience payoff are stated concretely rather than replaced by a genre label; escalation alters power, knowledge, relationship, exposure, cost, or time rather than repeating the same misunderstanding, humiliation, rescue, or reveal; setups/payoffs and episode handoffs resolve to explicit records.
- **Episode arc & agency (`STY-13`, `SCR-13`, `SCR-15`)**:
  - Opening pressure, protagonist want, resisting force, directional turn, local dramatic result before the outgoing hook, and exact next-episode entry state are legible from the screenplay alone (an episode that pauses an unfinished action without landing a local result fails `STY-13`).
  - The protagonist's choice causes the result (or earlier action triggered the external arrival and present response).
  - When a turn is framed as a consequential choice (`SCR-13`), both directions protect a live value and the chosen action causes a perceptible cost (leave inactive for single-path pursuit; fail if one direction was already valueless/impossible or if a cost/deadline was invented at decision time).
  - Payoffs preserve established residue rather than replacing meaning with a slogan (`SCR-15`), and post-result beats do not contradict consequences declared irreversible.
  - Capacity estimates (`STY-16`) are informational only; rhythm checks use only an accepted profile ([below](#rhythm-profile-rev-12)).
- **Foreknowledge & authorized ability (`STY-17`)**: separate the **contract layer** (scope, failure conditions, cost, reliability accepted in the story engine before first use) from the **disclosure layer** (current episode knowledge). Partial disclosure is normal suspense, not a defect. Fail when:
  - A later ability or exemption traces to no contract clause (retroactive widening), or a disclosed rule is violated without an unreliable-device contract;
  - Stripping the device leaves no protagonist choice, or the author invents ad-hoc timeline limits/costs to weaken the protagonist or dilute genre payoff;
  - An on-screen readable device carrier conflicts with a global `no-text` policy.
- **Entry, character arc, and contested evidence (`STY-12`, `STY-15`, `SCR-14`)**:
  - First episode enters on an active window rather than dumping the backstory reservoir; world truth, character beliefs, and audience knowledge stay distinct; serial memory preserves relationship state, information permissions, setup debt, and physical handoff.
  - Every claimed character change shows a pressure test, choice/retreat, local result, cost, and changed visible strategy (`STY-12`).
  - Each evidence carrier separates what it directly proves from unresolved inference (`STY-15`). When a belief change hinges on contested evidence (`SCR-14`), response stays within what was proved (or intentionally preserves uncertainty), at least one visible state change narrows live explanations or alters the next action (mere photographing/bagging/logging is not a turn), and any continuity-dependent proof (sealing, position, lack of contact) is preserved by preceding action rather than asserted by a label.

## Adaptation fidelity (`STY-07`, `STY-30`, `REV-03`)

Active only when adapting a source (`项目开发/adaptation-map.jsonl`):

- **Core character stance & main line (`STY-07`)**: core characters keep their source stance toward the protagonist, mode of action, and relationships unless the creator accepted the change (turning a supporter into an oppressor or reversing a relationship without acceptance is a finding citing source fact + screenplay line per `REV-03`).
- **Explicit `add` mappings (`STY-30`)**: every character, scene, or opponent absent from the source must be registered as its own `add` mapping with its function, why existing source material cannot carry it, checked source facts, and a brief line for the creator (hiding additions inside `change_carrier`/`merge`/`move_earlier` is a `craft_default` finding; manufacturing an opponent solely to hit `opposed_reversals_per_episode_min` is reported as a profile deviation instead).

## Scene, action, and dialogue (`SCR-01`–`SCR-24`)

- **Scene test**: conflict/pursuit scenes must establish agenda, opposing force, traceable leverage/cost/choice that breaks the prior strategy (an opponent merely falling silent or leaving without lost leverage fails), and an exit state pressuring the next scene. Quiet, atmospheric, ritual, montage, or consequence-processing scenes pass when they deliver a legible change in knowledge, relationship, pressure, rhythm, or state.
- **Action & production meaning (`SCR-16`, `SCR-17`)**:
  - Internal states use playable behavior, evidence, or tagged `[VO]`/`[OS]`; on-screen text (`[画面文字]`), prop text, `[音效]`, and `[转场]` are explicitly tagged; prose avoids camera/prompt boilerplate; redundant `[连续性]` tags repeating an already explicit exit action are flagged.
  - Central participants supplying leverage or cost remain strategically active through the turn rather than turning into passive props, and obstacles are not erased by newly invented resources/permissions or ungrounded outside rescue.
  - Foregrounded literal deadlines (`SCR-16`) must have a feasible action chain or legible compression/method change/failure (never upgrade qualitative urgency into invented timestamps).
  - Bounded attempt/turn/breath counts (`SCR-17`) must complete their required visible state inside each unit boundary.
- **Dialogue (`SCR-08`, `SCR-09`)**:
  - Lines respond to the prior move and alter the next with distinct character voices, without restating a just-performed action or explaining an already visible mechanism a second time.
  - Parentheticals contain only simultaneous delivery/tactic cues, leaving physical actions and prop changes to action lines (`SCR-08`).
  - Splitting a long speech requires an inserted action that changes tactic and provides a sourced cut point; speeches with no internal turn are shortened rather than split with a filler glance/pause (`SCR-09`).

## Rhythm profile (`REV-12`)

Active only when `short-drama.json#/creator_authority/rhythm_profile` has `status: "accepted"` (inactive when missing, `unset`, or `proposed`). Measure arithmetic against the current screenplay (using declared pacing or a labelled real-time read estimate) and report deviations as non-blocking `craft_default` findings citing field, accepted value, measured value, and location:

| Field | What the reviewer measures |
|---|---|
| `first_hook_seconds` | Seconds from episode start to the first crisis, conflict, anomaly, or spectacle already happening on screen. |
| `beat_interval_seconds_max` | Longest gap between consecutive emotional touchpoints (conflict line, situation-changing action, or new information). |
| `opposed_reversals_per_episode_min` | Reversals driven or suffered by a human opponent with an agenda (system/number/environment-only changes do not count). |
| `end_on_peak` | Whether the last beat sits on or just before the peak, with no afterglow, summary, or quiet coda after it. |
| `reprise_previous_last_beat` | Whether the opening replays the previous episode's last beat (not applicable to EP001). |
| `vo_share_max` | `[VO]` characters divided by all dialogue characters (whitespace and parentheticals removed, punctuation kept; `[OS]` in denominator only). |
| `first_major_payoff_by_episode` | Series review only: episode in which the first major payoff lands. |

Storyboard rhythm fields (`target_avg_shot_seconds`, `close_shot_share_min`) are checked in the [visual rubric](rubric-visual-motion.md#rhythm-profile-shots).

## Local passes (`REV-13`)

After the whole-episode read, run three isolated passes (with or without a rhythm profile):

1. **Opening hook**: read only the first segment (up to `first_hook_seconds` or the first scene) to verify whether the hook is already happening rather than being set up; then read the opening beat alone (`SCR-22`, and `STY-25` for EP001) to check whether the first still frame raises a question by itself without needing text read, character recognition, or the next line heard first.
2. **Ending suspense**: read only the closing beats of the final scene to verify the accepted ending function (`end_on_peak` or open/line/image hook growing out of this episode's landed result).
3. **Mid-episode reversal density**: read only the middle segment, listing each human-driven reversal and flagging dead stretches or end-bunched reversals.

## Replaceable realization (`SCR-10`)

Active **only** on beats explicitly marked by the creator (never flag unmarked beats or predict platform censorship):

- Dramatic function must state *who is proven or changed* (never a vague label like “高潮”);
- The fallback must deliver the same affected person, cost, downstream payoffs (`payoff_refs`), and next-episode entry state without requiring unestablished setups, concrete enough to film (never “酌情处理” or bare scene deletion without naming which existing beat absorbs the function);
- Flag any depiction weakened preemptively without a stated creator requirement.
