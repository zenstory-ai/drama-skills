# MiniMax H3 提示词写法

在目标模型配置明确指定 `target_video_model: minimax-h3` 时使用。推荐配置：

```json
{
  "target_video_model": "minimax-h3",
  "video_prompt_dialect": "minimax-h3",
  "video_prompt_language": "en",
  "native_duration_seconds": {"min": 4, "max": 15},
  "supported_generation_modes": ["text", "first_frame", "first_last_frame", "reference"],
  "audio_generation": "same_pass"
}
```

H3 的分段标签与画面描写使用英文；中文对白保留原文并写成 `<d>[Chinese] 逐字台词</d>`（`<d>` 标签内只放台词正文，不塞入素材标签），前方用固定说话人编号 `(S1)`、`(S2)` 引出。

## 模式互斥与首帧锁图权衡

| 本镜传入素材组合 | H3 模式 | 正文结构 | 核心特性 |
|---|---|---|---|
| 无参考素材（`无（文生视频）` 或 `无`） | Base（文生） | 三段 | 纯文本生成，漫剧/动画需显式强调非实拍 |
| 仅 1 张 `用途：起始帧`（不挂 `reference_audio`） | `first_frame` | 三段 | **严格锁死首帧像素与开场构图** |
| 1 张 `起始帧` + 1 张 `结束帧`（不挂 `reference_audio`） | `first_last_frame` | 三段 | **严格锁死首尾两帧构图** |
| 带有角色/场景/道具参考图、`reference_video` 或 **`reference_audio`** | `reference`（full-reference） | 六段 | 支持多主体与原声音色参考，但**禁用 `first_frame` 首帧硬锁** |

- **首帧锁图 vs 跨镜音色直出的条件权衡**：H3 一旦挂载 `reference_audio`（或搭配多张设定图），就会切入 `full-reference` 模式并**失去 `first_frame` / `first_last_frame` 的首帧硬锁能力**（即使把首帧作为 `<Picture 1>` 传入并标 `fully_preserved`，开场构图仍可能产生轻微漂移）。动笔时按本镜核心诉求二选一：
  - **需要严格锁住分镜首帧构图、站位衔接或复杂三维/漫剧画风起手时**：优先选用 `first_frame` 或 `first_last_frame` 三段模式，不挂 `reference_audio`；跨镜角色音色一致性交给后期配音、TTS 干音贴片或音色转换统一解决。
  - **无需像素级锁死首帧、追求跨镜原声音画同出一致时**：选用 `full-reference` 六段模式挂载 `reference_audio`——仓库内《视频提示词.md》的 `- 参考音频：`（`VID-27`）只绑定《视觉设定.md》中该人物固定的 `- 声音参考：` 借用音色（接口 `usage_type: reference`、`retention_analysis` 标 `reference`，配合正文 `<d>` 台词引文发声；`fully_copy` / `partially_copy` 仅适用于外部平台手动上传单句干音 `relay_external`）。将角色/场景设定图或首帧图作为 `<Picture N>`（`reference_image`）一并传入时，**把首帧图作为 `<Picture N>` 传入须在 `MOTION-...` 的 `输入参考图` 中将该槽位 `用途` 由 `起始帧` 改标为 `构图`**（避免 `production_tool.py` 映射为 `first_frame` 触发与 `full-reference` 的接口互斥报错），且未同挂对应设定条目 `主体` / `造型状态` 参考图时须在正文按 `CON-07` 原字保留生效的 `LOCK-...` 锁定词。
- 本套件不采用仅传尾帧倒推开场的 L2VA 模式；`生成方式` 字段仍只填 `文生视频` 或 `图生视频`。

## Base / 首帧 / 首尾帧（三段结构）

```text
integrated_multimodal_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
```

- `integrated_multimodal_description`：按 `[Shot 1]`、`[Shot 2]` 写画面动作、运镜、说话人与 `<d>[Chinese] 逐字台词</d>`（单镜保留 `[Shot 1]`；多镜切点写 `[Shot 2] At 00:03.500, ...`）。
- `overall_soundscape`：汇总环境底声、动作音效与叹气喘息等非语言人声，不重抄台词。
- `non_diegetic_music`：无画外配乐时明确写 `non_diegetic_music: N/A`，防止模型自行混入背景音乐。
- **漫剧与动画画风防实拍化（`craft_default`）**：H3 文生默认偏向真人摄影，非实拍项目走 Base 文生时需在首句与每个 `[Shot N]` 开头点明画风媒介并排除 `realistic` / `photorealistic`；三维 CG 建议挂定稿首帧走 `first_frame` 模式。首帧模式下人物转身方向偶有不听指令，要求严格接转身方向时优先在首帧摆好朝向或留给后期切点衔接。
- **近景反应镜调校（`craft_default`）**：拍听闻消息后的近景反应时，按「**触发动静 → 用一个准确情绪词点名（如“他瞬间怔住”）→ 给两处在当前景别清晰可见的外露破绽（如眼神定死、拇指悬停半空；嘴角笑意凝固、小臂收紧）→ 1.5 秒内落定保持**」组织。光写抽象情绪词容易五官乱飞，只列零碎动作不点情绪词又容易力度发软。

## Full-reference（六段结构，整条一次提交）

带有 `reference_image`、`reference_video` 或 `reference_audio` 时统一采用六段结构（《视频提示词.md》参考槽位仅登记图片与角色音色参考；挂载 `reference_video` 走外部平台手动提交 `relay_external`）：

```text
subject_definitions: ...
summary: ...
retention_analysis: ...
detailed_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
```

- **素材编号与保留度**：`<Picture N>`、`<Video N>`、`<Audio N>` 按同类素材在本镜的 `顺序` 各自从 1 编号；在 `subject_definitions` 将 `<Picture N>` 绑定到角色或场景主体 `<Subject N>` 后，后续段落（含跨时段再次提及时）统一复用同一 `<Subject N>` 以防脱绑换脸。`retention_analysis` 标明保留程度——视觉用 `fully_preserved` / `partially_preserved` / `attribute_transfer` / `weak_reference`；仓库内绑定角色固定 `- 声音参考：`（`VID-27`）配 `<d>` 台词时统一用 `reference`（即 `usage_type: reference`），而 `fully_copy` / `partially_copy` 仅在外部平台手动上传单句干音（`relay_external`）时使用（背景弱参考用 `weak_reference`）。
- **无首帧近景补面部板与取景说明**：未传起始帧时，在 `detailed_description` 明确写出景别切线与人物占比防被场景图拉成远景；人脸占大头的近景说话镜若只有全身设定图，可增挂同造型面部特写图并在 `retention_analysis` 区分五官与服装职责。超过 9 张 `reference_image` 上限时按本镜景别与视觉焦点取舍（见 [模型与交付配置](model-and-delivery-profiles.md)）。

### 六段示例

```text
subject_definitions: <Subject 1> is the elementary-school boy in <Picture 2>, with a round short black haircut and a light grey-blue hooded jacket over a white inner shirt. <Subject 2> is the home study in <Picture 3>, with the desk against the window wall, a full bookshelf on the left and a warm desk lamp. <Picture 1> supplies the opening framing reference.
summary: The boy leans over an open textbook at his desk and stops when he notices the printed map.
retention_analysis: <Picture 1> (appears in [Shot 1]): fully_preserved - overhead framing, desk edge position and the boy's seated placement guide the opening shot. <Subject 1> (appears in [Shot 1]): fully_preserved - face shape, hair silhouette and jacket layering stay consistent; his pose and expression follow this shot. <Subject 2> (appears in [Shot 1]): partially_preserved - desk orientation, bookshelf wall and lamp position are kept.
detailed_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: N/A
```

### 多镜合生关键帧排布

采用 `full-reference` 多镜合生（4–15 秒内，每切均备有首帧实图排在 `<Picture N>` 最前）时，`GROUP-...` 的 `输入参考图` 须将各切首帧图的 `用途` 由 `起始帧` 改标为 `构图`，以满足单条目最多一张 `起始帧` 的参考槽位校验及 H3 参考槽位语义（单条 `MOTION-...` 改标 `构图` 同时避免 `production_tool.py` 将其映射为 `first_frame` 触发互斥报错；未同挂对应条目 `主体` / `造型状态` 图时，两者均须按 `CON-07` 在正文保留生效的 `LOCK-...` 锁定词），并在 `subject_definitions` 首句写明切点帧对应关系、在 `detailed_description` 同步标 `[Shot 2] At 00:03.000, ...`：

```text
<Picture 1> aligns with the 0.00-second mark as the opening frame of [Shot 1]; <Picture 2> aligns with the 3.00-second mark as the frame of [Shot 2].
```

## 参数上限、对白与 Context-IR

- **素材、画幅、字数与时长上限**：提示词正文上限 **7000 字符**；单次上限为 1 张首帧、1 张尾帧、9 张 `reference_image`、3 段 `reference_video`、3 段 `reference_audio`（音视频单段 2–15 秒且同类总长 ≤15 秒）；分辨率支持 `768P` / `2K`，画幅比例支持 `1:1`、`3:4`、`4:3`、`9:16`、`16:9`、`21:9`（图生与参考模式另支持 `adaptive`，纯文生须显式指定具体比例）。`MiniMax-H3` 的 `duration` 必填且支持 **4–15 秒任意整数**；`MiniMax-H3-Max` 支持 5–15 秒（480P/768P），仅支持文生与首尾帧，不支持 `full-reference`。
- **Context-IR**：提示词扩写接口本身不出视频，调生成接口仍须传 `duration`，启用扩写后核查逐字台词是否被改动。

### 对白说话人绑定与参考音频

- **对白节奏与单喊人名**：按 [台词时长估算](performance-action-timing.md#台词时长估算) 留足发声窗口（H3 中文常速约 4.1 实读字/秒；`first_frame` 模式常有 1.3–2.4 秒起音延迟，排镜长时留出余量或交后期裁除片头静帧）；单喊两字人名发音易漂移，画面可用时交剪辑换音。
- **说话人绑定与参考音频**：口语语种与声线写在 `<d>` 外，并在 `<d>` 前带出该角色在《视觉设定.md》登记的 `- 提示词名称：`（确保同场多人共用短句台词时也能准确判定说话人）：`<Subject 1> (<提示词名称>, S1), the boy on-screen with a clear voice, opens his mouth and says: <d>[Chinese] ...</d>`；同框不说话的正脸角色可补写 `lips remain closed` 防串口型；跨切镜续念可用 `<scenetrans>`，剧本写明半句被打断才用 `<cutoff>`。跨镜锁音色时按上方 `full-reference` 六段结构传入 `reference_audio`（与 `first_frame` 首帧硬锁的条件取舍见上文「模式互斥与首帧锁图权衡」）。

官方依据（2026-09-07 核对）：
- [Base 提示词指南](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt)：对白位置、说话人、语速描述、切镜时间戳与跨镜发声。
- [Full-reference 指南](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt)：六段结构、音频引用与复用语义。
- [视频生成 API](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)：必填时长、型号差异和输入模式互斥。
- [官方 CLI 的 H3 指南](https://github.com/MiniMax-AI/cli/blob/main/skill/h3-video/references/h3-video.md)：音频配合视觉参考，声画配合与生成后检查。
- [Context-IR API](https://platform.minimax.io/docs/api-reference/video-generation-v2-h3-context-ir)：提示词增强和独立的时长输入。
