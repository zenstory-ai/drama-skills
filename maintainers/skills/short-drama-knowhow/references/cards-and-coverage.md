# 私有卡片与 Coverage Matrix

## 内容导航

- 卡片共通纪律
- Observation card schema
- Decision card schema
- 完全合成例子
- 题材 × 机制 coverage matrix

## 卡片共通纪律

卡片只保存在维护者指定的隔离工作区。用随机内部 ID、内容 hash 或抽象 locator 追溯证据；
不要在卡片之外复制整段剧本。观察和解释分栏，未知保持未知。一个项目要先通读完整文本链再制卡，
不能把搜索命中当作完整上下文。

`genre_axes` 描述题材、受众承诺和情绪合同；`mechanism_axes` 描述实现机制，不把桥段名当机制。
`evidence` 记录能复核的位置与观察，不记录可识别原文。`counterevidence` 即使为空也必须解释寻找范围。
先按项目实际存在的层还原 `version_refs`，只记录读到的版本引用，并把缺层放进 `missing_layers`；
再判断每层记录的 `source_role`，分清创作来源、派生投影、修改请求、执行任务与结果证据。
`creator_overrides` 单列，避免把创作者的明确取舍误读成系统规律。提示词存在、任务成功或提交次数
只说明流程活动，不能填进 `observation_evidence` 冒充效果证明。

`observation_kind` 按证据选择：只有项目文本、没有合格媒体观察报告时使用 `none`；输入参考观察使用
`input_reference`；生成结果观察使用 `generated_result`。后两者必须把 `evidence_mode` 写成
`creator_reported` 或 `authorized_media_inspection` 并填写对应的 `observation_evidence`；没有这份证据时
退回 `none`，只能提出文字风险，不能据此校准生产。本 skill 只读取文字；`media_observed` 专指
**制卡的维护者 agent 本人**是否看过媒体，因此始终为 `false`。创作者或另一个获授权观察者
是否看过媒体，写在 `observer_report.observer_media_observed` 并明确归因，不能借此声称本 agent 看过。
一张卡不能混合输入参考与生成结果观察；一条提示词同时承担多个职责时也分卡记录，避免把
身份（identity）、风格（style）、构图（composition）等职责压成一个含糊的 `prompt_role`。

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
```

共通头部的 `evidence.direct_observations` 只记录文本、记录版本和层间投影链；媒体尾段里的
`observation_evidence.direct_observations` 只记录授权观察者在所列区域或时间段实际看见/听见的现象。
不要把同一句发现复制到两处，也不要用后者保存任务状态、提示词摘要或因果解释。

在共通头部后，按实际证据**选择且仅选择一个完整尾段**；同一张卡不合并尾段或重复 YAML key。
`evidence_mode` 的可选值为
`evidence_mode: none | creator_reported | authorized_media_inspection`。

### 纯文本尾段（none）

```yaml
media_observed: false
observation_kind: none
evidence_mode: none
limitations: [text-only-chain-does-not-prove-rendered-result]
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

纯文本卡不建立一组全空的媒体字段。

### 生成结果观察尾段（generated_result）

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

### 输入参考观察尾段（input_reference）

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

以下为全新合成例子，演示观察与解释的抽象层级：

```yaml
card_type: observation_card
card_id: obs-synthetic-001
source_project_ref: synthetic-only
chain_read:
  available_layers: [brief, story, episode_map, screenplay, assets, continuity, image_prompt_text, storyboard_text, video_prompt_text, review]
  missing_layers: []
  version_refs:
    - layer: project
      ref: synthetic-project-v1
    - layer: screenplay
      ref: synthetic-script-v1
    - layer: storyboard_text
      ref: synthetic-board-v1
  creator_overrides: [none]
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
evidence:
  direct_observations:
    - locator: synthetic-screenplay-scene-03
      source_role: creative_source
      note: action-causes-visible-result-before-explanation
  agent_interpretation: withholding-the-reason-keeps-the-proof-dramatic-rather-than-verbal
  unknowns: [whether-a-warmer-genre-needs-a-softer-public-reaction]
media_observed: false
observation_kind: none
evidence_mode: none
limitations: [synthetic-text-only-example]
counterevidence:
  searched: synthetic-alternate-scene
  findings: [early-explanation-removes-the-misreading-but-improves-closeness]
  alternate_explanations: [specific-consequence-may-matter-more-than-information-order]
privacy:
  contains_source_wording: false
  contains_identifiers: false
  public_eligible: false
confidence: tentative
```

对应 decision card 应把结论限定为一个可选机制：当观众已理解人物能力、场内人物仍误读、且后果能被表演时，
可先呈现行动后果再解释原因；若题材承诺亲密协作或误读会破坏人物好感，就改用共同发现。不得写成
“逆袭题材必须延迟解释”。

## 题材 × 机制 coverage matrix

矩阵每一格使用以下记录，不用计数替代判断：

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

选样仪表可以显示各轴是否为空、哪些项目链缺层、哪些卡片互相冲突；它只能触发下一轮定性阅读。
禁止把格内项目数、题材占比、评分均值或高频词直接转换成写作公式、强制阈值或质量排序。
