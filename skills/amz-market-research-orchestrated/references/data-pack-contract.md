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

The normalizer writes `data/normalized/normalized_data_pack.json` as the master read-only handoff for child report skills, writes `data/normalized/cross_validated_data_pack.json` for backward compatibility, and mutates `data/data_pack.json` with deduped, enriched entities.

For standard and deep research runs, keyword depth is a hard delivery gate:

- collect at least 1200 raw keyword rows before normalization when possible,
- keep at least 1000 deduped keyword rows in `data_pack.keywords`,
- save the paginated collection summary to `data/normalized/keyword_collection_summary.json`.

Before child report generation, run the readiness gate:

```bash
python skills/amz-market-research-orchestrated/scripts/check_data_readiness.py --dir reports/{task_id} --depth standard --write
```

The generated `data/normalized/data_readiness_report.json` must have:

- `acceptance_ready = true`,
- `sample_class = acceptance_sample`,
- no `blocking_gaps`.

Standard/deep runs are `non_acceptance_sample` when source lineage is empty, deduped keyword samples are below 1000, Amazon valid competitor depth is below 30/60, or broad market terms are not split into at least three primary segments with ten competitors each after recovery attempts. When only 1688 supplier quote depth, field quality, or price-spread gates fail after recovery, the run is `partial_acceptance_sample`: customer-facing market, lifecycle, and demand analysis may be delivered, but supply-chain gross-margin conclusions must be disabled and replaced by a diagnostic panel. Do not use AI-generated placeholder entities, copied template rows, or duplicated rows to satisfy sample counts.

Review depth is a confidence gate rather than a structural blocker:

- standard reports should target at least 80 review samples,
- deep reports should target at least 200 review samples,
- below those targets, VOC sections must avoid precise percentages and the quality score must remain capped.

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
| `reviews` | `source_ids`, `validation`, `title_cn`, `summary_cn`, `themes_cn` |
| `tiktok_products`, `tiktok_videos`, `suppliers`, `web_documents` | `source_ids`, `validation` |

Keyword dedupe must not collapse global demand and ASIN traffic into one row:

- global keyword rows: dedupe by normalized English keyword,
- ASIN traffic rows: dedupe by `asin + normalized English keyword`.

HTML should display global demand in the main keyword table, adjacent/noisy terms in a separate table, and ASIN traffic terms in an ASIN traffic foldout.

Client HTML renders Chinese review summary first. It may also display a short English review excerpt when the element is marked `data-allow-english-review="short"` and paired with `summary_cn`, `title_cn`, `themes_cn`, sentiment, and suggested actions. Full raw English review text and English review titles remain audit-only.

1688 supplier data is delivery-blocking for standard/deep supply and profitability sections:

- Run multi-round, paged Sorftime `ali1688_similar_product(searchName,page)` collection until there are at least 50 deduped valid quotes or all configured rounds are exhausted.
- A valid supplier quote has title, supplier/shop, positive RMB price, and canonical URL/product ID/title+shop identity.
- Deduplicate suppliers by canonical URL, product ID, or title + store before counting the 50-quote gate.
- The 50-quote gate is only a quantity floor. Title coverage and URL/product-ID/stable identity coverage must each be at least 70%.
- `supplier_1688_collection_summary.json` must include `documented_field_coverage` for the official 16 fields (`Title`, `Photo`, `URL`, `Price`, `ProductId`, `StoreName`, `ServiceScore`, `ServiceScoreDetail`, `OnlineDate`, `SalesOf30d`, `WholesalePriceRange`, `RepurchaseRate`, `ShippingOrigin`, `ReviewCount`, `Score`, `SkuCount`). Treat `Url`/`url` as aliases of `URL`.
- If the active MCP response omits documented product-title or product-URL fields (`Title`, `URL`), preserve the raw response and fail the supplier field-quality gate instead of inventing customer-facing supplier titles or profitability conclusions.
- Price distribution must be sane enough for cost modeling: `max/P50 > 20` or `P75/P25 > 5` fails the global spread gate. If a same-search-term `seed_keyword` bucket has at least 50 valid quotes and passes field/spread gates, the supply module may use only that bucket and must record the global spread problem as a warning. If no same-search bucket passes, block gross-margin conclusions.
- `data_readiness_report.json`, `delivery_result.json`, and `report-data.json` must expose `supplier_quote_gate` and `supplier_quality_gate`.
- Customer HTML must not render final 1688 cost or gross-margin conclusions when either supplier gate fails.

Amazon competitor data is delivery-blocking for standard/deep market and profitability sections:

- Standard reports require at least 30 deduped valid competitors; deep reports require at least 60.
- Each valid competitor must have ASIN, title, brand, price, rating, review count, sales or ranking proxy, and segment.
- Amazon competitor collectors must preserve product image URLs when the MCP response provides them. Normalize documented/common image fields such as `Photo`, `photo`, `image`, `Image`, `image_url`, `ImageUrl`, `imageUrl`, `main_image`, `mainImage`, `main_image_url`, `MainImage`, `thumbnail`, `thumbnail_url`, and `Thumbnail` into `products[].image_url`; write image URL coverage into `product_collection_summary.json`.
- Broad terms such as `smart lighting`, `lighting`, and `智能照明` must split into primary segments before analysis. At least three primary segments must each carry ten valid competitors.
- Gross-margin tables must use real competitor ASIN prices as price-band anchors; brand averages and mixed-category averages cannot substitute for ASIN-backed prices.
- Amazon and TikTok output-field coverage is verified from actual MCP result rows, not from `tools/list` input schemas. Zero-row ASIN/productId/category dimensions must be retried with alternate valid samples and recorded as data gaps only after retry evidence exists.
- If `data_gaps[].type == amazon_product_enrichment_empty_dimensions`, it must include `retry_evidence` with multiple attempted ASINs, `empty_dimensions`, `successful_dimensions`, and per-tool `tool_stats`. A generic "returned no rows" message without retry evidence is invalid.

## Cleaning Boundary

Global cleaning belongs to `amz-market-research-orchestrated`:

- products: ASIN first, then normalized title fingerprint when ASIN is missing,
- keywords: global market terms and ASIN traffic terms remain separate buckets,
- reviews: ASIN + date + title + body fingerprint,
- suppliers: canonical URL, product ID, or title + store,
- web documents: canonical URL with query strings and fragments removed.
- data_gaps: dedupe by `module/type + gap/reason` so repeated recovery or collector runs do not stack duplicate customer/audit blockers.

Child report skills may do display-layer grouping, sorting, bucketing, and truncation, but they must not overwrite the global dedupe result or create a competing data pack.

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

The HTML bundle is validated against `html-report-design-contract.md`: `output/html_reports/report.html` must be the portable `three-report-index-v2` entry page with same-folder child links, `output/report.html` must remain a compatibility entry into `html_reports/`, and the three child reports must include semantic sections, client-readable insight tables, evidence strength language, and their required report modules. Raw `source_id` values stay in JSON/Markdown audit artifacts, not client HTML.
