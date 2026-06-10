#!/usr/bin/env python3
"""Compare rendered reports against the downloaded reference HTML templates."""

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
DEFAULT_DOWNLOAD_ROOT = Path(r"C:\Users\wz\Downloads\downloadpage")

REPORT_CASES = {
    "market_depth": {
        "folder": "143101",
        "generated": "market-depth-report.html",
        "min_text": 1000,
        "must_exist": [
            ".comp-table",
            ".comp-deep-grid",
            ".pricing-grid",
            ".prompt-grid",
            ".supply-grid",
            ".kpi-grid",
        ],
        "reference_signals": [
            ".comp-table",
            ".comp-deep-grid",
            ".pricing-grid",
            ".prompt-grid",
            ".supply-grid",
            ".kpi-grid",
            ".chart-container",
        ],
        "box_selectors": [".comp-table", ".pricing-grid", ".prompt-grid", ".supply-grid"],
    },
    "lifecycle_strategy": {
        "folder": "143511",
        "generated": "lifecycle-strategy-report.html",
        "min_text": 1000,
        "must_exist": [
            ".persona-grid",
            ".timeline-grid",
            ".sku-strategy-grid",
            ".bundle-grid",
            ".phase-grid",
            ".risk-grid",
            ".filter-bar",
            ".sku-table-wrap",
        ],
        "reference_signals": [
            ".persona-grid",
            ".timeline-grid",
            ".bundle-grid",
            ".phase-grid",
            ".risk-grid",
            ".filter-bar",
            ".filter-btn",
            ".kpi-grid",
            ".chart",
        ],
        "box_selectors": [".bundle-grid", ".phase-grid", ".risk-grid", ".kpi-grid"],
    },
    "demand_gap": {
        "folder": "143645",
        "generated": "demand-gap-report.html",
        "min_text": 1000,
        "must_exist": [
            ".kpi-grid",
            ".chart",
            ".focus",
            ".warn",
            ".ok",
            ".demand-sentiment-columns",
            ".demand-evidence-card",
        ],
        "reference_signals": [
            ".kpi-grid",
            ".chart",
            ".focus",
            ".warn",
            ".ok",
            ".quote-cn",
            ".quote-origin",
        ],
        "box_selectors": [".kpi-grid", ".focus", ".warn", ".ok"],
    },
}

PLAYWRIGHT_SPEC = r"""
const { test, expect } = require('playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const reportDir = process.env.REPORT_DIR;
const outDir = process.env.REFERENCE_COMPARE_OUT;
const cases = JSON.parse(process.env.REFERENCE_COMPARE_CASES || '{}');
if (!reportDir) throw new Error('REPORT_DIR is required');
if (!outDir) throw new Error('REFERENCE_COMPARE_OUT is required');
fs.mkdirSync(outDir, { recursive: true });

const viewports = [
  { key: 'pc-1366', width: 1366, height: 900 },
  { key: 'pc-1440', width: 1440, height: 900 },
];

function fileUrl(filePath) {
  return pathToFileURL(path.resolve(filePath)).href;
}

function generatedUrl(name) {
  return fileUrl(path.resolve(reportDir, 'output/html_reports', name));
}

async function collectMetrics(page, selectors, boxSelectors) {
  return await page.evaluate(({ selectors, boxSelectors }) => {
    const selectorCounts = {};
    const boxes = {};
    for (const selector of selectors) {
      selectorCounts[selector] = document.querySelectorAll(selector).length;
    }
    for (const selector of boxSelectors) {
      const node = document.querySelector(selector);
      if (!node) {
        boxes[selector] = null;
        continue;
      }
      const rect = node.getBoundingClientRect();
      boxes[selector] = {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    }
    const style = getComputedStyle(document.body);
    return {
      title: document.querySelector('h1')?.innerText || document.title || '',
      textLength: (document.body.innerText || '').length,
      scrollOverflow: document.documentElement.scrollWidth - window.innerWidth,
      sections: document.querySelectorAll('section,.section,.sec').length,
      tables: document.querySelectorAll('table').length,
      bodyClass: document.body.className || '',
      backgroundColor: style.backgroundColor,
      selectorCounts,
      boxes,
    };
  }, { selectors, boxSelectors });
}

function imageDataUrl(filePath) {
  return `data:image/png;base64,${fs.readFileSync(filePath).toString('base64')}`;
}

async function screenshotDistance(page, referencePath, generatedPath) {
  return await page.evaluate(async ({ referenceImage, generatedImage }) => {
    const load = src => new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('screenshot image load failed'));
      img.src = src;
    });
    const [reference, generated] = await Promise.all([load(referenceImage), load(generatedImage)]);
    const width = 160;
    const height = 100;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(reference, 0, 0, width, height);
    const refPixels = ctx.getImageData(0, 0, width, height).data;
    ctx.clearRect(0, 0, width, height);
    ctx.drawImage(generated, 0, 0, width, height);
    const genPixels = ctx.getImageData(0, 0, width, height).data;
    let total = 0;
    for (let idx = 0; idx < refPixels.length; idx += 4) {
      total += Math.abs(refPixels[idx] - genPixels[idx]);
      total += Math.abs(refPixels[idx + 1] - genPixels[idx + 1]);
      total += Math.abs(refPixels[idx + 2] - genPixels[idx + 2]);
    }
    return total / ((refPixels.length / 4) * 255 * 3);
  }, { referenceImage: imageDataUrl(referencePath), generatedImage: imageDataUrl(generatedPath) });
}

function compareCase(caseKey, viewport, spec, refMetrics, genMetrics, refBytes, genBytes, pixelDistance) {
  const failures = [];
  if (refBytes <= 10000) failures.push(`${caseKey}/${viewport}: reference screenshot is too small (${refBytes})`);
  if (genBytes <= 10000) failures.push(`${caseKey}/${viewport}: generated screenshot is too small (${genBytes})`);
  const screenshotByteRatio = refBytes > 0 ? genBytes / refBytes : 0;
  if (screenshotByteRatio < 0.45 || screenshotByteRatio > 2.20) {
    failures.push(`${caseKey}/${viewport}: screenshot byte ratio ${screenshotByteRatio.toFixed(2)} outside 0.45-2.20`);
  }
  const maxPixelDistance = spec.max_pixel_distance || 0.16;
  if (pixelDistance > maxPixelDistance) {
    failures.push(`${caseKey}/${viewport}: pixel distance ${pixelDistance.toFixed(3)} > ${maxPixelDistance.toFixed(3)}`);
  }
  if (genMetrics.textLength <= spec.min_text) failures.push(`${caseKey}/${viewport}: generated text length ${genMetrics.textLength} <= ${spec.min_text}`);
  if (genMetrics.scrollOverflow > 8) failures.push(`${caseKey}/${viewport}: generated horizontal overflow ${genMetrics.scrollOverflow}`);
  if (refMetrics.backgroundColor !== genMetrics.backgroundColor) {
    failures.push(`${caseKey}/${viewport}: body background differs from reference (${refMetrics.backgroundColor} vs ${genMetrics.backgroundColor})`);
  }
  if (refMetrics.sections > 0 && genMetrics.sections < Math.max(1, Math.floor(refMetrics.sections * 0.85))) {
    failures.push(`${caseKey}/${viewport}: generated section count ${genMetrics.sections} below reference-compatible floor ${refMetrics.sections}`);
  }
  for (const selector of spec.must_exist || []) {
    if ((genMetrics.selectorCounts[selector] || 0) <= 0) failures.push(`${caseKey}/${viewport}: generated missing required selector ${selector}`);
  }
  const comparedSignals = [];
  const matchedSignals = [];
  for (const selector of spec.reference_signals || []) {
    const refCount = refMetrics.selectorCounts[selector] || 0;
    const genCount = genMetrics.selectorCounts[selector] || 0;
    if (refCount <= 0) continue;
    comparedSignals.push(selector);
    if (genCount > 0) matchedSignals.push(selector);
  }
  const signalScore = comparedSignals.length ? matchedSignals.length / comparedSignals.length : 1;
  if (signalScore < 0.7) {
    failures.push(`${caseKey}/${viewport}: reference signal score ${signalScore.toFixed(2)} < 0.70; matched ${matchedSignals.length}/${comparedSignals.length}`);
  }
  const comparedBoxes = [];
  const matchedBoxes = [];
  const boxDetails = {};
  for (const selector of spec.box_selectors || []) {
    const refBox = refMetrics.boxes[selector];
    const genBox = genMetrics.boxes[selector];
    if (!refBox) continue;
    comparedBoxes.push(selector);
    if (!genBox || refBox.width <= 0 || refBox.height <= 0 || genBox.width <= 0 || genBox.height <= 0) {
      failures.push(`${caseKey}/${viewport}: generated missing reference layout box ${selector}`);
      continue;
    }
    const widthRatio = genBox.width / refBox.width;
    const leftDelta = Math.abs(genBox.x - refBox.x);
    const centerDelta = Math.abs((genBox.x + genBox.width / 2) - (refBox.x + refBox.width / 2));
    boxDetails[selector] = { widthRatio, leftDelta, centerDelta };
    if (widthRatio < 0.82 || widthRatio > 1.18) {
      failures.push(`${caseKey}/${viewport}: ${selector} width ratio ${widthRatio.toFixed(2)} outside 0.82-1.18`);
    }
    if (leftDelta > 110) {
      failures.push(`${caseKey}/${viewport}: ${selector} left delta ${leftDelta.toFixed(0)}px > 110px`);
    }
    if (centerDelta > 110) {
      failures.push(`${caseKey}/${viewport}: ${selector} center delta ${centerDelta.toFixed(0)}px > 110px`);
    }
    matchedBoxes.push(selector);
  }
  const layoutScore = comparedBoxes.length ? matchedBoxes.length / comparedBoxes.length : 1;
  if (layoutScore < 1) failures.push(`${caseKey}/${viewport}: layout box score ${layoutScore.toFixed(2)} < 1.00`);
  return { failures, signalScore, comparedSignals, matchedSignals, layoutScore, comparedBoxes, matchedBoxes, boxDetails, screenshotByteRatio, pixelDistance };
}

test('reference template visual comparison', async ({ browser }) => {
  const context = await browser.newContext();
  const results = [];
  const failures = [];
  for (const [caseKey, spec] of Object.entries(cases)) {
    for (const viewport of viewports) {
      const refPage = await context.newPage();
      const genPage = await context.newPage();
      await refPage.setViewportSize({ width: viewport.width, height: viewport.height });
      await genPage.setViewportSize({ width: viewport.width, height: viewport.height });
      await refPage.goto(fileUrl(spec.reference_html), { waitUntil: 'networkidle' });
      await genPage.goto(generatedUrl(spec.generated), { waitUntil: 'networkidle' });
      const selectors = Array.from(new Set([...(spec.must_exist || []), ...(spec.reference_signals || [])]));
      const refMetrics = await collectMetrics(refPage, selectors, spec.box_selectors || []);
      const genMetrics = await collectMetrics(genPage, selectors, spec.box_selectors || []);
      const refShot = `${caseKey}-${viewport.key}-reference.png`;
      const genShot = `${caseKey}-${viewport.key}-generated.png`;
      await refPage.screenshot({ path: path.join(outDir, refShot), fullPage: false });
      await genPage.screenshot({ path: path.join(outDir, genShot), fullPage: false });
      const refPath = path.join(outDir, refShot);
      const genPath = path.join(outDir, genShot);
      const refBytes = fs.statSync(refPath).size;
      const genBytes = fs.statSync(genPath).size;
      const pixelDistance = await screenshotDistance(genPage, refPath, genPath);
      const comparison = compareCase(caseKey, viewport.key, spec, refMetrics, genMetrics, refBytes, genBytes, pixelDistance);
      failures.push(...comparison.failures);
      results.push({
        report: caseKey,
        viewport: viewport.key,
        referenceScreenshot: refShot,
        generatedScreenshot: genShot,
        referenceBytes: refBytes,
        generatedBytes: genBytes,
        signalScore: comparison.signalScore,
        layoutScore: comparison.layoutScore,
        screenshotByteRatio: comparison.screenshotByteRatio,
        pixelDistance: comparison.pixelDistance,
        comparedSignals: comparison.comparedSignals,
        matchedSignals: comparison.matchedSignals,
        comparedBoxes: comparison.comparedBoxes,
        matchedBoxes: comparison.matchedBoxes,
        boxDetails: comparison.boxDetails,
        referenceMetrics: refMetrics,
        generatedMetrics: genMetrics,
      });
      await refPage.close();
      await genPage.close();
    }
  }
  await context.close();
  fs.writeFileSync(path.join(outDir, 'reference-visual-results.json'), JSON.stringify(results, null, 2));
  fs.writeFileSync(path.join(outDir, 'reference-visual-failures.json'), JSON.stringify(failures, null, 2));
  expect(failures).toEqual([]);
});
"""


class ReferenceCompareError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def first_html(folder: Path) -> Path:
    html_files = sorted(folder.rglob("*.html"))
    if not html_files:
        raise ReferenceCompareError(f"no html file found under {folder}")
    return html_files[0]


def build_cases(download_root: Path) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for key, spec in REPORT_CASES.items():
        folder = download_root / str(spec["folder"])
        if not folder.exists():
            raise ReferenceCompareError(f"missing reference folder: {folder}")
        case = dict(spec)
        case["reference_html"] = str(first_html(folder))
        cases[key] = case
    return cases


def markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Template Reference Visual Comparison",
        "",
        f"- report_dir: `{audit['report_dir']}`",
        f"- checked_at: `{audit['checked_at']}`",
        f"- overall_pass: `{str(audit['overall_pass']).lower()}`",
        f"- reference_root: `{audit['reference_root']}`",
        f"- output_dir: `{audit['output_dir']}`",
        "",
        "| Report | Viewport | Signal score | Layout score | Byte ratio | Pixel distance | Reference screenshot | Generated screenshot |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for item in audit.get("results") or []:
        lines.append(
            f"| `{item.get('report')}` | `{item.get('viewport')}` | {float(item.get('signalScore') or 0):.2f} | "
            f"{float(item.get('layoutScore') or 0):.2f} | {float(item.get('screenshotByteRatio') or 0):.2f} | "
            f"{float(item.get('pixelDistance') or 0):.3f} | "
            f"`{item.get('referenceScreenshot')}` | `{item.get('generatedScreenshot')}` |"
        )
    if audit.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in audit["failures"]:
            lines.append(f"- {failure}")
    if audit.get("stderr"):
        lines.extend(["", "## stderr", "", "```text", str(audit["stderr"])[:4000], "```"])
    return "\n".join(lines) + "\n"


def run_compare(report_dir: Path, download_root: Path = DEFAULT_DOWNLOAD_ROOT, out_dir: Path | None = None) -> dict[str, Any]:
    report_dir = report_dir.resolve()
    download_root = download_root.resolve()
    out_dir = (out_dir or (report_dir / "output" / "template_reference_visual_compare")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        cases = build_cases(download_root)
    except ReferenceCompareError as exc:
        audit = {
            "report_dir": str(report_dir),
            "checked_at": utc_now(),
            "overall_pass": False,
            "reference_root": str(download_root),
            "output_dir": str(out_dir),
            "results": [],
            "failures": [str(exc)],
            "stdout": "",
            "stderr": "",
        }
        write_json(out_dir / "template_reference_visual_compare.json", audit)
        (out_dir / "template_reference_visual_compare.md").write_text(markdown(audit), encoding="utf-8")
        return audit

    npx = shutil.which("npx")
    if not npx:
        audit = {
            "report_dir": str(report_dir),
            "checked_at": utc_now(),
            "overall_pass": False,
            "reference_root": str(download_root),
            "output_dir": str(out_dir),
            "results": [],
            "failures": ["npx executable not available"],
            "stdout": "",
            "stderr": "",
        }
        write_json(out_dir / "template_reference_visual_compare.json", audit)
        (out_dir / "template_reference_visual_compare.md").write_text(markdown(audit), encoding="utf-8")
        return audit

    spec_path = SCRIPT_DIR / "tmp_template_reference_visual_compare.spec.js"
    spec_path.write_text(textwrap.dedent(PLAYWRIGHT_SPEC).strip() + "\n", encoding="utf-8")
    env = dict(
        os.environ,
        REPORT_DIR=str(report_dir),
        REFERENCE_COMPARE_OUT=str(out_dir),
        REFERENCE_COMPARE_CASES=json.dumps(cases, ensure_ascii=False),
    )
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

    results_path = out_dir / "reference-visual-results.json"
    failures_path = out_dir / "reference-visual-failures.json"
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    failures = json.loads(failures_path.read_text(encoding="utf-8")) if failures_path.exists() else []
    audit = {
        "report_dir": str(report_dir),
        "checked_at": utc_now(),
        "overall_pass": result.returncode == 0,
        "reference_root": str(download_root),
        "output_dir": str(out_dir),
        "results": results,
        "failures": failures,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    write_json(out_dir / "template_reference_visual_compare.json", audit)
    (out_dir / "template_reference_visual_compare.md").write_text(markdown(audit), encoding="utf-8")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare generated reports against downloaded reference HTML templates.")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--download-root", type=Path, default=DEFAULT_DOWNLOAD_ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    audit = run_compare(args.dir, args.download_root, args.out)
    print(json.dumps({"overall_pass": audit["overall_pass"], "audit": str(Path(audit["output_dir"]) / "template_reference_visual_compare.json")}, ensure_ascii=False))
    return 0 if audit["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
