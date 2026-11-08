# 多集整稿接入与断点续跑

当创作者给的是一份已经写好的多集剧本、散稿或合订稿，并希望生成或补齐
`项目开发/episode-map.jsonl` 时使用本流程。**Agent 判断这份文件实际怎样分集、每集讲了什么；
脚本保存精确定位并防止重复劳动**。小说改编走改编分析，整稿接入则按当前分集逐段读取。

## 不变边界

- 原文件原样保存在 `输入/`；byte span 按原始字节计算，CRLF 不做归一化。
- 自动标题识别只生成候选索引，不是对文件语义的裁决。不要为了迎合脚本而改写创作者原文。
- 不把整稿、全部分集正文或整季 map 塞进 heredoc、内联 Python、命令参数或单次模型上下文。
- `episode_intake.py` 不生成转折、回报、钩子等创作字段。它只做索引、校验、单集切分、
  完成集推导和 Agent 所写记录的原子合并。
- 批次没有通用固定值。Agent 先看索引里的各集 `byte_length`、实际复杂度和当前可用上下文，
  再为**本轮**明确选择 `--batch-size`；首轮宜保守，读过真实单集片段后可以调整。

## 1. 在工作区只建一次候选索引

```text
python3 <本技能目录>/scripts/episode_intake.py index \
  输入/<完整剧本> \
  --source-ref 输入/<完整剧本> \
  --out 项目开发/_work/episode-intake-index.next.json
```

脚本识别短独立行形式的 `第N集`、`第N集 标题` 与 Markdown `# EP N`，统一写成规范
`EP001` ID。索引只含行/字节跨度、长度与结构问题，不含正文。

退出码 `0` 表示机械结构自洽；退出码 `2` 表示候选文件已写入磁盘但有缺号、重号、空集或未识别等
问题。

`unmapped_spans` 用 locator 标出第一个集标题之前的前言与目录；插在集间的制作说明或尾注会被并入相邻集跨度且 `problems` 为空，需由 Agent 小范围检查每个 `unmapped_spans` 并读取每集首尾与疑似边界附近的几行，确认材料无遗漏、说明未混入正文，进而判断文件实际使用的分集规律（幕标题、分隔线、混合标题或目录加正文），不扩大自动正则去猜语义。

非标准结构由 Agent 写一个简短的 JSONL 边界文件（每行给规范 `episode_id` 与 1-based `line_start`，必要时给 `line_end`），再由工具推导精确 byte span 并阻断重号、跳号、倒序、空跨度和非规范 ID：

```jsonl
{"episode_id":"EP001","line_start":12}
{"episode_id":"EP002","line_start":58}
```

```text
python3 <本技能目录>/scripts/episode_intake.py manual-index \
  输入/<完整剧本> <临时边界.jsonl> \
  --source-ref 输入/<完整剧本> \
  --out 项目开发/_work/episode-intake-index.next.json
```

候选索引通过 `verify` 后保存到正式路径（core 项目工具可用时执行 `publish` 原子发布；独立运行时直接保存为 `项目开发/episode-intake-index.json`），确认下游已改读正式路径后再删除 `_work/` 候选：

```text
python3 <本技能目录>/scripts/episode_intake.py verify \
  项目开发/_work/episode-intake-index.next.json 输入/<完整剧本>

python3 <core 技能目录>/scripts/project_tool.py publish <项目根> \
  --owner short-drama-develop --artifact-id series:episode-intake-index \
  --output 项目开发/episode-intake-index.json=项目开发/_work/episode-intake-index.next.json \
  --input 输入/<完整剧本>
```

## 2. 每次只读当前集

切分单集前先运行 `verify`（核对总长度、跨度、顺序与行/字节对应；编辑过原文件必须重建索引，不沿用旧 locator）：

```text
python3 <本技能目录>/scripts/episode_intake.py verify \
  项目开发/episode-intake-index.json 输入/<完整剧本>

python3 <本技能目录>/scripts/episode_intake.py progress \
  项目开发/episode-intake-index.json 输入/<完整剧本> \
  项目开发/episode-map.jsonl --batch-size <本轮由 Agent 决定>

python3 <本技能目录>/scripts/episode_intake.py slice \
  项目开发/episode-intake-index.json 输入/<完整剧本> EP001 \
  --out <临时单集文件>
```

只读取 `next_batch` 指向的单集片段，携带已接受的紧凑前情、上一集交接和相关 map 记录写本集条目，不回读整稿。每完成一集先落到短 batch JSONL，再处理下一集。

## 3. 合并与发布

`merge` 将当前 map 与本轮 batch 合并写入新候选文件（拒绝未知 ID、批内重号、超上限记录及对已完成集的冲突重写；相同记录重放为 no-op）：

```text
python3 <本技能目录>/scripts/episode_intake.py merge \
  项目开发/episode-intake-index.json 输入/<完整剧本> \
  <本轮 batch.jsonl> 项目开发/episode-map.jsonl \
  --out 项目开发/episode-map.next.jsonl \
  --batch-size <本轮由 Agent 决定>
```

合并成功后发布到正式路径（core 工具可用时用 `publish`；独立运行时核对差异后保存为 `项目开发/episode-map.jsonl`），确认保存后再删除临时候选与单集片段：

```text
python3 <core 技能目录>/scripts/project_tool.py publish <项目根> \
  --owner short-drama-develop --artifact-id series:episode-map \
  --output 项目开发/episode-map.jsonl=项目开发/episode-map.next.jsonl \
  --input 输入/<完整剧本> \
  --input 项目开发/episode-intake-index.json
```

中断后重新运行 `progress`，以磁盘上的 `episode-map.jsonl` 为唯一完成真相（如已有 `EP001`、`EP003`，则 `EP002` 仍列在 `pending`）。全部 `pending` 清空后，再做所有者检查与创作者确认。
