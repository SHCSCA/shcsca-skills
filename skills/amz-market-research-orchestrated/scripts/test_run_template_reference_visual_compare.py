#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

import run_template_reference_visual_compare as reference_compare


class TemplateReferenceVisualCompareTest(unittest.TestCase):
    def test_build_cases_resolves_downloaded_reference_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ["143101", "143511", "143645"]:
                target = root / folder / "agent.wenmai-ai.com" / "reports" / folder
                target.mkdir(parents=True)
                (target / "reference.html").write_text("<!doctype html><html><body>ref</body></html>", encoding="utf-8")

            cases = reference_compare.build_cases(root)

            self.assertEqual(set(cases), {"market_depth", "lifecycle_strategy", "demand_gap"})
            self.assertTrue(cases["market_depth"]["reference_html"].endswith("reference.html"))
            self.assertEqual(cases["market_depth"]["generated"], "market-depth-report.html")
            self.assertIn(".pricing-grid", cases["market_depth"]["must_exist"])

    def test_build_cases_fails_when_reference_folder_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(reference_compare.ReferenceCompareError) as ctx:
                reference_compare.build_cases(Path(tmp))

        self.assertIn("missing reference folder", str(ctx.exception))

    def test_markdown_lists_reference_and_generated_screenshots(self):
        audit = {
            "report_dir": "reports/example",
            "checked_at": "2026-06-09T00:00:00Z",
            "overall_pass": True,
            "reference_root": "C:/Downloads/downloadpage",
            "output_dir": "reports/example/output/template_reference_visual_compare",
            "results": [
                {
                    "report": "market_depth",
                    "viewport": "pc-1440",
                    "signalScore": 0.86,
                    "layoutScore": 1.0,
                    "screenshotByteRatio": 1.05,
                    "pixelDistance": 0.071,
                    "referenceScreenshot": "market_depth-pc-1440-reference.png",
                    "generatedScreenshot": "market_depth-pc-1440-generated.png",
                }
            ],
            "failures": [],
            "stderr": "",
        }

        md = reference_compare.markdown(audit)

        self.assertIn("Template Reference Visual Comparison", md)
        self.assertIn("market_depth-pc-1440-reference.png", md)
        self.assertIn("market_depth-pc-1440-generated.png", md)
        self.assertIn("0.86", md)
        self.assertIn("1.05", md)
        self.assertIn("0.071", md)


if __name__ == "__main__":
    unittest.main()
