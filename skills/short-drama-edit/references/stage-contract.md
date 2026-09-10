# 剪辑阶段契约

本阶段只拥有 `剧集/<EP>/剪辑单.md` 中的 `CUT-...` 项、交付规格章节，以及渲染到
`剧集/<EP>/制作成果/成片/` 的成片与中间文件。它继承镜序、镜头职责、台词原文和已生产的素材
字节，不回写剧本、视觉设定、分镜或视频提示词。

剪辑单不是第六份创作文档。五文档回答「这一集是什么」，剪辑单只回答「已经拿到的这些素材，
哪些帧进成片」。因此它可以整镜不用、可以只取一段素材的中间三秒，但不能改变任何一镜的职责、
台词、起终状态或时长声明——那些改动必须回到拥有它们的上游文档，再重新进入生产。

素材与文档不一致是本阶段的正常输入，不是要修好才能开工的前置条件。上游写「三秒推进到特写」，
生成结果只有前一秒可用，剪辑记录下这个事实并做出取舍；把不一致原样报告回去，比在剪辑里假装
它不存在更有价值。

## 本阶段规则

### `EDT`

| ID | Class | Knowledge |
|---|---|---|
| EDT-01 | structural_invariant | Every `CUT-...` binds one existing `MOTION-...` and one currently readable media file; a cut with no material source cannot exist. |
| EDT-02 | structural_invariant | 入点, 出点 and 时长 are self-consistent (`出点 - 入点 == 时长`), non-negative, and the 出点 does not exceed the source file's measured duration. |
| EDT-03 | structural_invariant | Editing selects and orders existing frames. It never rewrites dialogue, shot purpose, start/end state, or any upstream declared duration; a needed semantic change is reported to the owning document instead. |
| EDT-04 | structural_invariant | A dialogue line that survives into the cut survives whole. A cut boundary may not fall inside a spoken word, and a line's audible span is fixed before its picture in/out is chosen. |
| EDT-05 | structural_invariant | Every character of a burned subtitle comes from the line as written in `剧本.md`; punctuation may follow subtitle convention (a trailing full stop is normally dropped) but not one character changes. Transcription locates a line in time; it never becomes the line. |
| EDT-06 | structural_invariant | Two cuts drawn from the same source file do not overlap in source time. Deliberate repetition is declared as repetition and states why the second appearance still earns its place. |
| EDT-07 | reviewed_invariant | Each cut's in-point and out-point land inside that material's usable band, and 取舍 names what is visible at each boundary rather than citing an abstract need for pace. |
| EDT-08 | reviewed_invariant | Adjacent cuts do not share shot size, camera position and movement direction all at once; two cuts carrying the same information are resolved by dropping one, not by halving both. |
| EDT-09 | reviewed_invariant | Time saved by trimming one cut is not redistributed to others to hit a target duration. A shorter film is a result, not a deficit to refill. |
| EDT-10 | reviewed_invariant | Per-shot generated material carries its own ambience or music bed, so every join is checked for an audible sound-bed hard cut and handled by crossfade, common floor, or an upstream request for a music-free deliverable. |
| EDT-11 | reviewed_invariant | Unused material is recorded with a reason that distinguishes a missing file from an unusable result; the two look identical in the document but route to different owners. |
| EDT-12 | craft_default | The delivered film is loudness-normalized to one declared target, and burned subtitles are the default for vertical short drama. |
| EDT-13 | craft_default | Target duration is intent. The report states the gap between target and actual and why, instead of cutting content to reach a round number. |
| EDT-14 | taste_option | Cut rhythm, whether a beat is held or clipped, and whether a moment repeats are creator choices; the suite records them and does not treat any of them as defects. |
| EDT-15 | structural_invariant | Rendering, duration match and file existence are technical outcomes. None of them may be reported as a statement about whether the film is good; quality goes to review or to the creator. |
| EDT-16 | reviewed_invariant | Generated shots drift in exposure and white balance, so adjacent cuts are compared before delivery and a visible mismatch is corrected. The correction is written in the cut list as a stated creator decision with explicit numbers; the tool never measures a clip and adjusts it on its own, because a correction nobody wrote down is one nobody can review. Shot-matching does not rescue a wrong shot — drifted identity, a changed light direction, or a missing secondary source goes back upstream rather than under a colour correction. |

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
