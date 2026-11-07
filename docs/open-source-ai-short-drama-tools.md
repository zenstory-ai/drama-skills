# 开源 AI 短剧 / 漫剧工具怎么选：9 个项目按使用方式对比（2026）

选开源 AI 短剧或漫剧工具，先按使用方式分三类。第一类是装进 Claude Code、Codex 等编程 Agent 的 skill 包，第二类是下载就能用的桌面应用，第三类是用 Docker 自己部署的网页工作台。分好类后再核对四件事：它覆盖从剧本到成片的哪几个环节，图片和视频模型从哪里来、要不要自己付费，跨镜头的人物一致靠什么维持，许可证允不允许你的用法。

> 利益相关：本文由 Drama Skills 的维护者编写，Drama Skills 也在对比之列。所有项目按同一组标准列出，事实取自各项目自己的仓库与 README，截至 2026-10-30；星标数和最近提交日期会变，引用前请回仓库核对。README 只是项目自述，表中“未说明”表示 README 没有写，不代表没有这项能力。

## 一、总表

| 项目 | 使用方式 | 许可证 | 星标 / 最近提交 | 覆盖环节 | 模型从哪来 | 跨镜一致性靠什么 |
|---|---|---|---|---|---|---|
| [Toonflow](https://github.com/HBAI-Ltd/Toonflow-app) | 桌面应用（Windows / macOS）和 Android 应用，也可 Docker 部署网页版；无限画布 + 内置 Agent | MIT（v1.0.8 之前为 AGPL-3.0，之后一段为 Apache-2.0 加附加条款） | 19,981 / 2026-10-27 | 剧本、分镜、角色与场景素材、图片、视频；剪辑与配音未说明 | 自配第三方 API，也可接本地 ComfyUI 和 LLM | README 未说明具体机制，可把参考图连到视频节点 |
| [火宝短剧 huobao-drama](https://github.com/chatfire-AI/huobao-drama) | 网页应用，另有 Electron 桌面版和 Docker | CC BY-NC-SA 4.0（禁止商用） | 16,787 / 2026-10-25 | 小说改剧本、角色/场景/道具出图、分镜、视频、FFmpeg 加字幕并拼整集；配音未说明 | OpenAI 兼容接口、Gemini、火山；视频含 Seedance 2.0、MiniMax H3、Wan 3.0 | 每个资产生成一致性参考图，分镜里写 `@角色名` 自动对应参考图 |
| [waoowaoo](https://github.com/waooAI/waoowaoo) | 自托管网页应用（Docker：Next.js、MySQL、Redis、Temporal、MinIO），README 标注 Preview | Elastic License 2.0（README 自述为源码可见，非 OSI 开源） | 14,721 / 2026-09-21 | 角色设定图、图片、视频；README 写明本版不含配乐和配音 | 只开放 OpenRouter，需自付费用 | README 未说明人物一致机制，写有参考图、首帧或首尾帧衔接镜头 |
| [ViMax](https://github.com/HKUDS/ViMax) | 命令行 / 终端界面 + 本地网页 | MIT | 12,807 / 2026-09-30 | 点子/剧本/小说到视频：剧本、角色、分镜、图片、视频、拼装 | OpenAI 兼容 LLM、Nano Banana、Veo，更新日志里加入 GPT Image 2、Seedance 2.0 Fast | AutoCameo 用参考照片保持外观；每个关键帧生成 2 个候选再由视觉模型挑选 |
| [DramaClaw](https://github.com/dramaclaw/dramaclaw) | 自托管网页应用（Docker）：无限画布 + 分集流水线 + 内置 Agent | Elastic License 2.0（要求界面标注 “Powered by DramaClaw”，不允许做成托管服务） | 6,658 / 2026-10-30 | 剧本、资产、分镜与首帧、图片、视频、配音、音乐、剪辑与字幕导出 | 所有推理走 OpenAI 兼容网关，可用官方网关或自带供应商；本机不跑模型 | 资产库维护跨集固定身份、角色立绘和每集变体；用 3D 场景与全景锁定空间（3D 预演标注内测） |
| [shuohao-skills](https://github.com/eternityspring/shuohao-skills) | 编程 Agent skill 包（7 个），支持 Claude Code、Codex | Apache-2.0 | 5,733 / 2026-10-26 | 改编大纲、人物与美术设定、剧本、站位、分镜、角色参考图；不做视频生成与剪辑 | 写作用 Agent 自己的模型；参考图可走 ComfyUI、GPT Image 2 等 | character-refs 生成角色参考图交给分镜；美术设定写一致性锚点 |
| [Drama Skills](https://github.com/zenstory-ai/drama-skills)（我们） | 编程 Agent skill 包（12 个），支持 Claude Code、Codex，附本地 Dashboard | MIT | 3,560 / 2026-10-30 | 原著分析、分集剧本、视觉设定、分镜、图片/视频提示词、确认后生产（图、视频、配音、音乐）、剪辑成片、审查 | 写作用 Agent 自己的模型；生产阶段可选 Seedance、GPT Image 2、MiniMax H3 视频、MiniMax 语音与音乐，需自付费用 | 把造型写成可原样贴进提示词的“连续性锁”短语并绑定参考图，检查脚本核对引用 |
| [LocalMiniDrama](https://github.com/xuanyustudio/LocalMiniDrama) | Windows 桌面应用（Electron），也可从源码以网页方式运行 | MIT | 2,287 / 2026-10-30 | 故事/剧本、角色/场景/道具图、分镜、图片、视频、合成 | 通义、火山（豆包 / Seedance 2.0）、可灵、Vidu、Gemini、OpenAI 兼容等；本地只有 Ollama 且只用于文本 | `@图片N` 多图参考，加尾帧衔接 |
| [ai-anime-series](https://github.com/10291124jcjc-dotcom/ai-anime-series) | Agent skill + Python 脚本，2026-10-28 新建 | 脚本 MIT，其余 CC BY-NC 4.0 | 220 / 2026-10-28 | 固定角色的单元剧：剧本与镜头表、角色设定图、宫格故事板、视频、拼合集；无配音 | 即梦 / Dreamina（需会员），出图出视频在即梦里手动操作 | 三视图、表情、动作、剪影组成的角色设定图加故事板，编号后一起作为参考 |

另有两个本月新建、星标还很少的项目：[ComfyUI-BBAIGC-MiniMax-H3](https://github.com/BBAIGC/ComfyUI-BBAIGC-MiniMax-H3) 是 ComfyUI 节点，README 宣称用本地 MiniMax H3 权重全本地生成，作者设备为 16GB 显存显卡加 64GB 内存，仓库未声明许可证；[fuxing-ai-drama-studio](https://github.com/ian09270927/fuxing-ai-drama-studio) 用自己的角色照片和录音做短剧，含声音克隆和对嘴，模型跑在 Google Colab 上。

## 二、按你的情况选

**想要一个打开就能用的应用。** 看 Toonflow、LocalMiniDrama 和火宝短剧的桌面版。Toonflow 星标最多，画布式操作，模型来源最灵活；LocalMiniDrama 接入的国内模型最多（通义、豆包、可灵、Vidu）。三者生成图片和视频都要调用云端付费 API，“本地”指的是项目数据存在自己电脑上。火宝桌面版有一个 README 写明的限制：Seedance 引用本地参考图需要公网地址，桌面版会直接报错。

**团队或工作室自己部署一套网页工作台。** 看 DramaClaw、waoowaoo 和火宝短剧的 Docker 版。DramaClaw 覆盖环节最全，从剧本一直到配音、音乐和剪辑；waoowaoo 目前只接 OpenRouter，本版不含配乐和配音。两者都是 Elastic License 2.0，可以自用和二次开发，但不能把软件本身做成托管服务卖给别人。火宝是 CC BY-NC-SA 4.0，商用前要先联系作者。Toonflow 的服务端口没有登录鉴权，README 提醒服务器部署时要用防火墙或带认证的反向代理。

**已经在用 Claude Code 或 Codex 写东西。** 看 Drama Skills、shuohao-skills 和 ai-anime-series。这类工具不带界面，剧本和分镜用 Agent 当前的模型写，产出是文件夹里的 Markdown，便于逐条修改和版本管理。区别在覆盖范围：shuohao-skills 止步于分镜和角色参考图；Drama Skills 往后延伸到确认后生产、剪辑成片和审查；ai-anime-series 专做固定角色的单元剧，生成环节依赖在即梦里手动操作。

**想研究多智能体视频生成的做法。** 看 ViMax。它是研究型框架，README 没有把自己定位成短剧或漫剧工具，但从小说生成视频（Novel2Video）和人物一致（AutoCameo）的实现可以参考。注意每个关键帧生成两个候选，会增加 API 费用。

## 三、选之前再核对三件事

1. **许可证。** 九个项目里只有 Toonflow、ViMax、Drama Skills、LocalMiniDrama 是 MIT，shuohao-skills 是 Apache-2.0，这五个对商用和二次分发限制最少。DramaClaw 和 waoowaoo 的 Elastic License 2.0 禁止对外提供托管服务；火宝短剧和 ai-anime-series 的非脚本部分是 CC 非商用许可。做商业短剧前，先确认你的用法在许可范围内。生成内容本身的版权和平台规则另算，与工具许可证无关。
2. **成本在哪里。** 这些工具本身免费，钱花在图片、视频和配音模型上。按秒计费的视频模型是大头，重跑一个镜头就多付一次。README 给了参考数字的只有个别项目，例如 Toonflow 一个案例的模型调用总费用约 130 元，Drama Skills 68 秒样片的视频生成约 40 元；各自的模型和镜头数不同，不能直接横比。
3. **“本地”是哪一层。** 能全本地生成视频的只有 ComfyUI 一类方案，需要大显存显卡和几十 GB 模型文件。其余项目说的本地或本机优先，多指剧本、素材和工程文件存在自己电脑上，生成仍然调用云端 API。

## 常见问题

**做 AI 漫剧需要显卡吗？**

用上表大多数项目都不需要，图片和视频由云端模型生成。只有在本机跑开源视频模型（例如 ComfyUI 加本地权重）才需要大显存显卡。

**开源工具和即梦这类在线平台怎么取舍？**

在线平台开箱即用，模型和计费由平台决定，作品和素材存在服务方。开源工具能换模型、改流程，把剧本、分镜和素材留在自己手里，代价是要自己配 API、部署环境，并且自己承担模型费用。

**人物在不同镜头里长得不一样，换工具能解决吗？**

工具只能把参考图和造型描述更稳定地带进每一次生成，最终一致程度还取决于视频模型本身。更可靠的做法是先定好角色设定图和一段固定的造型描述，每个镜头都原样引用，详见[跨镜头角色一致性](character-consistency-across-shots.md)。

## 相关

- Drama Skills 的完整流程：[漫剧创作全流程指引](comic-drama-workflow.md)
- 分镜怎么写：[短剧分镜脚本模板](short-drama-storyboard-script-template.md)
- 视频提示词：[Seedance 提示词怎么写](seedance-prompt-writing.md)
- 仓库地址：https://github.com/zenstory-ai/drama-skills
