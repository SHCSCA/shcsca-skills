#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from site_assets import REPORT_CSS, REPORT_JS, REPORT_POST_REFERENCE_CSS, SITE_ASSETS, TEMPLATE_REFERENCE_REPORTS
from test_render_dashboard_html import SCRIPT, make_renderable_report

SKILL_DIR = Path(__file__).resolve().parents[1]


class SiteAssetsTest(unittest.TestCase):
    def run_renderer(self, report_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(report_dir)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_assets_are_local_and_declare_interaction_hooks(self):
        combined = REPORT_CSS + "\n" + REPORT_JS
        self.assertNotIn("http://", combined)
        self.assertNotIn("https://", combined)
        self.assertEqual(
            TEMPLATE_REFERENCE_REPORTS,
            {
                "market_depth": "downloadpage/143101 AI plush market scan template",
                "lifecycle_strategy": "downloadpage/143511 AI plush lifecycle strategy template",
                "demand_gap": "downloadpage/143645 demand gap report template",
            },
        )
        for selector in [
            ".site-nav",
            ".table-tools",
            ".tab-button",
            ".evidence-drawer",
            ".mini-chart",
            ".grid-3",
            ".metric-strip",
            ".bar.good span",
            ".bar.bad span",
            ".supply-card",
            ".source-grid",
            ".conclusion-grid",
            ".kano-grid",
            ".row2",
            ".thumb-wall",
            ".demand-chart",
            ".template-market .report-header",
            ".template-lifecycle .report-header",
            ".template-demand .report-header",
            ".template-demand .hero",
            ".persona-grid",
            ".timeline-grid",
            ".bundle-grid",
            ".filter-btn",
            ".sku-table-wrap",
            ".quote-cn",
            ".chart-interpretation",
            "@media(max-width:760px)",
        ]:
            self.assertIn(selector, REPORT_CSS)
        for snippet in [
            "site-nav-toggle",
            "input.type='search'",
            "querySelectorAll('th')",
            "data-tabs",
            "data-tab-target",
            ".mini-chart .bar-row",
            ".filter-bar",
            "dataset.filter",
            "addEventListener('click'",
        ]:
            self.assertIn(snippet, REPORT_JS)

    def test_template_baseline_manifest_is_auditable(self):
        manifest = json.loads((SKILL_DIR / "references" / "template-baseline-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["baselines"]), {"market_depth", "lifecycle_strategy", "demand_gap"})
        expected_folders = {"market_depth": "143101", "lifecycle_strategy": "143511", "demand_gap": "143645"}
        for key, folder in expected_folders.items():
            baseline = manifest["baselines"][key]
            self.assertIn(folder, baseline["download_folder"])
            self.assertRegex(baseline["sha256"], re.compile(r"^[A-F0-9]{64}$"))
            self.assertGreater(baseline["line_count"], 100)
            self.assertTrue(baseline["borrowed_css_signals"])
            self.assertTrue(baseline["borrowed_js_signals"])
        for excluded in ["_next/static/chunks", "cdn.jsdelivr.net echarts runtime", "hard-coded sample SKU_DATA"]:
            self.assertIn(excluded, manifest["excluded_assets"])

    def test_slot_contract_matches_demand_reference_chart_slots(self):
        contract = json.loads((SKILL_DIR / "references" / "html-template-slot-contract.json").read_text(encoding="utf-8"))
        demand = contract["reports"]["demand_gap"]

        self.assertEqual(demand["required_ids"], ["appealsRose", "gapRadar"])
        self.assertEqual(demand["exact_class_counts"]["demand-chart"], 2)
        self.assertEqual(demand["minimum_class_counts"]["chart"], 2)

    def test_chart_and_card_assets_avoid_customer_confusing_labels_and_overflow(self):
        self.assertNotIn("清洗数据", REPORT_JS)
        self.assertNotIn("项目 '+", REPORT_JS)
        self.assertNotIn("SKU '+", REPORT_JS)
        self.assertIn("数据指标 '+", REPORT_JS)
        self.assertIn("拓品方案 '+", REPORT_JS)
        self.assertIn("ecosystemPath:row.dataset.ecosystemPath", REPORT_JS)
        self.assertIn("const pathMap=new Map()", REPORT_JS)
        self.assertIn("SKU 紧凑评分卡", REPORT_JS)
        self.assertIn("Top 15 SKU 优先级", REPORT_JS)
        self.assertIn("row.getAttribute('data-filter')", REPORT_JS)
        self.assertNotIn("Type ${type}", REPORT_JS)
        self.assertNotIn("未分层赛道", REPORT_JS)
        self.assertIn("月销量估算", REPORT_JS)
        self.assertIn("label:{show:false}", REPORT_JS)
        self.assertIn("nodeClick:false", REPORT_JS)
        self.assertIn("function shortSkuLabel", REPORT_JS)
        self.assertIn("shortSkuLabel(row.label)", REPORT_JS)
        self.assertIn(".template-market .container,.template-lifecycle .container,.template-demand .container,.template-demand .wrap{width:min(1200px,calc(100% - 32px));margin:0 auto}", REPORT_CSS)
        self.assertIn(".template-market .report-header,.template-lifecycle .report-header{max-width:100%;overflow:hidden", REPORT_CSS)
        self.assertIn(".template-market .report-header h1,.template-lifecycle .report-header h1{max-width:min(100%,1180px);overflow-wrap:break-word;text-wrap:balance}", REPORT_CSS)
        self.assertNotIn(".template-market .report-header h1,.template-lifecycle .report-header h1{max-width:calc(100% - 280px)", REPORT_CSS)
        self.assertIn("body.template-demand .wrap{max-width:1360px;width:min(1360px,calc(100% - 48px));margin:0 auto;padding:24px}", REPORT_POST_REFERENCE_CSS)
        self.assertIn(".template-market #market-dashboard>.kpi-grid{grid-template-columns:repeat(4,minmax(0,1fr))}", REPORT_CSS)
        self.assertNotIn("#executive-dashboard", REPORT_CSS)
        self.assertIn(".demand-sentiment-columns", REPORT_CSS)
        self.assertIn(".demand-column-head", REPORT_CSS)
        self.assertIn(".demand-sentiment-column.positive .demand-column-head", REPORT_CSS)
        self.assertIn(".demand-sentiment-column.negative .demand-column-head", REPORT_CSS)
        self.assertIn(".demand-evidence-card,.sentiment-empty-card{border:1px solid #e0ddd8;background:#fff", REPORT_CSS)
        self.assertNotIn("background:#13243d;color:#e6edf8;padding:16px;min-height:236px", REPORT_CSS)
        self.assertIn(".comp-table th:first-child,.comp-table td:first-child{width:112px;min-width:112px;white-space:nowrap", REPORT_CSS)
        self.assertIn(".comp-table .asin-token{display:inline-block;white-space:nowrap", REPORT_CSS)
        self.assertIn(".comp-table th:nth-child(5),.comp-table td:nth-child(5){min-width:96px}", REPORT_CSS)
        self.assertIn(".sku-strategy-card", REPORT_CSS)
        self.assertIn(".sku-strategy-card{border:1px solid rgba(26,39,68,.14);background:#fff;padding:0", REPORT_CSS)
        self.assertIn(".sku-strategy-head{display:flex;justify-content:space-between;gap:12px;align-items:center", REPORT_CSS)
        self.assertIn("body.template-lifecycle .sku-strategy-head{display:flex;justify-content:space-between", REPORT_POST_REFERENCE_CSS)
        self.assertIn("body.template-lifecycle .sku-strategy-card h3{margin:16px 18px 14px", REPORT_POST_REFERENCE_CSS)
        self.assertIn("body.template-market .report-header::before,body.template-market .report-header::after,body.template-lifecycle .report-header::before,body.template-lifecycle .report-header::after{display:none", REPORT_POST_REFERENCE_CSS)
        self.assertIn("body.template-market .mini-chart .bar-row,body.template-lifecycle .mini-chart .bar-row{grid-template-columns:minmax(0,1.2fr) minmax(72px,1.8fr) 42px", REPORT_POST_REFERENCE_CSS)
        self.assertIn(".sku-strategy-card h3", REPORT_CSS)
        self.assertIn(".sku-strategy-meta", REPORT_CSS)
        self.assertIn("row.dataset.supply", REPORT_JS)
        self.assertIn("row.dataset.phase", REPORT_JS)
        self.assertIn("dataset.chartDisabled==='true'", REPORT_JS)
        self.assertIn(".diagnostic-chart-container", REPORT_CSS)
        self.assertIn(".diagnostic-chart-item", REPORT_CSS)
        self.assertIn(".cosmo-matrix-cell[data-confidence=\"高\"] .cosmo-confidence-pill", REPORT_CSS)
        self.assertIn(".cosmo-relation-title", REPORT_CSS)
        self.assertIn(".cosmo-evidence-strip", REPORT_CSS)
        self.assertIn(".cosmo-action-label", REPORT_CSS)
        self.assertIn(".cosmo-action-card[data-action-kind", REPORT_CSS)
        self.assertIn(".cosmo-relation-kind", REPORT_CSS)
        self.assertIn(".cosmo-relation-lane", REPORT_CSS)
        self.assertIn(".cosmo-relation-id", REPORT_CSS)
        self.assertIn(".cosmo-matrix-lanes", REPORT_CSS)
        self.assertIn(".cosmo-matrix-lane{", REPORT_CSS)
        self.assertIn(".cosmo-matrix-lane.product-lane", REPORT_CSS)
        self.assertIn(".cosmo-matrix-lane.user-lane", REPORT_CSS)
        self.assertIn(".cosmo-lane-title", REPORT_CSS)
        self.assertIn(".cosmo-lane-grid", REPORT_CSS)
        self.assertIn(".cosmo-layout-stacked", REPORT_CSS)
        self.assertIn(".cosmo-submodule-grid", REPORT_CSS)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", REPORT_CSS)
        self.assertNotIn("grid-template-columns:minmax(0,1.55fr) minmax(320px,.65fr)", REPORT_CSS)
        self.assertIn(".cosmo-matrix-cell[data-dimension=\"用户标签\"]", REPORT_CSS)
        self.assertIn(".cosmo-matrix-cell[data-dimension=\"产品标签\"]", REPORT_CSS)
        self.assertNotIn("min-height:214px", REPORT_CSS)
        self.assertNotIn("cosmo-matrix-cell{border:1px solid rgba(26,39,68,.12);background:#fbfcfd;padding:12px;min-height:168px;display:grid;grid-template-rows:auto auto auto auto;align-content:start;gap:7px;overflow:hidden", REPORT_CSS)
        self.assertIn(".cosmo-matrix-cell{border:1px solid rgba(26,39,68,.12);background:#fbfcfd;padding:12px;min-height:248px;display:grid", REPORT_CSS)
        self.assertIn(".cosmo-matrix-cell{border:1px solid rgba(26,39,68,.12);background:#fbfcfd;padding:12px;min-height:248px;display:grid;grid-template-rows:auto;align-content:start;gap:8px;overflow:visible", REPORT_CSS)
        self.assertIn(".cosmo-card-meta-grid", REPORT_CSS)
        self.assertIn(".cosmo-term-block", REPORT_CSS)
        self.assertIn(".cosmo-action-direction", REPORT_CSS)
        self.assertIn(".cosmo-business-meaning{margin:0!important", REPORT_CSS)
        self.assertIn(".comp-image-diagnostic-card", REPORT_CSS)
        self.assertIn(".image-load-fallback[hidden]{display:none!important}", REPORT_CSS)
        self.assertIn("fallback.classList.add('is-visible')", REPORT_JS)
        self.assertIn("if(img.complete&&img.naturalWidth===0)showImageFallback(img)", REPORT_JS)

    def test_renderer_writes_shared_assets_and_html_uses_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)

            result = self.run_renderer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            asset_root = report_dir / "output" / "html_reports" / "assets"
            css_text = (asset_root / "report.css").read_text(encoding="utf-8").strip()
            self.assertTrue(css_text.startswith(REPORT_CSS))
            self.assertIn(REPORT_POST_REFERENCE_CSS, css_text)
            self.assertIn("canonical reference template: market_depth", css_text)
            self.assertIn("canonical reference template: lifecycle_strategy", css_text)
            self.assertIn("canonical reference template: demand_gap", css_text)
            self.assertEqual((asset_root / "report.js").read_text(encoding="utf-8").strip(), REPORT_JS)
            site_data = json.loads((report_dir / SITE_ASSETS["data"]).read_text(encoding="utf-8"))
            self.assertIn("interactive_features", site_data)

            bundle_html = (report_dir / "output" / "html_reports" / "report.html").read_text(encoding="utf-8")
            compat_html = (report_dir / "output" / "report.html").read_text(encoding="utf-8")
            self.assertIn('href="assets/report.css"', bundle_html)
            self.assertIn('src="assets/report.js"', bundle_html)
            self.assertIn('href="html_reports/assets/report.css"', compat_html)
            self.assertIn('src="html_reports/assets/report.js"', compat_html)
            for html_doc in [bundle_html, compat_html]:
                self.assertNotIn("https://cdn", html_doc.lower())
                self.assertNotIn('href="output/', html_doc)


if __name__ == "__main__":
    unittest.main()
