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
    const text = msg.text();
    const isImageResourceError = text.includes('Failed to load resource') && /status of (400|403|404)/.test(text);
    if (msg.type() === 'error' && !isImageResourceError) errors.push(text);
  });
  page.on('pageerror', err => errors.push(err.message));
  await page.setViewportSize({ width, height });
  await page.goto(reportUrl(name), { waitUntil: 'networkidle' });
  await expect(page.locator('.site-nav')).toHaveCount(1);
  await expect(page.locator('.site-nav')).toBeVisible();
  await expect(page.locator('h1').first()).toBeVisible();
  await expect(page.locator('body')).not.toContainText('图片加载失败');
  expect(errors).toEqual([]);
}

async function expectEchartsRendered(page, ids) {
  for (const id of ids) {
    await page.waitForFunction((chartId) => {
      const el = document.getElementById(chartId);
      if (!el) return false;
      const rendered = el.querySelector('canvas,svg');
      return !!rendered && el.clientWidth > 0 && el.clientHeight > 0;
    }, id);
  }
}

test('static bundle links navigate and render visible report pages', async ({ page }) => {
  const chartIds = {
    'market-depth-report.html': ['priceChart', 'bubbleChart', 'growthChart', 'featureChart', 'radarChart', 'marginChart'],
    'lifecycle-strategy-report.html': ['sunburst', 'priorityChart', 'aovChart'],
    'demand-gap-report.html': ['appealsRose', 'gapRadar']
  };
  for (const href of Object.keys(chartIds)) {
    await openReport(page, 'report.html');
    await page.click(`a[href="${href}"]`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.site-nav')).toHaveCount(1);
    await expect(page.locator('h1').first()).toBeVisible();
    await expect(page.locator('table:visible').first()).toBeVisible();
    await expectEchartsRendered(page, chartIds[href]);
  }
});

test('desktop interactions work on child reports', async ({ page }) => {
  await openReport(page, 'market-depth-report.html');
  await expect(page.locator('.table-tools').first()).toBeVisible();
  await expect(page.locator('body')).toHaveClass(/template-market/);
  await expect(page.locator('.section-title', { hasText: '建议定价策略' })).toBeVisible();
  await expect(page.locator('.pricing-card.recommended')).toBeVisible();
  await expect(page.locator('.comp-table').first()).toBeVisible();
  const marketSearch = page.locator('.table-tools:visible input[type="search"]').first();
  await marketSearch.fill('zzzz-no-match');
  const marketRowsAfterFilter = await marketSearch.evaluate(input => {
    const table = input.closest('.table-tools')?.nextElementSibling;
    return table ? table.querySelectorAll('tbody tr:not(.is-filtered-out)').length : -1;
  });
  expect(marketRowsAfterFilter).toBe(0);
  await openReport(page, 'lifecycle-strategy-report.html');
  const search = page.locator('.table-tools:visible input[type="search"]').first();
  await expect(search).toBeVisible();
  await search.fill('zzzz-no-match');
  const visibleRowsAfterFilter = await search.evaluate(input => {
    const table = input.closest('.table-tools')?.nextElementSibling;
    return table ? table.querySelectorAll('tbody tr:not(.is-filtered-out)').length : -1;
  });
  expect(visibleRowsAfterFilter).toBe(0);
  await search.fill('');
  const filterButton = page.locator('.filter-bar .filter-btn[data-filter]').nth(1);
  if (await filterButton.count()) {
    await filterButton.click();
    await expect(filterButton).toHaveAttribute('aria-pressed', 'true');
  }
  const firstHeader = page.locator('th[data-sortable]:visible').first();
  await expect(firstHeader).toBeVisible();
  await firstHeader.click();
  await expect(firstHeader).toHaveAttribute('data-sort-dir', 'asc');
  const tab = page.locator('[data-tab-target]').nth(1);
  if (await tab.count()) {
    await tab.click();
    await expect(tab).toHaveAttribute('aria-selected', 'true');
  }
  const bar = page.locator('.mini-chart .bar-row').first();
  if (await bar.count()) {
    await bar.hover();
    await expect(bar).toHaveClass(/is-linked/);
  }
});

test('mobile navigation and screenshots are nonblank', async ({ page }) => {
  await openReport(page, 'report.html', 390, 844);
  const toggle = page.locator('.site-nav-toggle');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.locator('.site-nav')).toHaveClass(/is-open/);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(8);
  const shot = await page.screenshot({ fullPage: false });
  expect(shot.length).toBeGreaterThan(10000);
  const visibleText = await page.locator('body').innerText();
  expect(visibleText.length).toBeGreaterThan(700);
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
