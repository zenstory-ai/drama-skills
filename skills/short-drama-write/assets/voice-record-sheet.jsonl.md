# `voice-record-sheet.jsonl` 填写模板

本模板用于维护旧版结构化项目中已有的录音表。当前五文档创作路径只写 `剧本.md`，不生成本表；
以下快照与块引用沿用旧项目格式，不作为新项目的交付要求。

每行一条待录台词。这份表是**剧本的投影，不是第二份台词权威**：`line_text` 必须逐字
等于 `source_ref` 指向的剧本块，需要改词就改剧本再重新投影，不在这里改。示例值不是
默认答案；不适用的字段删掉，不要添加媒体任务、供应商或接口。

按人物集中录音时，配音者需要补足剧情上下文：角色此刻知道什么、对谁说、接谁的话，以及这句要
达成什么。本表将这些信息与逐字台词放在一起。

第一行声明本表引用的上游快照，一个快照只写一次：

```json
{"record_type": "sources", "schema_version": "1.0.0", "sources": {"screenplay-index": {"owner": "short-drama-write", "artifact": "剧集/EP001/screenplay-index.jsonl"}}}
```

其后每行一条待录台词，`source_ref` 用 `src` 指向上面声明的快照，加 `record_id` 指向其中的剧本块：

```json
{
  "line_id": "VLINE-EP001-SC001-003",
  "episode_id": "EP001",
  "scene_id": "EP001-SC001",
  "speaker": "CHAR-<id>",
  "speaker_display": "<剧本里逐字写的那个名字>",
  "line_text": "<逐字等于剧本块原文的冒号之后部分>",
  "source_ref": {
    "src": "screenplay-index",
    "record_id": "BLK-EP001-SC001-D03"
  },
  "channel": "sync | dubbed | VO | OS",
  "lip_sync_constrained": true,
  "addressed_to": ["CHAR-<id>"],
  "preceding_line_id": "VLINE-EP001-SC001-002",
  "speaker_knows_now": "<此刻他知道什么、还不知道什么>",
  "tactic": "<质问 | 试探 | 收回 | 交换 | 拖延……：这一句要达成什么>",
  "pronunciation_notes": [
    {
      "surface": "<多音字、生僻字、专名或数字>",
      "reading": "<确定读法>",
      "decided_by": "creator | <role>:<stable-id>"
    }
  ],
  "target_seconds": null,
  "unresolved": []
}
```

## 字段用途

| 字段 | 不写会怎样 |
|---|---|
| `source_ref` | 剧本改一句而表没跟上，录出来的是旧词；绑定了块 ID 才能切出剧本原字节逐字比对 |
| `speaker` 与 `speaker_display` | 前者绑定资产身份，后者保留剧本里逐字写的名字，避免把身份编号与显示名混用 |
| `channel` 与 `lip_sync_constrained` | 同期与配音、画内与 VO 的可改余地完全不同，混在一起就只能按最严的来。`channel` 必须与它投影的块一致：`[VO]` / `[OS]` 块只能记为同名声道或 `dubbed`，画内对白块不能记成 VO/OS——校验器判定，诊断码 `VOICE_CHANNEL_DISAGREES_WITH_BLOCK` |
| `addressed_to` / `preceding_line_id` | 集中录制时配音者不知道在对谁说、接谁的话，语气只能靠猜 |
| `speaker_knows_now` | 同一句话在“已经知道”和“还不知道”时可能有不同读法，须服从角色此刻的知情边界 |
| `tactic` | 写明这句要怎样影响对方，可参考本技能对白方法的策略库 |
| `pronunciation_notes` | 专名、多音字和数字的确定读法在录音前确认并记录 |
| `target_seconds` | 有画面时长约束的行要提前知道，不要在混录时才发现塞不下 |

## 诊断码

以下列出逐字投影与结构的诊断码；`voice_sheet_check.py` 不判断配音表演。

| 代码 | 分级 | 判定者 | 含义 |
|---|---|---|---|
| VOICE_LINE_HAS_NO_ID | structural_invariant | validator | 配音行没有 `line_id` |
| VOICE_LINE_ID_REPEATS | structural_invariant | validator | `line_id` 重复 |
| VOICE_CHANNEL_INVALID | structural_invariant | validator | `channel` 不是 sync / dubbed / VO / OS |
| VOICE_CHANNEL_DISAGREES_WITH_BLOCK | structural_invariant | validator | `channel` 与它投影的块不符：画外音块记成画内，或画内对白记成 VO/OS |
| VOICE_SOURCE_REF_MISSING | structural_invariant | validator | `source_ref` 没有指向任何上游快照 |
| VOICE_SOURCE_REF_UNDECLARED | structural_invariant | validator | `src` 在本文件 `sources` 里没有对应条目 |
| VOICE_SOURCE_REF_UNRESOLVABLE | structural_invariant | validator | `record_id` 在剧本索引里找不到 |
| VOICE_SOURCE_IS_NOT_DIALOGUE | structural_invariant | validator | 配音行投影的块不是台词，也不是 `[VO]`/`[OS]` |
| VOICE_BLOCK_SPAN_INVALID | structural_invariant | validator | 索引记的块跨度装不进这份剧本，或落在半个字符上（索引已过期） |
| VOICE_BLOCK_IS_UNPARSEABLE | structural_invariant | validator | 台词块不符合文档写明的行语法 |
| VOICE_LINE_TEXT_DIVERGED | structural_invariant | validator | `line_text` 与剧本原字节不一致——**以剧本为准** |
| VOICE_SPEAKER_DIVERGED | structural_invariant | validator | `speaker_display` 与剧本里写的名字不一致 |
| SOURCE_ENTRY_IS_INCOMPLETE | structural_invariant | validator | 引用解析器发现 `sources` 条目缺 `owner` 或 `artifact`；本表校验输出时归为 `VOICE_SOURCE_REF_UNDECLARED` |

## 边界

- **本表不拥有台词文字、说话人和信息权限**，它们属于剧本；本表也不拥有逐镜的音频实现
  （空间化、层级、与画面的对位），那属于视频提示词环节，本表只引用不复制。
- 表里出现与剧本不一致的文字时，**剧本为准**，把差异作为 `unresolved` 记下来交给
  负责人，不要就地"顺一下"。
- 本表不生成音频、不调用任何语音服务，也不从文字判断成品音质；实际 TTS 交给
  `$short-drama-produce`，并须在看到本次任务预览后明确确认。
