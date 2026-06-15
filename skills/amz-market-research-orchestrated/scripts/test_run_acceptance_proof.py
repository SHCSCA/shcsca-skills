#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_acceptance_proof as proof_runner


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class RunAcceptanceProofTest(unittest.TestCase):
    def test_run_proof_writes_json_and_markdown_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "output" / "delivery_result.json", {"status": "complete", "decision": "Watch"})
            write_json(report_dir / "analysis" / "critic_review.json", {"pass": True, "score": 86})

            def fake_step(name, _command, _cwd):
                if name in {"readiness", "readiness_after_recovery"}:
                    write_json(
                        report_dir / "data" / "normalized" / "data_readiness_report.json",
                        {
                            "acceptance_ready": True,
                            "sample_class": "acceptance_sample",
                            "blocking_gaps": [],
                            "warnings": [],
                        },
                    )
                return {"name": name, "command": [], "returncode": 0, "stdout": "", "stderr": "", "pass": True}

            with patch.object(proof_runner, "run_step", side_effect=fake_step):
                proof = proof_runner.run_proof(report_dir, "standard")

            self.assertTrue(proof["overall_pass"])
            self.assertEqual(proof["sample_class"], "acceptance_sample")
            self.assertEqual([step["name"] for step in proof["steps"]], ["template_parity", "readiness", "render", "validate"])
            self.assertTrue((report_dir / "output" / "acceptance_proof.json").exists())
            markdown = (report_dir / "output" / "acceptance_proof.md").read_text(encoding="utf-8")
            self.assertIn("# Acceptance Proof", markdown)
            self.assertIn("acceptance_ready", markdown)

    def test_failed_readiness_ignores_stale_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "output" / "delivery_result.json", {"status": "complete", "decision": "Go"})
            write_json(report_dir / "analysis" / "critic_review.json", {"pass": True, "score": 92})

            def fake_step(name, _command, _cwd):
                if name in {"readiness", "readiness_after_recovery"}:
                    write_json(
                        report_dir / "data" / "normalized" / "data_readiness_report.json",
                        {
                            "acceptance_ready": False,
                            "sample_class": "non_acceptance_sample",
                            "blocking_gaps": [{"module": "keyword_sample_depth"}],
                            "warnings": [],
                        },
                    )
                    return {"name": name, "command": [], "returncode": 2, "stdout": "", "stderr": "", "pass": False}
                if name == "readiness_recovery":
                    return {"name": name, "command": [], "returncode": 2, "stdout": "", "stderr": "", "pass": False}
                return {"name": name, "command": [], "returncode": 0, "stdout": "", "stderr": "", "pass": True}

            with patch.object(proof_runner, "run_step", side_effect=fake_step):
                proof = proof_runner.run_proof(report_dir, "standard")

            self.assertFalse(proof["overall_pass"])
            self.assertEqual(proof["sample_class"], "non_acceptance_sample")
            self.assertIsNone(proof["delivery_status"])
            self.assertIsNone(proof["critic_pass"])
            self.assertTrue(proof["stale_delivery_ignored"])
            self.assertEqual([step["name"] for step in proof["steps"]], ["template_parity", "readiness", "readiness_recovery", "readiness_after_recovery"])

    def test_partial_diagnostic_delivery_can_pass_without_full_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "output" / "delivery_result.json", {"status": "complete", "decision": "Watch"})
            write_json(report_dir / "analysis" / "critic_review.json", {"pass": True, "score": 82})

            def fake_step(name, _command, _cwd):
                if name in {"readiness", "readiness_after_recovery"}:
                    write_json(
                        report_dir / "data" / "normalized" / "data_readiness_report.json",
                        {
                            "acceptance_ready": False,
                            "partial_report_ready": True,
                            "sample_class": "partial_acceptance_sample",
                            "supply_conclusion_blocked": True,
                            "blocking_gaps": [
                                {
                                    "module": "supplier_quote_relevance",
                                    "reason": "1688 严格相关报价不足 50 条，供应链毛利率必须诊断交付。",
                                }
                            ],
                            "warnings": [],
                        },
                    )
                    return {"name": name, "command": [], "returncode": 2, "stdout": "", "stderr": "", "pass": False}
                if name == "readiness_recovery":
                    return {"name": name, "command": [], "returncode": 0, "stdout": "", "stderr": "", "pass": True}
                return {"name": name, "command": [], "returncode": 0, "stdout": "", "stderr": "", "pass": True}

            with patch.object(proof_runner, "run_step", side_effect=fake_step):
                proof = proof_runner.run_proof(report_dir, "deep")

            self.assertTrue(proof["overall_pass"])
            self.assertFalse(proof["full_acceptance_pass"])
            self.assertTrue(proof["diagnostic_delivery_pass"])
            self.assertEqual(proof["delivery_mode"], "diagnostic_delivery")
            markdown = (report_dir / "output" / "acceptance_proof.md").read_text(encoding="utf-8")
            self.assertIn("Delivery mode: `diagnostic_delivery`", markdown)
            self.assertIn("full_acceptance_pass: `False`", markdown)

    def test_critic_failure_blocks_overall_pass_even_when_steps_succeed(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "output" / "delivery_result.json", {"status": "complete", "decision": "Watch"})
            write_json(report_dir / "analysis" / "critic_review.json", {"pass": False, "score": 55, "grade": "D"})

            def fake_step(name, _command, _cwd):
                if name in {"readiness", "readiness_after_recovery"}:
                    write_json(
                        report_dir / "data" / "normalized" / "data_readiness_report.json",
                        {
                            "acceptance_ready": True,
                            "sample_class": "acceptance_sample",
                            "blocking_gaps": [],
                            "warnings": [],
                        },
                    )
                return {"name": name, "command": [], "returncode": 0, "stdout": "", "stderr": "", "pass": True}

            with patch.object(proof_runner, "run_step", side_effect=fake_step):
                proof = proof_runner.run_proof(report_dir, "standard")

            self.assertFalse(proof["overall_pass"])
            self.assertFalse(proof["critic_pass"])
            self.assertTrue(proof["readiness"]["acceptance_ready"])

    def test_reference_visual_compare_can_be_added_to_acceptance_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            download_root = Path(tmp) / "downloadpage"
            write_json(report_dir / "output" / "delivery_result.json", {"status": "complete", "decision": "Watch"})
            write_json(report_dir / "analysis" / "critic_review.json", {"pass": True, "score": 86})

            def fake_step(name, command, _cwd):
                if name in {"readiness", "readiness_after_recovery"}:
                    write_json(
                        report_dir / "data" / "normalized" / "data_readiness_report.json",
                        {
                            "acceptance_ready": True,
                            "sample_class": "acceptance_sample",
                            "blocking_gaps": [],
                            "warnings": [],
                        },
                    )
                if name == "reference_visual_compare":
                    self.assertIn("--download-root", command)
                    self.assertIn(str(download_root), command)
                    write_json(
                        report_dir / "output" / "template_reference_visual_compare" / "template_reference_visual_compare.json",
                        {"overall_pass": True},
                    )
                return {"name": name, "command": command, "returncode": 0, "stdout": "", "stderr": "", "pass": True}

            with patch.object(proof_runner, "run_step", side_effect=fake_step):
                proof = proof_runner.run_proof(report_dir, "standard", reference_visual=True, download_root=download_root)

            self.assertTrue(proof["overall_pass"])
            self.assertEqual(
                [step["name"] for step in proof["steps"]],
                ["template_parity", "readiness", "render", "validate", "reference_visual_compare"],
            )
            self.assertEqual(proof["reference_visual_compare"], "output/template_reference_visual_compare/template_reference_visual_compare.json")
            markdown = (report_dir / "output" / "acceptance_proof.md").read_text(encoding="utf-8")
            self.assertIn("Template Reference Visual Compare", markdown)
            self.assertIn("template_reference_visual_compare.json", markdown)


if __name__ == "__main__":
    unittest.main()
