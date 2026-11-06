# Agent Note: 技能说明消解翻译腔与案例文案短剧质感润色

Status: implemented

## Problem

上一轮 `2026-10-15-polish-drama-*` 五步精修主要对齐了技能文档与脚本检查器的契约，但保留了代码块、正反配对例句、引用块及 `examples/` 下的完整案例原文。仓库里仍有两类明显的语言问题：

1. **技能说明与写作/开发规则带有生硬的英文直译和自造黑话**：例如把五份创作者文档叫作“创作表面”，把不可逆转折叫作“终止性转变”，把代价高昂的阻碍叫作“昂贵阻力”，把阶段性结果叫作“局部结果”，把备选拍法叫作“可替代实现”，把反应镜头叫作“承受者反应”；部分段落仍夹杂电报体短碎句、元说明和防御性补丁，既让阅读费力，也容易把 agent 生成的剧本和设定带向翻译腔。
2. **随仓案例与模板文案缺乏网络短剧质感**：`examples/excerpt-chain/`（《入职三年无人识，今日亮牌天下惊》）充斥“把酒店续约后果推入钩子”“私人判断由注视、捡拾、递牌、躬身、托盘失手与挤笑等可见动作表达”“这项礼仪动作完成后，她抬高音量逐字说”等书面分析腔；`examples/golden-project/`（《善意不结账》）的开发文档、节拍表、单集剧本与卡片大量使用“昂贵阻力”“终止性转变”“正在把帮助继续传下去的人，以及愿意加入的新行动者”等欧化长句；`examples/creator-first/EP001/` 及各技能内置模板也有“承受者反应兼笑点”“授予清单从他面前进来”等别扭表述。

## Decision

按五步精修法系统润色创作者技能、公开说明文档以及 `examples/` 与技能 `assets/` 案例：

1. **技能说明去翻译腔与五步精修**：把“创作表面”“焦点人物”“昂贵阻力”“终止性转变”“局部结果”“可替代实现”“承受者反应”“方向性转折”“可见接收”“议程”“在压力活跃处进入”“信息赤字”“私人反应”“人物声音”等直译生造词替换为地道的中文影视与短剧行业用语（如“创作者文档”“主视角人物/主动方”“硬阻力”“终局转折”“当集结果/阶段性结果”“备选拍法”“听者反应”“局势转折”“外显反应”“算盘/企图”“从冲突绷紧的地方切入”“信息差”“私下反应”“人物腔调”；译名替换不改变规则范围：单集语境用“当集结果”，跨集、人物弧线与机制循环用“阶段性结果”，“保护对象”“信念”“独特矛盾”“反复回报”“信息释放”“字面精确死线”保留原概念），把 `short-drama`、`short-drama-develop`、`short-drama-write`、`short-drama-storyboard`、`short-drama-video-prompts`、`short-drama-review` 示例中的抽象代号（`角色甲`/`角色乙`/`人物乙`/`甲`/`乙`/`A`/`B`）替换为有具体身份与对手关系的短剧人物，并在 `short-drama-write` 增加一条 `craft_default`：中文对白与动作描写默认地道、贴合人物身份，人物或作品选择其他风格时以该选择为准。
2. **全量案例文案短剧化精修**：
   - `examples/creator-first/`：润色说明文档与 `EP001` 分镜、设定中的生硬句式，保留 `creator_markdown_check.py` 与回归测试依赖的稳定标识、时长及中英引号对齐。
   - `examples/excerpt-chain/`：把《入职三年无人识，今日亮牌天下惊》的剧本、资产设定、分镜与视频提示词改写为干脆利落、冲突直接的都市反转短剧工作稿。
   - `examples/golden-project/`：把《善意不结账》的创意立项、故事引擎、分集地图、8 集完整剧本、节拍表、单集卡片、资产设定（`characters.jsonl`、`props.jsonl`、`prop-states.jsonl`）、跨集连续性（`continuity.jsonl`）、分镜信息变化（`shots.jsonl`）与动作规格润色成自然接地气的中文短剧文本，消除逐集或逐镜复制粘贴的占位套话，同步 `EP001`–`EP008` 的 `screenplay-index.jsonl`。逐集规划字段按各集剧本写，不共用同一句；对白润色保留了工地砸伤腿、儿子每周五送汤这类不改变主线的具体说法。
   - `审查/verdict.json` 只追加维护者自检说明；`创作者决策/` 不改，文本改动没有补造新的创作者接受记录。
   - 同步精修 `short-drama-write`、`short-drama-develop`、`short-drama-novel-analyze`、`short-drama-assets`、`short-drama-image-prompts`、`short-drama-storyboard`、`short-drama-video-prompts`、`short-drama-review` 的合成正反例、`assets/` 模板与 `docs/` 示例。

## Alternatives considered

- **只改技能正文，不动 `examples/` 与技能内置示例**：改动面小，不需要重算 `golden-project` 的剧本索引或核对跨文件台词引用。未采用：技能内置示例和 `creator-first` 是读者与 agent 直接参考的写法，保留翻译腔会和新规范不一致。代价是 `excerpt-chain` 与 `golden-project` 这两份维护夹具也跟着改动，它们仍不作为当前 Skill 的操作说明。
- **彻底重写案例剧情与场次结构**：可以完全自由发挥文风。未采用：`examples/creator-first/EP001` 与 `examples/golden-project` 承担着全仓结构校验、溯源索引与创作台回归测试的基准职责；保持场次、镜头编号、角色名与核心戏剧事实不变，只精修语言质感，才能兼顾短剧质感与确定性回归。

## Consequences

- **收益**：技能说明、创作规范与随仓案例统一为地道、利落的中文短剧行业表达，减少随仓文字里的翻译腔；是否改善生成文本未经实测。
- **代价**：修改 `examples/golden-project/剧集/EP00*/screenplay.md` 后需用 `screenplay_index.py` 重建索引并同步 `motion-specs.jsonl` 中的引文；修改 `skills/*` 后需同步更新 `.clawhub/publish.json` 的技能版本与锁文件。
