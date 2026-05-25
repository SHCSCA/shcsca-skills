# Orchestration Brief Contract

Use this contract as the top-level handoff between the market research controller and the four planes.

## OrchestrationBrief

```json
{
  "task_id": "",
  "created_at": "",
  "research_object": {
    "type": "keyword | asin | brand | category | file | url",
    "value": "",
    "marketplaces": ["Amazon US"],
    "languages": ["en"]
  },
  "task_purpose": {
    "primary": "new_market_entry | product_iteration | segment_discovery | competitor_differentiation | social_voc | supply_profit_validation | executive_report",
    "secondary": [],
    "decision_to_support": "",
    "stage": "idea | validation | launch | scaling | optimization"
  },
  "data_scope": {
    "depth": "quick | standard | deep",
    "platforms": ["amazon", "reddit", "youtube"],
    "budget_mode": "free_first | balanced | quality_first",
    "max_paid_runs": 8,
    "max_items": 800
  },
  "method_scope": {
    "preferred_methods": [],
    "excluded_methods": [],
    "confidence_requirement": "directional | decision_grade"
  },
  "output_scope": {
    "audience": "self | founder | product | marketing | boss | client | investor",
    "formats": ["html"],
    "targets": ["local_file"],
    "style": {
      "language_profile": "zh_cn_localized",
      "tone_profile": "seasoned_direct_plainspoken",
      "visual_profile": "rational_aesthetics_html",
      "document_profile": "structured_decision_doc",
      "custom_notes": ""
    },
    "save_as_default": false
  }
}
```

## Derived DataNeed

The data source plane receives a DataNeed derived from the brief. Include purpose context so the data layer can prioritize sources without doing business analysis:

```json
{
  "task_id": "",
  "requester_skill": "amz-market-research-orchestrated",
  "purpose_context": {
    "primary": "product_iteration",
    "needed_decision": "rank product improvements"
  },
  "research_object": {},
  "depth": "standard",
  "data_needs": []
}
```

## Derived AnalysisBrief

The methodology plane receives:

```json
{
  "task_id": "",
  "research_object": {},
  "task_purpose": {},
  "data_pack_path": "",
  "available_entities": [],
  "constraints": {},
  "output_need": {}
}
```

## Derived OutputBrief

The output plane receives:

```json
{
  "task_id": "",
  "research_object": "",
  "audience": "",
  "artifacts": {},
  "delivery": {},
  "style": {},
  "preference": {}
}
```
