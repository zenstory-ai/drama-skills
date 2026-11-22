# 规则与路由索引

## 阶段问题路由

| 创作问题 | 负责技能 |
|---|---|
| 长篇原著章节索引、抽样快评、逐章提取与分集候选 | `short-drama-novel-analyze` |
| 对标剧实测、手法提炼、同尺差距对照、视频反推剧本与成片还原 | `short-drama-breakdown` |
| 创意开发、改编方案、分集大纲、题材打法与节奏目标拟定 | `short-drama-develop` |
| 单集场次剧本、对白交锋、场内声音设计与剧本估时 | `short-drama-write` |
| 人物造型、地点视角、道具状态、角色声线与连戏锁 | `short-drama-assets` |
| 角色三视图、场景板、道具板等静态设定图提示词 | `short-drama-image-prompts` |
| 场面拆镜、站位调度、运镜设计与首尾帧提示词 | `short-drama-storyboard` |
| 视频动态提示词、多镜合生、接力方式、目标模型适配与成片配乐（`MUSIC-*`） | `short-drama-video-prompts` |
| 外部模型生图、生视频、配音、配乐任务预览与确认执行 | `short-drama-produce` |
| 剪辑单编排、花字字卡叠加、音画对切与成片渲染 | `short-drama-edit` |
| 独立审稿、节奏核对与出片问题归因 | `short-drama-review` |
| 项目初始化与全局配置、制作形态选型、创作台、导出与交付校验 | `short-drama` |

## 规则分级与优先级

- **硬门禁 vs 软门禁原则**：只有 100% 确定性的机械与安全核对（编号与跨文件 ID 解析、本地文件路径与符号链接安全、时长算术、下游必需字段、外发/付费确认令牌）设为脚本硬阻断 `ERROR`（`structural_invariant`）；其余所有启发式核查、跨语种提示词名称提醒、语义保真与正文锁词覆盖一律采用**软门禁**（脚本输出 `WARNING` 提醒 Agent 重点复核、退出码保持 `0`，或交由 `short-drama-review` 按 `reviewed_invariant` 结合上下文审定），绝不拿脆弱启发式粗暴阻断创作。
- **四级规则**：`structural_invariant`（100% 确定性结构与安全底线，由脚本硬阻断）、`reviewed_invariant`（需结合剧情上下文与语义核实的内容底线，归 `short-drama-review` 技能，脚本仅可输出软 `WARNING` 提醒）、`craft_default`（成熟创作经验，说明用意即可突破）、`taste_option`（审美与风格取向，不作打回理由）。各环节细则见对应技能的 `references/stage-contract.md`。
- **冲突优先级**：创作者拍板的核心设定与改编底线 → 已确认的单集大纲与连戏事实 → 各技能 `stage-contract.md` → 题材卡、形态卡与通用经验。
