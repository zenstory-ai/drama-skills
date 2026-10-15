# `motion-specs.jsonl` 填写模板

本文件保留用于旧格式追溯与离线回归。当前发行版将旧项目 JSON/JSONL 只读留存；继续按旧格式编辑须使用锁定的 `v0.5.0`。升级时在新项目根逐集确认五份 Markdown，不在同一根维护两套创作事实。下列填写或导出说明用于解释旧版格式。

文件第一行是 `sources` 声明：每个已接受上游快照在这里声明一次 `owner` 和 `artifact`，后续记录用
对应的 key 引用。key 由产物文件名派生，使用简短小写名字，在本文件内稳定且唯一。
本阶段插入的片段（[`performance.fragment.json`](performance.fragment.json)、
[`coverage-scope.fragment.json`](coverage-scope.fragment.json)）落进同一个文件，它们用到的 key
也在这里声明。

```jsonl
{"record_type":"sources","schema_version":"1.0.0","sources":{"shots":{"owner":"short-drama-storyboard","artifact":"剧集/<EP>/storyboard/shots.jsonl"},"keyframes":{"owner":"short-drama-storyboard","artifact":"剧集/<EP>/storyboard/keyframes.jsonl"},"screenplay-index":{"owner":"short-drama-write","artifact":"剧集/<EP>/screenplay-index.jsonl"},"characters":{"owner":"short-drama-assets","artifact":"设定集/characters.jsonl"},"short-drama":{"owner":"creator","artifact":"short-drama.json"}}}
```

其后每行一个候选运动规格对象。引用写 `src` 加它指向的记录 `record_id` 或字段 `field`；
`boundary_refs` 只读，候选状态属于本运动规格，不向已经接受的上游引用传播。不要加入
`duration_override`、`end_override` 或 `next_shot_write`。以下字符串只说明怎样填写，
不是固定答案。

```json
{
  "motion_id": "MOTION-<stable-id>",
  "status": "candidate",
  "shot_ref": {
    "src": "shots",
    "record_id": "SHOT-<id>"
  },
  "keyframe_ref": {
    "src": "keyframes",
    "record_id": "KEY-<id>"
  },
  "production_profile_ref": {
    "src": "short-drama",
    "field": "/creator_authority/production_profile"
  },
  "boundary_refs": {
    "duration": {
      "src": "shots",
      "record_id": "SHOT-<id>",
      "field": "/duration_seconds",
      "value_seconds": 0.0
    },
    "start": {
      "src": "shots",
      "record_id": "SHOT-<id>",
      "field": "/start_boundary"
    },
    "primary_transition": {
      "src": "shots",
      "record_id": "SHOT-<id>",
      "field": "/primary_transition"
    },
    "end": {
      "src": "shots",
      "record_id": "SHOT-<id>",
      "field": "/end_boundary"
    },
    "next_start": {
      "src": "shots",
      "record_id": "SHOT-<next-id>",
      "field": "/start_boundary",
      "access": "comparison_only"
    }
  },
  "reference_bindings": [
    {
      "slot_id": "REF-<stable-slot>",
      "order": 1,
      "artifact_ref": {
        "src": "keyframes",
        "record_id": "KEY-<id>"
      },
      "role": "start_frame | continuity_video | actual_tail_frame",
      "may_control": [
        "<本镜 accepted 起始构图与可见状态>"
      ],
      "must_not_control": [
        "<尚未发生的动作/终态/无权威文字>"
      ],
      "admission_status": "unverified | creator_described | visually_inspected",
      "reference_observation_ref": null,
      "unresolved_risks": [
        "<没有观察证据时保留的文字/水印/裁切风险>"
      ]
    }
  ],
  "start_anchor": {
    "pose_balance": "<仅运动必需>",
    "gaze": "<目标>",
    "hands": {
      "left": "<状态>",
      "right": "<状态>"
    },
    "held_props": [
      "<exact binding + hand>"
    ],
    "spatial_relations": [
      "<与行动对象的关系>"
    ]
  },
  "ordered_subject_motion": [
    {
      "order": 1,
      "actor": "<asset binding>",
      "trigger": "<accepted cue>",
      "action": "<可见动作>",
      "direction_or_path": "<方向/路径>",
      "object_or_contact": "<对象/接触>",
      "result": "<阶段结果>",
      "timing": {
        "mode": "relative | explicit",
        "value": "<顺序词或秒区间>"
      }
    }
  ],
  "camera": {
    "behavior": "locked | move | transition",
    "motivation": "reveal | pressure | alignment | relationship | transition | deliberate_stillness",
    "intervals": [
      {
        "range": "<相对阶段或秒区间>",
        "mode": "<lock/pan/tilt/dolly/handheld/follow>",
        "path_tempo": "<方向/节奏>",
        "endpoint": "<在 accepted framing/boundary 内>"
      }
    ]
  },
  "environment_motion": [
    {
      "element": "<已有环境元素>",
      "motion": "<有剧情意义的变化>",
      "cause": "<连续性/主体动作>"
    }
  ],
  "audio": [
    {
      "source_ref": {
        "src": "screenplay-index",
        "record_id": "BLK-<EP>-<SC>-D<nn>"
      },
      "speaker_ref": {
        "src": "characters",
        "record_id": "CHAR-<id>"
      },
      "voice_direction_ref": {
        "src": "characters",
        "record_id": "CHAR-<id>",
        "field": "/voice_direction"
      },
      "kind": "dialogue | VO | OS | SFX | ambience | music",
      "exact_text": "<仅 source 有文本时逐字引用>",
      "delivery_or_spatial_intent": "<不改文本的表演/声源/层级>",
      "timing": "<相对阶段或秒区间>"
    }
  ],
  "timing_plan": {
    "mode": "relative | explicit",
    "phases": [
      "<阶段、overlap 与 landing 空间>"
    ],
    "declares_overlap": false,
    "declared_total_or_endpoint_seconds": 0.0
  },
  "end_report": {
    "projection": {
      "pose": "<reported>",
      "position": "<reported>",
      "gaze": "<reported>",
      "hands": "<reported>",
      "held_props": "<reported>",
      "visible_state": "<reported>"
    },
    "comparison": "match | mismatch | unrealized",
    "differences": []
  },
  "reference_frame_economy": {
    "frame_carries": [
      "appearance",
      "composition",
      "base lighting"
    ],
    "repeated_for_motion_only": [
      "<hand/prop/path 等必要局部>"
    ]
  },
  "creator_overrides": [
    {
      "rule_id": "<VID-*>",
      "choice": "<覆盖>",
      "rationale": "<理由>"
    }
  ],
  "generic_prompt": "<把本规格渲染成一段只含要拍出来的画面的交付文本：从已接受起点的姿态与持物说起，逐条写动作、接触、摄影机行为与终点状态；不写镜头/记录 ID、规则 ID、状态词、工艺备注与成段否定罗列；写满的样子见 references/production-prompt-grammar.md>",
  "derivation": {
    "recipe_version": "<version>"
  },
  "provenance": "creator_project"
}
```


运动规格**不带指回交付容器的引用**。依赖方向只有一条：容器 → 运动规格 → 镜头。两端在各自
`sources` 里互相声明对方会形成环——依赖方向必须单向，
无法按上游先于下游的顺序形成稳定快照。要找某个镜头属于哪个容器，从容器记录的 `members[]` 反查，不在本文件里
存副本。容器记录见 [delivery-container.jsonl.md](delivery-container.jsonl.md)。

默认 master 不重复 `purpose_ref` 或 `coverage_scope`：镜头目的、场次计划与原文覆盖从准确
`shot_ref` 及其上游读取。只有 pickup/alternate 才按
[motion-recipe.md](../references/motion-recipe.md) 增加 `coverage_scope`，记录相对母版的补充、保留与去向。
`boundary_refs` 只保留结构校验需要的 duration/start/end/next-start 精确字段投影，不再重复镜头目的、
场次计划或原文职责；删除它前必须先让 timing 与 continuity 校验器能从 `shot_ref` 安全解析同一快照。

普通记录省略 `performance_arcs[]` 与 `attention_handoffs[]`；存在可见表演变化或注意交接时，按
[`performance.fragment.json`](performance.fragment.json) 插入完整字段。空镜、道具细节、纯空间
转场和只有物理动作的镜头不编造 arc。多参考的 `slot_id` 稳定且 `order` 唯一。
`end_report` 只作终点比较；末镜没有真实下一镜时，移除 `boundary_refs.next_start`，改用
`next_start_locator` 描述未来起点的定位信息，写法见 `motion-terminal.example.jsonl`。该定位信息未解析前不能证明连续性已匹配。附加参考为空时使用空数组；对白说话者与声音方向只有在已接受引用存在时才填写。
母版、补拍和替代关系保留在同一规格文件内，替代决定由审查结论拥有。具体取舍按
`references/motion-recipe.md` 与 `references/review-and-fixtures.md` 判断。
