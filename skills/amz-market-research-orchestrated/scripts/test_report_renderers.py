#!/usr/bin/env python3
import json
import inspect
import re
import tempfile
import unittest
from pathlib import Path

import report_renderers
from report_renderers import build_report_documents
from render_dashboard_html import renderer_callbacks
from test_render_dashboard_html import make_renderable_report


class ReportRenderersTest(unittest.TestCase):
    def test_renderer_callbacks_cover_report_renderer_dependencies(self):
        source = inspect.getsource(report_renderers.build_report_documents)
        needed = set(re.findall(r'call\(fns, "([^"]+)"', source))
        missing = sorted(needed - set(renderer_callbacks()))
        self.assertEqual(missing, [])

    def test_builds_bundle_and_compat_documents_from_callbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            analysis_plan = json.loads((report_dir / "analysis" / "analysis_plan.json").read_text(encoding="utf-8"))
            delivery = json.loads((report_dir / "output" / "delivery_result.json").read_text(encoding="utf-8"))

            rendered_docs, compat_index = build_report_documents(
                data_pack,
                analysis_plan,
                {},
                {},
                {},
                {},
                {},
                {},
                delivery,
                "Watch",
                renderer_callbacks(),
            )

            self.assertEqual(sorted(rendered_docs.keys()), ["demand_gap", "index", "lifecycle_strategy", "market_depth"])
            self.assertIn('data-report-style="three-report-index-v2"', rendered_docs["index"])
            self.assertIn('data-report-style="market-depth-report-v2"', rendered_docs["market_depth"])
            self.assertIn('data-report-style="lifecycle-strategy-report-v2"', rendered_docs["lifecycle_strategy"])
            self.assertIn('data-report-style="demand-gap-report-v2"', rendered_docs["demand_gap"])
            self.assertIn('href="market-depth-report.html"', rendered_docs["index"])
            self.assertNotIn('href="html_reports/market-depth-report.html"', rendered_docs["index"])
            self.assertIn('href="html_reports/market-depth-report.html"', compat_index)
            self.assertIn('href="html_reports/lifecycle-strategy-report.html"', compat_index)
            self.assertIn('href="html_reports/demand-gap-report.html"', compat_index)
            self.assertIn("市场深度调研报告", rendered_docs["market_depth"])
            self.assertIn("产品全生命周期拓品战略报告", rendered_docs["lifecycle_strategy"])
            self.assertIn("用户心智断层与需求机会报告", rendered_docs["demand_gap"])
            for html_doc in [*rendered_docs.values(), compat_index]:
                self.assertIn("assets/report.css", html_doc)
                self.assertIn("assets/report.js", html_doc)
                self.assertNotIn("{{", html_doc)


if __name__ == "__main__":
    unittest.main()
