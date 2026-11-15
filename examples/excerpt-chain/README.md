# 四阶段节选示例：同一场戏从剧本到视频提示词的交接

本目录保留四份历史归档节选，仅用于展示同一场都市反转戏如何从剧本一路交接到角色场景设定、分镜与视频提示词。剧中情节、人物和地名均为虚构。

> **注意**：后三份下游节选（`EP001-资产设定.md`、`EP001-分镜.md`、`EP001-视频提示词.md`）使用的是早期归档的文件名与旧字段名，**不兼容**现行 `creator_markdown_check.py` 校验器；若要复制或参考当前版本的五份创作文档模板与字段写法，请改看 [examples/creator-first/EP001/](../creator-first/EP001/)（供内部结构化脚本自测的样例见 [golden-project/](../golden-project/)）。

| 文件 | 环节 | 对应技能 |
|---|---|---|
| [EP001-剧本.md](EP001-剧本.md) | 分集剧本（片场制作稿格式） | `short-drama-write` |
| [EP001-资产设定.md](EP001-资产设定.md) | 角色三视图 / 场景方位图 / 物品白底图（历史归档文件名与字段） | `short-drama-assets` + `short-drama-image-prompts` |
| [EP001-分镜.md](EP001-分镜.md) | 剧本落镜 + 镜头目的 + 观众可见信息（历史归档文件名与字段） | `short-drama-storyboard` |
| [EP001-视频提示词.md](EP001-视频提示词.md) | 主镜头与局部补拍的视频提示词约定（历史归档文件名与字段） | `short-drama-video-prompts` |

按上表顺序阅读即可看清跨阶段交接逻辑；实际新建或编写现行剧集文档时请以 [examples/creator-first/EP001/](../creator-first/EP001/) 为准。

## 关于剧本格式

[EP001-剧本.md](EP001-剧本.md) 使用国内短剧常见的**片场制作稿格式**（`【场景】`、`△`、`▲`、`【人物】`），展示创作者常见来稿的写法。
旧稿格式整理方法与标准写法见 [screenplay-format.md](../../skills/short-drama-write/references/screenplay-format.md)。
当前 `short-drama-write` 将确认后的剧本写入 `剧本.md`。
