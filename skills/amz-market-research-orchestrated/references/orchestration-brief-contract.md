# Orchestration Brief Contract v1

The brief is the top-level contract for one market research run. It is generated after the agent parses the user's intent and confirms only the missing high-impact details.

## OrchestrationBrief

```json
{
  "task_id": "ai_plush_us_20260526",
  "created_at": "2026-05-26T10:30:00+08:00",
  "research_object": {
    "type": "keyword | asin | brand | category | file | url | product_idea",
    "value": "ai plush toy",
    "seed_asins": [],
    "seed_keywords": [],
    "user_files": []
  },
  "task_purpose": {
    "primary": "new_market_entry | product_iteration | segment_discovery | competitor_differentiation | social_voc | supply_profit_validation | executive_report",
    "secondary": [],
    "decision_to_support": "判断是否进入并选择切入点",
    "stage": "idea | validation | launch | scaling | optimization"
  },
  "market_scope": {
    "amazon_site": "US",
    "tiktok_site": "US",
    "supply_market": "CN_1688",
    "language": ["en", "zh-CN"]
  },
  "data_scope": {
    "depth": "quick | standard | deep",
    "platforms": ["amazon", "tiktok_shop", "1688", "web"],
    "amazon_product_pool_target": 100,
    "review_sample_per_core_asin": 100,
    "firecrawl_source_target": 8,
    "include_walmart": false
  },
  "output_scope": {
    "audience": "self | founder | product | marketing | boss | client | investor",
    "formats": ["html", "markdown", "json_data_pack"],
    "targets": ["local_file"],
    "style": {
      "language_profile": "zh_cn_localized",
      "tone_profile": "seasoned_direct_plainspoken",
      "visual_profile": "rational_aesthetics_html",
      "document_profile": "structured_decision_doc",
      "custom_notes": ""
    }
  },
  "constraints": {
    "target_price_band": "",
    "forbidden_categories": [],
    "known_competitors": [],
    "known_supplier_costs": [],
    "must_include": [],
    "must_exclude": []
  }
}
```

## Depth Defaults

| Depth | Amazon | TikTok | 1688 | Firecrawl |
|---|---|---|---|---|
| `quick` | Keyword detail, search result/product pool 20-50, core ASIN detail/reviews | Optional | Optional | 3-5 public sources |
| `standard` | Top100 or near-Top100, keyword trend/extensions/search results, details/trends/variations/reviews/traffic terms | Similar products and trends | Similar products and cost proxy | Reports, brand sites, review/policy sources |
| `deep` | Standard plus multi-keyword dedupe and competitor tiers | Product detail, trend, videos, creators | Cost band and copyability read | Broader source set and stronger limitations |

## Derived Run Plan

The agent turns the brief into a run plan:

```json
{
  "task_id": "",
  "mcp_calls": [
    {
      "provider": "sorftime",
      "tool": "product_search",
      "arguments": {},
      "required": true,
      "raw_path": "reports/task/data/raw/sorftime_product_search_keyword.json"
    }
  ],
  "normalization_targets": ["products", "keywords", "reviews"],
  "analysis_modules": ["market_size", "competitors", "voc", "opportunity", "profitability"],
  "output_artifacts": ["report.html", "report.md", "data_pack.json", "analysis_plan.json", "lineage.md", "delivery_result.json"]
}
```

The run plan is not a public artifact requirement, but it is useful for explaining and auditing the agent's execution.
