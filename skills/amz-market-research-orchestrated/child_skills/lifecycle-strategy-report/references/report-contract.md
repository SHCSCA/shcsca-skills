# Lifecycle Strategy Report Contract

`child_skills/lifecycle-strategy-report` is an internal module of `amz-market-research-orchestrated` and consumes the normalized master data pack as read-only input.

The orchestrator should also provide `analysis/lifecycle_strategy_view.json`. This view model is the child report's preferred client-safe input and must include `kpis`, `charts`, `tables`, `cards`, `evidence_strength`, `sample_coverage`, `limitations`, and `client_safe_text`.

Required report sections: strategy dashboard, personas, lifecycle journey, four-plane expansion ecosystem, SKU pool, Bundle strategy, 30/60/90 roadmap, risk matrix, and market validation summary.

Display-layer aggregation may rank SKUs and bundles for readability, but the source of truth remains `normalized_data_pack.json`.
