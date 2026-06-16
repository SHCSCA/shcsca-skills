# Proof Run Log

This file records local proof runs that are relevant to the `amz-market-research-orchestrated` 100-point scorecard. It is a pointer log, not a replacement for the generated proof JSON files.

## 2026-06-16

### COSMO Template Visual Fix

Scope:

- Fixed the `COSMO + Alexa 标签识别` market-depth module after canonical `143101` CSS reset removed COSMO padding.
- Kept data-expression logic unchanged; this run only changed shared CSS/post-reference overrides and CSS contract tests.
- Verified that the 15-tag matrix keeps low-border cards, `cosmo-top-list` and `cosmo-gap-panel` render as horizontal full-width submodules, and PC rendering has no left clipping or horizontal overflow.

Rendered sample:

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir reports/wall_lighting_us_20260615 --no-recover
```

Visual audit evidence:

- Chrome 1440px rendered `reports/wall_lighting_us_20260615/output/html_reports/market-depth-report.html`.
- DOM/computed-style checks after render:
  - `summaryPadding = 18px 18px 18px 22px`
  - `cellPadding = 14px`
  - `panelPadding = 18px`
  - `horizontalOverflow = false`
  - `cosmo-top-list` card width around `262px` at 1440px, no narrow sidebar layout

Regression commands:

```bash
python -m unittest -v test_site_assets test_site_interactions test_validate_market_research_deliverables
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/wall_lighting_us_20260615
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/wall_lighting_us_20260615 --depth deep --reference-visual --download-root C:\Users\wz\Downloads\downloadpage
```

Result:

- `test_site_assets + test_site_interactions + test_validate_market_research_deliverables`: 74 tests passed
- `validate_market_research_deliverables.py`: `validate_ok`
- `run_acceptance_proof.py`: `overall_pass=true`, `delivery_mode=full_acceptance`, `full_acceptance_pass=true`

## 2026-06-03

### Template Parity

Command:

```bash
python skills/amz-market-research-orchestrated/scripts/validate_template_parity_contract.py --require-downloads
```

Result:

- `template_parity_contract=true`
- `require_downloads=true`
- Baselines found: `market_depth`, `lifecycle_strategy`, `demand_gap`
- Local folders verified:
  - `C:\Users\wz\Downloads\downloadpage\143101`
  - `C:\Users\wz\Downloads\downloadpage\143511`
  - `C:\Users\wz\Downloads\downloadpage\143645`

### Acceptance Sample 1

Command:

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/lighting_us_20260528 --depth standard
```

Generated artifact:

```text
reports/lighting_us_20260528/output/acceptance_proof.json
reports/lighting_us_20260528/output/acceptance_proof.md
```

Result:

- `overall_pass=true`
- `sample_class=acceptance_sample`
- readiness passed with 17 products and 1208 keywords
- render passed
- validator passed
- critic passed with score 74

### Acceptance Sample 2

Command:

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir skills/amz-market-research-orchestrated/reports/wall_sconce_us_20260526 --depth standard
```

Generated artifact:

```text
skills/amz-market-research-orchestrated/reports/wall_sconce_us_20260526/output/acceptance_proof.json
skills/amz-market-research-orchestrated/reports/wall_sconce_us_20260526/output/acceptance_proof.md
```

Result:

- `overall_pass=true`
- `sample_class=acceptance_sample`
- readiness passed with 123 products, 1106 keywords, and 776 reviews
- render passed
- validator passed
- critic passed with score 78

### Non-Acceptance Sample

Fail-closed renderer command:

```bash
python skills/amz-market-research-orchestrated/scripts/render_dashboard_html.py --dir skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525
```

Result:

```text
render_failed: data readiness failed before rendering: product_sample_depth, keyword_sample_depth
```

Proof command:

```bash
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525 --depth standard
```

Generated artifact:

```text
skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525/output/acceptance_proof.json
skills/amz-market-research-orchestrated/reports/neck_massager_us_20260525/output/acceptance_proof.md
```

Result:

- `overall_pass=false`
- `sample_class=non_acceptance_sample`
- blocking gaps: `product_sample_depth`, `keyword_sample_depth`
- `delivery_status=null`
- `critic_pass=null`
- `stale_delivery_ignored=true`
