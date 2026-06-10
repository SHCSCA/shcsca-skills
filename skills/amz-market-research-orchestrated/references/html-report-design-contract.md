# HTML Report Design Contract v2

Use this contract when generating the v2 HTML bundle. The executive-facing output is no longer one large dashboard. It is one entry page plus three standalone reports:

```text
output/report.html                         # compatibility entry, links into html_reports/
output/html_reports/report.html            # portable bundle entry / navigation
output/html_reports/market-depth-report.html
output/html_reports/lifecycle-strategy-report.html
output/html_reports/demand-gap-report.html
output/html_reports/assets/report.css
output/html_reports/assets/report.js
output/html_reports/assets/report-data.json
```

Do not copy the provided sample reports verbatim. Reuse their structure pattern: dark report header, KPI dashboard, numbered modules, dense cards, insight tables, matrices, roadmap, risk section, and executive summary cards. HTML is the client-facing analysis layer; source audit details stay in JSON/Markdown artifacts.

Template baselines for this design system:

| Report | Local template baseline |
|---|---|
| Market depth | `downloadpage/143101` report HTML |
| Lifecycle strategy | `downloadpage/143511` report HTML |
| Demand gap | `downloadpage/143645` report HTML, using the active `mode-r3` look |

Use the `reports/*/*.html` files in those folders as the source of visual and interaction patterns. Do not import `_next/static/chunks`, iframe case shells, Next runtime scripts, external CDN URLs, or hard-coded sample data. Shared CSS and JS must be folded into `output/html_reports/assets/report.css` and `output/html_reports/assets/report.js`.

## Hard Requirements

The four files inside `output/html_reports/` must:

- Be standalone HTML documents with inline CSS.
- Work offline for core content; do not depend on external CDN for layout, tables, text, decisions, or charts.
- Load shared static site assets from `assets/` for the common design system, table interactions, report navigation, and sanitized report metadata.
- Use semantic sections in child reports, not a single Markdown blob.
- Never wrap Markdown in `<pre>`, `.markdown-body`, or raw Markdown tables.
- Render analysis as real HTML tables, cards, score grids, timelines, or CSS/SVG charts.
- Hide technical identifiers from client HTML: no `source_id`, `source_ids`, `provider`, `tool`, `raw_path`, file path, `Product ID`, or `product_id`. ASIN values are allowed only inside scoped customer components marked `data-allow-asin="benchmark-sniper"`, `data-allow-asin="profit-model"`, `data-allow-asin="competitor-table"`, or `data-allow-asin="demand-target-anchor"`; all other ASIN values are leaks.
- Use client-readable credibility language: `证据强度`, `数据覆盖`, `数据缺口`, `置信等级`, and `建议动作`.
- Support static-site interactions without CDN: top navigation, mobile directory, table search, table sorting, collapsible evidence drawers, and lightweight chart hover/link states.
- Support template-derived report interactions without CDN: lifecycle-style `.filter-bar` / `.filter-btn[data-filter]` controls, sortable/searchable SKU and evidence tables, tabs, and chart fallback hover states.
- Use Chinese-facing content by default. VOC cards may show a short English review excerpt only when paired with Chinese summary and marked `data-allow-english-review="short"`. Full raw English reviews, English review titles, raw scraped comments, and raw field values remain audit-only.

Internal template markers:

`data-report-style` may exist inside source templates while rendering, but final customer HTML must not contain `three-report-index-v2`, `market-depth-report-v2`, `lifecycle-strategy-report-v2`, or `demand-gap-report-v2`. Template compliance is validated by required structure, body classes, canonical class/id parity, and structure-level component checks instead of customer-visible internal markers.

Required body template classes:

| File | Body class |
|---|---|
| `market-depth-report.html` | `template-market` |
| `lifecycle-strategy-report.html` | `template-lifecycle` |
| `demand-gap-report.html` | `template-demand mode-r3` |

## Entry Page

`output/html_reports/report.html` is the portable bundle entry page. It must:

- Link to the three child reports by same-folder filename only: `market-depth-report.html`, `lifecycle-strategy-report.html`, and `demand-gap-report.html`.
- Show report object, target market, data depth, Go / Watch / No-Go, evidence strength, sample coverage, quality grade, data gaps, and suggested actions.
- Avoid duplicating the full report body.

`output/report.html` is a compatibility entry for older callers. It must link into the portable folder with `html_reports/market-depth-report.html`, `html_reports/lifecycle-strategy-report.html`, and `html_reports/demand-gap-report.html`.

## Required Child Sections

### 市场深度调研报告

Required visible sections:

1. 大盘结论
2. 需求结构
3. 竞品格局
4. VOC 洞察
5. 标杆打法
6. 机会定义
7. TikTok 内容信号
8. 1688 供应链判断：必须基于去重有效 1688 报价 `>=50`；不足时阻断供应链成本结论并继续多轮 Sorftime 1688 采集。
9. 风险与行动摘要

Required client-analysis terms: `可进入性评分`, `价格带机会`, `竞争强度`, `关键切入口`, `商业含义`.

### 产品全生命周期拓品战略报告

Required visible sections:

1. 战略仪表盘
2. 用户画像
3. 生命周期旅程
4. 四维拓品生态
5. 拓品方案池
6. Bundle 策略
7. 30/60/90 天路线图
8. 风险矩阵
9. 市场验证摘要

Required client-analysis terms: `SKU`, `Bundle`, `供应链`, `复购`, `AOV`, `LTV`.

### 用户心智断层与需求机会报告

Required visible sections:

1. 目标ASIN锚点
2. 决策看板
3. `$APPEALS` 痛点图
4. 满意度鸿沟
5. `KANO × JTBD`
6. 用户原声（正面反馈 6 槽 + 负面反馈 6 槽，可展示短英文评论摘录）
7. 需求优先级

Required client-analysis terms: `KANO`, `JTBD`, `心智断层`, `负面触发点`, `转化机会`.

## Visual System

- Market and lifecycle reports use the restrained executive palette: deep navy header, warm off-white background, white cards, thin borders, muted blue accent, sage/rose/warm accents for opportunity and risk.
- Demand-gap report uses the `143645` active `mode-r3` analytical style: strong navy hero, white evidence cards, red/green sentiment accents, clear gap/risk emphasis, and readable tables.
- No decorative CDN charts are required. Use CSS mini bars, tables, and cards as offline-first chart fallbacks.
- Required reusable hooks in child reports: `report-header`, `kpi-grid`, `section-number`, `evidence-table`, `insight-table`, `mini-chart`, `chart-container`, `insight-box`, `conclusion`, `deep-dive-grid`, `comp-deep-card`, `persona-grid`, `timeline-grid`, `bundle-grid`, `sku-table-wrap`, `filter-btn`, `quote-cn`, and `chart-interpretation`.

## Content Depth Rules

- Every major module must lead with conclusion, evidence strength, business meaning, and suggested action.
- Market report must preserve competitor, demand, TikTok, 1688, web, and risk evidence as client-readable insight tables.
- Keyword content must summarize demand structure and intent clusters; raw reverse-traffic details stay in audit artifacts.
- Lifecycle report must turn market evidence into SKU, bundle, supply-chain, and roadmap decisions rather than repeating the market scan.
- Demand-gap report must turn reviews/VOC into Chinese `$APPEALS`, Gap Analysis, KANO, JTBD, representative voice summaries, and priority actions.
- User voice cards must keep the fixed template structure: left column `正面反馈` with exactly 6 cards, right column `负面反馈` with exactly 6 cards, plus a collapsed evidence-detail drawer. Cards may show star rating, sentiment, short English review excerpt, Chinese insight, theme, evidence strength, unmet point, and action implication. Full raw English reviews, English review titles, and scraped comment text remain audit-only.
- Market pricing strategy must render exactly 3 pricing cards and exactly 3 AI image prompt cards, with stable `#pricing` and `#prompt` anchors. Lifecycle SKU strategy must render the five fixed SKU slots: 基础款、升级款、套装款、配件款、复购耗材. Template slots must not disappear when data is thin; data insufficiency is handled by readiness diagnostics, blocked delivery, or explicit audit files, not by deleting layout.
- Missing lifecycle or demand-gap analysis JSON may be filled from Data Pack defaults, but the limitation must remain visible in `data_gaps` or `analysis_plan.limitations`.

## Anti-Patterns

Reject these outputs:

- A `<pre>` block containing the Markdown report.
- A generic article page with only headings and paragraphs.
- A report that exposes `source_id`, provider/tool names, raw paths, Product IDs, ASIN values, or source tables in client HTML.
- A report that copies raw English reviews, English review titles, or scraped comment text directly into client HTML.
- A child report that silently drops TikTok, 1688, data gaps, SKU strategy, or demand-gap sections.
- Any CDN-dependent chart-only report that cannot be audited offline.
