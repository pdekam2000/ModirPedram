#!/usr/bin/env python3
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=10000)
    page = next(cand for ctx in browser.contexts for cand in ctx.pages if "runwayml.com" in cand.url)

    def read_duration():
        btn = page.get_by_role("button", name="Duration")
        text = btn.inner_text(timeout=3000).replace("\n", " ").strip()
        m = re.search(r"(\d{1,2})s", text)
        return text, int(m.group(1)) if m else None

    if page.get_by_role("slider").count() == 0:
        page.get_by_role("button", name="Duration").click(timeout=5000, force=True)
        time.sleep(0.4)
    before_text, before_val = read_duration()
    slider = page.get_by_role("slider").first
    track = page.locator('[class*="Slider__Root"]').first
    tbox = track.bounding_box()
    if tbox:
        page.mouse.click(tbox["x"] + 8, tbox["y"] + tbox["height"] / 2)
        time.sleep(0.3)
    min_text, min_val = read_duration()
    if tbox:
        page.mouse.click(tbox["x"] + tbox["width"] - 8, tbox["y"] + tbox["height"] / 2)
        time.sleep(0.3)
    max_text, max_val = read_duration()
    print(json.dumps({"before": before_text, "min": min_text, "max": max_text, "min_val": min_val, "max_val": max_val}, indent=2))
