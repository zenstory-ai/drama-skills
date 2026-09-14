# 剪辑阶段契约

本阶段只拥有 `剧集/<EP>/剪辑单.md` 中的 `CUT-...` 项、交付规格章节，以及渲染到
`剧集/<EP>/制作成果/成片/` 的成片与中间文件。它继承镜序、镜头职责、台词原文和已生产的素材
字节，不回写剧本、视觉设定、分镜或视频提示词。

剪辑单记录素材取舍、时间与后期处理。可以缩短、重排或省略素材，但不回写上游的台词、
镜头职责和状态；确需改变故事内容时交由上游修订。

## 本阶段规则

### `EDT`

| ID | Class | Knowledge |
|---|---|---|
| EDT-01 | structural_invariant | Every `CUT-...` binds one existing `MOTION-...` and one currently readable media file; a cut with no material source cannot exist. |
| EDT-02 | structural_invariant | 入点, 出点 and 时长 are self-consistent (`出点 - 入点 == 时长`), non-negative, and the 出点 does not exceed the source file's measured duration. |
| EDT-03 | structural_invariant | Editing selects and orders existing frames. It never rewrites dialogue, shot purpose, start/end state, or any upstream declared duration; a needed semantic change is reported to the owning document instead. |
| EDT-04 | reviewed_invariant | Dialogue retained in the film remains audibly complete. Picture may cut during a line if the sound remains continuous and the narrative is clear. Separate picture and audio editing requires an external tool; the built-in renderer trims them together. |
| EDT-05 | structural_invariant | When subtitles are requested, every retained spoken line has a cue derived verbatim from the screenplay; punctuation may follow subtitle convention. Transcription locates speech but does not replace the source text. |
| EDT-06 | structural_invariant | Two cuts drawn from the same source file do not overlap in source time. Deliberate repetition is declared as repetition and states why the second appearance still earns its place. |
| EDT-07 | reviewed_invariant | Each cut's in-point and out-point land inside that material's usable band, and 取舍 names what is visible at each boundary rather than citing an abstract need for pace. |
| EDT-08 | craft_default | Check adjacent cuts for unintended visual jumps and duplicated information. Similar framing, deliberate repetition and jump cuts are valid when they serve the accepted narrative. |
| EDT-09 | craft_default | Do not mechanically redistribute trimmed time. Extend another beat only when its performance or readability benefits, and preserve explicit delivery-duration requirements. |
| EDT-10 | reviewed_invariant | Listen to joins for unintended changes in ambience or music. Use an appropriate documented audio treatment when needed; the built-in renderer does not execute prose mixing instructions. |
| EDT-11 | reviewed_invariant | Record unused shots with a reason: missing material, unusable quality, or an intentional narrative omission. |
| EDT-12 | craft_default | The delivered film is loudness-normalized to one declared target, and burned subtitles are the default for vertical short drama. |
| EDT-13 | craft_default | Distinguish a reference target from a required delivery duration. Report the gap and satisfy a fixed requirement or identify the material needed to do so. |
| EDT-14 | taste_option | Cut rhythm, whether a beat is held or clipped, and whether a moment repeats are creator choices; the suite records them and does not treat any of them as defects. |
| EDT-15 | structural_invariant | Rendering, duration match and file existence are technical outcomes. None of them may be reported as a statement about whether the film is good; quality goes to review or to the creator. |
| EDT-16 | reviewed_invariant | Compare shots within the same scene and lighting state using comparable image regions. Record corrections, then inspect the output. Whole-frame averages alone do not establish a mismatch; intentional lighting changes are valid. |
| EDT-17 | structural_invariant | After material is regenerated, re-measure the spoken spans and update its subtitle windows before rendering. The material-mtime warning is a prompt to check, not proof of alignment. |
| EDT-18 | taste_option | Optional grain is declared once in the delivery spec and applied dynamically after assembly by the built-in renderer. Its supported range is a tool limit, not a quality standard; other treatments may use external grading tools. |

规则分级由高到低：`structural_invariant`（结构缺陷，阻断）、
`reviewed_invariant`（需证据判断）、`craft_default`（常用做法，可覆盖）、
`taste_option`（创作者选择，不作缺陷）。创作者已接受的事实优先于本表。

## 与上游阶段的分工

| 问题 | 归属 |
|---|---|
| 这句台词该怎么说 | `剧本.md` |
| 这一镜承担什么、起终状态是什么 | `分镜.md` |
| 这一镜怎么动、生成时说什么 | `视频提示词.md` |
| 这一段素材怎么来的、花了多少钱 | 生产运行记录 |
| **这一段素材哪几帧进成片** | **`剪辑单.md`** |
| 成片好不好看 | 审查，或创作者本人 |

生成结果与上游声明不符时，剪辑记录事实并取舍，同时把不符点名报告；不在剪辑单里修改上游声明
来让它们看起来一致。
