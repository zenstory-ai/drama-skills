# AGENTS.md

## 重要改动必须留笔记

决策笔记放在 `.agents/notes/{proposed,implemented,rejected}/{feature,bug-fix,simplification,architecture,process,testing}/yyyy-mm-dd-topic.md`，沿用 DeepSeek Harness 的 agent-notes 约定（方法见 https://github.com/czm15053/write-notes-like-deepseek）。正文中文，小节标题保留英文。

1. 非平凡改动（改了行为、架构、跨文件或跨 skill 契约、流程与工具链、测试策略、落盘格式）动手前，先在 `.agents/notes/` 里搜同主题旧笔记：有归属就地更新事实；没有就先写 `proposed/`，落地时随同代码改动在同一次提交里转 `implemented/`。纯机械改动（排版、改名、版本号、不改行为的补丁、常规 CRUD）直接提交，不写。
2. 每篇必有 `## Problem`、`## Decision`（现在时，只写已落地事实）或 `## Proposal`、`## Alternatives considered`（每个被否方案先写它最强的理由再写为何不用，没考虑过的不要编）、`## Consequences`（收益和代价都写）。
3. 禁止把一篇笔记改写成相反的决定：事实（路径、名字、默认值）就地改；决定翻转就另开一篇并互链。
4. 不建 `INDEX.md`，目录位置就是状态；检索用 `rg --hidden .agents/notes/`。
