# 首尾帧构图、受光与漫剧定格写法

首帧与尾帧提示词用于定格镜头开场（`起点`）或收尾（可选 `终点`）那一瞬间的静态画面，并对齐本帧实际入画的人物与造型、地点与视角、道具与状态（`SHT-05`、`SHT-06`、`SHT-21`）。

## 1. 五步编写顺序与连戏垫图策略

按画面可见要素依次组织正文（不写「机位架在轴线左侧」「反打镜」等生图模型看不懂的分镜调度黑话）：

1. **画幅、取景与焦段透视**：画幅比例、景别切点、俯仰高度、精准焦段与透视感（如 `9:16 vertical medium close-up, 50mm lens at chest height, slight low angle`）及视觉焦点。
2. **空间层次与陈设尺度**：所在房间与观看朝向、同框 `固定陈设`、前中后景关系、人物步距与家具落在人身上的高度参照（如木柜台齐成年人腰带）。
3. **人物落位与身体朝向**：入画角色站坐位置、**胸口身体朝向与转头方向分开写清**、四肢姿态、视线落点与手中物件。跨镜延续姿态直接写出具体画面，不写“同上”。
4. **定格神态与肢体细节**：写当前景别看得见的静态神态（下颌绷紧、指节攥白、目光钉在鞋尖），不写空泛心理词或连续变化过程。
5. **实景光线、画风与排除项**：沿用本场主光方向、道具字迹规则与全集统一画风词，只针对易抢跑终点或画错处的隐患写具体排除项。

### 连戏垫图与同机位派生策略（`craft_default`）

- **同机位切景或微调优先基于上一镜首帧派生**：相邻镜头处于同一机位朝向（如双人中景推切单人近景、固定机位微调表情手势或接续下一拍动作）时，**允许且推荐直接拿已确认的上一镜首帧（或定调帧）配合指令改图模型派生下一镜首帧**，最大限度锁死人物脸型、衣褶与背景陈设连戏。
- **反打翻面或大换背景朝向时改挂场景图**：一旦正反打越过桌面换到对面背景、或大角度更换观看方向，不再拿上一镜反面首帧硬改背景（否则门窗桌椅极易扭曲错位），改挂对应观看朝向的场景空镜图（`用途：空间布局`）配角色设定图（`用途：外貌`）。近景被全景场景图拉远成全身时，把取景切点（如 `framed from mid-chest up`）提前写硬，或撤掉全景图改写浅景深虚化背景色块。
- **按本镜入画范围裁剪共用段落**：把整场共用的比例、连戏或视角说明拼进每镜正文前按本镜裁剪，删掉本镜不在场的人和看不到的陈设，并写明本镜只有哪些人（模型会把段落里顺带提到的旁人画进画面）；**特写和道具插入镜不带比例与房间描述**。

英文首帧正例（暴雨初歇的公交候车亭，科室主任陈默站在长凳前劝实习医生林舒顶锅签字，默认 `prompt_language: en`）：

```markdown
### 首帧提示词
> 9:16 vertical two-person medium close-up, 50mm lens at chest height with a subtle five-degree low angle. Under a rain-wet bus shelter at night, the wet metal bench armrest and half a damp folded newspaper sit in the lower foreground, a blurred illuminated route lightbox in the background. Linshu sits on the right end of the bench on the right third line, torso facing forward, hands folded tight over her knees, gaze lowered onto Chenmo's leather shoe tips, a closed black long-handled umbrella leaning against the right armrest. Chenmo stands two steps in front of her on frame left, hands in his dark suit trouser pockets, body squared toward Linshu while his head turns slightly toward the street. A hard cool-white streetlight beam cuts down from upper frame right through the canopy seam, leaving the left side in deep shadow, realistic motion-comic keyframe, crisp silhouette separation, no hand-reaching motion, no rain streaks, no text, no watermark.
```

## 2. 实景受光方向与漫剧专属视觉词条

### 光源来向与受光面连起来写

- `视觉设定.md` 地点条目定好窗户与灯具方位后，同一场连续戏跨镜守住统一的主光方向与冷暖主次。角色设定图采用中性平柔光只是为了展示五官衣着，进场入镜后人物面部的明暗交界必须改按房间真实光源方向落笔——直接写明主光从画面哪一侧打来、亮哪半边脸、暗部保不保留眼神光（如 `cool window light from frame left lighting the left side of his face, soft shadow across the right cheek with clear catchlights`），不用“氛围感拉满”等空话顶替光位。
- 暂不露真容的悬念镜，顺着房间原有窗光或门缝光把人物摆进逆光剪影或背光暗区，不临时乱改房间主光源位置。

### 漫剧专属画面词条（`taste_option`）

项目采用二维漫剧或条漫视觉方向时，除常规构图光影外，可按画风底子选配以下漫剧专属表现词（正文中只写具体视觉效果，不写分类标签）：

- **线稿与平涂色阶**：清晰闭合线稿（`clean closed line art`）、赛璐璐硬边二分阴影（`cel-shaded hard-edge two-tone shadows`）、精简平涂色阶（`flat color blocks with simplified tonal steps`，弱化琐碎写实毛孔杂纹）。
- **国风墨韵与港漫颗粒**：毛笔墨线粗细顿挫与衣摆水墨飞白（`expressive brush-ink line weight with dry-brush feibai strokes`）、分层水色罩染留白、复古网点纸颗粒与密集排线暗部（`halftone screentone shading and dense cross-hatching`）。
- **定格张力与前后分离**：起手蓄力或击中瞬间的顺向速度线残影（`directional speed lines`）、大透视张力伸展与飞溅碎屑定格；遇浓密雨雾、剑气或电弧光效时，写明光效粒子不糊住人物五官轮廓、手部与器械剪影干净分离。

## 3. 尾帧适用情形与防串戏守则（`SHT-06` / `SHT-10` / `SHT-17`）

- **尾帧按需补写与插值取舍（`SHT-17`）**：每镜默认只写 `### 首帧提示词` 定格镜头 `起点`；仅在后续视频生成确需锁死收尾构图时补写 `### 尾帧提示词` 定格镜头 `终点`（内容与 `- 终点：` 字段严格一致）。同时挂载首尾双帧由模型自动插值过渡，适合转身站定、递物落定、落座完毕等起止清晰的镜头；中间过程含复杂招式或精细手法的镜头，默认优先用单首帧配动作提示词或拆镜处理（`craft_default`）。
- **单帧定格防串戏（`SHT-06`、`SHT-10`）**：`### 首帧提示词` 只画 `起点` 已到位的姿态与物件状态，绝不提前画入半途或 `终点` 才发生的结果（如起点手垂身侧、终点握住铜铃绳，首帧严禁写成已握绳）；`### 尾帧提示词` 同样删净开场已消失的旧姿态。带先后顺序的过程词（先、随后、接着）、神情渐变与推拉摇移运镜一律留给 `$short-drama-video-prompts`。
