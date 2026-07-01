#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

SCAN_JS = """
() => {
  const out = { sliders: [], durationNodes: [], buttons: [] };
  for (const el of document.querySelectorAll('[role="slider"], input[type="range"], [aria-valuenow]')) {
    const r = el.getBoundingClientRect();
    out.sliders.push({ tag: el.tagName.toLowerCase(), role: el.getAttribute('role')||'', aria: el.getAttribute('aria-label')||'', valuenow: el.getAttribute('aria-valuenow')||'', x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) });
  }
  for (const el of document.querySelectorAll('*')) {
    const t = (el.innerText||'').trim();
    if (/^\\d{1,2}s$/.test(t) && el.children.length===0) {
      const r = el.getBoundingClientRect();
      out.durationNodes.push({ text:t, tag:el.tagName.toLowerCase(), x:Math.round(r.x), y:Math.round(r.y) });
    }
  }
  for (const el of document.querySelectorAll('button')) {
    const t = (el.innerText||'').trim();
    if (/\\d{1,2}s/.test(t)) {
      const r = el.getBoundingClientRect();
      out.buttons.push({ text:t.replace(/\\s+/g,' '), x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height) });
    }
  }
  return out;
}
"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=10000)
    page = None
    for ctx in browser.contexts:
        for cand in ctx.pages:
            if "runwayml.com" in cand.url:
                page = cand
                break
    result = {"before": page.evaluate(SCAN_JS)}
    btn = page.locator("button").filter(has_text="15s").first
    if btn.count():
        btn.click(timeout=5000)
        time.sleep(0.6)
    result["after_click"] = page.evaluate(SCAN_JS)
    print(json.dumps(result, indent=2))
