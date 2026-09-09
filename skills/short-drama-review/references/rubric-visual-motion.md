# Storyboard, Keyframe, And Motion Rubric

## 目录

- [Coverage](#coverage-and-meaning)
- [Shot](#shot-purpose-and-geography)
- [Keyframe](#frozen-keyframe)
- [Motion](#motion)
- [Continuity](#cross-shot-continuity)
- [Findings](#common-findings)
- [Production risks and authorized observations](#production-risk-and-authorized-observation-checklist-rev-08)

## Coverage and meaning

- Does every production-relevant block have a disposition?
- Are omissions/repeats explained?
- Does each shot preserve the source action, dialogue, information, and reaction?
- Has downstream work invented or deleted a story fact?

## Shot purpose and geography

- For a high-value scene with an accepted coverage audition: did the approaches
  genuinely differ — in knowledge timing, audience alignment, performance space,
  strongest image, landing, losses, or production fit?
- Does the formal plan bind the approach the creator selected, rather than the first draft?
- When a scene visual plan was used: do its start/end audience positions, spatial
  pressure, camera rhythm, reaction landing, and sound movement carry **one** dramatic turn?
- Does that plan stay clear of owning shot boundaries? (Ordinary scenes need no plan
  merely to satisfy a form.)
- What changes for audience or character by the shot end?
- Why is this a new shot?
- Do framing and camera behavior serve attention, alignment, pressure, reveal, or
  rhythm rather than decorate the prose?
- Are Location/View, axis, screen direction, eyelines, entrances, positions,
  hands, and props coherent?
- Are exact asset variants bound?
- Does the shot expose every fact it must carry while protecting
  facts the source withholds until a later action or cut?
- Do crop, occlusion, focus, back view, and offscreen space serve that information
  permission rather than accidentally reveal or conceal it?

## Frozen keyframe

- Can all described facts exist in one still instant?
- Does it project the start state written for this shot?
- Are focal hierarchy, composition, camera/lens, geography, pose/gaze/hands/prop,
  expression, and light legible?
- Does it avoid ordered actions, performance arcs, camera moves, or transforming
  environments?
- Read the finished keyframe text, not the shot's intent: is every visible character,
  place, and prop whose identity, Look, or geography must stay recognizable listed in
  this shot's `视觉依据` (`SHT-22`)? A second body that entered the composition while the
  frame was being written is the usual miss.
- Does each declared 控制 scope stay inside what this frame can carry, and is nothing
  bound merely because it was bound in the previous shot (`SHT-24`)?
- When real reference images are bound, does every `REF-...` slot declare a 用途, so the
  shot says which start frame and which identity/geography/prop pictures it sends
  (`SHT-25`, `VID-24`)?
- Is anything the frames need kept consistent across shots — a carried prop, a garment —
  absent from `视觉设定.md` entirely, so it can appear in no shot's basis at all? The
  mechanical check cannot see this: an entry that does not exist cannot be reported missing.

## Motion

- Does it start from the accepted frame/boundary?
- Are subject actions ordered and small enough to preserve intended performance?
- Does performance change express the story move rather than stack synonyms?
- In multi-character motion: do the actors who actually change have distinct,
  readable triggers, choices, leaks, or landings — as this shot needs, not one
  identical arc per actor?
- Is attention handed off only where it truly transfers, rather than for
  synchronized reaction?
- Does any text-readiness claim cite the current creator-visible inputs and a real blocking gap?
- Does it avoid any claim about generated media quality or create a second readiness truth?
- Is camera behavior coherent and motivated?
- Are environment motion, dialogue, SFX, and audio included only when relevant?
- Does the described end match the storyboard's written end state without rewriting the next shot?
- When a reference frame carries appearance/composition, does motion prose avoid
  dumping the full visual 设定集?
- Does every claim about text-bearing reference pixels cite a creator/reference-owner
  description or an authorized input-reference observation? Without that evidence,
  is admission still `unverified` instead of pretending a negative prompt solved it?
- For any selective transform, are the accepted trigger, exact target scope,
  end geometry/state, and preserve set explicit? Do non-target people, props,
  text surfaces, and spatial anchors keep their required position, count, and state?
- Does each media reference state its exact purpose, what may be copied, and what
  must not be copied, rather than treating all visible pixels as authority?

For a copyable body, ask these separately — they are the two rules a rewrite regresses on
most often, because a body that reads "complete" can still carry both defects. Findings here
are about whether the body states this shot's sound and text truthfully and completely; only
the music-layer item below has a measured generation consequence behind it:

- Does the body carry only what will be filmed (`VID-22`)? Negative action intent must
  already be rewritten as a visible positive state. The one permitted negation is the
  no-subtitle/caption/dialogue-overlay declaration; a second exclusion clause is a defect,
  not extra safety. (The often-repeated reason — that a noun inside a negation gets
  rendered — did not reproduce in this suite's probes, so cite the body's own clarity,
  not that mechanism, when you raise this.)
- When the target model generates audio in the same pass (`VID-23`), is the sound written
  as a closed positive event set — what the track consists of, and across what span —
  rather than a list of what must not be heard? Check three failures by name:
  - an exclusion clause (`No dialogue`, `无对白`, `no music`) standing in for a positive
    soundscape, so the body never says what this shot sounds like;
  - a completeness declaration that enumerates a layer this shot does not have. "The audio
    timeline is complete after the listed ambience, effects and timed dialogue" on a shot
    with no lines states something untrue of this shot. Read the declaration against the
    shot's actual layers, not against a template;
  - a shot that leaves the non-diegetic music layer unstated. This is the one sound defect
    with measured consequences: bodies that omitted the layer came back with an invented
    score. **The dialect's empty form satisfies this** — for H3 that is the literal line
    `non_diegetic_music: N/A`, which is a correct statement of "no non-diegetic music",
    not a placeholder. Raise this only when the layer is missing from the body altogether;
    never ask an owner to delete a present empty form;
  - a shot with no lines whose body never says what the track *is* for the full duration,
    and never gives the on-screen performers a visible non-speaking state.
  Report a contradictory pair — an exclusion clause plus a declaration that enumerates the
  excluded layer — as one finding against the body's sound contract, and quote both
  sentences. Raise it as an internally inconsistent sound contract, which it is; do not
  assert that it makes the model invent lines, which this suite has probed and not seen.

These two apply to a body the review itself is about to ask an owner to rewrite. A revision
request that removes a defect by adding `no ...` has moved the defect, not fixed it.

For a pickup or alternate, ask these separately:

- Does the pickup/alternate name its master by visible `MOTION-...` heading?
- Is every source obligation assigned to the master, this version, another named version or a requested storyboard revision?
- Are the changed items and the items that must remain unchanged explicit?
- Is replacement only requested here? The review Markdown decides whether the master remains primary or the alternate replaces it.

For music, ask these separately (`VID-14`):

- Is intent written as a relative entry/exit/duck against neighbouring shots,
  rather than an independent cue per shot?
- Do adjacent annotations actually join?
- Does the text ask for a per-shot music bed against an accepted timeline-layer plan?
- Whether a rendered clip carries a baked-in track is **not decidable here**. Cite it
  only from an authorized text observation record; otherwise keep it `unverified`
  and never infer a mix result from prose.

Explicit timing that does not sum exactly to its shot's accepted duration—over or
under—is a structural error. Untimed overload is a
reviewed feasibility question: cite which action/performance/story beat would be
lost, not a universal verbs-per-second formula.

Container arithmetic is a separate structural check (`VID-13`). Count the accepted
shots a delivery container carries, then confirm its duration equals the sum of
their accepted durations. For a multi-shot container, confirm the members are
contiguous in source order, share one geography/asset binding chain, do not cross a
scene boundary, and each remains independently reviewable. A space or subject jump
belongs on a member boundary; the same jump inside a member's timed segment is a
hidden cut. Report an arithmetic mismatch and a hidden cut as two findings, not one.

- Is the axis recorded as two named anchors, a stated working side, and a per-character
  screen position — rather than a placeholder?
- In a shot-reverse-shot pair, are the two screen directions complementary?
- Bare left/right always means **screen** left/right. Where a subject's own side is
  meant, does the text name the subject?

## Cross-shot continuity

Trace Look, injury, dirt/wetness, emotion/knowledge, position/facing/gaze, hands,
held prop, prop owner/state, location/time/weather/light, axis, and screen
direction. Distinguish unexplained contradiction from declared montage,
ellipsis, dream, or deliberate disorientation.

## Common findings

- beautiful shot with no dramatic purpose;
- dialogue covered but consequential reaction absent;
- anonymous asset or wrong variant;
- cross-location/time action hidden in one ordinary shot;
- keyframe contains “first/then/finally”;
- locked camera also pans or pushes in the same interval;
- motion invents a grab, injury, transfer, relationship change, or line;
- a selective transform removes, copies, or reshapes a non-target person, prop,
  text surface, or spatial anchor because its preserve set was unspecified;
- end pose/prop state disagrees with next start;
- every emotional beat uses the same close-up/push template;
- provider batching is mistaken for editorial shot structure.
- a narrowed pickup silently replaces the master and drops dialogue, reaction,
  reveal, end-state, or creator-directive obligations.

## Production-risk and authorized-observation checklist (REV-08)

审查范围包含生产结果或全集时，使用当前可用的只读工具实际查看媒体：核对绑定参考与结果版本，抽取
有代表性的中间帧，并检查镜头边界前后、动作过渡和状态端点；声轨只有在实际播放或分析后才可判断。
记录文件、版本、时间点、方法和覆盖限制。媒体或某个维度无法读取时，该维度保持 `PROVISIONAL`；
prompt/spec 本身已能直接证明的矛盾仍按文字证据判 `REVISE`。不得从任务成功、结果地址或提示词存在
推断成片质量。

需要项目校准时，先区分输入参考与生成结果。创作者提供的观察和 reviewer 使用可用工具直接形成的观察
须绑定结果文件/版本、观察方法和限制；对应提示词/镜头标题、参考顺序、制作形态/配置缺失时标未知，
仍可报告直接看见的缺陷，但不能断言缺陷由未知请求造成。finding 给出最小修改项与保持项，
结论只在该项目和版本条件下有效。旧版本的观察或“重试已
修复”文字不能替未观察的新结果通过审查。

短剧生产中需要防范的文字风险或有界媒体观察包括：

- on-screen text or subtitle residue despite a declared no-text constraint;
- a text-bearing reference admitted under no-text or exact-readable policy
  without an allowed surface or a crop, clean, mask, or replace decision;
- background music implied where the audio boundary allows sound effects only;
- wardrobe or look drift against the bound reference (re-describing clothes the
  reference already fixes invites drift — flag redundant appearance prose);
- 180° axis violation or eyeline mismatch across consecutive shots without a
  declared transition;
- lip-sync mismatch: dialogue bound to the wrong character, inner monologue
  written as mouthed speech, or extra lines the source dialogue never contained;
- explicit segment timings that do not sum exactly to the shot duration, in either direction;
- emotion-intensity mismatch between stated level and described performance
  (a declared 9/10 rage performed as mild irritation, or the reverse).
