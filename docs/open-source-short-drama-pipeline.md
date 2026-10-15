# An open-source AI short-drama pipeline: script, assets, storyboard, prompts, then generation

Drama Skills (`zenstory-ai/drama-skills`) is an MIT-licensed set of 11 agent skills for Claude Code and Codex that takes a short drama or motion comic (漫剧) from idea or novel to per-episode script, visual asset sheet, storyboard with frozen keyframes, and copy-ready image and video prompts. The core episode stages write Markdown into `剧集/<EP>/`; media generation runs after the creator explicitly confirms a previewed batch. Optional adapters cover Seedance, GPT Image 2, MiniMax H3 video, MiniMax speech and MiniMax Music.

中文全流程：[漫剧创作全流程指引](comic-drama-workflow.md)

## What "generator" means here

Each stage owns a creative decision and records it in the corresponding document:

```text
idea / novel / existing script
        │
        ├─ novel analysis, story development (both optional)
        ▼
      剧本.md            episode script
        ▼
    视觉设定.md          visual asset sheet: identities, variants, continuity locks
      ├──────────────┐
      ▼              ▼
图片提示词.md       分镜.md   storyboard with frozen keyframes per shot
                      ▼
                 视频提示词.md   per-shot video prompts (skip for static motion comics)
                      │
              preview → explicit confirmation → production → edit → review
```

The five core Markdown documents hold each episode's creative decisions. Editing and requested review add their own cut list or findings; they do not replace those source documents.

## The 11 skills

| Skill | Role |
|---|---|
| `short-drama` | Initialise or continue a project, route requests, Look Development, local dashboard |
| `short-drama-novel-analyze` | Read-only analysis of a long novel: chapter index, adaptation value, per-chapter function, episode candidates |
| `short-drama-develop` | Traceable adaptation plan, story engine, episode map, director's statement, genre and hook playbooks |
| `short-drama-write` | Shootable per-episode script with causal beats; also normalises an existing script without rewriting it |
| `short-drama-assets` | Characters and looks, locations and views, props and states, continuity locks |
| `short-drama-image-prompts` | Lookdev style frames, character/location/prop reference-board prompts |
| `short-drama-storyboard` | Shot list with dramatic purpose, spatial continuity, frozen keyframe prompts |
| `short-drama-video-prompts` | Per-shot action, performance, camera, sound, start and end states; timeline music spec |
| `short-drama-produce` | Runs confirmed image, video, TTS or music jobs through external adapters and records results |
| `short-drama-edit` | In and out points, shot order, dialogue completeness, subtitles, loudness, render |
| `short-drama-review` | Structural and continuity review; writes findings, does not edit source files |

## What makes it hold together across shots

Three mechanisms, all in files:

- **Continuity locks.** The asset sheet locks only visible facts that do not change with the plot (a fixed earring, a coat colour) and leaves changing state to per-shot notes. Locks are written as minimal noun phrases so they can be pasted into prompts unchanged.
- **Prompts, plans and references.** `IMG-*` identifies a prompt entry. `PLAN-*` tells the creator what to attach in an external generation tool. `REF-*` binds a real image in the project. Both plans and references can support video prompts; this pack's production tool requires readable `REF-*` files.
- **Frozen keyframes plus visual evidence.** Each shot writes the exact start-of-shot image, then back-fills which characters, locations and props in that frame must keep identity, look or geography. Anything named in the keyframe must appear in the evidence list.

Details in [跨镜一致性](character-consistency-across-shots.md) (Chinese).

## Production and review boundaries

- Media production uses configured adapters after you explicitly confirm the previewed batch. A preview, a "continue", or a budget note does not grant that confirmation.
- Review records findings and revision requests; the responsible creator makes the creative decisions.
- Language: skills, file names and creator-facing text are Chinese. Image and keyframe prompts follow the project's `format.prompt_language`; video prompts first follow the target model profile's `video_prompt_language`. Spoken lines retain the script language.

## Install and first request

```bash
npx skills add zenstory-ai/drama-skills -y -g
```

Then, in an agent, in an empty project folder:

```text
用 $short-drama 初始化一个都市打脸题材的短剧项目，竖屏 9:16
用 $short-drama-write 写第 1 集：外卖员在高档餐厅被经理羞辱，亮出集团董事身份
```

A complete public example of one episode, from script to prompts, is in [`examples/creator-first/EP001/`](../examples/creator-first/EP001/).

## Related

- Repository: https://github.com/zenstory-ai/drama-skills (formerly `worldwonderer/drama-skills`; old links redirect)
- Site guides: https://zenstory.ai/drama-skills/novel-to-short-drama , https://zenstory.ai/drama-skills/character-consistency
- Sibling packs: web-fiction writing (`oh-story-claudecode`), novel to game (`novel-to-game`), video recap (`video-recap-skills`)
