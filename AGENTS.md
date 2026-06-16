# AGENTS.md

## Project Scope

This repository is a skills collection. Keep user-facing documentation aligned with the actual `skills/` directory and each skill's `SKILL.md`.

## Key Rules

- Use `rg` / `rg --files` for repository search.
- Do not treat `amz-market-depth-report`, `amz-lifecycle-strategy-report`, or `amz-demand-gap-report` as top-level skills. They are internal modules under `skills/amz-market-research-orchestrated/child_skills/`.
- `amz-market-research-orchestrated` is the only external trigger for the Amazon market research workflow.
- The root README is for human users. Keep it concise and aligned with the actual installable skill directories.
- There is no root `docs/` directory currently. Sync project knowledge through `README.md`, this file, and skill-local `SKILL.md` / `references/`.
- Ignore untracked scratch or generated output directories unless the user explicitly asks to publish them.

## Validation

For `amz-market-research-orchestrated`, common checks are:

```bash
python -m unittest -v test_site_assets test_site_interactions test_validate_market_research_deliverables
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/<report_dir>
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<report_dir> --depth deep --reference-visual --download-root C:\Users\wz\Downloads\downloadpage
```
