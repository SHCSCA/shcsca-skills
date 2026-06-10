# Demand Gap Report Contract

`child_skills/demand-gap-report` is an internal module of `amz-market-research-orchestrated` and consumes the normalized master data pack as read-only input.

The orchestrator should also provide `analysis/demand_gap_view.json`. This view model is the child report's preferred client-safe input and must include `kpis`, `charts`, `tables`, `cards`, `evidence_strength`, `sample_coverage`, `limitations`, and `client_safe_text`.

Required report sections: target anchor, decision board, demand-theme pain map, satisfaction gap, KANO × JTBD, user voice theater, and demand priority table.

Display-layer aggregation may cluster review themes for readability, but the source of truth remains `normalized_data_pack.json`.
