#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from site_assets import REPORT_CSS, REPORT_JS, SITE_ASSETS, TEMPLATE_REFERENCE_REPORTS
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

    def test_renderer_writes_shared_assets_and_html_uses_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)

            result = self.run_renderer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            asset_root = report_dir / "output" / "html_reports" / "assets"
            self.assertEqual((asset_root / "report.css").read_text(encoding="utf-8").strip(), REPORT_CSS)
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
