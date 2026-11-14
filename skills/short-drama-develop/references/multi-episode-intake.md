# 多集完整剧本导入与分段续拆

当创作者给来一份已经写好的多集完整剧本、散稿、局部选集或合订稿，希望据此生成或更新 `项目开发/episode-map.jsonl` 时走本流程。**Agent 判断这份文件实际怎样分集、每集讲了什么；脚本负责记准行号字节位置，免得返工重拆**。

## 硬性边界

- 原稿原封不动保存在 `输入/`；字节跨度按原始字节计算，CRLF 换行符不做改写，绝不为迁就脚本去改创作者原稿。
- 不把整部多集剧本或整季分集大纲一次性塞进单次对话上下文、heredoc 或命令行参数。
- `episode_intake.py` 不生成转折、回报、钩子等创作字段。它只负责建索引、做校验、切单集片段、推算待拆集数，以及把 Agent 写好的分集记录原子合并落盘。
- 批次没有通用固定值。Agent 先看索引里各集的 `byte_length`、剧情复杂度和当前剩余上下文空间，再为本轮敲定合适的 `--batch-size`。

## 1. 建候选索引（支持非第 1 集起步与跳集选拆）

```text
python3 <本技能目录>/scripts/episode_intake.py index \
  输入/<完整剧本> \
  --source-ref 输入/<完整剧本> \
  --out 项目开发/_work/episode-intake-index.next.json
```

脚本自动识别独立短行的 `第N集`、`第N集 标题` 与 Markdown `# EP N`，转为标准 `EP001` 格式。索引**允许不从第 1 集起步，也允许跳集**（例如只导入第 5～10 集分卷稿，或只抽第 1、8、12 集试拆高潮集）；退出码 `0` 表示集号按源码出现顺序严格递增且无重号、无空集，退出码 `2` 表示存在重号、倒序、空集或未识别出标题等问题。

`unmapped_spans` 会标出第一个分集标题之前的序言与目录位置，但夹在两集之间的制作备注或尾注会归入前一集末尾。Agent 须查看 `unmapped_spans` 并抽读切口前后几行文字确认分集边界；遇到幕标题、分隔线等非标准写法时，手写简短的边界 JSONL（填标准 `episode_id`、`line_start` 及可选 `line_end`）生成精确索引：

```jsonl
{"episode_id":"EP005","line_start":12}
{"episode_id":"EP008","line_start":58}
```

```text
python3 <本技能目录>/scripts/episode_intake.py manual-index \
  输入/<完整剧本> <临时边界.jsonl> \
  --source-ref 输入/<完整剧本> \
  --out 项目开发/_work/episode-intake-index.next.json
```

候选索引跑通 `verify` 后存到正式路径 `项目开发/episode-intake-index.json`（项目内有 core 工具时可用 `publish` 原子发布）：

```text
python3 <本技能目录>/scripts/episode_intake.py verify \
  项目开发/_work/episode-intake-index.next.json 输入/<完整剧本>
```

## 2. 每次只切当前批次要读的那几集

切单集文本前先跑 `verify`（原稿一旦改动必须重建索引，不拿旧位置硬切）：

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

每次只读 `next_batch` 列出的那几集切片与上一集末尾交接，写完一集追加进本轮临时 batch JSONL。

## 3. 合并落盘、修订覆盖与分段续拆

`merge` 把现有分集大纲与本轮 batch 按索引集序合并落盘：**允许用新批次中的同 `episode_id` 记录覆盖更新已有分集记录**（返回 `added` 与 `updated` 列表；完全一致的记录重放自动幂等跳过），同时严守核心护栏——**拒绝写入任何不在索引声明 `episode_ids` 集合内的未知集号**、同批重复集号或超出 `--batch-size` 上限的批次：

```text
python3 <本技能目录>/scripts/episode_intake.py merge \
  项目开发/episode-intake-index.json 输入/<完整剧本> \
  <本轮 batch.jsonl> 项目开发/episode-map.jsonl \
  --out 项目开发/episode-map.next.jsonl \
  --batch-size <本轮由 Agent 决定>
```

核对无误后保存至 `项目开发/episode-map.jsonl`（或通过项目工具 `publish` 发布）并清理临时文件。中途断开后重跑 `progress`，自动按磁盘现有记录推导剩余 `pending` 集号。
