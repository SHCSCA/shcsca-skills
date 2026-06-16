#!/usr/bin/env python3
import json
import shutil
import subprocess
import textwrap
import unittest

from site_assets import REPORT_JS


NODE_SCRIPT = r"""
const reportJs = __REPORT_JS__;

class ClassList {
  constructor(element) { this.element = element; this.values = new Set((element.className || '').split(/\s+/).filter(Boolean)); }
  sync() { this.element.className = [...this.values].join(' '); }
  add(name) { this.values.add(name); this.sync(); }
  remove(name) { this.values.delete(name); this.sync(); }
  contains(name) { return this.values.has(name); }
  toggle(name, force) {
    const shouldAdd = force === undefined ? !this.values.has(name) : Boolean(force);
    if (shouldAdd) this.values.add(name); else this.values.delete(name);
    this.sync();
    return shouldAdd;
  }
}

class Element {
  constructor(tag, className = '', text = '') {
    this.tag = tag;
    this.className = className;
    this.textContent = text;
    this.children = [];
    this.parentNode = null;
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.hidden = false;
    this.value = '';
    this.type = '';
    this.classList = new ClassList(this);
  }
  appendChild(child) {
    if (child.parentNode) {
      const old = child.parentNode.children.indexOf(child);
      if (old >= 0) child.parentNode.children.splice(old, 1);
      if (child.parentNode.rows) {
        const rowIndex = child.parentNode.rows.indexOf(child);
        if (rowIndex >= 0) child.parentNode.rows.splice(rowIndex, 1);
      }
    }
    child.parentNode = this;
    this.children.push(child);
    if (this.rows && !this.rows.includes(child)) this.rows.push(child);
    return child;
  }
  insertBefore(child, before) {
    child.parentNode = this;
    const index = this.children.indexOf(before);
    if (index >= 0) this.children.splice(index, 0, child); else this.children.push(child);
    return child;
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  dispatch(type) { for (const fn of this.listeners[type] || []) fn({ target: this }); }
  setAttribute(key, value) { this.attributes[key] = String(value); if (key === 'aria-selected') this.ariaSelected = String(value); }
  matches(selector) {
    if (selector === 'table') return this.tag === 'table';
    if (selector === 'img') return this.tag === 'img';
    if (selector === 'th') return this.tag === 'th';
    if (selector === 'tbody tr') return this.tag === 'tr' && this.parentNode && this.parentNode.tag === 'tbody';
    if (selector === '[data-tabs]') return this.dataset.tabs !== undefined;
    if (selector === '[data-tab-target]') return this.dataset.tabTarget !== undefined;
    if (selector === '[data-tab-panel]') return this.dataset.tabPanel !== undefined;
    if (selector.startsWith('.')) return this.classList.contains(selector.slice(1));
    return false;
  }
  querySelectorAll(selector) {
    if (selector === 'tbody tr' && this.tBodies) return this.tBodies.flatMap(body => body.rows);
    const results = [];
    const visit = (node) => {
      for (const child of node.children) {
        if (child.matches(selector)) results.push(child);
        visit(child);
      }
    };
    visit(this);
    return results;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function makeRow(values) {
  const row = new Element('tr');
  row.cells = values.map(value => new Element('td', '', value));
  row.textContent = values.join(' ');
  return row;
}

const root = new Element('root');
const nav = root.appendChild(new Element('nav', 'site-nav'));
const navToggle = root.appendChild(new Element('button', 'site-nav-toggle'));
const tableParent = root.appendChild(new Element('section'));
const table = tableParent.appendChild(new Element('table'));
const headA = new Element('th', '', 'Name');
const headB = new Element('th', '', 'Score');
table.children.push(headA, headB);
const tbody = new Element('tbody');
tbody.rows = [];
tbody.appendChild(makeRow(['banana', '20']));
tbody.appendChild(makeRow(['apple', '10']));
table.tBodies = [tbody];
table.appendChild(tbody);

const tabs = root.appendChild(new Element('div'));
tabs.dataset.tabs = '';
const tabA = tabs.appendChild(new Element('button'));
tabA.dataset.tabTarget = 'a';
const tabB = tabs.appendChild(new Element('button'));
tabB.dataset.tabTarget = 'b';
const panelA = tabs.appendChild(new Element('div'));
panelA.dataset.tabPanel = 'a';
const panelB = tabs.appendChild(new Element('div'));
panelB.dataset.tabPanel = 'b';

const chart = root.appendChild(new Element('div', 'mini-chart'));
const bar = chart.appendChild(new Element('div', 'bar-row'));
const imageFrame = root.appendChild(new Element('span', 'image-frame'));
const image = imageFrame.appendChild(new Element('img', 'comp-product-thumb'));
image.complete = true;
image.naturalWidth = 0;
const imageFallback = imageFrame.appendChild(new Element('span', 'image-load-fallback', '图片加载失败'));
imageFallback.hidden = true;
image.nextElementSibling = imageFallback;

global.document = {
  querySelector(selector) {
    if (selector === '.site-nav') return nav;
    if (selector === '.site-nav-toggle') return navToggle;
    return root.querySelector(selector);
  },
  querySelectorAll(selector) {
    if (selector === 'table') return [table];
    if (selector === '[data-tabs]') return [tabs];
    if (selector === '.mini-chart .bar-row') return [bar];
    if (selector === '.image-frame img') return [image];
    return root.querySelectorAll(selector);
  },
  createElement(tag) { return new Element(tag); }
};

global.window = { addEventListener() {} };

eval(reportJs);

navToggle.dispatch('click');
const input = tableParent.children.find(child => child.className === 'table-tools').children[0];
input.value = 'banana';
input.dispatch('input');
headA.dispatch('click');
tabB.dispatch('click');
bar.dispatch('mouseenter');
const hovered = bar.classList.contains('is-linked');
bar.dispatch('mouseleave');
globalThis.__reportCheckImageFallbacks();

const result = {
  navOpen: nav.classList.contains('is-open'),
  inputCreated: input.type === 'search' && input.attributes['aria-label'] === '筛选当前表格',
  appleFiltered: tbody.rows.find(row => row.cells[0].textContent === 'apple').classList.contains('is-filtered-out'),
  sortedFirstRow: tbody.rows[0].cells[0].textContent,
  tabBSelected: tabB.attributes['aria-selected'] === 'true' && panelA.hidden === true && panelB.hidden === false,
  chartHover: hovered && !bar.classList.contains('is-linked'),
  imageFallback: image.hidden === true && imageFallback.hidden === false
};

console.log(JSON.stringify(result));
"""


class SiteInteractionsTest(unittest.TestCase):
    def test_report_js_behaviors_execute_against_minimal_dom(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node executable not available")
        script = NODE_SCRIPT.replace("__REPORT_JS__", json.dumps(REPORT_JS))

        result = subprocess.run([node, "-e", script], text=True, capture_output=True, check=False)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["navOpen"])
        self.assertTrue(payload["inputCreated"])
        self.assertTrue(payload["appleFiltered"])
        self.assertEqual(payload["sortedFirstRow"], "apple")
        self.assertTrue(payload["tabBSelected"])
        self.assertTrue(payload["chartHover"])
        self.assertTrue(payload["imageFallback"])


if __name__ == "__main__":
    unittest.main()
