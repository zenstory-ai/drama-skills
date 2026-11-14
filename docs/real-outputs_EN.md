# See what it produces: excerpts of real output

[中文](real-outputs.md)

These excerpts come from repository samples and versioned runs; each section names its source.
Chinese text is translated where marked. A “…” marks an omission within a line or a whole paragraph;
fields outside the discussion are not listed.

## One shot through four documents: the storyboard traces back to the script, the look stays locked

Origin: the [public sample `examples/creator-first/EP001`](../examples/creator-first/EP001/), written to the
current document format rules; it passes `creator_markdown_check.py`. The same shot,
`SHOT-EP001-002`, is handled one layer at a time. The script only says what happens (translated):

```markdown
[OS] Someone from another army unit: The Rocket Force? Four accounts, four followers between them, right?

Laughter pours out of the laptop's speaker. Behind the desk, Zhou Bosen sits bolt upright facing the screen, face set.
In front of it, Jiang Chen, palms on the desk edge, snaps back to himself.
```

`视觉设定.md` records appearance details that must stay consistent across shots, and gives fixed wardrobe a
**continuity lock** (`连戏锁`) whose **locked phrase** (`锁定词`) can be pasted into prompts unchanged (translated):

```markdown
## Character · Jiang Chen
- Appearance traits: long face, high brow ridge, deep-set eyes, crew cut, straight shoulders. Not an idol fringe, not loose streetwear.
- Prompt name: Jiangchen
- Continuity lock: LOCK-JIANGCHEN-DRESS "Jiang Chen's pine-green service uniform" (shots: SHOT-EP001-002, SHOT-EP001-003, SHOT-EP001-007, …;
  image prompt entry: IMG-JIANGCHEN-SHEET) · locked phrase: pine-green lapel service jacket
```

`分镜.md` writes this shot's start, action, end, and why the camera moves the way it does; the **first-frame prompt**
(`首帧提示词`) depicts only the opening instant. Once that prompt is written, the shot lists every character, location
and prop in the frame whose appearance, look or layout must stay consistent under **on-screen settings** (`出场设定`),
and the locked phrase appears verbatim in the first-frame prompt (translated; the prompt is quoted as written):

```markdown
## SHOT-EP001-002 · Four accounts, four followers
- Source: EP001-SC001
- Duration: 4s
- Camera: slow push-in, starting at the loudest point of the laughter, past the back of the laptop toward the desk, stopping
  on Zhou Bosen's set face; the laughter is aimed at him.
- Start: Zhou Bosen sits bolt upright facing the laptop, right hand beside his tea tumbler; Jiang Chen's palms rest flat on
  the glass edge, his eyes unfocused.
- Action: as the laughter rolls in, Zhou Bosen's jaw tightens and his back straightens another fraction; Jiang Chen blinks once and his eyes snap into focus.
- End: the frame settles on Zhou Bosen's set face in the screen glow; Jiang Chen still leans on the desk at the right edge.
- Input references: none (text-to-video).
- On-screen settings: 视觉设定.md · character "Jiang Chen" (controls: appearance, build, this episode's look); character "Zhou Bosen" (controls: appearance, build, this episode's look);
  location "Deputy regiment commander's office" (controls: clear glass desktop, coaster, binder shelves, blind-filtered window light);
  prop "Laptop" (controls: thin silver body, red lid sticker); prop "Glass tea tumbler" (controls: double-walled glass, sunken tea leaves).

### First-frame prompt
> 9:16 vertical two-person medium shot in a present-day army arts-troupe office, framed at chest height: Jiangchen, a lean
> young man in a pine-green lapel service jacket, stands mid-ground on frame right … with both palms flat on the glass and a
> dazed, unfocused look; Zhoubosen, a broad square-faced middle-aged officer, sits bolt upright behind the desk … facing a
> thin silver laptop whose lid faces the camera, … his right hand beside a double-walled glass tea tumbler on a dark round
> coaster; … no text, no logo.
```

`视频提示词.md` summarises who and what is on screen in one **opening frame description** (`开场画面`, locked phrase
included), maps out the **action progression** (`动作过程`), and devotes the copyable prompt to playable motion, the
storyboard's camera move, and a clear ending frame (translated; the prompt is quoted as written):

```markdown
## MOTION-EP001-002 · Four accounts, four followers
- Storyboard: SHOT-EP001-002
- Duration: 4s
- Generation mode: text-to-video
- Input references: none (text-to-video).
- Opening frame description: In a present-day army arts-troupe office with a bookcase of blue document binders …, a lean young
  East Asian man in a pine-green lapel service jacket stands mid-ground on frame right with both palms flat on the front edge
  of a light-oak desk with a clear glass top and a dazed look, …
- Start frame: Zhou Bosen sits bolt upright facing the laptop; Jiang Chen leans on the desk edge, dazed.
- Action progression: laughter rolls in → Zhou Bosen's jaw tightens and his back straightens further, Jiang Chen blinks back to himself → the camera pushes in to Zhou Bosen's set face
- End: the frame rests on Zhou Bosen's set face in the screen glow; Jiang Chen at the right edge.

### Copyable prompt
> … Laughter keeps pouring out of the laptop's small speaker. The seated officer's jaw tightens and his back straightens a
> little more. The young man blinks once and his eyes snap into focus. At the loudest point of the laughter, the camera moves
> steadily forward past the back of the laptop and stops when the seated officer's tight face fills the middle of the frame,
> the young man remaining at the right edge. …
```

The four originals: [`剧本.md`](../examples/creator-first/EP001/剧本.md) ·
[`视觉设定.md`](../examples/creator-first/EP001/视觉设定.md) ·
[`分镜.md`](../examples/creator-first/EP001/分镜.md) ·
[`视频提示词.md`](../examples/creator-first/EP001/视频提示词.md). The three consistency layers are explained in
[Cross-shot consistency](character-consistency-across-shots.md) (Chinese).

## What the checker catches: break the sample in two places on purpose

Origin: the same public sample as the previous subsection. `creator_markdown_check.py` runs cross-document checks
across the five files of one episode. It passes on the sample as shipped. Remove Zhou Bosen from `SHOT-EP001-002`'s
on-screen settings (`出场设定`) and change `MOTION-EP001-003`'s duration from `2s` to `3s`, and it reports the exact
cause rather than a generic "validation failed":

```text
$ python3 skills/short-drama/scripts/creator_markdown_check.py examples/creator-first/EP001 --project-root examples/creator-first
OK: examples/creator-first/EP001

$ python3 skills/short-drama/scripts/creator_markdown_check.py <broken copy>/EP001 --project-root <broken copy>
ERROR: SHOT-EP001-002: 首帧提示词写到人物「周薄森」，出场设定没有覆盖；本镜确实看不见时在出场设定末尾加「；画外：人物「周薄森」」，正文里这个名字不可靠时在《视觉设定.md》写「提示词名称：无」
ERROR: SHOT-EP001-003: 分镜时长 2 秒与视频提示词 3 秒不一致；视频提示词时长必须与分镜一致
```

The first line says: the first-frame prompt names the character "Zhou Bosen" (`周薄森`), but `出场设定` (on-screen
settings) does not cover him; if he is genuinely not visible, append `; off-screen: character "Zhou Bosen"`
(`；画外：人物「周薄森」`) to `出场设定`, and if that name is unreliable in prompt text, set `提示词名称：无`
(`Prompt name: none`) in `视觉设定.md`. The second: the storyboard says 2 seconds and the video prompt says 3; the
video prompt's duration must match the storyboard.

It also checks that every shot's "source" starts with a scene ID that really exists in `剧本.md` and that any character,
location, prop or look named in `首帧提示词`, `尾帧提示词` or a text-to-video `开场画面` is covered by `出场设定` (on-screen settings) or declared
off-screen (rather than scanning `来源` quotations); that every scene in the script has a corresponding shot or is listed as deliberately unfilmed; that explicit spoken dialogue
quoted inside the copyable prompt body (introduced by speech verbs or `<d>`, rather than ordinary signage or idiom quotes) can be found, punctuation aside, in `剧本.md`, `视觉设定.md` or
`分镜.md`; and that every `REF-*` points at an image that really is in the project with a stated purpose.

## Estimate dialogue before fixing shot length; cut on measured timings

Origin: a run made at v0.6.6 (retaining the field labels from that version), the one that produced the sample film in
the README. At the storyboard stage each line of dialogue is timed into the shot length, with the estimate written into
the shot's "sound" line; the shot is generated at 7 s to leave a settle margin, and the target length in the cut is
written separately (translated):

```markdown
## SHOT-EP001-017 · Gentlemen, hear the dragon roar
- Source: EP001-SC003 「江晨（对着空剪辑室）：诸君，且听龙吟。」 (Jiang Chen, to the empty edit room: "Gentlemen, hear the dragon roar.")
- Duration: 7s
- Target length in cut: 6.5s. … seconds 6.5–7 are the settle margin; editing trims that 0.5 s from the end.
- Sound: Jiang Chen, 1 line, 6 spoken characters, ≈1.5 s at 4.1 characters/s (text estimate: he normally speaks fast with crisp
  endings; this line is half a step slower, with a gap between characters). Layout of the 7 s: finish reading the result on
  screen 1.4 s + slow exhale and shoulders dropping 1.5 s + eyes lifting 0.7 s + the line 1.5 s + pull-back to the settle and one
  beat 1.4 s (the 6.5 s cut target ends here) + hold 0.5 s, trimmed in the cut. …
- Input references: PLAN-SHOT-START (order: 1) · SHOT-EP001-017 "this shot's opening keyframe" (purpose: start frame; controls: opening composition …);
  PLAN-JC-LOOK-C (order: 2) · IMG-JIANGCHEN-LOOK-C "Jiang Chen, dried-mud dawn fatigues state board" (purpose: look state; …); …
```

This shot was written as an image-to-video prompt for MiniMax H3. The locked phrase on Jiang Chen's fatigues in
`视觉设定.md`, `olive drab field fatigue uniform with blank collar tabs`, appears verbatim inside `subject_definitions`,
and the line is given character by character inside `<d>` only (translated; the prompt is quoted as written):

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
- Choice: in = 0.84 s ahead of the measured speech span (2.04–3.20 s in the source), hand already on the mouse; out = 1.00 s after
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
can be found verbatim in the script; `verify` only outputs measured data. That run's `RUN-LOG` records that the first
person these two checks caught was the author: a subtitle window estimated from a transcript fell outside its
interval and `check` stopped it; the resolution was written as `1080×1920` while the clips were `768×1344`, and `verify`
stopped that. The same log keeps two measurement results: a single `loudnorm` pass landed at `-12.33 LUFS`, `3.7 dB` off
target, and only a second pass reached `-15.79`; speech transcription heard "诸君，且听龙吟" as "朱军且听龙银", which
is why transcription only locates timing and subtitles are never taken from it.

The originals of this run — the
[cut list](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%89%AA%E8%BE%91%E5%8D%95.md),
the [21-shot storyboard](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%88%86%E9%95%9C.md)
and the [RUN-LOG](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/RUN-LOG.md) —
sit in commit `004d945` together with the eight clips and the film; by repository rule they are no longer kept in
the working repository directory. They were written to the v0.6.6 rules; besides renamed field labels and checking `首帧提示词`, `尾帧提示词`, and text-to-video `开场画面` names against `出场设定`, the current
cut-list checker also requires the 13 unused shot IDs to be listed one by one rather than as a range, and the
FAQ entry [What do I do after upgrading?](../README_EN.md#what-do-i-do-after-upgrading) explains how to update older
episodes.

## The source triage is compared against its own full pass

Origin: `evaluations/让你管账号/reference-run` (the v0.4.2 run). `$short-drama-novel-analyze` first triages an
evenly sampled 12 of 20 chapters, then extracts all 20; when the full pass is done it goes back over the triage line
by line and says which calls were overturned (4 of the table's 7 rows, translated):

| S1 triage call | Full result | Verdict |
|---|---|---|
| Framework is a levelling-up story with a weak revenge thread | Holds. Two task loops; the rival thread in chapters 13–17 does not drive the main line | **Not overturned** |
| About 67% directly filmable (`screen_ready`) | 19 of the 24 candidate episodes are `screen_ready` (79%), 5 need a visual form (`needs_carrier`), 0 prose-only (`prose_only`) | **Overturned (too conservative)**. See below |
| Chapter 13 is prose-only (`prose_only`) | Does not hold on the full pass. The chapter's dramatic role (the rival's entrance and accusation) can be played entirely by one person at an edit desk; the triage mistook "walls of online comments" for the dramatic role itself, when that was only how the novel presented it | **Overturned** |
| 22–26 episodes | 24 were cut | **Not overturned** |

> **The two overturned calls share one cause**: at the sampling stage it is easy to mistake "how the novel writes a
> beat" for "whether that beat can be filmed". Chapter 13 is wall-to-wall online comments and looks unfilmable, but its
> role in the story is the rival's entrance, which translates cleanly into visible action. The next book's triage should
> ask what dramatic job a chapter does before judging its prose form.

(The operator of this run had read the whole book before the triage; the declaration at the top of `triage.md` says
the comparison is therefore optimistic: it demonstrates the cross-check step, not the accuracy of blind sampling.)
Every episode candidate carries `source_ref` / `chapter_range` back into the chapter index, and
`creator_acceptance` is always `pending` — the analysis skill never approves its own output; the creator signs off.
Originals: [`triage.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/triage.md) ·
[`adaptation-value.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/adaptation-value.md) ·
[`episode-candidates.jsonl`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/episode-candidates.jsonl)

## Source-setting checklist: every key novel fact names the episode and the shot that shows it

Same origin. `$short-drama-develop` lists the source settings that must not be altered, and each one has to answer
"which shot shows this to the audience"; anything held back from Episode 1 is explicitly scheduled for a numbered
later episode (3 of the table's 9 rows, translated):

| ID | Key source setting | How it pays off this round |
|---|---|---|
| F-W2 | **New media in this world is behind across the board**: not just the military, creators with over ten thousand followers are rare in any field | **Shown in EP001**. How we show it: he scrolls to the platform's industry chart, and the top creator's follower count has four digits. The audience contrasts that with his past life and draws the conclusion themselves |
| F-C5 | He knows nothing about music; in his previous life he hired music consultants, and he cannot even copy a famous tune | **Shown in EP001**. How we show it: he writes the word "score", the pen stops, he tosses it aside |
| F-SYS-COST | The device has a cost | **Explicitly scheduled for EP007** (first visible cost). EP001 only plants the rule setup without revealing the cost |

The system's rules and cost are written out in full and accepted before EP001 begins; inventing a new rule mid-season
to rescue a stuck plot is treated as a writing defect:

> DEV-04 · Cost of use: everything the device grants is taken by this world as his own talent. The misattribution
> cannot be corrected — the moment he denies it, the granted ability fails for that performance. First in effect:
> EP001 (first visible cost in EP007).

Originals: [`creative-brief.md`](../evaluations/让你管账号/reference-run/项目开发/creative-brief.md) ·
[`story-engine.md`](../evaluations/让你管账号/reference-run/项目开发/story-engine.md) ·
[`episode-map.jsonl`](../evaluations/让你管账号/reference-run/项目开发/episode-map.jsonl)

## Claims about models in the skills were checked against real generations first

Origin: `evaluations/model-behavior-probes.md`. The four observations below come from exploratory runs in September 2026
(MiniMax H3, Seedance 2.0/2.5 and gpt-image-2). The repository summary records sample sizes, methods and scope;
raw media stays outside the repository. These results do not cover every model capability or call setup (translated):

| Test | Sample and result | How to use it |
|---|---|---|
| H3 Chinese dialogue | Same shot 20 times, 7–108 characters, 5–13 s; natural pace ≈4.1 characters/s, denser input rushes or truncates | A timing estimate creators can override at will; 50 characters in 5 s still came out complete, so no hard "more than 9 characters/s truncates" cutoff applies |
| Multi-shot cut point | Asked to cut at 4 s: H3 3.96/4.04/4.12 s, Seedance 2.5 3.71/4.29/4.46 s; 2.0 with no second given landed at 5.21–5.54 s | Measure the actual cut point in editing; not a precision guarantee, and not a strict same-syntax comparison |
| H3 speaker lip-sync | One shot (a child shouts a line in the distance, a rider up close says nothing), three groups of 6, 6 s each. In the group where the rider still faces the camera during the line: the earlier phrasing put the lips on the rider, the child's mouth closed, in 2 of 3; with the speaker given a voice and on-screen tag, the line placed after his action sentence, and the rider written explicitly as not speaking with lips closed, all 3 landed on the child … | The voice was not wrong; the lip movement gravitated to the most prominent front-facing face … small sample, still check whose face moves after generating |
| Continuing from the real last frame | With the previous clip's last frame attached, 2 runs kept the opening; text only, 2 runs did not | When cross-shot motion continuity matters, attach the actual rendered end frame as a reference |

Full table and test-condition notes: [Model behaviour observations](../evaluations/model-behavior-probes.md) (Chinese).
