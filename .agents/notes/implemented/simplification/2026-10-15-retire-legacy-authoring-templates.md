# Agent Note: 退役旧创作模板，只发货五文档入口

Status: implemented

## Problem

[五份创作者文档](../architecture/2026-08-22-creator-first-five-documents.md)保留了旧格式模板、旧根只读和锁定旧版本的兼容解释。用户在本轮精修后明确要求“不需要留兼容”，因此继续把这些旧创作模板随技能发货会留下第二套作者入口。部分测试直接解析模板中的 JSON 对象，需要保留其合成数据而非继续发布模板。

这是对旧兼容保留决定的翻转，另立本笔记，不改写旧决定。当前五文档及编号规则、专业技法、反例与配对示例仍保留。

## Decision

从技能目录移出 16 份作者模板：删除 image 四份、video 四份、分镜关键帧派生文本和写作录音表共十份 Markdown；另将分镜 coverage/shot/keyframe 与写作 episode-card/standalone/beats 六份 JSON/JSONL 迁出。

测试资料统一放到 `tests/fixtures/authoring-records/`，共九份纯数据 fixture。前三份从 image、motion 和 container Markdown 中提取 sources 与记录对象，字段和值保持相等；其余六份原始数据按字节复制。迁移前检索确认六份原始模板没有运行时文件读取消费者；shot 模板除 suite anatomy 外，还被 reference integrity 的 schema 映射读取，现均指向测试 fixture。两个测试模块仍检查引用形状、字段指针、候选权限与派生关系，不因移出技能目录而漏检原对象。

当前 SKILL/references 去掉旧格式写入、反写、重新派生与锁版本兼容入口，只讲五文档。单帧身份、造型、地理、文字政策和局部修改留在 image 的 common/character/location/prop/edit 参考；首尾边界与时长加总留在 storyboard 的 keyframe-craft/production-shot-grammar；有序动作、表演、时间与容器算术留在 video 的 motion-recipe/delivery-profile。录音表中有用的说话对象、前句、知情、策略和读法核对并入 write 的 scene-sound-dramaturgy，时间线音乐与逐字歌词职责留在 camera-audio-continuity。

现有运行时检查器、确有 self-test 或行为测试消费者的合成示例不删除。生产 job、原著分析索引与审核证据各有现行用途，不因字段结构化而一并删除。

## Alternatives considered

- **保留模板并在开头标明只读与旧版本**：便于旧项目追溯，也不影响原测试。未采用：用户明确取消兼容要求，旧作者入口不再属于当前发货内容。
- **连同检查器及所有 JSON 示例一起删除**：目录最少、没有旧结构残留。未采用：现有运行时自测与行为回归仍实际使用其中的合成数据，删除会扩大为无关运行时重构。

## Consequences

- **收益**：创作者只会进入当前五文档路线，维护测试仍保有原对象及引用契约。
- **代价**：当前技能不再提供旧创作格式的模板或继续编辑指导；测试 fixture 不作为技能接口发货。
- **验证**：14 份当前文档和 10 份退役文档按五步核对；当前文档的 33 个既有 fenced blocks、全部引用块、配对示例与编号规则 ID/Class 不变。三组提取记录逐字段相等，六份原始数据字节相同。suite anatomy/reference integrity/安装解析 24 项、golden/workflow 23 项通过；image/video/storyboard/write 自测分别 10/10/13/14 项通过。两个修改后的测试模块通过 ruff；未运行外部生产。
