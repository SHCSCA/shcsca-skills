# Sample Coverage Matrix

Use this registry to classify local report directories. A report directory is a client delivery sample only when it passes readiness, render, critic, and final validation in the current codebase.

## Sample Classes

| Class | Meaning | Required proof |
|---|---|---|
| `acceptance_sample` | Can be used to prove the skill is structurally ready for client delivery. | `run_acceptance_proof.py` returns `overall_pass=true`; proof JSON shows readiness, render, and final validator all passed; browser smoke covers the portable bundle when UI changes are in scope. |
| `non_acceptance_sample` | Historical or incomplete data pack. Useful for negative tests and readiness blockers, not delivery claims. | `check_data_readiness.py --write` returns `acceptance_ready=false` with blocking gaps such as empty products or keyword depth below 1000. |
| `demo_sample` | Synthetic or fixture-only sample used by unit tests. | Temporary test directory or explicit fixture. Must not be described as real Sorftime/Firecrawl evidence. |

## Current Local Samples

| Path | Class | Current proof target | Notes |
|---|---|---|---|
| `reports/lighting_us_20260528` | `acceptance_sample` | readiness pass, render pass, final validator pass, browser smoke source for generated fixture parity. | Review depth is thin and should remain a warning, not a structural blocker. |
| `skills/amz-market-research-orchestrated/reports/wall_sconce_us_20260526` | `acceptance_sample` | readiness pass, render pass, final validator pass. | Large evidence pack used for validator performance and customer-safety regression. |
| `skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525` | `non_acceptance_sample` | readiness fail; renderer must stop before client HTML delivery. | Products and keywords are empty; do not use to claim delivery completion. |

## Required Verification Commands

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<task_id> --depth standard
npm run test:amz-browser
```

Negative samples should prove the gate closes:

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525
```

Expected result: non-zero exit and `render_failed: data readiness failed before rendering`.

## Rules

- Do not promote a sample from `non_acceptance_sample` to `acceptance_sample` by editing counts, duplicating rows, or injecting AI-generated placeholder entities.
- Do not use `delivery_result.status=complete` or `critic_review.pass=true` alone as proof. The validator must also prove `delivery_result.data_readiness`, `report-data.json.readiness`, and `data_readiness_report.json` agree with a fresh readiness assessment.
- If a real collector cannot fetch enough evidence in the current environment, keep the sample as non-acceptance and document the missing collector path instead of fabricating evidence.
