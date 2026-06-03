---
name: amz-market-research-critic
description: "Use when amz-market-research-orchestrated has produced market research view models or HTML reports that need evidence-quality, decision-consistency, and client-safety review."
---

# amz-market-research-critic

## Positioning

This is an internal critic module owned by `amz-market-research-orchestrated`. It is not an external entrypoint. It reviews report drafts after the orchestrator has produced the normalized data pack, client-safe view models, and child report HTML.

The critic is a semantic quality gate. It does not replace the hard validator, does not collect data, and must not rewrite `normalized_data_pack.json`.

## Inputs

```text
reports/{task_id}/data/normalized/normalized_data_pack.json
reports/{task_id}/analysis/analysis_plan.json
reports/{task_id}/analysis/market_depth_view.json
reports/{task_id}/analysis/lifecycle_strategy_view.json
reports/{task_id}/analysis/demand_gap_view.json
reports/{task_id}/output/html_reports/market-depth-report.html
reports/{task_id}/output/html_reports/lifecycle-strategy-report.html
reports/{task_id}/output/html_reports/demand-gap-report.html
reports/{task_id}/output/delivery_result.json
skills/amz-market-research-orchestrated/references/acceptance-scenarios.md
```

## Outputs

```text
reports/{task_id}/analysis/critic_review.json
reports/{task_id}/analysis/refinement_plan.json
reports/{task_id}/analysis/critic_summary.md
reports/{task_id}/training_data/failed_cases.jsonl
```

## Review Contract

The critic output must be JSON with these fields:

```json
{
  "pass": false,
  "score": 65,
  "grade": "C",
  "blocking_issues": [
    "VOC sample is too thin for a high-confidence Go decision."
  ],
  "report_issues": {
    "market_depth": [],
    "lifecycle_strategy": [],
    "demand_gap": []
  },
  "data_confidence": {
    "review_depth": "low",
    "cross_validation": "low",
    "decision_confidence": "overstated"
  },
  "suggestions": [
    "Downgrade the decision to Watch or explicitly mark VOC confidence as low."
  ],
  "refinement_targets": [
    {
      "report_type": "demand_gap",
      "action": "soften_conclusion",
      "reason": "Review sample cannot support category-wide VOC conclusions."
    }
  ]
}
```

## Review Rules

- Fail reports that give a strong `Go`, `B+`, or high confidence when review depth, cross-validation, or data gaps do not support it.
- Fail reports that hide missing landed cost, FBA fee, return rate, ACOS, or review coverage as if the decision is fully proven.
- Fail report contradictions across the three child reports.
- Fail customer-facing technical leaks such as `source_id`, ASIN, provider, raw path, internal path, or raw English review text.
- Convert missing evidence into explicit data gaps and next validation actions.
- Never invent replacement facts. The only allowed refinement is changing analysis strength, wording, grouping, and visibility of limitations.

## Refinement Protocol

When the critic fails a draft, the orchestrator may run at most two refinement rounds. A refinement round may update `*_view.json`, child report HTML, `critic_review.json`, and `refinement_plan.json`. It must not recollect data or change the normalized facts unless the user explicitly starts a new data collection run.

Every run must also write `analysis/critic_summary.md` for operator review. The summary must include final pass state, score, grade, readiness state, original decision, final decision, whether the decision was adjusted, unresolved findings, applied refinement operations, and the guardrail that failed critic rounds cannot be delivered as complete.
