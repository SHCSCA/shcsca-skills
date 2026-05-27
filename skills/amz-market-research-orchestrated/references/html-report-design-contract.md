# HTML Report Design Contract v2

Use this contract when generating the v2 HTML bundle. The executive-facing output is no longer one large dashboard. It is one entry page plus three standalone reports:

```text
output/report.html                         # compatibility entry, links into html_reports/
output/html_reports/report.html            # portable bundle entry / navigation
output/html_reports/market-depth-report.html
output/html_reports/lifecycle-strategy-report.html
output/html_reports/demand-gap-report.html
```

Do not copy the provided sample reports verbatim. Reuse their structure pattern: dark report header, KPI dashboard, numbered modules, dense cards, evidence tables, matrices, roadmap, risk section, and source-linked appendix.

## Hard Requirements

The four files inside `output/html_reports/` must:

- Be standalone HTML documents with inline CSS.
- Work offline for core content; do not depend on external CDN for layout, tables, text, decisions, or charts.
- Use semantic sections in child reports, not a single Markdown blob.
- Never wrap Markdown in `<pre>`, `.markdown-body`, or raw Markdown tables.
- Render evidence as real HTML tables, cards, score grids, timelines, or CSS/SVG charts.
- Include visible `source_id` evidence in child reports.

Required `data-report-style` markers:

| File | Marker |
|---|---|
| `output/report.html` | `three-report-index-v2` |
| `output/html_reports/report.html` | `three-report-index-v2` |
| `output/html_reports/market-depth-report.html` | `market-depth-report-v2` |
| `output/html_reports/lifecycle-strategy-report.html` | `lifecycle-strategy-report-v2` |
| `output/html_reports/demand-gap-report.html` | `demand-gap-report-v2` |

## Entry Page

`output/html_reports/report.html` is the portable bundle entry page. It must:

- Link to the three child reports by same-folder filename only: `market-depth-report.html`, `lifecycle-strategy-report.html`, and `demand-gap-report.html`.
- Show report object, target market, data depth, Go / Watch / No-Go, source count, quality grade, data coverage, and data gaps.
- Avoid duplicating the full report body.

`output/report.html` is a compatibility entry for older callers. It must link into the portable folder with `html_reports/market-depth-report.html`, `html_reports/lifecycle-strategy-report.html`, and `html_reports/demand-gap-report.html`.

## Required Child Sections

### 市场深度调研报告

Required visible sections:

1. 大盘仪表盘
2. 关键词需求
3. Top 竞品
4. VOC 痛点/爽点
5. 标杆竞品深挖
6. 机会判断
7. TikTok 验证
8. 1688 供应链
9. Web 风险
10. 数据血缘

Required mapped-data terms: `关键词中文`, `英文关键词`, `相关性`, `中文定位`, `英文标题`, `去重`.

### 产品全生命周期拓品战略报告

Required visible sections:

1. 战略仪表盘
2. 用户画像
3. 生命周期旅程
4. 四维拓品生态
5. SKU 执行总表
6. Bundle 策略
7. 30/60/90 天路线图
8. 风险矩阵
9. 市场数据验证

Required mapped-data terms: `SKU`, `Bundle`, `供应链`, `复购`.

### 用户心智断层与需求机会报告

Required visible sections:

1. 目标 ASIN/研究对象锚点
2. 决策看板
3. `$APPEALS` 痛点全景
4. 满意度鸿沟
5. `KANO × JTBD` 机会矩阵
6. 用户原声
7. 需求优先级与证据表

Required mapped-data terms: `KANO`, `JTBD`, `source_id`.

## Visual System

- Market and lifecycle reports use the restrained executive palette: deep navy header, warm off-white background, white cards, thin borders, muted blue accent, sage/rose/warm accents for opportunity and risk.
- Demand-gap report may keep a darker analytical style, but tables and text must remain legible and printable.
- No decorative CDN charts are required. Use CSS mini bars, tables, and cards as offline-first chart fallbacks.
- Required reusable hooks in child reports: `report-header`, `kpi-grid`, `section-number`, `evidence-table`, `mini-chart`, `chart-container`, `insight-box`, `conclusion`, `deep-dive-grid`, `comp-deep-card`, `appendix-table`.

## Content Depth Rules

- Every major module must include evidence counts or at least one visible `source_id`.
- Market report must preserve competitor, keyword, TikTok, 1688, web, appendix, and lineage evidence as tables.
- Keyword content must separate core demand, adjacent/noisy category terms, and ASIN reverse traffic terms.
- Lifecycle report must turn market evidence into SKU, bundle, supply-chain, and roadmap decisions rather than repeating the market scan.
- Demand-gap report must turn reviews/VOC into `$APPEALS`, Gap Analysis, KANO, JTBD, and priority actions.
- Missing lifecycle or demand-gap analysis JSON may be filled from Data Pack defaults, but the limitation must remain visible in `data_gaps` or `analysis_plan.limitations`.

## Anti-Patterns

Reject these outputs:

- A `<pre>` block containing the Markdown report.
- A generic article page with only headings and paragraphs.
- A report with no evidence table or no visible `source_id`.
- A child report that silently drops TikTok, 1688, data gaps, lineage, SKU strategy, or demand-gap sections.
- Any CDN-dependent chart-only report that cannot be audited offline.
