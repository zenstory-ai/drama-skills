# 规则与路由索引

## 阶段问题路由

| 创作问题 | 负责技能 |
|---|---|
| 长篇原著章节索引、抽样快评、逐章提取与分集候选 | `$short-drama-novel-analyze` |
| 对标剧实测、手法提炼、同尺差距对照与成片还原 | `$short-drama-breakdown` |
| 创意开发、改编方案、分集大纲、题材打法与节奏目标拟定 | `$short-drama-develop` |
| 单集场次剧本、对白交锋、场内声音设计与剧本估时 | `$short-drama-write` |
| 人物造型、地点视角、道具状态、角色声线与连戏锁 | `$short-drama-assets` |
| 角色三视图、场景板、道具板等静态设定图提示词 | `$short-drama-image-prompts` |
| 场面拆镜、站位调度、运镜设计与首尾帧提示词 | `$short-drama-storyboard` |
| 视频动态提示词、多镜合生、接力方式与目标模型适配 | `$short-drama-video-prompts` |
| 外部模型生图、生视频、配音任务预览与确认执行 | `$short-drama-produce` |
| 剪辑单编排、花字字卡叠加、音画对切与成片渲染 | `$short-drama-edit` |
| 独立审稿、节奏核对与出片问题归因 | `$short-drama-review` |
| 项目初始化与全局配置、制作形态选型、创作台与交付打包 | `$short-drama` |

## 规则分级与优先级

- **四级规则**：`structural_invariant`（编号、跨文件引用、时长算术等确定性结构，由脚本核对）、`reviewed_invariant`（需结合剧情上下文核实的内容底线，归 `$short-drama-review`）、`craft_default`（成熟创作经验，说明用意即可突破）、`taste_option`（审美与风格取向，不作打回理由）。各环节细则见对应技能的 `references/stage-contract.md`。
- **冲突优先级**：创作者拍板的核心设定与改编底线 → 已确认的单集大纲与连戏事实 → 各技能 `stage-contract.md` → 题材卡、形态卡与通用经验。
