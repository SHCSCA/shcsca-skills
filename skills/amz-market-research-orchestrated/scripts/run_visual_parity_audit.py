#!/usr/bin/env python3
"""Run browser-based visual parity smoke checks for rendered HTML reports."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


PLAYWRIGHT_SPEC = r"""
const { test, expect } = require('playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const reportDir = process.env.REPORT_DIR;
const outDir = process.env.VISUAL_AUDIT_OUT;
if (!reportDir) throw new Error('REPORT_DIR is required');
if (!outDir) throw new Error('VISUAL_AUDIT_OUT is required');
fs.mkdirSync(outDir, { recursive: true });

const pages = [
  { name: 'report.html', key: 'index', minText: 300, selector: 'html[data-report-style="three-report-index-v2"]' },
  { name: 'market-depth-report.html', key: 'market_depth', minText: 1000, selector: 'html[data-report-style="market-depth-report-v2"]' },
  { name: 'lifecycle-strategy-report.html', key: 'lifecycle_strategy', minText: 1000, selector: 'body.template-lifecycle' },
  { name: 'demand-gap-report.html', key: 'demand_gap', minText: 1000, selector: 'body.template-demand' },
];

const viewports = [
  { key: 'desktop', width: 1366, height: 900 },
  { key: 'mobile', width: 390, height: 844 },
];

function reportUrl(name) {
  return pathToFileURL(path.resolve(reportDir, 'output/html_reports', name)).href;
}

test('real report visual parity audit', async ({ page }) => {
  const results = [];
  const errors = [];
  const failures = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));

  for (const report of pages) {
    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(reportUrl(report.name), { waitUntil: 'networkidle' });
      if (report.key === 'index') {
        await expect(page.locator('.site-nav')).toHaveCount(1);
        await expect(page.locator('.site-nav')).toBeVisible();
      } else {
        await expect(page.locator('.site-nav')).toHaveCount(0);
      }
      await expect(page.locator('h1').first()).toBeVisible();
      await expect(page.locator(report.selector)).toHaveCount(1);
      const metrics = await page.evaluate(() => {
        const text = document.body.innerText || '';
        const requiredSelectors = [
          '.report-header',
          '.kpi-grid',
          '.chart-container',
          '.evidence-table',
          '.filter-bar',
          '[data-tabs]',
          '.evidence-drawer',
          '.mini-chart .bar-row',
        ];
        const selectorCounts = {};
        for (const selector of requiredSelectors) {
          selectorCounts[selector] = document.querySelectorAll(selector).length;
        }
        return {
          title: document.querySelector('h1')?.innerText || '',
          textLength: text.length,
          scrollOverflow: document.documentElement.scrollWidth - window.innerWidth,
          sections: document.querySelectorAll('section,.section,.sec').length,
          tables: document.querySelectorAll('table').length,
          selectorCounts,
        };
      });
      const screenshotName = `${report.key}-${viewport.key}.png`;
      const screenshotPath = path.join(outDir, screenshotName);
      await page.screenshot({ path: screenshotPath, fullPage: false });
      const screenshotBytes = fs.statSync(screenshotPath).size;
      if (metrics.textLength <= report.minText) failures.push(`${report.key}/${viewport.key}: text density ${metrics.textLength} <= ${report.minText}`);
      if (metrics.scrollOverflow > 8) failures.push(`${report.key}/${viewport.key}: horizontal overflow ${metrics.scrollOverflow}`);
      if (report.key !== 'index' && metrics.sections < 7) failures.push(`${report.key}/${viewport.key}: sections ${metrics.sections} < 7`);
      const minTables = report.key === 'market_depth' ? 1 : 3;
      if (report.key !== 'index' && metrics.tables < minTables) failures.push(`${report.key}/${viewport.key}: tables ${metrics.tables} < ${minTables}`);
      if (screenshotBytes <= 10000) failures.push(`${report.key}/${viewport.key}: screenshot bytes ${screenshotBytes} <= 10000`);
      results.push({ report: report.key, viewport: viewport.key, screenshot: screenshotName, screenshotBytes, metrics });
    }
  }
  fs.writeFileSync(path.join(outDir, 'visual-parity-results.json'), JSON.stringify(results, null, 2));
  fs.writeFileSync(path.join(outDir, 'visual-parity-failures.json'), JSON.stringify({ errors, failures }, null, 2));
  expect(errors).toEqual([]);
  expect(failures).toEqual([]);
});
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Visual Parity Audit",
        "",
        f"- report_dir: `{audit['report_dir']}`",
        f"- checked_at: `{audit['checked_at']}`",
        f"- overall_pass: `{str(audit['overall_pass']).lower()}`",
        f"- output_dir: `{audit['output_dir']}`",
        "",
        "## Screenshots",
        "",
        "| Report | Viewport | Screenshot | Bytes | Sections | Tables | Overflow |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for item in audit.get("results") or []:
        metrics = item.get("metrics") or {}
        lines.append(
            f"| `{item.get('report')}` | `{item.get('viewport')}` | `{item.get('screenshot')}` | "
            f"{item.get('screenshotBytes')} | {metrics.get('sections')} | {metrics.get('tables')} | {metrics.get('scrollOverflow')} |"
        )
    if audit.get("stderr"):
        lines.extend(["", "## stderr", "", "```text", str(audit["stderr"])[:4000], "```"])
    return "\n".join(lines) + "\n"


def run_audit(report_dir: Path, out_dir: Path | None = None) -> dict[str, Any]:
    report_dir = report_dir.resolve()
    out_dir = (out_dir or (report_dir / "output" / "visual_parity_audit")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    npx = shutil.which("npx")
    if not npx:
        audit = {
            "report_dir": str(report_dir),
            "checked_at": utc_now(),
            "overall_pass": False,
            "output_dir": str(out_dir),
            "error": "npx executable not available",
            "results": [],
        }
        write_json(out_dir / "visual_parity_audit.json", audit)
        (out_dir / "visual_parity_audit.md").write_text(markdown(audit), encoding="utf-8")
        return audit

    spec_path = SCRIPT_DIR / "tmp_visual_parity.spec.js"
    spec_path.write_text(textwrap.dedent(PLAYWRIGHT_SPEC).strip() + "\n", encoding="utf-8")
    env = dict(os.environ, REPORT_DIR=str(report_dir), VISUAL_AUDIT_OUT=str(out_dir))
    try:
        result = subprocess.run(
            [npx, "--yes", "playwright", "test", spec_path.name, "--reporter=line", "--workers=1"],
            text=True,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(SCRIPT_DIR),
            timeout=240,
        )
    finally:
        spec_path.unlink(missing_ok=True)

    results_path = out_dir / "visual-parity-results.json"
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    failures_path = out_dir / "visual-parity-failures.json"
    failures = json.loads(failures_path.read_text(encoding="utf-8")) if failures_path.exists() else {}
    audit = {
        "report_dir": str(report_dir),
        "checked_at": utc_now(),
        "overall_pass": result.returncode == 0,
        "output_dir": str(out_dir),
        "results": results,
        "failures": failures.get("failures") or [],
        "browser_errors": failures.get("errors") or [],
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    write_json(out_dir / "visual_parity_audit.json", audit)
    (out_dir / "visual_parity_audit.md").write_text(markdown(audit), encoding="utf-8")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run browser screenshot parity checks for a rendered report directory.")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    audit = run_audit(args.dir, args.out)
    print(json.dumps({"overall_pass": audit["overall_pass"], "audit": str(Path(audit["output_dir"]) / "visual_parity_audit.json")}, ensure_ascii=False))
    return 0 if audit["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
