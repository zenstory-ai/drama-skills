# Storyboard, Keyframe, And Motion Rubric

## Coverage, shot purpose, and geography (`SHT-01`–`SHT-31`)

- **Coverage & meaning**: every production-relevant action, line, sound, and `[画面文字]` in `剧本.md` traces to a shot or an explicit omission reason without inventing or deleting story facts.
- **Audition & scene plan**: when a coverage audition was used, approaches must differ in knowledge timing, alignment, performance space, or landing, and `分镜.md` must implement the selected option. When a scene visual plan was used, its start/end audience positions, spatial pressure, camera rhythm, reaction landing, and sound movement carry one dramatic turn without taking over individual shot boundaries.
- **Shot purpose, `运镜` & geography (`SHT-04`)**:
  - Each shot changes audience/character state and protects information permissions (crop, occlusion, back view, and offscreen space neither leak withheld facts early nor hide required evidence/reaction).
  - Every shot's `运镜` line states a behavior and a reason tied to the shot's purpose (`SHT-04`; fail on missing `运镜`, bare `运镜：固定` with no reason, or an episode locked on nearly every shot including its peak).
  - Axis is recorded as two named anchors, a working side, and per-character screen positions; shot-reverse-shot directions are complementary; bare left/right means screen left/right (subject-relative sides must name the subject).
- **Cross-shot continuity**: trace Look, injury, dirt/wetness, emotion/knowledge, position/facing/gaze, hands, held prop, prop owner/state, location/time/weather/light, axis, and screen direction across cuts (distinguishing contradiction from declared montage/ellipsis/dream).

## Rhythm profile: shots

Under the `REV-12` conditions in the [story rubric](rubric-story-script.md#rhythm-profile-rev-12), measure two storyboard fields: average shot length per scene (scene duration ÷ shot count) against `target_avg_shot_seconds`, and the episode share of close-range shots (近景、特写、大特写、细节镜头 ÷ total shots) against `close_shot_share_min`. Also flag shot durations derived from screenplay word counts instead of the scene's sound timeline (`SHT-28`).

## Frozen keyframe (`SHT-17`, `SHT-22`, `SHT-24`, `SHT-25`)

- **Single still instant**: projects the shot's start state (or end state for an optional closing keyframe per `SHT-17`) with legible focal hierarchy, composition, camera/lens, geography, pose/gaze/hands/prop, expression, and light; fail if it contains ordered actions (“first/then/finally”), performance arcs, camera moves, or transforming environments.
- **Visual basis & reference scope**:
  - Every visible character, place, and prop in the finished keyframe text whose identity, Look, or geography must stay recognizable is listed in `视觉依据` (`SHT-22`), and any cross-shot recurring prop/garment missing from `视觉设定.md` altogether is flagged.
  - Each `控制` scope stays within what this frame carries and is not copied over from the previous shot out of habit (`SHT-24`).
  - Every real reference image (`REF-...`) declares a valid `用途` (`SHT-25`, `VID-24`).

## Motion and production-risk checks (`VID-01`–`VID-28`, `REV-08`)

- **Action, performance & end boundary**: starts from the accepted frame/boundary; ordered actions fit within the accepted duration (explicit segment timings not summing to shot duration fail structurally; untimed overload fails when a beat/reaction is crowded out); multi-character shots give distinct triggers/choices/leaks/landings only to actors who change and record real `attention_handoffs[]`; end state matches the storyboard's written end state without inventing grabs, injuries, transfers, or lines.
- **Sound, music & container rules (`VID-13`, `VID-14`, `VID-22`, `VID-23`)**:
  - Copyable body actions and sound match the source and account for intended ambience or silence (`VID-22`, `VID-23`; H3 `non_diegetic_music: N/A` is valid).
  - Music intent is written as relative entry/exit/duck against adjacent shots rather than an independent per-shot music bed (`VID-14`; never infer whether a rendered clip has baked-in music without an authorized observation record).
  - Delivery container duration equals the sum of its accepted member shot durations (`VID-13`), members are contiguous in source order within one scene and binding chain, and any space/subject jump inside a member's timed segment is reported as a hidden cut separate from arithmetic mismatch.
- **Text-risk and authorized-observation checklist (`REV-08`)**: flag as text risks (or as observed defects when backed by an authorized observation record; see [项目校准](project-calibration.md)):
  - On-screen text/subtitle residue under `no-text`, or a text-bearing reference admitted without an allowed surface or crop/clean/mask/replace decision;
  - Redundant prose re-describing clothes/appearance already fixed by a bound reference (inviting wardrobe drift);
  - Contradictory camera flags in the same interval (e.g. locked camera + pan/push), 180° axis breaks, lip-sync/VO-mouthing mismatches, or emotion-intensity mismatch between stated level and described performance.
