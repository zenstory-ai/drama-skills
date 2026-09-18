# 看看它的输出：真实产出节选

[English](real-outputs_EN.md)

这是 README「看看它的输出」一节的完整版。下面每一段都摘自仓库里的文件或一次真实运行，每段开头写明出处。节选只保留讨论到的字段：句内的省略以「……」标出，
省略的整段以单独一行「……」标出，未列出的字段行不另标。

## 一镜穿过四份文档：分镜追得回剧本，造型锁得住

出处：[公开样例 `examples/creator-first/EP001`](../examples/creator-first/EP001/)，按当前文档契约整理，`creator_markdown_check.py` 通过。同一个镜头 `SHOT-EP001-002`，
在四份文档里各管一层。剧本只写发生了什么：

```markdown
桌对面，周薄森把一摞材料推过厚玻璃桌面。纸角碰到江晨指尖。
……
周薄森端起缺口搪瓷茶缸，抿一口冷茶，眉头皱得更深。
……
他把茶缸放回那圈旧茶渍里。
```

`视觉设定.md` 把跨镜必须保持的可见事实写成条目，并给造型上「连续性锁」，锁面就是一条能原样贴进提示词的短语：

```markdown
## 人物 · 江晨
- 识别锚点：长脸、高眉骨、深眼窝、短寸、绷直的肩背。不要改成偶像刘海或宽松潮服。
- 画面代称：Jiangchen
- 连续性锁：LOCK-JIANGCHEN-DRESS《江晨橄榄绿立领常服》（镜头：SHOT-EP001-002、SHOT-EP001-003、SHOT-EP001-007；
  图片提示词项：IMG-JIANGCHEN-SHEET）· 锁面：olive-green stand-collar service dress
```

`分镜.md` 写这一镜的起点和终点，冻结关键帧只画起点那一格；写完之后反查画面里需要认出身份、造型或地理的条目，
回填成「视觉依据」——锁面在关键帧正文里原样出现：

```markdown
## SHOT-EP001-002 · 把空白交到他手里
- 来源：EP001-SC001
- 时长：8s
- 起点：材料在周薄森手下，茶缸停在旧茶渍旁。
- 终点：纸角抵住江晨指尖；周薄森说出“基本还是空白”。
- 输入参考图：无（创作者已明确选择文生视频）。
- 视觉依据：《视觉设定.md》·人物「江晨」（控制：身份、体态、本集造型）；人物「周薄森」（控制：身份、体态、本集造型）；
  地点「副团长办公室」（控制：玻璃桌面、旧茶渍、文件盒书柜、左侧窗光）；道具「缺口搪瓷茶缸」（控制：右侧把手缺瓷、深灰铁胎）。

### 冻结关键帧提示词
> 9:16 vertical two-person medium shot inside an old regiment office, Zhoubosen, a broad square-faced middle-aged officer on
> frame right rests one hand on a stack of papers ……, Jiangchen, a lean young man in olive-green stand-collar service dress,
> seen three-quarter from behind on frame left ……; chipped white enamel mug beside an old tea ring, …… no text, no logo.
```

`视频提示词.md` 把外观压成一句「静态视觉锚点」（锁面原样在内），其余篇幅只写「起点 → 动作 → 终点」里模型能执行的动作和可验证的终点：

```markdown
## MOTION-EP001-002 · 把空白交到他手里
- 分镜：SHOT-EP001-002
- 时长：8s
- 生成方式：文生视频
- 静态视觉锚点：A broad square-faced middle-aged East Asian officer sits frame right and a lean young East Asian man in
  olive-green stand-collar service dress sits frame left across a glass-covered desk in an old office lit from the left.
- 起始帧：周薄森右手压住材料，江晨手停在桌边。
- 终点：材料抵住江晨指尖，周薄森把茶缸放回旧茶渍。

### 可复制提示词
> A broad square-faced middle-aged East Asian officer sits frame right and a lean young East Asian man in olive-green
> stand-collar service dress sits frame left across a glass-covered desk in an old office lit from the left. The middle-aged
> officer pushes the paper stack about twenty centimeters across the glass desk while speaking calmly. The young man does not
> reach for it until the paper touches his fingertip. The officer then lifts the chipped white enamel mug for one small sip,
> frowns at the cold tea, and returns it exactly to the old tea ring. Keep both seated positions, uniforms, file-box wall and
> left-window light stable. Locked camera, restrained natural performance, no object duplication.
```

四份原文：[`剧本.md`](../examples/creator-first/EP001/剧本.md) ·
[`视觉设定.md`](../examples/creator-first/EP001/视觉设定.md) ·
[`分镜.md`](../examples/creator-first/EP001/分镜.md) ·
[`视频提示词.md`](../examples/creator-first/EP001/视频提示词.md)。三层机制的说明见
[跨镜一致性怎么做](character-consistency-across-shots.md)。

## 检查器抓什么：把样例故意改坏两处

出处：同上一节的公开样例。`creator_markdown_check.py` 核对一集五份文档之间可执行的契约。原样跑过；删掉 SHOT-002 视觉依据里的周薄森、
再把 MOTION-003 的时长从 5s 改成 4s，它报的是原因，不是「校验失败」：

```text
$ python3 skills/short-drama/scripts/creator_markdown_check.py examples/creator-first/EP001 --project-root examples/creator-first
OK: examples/creator-first/EP001

$ python3 skills/short-drama/scripts/creator_markdown_check.py <改坏的副本>/EP001 --project-root <改坏的副本>
ERROR: SHOT-EP001-002: 冻结关键帧提示词写到人物「周薄森」，视觉依据没有覆盖；本镜确实看不见时在视觉依据末尾加「；画外：人物「周薄森」」，正文里这个名字不可靠时在《视觉设定.md》写「画面代称：无」
ERROR: SHOT-EP001-003: 分镜时长 5 秒与视频提示词 4 秒不一致；视频提示词只能原样照抄已接受的镜头时长
```

它还核对：每镜「来源」必须以《剧本.md》里真实存在的场景 ID 开头，引文里点到的人物、地点、道具等条目要么在视觉依据里覆盖、
要么声明画外；剧本里每个场景都有镜头承载或写进「未拍场次」；视频提示词的可复制正文里引号内的台词能在《剧本.md》
《视觉设定.md》《分镜.md》里找到（不计标点）；`REF-*` 指向的图片真的在项目里且每张写了用途。

## 对白先估时再定镜长，剪辑再按实测下刀

出处：v0.6.6 时的一次实跑，文首样片就是它剪出来的。分镜阶段把每句对白的发声时间估进镜长，估时依据写在「声音」里；
生成 7 秒是为了给落幅留余量，成片目标另写一行：

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

这一镜按 MiniMax H3 写成图生视频提示词。《视觉设定.md》里江晨作训服的连续性锁「锁面：olive drab field fatigue
uniform with blank collar tabs」原样出现在 `subject_definitions` 里，对白只在 `<d>` 内逐字给出：

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

素材生成出来之后，`剪辑单.md` 每一刀都写画面上发生了什么，字幕逐字取自剧本，时间来自对源素材的实测：

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

`edit_tool.py check` 核对区间自洽、素材是否比剪辑单新、字幕能否在剧本里逐字找到；`verify` 只回报测量数字。
这一趟的 RUN-LOG 里记着这两道机械校验第一次抓到的是写它的人：作者按转写估的字幕窗口超出了区间，被 `check` 拦下；
画幅写成 1080×1920 而素材是 768×1344，被 `verify` 拦下。同一份记录还留着两条测量结论：单遍 `loudnorm` 落在
-12.33 LUFS、偏离目标 3.7 dB，两遍之后才到 -15.79；语音转写把「诸君，且听龙吟」听成「朱军且听龙银」，
所以转写只用来定位时间，字幕从不取自转写。

这次实跑的原件——[剪辑单](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%89%AA%E8%BE%91%E5%8D%95.md)、
[21 镜分镜](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/%E5%89%A7%E9%9B%86/EP001/%E5%88%86%E9%95%9C.md)
与 [RUN-LOG](https://github.com/zenstory-ai/drama-skills/blob/004d945d452f4eb607c5820f437218217af60f6e/evaluations/%E8%AE%A9%E4%BD%A0%E7%AE%A1%E8%B4%A6%E5%8F%B7/reference-run-0.6.6/RUN-LOG.md)——连同八段素材和成片都在提交
`004d945` 里，按仓库规则不再留在当前树。它们按 v0.6.6 的规则写成；用现在的检查器重跑会多报两处（13 个未采用镜号要逐个列出；
SHOT-018「来源」引文里的「发射车」要么进视觉依据、要么声明画外），改法见常见问题[「升级到新版本后要做什么」](../README.md#升级到新版本后要做什么)。

## 原著快评会被自己的全量结果对照

出处：`evaluations/让你管账号/reference-run`（v0.4.2 实跑）。`$short-drama-novel-analyze` 先等距抽 12 章做快评，
再全量拆 20 章；全量做完后回头逐条对照快评，写明哪条被推翻（原表 7 行，节选 4 行）：

| S1 的判断 | 全量结果 | 结论 |
|---|---|---|
| 框架是升级流 + 弱复仇线 | 成立。两次任务闭环，第 13–17 章的对手线不驱动主线 | **未推翻** |
| `screen_ready` 约 67% | 全量 24 个候选集里 19 个 `screen_ready`（79%），5 个 `needs_carrier`，`prose_only` 0 个 | **被推翻（偏保守）**。原因见下 |
| 第 13 章是 `prose_only` | 全量看不成立。第 13 章的功能（对手登场并制造指控）完全可以由剪辑台前的一个人承担；抽样时把「大段网友评论」误当成了功能本身，其实那只是原著的载体 | **被推翻** |
| 分集量级 22–26 | 实际切出 24 | **未推翻** |

> **被推翻的那两条有同一个成因**：抽样阶段容易把「原著用什么写」当成「这个功能能不能拍」。
> 第 13 章满屏都是网友评论，看上去无法影像化，但它承担的功能是对手登场，那完全是可见行动。
> 下一本书的快评应当先问功能，再看载体。

（这次的执行者事先通读过全书，`triage.md` 开头的「执行者声明」写明对照因此偏乐观：它示范的是回填机制，测不出抽样本身的准确度。）
每个分集候选都带 `source_ref` / `chapter_range` 指回索引，`creator_acceptance` 一律
`pending`——分析技能不批准自己的产物。
原文：[`triage.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/triage.md) ·
[`adaptation-value.md`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/adaptation-value.md) ·
[`episode-candidates.jsonl`](../evaluations/让你管账号/reference-run/项目开发/source-analysis/episode-candidates.jsonl)

## 改编契约：每条来源事实写明在哪一集、哪个画面兑现

出处同上。`$short-drama-develop` 把原著里不可更改的事实列成表，每条都要答出「观众从哪个画面得到它」，
答不出就显式延后到第几集（原表 9 行，节选 3 行）：

| ID | 事实 | 本轮兑现 |
|---|---|---|
| F-W2 | **这个世界的新媒体整体落后**：不只军队，全行业粉丝过万的博主都屈指可数 | **EP001 兑现**。可见载体：主角划到平台的行业榜单页，榜首博主的粉丝数是四位数。这个数字与他前世的量级对照，观众自己得出结论 |
| F-C5 | 主角不懂音乐，前世靠请音乐顾问，连有名的曲子都抄不出来 | **EP001 兑现**。可见载体：他写下「配乐」两个字后笔停住，把笔扔开 |
| F-SYS-COST | 装置有代价 | **显式延后到 EP007**（代价第一次可见）。本轮只在 EP001 埋契约条款，不披露 |

金手指的契约在 EP001 之前一次写完并被接受，写不下去时补条款救场按缺陷处理：

> DEV-04 · 使用代价：装置给的每一样东西都会被这个世界当成他自己的才华。这个误认无法澄清——他一旦否认，
> 装置授予的能力在该次表演中失效。首次生效：EP001（代价第一次可见在 EP007）。

原文：[`creative-brief.md`](../evaluations/让你管账号/reference-run/项目开发/creative-brief.md) ·
[`story-engine.md`](../evaluations/让你管账号/reference-run/项目开发/story-engine.md) ·
[`episode-map.jsonl`](../evaluations/让你管账号/reference-run/项目开发/episode-map.jsonl)

## 技能里关于模型的说法，先拿真实生成核对过

出处：`evaluations/model-behavior-probes.md`。技能里每一句「模型会怎样」都对应仓库里留档的一次生成观察：
2026 年 9 月的一批探索性观察（MiniMax H3、Seedance 2.0/2.5、gpt-image-2），摘要留在仓库里、原始媒体在仓库外，
写明样本量、方法和它能支持什么判断（原表 20 行，节选 4 行）：

| 观察 | 样本与结果 | 可用于什么判断 |
|---|---|---|
| H3 中文对白 | 同镜头 20 次，7–108 字、5–13 秒；自然语速约 4.1 字/秒，较密输入赶词或截断 | 作为可覆盖估时参考；50 字/5 秒仍完整，不能划定“超过 9 字/秒必截断”的阈值 |
| 多镜切点 | 要求 4 秒切：H3 3.96/4.04/4.12 秒，2.5 为 3.71/4.29/4.46 秒；2.0 未指定秒数，落在 5.21–5.54 秒 | 测实际切点；不是精度承诺，也不是同语法严格对照 |
| H3 说话人口型 | 同一镜（远处小孩喊一句，近处骑手不说话），三组各 6 次、6 秒。骑手在台词期间仍正对镜头的一组：现行写法 3 次中 2 次口型落在骑手、小孩闭嘴；说话人带音色与在画标注、台词跟在其动作句后、并明写骑手不说话嘴唇闭合的 3 次全部落在小孩…… | 声音没选错，错的是口型落到画里最显眼的正脸……样本小，生成后仍核对口型落在谁脸上 |
| 实际尾帧续接 | 带上一段尾帧 2 次保持开场，纯文字 2 次未保持 | 需要连续画面时优先使用真实产物作参考 |

完整表格与执行路径限制：[模型行为观察摘要](../evaluations/model-behavior-probes.md)。
