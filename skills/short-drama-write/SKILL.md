---
name: short-drama-write
description: 编写或修订可拍摄的中文短剧、漫剧单集 Markdown 剧本，也负责保留作者原文并规范化现成剧本。用户提出“写/改一集短剧”“把大纲写成剧本”“优化场景/对白”“去模板感”“去 AI 味润色”“续写下一集”或提供剧本要求进入后续制作时使用；不负责资产、分镜、媒体提示词或终审。
license: MIT
---

# 短剧写作

把单集意图写成可表演、可拍摄、会改变故事状态的 `剧集/<EP>/剧本.md`。

## Quick Start

只维护一份剧本 Markdown，不另建 episode card、beats、block index、录音表、QA 或接受记录。
一级标题使用 `# EP001 集名`，场景标题使用 `## EP001-SC001 内 · 地点 · 时间/天气`。
对白写 `角色（可选表演提示）：台词`；生产标签使用 `[VO]`、`[OS]`、`[SFX]`、`[画面文字]`、
`[连续性]`、`[转场]`。不要把含冒号的动作叙述误写成对白。

## 入口

- 有分集规划：读取本集进入状态、目标、转折、回报和交接事实。
- 只有想法/大纲：在上下文形成最小单集契约和因果节拍，再直接写剧本。
- 已有剧本：保留作者语言，只做用户点名的定点修订。
- 非规范文本要进入制作：保留原文，只做必要的场景、动作、对白和生产标签规范化。

开发大纲和长篇分析都是可选上游；当前材料足够时直接写。

## 工作流

1. 锁定本集承诺的观看体验、进入状态、谁现在要什么、核心阻力、当集兑现和退出状态。
2. 在上下文排“因为—行动—结果—下一股压力”，不另存节拍表；逐场确定不可替代的功能、看得见的局面变化与场尾状态。
3. 把动作、对白、画外音、声音事实和画面文字写入同一份 `剧本.md`。用户要求整集就写完整集，场景批次自动续跑。
4. 交稿前只读剧本通读自查，按下方写作要求与[经济性遍](references/script-craft.md#81-经济性遍)清理冗余。

## 写作要求

- 先服从输入已给出的事实、`必须/禁止`、题材观看契约和退出状态；不得补造题面没有的精确数字、记录、资源、程序、关系或机关。
- 每场改变信息、权力、关系、情绪、物理状态或风险；无变化的场删掉或合并。核心阻力的转向要有可追溯的事实、筹码、权限、代价或人物行动，不能只靠对手停止反应。
- 冲突戏的对白优先在争取、回避、试探、逼迫或重新定义关系，温情、喜剧或余韵段落服从本场情绪与关系落点；用可见、可听、可触的行为表现状态，不用解释替代行动。中文表达默认地道，台词贴合人物身份与人情分寸，动作描写用准确动词与具体物件；非风格选择的翻译腔、公文腔和说明书式旁白改掉。
- 自写对白初稿写完通读一遍，删掉只替观众补背景、复述刚演完动作或空喊狠话的句子，纯属场面说明的内容改成动作；创作者原文不按此删减。
- 全集第一拍应能独立形成钩子，见[开场第一拍](references/script-craft.md#71-开场接住进入状态)。
- 理解当前行动所必需的赌注要进入剧本，载体服从题材；选择、证据、限定次数/轮次、精确倒计时只在输入以它为发动机时启用（见下节按需知识），普通决定、普通物件和定性时间压力不升级成机关。
- 压缩过程时只保留改变策略、关系、风险或结果的节点。资源与外部反应须来自输入或前文建立，且不能替人物完成最难的戏剧行动。
- 承担主要冲突的角色保持相称的目标、判断或策略；事务性、环境性角色保持简洁，不硬加秘密、反转或人物弧。
- 已建立的代价、不可逆后果、关键持物、空间和知识状态进入可追溯的退出状态；结尾可推进、留白、反讽、安静收束或停在开放状态，不强制追加外部事件；已接受节奏档案的 `end_on_peak` 为 `true` 时停在峰值上（见[项目节奏档案](references/script-craft.md#64-项目节奏档案)）。
- `[连续性]` 只交接前文动作已建立、又易在下游丢失的状态；不能用作者标签证明镜头外从未发生某事，也不复述正文已清楚呈现的结果。
- 输入给出目标时长时按真实表演、动作和停顿压稿，先删重复验证、解释和同义收尾；峰值上有铺垫的爆发、紧跟其后的宣判句和收住这一拍的动作不算同义收尾，压稿前先读[经济性遍](references/script-craft.md#81-经济性遍)里的 `SCR-23`。不用统一字数、镜头数或节拍数填模板。
- 用户原文优先；局部修订保留无关段落，“去 AI 味”不抹平作者个性；会改变剧情走向的选择交给用户。

## 按需知识

默认只读本 SKILL 和直接输入；出现下列信号时再按需读取对应引用：

- 阶段边界与规则分级：[阶段契约](references/stage-contract.md)
- 场景标题、对白和生产标签语法，或把现成剧本[规范化](references/screenplay-format.md#7-现有文本的规范化入口)：[剧本格式](references/screenplay-format.md)
- 项目特有的制作稿方言：[制作格式方言](references/production-format-dialect.md)
- 输入含[核心选择](references/script-craft.md#33-把一拍写成艰难选择时两个方向都要活着)、[有限次数/轮次/呼吸/节拍](references/script-craft.md#63-有限单位按完成状态计数)、[精确倒计时](references/script-craft.md#62-倒计时先算动作不要只写数字)或[会改变人物判断的关键物证](references/script-craft.md#52-证据先改变判断再改变关系)：[剧作手艺](references/script-craft.md)
- 过去关系需借对白进入，或区分人物腔调与潜台词：[对白手艺](references/dialogue-craft.md)
- 台词使用非中文或跨语种改写：[非中文台词](references/dialogue-craft.md#62-非中文台词从场景直接写不逐句翻译)
- 声源、留白与 sound bridge：[场景声音戏剧](references/scene-sound-dramaturgy.md)
- 创作者标注需要备选拍法以保住戏剧功能：[可替换拍法](references/substitutable-realization.md)
- 长单集跨上下文续写的最小交接：[场景交接摘要](references/scene-handoff-capsule.md)
- 使用 `[VO]`、外化小说内心独白或落地痛点场景：[能演的不说](references/script-craft.md#44-能演的不说vo内心独白与痛点)
- `short-drama.json` 中 `creator_authority.rhythm_profile` 状态为 `accepted`：[项目节奏档案](references/script-craft.md#64-项目节奏档案)

## 时长估算（按需）

仅当用户问时长，或已接受节奏档案需核对 VO 占比时，才把索引写入系统临时目录。先用第一条命令生成临时路径，再原样填入后两条命令（Windows 无 `python3` 时用 `py -3`；`--speaker` 替换为本集实际说话者）。存在 `short-drama.json` 时可在第三条命令加 `--project short-drama.json`；本集有独立目标时长时再加 `--target-seconds <秒数>`（仅 `duration_estimate.py` 接受这两个参数）：

```text
python3 -c "from pathlib import Path; import tempfile, uuid; print(Path(tempfile.gettempdir()) / ('short-drama-' + uuid.uuid4().hex + '.jsonl'))"
python3 "{技能目录}/scripts/screenplay_index.py" "剧集/EP001/剧本.md" --output "粘贴第一条命令输出的完整路径" --speaker "本集角色一" --speaker "本集角色二"
python3 "{技能目录}/scripts/duration_estimate.py" "剧集/EP001/剧本.md" --index "粘贴第一条命令输出的完整路径"
```

**改稿后重跑**：已写入的索引路径直接重写会报 `already holds an index`。保留原块 ID 需在改稿前存快照，重跑第二条命令时加 `--previous-index <同一路径> --previous-source <旧剧本快照路径>`；重编号则加 `--no-previous` 或换新临时路径。

计数口径：
- `dialogue_characters`（含标点）用于算 `vo_share`（`[VO]` 占全部台词比例；`[OS]` 计入全部台词不计入 `[VO]`）；`voiced_characters`（去标点）按字数语速换算秒数。
- 空格分词外语按词计入 `voiced_words`；中英混排各自按单位计（`OK，走吧` 为 1 词 2 字）；未声明语速的单位列在 `untimed_speech`，数字与缩写按实际读法另估。
- 所有台词有语速时输出 `speech_seconds` 与 `speech_share`，漫剧判读见[漫剧靠声音往前推](references/script-craft.md#45-漫剧靠声音往前推)。
- `[画面文字]`、`[SFX]`、`[转场]` 行数列在 `untimed`；若 `format.pacing` 声明了 `on_screen_text_characters_per_second`，`[画面文字]` 全部文字计入 `on_screen_text_seconds`。画面文字多或唱段长的集需另留读字与演唱时间。
- 无语速或动作速率配置时只报可数事实，不猜秒数。

## 完成

用户点名范围已写入，场景因果连贯，对白与行动可表演，承诺兑现或有意延迟，结尾完成预定功能即完成。资产、分镜、审查与生产仅在用户点名时启动；写完后可转 `$short-drama` 做局部机械核对。

## 安装维护

只有安装、升级或排障时运行 `python3 scripts/selftest.py`。
