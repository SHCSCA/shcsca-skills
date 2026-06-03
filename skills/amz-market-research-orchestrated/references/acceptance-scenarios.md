# Acceptance Scenarios

Use these scenarios when checking whether `amz-market-research-orchestrated` v2 was followed correctly on a real research run.

For local sample classification, use [sample-coverage-matrix.md](sample-coverage-matrix.md). Only `acceptance_sample` directories may be used as delivery proof.

## Scenario 1: New Market Entry

Input:

```text
调研 ai plush toy 在 Amazon US 是否值得做，按标准版输出 HTML + Markdown + Data Pack。
```

Required evidence:

- `OrchestrationBrief.task_purpose.primary = new_market_entry`
- Amazon keyword, product pool, competitor, review, and trend evidence from Sorftime
- Standard/deep runs collect at least 1000 deduped keyword rows after normalization
- `check_data_readiness.py --write` produces `acceptance_ready=true` and `sample_class=acceptance_sample`
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

This degradation scenario does not apply to empty source lineage, empty product samples, or keyword depth below 1000 in standard/deep runs. Those are readiness blockers and must produce `non_acceptance_sample` rather than a completed client report.

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
- Market report modules remain visible: 大盘结论、需求结构、竞品格局、VOC 洞察、标杆打法、机会定义、TikTok 内容信号、1688 供应链判断、风险与行动摘要
- Lifecycle report modules remain visible: 战略仪表盘、用户画像、生命周期旅程、四维拓品生态、拓品方案池、Bundle 策略、30/60/90 天路线图、风险矩阵、市场验证摘要
- Demand-gap report modules remain visible: 研究对象概述、决策看板、$APPEALS 痛点图、满意度鸿沟、KANO × JTBD、用户原声、需求优先级
- Competitor, demand, supplier, TikTok, web, SKU, and KANO/JTBD evidence are rendered as customer-readable insight tables
- Customer HTML includes `证据强度`, `样本覆盖`, `数据缺口`, and `建议动作`
- Customer HTML does not display `source_id`, provider/tool names, raw paths, Product IDs, ASIN values, or source tables
- `data/normalized/data_readiness_report.json` is present with `acceptance_ready=true`
- `analysis/critic_summary.md` is present and states readiness, critic score, final decision, unresolved findings, and failed-critic delivery guardrail
- Data Pack still contains at least 1000 deduped keyword samples for standard/deep reports
- Competitor and VOC tables use Chinese-facing positioning, review summaries, themes, sentiment, and recommended actions rather than raw English titles/comments
- Data coverage visibly shows cross-validation and dedupe counts
- Competitor deep dives show image if available, positioning, trend, unmet need, and suggested action without exposing technical IDs
- VOC includes theme chart, star distribution, quote cards, and review evidence table
- Full source appendix stays in JSON/Markdown audit artifacts, not client HTML
- Important conclusions are traceable to `source_id` in audit artifacts, not visible HTML
- Core content works offline without CDN

## Universal Gate

Every real run must pass:

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/{task_id} --depth standard
```

Passing the proof command does not prove the business conclusion is correct; it proves readiness, render, critic delivery state, customer safety, and final validation are structurally auditable.

For HTML, passing the proof also proves the template parity contract is intact, the bundle is not a raw Markdown shell, contains the required three-report modules, passes data readiness, and meets the 1000-keyword minimum for standard/deep reports.

Historical directories that fail readiness may remain in the repository or local reports folder only as `non_acceptance_sample` evidence. They must not be used to claim delivery completion, even if older `delivery_result.json` or `critic_review.json` files contain `complete` or `pass=true`.
