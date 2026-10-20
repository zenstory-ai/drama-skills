# Agent Note: 旧 JSON 检查器移出技能，创作链路只剩一套检查口径

Status: implemented

## Problem

[退役旧创作模板](2026-10-15-retire-legacy-authoring-templates.md)只移走了作者模板，按当时的判断保留了运行时检查器与其合成示例。结果技能目录里仍随发货八个只读旧 JSON/JSONL 的检查器，以及十余份无人引用的 JSON(L) 示例。当前 SKILL 与 references 规定单集链路只写五份 Markdown、审查不建 sources/record ID，而这些脚本要求的正是被禁止的输入：`review_check.py` 只认 fatal/error/warning/note 和 JSON verdict，审查技能用 blocker/major/minor/note 的 Markdown。

社区创作者用第三方工作流套这些技能时反馈“审核脚本会自相矛盾”。一个会枚举 `scripts/*_check.py` 的 agent 拿到的是两套互斥的检查口径。

同一轮核对还发现三处当前链路内部的矛盾：场景 ID 有三套正则，`creator_markdown_check.py` 接受 `S01-EP001-SC001` 而写作阶段的 `screenplay_index.py` 拒绝它；`creator-documents.md` 里配对的 SHOT/MOTION 示例照抄就会被检查器拒绝（输入参考图不一致且仍待补，文生视频却写了关键帧起始帧）；storyboard、video、review 的若干 references 仍用 `start_boundary`/`end_boundary` 字段名，而模板字段是「起点」「终点」。

## Decision

- `asset_check.py`、`image_prompt_check.py`、`storyboard_check.py`、`motion_timing_check.py`、`container_check.py`、`music_spec_check.py`、`review_check.py`、`voice_sheet_check.py` 及其最小示例移到 `tests/legacy/<技能名>/`，保持原相对布局，只服务 golden-project 与 reference-run 两个历史回归。只测试这些检查器的五个技能 selftest 删除；写作技能的 selftest 去掉配音表部分后保留。
- assets、storyboard、video-prompts、review 下无消费者的 JSON(L) 示例删除；location-view 与 prop-state 两份仍被引用完整性测试读取，移入 `tests/fixtures/authoring-records/`。只断言已退役模板形状的测试一并删除。
- assets、image-prompts、storyboard、video-prompts、review 五个技能现在只有知识文档，SKILL.md 不再有「安装维护」selftest 说明，独立运行测试的 selftest 名单同步收窄。
- `screenplay_index.py` 场景标题接受任意连字符前缀（集号取 `EP` 段），`edit_tool.py` 的场景 ID 与 `creator_markdown_check.py` 用同一形状。
- `creator-documents.md` 的 SHOT-EP001-001 与 MOTION-EP001-001 改为一致的文生视频示例，起始帧写可见状态；待补参考图的写法仍在回退格式示例中展示。references 中的旧字段名改为「起点」「终点」。
- SHT-16/17、VID-04/13/15 的规则分级不变；creator-first 链路里由审查按 rubric 核对。
- 审查 finding ID `REV-001` 与规则 ID `REV-01` 同前缀的问题不改：创作台按 `REV-` 解析审查发现，改格式会让既有项目的审查读不出来，而三位与两位编号本身可区分。

## Alternatives considered

- **在 `creator_markdown_check.py` 里把五条算术不变量按 Markdown 全部重建**：机械校验最强，与结构化时代对齐。未采用：五文档里没有分段时长与交付容器的可解析字段，重建要先发明新字段，违背“用户没要求的字段不为完整而补造”；算术不变量由审查核对已足够，等真有字段需求再按条补。
- **连同 golden-project 与 reference-run 一起删除**：仓库里不再有任何旧格式。未采用：两者是现有发布闸门与回归的来源，删掉需要先有一份五文档格式的完整实跑来替代，那是独立的一轮工作。
- **保留检查器，只在脚本开头标“旧格式”**：改动最小。未采用：agent 枚举脚本时不读注释，矛盾仍在；上一轮已按用户要求取消兼容。

## Consequences

- **收益**：创作者与第三方工作流在技能里只会遇到 `creator_markdown_check.py` 一套结构检查；审查技能不再附带与自身格式相反的脚本；带季前缀的项目在写作、跨文档检查与剪辑三处读到同一个场景 ID。
- **代价**：五个技能失去 selftest；`tests/test_workflow_evaluation.py` 的发布闸门仍验证旧结构格式，五文档格式的完整实跑需要另行补上。技能包内容变化，ClawHub 版本与 `packageDigest` 在发版时按 `.clawhub/README.md` 更新。
- **验证**：全量 unittest 与 ruff 通过；新增场景 ID 前缀与示例配对两条行为测试，在未修复的代码/文档上各自失败。
