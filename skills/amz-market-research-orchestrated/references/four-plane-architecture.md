# Four-Plane Architecture v2

The original architecture separated market research into four planes. v2 keeps the language, but ships a self-contained implementation path instead of depending on missing external orchestrator skills.

## 1. Data Source Plane

Built into this skill for v2.

Primary providers:

- Sorftime MCP for Amazon, TikTok Shop, 1688, and optional Walmart data.
- Firecrawl MCP for public web evidence and fallback pages.
- User files for cost sheets, exported reviews, supplier quotes, and internal context.

Responsibilities:

- Convert `OrchestrationBrief` into concrete MCP calls.
- Save raw MCP responses under `data/raw/`.
- Normalize outputs into `data_pack.json`.
- Record lineage, confidence, failures, and fallback behavior.

## 2. Methodology Plane

Built into this skill for v2.

Responsibilities:

- Select a method chain based on purpose and available data.
- Produce `analysis_plan.json`.
- Track `used_source_ids`, confidence, limitations, and data gaps.

Example chains:

- New market entry: category/keyword/product pool -> trend -> concentration -> price-value matrix -> VOC -> supply gate -> Go/Watch/No-Go.
- Product iteration: product detail -> reviews -> variations -> traffic terms -> competitor benchmark -> Kano/RICE-style priority.
- Segment discovery: product pool -> review/VOC clusters -> TikTok scenes -> price bands -> opportunity matrix.

## 3. Task Purpose Plane

Owner: `amz-market-research-orchestrated`.

Responsibilities:

- Clarify the user's real decision.
- Keep one primary purpose and at most two secondary purposes.
- Translate purpose into data depth and method chain requirements.
- Prevent reports from becoming broad but shallow.

## 4. Output Plane

Built into this skill for v2.

Responsibilities:

- Generate `report.html`, `report.md`, `data_pack.json`, `analysis_plan.json`, `lineage.md`, and `delivery_result.json`.
- Preserve data lineage, quality score, method chain, limitations, and next validation actions.
- Run `validate_market_research_deliverables.py`.

Does not:

- Write directly to Feishu, Notion, Obsidian, or other knowledge bases in v2.
- Hide missing data for presentation polish.

## v2 Flow

```text
User request
  -> Parse/confirm purpose, market, depth, output
  -> OrchestrationBrief
  -> Sorftime MCP raw data
  -> Firecrawl public evidence
  -> Data Pack normalization
  -> Analysis Plan and module outputs
  -> HTML/Markdown/Data Pack delivery
  -> Validation script
  -> Chat summary with paths and Go/Watch/No-Go
```

## Expansion Rules

- Add a new provider by updating `sorftime-firecrawl-tool-map.md` and Data Pack normalization rules.
- Add a new analysis module by updating `analysis-module-contracts.md` and the report module list.
- Add a new output target by adding a delivery contract; do not remove local HTML/Markdown/Data Pack.
- Keep `source_id` lineage mandatory for every new module.
