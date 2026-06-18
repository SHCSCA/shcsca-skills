# Proof Run Log

This file records local proof runs that are relevant to the `amz-market-research-orchestrated` 100-point scorecard. It is a pointer log, not a replacement for the generated proof JSON files.

## 2026-06-18

### Standard Template Delivery Gate Check

Scope:

- Verified the current standard HTML renderer, validators, customer-safety rules, browser smoke test, visual audit, and acceptance-proof semantics after the image fallback and lifecycle priority fixes.
- Confirmed that runtime Amazon image URL failures use a stable silent placeholder instead of customer-visible failure copy.
- Confirmed that lifecycle priority display is adaptive: compact score cards for small SKU pools, full horizontal list for medium pools, and Top 15 plus complete candidate-pool detail for large pools.
- Confirmed that diagnostic delivery remains distinct from full acceptance: a real report can pass diagnostic rendering and validators while `overall_pass=false` when readiness gates are still blocked.

Regression commands:

```bash
python -m unittest discover -s skills/amz-market-research-orchestrated/scripts -p "test_*.py" -v
npm run test:amz-browser
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/electric_cupping_massager_us_20260617
python skills/amz-market-research-orchestrated/scripts/run_visual_parity_audit.py --dir reports/electric_cupping_massager_us_20260617
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/wall_lighting_us_20260615
python skills/amz-market-research-orchestrated/scripts/run_visual_parity_audit.py --dir reports/wall_lighting_us_20260615
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/electric_cupping_massager_us_20260617 --depth standard
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/wall_lighting_us_20260615 --depth standard
```

Result:

- Full Python discovery suite: 360 tests passed.
- Browser smoke: passed through `npm run test:amz-browser`.
- `validate_market_research_deliverables.py`: passed for `electric_cupping_massager_us_20260617` and `wall_lighting_us_20260615`.
- `run_visual_parity_audit.py`: passed for both real sample reports. External image resource failures are filtered only for remote image 400/403/404; JavaScript/page errors and layout failures remain blocking.
- `electric_cupping_massager_us_20260617`: `overall_pass=false`, `delivery_mode=diagnostic_delivery`, `diagnostic_delivery_pass=true`, `decision=No-Go`; blocked by keyword sample depth and customer-intent duplicate ratio.
- `wall_lighting_us_20260615`: `overall_pass=false`, `delivery_mode=diagnostic_delivery`, `diagnostic_delivery_pass=true`; blocked by keyword customer-intent duplicate ratio and Chinese mapping coverage.
- A temporary acceptance fixture was also checked as `overall_pass=true`, `delivery_mode=full_acceptance`, `full_acceptance_pass=true`.

Customer HTML forbidden-copy scan:

```bash
rg -n --glob "*.html" "图片加载失败|参考竞品图片未返回|竞品图片未返回|Type A|Type B|Type C|Type D|source_id|raw_path|provider|待补|暂无|未命名竞品|竞品记录|清洗数据|样本 [0-9]|PROMPT 0[123]" reports/electric_cupping_massager_us_20260617/output reports/wall_lighting_us_20260615/output
```

Result: no customer HTML matches.

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
