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

详细工具映射见 [sorftime-firecrawl-tool-map.md](references/sorftime-firecrawl-tool-map.md)，数据契约见 [data-pack-contract.md](references/data-pack-contract.md)，HTML 设计规范见 [html-report-design-contract.md](references/html-report-design-contract.md)，模板 parity 清单见 [html-template-parity-checklist.md](references/html-template-parity-checklist.md)，验收场景见 [acceptance-scenarios.md](references/acceptance-scenarios.md)，样本登记见 [sample-coverage-matrix.md](references/sample-coverage-matrix.md)，100 分改进路线见 [100-point-improvement-plan.md](references/100-point-improvement-plan.md)。

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

## 100 分工作协议

本 Skill 的核心不是测试脚本，而是一次完整市场调研交付的行为协议。Agent 使用本 Skill 时按以下优先级执行：

1. **先交付调研判断框架**：明确研究对象、主要决策、市场范围、数据深度和输出方向；没有确认卡，不进入完整三报告采集。
2. **再拿真实证据**：优先调用 Sorftime / Firecrawl / 本地可用采集工具；不能用 AI 编造产品、关键词、评论、供应商或网页证据。
3. **再清洗和归一化**：Data Pack 是唯一事实底座；子报告只能读 `normalized_data_pack.json`，不能改写事实口径。
4. **再编排子报告**：市场深度、生命周期、需求断层三个 child modules 分别产出自己的客户安全 view 和 HTML。
5. **再让 critic 驳回或放行**：critic 不是装饰字段；二次修正后仍不通过时，主控必须停止交付宣称。
6. **最后才做 proof**：`run_acceptance_proof.py` 只用于证明交付已闭环；不能用跑测试替代调研、分析、采集或报告质量。

HTML 模板是标准化交付资产，不是 AI 临场发挥的设计稿。三个 child report 必须以 `assets/canonical_templates/` 中的参考 HTML 为母版，保留其布局、样式、CSS class 体系、图表/表格/卡片结构和交互模型；AI 与脚本只负责把 `normalized_data_pack.json` 清洗后的事实、中文分析文案和客户安全 view 填入模板槽位。不得因为数据不足、生成方便或审美偏好而改成通用报告壳、Markdown 包装页或另一套临时 UI。

从 78-82 分推进到 100 分的主线见 [100-point-improvement-plan.md](references/100-point-improvement-plan.md)。该文件记录当前分数、已完成能力、剩余缺口和下一步推荐。

执行中必须按“业务进度”汇报，而不是按“测试进度”汇报。有效进度包括：确认卡是否完成、真实数据是否拿到、Data Pack 是否去重归一、三个 child modules 是否产出报告 view、critic 是否驳回或放行、客户版 HTML 是否可交付。单元测试、脚本测试和 validator 只能作为这些动作之后的证明。

Subagent 只能承担可隔离的侧翼任务，例如采集证据审计、HTML 客户安全审计、critic contract 审计或模板 parity 审计。主控 Agent 必须保留架构决策、Data Pack 口径、是否交付、是否降级为样本的最终责任。

Fail-closed 恢复与停止规则：

- 归一化必须先运行 `research_relevance_gate` 再进入 view model 或 HTML。客户报告只能读取 `effective_products`、`effective_keywords`、`effective_reviews`、`effective_suppliers`；原始 `products/keywords/reviews/suppliers` 只留审计和复盘。对于 `smart lighting`、`lighting`、`智能照明` 等照明研究，`owala`、`water bottle`、`bottle`、运动水杯、非照明家居装饰等污染品或污染词必须剔出有效池；`keyword_cn=未映射关键词` 或缺少照明语义的关键词不得参与市场规模、赛道、推荐结论和图表。
- 模板完整和结论可信必须同时满足。数据不达标时采用“完整模板诊断模式”：保留所有章节、卡片、图表容器、表格槽位和交互，但对应槽位只显示中文业务诊断、失败原因和补采动作；不得删除章节、空图、显示英文技术错误，也不得用伪数据填充。
- `categories` 必须从有效产品类目聚合生成，不能出现有效产品有类目但 `categories=0` 的矛盾。
- 关键词必须按 `normalized lowercase keyword + source bucket` 去重；重复率超过门槛时 readiness 失败，不得继续输出完整市场判断。
- `acceptance_ready=false` 时，必须先运行 `recover_data_readiness.py` 做定向补采恢复；恢复轮次耗尽后若只剩供应链报价深度/字段质量/价差问题，则进入 `partial_acceptance_sample`，继续输出市场、生命周期和需求报告，但禁用供应链毛利率结论；若仍有产品池、关键词、来源血缘或赛道拆分阻断，才停止客户版三报告并登记为 `non_acceptance_sample`。
- critic 二次修正后仍 `pass=false` 时，不得声明交付完成；必须输出未解决问题和下一轮差量修正计划。
- critic `grade=D`、`score<60`、readiness 核心门禁失败、数据污染命中或 HTML validator 失败时，最终 `pass` 必须为 `false`；`run_acceptance_proof.py` 必须聚合 readiness、critic 和 HTML validator。完整交付以 `full_acceptance_pass=true` 为准；若只剩被允许的局部阻断且 `partial_report_ready=true`，可输出 `delivery_mode=diagnostic_delivery`，但必须禁用对应结论并展示中文诊断。
- 产品池、关键词、评论或网页证据不足时，不得用 AI 推断、模板样例或重复数据补齐。
- 客户版 HTML 出现 `source_id`、provider、raw path、内部版本标记、`竞品记录` 等技术或占位字段时，必须停止交付并修正渲染层。
- ASIN 只允许在“目标锚点”“标杆竞品狙击拆解”“竞品表”“竞品参考毛利率测算”“SKU 参考竞品”中通过白名单组件展示；其他区域仍需脱敏。
- 英文原始评论只允许作为 VOC 短摘出现，并必须同时展示中文归纳、主题、情绪和行动建议。
- 市场深度报告必须生成并读取 `analysis/cosmo_alexa_tags.json`。该文件固定包含 15 类 COSMO + Alexa 标签关系，优先读取 `analysis_plan.report_label_profile.cosmo_relation_terms` 作为当前类目的 AI 标签画像，再用当前 `effective_products`、`effective_keywords`、`effective_reviews`、TikTok 信号和 1688 标题/类目做逐词证据匹配和补充；不得写死某个行业的标签词。AI 标签画像只作为候选词，未被当前有效数据文本支撑的词不能进入客户可见 `terms`，只能在审计文件中作为低覆盖补证线索保留；不得写成高置信事实。
- COSMO 标签必须按 relation 生成差异化词组，禁止把同一组标签或同一个泛化标签批量复用到多个 relation。英文 cue 必须按词边界匹配，不能让 `pet` 命中 `competitor`、`cat` 命中其他单词片段。
- 客户 HTML 的 COSMO 模块只能展示中文标签、`产品意图/用户意图` 和客户可读的 `产品/用户` 标记；`P01/U09` 这类槽位编号只能保留在 `data-cosmo-relation` 属性和审计文件中，不得出现在可见客户文案。`USED_*`、`CAPABLE_OF`、`IS_A`、`xWANT`、`xIs_A`、`xINTERSTED_IN`、`REL_*` 等内部 relation code 只能保留在 `analysis/cosmo_alexa_tags.json` 和审计文件，不能出现在可见文本、隐藏文本或 `data-*` 属性。
- 生命周期报告必须生成并读取 `analysis/lifecycle_strategy.json`。其中 `sku_candidate_pool` 是真实候选池，`recommended_skus` 是推荐 SKU，`ecosystem_nodes` 是图表节点，`filter_diagnostics` 说明筛选损耗；生命周期策略类型必须用 `core_validation`、`scenario_upgrade`、`accessory_gap`、`maintenance_repurchase` 语义 key 和中文 `type_label_cn`，不得在数据层或客户层使用裸 `A/B/C/D`；旧 5 个固定卡片只代表模板布局槽，不得冒充完整 SKU 池。
- `research_relevance.passed=false` 的产品、关键词、评论、供应记录不得进入客户 view model。若剔除后 SKU 候选池或标签覆盖不足，客户页保留完整模板并显示中文诊断，不得用 `未命名竞品`、`户外感应灯`、`Type A/B/C/D` 或旧 fallback SKU 填充。

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
- TikTok 验证：跑 `collect_sorftime_tiktok_signals.py`，内部按 Sorftime schema 调用 `tiktok_similar_product(searchName,page,site)`、`tiktok_product_detail(productId,site)`、`tiktok_product_trend(productId,site)`、`tiktok_product_video(productId,page,site)`、`tiktok_product_video_author(productId,site)`。
- 供应链验证：跑 `collect_sorftime_1688_suppliers.py`，内部按 Sorftime 官方文档调用 `ali1688_similar_product(searchName,page)`，并记录每页实际返回字段；1688 官方 16 字段覆盖率写入 `documented_field_coverage`，`Url/url` 只作为 `URL` 别名处理。若 MCP 实际响应缺少 `Title` / `URL`，必须阻断供应链毛利率结论并写入诊断。
- 竞品池补采：跑 `collect_sorftime_products.py`，内部优先按 Amazon schema 调用 `product_search`，必要时回退到 `keyword_search_results`，不得复用 TikTok 或 1688 参数结构。
- Amazon 竞品主图：`collect_sorftime_products.py` 必须统计 `image_url_coverage`。若有效竞品池图片覆盖不足，必须写入 `data_gaps.type=competitor_image_coverage` 并继续用 `collect_sorftime_product_enrichment.py` 对核心 ASIN 调用 `product_detail` 补采图片字段；竞品全景扫描、竞品表、标杆竞品狙击拆解、生命周期 SKU 卡和 SKU 表只能展示 Amazon 竞品主图或 ASIN 详情图，不能使用 1688 货源图冒充 Amazon 竞品图。所有远程竞品图必须带本地静态 `report.js` 加载失败兜底；若 Sorftime 没返回图片 URL，保留图片槽位并显示中文数据诊断；若已有 Amazon 图片 URL 但浏览器运行时被远端阻断或超时，保留稳定图片框并静默切换为中性占位，不允许客户页出现浏览器破图或 `图片加载失败`、`竞品图片未返回`、`参考竞品图片未返回` 等失败文案。生命周期候选池应把参考竞品图写入 `reference_image_url`；若 Sorftime 没返回图片，保留 SKU 槽位并显示数据诊断，不造图、不借用供应端图片。
- Amazon 竞品增强：跑 `collect_sorftime_product_enrichment.py`，对已入池 ASIN 调用 `product_detail`、`product_trend`、`product_variations`、`product_traffic_terms`、`competitor_product_keywords`。可用维度必须写回 Data Pack；返回空的维度必须进入 `data_gaps`，不能写成已验证事实。若某个维度对首个 ASIN 返回 0 行，必须换其他已入池 ASIN 继续复测；多 ASIN 仍为空时才写成当前 Sorftime 维度缺口。
- MCP 字段审计：当用户质疑官方字段与实际结果不一致，或采集字段缺失时，跑 `audit_sorftime_mcp_contracts.py`，保存 Amazon / TikTok / 1688 的 schema、实际参数、返回行数和实际字段集合。`tools/list` 只能证明入参 schema；出参字段覆盖率必须来自真实 `tools/call` 抽样。Amazon / TikTok 没有官方固定 16 字段清单时，以本 skill 的标准化维度覆盖率审计；1688 按官方 16 字段审计。

标准版和深度版必须补齐关键词样本深度：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir reports/{task_id} --min-keywords 1200
```

标准版和深度版必须补齐 Amazon 竞品池深度：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_products.py --dir reports/{task_id} --min-products 30 --max-seeds 8 --max-pages 3 --site US --min-segments 3 --min-per-segment 10
```

产品池补齐后必须对核心 ASIN 做增强采集：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_product_enrichment.py --dir reports/{task_id} --max-products 10 --max-pages 1 --site US
```

评论样本采集建议在产品池/ASIN 明确后运行：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_reviews.py --dir reports/{task_id} --review-type Both --min-reviews 80
```

TikTok 内容信号建议在关键词/产品池明确后运行；TikTok 只能作为内容场景、渠道热度和创作者链路证据，不能替代 Amazon 购买需求：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_tiktok_signals.py --dir reports/{task_id} --site US --max-seeds 4 --max-pages 1 --max-products-detail 3 --video-pages 1
```

采集完成但进入归一化/渲染前，必须先运行数据准备度门禁：

```bash
python skills/amz-market-research-orchestrated/scripts/check_data_readiness.py --dir reports/{task_id} --depth standard --write
```

若输出 `acceptance_ready=false`，先运行恢复器，而不是立刻下结论：

```bash
python skills/amz-market-research-orchestrated/scripts/recover_data_readiness.py --dir reports/{task_id} --depth standard --max-rounds 2
```

恢复器会按失败模块定向调用关键词、Amazon 产品池、1688、评论和 TikTok 采集脚本，并在每轮后重新归一化和复检。恢复后若只剩 1688 供应链报价问题，报告进入 partial 模式：客户仍可阅读市场深度、生命周期和需求断层分析，供应链模块只展示补采诊断和报价池质量，不输出毛利率结论。恢复后若产品池不足、关键词样本不足 1000、来源血缘缺失或赛道拆分失败，不得继续生成客户版三报告；只能输出补采诊断并把当前目录标为历史/演示样本。所有场景都禁止用 AI 推断、模板样例或重复数据补足。

标准版 / 深度版还必须满足以下硬门槛：

- 标准版至少 30 个去重有效 Amazon 竞品；深度版至少 60 个。
- 每个有效竞品必须具备 ASIN、标题、品牌、价格、评分、评论数、销量或排名代理字段、细分赛道。
- `smart lighting`、`lighting`、`智能照明` 等大词必须先拆分赛道；宽泛研究至少 3 个主赛道，每个主赛道至少 10 个有效竞品。
- 1688 去重有效报价至少 50 条只是数量门槛；商品标题覆盖率和链接/稳定商品指纹覆盖率必须各不低于 70%。
- 1688 价格分布若 `max/P50 > 20` 或 `P75/P25 > 5`，先检查同搜索词报价桶；若某一 `seed_keyword` 桶拥有至少 50 条有效报价且字段质量、价差门禁均通过，则客户页只能使用该同口径报价桶进入毛利率测算，并把全局价差异常写为 warning。若全局和同桶都不通过，必须阻断毛利率测算，输出补采诊断。
- 供应链毛利率必须绑定真实 Amazon 竞品 ASIN 的价格、月销量、评分和评论数，并使用 1688 P25/P50/P75 成本分位数；不得用品牌均值或混合类目均值冒充。
- 门槛不通过时，渲染脚本默认先运行恢复器；恢复后仍不通过，才写补采诊断 HTML，命令仍需返回失败，避免被误当成完整客户报告。

采集策略：

- `category_keywords` 按类目 nodeId 分页采集，Sorftime 每页 20 条。
- `keyword_extends` 对主关键词、核心子方向词、已有高相关词分页采集。
- 目标采集量默认 1200 条，给去重留余量；归一化后 `data_pack.keywords` 不得少于 1000 条。
- 评论样本是置信度门槛：标准版建议 80 条以上，深度版建议 200 条以上；不足时 VOC 可降级展示，但不能写精确比例或强结论。
- TikTok 相似商品按 `searchName/page/site` 采集，商品详情/趋势/视频/达人链路按 `productId/site` 或 `productId/page/site` 采集；1688 相似货源按 `searchName/page` 采集。MCP 返回 `isError=true` 必须写入诊断；成功但 0 行必须换搜索词、ASIN、productId 或 category node 复测后再判定为数据缺口；实际响应缺少官方文档关键字段时必须写入诊断，不能当作空数据。
- 关键词、评论、TikTok 和 1688 采集脚本低于门槛时返回退出码 `2`，这不是环境故障，而是数据深度未达标信号。
- 原始 MCP 返回必须保存到 `data/raw/`，采集摘要保存到 `data/normalized/*_collection_summary.json`；恢复过程必须保存到 `data/normalized/readiness_recovery_report.json`。

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
- 中文映射：关键词新增 `keyword_cn`、`intent_cn`、`relevance_cn`；产品新增 `title_cn`、`segment_cn`、`positioning_cn`；评论新增 `title_cn`、`summary_cn`、`themes_cn`，客户版 HTML 不直接展示英文原评。归一化脚本只负责清洗、去重、字段标准化和污染字段剔除，不得为某个类目写死客户标题、赛道名、标签或拓品类型名。
- 噪声分层：核心关键词、相邻泛流量、ASIN 反查流量词必须分开展示，不能把泛词流量当成品类机会。
- 幂等 baseline：首次归一化写入 `data/normalized/normalization_baseline.json`，后续反复渲染不得冲掉原始样本数和去重收益。
- 样本门槛：标准版和深度版归一化后关键词不得少于 1000 条；不足时继续分页采集或在 `data_gaps` 标注为未达交付标准。
- 准备度门槛：`data/normalized/data_readiness_report.json.acceptance_ready=true` 代表完整交付；`partial_report_ready=true` 代表诊断交付，只允许在固定模板中展示可验证模块和中文阻断原因，不得输出被阻断的毛利率、供应链可控或首发可打样结论；`non_acceptance_sample` 只能作为历史/演示样本保留，不能用于交付宣称。
- 状态一致性：最终交付必须让 `data_readiness_report.json`、`delivery_result.json.data_readiness`、`report-data.json.readiness` 三处一致；critic 通过不能覆盖 readiness 失败。

标准化结果保存到：

```text
reports/{task_id}/data/normalized/cross_validated_data_pack.json
reports/{task_id}/data/normalized/normalized_data_pack.json
```

## Step 6: 分析模块

按任务目的组合方法链，输出 `analysis_plan.json`。v2 固定为三条报告方法链：

1. 市场深度调研：大盘结论、需求结构、竞品格局、VOC 洞察、标杆打法、机会定义、TikTok 内容信号、1688 供应链判断、风险与行动摘要。
2. 产品全生命周期拓品战略：战略仪表盘、用户画像、生命周期旅程、四维拓品生态、拓品方案池、Bundle 策略、30/60/90 天路线图、风险矩阵、市场验证摘要。
3. 用户心智断层与需求机会：研究对象概述、决策看板、需求主题痛点图、满意度鸿沟、`KANO × JTBD`、用户原声、需求优先级。

分析阶段必须由 AI 基于当前研究对象、有效竞品标题、类目、关键词、评论和供应链证据生成 `report_label_profile`，并写入 `analysis_plan.json`。这是客户页标题、标签和生命周期类型名的唯一来源；HTML 模板不得写死行业标签，也不得把内部类型码直接展示给客户。

`report_label_profile` 最低结构：

```json
{
  "label_generation_basis": "基于当前研究对象、effective_products、effective_keywords、effective_reviews 生成",
  "product_title_labels": {
    "B0EXAMPLE": "当前产品对应的中文短名"
  },
  "segment_labels": {
    "raw segment/category text": "当前类目下的中文赛道名"
  },
  "keyword_labels": {
    "raw keyword lower-case": "当前类目下的中文流量标签"
  },
  "traffic_tag_labels": {
    "raw traffic keyword lower-case": "当前类目下的中文入口标签"
  },
  "lifecycle_type_labels": {
    "A": "当前类目下的主产品路径名",
    "B": "当前类目下的升级/套装路径名",
    "C": "当前类目下的配件/补位路径名",
    "D": "当前类目下的维护/复购路径名"
  }
}
```

生成要求：

- `product_title_labels` 不得使用 `未命名竞品`、`竞品记录`、`样本`、旧类目名或模板词。
- `segment_labels` 和 `keyword_labels` 必须来自当前产品语义；例如不能因为旧模板是 lighting，就在 Hunting Blinds、宠物用品、家居收纳等项目里输出照明标签。
- `lifecycle_type_labels` 可以保留内部 A/B/C/D 作为键，但值必须是当前项目可读中文业务名；客户 HTML 只能展示值，不能展示 `Type A/B/C/D`。
- 如果 AI 无法生成可信标签，必须写入 `analysis_plan.limitations` 和 critic 改进项；客户页对应槽位显示中文诊断，不得由模板硬编一个行业词兜底。

推荐额外写入：

```text
reports/{task_id}/analysis/
  cosmo_alexa_tags.json
  lifecycle_strategy.json
  demand_gap.json
```

如果 `cosmo_alexa_tags.json` 或 `lifecycle_strategy.json` 缺失，完整客户报告必须进入诊断或重新生成分析产物；不得静默退回旧模板样例。`demand_gap.json` 缺失时，HTML 渲染器可从 Data Pack 推导基础区块，但必须在 `data_gaps` 或 `analysis_plan.limitations` 标注分析深度不足。

`analysis/cosmo_alexa_tags.json` 必须包含 15 类关系：`USED_FOR_FUNC`、`USED_FOR_EVE`、`USED_FOR_AUD`、`CAPABLE_OF`、`USED_TO`、`USED_AS`、`IS_A`、`USED_ON`、`USED_IN_LOC`、`USED_IN_BODY`、`USED_WITH`、`USED_BY`、`xINTERSTED_IN`、`xIs_A`、`xWANT`。每类必须包含中文标签名、英文 relation type、标签词、证据来源、置信度、覆盖证据数，以及 Listing / QA / 广告动作建议。市场深度 HTML 必须展示“COSMO + Alexa 标签识别 · 产品标签 × 用户标签”板块，包含覆盖矩阵、高置信标签、用户标签与产品标签缺口和建议动作。

`analysis/lifecycle_strategy.json` 必须包含：

```json
{
  "module": "lifecycle_strategy",
  "sku_candidate_pool": [],
  "recommended_skus": [],
  "ecosystem_nodes": [],
  "filter_diagnostics": {
    "effective_products": 0,
    "effective_suppliers": 0,
    "sku_candidate_pool": 0,
    "recommended_skus": 0,
    "filtered_out": []
  },
  "limitations": []
}
```

当有效竞品和供应记录充足时，`sku_candidate_pool` 目标为 30-80 个，图表、表格和筛选控件必须读取候选池而不是 5 个展示卡片。四维生态图必须是“研究对象 -> 四维路径 -> 细分赛道/场景 -> SKU/参考 ASIN”的多层结构；优先级图必须按 SKU 数量自适应，少量 SKU 用紧凑评分卡，多量 SKU 用 Top 榜和完整候选池折叠表。

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
    cosmo_alexa_tags.json
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
- HTML 要有客户可读的证据强度、数据覆盖、数据缺口、置信等级和建议动作；Markdown / JSON 保留完整审计链路。
- HTML 必须统一读取 `report_readiness_view`，只允许出现三种交付状态：`完整可交付`、`诊断交付`、`阻断交付`。入口页、市场页、生命周期页和需求断层页不得各自独立判断供应链、证据强度或最终决策。
- `delivery_result.json.decision` 必须明确为 `Go`、`Watch` 或 `No-Go`，不能为 `null`。当供应链毛利率被阻断但市场/VOC/生命周期仍可阅读时，默认降级为 `Watch`；核心数据污染或产品池/关键词不足时降级为 `No-Go` 或阻断交付。
- 当 `report_readiness_view.supply_blocked=true` 时，所有客户 HTML 必须显示 `供应链测算未达门槛`，证据强度最高只能是 `中 / 诊断交付`，并禁止出现供应链已可控、可打样或毛利率可测算这类矛盾表达。
- 聊天里只给摘要和路径，不粘贴完整报告。

HTML 主体必须使用真实结构化组件：

- 四个 HTML 都必须是 standalone HTML document；`data-report-style` 只允许作为内部模板标记，最终客户 HTML 必须剥离该属性，避免泄露模板/技术标识。
- 三份子报告必须使用 `<section>` 编号章节、KPI cards、CSS mini charts、evidence tables、cards、risk/roadmap/timeline 等结构化组件。
- 竞品、需求、1688、TikTok、Web、SKU、KANO/JTBD 等必须用客户可读的 insight table / card / matrix 表达，不能用 Markdown 表格文本。
- 客户版 HTML 禁止展示 `source_id`、`source_ids`、provider/tool、raw_path/path、Product ID、product_id 或“来源”字段；ASIN 仅允许在竞品狙击和供应链毛利率测算组件中以 `data-allow-asin` 作用域展示，其他位置出现 ASIN 必须视为泄露。
- 能展示的数据要先转成 AI 深度分析后的结论、商业含义和建议动作；原始长表、数据血缘和完整来源细节只保留在 `data_pack.json`、`lineage.md`、`report.md`、`delivery_result.json` 中。
- 评论/VOC 必须先做中文化映射：用户原声展示中文摘要、星级、情绪、主题和需求含义；可并列展示短英文评论摘录，但必须标记 `data-allow-english-review="short"`，完整英文原评、英文标题和抓取字段原值只留在审计文件。
- 市场深度报告的 VOC 证据卡必须固定为左右分栏：左侧 `正面好评`、右侧 `负面差评`，每侧 6 槽，使用 `market-voc-sentiment-columns`、`market-voc-column positive`、`market-voc-column negative` 和 `market-voc-card joy/pain`。不得再用单一 `quote-grid` 把好评和差评混排。
- 市场深度报告的 `COSMO + Alexa 标签识别` 必须使用固定四区块：`cosmo-matrix` 15 类 relation 矩阵、`cosmo-top-list` 高置信标签排行、`cosmo-gap-panel` 产品/用户标签缺口、`cosmo-action-board` Listing / QA / 广告动作。`cosmo-matrix` 内必须再拆成 `product-lane` 和 `user-lane` 两条中文分区：`产品标签 · 产品被算法识别为什么`、`用户标签 · 用户为什么搜索/购买`。矩阵格必须使用客户可读的 `产品意图/用户意图` 与 `产品/用户` 标记，不得把英文 relation code 或 `P01/U09` 槽位编号当成可见标题；不得退回普通小卡片堆叠，也不得为了填满 15 类而把无证据 relation 写成高置信。
- COSMO 标签生成必须是类目通用逻辑：狩猎、灯具、宠物、电子等类目词只能在当前有效竞品、关键词、评论或供应标题明确支持时出现。禁止因为 `outdoor`、`box`、`waterproof` 等泛词，把非狩猎产品误标成 `盲棚`、`猎人`、`隐蔽装备` 等类目专属标签。
- COSMO 客户页不得出现 `USED_*`、`CAPABLE_OF`、`xWANT`、`REL_1` 等内部码；这些只允许留在 `analysis/cosmo_alexa_tags.json` 和审计文件，不能出现在可见文本、隐藏文本或 `data-*` 属性。高/中置信 relation 的词组重复签名和单词过度复用必须让 validator 失败。
- 生命周期 SKU 表默认只展示 Top 8-15 候选，完整候选池放入折叠表或分页表。每个 SKU 必须区分 `供应锚点` 和 `仅竞品/VOC 候选`；客户可见标签必须是当前产品证据生成的中文策略名，不得展示 `Type A/B/C/D`。

推荐生成顺序：

1. 先生成 `data_pack.json` 和 `analysis/*.json`。
2. 标准版/深度版先补齐 1000+ 关键词样本：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir reports/{task_id} --min-keywords 1200
```

3. 标准版/深度版先补齐 1688 去重有效报价 `>=50`。不足 50 时必须多轮切换 Sorftime 1688 搜索词，不得生成最终供应链成本或毛利率结论：

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_1688_suppliers.py --dir reports/{task_id} --min-valid-quotes 50 --max-rounds 5
```

4. 运行数据准备度门禁，失败则停止交付生成并继续采集：

```bash
python skills/amz-market-research-orchestrated/scripts/check_data_readiness.py --dir reports/{task_id} --depth standard --write
```

5. 运行交叉验证 / 去重 / 中文映射：

```bash
python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir reports/{task_id}
```

6. 再运行结构化 HTML 渲染器：

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir reports/{task_id}
```

7. 如需增强视觉，再基于生成的 HTML 做局部编辑，但必须保留所有必备章节、模板结构、关键 class/id 和客户安全约束；不得把 `data-report-style` 等内部模板标识重新带回客户 HTML。

完成后运行：

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/{task_id} --depth standard
```

只有 proof 输出 `overall_pass=true`、`delivery_mode=full_acceptance`、`full_acceptance_pass=true`，且 validator 步骤通过，才能宣称完整市场研究交付完成。若 proof 输出 `overall_pass=false`、`delivery_mode=diagnostic_delivery`、`diagnostic_delivery_pass=true`，只能交付“完整模板诊断报告”：四页模板必须完整，客户页只能展示中文诊断和补采动作，不得宣称完整市场结论或毛利率可测算。单独的 `delivery_result.status=complete` 或 `critic_review.pass=true` 都不是完成证明。

## 报告质量规则

- 写“估算月销量（Sorftime）”，不要写“官方销量”。
- 不把 Amazon `bought in past month`、Sorftime 估算、TikTok sold 混成一个数字。
- 不用 TikTok 热度替代 Amazon 购买需求。
- 不用少量评论写精确百分比；样本小则写频次、主题和代表证据。
- 不在缺成本时写伪利润表；1688 去重有效报价不足 50 条时必须阻断供应链成本和毛利率结论。
- 不因为 TikTok 或 Firecrawl 失败就删除模块；保留模块并说明缺口。1688 报价不足 50 条时保留诊断，但最终供应链成本/毛利率模块必须阻断。
- 所有关键结论必须能在审计文件中追溯到 `source_id`，但客户版 HTML 不展示这些技术标识。
- 所有关键方法必须能追溯到 `method_chain`。
- `output/html_reports/report.html` 必须用同文件夹相对链接打开三份子报告；`output/report.html` 必须作为兼容入口链接到 `html_reports/`。
- 三份子报告必须分别通过模板结构、必备章节、关键 class/id 和结构级 parity validator；客户 HTML 不得展示 `three-report-index-v2`、`market-depth-report-v2`、`lifecycle-strategy-report-v2`、`demand-gap-report-v2`。
- 四个 HTML 都不得出现 `<pre>` 包裹的 Markdown、原始 Markdown 表格、或只靠标题段落撑起来的文章页。
- 输出默认全中文；客户版 HTML 仅保留品牌名、平台名、竞品狙击/毛利率测算所需 ASIN、必要英文专有名词和授权英文评论短摘，Product ID / source_id 等技术标识只留在审计文件。
- 客户版 HTML 不直接展示完整英文评论原文或英文评论标题；必须转成中文摘要、中文主题、情绪标签和建议动作，英文只允许短摘并与中文摘要并列。

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
