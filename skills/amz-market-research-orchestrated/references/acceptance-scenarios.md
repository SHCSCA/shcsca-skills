# Acceptance Scenarios

Use these scenarios when checking whether `amz-market-research-orchestrated` v2 was followed correctly on a real research run.

## Scenario 1: New Market Entry

Input:

```text
调研 ai plush toy 在 Amazon US 是否值得做，按标准版输出 HTML + Markdown + Data Pack。
```

Required evidence:

- `OrchestrationBrief.task_purpose.primary = new_market_entry`
- Amazon keyword, product pool, competitor, review, and trend evidence from Sorftime
- Standard/deep runs collect at least 1000 deduped keyword rows after normalization
- TikTok similar product or explicit TikTok data gap
- 1688 similar product or explicit supply data gap
- Firecrawl public sources for reports, brand/review/policy evidence
- `normalization.deduped = true` with raw, deduped, removed, and cross-validated counts
- Opportunity matrix and Go / Watch / No-Go

## Scenario 2: Product Iteration

Input:

```text
围绕一个指定 ASIN 做产品迭代，找差评痛点、功能机会和 Listing 改进方向。
```

Required evidence:

- `OrchestrationBrief.research_object.type = asin`
- Sorftime `product_detail`, `product_trend`, `product_reviews`, `product_variations`, and `product_traffic_terms`
- Review/VOC module maps complaint themes to product changes
- Competitor benchmark is used when related ASINs or keyword results are available
- Global keywords and ASIN reverse traffic terms are not collapsed into one analytical row
- Report avoids precise percentages when review sample is small

## Scenario 3: Missing Data Degradation

Input:

```text
按标准版调研一个品类，但 TikTok 或 1688 没有返回可用数据。
```

Required evidence:

- `data_pack.json` keeps `tiktok_products`, `tiktok_videos`, or `suppliers` as empty arrays
- `data_gaps` explains the missing module, cause, confidence impact, and next action
- Report keeps TikTok or 1688 section instead of deleting it
- Final decision confidence is reduced when the missing module affects the purpose
- `validate_market_research_deliverables.py` still passes if lineage and required files are intact

## Scenario 4: Three-Part Executive HTML Bundle

Input:

```text
调研一个 Amazon US 品类，输出老板/客户能看的 HTML 报告。
```

Required evidence:

- `output/html_reports/report.html` uses `data-report-style="three-report-index-v2"` and links to all three child reports with same-folder relative links
- `output/report.html` uses `data-report-style="three-report-index-v2"` and links into `html_reports/`
- `output/html_reports/market-depth-report.html` uses `data-report-style="market-depth-report-v2"`
- `output/html_reports/lifecycle-strategy-report.html` uses `data-report-style="lifecycle-strategy-report-v2"`
- `output/html_reports/demand-gap-report.html` uses `data-report-style="demand-gap-report-v2"`
- HTML files are designed reports, not Markdown wrappers
- Entry page contains report title, market, depth, data quality, data gaps, and Go / Watch / No-Go
- Market report modules remain visible: 大盘仪表盘、关键词需求、Top 竞品、VOC 痛点/爽点、标杆竞品深挖、机会判断、TikTok 验证、1688 供应链、Web 风险、数据血缘
- Lifecycle report modules remain visible: 战略仪表盘、用户画像、生命周期旅程、四维拓品生态、SKU 执行总表、Bundle 策略、30/60/90 天路线图、风险矩阵、市场数据验证
- Demand-gap report modules remain visible: 目标 ASIN/研究对象锚点、决策看板、$APPEALS 痛点全景、满意度鸿沟、KANO × JTBD 机会矩阵、用户原声、需求优先级与证据表
- Competitor, keyword, supplier, TikTok, web, SKU, KANO/JTBD, appendix, and lineage evidence are rendered as HTML tables
- Keyword tables include `关键词中文`, `英文关键词`, `相关性`, `中文意图`, and `source_id`
- Full keyword appendix shows at least 1000 deduped keyword samples for standard/deep reports
- Competitor tables include `中文定位` and `英文标题`
- Data coverage visibly shows cross-validation and dedupe counts
- ASIN deep dives show image if available, traffic terms, trend, variation samples, and source IDs
- VOC includes theme chart, star distribution, quote cards, and review evidence table
- Full appendix exposes renderable Data Pack entity groups with `<details>` blocks in the market report
- Important conclusions cite `source_id` in visible content
- Core content works offline without CDN

## Universal Gate

Every real run must pass:

```bash
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/{task_id}
```

Passing the validator does not prove the business conclusion is correct; it proves the report is structurally auditable.

For HTML, passing the validator also proves the bundle is not a raw Markdown shell, contains the required three-report modules, and meets the 1000-keyword minimum for standard/deep reports.
