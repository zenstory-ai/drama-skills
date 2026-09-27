# Agent Note: 每个技能自包含，不跨技能引用文件

Status: implemented

## Problem

七个子技能曾有 34 处跨 skill 文档引用（30 处指向核心 references、4 处兄弟耦合），核心又有 26 处反向指向子技能文件。任何一个技能都无法脱离其他技能的文件被读懂；只安装写作技能的创作者点开链接就是断链；一条规则改在核心里，子技能的 reviewer 看到的还是旧版。

## Decision

`skills/*` 每个目录是独立安装单元，可以单独 symlink 使用。技能内所有 Markdown 相对链接 must 落在本技能目录内：`test_installation_resolution` 解析每个链接、`resolve()` 后断言仍在目录里——用解析而不是前缀匹配，因为 `](../short-drama-develop/` 曾绕过 `](../short-drama/` 的前缀检查。跨技能只按技能名路由（`$short-drama`、`$short-drama-review`），never 指向对方的文件；硬阻断 never 依赖不随本技能发布的文档。共享内容按阶段切片内联到各技能的 `references/stage-contract.md`，不做整文件复制；CON-* 在 assets、storyboard、video-prompts 三份契约各存一份，同一 ID 的 (class, knowledge) must 完全一致，测试强制。核心 `knowhow-index.md` 只保留「主题 → 负责技能名」的路由、分级定义与冲突优先级，不含规则行。

没有套件级清单：`suite-manifest.json`、`suite-ref.json`、`suite_verify.py`、sibling pin 都不存在，测试断言它们不被发布；缺少 sibling 不阻断当前任务。每个技能自带最小样例、结构校验器与 `selftest.py`，CI 把它单独复制到陌生路径、从无关 cwd 运行。

规则本身如何分级见 [规则四级分级与脚本边界](2026-07-16-rule-tiers-and-script-boundary.md)。

来源：2bdf07f、239f8df、86a5280、2752658、8fcdbad（0.4.0）、2c86707、6baaeed、aed855c

## Alternatives considered

- **核心集中放共享 references，子技能链接过去（初始形态）** — 最强理由：一处改全套生效，没有副本。被否：单独安装即断链；读者要跨目录才能读懂一个阶段；核心反向引用子技能后两边互相依赖。
- **套件级 hash 清单加 `suite-ref.json` pin 保证整套一致（0.2–0.3）** — 最强理由：混装可被安装验证发现。0.4.0 删除：缺 sibling 就阻断当前任务，清单坏掉的后果面向安装者，每次改动都要重建八份 pin。
- **整文件复制到每个技能** — 最强理由：零切片工作。被否：形态卡这类只给路由用的内容会被复制进不读它的技能，改动面翻倍；因此按「本阶段需要形态回答哪几件事」切片。

## Consequences

- **收益**：任何一个目录拷走就能读、能跑 selftest；reviewer 打开一个技能就拿到该阶段完整规则表。
- **代价与已知上限**：CON-* 改一处必须改三处，README 如实写出这一条；跨技能引用只能用技能名，无法深链到对方的具体小节；核心索引从 168 行降到 81 行后，路由表说不清一个主题在负责技能的哪份文件里，要靠各技能 SKILL.md 的按需知识列表。
