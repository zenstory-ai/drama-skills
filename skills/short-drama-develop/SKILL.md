---
name: short-drama-develop
description: 将中文小说、短剧或漫剧想法、梗概、改编材料、已有系列笔记或多集完整剧本发展成可追溯的改编方案、戏剧方向、创作简报、导演阐述、故事引擎与分集地图，并按题材与制作形态（画风）选择写法。用户提出“导入小说做短剧”“从多集整稿生成/补分集地图”“开发短剧/漫剧”“做故事设定/系列大纲/分集规划”“写导演阐述”“这个题材怎么写”“定画风/制作形态”“把这个点子变成短剧”或需要梳理人物冲突与集间交接时使用；已有单集剧本可直接进入写作、资产或审查流程，不强制补开发文件。
license: MIT
---

# 短剧开发

把创作者的意图变成能持续制造**选择、代价与状态变化**的故事系统，保留创作者对题材、结局和尺度的选择。流行套路只能作为候选方法。

## Quick Start

离线验证多集整稿的精确索引、按集切分和源文件变更检测：

```bash
python3 {技能目录}/scripts/selftest.py
python3 {技能目录}/scripts/episode_intake.py index <多集整稿> --out <episode-intake-index.json>
```

## 开始前

本技能可独立运行；若在 `short-drama` 项目内且项目工具可用，可读取 `status` 并使用其发布生命周期。[阶段契约](references/stage-contract.md) 定义本阶段边界、制作形态输入与规则表，无需读取其他技能的文件。

## 先判断入口

1. **只有想法、题材或情绪目标**：完成方向探索，再建立创作简报与故事引擎。
2. **已有梗概、小说、改编材料或系列笔记**：保存来源并列出已承诺事实、可改范围、来源片段与待确认项。长材料先做语义分段、功能账本和候选分集，不用正则命中直接发布剧集或资产。
3. **方向已定，只需规划分集**：读取既有简报与引擎，直接制作或修订分集地图。
4. **已有单集剧本**：不补造开发材料；写/改剧本交给 `$short-drama-write`，拆资产或后续制作从对应技能直接进入。
5. **已有多集整稿，要生成或补分集地图**：保留原文件，只加载 [多集整稿接入与断点续跑](references/multi-episode-intake.md)。由 Agent 按文件实际结构决定边界与本轮批次；脚本只做精确索引、单集切分、校验和续跑。

信息足够时直接工作；仅当缺口会改变主角、冲突引擎、结局承诺或改编边界时才提问。

## 每次执行

### 1. 锁定创作者契约

读取创作者输入和已接受文件，区分：不可改的事实/主题/角色/结局承诺、可探索的空白、形式与制作边界、目标观众反复获得的回报。新项目复制 [creative-brief.md](assets/creative-brief.md)；若改动已接受事实，先展示语义差异与下游影响，不直接覆盖。

### 2. 探索真正不同的方向

方向未定时，提出少量**机制不同**的候选（改变主角策略、对抗来源、代价或冲突持续方式，而非只换标题或职业）；方向明确时直接深化。每个候选说明戏剧承诺、主角追求、对抗机制、反复回报、可升级状态、终止条件与制作负担，交创作者选择或组合并记录理由（未选方案不进入既定事实）。

- 深化承诺与冲突机制：读 [story-craft.md](references/story-craft.md)。
- 题材已确定时：从 [genre-cards.md](references/genre-cards.md) 按索引取**一张**题材卡校准压力来源、场面细节与制作负担（仅作内部参考，不进入交付物）。
- 主角带已知经历或外部授权能力开局时：另读 [premise-devices.md](references/premise-devices.md) 为装置设定边界与代价。

### 3. 建立故事引擎

复制 [story-engine.md](assets/story-engine.md)，写清：压力如何启动与主角应对策略、对手/系统如何反制及退出成本、每轮冲突改变什么状态、人物各自的目标/筹码/底线/关系压力、引擎终止条件、视听与规模边界。

连续剧、长篇改编或人物纵向变化较重时，另读 [serial-character-and-memory.md](references/serial-character-and-memory.md)，建立前史储备（不直接倒进首集对白）、叙事切入窗口、信念压力测试、信息权限与跨集记忆。

### 4. 把全剧脉络落到分集

读取 [episode-design.md](references/episode-design.md)，复制 [episode-map.jsonl](assets/episode-map.jsonl)。每集记录进入状态、开场、当集追求、阻力、局势转折、当集结果、信息释放、出去的压力及下一集继承事实。

- 每集必须先落地一个当集戏剧结果，相邻集精确交接，再安排外部压力与情感负荷双轨节奏。
- 第 1 集入口先比较时序入口、收益入口与冷开；改编项目按原著分析爽点表把高光排到观众尽早拿到的位置。
- 按制作形态从分集设计默认值提出项目节奏档案，写入创作简报交创作者接受后，由 `$short-drama` 写入 `creator_authority.rhythm_profile`。

### 5. 做所有者检查并交接

提交预览前自检：

- 分集、铺垫和兑现引用可解析，未决项已显式标记；
- 选定方向贯穿简报、引擎与分集地图，每次升级均改变权力、信息、关系、暴露、资源、时间或代价；
- 每集先兑现部分当集承诺，再留下具体决定、危险或问题；
- 改编项目保留核心人物立场、核心关系与主线（创作者已接受的改动除外），原著没有的新增内容均登记为 `add` 并列入简报。

展示创作者可读的新增/修改摘要请创作者接受。需要独立质量结论时调用 `$short-drama-review`。若项目需要导演阐述，按 [director-brief-craft.md](references/director-brief-craft.md) 产出 `项目开发/director-brief.md` 候选并标明 `visual_direction` / `production_profile` 语义差异，创作者接受后由 `$short-drama` 写入权威配置。

## 产物与边界

规则分级（`structural_invariant` / `reviewed_invariant` / `craft_default` / `taste_option`）与 `STY-01`–`STY-30` 规则表见 [stage-contract.md](references/stage-contract.md)；不用固定的情节点、转折时刻、篇幅比例或数量配方替代因果判断。本技能只拥有：

- `项目开发/creative-brief.md`
- `项目开发/story-engine.md`
- `项目开发/director-brief.md`（按需）
- `项目开发/adaptation-map.jsonl`（长材料改编时，只记 locator/span、去引用功能摘要、去向与未决项，例见 [adaptation-map.example.jsonl](assets/adaptation-map.example.jsonl)）
- `项目开发/series-arc.json`（按需）
- `项目开发/episode-intake-index.json`（多集整稿接入时的可重建机械索引）
- `项目开发/episode-map.jsonl`

不写场景动作与台词（归 `$short-drama-write`），不拆资产，不写提示词，不生成媒体，也不签发终审结论。

## 按需加载

- **承诺、引擎、人物压力、升级与铺垫兑现**：[story-craft.md](references/story-craft.md)
- **分集契约、因果节拍、集间交接、首集入口、门槛集与项目节奏档案**：[episode-design.md](references/episode-design.md)
- **已有多集完整剧本/散稿，要避免整稿进入上下文并可中断续跑**：
  [multi-episode-intake.md](references/multi-episode-intake.md)
- **人物驱动力、前史与切入、跨集变化、信息权限、双轨节奏与恢复记忆**：
  [serial-character-and-memory.md](references/serial-character-and-memory.md)
- **有原材料、需要按爽点压缩、提前或冷开后文、合并人物场景、把信息视觉化**：
  [adaptation-craft.md](references/adaptation-craft.md)
- **创作者提供对标作品、样例剧本或提示词，希望学习机制而非仿写表达**：
  [creative-reference-intake.md](references/creative-reference-intake.md)
- **单元故事里同一套机制被反复运行，或中段开始重复、越写越薄**：
  [mechanism-loop.md](references/mechanism-loop.md)
- **需要区分揭示、反转、回报和钩子，或按题材选压力机制**：
  [reveal-reversal-payoff.md](references/reveal-reversal-payoff.md)
- **按题材选择冲突推进方式、设计开场或规划集尾钩子时的定性案例方法**：
  [genre-and-hook-playbook.md](references/genre-and-hook-playbook.md)
- **已确定题材，需要该题材更常用的压力、具体场面细节、钩子取向与制作难点**：
  [genre-cards.md](references/genre-cards.md)（索引与召回规范；一次只读一张卡）
- **主角带着已知结果开局，或获得外部授权的能力**：
  [premise-devices.md](references/premise-devices.md)（装置层，叠加在题材卡之上）
- **起草项目级视觉方向与生产规则（导演阐述）**：
  [director-brief-craft.md](references/director-brief-craft.md)
- **本阶段拥有什么、继承什么、不越权什么**：[stage-contract.md](references/stage-contract.md)
