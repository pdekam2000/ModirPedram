#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

JS = """
() => {
  const out = { nearDuration: [], candidates: [], allRoles: [] };
  const durationNode = [...document.querySelectorAll('*')].find(el => (el.innerText||'').trim() === '15s' && el.children.length===0);
  if (durationNode) {
    let parent = durationNode.parentElement;
    for (let i = 0; i < 6 && parent; i++) {
      const kids = [...parent.querySelectorAll('*')].slice(0, 40).map(el => {
        const r = el.getBoundingClientRect();
        return {
          tag: el.tagName.toLowerCase(),
          role: el.getAttribute('role')||'',
          aria: el.getAttribute('aria-label')||'',
          text: (el.innerText||'').trim().slice(0,30),
          valuenow: el.getAttribute('aria-valuenow')||'',
          x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)
        };
      });
      out.nearDuration.push({depth:i, tag: parent.tagName.toLowerCase(), className:(parent.className||'').toString().slice(0,60), kids});
      parent = parent.parentElement;
    }
  }
  for (const el of document.querySelectorAll('[role], input, button, label, [contenteditable="true"]')) {
    const aria = (el.getAttribute('aria-label')||'').toLowerCase();
    const text = (el.innerText||'').trim().toLowerCase();
    if (aria.includes('duration') || aria.includes('slider') || text === 'frames' || text.includes('describe your shot') || text.includes('upload')) {
      const r = el.getBoundingClientRect();
      out.candidates.push({
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role')||'',
        aria: el.getAttribute('aria-label')||'',
        text: (el.innerText||'').trim().slice(0,50),
        valuenow: el.getAttribute('aria-valuenow')||'',
        type: el.getAttribute('type')||'',
        contenteditable: el.getAttribute('contenteditable')||'',
        x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)
      });
    }
  }
  const roles = new Set();
  for (const el of document.querySelectorAll('[role]')) roles.add(el.getAttribute('role'));
  out.allRoles = [...roles].sort();
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
    print(json.dumps(page.evaluate(JS), indent=2, ensure_ascii=False))
