# Agent Note: 测试证明行为，不钉死文案

Status: implemented

## Problem

一次统计发现 13 条「断言 markdown 里出现某个字符串」的测试里 12 条是同一次新增的。这类断言不验证任何行为：改一次措辞就红，下一个人要么顺手改断言（等于没有断言），要么不敢改措辞；正则还会跨过否定词，`long-form generation.*is.*container` 匹配到了 "is not a multi-shot container"。仓库大多数改动是 SKILL.md 与 references 文本，若测试钉住文案，文本就没法演进。

## Decision

never 新增只断言某份文档或源码「包含 / 不包含某个纯字符串」的单元测试（CONTRIBUTING 第 5 条）。规则能结构化时解析并验证契约：路由表行数、规则表的 ID 与分级、标题锚点集合（`test_suite_anatomy`）；工具用输入 / 输出夹具证明行为（各技能 `selftest.py`、fixture adapter）；内容质量用隔离实跑与盲评（`evaluations/content_quality_gate.py`）；泄漏扫描器本身可以匹配文本，但它的测试验证扫描行为与边界。允许的字面扫描只有一种方向：断言被禁字段名或私有词汇**不存在**，那是负向结构契约（`RETIRED_DIGEST_KEYS` 三条、私有词表扫描）。

每条针对某处改动而写的测试 must 先确认会红：变异测试逐条删守卫（`tests/test_guards_bite.py` 记录了 67 处里 17 处删掉仍全绿），每次提交写明「验过会咬人」。夹具按字段锚定，never 按台词字面锚定——夹具台词一改，检查一次都不触发而测试照样绿。

来源：4ac1f33、a19e208、04fc9e8、bc04019、9735549、42696db、068097b、29f056f、b4f75cd、795cb80、dc9b0fa

## Alternatives considered

- **把已发布机制各自钉到文件与子串上，防合并静默丢失** — `tests/test_release_surface.py`（b4f75cd）曾这么做：一次合并两个分支改到相邻行，git 不报冲突，三处修复连同覆盖它们的测试一起丢了，于是把 25 条机制钉到子串。最强理由是它确实能报出「丢了哪条」。次日 #158 删除了整份 299 行——它正是本条禁止的形状，合并丢失要靠每条机制自己的行为测试来抓。
- **保留 prose 断言作为文档契约** — 理由是文档也是接口。被否（4ac1f33）：改成结构断言后契约仍在——路由表恰好 4 行且只有一行从已生成结果起步、能力表恰好 3 档、finding 模板真的装得下 `disposition`。
- **`test_bounded_workflow.py` 断言 `## Bounded execution` 子串** — 被删（9735549）：它唯一的结构断言已由 `test_suite_anatomy` 覆盖。

## Consequences

- **收益**：措辞可以随时改；测试红意味着行为变了，而不是句子变了；有变异证据的测试才算覆盖。
- **代价与已知上限**：结构断言需要解析器——`RULE_ROW` 一度只捕获 ID 与分级，三份 CON-* 副本改了正文也不红，后来才捕获第三列（239f8df）；负向字面扫描的例外要在测试里写明为什么它是结构安全契约，否则下一个人会拿它当先例加正向子串断言。
