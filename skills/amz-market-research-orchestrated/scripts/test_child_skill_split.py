#!/usr/bin/env python3
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ChildSkillSplitTest(unittest.TestCase):
    def test_three_report_child_skills_exist_with_contracts(self):
        expected = {
            "amz-market-depth-report": "market-depth-report.html",
            "amz-lifecycle-strategy-report": "lifecycle-strategy-report.html",
            "amz-demand-gap-report": "demand-gap-report.html",
        }

        for skill_name, output_file in expected.items():
            skill_dir = ROOT / skill_name
            skill_md = skill_dir / "SKILL.md"
            contract = skill_dir / "references" / "report-contract.md"
            template = skill_dir / "templates" / output_file
            self.assertTrue(skill_md.exists(), f"{skill_name} missing SKILL.md")
            self.assertTrue(contract.exists(), f"{skill_name} missing report contract")
            self.assertTrue(template.exists(), f"{skill_name} missing template")

            text = skill_md.read_text(encoding="utf-8")
            self.assertIn("normalized_data_pack.json", text)
            self.assertIn("只读", text)
            self.assertIn(output_file, text)
            self.assertIn("展示层", text)


if __name__ == "__main__":
    unittest.main()
