# Acceptance Scenarios

Use these scenarios when checking whether `amz-market-research-orchestrated` v1 was followed correctly on a real research run.

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

## Scenario 4: Executive HTML Report

Input:

```text
调研一个 Amazon US 品类，输出老板/客户能看的 HTML 报告。
```

Required evidence:

- `report.html` uses `data-report-style="strategic-dashboard-v1"`
- HTML is a designed dashboard, not a Markdown wrapper
- First viewport contains report title, market, depth, data quality, and Go / Watch / No-Go
- Required modules remain visible: 数据覆盖、市场大盘、关键词需求、Top 竞品、竞品深挖、Review / VOC、TikTok 验证、1688 供应链、Web / 风险补充、机会矩阵、数据缺口、完整数据附录、数据血缘
- Competitor, keyword, supplier, TikTok, web, appendix, and lineage evidence are rendered as HTML tables
- Keyword tables include `关键词中文`, `英文关键词`, `相关性`, `中文意图`, and `source_id`
- Full keyword appendix shows at least 1000 deduped keyword samples for standard/deep reports
- Competitor tables include `中文定位` and `英文标题`
- Data coverage visibly shows cross-validation and dedupe counts
- ASIN deep dives show image if available, traffic terms, trend, variation samples, and source IDs
- VOC includes theme chart, star distribution, quote cards, and review evidence table
- Full appendix exposes all renderable Data Pack entity groups with `<details>` blocks
- Important conclusions cite `source_id` in visible content
- Core content works offline without CDN

## Universal Gate

Every real run must pass:

```bash
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/{task_id}
```

Passing the validator does not prove the business conclusion is correct; it proves the report is structurally auditable.

For HTML, passing the validator also proves the file is not a raw Markdown shell, contains the required dashboard modules, and meets the 1000-keyword minimum for standard/deep reports.
