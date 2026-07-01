#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

JS = """
() => {
  const slider = document.querySelector('[role="slider"]');
  if (!slider) return { error: 'no slider' };
  const track = slider.parentElement;
  const grand = track ? track.parentElement : null;
  const describe = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role')||'',
      aria: el.getAttribute('aria-label')||'',
      className: (el.className||'').toString().slice(0,80),
      valuenow: el.getAttribute('aria-valuenow')||'',
      valuetext: el.getAttribute('aria-valuetext')||'',
      text: (el.innerText||'').trim().slice(0,60),
      x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)
    };
  };
  return { handle: describe(slider), track: describe(track), container: describe(grand), siblings: track ? [...track.children].map(describe) : [] };
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
    if page.locator('[role="slider"]').count() == 0:
        page.get_by_role("button", name="Duration").click(timeout=5000)
        time.sleep(0.5)
    print(json.dumps(page.evaluate(JS), indent=2))
