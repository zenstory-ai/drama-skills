# 私有卡片与 Coverage Matrix

## 卡片共通纪律

卡片只保存在维护者指定的隔离工作区，先通读项目完整文本链再制卡，用随机内部 ID、内容 hash 或抽象 locator 追溯证据，不摘抄可识别原文。

- **轴与证据分离**：`genre_axes` 记题材、受众承诺和情绪合同；`mechanism_axes` 记实现机制（不把桥段名当机制）；`evidence` 记可复核位置与改写后的观察；`counterevidence` 即使为空也须写明检索范围；`creator_overrides` 单列，不把创作者特例误读为通用规律。
- **版本与角色还原**：先按项目实际存在的层还原 `version_refs`，缺层记入 `missing_layers`，再标明每条记录的 `source_role`。提示词存在、任务成功或提交次数只代表流程活动，不得填入 `observation_evidence` 冒充效果证明。
- **媒体观察边界**：本 skill 只读文字，制卡 agent 的 `media_observed` 恒为 `false`。仅当存在创作者或获授权观察者的文字报告时，`observation_kind` 才可设为 `input_reference` 或 `generated_result`（对应 `evidence_mode` 为 `creator_reported` 或 `authorized_media_inspection`），并在 `observer_report.observer_media_observed` 归因；无合格报告时一律填 `none`。输入参考观察与生成结果观察不得混入同一张卡；一条提示词兼顾多职责时按 `prompt_role` 分卡记录。

## Observation card schema

```yaml
card_type: observation_card
card_id: obs-internal-id
source_project_ref: opaque-project-ref
chain_read:
  available_layers: [brief, story, episode_map, screenplay, assets, continuity, image_prompt_text, storyboard_text, video_prompt_text, review]
  missing_layers: []
  version_refs:
    - layer: screenplay
      ref: opaque-version-ref
    - layer: storyboard_text
      ref: opaque-version-ref
  creator_overrides: [bounded-override-or-none]
genre_axes:
  surface_genre: abstract-label
  audience_promise: abstract-promise
  emotional_contract: abstract-contract
production_axes:
  production_form: abstract-form-or-unknown
  visual_style_axes: [observable-shape-material-light-or-motion-axis]
  scene_function: abstract-scene-function
  prompt_role: identity | geography | composition | style | state | action | performance | camera | sound | none
mechanism_axes: [mechanism-label]
observation:
  setup_state: what-the-audience-can-understand
  pressure_or_question: dramatic-problem
  character_action: playable-action
  information_change: audience-state-change
  turn_or_payoff: observable-dramatic-result
  downstream_translation: how-text-production-layers-preserve-or-alter-intent
evidence:
  direct_observations:
    - locator: opaque-layer-and-record-ref
      source_role: creative_source | derived_projection | revision_request | execution_task | input_reference_observation | generated_result_observation | other_result_evidence
      note: paraphrased-observation-without-source-wording
  agent_interpretation: bounded-causal-reading
  unknowns: []
counterevidence:
  searched: what-was-checked
  findings: []
  alternate_explanations: []
privacy:
  contains_source_wording: false
  contains_identifiers: false
  public_eligible: false
confidence: tentative | supported | conflicted
```

共通头部的 `evidence.direct_observations` 只记文本版本与层间投影链；媒体尾段的 `observation_evidence.direct_observations` 只记授权观察者在指定区域或时间段实际看到/听到的现象，两处不重复抄写。在共通头部后，按实际证据**三选一**拼接以下媒体观察尾段：

### 1. 纯文本尾段（`none`）

```yaml
media_observed: false
observation_kind: none
evidence_mode: none
limitations: [text-only-chain-does-not-prove-rendered-result]
```

### 2. 生成结果观察尾段（`generated_result`）

```yaml
media_observed: false
observation_kind: generated_result
evidence_mode: creator_reported | authorized_media_inspection
observer_report:
  observer_ref: opaque-creator-or-authorized-observer
  observer_media_observed: true
observation_evidence:
  observed_media_ref: bounded-media-locator
  prompt_or_spec_refs: [exact-versioned-record-ref]
  reference_slot_conditions: [stable-slot-id-order-and-ref-set]
  production_configuration: bounded-project-configuration-or-unknown
  bounded_regions_or_intervals: [what-was-actually-observed]
  direct_observations: [creator-attributed-or-inspector-observation]
  limitations: [unseen-or-uncertain-content]
  valid_only_for: exact-project-prompt-reference-and-configuration-versions
```

### 3. 输入参考观察尾段（`input_reference`）

```yaml
media_observed: false
observation_kind: input_reference
evidence_mode: creator_reported | authorized_media_inspection
observer_report:
  observer_ref: opaque-creator-or-authorized-observer
  observer_media_observed: true
observation_evidence:
  observed_media_ref: bounded-media-locator
  input_reference_refs: [exact-versioned-reference-record-ref]
  bounded_regions_or_intervals: [what-was-actually-observed]
  direct_observations: [creator-attributed-or-inspector-observation]
  limitations: [occlusion-resolution-or-unseen-content]
  valid_only_for: exact-reference-version
```

## Decision card schema

```yaml
card_type: decision_card
decision_id: dec-internal-id
observation_refs: [obs-internal-id]
candidate_claim:
  problem: transferable-dramatic-or-production-problem
  heuristic: conditional-option-not-command
  expected_observable_effect: text-level-effect
  preserve_set: [upstream-fact-or-non-target-field]
classification: bounded_pattern | craft_option | rejected_generalization | conflict_pending
applies_when:
  genre_axes: [abstract-axis]
  audience_state: required-state
  character_state: required-state
  production_constraints: [text-production-constraint]
fails_or_changes_when:
  counterexample_refs: [obs-counterexample-id]
  warning_signals: [signal]
  alternatives: [alternative-mechanism]
conflicts:
  competing_claims: []
  resolution_or_open_question: explanation
sampling_role:
  matrix_cells: [genre-axis-x-mechanism-axis]
  next_contrast_to_read: abstract-sampling-intent
decision:
  status: hold | synthesize | narrow | reject | propose
  rationale: semantic-judgment-not-frequency
review:
  reviewer_ref: null
  reviewed_at: null
  notes: []
```

## 完全合成例子

```yaml
card_id: obs-synthetic-001
source_project_ref: synthetic-only
genre_axes:
  surface_genre: community-workplace-comedy
  audience_promise: overlooked-newcomer-earns-agency
  emotional_contract: embarrassment-turns-into-earned-recognition
mechanism_axes: [public-misreading, delayed-capability-proof]
observation:
  setup_state: the-audience-knows-the-newcomer-notices-a-routing-error
  pressure_or_question: speaking-up-risks-looking-incompetent
  character_action: the-newcomer-quietly-reroutes-one-delivery
  information_change: coworkers-see-the-result-before-the-reason
  turn_or_payoff: ridicule-reverses-only-after-a-specific-consequence
  downstream_translation: shots-preserve-who-knows-what-and-prompts-stage-the-action-before-the-reaction
counterevidence:
  searched: synthetic-alternate-scene
  findings: [early-explanation-removes-the-misreading-but-improves-closeness]
  alternate_explanations: [specific-consequence-may-matter-more-than-information-order]
```

对应 `decision_card` 应将结论限定为可选机制：当观众已知晓人物能力、场内人物仍误读且后果可表演时，可先呈现行动后果再解释原因；若题材承诺亲密协作或误读会损伤人物好感，则改用共同发现，不写成“逆袭题材必须延迟解释”。

## 题材 × 机制 coverage matrix

```yaml
cell_id: genre-axis-x-mechanism-axis
genre_and_promise: abstract-genre-plus-audience-promise
mechanism: dramatic-or-production-mechanism
supporting_observation_refs: []
opposing_observation_refs: []
boundary_notes: []
conflicts_or_alternatives: []
chain_gaps: []
confidence: empty | tentative | supported | conflicted
next_sample_intent: contrast-or-gap-to-seek
```
