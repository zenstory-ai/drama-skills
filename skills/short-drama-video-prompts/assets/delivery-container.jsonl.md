# `delivery-containers.jsonl` 填写模板

本文件保留用于旧格式追溯与离线回归。当前发行版将旧项目 JSON/JSONL 只读留存；继续按旧格式编辑须使用锁定的 `v0.5.0`。升级时在新项目根逐集确认五份 Markdown，不在同一根维护两套创作事实。下列填写或导出说明用于解释旧版格式。

每行一个交付容器对象。容器只是**已接受镜头的排布方式**：它记录哪些镜头按什么顺序装进
同一个交付单位，以及由此得出的容器时长。它不拥有镜头边界、目的、起止状态或时长——
这些仍属分镜；容器只引用它们并做加法。

只有创作者声明了分段或多镜打包的交付方式时才需要本文件；单镜交付不必创建容器记录，
`VID-13` 在那种情形下由运动规格自身的镜头时长满足。

文件第一行是 `sources` 声明：每个已接受上游快照在这里声明一次 `owner` 和 `artifact`，后续记录用
对应的 key 引用。key 由产物文件名派生，使用简短小写名字，在本文件内稳定且唯一。

```jsonl
{"record_type":"sources","schema_version":"1.0.0","sources":{"shots":{"owner":"short-drama-storyboard","artifact":"剧集/<EP>/storyboard/shots.jsonl"},"motion-specs":{"owner":"short-drama-video-prompts","artifact":"剧集/<EP>/storyboard/motion-specs.jsonl"},"short-drama":{"owner":"creator","artifact":"short-drama.json"}}}
```

其后每行一个容器记录，引用写 `src` 加它指向的记录 `record_id` 或字段 `field`：

```json
{
  "container_id": "CONT-<stable-id>",
  "status": "candidate",
  "production_profile_ref": {
    "src": "short-drama",
    "field": "/creator_authority/production_profile"
  },
  "members": [
    {
      "order": 1,
      "shot_ref": {
        "src": "shots",
        "record_id": "SHOT-<id>"
      },
      "motion_ref": {
        "src": "motion-specs",
        "record_id": "MOTION-<stable-id>"
      },
      "accepted_duration_ref": {
        "src": "shots",
        "record_id": "SHOT-<id>",
        "field": "/duration_seconds"
      },
      "accepted_duration": "<从 accepted_duration_ref 读到的值，投影不改写>",
      "location_binding_ref": {
        "src": "shots",
        "record_id": "SHOT-<id>",
        "field": "/location_binding"
      },
      "asset_bindings_ref": {
        "src": "shots",
        "record_id": "SHOT-<id>",
        "field": "/asset_bindings"
      }
    }
  ],
  "container_duration": "<各成员 accepted_duration 之和>",
  "membership_basis": {
    "source_order_contiguous": "<true | 说明为什么不连续及去向>",
    "binding_chain_equal": "<true | 说明哪一位成员的绑定不同、以及为什么仍同容器>",
    "scene_boundary_not_crossed": "<true | 说明跨越原因与已接受依据>"
  },
  "unresolved": [],
  "provenance": "creator_project"
}
```

## 结构校验点

容器记录供本地核对 `VID-13`，无需从渲染文本反推。带 ✓ 的由
[container_check.py](../scripts/container_check.py) 判定，其余由审查者核对：

1. ✓ `members[]` 非空，`order` 唯一、连续、升序；
2. 每条引用的 `src` 在本文件 `sources` 声明里找得到对应条目；
3. ✓ 每个成员的 `accepted_duration` 等于其 `shot_ref.record_id` 对应镜头的 `duration_seconds`；
   `accepted_duration_ref` 的来源和字段是否正确仍由审查者核对，脚本不解析这条引用；
4. ✓ `container_duration` 等于各成员 `accepted_duration` 之和；
5. 每个成员的 `motion_ref` 指向的运动规格，其 `shot_ref` 与该成员 `shot_ref` 解析到同一镜头记录；
6. **逐成员**解析 `location_binding_ref` 与 `asset_bindings_ref`，各成员解析结果相同时
   `binding_chain_equal` 才能为 `true`；只引用其中一条成员记录不构成证明。
7. ✓ `membership_basis` 三项均非空；结论的证据及未成立项是否写入 `unresolved` 由审查者核对。

任何一项不成立即为结构缺陷，按主技能的 `stale` 与恢复流程处理，不在渲染文本里补救。

## 依赖方向是单向的

容器 → 运动规格 → 镜头，**不存在反向的文件引用**。运动规格不带 `container_ref`：
两端在各自 `sources` 里互相声明对方会形成环：依赖方向必须单向，否则谁都不能先落盘。
文字上写“只读”不能消除这个环。

要从一个镜头反查它属于哪个容器，扫描容器记录的 `members[]`，不在运动规格里存副本。

## 与其他记录的关系

- **运动规格**：每条运动规格仍然只绑定一个 `shot_ref`，且不感知容器的存在。
- **渲染文本**：`video-prompts.md` 的容器一节由本记录派生，是缓存，不是权威；文本与本
  记录不一致时以本记录为准。
- **成员时长**：一律是分镜的只读投影。要改时长就改分镜，然后重算 `container_duration`；
  不得在容器里直接改数。
- **成员资格判据**：语义部分见 `references/delivery-profile.md` 的多镜容器成员资格；
  本文件只负责让判据的结论可被引用与核对。

复制后删除不适用的可选字段。容器不跨越已接受的场次或时间跳跃；省略、闪回分支与声明过的
蒙太奇各自单独成容器。
