# HTML Report Design Contract v1

Use this contract when generating `output/report.html`. The HTML report is the executive-facing artifact. It must read like a strategic intelligence dashboard, not like a Markdown document opened in a browser.

Reference inspiration:

- `https://agent.wenmai-ai.com/reports/ai-plush-market-scan-2026/ai-plush-market-scan-2026.v001.html`
- `https://agent.wenmai-ai.com/reports/ai-plush-lifecycle-strategy/ai-plush-lifecycle-strategy.v001.html`

Do not copy those reports verbatim. Reuse the structure pattern: dark report header, KPI dashboard, numbered modules, dense cards, evidence tables, matrices, roadmap, risk section, and data appendix.

## Hard Requirements

`report.html` must:

- Be a standalone HTML document with inline CSS.
- Put `data-report-style="strategic-dashboard-v1"` on the `<html>` element.
- Use semantic sections, not a single Markdown blob.
- Never wrap Markdown in `<pre>`, `.markdown-body`, or raw Markdown tables.
- Render evidence as real HTML tables, cards, score grids, timelines, or CSS/SVG charts.
- Include source references in visible content using `source_id`.
- Work offline for core content. Do not depend on external CDN for text, tables, layout, or decision cards.

The validator enforces these required visible sections:

1. `Go / Watch / No-Go`
2. `数据覆盖`
3. `市场大盘`
4. `关键词需求`
5. `Top 竞品`
6. `竞品深挖`
7. `Review / VOC`
8. `TikTok 验证`
9. `1688 供应链`
10. `Web / 风险补充`
11. `机会矩阵`
12. `数据缺口`
13. `完整数据附录`
14. `数据血缘`

## Visual System

Use a restrained executive-report palette:

- Deep navy header/background.
- Warm off-white page background.
- White cards with thin borders.
- Muted blue as primary accent.
- Sage/rose/warm/lavender accents for opportunities, risks, and matrices.
- No decorative gradients or floating blobs. Subtle header shapes are acceptable only if they do not distract.

The default visual baseline should follow the provided case-report template:

- deep navy `report-header` with badge, subtitle, metadata, and subtle circular overlays,
- square executive cards with a thin left accent bar, not generic rounded dashboard tiles,
- `chart-container` blocks before long evidence tables,
- dark `comp-deep-header` inside competitor deep-dive cards,
- `pain-card` / `joy-card` style VOC blocks,
- dark strategic `conclusion` or executive readout block.

Recommended layout:

- Header: badge, title, subtitle, report date, target market, data depth, primary decision.
- KPI grid: 6-10 cards with market size proxy, demand signal, competition density, evidence counts, data quality, recommended decision.
- Numbered sections: each section has `section-number`, title, short descriptor, and a dense content block.
- Tables: competitor matrix, keyword matrix, supplier matrix, source appendix.
- Cards: ASIN deep-dive cards, VOC quote cards, opportunity cards, risk cards.
- CSS charts: bar groups, score meters, price-band bars, segment bars, source coverage bars, or inline SVG. Use data tables as fallback.
- Collapsible detail appendices: use `<details>` for long tables so the report is both complete and scannable.

## Required HTML Skeleton

Use `assets/report-template.html` as the starting point. Replace template tokens with structured data from `data_pack.json` and module outputs.

Minimum class hooks:

- `report-header`
- `kpi-grid`
- `section-number`
- `evidence-table`
- `mini-chart`
- `deep-dive-grid`
- `comp-deep-card`
- `appendix-table`
- `opportunity-matrix`
- `data-lineage`

## Content Depth Rules

The HTML must be at least as complete as `report.md`, but more scannable:

- The first viewport must answer whether to enter, why, and which sub-opportunity to test.
- Every major module must include evidence counts and at least one `source_id`.
- Data coverage must show source count, entity counts, provider coverage, quality score, and method chain.
- Market section must show category proxy metrics, concentration, price bands, segment structure, seller origin, and source IDs.
- Keyword section must show demand Top terms, CPC pressure, competition pressure, data source types, and longtail table.
- Keyword section must show Chinese and English side-by-side: `关键词中文`, `英文关键词`, `相关性`, `中文意图`, and `source_id`.
- Keyword section must separate high-relevance market demand, adjacent/noisy category terms, and ASIN reverse traffic terms. Do not rank `battery pack`, generic LED, or unrelated decor terms as core category demand.
- Keyword appendix must expose at least 1000 deduped keyword rows for standard/deep reports.
- Competitor section must show at least Top 25 relevant products with product, price, rating, review count, estimated monthly sales, segment, launch/date if available, and source.
- Competitor tables and cards must include Chinese positioning (`中文定位`) and original English title (`英文标题`) so the user can read the strategy while preserving auditability.
- Competitor deep dive must include ASIN cards with image when available, trend, traffic terms, variation samples, and source IDs.
- VOC section must show sample size, star distribution, top themes, low-star themes, quote cards, and review evidence table.
- TikTok section must show product table, video evidence, relevance/noise judgment, and channel limitation.
- 1688 section must show price bands, supplier origins, supplier table, and cost caveat.
- Web/risk section must show Firecrawl documents and risk cards.
- Opportunity matrix must include opportunity, target user/scenario, price band, evidence, risk, recommendation.
- Final decision must include enter conditions, stop conditions, and next validation actions.
- Data gaps must be visible as a first-class section, not buried in the appendix.
- Full data appendix must include all renderable entities or a substantial capped table plus a pointer to `data_pack.json` if the table is too large.
- Data lineage appendix must include source IDs, provider, tool, label/query, confidence, and limitation/raw path.

## Layout Pattern

Use the bundled template and keep the report close to the reference case-report feel:

- deep navy report header with metadata and table of contents,
- KPI grid immediately under the header,
- executive conclusion box before deep sections,
- chart/card rows before long tables,
- ASIN deep-dive cards with product images and Chinese strategic reading,
- long evidence tables in `<details>` blocks,
- visible data coverage and normalization summary near the top.

## Anti-Patterns

Reject these outputs:

- A `<pre>` block containing the Markdown report.
- A generic article page with only headings and paragraphs.
- A report with no KPI dashboard, no evidence table, or no source IDs.
- A report that only shows Top 10 rows while hiding available product, keyword, review, TikTok, supplier, or web evidence.
- A beautiful page that drops TikTok, 1688, data gaps, or lineage sections.
- A chart-only report without tables that can be audited offline.
