# 评估

`examples/` 回答「产物长什么样」。这里回答另一个问题：

> 把一本真正的长篇交给这套技能，按文档从头走一遍，它还跑得通吗？

差别不是规模，是**来源**。`examples/` 下的样例是手工塑形的，所以只覆盖我们想到过的情况。
v0.4.2 之后修掉的三处缺陷全部从它们旁边走了过去，原因是同一个——**样例里没有那种输入**：

| 缺陷 | 样例为什么看不见 |
|---|---|
| 时长估算把画外音计零秒 | 八集剧本里 `[VO]` / `[OS]` 出现 0 次 |
| 配音本结构上装不下画外音 | 根本没有配音本 |
| 重建索引会静默重编块号 | 没有一份被修订过的剧本 |

## 让你管账号

固定输入：`让你管账号/reference-run/输入/长篇-让你管账号，你高燃混剪炸全网.txt`
（147,010 字节 / 52,552 字 / 20 章）。版权归仓库所有者，收录用途限定为评估基准与工作流示例。

`reference-run/` 是按文档实跑一次录下来的完整产物，21 个产物全部 `accepted`，
EP001 时长 94.8 秒 / 目标 90 秒。它是**回归基准**，不是范文。

| 阶段 | 规模 |
|---|---|
| novel-analyze S0–S5 | 437 个情节点 / 14 个剧情单元 / 24 个分集候选 |
| develop | EP001–EP003 分集地图；13 条带精确 span 的改编映射 |
| write | EP001：44 个块 / 18 句口播 / 完整配音本 |
| assets · image-prompts | 2 角色 / 2 地点 / 2 道具；7 条图片提示词规格 |
| storyboard · video-prompts | 20 镜 / 20 张关键帧 / 20 条运动规格 / 2 个容器 / 2 条配乐 |

开头那张表点名的三样东西，它都带着：8 句画外音、一份覆盖全部 18 句口播的配音本、
一份带真实修订历史的剧本索引。

`reference-run/RUN-LOG.md` 记着这一次实跑遇到的人工介入与检查器报错，
下次实跑拿它对照，判断遇到的是老问题还是新问题。

## 新的实跑产物

后续完整项目、生成媒体、供应商响应和运行状态放在仓库外，或被忽略的 `evaluations/local-runs/`。
保留上面的既有回归基准；需要新增公共夹具时提取最小合成输入，并让测试实际使用它。
模型探索只在 [观察摘要](model-behavior-probes.md) 留下去标识的结果与适用范围。

## 跨题材内容质量门禁

`content-quality-corpus.json` v3 冻结 16 个合成案例，覆盖 16 种题材。已经用于修订或看过结果的
12 个案例全部归 development；候选写作指令、量表、提示词、阈值与 replicate 方案冻结后，另建
4 个只运行一次的 holdout。四个负对照中包含不直接提示评测目标的普通题面，用来发现 Skill 是否会
自发把局部手艺写成通用模板。holdout 结果一旦促成上述输入修改，就立即退役为 development；下一次
结论必须另建未运行的新案例，不能在同一组题上反复调到通过。

候选与基线使用同一创作模型、同一题面、同一份中性创作模板和隔离会话生成。生成器不得直接运行在
两个完整仓库 worktree 中：每次调用都在无 `.git`、无 `evaluations/` 的净化临时根中，只物化当前
arm 被 seal 绑定的 `skills/short-drama-write/` bundle，提示词从标准输入传入。收据必须声明
`workspace_policy: source-bundle-only`，且 `workspace_bundle_sha256` 等于当前 arm 的 source bundle；
否则门禁 fail-closed。这个约束防止候选看到新增题面、量表或历史报告，而基线看不到的环境混杂。

每个案例、每个 arm 预先固定 3 次独立创作 replicate，全部等权纳入，不做 best-of-N，也不只重跑分数较差的作品。每个
replicate 再由 Codex、Kimi 各自交换 A/B 位置盲评，共 4 份报告；完整一轮为 96 份创作作品与 192 份
盲评报告。Kimi CLI 未提供独立 reasoning-effort 开关，因此配置与收据如实记录为
`provider-default`，不伪造未实际传入供应商的档位。

盲评同样不得在完整仓库或运行目录中执行。每次 judge 调用使用无 `.git`、无任何文件的空临时根，完整
题面、A/B 作品、量表与固定 JSON 模板只作为本次调用的 prompt 输入传入，不在工作区物化；收据必须声明 `workspace_policy: prompt-only`
并使用空工作区的固定 bundle SHA。Codex 可从 stdin 读取该 prompt，Kimi 使用非交互 `--prompt` 参数；
二者都不能把 prompt 或评测文件落到工作区。这样 judge 无法从 manifest、文件名、另一份报告或历史输出恢复版本
身份。缺少该身份的报告即使 JSON 和分数齐全，也不能进入正式聚合。

[`content-quality-rubric.md`](content-quality-rubric.md) 只评剧本。`content_quality_gate.py` v5
先在 replicate 内平均，再等权聚合为案例，最后计算 development、holdout 与全语料宏平均；它拒绝
缺失、重复、额外或选择性纳入的 replicate。门禁不信任运行 manifest 自报的题材和 split，而与公开
corpus 逐案例核对，并绑定基线提交、候选 Skill bundle、创作/评审模板、量表、模型配置、corpus JSON
与全部题面正文组成的 bundle、每份作品、报告、调用收据和外部私有词表。它还分别报告模型家族、A/B
位置、评分维度和单案例变化，并拒绝重复题面或跨案例/arm/replicate 重用作品。

实际作品、收据、报告、私有词表和可信 seal 放在被忽略的 `.omx/`。manifest 中的 seal 只是一份随
证据携带的副本；门禁要求它逐字段等于维护者在冻结时另存、且不由运行脚本重建的可信 seal。运行时
必须显式提供维护者控制的词表和可信 seal：

```bash
python3 evaluations/content_quality_gate.py path/to/manifest.json \
  --trusted-leakage-terms path/to/maintainer-terms.txt \
  --trusted-seal path/to/maintainer-seal.json
```

manifest schema v5、corpus schema v3、config schema v3 与 receipt schema v2 都不兼容旧格式；这是
有意的 fail-closed 变更，不保留兼容分支。缺少净化工作区身份的历史运行只能作为方向性诊断，不能
追认为正式门禁证据。

这套评测不能靠断言文档里存在某句话替代。文案是否泛化由真实跨题材产出、单次 holdout、负对照和
盲评诊断证明；单元测试只验证门禁面对合成输入、篡改、replicate 缺失/复用和伪造元数据时的行为。

## 每次发布前

分两层，因为两层能判定的东西不同。

**回归闸门**（脚本，随测试跑）：

```bash
python3 -m unittest tests.test_workflow_evaluation
```

把录下来的那次运行重新过一遍主工作流用到的检查器——资产、图片提示词、分镜覆盖、
交付容器、运动时长、配乐、配音本、剧本时长——并核对派生层还能从各自的源头重建：
章节索引能否从原著重算出同一张表、剧本索引重建后块号是否一字不动、21 个产物是否都还 `accepted`。
**这一层判定「没有退步」，不看戏写得怎么样**。

不在覆盖范围内的两个阶段：`$short-drama-review` 是单独请求的审查阶段，
`$short-drama-produce` 需要本机没有的生成后端。

**主工作流实跑**（人或 Agent，发布候选上做一次）：闸门跑的是录下来的结果，
这一步跑的是流程本身。开一个新项目，只给它那份原著，按各技能 SKILL.md 走到
EP001 的视频提示词，再与 `reference-run/` 对照——不是对照文本相同（创作产物每次都不一样），
而是对照**哪一步需要人替系统解决问题**、**哪个检查器报错**、
以及**文档说的做法是不是真的能走通**。

**开跑前先把套件固定在一个提交上**。实跑要走几个小时，其间技能文件不能变：

```bash
git rev-parse HEAD                      # 记下来，写进这次实跑的报告
git worktree add /tmp/eval-run <commit> # 在这份固定副本上跑，不要用正在改的工作区
```

不固定就没有可复现性——摩擦记到一半，被记录的那份文档可能已经改掉了，
而报出来的问题究竟属于哪一版无从判断。这不是理论问题：v0.5.0 的那次实跑跨了
三个 HEAD，其中一条发现因为缺陷在被撞上的同时已被修复而只能撤回。

第三条不能省：上一轮最重的一个缺陷是 `SKILL.md` 写的重建方式与脚本实际行为不一致，
而所有测试都是绿的。发现的问题按 `CONTRIBUTING.md` 的分类记进 `CHANGELOG.md`。

`让你管账号` 这一节仍只回答主工作流是否顺畅；内容 A/B 使用上面的独立跨题材语料，
不拿回归运行冒充剧本质量证明。
