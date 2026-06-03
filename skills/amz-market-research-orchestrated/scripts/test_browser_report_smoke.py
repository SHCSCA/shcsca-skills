#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from test_render_dashboard_html import make_renderable_report


SCRIPT_DIR = Path(__file__).resolve().parent
RENDERER = SCRIPT_DIR / "render_dashboard_html.py"


PLAYWRIGHT_SPEC = r"""
const { test, expect } = require('playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const reportDir = process.env.REPORT_DIR;
if (!reportDir) throw new Error('REPORT_DIR is required');

function reportUrl(name) {
  return pathToFileURL(path.resolve(reportDir, 'output/html_reports', name)).href;
}

async function openReport(page, name, width = 1280, height = 900) {
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));
  await page.setViewportSize({ width, height });
  await page.goto(reportUrl(name), { waitUntil: 'networkidle' });
  await expect(page.locator('.site-nav')).toBeVisible();
  await expect(page.locator('h1').first()).toBeVisible();
  expect(errors).toEqual([]);
}

test('static bundle links navigate and render visible report pages', async ({ page }) => {
  await openReport(page, 'report.html');
  for (const href of ['market-depth-report.html', 'lifecycle-strategy-report.html', 'demand-gap-report.html']) {
    await page.click(`a[href="${href}"]`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.site-nav')).toBeVisible();
    await expect(page.locator('h1').first()).toBeVisible();
    await expect(page.locator('table').first()).toBeVisible();
  }
});

test('desktop interactions work on child reports', async ({ page }) => {
  await openReport(page, 'market-depth-report.html');
  const filterable = page.locator('.filterable-table').first();
  await expect(filterable).toBeVisible();
  const search = filterable.locator('.table-tools input[type="search"]').first();
  await expect(search).toBeVisible();
  await search.fill('zzzz-no-match');
  const visibleRowsAfterFilter = await search.evaluate(input => {
    const table = input.closest('.table-tools')?.nextElementSibling;
    return table ? table.querySelectorAll('tbody tr:not(.is-filtered-out)').length : -1;
  });
  expect(visibleRowsAfterFilter).toBe(0);
  await search.fill('');
  const filterButton = filterable.locator('.filter-bar .filter-btn[data-filter="高相关"]').first();
  await expect(filterButton).toBeVisible();
  await filterButton.click();
  await expect(filterButton).toHaveAttribute('aria-pressed', 'true');
  const filteredState = await filterButton.evaluate(button => {
    const table = button.closest('.filterable-table')?.querySelector('table');
    const rows = [...table.querySelectorAll('tbody tr')];
    return {
      visible: rows.filter(row => !row.classList.contains('is-filtered-out')).map(row => row.dataset.filter || ''),
      hidden: rows.filter(row => row.classList.contains('is-filtered-out')).map(row => row.dataset.filter || '')
    };
  });
  expect(filteredState.visible.length).toBeGreaterThan(0);
  expect(filteredState.visible.every(value => value.includes('高相关'))).toBeTruthy();
  expect(filteredState.hidden.some(value => !value.includes('高相关'))).toBeTruthy();
  await search.fill('zzzz-no-match');
  const combinedVisible = await filterButton.evaluate(button => {
    const table = button.closest('.filterable-table')?.querySelector('table');
    return table.querySelectorAll('tbody tr:not(.is-filtered-out)').length;
  });
  expect(combinedVisible).toBe(0);
  await search.fill('');
  const firstHeader = page.locator('th[data-sortable]').first();
  await expect(firstHeader).toBeVisible();
  await firstHeader.click();
  await expect(firstHeader).toHaveAttribute('data-sort-dir', 'asc');
  const tab = page.locator('[data-tab-target]').nth(1);
  if (await tab.count()) {
    await tab.click();
    await expect(tab).toHaveAttribute('aria-selected', 'true');
  }
  const drawer = page.locator('.evidence-drawer').first();
  await expect(drawer).toBeVisible();
  const bar = page.locator('.mini-chart .bar-row').first();
  if (await bar.count()) {
    await bar.hover();
    await expect(bar).toHaveClass(/is-linked/);
  }
});

test('mobile navigation and screenshots are nonblank', async ({ page }) => {
  await openReport(page, 'demand-gap-report.html', 390, 844);
  const toggle = page.locator('.site-nav-toggle');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.locator('.site-nav')).toHaveClass(/is-open/);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(8);
  const shot = await page.screenshot({ fullPage: false });
  expect(shot.length).toBeGreaterThan(10000);
  const visibleText = await page.locator('body').innerText();
  expect(visibleText.length).toBeGreaterThan(1000);
});
"""


class BrowserReportSmokeTest(unittest.TestCase):
    def test_static_reports_pass_real_browser_smoke(self):
        npx = shutil.which("npx")
        if not npx:
            self.skipTest("npx executable not available")
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "report"
            make_renderable_report(report_dir)
            render = subprocess.run(
                [sys.executable, str(RENDERER), "--dir", str(report_dir)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stderr + render.stdout)
            spec_path = SCRIPT_DIR / "tmp_browser_report_smoke.spec.js"
            spec_path.write_text(textwrap.dedent(PLAYWRIGHT_SPEC).strip() + "\n", encoding="utf-8")
            try:
                env = dict(**__import__("os").environ, REPORT_DIR=str(report_dir))
                result = subprocess.run(
                    [npx, "--yes", "playwright", "test", spec_path.name, "--reporter=line", "--workers=1"],
                    text=True,
                    capture_output=True,
                    check=False,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    cwd=SCRIPT_DIR,
                    timeout=180,
                )
            finally:
                spec_path.unlink(missing_ok=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
