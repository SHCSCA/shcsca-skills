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

- Be standalone HTML documents that load shared local `assets/report.css`, `assets/report.js`, and `assets/echarts.min.js`; inline CSS is allowed for small page-specific overrides but is not required.
- Work offline for core content; do not depend on external CDN for layout, tables, text, decisions, or charts.
- Load shared static site assets from `assets/` for the common design system, table interactions, report navigation, and sanitized report metadata.
- Use semantic sections in child reports, not a single Markdown blob.
- Never wrap Markdown in `<pre>`, `.markdown-body`, or raw Markdown tables.
- Render analysis as real HTML tables, cards, score grids, timelines, or CSS/SVG charts.
- Hide technical identifiers from client HTML: no `source_id`, `source_ids`, `provider`, `tool`, `raw_path`, file path, `Product ID`, or `product_id`. ASIN values are allowed only inside scoped customer components marked `data-allow-asin="benchmark-sniper"`, `data-allow-asin="profit-model"`, `data-allow-asin="competitor-table"`, or `data-allow-asin="demand-target-anchor"`; all other ASIN values are leaks.
- Use client-readable credibility language: `证据强度`, `数据覆盖`, `数据缺口`, `置信等级`, and `建议动作`.
- Support static-site interactions without CDN: top navigation on the entry page and all three child reports, mobile directory, table search, table sorting, collapsible evidence drawers, and lightweight chart hover/link states.
- Support template-derived report interactions without CDN: lifecycle-style `.filter-bar` / `.filter-btn[data-filter]` controls, sortable/searchable SKU and evidence tables, tabs, and chart fallback hover states.
- Use Chinese-facing content by default. VOC cards may show a short English review excerpt only when paired with Chinese summary and marked `data-allow-english-review="short"`. Full raw English reviews, English review titles, raw scraped comments, and raw field values remain audit-only.
- Market-depth AI image prompt cards are client-facing strategy instructions, not raw generation logs. Keep the three fixed prompt slots, but write the visible prompt body in Chinese business language. Do not expose raw English prompt templates such as `Product concept`, `traffic validation`, `with the product`, `differentiated comparison`, or `premium bundle` in customer HTML.

Internal template markers:

`data-report-style` may exist inside source templates while rendering, but final customer HTML must not contain `three-report-index-v2`, `market-depth-report-v2`, `lifecycle-strategy-report-v2`, or `demand-gap-report-v2`. Template compliance is validated by required structure, body classes, canonical class/id parity, and structure-level component checks instead of customer-visible internal markers.

Template scope: templates own layout, CSS classes, chart containers, table slots, card counts, interactions, and visual rhythm. Templates must not own category-specific business labels. Customer-facing product names, segment names, keyword tags, and lifecycle path labels must come from `analysis_plan.report_label_profile` or from explicit `customer_*` fields produced by the analysis layer for the current research object. Final customer HTML must not expose internal `Type A/B/C/D` labels or reuse labels from an unrelated category.

Required body template classes:

| File | Body class |
|---|---|
| `market-depth-report.html` | `template-market` |
| `lifecycle-strategy-report.html` | `template-lifecycle` |
| `demand-gap-report.html` | `template-demand mode-r3` |

## Entry Page

`output/html_reports/report.html` is the portable bundle entry page. It must:

- Link to the three child reports by same-folder filename only: `market-depth-report.html`, `lifecycle-strategy-report.html`, and `demand-gap-report.html`.
- Read the unified `report_readiness_view` and show report object, target market, data depth, `完整可交付 / 诊断交付 / 阻断交付`, Go / Watch / No-Go, evidence strength, sample coverage, quality grade, blocking conclusions, data gaps, and suggested actions.
- If `report_readiness_view.supply_blocked=true`, show `供应链测算未达门槛`, cap evidence strength at `中 / 诊断交付`, and do not display `供应链可控度较高`, `50+ 可打样`, or `毛利率可测算`.
- If readiness enters `non_acceptance_sample` / `阻断交付`, still render the standard four-page HTML bundle with the normal index, market-depth, lifecycle, and demand-gap templates. Required headings, anchors, chart containers, tables, and report navigation must remain present; only the data slots and conclusions downgrade to Chinese diagnostics. Do not replace child reports with a simplified generic diagnostic HTML page.
- For blocked diagnostic bundles, `delivery_result.status` is `blocked`, `delivery_result.decision` is `No-Go` or `Watch`, `critic_review.pass` is `false`, and child invocations are marked `diagnostic_template` / `main_renderer_diagnostic`. Stale `critic_review.pass=true` or old subprocess invocation logs must never be reused as proof of a blocked diagnostic delivery.
- Avoid duplicating the full report body.

`output/report.html` is a compatibility entry for older callers. It must link into the portable folder with `html_reports/market-depth-report.html`, `html_reports/lifecycle-strategy-report.html`, and `html_reports/demand-gap-report.html`.

## Required Child Sections

### 市场深度调研报告

Required visible sections:

1. 大盘结论
2. COSMO + Alexa 标签识别：固定展示 15 类核心标签，解释产品标签与用户标签的意图匹配。
3. 需求结构
4. 竞品格局
5. VOC 洞察
6. 标杆打法
7. 机会定义
8. TikTok 内容信号
9. 1688 供应链判断：必须基于去重有效 1688 报价 `>=50`；不足时阻断供应链成本结论并继续多轮 Sorftime 1688 采集。
10. 风险与行动摘要

Required client-analysis terms: `可进入性评分`, `价格带机会`, `竞争强度`, `关键切入口`, `商业含义`, `COSMO + Alexa`, `15 类核心标签`.

Competitor images in `competitor-scan`, the competitor table, and benchmark sniper cards may only use Amazon competitor product images or ASIN detail/enrichment images from Amazon image domains such as `media-amazon.com`, `ssl-images-amazon.com`, or `images-amazon.com`. They must not use arbitrary external image URLs, 1688, Alibaba, AliExpress, or `alicdn.com` supplier images. If Amazon image coverage is missing, render the fixed Chinese image diagnostic slot instead of substituting supplier images.

The `COSMO + Alexa 标签识别` section must follow the reference template rhythm, not a generic card stack. It contains four required zones:

1. `cosmo-matrix`: all 15 relation slots with `data-cosmo-relation`, Chinese label, confidence, evidence count, coverage status, and visible `产品意图/用户意图` plus customer-readable `产品/用户` markers. The matrix must be split into two visible lanes: `product-lane` titled `产品标签 · 产品被算法识别为什么` and `user-lane` titled `用户标签 · 用户为什么搜索/购买`. Customer HTML may keep compact P/U slot IDs only in `data-cosmo-relation` for validator and audit mapping; raw internal relation codes such as `USED_FOR_FUNC`, `CAPABLE_OF`, `IS_A`, `xWANT`, `xIs_A`, `xINTERSTED_IN`, or `REL_*` are audit-only and must not appear in visible text, hidden text, or `data-*` attributes. P/U slot IDs such as `P01` or `U09` must not appear in visible customer copy.
2. `cosmo-top-list`: high-confidence product/user tags ranked by confidence and evidence count.
3. `cosmo-gap-panel`: product label vs user intent gaps, with low-coverage relations shown as diagnostics instead of forced high confidence.
4. `cosmo-action-board`: Listing / QA / ad actions derived from the current effective evidence.

AI-generated label profiles are input candidates only. Every customer-visible COSMO term in a high/medium-confidence relation must be supported by the current relation evidence excerpt or effective data text. Unsupported profile terms must not be shown as chips; the slot should remain a low-coverage Chinese diagnostic instead of displaying cross-category labels.

COSMO visual rules are part of the market template contract:

- The 15-tag matrix is a dense decision module, not a debug table. Matrix cards must avoid heavy nested borders; use status-color top/left accents and light separators only.
- `cosmo-summary-item`, `cosmo-panel`, and `cosmo-matrix-cell` padding must be restored after importing canonical template CSS. The `143101` reference CSS includes a broad `body.template-market * { margin: 0; padding: 0; box-sizing: border-box }` reset, so shared assets must include final `body.template-market #cosmo-alexa-tags ...` overrides in `REPORT_POST_REFERENCE_CSS`.
- `cosmo-top-list` and `cosmo-gap-panel` must not render as narrow vertical sidebars. They sit under the matrix as full-width submodules; their rows render as horizontal card flows with responsive `auto-fit` columns.
- At PC widths 1366 and 1440, the COSMO module must show no left-edge clipping, no horizontal overflow, no collapsed padding, and no customer-visible raw relation codes.

When `supply_conclusion_blocked=true`, the market dashboard must place the supply-chain diagnostic immediately after the KPI dashboard and before cost/profit interpretation.

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

Lifecycle supply-chain KPIs must read `report_readiness_view` and the supplier quality gate. Strictly relevant 1688 quotes below threshold render as `供应链待验证`; they must not say `中低风险`, `供应链可控度较高`, `50+ 可打样`, or imply a ready-to-sample SKU.

Market competitor modules and lifecycle SKU modules should render referenced Amazon competitor images when the current effective product pool contains an allowlisted Amazon image URL. The competitor panorama, competitor table, benchmark deep-dive cards, lifecycle SKU cards, and SKU tables must use the same Amazon image-domain allowlist. Missing image coverage must not silently collapse the visual slot: the market report must show a visible Chinese diagnostic card explaining that the image dimension did not return a displayable URL and that the collection layer must supplement product main-image links. Missing images must never be backfilled with 1688, Alibaba, AliExpress, or `alicdn.com` supplier images.

### 用户心智断层与需求机会报告

Required visible sections:

1. 目标ASIN锚点
2. 决策看板
3. 需求主题痛点图
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
- Market competitor modules must render product images when real HTTP(S) image URLs exist: the Top competitor table uses compact thumbnails, the competitor scan may show an image strip, and benchmark-sniper cards may show a product image. When the data source does not return image URLs, keep the fixed image/diagnostic slot and show a Chinese data-source diagnostic instead of broken images, empty `src`, local paths, data URIs, or fabricated placeholders.
- Market VOC evidence must render as a fixed two-column theater: left `正面好评` and right `负面差评`, with exactly 6 `market-voc-card` slots per side. The class contract is `market-voc-sentiment-columns`, `market-voc-column positive`, `market-voc-column negative`, `market-voc-card joy`, and `market-voc-card pain`. A legacy one-grid `quote-grid` layout is not acceptable for the market VOC evidence block.
- Keyword content must summarize demand structure and intent clusters; raw reverse-traffic details stay in audit artifacts.
- Lifecycle report must turn market evidence into SKU, bundle, supply-chain, and roadmap decisions rather than repeating the market scan.
- Lifecycle report must read `analysis/lifecycle_strategy.json` for the full `sku_candidate_pool`, `recommended_skus`, `ecosystem_nodes`, and `filter_diagnostics`. The five fixed SKU cards are only layout slots; charts, filters, tables, and diagnostics must use the full candidate pool.
- Lifecycle ecosystem must render a three-layer structure: research object -> four-dimensional path (`关联度`, `场景`, `消耗`, `维护`) -> segment/scenario -> SKU candidate or reference ASIN. Internal `Type A/B/C/D` labels must not be visible in customer HTML.
- Lifecycle priority display must be adaptive: `<=8` SKU candidates use compact score cards, `9-20` use a horizontal full list, and `>20` use a Top 15 chart plus full candidate-pool table or drawer. Empty 0-100 axes for a small pool are invalid.
- Lifecycle SKU execution defaults to Top 8-15 visible candidates. The full candidate pool must be in a collapsed table/drawer, and each row must distinguish `供应锚点` from `仅竞品/VOC 候选` so users do not read every candidate as immediately sample-ready.
- Demand-gap report must turn reviews/VOC into Chinese demand themes, Gap Analysis, KANO, JTBD, representative voice summaries, and priority actions.
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
- A market-depth report missing the `COSMO + Alexa 标签识别` section or missing any of the 15 relation types from `analysis/cosmo_alexa_tags.json`.
- A lifecycle report that uses `未命名竞品`, `户外感应灯`, `Type A/B/C/D`, or old fixed fallback SKU names as visible customer labels for an unrelated category.
- A lifecycle report whose ecosystem chart is only a flat A/B/C/D pie/donut or whose priority chart implies 100 SKU when only a few candidates exist.
- Any CDN-dependent chart-only report that cannot be audited offline.
