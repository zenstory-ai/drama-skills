# Agent Note: 为 Python 3.9 与固定版本 Playwright CI 任务锁定 Ubuntu 24.04

Status: implemented

## Problem

GitHub Actions 将浮动标签 `ubuntu-latest` 升级到 Ubuntu 26.04 后，[ci.yml](../../../../.github/workflows/ci.yml) 中两个原本依赖旧版宿主镜像的作业在进入仓库测试前直接失败：

1. `tests (py3.9)`：`actions/setup-python@v5` 读取的 `actions/python-versions` 清单仅为 Ubuntu 22.04 与 24.04 提供 Python 3.9 预编译包，Ubuntu 26.04 报 `The version '3.9' with architecture 'x64' was not found for Ubuntu 26.04`。
2. `Dashboard browser regressions`：工作流为避免无锁升级特意固定了 `playwright==1.58.0`，而该版本执行 `playwright install --with-deps chromium` 时拒绝 `ubuntu26.04-x64`（`Playwright does not support chromium on ubuntu26.04-x64`）。

这两个作业同时列在 [policy.json](../../../../.release/policy.json) 的 `ciWorkflows` 必检清单中（参见 [2026-10-03-source-release-contract.md](2026-10-03-source-release-contract.md)）；若任其失败，不仅 PR 无法取得全绿验证，合入 `main` 后也会阻断后续源码发布契约核验。

## Decision

[ci.yml](../../../../.github/workflows/ci.yml) 为受影响的两个任务固定兼容的 `ubuntu-24.04` 运行器，不升级依赖、不删改检查、不改动测试期望与作业名：

- `test` 矩阵保留 `python-version: ["3.9", "3.10", "3.14"]` 与作业名 `tests (py${{ matrix.python-version }})`，`runs-on` 设为 `${{ matrix.python-version == '3.9' && 'ubuntu-24.04' || 'ubuntu-latest' }}`，使最低支持版本 `3.9` 运行在提供预编译包的 `ubuntu-24.04` 上，`3.10` 与 `3.14` 继续跟随最新 Ubuntu 运行器验证。
- `dashboard-browser` 保留作业名 `Dashboard browser regressions` 与锁定的 `playwright==1.58.0`，`runs-on` 固定为与之匹配的 `ubuntu-24.04`。

## Alternatives considered

- 直接提升仓库 Python 下限（放弃 3.9）并升级 `playwright` 版本：能全部留在 `ubuntu-latest` 上运行；但提升 Python 下限属于跨全套脚本与两份 README 的兼容性变更，且在未单开依赖升级评审时改动锁定工具版本违背 `ci.yml`「工具版本有意锁定、避免意外漂移」的既有约定。
- 将 `ci.yml` 全部 Ubuntu 作业一律改为 `ubuntu-24.04`：写法最整齐；但会让已支持 Ubuntu 26.04 的 `tests (py3.10)`、`tests (py3.14)` 与 `lint and types` 失去对最新默认 Linux 运行器的持续覆盖。

## Consequences

- **收益**：最小改动恢复 `tests (py3.9)` 与 `Dashboard browser regressions` 在 GitHub Actions 上的完整执行，保持 `.release/policy.json` 要求的全部 6 个作业名、测试覆盖和锁定工具版本不变。
- **代价**：`ubuntu-24.04` 镜像在未来 GitHub Actions 生命周期结束前，需要与 `MINIMUM_PYTHON` 或锁定的 `playwright` 版本一并做计划内升级，而不会随 `ubuntu-latest` 自动静默迁移。
