# Critic Contract

`amz-market-research-critic` reviews the semantic reliability of the three market research reports.

## Hard Boundaries

- Input facts come from `data/normalized/normalized_data_pack.json`.
- Customer-facing language comes from the three `analysis/*_view.json` files and report HTML.
- The critic can request refinement but cannot alter facts, remove data gaps, or create unsupported evidence.
- `validate_market_research_deliverables.py` remains the final hard gate.

## Failure Classes

| Class | Meaning |
|---|---|
| `evidence_depth` | Sample size or source coverage is too thin for the conclusion. |
| `decision_consistency` | Score, grade, and Go/Watch/No-Go do not match data quality. |
| `report_contradiction` | Child reports make incompatible claims. |
| `client_safety` | Customer assets expose technical identifiers or raw private evidence. |
| `missing_component` | Required section, component, or interaction is declared but absent. |

## Minimum Review Checks

- Compare review counts and cross-validation counts to final decision strength.
- Check that `status=partial` is reflected in confidence wording.
- Check that every major opportunity has supporting evidence or an explicit data gap.
- Check that no child report silently upgrades AI inference into measured fact.
- Check that missing metrics become customer-readable limitations.
- Check that ASIN values appear only in approved benchmark/profitability scopes and that English review text appears only as short excerpts paired with Chinese summaries.
- Check that supply-chain cost and gross-margin conclusions are blocked unless `supplier_quote_gate.passed=true` with at least 50 deduped valid 1688 quotes.
