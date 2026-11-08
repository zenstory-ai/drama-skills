# Assets And Asset-Image Prompt Rubric

## Occurrence and decision

- Trace every production-relevant appearance to a scene ID and action/dialogue quote in `剧本.md` (exclude incidental screenplay nouns).
- Require an explicit decision (`复用` / `新增身份` / `新增变体` / `待定`) and handle pronouns, aliases, groups, memories, portraits, and screen content without guessing.

## Identity versus variant

### Character / Look

- **Identity**: stable face/body/hair anchors, distinguishing marks, and persistent voice identity.
- **Look**: wardrobe, makeup, hair arrangement, injury, dirt/wetness, disguise, age/weathering state, validity range.
- Fail when a costume change creates a new person, incompatible Looks mix in one prompt without story reason, or protagonist/antagonist labels silently invent beauty, ugliness, body type, skin tone, or facial morality.

### Voice direction (optional, `AST-07`–`AST-12`)

Only reviewed when `视觉设定.md` records a voice direction. Timbre is carried by a named reference recording plus pronunciation choices; accompanying text selects or judges a voice, never stands in for one.

Fail when:
- no reference exists and prose adjectives stand in for identity instead of `待选型`;
- a binding omits what it controls/excludes, or leaks take emotion, room reverb/mic distance, or background noise into identity (`AST-08`);
- an audible claim lacks creator description or authorized listening observation (`AST-09`);
- one proper noun has two accepted spellings in `视觉设定.md` (`AST-10`, structural blocker);
- confusable references lack a distinguishing trait naming the nearest neighbour (`AST-11`);
- reference audio bytes, provider parameters, model names, task fields, or URLs appear in `视觉设定.md` or delivery files.

Weak or unbounded selection criteria are reported as a craft note (`AST-12`).

### Location / View

- **Identity**: architecture, layout, entrances, zones, anchors, materials, navigation.
- **View**: camera-facing orientation/zone, time/weather/light state, visible anchors.
- Fail when each camera angle becomes an unrelated location, geography changes silently between scene and plate, or Views sharing a time/weather state have unrecorded differences in key-light source, warm/cool priority, contrast direction, or practical on/off state when compared side by side (`IMG-10`).

### Prop / State

- **Identity**: scale, shape, material, function, moving parts, marks, text policy.
- **State**: owner/hand/location, open/closed, clean/damaged/wet/bloodied, contents, validity.
- Fail when a prop teleports, changes scale/material, or loses required readable evidence.

## Era

Era comes from source facts (devices, platforms, slang, stated years). Fail when `视觉设定.md`, `图片提示词.md`, or `视频提示词.md` contradicts source era facts, or uses retro/aged descriptors (`旧/老式/复古/褪色/斑驳`, `old`, `worn`, `dusty`, `period`, `CRT`) without source basis or explicit creator choice (`AST-14`, `STY-07`). Missing era anchors or unstated era-specific forms are craft notes (`AST-15`).

## Prompt recipe and failure checks

Every prompt requires purpose, exact binding, identifying facts, current variant, composition, background, lighting, text policy, constraints, and exclusions:

- **Reference admission**: each media reference must declare one purpose, facts to copy, facts to exclude, and pixel/text admission. Fail on "use the whole reference" or when a composition/scale/effect reference leaks identity, wardrobe, text, count, or story state.
- **Type-specific checks**:
  - **Character sheet**: one identity and coherent Look, neutral background/light, no story action chain or accidental pose mixed into immutable anchors.
  - **Location plate**: navigable geography, orientation, fixed anchors, material, palette, light direction; empty of cast unless specified.
  - **Prop plate**: scale cue, shape, materials, wear, moving parts, current state, viewing angle, isolation, text policy.
  - **Edit delta**: exact target/region, changes, preserve set, and continuity impact (fail on vague "make better" requests or unrelated regeneration).
- **Blocking prompt failures**:
  - quality/style boilerplate precedes or replaces identity/geography/scale, or the prompt dumps the entire visual spec instead of the needed variant;
  - one character or prop occupies mutually exclusive positions, hands, or eyelines in the same frozen instant;
  - negative constraints contradict required visible facts, or `图片提示词.md` contradicts `视觉设定.md`;
  - private URLs, source IDs, provider task fields, or operator complaints leak into the prompt.
