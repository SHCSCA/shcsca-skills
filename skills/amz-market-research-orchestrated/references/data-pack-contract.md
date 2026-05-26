# Data Pack Contract

`data_pack.json` is the audit layer for the v2 market research skill. The final report bundle is only trusted when its key claims can be traced back to this file.

## Required Top-Level Shape

```json
{
  "task_id": "",
  "created_at": "",
  "research_object": {},
  "scope": {},
  "sources": [],
  "products": [],
  "keywords": [],
  "categories": [],
  "reviews": [],
  "tiktok_products": [],
  "tiktok_videos": [],
  "suppliers": [],
  "web_documents": [],
  "data_gaps": [],
  "quality": {},
  "normalization": {}
}
```

## Source Object

Every data-producing call or user file becomes a source object.

```json
{
  "source_id": "src_001",
  "provider": "sorftime | firecrawl | user_file | ai_inference",
  "tool": "product_search",
  "query": {},
  "raw_path": "reports/task/data/raw/sorftime_product_search_ai_plush.json",
  "fetched_at": "2026-05-26T10:30:00+08:00",
  "confidence": "high | medium | low",
  "limitation": ""
}
```

Rules:

- `source_id`, `provider`, `fetched_at`, and `confidence` are required.
- `raw_path` is required for Sorftime, Firecrawl, and user-file sources whenever raw data is saved locally.
- `ai_inference` sources are allowed only for clearly labeled derived judgments.

## Entity Rules

Every non-empty entity object must contain:

- `source_id`
- `provider`
- A platform key such as `asin`, `keyword`, `node_id`, `product_id`, `video_id`, `url`, or `supplier_name`

If a module has no data, keep the array empty and add a `data_gaps` entry explaining:

- which module failed,
- why it failed,
- how it affects confidence,
- what should be done next.

After first assembly, run:

```bash
python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir reports/{task_id}
```

The normalizer writes `data/normalized/cross_validated_data_pack.json` and mutates `data/data_pack.json` with deduped, enriched entities.

For standard and deep research runs, keyword depth is a hard delivery gate:

- collect at least 1200 raw keyword rows before normalization when possible,
- keep at least 1000 deduped keyword rows in `data_pack.keywords`,
- save the paginated collection summary to `data/normalized/keyword_collection_summary.json`.

## Normalization Object

```json
{
  "deduped": true,
  "normalized_at": "2026-05-26T00:00:00Z",
  "before_counts": {},
  "after_counts": {},
  "removed_counts": {},
  "cross_validated_counts": {},
  "rules": []
}
```

Rules:

- `before_counts` is based on the first unnormalized Data Pack and is preserved in `data/normalized/normalization_baseline.json`.
- Re-running the renderer or normalizer must not reset original sample counts.
- `cross_validated_counts` counts entities with at least two `source_ids`.
- Reports must show raw count, deduped count, removed count, and cross-validated count.
- `after_counts.keywords` must be at least 1000 for standard/deep reports.

## Minimum Entity Meanings

| Entity | Meaning |
|---|---|
| `products` | Amazon products, competitor pool, Top100 rows, product details, variations, traffic terms. |
| `keywords` | Keyword detail, trend, extensions, natural search result evidence. |
| `categories` | Category search, category report, category trend, category keywords. |
| `reviews` | Amazon review samples and derived review clusters. |
| `tiktok_products` | TikTok Shop similar products, product detail, product trend. |
| `tiktok_videos` | TikTok product videos, creators, content performance. |
| `suppliers` | 1688 supplier and cost proxy records. |
| `web_documents` | Firecrawl pages: reports, brand pages, review media, policy, recalls, retailer pages. |

## Enriched Fields

The normalizer adds the fields below when possible:

| Entity | Added fields |
|---|---|
| `products` | `source_ids`, `validation`, `title_cn`, `segment_cn`, `positioning_cn` |
| `keywords` | `source_ids`, `validation`, `keyword_cn`, `intent_cn`, `relevance_cn`, `is_core_relevant`, `recommended_use_cn` |
| `reviews` | `source_ids`, `validation`, `themes_cn` |
| `tiktok_products`, `tiktok_videos`, `suppliers`, `web_documents` | `source_ids`, `validation` |

Keyword dedupe must not collapse global demand and ASIN traffic into one row:

- global keyword rows: dedupe by normalized English keyword,
- ASIN traffic rows: dedupe by `asin + normalized English keyword`.

HTML should display global demand in the main keyword table, adjacent/noisy terms in a separate table, and ASIN traffic terms in an ASIN traffic foldout.

## Quality Object

```json
{
  "overall_score": 0.0,
  "grade": "directional | directional_decision | decision_grade",
  "coverage": {
    "amazon": "complete | partial | missing",
    "reviews": "complete | partial | missing",
    "tiktok": "complete | partial | missing",
    "supply": "complete | partial | missing",
    "web": "complete | partial | missing"
  },
  "notes": []
}
```

Quality guidance:

- `decision_grade`: Amazon product pool, keyword evidence, review evidence, trend evidence, and supply evidence are all present.
- `directional_decision`: Most core evidence exists, but one major module is partial.
- `directional`: Good for early screening only; key modules are missing or shallow.

## Validation

Run:

```bash
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/{task_id}
```

The validator checks:

- required output files,
- required Data Pack keys,
- source IDs and provider lineage,
- normalization, dedupe, and cross-validation metadata,
- method-chain source references,
- report quality phrases,
- standalone v2 HTML bundle shape,
- `delivery_result.json`.

The HTML bundle is validated against `html-report-design-contract.md`: `report.html` must be the `three-report-index-v2` entry page, and the three child reports must include semantic sections, HTML evidence tables, visible source IDs, and their required report modules.
