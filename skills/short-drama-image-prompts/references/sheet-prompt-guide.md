# 美术设定图与视觉定调提示词指南

## 1. 通用编写顺序（`IMG-01` / `IMG-02`）

每条 `IMG-...` 对准 `视觉设定.md` 已确认的条目（待拍板项先不写提示词），按核心辨识特征优先的顺序组织 `### 可复制提示词` 正文（不涉及的项略过，正文不夹小标题或内部编号）：

1. **设定图类型与主体**：开篇点明是角色全身/头肩设定图、场景空镜图、道具设定图、分栏对照设定板还是视觉定调图，以及所画主体。
2. **固定核心外观**：跨造型、跨视角不变的五官骨相、空间结构方位或道具轮廓比例（不用“绝美、大片质感、8K 大师杰作”顶替具体特征）。
3. **本张造型、视角或状态**：当前穿戴层次、观看朝向、时段光线或开合旧损状态。默认一图只画单一共存状态；确需在同一张设定板上展示开合、前后或两处关联分区对照时，开篇明确声明分栏/并列排版（如 `Two-panel location sheet: Panel A ..., Panel B ...` 或 `shown open from behind and closed from above`），标清各栏状态互不串混。
4. **构图版式与尺寸参照**：景别、单图或多视图共享底线并排、普通尺寸参照物。并排展示正/侧/背多视图时，按当前提示词语言按需补充无图注约束（如 `no view labels, no callout arrows, no dimension marks`），防止模型自动生成标尺线与视图文字。
5. **材质、色彩与布光**：面料/器物肌理、主次配色与受光方式。基础设定图优先用看清骨相起伏与服装层次的前侧柔光（避开扭曲五官的底光或把正脸打黑的纯逆光，也不按性别或正反派套刻板光位）；场景图与状态图对齐场内真实光源。
6. **背景、清场与字迹排除项**：干净纯色底或空镜清场要求、印字部位处理，以及针对易画错处的具体排除词（排除词不得与前文磨损或字迹要求自相矛盾）。

## 2. 角色、场景与道具设定图要点（`IMG-03` ~ `IMG-05` / `IMG-10`）

- **角色设定图（`IMG-03`）**：
  - 按下游垫图需求选**全身多视图**（展示头身比例与整套日常服装，各视图同衣同态）、**头肩特写图**（与全身图挂同一张 `外貌` 参考图锁死五官发际线）或**换装/状态图**；避开夸张广角畸变、剧烈运动残影与遮脸道具。
  - 本貌段聚焦脸型比例、眉眼鼻唇特征、发际线与永久印记；剪影感或简练漫剧画风将细碎五官特征转写为发型轮廓缺口、肩背体态与闭合线稿/平涂色块表现。
- **场景空镜设定图（`IMG-04`、`IMG-10`）**：
  - 顺着「机位落点与视线朝向 → 出入口与固定陈设相对间距 → 墙地顶材质与当前光景」落笔（如写清柜台与临河窗平行及间距，防止画成居中孤岛）；画风概括只能省次要摆件，不省本视角必现的门窗与主通道。
  - **全景母图延展多视角**：同一房间需出正反打等多个朝向时，先写一张交代全局分区的母图，分视角图挂母图作 `空间布局` 参考；同一时段天气下各视角保持**主光源位置、冷暖色温主次、明暗反差与灯具亮灭一致**。
  - **清场尺度**：室内外常规空镜不画演员与剧情动作；需借人影衬托宏大建筑体量或市集烟火气时，只留远处极小比例、不挡动线的背景轮廓。
- **道具设定图（`IMG-05`）**：
  - 写清长宽厚轮廓、尺寸参照（刻度垫板、常规桌面边缘，耳坠或门锁可带局部穿戴/安装参照，不默认拉主角的手当尺子）、材质反光与固定磕痕，并把合页、搭扣、封签、钥匙齿纹等关键辨识结构摆到清晰可见的角度。

## 3. 道具字迹处理与参考图边界（`IMG-07` ~ `IMG-09`）

### 道具字迹落地写法（`IMG-07`）

| `视觉设定.md` 字迹规则 | 生图提示词落地写法 |
|---|---|
| 字迹清晰可读 | 直接生成时写准字句原文、语种与印字部位，只排除无关水印杂字（**严禁同时挂 `no text` 等全局禁字词**）；若画风笔触极粗或涉复杂手写签名，改为画好端正干净的印字底面交后期叠字 |
| 只留版式轮廓 | 画清标签、印章或铭牌外框与色块条纹，声明无任何可辨认字符、人名或号码 |
| 表面无字 | 器物表面干净或仅带无字纹样，明确禁字 |
| 字句待创作者拍板 / 只在后期叠加 | 底图对应区域留出干净无遮挡平面或空墙，不在生图阶段编造字句或画入虚拟系统弹窗 |

### 参考图控制范围与杂字核验（`IMG-08` / `IMG-09`）

`- 参考：` 语法与十项固定 `用途` 词表见 `SKILL.md`（设定图常用前七项与 `风格`；同一张图在同一条目只占一个 `REF-...` 图位，次要作用写进 `控制：`）：

- **`控制` 与 `不得控制` 边界**：`外貌` / `主体` 参考图只锁五官骨相与身形（或物件本体形制），不锁死站姿与临时换装；`构图` / `尺度` 只借景别占比、留白或大小比例，不带入原图无关人物与字样；`效果` 只借目标部位伤污或光效形态。
- **实看核验与原图杂字（`IMG-08`）**：未获创作者说明且未实际打开图片核验时，如实标明未核验。负面排除词擦不掉参考图自带的水印、角标、UI 或硬字幕；原图杂字与字迹要求冲突时须先裁切清理、换图或改后期叠字。

## 4. 视觉定调图（Lookdev，`IMG-11`）

开拍前需要校准全剧画风影调时，挑最易暴露画风跑偏的典型画面出少量 `IMG-...` 测试图（不凑固定张数）：

- **人物神态定调图**：绑定核心角色与日常造型，实测五官辨识度、线稿/肤质肌理与微表情表现力；
- **核心场景定调图**：绑定主场景常用朝向，实测空间透视、材质层次与冷暖布光；
- **重头冲突戏定调图**：对准真实剧本场景 ID 与当场知情边界，实测对峙张力、前景遮挡与画面繁简度（不提前泄露未揭晓的真容或底牌）。
- 挂载 `用途：风格` 参考图时，`控制` 只列色调冷暖、笔触肌理、阴影软硬与景深质感，`不得控制` 锁住人物长相、固定陈设、在场人数与道具字样；返修时针对跑偏维度定向调整光比、色温或线条描述即可。

## 5. 英文提示词正例（默认 `prompt_language: en`）

- **角色多视图设定板（`IMG-LUOJING-SHEET · 罗静夜班工装角色板`）**：
  > Full-body character sheet of a tall, lean woman around thirty, front view alongside a head-and-shoulders profile inset on one shared ground line. Narrow oval face, natural gap at the outer tail of her right eyebrow, short wavy black hair, calm guarded expression. Night-shift maintenance uniform: dark forest-green work overshirt with the top button undone over a washed off-white crew-neck T-shirt, a blank round cloth patch stitched on the left chest, a thumb-wide pale brown scorch mark at the right cuff, charcoal straight-leg work trousers and scuffed black ankle boots. Soft even studio key light from upper front-left showing facial bone structure, layered collar and lived-in cotton twill texture, plain neutral light-grey background, consistent facial identity and hair length across both views, no view labels, no callout lines, no dimension marks, no handheld tools, no text, no watermark.

- **场景空镜设定板（`IMG-REPAIR-ROOM · 广播站维修间空镜板`）**：
  > Empty interior location plate of a narrow community broadcast repair room seen from the south doorway looking straight toward the back wall. Along the right wall runs a waist-high worn wooden workbench ending beside a single grey steel fire door on the back wall; along the left wall sit two high horizontal windows above a row of shallow grey metal cabinets, leaving a clear central walkway from the entrance to the fire door. Cool white fluorescent tube lighting overhead with faint dusk blue outside the high windows, concrete floor with subtle cable tray along the skirting board. Eye-level architectural framing, clear spatial depth and furniture alignment, uninhabited empty room, no people, no text, no watermark.
