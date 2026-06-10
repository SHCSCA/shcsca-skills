# Sample Coverage Matrix

Use this registry to classify local report directories. A report directory is a client delivery sample only when it passes readiness, render, critic, and final validation in the current codebase.

## Sample Classes

| Class | Meaning | Required proof |
|---|---|---|
| `acceptance_sample` | Can be used to prove the skill is structurally ready for client delivery. | `run_acceptance_proof.py` returns `overall_pass=true`; proof JSON shows readiness, render, and final validator all passed; browser smoke covers the portable bundle when UI changes are in scope. |
| `partial_acceptance_sample` | Real data run where non-supply analysis is deliverable, but 1688 gross-margin conclusions are disabled after recovery. | `run_acceptance_proof.py` returns `overall_pass=true`, `data_readiness_report.json.partial_report_ready=true`, and the supply module renders a diagnostic instead of margin conclusions. |
| `non_acceptance_sample` | Historical or incomplete data pack. Useful for negative tests and readiness blockers, not delivery claims. | `check_data_readiness.py --write` returns `acceptance_ready=false`, and `recover_data_readiness.py` cannot resolve the blocking gaps with real collector attempts. |
| `demo_sample` | Synthetic or fixture-only sample used by unit tests. | Temporary test directory or explicit fixture. Must not be described as real Sorftime/Firecrawl evidence. |

## Current Local Samples

| Path | Class | Current proof target | Notes |
|---|---|---|---|
| `reports/lighting_us_20260528` | `acceptance_sample` | `output/acceptance_proof.json`, checked `2026-06-03T06:35:28Z`, `overall_pass=true`. | Review depth is thin and remains a warning, not a structural blocker. |
| `skills/amz-market-research-orchestrated/reports/wall_sconce_us_20260526` | `acceptance_sample` | `output/acceptance_proof.json`, checked `2026-06-03T06:35:46Z`, `overall_pass=true`. | Large evidence pack used for validator performance and customer-safety regression. |
| `skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525` | `non_acceptance_sample` | `output/acceptance_proof.json`, checked `2026-06-03T06:37:39Z`, `overall_pass=false`, `stale_delivery_ignored=true`. | Products and keywords are empty; old delivery artifacts are ignored and must not be used to claim completion. |

## Required Verification Commands

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<task_id> --depth standard
npm run test:amz-browser
```

Negative samples should prove the gate closes:

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525
```

Expected result: Sorftime recovery attempts first, then non-zero exit and `render_failed: data readiness failed before final rendering after recovery` if the data still cannot meet the gates.

## Rules

- Do not promote a sample from `non_acceptance_sample` to `acceptance_sample` by editing counts, duplicating rows, or injecting AI-generated placeholder entities.
- Do not use `delivery_result.status=complete` or `critic_review.pass=true` alone as proof. The validator must also prove `delivery_result.data_readiness`, `report-data.json.readiness`, and `data_readiness_report.json` agree with a fresh readiness assessment.
- If a real collector cannot fetch enough evidence in the current environment, keep the sample as non-acceptance and document the missing collector path instead of fabricating evidence.
