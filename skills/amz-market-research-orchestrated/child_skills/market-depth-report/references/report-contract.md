# Market Depth Report Contract

`child_skills/market-depth-report` is an internal module of `amz-market-research-orchestrated` and consumes the normalized master data pack as read-only input.

The orchestrator should also provide `analysis/market_depth_view.json`. This view model is the child report's preferred client-safe input and must include `kpis`, `charts`, `tables`, `cards`, `evidence_strength`, `sample_coverage`, `limitations`, and `client_safe_text`.

Required report sections: market dashboard, keyword demand, competitor landscape, VOC, benchmark deep dives, opportunity definition, TikTok validation, 1688 supply chain, and risk/action summary.

Display-layer aggregation may dedupe presentation rows further for readability, but the source of truth remains `normalized_data_pack.json`.
