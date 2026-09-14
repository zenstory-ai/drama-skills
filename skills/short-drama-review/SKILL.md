---
name: short-drama-review
description: 审查短剧项目中的原著分析、故事、剧本、视觉设定、图片提示词、分镜、冻结关键帧、视频提示词和已有媒体。用户提出“审稿/检查剧本”“检查资产或连续性”“检查图片/视频提示词”“检查原著分析”“审查模板感”“根据生产观察做项目校准”时使用；只写审查问题、结论和修订要求，不代替 owner 修改来源文件。
license: MIT
---

# 短剧审查

优先由未参与当前版本创作的 reviewer 执行；条件不允许时可以自检并如实说明。审查与修改是两个工作
单元：本技能只定位问题、影响和必须达到的修订结果，不在同一轮替 owner 改来源。

## Quick Start

直接读取用户点名的当前文件。单集审查需要落盘时写 `审查/EP001-审查.md`；独立文件审查使用
`审查/<主题>-审查.md`。用户只要口头结论时直接回复，不为“完整”创建审查文件。

审查 Markdown 建议结构：

```markdown
# EP001 审查

- 范围：剧本、分镜、视频提示词
- 结论：REVISE
- 复核方式：独立 reviewer / 自检

## Blocker · REV-001 · 画面文字未被镜头承载
- 位置：剧本.md / EP001-SC002；分镜.md / SHOT-EP001-004
- 证据：……
- 影响：……
- 修订结果：由 short-drama-storyboard 补入准确文字及可读条件。
- 规则：SHT-01 · reviewed_invariant
```

引用只使用文件名、标题 ID、行号或短引文；不建立 sources 声明、哈希、record ID 或第二套状态。

## 选择审查范围

- `source_analysis`
- `story_script`
- `assets_continuity`
- `image_prompts`
- `storyboard_keyframes`
- `video_prompts`
- `production_outputs`
- `full_episode`
- `delivery_privacy`
- `project_calibration`

只读对应资料，不预加载整个项目：

- 原著分析：[原著分析审查表](references/rubric-source-analysis.md)
- 故事、场景、行动与对白：[故事剧本审查表](references/rubric-story-script.md)
- 身份、变体、连续性与图片提示词：[资产提示词审查表](references/rubric-assets-prompts.md)
- 原文落实、镜头、关键帧与视频运动：[视觉运动审查表](references/rubric-visual-motion.md)
- 完整审查方法：[审查方法](references/review-method.md)
- 制作端常见缺陷：[生产质量门](references/production-quality-gates.md)
- 授权生产观察的项目内校准：[项目校准](references/project-calibration.md)
- 模板感、重复手法或 AI 味：[反模板修订](references/anti-template-repair.md)
- 阶段边界、参考媒体与规则表：[阶段契约](references/stage-contract.md)

## 工作流

### 1. 冻结范围

写清当前要审哪些文件、章节、镜头或提示词，以及创作者已经明确的限制。目标在审查中发生变化时，
重新读取再下结论。

### 2. 先查可证明事实

- 五文档的可见 ID、引用和时长是否一致；
- 剧本对白、动作、声音、画面文字是否都有画面/声音承载；
- 人物、地点、道具状态和镜头起止是否连续；
- 提示词是否从准确起点到准确终点；
- 目标模型画音同轨时，声音内容、时序和发声边界是否与来源一致；无对白镜是否交代底声或静默
  （`VID-22`、`VID-23`，见 [视觉运动审查表](references/rubric-visual-motion.md)）；
- 私有输入、凭据、绝对路径或内部流程文字是否泄漏。

缺少必要输入时只停止依赖它的判断，其他问题可以继续汇总。

### 3. 带证据审内容

每个 finding 包含：位置、必要短引文或冲突事实、观众/制作影响、必须达到的修订结果、owner、严重
程度和规则等级。不能只说“AI 味”“不够电影感”或给无证据分数。

### 4. 跨文档综合

```text
剧本事实 -> 视觉设定 -> 镜头职责与边界 -> 冻结关键帧 -> 视频运动 -> 下一状态
```

优先守住原意、知情时机与连续性，不奖励脱离来源的华丽提示词。

### 5. 结论与分派

- `APPROVE`：没有阻断问题；
- `APPROVE_WITH_NOTES`：只有不阻断的改进；
- `REVISE`：存在结构、内容或限制冲突；
- `PROVISIONAL`：关键输入不足，暂时无法完成判断。

按 owner 分组修订要求。本轮完成后交还控制权；修改和复审只有用户明确请求时开始。

## 严重程度

- `blocker`：不安全、不可交付或会让流程走错；
- `major`：明显破坏剧情理解、连续性或制作结果；
- `minor`：有具体影响但不阻断；
- `note`：创作选择或可选润色。

## 边界

- 不提交图片、视频、TTS 或音乐任务，不配置 adapter，不把 Dashboard 操作当生产授权。
- 无法读取媒体时明确限制，不从文字或 adapter 状态推断脸部一致、表演、口型、混音或市场表现。
- 生产观察必须绑定准确输入、提示词、参考、配置和结果版本；不能泛化成通用规则。
- 审查文件只保留修订所需的最小证据，不复制完整私有输入。

## 安装维护

只有安装、升级或排障时运行 `python3 scripts/selftest.py`。
