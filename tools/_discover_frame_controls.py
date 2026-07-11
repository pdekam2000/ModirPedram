#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

JS = """
() => {
  const out = {};
  const frames = document.querySelector('label:has-text("Frames")');
  out.frames = frames ? {x: Math.round(frames.getBoundingClientRect().x), y: Math.round(frames.getBoundingClientRect().y)} : null;
  const prompt = document.querySelector('[contenteditable="true"]');
  out.prompt = prompt ? { aria: prompt.getAttribute('aria-label')||'', ce: prompt.getAttribute('contenteditable'), x: Math.round(prompt.getBoundingClientRect().x), y: Math.round(prompt.getBoundingClientRect().y) } : null;
  const uploads = [...document.querySelectorAll('span, button')].filter(el => (el.innerText||'').trim()==='Upload').slice(0,3).map(el => {
    const r = el.getBoundingClientRect();
    return { tag: el.tagName.toLowerCase(), x: Math.round(r.x), y: Math.round(r.y), parentText: (el.parentElement?.innerText||'').trim().slice(0,40) };
  });
  out.uploads = uploads;
  const gen = document.querySelector('button:has-text("Generate")');
  out.generate = gen ? { x: Math.round(gen.getBoundingClientRect().x), y: Math.round(gen.getBoundingClientRect().y) } : null;
  return out;
}
"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=10000)
    page = next(cand for ctx in browser.contexts for cand in ctx.pages if "runwayml.com" in cand.url)
    print(json.dumps(page.evaluate(JS), indent=2, ensure_ascii=False))
