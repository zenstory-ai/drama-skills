# Agent Note: 生产与剪辑工具原生支持多镜合生分组 `GROUP-*`

Status: implemented

## Problem

在 [跨文档检查支持局部核对、交付分组与「入画」锁范围](2026-10-20-partial-check-groups-in-frame-locks.md) 中，《视频提示词.md》引入了 `## GROUP-<EP>-<n> · <名称>` 条目，由 `creator_markdown_check.py` 校验成员连续性、时长加总、台词引文与连戏锁，并由 `creator_views.usable_groups` 并入创作台复制队列；但当时决定内置生产工具仍只接受 `MOTION-*` 来源，分组正文仅靠创作者手工复制到外部生成工具。

随着 `$short-drama-produce` 与 `$short-drama-edit` 成为仓库内的标准投产与成片剪辑阶段，这一断层带来了两处直接阻断：

1. **投产阶段无法提交 `GROUP-*`**：`production_tool.py` 的 `CREATOR_SOURCE_ENTRIES` 对《视频提示词.md》只认 `MOTION-` 前缀，且强制要求条目具备 `- 输入参考图：` 字段（而分组级 `- 输入参考图：` 在校验器中属于可选字段）。创作者写好并通过校验的合生分组无法用 `production_tool.py prepare` 单次生成视频。
2. **剪辑阶段与创作台剪辑单视图无法消费 `GROUP-*`**：合生出一条多镜视频后，若创作者不拆碎而直接在《剪辑单.md》写 `- 来源：GROUP-EP001-01 · 制作成果/视频/g1.mp4`（或在 `- 未采用镜头：` 登记该分组），`edit_tool.py` 与 `creator_views.parse_cut_list` 均因只接受 `(MOTION|SHOT|IMG)-` 而直接报错；即使手工改挂首个成员 `MOTION-EP001-001`，其余成员 `MOTION-*` 与 `SHOT-*` 也会被 `EDT-11` 误判为未交代下落。

## Decision

翻转此前“内置生产工具只接受 `MOTION-*`”的限制，在 `$short-drama-produce`、`$short-drama-edit` 与 `$short-drama` 创作台中原生打通 `GROUP-*` 合生分组：

1. **`production_tool.py` 支持 `GROUP-*` 视频任务**：
   - 《视频提示词.md》的合法 `source_entry` 前缀扩展为 `("MOTION-", "GROUP-")`；
   - 当 `source_entry` 为 `GROUP-*` 且分组条目未显式声明 `- 输入参考图：` 时，按无分组级图片参考（`[]`）编译任务；当分组显式声明了 `- 输入参考图：` 或 `- 参考音频：` 时，按与 `MOTION-*` 相同的槽位校验与待补拦截规则编译。
2. **`edit_tool.py` 与 `creator_views.py` 支持 `GROUP-*` 剪辑来源与成员覆盖**：
   - 《剪辑单.md》视频段的 `- 来源：` 与片头 `- 未采用镜头：` 均支持 `GROUP-...`（同时继续兼容把同一条合生视频按切点拆成多段 `MOTION-...` 的剪法）；
   - `edit_tool.py` 从剥离 HTML 注释后的《视频提示词.md》解析各 `GROUP-*` 的 `- 成员：` 列表：当某个 `GROUP-*` 被剪辑段采用或登记为未采用时，其包含的全部成员 `MOTION-*` 及对应 `SHOT-*` 自动计入已交代下落（`EDT-11`）；当分组全部成员归属同一剧本场次时，自动继承该场次键参与同场自动接镜（跨场或未解析分组返回 `None`）；
   - `creator_views.parse_cut_list`、`read_episode` 与创作台前端同步识别 `GROUP-*` 来源并关联成员镜头；更新 `skills/short-drama-produce/SKILL.md`、`skills/short-drama-produce/references/adapter-contract.md`、`skills/short-drama-edit/SKILL.md` 与 `skills/short-drama-edit/references/stage-contract.md`（`EDT-01`）。

## Alternatives considered

1. **维持现状，仅在《视频提示词.md》与《剪辑单.md》文档注明 `GROUP-*` 只能手工外部生成并在剪辑单拆成 `MOTION-*`**。
   - 最强理由：不改 `production_tool.py` 与 `edit_tool.py` 代码，改动面最小。
   - 为何不用：多镜合生本来就是 Seedance 2.0 / 2.5 与 Wan 3.0 等内置适配器目标模型的主力能力，校验器放行而投产与剪辑工具报错会让标准流程在中途断裂；且连续一镜到底或模型切点已准的合生片段强迫拆行重挂多个 `MOTION-*` 纯属机械负担。
2. **当 `GROUP-*` 未写分组级 `- 输入参考图：` 时，在 `production_tool.py` 自动合并所有成员 `MOTION-*` 的参考图**。
   - 最强理由：省去创作者在分组条目再写一行分组级 `- 输入参考图：`。
   - 为何不用：不同成员镜头的 `顺序：1` 槽位往往冲突，且分组正文里的 `@图片1` / `图1` 编号必须由分组自己的参考图顺序唯一决定；自动拼接成员参考图会造成槽位重排和提示词指代错位。未写分组级 `- 输入参考图：` 就按无图片参考处理，需要挂图时在分组下显式声明，语义确定且与校验器一致。

## Consequences

- **收益**：
  - 通过 `creator_markdown_check.py` 的 `GROUP-*` 条目可直接用 `production_tool.py` 投产，并在 `edit_tool.py` 与创作台顺畅完成整段入片、拆段精剪或未采用登记，不再出现校验绿灯而下游报错的断层。
- **代价**：
  - `production_tool.py`、`edit_tool.py` 与 `creator_views.py` 需同步感知 `GROUP-*` 前缀及其 `- 成员：` 映射，并在 `tests/` 中维护从校验、投产到剪辑的端到端回归用例。
