# 拆解学习阶段契约

本阶段只拥有 `输入/对标/<REF-ID>/` 下的登记、测量结果、转写挂接、拼图、字幕扫描、音轨测量、逐镜小段与
还原层（`还原/` 下单独初始化的还原项目及其保真度核对），以及 `项目开发/对标拆解.md` 里的拆解报告、差距表和
学习记录。它只还原对标，还原结果只写进 `输入/对标/`；不写本项目的剧本、视觉设定、分镜或提示词，不写项目配置；
节奏数值经 `$short-drama-develop` 提出、创作者接受后才进入项目节奏档案。

## 本阶段规则

### `BRK`

| ID | Class | Knowledge |
|---|---|---|
| BRK-01 | structural_invariant | Before measuring, every reference gets a REF-ID, a locator, the permitted use (`study`, `owned` or `licensed`, with the basis recorded for the last two), whether the source may be uploaded to an external model service, and the question this round must answer. Without a registered upload permission, only local measurement runs. |
| BRK-02 | structural_invariant | Reference media, transcripts, contact sheets, subtitle crops, shot clips and the reconstruction project stay under `输入/对标/<REF-ID>/`. Except as BRK-11 allows, no stage of this project reads the reconstruction as its own material, and the report and every handoff carry no reference title, character name, line, or distinctive plot sequence. |
| BRK-03 | reviewed_invariant | Each finding separates direct observation, interpretation and unknown. A number names its method: sample, cut threshold, transcript source. |
| BRK-04 | reviewed_invariant | A mechanism candidate states how many references show it, what audience problem it solves, and where it fails. One reference alone is labelled single-source; a count alone is never a rule. |
| BRK-05 | craft_default | Opening episodes are measured apart from later ones, and adjacent episodes are measured in pairs, so first-episode structure and how an episode picks up the last one stay visible. |
| BRK-06 | structural_invariant | A plan, own footage and a reference sit in one table only when measured the same way; every number states whether it came from a plan or from footage. |
| BRK-07 | reviewed_invariant | A measured value is evidence for a proposal, not a quality threshold. It reaches the rhythm profile only through `$short-drama-develop` and creator acceptance. |
| BRK-08 | structural_invariant | This stage edits no document another skill owns. Each gap is handed to its owner with the evidence and the creator's answer on whether the difference is intended. |
| BRK-09 | reviewed_invariant | A generation check compares versions on the same model and resolution, and on the same aspect ratio unless the aspect ratio is itself the change, with at least two runs per version; visual judgments are made on unlabelled, shuffled frames and name who judged. |
| BRK-10 | taste_option | Aspect ratio, production form and on-screen text conventions seen in references are offered as options tied to their playback surface, never adopted as defaults. When the project's playback surface matches the references', the option may be the recommendation; the creator still makes the choice. |
| BRK-11 | structural_invariant | The reconstruction leaves `输入/对标/<REF-ID>/` only when the registered use is `owned` or `licensed` and a basis is recorded. Leaving means the creator copies the whole reconstruction project out as a new project, or other skills keep working inside it; its files are never merged into this project's episodes. |
| BRK-12 | reviewed_invariant | A reconstruction takes cut times from the measure and line times from burned-in subtitles where they exist, and marks every line, name and shot fact it could not anchor that way as inferred. A model cut that matches no measured or candidate cut is listed for a person to judge, never dropped or accepted automatically. A name needs on-screen or spoken evidence; otherwise the reconstruction uses a role label. |
