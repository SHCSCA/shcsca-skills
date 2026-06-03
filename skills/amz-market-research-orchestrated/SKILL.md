---
name: amz-market-research-orchestrated
description: "Amazon / 电商市场调研可执行 v2 主控 Skill。用户要求调研市场、品类、赛道、竞品格局、用户需求、产品迭代、新细分机会、TikTok 验证或 1688 供应链成本时使用。以 Sorftime MCP 为主数据源，Firecrawl 为公开网页补充，生成可审计的 Data Pack、Analysis Plan、交互式静态站点三报告和 Markdown 审计稿。"
---

# Amazon 市场调研总控 v2

## 定位

`amz-market-research-orchestrated` 是面向 Amazon / 跨境电商选品和产品策略的深度市场调研主控 Skill。它是唯一外部触发入口，不再依赖未随仓库提供的外部 `data-source-orchestrator`、`market-method-orchestrator`、`research-output-orchestrator`；v2 内置最小可执行流程，并在自身目录内管理三个报告 child module 和一个 critic child module：

| Internal module | 职责 |
|---|---|
| `amz-market-research-orchestrated` | 调研确认、采集调度、全局清洗去重、质量评分、子报告编排和交付整合 |
| `child_skills/market-depth-report` | 市场深度调研报告 |
| `child_skills/lifecycle-strategy-report` | 产品全生命周期拓品战略报告 |
| `child_skills/demand-gap-report` | 用户心智断层与需求机会报告 |
| `child_skills/market-research-critic` | 证据强度、结论一致性和客户安全语义评审 |

内部 child modules 不作为顶层 skill 单独触发：它们只由主控读取、调度和验收。

主控流程：

1. 澄清调研目的和数据深度。
2. 生成 `OrchestrationBrief`。
3. 用 Sorftime MCP 抓 Amazon / TikTok Shop / 1688 主数据。
4. 用 Firecrawl 抓公开报告、品牌站、测评、法规和召回信息。
5. 标准化为 `data_pack.json` 和 `data/normalized/normalized_data_pack.json`，交叉验证、去重、补中文映射，并保留 `source_id`、质量评分和数据缺口。
6. 将只读 `normalized_data_pack.json`、`analysis_plan.json`、`report_brief.json` 和客户安全 `*_view.json` 交给三个内部报告模块生成三份报告。
7. 调用内部 critic 模块输出 `critic_review.json` 和 `refinement_plan.json`；如不通过，最多做两轮差量修正，不重新采集、不改写事实源。
8. 用脚本校验交付物，确认报告可追溯、可复核、可离线打开，且客户可见资产不泄露技术字段。

详细工具映射见 [sorftime-firecrawl-tool-map.md](references/sorftime-firecrawl-tool-map.md)，数据契约见 [data-pack-contract.md](references/data-pack-contract.md)，HTML 设计规范见 [html-report-design-contract.md](references/html-report-design-contract.md)，验收场景见 [acceptance-scenarios.md](references/acceptance-scenarios.md)。

## 触发场景

当用户说以下任一意图时使用本 Skill：

- 帮我调研某个 Amazon 市场、品类、赛道或产品想法。
- 判断一个新品类、新产品方向或微创新是否值得做。
- 拆解竞品格局、价格带、评论痛点、Listing 卖点和差异化机会。
- 从 Amazon Review、TikTok Shop、Reddit、YouTube、测评站或公开报告里做 VOC。
- 评估 TikTok 热度是否能反哺 Amazon 选品。
- 用 1688 / Alibaba 供应链信号估算采购成本、同款供给和可复制风险。
- 输出老板/客户可看的 HTML、Markdown 和数据包。

如果用户只是要下载某个 ASIN 的评论、查一个关键词或抓单页数据，不启动完整调研总控；直接调用对应 MCP 或轻量采集流程即可。

## 核心原则

1. 先明确决策，再选择数据深度，再拿数据，再下结论。
2. Sorftime 是主数据源；Firecrawl 只能作为公开网页补充和兜底。
3. 数据广度不等于深度；v2 必须优先打穿 Amazon 产品池、评论、关键词、趋势和供应链证据。
4. 所有关键结论必须追溯到 `data_pack.json` 的 `source_id`，或明确标注为 AI 推理。
5. 报告不能把 Sorftime、第三方或公开网页估算写成 Amazon 官方销量。
6. 缺少成本、退货率、FBA 费用或广告数据时，只写成本门槛和利润红线，不写伪利润表。
7. TikTok 热度只能作为需求、内容、场景和渠道证据，不能单独证明 Amazon 购买需求。
8. 数据失败时保留模块、说明缺口和影响，不删除章节假装完整。

## Step 0: 解析并补齐用户输入

完整三报告调研启动前必须先做“调研确认卡”。优先从用户原话中解析，但必须让用户明确确认；如果用户没有明确答复，不进入 Sorftime / Firecrawl 采集和报告生成。

```text
为了把调研做成可审计的三报告交付包，我需要你明确确认下面信息：

1. 研究对象：关键词、ASIN、品牌、类目、产品想法或文件。
2. 主要决策：新品类进入 / 产品迭代 / 细分机会 / 竞品差异化 / VOC / 供应链利润 / 汇报。
3. 目标市场：Amazon 站点、TikTok Shop 站点、供应链市场。
4. 数据深度：快速版 / 标准版 / 深度版。
5. 输出方向：三份报告都要，还是更重市场判断 / 生命周期拓品 / 用户需求断层中的某一份。
6. 约束条件：目标价格带、禁做方向、已知竞品、已有成本、必须包含或排除的信息。

请直接按 1-6 回复；我会基于你的答复生成 OrchestrationBrief 再开始采集。
```

默认值：

- 目标市场：Amazon US。
- TikTok Shop：US。
- 1688：CN 供应端。
- 输出：`三份 HTML + Markdown + Data Pack`，便携 HTML 入口为 `output/html_reports/report.html`；`output/report.html` 仅作兼容入口。
- 语言和风格：中文、本土化、老练直接、面向跨境卖家决策。
- `primary purpose` 只能有一个，`secondary purposes` 最多两个。

显式确认规则：

- 如果用户已经在一句话里给齐 1-6，先复述成确认卡，并要求用户回复“确认”或修改点。
- 如果用户只给研究对象，必须先问清主要决策、数据深度和输出方向。
- 如果用户要“直接开始”，但关键字段缺失，仍需先让用户补齐；不能用默认值静默启动完整三报告。
- 默认值只能作为推荐项呈现，不能替代用户明确答复。

不要默认索取：

- Sorftime / Firecrawl API key，除非当前环境没有对应 MCP。
- 完整竞品清单，除非用户已有指定竞品。
- 成本参数，除非用户希望做利润敏感性测算。
- Review 文件，除非 Sorftime 评论不可用或样本严重不足。

## Step 1: 确认数据深度

按 [research-scope-menu.md](references/research-scope-menu.md) 执行。默认推荐“标准版”，只有用户明确要快速判断时才降级。

| 深度 | 目标 | 最小数据门槛 |
|---|---|---|
| 快速版 | 判断类目是否值得继续看 | Amazon 关键词详情、搜索结果/产品池 20-50、核心竞品详情、核心 ASIN 评论、Firecrawl 3-5 个公开来源 |
| 标准版 | 支撑选品或产品方向判断 | Amazon Top100 或近似 Top100、关键词趋势/延伸词/自然位、至少 1000 条关键词样本、竞品详情/趋势/变体/评论/反查词、TikTok 相似产品与趋势、1688 相似货源、公开报告/品牌站/测评 |
| 深度版 | 支撑立项、汇报或打样前判断 | 标准版全部内容、多关键词交叉去重、至少 1000 条关键词样本、竞品分层、TikTok 商品/视频/达人链路、1688 成本带和同款供给、质量评分、缺口和下一步验证动作 |

## Step 2: 生成 OrchestrationBrief

使用 [orchestration-brief-contract.md](references/orchestration-brief-contract.md) 的格式。Brief 必须包含：

- `task_id`
- `research_object`
- `task_purpose`
- `market_scope`
- `data_scope`
- `output_scope`
- `constraints`

命名建议：`{normalized_keyword}_{market}_{yyyymmdd}`，例如 `ai_plush_us_20260526`。

## Step 3: Sorftime 主数据采集

按研究对象选择入口：

- 关键词 / 产品想法：先跑 `keyword_detail`、`keyword_extends`、`keyword_search_results`、`product_search`。
- ASIN：先跑 `product_detail`、`product_trend`、`product_reviews`、`product_variations`、`product_traffic_terms`。
- 类目：先跑 `category_name_search`、`category_report`、`category_trend`、`category_keywords`。
- TikTok 验证：跑 `tiktok_similar_product`、`tiktok_product_detail`、`tiktok_product_trend`、`tiktok_product_video`、`tiktok_product_video_author`。
- 供应链验证：跑 `ali1688_similar_product`。

标准版和深度版必须补齐关键词样本深度：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir reports/{task_id} --min-keywords 1200
```

评论样本采集建议在产品池/ASIN 明确后运行：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_reviews.py --dir reports/{task_id} --review-type Both --min-reviews 80
```

采集完成但进入归一化/渲染前，必须先运行数据准备度门禁：

```bash
python skills/amz-market-research-orchestrated/scripts/check_data_readiness.py --dir reports/{task_id} --depth standard --write
```

若输出 `acceptance_ready=false`，不得继续生成客户版三报告；只能继续真实采集或把当前目录标为历史/演示样本。尤其当产品池为 0 或关键词样本不足 1000 时，禁止用 AI 推断、模板样例或重复数据补足。

采集策略：

- `category_keywords` 按类目 nodeId 分页采集，Sorftime 每页 20 条。
- `keyword_extends` 对主关键词、核心子方向词、已有高相关词分页采集。
- 目标采集量默认 1200 条，给去重留余量；归一化后 `data_pack.keywords` 不得少于 1000 条。
- 评论样本是置信度门槛：标准版建议 80 条以上，深度版建议 200 条以上；不足时 VOC 可降级展示，但不能写精确比例或强结论。
- 关键词和评论采集脚本低于门槛时返回退出码 `2`，这不是环境故障，而是数据深度未达标信号。
- 原始 MCP 返回必须保存到 `data/raw/`，采集摘要保存到 `data/normalized/keyword_collection_summary.json`。

所有原始返回保存到：

```text
reports/{task_id}/data/raw/{provider}_{tool}_{slug}.json
```

所有标准化实体写入：

```text
reports/{task_id}/data/data_pack.json
reports/{task_id}/data/normalized/*.json
```

## Step 4: Firecrawl 补充采集

Firecrawl 只补公开网页证据，不替代 Sorftime 主数据。

优先补：

- 行业报告和市场规模公开页。
- 竞品品牌官网、独立站、产品页。
- BestBuy、Walmart、Target 等零售对照页。
- Consumer Reports、Wirecutter、Reddit、YouTube 页面或公开测评。
- CPSC、FDA、FTC、Amazon policy 等法规、召回、合规信息。

Firecrawl 结果必须写入 `web_documents`，并带 `source_id`、`provider=firecrawl`、`fetched_at`、`url`、`confidence`、`limitation`。不得把 Firecrawl 摘要绕过 Data Pack 直接写进报告结论。

## Step 5: 标准化 Data Pack

`data_pack.json` 至少包含：

- `sources`
- `products`
- `keywords`
- `categories`
- `reviews`
- `tiktok_products`
- `tiktok_videos`
- `suppliers`
- `web_documents`
- `data_gaps`
- `quality`

每个非空实体必须包含：

- `source_id`
- `provider`
- 原平台主键，如 `asin`、`keyword`、`node_id`、`product_id`、`url`
- 采集或样本限制说明，如适用

如果某模块无数据，保留空数组，并在 `data_gaps` 写明原因和影响。

生成初版 `data_pack.json` 后必须先运行归一化脚本，再进入分析和 HTML 渲染：

```bash
python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir reports/{task_id}
```

归一化脚本必须完成：

- 交叉验证和去重：Amazon 产品按 ASIN 或标题指纹，关键词按“全局词 / ASIN 反查词”分桶，Review 按 ASIN+日期+标题+正文指纹，TikTok 按 product_id / canonical URL，Web 按 canonical URL，1688 按 canonical URL、商品 ID 或标题+店铺。
- 数据血缘合并：保留 `source_ids`、`validation.evidence_source_count`、`validation.cross_validated`、`validation.conflicts`。
- 中文映射：关键词新增 `keyword_cn`、`intent_cn`、`relevance_cn`；产品新增 `title_cn`、`segment_cn`、`positioning_cn`；评论新增 `title_cn`、`summary_cn`、`themes_cn`，客户版 HTML 不直接展示英文原评。
- 噪声分层：核心关键词、相邻泛流量、ASIN 反查流量词必须分开展示，不能把泛词流量当成品类机会。
- 幂等 baseline：首次归一化写入 `data/normalized/normalization_baseline.json`，后续反复渲染不得冲掉原始样本数和去重收益。
- 样本门槛：标准版和深度版归一化后关键词不得少于 1000 条；不足时继续分页采集或在 `data_gaps` 标注为未达交付标准。
- 准备度门槛：`data/normalized/data_readiness_report.json.acceptance_ready` 必须为 `true` 才能进入三报告渲染；`non_acceptance_sample` 只能作为历史/演示样本保留，不能用于交付宣称。

标准化结果保存到：

```text
reports/{task_id}/data/normalized/cross_validated_data_pack.json
reports/{task_id}/data/normalized/normalized_data_pack.json
```

## Step 6: 分析模块

按任务目的组合方法链，输出 `analysis_plan.json`。v2 固定为三条报告方法链：

1. 市场深度调研：大盘结论、需求结构、竞品格局、VOC 洞察、标杆打法、机会定义、TikTok 内容信号、1688 供应链判断、风险与行动摘要。
2. 产品全生命周期拓品战略：战略仪表盘、用户画像、生命周期旅程、四维拓品生态、拓品方案池、Bundle 策略、30/60/90 天路线图、风险矩阵、市场验证摘要。
3. 用户心智断层与需求机会：研究对象概述、决策看板、`$APPEALS` 痛点图、满意度鸿沟、`KANO × JTBD`、用户原声、需求优先级。

推荐额外写入：

```text
reports/{task_id}/analysis/
  lifecycle_strategy.json
  demand_gap.json
```

如果这两个文件缺失，HTML 渲染器会从 Data Pack 推导基础区块，但必须在 `data_gaps` 或 `analysis_plan.limitations` 标注分析深度不足。

方法链必须记录：

```json
{
  "method_id": "market.top100_competitor_scan",
  "name": "Top100 竞品扫描",
  "used_source_ids": ["src_001"],
  "output": "生成价格/评分/月销/评论/卖点矩阵"
}
```

## Step 7: 输出交付物

默认写入：

```text
reports/{task_id}/
  report_brief.json
  data/
    raw/
    normalized/
      normalized_data_pack.json
    data_pack.json
    lineage.md
  analysis/
    analysis_plan.json
    market_size.json
    competitors.json
    voc.json
    opportunity.json
    profitability.json
    lifecycle_strategy.json
    demand_gap.json
  output/
    report.html
    html_reports/
      report.html
      market-depth-report.html
      lifecycle-strategy-report.html
      demand-gap-report.html
      assets/
        report.css
        report.js
        report-data.json
    report.md
    delivery_result.json
```

报告默认要求：

- HTML 必须按 [html-report-design-contract.md](references/html-report-design-contract.md) 生成三报告交付包：四个可交付 HTML 必须放在 `output/html_reports/` 同一文件夹内，其中 `report.html` 是便携入口页，三份子报告分别是 `market-depth-report.html`、`lifecycle-strategy-report.html`、`demand-gap-report.html`；`output/report.html` 是兼容入口，链接到 `html_reports/`。
- HTML 优先使用 `assets/report-index-template.html`、`assets/market-depth-template.html`、`assets/lifecycle-strategy-template.html`、`assets/demand-gap-template.html` 和 `scripts/render_dashboard_html.py`；不得把 Markdown 包进 `<pre>` 或 `.markdown-body`。
- HTML 可离线打开，不依赖外部 CDN 才能显示核心内容、布局、表格和关键判断。
- HTML 静态站点包必须包含 `output/html_reports/assets/report.css`、`report.js`、`report-data.json`，支持表格筛选/排序、顶部导航、移动端目录、折叠证据和轻量图表交互。
- 三份子报告的视觉与交互基准必须吸收用户提供的本地下载模板：`downloadpage/143101` 对应市场深度、`downloadpage/143511` 对应生命周期、`downloadpage/143645` 对应需求断层。只抽取报告页 HTML/CSS/JS 的布局与交互模式到共享 `report.css` / `report.js`；不得搬运 `_next` chunks、iframe case 壳、CDN 依赖或样例硬编码数据。
- Markdown 保留完整证据链和方法链；它是审计稿，不是 HTML 的渲染源。
- HTML 要有客户可读的证据强度、样本覆盖、数据缺口、置信等级和建议动作；Markdown / JSON 保留完整审计链路。
- 聊天里只给摘要和路径，不粘贴完整报告。

HTML 主体必须使用真实结构化组件：

- 四个 HTML 都必须是 standalone HTML document，并带对应 `data-report-style`。
- 三份子报告必须使用 `<section>` 编号章节、KPI cards、CSS mini charts、evidence tables、cards、risk/roadmap/timeline 等结构化组件。
- 竞品、需求、1688、TikTok、Web、SKU、KANO/JTBD 等必须用客户可读的 insight table / card / matrix 表达，不能用 Markdown 表格文本。
- 客户版 HTML 禁止展示 `source_id`、`source_ids`、provider/tool、raw_path/path、Product ID、product_id、ASIN 值或“来源”字段；`output/html_reports/report.html` 必须用同文件夹相对链接打开三份子报告，不能写 `output/` 前缀。
- 能展示的数据要先转成 AI 深度分析后的结论、商业含义和建议动作；原始长表、数据血缘和完整来源细节只保留在 `data_pack.json`、`lineage.md`、`report.md`、`delivery_result.json` 中。
- 评论/VOC 必须先做中文化映射：用户原声展示中文摘要、星级、情绪、主题和需求含义；英文评论原文、英文标题、抓取字段原值只留在审计文件。

推荐生成顺序：

1. 先生成 `data_pack.json` 和 `analysis/*.json`。
2. 标准版/深度版先补齐 1000+ 关键词样本：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir reports/{task_id} --min-keywords 1200
```

3. 运行数据准备度门禁，失败则停止交付生成并继续采集：

```bash
python skills/amz-market-research-orchestrated/scripts/check_data_readiness.py --dir reports/{task_id} --depth standard --write
```

4. 运行交叉验证 / 去重 / 中文映射：

```bash
python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir reports/{task_id}
```

5. 再运行结构化 HTML 渲染器：

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir reports/{task_id}
```

6. 如需增强视觉，再基于生成的 HTML 做局部编辑，但必须保留四个 `data-report-style` 标记和所有必备章节。

完成后运行：

```bash
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/{task_id}
```

只有输出 `validate_ok` 才能宣称交付完成。

## 报告质量规则

- 写“估算月销量（Sorftime）”，不要写“官方销量”。
- 不把 Amazon `bought in past month`、Sorftime 估算、TikTok sold 混成一个数字。
- 不用 TikTok 热度替代 Amazon 购买需求。
- 不用少量评论写精确百分比；样本小则写频次、主题和代表证据。
- 不在缺成本时写伪利润表；改写价格红线和成本门槛。
- 不因为 TikTok、1688 或 Firecrawl 失败就删除模块；保留模块并说明缺口。
- 所有关键结论必须能在审计文件中追溯到 `source_id`，但客户版 HTML 不展示这些技术标识。
- 所有关键方法必须能追溯到 `method_chain`。
- `output/html_reports/report.html` 必须包含 `data-report-style="three-report-index-v2"`，并用同文件夹相对链接打开三份子报告；`output/report.html` 必须作为兼容入口链接到 `html_reports/`。
- 三份子报告必须分别包含 `data-report-style="market-depth-report-v2"`、`data-report-style="lifecycle-strategy-report-v2"`、`data-report-style="demand-gap-report-v2"`。
- 四个 HTML 都不得出现 `<pre>` 包裹的 Markdown、原始 Markdown 表格、或只靠标题段落撑起来的文章页。
- 输出默认全中文；客户版 HTML 仅保留品牌名、平台名和必要英文专有名词，ASIN / Product ID / source_id 等技术标识只留在审计文件。
- 客户版 HTML 不直接展示英文评论原文或英文评论标题；必须转成中文摘要、中文主题、情绪标签和建议动作。

## 结束语模板

```text
报告入口已生成：/absolute/path/to/output/html_reports/report.html
兼容入口：/absolute/path/to/output/report.html

核心判断：Go / Watch / No-Go
任务目的：
数据深度：
主要数据源：Sorftime / Firecrawl / 用户文件
方法链：
主要机会：
最大风险：
数据质量：
输出文件：
- /absolute/path/to/output/html_reports/market-depth-report.html
- /absolute/path/to/output/html_reports/lifecycle-strategy-report.html
- /absolute/path/to/output/html_reports/demand-gap-report.html
```

不要在聊天中粘贴完整 HTML。
