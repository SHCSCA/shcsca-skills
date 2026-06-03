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
                if name == "readiness":
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
            self.assertEqual([step["name"] for step in proof["steps"]], ["readiness", "render", "validate"])
            self.assertTrue((report_dir / "output" / "acceptance_proof.json").exists())
            markdown = (report_dir / "output" / "acceptance_proof.md").read_text(encoding="utf-8")
            self.assertIn("# Acceptance Proof", markdown)
            self.assertIn("acceptance_ready", markdown)


if __name__ == "__main__":
    unittest.main()
