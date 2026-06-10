# Sorftime + Firecrawl Tool Map

This file defines the v2 data-source map for `amz-market-research-orchestrated`.

Do not store MCP keys in this repository. Use the MCP tools already configured in the runtime, or ask the user to configure Sorftime / Firecrawl only when the tools are unavailable.

## Provider Roles

| Provider | Role | Notes |
|---|---|---|
| Sorftime MCP | Primary ecommerce data source | Amazon, TikTok Shop, 1688, and optional Walmart data. |
| Firecrawl MCP | Public web evidence and fallback | Reports, brand sites, review media, policy pages, recalls, public retailer pages. |
| User files | Optional supplemental evidence | Cost sheets, supplier quotes, internal ads data, exported reviews. |

Runtime rule: use the Sorftime and Firecrawl MCP tools already configured in the active agent environment. Do not write API keys or MCP server URLs into this repository. If Firecrawl is unavailable in the runtime, keep `web_documents` empty and write a `data_gaps` entry instead of dropping the Web/risk section.

## Amazon Tools

| Need | Preferred Sorftime tool | Required when |
|---|---|---|
| Product idea / keyword entry | `keyword_detail`, `keyword_extends`, `keyword_search_results`, `product_search` | Keyword or product idea input. |
| Product / ASIN entry | `product_detail`, `product_trend`, `product_reviews`, `product_variations`, `product_traffic_terms` | ASIN input or competitor deep dive. |
| Category entry | `category_name_search`, `category_report`, `category_trend`, `category_keywords` | User names a category or asks for Top100 / market scan. |
| Competitor traffic | `competitor_product_keywords`, `product_ranking_trend_by_keyword` | Competitor differentiation or traffic analysis. |
| Historical product pool | `product_search_from_history`, `category_report_from_history`, `keyword_list_from_history` | Deep or time-windowed research. |

For standard/deep keyword depth, page `category_keywords` and `keyword_extends` with `scripts/collect_sorftime_keywords.py`. Sorftime returns 20 rows per page; the normalized Data Pack must keep at least 1000 keyword rows.

For standard/deep competitor depth, run `scripts/collect_sorftime_products.py`. Amazon product collection is separate from TikTok and 1688 collection: it may call `product_search` or `keyword_search_results` with Amazon site arguments, but it must not send TikTok `productId/site` or 1688 `searchName`-only assumptions to Amazon tools.

Amazon `tools/list` schemas only verify accepted input parameters. They do not prove which output fields will be returned for a given ASIN/category/keyword. When a Sorftime Amazon dimension succeeds but returns zero rows, retry against other valid ASINs or category/product-name samples before treating the dimension as unavailable. Record row counts, actual fields, and empty dimensions in `product_enrichment_collection_summary.json` and `sorftime_mcp_contract_audit.json`.

## TikTok Shop Tools

| Need | Preferred Sorftime tool | Required when |
|---|---|---|
| Find TikTok category | `tiktok_category_name_search`, `tiktok_category_report` | Full-domain or TikTok validation. |
| Find similar products | `tiktok_similar_product` | Standard and deep reports when product idea is consumer-facing. |
| Product detail | `tiktok_product_detail`, `tiktok_product_trend` | TikTok product IDs are found. |
| Video and creator evidence | `tiktok_product_video`, `tiktok_product_video_author`, `tiktok_author` | Deep reports and content/channel strategy. |

Use `scripts/collect_sorftime_tiktok_signals.py` for standard/deep runs. Current Sorftime MCP schemas:

- `tiktok_similar_product`: `searchName`, optional `page`, optional `site`.
- `tiktok_author`: `searchName`, optional `page`, optional `site`.
- `tiktok_product_detail`: `productId`, optional `site`.
- `tiktok_product_trend`: `productId`, optional `site`.
- `tiktok_product_video`: `productId`, optional `page`, optional `site`.
- `tiktok_product_video_author`: `productId`, optional `site`.
- `tiktok_category_name_search`: `searchName`, optional `site`.
- `tiktok_category_report`: `nodeId`, optional `site`.

Do not use `keyword` for TikTok search calls, and do not use `product_id` when the MCP schema requires `productId`.
TikTok `site` follows the TikTok schema enum, not the Amazon `amzSite` enum: `Unknow`, `US`, `MY`, `PH`, `VN`, `TH`, `ID`, `GB`, `JP`.

TikTok output fields are also audited by actual `tools/call` rows, not by `tools/list` alone. If `tiktok_author`, `tiktok_product_video`, or creator/video dimensions return zero rows for one product or keyword, retry with another productId/searchName from the collected TikTok product pool. Only after those retries can the report mark a TikTok creator/content dimension as a data gap.

For v2 three-report output, TikTok evidence feeds both `market-depth-report.html` and `demand-gap-report.html`: treat it as content/channel and scene evidence, not Amazon purchase proof.

## 1688 Tool

| Need | Preferred Sorftime tool | Required when |
|---|---|---|
| Supplier and cost proxy | `ali1688_similar_product` | Standard/deep reports and supply/profit validation. |

Official Sorftime MCP docs for `ali1688_similar_product` require `searchName` and `page`. Do not send Amazon-style `keyword`, `amzSite`, or TikTok `site` arguments to 1688. Some runtime `tools/list` schemas may omit `page`; the collector must still call the documented `searchName,page` contract and record actual response fields.

The documented 1688 response has 16 fields: `Title`, `Photo`, `URL`, `Price`, `ProductId`, `StoreName`, `ServiceScore`, `ServiceScoreDetail`, `OnlineDate`, `SalesOf30d`, `WholesalePriceRange`, `RepurchaseRate`, `ShippingOrigin`, `ReviewCount`, `Score`, `SkuCount`. Treat `Url`/`url` as aliases of the documented `URL` field. The collector must write `documented_field_coverage` into `supplier_1688_collection_summary.json`; if coverage is incomplete, the supply-chain module must explain the missing fields and block gross-margin conclusions.

1688 quality has two layers. Global mixed-category prices may fail the spread gate (`max/P50 > 20` or `P75/P25 > 5`). This does not automatically block the report if a same-search-term bucket has at least 50 valid quotes, field coverage passes, and price spread passes. In that case the report may use only the passing bucket for supply-chain and gross-margin calculations, while writing the global spread issue as a warning and keeping the mixed data in audit files.

Use 1688 data as a cost and supply maturity proxy. Do not treat listed supplier prices as landed cost. In v2, `ali1688_similar_product` also feeds the lifecycle report's SKU supply-chain and risk sections.

## Optional Walmart Tools

| Need | Preferred Sorftime tool |
|---|---|
| Retail channel comparison | `walmart_keyword_search_results`, `walmart_product_detail_by_product_id`, `walmart_product_trend_by_product_id`, `walmart_category_report_by_node_id` |

Walmart is optional in v2. Use it when the category is strongly mass-retail driven or when Amazon evidence is ambiguous.

## Firecrawl Tools

| Need | Preferred Firecrawl tool |
|---|---|
| Open-ended source discovery | `firecrawl_search` |
| Known page extraction | `firecrawl_scrape` |
| Structured extraction from multiple URLs | `firecrawl_extract` |
| Site URL discovery | `firecrawl_map` |
| Multi-page crawl | `firecrawl_crawl` |

Firecrawl outputs must be normalized into `web_documents`. They must not bypass `data_pack.json`.

## Raw File Naming

Use deterministic filenames:

```text
data/raw/{provider}_{tool}_{slug}_{yyyymmdd_hhmmss}.json
```

Examples:

```text
data/raw/sorftime_product_search_ai_plush_20260526_103000.json
data/raw/sorftime_tiktok_similar_product_ai_plush_20260526_103500.json
data/raw/firecrawl_search_ai_plush_reports_20260526_104000.json
```

## Source ID Rules

- Assign monotonically increasing IDs: `src_001`, `src_002`, `src_003`.
- One raw MCP/tool response can be one source.
- Derived entities must retain the source ID of the raw response.
- If one conclusion combines multiple sources, cite all source IDs in `analysis_plan.method_chain[].used_source_ids`.
