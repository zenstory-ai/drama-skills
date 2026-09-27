# Agent Note: 规则四级分级与脚本边界

Status: implemented

## Problem

把创作判断写成规则代码会把导演判断僵化成表单；把统一的字数、比例、数量配方设为质量门槛会拒掉合法项目；同一条规则在不同文件里若约束力不同，reviewer 打开哪个文件就得到哪条规则。需要一套共用的约束力词汇，并规定脚本只能守哪一级。

## Decision

每条规则归入四级之一（`skills/short-drama/references/knowhow-index.md` 的分级表）：`structural_invariant` 是本地可证明的引用、ID、算术或显式状态矛盾，校验器可阻断；`reviewed_invariant` 是语义义务，由 reviewer 引用证据判定；`craft_default` 是通常有帮助的做法，创作者说明理由即可覆盖；`taste_option` 是表达选择，不得单独阻断交付。规则住在各技能 `references/stage-contract.md` 的表里，用稳定 ID（SCR-、STY-、SHT-、VID-、IMG-、AST-、EDT- 等）在 knowhow-index 注册；题材卡与形态卡永远是 `craft_default`，不能铸造 `structural_invariant`。

脚本只做确定性工作——稳定索引、跨文件结构对账、算术与集合比对——判断归审查者。校验器的阻断级别 must 与规则分级一致，`craft_default` 被当作阻断执行是差两级；never 用固定词表或形容词比例阻断交付；数值规则只能是创作者已接受值上的算术。CHANGELOG 按分级归类：`structural_invariant` 与 `reviewed_invariant` 的新增或收紧记为变更（可能阻断既有产物），即使只约束新增的可选层；`craft_default` 与 `taste_option` 记为新增。

规则表如何分布到各技能见 [每个技能自包含](2026-07-26-self-contained-skills.md)。

来源：27f4319、1b564a0、4e15468、15eba8d、c88add8、9e9d82d、6baaeed、810945d、2752658

## Alternatives considered

- **用关键词或正则匹配创作语义** — 最强理由：可自动化、能进 CI、结果可复现。三次被否（15eba8d、194d8d9、ea8be01）：把上下文判断变成脆弱规则；`generability` 若写成关键词检查会把「退伍军人群里」误判成人群场面，所以写成参考资料。
- **固定质量词表阻断交付** — `image_prompt_check.py` 曾把 `masterpiece|8k|uhd` 编译成 `ValidationError`。被否（6baaeed）：IMG-02 是 `craft_default`；词表抓到 `8k` 却放过 `common-recipe.md` 自己点名的空泛词，「是否空泛」是语义，属于 reviewer。保留的只有引擎专用语法（`--ar`、`::N`），那是本地可证明的冲突。
- **品牌禁词表、白名单或新校验维度** — 处理现实品牌最直接。被否（810945d）：套件不携带任何平台的审核标准，政策选择以 `craft_default` 路由给创作者。
- **通用节拍、字数、反应镜配额** — 行业数字现成。被否（4e15468、c88add8）：与项目的动作预算和创作者权威冲突，数值只作为项目档案。

## Consequences

- **收益**：谁能判、能不能阻断一目了然；创作者一句理由即可覆盖默认。
- **代价与已知上限**：语义规则靠 reviewer 引用证据，覆盖率低于脚本；分级一致性靠测试（同 ID 不同分级会红）；收紧分级即可能阻断既有产物的变更，必须附迁移说明。
