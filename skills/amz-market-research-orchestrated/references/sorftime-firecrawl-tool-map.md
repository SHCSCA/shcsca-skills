# Sorftime + Firecrawl Tool Map

This file defines the v1 data-source map for `amz-market-research-orchestrated`.

Do not store MCP keys in this repository. Use the MCP tools already configured in the runtime, or ask the user to configure Sorftime / Firecrawl only when the tools are unavailable.

## Provider Roles

| Provider | Role | Notes |
|---|---|---|
| Sorftime MCP | Primary ecommerce data source | Amazon, TikTok Shop, 1688, and optional Walmart data. |
| Firecrawl MCP | Public web evidence and fallback | Reports, brand sites, review media, policy pages, recalls, public retailer pages. |
| User files | Optional supplemental evidence | Cost sheets, supplier quotes, internal ads data, exported reviews. |

## Amazon Tools

| Need | Preferred Sorftime tool | Required when |
|---|---|---|
| Product idea / keyword entry | `keyword_detail`, `keyword_extends`, `keyword_search_results`, `product_search` | Keyword or product idea input. |
| Product / ASIN entry | `product_detail`, `product_trend`, `product_reviews`, `product_variations`, `product_traffic_terms` | ASIN input or competitor deep dive. |
| Category entry | `category_name_search`, `category_report`, `category_trend`, `category_keywords` | User names a category or asks for Top100 / market scan. |
| Competitor traffic | `competitor_product_keywords`, `product_ranking_trend_by_keyword` | Competitor differentiation or traffic analysis. |
| Historical product pool | `product_search_from_history`, `category_report_from_history`, `keyword_list_from_history` | Deep or time-windowed research. |

For standard/deep keyword depth, page `category_keywords` and `keyword_extends` with `scripts/collect_sorftime_keywords.py`. Sorftime returns 20 rows per page; the normalized Data Pack must keep at least 1000 keyword rows.

## TikTok Shop Tools

| Need | Preferred Sorftime tool | Required when |
|---|---|---|
| Find TikTok category | `tiktok_category_name_search`, `tiktok_category_report` | Full-domain or TikTok validation. |
| Find similar products | `tiktok_similar_product` | Standard and deep reports when product idea is consumer-facing. |
| Product detail | `tiktok_product_detail`, `tiktok_product_trend` | TikTok product IDs are found. |
| Video and creator evidence | `tiktok_product_video`, `tiktok_product_video_author`, `tiktok_author` | Deep reports and content/channel strategy. |

## 1688 Tool

| Need | Preferred Sorftime tool | Required when |
|---|---|---|
| Supplier and cost proxy | `ali1688_similar_product` | Standard/deep reports and supply/profit validation. |

Use 1688 data as a cost and supply maturity proxy. Do not treat listed supplier prices as landed cost.

## Optional Walmart Tools

| Need | Preferred Sorftime tool |
|---|---|
| Retail channel comparison | `walmart_keyword_search_results`, `walmart_product_detail_by_product_id`, `walmart_product_trend_by_product_id`, `walmart_category_report_by_node_id` |

Walmart is optional in v1. Use it when the category is strongly mass-retail driven or when Amazon evidence is ambiguous.

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
