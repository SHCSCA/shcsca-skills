# AGENTS.md

## Project Scope

This repository is a skills collection. Keep user-facing documentation aligned with the actual `skills/` directory and each skill's `SKILL.md`.

## Key Rules

- Use `rg` / `rg --files` for repository search.
- Do not treat `amz-market-depth-report`, `amz-lifecycle-strategy-report`, or `amz-demand-gap-report` as top-level skills. They are internal modules under `skills/amz-market-research-orchestrated/child_skills/`.
- `amz-market-research-orchestrated` is the only external trigger for the Amazon market research workflow.
- `amz-ad-architecture` is a top-level installable skill for Chinese Amazon advertising structures, cost-profit and CPC linkage, metric definitions, negative targeting, and seven-day optimization rules.
- `amz-create-image` is a top-level installable skill whose default designer handoff is a compact two-sheet workbook (`主图副图` and `A+需求`), including Premium A+ function and scene carousel planning when appropriate.
- The root README is for human users. Keep it concise and aligned with the actual installable skill directories.
- There is no root `docs/` directory currently. Sync project knowledge through `README.md`, this file, and skill-local `SKILL.md` / `references/`.
- Ignore untracked scratch or generated output directories unless the user explicitly asks to publish them.

## Validation

For `amz-market-research-orchestrated`, common checks are:

```bash
python -m unittest discover -s skills/amz-market-research-orchestrated/scripts -p "test_*.py" -v
npm run test:amz-browser
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/<report_dir>
python skills/amz-market-research-orchestrated/scripts/run_visual_parity_audit.py --dir reports/<report_dir>
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<report_dir> --depth standard
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<report_dir> --depth deep --reference-visual --download-root C:\Users\wz\Downloads\downloadpage
```

Acceptance semantics:

- Full acceptance requires `overall_pass=true`, `delivery_mode=full_acceptance`, and `full_acceptance_pass=true`.
- Real reports with insufficient data gates may be valid diagnostic deliveries only when `overall_pass=false`, `delivery_mode=diagnostic_delivery`, and `diagnostic_delivery_pass=true`; do not describe these as complete market conclusions.
- Visual audits may ignore remote image 400/403/404 resource failures, but JavaScript errors, page errors, missing required components, and layout overflow are still failures.
