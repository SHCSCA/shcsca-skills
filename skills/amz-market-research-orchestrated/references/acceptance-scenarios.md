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
- `report_readiness_view.status` is `诊断交付` or `阻断交付` when the missing module blocks a core conclusion
- If `valid_supplier_quotes < 50` or supplier field quality fails, all reports show `供应链测算未达门槛`, profit/margin conclusions are blocked, and customer HTML does not contain `供应链可控度较高`, `50+ 可打样`, or `毛利率可测算`
- `delivery_result.json.decision` is explicitly `Watch` or `No-Go`, never `null`
- `validate_market_research_deliverables.py` passes only when the diagnostic state, lineage, required files, and customer-safe wording are intact

This degradation scenario does not apply to empty source lineage, empty product samples, or keyword depth below 1000 in standard/deep runs. Those are readiness blockers and must produce `non_acceptance_sample` rather than a completed client report.

## Scenario 4: Three-Part Executive HTML Bundle

Input:

```text
调研一个 Amazon US 品类，输出老板/客户能看的 HTML 报告。
```

Required evidence:

- `output/html_reports/report.html` links to all three child reports with same-folder relative links and does not expose internal template markers.
- `output/report.html` links into `html_reports/` and does not expose internal template markers.
- All four files in `output/html_reports/` include the shared top navigation and work with local `assets/report.css`, `assets/report.js`, and `assets/echarts.min.js`.
- `output/html_reports/market-depth-report.html` passes required section, canonical class/id, and structure-level parity checks.
- `output/html_reports/lifecycle-strategy-report.html` passes required section, canonical class/id, and structure-level parity checks.
- `output/html_reports/demand-gap-report.html` passes required section, canonical class/id, and structure-level parity checks.
- `analysis/cosmo_alexa_tags.json` exists, contains all 15 COSMO + Alexa relation types, and the market-depth report renders the `COSMO + Alexa 标签识别` section as four zones: `cosmo-matrix`, `cosmo-top-list`, `cosmo-gap-panel`, and `cosmo-action-board`.
- `analysis/lifecycle_strategy.json` exists, contains `sku_candidate_pool`, `recommended_skus`, `ecosystem_nodes`, and `filter_diagnostics`, and lifecycle charts/tables read from the candidate pool instead of fixed fallback SKU examples.
- `report_readiness_view` exists in the rendered data payload, all HTML pages use the same `完整可交付 / 诊断交付 / 阻断交付` state, and supply-chain blocking language is consistent across entry, market, lifecycle, and demand reports.
- HTML files are designed reports, not Markdown wrappers
- Entry page contains report title, market, depth, data quality, data gaps, and Go / Watch / No-Go
- Market report modules remain visible: 大盘结论、COSMO + Alexa 标签识别、需求结构、竞品格局、VOC 洞察、标杆打法、机会定义、TikTok 内容信号、1688 供应链判断、风险与行动摘要
- Lifecycle report modules remain visible: 战略仪表盘、用户画像、生命周期旅程、四维拓品生态、拓品方案池、Bundle 策略、30/60/90 天路线图、风险矩阵、市场验证摘要
- Demand-gap report modules remain visible: 目标ASIN锚点、决策看板、需求主题痛点图、满意度鸿沟、KANO × JTBD、用户原声、需求优先级
- Competitor, demand, supplier, TikTok, web, SKU, and KANO/JTBD evidence are rendered as customer-readable insight tables
- Customer HTML includes `证据强度`, `数据覆盖`, `数据缺口`, and `建议动作`
- Customer HTML does not display `source_id`, provider/tool names, raw paths, Product IDs, or source tables; ASIN appears only in the target anchor, benchmark sniper, competitor table, profit model, SKU reference, or demand anchor scope.
- `data/normalized/data_readiness_report.json` is present with `acceptance_ready=true`
- `analysis/critic_summary.md` is present and states readiness, critic score, final decision, unresolved findings, and failed-critic delivery guardrail
- Data Pack still contains at least 1000 deduped keyword samples for standard/deep reports
- Competitor and VOC tables use Chinese-facing positioning, review summaries, themes, sentiment, and recommended actions rather than raw English titles/comments
- Data coverage visibly shows cross-validation and dedupe counts
- Lifecycle customer HTML must not show `未命名竞品`, unrelated category labels such as `户外感应灯` in non-lighting research, raw `Type A/B/C/D` labels, or old fallback SKU names.
- Lifecycle SKU table defaults to Top 8-15 rows and moves the full candidate pool into a collapsed drawer/table; rows distinguish `供应锚点` from `仅竞品/VOC 候选`.
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
