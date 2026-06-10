# Analysis Module Contracts v2

Analysis modules consume the normalized `data_pack.json` fields and return structured findings. They must not call MCP tools directly; data access happens before analysis.

## Common Input

```json
{
  "task_id": "",
  "module": "amazon_competitor",
  "method_ids": ["competitor.price_value_matrix", "competitor.review_gap"],
  "data_pack_path": "reports/task/data/data_pack.json",
  "allowed_entities": ["products", "reviews", "keywords"],
  "question": "What competitor weaknesses create an opportunity?",
  "output_path": "reports/task/analysis/competitors.json"
}
```

Before any module runs, `data_pack.json` must have:

- `normalization.deduped = true`
- stable `before_counts`, `after_counts`, `removed_counts`, and `cross_validated_counts`
- at least 1000 deduped keyword rows for standard/deep reports
- keyword Chinese mapping fields: `keyword_cn`, `intent_cn`, `relevance_cn`
- product Chinese mapping fields: `title_cn`, `segment_cn`, `positioning_cn`
- `source_ids` and `validation` on deduped entities where cross-source evidence exists

## Common Output

```json
{
  "module": "amazon_competitor",
  "method_ids": [],
  "status": "complete | partial | blocked",
  "used_source_ids": ["src_001"],
  "findings": [],
  "tables": [],
  "charts": [],
  "evidence": [],
  "confidence": "high | medium | low",
  "limitations": []
}
```

Every module output must include `used_source_ids`. If a module is blocked or partial, it must include a limitation and the missing evidence.

Module outputs should also expose report-ready blocks for the v2 HTML bundle:

- `kpis`: short label/value/subtext cards.
- `tables`: evidence rows with source IDs.
- `cards`: opportunities, VOC clusters, risks, or competitor layers.
- `charts`: simple series that can be rendered as CSS/SVG or kept as tables offline.
- `html_report_hint`: one of `market_depth`, `lifecycle_strategy`, or `demand_gap`.
- `html_section_hint`: the target section id from `html-report-design-contract.md`.

## Required v2 Modules

| Module | Consumes | Returns |
|---|---|---|
| `market_size` | `categories`, `keywords`, `products`, `web_documents` | Market size proxy, demand trend, price bands, concentration, seasonality, confidence. |
| `keyword_demand` | `keywords`, `products` | Core terms, extensions, natural search competitors, search intent, Chinese keyword mapping, relevance/noise split, content/listing implications. |
| `amazon_competitors` | `products`, `reviews`, `keywords`, `categories` | Top competitor matrix, price/rating/review/sales estimates, feature map, listing promises, gaps. |
| `voc` | `reviews`, `web_documents`, `tiktok_videos` | Complaint clusters, positive motives, objections, emotional language, sample limitations. |
| `tiktok_validation` | `tiktok_products`, `tiktok_videos` | Similar-product heat, trend, content hooks, creator/channel evidence, Amazon relevance limits. |
| `supply_chain` | `suppliers`, `products` | 1688 cost proxy, MOQ/copyability signal, target landed-cost ceiling, supply risks. |
| `opportunity` | All module outputs | Opportunity matrix, recommended wedge, target segment, experiments, Go/Watch/No-Go. |
| `lifecycle_strategy` | `products`, `keywords`, `reviews`, `suppliers`, `tiktok_products`, `opportunity` | User personas, lifecycle journey, SKU table, bundle strategy, 30/60/90 roadmap, supply-chain risks. |
| `demand_gap` | `reviews`, `keywords`, `products`, `web_documents`, `tiktok_videos` | Demand-theme pain map, satisfaction gaps, KANO × JTBD matrix, user quotes, demand priority table. |

## HTML Section Mapping

| HTML report | HTML section | Primary module | Required visual block |
|---|---|---|---|
| `market_depth` | `market-dashboard` | `market_size` | KPI cards + price/volume/concentration chart or table. |
| `market_depth` | `keyword-demand` | `keyword_demand` | Keyword evidence table + intent cards. |
| `market_depth` | `competitor-landscape` | `amazon_competitors` | Top competitor table + segment cards. |
| `market_depth` | `voc` | `voc` | Pain/joy cards + theme frequency table. |
| `market_depth` | `tiktok-validation` | `tiktok_validation` | Product/video table + relevance limitation card. |
| `market_depth` | `supply-chain` | `supply_chain` | Supplier table + cost threshold cards. |
| `market_depth` | `opportunity` | `opportunity` | Opportunity cards + enter/stop conditions. |
| `market_depth` | `lineage` | All sources | Source appendix table. |
| `lifecycle_strategy` | `strategy-dashboard` | `lifecycle_strategy` | SKU count, self-supply count, repeat-purchase signal. |
| `lifecycle_strategy` | `personas` | `lifecycle_strategy`, `voc` | Persona cards + evidence table. |
| `lifecycle_strategy` | `lifecycle-journey` | `lifecycle_strategy` | Timeline + stage table. |
| `lifecycle_strategy` | `sku-table` | `lifecycle_strategy`, `supply_chain` | SKU execution table with source IDs. |
| `lifecycle_strategy` | `bundle-strategy` | `lifecycle_strategy` | Bundle cards + AOV table. |
| `demand_gap` | `appeals-map` | `demand_gap`, `voc` | Demand-theme chart/table. |
| `demand_gap` | `gap-analysis` | `demand_gap` | Gap table or CSS radar substitute. |
| `demand_gap` | `kano-jtbd` | `demand_gap` | KANO × JTBD matrix. |
| `demand_gap` | `voice-theater` | `reviews` | Quote cards + review table. |

## Guardrails

- Do not treat Sorftime monthly sales estimates as official Amazon sales.
- Do not treat TikTok sold counts or video engagement as Amazon purchase validation.
- Do not write precise percentages from small review samples.
- Do not recommend an opportunity supported by only one weak source unless labeled speculative.
- Do not rank keyword opportunities until high-relevance terms are separated from adjacent/noisy category terms and ASIN traffic terms.
- Do not write a P&L without landed cost, FBA fees, return rate, referral fee, and ad cost. Use threshold models instead.
- Do not invent lifecycle SKU economics when supply evidence is missing; use directional price bands and mark the gap.
- Do not treat demand-gap findings as proven demand unless tied to reviews, keywords, or multiple public sources.

## Analysis Plan

`analysis_plan.json` must contain:

```json
{
  "task_id": "",
  "research_object": "",
  "primary_purpose": "",
  "secondary_purposes": [],
  "method_chain": [
    {
      "method_id": "market.top100_competitor_scan",
      "name": "Top100 竞品扫描",
      "used_source_ids": ["src_001"],
      "output": "价格/评分/月销估算/评论/卖点矩阵"
    }
  ],
  "confidence": {},
  "limitations": []
}
```

The validator requires `method_chain`, `confidence`, and `limitations`.

## Optional Module Artifact Shapes

`analysis/lifecycle_strategy.json`:

```json
{
  "module": "lifecycle_strategy",
  "used_source_ids": ["src_001"],
  "personas": [],
  "skus": [],
  "bundles": [],
  "roadmap": [],
  "risks": [],
  "limitations": []
}
```

`analysis/demand_gap.json`:

```json
{
  "module": "demand_gap",
  "used_source_ids": ["src_001"],
  "appeals": [],
  "gaps": [],
  "opportunities": [],
  "quotes": [],
  "limitations": []
}
```

If these files are absent, the renderer may derive default report blocks from Data Pack evidence, but the report must remain visibly source-linked and must not hide the limitation.
