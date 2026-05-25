---
name: amz-market-research-orchestrated
description: "【未完成 / WIP】四板块解耦式 Amazon / 电商市场调研总控 Skill。用户要求调研市场、品类、赛道、竞品格局、用户需求、产品迭代或新细分机会时使用。当前仍依赖未随本仓库完整提供的 data-source-orchestrator、market-method-orchestrator 和 research-output-orchestrator，不应当作稳定可用版本。"
---

# Amazon 市场调研总控（四板块编排版，未完成）

> 状态：未完成 / WIP。当前版本用于沉淀市场研究总控框架和契约草案，仍依赖未随本仓库完整提供的外部编排 Skill：`data-source-orchestrator`、`market-method-orchestrator`、`research-output-orchestrator`。在这些依赖补齐前，不要把它当成稳定可安装、可完整执行的 Skill。

## 定位

承担 Amazon / 电商市场调研任务的总控入口。负责澄清用户目的、确认数据范围和输出风格、生成 Orchestration Brief、调度数据源、选择方法链、组织分析结果并交给输出层交付。

本 Skill 不直接硬编码具体数据接口，不把所有分析方法写死在一个流程里，也不把输出平台绑定到报告生成逻辑中。四个板块是并列能力面：

1. 数据源平面：`data-source-orchestrator`
2. 方法论平面：`market-method-orchestrator`
3. 任务目的平面：本 Skill + 方法编排器的 purpose playbooks
4. 输出平面：`research-output-orchestrator`

详细架构见 [four-plane-architecture.md](references/four-plane-architecture.md)。

## 触发场景

当用户说以下任一意图时使用本 Skill：

- 帮我调研 XX 市场、品类、赛道。
- 判断某个产品方向值不值得做。
- 对一个品类做新产品/新细分市场开发。
- 基于评论、Reddit、YouTube、TikTok、Amazon 等数据做用户洞察。
- 基于竞品数据做差异化机会。
- 现有产品要迭代优化，希望从评论和竞品中挖需求。
- 需要输出 HTML、Markdown、飞书文档或知识库报告。

如果用户只是抓取 Amazon 商品、下载评论或查某个 ASIN，不启动完整市场调研总控；转给数据源平面或已有采集 Skill。

## 核心原则

1. 先问目的，再定方法，再拿数据，再写报告。
2. 数据源、分析方法、任务目的和输出规范互相解耦。
3. 同样是“市场调研”，新市场进入、产品迭代、细分场景发现、竞品差异化的分析链路不同。
4. 方法链要能解释为什么选这些方法，不堆砌框架名。
5. 输出必须保留数据血缘、质量评分、方法链和限制。
6. 默认输出风格为全中文本土化、老练犀利、理性美学网页报告；用户指定其他风格时以用户为准。

## Step 0: 澄清任务目的

如果用户没有说明目的，先用短问题确认：

```text
这次调研主要服务哪个决策？
1. 是否进入一个新品类/新市场
2. 现有产品迭代优化
3. 发现新的细分人群/场景/价格带
4. 竞品拆解和差异化定位
5. 社媒/VOC 用户洞察
6. 供应链、利润和可行性验证
7. 老板/客户汇报
```

如果用户已经明确目的，直接复述并进入下一步。允许一个 primary purpose + 最多两个 secondary purposes。

## Step 1: 确认数据源范围

按 [research-scope-menu.md](references/research-scope-menu.md) 询问数据深度。默认推荐“电商 + 社媒标准版”，但如果用户只要快速判断，可以降级为 Amazon-only。

```text
我可以按三个数据深度做：

1. Amazon-only 快速版：Amazon 市场/竞品/评论/关键词。
2. 电商 + 社媒标准版：Amazon + Reddit + YouTube。（推荐）
3. 全域深度版：Amazon + Reddit + YouTube + TikTok/TikTok Shop + Keepa + 1688/供应链 + 公开报告。

目标站点默认 Amazon US。是否确认这个范围？
```

## Step 2: 确认输出方式

如果用户没有指定输出，调用输出平面的确认菜单：

```text
报告完成后你希望怎么交付？
1. 默认本地 HTML 报告
2. HTML + Markdown + 数据包
3. 写入飞书/Lark 文档或知识库
4. 写入 Obsidian/Notion/其他知识库连接器

默认风格：全中文、老练犀利、讲人话；网页报告采用理性美学直角卡片和交互图表，文档报告采用结构化表格/列表。
是否把这个选择保存为以后市场调研的默认输出方式？
```

如果用户已明确要 HTML、飞书或 Markdown，直接写入 OutputBrief，不重复打断。

## Step 3: 生成 OrchestrationBrief

将目的、数据范围、方法要求和输出要求合成统一 brief：

```json
{
  "task_id": "interactive_companion_toy_20260427",
  "research_object": {"type": "keyword", "value": "interactive companion toy"},
  "task_purpose": {
    "primary": "new_market_entry",
    "secondary": ["segment_discovery"],
    "decision_to_support": "判断是否进入并选择切入点"
  },
  "data_scope": {
    "depth": "standard",
    "platforms": ["amazon", "reddit", "youtube"],
    "marketplaces": ["Amazon US"]
  },
  "output_scope": {
    "formats": ["html", "json"],
    "targets": ["local_file"],
    "include_appendix": true,
    "style": {
      "language_profile": "zh_cn_localized",
      "tone_profile": "seasoned_direct_plainspoken",
      "visual_profile": "rational_aesthetics_html",
      "document_profile": "structured_decision_doc"
    }
  }
}
```

详细契约见 [orchestration-brief-contract.md](references/orchestration-brief-contract.md)。

## Step 4: 调度数据源平面

把 OrchestrationBrief 转为 DataNeed，交给 `data-source-orchestrator`。

要求 Data Pack 返回：

- 原始文件路径。
- 标准化实体：products、reviews、keywords、categories、videos、social_posts、suppliers、web_documents。
- Data lineage。
- Quality score。
- 数据缺口和降级说明。

如果 required 数据缺失，先让数据源平面走 fallback；仍失败时保留缺口，后续方法链降低置信度。

## Step 5: 调度方法论平面

把 Data Pack 摘要和 task purpose 交给 `market-method-orchestrator`。

方法论平面必须返回：

- Analysis Plan。
- method_chain。
- data_gaps。
- report_ready_sections。
- confidence and limitations。

不同目的的默认方法链：

| 任务目的 | 默认方法链 |
|---|---|
| 新市场/新品类进入 | 市场三源估算 -> 趋势/季节性 -> 集中度 -> Porter 五力 -> STP -> 竞品价格价值矩阵 -> JTBD -> ERRC -> 成本门槛 |
| 当前产品迭代 | 评论主题聚类 -> 方面情绪 -> 投诉转需求 -> Kano -> Listing promise gap -> 竞品功能 benchmark -> RICE |
| 新细分市场发现 | VOC 聚类 -> 使用场景聚类 -> PSPS -> STP -> TAM/SAM/SOM 切片 -> 定位图 -> Value Proposition Canvas |
| 竞品差异化 | 功能 benchmark -> 4P/7P -> review gap -> price-value matrix -> moat/copyability -> strategy canvas -> ERRC |
| 社媒/VOC 洞察 | 内容主题图 -> 情绪语言 -> 购买阻力 -> JTBD -> PSPS -> message-market fit |
| 供应链/利润验证 | price ladder -> cost ceiling -> unit economics gate -> supplier risk -> Keepa market dynamics |

完整 playbook 见 `market-method-orchestrator/references/task-purpose-playbooks.md`。

## Step 6: 综合判断

只在数据和方法都返回后综合。判断顺序：

1. 研究对象真实市场定义是什么，是否需要从用户原词切换到可测代理类目。
2. 市场规模和趋势是否足够。
3. 竞争格局是否允许进入。
4. 用户痛点是否强烈且可修复。
5. 是否存在清晰细分人群/场景/价格带。
6. 供应链和利润是否存在明显硬门槛。
7. 输出 Go / Watch / No-Go，并给下一步验证动作。

## Step 7: 调度输出平面

将结果交给 `research-output-orchestrator`，按 OutputBrief 生成：

- HTML 报告。
- Markdown 版本。
- JSON Data Pack 和 Analysis Plan。
- 飞书/Lark/知识库写入结果。
- 数据血缘与方法链附录。
- 输出风格合规结果。

## 报告质量规则

- 不把第三方估算销量写成官方销量；写作“估算月销量（来源名）”。
- 不把 Amazon `bought in past month` 和第三方估算合并成同一个数字。
- 不用社媒热度替代购买需求；只能作为需求、场景、情绪证据。
- 不用少量评论写精确百分比；样本小则写频次和代表证据。
- 不在缺少成本时写伪利润表；改写价格红线和成本门槛。
- 不因为某个平台数据失败就删除模块；保留模块并说明缺失和影响。
- 所有关键结论必须能追溯到 Data Pack 的 source_id 或明确标注为 AI 推理。
- 所有关键方法必须能追溯到 method_chain，避免“报告看起来很完整但逻辑不可复用”。
- 报告默认全中文本土化输出，仅保留品牌名、ASIN、平台名、工具名和必要英文专有名词。
- 网页报告默认遵循 `research-output-orchestrator/references/output-style-guide.md` 的理性美学标准：独立 HTML、企业深蓝/莫兰迪青灰、直角卡片、无阴影、细边框、交互图表。
- 文档/Markdown/知识库报告默认开头总结、分层标题、表格和列表优先，逻辑清晰、少废话。

## 默认文件结构

```text
reports/{task_id}/
  data/
    raw/
    normalized/
    data_pack.json
    lineage.md
  analysis/
    analysis_plan.json
    market_size.json
    competitors.json
    voc.json
    opportunity.json
    profitability.json
  output/
    report.html
    report.md
    delivery_result.json
```

## 结束语模板

完成后只在聊天里给高密度摘要：

```text
报告已生成：/absolute/path/to/report.html

核心判断：Go / Watch / No-Go
任务目的：
方法链：
主要机会：
最大风险：
数据范围：
输出方式：
输出风格：
```

不要在聊天中粘贴完整 HTML。
