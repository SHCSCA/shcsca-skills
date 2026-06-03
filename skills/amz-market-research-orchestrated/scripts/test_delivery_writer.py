#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from delivery_writer import write_delivery_result, write_lineage_markdown, write_report_brief


CHILD_SKILLS = {
    "market_depth": "child_skills/market-depth-report",
    "lifecycle_strategy": "child_skills/lifecycle-strategy-report",
    "demand_gap": "child_skills/demand-gap-report",
    "critic": "child_skills/market-research-critic",
}


class DeliveryWriterTest(unittest.TestCase):
    def test_writes_delivery_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            data_pack = {
                "task_id": "ai_plush_us",
                "research_object": {"value": "ai plush"},
                "sources": [{"source_id": "src_001", "provider": "sorftime", "tool": "search", "confidence": "medium"}],
            }
            analysis_plan = {"task_id": "ai_plush_us"}

            write_lineage_markdown(data_pack, report_dir / "data" / "lineage.md")
            write_report_brief(report_dir, data_pack, analysis_plan, "Watch", CHILD_SKILLS)
            write_delivery_result(report_dir, {"decision": "Watch"}, CHILD_SKILLS)

            lineage = (report_dir / "data" / "lineage.md").read_text(encoding="utf-8")
            brief = json.loads((report_dir / "report_brief.json").read_text(encoding="utf-8"))
            delivery = json.loads((report_dir / "output" / "delivery_result.json").read_text(encoding="utf-8"))

            self.assertIn("src_001", lineage)
            self.assertEqual(brief["child_skills"], CHILD_SKILLS)
            self.assertEqual(brief["child_skill_invocations"]["market_depth"]["module"], "child_skills/market-depth-report")
            self.assertEqual(brief["child_skill_invocations"]["market_depth"]["dispatch_mode"], "subprocess_child_renderer")
            self.assertEqual(brief["child_skill_invocations"]["market_depth"]["invocation_log"], "analysis/child_skill_invocation_log.json")
            self.assertIn("data/normalized/normalized_data_pack.json", brief["child_skill_invocations"]["market_depth"]["inputs"])
            self.assertIn("output/html_reports/market-depth-report.html", brief["child_skill_invocations"]["market_depth"]["outputs"])
            self.assertEqual(brief["static_site"]["bundle_dir"], "output/html_reports")
            self.assertEqual(delivery["html_reports"]["index"], "output/html_reports/report.html")
            self.assertEqual(delivery["html_reports"]["compat_index"], "output/report.html")
            self.assertEqual(delivery["child_skills"]["critic"], "child_skills/market-research-critic")
            self.assertEqual(delivery["child_skill_invocations"]["critic"]["renderer"], "child_skills/market-research-critic/scripts/run_critic.py")
            self.assertEqual(delivery["child_skill_invocations"]["critic"]["dispatch_mode"], "subprocess_critic_child")
            self.assertEqual(delivery["child_skill_invocations"]["critic"]["invocation_log"], "analysis/child_skill_invocation_log.json")
            self.assertEqual(delivery["child_skill_invocations"]["critic"]["data_policy"], "read_only_normalized_data_pack")
            self.assertIn("html", delivery["formats"])
            self.assertIn("table_filter", delivery["interactive_features"])


if __name__ == "__main__":
    unittest.main()
