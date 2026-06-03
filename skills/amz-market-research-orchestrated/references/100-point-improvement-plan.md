# 100-Point Improvement Plan

This document is the controller-level scorecard for pushing `amz-market-research-orchestrated` from the earlier 78-82 range toward a defensible 100. It is intentionally stricter than "tests pass": a score only counts when the repository has a contract, implementation, and evidence path.

## Current Score

| Area | Weight | Current | Status |
|---|---:|---:|---|
| Architecture split and child skill ownership | 15 | 14 | Main skill owns orchestration; internal child skills own market, lifecycle, demand-gap, and critic modules. |
| Data cleaning, dedupe, lineage, readiness | 20 | 18 | Normalizer and readiness gate are fail-closed; sample registry now separates acceptance and non-acceptance samples. |
| Static HTML product quality | 15 | 14 | Three-report bundle, local CSS/JS, interactions, template baseline, parity checklist, and parity contract gate are in place; remaining work is screenshot-level visual review against fresh real reports. |
| Critic/refinement loop | 15 | 12 | Critic runs as an internal child process, writes operator summaries, and final validator gates pass state; remaining work is richer asynchronous feedback history over real failed cases. |
| Collector reliability | 15 | 11 | Keyword/review collectors now expose `collection_ready` and failure semantics; remaining work is live Sorftime replay evidence and broader product/category collector coverage. |
| Customer safety and audit integrity | 10 | 10 | Client HTML rejects technical leaks and raw English review leakage; critic summary and proof run log provide reviewer-facing audit pointers. |
| Verification and sample proof | 10 | 10 | Two accepted samples now pass unified proof and one non-acceptance sample proves fail-closed behavior with stale delivery ignored. |
| **Total** | **100** | **89** | Improved from 78-82, but not yet complete. |

## Completed Upgrades

- Split child skills under the orchestrator instead of top-level sibling skills.
- Added real child process dispatch and `analysis/child_skill_invocation_log.json`.
- Added hard global dedupe and customer-safe HTML validation.
- Added `check_data_readiness.py` as a pre-render gate.
- Added `data_readiness_report.json`, `delivery_result.data_readiness`, and `report-data.json.readiness` as a three-way status contract.
- Added `run_acceptance_proof.py` as the operator-facing proof entrypoint for readiness, rendering, validation, and proof artifacts.
- Added `analysis/critic_summary.md` as an operator-facing critic review summary.
- Added `html-template-parity-checklist.md` to convert the three downloaded HTML baselines into explicit layout and interaction expectations.
- Added `validate_template_parity_contract.py` and wired it into `run_acceptance_proof.py`.
- Generated proof artifacts for two `acceptance_sample` directories and one `non_acceptance_sample`; see `proof-run-log.md`.
- Added collector failure semantics:
  - no keyword seed/node writes `keyword_collection_no_seed` and returns exit code `2`;
  - no review ASIN writes `review_collection_no_asin` and returns exit code `2`;
  - low sample depth is a data readiness problem, not a completed delivery.
- Added acceptance/non-acceptance/demo sample registry in `sample-coverage-matrix.md`.

## Remaining Gaps To Reach 100

### P1: Live Collector Proof

Current tests mock Sorftime responses. That proves parser and contract behavior, not live data availability.

Required next evidence:

```bash
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir reports/<real_task> --min-keywords 1200
python skills/amz-market-research-orchestrated/scripts/collect_sorftime_reviews.py --dir reports/<real_task> --review-type Both --min-reviews 80
```

Acceptance:

- raw files are written under `data/raw/`;
- collection summaries show `collection_ready=true`;
- after normalization, readiness remains `acceptance_ready=true`.

### P1: Unified Proof Command Evidence

The unified command is implemented and has now been run against accepted and rejected samples. Keep this section as the operational proof requirement for future samples.

Current artifact:

```text
scripts/run_acceptance_proof.py
```

It runs readiness, render, final validator, and writes:

```text
output/acceptance_proof.json
output/acceptance_proof.md
```

It now also runs the static template parity contract before readiness/render/validator.

Acceptance:

- at least two `acceptance_sample` directories produce successful proof artifacts;
- at least one `non_acceptance_sample` fails closed with an explicit readiness or validator reason;
- proof output includes enough context for an operator to see whether failure came from data readiness, rendering, critic, or customer-safety validation.

Current proof log:

```text
references/proof-run-log.md
```

### P1: Real Critic Feedback History

The critic loop and operator summary are present. The remaining gap is real failed-case history from production-like runs, not more synthetic cases.

Required upgrade:

- keep failed critic cases in `training_data/failed_cases.jsonl` only for real failed rounds.
- review accumulated failed cases and tune SKILL.md only when a repeated failure pattern appears.

### P2: Visual Parity Review Evidence

The generated reports borrow local templates and now have an explicit parity checklist plus a static parity contract against the three reference downloaded templates. The remaining work is evidence: browser screenshots and human review against fresh rendered reports.

Current artifact:

```text
references/html-template-parity-checklist.md
scripts/validate_template_parity_contract.py
```

These track and verify market/depth/lifecycle/demand-gap sections, components, interactions, and responsive layout signals.

### P2: Product/Category Collector Coverage

Keyword and review collectors are now explicit. Product/category collection is still represented through the Data Pack contract and Sorftime tool map, but not as a dedicated local collector script with the same summary semantics.

Recommended artifact:

```text
scripts/collect_sorftime_products.py
```

Only build this if the runtime has stable Sorftime product/search tools available.

## Recommendation

Do not spend the next cycle adding more isolated unit tests. The highest-value next move is live collector proof: run Sorftime-backed keyword/review collection on one fresh task and preserve the raw collection summaries, then perform screenshot-level visual parity review on the rendered HTML.

## Definition Of 100

The skill reaches 100 only when all of the following are true:

- one command can prove readiness, render, critic, customer safety, and static bundle integrity;
- at least two `acceptance_sample` directories pass the full proof command;
- at least one `non_acceptance_sample` proves fail-closed behavior;
- delivery status, critic status, and readiness status cannot contradict each other;
- customer HTML never exposes raw technical identifiers or raw English review/commentary fields;
- the sample matrix and proof artifacts tell an operator exactly what is accepted, what is historical, and what must be recollected.
