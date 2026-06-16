# HTML Template Parity Checklist

This checklist turns the user's three downloaded HTML templates into enforceable design and interaction expectations for `amz-market-research-orchestrated`. The three downloaded HTML files are canonical report templates, not loose inspiration. The orchestrator must preserve their layout, component hierarchy, CSS vocabulary, and interaction model, then render real report data from the normalized data pack into template content slots.

## Source Mapping

| Report | Download folder | Local baseline | Required output |
|---|---|---|---|
| Market depth | `C:\Users\wz\Downloads\downloadpage\143101` | `references/template-baseline-manifest.json.baselines.market_depth` | `output/html_reports/market-depth-report.html` |
| Lifecycle strategy | `C:\Users\wz\Downloads\downloadpage\143511` | `references/template-baseline-manifest.json.baselines.lifecycle_strategy` | `output/html_reports/lifecycle-strategy-report.html` |
| Demand gap | `C:\Users\wz\Downloads\downloadpage\143645` | `references/template-baseline-manifest.json.baselines.demand_gap` | `output/html_reports/demand-gap-report.html` |

Packaged canonical assets:

- `assets/canonical_templates/market-depth-reference.html`
- `assets/canonical_templates/lifecycle-strategy-reference.html`
- `assets/canonical_templates/demand-gap-reference.html`
- `assets/canonical_templates/echarts.min.js`
- `references/html-template-slot-contract.json`

## Global Rules

- Do not copy `_next/static/chunks`, iframe shells, remote CDN scripts, or hard-coded sample data into customer outputs.
- Do preserve the canonical template layout, section order, CSS class vocabulary, card/table/chart structure, spacing model, color system, and interaction affordances.
- AI may generate analysis text and map clean data into slots; it must not invent a new page layout, choose a different style system, or replace the canonical template with a generic report shell.
- Do not expose `source_id`, provider, raw path, Product ID, or unscoped technical fields in customer HTML. ASIN may appear only in the benchmark sniper, profit model, competitor table, and demand target anchor components with explicit `data-allow-asin` scope.
- Keep all shared runtime assets local under `output/html_reports/assets/`.
- Preserve mobile behavior through CSS media rules and JS that does not depend on a build step.
- Use generated view models from `normalized_data_pack.json`; never fill visual components with sample template data.
- Template skeletons are fixed contracts. Data quality may block a conclusion or trigger a diagnostic artifact, but it must not remove required headings, cards, tables, anchors, or chart containers from the standard HTML template.

## Market Depth Parity

Baseline folder: `143101`.

Required section density:

- 大盘结论
- COSMO + Alexa 标签识别
- 需求结构
- 竞品格局
- VOC 洞察
- 标杆打法
- 机会定义
- TikTok 内容信号
- 1688 供应链判断
- 风险与行动摘要
- Executive market verdict and Go / Watch / No-Go summary.
- TAM/SAM/SOM or market sizing equivalent when evidence exists; otherwise explicit data gap.
- Demand trend and keyword structure.
- Price band, competitor matrix, and opportunity matrix.
- VOC pain points and benchmark competitor teardown.
- TikTok signal and 1688 supply-chain signal.
- Risk and action summary.

Required components:

- `report-header`, `header-meta`, `kpi-grid`, `kpi-card`.
- `cosmo-layout` with four fixed zones: `cosmo-matrix`, `cosmo-top-list`, `cosmo-gap-panel`, and `cosmo-action-board`. The matrix must render all 15 COSMO + Alexa relation slots with `data-cosmo-relation`, evidence coverage, confidence status, and Listing / QA / ad actions.
- COSMO visual parity requires `cosmo-matrix` cards to use light separators instead of table-like heavy borders. `cosmo-top-list` and `cosmo-gap-panel` must render below the matrix as full-width horizontal card flows, not as narrow vertical sidebars. Because the reference market CSS resets all element padding, final shared assets must include post-reference `body.template-market #cosmo-alexa-tags ...` overrides that restore KPI, summary, panel, and matrix-card spacing.
- `chart-container`, `mini-chart`, radar/bar/bubble fallback semantics.
- `comp-table` or equivalent competitor evidence table.
- `voc-grid`, `deep-dive-grid`, `comp-deep-card`.
- `opportunity-matrix`.
- Exactly 3 pricing strategy cards and exactly 3 AI image prompt cards with stable `#pricing` and `#prompt` anchors.
- Competitor table must expose scoped ASIN values using `data-allow-asin="competitor-table"`.
- Demand target anchor must expose the target reference ASIN using `data-allow-asin="demand-target-anchor"`.
- Evidence drawer for methodology and limitations.

Required interactions:

- Section navigation.
- Table search and sorting.
- Filter chips for evidence or competitor group.
- Chart rows linked to evidence tables where possible.

## Lifecycle Strategy Parity

Baseline folder: `143511`.

Required section density:

- 战略仪表盘
- 用户画像
- 生命周期旅程
- 四维拓品生态
- 拓品方案池
- Bundle 策略
- 30/60/90 天路线图
- 风险矩阵
- 市场验证摘要
- Strategic dashboard.
- Persona / segment grid.
- Lifecycle journey or timeline.
- Four-dimensional product ecosystem.
- SKU / expansion pool with priority.
- Bundle strategy.
- 30 / 60 / 90 day roadmap.
- Risk matrix.
- Market validation summary.

Required components:

- `persona-grid`, `timeline-grid`, `bundle-grid`, `phase-grid`, `risk-grid`.
- `sku-table-wrap`, sortable SKU table, priority bars.
- `#skuTable`, `#skuBody`, and `#skuFullPool` / `sku-full-pool` as stable SKU table and full candidate-pool anchors.
- `type-badge`, `supply-badge`, filter bar and filter buttons.
- Bundle cards with price, savings, and dependency assumptions.
- Four-dimensional ecosystem must keep a two-chart layout: `#sunburst` plus `#priorityChart`.
- `#sunburst` must use a three-layer data structure: research object -> four-dimensional path -> segment/scenario -> SKU candidate or reference ASIN. A flat A/B/C/D pie/donut is not acceptable.
- `#priorityChart` must adapt to candidate-pool size: compact score cards for `<=8`, full horizontal list for `9-20`, and Top 15 plus full candidate-pool table/drawer for `>20`.
- 拓品方案池 must keep the five fixed SKU slots: 基础款、升级款、套装款、配件款、复购耗材.
- 30/60/90 路线图 must keep six roadmap cards: three `Phase` strategy cards plus three action checklist cards, split across `roadmap-phase-grid` and `roadmap-action-grid`.
- SKU table controls must keep seven reference filters: 全部、四个当前证据生成的中文策略类型、供应链验证、P1 立即启动.
- Filter controls may use internal `data-filter` values such as A/B/C/D, but visible customer labels must come from current `analysis_plan.report_label_profile.lifecycle_type_labels` or current evidence-derived Chinese names, never raw `Type A/B/C/D`.

Required interactions:

- SKU table sort.
- SKU or bundle filtering.
- Tabs for roadmap / bundle / risk groups.
- Collapsible evidence details for supply-chain and cost assumptions.

## Demand Gap Parity

Baseline folder: `143645`.

Required section density:

- 目标ASIN锚点
- 决策看板
- 市场痛点全景图（需求主题）
- 满意度鸿沟
- KANO x JTBD
- 用户原声
- 需求优先级
- Research object overview.
- Decision board.
- Demand-theme pain map.
- Satisfaction gap.
- KANO x JTBD classification.
- User voice theater.
- Need priority table.
- Conversion opportunity actions.

Required components:

- `mode-r3` or equivalent demand-gap visual mode.
- Dark or high-contrast report header when used by the template family.
- `kpi-grid`, `chart`, `chart-interpretation`.
- `quote-cn`, localized VOC cards, warning and opportunity callouts.
- Market VOC evidence must use `market-voc-sentiment-columns` with left `正面好评` and right `负面差评`; class signatures must include `market-voc-column positive`, `market-voc-column negative`, `market-voc-card joy`, and `market-voc-card pain`; each side must render exactly 6 cards and must not fall back to a single mixed `quote-grid`.
- `demand-sentiment-columns` with left `正面反馈` and right `负面反馈`; the two column class signatures must be `demand-sentiment-column positive` and `demand-sentiment-column negative`; each side must render exactly 6 cards.
- Demand evidence cards must follow the 143645 R3 evidence-card language: white cards, thin borders, red/green sentiment accents, Chinese insight, short English excerpt when available, evidence strength, unmet point, and action opportunity.
- User voice details must be kept in a collapsed `evidence-drawer` so the main evidence theater remains dense and readable.
- The collapsed drawer summary must keep the fixed label `用户原声证据明细表`.
- Prioritization table with evidence strength and confidence.

Required interactions:

- VOC tabs or filters.
- Expandable quote/evidence drawers.
- Radar or rose chart fallback rendered without CDN.
- Mobile single-column layout with no text overlap.

## Acceptance Checklist

Before claiming template parity:

- `template-baseline-manifest.json` lists all three source folders and excluded assets.
- `html-template-slot-contract.json` lists fixed slot counts, required IDs, component groups, and scoped customer exceptions for all three reports.
- The three canonical reference HTML files are packaged under `assets/canonical_templates/`.
- `echarts.min.js` is local in the skill and copied into `output/html_reports/assets/`; customer HTML must not reference `cdn.jsdelivr.net`.
- `assets/report.css` contains shared selectors for every required component family above.
- `assets/report.js` contains local hooks for nav, search, sort, tabs, filters, drawers, and chart fallbacks.
- `validate_market_research_deliverables.py` rejects missing static assets, missing required child sections, broken child links, non-portable paths, and customer HTML leaks.
- At least one rendered acceptance sample passes the validator with all three child reports present.
- A human visual review confirms the rendered reports carry the same density and interaction shape as the three downloaded baselines without copying sample data.

## Known Remaining Gaps

- `run_visual_parity_audit.py` provides browser screenshot evidence, but visual approval still needs at least one recent acceptance sample audit artifact.
- `run_template_reference_visual_compare.py` opens the downloaded reference HTML and generated customer HTML side by side at PC `1366x900` and `1440x900`, captures paired screenshots, and verifies selector signal parity, screenshot byte ratio, downsampled pixel distance, body background, section density, key component width ratio, left offset, and center offset.
- Pixel-perfect approval still needs human review of the paired screenshots, but the automated gate must prove the generated report retains the reference template component vocabulary and PC layout skeleton.
- Real-data parity is not proven until `run_acceptance_proof.py` passes on an `acceptance_sample` generated from fresh Sorftime-backed data.
