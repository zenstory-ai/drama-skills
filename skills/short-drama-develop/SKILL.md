---
name: short-drama-develop
description: 将中文小说、短剧或漫剧点子、梗概、改编材料、系列笔记或多集完整剧本整理成有据可查的改编方案、故事走向、立项简报、导演阐述、核心冲突设定与分集大纲，并按题材与制作形态（画风）匹配写法。用户提出“导入小说做短剧”“从多集剧本生成/补分集大纲”“开发短剧/漫剧”“做故事设定/系列大纲/分集规划”“写导演阐述”“这个题材怎么写”“定画风/制作形态”“把这个点子变成短剧”或需要梳理人物冲突与上下集交接时使用；已有单集剧本可直接进入剧本写作、视觉设定或审查流程，不强制补开发文件。
license: MIT
---

# 短剧开发

把创作者的原始想法落成能推着人物做抉择、付代价、变局面的故事框架，守住创作者对题材、结局走向和尺度的拍板权。常见桥段套路仅作备选参考。

## 快速开始

离线验证多集完整剧本的精确索引、按集切分和原稿改动检测：

```bash
python3 {技能目录}/scripts/selftest.py
python3 {技能目录}/scripts/episode_intake.py index <多集完整剧本> --out <episode-intake-index.json>
```

## 开始前

本技能可独立运行；若在 `short-drama` 项目内且项目工具可用，可读取 `status` 并接入其发布流程。[开发阶段职责与规则](references/stage-contract.md) 说明本环节职责范围、画风/制作形态要求与 `STY-*` 规则表，无需读取其他技能的文件。

## 按体量选入口，不设多余门禁

1. **轻量单集或迷你短篇项目**：支持直接在 `creative-brief.md` 写一份**合一简纲**（意图 + 核心冲突 + 简明分场/分集脉络），不强制拆 `story-engine.md` 与 `episode-map.jsonl`，写完即可交 `$short-drama-write` 开写剧本。
2. **已有明确设定、详细梗概或原著材料**：**直接顺着既有方向深挖落地，不再强行停下来凑 2～3 个备选方向等拍板**；只在缺失信息会颠覆主角立场、核心矛盾或结局底线时才追问。
3. **只有模糊点子、题材或情绪**：给出两三个打法真正不同的备选方向（换破局手段、压制方式或代价落点，不只改剧名职业）供创作者挑选。
4. **已有单集剧本**：不硬补开发文档；写剧本或改稿交 `$short-drama-write`，拆视觉设定或后续制作直接从对应技能切入。
5. **已有多集完整剧本/选集稿，要生成或更新分集大纲**：原稿不动，加载 [多集完整剧本导入与分段续拆](references/multi-episode-intake.md)（支持从非第 1 集起步、跳集选拆与批次覆盖更新）。

## 核心开发步骤（按项目体量裁剪）

### 1. 敲定创作底线与核心看点

理清不能改的关键事实/主题/人物/结局走向、可发挥的留白、制作条件限制与核心看点兑现。新项目复制 [creative-brief.md](assets/creative-brief.md)；改动已确认设定时说明改动点及下游影响，不静默覆盖。

- 核心看点与主线矛盾推演（含系统/规则类的机制循环）：读 [story-craft.md](references/story-craft.md)。
- 题材落位：从 [genre-cards.md](references/genre-cards.md) 按需查取 **1 张**主赛道题材卡找准阻力与细节（内部参考，不写入交付文档）。
- 跨题材开场钩子对比，或带有重生预知、系统外挂等高概念奇招：读 [genre-and-hook-playbook.md](references/genre-and-hook-playbook.md)（首集 3 秒强冲突拍脸仅作常规爽剧默认做法，悬疑、温情生活流、年代情感等题材可采用环境异象、点睛独白或日常切口开场）。

### 2. 搭好核心矛盾与人物关系网（中长篇适用）

多集连载项目复制 [story-engine.md](assets/story-engine.md)，写清危机触发、主角破局路数与软肋、对手变招反扑、主要人物小传与双向拿捏关系、信息差与伏笔台账。人物成长线或跨集连戏较重时，配合读 [serial-character-and-memory.md](references/serial-character-and-memory.md)。

### 3. 按需编制分集大纲 (`episode-map.jsonl`)

`episode-map.jsonl` 定位为**多集连载长剧的按需分集状态账**。需要排多集连载时，读 [episode-design.md](references/episode-design.md) 并复制 [episode-map.jsonl](assets/episode-map.jsonl)，每集只记本集核心推进（钩子、目标、阻力、转折动作、阶段结果、信息揭晓）与单向交接给下一集的 `handoff_state`，不重复抄写上一集状态。

- 常规连载集在抛出集尾悬念前宜先落定一个本集阶段结果；单元温情剧也可在情绪落点舒缓收束。
- 按制作形态提出节奏参考起点，经创作者确认后由 `$short-drama` 写入 `creator_authority.rhythm_profile`。写单集剧本时若发现原分集切分或节奏排布存在结构卡点，路由回 `$short-drama-develop` 更新 `episode-map.jsonl` / `adaptation-map.jsonl`，不由下游技能直接改写。

### 4. 自检并交接

提交前核对：集号与伏笔埋收编号前后一致、未定项已标明；每次冲突升级带来实质处境变化；改编项目保住原著核心人物立场与主线脉络，重要新增项已单列说明。需要独立审稿结论时调用 `$short-drama-review`；需要起草全剧视听总纲或拆解对标材料时读 [director-brief-craft.md](references/director-brief-craft.md)。

## 产物与边界

规则分级与 `STY-01`–`STY-30` 见 [stage-contract.md](references/stage-contract.md)。本技能按需维护：

- `项目开发/creative-brief.md`（轻量项目可直接含合一简纲）
- `项目开发/story-engine.md`（中长篇或复杂人物关系按需使用）
- `项目开发/episode-map.jsonl`（多集连载按需分集状态账）
- `项目开发/director-brief.md`（按需）
- `项目开发/adaptation-map.jsonl`（百万字级长篇或大跨度重排按需使用，例见 [adaptation-map.example.jsonl](assets/adaptation-map.example.jsonl)）
- `项目开发/series-arc.json`（按需）
- `项目开发/episode-intake-index.json`（多集剧本导入时可随时重建的字节索引）

不写具体场次动作与台词（归 `$short-drama-write`），不拆视觉设定，不写生图/视频提示词，不生成媒体文件，也不出具终审结论。

## 按需加载

- **核心看点、主线矛盾框架、机制循环（系统/规则/博弈类）、人物推力与伏笔台账**：[story-craft.md](references/story-craft.md)
- **分集状态账设计、前因后果节拍、单向交接、付费卡点与节奏参考标准**：[episode-design.md](references/episode-design.md)
- **已有多集完整剧本/选集稿，精确切片、分段续拆与批次覆盖合并**：[multi-episode-intake.md](references/multi-episode-intake.md)
- **人物前史切入、弧光转变、信息差、张弛节奏与跨集连戏备忘**：[serial-character-and-memory.md](references/serial-character-and-memory.md)
- **小说改编必保取舍、支线删并、文字外化与高光前移因果修补**：[adaptation-craft.md](references/adaptation-craft.md)
- **区分信息揭秘、局势反转、看点兑现与集尾钩子**：[reveal-reversal-payoff.md](references/reveal-reversal-payoff.md)
- **跨题材推进对比、多元开场留钩语法与高概念奇招（重生/系统限制底表）**：[genre-and-hook-playbook.md](references/genre-and-hook-playbook.md)
- **题材目录与 15 张赛道参考卡（每次按需读一张）**：[genre-cards.md](references/genre-cards.md)
- **导演阐述写法、对标作品门道提炼与分集字数参考区间**：[director-brief-craft.md](references/director-brief-craft.md)
- **本阶段职责边界、制作形态四要素与 `STY` 规则表**：[stage-contract.md](references/stage-contract.md)
