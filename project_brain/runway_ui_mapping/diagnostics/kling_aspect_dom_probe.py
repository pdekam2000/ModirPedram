"""Kling 3.0 Pro — read-only DOM probe for left-panel aspect ratio controls (Phase 5C-2).

Connects to existing Chrome via CDP, inspects the Runway generate page, and writes
project_brain/runway_ui_mapping/diagnostics/kling_aspect_probe_<run_id>.json

Does NOT click Generate or spend credits.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CDP_URL = "http://127.0.0.1:9222"
DIAGNOSTICS_DIR = Path(__file__).resolve().parent
SEARCH_TERMS = ("16:9", "9:16", "Aspect", "ratio", "5s", "On")

PROBE_EVAL_SCRIPT = """() => {
  const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
  const lower = (value) => normalize(value).toLowerCase();
  const searchTerms = %SEARCH_TERMS%;

  const matchesTerm = (text, aria, title) => {
    const blob = lower(`${text} ${aria} ${title}`);
    return searchTerms.some((term) => blob.includes(lower(term)));
  };

  const isClickable = (node) => {
    if (!node) return false;
    const tag = String(node.tagName || '').toLowerCase();
    if (tag === 'button' || tag === 'a') return true;
    const role = normalize(node.getAttribute('role') || '');
    if (role === 'button' || role === 'menuitem' || role === 'option') return true;
    const tabIndex = node.getAttribute('tabindex');
    if (tabIndex !== null && tabIndex !== '-1') return true;
    if (typeof node.onclick === 'function') return true;
    const style = window.getComputedStyle(node);
    if (style.cursor === 'pointer') return true;
    return false;
  };

  const nearestClickableAncestor = (node) => {
    let current = node;
    for (let depth = 0; depth < 12 && current; depth++) {
      if (isClickable(current)) return current;
      current = current.parentElement;
    }
    return null;
  };

  const dataAttributes = (node) => {
    const out = {};
    if (!node || !node.attributes) return out;
    for (const attr of Array.from(node.attributes)) {
      if (attr.name.startsWith('data-')) out[attr.name] = attr.value;
    }
    return out;
  };

  const describeNode = (node, matchReason) => {
    if (!node) return null;
    const rect = node.getBoundingClientRect();
    const text = normalize(node.innerText || '');
    const textContent = normalize(node.textContent || '');
    const aria = normalize(node.getAttribute('aria-label') || '');
    const title = normalize(node.getAttribute('title') || '');
    const clickableAncestor = nearestClickableAncestor(node);
    let ancestorInfo = null;
    if (clickableAncestor && clickableAncestor !== node) {
      const aRect = clickableAncestor.getBoundingClientRect();
      ancestorInfo = {
        tagName: clickableAncestor.tagName,
        role: clickableAncestor.getAttribute('role') || '',
        ariaLabel: normalize(clickableAncestor.getAttribute('aria-label') || ''),
        innerText: normalize(clickableAncestor.innerText || '').slice(0, 120),
        className: String(clickableAncestor.className || '').slice(0, 200),
        id: clickableAncestor.id || '',
        boundingBox: {
          x: Math.round(aRect.x),
          y: Math.round(aRect.y),
          width: Math.round(aRect.width),
          height: Math.round(aRect.height),
        },
      };
    }
    return {
      matchReason,
      tagName: node.tagName,
      role: node.getAttribute('role') || '',
      ariaLabel: aria,
      title,
      innerText: text.slice(0, 160),
      textContent: textContent.slice(0, 160),
      className: String(node.className || '').slice(0, 240),
      id: node.id || '',
      type: node.getAttribute('type') || '',
      dataAttributes: dataAttributes(node),
      isClickable: isClickable(node),
      nearestClickableAncestor: ancestorInfo,
      boundingBox: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
    };
  };

  const panelSelectors = [
    '[class*="left-panel"]',
    '[class*="LeftPanel"]',
    '[class*="leftPanel"]',
    '[class*="LeftPanel"]',
    '[class*="panel"]',
  ];
  const panelRoots = [];
  for (const selector of panelSelectors) {
    for (const node of document.querySelectorAll(selector)) {
      const rect = node.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      panelRoots.push({
        selector,
        className: String(node.className || '').slice(0, 240),
        boundingBox: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        },
      });
    }
  }

  const anchorSelectors = [
    '[contenteditable="true"]',
    'textarea',
  ];
  const anchors = [];
  for (const selector of anchorSelectors) {
    for (const node of document.querySelectorAll(selector)) {
      const rect = node.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      anchors.push({
        selector,
        placeholder: normalize(node.getAttribute('placeholder') || ''),
        ariaLabel: normalize(node.getAttribute('aria-label') || ''),
        innerText: normalize(node.innerText || '').slice(0, 120),
        boundingBox: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        },
      });
    }
  }

  const promptHints = [];
  for (const node of document.querySelectorAll('p, div, span, label')) {
    const text = normalize(node.innerText || node.textContent || '');
    if (!text) continue;
    if (!/describe your shot|describe this shot|add a first video frame/i.test(text)) continue;
    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    promptHints.push({
      innerText: text.slice(0, 160),
      tagName: node.tagName,
      className: String(node.className || '').slice(0, 200),
      boundingBox: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
    });
  }

  const settingsRowCandidates = [];
  for (const node of document.querySelectorAll('button, [role="button"], span, div, label')) {
    const text = normalize(node.innerText || node.textContent || '');
    const aria = normalize(node.getAttribute('aria-label') || '');
    if (!text && !aria) continue;
    const compact = text.replace(/\\s/g, '');
    const looksLikeSettingsChip =
      text === 'On' ||
      text === 'Off' ||
      /^\\d:\\d$/.test(compact) ||
      /^\\d+s$/i.test(compact) ||
      /aspect\\s*ratio/i.test(aria);
    if (!looksLikeSettingsChip) continue;
    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    settingsRowCandidates.push(describeNode(node, 'settings_chip_candidate'));
  }

  const matchedElements = [];
  const seen = new Set();
  for (const node of document.querySelectorAll('*')) {
    const text = normalize(node.innerText || '');
    const textContent = normalize(node.textContent || '');
    const aria = normalize(node.getAttribute('aria-label') || '');
    const title = normalize(node.getAttribute('title') || '');
    if (!matchesTerm(text, aria, title) && !matchesTerm(textContent, aria, title)) continue;
    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    const key = `${node.tagName}|${rect.x}|${rect.y}|${text.slice(0, 40)}|${aria.slice(0, 40)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    let reason = 'search_term';
    if (/16:9|9:16/.test(text.replace(/\\s/g, ''))) reason = 'aspect_ratio_text';
    else if (/aspect/i.test(aria) || /ratio/i.test(aria)) reason = 'aspect_aria';
    else if (/^\\d+s$/i.test(text.replace(/\\s/g, ''))) reason = 'duration_text';
    else if (text === 'On' || text === 'Off') reason = 'audio_toggle_text';
    matchedElements.push(describeNode(node, reason));
  }

  matchedElements.sort((a, b) => a.boundingBox.y - b.boundingBox.y || a.boundingBox.x - b.boundingBox.x);
  settingsRowCandidates.sort((a, b) => a.boundingBox.y - b.boundingBox.y || a.boundingBox.x - b.boundingBox.x);

  return {
    pageUrl: location.href,
    pageTitle: document.title,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    panelRoots,
    anchors,
    promptHints,
    settingsRowCandidates,
    matchedElements,
  };
}"""


def _probe_helper_diagnostics(page: Any) -> dict[str, Any]:
    from content_brain.execution.kling_frame_to_video_live_engine import (
        _find_kling_left_panel_aspect_button,
        _kling_left_panel_scope,
    )

    panel = _kling_left_panel_scope(page)
    panel_info: dict[str, Any] = {"strategy": "unknown", "visible": False}
    try:
        panel_info["count"] = panel.count()
        panel_info["visible"] = bool(panel.count() > 0 and panel.first.is_visible())
        if panel.count() > 0:
            box = panel.first.bounding_box()
            panel_info["boundingBox"] = box
            try:
                panel_info["className"] = str(panel.first.get_attribute("class") or "")[:240]
            except Exception as exc:
                panel_info["className_error"] = str(exc)
    except Exception as exc:
        panel_info["error"] = str(exc)

    for name, selector in (
        ("left_panel_class", '[class*="left-panel"]'),
        ("LeftPanel_class", '[class*="LeftPanel"]'),
    ):
        try:
            loc = page.locator(selector).first
            panel_info[name] = {
                "count": loc.count(),
                "visible": loc.count() > 0 and loc.is_visible(),
            }
        except Exception as exc:
            panel_info[name] = {"error": str(exc)}

    aspect_button, strategy = _find_kling_left_panel_aspect_button(page)
    helper_result: dict[str, Any] = {
        "strategy": strategy or None,
        "found": aspect_button is not None,
    }
    if aspect_button is not None:
        try:
            helper_result["innerText"] = str(aspect_button.inner_text(timeout=2000) or "").strip()
            helper_result["ariaLabel"] = str(aspect_button.get_attribute("aria-label") or "")
            helper_result["boundingBox"] = aspect_button.bounding_box()
        except Exception as exc:
            helper_result["read_error"] = str(exc)

    playwright_probes: list[dict[str, Any]] = []
    scopes = [
        ("page", page),
        ("left_panel_scope", panel),
    ]
    probes = [
        ("role_button_aspect_regex", lambda scope: scope.get_by_role("button", name=re.compile(r"aspect\s*ratio", re.I)).first),
        ("role_button_16_9", lambda scope: scope.get_by_role("button", name=re.compile(re.escape("16:9"))).first),
        ("role_button_9_16", lambda scope: scope.get_by_role("button", name=re.compile(re.escape("9:16"))).first),
        ("text_exact_16_9", lambda scope: scope.get_by_text("16:9", exact=True).first),
        ("text_exact_9_16", lambda scope: scope.get_by_text("9:16", exact=True).first),
        ("text_exact_5s", lambda scope: scope.get_by_text("5s", exact=True).first),
        ("text_exact_On", lambda scope: scope.get_by_text("On", exact=True).first),
    ]
    for scope_name, scope in scopes:
        for probe_name, factory in probes:
            entry: dict[str, Any] = {"scope": scope_name, "probe": probe_name}
            try:
                loc = factory(scope)
                count = loc.count()
                entry["count"] = count
                if count > 0:
                    entry["visible"] = loc.is_visible()
                    if entry["visible"]:
                        entry["innerText"] = str(loc.inner_text(timeout=1500) or "").strip()[:120]
                        entry["ariaLabel"] = str(loc.get_attribute("aria-label") or "")
                        entry["boundingBox"] = loc.bounding_box()
            except Exception as exc:
                entry["error"] = str(exc)
            playwright_probes.append(entry)

    return {
        "panelScope": panel_info,
        "currentHelper": helper_result,
        "playwrightProbes": playwright_probes,
    }


def run_probe(*, run_id: str, cdp_url: str = DEFAULT_CDP_URL) -> dict[str, Any]:
    from content_brain.execution.kling_frame_to_video_live_dry_run import _find_runway_generate_page

    started = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "version": "kling_aspect_dom_probe_v1",
        "run_id": run_id,
        "started_at": started,
        "cdp_url": cdp_url,
        "search_terms": list(SEARCH_TERMS),
        "read_only": True,
        "credits_spent": False,
    }

    playwright = None
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        page = _find_runway_generate_page(browser)
        if page is None:
            raise RuntimeError("No Runway generate tab found on CDP browser")

        payload["page_url"] = page.url
        script = PROBE_EVAL_SCRIPT.replace("%SEARCH_TERMS%", json.dumps(list(SEARCH_TERMS), ensure_ascii=False))
        dom_payload = page.evaluate(script)
        payload["dom"] = dom_payload if isinstance(dom_payload, dict) else {"raw": dom_payload}
        payload["helperDiagnostics"] = _probe_helper_diagnostics(page)

        aspect_matches = [
            item
            for item in list(payload.get("dom", {}).get("matchedElements") or [])
            if item and item.get("matchReason") in {"aspect_ratio_text", "aspect_aria", "settings_chip_candidate"}
            and ("16:9" in str(item.get("innerText") or "").replace(" ", "")
                 or "9:16" in str(item.get("innerText") or "").replace(" ", "")
                 or "aspect" in str(item.get("ariaLabel") or "").lower())
        ]
        payload["aspectCandidates"] = aspect_matches[:20]
        payload["ok"] = True
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = str(exc)
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass

    payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    out_path = DIAGNOSTICS_DIR / f"kling_aspect_probe_{run_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["output_path"] = str(out_path.resolve()).replace("\\", "/")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling aspect ratio DOM probe (read-only)")
    parser.add_argument("--run-id", default="manual_probe")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    args = parser.parse_args()
    result = run_probe(run_id=str(args.run_id), cdp_url=str(args.cdp_url))
    print(json.dumps({"ok": result.get("ok"), "output_path": result.get("output_path"), "error": result.get("error")}, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
