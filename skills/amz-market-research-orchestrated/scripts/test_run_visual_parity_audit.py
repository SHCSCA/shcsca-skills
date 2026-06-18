#!/usr/bin/env python3
import unittest

import run_visual_parity_audit as visual_audit


class VisualParityAuditTest(unittest.TestCase):
    def test_playwright_spec_ignores_external_image_resource_errors_only(self):
        spec = visual_audit.PLAYWRIGHT_SPEC

        self.assertIn("isImageResourceError", spec)
        self.assertIn("status of (400|403|404)", spec)
        self.assertIn("!isImageResourceError", spec)
        self.assertIn("page.on('pageerror'", spec)


if __name__ == "__main__":
    unittest.main()
