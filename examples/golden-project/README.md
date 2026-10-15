# Golden Sample：善意不结账

这份八集现实题材短剧是历史结构化回归夹具，供维护者检查项目开发、剧本索引、资产、提示词、分镜和审查之间的引用。当前创作样例见 [creator-first/](../creator-first/)。

## 阅读顺序

1. `short-drama.json` 与 `输入/premise.md`
2. `项目开发/creative-brief.md`、`story-engine.md`、`episode-map.jsonl`
3. `剧集/EP001` 到 `EP008` 的剧本、资产和分镜目录
4. `设定集` 的跨集身份、视图和道具状态
5. `创作者决策` 中的资产与逐集接受记录
6. `审查/findings.jsonl` 与 `审查/verdict.json`

## 样例边界

- 所有剧情与人物均为公开样例改写，不保留来源系统标识或远程任务字段。
- 仓库只提交 UTF-8 文本和 JSON，不提交图片、音频、视频或供应商结果。
- Dashboard 只负责展示；这里的权威产物和校验入口仍归各 Skill 所有。
- 引用只声明上游产物的归属与路径，不带字节摘要；产物是否仍是被接受的那一版由项目状态判定，不由文件里的哈希判定。
- 规格内的 `candidate` 表示可预览的创作记录形态；是否接受只看 `创作者决策` 里那条独立记录，不靠改状态字样伪造。

## 独立校验

在仓库根目录运行各 Skill 自带的校验器。例如：

```bash
python3 skills/short-drama-assets/scripts/asset_check.py --characters examples/golden-project/设定集/characters.jsonl --looks examples/golden-project/设定集/looks.jsonl
python3 skills/short-drama-image-prompts/scripts/image_prompt_check.py examples/golden-project/剧集/EP001/assets/image-prompt-specs.jsonl
python3 skills/short-drama-storyboard/scripts/storyboard_check.py examples/golden-project/剧集/EP001/storyboard/coverage.json --shots examples/golden-project/剧集/EP001/storyboard/shots.jsonl --keyframes examples/golden-project/剧集/EP001/storyboard/keyframes.jsonl --project examples/golden-project/short-drama.json
python3 skills/short-drama-video-prompts/scripts/motion_timing_check.py examples/golden-project/剧集/EP001/storyboard/motion-specs.jsonl --shots examples/golden-project/剧集/EP001/storyboard/shots.jsonl
python3 skills/short-drama-review/scripts/review_check.py --findings examples/golden-project/审查/findings.jsonl --verdict examples/golden-project/审查/verdict.json
```

完整的可移植性、引用完整性、索引可重建性与生命周期演练由 `tests/test_golden_project.py` 覆盖。
