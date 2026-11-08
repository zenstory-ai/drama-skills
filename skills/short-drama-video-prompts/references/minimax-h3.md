# MiniMax H3 提示词方言

只在目标档案明确写 `target_video_model: minimax-h3` 时使用。推荐档案：

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

H3 的结构字段与描述用英文；中文对白保留原文并写成 `<d>[Chinese] 逐字台词</d>`，由稳定说话人 ID `(S1)`、`(S2)` 引出，不在对白前加外语或语气词。

## 模式选择（由槽位 `用途` 组合决定）

| 本镜绑定的参考图（`REF-...` 与 `PLAN-...` 同权） | H3 模式 | 正文结构 |
|---|---|---|
| 无图（创作者已明确选择文生视频） | Base（文生） | 三段 |
| 仅 1 张 `用途：起始帧` | `first_frame` | 三段 |
| 1 张 `用途：起始帧` + 1 张 `用途：结束帧` | `first_last_frame` | 三段 |
| 其他任何组合（起始帧与身份/地理/道具图并存，或仅有后者） | `reference`（full-reference） | 六段 |

- 本套件不使用只给尾帧推断开场的 L2VA 模式（`结束帧` 只在同时绑定 `起始帧` 时出现）。
- **首/尾帧与 full-reference 互斥**：「起始帧 + 角色板 + 场景板」或连续段「上一段实际视频 + 实际尾帧」统一走 full-reference，起始帧或实际尾帧以 `reference_image`（`<Picture 1>`）送入，上一段实际视频以 `reference_video`（`<Video 1>`）送入。「生成方式」字段仍只写 `文生视频` 或 `图生视频`。

## Base / 首帧 / 首尾帧（三段结构）

```text
integrated_multimodal_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
```

- `integrated_multimodal_description`：按 `[Shot 1]`、`[Shot 2]` 写画面、动作、说话人、逐字对白与同步声音（单镜也保留 `[Shot 1]`；首镜不加时间戳，后续切镜写 `[Shot 2] At 00:03.500, ...`）。
- `overall_soundscape`：汇总环境声、物理音效与非语言人声，不重复对白；无对白镜优先描述所需声轨（嘴部状态按实际表演写，必要时可补“无对白”）。
- `non_diegetic_music`：无非画内配乐时显式写 `non_diegetic_music: N/A`（省略该层易导致模型自行补乐）。
- **文生模式守住非实拍画风（`craft_default`）**：H3 文生偏向真人实拍。非实拍文生须在首句（如 `A 2D hand-drawn anime animation ... not live-action, not photographed, no real actors`）与每个 `[Shot N]` 后重复声明媒介并排除 `realistic`/`photorealistic`；三维 CG 文生仍易滑向真人，建议每个容器开场挂一张已接受画风的三维起始帧走首帧模式。
- **转身与出画方向（`craft_default`）**：首帧模式下 H3 常忽略提示词中的转身方向。需靠转身或出画方向接戏时，优先在起始帧先摆出朝向或多抽候选挑选，挑不出时交 `$short-drama-edit` 在转身前切走。

## Full-reference（六段结构，一次整体提交）

任何 `reference_image`、`reference_video` 或 `reference_audio` 进入任务时使用六段英文结构（同一 `MOTION-...` 的六段作为一条完整提示词一次提交）：

```text
subject_definitions: ...
summary: ...
retention_analysis: ...
detailed_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
```

### 素材编号与保留职责

- `<Picture N>`、`<Video N>`、`<Audio N>` 按同类素材在本镜「输入参考图 / 参考音频」中的 `顺序` 从 1 递增编号，`<Subject N>` 指向可复用主体（`REF-...` 与 `PLAN-...` 正文写法完全一致）。
- `subject_definitions` 绑定主体与标签（`<Subject 1> is the ... in <Picture 2>, with ...`）；`retention_analysis` 写明保留强度与出现镜次（视觉用 `fully_preserved` / `partially_preserved` / `attribute_transfer` / `weak_reference`，音频用 `fully_copy` / `partially_copy` / `reference` / `weak_reference`）。
- **各用途边界**：`起始帧` 管开场构图与姿态；`身份` 管跨镜长相与体态；`地理` 管空间关系；`造型状态` 管服装与损污。无起始帧时地点图易拉宽景别，须在 `detailed_description` 写明具体取景边界（见[目标模型能力档案](target-model-profile.md#参考条件方式)）。
- **近景/特写加挂面部识别板（`craft_default`）**：无起始帧且脸占画面大块的近景/特写/说话镜，若身份槽只有全身板，由 `$short-drama-image-prompts` 加出一张同 Look 面部识别板作为第二个 `用途：身份` 槽，在 `subject_definitions` 同时绑两张图（`<Subject 1> is the woman in <Picture 1> and <Picture 2>...`）并在 `retention_analysis` 分工五官发际与体态服装，生成后核对五官与痣位。

### 完整例子

```markdown
- 输入参考图：REF-SHOT002-START（顺序：1）· 剧集/EP001/制作成果/images/SHOT-EP001-002.png《SHOT-EP001-002 起始帧》（用途：起始帧；控制：起始构图、双人站位；不得控制：尚未发生的动作、终态）；REF-XIAOYU-SHEET（顺序：2）· 输入/参考图/小雨定妆.png《小雨定妆照》（用途：身份；控制：脸型、发型剪影、身高比例；不得控制：构图、动作、表情）；REF-STUDY-PLATE（顺序：3）· 输入/参考图/家庭书房.png《家庭书房场景图》（用途：地理；控制：书桌方位、书架墙、灯位；不得控制：人物身份、动作、道具状态）
```

```text
subject_definitions: <Subject 1> is the elementary-school boy in <Picture 2>, with a round short black haircut and a light grey-blue hooded jacket over a white inner shirt. <Subject 2> is the home study in <Picture 3>, with the desk against the window wall, a full bookshelf on the left and a warm desk lamp. <Picture 1> is the opening composition of this shot.
summary: The boy leans over an open textbook at his desk and stops when he notices the printed map.
retention_analysis: <Picture 1> (appears in [Shot 1]): fully_preserved - overhead framing, desk edge position and the boy's seated placement open the shot exactly as supplied. <Subject 1> (appears in [Shot 1]): fully_preserved - face shape, hair silhouette and the jacket-over-shirt layering stay identical; his pose and expression are set by this shot, not by <Picture 2>. <Subject 2> (appears in [Shot 1]): partially_preserved - desk orientation, bookshelf wall and lamp position are kept; the props on the desk follow this shot.
detailed_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: N/A
```

### 多镜容器：每切一张关键帧

**`taste_option`**：相邻镜头可装进同一次 full-reference 生成，每切挂各自的已接受关键帧。
**`craft_default`**：须同时满足：① 每个成员镜头都有已接受起始帧图片（缺一张即逐镜生成）；② 成员时长之和在 4–15 秒内，按[交付形态](delivery-profile.md)记账；③ 共用一份参考清单（各切关键帧按切序排最前，共用身份/地点图排后面）。在 `subject_definitions` 前首行写对齐句：

```text
<Picture 1> aligns with the 0.00-second mark as the opening frame of [Shot 1]; <Picture 2> aligns with the 3.00-second mark as the frame of [Shot 2]; <Picture 3> aligns with the 6.00-second mark as the frame of [Shot 3].
```

`detailed_description` 后续各切写 `[Shot 2] At 00:03.000, ...` 与对齐句一致（只挂首切关键帧会导致后续切点偏离或出现多余切镜）。文生与首帧模式直接用 `[Shot N]` 切多镜，无需逐切关键帧。

## 素材上限与时长

- **素材上限**：单次最多 1 张首帧、1 张尾帧、9 张 `reference_image`、3 段 `reference_video`、3 段 `reference_audio`（音视频每段 2–15 秒且各自合计 ≤15 秒）；分辨率 `768P` 或 `2K`。内置生产选择器尚不支持绑定续接视频，投产按[交付路线的接口边界](delivery-profile.md#从已生成结果续接)停靠，不把视频塞进图片 `REF-...`。
- **时长（`structural_invariant`）**：`MiniMax-H3` 的 `duration` 必填，取 4–15 的任一整数秒（非仅 5/10/15 三档）。`MiniMax-H3-Max` 为 5–15 秒、480P/768P，仅支持文生和首/尾帧，不支持 full-reference。

## 对白、说话人绑定与参考音频

- **对白容量与延迟开口（`craft_default`）**：按[对白预算](performance-action-timing.md#对白预算)核对发声时长（H3 中文常速约 4.1 可发声字/秒）。首帧模式下模型常在约 1.3–2.4 秒才出声，排镜长须计入前置等待（静止等待可由 `$short-drama-edit` 剪除）；单喊两字人名发音易漂移，画面可用时交剪辑换音。口语语言、声线与语速写在 `<d>` 外，`<d>` 内只放 `[Chinese] 逐字台词`。同次生成内跨切发声可用 `<scenetrans>`；剧本要求尾字截断才用 `<cutoff>`。
- **说话人绑定与同框闭嘴（`craft_default`）**：说话人首次出现时在 `<d>` 外交代画内/画外与音色，台词紧跟其可见动作句：`<Subject 1> (S1), the boy on-screen with a clear high voice, opens his mouth and calls out: <d>[Chinese] ...</d>`。同框有不说话的正脸时须显式写闭嘴：`The messenger does not speak; his lips remain completely closed.`（防止口型误落到近景不说话者；分镜能安排不说话者背身或出画时更稳）。
- **跨镜音色与参考音频（`craft_default`）**：仅靠文字描述锁不住跨镜同一嗓音。角色在两镜以上开口时须绑定《视觉设定.md》中的参考音频（走 full-reference，配合至少一张图或视频）：只参照音色/情绪用 `reference`；原样复用整轨用 `fully_copy`，复用局部对白层加环境声用 `partially_copy`。
- **Context-IR**：H3-Context-IR 只做多模态提示词增强、不生成视频且仍需调用方传入 4–15 秒 `duration`，启用后仍须核对增强后的逐字台词与时长容量。

官方依据（2026-09-07 核对）：
- [Base 提示词指南](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt)：对白位置、说话人、语速描述、切镜时间戳与跨镜发声。
- [Full-reference 指南](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt)：六段结构、音频引用与复用语义。
- [视频生成 API](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)：必填时长、型号差异和输入模式互斥。
- [官方 CLI 的 H3 指南](https://github.com/MiniMax-AI/cli/blob/main/skill/h3-video/references/h3-video.md)：音频配合视觉参考，声音对齐与生成后检查。
- [Context-IR API](https://platform.minimax.io/docs/api-reference/video-generation-v2-h3-context-ir)：提示词增强和独立的时长输入。
