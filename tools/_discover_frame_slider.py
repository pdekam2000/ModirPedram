#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

JS = """
() => {
  const out = { sliders: [], durationTexts: [], durationNodes: [], tracks: [] };
  for (const el of document.querySelectorAll('[role="slider"], input[type="range"], [aria-valuenow]')) {
    const r = el.getBoundingClientRect();
    out.sliders.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      aria: el.getAttribute('aria-label') || '',
      valuenow: el.getAttribute('aria-valuenow') || '',
      valuetext: el.getAttribute('aria-valuetext') || '',
      text: (el.innerText || '').trim().slice(0, 40),
      x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)
    });
  }
  const body = document.body.innerText || '';
  out.durationTexts = (body.match(/\\b\\d{1,2}s\\b/g) || []).slice(0, 20);
  for (const el of document.querySelectorAll('*')) {
    const t = (el.innerText || '').trim();
    if (/^\\d{1,2}s$/.test(t) && el.children.length === 0) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        out.durationNodes.push({ text: t, tag: el.tagName.toLowerCase(), x: Math.round(r.x), y: Math.round(r.y) });
      }
    }
  }
  for (const el of document.querySelectorAll('[class*="track"], [data-testid*="slider"], [class*="Slider"]')) {
    const r = el.getBoundingClientRect();
    if (r.width > 20 && r.height > 0 && r.height < 40) {
      out.tracks.push({ tag: el.tagName.toLowerCase(), className: (el.className||'').toString().slice(0,80), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)});
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
        if page:
            break
    if not page:
        print(json.dumps({"error": "no_runway_tab"}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps({"url": page.url, "discovery": page.evaluate(JS)}, indent=2, ensure_ascii=False))
