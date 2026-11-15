# Agent Note: 统一 7 脚本创作文档解析边界并以契约测试锁死跨技能规则一致性

Status: implemented

## Problem

在完成 [全仓消除 AI 黑话与五份创作文档字段破坏性重命名](../simplification/2026-11-14-eliminate-ai-jargon-and-breaking-field-renames.md) 与 [松绑过严脚本与流程门禁、重定级阶段规则并归并碎片化参考文档](../simplification/2026-11-14-relax-gates-consolidate-references-and-recalibrate-rules.md) 后，对全仓 549 个跟踪文件的差分实跑审查发现：由于各独立安装的技能按硬规则 1 不能相互导入对方脚本，仓库内共有 7 个 Python 脚本（`creator_markdown_check.py`、`creator_views.py`、`screenplay_index.py`、`duration_estimate.py`、`breakdown_tool.py`、`production_tool.py`、`edit_tool.py`）各自用独立正则解析同一批创作者 Markdown 文档，缺少跨脚本同源输入测试与跨技能规则等级自动化核对，导致以下两类系统性漂移：

1. **同一份合法 Markdown 在不同阶段脚本中解析结果不一致**：
   - UTF-8 BOM 头、`CRLF` 换行、加粗字段键（如 `- **连戏锁**：`、`- **提示词名称**：`、`- **分镜**：`）与列表符/半角冒号（`* 外观特征: ...`）在部分脚本被识别、在另一脚本静默丢失；
   - 非条目 `## ` 二级标题（如分类小节、文末备注、`审查/*.md` 的 `## 被删的强钩子`）以及行内与跨行 HTML 注释 `<!-- ... -->`（含围栏代码块内外的区分）未在 `screenplay_index.py`、`duration_estimate.py`、`edit_tool.py` 等全部解析器统一截断或剥离；
   - `剧本.md` 的紧凑中点场头（`## EP001-SC001 内·客厅·夜`）、`内外` 空间标记、首场前与各场头下方的 `人物：` 出场声明行、多词外文说话人旁白（`[VO] Dr. Lin：…`）、动作段数字时钟（`12:00，…`）以及 `分镜.md` 的场前 `## 场景站位`（见 [场景站位与机位表达](../feature/2026-10-20-scene-blocking-and-camera-terms.md)）、无单位纯数字秒数（`- 时长：4`）与引文内场景号（`- 来源：EP001-SC001「…EP001-SC003…」`）在各脚本间判定矛盾；
   - `审查/*.md` 字段改名为 `- 修改要求：` 并新增 `PROVISIONAL` 结论后，`creator_views.py` 仍读取旧字段名；`MOTION-*` 的 `- 输入参考图：无（待补参考图：…）` 被 `production_tool.py` 误编译为 0 参考图文生视频。
2. **跨技能规则表引用、生产/剪辑底层边界与外围工程清单缺少自动化契约核验**：
   - `$short-drama-review` 的评分表与上游 `stage-contract.md` 母表存在个别规则编号或四级分类（如 `STY-11`、`IMG-01`、`SHT-17`、`SHT-22`、`VID-03`）漂移，且缺少对《剪辑单.md》（`EDT-01`–`EDT-23`）的成体系核查节；
   - 生产与剪辑工具链在并发 `run/collect` 状态覆盖、Python 3.9 `socket.timeout`、`.opus` 参考音频内联编码与探测、`gpt-image-2` 参考图本地魔数预检、全静音成片 `loudnorm`（`-inf`）与非法 JSON 输出、单引号路径转义、`_inside(root.resolve())` 软链目录越界防护、`tools/compact_refs.py` 多文件半截写入与软链异常栈输出，以及两项式 Remotion 任务面板进度条上存在边界漏洞；
   - `.github/workflows/ci.yml` 的 `mypy` 未覆盖全部现役技能脚本与各技能 `selftest.py`、未针对 Python 3.9 标准库下限做类型核验，也未对 `rules.mjs` 执行语法检查；`.gitignore` 漏忽略 `叠层.props.json`，`.clawhub/publish.json` 的 `runtimeDependsOn` 仍停留在破坏性改名前的旧版本。

## Decision

在不违反硬规则 1（保持每个技能目录独立自包含、不抽跨技能公共 Python 包）的前提下，统一 7 个脚本的 Markdown 解析边界与契约文档，并用仓库层契约测试自动锁死跨脚本与跨技能一致性：

1. **对齐 7 个脚本的创作者文档解析语法**：
   - 统一归一化 UTF-8 BOM（`\ufeff`）与 `CRLF`/`CR` 换行，统一支持围栏代码块外行内与跨行 HTML 注释 `<!-- ... -->` 剥离（保留内部换行符维持行号，且在可复制提示词引用块与代码围栏内保留字面值，覆盖 `screenplay_index.py`、`duration_estimate.py`、`edit_tool.py` 等全部解析器）、任意 `^## ` 二级标题截断当前条目、可选成对强调包裹字段名（`- **字段**：`、`* *字段*:`）及 `[-*+]` 列表符与全半角冒号；
   - 对齐 `剧本.md` 场头中点两侧空白宽容度与 `内|外|内外` 空间词、首场前与各场头下方的 `人物：` 声明行识别、多词外文说话人旁白字幕分类与数字时钟前缀排除；新增 `duration_estimate.py --extra-speaker` 在自动识别集合上做并集追加；
   - 支持《分镜.md》在文档头部或各场首镜前书写 `## 场景站位 · <场景 ID> · <地点名>`，对齐无单位纯数字秒数与剥离引文后的来源场景号提取；
   - 更新 `creator_views.py` 读取审查 `- 修改要求：`、映射 `PROVISIONAL`、单独解析 `## 被删的强钩子`、通过《视频提示词.md》真实绑定映射剪辑单镜头并改用正则原串偏移生成搜索摘要；修复 `app.js` 字幕重点词单遍纯文本切分高亮与 `(类别, 名称)` 设定复合键。
2. **补齐校验、生产、剪辑与工程外围边界防护**：
   - 收紧 `creator_markdown_check.py` 与 `production_tool.py` 对 `IMG-*`、`GROUP-*`、`MOTION-*` 未决参考图（`待补参考图` / `不可提交`）的拦截，收紧 `GROUP-*` 分组级 `REF` `起始帧` 对连戏锁的豁免范围至首镜已承载的锁定词，改写强调字段行为无嵌套量词确定性正则以消除回溯风险，在 `creator_markdown_check.py`、`production_tool.py` 与 `provider_adapters.py` 全量对齐 `.opus` 参考音频后缀与 MIME/魔数校验，并移除旧 `可复制通用提示词` 别名；
   - 修复 `production_tool.py` 的 `run_job`/`collect_job` 并发状态保护、批次断点续跑（`reusable_runs`）确认收据消费与输出预检、`provider_adapters.py` 的 Python 3.9 超时识别、同步适配器拒绝 `collect_provider_job_id` 及 `gpt-image-2` 本地参考图预检；
   - 修复 `edit_tool.py` 全静音音轨跳过第二遍 `loudnorm` 与 `allow_nan=False` 输出、单引号路径与 `libass` 滤镜探测、流探测校验、`--remotion-workspace` 项目外隔离及 `TaskPanel.tsx` 进度项提取；
   - 加固 `episode_intake.py`、`novel_index.py`、`breakdown_tool.py`（补齐围栏代码块清空）、`project_tool.py`（补齐 `format.pacing.on_screen_text_characters_per_second` 配置键与父子 `authority` 摘要联动更新）中 `_inside(root.resolve())` 目录边界校验；将 `tools/compact_refs.py` 改为先在内存中完成全集/全项目改写与重校验，再经同目录临时文件加 `os.replace` 原子落盘（中途失败自动回滚已写文件），并在 `main()` 统一拦截软链或越界路径 `ValueError`/`OSError` 返回干净退出码 `1`；在 `tests/test_suite_anatomy.py` 排除被 `.gitignore` 忽略的 `evaluations/local-runs/` 本地实跑目录与非文件项，避免本机人工实跑污染随包文件扫描；
   - 加固 `.github/workflows/ci.yml`：保留锁定的 `mypy==2.3.0 --python-version 3.10` 并新增独立 `/tmp/mypy39` 虚拟环境执行 `mypy==1.19.1 --python-version 3.9` 以守住 Python 3.9 标准库 API 下限，两套检查均覆盖全部现役脚本、`tools/*.py` 以及按 `for selftest in skills/*/scripts/selftest.py` 逐个执行的 7 个技能自测脚本，同时补齐 `node --check skills/short-drama-edit/assets/remotion/src/rules.mjs`；同步更新 `.gitignore`、`DESIGN.md` 与 `.clawhub/publish.json` 的 `runtimeDependsOn`。
3. **新增常驻横向一致性契约测试（`tests/test_cross_parser_parity.py`）**：
   - `CrossScriptMarkdownParserParityTests` 用同一套覆盖 UTF-8 BOM、`CRLF`、行内与跨行 HTML 注释、加粗字段、非条目 `## ` 标题、紧凑与 `内外` 场头、场头 `人物：` 行、时钟动作行、外文 `[VO]` 说话人、场前 `## 场景站位`、无单位秒数、引文内场景号与 `PROVISIONAL` 审查报告的单集夹具同时驱动全部 7 个脚本，断言零误报且提取结构一致，并验证代码围栏内外 HTML 注释剥离一致；
   - `CrossSkillRuleTierParityTests` 自动扫描全部 `skills/*/references/stage-contract.md` 母表与全技能 Markdown 文档中的规则 ID 及四级分类标注，确保无悬空规则号、无跨技能等级冲突。

## Alternatives considered

1. **在仓库根目录抽出共享 Python 解析库（如 `common/markdown_parser.py`）供 7 个脚本直接 `import`**。
   - 最强理由：解析正则与预处理函数在代码层面只有唯一一份源码，从根本上消除多处维护同一语法的成本。
   - 为何不用：直接违反 `AGENTS.md` 硬规则 1（每个 `skills/<name>/` 目录必须是独立可分发、自包含的安装单元，不能依赖仓库根目录或其他技能目录的模块）。通过明确语法基准加仓库级 `tests/test_cross_parser_parity.py` 差分对测，既保住单技能独立分发，又能第一时间拦截任何语法偏离。
2. **仅人工逐个修补本次审查列出的点位，不新增跨脚本解析与跨技能规则对账测试**。
   - 最强理由：省去编写横向测试夹具的工作量，本轮即可更快收工。
   - 为何不用：按技能分目录迭代时，未来任何单技能调整字段或规则等级仍可能再次遗漏下游解析器或审查表；用确定性测试锁死契约才能终结“修一轮冒一轮横向偏差”的循环。

## Consequences

- **收益**：
  - 创作者在同一单集中使用的合法排版（UTF-8 BOM、`CRLF` 换行、加粗字段名、HTML 注释暂存、紧凑场次标题、场头 `人物：` 声明、多词外文角色名、各场开头站位块、静音试剪等）在校验、创作台、索引、估时、拉片、投产与剪辑各阶段脚本中表现一致。
  - 跨脚本解析对齐测试、跨技能规则等级核对测试与 CI Python 3.9 类型检查成为常驻门禁，后续改动一旦打破横向契约或误用高版本标准库 API 会在本地单测与 CI 立即暴露。
- **代价**：
  - 7 个独立脚本内部各自保有轻量的换行/BOM 归一化、HTML 注释剥离与强调符剥离辅助函数，变更创作者文档基础语法时需按 `test_cross_parser_parity.py` 的红灯提示同步各消费脚本。
