# Agent Note: 私有 knowhow 技能与受保护发布门禁留在公共树之外

Status: implemented

## Problem

套件的工艺知识有一部分来自非公开的完整项目链。公共仓库不得含非公开项目内容、内部标识、私有网址、供应商任务或媒体文件，而普通开发环境拿不到维护者的私有词汇，无法证明「没有泄漏」；如果门禁在这种环境下默默通过，绿灯会被当成证明。学习流程本身也不能变成运行时依赖。

## Decision

`maintainers/skills/short-drama-knowhow` 是 maintainer-only 技能，故意不放在公共 `skills/*`（`test_installation_resolution` 的 `EXPECTED_SKILLS` 是封闭集），维护者从受控 checkout 显式 symlink 到 `$CODEX_HOME/skills` 后调用。它只研究文本，先写私有 observation / decision cards，去标识候选经 fresh agent 盲测与独立审查后才进公共 skill；每次 promotion / hold / retire 按 `references/promotion-ledger.md` 留下去标识事件。盲测 arms、verdict、回滚记录放在仓库外或被忽略的 `.omx/evals/`、`maintainers/evals/`；公共测试 never 依赖它们，受保护 CI 需要时通过外部路径注入。

受保护发布门禁（`tests/private_release_gate.py`）fail-closed：`DRAMA_REQUIRE_PRIVATE_RELEASE_GATE=1` 时 must 同时给出仓库外的 `DRAMA_PRIVATE_TERMS_FILE`，文件缺失、不可读或只有注释都抛错；普通开发不设该变量时返回空词表，只证明公开的通用边界，不声称检查过私有词汇。词表内容、扫描命中与私有来源指纹 never 进入公共日志。扫描面按 git tracked 文件枚举，没有 checkout 时显式 skip 而不是绿灯。精确词扫描只负责明显泄漏；由非公开材料晋升的候选还要由未看过来源的 fresh agent 做语义 de-copy 盲审，取不到独立上下文就不发布。

来源：194d8d9、ea8be01、06adb77、fc9956f、945143e、86a5280、16966f7、86a8b51

## Alternatives considered

- **把 blind-eval 产物和私有卡片发进公共树** — 最强理由：晋升证据可追溯。被否（ea8be01）：它们不属于发布树，带着来源表达；公共测试随之解耦。
- **把 knowhow 技能放进 `skills/`** — 一起安装省事。被否：它要求授权只读来源与隔离工作区，普通创作者没有这些前提也不需要。
- **门禁 rglob 工作树而不是 tracked 文件** — 最强理由：本地未提交的文件也被扫。被否（fc9956f）：实测扫了 63 个不发布的文件却漏掉 141 个随发布的样例文件；「release-facing」的定义就是 tracked。
- **门禁未完成时直接合并** — 允许，但 must 在合并说明里写「门禁覆盖声明」，ledger 记 hold 而非 promotion（86a5280、16966f7 的做法）。

## Consequences

- **收益**：公共树自己能证明公开边界；维护者技能与公共技能的目录分界由测试守住。
- **代价与已知上限**：普通 CI 全绿不等于无泄漏，受保护发布依赖维护者本机的词表；hash 只保证字节可重放，不能代替语义审查；扫描根目录是硬编码前缀，改目录名要同步，否则门禁退化为空操作（945143e 加了「每个根至少匹配一个文件」的守卫）。
