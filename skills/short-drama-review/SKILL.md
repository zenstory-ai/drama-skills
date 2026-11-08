---
name: short-drama-review
description: 审查短剧项目中的原著分析、故事、剧本、视觉设定、图片提示词、分镜、冻结关键帧、视频提示词和已有媒体。用户提出“审稿/检查剧本”“检查资产或连续性”“检查图片/视频提示词”“检查原著分析”“审查模板感”“根据生产观察做项目校准”时使用；只写审查问题、结论和修订要求，不代替负责人修改来源文件。
license: MIT
---

# 短剧审查

优先由未参与当前版本创作的独立 reviewer 执行；自检时必须如实标注。本技能只定位问题、影响与必须达到的修订结果，将修改交回负责技能，审查与修改严格分离。

## Quick Start

直接读取用户点名的当前文件。需落盘时单集写 `审查/EP001-审查.md`，专项写 `审查/<主题>-审查.md`；仅需口头结论时直接回复。引用只使用文件名、标题 ID、行号或短引文，不建 sources 声明、哈希或 record ID：

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
- 规则：SHT-01 · structural_invariant
```

## 选择审查范围与按需资料

按范围（`source_analysis`、`story_script`、`assets_continuity`、`image_prompts`、`storyboard_keyframes`、`video_prompts`、`production_outputs`、`full_episode`、`delivery_privacy`、`project_calibration`）只读对应参考资料，不预加载整个项目：

- 原著分析：[原著分析审查表](references/rubric-source-analysis.md)
- 故事、剧本、改编忠实度、已接受节奏档案与三遍局部检查：[故事剧本审查表](references/rubric-story-script.md)
- 身份/变体、连续性、时代锚点与图片提示词：[资产提示词审查表](references/rubric-assets-prompts.md)
- 原文覆盖、镜头、冻结关键帧与视频运动：[视觉运动审查表](references/rubric-visual-motion.md)
- 证据化审查与补丁复审方法：[审查方法](references/review-method.md)
- 生成素材与成片职责判定、四类瑕疵分流（`REV-15`）：[生成素材审查](references/generated-media.md)
- 跨环节返工原因、指令优先级与改写回归（`REV-09`）：[生产质量门](references/production-quality-gates.md)
- 授权生产观察与项目内单变量校准（`REV-10`、`REV-11`）：[项目校准](references/project-calibration.md)
- 模板感诊断、反例与修订目标（`REV-05`）：[反模板修订](references/anti-template-repair.md)
- 阶段边界与 `REV-01`–`REV-15` 规则表：[阶段契约](references/stage-contract.md)

## 工作流

1. **确定范围**：明确本次受审文件、章节、镜头或提示词及创作者已选限制；目标在审查中变化时重读后再下结论。
2. **先查可证明事实（`REV-01`）**：核对五文档可见 ID/引用/时长一致性、剧本全要素（对白/动作/声音/画面文字）承载、人物/地点/道具状态与镜头起止连续性、画音同轨模型的声音时序与无对白底声/静默交代（`VID-22`、`VID-23`），以及私有输入/凭据/绝对路径泄漏。缺某项输入时只停止依赖它的判断。
3. **带证据写 Finding（`REV-02`）**：每条包含位置、短引文或冲突事实、观众/制作影响、修订结果与保持集、负责技能、严重程度、规则等级及 `open`/`closed` 状态，禁用无证据的“AI 味”“不够电影感”或空泛打分。
4. **跨文档溯源**：按 `剧本事实 -> 视觉设定 -> 镜头职责与边界 -> 冻结关键帧 -> 视频运动 -> 下一状态` 核对原意、知情时机与连续性。
5. **给出结论与分派**：
   - 结论：`APPROVE`（无阻断问题）、`APPROVE_WITH_NOTES`（仅有非阻断改进）、`REVISE`（存在阻断交付的结构缺陷、经证据确认的内容缺陷或已接受限制冲突）、`PROVISIONAL`（关键输入不足）。
   - 严重程度：`blocker`（不安全、不可交付或让流程走错）、`major`（破坏剧情理解、连续性或制作结果）、`minor`（有具体影响但不阻断）、`note`（创作选择或可选润色）。
   - 按负责技能分组修订要求后交还控制权；修改与复审仅在用户明确请求时启动。

## 边界

- 不提交任何媒体生产任务，不配置 adapter，不修改受审源文件。
- 未直接读取或无授权观察记录的媒体一律标为未知，不从文字、任务状态或文件存在推断画面、表演、口型或混音质量。
- 生产观察仅在当前项目、提示词版本与配置下成立，不泛化为通用定律；审查文件只保留最小证据，不复制完整私有输入。
