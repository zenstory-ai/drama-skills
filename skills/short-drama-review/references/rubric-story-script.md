# Story And Script Rubric

## 目录

- [Promise](#story-promise-and-engine)
- [Episode](#episode-shape)
- [Entry and serial memory](#entry-character-and-serial-memory)
- [Adaptation fidelity](#adaptation-fidelity)
- [Scene](#scene-test)
- [Action](#action-and-production-meaning)
- [Dialogue](#dialogue)
- [Rhythm profile](#rhythm-profile-rev-12)
- [Local passes](#local-passes-rev-13)
- [Findings](#common-findings)

## Story promise and engine

- Can the creator state protagonist, pursuit, costly opposition, and recurring
  audience payoff without relying on a genre label?
- Can the conflict produce varied pressure, or does every episode repeat the same
  misunderstanding, humiliation, rescue, or reveal?
- Does escalation change power, knowledge, relationship, exposure, cost, or time?
- Do setups/payoffs and episode handoffs resolve to explicit records?

## Episode shape

- What pressure is active at the opening?
- What does the protagonist want now, and what resists it?
- Which choice/action causes the directional turn?
- If the episode frames that turn as a consequential choice, what live value does each
  executable direction protect, and what cost is newly caused by the action (`SCR-13`)?
  If it is an ordinary decision or single-path pursuit, leave this test inactive rather
  than manufacturing a dilemma.
- Conditional does not mean cursory: when the episode itself foregrounds a choice,
  evidence carrier, deadline, or rule, does resistance, action, and consequence dramatize
  it, rather than merely naming it in dialogue?
- Could a viewer identify those stakes from the screenplay alone, without access to
  the upstream brief or episode card?
- Do explicit brief facts, must/forbid constraints, genre contract, and required exit state
  outrank craft defaults, or did the screenplay invent precision, records, resources,
  procedures, relationships, or mechanisms merely to display a rule?
- When a choice cost or deadline is essential, was it perceptible before the decision,
  or invented at decision time by a convenient new condition?
- What part of the promised experience is delivered before the outgoing hook?
- What exact state enters the next episode?
- Before the outgoing hook, what local dramatic result has already landed?
- Which behavior, relationship history, line, silence, spatial choice, or object makes the
  protagonist's private reason legible? Do not require a recurring object when another
  carrier already does the work.
- Does the ending fulfill the episode's viewing contract through consequence, relationship,
  irony, afterimage, atmosphere, or intentional openness? A new external event is optional.
- If the ending declares a path closed or a consequence irreversible, do later beats
  accidentally contradict that claim without presenting an intentional new change?
- Whose choice caused that result (`STY-13`)? If it arrived by outside force, cite the
  protagonist's earlier action that made it arrive now, and what they did with it.
  A protagonist who only endures until rescue is this episode's audience, not its lead.

A capacity estimate (`STY-16`) is informational, never a blocking finding. If a
planned episode's shot/duration magnitude is far from the project's own accepted
ratios, note it as an advisory observation with the sampled basis, and leave the
resolution to the creator. Do not derive a word, line, or shot quota from it. The only
numbers a review checks are the ones in an accepted rhythm profile
([below](#rhythm-profile-rev-12)), and never another project's numbers.

When the premise grants foreknowledge or externally authorized ability (`STY-17`), keep
two layers apart and cite each from its own place:

- **Contract layer** (creator-accepted, in the story engine): is the device contract
  accepted before the device first takes effect, recording scope, failure conditions,
  cost, and whether the device's own declarations are reliable?
- **Disclosure layer** (per episode, in the information-permission field): what do the
  characters and the audience know right now?

Never report partial disclosure as a defect. An audience that does not yet know every
boundary is the normal case, and late-discovered limits are often the intended suspense.
What is reportable:

- A later device ability or exemption that traces to no contract clause—cite the episode
  and the missing clause. This is retroactive widening whether or not it was announced
  in-fiction.
- A disclosed rule violated later, unless the contract marks the device as unreliable
  and the setup is traceable.
- Strip the device out—does the episode still contain a choice? If not, cite what
  resistance was removed and never replaced.
- What did the opposition learn once the device was in play?
- For foreknowledge: does the information degrade as the timeline diverges, or does the
  author keep inventing reasons to weaken the protagonist? Is the audience's permission
  level held constant across episodes?
- For authorized ability: is the cost visible and landed on something the protagonist
  cares about? Does the device offer options, or decide for them?
- If the device uses an on-screen readable carrier, is the `exact-readable` obligation
  stated instead of coexisting with a global no-text policy?

## Entry, character, and serial memory

- What prior-world fact does the writer need in order to predict present choices?
  Which visible evidence does the audience need now, and which backstory is
  correctly withheld?
- Why is this the useful entry window? Would an earlier start become setup work,
  or a later start remove a consequential choice?
- For each claimed character change, where are the pressure test, choice or
  retreat, local result, cost, and changed visible strategy (`STY-12`)?
- Do world truth, character beliefs, and audience knowledge remain separate?
- For each evidence carrier, what claim does it directly support, and which identity,
  cause, motive, or mechanism remains an unresolved inference (`STY-15`)?
- When a major belief change hinges on contested evidence, is the response limited to
  what was proved, or does the story intentionally preserve/delay uncertainty (`SCR-14`)?
  Leave this test inactive for uncontested facts, comic misunderstanding, subjective
  narration, or clues whose ambiguity is the intended effect.
- When contested evidence is a primary episode engine, does at least one visible state
  change alter which explanations remain live or alter the next action, rather than
  leaving every increment to verbal report? Photographing, bagging, numbering, or logging
  is not a dramatic turn by itself. Once the required inference changes, does testing stop
  unless another live counter-explanation would genuinely change the next action?
- If a proof claim depends on continuity such as connection, sealing, position, time, or
  lack of contact, did preceding action preserve that exact property? A continuity label
  may carry forward a shown state; it cannot prove that an unseen event or contact never occurred.
- Does active serial memory preserve character/relationship state, information
  permissions, setup debt, rhythm direction, and the exact physical handoff?
- Do external pressure and emotional load rise, fall, or diverge for a reason?
  A breathing scene should process a consequence rather than suspend the story.

Do not require a fixed hook type, beat count, reversal, climax timestamp, or
dialogue quota beyond what an accepted rhythm profile declares.

## Adaptation fidelity

Active only when the project adapts a source. Read the source span each mapping in
`项目开发/adaptation-map.jsonl` cites, then the episode record and screenplay.

- For each core source character: is their stance toward the protagonist, their way of
  acting, and their relationships the same on screen as in the source (`STY-07`)?
  Pressure made louder or spoken aloud is fine; a supportive figure turned oppressor,
  or a relationship reversed, is a finding unless the creator accepted the change.
  Cite the source fact and the conflicting screenplay line (`REV-03`).
- Does the main line still run the source's way, and does any invented detail
  contradict a source fact?
- Is every character, scene, or opponent the source lacks registered as its own `add`
  mapping, with the function it serves, why existing source material cannot carry it,
  the source facts checked against it, and a line in the brief for the creator (`STY-30`)?
  An addition hidden inside `change_carrier`, `merge`, or `move_earlier` notes is a
  `craft_default` finding; an unregistered addition that also contradicts the source
  is a `STY-07` finding.
- When an episode's opponent was manufactured to meet `opposed_reversals_per_episode_min`,
  say so: the profile deviation is the honest outcome, not a new antagonist.

## Scene test

For a scene organized around active pursuit or conflict, ask:

1. Why must it exist?
2. Whose agenda organizes it?
3. What force opposes that agenda?
4. What traceable fact, leverage change, cost, authority, or choice makes the prior
   strategy fail? An opponent merely becoming silent or leaving is not enough.
5. What exit state pressures the next scene?

A quiet scene can pass when pressure and change are legible. Atmospheric, ritual,
montage, transition, and consequence-processing scenes may instead justify their
function through a necessary change in knowledge, relationship, pressure, rhythm,
or production state; do not invent an opponent or strategy failure merely to make
them fit this checklist. A loud scene can fail when nothing changes.

## Action and production meaning

- Are internal states expressed through playable behavior, evidence, or deliberate
  VO/OS?
- Are actions spatially coherent and consequential?
- Are exact on-screen text, prop text, SFX, VO/OS, and transitions tagged?
- Does prose avoid camera/prompt boilerplate while retaining production-critical
  facts?
- Do supporting characters who receive substantial dramatic emphasis have a goal, judgment,
  or strategy of their own? Incidental, transactional, choral, and environmental roles need
  not all alter the main plot.
- Does a central participant who supplies the main leverage, opposition, or cost remain
  strategically present through the turn and response, rather than becoming a passive prop
  once the protagonist acts?
- If that participant's leverage disappears, what already-established action, spatial fact,
  authority, relationship, or choice made it disappear? Do not infer neutralization merely
  from the protagonist completing one step.
- When a literal precise deadline is foregrounded and audience-auditable, does its action
  chain fit, or does the screenplay make compression, changed method, changed objective,
  or failure legible (`SCR-16`)? Qualitative urgency must not be upgraded into invented
  minutes, timestamps, notifications, or records. Do not apply a real-time test to montage,
  ellipsis, subjective time, or declared stylization.
- When the brief defines a limited number of attempts, turns, breaths, beats, or other units,
  does each unit end with its required visible state (`SCR-17`)? Labels, counts, requests,
  authorization, preparation, and cleanup after the boundary do not substitute for completion;
  an intentional failure or partial result may count when it is legible at that boundary.
- When exact timestamps share one literal continuity, are they mutually consistent?
- When the current date is necessary to a conclusion, is it supported by a current source?
- Does a compressed process retain only the steps that change strategy, relationship,
  risk, or result, instead of listing interchangeable operations?
- When multiple carriers repeat one pressure or fact, does each add rhythm, viewpoint,
  irony, misdirection, or consequence? If not, which one is redundant?
- Does a solution use established resources and still confront the core obstacle, rather
  than erase it with a newly invented convenience?
- Even when a resource is established, does it change the problem without conveniently
  performing the character's hardest dramatic work for them?
- Does an outside response increase or transform pressure in a way grounded in the work's
  established world, rather than suddenly forgiving, rewarding, or rescuing the character
  to make the ending easy?
- After a mechanism becomes visually clear, does dialogue change the relationship or
  narrow the claim instead of explaining the same mechanism again?
- When the brief gives a target duration but the project has no pacing rates, has the
  writer still performed a real-time read/action pass and removed obviously excessive
  repeated verification, date exposition, or equivalent closing beats?

## Dialogue

- What does each speaker want from the other now?
- What is withheld, reframed, threatened, bargained, accused, or proven?
- Does the line respond to the prior move and alter the next?
- Are voices distinct by worldview, status, relationship, vocabulary, and rhythm?
- Does exposition enter through conflict/evidence/consequence rather than a
  neutral information dump?
- When a long speech is split, does the inserted action change the speaker's tactic
  and give downstream a sourced cut point, rather than pad with a glance or a pause
  (`SCR-09`)? When a long speech carries no internal turn, was it shortened instead
  of split?

Silence, interruption, slang, narration, and sentence length are creator options,
not universal scoring ratios.

## Rhythm profile (`REV-12`)

Active only when `short-drama.json#/creator_authority/rhythm_profile` has `status`
`accepted`. A missing, `unset`, or `proposed` profile means nothing here is checked.
The review does arithmetic on the accepted values against the current screenplay and
nothing else:

| Field | What the reviewer measures |
|---|---|
| `first_hook_seconds` | Seconds from the episode start to the first hook: crisis, conflict, anomaly, or promised spectacle already happening on screen. |
| `beat_interval_seconds_max` | The longest gap between consecutive emotional touchpoints: a conflict line, a situation-changing action, or new information. |
| `opposed_reversals_per_episode_min` | Reversals driven or suffered by a human opponent with an agenda; changes completed by a system, a number, or the environment alone do not count. |
| `end_on_peak` | Whether the last beat sits on or just before the peak, with no afterglow, summary, or quiet coda after it. |
| `reprise_previous_last_beat` | Whether the opening replays the previous episode's last beat. Not applicable to the first episode. |
| `vo_share_max` | `[VO]` spoken characters as a share of all spoken characters; `$short-drama-write`'s duration estimate reports it when run with the project file. |
| `first_major_payoff_by_episode` | Series review only: the episode in which the first major payoff lands. |

Seconds come from the project's declared pacing, or from a real-time read-through
labelled as a text estimate; state which. A deviation is a `craft_default` finding that
cites the field, the accepted value, the measured value, and the location. Severity
follows audience impact and is never `blocker`; the creator may keep the episode with a
stated reason. Storyboard fields (`target_avg_shot_seconds`, `close_shot_share_min`)
are measured in the [visual rubric](rubric-visual-motion.md#rhythm-profile-shots).

## Local passes (`REV-13`)

After the whole-episode read, run three passes that each read one part only. A whole
read lets a strong middle excuse a flat opening; a part read cannot.

1. **Opening hook**: read only the first segment, up to `first_hook_seconds` or, with
   no accepted profile, the first scene. Would a viewer who saw only this stay? Name
   the hook and say whether it is happening or only being set up. Then read the first
   beat alone, the image of the first three seconds: does it raise a question by itself,
   or does it need on-screen text read, a character recognized, or the next line heard
   first (`SCR-22`)? A still image that poses its own question passes. For a first
   episode, also check that the brief compared the entry candidates on that same image
   (`STY-25`).
2. **Ending suspense**: read only the last segment, the final scene's closing beats.
   What question is left open? Does it grow out of this episode's result? Is it a line
   hook (an unfinished question, an identity hint) or an image hook (a door half open,
   an envelope half torn)? Does it stop before the answer?
3. **Mid-episode reversal density**: read only the middle. List each reversal with its
   location and the person driving or suffering it; flag long stretches with no
   touchpoint and reversals bunched at the end.

Each finding cites its own segment. The passes apply with or without a profile; only
the numeric comparisons need one.

## Replaceable realization (`SCR-10`)

Only for beats the creator marked. **An unmarked beat leaves this section
inactive**: do not raise a finding for the absence of a mark, do not guess which
beats need one, and never rate a depiction against a standard this suite does not
carry — it carries none, and predicts no outcome.

On a marked beat:

- Is the dramatic function written as *who is proven or changed*, rather than an
  emotion word? A function stated as "高潮" cannot be used to judge equivalence.
- Does the fallback deliver that same function — same person affected, cost still
  paid, `payoff_refs` and the next episode's entry state still satisfied?
- Does the fallback need a setup the script has not established? Then it is a
  rewrite, not a fallback.
- Is "delete the scene" being offered as the fallback? Deletion removes the
  function itself; the only acceptable variant is an explicit handover naming
  which existing beat now carries it and what that beat must absorb.
- Is the fallback concrete enough to become scene action, or is it "酌情处理"?

Report pre-emptive sanding as a finding in its own right when the current
depiction was already weakened to avoid a risk nobody stated: the loss is certain,
the benefit is not, and the mark exists precisely so the strong version can stay.

## Common findings

- genre label substituted for a dramatic promise;
- alternatives differ only in wording;
- coincidence carries a major turn with no prepared cause;
- scene repeats known information and leaves state unchanged;
- cliffhanger withholds all payoff;
- episode pauses an unfinished action without producing a local result (`STY-13`);
- first episode dumps the backstory reservoir instead of selecting an active entry;
- an adaptation hardens a source character or invents an opponent without an `add` mapping or creator acceptance;
- a declared character arc has no pressure test, choice, cost, or changed strategy;
- serial summary omits an information permission or unpaid setup obligation;
- generic emotion adjectives replace visible performance;
- every character explains the plot in the same voice;
- downstream production requirement was never marked in screenplay truth.
- a redundant `[连续性]` tag repeats an exit state already explicit in the final action;
- a story-critical ending state appears without a prior transition;
- the script uses atmosphere, silence, or a black frame to avoid landing a result the episode
  promised, rather than as an intentional ending form;
- a beat is sold as a consequential choice after one direction has already become valueless
  or impossible (`SCR-13`);
- contested evidence produces a broader conclusion than the evidence or intentionally
  incomplete verification supports (`SCR-14`);
- a claimed proof relies on a continuity property the preceding action already destroyed,
  or on a continuity label asserting an unseen negative event;
- a local payoff erases its established residue or replaces meaning with a slogan (`SCR-15`);
- a cost framed as central pressure automatically resets at success, leaving no material
  effect on ability, body, resource, relationship, or next action;
- a central participant supplies the opening leverage or cost but becomes a passive prop
  through the decisive action;
- the core opposing force disappears only because its holder becomes silent, stops acting,
  or leaves, without a traceable loss of leverage, accepted cost, or changed strategy;
- a literal, audience-auditable deadline succeeds only through unexplained speed, or
  qualitative urgency is upgraded into invented precise timing (`SCR-16`);
- a limited unit is counted before its required state completes, with the completion moved
  outside the boundary (`SCR-17`);
- a newly invented resource, permission, or ability removes the central obstacle;
- a limited result is renamed as a broader success or truth than the scene demonstrated;
- repeated carriers restate one pressure without adding viewpoint, rhythm, irony, or consequence;
- a second same-direction decision, closing line, or maxim merely translates a change,
  punchline, or metaphor that the preceding action already completed;
- post-result action unintentionally contradicts a consequence the screenplay called irreversible.
