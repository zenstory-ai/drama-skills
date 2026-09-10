# `image-prompts.md` 可复制输出模板

此文件由已接受规格生成。元信息用于核对来源；只复制引用块内的通用提示词。不要手写供应商参数。

**这份模板属于结构化管线**（`image-prompt-specs.jsonl` 一路）。creator-first 项目的《图片提示词.md》骨架以 `SKILL.md` 为准：`## IMG-... · 中文名`，字段写成不加粗的
`- 参考：`（取「无外部参考」或完整 `REF-...` 语法），正文标题是 `### 可复制提示词`。
不要把这里的加粗字段名、`参考图用途`、`本次呈现` 或 `### 可复制通用提示词` 搬进 creator-first 文档——
`creator_markdown_check.py` 按 `SKILL.md` 的骨架校验，照本模板写会被判「缺少参考字段」。

```markdown
# EP<编号> · 资产图片提示词

> 来源：`image-prompt-specs.jsonl` 的已接受记录
> 配方：`<recipe>@<version>`
> 范围：本文件仅提供提示词，不触发媒体服务；实际图片生产交 `$short-drama-produce`

## `<display name>` · `<purpose>`

- **规格**：`IMG-<id>`
- **绑定**：`<asset-id>` + `<variant-id>`
- **用途**：<后续复用目标>
- **参考图用途**：`<slot_id / order / reference>` 只决定 `<role / may_control>`；不得导入 `<must_not_control>`；检查状态 `<observation ref | unverified + risks>`；无参考则写“无”
- **文字来源政策**：`exact_readable | graphic_only | no_readable_text | pending_creator_text`
- **本次呈现**：`readable | symbolic | blank | postproduction`（附 source → treatment 映射）
- **注意**：<未阻断的警告 / 创作者明确调整；无则写“无”>

### 可复制通用提示词

> <正文语言按 `short-drama.json#/format/prompt_language`（独立运行时由用户指定，未指定为 `en`）——这一格不预设中文。用途/主体与区分性锚点在前，状态、构图、空间/尺度、材质/光线、背景、文字政策、保持/排除依次展开。不要出现字段名、hash、审查话术或生成历史。>

### 变体/编辑说明

- **相对基准**：<基础版本；非变体可省略>
- **变化**：<看得见的变化；无则省略>
- **必须保持**：<`preserve_set`；非局部修改可简写或省略>
- **连续性影响**：<已接受的绑定 / 无；非局部修改可省略>

---
```

每个资产或版本独立一节；不要把多个互相冲突的造型、观察方向或状态合成一个可复制段落。
该文件被手改过时，先按 `restore | adopt` 流程预览将要恢复或采用的内容。
