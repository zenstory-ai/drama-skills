# 契约与所有权

## 工作流不是瀑布

```text
开发? -> 剧本 -> 视觉设定 -> 图片提示词
                    \-> 分镜 -> 视频提示词
                    \-> 明确确认后的媒体生产
```

可从任一已有材料直接进入；Look Development 和审查均按需发生。各负责技能只修改自己拥有的 Markdown，引用上游可见事实但不私自改写。规则分级（`structural_invariant` / `reviewed_invariant` / `craft_default` / `taste_option`）与冲突优先级见 [规则与路由索引](knowhow-index.md#规则分级)。

## 输出语言

| 内容 | 有项目配置时 | 独立任务默认 |
|---|---|---|
| 创作者可读说明与审查 | `short-drama.json#/language` | 用户当前语言 |
| 图片、关键帧的可复制正文 | `short-drama.json#/format/prompt_language` | `en` |
| 视频的可复制正文 | `creator_authority.production_profile.choices.video_prompt_language`；未声明时回退 `format.prompt_language` | 根据目标视频模型确认；未声明时使用用户当前语言 |

创作者说明、通用提示词语言和视频模型提示词语言互相独立；画面中的对白和可读文字来自剧本与视觉事实，不由描述语言推断。

## 稳定身份与引用

- **文档条目 ID**：使用创作者可见的稳定 ID（`EP001-SC001`、`IMG-...`、`SHOT-...`、`MOTION-...`）。显示名可变而 ID 不变；跨文档直接引用这些 ID，不写哈希、内部路径、隐藏状态或第二套 record ID。`IMG-...` 专属《图片提示词.md》的提示词标题，不代表已有图片文件。
- **参考图槽位（`REF-...` 与 `PLAN-...`）**：项目内真实可读图片使用 `REF-...` 槽位，创作者在项目外准备并自行挂载的图片使用 `PLAN-...` 槽位；完整语法与四种状态见 [五份创作文档](creator-documents.md#分镜md) 与 [参考角色](reference-roles.md)。

## 信任与文件安全

普通创作不联网。实际媒体生产只允许项目外 adapter 读取环境凭据，并始终经过 `preview -> explicit confirm -> run`。严禁把私有输入、凭据、绝对路径或非公开观察写入可交付文档。
