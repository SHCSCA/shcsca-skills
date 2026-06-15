# scripts

Command-line helpers for `amz-market-research-orchestrated`.

## validate_market_research_deliverables.py

Validates a generated report directory:

```bash
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/<task_id>
```

Expected report shape:

```text
reports/<task_id>/
  report_brief.json
  data/
    data_pack.json
    normalized/
      normalized_data_pack.json
      data_readiness_report.json
    lineage.md
  analysis/
    analysis_plan.json
    critic_review.json
    refinement_plan.json
    critic_summary.md
  output/
    report.html                  # compatibility entry, links into html_reports/
    html_reports/
      report.html                # portable bundle entry
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

The script prints `validate_ok` on success and `validate_failed: ...` on failure. It also rejects HTML reports that are Markdown wrappers, expose technical audit identifiers, expose ASIN values outside approved benchmark/profitability scopes, copy full raw English reviews, or render 1688 profitability conclusions before the 50 valid quote gate passes.

## collect_sorftime_1688_suppliers.py

Collects 1688 supplier quotes with multi-round, paged Sorftime `ali1688_similar_product(searchName,page)` searches. It derives Chinese search seeds from Amazon competitors and keywords, retries up to five seed rounds, dedupes quote identities, and writes `supplier_1688_collection_summary.json`. The collector treats 50 quotes as a quantity floor only: title coverage, identity coverage, documented response fields, and price-spread gates must also pass.

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_1688_suppliers.py --dir reports/<task_id> --min-valid-quotes 50 --max-rounds 5 --max-pages 3 --force-rounds
```

## collect_sorftime_products.py

Collects Amazon competitor products into `data_pack.products`. It uses Amazon product-search schemas only, records raw MCP responses under `data/raw/`, and maps returned rows into the readiness fields: ASIN, title, brand, price, rating, review count, sales or rank proxy, and segment.

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_products.py --dir reports/<task_id> --min-products 30 --max-seeds 8 --max-pages 3 --site US --min-segments 3 --min-per-segment 10
```

## collect_sorftime_product_enrichment.py

Enriches existing Amazon ASINs after the competitor pool exists. It calls `product_detail`, `product_trend`, `product_variations`, `product_traffic_terms`, and `competitor_product_keywords` across multiple ASINs. Returned traffic and competitor keywords are written into `data_pack.keywords`; product detail/trend/variation rows are attached under each product's `sorftime_enrichment`. Empty dimensions are preserved in `product_enrichment_collection_summary.json` and one current `data_gaps` entry with `retry_evidence.asins_attempted`, not stacked across repeated runs.

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_product_enrichment.py --dir reports/<task_id> --max-products 10 --max-pages 1 --site US
```

## audit_sorftime_mcp_contracts.py

Audits Sorftime MCP schemas and actual returned fields for Amazon, TikTok, and 1688 using a real report's ASINs, keywords, and TikTok product IDs. Use this when official documentation and runtime responses appear inconsistent.

```bash
python skills/amz-market-research-orchestrated/scripts/audit_sorftime_mcp_contracts.py --dir reports/<task_id> --platform all
```

## collect_sorftime_tiktok_signals.py

Collects TikTok Shop product, trend, video, and creator signals with Sorftime's documented schemas. Similar-product and creator search use `searchName/page/site`; product detail, trend, video, and creator chain calls use `productId/site`, with `page` only for video lists.

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_tiktok_signals.py --dir reports/<task_id> --site US --max-seeds 4 --max-pages 1 --max-products-detail 3 --video-pages 1
```

## Tests

```bash
python skills/amz-market-research-orchestrated/scripts/test_html_components.py
python skills/amz-market-research-orchestrated/scripts/test_customer_copy.py
python skills/amz-market-research-orchestrated/scripts/test_customer_safety.py
python skills/amz-market-research-orchestrated/scripts/test_view_model_builder.py
python skills/amz-market-research-orchestrated/scripts/test_delivery_writer.py
python skills/amz-market-research-orchestrated/scripts/test_report_renderers.py
python skills/amz-market-research-orchestrated/scripts/test_critic_runner.py
python skills/amz-market-research-orchestrated/scripts/test_site_assets.py
python skills/amz-market-research-orchestrated/scripts/test_site_interactions.py
python skills/amz-market-research-orchestrated/scripts/test_check_data_readiness.py
python skills/amz-market-research-orchestrated/scripts/test_collect_sorftime_keywords.py
python skills/amz-market-research-orchestrated/scripts/test_collect_sorftime_reviews.py
python skills/amz-market-research-orchestrated/scripts/test_collect_sorftime_1688_suppliers.py
python skills/amz-market-research-orchestrated/scripts/test_collect_sorftime_tiktok_signals.py
python skills/amz-market-research-orchestrated/scripts/test_normalize_data_pack.py
python skills/amz-market-research-orchestrated/scripts/test_render_dashboard_html.py
python skills/amz-market-research-orchestrated/scripts/test_child_skill_split.py
python skills/amz-market-research-orchestrated/scripts/test_validate_market_research_deliverables.py
python skills/amz-market-research-orchestrated/scripts/test_run_acceptance_proof.py
```

These tests build temporary report directories and verify that Sorftime keyword/review collection parsing works, normalization is stable, global keywords stay separate from ASIN traffic terms, canonical URL/title/store dedupe works, customer copy and customer safety redaction stay intact, critic refinement records failed and passing rounds, the three child skills exist under the orchestrated skill, the renderer writes the portable static site bundle plus a compatibility entry, shared CSS/JS assets are local, `report.js` behaviors execute against a minimal DOM including image-load fallback, and the validator accepts valid artifacts while rejecting broken lineage, missing delivery files, missing static assets, Markdown-wrapped HTML, low keyword sample depth, missing child reports, broken child links, non-portable bundle links, customer HTML leaks, and incomplete report sections.

The shared site assets intentionally borrow the local downloaded report templates as visual baselines: `downloadpage/143101` for market depth, `downloadpage/143511` for lifecycle strategy, and `downloadpage/143645` for demand gap. The generator extracts reusable CSS/JS patterns into local `report.css` and `report.js`; it does not ship `_next` chunks, CDN URLs, iframe shells, or hard-coded sample report data.

## validate_template_parity_contract.py

Checks that the three downloaded HTML baselines, `template-baseline-manifest.json`, `html-template-parity-checklist.md`, shared CSS/JS, and report templates agree on required layout and interaction signals:

```bash
python skills/amz-market-research-orchestrated/scripts/validate_template_parity_contract.py
```

Use `--require-downloads` on the user's machine when auditing against the actual downloaded folders:

```bash
python skills/amz-market-research-orchestrated/scripts/validate_template_parity_contract.py --require-downloads
```

`run_acceptance_proof.py` runs this contract first. If template parity fails, the proof stops before readiness/render/validator.

For local strict template review, run acceptance proof with the downloaded reference templates enabled:

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<task_id> --depth deep --reference-visual --download-root C:\Users\wz\Downloads\downloadpage
```

This adds a `reference_visual_compare` step after final validation and records `output/template_reference_visual_compare/template_reference_visual_compare.json` in `output/acceptance_proof.json`.

## run_visual_parity_audit.py

Runs a real browser screenshot audit against an already rendered report directory:

```bash
python skills/amz-market-research-orchestrated/scripts/run_visual_parity_audit.py --dir reports/<task_id>
```

The audit opens `output/html_reports/report.html` plus the three child reports in desktop and mobile viewports, verifies core selectors, text density, table/section density, horizontal overflow, and nonblank screenshots. It writes:

```text
output/visual_parity_audit/visual_parity_audit.json
output/visual_parity_audit/visual_parity_audit.md
output/visual_parity_audit/*.png
```

This is the screenshot-level evidence layer for the template parity checklist. It still does not replace human visual review for final brand/design approval.

## run_template_reference_visual_compare.py

Compares an already rendered report directory against the three downloaded reference HTML folders on the user's machine:

```bash
python skills/amz-market-research-orchestrated/scripts/run_template_reference_visual_compare.py --dir reports/<task_id> --download-root C:\Users\wz\Downloads\downloadpage
```

The script opens both the downloaded reference HTML and generated customer HTML at PC `1366x900` and `1440x900`, captures paired screenshots, and checks:

- required generated template selectors are present;
- selectors that exist in the reference template are also represented in the generated report;
- screenshot byte ratio stays within `0.45-2.20`;
- downsampled screenshot `pixelDistance` stays within `0.16`;
- body background matches the reference page;
- generated section count remains within the reference-compatible floor;
- key component bounding boxes stay within `0.82-1.18` width ratio, `<=110px` left delta, and `<=110px` center delta;
- rendered pages have no horizontal overflow and produce nonblank screenshots.

It writes:

```text
output/template_reference_visual_compare/template_reference_visual_compare.json
output/template_reference_visual_compare/template_reference_visual_compare.md
output/template_reference_visual_compare/*-reference.png
output/template_reference_visual_compare/*-generated.png
```

Use this as the local reference-template evidence layer when reviewing whether the generated reports still follow the provided downloaded HTML templates.

## check_data_readiness.py

Checks whether a Data Pack is ready to enter standard/deep report generation:

```bash
python skills/amz-market-research-orchestrated/scripts/check_data_readiness.py --dir reports/<task_id> --depth standard --write
```

The script reads `data/normalized/normalized_data_pack.json` when present, otherwise `data/data_pack.json`, and writes `data/normalized/data_readiness_report.json` with `acceptance_ready`, `sample_class`, `blocking_gaps`, `warnings`, entity counts, and collector commands. Standard/deep runs are blocked when source lineage is empty, Amazon competitor depth is below 30/60, broad terms are not split into 3 primary segments with 10 competitors each, keyword samples are below 1000, or 1688 quote quality/spread gates fail. Review, Web, and TikTok gaps remain warnings so the report can degrade honestly when the final validator still accepts the structure and the limitations are visible. Review recommendations are 80 samples for standard reports and 200 samples for deep reports.

## recover_data_readiness.py

Runs targeted recovery before final diagnostics. It checks readiness, maps failed modules to the relevant Sorftime collectors, normalizes after each round, writes `data/normalized/readiness_recovery_report.json`, and returns `0` only when final readiness passes.

```bash
python skills/amz-market-research-orchestrated/scripts/recover_data_readiness.py --dir reports/<task_id> --depth standard --max-rounds 2
```

`render_dashboard_html.py` calls this by default before writing a diagnostic HTML. If recovery leaves only supplier quote depth, supplier quote quality, or supplier price-spread blockers, the renderer writes a `partial` delivery: market/VOC/lifecycle analysis continues, while the 1688 gross-margin conclusion is disabled and replaced by a diagnostic panel. Use `--no-recover` only for negative tests or when you intentionally want to inspect the immediate gate result.

When `sample_class=non_acceptance_sample`, keep the directory only as historical/demo evidence. Do not render or claim a completed client deliverable from it, even if older delivery or critic files contain `status=complete` or `pass=true`.

Final bundles must carry the same readiness state in three places: `data/normalized/data_readiness_report.json`, `output/delivery_result.json.data_readiness`, and `output/html_reports/assets/report-data.json.readiness`. The validator recomputes readiness and rejects stale or forged summaries.

Exit codes:

- `0`: ready for the next step.
- `1`: unreadable or invalid Data Pack.
- `2`: valid Data Pack but not ready for standard/deep report generation.

## Rendering module boundaries

`render_dashboard_html.py` is the orchestration entrypoint. It loads/normalizes data, runs readiness recovery when needed, runs critic refinement, calls the report document builder, applies final customer HTML redaction, and writes the delivery bundle.

Supporting modules keep the renderer small and auditable:

- `html_components.py`: pure formatting and HTML atoms.
- `customer_copy.py`: customer-facing Chinese summaries, theme labels, and product positioning copy.
- `customer_safety.py`: client-safe redaction for HTML and JSON payloads.
- `view_model_builder.py`: customer-safe view models and `report-data.json` payloads.
- `report_renderers.py`: pure document assembly for the index, compatibility index, and three child reports.
- `delivery_writer.py`: `lineage.md`, `report_brief.json`, and `delivery_result.json` writers.
- `critic_runner.py`: asynchronous-style critic/refinement artifacts, operator-facing `critic_summary.md`, and failed-case logging.
- `site_assets.py`: shared CSS, JS, asset paths, declared interactive features, and template-baseline selectors from the three downloaded HTML report references.

## collect_sorftime_keywords.py

Collects paginated Sorftime keyword rows before normalization:

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir reports/<task_id> --min-keywords 1200
```

Use this for standard and deep reports. Sorftime returns 20 rows per page, so the script pages through `category_keywords` and `keyword_extends`, saves raw MCP responses to `data/raw/`, and writes `data/normalized/keyword_collection_summary.json`. The validator requires at least 1000 deduped keyword rows in `data_pack.json`.

The default `--max-pages` is 75 so a single seed can theoretically collect up to 1500 raw rows before dedupe. If no nodeId or seed keyword is available, the script writes a `keyword_collection_no_seed` gap and returns exit code `2`; it does not call MCP just to fail on environment configuration. `keyword_collection_summary.json` includes `collection_ready`, `planned_calls`, `theoretical_row_capacity`, and `warnings`.

## collect_sorftime_reviews.py

Collects Sorftime review rows after ASIN/product sampling:

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_reviews.py --dir reports/<task_id> --review-type Both --min-reviews 80
```

The script infers ASINs from `--asin`, `research_object.seed_asins`, then top products. If no ASIN is available, it writes a `review_collection_no_asin` gap and returns exit code `2` without calling MCP. `review_collection_summary.json` includes `reviews_total`, `reviews_added`, `min_reviews`, `collection_ready`, `asin_count`, and `failures`. Standard reports should use `--min-reviews 80`; deep reports should use `--min-reviews 200` when VOC is a major decision input.

## normalize_data_pack.py

Cross-validates, dedupes, and enriches `data/data_pack.json`:

```bash
python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir reports/<task_id>
```

It adds `normalization`, `cleaning_summary`, `source_ids`, `validation`, canonical URLs, Chinese keyword/title fields, keyword relevance labels, and Chinese review fields (`title_cn`, `summary_cn`, `themes_cn`), then writes `data/normalized/normalized_data_pack.json` and `data/normalized/cross_validated_data_pack.json`. It also writes `data/normalized/normalization_baseline.json` on the first run so repeated rendering does not reset raw sample counts.

## render_dashboard_html.py

Renders the v2 HTML bundle from `data/data_pack.json` and optional `analysis/*.json` files using the bundled templates:

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir reports/<task_id>
```

Use it after generating the Data Pack and analysis artifacts, then run the validator. The renderer calls the normalizer before rendering and writes:

```text
output/report.html
output/html_reports/report.html
output/html_reports/market-depth-report.html
output/html_reports/lifecycle-strategy-report.html
output/html_reports/demand-gap-report.html
output/html_reports/assets/report.css
output/html_reports/assets/report.js
output/html_reports/assets/report-data.json
```

`output/html_reports/` is the portable static site folder: move or download that folder as a unit and its `report.html` will link to the three child reports and shared assets with same-folder relative links. `output/report.html` is retained as a compatibility entry that links into `html_reports/`.

The renderer also updates `output/delivery_result.json.html_reports`, `html_bundle_dir`, `child_skills`, `site_assets`, `interactive_features`, and `cleaning_summary`. Optional `analysis/lifecycle_strategy.json` and `analysis/demand_gap.json` enrich the second and third reports; when missing, the renderer derives directional blocks from the Data Pack and the limitations should remain visible in `data_gaps` or `analysis_plan.limitations`.

Customer HTML is Chinese-facing by default. Raw English reviews and English review titles remain in `data_pack.json` for audit, while HTML uses Chinese summaries, themes, sentiment labels, and suggested actions. Amazon competitor images may be rendered when Sorftime returns Amazon image URLs; every image tag must include customer-visible load fallback so local `file://` reports do not show broken-image icons when remote media is blocked or slow. Supplier-side 1688 images must never be used as Amazon competitor images.

Local sample classifications are tracked in `references/sample-coverage-matrix.md`. Use that matrix to distinguish accepted samples, negative readiness samples, and unit-test demo samples.

## run_acceptance_proof.py

Runs the operator-facing proof bundle:

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<task_id> --depth standard
```

It runs readiness, render, and final validation, then writes:

```text
output/acceptance_proof.json
output/acceptance_proof.md
```

Use this as the preferred proof command when deciding whether a local sample is a complete or diagnostic delivery. The proof separates:

- `full_acceptance_pass=true`: readiness, renderer, validator, critic, and optional reference visual checks passed with `acceptance_ready=true`.
- `diagnostic_delivery_pass=true`: readiness still has a supported partial blocker such as supplier quote relevance, but `partial_report_ready=true`, the renderer suppresses blocked conclusions, and validator/critic/reference visual checks pass.
- `delivery_mode=blocked`: core readiness, validator, critic, or template checks failed. Blocked samples return non-zero and still write proof output explaining the failed step.

## prototypes

`../prototypes/client-html-style-preview.html` is a static style preview for the client-facing report language. Treat it as a visual reference for spacing, palette, cards, and customer-readable wording; it is not a generated report artifact and should not be copied as final evidence.
