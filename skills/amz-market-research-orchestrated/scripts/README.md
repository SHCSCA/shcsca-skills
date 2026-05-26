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
  data/
    data_pack.json
    lineage.md
  analysis/
    analysis_plan.json
  output/
    report.html
    market-depth-report.html
    lifecycle-strategy-report.html
    demand-gap-report.html
    report.md
    delivery_result.json
```

The script prints `validate_ok` on success and `validate_failed: ...` on failure. It also rejects HTML reports that are Markdown wrappers instead of the v2 entry page plus three standalone source-linked reports.

## Tests

```bash
python skills/amz-market-research-orchestrated/scripts/test_collect_sorftime_keywords.py
python skills/amz-market-research-orchestrated/scripts/test_normalize_data_pack.py
python skills/amz-market-research-orchestrated/scripts/test_render_dashboard_html.py
python skills/amz-market-research-orchestrated/scripts/test_validate_market_research_deliverables.py
```

These tests build temporary report directories and verify that Sorftime keyword pagination parsing works, normalization is stable, global keywords stay separate from ASIN traffic terms, the renderer writes `report.html` plus three child reports, and the validator accepts valid artifacts while rejecting broken lineage, missing delivery files, Markdown-wrapped HTML, low keyword sample depth, missing child reports, missing child links, and incomplete report sections.

## collect_sorftime_keywords.py

Collects paginated Sorftime keyword rows before normalization:

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir reports/<task_id> --min-keywords 1200
```

Use this for standard and deep reports. Sorftime returns 20 rows per page, so the script pages through `category_keywords` and `keyword_extends`, saves raw MCP responses to `data/raw/`, and writes `data/normalized/keyword_collection_summary.json`. The validator requires at least 1000 deduped keyword rows in `data_pack.json`.

## normalize_data_pack.py

Cross-validates, dedupes, and enriches `data/data_pack.json`:

```bash
python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir reports/<task_id>
```

It adds `normalization`, `source_ids`, `validation`, Chinese keyword/title fields, keyword relevance labels, and writes `data/normalized/cross_validated_data_pack.json`. It also writes `data/normalized/normalization_baseline.json` on the first run so repeated rendering does not reset raw sample counts.

## render_dashboard_html.py

Renders the v2 HTML bundle from `data/data_pack.json` and optional `analysis/*.json` files using the bundled templates:

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir reports/<task_id>
```

Use it after generating the Data Pack and analysis artifacts, then run the validator. The renderer calls the normalizer before rendering and writes:

```text
output/report.html
output/market-depth-report.html
output/lifecycle-strategy-report.html
output/demand-gap-report.html
```

It also updates `output/delivery_result.json.html_reports`. Optional `analysis/lifecycle_strategy.json` and `analysis/demand_gap.json` enrich the second and third reports; when missing, the renderer derives directional blocks from the Data Pack and the limitations should remain visible in `data_gaps` or `analysis_plan.limitations`.
