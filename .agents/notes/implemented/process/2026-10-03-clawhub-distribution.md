# Agent Note: ClawHub 分发采用显式清单和单一写入器

Status: implemented

## Problem

产品 skill 没有统一的公开分发清单；仅靠各仓临时命令或等下一次 Release，会漏传、错传，且无法区分渠道缺失与尚未发布。旧流程还可能通过扫描整个 `skills/` 目录和临时删除目录来表达排除项，无法审查每个候选的发布者、版本、权利与包闭包。

## Decision

- `.clawhub/publish.json` 显式枚举仓库中的每个产品 skill，记录固定 `bootstrapSha`、owner/slug、semver、处置、skill 内包闭包、运行前提、发现元数据和权利证据。未验证过的运行时不写入 `supportedRuntimes`。
- `.clawhub/README.md` 记录 2026-10-03 的 MIT-0 分发授权、根 `LICENSE` 保留方式和规范内容指纹。包只收 skill 目录内的运行资产；仓库开发脚本不因位于根目录而被带入。
- 手动 `bootstrap` 使用固定起点提交，首次补齐不等待未来 Release。稳定 Release、十二小时 `reconcile` 和手动入口解析出四十位提交 SHA 后，统一调用组织级可复用写入器；不再保留独立 tag 写入口。
- 每个可发布条目用跨平台 `packageDigest` 锁定逐文件内容；内容或依赖版本改变时同时 bump 明确 semver 并运行中央 `lock`。稳定 release 的 policy 与 source 是同一不可变提交；仅旧 source 不含清单的冷启动兼容期允许用另一个固定受审 policy SHA。
- PR caller 只传 `mode: validate` 且不传发布 secret。中央引用必须替换成经审查的固定 commit SHA；仓库内 guard 在 `ROOT_REPLACE` 尚未替换时失败，防止占位引用被当作可上线配置。
- README 只链接可验证的 ClawHub 站点入口。单个 skill 的 URL 必须等发布者、版本和匿名访问均验证后再写，不能根据 slug 猜测。

## Alternatives considered

- **继续由维护者在本机运行全目录同步**——最强理由是改动最少。否：目录扫描会把排除项混入，也不能留下可审查的冷启动、包内容与所有权证据。
- **只在未来 Release 发布**——最强理由是天然绑定版本。否：现有漏项会继续存在到下次发版，不满足本次冷启动。
- **每个触发器保留一套发布命令**——最强理由是各仓可以独立调整。否：多套 writer 容易发生重复 bump、身份漂移与部分失败后的重复上传；薄 caller 只负责解析不可变 source，写入语义集中一处。

## Consequences

收益是每个候选都有明确去向，首次补齐不依赖新 Release，后续入口也不会形成多个写入器；包内容、许可证和指纹可以逐项复核。代价是仓库需维护清单；中央工作流 SHA、owner-qualified identity 与首发版本必须在真实写入前完成组织级核对。定时任务会消耗少量 Actions 配额，但相同 owner/slug/version/fingerprint 必须为 no-op。

## Verification

本次以 `actionlint` 验证两个 caller 的 YAML 与表达式；另用本地清单审计核对完整目录覆盖、固定 SHA、semver、权利锚点、依赖版本、包内无 symlink 与 38 个候选总数。中央引用已固定为经独立审查、通过 20 项回归测试的 `d77b6785e1d04f608577219aeed6dfdcd93e24b1`；uses 与 control_ref 相同，guard 只匹配 YAML 值，不会匹配自己的命令字符串。真实 GitHub CI 与首次公开分发由组织集成线留证。

`python3 -B -m unittest discover -s tests -v` 与 `ruff check --no-cache .` 全部通过。
