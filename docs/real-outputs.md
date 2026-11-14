# 看看它的输出：真实产出节选

[English](real-outputs_EN.md)

以下节选来自仓库样例和注明版本的真实运行，各节标明出处。句内省略以「……」表示，整段省略另起一行；未讨论的字段不列出。

## 一镜穿过四份文档：分镜追得回剧本，造型锁得住

出处：[公开样例 `examples/creator-first/EP001`](../examples/creator-first/EP001/)，按当前文档格式约定整理，`creator_markdown_check.py` 校验通过。同一个镜头 `SHOT-EP001-002`，在四份文档里各管一层。剧本只写发生了什么：

```markdown
[OS] 其他军团的人：火箭军？四个号，加起来四个粉吧。

笔记本的扬声器里一片哄笑。桌后，周薄森对着屏幕坐得笔直，脸绷着。桌前，江晨双手撑着桌沿，猛地回神。
```

`视觉设定.md` 把跨镜必须保持一致的外观细节写成条目，并给固定穿着加上「连戏锁」，其中的「锁定词」就是一条能原样贴进提示词的短语：

```markdown
## 人物 · 江晨
- 外观特征：长脸、高眉骨、深眼窝、短寸、绷直的肩背。不要改成偶像刘海或宽松潮服。
- 提示词名称：Jiangchen
- 连戏锁：LOCK-JIANGCHEN-DRESS《江晨松枝绿常服》（镜头：SHOT-EP001-002、SHOT-EP001-003、SHOT-EP001-007、……；
  图片提示词项：IMG-JIANGCHEN-SHEET）· 锁定词：pine-green lapel service jacket
```

`分镜.md` 写清这一镜的起点、动作、终点以及运镜理由，「首帧提示词」只画开场那一格；写完之后对照画面清点需要认出外貌、造型或空间陈设的人物、场景与道具，回填成「出场设定」——锁定词在首帧提示词正文里原样出现：

```markdown
## SHOT-EP001-002 · 四个号，四个粉
- 来源：EP001-SC001
- 时长：4s
- 运镜：缓推，哄笑声最响时开始，越过笔记本背面推向桌后，停在周薄森绷紧的脸；这阵笑是冲他去的。
- 起点：周薄森面对笔记本坐得笔直，右手搭在茶杯旁；江晨双手掌心朝下撑在玻璃桌沿，眼神涣散。
- 动作：哄笑声滚过来，周薄森下颌收紧、腰背又挺直一分；江晨眨了一下眼，眼神猛地聚拢。
- 终点：画面停在周薄森绷紧的脸与屏幕冷光；江晨仍撑着桌沿，留在画右边缘。
- 输入参考图：无（文生视频）。
- 出场设定：《视觉设定.md》·人物「江晨」（控制：外貌、体态、本集造型）；人物「周薄森」（控制：外貌、体态、本集造型）；
  地点「副团长办公室」（控制：清玻璃桌面、杯垫、文件夹书柜、卷帘窗光）；道具「笔记本电脑」（控制：银色轻薄机身、盖角红贴签）；
  道具「玻璃泡茶杯」（控制：双层玻璃杯身、沉底茶叶）。

### 首帧提示词
> 9:16 vertical two-person medium shot in a present-day army arts-troupe office, framed at chest height: Jiangchen, a lean
> young man in a pine-green lapel service jacket, stands mid-ground on frame right …… with both palms flat on the glass and a
> dazed, unfocused look; Zhoubosen, a broad square-faced middle-aged officer, sits bolt upright behind the desk …… facing a
> thin silver laptop whose lid faces the camera, …… his right hand beside a double-walled glass tea tumbler on a dark round
> coaster; …… no text, no logo.
```

`视频提示词.md` 先用一句「开场画面」定住人物与环境（锁定词原样在内），再用「动作过程」和可复制正文写清模型能演出来的动作变化、照分镜定好的运镜，以及画面结果清楚的收尾状态：

```markdown
## MOTION-EP001-002 · 四个号，四个粉
- 分镜：SHOT-EP001-002
- 时长：4s
- 生成方式：文生视频
- 输入参考图：无（文生视频）。
- 开场画面：In a present-day army arts-troupe office with a bookcase of blue document binders ……, a lean young East Asian
  man in a pine-green lapel service jacket stands mid-ground on frame right with both palms flat on the front edge of a
  light-oak desk with a clear glass top and a dazed look, ……
- 起始帧：周薄森对着笔记本坐得笔直，江晨撑着桌沿发懵。
- 动作过程：哄笑滚过来 → 周薄森下颌收紧、腰背再挺，江晨眨眼回神 → 画面推到周薄森绷紧的脸
- 终点：画面停在周薄森绷紧的脸与屏幕冷光，江晨留在画右边缘。

### 可复制提示词
> …… Laughter keeps pouring out of the laptop's small speaker. The seated officer's jaw tightens and his back straightens a
> little more. The young man blinks once and his eyes snap into focus. At the loudest point of the laughter, the camera moves
> steadily forward past the back of the laptop and stops when the seated officer's tight face fills the middle of the frame,
> the young man remaining at the right edge. ……
```

四份原文：[`剧本.md`](../examples/creator-first/EP001/剧本.md) ·
[`视觉设定.md`](../examples/creator-first/EP001/视觉设定.md) ·
[`分镜.md`](../examples/creator-first/EP001/分镜.md) ·
[`视频提示词.md`](../examples/creator-first/EP001/视频提示词.md)。三道防穿帮做法的说明见
[跨镜一致性怎么做](character-consistency-across-shots.md)。

## 检查器抓什么：把样例故意改坏两处

出处：同上一节的公开样例。`creator_markdown_check.py` 自动核对一集五份文档之间的跨文档引用与格式规则。样例原样跑直接通过；如果故意删掉 `SHOT-EP001-002` 出场设定里的周薄森，再把 `MOTION-EP001-003` 的时长从 `2s` 改成 `3s`，它会直接报出具体原因，而不只是笼统的一句「校验失败」：

```text
$ python3 skills/short-drama/scripts/creator_markdown_check.py examples/creator-first/EP001 --project-root examples/creator-first
OK: examples/creator-first/EP001

$ python3 skills/short-drama/scripts/creator_markdown_check.py <改坏的副本>/EP001 --project-root <改坏的副本>
ERROR: SHOT-EP001-002: 首帧提示词写到人物「周薄森」，出场设定没有覆盖；本镜确实看不见时在出场设定末尾加「；画外：人物「周薄森」」，正文里这个名字不可靠时在《视觉设定.md》写「提示词名称：无」
ERROR: SHOT-EP001-003: 分镜时长 2 秒与视频提示词 3 秒不一致；视频提示词时长必须与分镜一致
```

它还会核对：每镜「来源」必须以《剧本.md》里真实存在的场次编号开头；「首帧提示词」「尾帧提示词」与文生视频「开场画面」里点到的人物、地点、道具等条目要么列进「出场设定」、要么注明画外（不扫描「来源」引文）；剧本里每场戏都有对应镜头，或写进「未拍场次」并说明理由；提示词可复制正文里由发声动词或 `<d>` 引出的显式开口台词能在《剧本.md》《视觉设定.md》《分镜.md》里找到（不计标点，不误拦普通招牌或成语引号）；`REF-*` 指向的图片确实存在于项目目录里，且每张都写明了用途。

## 对白先估时再定镜长，剪辑再按实测下刀

出处：v0.6.6 版本时的一次实跑（下方代码块保留该版本的历史字段名），README 中的样片来自这次剪辑。分镜阶段先把每句台词的实读时长估进镜长，估时依据写在「声音」里；生成 7 秒是为了给画面收尾留余量，成片目标时长另写一行：

```markdown
## SHOT-EP001-017 · 诸君，且听龙吟
- 来源：EP001-SC003「江晨（对着空剪辑室）：诸君，且听龙吟。」
- 时长：7s
- 成片目标时长：6.5s。……第 6.5–7 秒是落幅保持的余量；剪辑阶段从末尾裁掉这 0.5 秒。
- 声音：江晨 1 句，可发声 6 字，按 4.1 字/秒约 1.5 秒（文本估计：他平时语速快、句尾干脆，这一句压慢半档，字与字之间留出间隔）。
  生成 7 秒的排布：读完屏幕上的结果 1.4 秒 ＋ 缓慢呼气与松肩 1.5 秒 ＋ 抬眼 0.7 秒 ＋ 说完 1.5 秒
  ＋ 后拉到落幅并停一拍 1.4 秒（成片目标 6.5 秒在这里切）＋ 落幅保持 0.5 秒，末尾这 0.5 秒剪辑裁掉。……
- 输入参考图：PLAN-SHOT-START（顺序：1）· SHOT-EP001-017《本镜冻结关键帧》（用途：起始帧；控制：本镜起始构图……）；
  PLAN-JC-LOOK-C（顺序：2）· IMG-JIANGCHEN-LOOK-C《江晨干泥凌晨作训服状态板》（用途：造型状态；……）；……
```

这一镜按 MiniMax H3 写成图生视频提示词。《视觉设定.md》里江晨作训服的锁定短语 `olive drab field fatigue uniform with blank collar tabs`（v0.6.6 当时记作「锁面」）原样出现在 `subject_definitions` 里，台词只在 `<d>` 标签内逐字给出：

```markdown
## MOTION-EP001-017 · 诸君，且听龙吟
- 生成方式：图生视频

### 可复制提示词
> subject_definitions: <Subject 1> is Jiang Chen, the young man in <Picture 2>: …… he wears a full olive drab field fatigue
> uniform with blank collar tabs with two buttons undone and the collar turned out …… <Picture 1> is the opening composition of this shot.
> ……
> detailed_description: [Shot 1] …… From about 3.6 seconds he speaks, half a step slower than his usual pace with a small gap
> between characters, the line addressed to a room with nobody in it: <Subject 1> (S2) <d>[Chinese] 诸君，且听龙吟。</d> ……
> ……
> non_diegetic_music: N/A
```

素材生成出来之后，`剪辑单.md` 每一刀都写清画面上发生了什么，字幕逐字取自剧本，时间点来自对源素材的实测：

```markdown
# EP001 剪辑单
- 成片目标时长：25.00 秒
- 画幅与帧率：9:16 · 768×1344 · 24fps
- 交付响度：-16 LUFS
- 未采用镜头：MOTION-EP001-001 至 MOTION-EP001-009（理由：文件缺失——本次只生产 SC003 一场）；……

## CUT-EP001-003 · 全押抖手
- 来源：MOTION-EP001-012 · 制作成果/video/MOTION-EP001-012.mp4
- 入点：1.20
- 出点：4.20
- 时长：3.00
- 取舍：入点=按实测发声区间（源 2.04–3.20 秒）前推 0.84 秒余量，手已在鼠标上；出点=句尾收音后留 1.00 秒，提交按钮已高亮
- 字幕：全押抖手

## CUT-EP001-008 · 诸君，且听龙吟
- 来源：MOTION-EP001-017 · 制作成果/video/MOTION-EP001-017.mp4
- 入点：2.00
- 出点：7.00
- 时长：5.00
- 取舍：入点=开头 1.5 秒的凝视与上一段发布前的蓄势重复，整段去掉，从身体前倾进；出点=实测句尾收音在源 6.82 秒，
  出点留到 7.00 秒，身体后靠的姿态变化已完成（素材总长 7.29 秒，可用余量只有 0.29 秒）
- 字幕：诸君，且听龙吟
```

`edit_tool.py check` 核对区间自洽、素材是否比剪辑单新、字幕能否在剧本里逐字找到；`verify` 只输出实测数据。这一趟的 `RUN-LOG` 里记着这两道机械校验第一次拦下的就是写它的人：作者按语音转写估的字幕时间窗超出了片段区间，被 `check` 拦下；画幅写成 `1080×1920` 而实际素材是 `768×1344`，被 `verify` 拦下。同一份记录还留着两条实测结论：单遍 `loudnorm` 落在 `-12.33 LUFS`、偏离目标 `3.7 dB`，跑两遍之后才压准到 `-15.79`；语音转写把「诸君，且听龙吟」听成了「朱军且听龙银」，所以转写只用来定位发声起止时间，字幕一律取自剧本原词。

这次实跑的原件——[剪辑单](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%89%AA%E8%BE%91%E5%8D%95.md)、
[21 镜分镜](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%88%86%E9%95%9C.md)
与 [RUN-LOG](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/RUN-LOG.md)——连同八段素材和成片都在提交 `004d945` 里，按仓库规则不再保留在当前代码目录里。它们按 v0.6.6 的旧规则写成；用现在的检查器重跑除了字段改名以及核对「首帧提示词」「尾帧提示词」和文生视频「开场画面」是否被「出场设定」覆盖外，剪辑单里的 13 个未采用镜号也要逐个列出（不再支持范围简写），旧项目升级改法见常见问题[「升级到新版本后要做什么」](../README.md#升级到新版本后要做什么)。

## 原著快评会被自己的全量结果对照

出处：`evaluations/让你管账号/reference-run`（v0.4.2 实跑）。`$short-drama-novel-analyze` 先等距抽 12 章做快评，再全量拆完 20 章；全量拆完后回头逐条对照快评，写明哪条判断被推翻（原表 7 行，节选 4 行）：

| 抽样快评判断 | 全量拆解结果 | 结论 |
|---|---|---|
| 框架是升级流 + 弱复仇线 | 成立。两次任务闭环，第 13–17 章的对手线不推动主线 | **未推翻** |
| 可直接拍（`screen_ready`）约 67% | 全量 24 个候选集里 19 个可直接拍 `screen_ready`（79%），5 个需补画面表现 `needs_carrier`，纯文字叙述 `prose_only` 为 0 个 | **被推翻（偏保守）**。原因见下 |
| 第 13 章是纯文字叙述（`prose_only`） | 全量看不成立。第 13 章的剧情作用（对手登场并制造指控）完全可以由剪辑台前的一个人演出来；抽样时把「大段网友评论」误当成了剧情作用本身，其实那只是原著的文字写法 | **被推翻** |
| 分集量级 22–26 集 | 实际切出 24 集 | **未推翻** |

> **被推翻的那两条有同一个成因**：抽样阶段容易把「原著用什么形式写」当成「这段戏能不能拍」。
> 第 13 章满屏都是网友评论，看上去没法拍成画面，但它在故事里起的作用是让对手登场发难，这完全能拍成具体动作。
> 下一本书做快评时，应当先看这一章起什么戏剧作用，再看原著用了什么表现形式。

（这次的执行者事先通读过全书，`triage.md` 开头的「执行者声明」写明对照结果因此偏乐观：它示范的是回查核对做法，测不出盲抽本身的准确度。）
每个候选集都带 `source_ref` / `chapter_range` 指回章节索引，`creator_acceptance` 一律填 `pending`——拆解技能不会自行拍板通过，必须留待创作者确认。
原文：[`triage.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/triage.md) ·
[`adaptation-value.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/adaptation-value.md) ·
[`episode-candidates.jsonl`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/episode-candidates.jsonl)

## 原著设定兑现表：每条关键设定写明在哪一集、哪个画面拍出来

出处同上。`$short-drama-develop` 把原著里不可更改的关键设定列成表，每条都要答出「观众从哪个画面看懂它」；首集暂不交代的就明确标出留到第几集（原表 9 行，节选 3 行）：

| ID | 原著关键设定 | 本轮兑现方式 |
|---|---|---|
| F-W2 | **这个世界的新媒体整体落后**：不只军队，全行业粉丝过万的博主都屈指可数 | **EP001 兑现**。画面表现：主角划到平台的行业榜单页，榜首博主的粉丝数是四位数。这个数字与他前世的量级形成反差，观众自己就能看出结论 |
| F-C5 | 主角不懂音乐，前世靠请音乐顾问，连有名的曲子都抄不出来 | **EP001 兑现**。画面表现：他写下「配乐」两个字后笔尖停住，把笔扔开 |
| F-SYS-COST | 装置有代价 | **明确留到第 7 集（EP007）交代**（代价第一次在画面里显现）。EP001 只埋下规则伏笔，暂不揭晓 |

金手指的使用规则与代价在开写 EP001 之前就一次定清并经创作者确认；如果写到后面卡壳才临时打补丁救场，按剧作漏洞处理：

> DEV-04 · 使用代价：装置给的每一样东西都会被这个世界当成他自己的才华。这个误认无法澄清——他一旦否认，
> 装置授予的能力在该次表演中失效。首次生效：EP001（代价第一次可见在 EP007）。

原文：[`creative-brief.md`](../evaluations/让你管账号/reference-run/项目开发/creative-brief.md) ·
[`story-engine.md`](../evaluations/让你管账号/reference-run/项目开发/story-engine.md) ·
[`episode-map.jsonl`](../evaluations/让你管账号/reference-run/项目开发/episode-map.jsonl)

## 技能里关于模型的说法，先拿真实生成核对过

出处：`evaluations/model-behavior-probes.md`。下面摘录 2026 年 9 月的四项摸底实测（MiniMax H3、Seedance 2.0/2.5、gpt-image-2）。摘要记录了样本量、测试做法与适用范围，原始音视频保存在仓库外；这些结果只代表当时的测试表现，不覆盖模型的全部能力或所有调用方式。

| 实测项 | 样本与结果 | 可用于什么判断 |
|---|---|---|
| H3 中文对白 | 同镜头跑 20 次，7–108 字、5–13 秒；自然语速约 4.1 字/秒，字数较密时会赶词或截断 | 作为创作者可随时手改调整的估时参考；50 字/5 秒仍完整念完，不能硬划“超过 9 字/秒必截断”的死线 |
| 多镜切点 | 要求 4 秒切：H3 为 3.96/4.04/4.12 秒，2.5 为 3.71/4.29/4.46 秒；2.0 未指定秒数，落在 5.21–5.54 秒 | 实测切点位置；不是精度承诺，也不是同一套语法的严格对照 |
| H3 说话人口型 | 同一镜（远处小孩喊一句，近处骑手不说话），三组各 6 次、6 秒。骑手在台词期间仍正对镜头的一组：原写法 3 次中 2 次口型落在骑手、小孩闭嘴；给说话人加上音色与在画标注、台词紧跟动作句后、并写明骑手闭嘴不说话的 3 次全部落在小孩…… | 声音本身没配错，错的是口型容易抢到画面里最显眼的正脸上……样本较小，生成后仍需人工核对口型落在谁脸上 |
| 实际尾帧续接 | 挂上一段实际尾帧的 2 次保住了开场衔接，纯靠文字描述的 2 次未能保住 | 需要跨镜连续动作时，优先挂真实生成的尾帧作参考 |

完整表格与实测条件说明：[模型行为观察摘要](../evaluations/model-behavior-probes.md)。
