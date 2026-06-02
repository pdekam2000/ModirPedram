#!/usr/bin/env python3
"""
Phase RUNWAY-UI-MAPPER-C — Safe Runway UI discovery + manual learning via Chrome CDP.

Modes: --scan, --label, --observe, --click-label (click element in browser → terminal label).

Never: auto-click Generate, create video, spend credits, store credentials/cookies/storage, auto-login.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CDP_URL = "http://127.0.0.1:9222"
MAPPER_VERSION_V1 = "runway_ui_mapper_v1"
MAPPER_VERSION_V2 = "runway_ui_mapper_v2"

OUTPUT_DIR = ROOT / "project_brain" / "runway_ui_mapping"
JSON_PATH = OUTPUT_DIR / "runway_ui_map.json"
CANDIDATES_PATH = OUTPUT_DIR / "selector_candidates.json"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"

BLOCKED_CLICK_SUBSTRINGS: tuple[str, ...] = (
    "generate",
    "create",
    "submit",
    "upgrade",
    "purchase",
    "buy",
    "subscribe",
    "delete",
)

VALID_SEMANTIC_LABELS: tuple[str, ...] = (
    "prompt_box",
    "generate_button",
    "try_it_now_button",
    "duration_10s",
    "aspect_ratio_16_9",
    "model_selector",
    "gen45_option",
    "first_video_frame_upload",
    "reference_image_upload",
    "download_button",
    "generated_video_card",
    "queue_status_text",
    "progress_status_text",
    "skip",
    "unknown",
)

VALID_ACTION_LABELS: tuple[str, ...] = (
    "open_editor",
    "set_duration_10s",
    "set_aspect_ratio_16_9",
    "open_first_video_frame",
    "open_reference_image",
    "open_model_menu",
    "select_gen45",
    "open_duration_menu",
    "open_aspect_menu",
    "focus_prompt_box",
    "other",
)

LABEL_SAFETY_DEFAULTS: dict[str, dict[str, Any]] = {
    "generate_button": {
        "auto_click_allowed": False,
        "requires_real_video_approval": True,
    },
}

DEFAULT_SAFETY_V2: dict[str, Any] = {
    "no_credentials_stored": True,
    "no_cookies_stored": True,
    "no_storage_stored": True,
    "generate_never_auto_clicked": True,
    "auto_click_blocklist": list(BLOCKED_CLICK_SUBSTRINGS),
    "requires_approval": ["generate_button"],
}

# Semantic labels where real click may pass through with --allow-safe-clicks.
SAFE_CLICK_SEMANTIC_LABELS: frozenset[str] = frozenset(
    {
        "prompt_box",
        "duration_10s",
        "aspect_ratio_16_9",
        "gen45_option",
        "model_selector",
        "try_it_now_button",
        "first_video_frame_upload",
        "reference_image_upload",
        "download_button",
        "generated_video_card",
        "queue_status_text",
        "progress_status_text",
    }
)

CLICK_LABEL_INSTALL_JS = """
(allowSafeClicks) => {
  const BLOCKED = ['generate','create','submit','upgrade','purchase','buy','subscribe','delete'];
  const HIGHLIGHT_CLASS = 'runway-mapper-click-highlight';
  const STYLE_ID = 'runway-mapper-click-style';

  function labelOf(el) {
    if (!el) return '';
    const parts = [
      el.innerText, el.textContent, el.getAttribute('aria-label'),
      el.getAttribute('title'), el.getAttribute('placeholder'),
      el.getAttribute('name'), el.getAttribute('value'),
    ];
    return parts.filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim().slice(0, 240);
  }

  function nearbyText(el) {
    let node = el && el.parentElement;
    for (let i = 0; i < 3 && node; i++) {
      const t = (node.innerText || '').replace(/\\s+/g, ' ').trim();
      if (t && t.length > 3) return t.slice(0, 180);
      node = node.parentElement;
    }
    return '';
  }

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) {
      try { return '#' + CSS.escape(el.id); } catch (e) { return '#' + el.id; }
    }
    const testId = el.getAttribute('data-testid');
    if (testId) return `[data-testid="${testId}"]`;
    const aria = el.getAttribute('aria-label');
    if (aria) {
      return `${el.tagName.toLowerCase()}[aria-label="${aria.replace(/"/g, '\\\\"')}"]`;
    }
    return el.tagName.toLowerCase();
  }

  function isDangerous(el) {
    const hay = labelOf(el).toLowerCase();
    return BLOCKED.some(t => hay.includes(t));
  }

  function pickTarget(ev) {
    let node = ev.target;
    const interactive = ['BUTTON','A','INPUT','SELECT','TEXTAREA','LABEL','VIDEO'];
    while (node && node !== document.body) {
      const tag = (node.tagName || '').toUpperCase();
      if (interactive.includes(tag) || node.isContentEditable || node.getAttribute('role') === 'button') {
        return node;
      }
      node = node.parentElement;
    }
    return ev.target;
  }

  function highlight(el) {
    document.querySelectorAll('.' + HIGHLIGHT_CLASS).forEach(n => n.classList.remove(HIGHLIGHT_CLASS));
    if (el && el.classList) el.classList.add(HIGHLIGHT_CLASS);
  }

  function buildMeta(el) {
    const rect = el.getBoundingClientRect();
    const combined = labelOf(el);
    return {
      tag: (el.tagName || '').toLowerCase(),
      role: el.getAttribute('role') || '',
      type: el.getAttribute('type') || '',
      text: (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 200),
      aria_label: el.getAttribute('aria-label') || '',
      placeholder: el.getAttribute('placeholder') || '',
      title: el.getAttribute('title') || '',
      name: el.getAttribute('name') || '',
      href: el.getAttribute('href') || '',
      disabled: !!el.disabled,
      contenteditable: !!el.isContentEditable,
      css_selector: cssPath(el),
      combined_label: combined,
      nearby_text: nearbyText(el),
      bounding_box: {
        x: Math.round(rect.x), y: Math.round(rect.y),
        width: Math.round(rect.width), height: Math.round(rect.height),
      },
      page_url: location.href || '',
      page_title: document.title || '',
      click_blocked: isDangerous(el),
      captured_at: new Date().toISOString(),
    };
  }

  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .${HIGHLIGHT_CLASS} { outline: 3px solid #00b4ff !important; outline-offset: 2px !important; }
      #runway-mapper-click-banner {
        position: fixed; top: 8px; left: 50%; transform: translateX(-50%);
        z-index: 2147483646; background: rgba(0,20,40,0.92); color: #fff;
        padding: 8px 14px; border-radius: 8px; font: 12px/1.4 sans-serif;
        pointer-events: none; box-shadow: 0 2px 8px rgba(0,0,0,0.35);
      }
    `;
    document.head.appendChild(style);
  }

  let banner = document.getElementById('runway-mapper-click-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'runway-mapper-click-banner';
    banner.textContent = 'Runway UI Mapper: click-label (dangerous clicks blocked)';
    document.body.appendChild(banner);
  }

  const handler = (ev) => {
    const target = pickTarget(ev);
    if (!target) return;
    const dangerous = isDangerous(target);
    const prevent = dangerous || !allowSafeClicks;
    if (prevent) {
      ev.preventDefault();
      ev.stopPropagation();
      if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
    }
    highlight(target);
    const meta = buildMeta(target);
    meta.prevented_default = prevent;
    meta.allow_safe_clicks_mode = !!allowSafeClicks;
    try {
      if (typeof window.runwayMapperReportClick === 'function') {
        window.runwayMapperReportClick(meta);
      }
    } catch (err) {
      console.log('RUNWAY_MAPPER_CLICK_ERROR ' + String(err));
    }
  };

  window.__runwayMapperTeardown = () => {
    document.removeEventListener('click', handler, true);
    document.querySelectorAll('.' + HIGHLIGHT_CLASS).forEach(n => n.classList.remove(HIGHLIGHT_CLASS));
    const b = document.getElementById('runway-mapper-click-banner');
    if (b) b.remove();
  };

  document.addEventListener('click', handler, true);
  window.__runwayMapperClickLabelActive = true;
}
"""

EXTRACT_ELEMENTS_JS = """
() => {
  const MAX = 500;
  const results = [];
  const seen = new Set();

  function visible(el) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    const st = window.getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') return false;
    return true;
  }

  function labelOf(el) {
    const parts = [
      el.innerText,
      el.textContent,
      el.getAttribute('aria-label'),
      el.getAttribute('title'),
      el.getAttribute('placeholder'),
      el.getAttribute('name'),
      el.getAttribute('value'),
    ];
    return parts.filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim().slice(0, 240);
  }

  function nearbyText(el) {
    let node = el.parentElement;
    for (let i = 0; i < 3 && node; i++) {
      const t = (node.innerText || '').replace(/\\s+/g, ' ').trim();
      if (t && t.length > 3) return t.slice(0, 180);
      node = node.parentElement;
    }
    return '';
  }

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) {
      try { return '#' + CSS.escape(el.id); } catch (e) { return '#' + el.id; }
    }
    const testId = el.getAttribute('data-testid');
    if (testId) return `[data-testid="${testId}"]`;
    const aria = el.getAttribute('aria-label');
    if (aria) {
      const tag = el.tagName.toLowerCase();
      return `${tag}[aria-label="${aria.replace(/"/g, '\\\\"')}"]`;
    }
    let path = el.tagName.toLowerCase();
    const parent = el.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
      if (siblings.length > 1) {
        const idx = siblings.indexOf(el) + 1;
        path += `:nth-of-type(${idx})`;
      }
    }
    return path;
  }

  function playwrightHint(el, label) {
    const tag = (el.tagName || '').toLowerCase();
    const role = el.getAttribute('role');
    if (tag === 'textarea') return 'locator("textarea")';
    if (el.isContentEditable) return 'locator("[contenteditable=\\"true\\"]")';
    if (tag === 'select') return 'locator("select")';
    if (role === 'button' && label) {
      const short = label.slice(0, 48).replace(/"/g, '');
      return `get_by_role("button", name=/${short}/i)`;
    }
    if (label && label.length < 60) {
      return `get_by_text("${label.replace(/"/g, '')}", exact=False)`;
    }
    return `locator("${cssPath(el).replace(/"/g, '')}")`;
  }

  const selectors = [
    'textarea', 'input', 'button', 'a', 'select',
    '[role="button"]', '[contenteditable="true"]', 'video', 'label',
  ];

  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      if (results.length >= MAX) break;
      const rect = el.getBoundingClientRect();
      const label = labelOf(el);
      const key = el.tagName + '|' + label + '|' + Math.round(rect.top) + '|' + Math.round(rect.left);
      if (seen.has(key)) continue;
      seen.add(key);
      results.push({
        tag: (el.tagName || '').toLowerCase(),
        role: el.getAttribute('role') || '',
        type: el.getAttribute('type') || '',
        text: (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 200),
        aria_label: el.getAttribute('aria-label') || '',
        placeholder: el.getAttribute('placeholder') || '',
        title: el.getAttribute('title') || '',
        name: el.getAttribute('name') || '',
        href: el.getAttribute('href') || '',
        disabled: !!el.disabled,
        visible: visible(el),
        contenteditable: !!el.isContentEditable,
        css_selector: cssPath(el),
        playwright_locator: playwrightHint(el, label),
        bounding_box: {
          x: Math.round(rect.x), y: Math.round(rect.y),
          width: Math.round(rect.width), height: Math.round(rect.height),
        },
        nearby_text: nearbyText(el),
        combined_label: label,
      });
    }
  }

  const bodyText = (document.body && document.body.innerText) || '';
  return {
    elements: results,
    body_text_snippet: bodyText.replace(/\\s+/g, ' ').trim().slice(0, 4000),
    url: location.href || '',
    title: document.title || '',
    active_tag: document.activeElement ? document.activeElement.tagName : '',
    active_label: document.activeElement
      ? labelOf(document.activeElement) : '',
  };
}
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"[:512]


def _is_runway_url(url: str) -> bool:
    host = (urlparse(_safe_url(url)).netloc or "").lower()
    return "runwayml.com" in host or "runway.com" in host


def _is_blocked_label(label: str) -> bool:
    lower = str(label or "").lower()
    return any(token in lower for token in BLOCKED_CLICK_SUBSTRINGS)


def assign_element_ids(elements: list[dict[str, Any]], *, visible_only: bool = True) -> dict[str, dict[str, Any]]:
    counters: Counter[str] = Counter()
    out: dict[str, dict[str, Any]] = {}
    ordered = sorted(
        elements,
        key=lambda el: (
            0 if el.get("visible") else 1,
            el.get("bounding_box", {}).get("y", 9999),
            el.get("bounding_box", {}).get("x", 9999),
        ),
    )
    for el in ordered:
        if visible_only and not el.get("visible"):
            continue
        tag = str(el.get("tag") or "el").lower()
        if tag in {"button", "a"} or el.get("role") == "button":
            prefix = "btn"
        elif tag == "select":
            prefix = "select"
        elif tag in {"textarea", "input"} or el.get("contenteditable"):
            prefix = "input"
        elif tag == "video":
            prefix = "video"
        else:
            prefix = "el"
        counters[prefix] += 1
        element_id = f"{prefix}_{counters[prefix]:03d}"
        record = dict(el)
        record["element_id"] = element_id
        record["click_blocked"] = _is_blocked_label(
            record.get("combined_label") or record.get("text") or ""
        )
        out[element_id] = record
    return out


def build_safety_for_label(semantic_label: str) -> dict[str, Any]:
    base = dict(LABEL_SAFETY_DEFAULTS.get(semantic_label, {}))
    if semantic_label == "generate_button":
        base.setdefault("auto_click_allowed", False)
        base.setdefault("requires_real_video_approval", True)
        base.setdefault("requires_approval", True)
    else:
        blocked_sem = _is_blocked_label(semantic_label.replace("_", " "))
        base.setdefault("auto_click_allowed", not blocked_sem)
        base.setdefault("requires_real_video_approval", False)
        base.setdefault("requires_approval", blocked_sem)
    return base


def resolve_label_safety(semantic_label: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Merge semantic label rules with clicked element text (Generate-like UI)."""
    safety = build_safety_for_label(semantic_label)
    combined = str(
        metadata.get("combined_label") or metadata.get("text") or metadata.get("aria_label") or ""
    ).lower()
    if semantic_label == "generate_button" or "generate" in combined:
        safety["auto_click_allowed"] = False
        safety["requires_approval"] = True
        safety["requires_real_video_approval"] = True
    elif _is_blocked_label(combined):
        safety["auto_click_allowed"] = False
        safety["requires_approval"] = True
    elif semantic_label in SAFE_CLICK_SEMANTIC_LABELS:
        safety.setdefault("auto_click_allowed", True)
        safety.setdefault("requires_approval", False)
    return safety


def _boxes_close(
    a: dict[str, Any] | None,
    b: dict[str, Any] | None,
    *,
    tolerance: int = 14,
) -> bool:
    if not a or not b:
        return False
    return (
        abs(int(a.get("x", 0)) - int(b.get("x", 0))) <= tolerance
        and abs(int(a.get("y", 0)) - int(b.get("y", 0))) <= tolerance
        and abs(int(a.get("width", 0)) - int(b.get("width", 0))) <= tolerance
        and abs(int(a.get("height", 0)) - int(b.get("height", 0))) <= tolerance
    )


def sanitize_click_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Strip storage/credential-like keys from click capture payloads."""
    forbidden_key_parts = ("cookie", "token", "localstorage", "sessionstorage", "authorization")
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        lower = str(key).lower()
        if any(part in lower for part in forbidden_key_parts):
            continue
        out[key] = value
    return out


def merge_clicked_element(
    elements: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> str:
    css = metadata.get("css_selector") or ""
    box = metadata.get("bounding_box") or {}
    for eid, el in elements.items():
        if el.get("css_selector") == css and _boxes_close(el.get("bounding_box"), box):
            el.update(
                {
                    "text": metadata.get("text") or el.get("text"),
                    "aria_label": metadata.get("aria_label") or el.get("aria_label"),
                    "combined_label": metadata.get("combined_label") or el.get("combined_label"),
                    "bounding_box": box or el.get("bounding_box"),
                    "page_url": metadata.get("page_url") or el.get("page_url"),
                    "page_title": metadata.get("page_title") or el.get("page_title"),
                    "click_blocked": metadata.get("click_blocked", el.get("click_blocked")),
                }
            )
            return eid
    record = sanitize_click_metadata(metadata)
    record.setdefault("visible", True)
    record.setdefault("combined_label", record.get("combined_label") or record.get("text") or "")
    assigned = assign_element_ids([record])
    elements.update(assigned)
    return next(iter(assigned))


def persist_click_label(
    ui_map: dict[str, Any],
    *,
    label_name: str,
    element_id: str,
    metadata: dict[str, Any],
    notes: str = "",
    operator_confirmed: bool = True,
) -> dict[str, Any]:
    clean_meta = sanitize_click_metadata(metadata)
    safety = resolve_label_safety(label_name, clean_meta)
    css = str(clean_meta.get("css_selector") or "")
    entry: dict[str, Any] = {
        "element_id": element_id,
        "metadata": clean_meta,
        "selector_candidates": {
            "css": css,
            "playwright": f"page.locator({json.dumps(css)})" if css else "",
        },
        "operator_confirmed": operator_confirmed,
        "confirmed_at": _now_iso(),
        "notes": notes[:500],
        "auto_click_allowed": bool(safety.get("auto_click_allowed")),
        "requires_approval": bool(safety.get("requires_approval")),
    }
    if safety.get("requires_real_video_approval"):
        entry["requires_real_video_approval"] = True
    labels = ui_map.setdefault("labels", {})
    labels[label_name] = entry
    if label_name == "generate_button" or entry["requires_approval"]:
        ui_map.setdefault("safety", dict(DEFAULT_SAFETY_V2))
        req = set(ui_map["safety"].get("requires_approval") or [])
        req.add(label_name)
        ui_map["safety"]["requires_approval"] = sorted(req)
    return entry


def append_labeling_session(ui_map: dict[str, Any], session: dict[str, Any]) -> None:
    sessions = ui_map.setdefault("labeling_sessions", [])
    sessions.append(session)


def init_v2_map(
    *,
    page: dict[str, Any],
    elements: dict[str, dict[str, Any]],
    open_tabs: list[dict[str, Any]] | None = None,
    scan_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = load_ui_map(allow_missing=True)
    merged_scan = dict(existing.get("scan") or {})
    if scan_meta:
        merged_scan.update(scan_meta)
    return {
        "version": MAPPER_VERSION_V2,
        "created_at": existing.get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
        "page": page,
        "open_tabs": open_tabs or existing.get("open_tabs") or [],
        "elements": elements,
        "labels": dict(existing.get("labels") or {}),
        "actions": dict(existing.get("actions") or {}),
        "labeling_sessions": list(existing.get("labeling_sessions") or []),
        "safety": dict(DEFAULT_SAFETY_V2),
        "scan": merged_scan,
    }


def load_ui_map(*, allow_missing: bool = False) -> dict[str, Any]:
    if not JSON_PATH.is_file():
        if allow_missing:
            return {}
        raise FileNotFoundError(f"Missing {JSON_PATH}. Run --scan first.")
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def load_candidates(*, allow_missing: bool = False) -> dict[str, Any]:
    if not CANDIDATES_PATH.is_file():
        if allow_missing:
            return {}
        raise FileNotFoundError(f"Missing {CANDIDATES_PATH}. Run --scan first.")
    return json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def save_ui_map(data: dict[str, Any]) -> Path:
    data["updated_at"] = _now_iso()
    if "version" not in data:
        data["version"] = MAPPER_VERSION_V2
    return save_json(JSON_PATH, data)


class RunwayUIMapper:
    def __init__(self, *, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser = None

    def connect(self) -> None:
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        print(f"[RunwayUIMapper] Connecting CDP: {self.cdp_url}")
        self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)

    def disconnect(self) -> None:
        print("[RunwayUIMapper] Disconnecting (Chrome stays open).")
        try:
            if self.playwright is not None:
                self.playwright.stop()
        except Exception as exc:
            print(f"[RunwayUIMapper] Playwright stop warning: {exc}")
        self.playwright = None
        self.browser = None

    def list_tabs(self) -> list[dict[str, Any]]:
        if self.browser is None:
            raise RuntimeError("Not connected")
        tabs: list[dict[str, Any]] = []
        index = 0
        for context in self.browser.contexts:
            for page in context.pages:
                try:
                    url = page.url or ""
                    title = page.title()
                except Exception:
                    url, title = "", ""
                tabs.append(
                    {
                        "index": index,
                        "url": _safe_url(url),
                        "title": str(title or "")[:200],
                        "is_runway_url": _is_runway_url(url),
                    }
                )
                index += 1
        return tabs

    def pick_page(self, tab_index: int | None = None):
        tabs = self.list_tabs()
        if not tabs:
            raise RuntimeError("No open tabs in CDP browser. Open Runway in Chrome first.")
        runway_indices = [t["index"] for t in tabs if t.get("is_runway_url")]
        if tab_index is None and not runway_indices:
            raise RuntimeError(
                "No Runway tab detected. Open https://app.runwayml.com and log in manually."
            )
        if tab_index is not None:
            if tab_index < 0 or tab_index >= len(tabs):
                raise RuntimeError(f"tab_index {tab_index} out of range (0..{len(tabs) - 1})")
            chosen = tab_index
        else:
            chosen = runway_indices[0]
        cursor = 0
        for context in self.browser.contexts:
            for page in context.pages:
                if cursor == chosen:
                    return page, tabs, chosen
                cursor += 1
        raise RuntimeError("Failed to resolve page for tab index")

    def extract_raw(self, page) -> dict[str, Any]:
        return page.evaluate(EXTRACT_ELEMENTS_JS)

    def capture_snapshot(self, page) -> dict[str, Any]:
        raw = self.extract_raw(page)
        elements = assign_element_ids(list(raw.get("elements") or []))
        return {
            "captured_at": _now_iso(),
            "page": {
                "url": _safe_url(raw.get("url") or ""),
                "title": str(raw.get("title") or "")[:200],
                "is_runway_url": _is_runway_url(raw.get("url") or ""),
            },
            "body_text_snippet": str(raw.get("body_text_snippet") or "")[:2000],
            "active_element": {
                "tag": str(raw.get("active_tag") or ""),
                "label": str(raw.get("active_label") or "")[:200],
            },
            "element_count": len(elements),
            "element_fingerprint": _fingerprint_elements(elements),
            "elements": elements,
        }

    def capture_screenshots(self, page, elements: dict[str, dict[str, Any]]) -> dict[str, str]:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        full_path = SCREENSHOTS_DIR / "00_full_page.png"
        page.screenshot(path=str(full_path), full_page=True)
        paths["full_page"] = _rel(full_path)
        viewport_path = SCREENSHOTS_DIR / "01_viewport.png"
        page.screenshot(path=str(viewport_path), full_page=False)
        paths["viewport"] = _rel(viewport_path)
        try:
            overlay = self._overlay_screenshot(full_path, elements)
            paths["overlay_numbered"] = _rel(overlay)
        except Exception as exc:
            print(f"[RunwayUIMapper] Overlay skipped: {exc}")
        return paths

    def _overlay_screenshot(self, base_image: Path, elements: dict[str, dict[str, Any]]) -> Path:
        from PIL import Image, ImageDraw, ImageFont

        visible = list(elements.values())[:40]
        image = Image.open(base_image).convert("RGBA")
        try:
            font = ImageFont.truetype("arial.ttf", 11)
        except Exception:
            font = ImageFont.load_default()
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        for el in visible:
            box = el.get("bounding_box") or {}
            x, y, w, h = box.get("x", 0), box.get("y", 0), box.get("width", 0), box.get("height", 0)
            if w < 4 or h < 4:
                continue
            color = (255, 80, 0, 200) if el.get("click_blocked") else (0, 180, 255, 200)
            odraw.rectangle([x, y, x + w, y + h], outline=color, width=2)
            tag = str(el.get("element_id") or "")[:10]
            label_top = max(0, y - 16)
            label_bottom = max(label_top + 1, y)
            odraw.rectangle([x, label_top, x + max(54, len(tag) * 6), label_bottom], fill=color)
            odraw.text((x + 2, label_top + 1), tag, fill=(255, 255, 255, 255), font=font)
        out = SCREENSHOTS_DIR / "02_overlay_numbered.png"
        Image.alpha_composite(image, overlay).convert("RGB").save(out)
        return out

    def mode_scan(self, *, tab_index: int | None = None) -> dict[str, Any]:
        self.connect()
        try:
            page, tabs, chosen = self.pick_page(tab_index)
            print(f"[RunwayUIMapper] SCAN tab={chosen} url={_safe_url(page.url)}")
            raw = self.extract_raw(page)
            elements = assign_element_ids(list(raw.get("elements") or []))
            page_info = {
                "url": _safe_url(raw.get("url") or ""),
                "title": str(raw.get("title") or "")[:200],
                "is_runway_url": _is_runway_url(raw.get("url") or ""),
            }
            screenshots = self.capture_screenshots(page, elements)
            for el in elements.values():
                el["screenshot_reference"] = screenshots.get("overlay_numbered") or screenshots.get("viewport")
                el["page_url"] = page_info["url"]
                el["page_title"] = page_info["title"]

            candidates = {
                "version": MAPPER_VERSION_V2,
                "scanned_at": _now_iso(),
                "page": page_info,
                "open_tabs": tabs,
                "selected_tab_index": chosen,
                "element_count": len(elements),
                "candidates": list(elements.values()),
            }
            save_json(CANDIDATES_PATH, candidates)

            ui_map = init_v2_map(
                page=page_info,
                elements=elements,
                open_tabs=tabs,
                scan_meta={
                    "mode": "scan",
                    "scanned_at": candidates["scanned_at"],
                    "selected_tab_index": chosen,
                    "screenshots": screenshots,
                    "body_text_snippet": str(raw.get("body_text_snippet") or "")[:4000],
                },
            )
            save_ui_map(ui_map)
            print(f"[RunwayUIMapper] Saved {len(elements)} elements -> {CANDIDATES_PATH.name}")
            return ui_map
        finally:
            self.disconnect()


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _fingerprint_elements(elements: dict[str, dict[str, Any]]) -> str:
    parts = []
    for eid in sorted(elements.keys())[:80]:
        el = elements[eid]
        parts.append(
            f"{eid}:{el.get('text','')[:24]}:{el.get('bounding_box',{}).get('y',0)}"
        )
    return "|".join(parts)


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b_el = before.get("elements") or {}
    a_el = after.get("elements") or {}
    b_ids = set(b_el.keys())
    a_ids = set(a_el.keys())
    added = [a_el[i] for i in sorted(a_ids - b_ids)][:20]
    removed = [b_el[i] for i in sorted(b_ids - a_ids)][:20]
    changed = []
    for eid in sorted(b_ids & a_ids):
        b, a = b_el[eid], a_el[eid]
        if (b.get("text"), b.get("visible")) != (a.get("text"), a.get("visible")):
            changed.append({"element_id": eid, "before": b, "after": a})
    return {
        "url_changed": before.get("page", {}).get("url") != after.get("page", {}).get("url"),
        "title_changed": before.get("page", {}).get("title") != after.get("page", {}).get("title"),
        "body_text_changed": before.get("body_text_snippet") != after.get("body_text_snippet"),
        "element_count_delta": after.get("element_count", 0) - before.get("element_count", 0),
        "added_elements": added,
        "removed_elements": removed,
        "changed_elements": changed[:20],
        "active_element_before": before.get("active_element"),
        "active_element_after": after.get("active_element"),
    }


def _print_candidate_table(elements: dict[str, dict[str, Any]], limit: int = 60) -> None:
    print("\n--- Visible elements (stable IDs) ---")
    for eid in sorted(elements.keys())[:limit]:
        el = elements[eid]
        if not el.get("visible"):
            continue
        label = (el.get("text") or el.get("aria_label") or el.get("combined_label") or "")[:50]
        tag = el.get("tag", "")
        box = el.get("bounding_box") or {}
        print(f"  {eid:12} [{tag:8}] ({box.get('x',0)},{box.get('y',0)}) {label!r}")
    extra = sum(1 for e in elements.values() if e.get("visible")) - limit
    if extra > 0:
        print(f"  ... and {extra} more visible elements")


def mode_label(*, from_stdin: str | None = None) -> int:
    """Manual labeling from selector_candidates.json or runway_ui_map.json elements."""
    data = load_candidates(allow_missing=True) or load_ui_map(allow_missing=True)
    if not data:
        print("[RunwayUIMapper] No candidates. Run: python tools/runway_ui_mapper.py --scan")
        return 1

    if "candidates" in data:
        elements_list = data["candidates"]
        elements = {el["element_id"]: el for el in elements_list if el.get("element_id")}
        page = data.get("page") or {}
    else:
        ui = load_ui_map()
        elements = dict(ui.get("elements") or {})
        page = ui.get("page") or {}

    if not elements:
        print("[RunwayUIMapper] No elements to label.")
        return 1

    _print_candidate_table(elements)
    print("\nValid labels:", ", ".join(VALID_SEMANTIC_LABELS))

    ui_map = load_ui_map(allow_missing=True)
    if not ui_map.get("elements"):
        ui_map = init_v2_map(page=page, elements=elements)
    labels: dict[str, Any] = dict(ui_map.get("labels") or {})

    def apply_label(element_id: str, semantic: str) -> None:
        if element_id not in elements:
            raise KeyError(element_id)
        entry = {
            "element_id": element_id,
            "semantic_label": semantic,
            "element": elements[element_id],
            "labeled_at": _now_iso(),
            **build_safety_for_label(semantic),
        }
        labels[semantic] = entry
        print(f"[RunwayUIMapper] Labeled {semantic} -> {element_id}")

    if from_stdin:
        # Format: element_id=btn_001 label=prompt_box  OR  btn_001 prompt_box
        for line in from_stdin.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line and "label=" in line:
                parts = dict(p.split("=", 1) for p in line.split() if "=" in p)
                apply_label(parts["element_id"], parts["label"])
            else:
                bits = line.split()
                if len(bits) >= 2:
                    apply_label(bits[0], bits[1])
    else:
        print("\nEnter element_id and semantic label (empty line to finish).")
        while True:
            try:
                eid = input("element_id> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[RunwayUIMapper] Label session ended.")
                break
            if not eid:
                break
            if eid == "?":
                _print_candidate_table(elements)
                continue
            try:
                semantic = input("semantic_label> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not semantic:
                continue
            if semantic not in VALID_SEMANTIC_LABELS:
                print(f"  Unknown label. Choose from: {', '.join(VALID_SEMANTIC_LABELS)}")
                continue
            if semantic == "skip":
                continue
            apply_label(eid, semantic)

    ui_map["elements"] = elements
    ui_map["labels"] = labels
    ui_map["page"] = page or ui_map.get("page") or {}
    if "generate_button" in labels:
        ui_map.setdefault("safety", dict(DEFAULT_SAFETY_V2))
        ui_map["safety"]["requires_approval"] = list(
            set(ui_map["safety"].get("requires_approval") or []) | {"generate_button"}
        )
    save_ui_map(ui_map)
    print(f"[RunwayUIMapper] Labels saved ({len(labels)}) -> {JSON_PATH}")
    return 0


def _start_quit_listener(stop_event) -> None:
    import threading

    def _reader() -> None:
        try:
            while not stop_event.is_set():
                line = input()
                if line.strip().lower() in {"q", "quit", "exit"}:
                    stop_event.set()
                    break
        except EOFError:
            stop_event.set()

    threading.Thread(target=_reader, daemon=True).start()


def mode_observe(
    mapper: RunwayUIMapper,
    *,
    tab_index: int | None = None,
    poll_seconds: float = 0.6,
) -> int:
    """Watch operator manual clicks; record before/after; never auto-click."""
    import threading

    mapper.connect()
    try:
        page, tabs, chosen = mapper.pick_page(tab_index)
        print(f"[RunwayUIMapper] OBSERVE tab={chosen} — click Runway UI manually.")
        print("[RunwayUIMapper] Tool will NOT click any buttons.")
        print("[RunwayUIMapper] Type 'q' + Enter here to stop, or Ctrl+C.")

        ui_map = load_ui_map(allow_missing=True)
        if not ui_map.get("elements"):
            snap = mapper.capture_snapshot(page)
            ui_map = init_v2_map(page=snap["page"], elements=snap["elements"], open_tabs=tabs)
        actions: dict[str, Any] = dict(ui_map.get("actions") or {})

        last_stable = mapper.capture_snapshot(page)
        action_idx = len(actions) + 1
        stop_event = threading.Event()
        _start_quit_listener(stop_event)

        while not stop_event.is_set():
            time.sleep(poll_seconds)
            current = mapper.capture_snapshot(page)
            diff = diff_snapshots(last_stable, current)
            changed = (
                diff.get("url_changed")
                or diff.get("title_changed")
                or diff.get("body_text_changed")
                or diff.get("added_elements")
                or diff.get("removed_elements")
                or diff.get("changed_elements")
                or diff.get("element_count_delta", 0) != 0
            )
            if not changed:
                continue
            print("\n[RunwayUIMapper] UI change detected.")
            print(f"  URL changed: {diff.get('url_changed')}")
            print(f"  Body changed: {diff.get('body_text_changed')}")
            print(f"  Elements +/-/delta: {len(diff.get('added_elements') or [])}/"
                  f"{len(diff.get('removed_elements') or [])}/{diff.get('element_count_delta')}")

            action_key = input(
                "What did this action do? (semantic action label, or 'other'): "
            ).strip() or "other"
            if action_key not in VALID_ACTION_LABELS:
                print(f"  Using 'other'. Valid: {', '.join(VALID_ACTION_LABELS)}")
                action_key = "other"

            record = {
                "action_id": f"action_{action_idx:03d}",
                "action_label": action_key,
                "observed_at": _now_iso(),
                "operator_initiated": True,
                "tool_auto_clicked": False,
                "before": last_stable,
                "after": current,
                "diff": diff,
            }
            if action_key == "other":
                note = input("Short note (optional): ").strip()
                if note:
                    record["operator_note"] = note[:240]

            actions[action_key] = record
            action_idx += 1
            last_stable = current
            ui_map["actions"] = actions
            ui_map["elements"] = current.get("elements") or ui_map.get("elements")
            ui_map["page"] = current.get("page") or ui_map.get("page")
            save_ui_map(ui_map)
            print(f"[RunwayUIMapper] Action recorded: {action_key}")

        save_ui_map(ui_map)
        print(f"[RunwayUIMapper] Observe session saved ({len(actions)} actions).")
        return 0
    finally:
        mapper.disconnect()


def _print_click_capture(meta: dict[str, Any]) -> None:
    print("\n--- Click captured ---")
    print(f"  tag={meta.get('tag')} role={meta.get('role')!r} type={meta.get('type')!r}")
    text = (meta.get("text") or meta.get("aria_label") or meta.get("combined_label") or "")[:80]
    print(f"  text: {text!r}")
    if meta.get("placeholder"):
        print(f"  placeholder: {meta.get('placeholder')!r}")
    print(f"  css: {meta.get('css_selector')}")
    box = meta.get("bounding_box") or {}
    print(f"  box: x={box.get('x')} y={box.get('y')} w={box.get('width')} h={box.get('height')}")
    if meta.get("nearby_text"):
        print(f"  nearby: {(meta.get('nearby_text') or '')[:60]!r}")
    print(f"  page: {_safe_url(meta.get('page_url') or '')}")
    print(f"  click_blocked (UI text): {meta.get('click_blocked')}")
    print(f"  prevented_default: {meta.get('prevented_default')}")


def mode_click_label(
    mapper: RunwayUIMapper,
    *,
    tab_index: int | None = None,
    allow_safe_clicks: bool = False,
) -> int:
    """Click elements in live Runway; terminal prompts for semantic labels."""
    import threading

    click_queue: list[dict[str, Any]] = []

    def _binding_click(_source, payload: dict[str, Any]) -> None:
        if isinstance(payload, dict):
            click_queue.append(payload)

    mapper.connect()
    session_started = _now_iso()
    labels_added: list[str] = []
    try:
        page, tabs, chosen = mapper.pick_page(tab_index)
        print(f"[RunwayUIMapper] CLICK-LABEL tab={chosen} url={_safe_url(page.url)}")
        print("[RunwayUIMapper] Click controls in the Runway browser to label them.")
        print("[RunwayUIMapper] Dangerous controls (Generate, Buy, etc.) never receive real clicks.")
        if allow_safe_clicks:
            print("[RunwayUIMapper] --allow-safe-clicks: non-dangerous clicks may pass through.")
        else:
            print("[RunwayUIMapper] All clicks blocked until you use --allow-safe-clicks.")
        print("[RunwayUIMapper] Type 'q' + Enter here to finish and save.")

        ui_map = load_ui_map(allow_missing=True)
        if not ui_map.get("elements"):
            snap = mapper.capture_snapshot(page)
            ui_map = init_v2_map(page=snap["page"], elements=snap["elements"], open_tabs=tabs)
        else:
            ui_map.setdefault("open_tabs", tabs)
            ui_map["page"] = ui_map.get("page") or (tabs[chosen] if chosen < len(tabs) else {})

        elements: dict[str, dict[str, Any]] = dict(ui_map.get("elements") or {})

        page.expose_binding("runwayMapperReportClick", _binding_click)
        page.evaluate(CLICK_LABEL_INSTALL_JS, allow_safe_clicks)

        stop_event = threading.Event()
        _start_quit_listener(stop_event)

        while not stop_event.is_set():
            while click_queue and not stop_event.is_set():
                meta = sanitize_click_metadata(click_queue.pop(0))
                _print_click_capture(meta)
                try:
                    label_name = input("What is this control? ").strip()
                except (EOFError, KeyboardInterrupt):
                    stop_event.set()
                    break
                if not label_name or label_name.lower() in {"q", "quit", "exit"}:
                    if label_name.lower() in {"q", "quit", "exit"}:
                        stop_event.set()
                    continue
                if label_name == "skip":
                    continue
                if label_name not in VALID_SEMANTIC_LABELS:
                    print(f"  Unknown label. Valid: {', '.join(VALID_SEMANTIC_LABELS)}")
                    continue
                try:
                    behavior = input("What does this control do? (optional): ").strip()
                except (EOFError, KeyboardInterrupt):
                    behavior = ""
                    stop_event.set()

                element_id = merge_clicked_element(elements, meta)
                persist_click_label(
                    ui_map,
                    label_name=label_name,
                    element_id=element_id,
                    metadata=meta,
                    notes=behavior,
                    operator_confirmed=True,
                )
                labels_added.append(label_name)
                ui_map["elements"] = elements
                ui_map["page"] = {
                    "url": _safe_url(meta.get("page_url") or page.url or ""),
                    "title": str(meta.get("page_title") or "")[:200],
                    "is_runway_url": _is_runway_url(meta.get("page_url") or ""),
                }
                ui_map.setdefault("scan", {})["last_click_label_at"] = _now_iso()
                save_ui_map(ui_map)
                print(f"[RunwayUIMapper] Saved label {label_name!r} -> {element_id}")

            time.sleep(0.12)

        try:
            page.evaluate("() => window.__runwayMapperTeardown && window.__runwayMapperTeardown()")
        except Exception:
            pass

        append_labeling_session(
            ui_map,
            {
                "session_id": f"click_label_{session_started.replace(':', '').replace('-', '')[:15]}",
                "mode": "click-label",
                "started_at": session_started,
                "ended_at": _now_iso(),
                "labels_added": labels_added,
                "allow_safe_clicks": allow_safe_clicks,
                "selected_tab_index": chosen,
                "page_url": _safe_url((ui_map.get("page") or {}).get("url") or ""),
            },
        )
        save_ui_map(ui_map)
        print(
            f"[RunwayUIMapper] Click-label session saved "
            f"({len(labels_added)} labels) -> {JSON_PATH}"
        )
        return 0
    finally:
        mapper.disconnect()


def capture_click_metadata_for_test(meta: dict[str, Any]) -> dict[str, Any]:
    """Test helper: sanitize + merge without browser."""
    return sanitize_click_metadata(meta)


def mode_label_noninteractive_for_test(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Test helper: apply labels without stdin."""
    lines = [f"element_id={e} label={l}" for e, l in pairs]
    mode_label(from_stdin="\n".join(lines))
    return load_ui_map()


def legacy_scan_compat(mapper: RunwayUIMapper, tab_index: int | None) -> dict[str, Any]:
    """Backward-compatible v1-style categories embedded in scan meta."""
    ui = mapper.mode_scan(tab_index=tab_index)
    return ui


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runway UI mapper + manual learning (CDP).")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--tab-index", type=int, default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scan", action="store_true", help="Read-only scan; save candidates + v2 map")
    mode.add_argument("--label", action="store_true", help="Manual semantic labeling session")
    mode.add_argument("--observe", action="store_true", help="Observe manual clicks; record actions")
    mode.add_argument(
        "--click-label",
        action="store_true",
        help="Click elements in browser; terminal prompts for labels",
    )
    parser.add_argument(
        "--allow-safe-clicks",
        action="store_true",
        help="With --click-label: allow non-dangerous clicks through to Runway",
    )
    parser.add_argument(
        "--label-batch",
        default=None,
        help="Non-interactive labels: lines 'element_id=btn_001 label=prompt_box'",
    )
    parser.add_argument("--observe-poll", type=float, default=0.6)
    # Legacy v1 flag -> scan only
    parser.add_argument(
        "--interactive-map",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    mapper = RunwayUIMapper(cdp_url=args.cdp_url)

    if args.label or args.label_batch:
        return mode_label(from_stdin=args.label_batch)

    if args.observe:
        try:
            return mode_observe(mapper, tab_index=args.tab_index, poll_seconds=args.observe_poll)
        except Exception as exc:
            print(f"[RunwayUIMapper] OBSERVE FAILED: {exc}")
            return 1

    if args.click_label:
        try:
            return mode_click_label(
                mapper,
                tab_index=args.tab_index,
                allow_safe_clicks=args.allow_safe_clicks,
            )
        except Exception as exc:
            print(f"[RunwayUIMapper] CLICK-LABEL FAILED: {exc}")
            return 1

    # Default and --scan and legacy --interactive-map (scan only, no auto clicks)
    try:
        ui_map = mapper.mode_scan(tab_index=args.tab_index)
    except Exception as exc:
        print(f"[RunwayUIMapper] SCAN FAILED: {exc}")
        return 1

    print("\n[RunwayUIMapper] SCAN complete")
    print(f"  Elements: {len(ui_map.get('elements') or {})}")
    print(f"  Page: {(ui_map.get('page') or {}).get('url')}")
    print(f"  Candidates: {CANDIDATES_PATH}")
    print(f"  Map: {JSON_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
