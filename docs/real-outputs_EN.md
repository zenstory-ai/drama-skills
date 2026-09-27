# See what it produces: excerpts of real output

[中文](real-outputs.md)

This is the full version of the README section "See what it produces". Every excerpt below is taken from a file in this repository or from one real run, and each subsection names its
origin first. The documents are Chinese and are translated here where marked. Excerpts keep only the fields under
discussion: cuts inside a line are marked with "…", omitted whole paragraphs with a "…" line of their own, and
omitted field lines are not marked.

## One shot through four documents: the storyboard traces back to the script, the look stays locked

Origin: the [public sample `examples/creator-first/EP001`](../examples/creator-first/EP001/), arranged by hand to the
current document contract; it passes `creator_markdown_check.py`. The same shot,
`SHOT-EP001-002`, is owned one layer at a time. The script only says what happens (translated):

```markdown
Across the desk, Zhou Bosen pushes a stack of papers over the thick glass top. A corner touches Jiang Chen's fingertip.
…
Zhou Bosen lifts the chipped enamel mug, takes a sip of cold tea, and frowns harder.
…
He puts the mug back into that old tea ring.
```

`视觉设定.md` writes the visible facts that must hold across shots as entries, and gives the look a
**continuity lock** whose lock phrase can be pasted into a prompt unchanged (translated):

```markdown
## Character · Jiang Chen
- Identity anchors: long face, high brow ridge, deep-set eyes, crew cut, straight shoulders. Not an idol fringe, not loose streetwear.
- Screen name: Jiangchen
- Continuity lock: LOCK-JIANGCHEN-DRESS "Jiang Chen's olive-green stand-collar service dress" (shots: SHOT-EP001-002, SHOT-EP001-003, SHOT-EP001-007;
  image prompt entry: IMG-JIANGCHEN-SHEET) · lock phrase: olive-green stand-collar service dress
```

`分镜.md` writes this shot's start and end; the frozen keyframe draws the start frame alone. Once the keyframe is
written, the shot lists which entries in that frame must keep identity, look or geography as its **visual basis**,
and the lock phrase appears verbatim in the keyframe body (translated; the prompt is quoted as written):

```markdown
## SHOT-EP001-002 · Handing him the blank
- Source: EP001-SC001
- Duration: 8s
- Start: the papers are under Zhou Bosen's hand; the mug rests beside the old tea ring.
- End: the corner of the papers touches Jiang Chen's fingertip; Zhou Bosen says "basically still blank".
- Input references: none (the creator explicitly chose text-to-video).
- Visual basis: 视觉设定.md · character "Jiang Chen" (controls: identity, build, this episode's look); character "Zhou Bosen" (controls: identity, build, this episode's look);
  location "Deputy regiment commander's office" (controls: glass desktop, old tea ring, file-box shelves, left window light); prop "Chipped enamel mug" (controls: chipped right handle, dark-grey iron body).

### Frozen keyframe prompt
> 9:16 vertical two-person medium shot inside an old regiment office, Zhoubosen, a broad square-faced middle-aged officer on
> frame right rests one hand on a stack of papers …, Jiangchen, a lean young man in olive-green stand-collar service dress,
> seen three-quarter from behind on frame left …; chipped white enamel mug beside an old tea ring, … no text, no logo.
```

`视频提示词.md` compresses appearance into one "static visual anchor" sentence (lock phrase included) and spends the
rest on the actions a model can execute between start and end, plus an end state you can verify (translated; the
prompt is quoted as written):

```markdown
## MOTION-EP001-002 · Handing him the blank
- Storyboard: SHOT-EP001-002
- Duration: 8s
- Generation mode: text-to-video
- Static visual anchor: A broad square-faced middle-aged East Asian officer sits frame right and a lean young East Asian man in
  olive-green stand-collar service dress sits frame left across a glass-covered desk in an old office lit from the left.
- Start frame: Zhou Bosen's right hand holds the papers down; Jiang Chen's hand rests at the desk edge.
- End: the papers touch Jiang Chen's fingertip; Zhou Bosen returns the mug to the old tea ring.

### Copyable prompt
> A broad square-faced middle-aged East Asian officer sits frame right and a lean young East Asian man in olive-green
> stand-collar service dress sits frame left across a glass-covered desk in an old office lit from the left. The middle-aged
> officer pushes the paper stack about twenty centimeters across the glass desk while speaking calmly. The young man does not
> reach for it until the paper touches his fingertip. The officer then lifts the chipped white enamel mug for one small sip,
> frowns at the cold tea, and returns it exactly to the old tea ring. Keep both seated positions, uniforms, file-box wall and
> left-window light stable. Locked camera, restrained natural performance, no object duplication.
```

The four originals: [`剧本.md`](../examples/creator-first/EP001/剧本.md) ·
[`视觉设定.md`](../examples/creator-first/EP001/视觉设定.md) ·
[`分镜.md`](../examples/creator-first/EP001/分镜.md) ·
[`视频提示词.md`](../examples/creator-first/EP001/视频提示词.md). The three mechanisms are explained in
[Cross-shot consistency](character-consistency-across-shots.md) (Chinese).

## What the checker catches: break the sample in two places on purpose

Origin: the same public sample as the previous subsection. `creator_markdown_check.py` validates the executable
contract between the five documents of one episode. It passes on the sample as shipped. Remove Zhou Bosen from SHOT-002's visual basis and change MOTION-003's
duration from 5s to 4s, and it reports the cause, not "validation failed":

```text
$ python3 skills/short-drama/scripts/creator_markdown_check.py examples/creator-first/EP001 --project-root examples/creator-first
OK: examples/creator-first/EP001

$ python3 skills/short-drama/scripts/creator_markdown_check.py <broken copy>/EP001 --project-root <broken copy>
ERROR: SHOT-EP001-002: 冻结关键帧提示词写到人物「周薄森」，视觉依据没有覆盖；本镜确实看不见时在视觉依据末尾加「；画外：人物「周薄森」」，正文里这个名字不可靠时在《视觉设定.md》写「画面代称：无」
ERROR: SHOT-EP001-003: 分镜时长 5 秒与视频提示词 4 秒不一致；视频提示词只能原样照抄已接受的镜头时长
```

The first line says: the frozen keyframe names the character "Zhou Bosen" but the visual basis does not cover him;
if he is genuinely not visible, append "off-screen: character Zhou Bosen" to the visual basis, and if the name in the
prompt body is unreliable, set his screen name to "none" in `视觉设定.md`. The second: the storyboard says 5 seconds and the
video prompt says 4; a video prompt may only copy the accepted shot duration.

It also checks that every shot's "source" starts with a scene ID that really exists in `剧本.md` and that any character,
location, prop or look named in the source quotation is covered by the visual basis or declared off-screen; that every
scene in the script is carried by a shot or listed as deliberately unfilmed; that dialogue quoted inside the video
prompt's copyable body can be found, punctuation aside, in `剧本.md`, `视觉设定.md` or `分镜.md`; and that every `REF-*`
points at an image that really is in the project with a stated purpose.

## Estimate dialogue before fixing shot length; cut on measured timings

Origin: a run made at v0.6.6, the one that produced the sample film at the top. At the storyboard stage each line of dialogue is
timed into the shot length, with the estimate written into the shot's "sound" line; the shot is generated at 7 s to
leave a settle margin, and the target length in the cut is written separately (translated):

```markdown
## SHOT-EP001-017 · Gentlemen, hear the dragon roar
- Source: EP001-SC003 「江晨（对着空剪辑室）：诸君，且听龙吟。」 (Jiang Chen, to the empty edit room: "Gentlemen, hear the dragon roar.")
- Duration: 7s
- Target length in cut: 6.5s. … seconds 6.5–7 are the settle margin; editing trims that 0.5 s from the end.
- Sound: Jiang Chen, 1 line, 6 voiced characters, ≈1.5 s at 4.1 characters/s (text estimate: he normally speaks fast with crisp
  endings; this line is half a step slower, with a gap between characters). Layout of the 7 s: finish reading the result on
  screen 1.4 s + slow exhale and shoulders dropping 1.5 s + eyes lifting 0.7 s + the line 1.5 s + pull-back to the settle and one
  beat 1.4 s (the 6.5 s cut target ends here) + hold 0.5 s, trimmed in the cut. …
- Input references: PLAN-SHOT-START (order: 1) · SHOT-EP001-017 "this shot's frozen keyframe" (purpose: start frame; controls: opening composition …);
  PLAN-JC-LOOK-C (order: 2) · IMG-JIANGCHEN-LOOK-C "Jiang Chen, dried-mud dawn fatigues state board" (purpose: look state; …); …
```

This shot was written as an image-to-video prompt for MiniMax H3. The continuity lock on Jiang Chen's fatigues in
`视觉设定.md`, "lock phrase: olive drab field fatigue uniform with blank collar tabs", appears verbatim inside
`subject_definitions`, and the line is given character by character inside `<d>` only (translated; the prompt is
quoted as written):

```markdown
## MOTION-EP001-017 · Gentlemen, hear the dragon roar
- Generation mode: image-to-video

### Copyable prompt
> subject_definitions: <Subject 1> is Jiang Chen, the young man in <Picture 2>: … he wears a full olive drab field fatigue
> uniform with blank collar tabs with two buttons undone and the collar turned out … <Picture 1> is the opening composition of this shot.
> …
> detailed_description: [Shot 1] … From about 3.6 seconds he speaks, half a step slower than his usual pace with a small gap
> between characters, the line addressed to a room with nobody in it: <Subject 1> (S2) <d>[Chinese] 诸君，且听龙吟。</d> …
> …
> non_diegetic_music: N/A
```

Once the clips exist, `剪辑单.md` states what happens on screen at every cut, takes subtitles verbatim from the
script, and gets its timings from measuring the source clip (translated):

```markdown
# EP001 cut list
- Target length: 25.00 s
- Aspect and frame rate: 9:16 · 768×1344 · 24fps
- Delivery loudness: -16 LUFS
- Unused shots: MOTION-EP001-001 to MOTION-EP001-009 (reason: no file — only SC003 was produced this time); …

## CUT-EP001-003 · All in on Doushou
- Source: MOTION-EP001-012 · 制作成果/video/MOTION-EP001-012.mp4
- In: 1.20
- Out: 4.20
- Duration: 3.00
- Choice: in = 0.84 s ahead of the measured voiced span (2.04–3.20 s in the source), hand already on the mouse; out = 1.00 s after
  the line ends, the submit button already highlighted
- Subtitle: 全押抖手 ("All in on Doushou", verbatim from the script)

## CUT-EP001-008 · Gentlemen, hear the dragon roar
- Source: MOTION-EP001-017 · 制作成果/video/MOTION-EP001-017.mp4
- In: 2.00
- Out: 7.00
- Duration: 5.00
- Choice: in = the first 1.5 s of staring repeats the wind-up before publishing in the previous cut, dropped entirely, enter on the lean
  forward; out = the measured end of the line is at 6.82 s in the source, hold to 7.00 s, the settle back into the chair is complete
  (clip length 7.29 s, only 0.29 s of margin)
- Subtitle: 诸君，且听龙吟 ("Gentlemen, hear the dragon roar", verbatim from the script)
```

`edit_tool.py check` verifies that intervals add up, that no clip is newer than the cut list, and that every subtitle
can be found verbatim in the script; `verify` only reports measurements. That run's RUN-LOG records that the first
person these two checks caught was the author: a subtitle window estimated from a transcript fell outside its
interval and `check` stopped it; the aspect was written as 1080×1920 while the clips were 768×1344, and `verify`
stopped that. The same log keeps two measurement results: a single `loudnorm` pass landed at -12.33 LUFS, 3.7 dB off
target, and only a second pass reached -15.79; speech transcription heard "诸君，且听龙吟" as "朱军且听龙银", which
is why transcription only locates time and subtitles are never taken from it.

The originals of this run — the
[cut list](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%89%AA%E8%BE%91%E5%8D%95.md),
the [21-shot storyboard](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%88%86%E9%95%9C.md)
and the [RUN-LOG](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/RUN-LOG.md) —
sit in commit `004d945` together with the eight clips and the film; by repository rule they are no longer kept in
the current tree. They were written to the v0.6.6 rules; the current checkers report two more things on them (the
13 unused shot IDs must be listed one by one; the launcher named in SHOT-018's source quotation must either be covered
by its visual basis or declared off-screen), and the FAQ entry [What do I do after upgrading?](../README_EN.md#what-do-i-do-after-upgrading) says how.

## The source triage is compared against its own full pass

Origin: `evaluations/让你管账号/reference-run` (the v0.4.2 run). `$short-drama-novel-analyze` first triages an
evenly sampled 12 of 20 chapters, then extracts all 20; when the full pass is done it goes back over the triage line
by line and says which calls were overturned (4 of the table's 7 rows, translated):

| S1 triage call | Full result | Verdict |
|---|---|---|
| Framework is a levelling-up story with a weak revenge thread | Holds. Two task loops; the rival thread in chapters 13–17 does not drive the main line | **Not overturned** |
| About 67% `screen_ready` | 19 of the 24 candidate episodes are `screen_ready` (79%), 5 `needs_carrier`, 0 `prose_only` | **Overturned (too conservative)**. See below |
| Chapter 13 is `prose_only` | Does not hold on the full pass. The chapter's function (the rival's entrance and accusation) can be carried entirely by one person at an edit desk; the triage mistook "walls of online comments" for the function itself, when that was only the source's carrier | **Overturned** |
| 22–26 episodes | 24 were cut | **Not overturned** |

> **The two overturned calls share one cause**: at the sampling stage it is easy to mistake "what the source is
> written with" for "whether this function can be filmed". Chapter 13 is wall-to-wall online comments and looks
> unfilmable, but the function it carries is the rival's entrance, which is entirely visible action. The next book's
> triage should ask about function first, then about carrier.

(The operator of this run had read the whole book before the triage; the declaration at the top of `triage.md` says
the comparison is therefore optimistic: it demonstrates the backfill mechanism, not the accuracy of the sampling itself.)
Every episode candidate carries `source_ref` / `chapter_range` back into the index, and
`creator_acceptance` is always `pending` — the analysis skill does not approve its own output.
Originals: [`triage.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/triage.md) ·
[`adaptation-value.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/adaptation-value.md) ·
[`episode-candidates.jsonl`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/episode-candidates.jsonl)

## The adaptation contract: every source fact names the episode and the frame that pays it

Same origin. `$short-drama-develop` lists the source facts that may not change, and each one has to answer "which
frame does the audience get it from"; if it cannot, it is explicitly deferred to a numbered episode (3 of the
table's 9 rows, translated):

| ID | Fact | Paid this round |
|---|---|---|
| F-W2 | **New media in this world is behind across the board**: not just the military, creators with over ten thousand followers are rare in any field | **Paid in EP001**. Visible carrier: he scrolls to the platform's industry chart, and the top creator's follower count has four digits. The audience compares that with the scale of his previous life and draws the conclusion themselves |
| F-C5 | He knows nothing about music; in his previous life he hired music consultants, and he cannot even copy a famous tune | **Paid in EP001**. Visible carrier: he writes the word "score", the pen stops, he tosses it aside |
| F-SYS-COST | The device has a cost | **Explicitly deferred to EP007** (first visible cost). This round only plants the contract clause in EP001 and does not disclose it |

The system's contract is written in full and accepted before EP001; adding a clause later to rescue a stuck
episode is treated as a defect:

> DEV-04 · Cost of use: everything the device grants is taken by this world as his own talent. The misattribution
> cannot be corrected — the moment he denies it, the granted ability fails for that performance. First in effect:
> EP001 (first visible cost in EP007).

Originals: [`creative-brief.md`](../evaluations/让你管账号/reference-run/项目开发/creative-brief.md) ·
[`story-engine.md`](../evaluations/让你管账号/reference-run/项目开发/story-engine.md) ·
[`episode-map.jsonl`](../evaluations/让你管账号/reference-run/项目开发/episode-map.jsonl)

## Claims about models in the skills were checked against real generations first

Origin: `evaluations/model-behavior-probes.md`. Every "what the model does" statement in the skills corresponds to
a generation observation on record: a batch of exploratory observations from September 2026 (MiniMax H3, Seedance
2.0/2.5, gpt-image-2), the summary kept in the repository and the raw media outside it, with sample size, method and
what each one can support (4 of the table's 20 rows, translated):

| Observation | Sample and result | What it supports |
|---|---|---|
| H3 Chinese dialogue | Same shot 20 times, 7–108 characters, 5–13 s; natural pace ≈4.1 characters/s, denser input rushes or truncates | A creator-overridable timing reference; 50 characters in 5 s still came out complete, so no "more than 9 characters/s truncates" threshold can be drawn |
| Multi-shot cut point | Asked to cut at 4 s: H3 3.96/4.04/4.12 s, Seedance 2.5 3.71/4.29/4.46 s; 2.0 with no second given landed at 5.21–5.54 s | Measure the actual cut point; not a precision promise, and not a strict same-syntax comparison |
| H3 speaker lip-sync | One shot (a child shouts a line in the distance, a rider up close says nothing), three groups of 6, 6 s each. In the group where the rider still faces the camera during the line: the current phrasing put the lips on the rider, the child's mouth closed, in 2 of 3; with the speaker given a voice and on-screen tag, the line placed after his action sentence, and the rider written explicitly as not speaking with lips closed, all 3 landed on the child … | The voice was not wrong; the lips landed on the most prominent front-facing face … small sample, still check whose face the lips land on after generating |
| Continuing from the real last frame | With the previous clip's last frame bound, 2 runs kept the opening; text only, 2 runs did not | When continuity matters, prefer real outputs as references |

Full table and execution-path caveats: [Model behaviour observations](../evaluations/model-behavior-probes.md) (Chinese).
