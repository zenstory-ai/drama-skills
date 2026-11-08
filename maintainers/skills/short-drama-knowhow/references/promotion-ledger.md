# 去标识 Promotion Ledger

Promotion ledger 记录公共规则被晋升（`promotion`）、缩窄重测（`narrow-and-retest`）、暂缓（`hold`）或退休（`retire`）的决策与回滚定位。

## 记录边界

- 只引用完全合成的任务、匿名输出 hash、公共 skill 版本和独立审查结论；私有来源定位、连接信息、项目/人物名、原句、罕见设定组合与私有卡片引用严禁进入 ledger。
- `hold` 与 `retire` 必须与 `promotion` 一并记录；缺少可复核的匿名评测产物与独立 reviewer 证据说明时，不得写入 `promotion`。

## 事件 Schema

```yaml
event_version: 1
event_id: public-safe-random-id
rule_id: STY-or-other-public-rule-id
decision: promotion | narrow-and-retest | hold | retire
claim_scope: conditional-public-claim-with-applies-and-fails-boundaries
public_change:
  public_diff_hash: sha256-of-reviewed-public-diff
  baseline_skill_hash: sha256-of-anonymous-baseline-package
  candidate_skill_hash: sha256-of-anonymous-candidate-package
evaluation:
  synthetic_task_refs:
    - task_id: synthetic-task-id
      input_hash: sha256
      coverage_role: claimed-context | boundary | counterexample | transfer
  baseline_output_hashes: [sha256]
  candidate_output_hashes: [sha256]
  executor_context_refs:
    - arm: anonymous-arm-a
      context_ref: runtime-context-id
      fresh: true
    - arm: anonymous-arm-b
      context_ref: runtime-context-id
      fresh: true
review:
  reviewer_context_ref: independent-runtime-context-id
  independent: true
  verdict: promotion | narrow-and-retest | hold | retire
  evidence_summary: public-safe-comparison-of-specific-output-behavior
  counterexample_result: handled | overapplied | inconclusive
privacy:
  synthetic_only: true
  source_wording_present: false
  private_locator_present: false
rollback:
  supersedes: prior-event-id-or-null
  revert_target: public-commit-or-diff-hash
  retire_trigger: observed-overreach-no-gain-or-new-counterexample
```

## 写入与回滚

1. 揭盲前冻结合成输入、两个匿名 skill 包、输出 hash 与独立 reviewer 的初步结论；揭盲后核对版本映射、公共候选包与实际 diff，一致后写入 `review.verdict`。
2. 公共 `reference`、`rubric`、`synthetic fixture` 与 ledger 事件必须指向同一条件式 `claim_scope`。
3. 后续需要缩窄、替换或回滚时，新增事件并以 `rollback.supersedes` 指向旧事件（保留历史记录）；先按 `revert_target` 撤销或更新公共 diff，再用新合成任务重跑盲测与独立审查。
