# `lookdev-prompts.md` 可复制输出模板

此文件由已接受 Look Development 规格派生。它展示视觉方向怎样跨测试轴保持，
只复制引用块内的自然语言提示词；本文件不触发图片或媒体服务，实际生产交
`$short-drama-produce` 并单独确认。

**这是项目级文件，不是某一集的创作文档。** 它不参与 `creator_markdown_check.py` 的
五文档校验；某一集要用的资产提示词写进该集的《图片提示词.md》，骨架以 `SKILL.md` 为准。

```markdown
# 项目 Look Development 提示词

> 来源：`lookdev-image-prompt-specs.jsonl` 的已接受记录
> 视觉方向：`short-drama.json#/creator_authority/visual_direction/choices/look_development`
> 范围：仅代表帧提示词，不拥有角色身份、地点地理或剧情状态

## `LOOKDEV-<id>` · `<人物表现 | 核心地点 | 高压力场景>`

- **测试问题**：<本帧要暴露的视觉方向风险>
- **绑定事实**：<准确身份/变体；高压力帧再列 scene/block refs>
- **跨轴稳定**：<形状、材质、色彩、阴影、景深或密度中的共同规则>
- **本帧可变**：<当前场景允许变化的部分>
- **风格参考权限**：`<slot_id / order / reference>` 只决定 `<may_control>`，不得导入 `<must_not_control>`
- **仍未知**：<只能由授权生产观察回答的风险；无则写“无”>

### 可复制通用提示词

> <只写可被画出的主体、空间、构图、材质、光色和状态；不含字段名、hash、审查话术、供应商参数或生成历史。>

---
```

三类测试帧不要求固定数量或宫格。人物/地点帧没有剧情职责时不列 scene/block refs；高压力帧必须
显示其准确来源。规格或视觉方向改了就重新派生本文件，不直接手改缓存。
