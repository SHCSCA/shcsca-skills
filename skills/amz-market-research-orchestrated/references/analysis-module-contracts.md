# Analysis Module Contracts

Each analysis module consumes Data Pack fields and returns structured findings. Modules must not call raw data APIs directly.

In the four-plane architecture, this file is the legacy module contract. For method-chain selection, prefer `market-method-orchestrator/references/analysis-plan-contract.md` and `market-method-orchestrator/references/methodology-library.md`. Keep this file for compatibility with existing report modules.

## Common Input

```json
{
  "task_id": "",
  "module": "amazon_competitor",
  "method_ids": ["competitor.feature_benchmark", "competitor.review_gap"],
  "data_pack_path": "reports/task/data/data_pack.json",
  "allowed_entities": ["products", "reviews"],
  "question": "What competitor weaknesses create a product opportunity?",
  "output_path": "reports/task/analysis/amazon_competitors.json"
}
```

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

## Market Size Module

Consumes:

- `categories`
- `keywords`
- `products`
- trend fields from Sorftime, Keepa, or web reports

Returns:

- Market size and trend estimate.
- Price-band opportunity.
- Concentration and maturity.
- Seasonality and growth signals.
- Confidence by metric.

Do not:

- Treat third-party estimates as official platform sales.
- Merge category-level and keyword-level markets without explaining the difference.

## Amazon Competitor Module

Consumes:

- `products`
- `reviews` where `platform=amazon`
- keyword/search result entities
- Keepa historical fields when available

Returns:

- Top competitor table.
- Price/rating/review/sales matrix.
- Listing promise and feature map.
- Common complaint clusters.
- Defensible gaps and imitation risks.

Do not:

- Fabricate ASIN links.
- Use title-only data for deep product claims when details are missing.

## Social VOC Module

Consumes:

- `social_posts`
- `videos`
- `reviews` where `platform in [reddit, youtube, tiktok]`
- transcripts when available

Returns:

- Use cases.
- Complaints and objections.
- Desired outcomes.
- Emotional vocabulary.
- Content and creator signals.

Do not:

- Treat viral content as purchase validation without marketplace evidence.
- Quote user comments without URL or platform context.

## Opportunity Module

Consumes:

- Market module output.
- Amazon competitor module output.
- Social VOC module output.

Returns:

- Opportunity matrix.
- Differentiation pillars.
- Product wedge.
- Validation experiments.

Do not:

- Recommend opportunities that only appear in one weak source unless labeled speculative.

## Profitability and Supply Chain Module

Consumes:

- product prices and estimated sales.
- Keepa price/offer history.
- supplier listings from 1688, Jimu, or user files.
- user-provided cost assumptions.

Returns:

- Target price band.
- Cost ceiling.
- Contribution pool.
- Risk gates.
- Go / Watch / No-Go finance view.

Do not:

- Write a fake P&L when FBA fees, landed cost, return rate, or ad cost are unknown.
Use threshold models instead.
