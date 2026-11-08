# Creator-first 工作流

## 唯一落盘

每集按需维护五份创作者可读 Markdown（详细语法见 [五份创作文档](creator-documents.md)）：

| 阶段 | owner | 文件 |
|---|---|---|
| 剧本 | `short-drama-write` | `剧集/<EP>/剧本.md` |
| 视觉资产 | `short-drama-assets` | `剧集/<EP>/视觉设定.md` |
| 分镜与冻结关键帧 | `short-drama-storyboard` | `剧集/<EP>/分镜.md` |
| 图片提示词 | `short-drama-image-prompts` | `剧集/<EP>/图片提示词.md` |
| 视频提示词 | `short-drama-video-prompts` | `剧集/<EP>/视频提示词.md` |

- **按需建档**：无内容时不预建空文件；从任一阶段直接进入均合法，不为补齐名义流水线伪造上游。
- **不建并行创作文件**：单集主链不额外保存 JSON/JSONL、索引、指纹、覆盖表、QA 报告或场次交接摘要；稳定 ID 直接写进 Markdown 标题。`项目开发/` 下的原著拆解与多集分集索引仅在用户点名时建立，不改变单集五文档布局。
- **项目级事实同步**：Brief 或会话中已确认的集数、单集目标时长、画幅、语速、目标视频模型与续接路由（`continuation_route`）写入 `short-drama.json`（状态只用 `unset` 或 `accepted`），写法见本技能 `SKILL.md` 的「初始化与项目级档案写入」。输出语言优先级见 [契约与所有权](contract-and-ownership.md#输出语言)。

## 请求范围与停机边界

用户点名的范围就是本轮范围（如“写完这一集”或“从剧本做到视频提示词”）。场次、资产组和镜头组只是内部上下文批次，通过后自动续跑，不逐批交还控制权，也不为中间文件另开审查回合。

仅在以下三种情况停下：

1. 用户点名的范围已完成；
2. 缺失事实构成会显著改变剧情或视觉方向的真实创作分叉；
3. 下一步将调用外部媒体生产，须先展示精确 job 预览并取得显式确认。

对于视频提示词请求，已接受档案中有目标模型或参考图安排时直接沿用；无项目内匹配图且创作者未另选时的默认 `PLAN-...` 挂图路径见 [五份创作文档](creator-documents.md#ref-plan--与四种输入参考图状态)。

## 校验、审查与生产边界

- **结构与创作检查**：按本技能 `SKILL.md` 的「工作流与停机边界」运行 `creator_markdown_check.py`；各阶段按具体问题读取自身 craft references 与 [knowhow-index.md](knowhow-index.md)。
- **生产边界**：图片、视频、TTS 和音乐生产始终遵循 `preview -> explicit confirm -> run`。生产工具可在 `.short-drama/` 保存 job、确认和审计记录，job 的 `source` 指向拥有当前提示词的 Markdown，输出写入 `剧集/<EP>/制作成果/`；提示词、参数或路径一旦变化须重新预览并确认。
