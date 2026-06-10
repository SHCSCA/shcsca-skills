#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import child_report_renderer


ROOT = Path(__file__).resolve().parents[2]


class ChildSkillSplitTest(unittest.TestCase):
    def test_internal_child_modules_exist_with_contracts(self):
        expected = {
            "market-depth-report": ("market-depth-report.html", "render_market_depth_report.py"),
            "lifecycle-strategy-report": ("lifecycle-strategy-report.html", "render_lifecycle_strategy_report.py"),
            "demand-gap-report": ("demand-gap-report.html", "render_demand_gap_report.py"),
        }
        child_root = ROOT / "amz-market-research-orchestrated" / "child_skills"

        for module_name, (output_file, script_file) in expected.items():
            skill_dir = child_root / module_name
            skill_md = skill_dir / "SKILL.md"
            contract = skill_dir / "references" / "report-contract.md"
            template = skill_dir / "templates" / output_file
            script = skill_dir / "scripts" / script_file
            self.assertTrue(skill_md.exists(), f"{module_name} missing SKILL.md")
            self.assertTrue(contract.exists(), f"{module_name} missing report contract")
            self.assertTrue(template.exists(), f"{module_name} missing template")
            self.assertTrue(script.exists(), f"{module_name} missing render script")

            text = skill_md.read_text(encoding="utf-8")
            self.assertIn("normalized_data_pack.json", text)
            self.assertIn("只读", text)
            self.assertIn(output_file, text)
            self.assertIn("展示层", text)

        critic_dir = child_root / "market-research-critic"
        self.assertTrue((critic_dir / "SKILL.md").exists(), "critic missing SKILL.md")
        self.assertTrue((critic_dir / "references" / "critic-contract.md").exists(), "critic missing contract")
        self.assertTrue((critic_dir / "scripts" / "run_critic.py").exists(), "critic missing run script")
        critic_text = (critic_dir / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("critic_review.json", critic_text)
        self.assertIn("refinement_plan.json", critic_text)
        self.assertIn("normalized_data_pack.json", critic_text)

    def test_report_child_modules_are_not_top_level_skills(self):
        for old_name in ["amz-market-depth-report", "amz-lifecycle-strategy-report", "amz-demand-gap-report"]:
            self.assertFalse((ROOT / old_name).exists(), f"{old_name} should live under amz-market-research-orchestrated/child_skills")

    def test_internal_child_render_scripts_write_expected_html(self):
        child_root = ROOT / "amz-market-research-orchestrated" / "child_skills"
        scripts = [
            ("market-depth-report", "render_market_depth_report.py", "market_depth_view.json", "market-depth-report.html", "template-market", "大盘仪表盘 · Market Dashboard"),
            ("lifecycle-strategy-report", "render_lifecycle_strategy_report.py", "lifecycle_strategy_view.json", "lifecycle-strategy-report.html", "template-lifecycle", "生命周期旅程"),
            ("demand-gap-report", "render_demand_gap_report.py", "demand_gap_view.json", "demand-gap-report.html", "template-demand mode-r3", "KANO × JTBD"),
        ]
        view_model = {
            "kpis": [{"label": "核心判断", "value": "Watch", "subtext": "Go / Watch / No-Go"}],
            "charts": {},
            "tables": {"sample": [{"维度": "证据强度", "建议动作": "继续验证"}]},
            "cards": {},
            "evidence_strength": "中",
            "sample_coverage": {"keywords": 1000},
            "limitations": ["评论样本需要补充"],
            "client_safe_text": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            for _, _, view_file, _, _, _ in scripts:
                path = report_dir / "analysis" / view_file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(view_model, ensure_ascii=False), encoding="utf-8")
            for module_name, script_file, _, output_file, template_class, required_section in scripts:
                script = child_root / module_name / "scripts" / script_file
                result = subprocess.run([sys.executable, str(script), "--dir", str(report_dir)], text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                html_path = report_dir / "output" / "html_reports" / output_file
                self.assertTrue(html_path.exists(), output_file)
                html = html_path.read_text(encoding="utf-8")
                self.assertIn(f'class="{template_class}"', html)
                self.assertNotIn("site-nav", html)
                self.assertIn('href="assets/report.css"', html)
                self.assertIn('src="assets/report.js"', html)
                self.assertIn(required_section, html)
                if output_file != "market-depth-report.html":
                    self.assertIn("证据强度", html)
                self.assertNotIn("source_id", html)
            self.assertTrue((report_dir / "output" / "html_reports" / "assets" / "report.css").exists())
            self.assertTrue((report_dir / "output" / "html_reports" / "assets" / "report.js").exists())

    def test_child_renderer_does_not_silently_fallback_when_canonical_render_fails(self):
        child_root = ROOT / "amz-market-research-orchestrated" / "child_skills"
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            view_path = report_dir / "analysis" / "demand_gap_view.json"
            view_path.parent.mkdir(parents=True, exist_ok=True)
            view_path.write_text(json.dumps({"kpis": [], "tables": {}, "limitations": []}, ensure_ascii=False), encoding="utf-8")

            with patch("report_renderers.build_report_documents", side_effect=RuntimeError("canonical exploded")):
                with self.assertRaisesRegex(RuntimeError, "demand_gap child renderer failed to reuse canonical template"):
                    child_report_renderer.render_child_report(
                        report_dir,
                        child_root / "demand-gap-report",
                        "demand_gap_view.json",
                        "demand-gap-report.html",
                        "用户心智断层与需求机会报告",
                        "{{DEMAND_REPORT_TITLE}}",
                        "{{DEMAND_GAP_REPORT_BODY}}",
                    )

            html_path = report_dir / "output" / "html_reports" / "demand-gap-report.html"
            self.assertFalse(html_path.exists())


if __name__ == "__main__":
    unittest.main()
