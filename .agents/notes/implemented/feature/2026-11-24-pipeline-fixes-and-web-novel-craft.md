# Agent Note: 端到端流程脚本边界修复与网文改编语感工艺升级

Status: implemented

## Problem

在多集网文改编与单集全链路实跑中，套件在工具链边界与改编工艺两方面暴露出一组高摩擦问题：

1. **原著拆解与网文前置块冲突**：不少网文或导出的长篇文本在第一章正文前带有超过 500 字的书目元数据、作者说明或目录块；`novel_index.py` 原先对超过 500 字的前置文本一律硬报错，迫使创作者修改只读 `输入/` 原文或手动裁切。
2. **剧本估时遇外文借词整项丢字段与标签口径分裂**：中文现代剧剧本常夹带少量英文缩略语或外文借词（如 `CEO`、`PPT`、`VIP`、`offer`）。当项目只声明 `spoken_characters_per_second` 而未声明 `spoken_words_per_second` 时，`duration_estimate.py` 会直接省略整集 `speech_seconds` 与 `speech_share`；另外，声明 `on_screen_text_characters_per_second` 后，`untimed.tag_lines` 移除了 `画面文字`，但 `counts.untimed_tag_lines` 仍保留该键，双口径不一致。
3. **分集大纲缺乏确定性结构检查**：`short-drama-develop` 在 `v0.13.0` 将 `episode-map.jsonl` 收敛为 12 键扁平核心架构后，尚无本地脚本验证 JSONL 语法、集号唯一递增、核心键完整性与原著章节映射越界。
4. **单镜视频提示词对白超载与复合景别漏计**：视频提示词里常在短镜内塞入超长台词导致出片语速崩坏，此前缺乏按项目已声明语速核算的软提醒；本地创作台 `creator_views.py` 仅做景别精确集合匹配，会把 `中景缓推至近景`、`中景推至特写`、`全景推进至手部细节` 及英文 `close-up` / `detail shot` 等常见复合/英文写法漏计，拉低近景占比统计。
5. **剪辑单纸面预检与单句行内定时字幕缺口**：音视频素材尚未生成前，`edit_tool.py check` 会因缺少本地文件直接报错，无法先对纸面《剪辑单.md》做入出点算术、来源 ID、逐字字幕与路径安全预检；同时单句字幕若写作 `- 字幕：<起>-<止> <台词>`（未编号行内定时），原解析器无法提取纯台词。
6. **网文改编语感与包袱在跨阶段流转中衰减**：原著拆解只记剧情事件与爽点结果，不留说话锋芒、短回合呼吸与前后呼应包袱锚点，导致大纲压缩与写剧本阶段容易写成平淡信息播报，或把未说出口的内心独白混进普通动作行；同时 `creative-brief.md` 与 `short-drama/SKILL.md` 的节奏与中文配置示例容易被误读为僵化默认值。

## Decision

严格遵循「知识与做法优先 + 软门禁原则」（不新增硬性创作门槛、不改 `stage-contract.md` 阻断规则表、不引入跨技能运行时依赖），分四条线落地修复与增强：

1. **上游确定性脚本修复与补齐（`short-drama-write`、`short-drama-novel-analyze`、`short-drama-develop`）**：
   - `skills/short-drama-write/scripts/duration_estimate.py`：当存在已计价发声内容（`speech > 0`）但同时含未配速的外文借词时，照常输出已计价部分的 `speech_seconds` 与 `speech_share` 并标注 `"speech_partial": true`，同时保留 `untimed_speech` 提示；全篇未计价（`speech == 0` 且 `unpriced` 非空）时仍省略这两个字段以维持既有契约。当 `rates["declared"]` 为真且声明 `on_screen_text_characters_per_second` 时，同步从 `counts["untimed_tag_lines"]` 与 `untimed["tag_lines"]` 移除 `画面文字`（清空后一并省略键）。
   - `skills/short-drama-novel-analyze/scripts/novel_index.py`：为 `index` 与 `verify` 新增 `--ignore-preamble`。默认仍对超过 500 字的未索引前文硬拦截以防误漏真正的楔子正文；显式传入 `--ignore-preamble` 时，在 `_index.json` 持久化 `"preamble_ignored": true`，将超长前置块降级为软 `warnings` 并返回退出码 `0`，后续 `verify` 自动识别该标记放行且继续严格核对正文行号、字数与标题漂移。无章节文件仍硬阻断。
   - `skills/short-drama-develop/scripts/episode_intake.py`：新增 `check-map <episode-map.jsonl> [--novel-index <_index.json>]` 子命令与 `check_episode_map()`，并在 `skills/short-drama-develop/SKILL.md` 补充调用入口。硬门禁（退出码 `1`）仅覆盖 UTF-8/JSONL 语法、非空、规范唯一且严格递增的 `episode_id`、12 个扁平核心键存在性与基础类型及 `__FILL__` 未填占位符；跳集、空文本/空列表以及可选原著章节区间（`source_chapters`/`chapter_range`/`source_chapter_span`/`source_span`）越界或空映射一律作为软 `warnings` 输出（退出码 `0`）。
2. **核心校验软告警、复合景别统计与中文配置对齐（`short-drama`）**：
   - `skills/short-drama/scripts/creator_markdown_check.py`：新增 `_check_motion_speech_rates()`，仅在 `short-drama.json` 显式声明 `format.pacing.spoken_characters_per_second` 和/或 `spoken_words_per_second` 时启用（绝不自造默认语速）。从每条 `MOTION-...` 可复制提示词中抽取发声台词（兼容 `<d>...</d>`、Seedance `{...}` 及中英文说话引导引号，排除屏幕/招牌可读文字与“听到/说到……二字”引用），沿用与 `duration_estimate.py` 一致的 `_voiced_units()` 折算实读秒数；超出镜长 `1.35x`（`SPEECH_RATE_WARN_RATIO = 1.35`）时仅输出软门禁 `WARNING`（`VID-05`），退出码保持 `0`。
   - `skills/short-drama/scripts/creator_views.py`：新增 `shot_scales()` 与 `is_close_framing()`，在保持 `CLOSE_SCALES = {"近景", "特写", "大特写", "细节"}` 不变的前提下识别中文复合过渡景别（如 `中景缓推至近景`、`中景推至特写`、`近特写`、`全景推进至手部细节`）与英文等价景别（`close-up`、`extreme close-up`、`close shot`、`detail shot`、`medium close-up`、`medium shot push to close-up` 等），同时不误判纯 `中景`/`全景`/`远景`/独立 `中近景` 或非过渡性“环境细节”。
   - `skills/short-drama/SKILL.md`：补齐 `--prompt-language zh-CN`、`spoken_words_per_second` 配置示例、各视频模型原生时长区间说明（Seedance 2.5 为 `4–30` 秒，Seedance 2.0 / MiniMax H3 为 `4–15` 秒），并在硬/软门禁说明中补列单镜对白超载软提醒。
3. **剪辑单无编号定时字幕与纸面预检模式（`short-drama-edit`）**：
   - `skills/short-drama-edit/scripts/edit_tool.py`：收紧 `SUBTITLE_WINDOW` / `SUBTITLE_CUE` 数值正则为 `[0-9]+(?:\.[0-9]+)?` 防止畸形小数抛 `ValueError`；在 `_parse_subtitles()` 中为无编号 `- 字幕：`（含冒号入加粗写法）支持行内 `<起>-<止> <台词>` 提取纯台词与重点词，保持 `- 字幕时间：` 完全向后兼容，并以 `EditError` 明确拦截行内定时与 `- 字幕时间：` 混用等冲突写法。
   - 同一脚本新增 `check --plan-only`（支持与 `--partial` 组合），通过 `_has_symlink_component()` 与 `_inspect_media_path()` 明确区分 `ok` / `missing` / `unsafe`（绝对路径、Windows 盘符、越界 `..`、任意符号链接含悬空/父目录软链、非文件目录）。纸面预检保留全部确定性文档与安全硬阻断，对已有素材照常 `ffprobe`，仅将尚未生成的本地素材缺失降级为 `提醒`、输出 `"模式": "plan-only"` 并在 `未测` 如实列出；标准 `check` / `render` 不受任何削弱，`render` / `verify` 传 `--plan-only` 直接报错。同步更新 `skills/short-drama-edit/SKILL.md` 与 `references/format-spec.md`。
4. **网文改编语感与轻喜直球对白工艺升级（4 个技能，全为 `craft_default`）**：
   - `skills/short-drama-novel-analyze`：`SKILL.md` 补充 `novel_index.py index --ignore-preamble` 用法并关联语感锚点；`references/chapter-extraction.md` 与 `references/adaptation-value.md` 新增 1–3 行「原著语感与高光包袱锚点」（严守 `NVA-04` 不照抄整段）。
   - `skills/short-drama-develop`：`references/adaptation-craft.md` 将回查原著扩展至语感节奏/包袱原型并增补「保包袱完整优先于保事件数量」；`assets/creative-brief.md` 澄清 `rhythm_profile` JSON 为可手改起步示例，提示按视频模型最短原生时长调整 `target_avg_shot_seconds` 或改走多镜合生。
   - `skills/short-drama-write`：`references/dialogue-craft.md` 新增 `## 11. 网文轻喜与直球爽剧对白`（含两则 100% 原创合成对照）；`references/script-craft.md` 明确动作段短促分拍、禁止把未说出口的内心独白混进普通动作行（应外化为可见反应或显式 `[VO]`/`[OS]`）。
   - `skills/short-drama-review`：`references/rubric-story-script.md` 新增 3 条 `craft_default` 改编语感与包袱完整性抽查项，不改动 `stage-contract.md` 阻断规则表。

## Alternatives considered

- **为 `creator_markdown_check.py` 内置固定默认语速（如 4.5 字/秒）并将超速设为硬 `ERROR`**。最强理由：项目未配置 `format.pacing` 时也能立即拦截过长台词。被否：违背仓库软门禁原则与「不把统一配方写死成代码门槛」的硬规则——语速因题材、语种与表演节奏差异极大，未声明语速时自造默认值会制造大量误报，且超过 1.35 倍也可能存在合理快语速/叠音场景，因此仅在项目显式声明语速时触发、且只输出软 `WARNING`。
- **把 `novel_index.py` 默认改成自动忽略全部前置文本，或把 500 字阈值大幅放宽**。最强理由：不需要创作者额外传 `--ignore-preamble`。被否：网文与出版小说中，第一章标题前常出现真正的「楔子」「序幕」「引子」正文，静默忽略会导致正文首段被无声丢弃；改为默认保持拦截、显式 `--ignore-preamble` 并在 `_index.json` 持久化标记，才能把“跳过说明块”变成创作者有意识的选择。
- **在 `duration_estimate.py` 里为未配置的外文借词按固定默认英文语速估算**。最强理由：避免出现 `speech_partial` 标记。被否：同样违背“不替项目捏造未声明语速”的原则；只计已声明语速部分、照常产出 `speech_seconds` / `speech_share` 并如实标注 `speech_partial: true` 与 `untimed_speech`，既不丢数据也不虚构口径。
- **把 `edit_tool.py check --partial` 直接改成允许缺少全部素材**。最强理由：减少一个 CLI 参数。被否：`--partial` 的既有语义是“已生成部分镜头做局部试剪，仍要求剪辑单中引用到的每条素材真实存在可读”；把它放宽成允许缺失文件会破坏现有局部试剪门禁。独立的 `--plan-only` 让“有媒体局部试剪”与“无媒体纸面预检”语义清晰互斥。
- **把改编语感与包袱完整性写进 `stage-contract.md` 作为新的 `reviewed_invariant` 规则 ID**。最强理由：审稿时具备更高威慑力。被否：语感保留度与喜剧包袱取舍高度依赖题材定位与创作者口味，属于 `craft_default` 而非跨题材通用阻断底线，写进阻断规则表会破坏规则分级边界。

## Consequences

- **收益**：
  - 全链路 6 个高频技能（`short-drama`、`short-drama-novel-analyze`、`short-drama-develop`、`short-drama-write`、`short-drama-edit`、`short-drama-review`）的脚本边界与工艺短板一次收口，覆盖原著导入、分集大纲核对、剧本估时、视频提示词语速预警、创作台景别统计与无媒体纸面预检。
  - 所有新增检查严格遵守硬/软门禁边界与 Python 3.9 兼容，均有独立行为回归测试覆盖（`tests/test_core_check_and_views.py`、`tests/test_edit_plan_and_subtitle.py`、`tests/test_duration_estimate.py`、`tests/test_novel_index.py`、`tests/test_episode_intake.py`）。
  - 全部 6 个变更技能在 `.clawhub/publish.json` 中完成版本递增、伴随依赖对齐与 `packageDigest` 重锁。
- **代价**：
  - `creator_markdown_check.py` 与 `duration_estimate.py` 各维护一份轻量的 `_voiced_units()` 口径（保持各技能运行时零跨目录依赖），未来若调整多语种发声切词口径需两处同步核对（或在必要时纳入 `src/_shared/` 同步）。
  - `creator_markdown_check.py` 对视频提示词台词的抽取基于常见引号与标签约定，极少数非标准自由文本描述可能漏检或误检，这也是将其严格限定为软门禁 `WARNING` 的原因。

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v`（Python 3.14 与 Python 3.9 下限）全量通过。
- `ruff check --no-cache .`、`mypy`（3.9 与 3.10 严格模式）及 `python3 tools/sync_shared.py --check` 全部通过。
- ClawHub 中央锁定与校验脚本对 `.clawhub/publish.json` 全部 6 个升级技能及 `short-drama` 伴随依赖校验通过。
