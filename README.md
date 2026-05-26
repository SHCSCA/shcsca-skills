# shcsca-skills

> 面向跨境电商运营、内容生产、市场研究和工程协作的 Agent Skills 合集。

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-111827)](https://agentskills.io)
[![Skills](https://img.shields.io/badge/skills-curated%20%2B%20original-2563eb)](#skills-%E9%80%9F%E6%9F%A5)
[![Amazon Ops](https://img.shields.io/badge/Amazon%20Ops-ready-16a34a)](#%E8%B7%A8%E5%A2%83%E7%94%B5%E5%95%86-skills)

本仓库把可复用的业务方法论沉淀成 Skills：让 AI 不只是回答问题，而是按固定流程完成调研、判断、写作、需求拆解和工程协作。

## 适合谁

| 角色 | 能解决的问题 |
|---|---|
| Amazon 卖家 / 跨境运营 | 图片需求稿、功能需求验证、竞品拆解、Listing 转化判断 |
| 市场研究人员 | 公司、概念、赛道、竞品的横纵向深度研究 |
| 内容创作者 | 长文写作、风格约束、反空话表达 |
| 工程团队 | TDD、调试、需求拷问、Issue 拆解、架构改进 |
| AI Agent 用户 | 把团队经验变成可重复调用的工作流 |

## 快速开始

### 让 AI 自动安装

在支持 Skills 的 AI 工具里发送：

```text
帮我安装 <skill-name>，来源仓库 SHCSCA/shcsca-skills，直接装到当前工作区
```

### 手动安装

```bash
git clone https://github.com/SHCSCA/shcsca-skills.git
cd shcsca-skills

# 复制单个 skill 到你的 skills 目录
cp -r skills/<skill-name> ~/.openclaw/skills/
```

如果你的工具使用其他目录，把最后一行替换成对应的 Skills 目录即可。

## Skills 速查

| Skill | 类型 | 适用场景 |
|---|---|---|
| `amz-create-image` | 自建 | Amazon 主图 / 副图 / A+ 美工需求稿，按运营判断生成 Excel 交付稿 |
| `amz-market-research-orchestrated` | 自建 · 可执行 v2 | Amazon / 电商市场深度调研，使用 Sorftime MCP + Firecrawl 生成可审计三报告 |
| `zach-feature-demand-validator` | 自建 | 用 Review、关键词、社区证据判断功能点是不是真需求 |
| `hv-analysis` | khazix | 横向竞品 + 纵向演变的深度调研报告 |
| `khazix-writer` | khazix | 模拟“有见识的普通人”写长文，拒绝空洞套话 |
| `neat-freak` | khazix | 任务结束后同步项目文档、Agent 记忆和 README |
| `mattpocock/*` | mattpocock | 工程协作 Skills：TDD、诊断、需求拷问、Issue 拆解等 |

## 跨境电商 Skills

### `amz-market-research-orchestrated`（可执行 v2）

Amazon / 电商市场调研 Skill，用 Sorftime MCP 做主数据源，Firecrawl 做公开网页补充，生成带数据血缘、方法链和交付规范的市场研究报告。

v2 已内置最小可执行流程，不再依赖未随仓库提供的外部 orchestrator。默认输出 `HTML + Markdown + Data Pack`，其中 HTML 是离线可打开的三报告交付包，不是 Markdown 套壳：`report.html` 为入口页，另外生成市场深度调研、产品全生命周期拓品战略、用户心智断层与需求机会三份独立 HTML，并提供 `validate_market_research_deliverables.py` 校验数据血缘、方法链、输出文件、HTML 深度和关键质量规则。

计划覆盖的调研任务：

| 任务 | 目标 |
|---|---|
| 新市场 / 新品类进入 | 判断是否值得进入，以及切入点在哪里 |
| 产品迭代 | 从 Review、VOC、竞品差异中提炼优化方向 |
| 细分市场发现 | 找新人群、场景、价格带和未满足需求 |
| 竞品差异化 | 找功能、定位、价格和内容表达上的机会 |
| TikTok / VOC 洞察 | 用 TikTok Shop、评论、公开网页和内容信号辅助判断真实需求 |
| 1688 供应链验证 | 用 1688 相似货源判断采购成本带、同款供给和可复制风险 |

v2 主要数据源：

| 数据层 | 工具 |
|---|---|
| Amazon 商品 / 关键词 / 类目 / 评论 / 趋势 | Sorftime MCP |
| TikTok Shop 商品 / 趋势 / 视频 / 达人 | Sorftime MCP |
| 1688 相似货源和采购成本代理 | Sorftime MCP |
| 行业报告 / 品牌站 / 测评 / 法规 / 召回 | Firecrawl MCP |

### `amz-create-image`

Amazon 主图、辅图、A+ 视觉需求稿生成 Skill。

它不直接生成最终图片，而是把运营判断转成美工可执行的 Excel 图片需求稿。核心能力包括：

| 能力 | 输出 |
|---|---|
| 产品定位 | 适用人群、价格带、核心差异、购买理由 |
| 关键词意图 | 核心品类词、功能词、场景词、痛点词、问题型词到图片模块的映射 |
| Review / VOC 洞察 | 好评动机、差评痛点、退货疑虑、Q&A 问题到副图和 A+模块的映射 |
| 竞品拆解 | 信息层级、视觉钩子、未满足痛点，不复制竞品素材和文案 |
| A9 / COSMO / Rufus 视角 | 搜索相关性、点击转化、场景意图、对话式购物问题承接 |
| 合规风控 | 参数、认证、医疗安全承诺、侵权和夸大表达检查 |

工作流采用强门禁：

1. 收集产品资料和运营信号。
2. 要求上传主图 / 副图参考图。
3. 生成主图 / 副图需求稿并等待验收。
4. 验收通过后再要求上传 A+参考图。
5. 在已验收的原 Excel 工作簿中补充 A+需求稿，并另存新版本。

内置模板：`skills/amz-create-image/templates/amz-create-image_workbook.xlsx`

示例触发：

```text
/amz-create-image 帮我做一个 Amazon 太阳能户外灯的主图和副图美工需求稿
```

### `zach-feature-demand-validator`

用于判断“这个功能点到底是不是用户真的在意”。

它把需求验证拆成三类证据：

| 信号 | 看什么 |
|---|---|
| Review 信号 | 用户是否主动提到、抱怨缺失、因为它退货或差评 |
| 关键词信号 | 用户是否搜索这个功能或相关痛点 |
| 社区信号 | Reddit、Quora 等社区是否反复讨论同类需求 |

适合用于微创新立项、卖点筛选、竞品功能判断和产品路线取舍。

```text
/zach-feature-demand-validator 帮我验证 air fryer 的 steam 功能在美国站是不是真需求
```

## 研究与写作 Skills

### `hv-analysis`

横纵分析法调研 Skill：

| 方向 | 作用 |
|---|---|
| 纵向 | 追踪对象从诞生到当下的完整演变 |
| 横向 | 对比同一时期的主要竞品、替代方案和关键玩家 |
| 交汇判断 | 在时间线和竞争格局中形成结论 |

适合调研公司、概念、赛道、竞品和写作前的系统素材准备。

### `khazix-writer`

长文写作 Skill，目标是写出“有见识的普通人在认真聊一件打动他的事”。

它会主动避开空泛表达，比如“赋能、抓手、闭环”“首先其次最后”“在当今 AI 快速发展的时代”等模板味文字，并通过结构、节奏、内容和文字四层自检提升文章质感。

## 工作流与工程 Skills

### `neat-freak`

任务完成后的同步 Skill，关注三层收尾：

| 层级 | 同步内容 |
|---|---|
| 项目文档 | `CLAUDE.md`、`AGENTS.md`、`docs/` |
| Agent 记忆 | 跨会话需要保留的项目事实和流程 |
| 项目 README | 给团队成员看的最新使用说明 |

触发方式：`/neat`、`整理一下`、`同步一下`、`sync up`。

### `mattpocock/*`

来源：[mattpocock/skills](https://github.com/mattpocock/skills)，偏工程协作和软件开发工作流。

| 分类 | Skills |
|---|---|
| 工程 | `diagnose`、`grill-with-docs`、`triage`、`improve-codebase-architecture`、`setup-matt-pocock-skills`、`tdd`、`to-issues`、`to-prd`、`zoom-out` |
| 生产力 | `caveman`、`grill-me`、`write-a-skill` |
| 工具 | `git-guardrails-claude-code`、`setup-pre-commit`、`scaffold-exercises`、`migrate-to-shoehorn` |
| 个人 / 废弃 | `edit-article`、`obsidian-vault`、`design-an-interface`、`qa`、`request-refactor-plan`、`ubiquitous-language` |

## 仓库结构

```text
shcsca-skills/
├── README.md
└── skills/
    ├── amz-create-image/                  # 自建 · Amazon 图片需求稿
    │   ├── SKILL.md
    │   ├── references/
    │   └── templates/
    ├── amz-market-research-orchestrated/  # 自建 · 可执行 v2 · Amazon 市场研究总控
    ├── zach-feature-demand-validator/     # 自建 · 功能需求验证
    ├── hv-analysis/                       # khazix · 横纵分析法
    ├── khazix-writer/                     # khazix · 长文写作
    ├── neat-freak/                        # khazix · 任务收尾同步
    └── mattpocock/                        # mattpocock · 工程开发系列
        ├── engineering/
        ├── productivity/
        ├── misc/
        ├── personal/
        └── deprecated/
```

## 维护原则

| 原则 | 说明 |
|---|---|
| 可直接使用 | 每个 Skill 尽量保留完整 `SKILL.md`、必要 references 和模板 |
| 业务优先 | 自建 Skills 聚焦跨境电商、Amazon 运营、AI 工作流 |
| 渐进披露 | 大块规则放入 `references/`，主 `SKILL.md` 保持可读 |
| 不空谈 | Skill 应该沉淀流程、检查表、交付物规范，而不只是提示词 |

## 致谢

本仓库整理和引用了以下优质来源：

| 来源 | 作者 / 说明 |
|---|---|
| [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills) | 数字生命卡兹克 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock |
| 自建 Skills | SHCSCA 跨境电商和 AI 工作流实践 |

欢迎提交 Issue 或 PR 推荐新的优质 Skills。
