# Golden Sample：善意不结账

这套八集温情现实短剧是仓库的历史结构化回归夹具，供维护者校验项目开发、剧本索引、资产设定、提示词、分镜与审查之间的跨文件引用。日常创作的五文档入口见 [creator-first/](../creator-first/)。

## 阅读顺序

1. `short-drama.json` 与 `输入/premise.md`
2. `项目开发/creative-brief.md`、`story-engine.md`、`episode-map.jsonl`
3. `剧集/EP001` 到 `EP008` 的剧本、资产和分镜目录
4. `设定集` 的跨集人物身份、场景视图和道具状态
5. `创作者决策` 中的资产与逐集确认记录
6. `审查/findings.jsonl` 与 `审查/verdict.json`

## 样例边界

- 所有剧情与人物均为公开合成样例，不含外部客户项目标识或远程任务字段。
- 仓库只提交 UTF-8 文本和 JSON，不提交图片、音频、视频或供应商返回文件。
- Dashboard 只负责浏览展示；旧结构化记录的校验器已迁入 `tests/legacy/`，不再随技能分发。
- 引用只声明上游产物的归属与路径，不捆绑字节哈希；产物是否有效以项目确认记录为准。
- 规格内的 `candidate` 仅表示待确认草稿；是否正式通过只看 `创作者决策` 里的独立记录。

## 独立校验

这些 JSON 记录只能由已退役的旧格式检查器校验；检查器不再随技能发货，留在 `tests/legacy/` 供回归使用。在仓库根目录运行，例如：

```bash
python3 tests/legacy/short-drama-assets/scripts/asset_check.py --characters examples/golden-project/设定集/characters.jsonl --looks examples/golden-project/设定集/looks.jsonl
python3 tests/legacy/short-drama-image-prompts/scripts/image_prompt_check.py examples/golden-project/剧集/EP001/assets/image-prompt-specs.jsonl
python3 tests/legacy/short-drama-storyboard/scripts/storyboard_check.py examples/golden-project/剧集/EP001/storyboard/coverage.json --shots examples/golden-project/剧集/EP001/storyboard/shots.jsonl --keyframes examples/golden-project/剧集/EP001/storyboard/keyframes.jsonl --project examples/golden-project/short-drama.json
python3 tests/legacy/short-drama-video-prompts/scripts/motion_timing_check.py examples/golden-project/剧集/EP001/storyboard/motion-specs.jsonl --shots examples/golden-project/剧集/EP001/storyboard/shots.jsonl
python3 tests/legacy/short-drama-review/scripts/review_check.py --findings examples/golden-project/审查/findings.jsonl --verdict examples/golden-project/审查/verdict.json
```

完整的可移植性、引用完整性、索引可重建性与生命周期演练由 `tests/test_golden_project.py` 覆盖。
