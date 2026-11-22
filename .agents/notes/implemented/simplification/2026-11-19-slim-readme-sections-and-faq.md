# Agent Note: 精简 README 非核心章节与模型细则 FAQ

Status: implemented

## Problem

在 [README 面向读者而不是答案引擎](../process/2026-09-16-readme-for-readers-not-engines.md) 与 [README 用真实产出说话并回答高频问题](../process/2026-09-18-readme-real-outputs-and-faq.md) 落地后，随着模型适配文档与 v0.12 字段中文化持续累积，`README.md`（397 行）与 `README_EN.md`（447 行）再次膨胀并出现中英行数失衡：

1. **安装入口前仍有重复段落**：独立章节 `## 由来` 的第三段重复了 `## 这是什么` 中「先看预览、确认后再生成」的规则，拉长了读者到达 `## 安装` 的距离。
2. **FAQ 塞入过多单一模型底层标签与一次性历史字段清单**：10 个问题中包含 MiniMax H3 的 `<Subject N>` 六段结构、4.1 字/秒估时、正脸口型抢占等模型专有细则（已有各自技能参考文档承接），以及 v0.12 升级时整段罗列的 15 个旧字段名（已在 `CHANGELOG.md` 提供完整对照表）。
3. **尾部堆积重复与低频外链章节**：`## 延伸阅读` 罗列 13 条内外部文档链接，`## 交流` 与首屏 masthead 的 Telegram 按钮重复，`## 贡献` 仅重复指向仓库根目录已有的 `CONTRIBUTING.md`。

上述裁剪翻转了此前保留独立 `## 由来`、`## 延伸阅读`、`## 贡献` 与十条细则 FAQ 的决定，按仓库约定另立本篇并与旧笔记互链。

## Decision

同步精简并润色 `README.md` 与 `README_EN.md`，对齐中英结构与行密度：

1. **首屏与安装前动线**：完整保留 ZenStory AI 居中 masthead（含 `Python 3.9+` 徽章与 Telegram 入口）及两段样片；将原 `## 由来` 的工作室产线背景压缩为两句并入 `## 这是什么`，平台密钥外置与文档中立并入「先看预览、确认后再花钱生成」要点，使读者更快进入 `## 安装`（正文保留 `Python 3.9` 版本下限说明）。
2. **产出展示与十二技能表**：完整保留 `## 看看它的输出` 中的四份文档代码块与检查器报错原样输出及 `docs/real-outputs*.md` 入口链接，收紧十二技能职责表与快速开始中的冗长句式。
3. **FAQ 收敛为五条高层问题**：保留外部工具出参考图的挂图计划、生成中断后用 `audit` / `collect` 找回任务防重复扣费、本地无 GPU 与外部接口计费、静态漫剧免写视频提示词，以及 `### 升级到新版本后要做什么？` / `### What do I do after upgrading?`（保留标题锚点兼容 `docs/real-outputs*.md` 与安装段引用，正文改为指向 `CHANGELOG.md` 并运行 `creator_markdown_check.py` / `edit_tool.py check`）。
4. **删减非核心尾节并统一页脚**：删除 `## 延伸阅读`、`## 交流` 与 `## 贡献`；页脚固定为 `## 致谢` / `## Acknowledgments`（仅保留 `<https://linux.do>`）紧接 `## ZenStory AI 项目` / `## Part of ZenStory AI`。

## Alternatives considered

- **维持独立 `## 由来` 三段与十条 FAQ，仅删去 `## 延伸阅读` 与 `## 交流`**：
  - 最强理由：改动最小，H3 用户无需点进技能参考即可在首页读到六段粘贴与口型绑定细则，v0.11.x 旧项目用户也能直接在首页看到改名字段。
  - 不用：README 服务首次评估与上手的创作者，单一视频模型的提示词标签细则和一次性历史版本迁移表会把首页变成排障手册，且与 `skills/*/references/` 及 `CHANGELOG.md` 双重维护。
- **连同 `### 升级到新版本后要做什么？` 一并删除**：
  - 最强理由：升级说明完全交由 `CHANGELOG.md` 承担，FAQ 再少一条。
  - 不用：`docs/real-outputs.md`、`docs/real-outputs_EN.md` 与 README 安装段均通过页内锚点链向该小节；保留标题并将正文压缩为两句话，既不占篇幅又保持既有链接有效。

## Consequences

- **收益**：`README.md` 由 397 行降至 296 行，`README_EN.md` 由 447 行降至 303 行，中英小节与代码块一一对应；读者首屏后更快看到安装命令与快速开始，首页不再重复维护模型专有提示词细则与历史字段表。
- **代价**：`docs/` 下的专题指南不再在 README 末尾集中索引（仍可通过仓库目录、`docs/real-outputs*.md` 与 FAQ 内链访问）；MiniMax H3 细节问题需查阅对应技能的 `references/`。

## Verification

- 中英两份 README 的全部本地文件链接与页内锚点（含 `#安装` / `#install`、`#看看它的输出` / `#see-what-it-produces`、`#升级到新版本后要做什么` / `#what-do-i-do-after-upgrading`）逐一解析通过；中英标题数（各 18 个）与代码围栏数（各 11 个）严格对齐，`看看它的输出` 全部代码块与原文件逐字一致。
- 通过 `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v`（含 Python 3.9 下限一致性与 Markdown 粗体闭合测试）及 `ruff check --no-cache .`。
