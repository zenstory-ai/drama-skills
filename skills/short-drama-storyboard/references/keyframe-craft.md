# Frozen Keyframe Craft

## 目录

- [Boundary and instant tests](#boundary-and-instant-tests)
- [Purpose](#purpose)
- [Ordered recipe](#ordered-recipe)
- [尾帧：什么时候可以有，以及它换来什么代价](#尾帧什么时候可以有以及它换来什么代价sht-17)
- [Start-only drafting discipline](#start-only-drafting-discipline)
- [Static test](#static-test)

## Boundary and instant tests

- `SHT-05` — Project exactly one accepted shot boundary and bind the exact
  Character/Look, Location/View, and Prop/State variants visible there.
- `SHT-06` — Describe one freezeable instant. Ordered action, expression arcs,
  camera movement, and transforming weather belong to motion, not the keyframe.

## Purpose

Describe one frame that can exist at a single instant and accurately anchors the
accepted shot. A keyframe is not a compressed video prompt.

## Ordered recipe

1. **Purpose:** what the audience must notice now.
2. **Focal subject:** exact asset and variant IDs.
3. **Frame:** shot size, angle, lens intent, aspect-aware composition.
4. **Geography:** Location/View, fixed anchors, foreground/background zones.
5. **Boundary projection:** exact start position, body facing, pose, gaze, hands,
   held props. Give body facing for every person — it fixes which screen side they
   hold and which side the next reverse cuts from; `gaze` does not cover it. Add
   head facing only when it differs from body facing.
6. **Performance instant:** one visible expression/tension state, not an arc.
   Pick a channel the current shot size can actually read — gaze, breath, body
   set, object handling, or a held decision. A wide shot cannot carry an eyelid;
   a close-up cannot carry a full-body retreat. Naming only the emotion ("愤怒")
   leaves the translation to a downstream stage, and the keyframe is the first
   frame — a mistranslation there is wrong from frame one.
7. **Light and atmosphere:** inherit accepted direction/time/weather; add only
   frame-relevant detail.
8. **Text policy:** readable/symbolic/blank/postproduction for visible surfaces.
9. **Exclusions:** contradictions or drift likely for this frame.

Identity and boundary facts remain source references. The keyframe owns focal,
composition, camera/lens, frame-only staging, and exclusions.

### 写完之后过一遍可渲染检查

检查接手的人能否读出当前帧必须保持的可见事实。按构图和镜头职责核对下表，
只补本帧实际需要的内容：

| 检查内容 | 信息缺失时的风险 |
|---|---|
| 每个人在哪、彼此距离多少（"站在他正前方约两步"） | 人物间距逐镜漂移，观众读成换了场地 |
| 构图需要纵深时，前景、中景、背景分别承载什么 | 层次不明，主体与背景混在一起 |
| 视线该落在哪（本镜的视觉重点） | 画面平均用力，观众不知道该看谁 |
| 构图方式与景别 | 同一场每镜构图随机，剪不到一起 |
| 机位在轴线哪一侧、俯仰角度、焦段意图 | 越轴；正反打方向对不上 |
| 光从哪来、什么质感 | 同场光位逐镜跳变 |
| 每个在场者的姿态、朝向、手部、持物 | 下一镜接不住，道具凭空易手 |
| 与上一镜连续的关键状态在本帧具体是什么 | 只写“同上”，当前正文无法独立说明状态 |

连续性核对时可以与上一镜比较；可复制正文仍须写出当前帧的位置、持物和其他必要状态，
不能用“与上一镜相同”代替执行端本次需要的事实。

**`craft_default`：一件事只说一次。** 合并能自然衔接的句子，删除重复事实和不帮助确定画面的铺垫。
不设通用字数门槛；保留当前帧所需的身份、空间、构图、光线、文字和连续性事实。

以下合成片段示意构图与静态事实的组织方式：

```text
竖屏 9:16 中近景。机位在轴线左侧、高约一米二，平视略低约五度，中焦 50mm。前景是长凳
扶手与半张湿报纸（占下缘约六分之一）；中景是两人对峙；背景是虚焦的候车牌。三分构图，
她落在右三分线上。她：坐长凳右端，双手交叠压膝，身体朝向正前，视线落在对方鞋尖，
无持物。人物乙：站她正前方约两步、略偏画面左，双手插袋，身体朝向她，头略偏向出口。
光自画面右上顶棚缝隙斜下为主光（硬），左侧留暗，无补光。视觉重点在她压膝的双手。
排除：无动作过程，无雨丝拖影。
```

Every visible entry the finished frame carries is listed in the shot's required
`视觉依据` field, resolving to a real `视觉设定.md` entry; an `IMG-...` prompt item
in `图片提示词.md` is a separate axis and does not stand in for it, and
`视觉设定.md` itself does not define `IMG-...` IDs. Write that list from the
finished frame, not from the shot's intent — the subject that gets missed is the
one that entered the composition while the frame was being written. A frozen frame may determine whether the surface
is legible in this composition; it may not replace the exact wording or policy
with an untraceable prose instruction. If the policy is still undecided, say so
instead of inventing a hidden candidate state.

## 尾帧：什么时候可以有，以及它换来什么代价（`SHT-17`）

默认每镜一张首帧，冻结 `start_boundary`。交付工作流需要首尾帧时，再补一张投影
`end_boundary` 的尾帧；两帧之间的运动仍按分镜边界和运动提示词实现。

**`structural_invariant`**：《分镜.md》的首帧与收尾关键帧分别指向同一镜头已接受的起点与终点。
**尾帧是 `end_boundary` 的投影，
不是新的终点事实**——它与首帧对 `start_boundary` 的关系完全一样：可以决定这一帧怎么构图、
用什么景别镜头、光怎么落，不能决定人在哪、手里有什么、看着谁。尾帧与镜头终点不一致时，
错的是尾帧。

每镜的关键帧数量**不是固定的**。默认一张首帧；只有当交付工作流真的要消费尾帧时才加一张，
不为凑齐而画。补尾帧不改变 `SHT-10`：首帧仍然只能写 start 事实，尾帧只能写 end 事实，
两张各自守自己的边界，不互相借用。

**代价要说清楚：交出一对首尾帧，等于把两帧之间的运动交给了执行端插值**。 而运动路径本来
是运动规格拥有的东西。所以选了首尾帧接续的镜头，其运动规格不是"照旧再写一遍"，而是被
两端夹住了：它仍然要写清中间必须发生什么（动作顺序、对白落点、摄影机行为），但要意识到
执行端会优先满足两端的画面一致性。因此——

- 中间必须被看到的动作**不要只靠插值兑现**。如果一个动作是本镜存在的理由，两端之间没有
  任何东西保证它会发生，就该拆镜，或者让该动作落在其中一端。
- 两端差异越大，插值越自由，中间越不可控。首尾帧接续适合"状态改变清楚、路径无所谓"的
  镜头（转身、递交完成、坐下），不适合"路径本身是戏"的镜头。
- 终点报告仍然对照镜头 `end_boundary`，不对照尾帧。尾帧只是它的投影，不能自证到达。

## Start-only drafting discipline

**`SHT-10 · reviewed_invariant`**: rendered keyframe prose may contain only facts
from the boundary that frame declares. 首帧写进任何由运动或终点首次产生的事实是漂移；
尾帧写进在它之前就已经消耗掉的事实同样是漂移。两帧各守各的边界，不互相借用。

关键帧默认投影镜头起点，不能直接选取“本镜最有戏的时刻”。为避免提前写入终点事实：

1. 先明确本帧冻结 `SHOT-...` 的起点，草拟正文时暂不读终点与运动描述；
2. 只填起点已成立的位置、姿态、目光、双手、持物和可见状态；
3. 再对照终点，找出动作后才产生的事实，确保它们未进入起始关键帧正文；
4. 写完 Markdown 后从自然语言反向提取手位、持物、目光和可见状态，与镜头起点再比一次；
   不能只看条目说明而忽略真正交付的正文。

反例：start 是“右手空置、看对方”，end 是“右手握铃绳、看门”。冻结帧写
“手已握铃绳”会提前写入终点事实，属于边界漂移。

## Static test

Ask: could a still photographer capture every described fact at once?

Move these to motion:

- ordered verbs (先、再、随后、最终);
- expression changing from A to B;
- camera push/pan/track over time;
- entering/leaving/turning/reaching sequences;
- dialogue delivery arc or sound progression;
- light/weather transforming during the shot.

A single held pose may imply tension, but it must not require several moments.

## Prompt economy

Do not restate full character or location 设定集s. Bind accepted variants and
repeat only facts the frame needs to prevent ambiguity: distinguishing anchor,
current Look, crucial spatial anchor, held prop, light direction, text state.

Generic “cinematic, 8K, masterpiece” language cannot replace subject identity,
geography, composition, or continuity.

## Failure examples

- incompatible Looks appear in the same frame;
- “turns, runs, then looks back” appears in a still;
- the start hand/prop differs from the shot boundary;
- background changes location identity or orientation;
- light direction resets without source change;
- readable evidence is paired with no-text;
- prompt lists subjects but not their spatial relationship;
- framing has no focal hierarchy.
- structured projection matches start but rendered prompt describes a fact that
  first appears in the shot end or motion.
