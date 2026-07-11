#!/usr/bin/env python3
"""
Phase RUNWAY-UI-MAPPER-D — Safe Runway UI discovery + manual learning via Chrome CDP.

Modes: --scan, --label, --observe, --click-label, --hover-label (Alt+Click or Mapper ON → label popup).

Never: auto-click Generate, create video, spend credits, store credentials/cookies/storage, auto-login.
Hover-label (--hover-label): press L over target — no click, safe for Download / Generate / Buy controls.
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
    "prompt_input",
    "generate_button",
    "try_it_now_button",
    "duration_10s",
    "duration_8s",
    "duration_menu",
    "aspect_ratio_16_9",
    "aspect_ratio_9_16",
    "aspect_ratio_menu",
    "model_selector",
    "gen45_option",
    "gen45_model_button",
    "video_generation_button",
    "first_video_frame_upload",
    "reference_image_upload",
    "download_button",
    "download_mp4_button",
    "use_frame_button",
    "remove_image",
    "generated_video_card",
    "generation_status",
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

VALID_CONTROL_TYPES: tuple[str, ...] = (
    "direct_button",
    "dropdown_menu",
    "hover_menu",
    "menu_option",
    "upload_area",
    "status_text",
    "input_box",
)

# Semantic labels where automation may click without approval (when map says allowed).
SAFE_CLICK_SEMANTIC_LABELS: frozenset[str] = frozenset(
    {
        "prompt_box",
        "prompt_input",
        "duration_10s",
        "duration_8s",
        "duration_menu",
        "aspect_ratio_16_9",
        "aspect_ratio_9_16",
        "aspect_ratio_menu",
        "gen45_option",
        "gen45_model_button",
        "model_selector",
        "try_it_now_button",
        "first_video_frame_upload",
        "reference_image_upload",
        "download_button",
        "download_mp4_button",
        "use_frame_button",
        "remove_image",
        "generated_video_card",
        "generation_status",
        "queue_status_text",
        "progress_status_text",
    }
)

# Phase RUNWAY-BROWSER-CONTINUITY-C — completion via output controls (not status text)
CONTINUITY_COMPLETION_SIGNAL_LABELS: tuple[str, ...] = (
    "download_mp4_button",
    "use_frame_button",
)

CONTINUITY_COMPLETION_POLL_SECONDS: tuple[int, int] = (30, 60)

GENERATION_COMPLETE_RULE: dict[str, Any] = {
    "strategy": "output_controls_visible",
    "description": (
        "generation_complete when download_mp4_button OR use_frame_button is visible "
        "on the Gen-4.5 tools session output view"
    ),
    "expression": "download_mp4_button_visible OR use_frame_button_visible",
    "poll_interval_seconds": list(CONTINUITY_COMPLETION_POLL_SECONDS),
    "signals": list(CONTINUITY_COMPLETION_SIGNAL_LABELS),
    "generation_status_required": False,
}

# Labels allowed with weak/generic selectors until operator re-labels (Phase C).
WEAK_SELECTOR_TOLERANCE_LABELS: frozenset[str] = frozenset({"use_frame_button"})

# Phase RUNWAY-BROWSER-CONTINUITY-B/C — relabeling targets + validation
# Phase RUNWAY-STARTER-TO-VIDEO — starter image generation mapped labels (Image Gen tool).
STARTER_IMAGE_CANONICAL_LABELS: tuple[str, ...] = (
    "image_prompt_input",
    "image_aspect_ratio_menu",
    "image_aspect_ratio_9_16",
    "image_count_menu",
    "image_count_1",
    "image_count_4",
    "image_quality_menu",
    "image_quality_1k",
    "image_quality_2k",
    "image_quality_4k",
    "image_generate_button",
    "image_app_menu_button",
    "image_use_to_video_option",
)

STARTER_IMAGE_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "image_prompt_input": ("image_prompt_input", "Text to Image box", "Text to image box"),
    "image_aspect_ratio_menu": ("image_aspect_ratio_menu", "image_aspect_ratio"),
    "image_aspect_ratio_9_16": ("image_aspect_ratio_9_16", "aspect_ratio_9_16"),
    "image_count_menu": ("image_count_menu", "image_count"),
    "image_count_1": ("image_count_1", "1"),
    "image_count_4": ("image_count_4", "4"),
    "image_quality_menu": ("image_quality_menu", "image_quality", "Quality"),
    "image_quality_1k": ("image_quality_1k", "1K", "1k"),
    "image_quality_2k": ("image_quality_2k", "2K", "2k"),
    "image_quality_4k": ("image_quality_4k", "4K", "4k"),
    "image_generate_button": ("image_generate_button", "Generate Image", "Generate"),
    "image_app_menu_button": ("image_app_menu_button",),
    "image_use_to_video_option": (
        "image_use_to_video_option",
        "Use to Video",
        "Use in video",
    ),
}

CONTINUITY_CRITICAL_LABELS: tuple[str, ...] = (
    "download_mp4_button",
    "use_frame_button",
    "remove_image",
    "duration_menu",
    "aspect_ratio_menu",
    "duration_10s",
    "aspect_ratio_9_16",
    "aspect_ratio_16_9",
)

CONTINUITY_OPTIONAL_LABELS: tuple[str, ...] = (
    "generation_status",
    "queue_status_text",
    "progress_status_text",
)

CONTINUITY_PREREQUISITE_LABELS: tuple[str, ...] = (
    "prompt_input",
    "gen45_model_button",
    "try_it_now_button",
    "generate_button",
)

CONTINUITY_ALL_REQUIRED_LABELS: tuple[str, ...] = CONTINUITY_PREREQUISITE_LABELS + CONTINUITY_CRITICAL_LABELS

CONTINUITY_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "prompt_input": ("prompt_input", "prompt_box", "Prompt Box"),
    "gen45_model_button": ("gen45_model_button", "gen45_option", "Gen-4.5", "Ge-4.5"),
    "try_it_now_button": ("try_it_now_button", "Try it now"),
    "generate_button": ("generate_button", "Geerate", "Generate"),
    "download_mp4_button": ("download_mp4_button", "download_button", "DOWNLOAD MP4"),
    "generation_status": ("generation_status", "queue_status_text", "progress_status_text"),
    "use_frame_button": ("use_frame_button", "USE FRAME"),
    "remove_image": (
        "remove_image",
        "REMOVE IMAGE",
        "Remove image",
        "remove image",
        "Remove Image",
    ),
    "duration_menu": ("duration_menu", "VIEDO DURATION KONOPF"),
    "aspect_ratio_menu": ("aspect_ratio_menu",),
    "duration_10s": ("duration_10s", "10s duration", "10S"),
    "aspect_ratio_9_16": (
        "aspect_ratio_9_16",
        "aspect_ratio_menu 9: 16",
        "aspect_ratio_menu 9:16",
    ),
    "aspect_ratio_16_9": (
        "aspect_ratio_16_9",
        "aspect_ratio_menu 16:9",
        "16:9",
        "16.9 MODE",
        "16.9",
    ),
}

LABEL_NORMALIZATION_SUGGESTIONS: dict[str, str] = {
    "DOWNLOAD MP4": "download_mp4_button",
    "DOWNLOAD ALL": "download_mp4_button",
    "USE FRAME": "use_frame_button",
    "aspect_ratio_menu 9: 16": "aspect_ratio_9_16",
    "aspect_ratio_menu 9:16": "aspect_ratio_9_16",
    "aspect_ratio_menu 16:9": "aspect_ratio_16_9",
    "Prompt Box": "prompt_input",
    "Gen-4.5": "gen45_model_button",
    "Ge-4.5": "gen45_model_button",
    "Try it now": "try_it_now_button",
    "Geerate": "generate_button",
    "10s duration": "duration_10s",
    "8s duration": "duration_8s",
    "VIEDO DURATION KONOPF": "duration_menu",
    "REMOVE IMAGE": "remove_image",
    "Remove image": "remove_image",
}

CANONICAL_CONTINUITY_LABEL_ORDER: tuple[str, ...] = CONTINUITY_ALL_REQUIRED_LABELS

FORBIDDEN_CAPTURE_TAGS: frozenset[str] = frozenset({"body", "html"})

GENERIC_CSS_SELECTORS: frozenset[str] = frozenset(
    {
        "body",
        "html",
        "span",
        "div",
        "svg",
        "a",
        "button",
        "label",
        "video",
        "input",
        "select",
        "textarea",
    }
)

QUALIFIED_SELECTOR_MARKERS: tuple[str, ...] = (
    "[",
    "#",
    ":",
    "data-testid",
    "aria-label",
    "role=",
    "nth-",
)

TOOLS_SESSION_URL_MARKERS: tuple[str, ...] = ("mode=tools", "tool=video")

USE_FRAME_ALLOWED_URL_MARKERS: tuple[str, ...] = ("mode=tools", "tool=video")

USE_FRAME_FORBIDDEN_URL_MARKERS: tuple[str, ...] = (
    "mode=apps",
    "mode=sessions",
    "app=multi-shot",
    "/recents",
)

DOWNLOAD_MP4_ALLOWED_TAGS: frozenset[str] = frozenset(
    {"button", "a", "span", "div", "li", "menuitem"}
)

EXPECTED_CONTROL_TEXT: dict[str, tuple[str, ...]] = {
    "download_mp4_button": ("download",),
    "use_frame_button": ("use frame", "use frame image"),
    "remove_image": ("remove", "remove image", "clear", "delete image"),
    "generation_status": (
        "queue",
        "generating",
        "processing",
        "progress",
        "ready",
        "complete",
        "minute",
        "second",
        "%",
        "waiting",
    ),
    "duration_10s": ("10s", "10 seconds", "10 sec"),
    "duration_8s": ("8s", "8 seconds", "8 sec"),
    "aspect_ratio_9_16": ("9:16",),
    "aspect_ratio_16_9": ("16:9",),
    "duration_menu": ("5s", "8s", "10s", "duration", "second"),
    "aspect_ratio_menu": ("16:9", "9:16", "aspect", "ratio"),
}

CONTINUITY_RELABEL_CHECKLIST: tuple[dict[str, str], ...] = (
    {
        "step": "1",
        "label": "duration_menu",
        "when": "Gen-4.5 editor open (mode=tools&tool=video), before opening menu",
        "target": "Duration chip/button showing current value (e.g. 5s)",
        "avoid": "Menu option rows — label those as duration_10s / duration_8s",
    },
    {
        "step": "2",
        "label": "duration_10s",
        "when": "After clicking duration_menu",
        "target": "Menu row with text '10 seconds' or '10s'",
        "avoid": "Toolbar chip before menu opens",
    },
    {
        "step": "3",
        "label": "aspect_ratio_menu",
        "when": "Gen-4.5 editor, before opening ratio dropdown",
        "target": "Aspect ratio chip/button (shows 16:9 or 9:16)",
        "avoid": "Individual menu options",
    },
    {
        "step": "4",
        "label": "aspect_ratio_16_9",
        "when": "After clicking aspect_ratio_menu",
        "target": "Menu option row '16:9'",
        "avoid": "Multi-Shot or apps view",
    },
    {
        "step": "5",
        "label": "aspect_ratio_9_16",
        "when": "After clicking aspect_ratio_menu",
        "target": "Menu option row '9:16'",
        "avoid": "Label key with space typo (use aspect_ratio_9_16)",
    },
    {
        "step": "6",
        "label": "download_mp4_button",
        "when": "Generation complete — output view shows Download on the clip card",
        "target": "Button/link/menu item whose text or aria-label includes 'Download'",
        "avoid": "body/html, Download all batch icon, entire page — use --hover-label + L (no click)",
    },
    {
        "step": "7",
        "label": "use_frame_button",
        "when": "Same completed output view (appears with download_mp4_button)",
        "target": "Control with text 'Use frame' or 'Use frame image' on the video card",
        "avoid": "mode=apps, recents, multi-shot; weak span OK temporarily — re-label when possible",
    },
    {
        "step": "8",
        "label": "remove_image",
        "when": "After final clip — reference image still in upload/first-frame area",
        "target": "Remove / clear / X control on the lingering reference image thumbnail",
        "avoid": "Use frame (different action); do not capture page body",
    },
)

CLICK_LABEL_SAVE_PREFIX = "__RUNWAY_MAPPER_SAVE__"

CLICK_LABEL_INSTALL_JS = """
() => {
  const SAVE_PREFIX = '__RUNWAY_MAPPER_SAVE__';
  const HIGHLIGHT_CLASS = 'runway-mapper-click-highlight';
  const STYLE_ID = 'runway-mapper-click-style';
  const POPUP_ID = 'runway-mapper-popup';
  const TOGGLE_ID = 'runway-mapper-toggle';

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) {
      try { return '#' + CSS.escape(el.id); } catch (e) { return '#' + el.id; }
    }
    const testId = el.getAttribute('data-testid');
    if (testId) return '[data-testid="' + testId + '"]';
    const aria = el.getAttribute('aria-label');
    if (aria) return el.tagName.toLowerCase() + '[aria-label="' + aria.replace(/"/g, '\\\\"') + '"]';
    return el.tagName.toLowerCase();
  }

  function buildMeta(el) {
    const rect = el.getBoundingClientRect();
    return {
      tag: (el.tagName || '').toLowerCase(),
      role: el.getAttribute('role') || '',
      text: (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 200),
      aria_label: el.getAttribute('aria-label') || '',
      css_selector: cssPath(el),
      bounding_box: {
        x: Math.round(rect.x), y: Math.round(rect.y),
        width: Math.round(rect.width), height: Math.round(rect.height),
      },
      page_url: location.href || '',
      page_title: document.title || '',
    };
  }

  function clearHighlight() {
    document.querySelectorAll('.' + HIGHLIGHT_CLASS).forEach(n => n.classList.remove(HIGHLIGHT_CLASS));
  }

  function emitSave(payload) {
    payload._save_id = String(Date.now()) + '_' + Math.random().toString(16).slice(2);
    const line = SAVE_PREFIX + JSON.stringify(payload);
    try {
      document.documentElement.setAttribute('data-runway-mapper-pending-save', line);
    } catch (e) {}
    try {
      console.log(line);
    } catch (e) {}
    try {
      if (typeof window.runwayMapperSaveLabel === 'function') {
        window.runwayMapperSaveLabel(payload);
      }
    } catch (e) {}
  }

  function closePopup() {
    const popup = document.getElementById(POPUP_ID);
    if (popup) popup.remove();
    window.__runwayMapperPendingMeta = null;
    clearHighlight();
  }

  window.__runwayMapperDismissAfterSave = function() {
    closePopup();
  };

  function highlight(el) {
    clearHighlight();
    if (el && el.classList) el.classList.add(HIGHLIGHT_CLASS);
  }

  function onPopupSaveClick(meta, labelInput, warnEl) {
    console.log('MAPPER_POPUP_SAVE_CLICKED');
    const labelName = (labelInput.value || '').trim();
    if (!labelName) {
      warnEl.style.display = 'block';
      labelInput.focus();
      return;
    }
    warnEl.style.display = 'none';
    const payload = {
      label_name: labelName,
      metadata: window.__runwayMapperPendingMeta || meta,
    };
    payload._save_id = String(Date.now()) + '_' + Math.random().toString(16).slice(2);
    const line = SAVE_PREFIX + JSON.stringify(payload);
    try {
      document.documentElement.setAttribute('data-runway-mapper-pending-save', line);
    } catch (e) {}
    try {
      console.log(line);
    } catch (e) {}
    try {
      if (typeof window.runwayMapperSaveLabel === 'function') {
        window.runwayMapperSaveLabel(payload);
      }
    } catch (e) {}
  }

  function onPopupCancelClick() {
    console.log('MAPPER_POPUP_CANCEL_CLICKED');
    closePopup();
  }

  function openPopup(target, meta) {
    closePopup();
    highlight(target);
    window.__runwayMapperPendingMeta = meta;
    const rect = target.getBoundingClientRect();
    const popup = document.createElement('div');
    popup.id = POPUP_ID;
    popup.innerHTML =
      '<div class="rm-head">Label</div>' +
      '<input type="text" id="rm-label" class="rm-label-input" autocomplete="off" placeholder="e.g. test_button" />' +
      '<div id="rm-warn" class="rm-warn" style="display:none;color:#fca5a5;font-size:11px;margin:4px 0;">Enter a label first</div>' +
      '<div class="rm-actions">' +
      '<button type="button" id="rm-save">Save</button>' +
      '<button type="button" id="rm-cancel">Cancel</button>' +
      '</div>';
    document.body.appendChild(popup);
    popup.style.position = 'fixed';
    popup.style.zIndex = '2147483647';
    let left = rect.right + 8;
    let top = rect.top;
    const pw = 240;
    const ph = 110;
    if (left + pw > window.innerWidth - 8) left = Math.max(8, rect.left - pw - 8);
    if (top + ph > window.innerHeight - 8) top = Math.max(8, window.innerHeight - ph - 8);
    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
    const labelInput = popup.querySelector('#rm-label');
    const warnEl = popup.querySelector('#rm-warn');
    const saveBtn = popup.querySelector('#rm-save');
    const cancelBtn = popup.querySelector('#rm-cancel');
    labelInput.focus();
    saveBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      onPopupSaveClick(meta, labelInput, warnEl);
    });
    cancelBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      onPopupCancelClick();
    });
  }

  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent =
      '.' + HIGHLIGHT_CLASS + ' { outline: 3px solid #00b4ff !important; outline-offset: 2px !important; }' +
      '#' + POPUP_ID + ' { background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px;' +
      ' padding:10px; width:240px; font:13px system-ui,sans-serif; box-shadow:0 6px 20px rgba(0,0,0,.4); }' +
      '#' + POPUP_ID + ' .rm-head { font-weight:600; margin-bottom:8px; }' +
      '#' + POPUP_ID + ' .rm-label-input { width:100%; box-sizing:border-box; padding:6px 8px; margin-bottom:8px;' +
      ' border-radius:6px; border:1px solid #475569; background:#1e293b; color:#fff; }' +
      '#' + POPUP_ID + ' .rm-actions { display:flex; gap:8px; }' +
      '#' + POPUP_ID + ' .rm-actions button { flex:1; padding:6px; border:none; border-radius:6px; cursor:pointer; }' +
      '#' + POPUP_ID + ' #rm-save { background:#0ea5e9; color:#fff; font-weight:600; }' +
      '#' + POPUP_ID + ' #rm-cancel { background:#334155; color:#e2e8f0; }';
    (document.head || document.documentElement).appendChild(style);
  }

  const CAPTURE_OPTS = { capture: true, passive: false };

  window.__runwayMapperForceMode = false;
  window.__runwayMapperAltDown = false;

  function isInsideMapperUI(ev) {
    const popup = document.getElementById(POPUP_ID);
    const toggle = document.getElementById(TOGGLE_ID);
    const t = ev.target;
    if (!t) return false;
    if (popup && popup.contains(t)) return true;
    if (toggle && toggle.contains(t)) return true;
    return false;
  }

  function isCaptureActive(ev) {
    return !!(ev && (ev.altKey || window.__runwayMapperAltDown || window.__runwayMapperForceMode));
  }

  function logMapperClick(ev, phase) {
    try {
      console.log('MAPPER_CLICK', JSON.stringify({
        phase: phase,
        altKey: !!ev.altKey,
        mapperAltDown: !!window.__runwayMapperAltDown,
        forceMode: !!window.__runwayMapperForceMode,
        captureActive: isCaptureActive(ev),
        target: (ev.target && ev.target.tagName) || '',
        type: ev.type || '',
      }));
    } catch (e) {}
  }

  function blockEvent(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
  }

  function refreshToggleButton() {
    const btn = document.getElementById(TOGGLE_ID);
    if (!btn) return;
    btn.textContent = window.__runwayMapperForceMode ? 'Mapper: ON' : 'Mapper: OFF';
    btn.style.background = window.__runwayMapperForceMode ? '#0ea5e9' : '#475569';
    btn.style.color = '#fff';
  }

  function installToggleButton() {
    if (document.getElementById(TOGGLE_ID)) {
      refreshToggleButton();
      return;
    }
    const btn = document.createElement('button');
    btn.id = TOGGLE_ID;
    btn.type = 'button';
    btn.style.cssText =
      'position:fixed;top:12px;right:12px;z-index:2147483647;padding:8px 12px;border:none;border-radius:8px;' +
      'font:600 12px system-ui,sans-serif;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.35);';
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      window.__runwayMapperForceMode = !window.__runwayMapperForceMode;
      refreshToggleButton();
    });
    document.body.appendChild(btn);
    refreshToggleButton();
  }

  let lastPopupTarget = null;
  let lastPopupAt = 0;

  function tryCapture(ev, phase) {
    const popup = document.getElementById(POPUP_ID);
    const toggle = document.getElementById(TOGGLE_ID);
    if (
      (popup && popup.contains(ev.target)) ||
      (toggle && toggle.contains(ev.target))
    ) {
      return;
    }
    logMapperClick(ev, phase);
    if (!isCaptureActive(ev)) return;

    blockEvent(ev);

    const target = ev.target;
    if (!target || target.nodeType !== 1) return;

    const now = Date.now();
    if (lastPopupTarget === target && now - lastPopupAt < 500) return;

    if (phase === 'pointerdown' || phase === 'mousedown' || phase === 'click') {
      lastPopupTarget = target;
      lastPopupAt = now;
      openPopup(target, buildMeta(target));
    }
  }

  function onKeyDown(ev) {
    if (ev.key === 'Alt') window.__runwayMapperAltDown = true;
    if (ev.key === 'Escape') closePopup();
  }

  function onKeyUp(ev) {
    if (ev.key === 'Alt') window.__runwayMapperAltDown = false;
  }

  function onWindowBlur() {
    window.__runwayMapperAltDown = false;
  }

  function onPointerDown(ev) { tryCapture(ev, 'pointerdown'); }
  function onMouseDown(ev) { tryCapture(ev, 'mousedown'); }
  function onClick(ev) { tryCapture(ev, 'click'); }

  if (window.__runwayMapperTeardown) {
    window.__runwayMapperTeardown();
  }

  window.__runwayMapperTeardown = () => {
    document.removeEventListener('pointerdown', onPointerDown, true);
    document.removeEventListener('mousedown', onMouseDown, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKeyDown, true);
    document.removeEventListener('keyup', onKeyUp, true);
    window.removeEventListener('blur', onWindowBlur, true);
    closePopup();
    const toggle = document.getElementById(TOGGLE_ID);
    if (toggle) toggle.remove();
    window.__runwayMapperAltDown = false;
    window.__runwayMapperForceMode = false;
    window.__runwayMapperClickLabelActive = false;
  };

  installToggleButton();
  document.addEventListener('pointerdown', onPointerDown, CAPTURE_OPTS);
  document.addEventListener('mousedown', onMouseDown, CAPTURE_OPTS);
  document.addEventListener('click', onClick, CAPTURE_OPTS);
  document.addEventListener('keydown', onKeyDown, true);
  document.addEventListener('keyup', onKeyUp, true);
  window.addEventListener('blur', onWindowBlur, true);
  window.__runwayMapperClickLabelActive = true;
  console.log('MAPPER_INSTALL', JSON.stringify({
    href: location.href,
    capture: true,
    modes: ['alt_click', 'force_mode'],
  }));
  return true;
}
"""

HOVER_LABEL_INSTALL_JS = """
() => {
  const SAVE_PREFIX = '__RUNWAY_MAPPER_SAVE__';
  const HIGHLIGHT_CLASS = 'runway-mapper-hover-highlight';
  const PREVIEW_CLASS = 'runway-mapper-hover-preview';
  const STYLE_ID = 'runway-mapper-hover-style';
  const POPUP_ID = 'runway-mapper-hover-popup';
  const BADGE_ID = 'runway-mapper-hover-badge';
  const L_FLASH_ID = 'runway-mapper-l-flash';
  const KEY_OPTS = { capture: true, passive: false };

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) {
      try { return '#' + CSS.escape(el.id); } catch (e) { return '#' + el.id; }
    }
    const testId = el.getAttribute('data-testid');
    if (testId) return '[data-testid="' + testId + '"]';
    const aria = el.getAttribute('aria-label');
    if (aria) return el.tagName.toLowerCase() + '[aria-label="' + aria.replace(/"/g, '\\\\"') + '"]';
    return el.tagName.toLowerCase();
  }

  function buildMeta(el) {
    const rect = el.getBoundingClientRect();
    return {
      tag: (el.tagName || '').toLowerCase(),
      role: el.getAttribute('role') || '',
      text: (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 200),
      aria_label: el.getAttribute('aria-label') || '',
      css_selector: cssPath(el),
      bounding_box: {
        x: Math.round(rect.x), y: Math.round(rect.y),
        width: Math.round(rect.width), height: Math.round(rect.height),
      },
      page_url: location.href || '',
      page_title: document.title || '',
      capture_mode: 'hover_label',
    };
  }

  function clearHighlight() {
    document.querySelectorAll('.' + HIGHLIGHT_CLASS).forEach(n => n.classList.remove(HIGHLIGHT_CLASS));
  }

  function clearPreview() {
    document.querySelectorAll('.' + PREVIEW_CLASS).forEach(n => n.classList.remove(PREVIEW_CLASS));
  }

  function closePopup() {
    const popup = document.getElementById(POPUP_ID);
    if (popup) popup.remove();
    window.__runwayMapperHoverPendingMeta = null;
    clearHighlight();
  }

  window.__runwayMapperDismissAfterSave = function() {
    closePopup();
  };

  function highlight(el) {
    clearHighlight();
    if (el && el.classList) el.classList.add(HIGHLIGHT_CLASS);
  }

  function isInsideMapperUI(target) {
    if (!target) return false;
    const popup = document.getElementById(POPUP_ID);
    const badge = document.getElementById(BADGE_ID);
    if (popup && popup.contains(target)) return true;
    if (badge && badge.contains(target)) return true;
    return false;
  }

  function isTypingContext() {
    const active = document.activeElement;
    if (!active) return false;
    const tag = (active.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (active.isContentEditable) return true;
    return false;
  }

  function onPopupSaveClick(meta, labelInput, warnEl) {
    const labelName = (labelInput.value || '').trim();
    if (!labelName) {
      warnEl.style.display = 'block';
      labelInput.focus();
      return;
    }
    warnEl.style.display = 'none';
    const payload = {
      label_name: labelName,
      metadata: window.__runwayMapperHoverPendingMeta || meta,
      capture_mode: 'hover_label',
    };
    payload._save_id = String(Date.now()) + '_' + Math.random().toString(16).slice(2);
    const line = SAVE_PREFIX + JSON.stringify(payload);
    try {
      document.documentElement.setAttribute('data-runway-mapper-pending-save', line);
    } catch (e) {}
    try {
      console.log(line);
    } catch (e) {}
    try {
      if (typeof window.runwayMapperSaveLabel === 'function') {
        window.runwayMapperSaveLabel(payload);
      }
    } catch (e) {}
  }

  function onPopupCancelClick() {
    closePopup();
  }

  function openPopup(target, meta) {
    console.log('MAPPER_HOVER_POPUP_OPEN', JSON.stringify({
      tag: (target && target.tagName) || '',
      css: (meta && meta.css_selector) || '',
    }));
    closePopup();
    highlight(target);
    window.__runwayMapperHoverPendingMeta = meta;
    const rect = target.getBoundingClientRect();
    const popup = document.createElement('div');
    popup.id = POPUP_ID;
    popup.innerHTML =
      '<div class="rm-head">Label (hover — no click)</div>' +
      '<input type="text" id="rm-label" class="rm-label-input" autocomplete="off" placeholder="e.g. download_mp4_button" />' +
      '<div id="rm-warn" class="rm-warn" style="display:none;color:#fca5a5;font-size:11px;margin:4px 0;">Enter a label first</div>' +
      '<div class="rm-actions">' +
      '<button type="button" id="rm-save">Save</button>' +
      '<button type="button" id="rm-cancel">Cancel</button>' +
      '</div>';
    document.body.appendChild(popup);
    popup.style.position = 'fixed';
    popup.style.zIndex = '2147483647';
    let left = rect.right + 8;
    let top = rect.top;
    const pw = 260;
    const ph = 120;
    if (left + pw > window.innerWidth - 8) left = Math.max(8, rect.left - pw - 8);
    if (top + ph > window.innerHeight - 8) top = Math.max(8, window.innerHeight - ph - 8);
    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
    const labelInput = popup.querySelector('#rm-label');
    const warnEl = popup.querySelector('#rm-warn');
    popup.querySelector('#rm-save').addEventListener('click', (e) => {
      e.stopPropagation();
      onPopupSaveClick(meta, labelInput, warnEl);
    });
    popup.querySelector('#rm-cancel').addEventListener('click', (e) => {
      e.stopPropagation();
      onPopupCancelClick();
    });
    labelInput.focus();
  }

  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent =
      '.' + HIGHLIGHT_CLASS + ' { outline: 3px solid #22c55e !important; outline-offset: 2px !important; }' +
      '.' + PREVIEW_CLASS + ' { outline: 2px dashed #86efac !important; outline-offset: 1px !important; }' +
      '#' + POPUP_ID + ' { background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px;' +
      ' padding:10px; width:260px; font:13px system-ui,sans-serif; box-shadow:0 6px 20px rgba(0,0,0,.4); }' +
      '#' + POPUP_ID + ' .rm-head { font-weight:600; margin-bottom:8px; font-size:12px; }' +
      '#' + POPUP_ID + ' .rm-label-input { width:100%; box-sizing:border-box; padding:6px 8px; margin-bottom:8px;' +
      ' border-radius:6px; border:1px solid #475569; background:#1e293b; color:#fff; }' +
      '#' + POPUP_ID + ' .rm-actions { display:flex; gap:8px; }' +
      '#' + POPUP_ID + ' .rm-actions button { flex:1; padding:6px; border:none; border-radius:6px; cursor:pointer; }' +
      '#' + POPUP_ID + ' #rm-save { background:#22c55e; color:#fff; font-weight:600; }' +
      '#' + POPUP_ID + ' #rm-cancel { background:#334155; color:#e2e8f0; }' +
      '#' + BADGE_ID + ' { position:fixed; bottom:12px; left:12px; z-index:2147483646; padding:10px 14px;' +
      ' background:#14532d; color:#dcfce7; border:2px solid #22c55e; border-radius:8px;' +
      ' font:700 13px system-ui,sans-serif; pointer-events:none; box-shadow:0 2px 10px rgba(0,0,0,.35); }' +
      '#' + L_FLASH_ID + ' { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:2147483647;' +
      ' padding:16px 28px; background:#14532d; color:#dcfce7; border:3px solid #22c55e; border-radius:12px;' +
      ' font:700 20px system-ui,sans-serif; pointer-events:none; box-shadow:0 8px 32px rgba(0,0,0,.5); }';
    (document.head || document.documentElement).appendChild(style);
  }

  function showLDetectedFlash() {
    let flash = document.getElementById(L_FLASH_ID);
    if (!flash) {
      flash = document.createElement('div');
      flash.id = L_FLASH_ID;
      flash.textContent = 'L DETECTED';
      document.body.appendChild(flash);
    }
    flash.style.display = 'block';
    clearTimeout(window.__runwayMapperLFlashTimer);
    window.__runwayMapperLFlashTimer = setTimeout(() => {
      const node = document.getElementById(L_FLASH_ID);
      if (node) node.style.display = 'none';
    }, 1000);
  }

  if (!document.getElementById(BADGE_ID)) {
    const badge = document.createElement('div');
    badge.id = BADGE_ID;
    badge.textContent = 'HOVER MODE ACTIVE';
    document.body.appendChild(badge);
  } else {
    const badge = document.getElementById(BADGE_ID);
    if (badge) badge.textContent = 'HOVER MODE ACTIVE';
  }

  let lastMouseX = Math.round(window.innerWidth / 2);
  let lastMouseY = Math.round(window.innerHeight / 2);
  let lastPreviewTarget = null;

  function onMouseMove(ev) {
    lastMouseX = ev.clientX;
    lastMouseY = ev.clientY;
    if (document.getElementById(POPUP_ID)) return;
    const el = document.elementFromPoint(ev.clientX, ev.clientY);
    if (!el || el.nodeType !== 1 || isInsideMapperUI(el)) {
      clearPreview();
      lastPreviewTarget = null;
      return;
    }
    if (el === lastPreviewTarget) return;
    clearPreview();
    lastPreviewTarget = el;
    if (el.classList) el.classList.add(PREVIEW_CLASS);
  }

  function captureUnderMouse() {
    console.log('MAPPER_HOVER_CAPTURE_START', JSON.stringify({
      x: lastMouseX,
      y: lastMouseY,
    }));
    const target = document.elementFromPoint(lastMouseX, lastMouseY);
    if (!target || target.nodeType !== 1) {
      console.log('MAPPER_HOVER_CAPTURE_ABORT', JSON.stringify({ reason: 'no_element', x: lastMouseX, y: lastMouseY }));
      return;
    }
    if (isInsideMapperUI(target)) {
      console.log('MAPPER_HOVER_CAPTURE_ABORT', JSON.stringify({ reason: 'mapper_ui', tag: target.tagName }));
      return;
    }
    clearPreview();
    const meta = buildMeta(target);
    openPopup(target, meta);
    console.log('MAPPER_HOVER_CAPTURE', JSON.stringify({
      tag: target.tagName,
      x: lastMouseX,
      y: lastMouseY,
      text: (target.innerText || '').slice(0, 80),
    }));
  }

  function isLKey(ev) {
    const key = ev.key || '';
    const code = ev.code || '';
    return key === 'l' || key === 'L' || code === 'KeyL';
  }

  function onKeyDown(ev) {
    if (ev && ev.__runwayMapperHoverKeyHandled) return;
    if (ev) ev.__runwayMapperHoverKeyHandled = true;

    const active = document.activeElement;
    console.log('MAPPER_KEYDOWN', JSON.stringify({
      key: ev.key,
      code: ev.code,
      activeElement: active ? active.tagName : null,
      target: (ev.target && ev.target.tagName) || null,
      typingContext: isTypingContext(),
    }));

    if (ev.key === 'Escape') {
      closePopup();
      return;
    }

    if (isLKey(ev)) {
      console.log('MAPPER_L_DETECTED', JSON.stringify({
        key: ev.key,
        code: ev.code,
        activeElement: active ? active.tagName : null,
        typingContext: isTypingContext(),
      }));
      showLDetectedFlash();
    } else {
      return;
    }

    if (isInsideMapperUI(ev.target)) {
      console.log('MAPPER_L_BLOCKED', JSON.stringify({ reason: 'mapper_ui' }));
      return;
    }
    if (isTypingContext()) {
      console.log('MAPPER_L_BLOCKED', JSON.stringify({
        reason: 'typing_context',
        activeElement: active ? active.tagName : null,
        contentEditable: !!(active && active.isContentEditable),
      }));
      return;
    }

    try {
      ev.preventDefault();
      ev.stopPropagation();
      if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
    } catch (e) {}

    captureUnderMouse();
  }

  if (window.__runwayMapperHoverTeardown) {
    window.__runwayMapperHoverTeardown();
  }

  window.__runwayMapperHoverTeardown = () => {
    document.removeEventListener('mousemove', onMouseMove, true);
    document.removeEventListener('keydown', onKeyDown, true);
    window.removeEventListener('keydown', onKeyDown, true);
    closePopup();
    clearPreview();
    const badge = document.getElementById(BADGE_ID);
    if (badge) badge.remove();
    const flash = document.getElementById(L_FLASH_ID);
    if (flash) flash.remove();
    if (window.__runwayMapperLFlashTimer) clearTimeout(window.__runwayMapperLFlashTimer);
    window.__runwayMapperHoverLabelActive = false;
  };

  document.addEventListener('mousemove', onMouseMove, { capture: true, passive: true });
  document.addEventListener('keydown', onKeyDown, KEY_OPTS);
  window.addEventListener('keydown', onKeyDown, KEY_OPTS);
  window.__runwayMapperHoverLabelActive = true;
  console.log('MAPPER_HOVER_INSTALL', JSON.stringify({
    href: location.href,
    mode: 'hover_label',
    trigger: 'L_key',
    no_click: true,
    keydown_targets: ['document', 'window'],
    keydown_capture: true,
    badge: 'HOVER MODE ACTIVE',
  }));
  return true;
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


def suggest_normalized_label_name(raw_label: str) -> str | None:
    """Return canonical label name when operator used a legacy/raw label."""
    key = str(raw_label or "").strip()
    if not key:
        return None
    if key in CONTINUITY_ALL_REQUIRED_LABELS or key in VALID_SEMANTIC_LABELS:
        return None
    return LABEL_NORMALIZATION_SUGGESTIONS.get(key)


def _label_entry_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    meta = dict(entry.get("metadata") or {})
    for field in ("tag", "text", "aria_label", "role", "css_selector", "page_url", "combined_label"):
        if field not in meta and entry.get(field) is not None:
            meta[field] = entry.get(field)
    if "page_url" not in meta and entry.get("url"):
        meta["page_url"] = entry.get("url")
    selector_candidates = entry.get("selector_candidates") or {}
    if "css_selector" not in meta and selector_candidates.get("css"):
        meta["css_selector"] = selector_candidates.get("css")
    return meta


def _label_css_selector(entry: dict[str, Any], meta: dict[str, Any]) -> str:
    css = str(meta.get("css_selector") or "").strip()
    if css:
        return css
    selector_candidates = entry.get("selector_candidates") or {}
    return str(selector_candidates.get("css") or "").strip()


def _label_page_url(entry: dict[str, Any], meta: dict[str, Any]) -> str:
    return str(meta.get("page_url") or entry.get("url") or "").lower()


def _label_visible_text(entry: dict[str, Any], meta: dict[str, Any]) -> str:
    parts = [
        str(meta.get("text") or ""),
        str(meta.get("combined_label") or ""),
        str(meta.get("aria_label") or ""),
        str(entry.get("text") or ""),
        str(entry.get("aria_label") or ""),
        str(entry.get("label") or ""),
    ]
    return " ".join(parts).lower()


def _selector_is_too_generic(css: str) -> bool:
    normalized = str(css or "").strip().lower()
    if not normalized:
        return True
    if normalized in GENERIC_CSS_SELECTORS:
        return True
    if any(marker in normalized for marker in QUALIFIED_SELECTOR_MARKERS):
        return False
    root = normalized.split()[0] if normalized else ""
    return root in GENERIC_CSS_SELECTORS


def _url_has_markers(url: str, markers: tuple[str, ...]) -> bool:
    lower = str(url or "").lower()
    return all(marker.lower() in lower for marker in markers) if markers else True


def _url_has_any_marker(url: str, markers: tuple[str, ...]) -> bool:
    lower = str(url or "").lower()
    return any(marker.lower() in lower for marker in markers)


def find_label_entry(
    labels: dict[str, Any],
    canonical_name: str,
) -> tuple[str, dict[str, Any]] | None:
    aliases = CONTINUITY_LABEL_ALIASES.get(canonical_name, (canonical_name,))
    for alias in aliases:
        entry = labels.get(alias)
        if isinstance(entry, dict):
            return alias, entry
    return None


def build_continuity_normalized_labels(ui_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Resolve operator labels to canonical continuity keys (read-only normalization view)."""
    labels: dict[str, Any] = dict(ui_map.get("labels") or {})
    normalized: dict[str, dict[str, Any]] = {}
    for canonical in CANONICAL_CONTINUITY_LABEL_ORDER:
        found = find_label_entry(labels, canonical)
        if not found:
            continue
        alias, entry = found
        meta = _label_entry_metadata(entry)
        normalized[canonical] = {
            "source_alias": alias,
            "tag": meta.get("tag") or entry.get("tag") or "",
            "css_selector": _label_css_selector(entry, meta),
            "page_url": _label_page_url(entry, meta),
            "text": _label_visible_text(entry, meta)[:120],
            "suggested_rename": alias if alias != canonical else None,
        }
    return normalized


def continuity_completion_rule() -> dict[str, Any]:
    """Documented completion rule for orchestrator wait loops (Phase C)."""
    return dict(GENERATION_COMPLETE_RULE)


def map_has_valid_completion_signal(ui_map: dict[str, Any]) -> bool:
    """True when map defines at least one non-body completion signal label."""
    labels: dict[str, Any] = dict(ui_map.get("labels") or {})
    for signal in CONTINUITY_COMPLETION_SIGNAL_LABELS:
        found = find_label_entry(labels, signal)
        if not found:
            continue
        _, entry = found
        meta = _label_entry_metadata(entry)
        tag = str(meta.get("tag") or entry.get("tag") or "").lower()
        css = _label_css_selector(entry, meta)
        if tag in FORBIDDEN_CAPTURE_TAGS or css.lower() in {"body", "html"}:
            continue
        return True
    return False


def _capture_error_blocks_validation(canonical: str, warn: dict[str, str]) -> bool:
    code = str(warn.get("code") or "")
    if warn.get("severity") != "error":
        return False
    if canonical in WEAK_SELECTOR_TOLERANCE_LABELS and code in {
        "USE_FRAME_WRONG_PAGE",
        "USE_FRAME_PAGE_UNCONFIRMED",
        "GENERIC_SELECTOR",
    }:
        return False
    return True


def validate_label_capture(
    label_name: str,
    entry: dict[str, Any] | None = None,
    *,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Return warning dicts for a single label capture (non-blocking)."""
    warnings: list[dict[str, str]] = []
    canonical = suggest_normalized_label_name(label_name) or label_name
    if suggest_normalized_label_name(label_name):
        warnings.append(
            {
                "code": "NORMALIZE_LABEL",
                "severity": "info",
                "message": (
                    f"Consider renaming '{label_name}' -> '{suggest_normalized_label_name(label_name)}' "
                    "for orchestrator continuity keys."
                ),
            }
        )

    meta = dict(metadata or {})
    if entry:
        meta = _label_entry_metadata(entry)
    tag = str(meta.get("tag") or entry.get("tag") if entry else meta.get("tag") or "").lower()
    css = _label_css_selector(entry or {}, meta)
    page_url = _label_page_url(entry or {}, meta)
    visible = _label_visible_text(entry or {}, meta)

    if tag in FORBIDDEN_CAPTURE_TAGS:
        warnings.append(
            {
                "code": "FORBIDDEN_TAG",
                "severity": "error",
                "message": f"Label '{label_name}' captured tag '{tag}' — use button/link/menu item, not page root.",
            }
        )

    if _selector_is_too_generic(css):
        warnings.append(
            {
                "code": "GENERIC_SELECTOR",
                "severity": "warning",
                "message": (
                    f"Label '{label_name}' selector '{css or '(empty)'}' is too generic — "
                    "prefer aria-label, id suffix, or data-testid."
                ),
            }
        )

    expected_tokens = EXPECTED_CONTROL_TEXT.get(canonical) or EXPECTED_CONTROL_TEXT.get(label_name)
    if expected_tokens and visible:
        if not any(token in visible for token in expected_tokens):
            warnings.append(
                {
                    "code": "TEXT_MISMATCH",
                    "severity": "warning",
                    "message": (
                        f"Label '{label_name}' text/aria does not match expected control "
                        f"(expected one of: {', '.join(expected_tokens)})."
                    ),
                }
            )

    if canonical == "download_mp4_button" or label_name in CONTINUITY_LABEL_ALIASES.get("download_mp4_button", ()):
        if tag in FORBIDDEN_CAPTURE_TAGS:
            warnings.append(
                {
                    "code": "DOWNLOAD_NOT_BODY",
                    "severity": "error",
                    "message": "download_mp4_button must be a button, link, or menu item — never body/html.",
                }
            )
        elif tag and tag not in DOWNLOAD_MP4_ALLOWED_TAGS:
            warnings.append(
                {
                    "code": "DOWNLOAD_UNEXPECTED_TAG",
                    "severity": "warning",
                    "message": f"download_mp4_button tag '{tag}' is unusual — confirm this is the per-clip download control.",
                }
            )

    if canonical == "use_frame_button" or label_name in CONTINUITY_LABEL_ALIASES.get("use_frame_button", ()):
        if _url_has_any_marker(page_url, USE_FRAME_FORBIDDEN_URL_MARKERS):
            warnings.append(
                {
                    "code": "USE_FRAME_WRONG_PAGE",
                    "severity": "warning",
                    "message": (
                        "use_frame_button captured on apps/recents/multi-shot path — "
                        "prefer Gen-4.5 tools session output (mode=tools&tool=video). "
                        "Allowed temporarily if control works at runtime."
                    ),
                }
            )
        elif page_url and not _url_has_markers(page_url, USE_FRAME_ALLOWED_URL_MARKERS):
            warnings.append(
                {
                    "code": "USE_FRAME_PAGE_UNCONFIRMED",
                    "severity": "warning",
                    "message": (
                        "use_frame_button page URL missing mode=tools&tool=video — "
                        "confirm you are on the Gen-4.5 tools session output view."
                    ),
                }
            )
        if label_name in WEAK_SELECTOR_TOLERANCE_LABELS or canonical == "use_frame_button":
            if _selector_is_too_generic(css):
                warnings.append(
                    {
                        "code": "WEAK_SELECTOR_TOLERATED",
                        "severity": "info",
                        "message": (
                            "use_frame_button has a weak selector — tolerated for Phase C; "
                            "re-label when a stronger aria/id selector is available."
                        ),
                    }
                )

    if canonical == "remove_image" or label_name in CONTINUITY_LABEL_ALIASES.get("remove_image", ()):
        if tag in FORBIDDEN_CAPTURE_TAGS:
            warnings.append(
                {
                    "code": "REMOVE_IMAGE_NOT_BODY",
                    "severity": "error",
                    "message": "remove_image must target the image remove/clear control, not body/html.",
                }
            )

    if canonical == "generation_status" or label_name in CONTINUITY_LABEL_ALIASES.get("generation_status", ()):
        if tag in FORBIDDEN_CAPTURE_TAGS:
            warnings.append(
                {
                    "code": "STATUS_NOT_BODY",
                    "severity": "error",
                    "message": "generation_status must target a status text/region element, not body/html.",
                }
            )

    menu_labels = {"duration_menu", "aspect_ratio_menu", "duration_10s", "aspect_ratio_9_16", "aspect_ratio_16_9"}
    if canonical in menu_labels and page_url and "mode=apps" in page_url:
        warnings.append(
            {
                "code": "WRONG_WORKFLOW_PAGE",
                "severity": "error",
                "message": (
                    f"Label '{label_name}' captured on mode=apps (Multi-Shot) — "
                    "use Gen-4.5 tools path (mode=tools&tool=video) only."
                ),
            }
        )

    return warnings


def print_label_capture_warnings(label_name: str, warnings: list[dict[str, str]]) -> None:
    if not warnings:
        return
    print(f"[RunwayUIMapper] Label validation for '{label_name}':")
    for item in warnings:
        severity = str(item.get("severity") or "warning").upper()
        code = item.get("code") or "WARN"
        message = item.get("message") or ""
        print(f"  [{severity}] {code}: {message}")


def validate_continuity_mapping(ui_map: dict[str, Any]) -> dict[str, Any]:
    """Validate runway_ui_map.json for Phase B/C continuity controls."""
    labels: dict[str, Any] = dict(ui_map.get("labels") or {})
    normalized = build_continuity_normalized_labels(ui_map)
    results: dict[str, Any] = {
        "ok": True,
        "missing": [],
        "invalid": [],
        "warnings": [],
        "present": {},
        "optional_present": {},
        "normalized_labels": normalized,
        "completion_rule": continuity_completion_rule(),
        "completion_signals_ready": map_has_valid_completion_signal(ui_map),
    }

    for canonical in CONTINUITY_ALL_REQUIRED_LABELS:
        found = find_label_entry(labels, canonical)
        if not found:
            results["missing"].append(canonical)
            results["ok"] = False
            continue
        alias, entry = found
        results["present"][canonical] = alias
        meta = _label_entry_metadata(entry)
        css = _label_css_selector(entry, meta)
        tag = str(meta.get("tag") or entry.get("tag") or "").lower()

        if not css:
            results["invalid"].append(
                {"label": canonical, "reason": "empty selector_candidates.css / css_selector"}
            )
            results["ok"] = False

        capture_warnings = validate_label_capture(canonical, entry)
        for warn in capture_warnings:
            if _capture_error_blocks_validation(canonical, warn):
                results["invalid"].append({"label": canonical, "reason": warn.get("message")})
                results["ok"] = False
            elif warn.get("severity") in {"warning", "error"}:
                results["warnings"].append({"label": canonical, "message": warn.get("message")})
            elif warn.get("severity") == "info":
                results["warnings"].append({"label": canonical, "message": warn.get("message")})

        if canonical in {"download_mp4_button", "remove_image"} and tag in FORBIDDEN_CAPTURE_TAGS:
            results["invalid"].append(
                {"label": canonical, "reason": f"maps to forbidden tag '{tag}'"}
            )
            results["ok"] = False
        if canonical == "use_frame_button" and tag in FORBIDDEN_CAPTURE_TAGS:
            results["invalid"].append(
                {"label": canonical, "reason": f"maps to forbidden tag '{tag}'"}
            )
            results["ok"] = False

    for optional in CONTINUITY_OPTIONAL_LABELS:
        found = find_label_entry(labels, optional)
        if found:
            results["optional_present"][optional] = found[0]

    if not results["completion_signals_ready"]:
        results["warnings"].append(
            {
                "label": "completion_rule",
                "message": (
                    "No valid completion signal yet — need download_mp4_button or use_frame_button "
                    "with non-body selector after relabeling download from output view."
                ),
            }
        )
        if "download_mp4_button" not in results["missing"]:
            results["ok"] = False

    return results


def format_continuity_checklist(*, include_prerequisites: bool = True) -> str:
    lines = [
        "RUNWAY BROWSER CONTINUITY — OPERATOR RELABELING CHECKLIST",
        "=" * 60,
        "",
        "Safety: manual labeling only. Do NOT auto-click Generate. Do NOT spend credits via mapper.",
        "Workflow: Gen-4.5 Video Generation (mode=tools&tool=video) — NOT Multi-Shot.",
        "",
    ]
    if include_prerequisites:
        lines.extend(
            [
                "Prerequisites (should already exist from Phase A):",
                "  [ ] prompt_input  (or prompt_box / Prompt Box)",
                "  [ ] gen45_model_button  (or gen45_option / Gen-4.5)",
                "  [ ] try_it_now_button  (Try it now — NOT 'Try it' / Edit Studio)",
                "  [ ] generate_button  (Generate — approval-gated, do not auto-click)",
                "",
                "Critical output controls to relabel after a REAL completed generation:",
            ]
        )
    for item in CONTINUITY_RELABEL_CHECKLIST:
        lines.extend(
            [
                f"Step {item['step']}: {item['label']}",
                f"  When: {item['when']}",
                f"  Target: {item['target']}",
                f"  Avoid: {item['avoid']}",
                "",
            ]
        )
    lines.extend(
        [
            "Completion detection (Phase C — no generation_status required):",
            "  Poll every 30-60s after Generate until:",
            "    download_mp4_button visible  OR  use_frame_button visible",
            "",
            "Multi-clip loop:",
            "  Clip 1: prompt -> aspect_ratio_9_16 -> duration_10s -> Generate (manual)",
            "  Wait -> download_mp4_button -> save mp4",
            "  Clip 2+: use_frame_button -> prompt -> Generate -> download",
            "  Final clip: download -> save mp4 -> remove_image (do NOT use_frame)",
            "",
            "Normalization (type these exact names in the label popup when possible):",
            "  DOWNLOAD MP4        -> download_mp4_button  (prefer: --hover-label + L)",
            "  USE FRAME           -> use_frame_button",
            "  REMOVE IMAGE        -> remove_image",
            "  aspect_ratio_menu 9: 16 -> aspect_ratio_9_16",
            "",
            "Dangerous/output controls (Download, Generate, Buy):",
            "  python tools/runway_ui_mapper.py --hover-label",
            "  Move mouse over control, press L — no click, no download",
            "",
            "Validate after labeling:",
            "  python tools/runway_ui_mapper.py --validate-continuity",
            "  python tools/runway_ui_mapper.py --normalize-continuity",
            "  python project_brain/validate_runway_mapping_continuity_controls.py",
            "",
        ]
    )
    return "\n".join(lines)


def mode_continuity_checklist() -> int:
    print(format_continuity_checklist())
    return 0


def mode_normalize_continuity(*, map_path: Path | None = None) -> int:
    path = map_path or JSON_PATH
    if not path.is_file():
        print(f"[RunwayUIMapper] Missing map: {path}")
        return 1
    ui_map = json.loads(path.read_text(encoding="utf-8"))
    normalized = build_continuity_normalized_labels(ui_map)
    rule = continuity_completion_rule()
    print("\n[RunwayUIMapper] Continuity label normalization (read-only)")
    print(f"  Map: {path}")
    print(f"  Completion rule: {rule['expression']}")
    print(f"  Poll interval: {rule['poll_interval_seconds']}s")
    print("\n  Canonical labels:")
    for canonical in CANONICAL_CONTINUITY_LABEL_ORDER:
        item = normalized.get(canonical)
        if not item:
            print(f"    {canonical}: MISSING")
            continue
        rename = item.get("suggested_rename")
        rename_note = f" (rename from '{rename}')" if rename else ""
        print(
            f"    {canonical}{rename_note}\n"
            f"      tag={item.get('tag')} selector={item.get('css_selector')!r}"
        )
    optional = ui_map.get("labels") or {}
    for opt in CONTINUITY_OPTIONAL_LABELS:
        if find_label_entry(optional, opt):
            print(f"\n  Optional present: {opt}")
    print(f"\n  Completion signals ready: {map_has_valid_completion_signal(ui_map)}")
    return 0


def mode_validate_continuity(*, map_path: Path | None = None) -> int:
    path = map_path or JSON_PATH
    if not path.is_file():
        print(f"[RunwayUIMapper] Missing map: {path}")
        return 1
    ui_map = json.loads(path.read_text(encoding="utf-8"))
    report = validate_continuity_mapping(ui_map)
    print("\n[RunwayUIMapper] Continuity mapping validation")
    print(f"  Map: {path}")
    print(f"  OK: {report['ok']}")
    print(f"  Completion rule: {report['completion_rule']['expression']}")
    print(f"  Completion signals ready: {report['completion_signals_ready']}")
    if report["present"]:
        print("\n  Present:")
        for canonical, alias in sorted(report["present"].items()):
            print(f"    {canonical} <- '{alias}'")
    if report["missing"]:
        print("\n  Missing:")
        for name in report["missing"]:
            print(f"    - {name}")
    if report["invalid"]:
        print("\n  Invalid:")
        for item in report["invalid"]:
            print(f"    - {item['label']}: {item['reason']}")
    if report["warnings"]:
        print("\n  Warnings:")
        for item in report["warnings"]:
            print(f"    - {item['label']}: {item['message']}")
    if report.get("optional_present"):
        print("\n  Optional labels present:")
        for name, alias in sorted(report["optional_present"].items()):
            print(f"    {name} <- '{alias}'")
    return 0 if report["ok"] else 1


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


def _nest_label_under_parent(
    labels: dict[str, Any],
    parent_label: str,
    child_label: str,
    entry: dict[str, Any],
) -> None:
    """Store menu option under labels[parent].options[child]."""
    parent_entry = labels.get(parent_label)
    if not isinstance(parent_entry, dict) or not parent_entry.get("element_id"):
        parent_entry = {
            "control_type": "dropdown_menu",
            "options": {},
            "notes": "Parent container for menu options (auto-created)",
            "operator_confirmed": False,
            "created_at": _now_iso(),
        }
        labels[parent_label] = parent_entry
    options = parent_entry.setdefault("options", {})
    options[child_label] = dict(entry)


def persist_click_label(
    ui_map: dict[str, Any],
    *,
    label_name: str,
    element_id: str,
    metadata: dict[str, Any],
    notes: str = "",
    operator_confirmed: bool = True,
    confirmed_by: str = "shift_click_popup",
    control_type: str = "direct_button",
    parent_label: str = "",
) -> dict[str, Any]:
    clean_meta = sanitize_click_metadata(metadata)
    safety = resolve_label_safety(label_name, clean_meta)
    css = str(clean_meta.get("css_selector") or "")
    ctype = control_type if control_type in VALID_CONTROL_TYPES else "direct_button"
    if parent_label and ctype == "direct_button":
        ctype = "menu_option"
    entry: dict[str, Any] = {
        "element_id": element_id,
        "metadata": clean_meta,
        "selector_candidates": {
            "css": css,
            "playwright": f"page.locator({json.dumps(css, ensure_ascii=False)})" if css else "",
        },
        "operator_confirmed": operator_confirmed,
        "confirmed_by": confirmed_by,
        "confirmed_at": _now_iso(),
        "notes": notes[:500],
        "control_type": ctype,
        "auto_click_allowed": bool(safety.get("auto_click_allowed")),
        "requires_approval": bool(safety.get("requires_approval")),
    }
    if parent_label:
        entry["parent_label"] = parent_label
    if safety.get("requires_real_video_approval"):
        entry["requires_real_video_approval"] = True
    labels = ui_map.setdefault("labels", {})
    labels[label_name] = entry
    if parent_label:
        _nest_label_under_parent(labels, parent_label, label_name, entry)
    if label_name == "generate_button" or entry["requires_approval"]:
        ui_map.setdefault("safety", dict(DEFAULT_SAFETY_V2))
        req = set(ui_map["safety"].get("requires_approval") or [])
        req.add(label_name)
        ui_map["safety"]["requires_approval"] = sorted(req)
    capture_warnings = validate_label_capture(label_name, entry)
    print_label_capture_warnings(label_name, capture_warnings)
    suggested = suggest_normalized_label_name(label_name)
    if suggested and suggested != label_name:
        print(
            f"[RunwayUIMapper] Normalization suggestion: save future captures as '{suggested}' "
            f"instead of '{label_name}'."
        )
    return entry


def process_popup_save_payload(
    ui_map: dict[str, Any],
    elements: dict[str, dict[str, Any]],
    payload: dict[str, Any],
) -> str:
    """Apply in-page popup save payload to ui_map; returns saved label name."""
    label_name = str(payload.get("label_name") or "").strip()
    if not label_name:
        raise ValueError("label_name required")
    meta = sanitize_click_metadata(dict(payload.get("metadata") or {}))
    capture_mode = str(payload.get("capture_mode") or meta.get("capture_mode") or "click_label_popup")
    if capture_mode == "hover_label":
        meta["capture_mode"] = "hover_label"
    element_id = merge_clicked_element(elements, meta)
    css = str(meta.get("css_selector") or "")
    entry: dict[str, Any] = {
        "label": label_name,
        "element_id": element_id,
        "text": meta.get("text") or "",
        "aria_label": meta.get("aria_label") or "",
        "role": meta.get("role") or "",
        "tag": meta.get("tag") or "",
        "bounding_box": meta.get("bounding_box") or {},
        "url": _safe_url(meta.get("page_url") or ""),
        "selector_candidates": {"css": css},
        "metadata": meta,
        "operator_confirmed": True,
        "confirmed_at": _now_iso(),
        "capture_mode": capture_mode,
        "confirmed_by": "hover_label_l_key" if capture_mode == "hover_label" else "click_label_popup",
    }
    ui_map.setdefault("labels", {})[label_name] = entry
    ui_map["page"] = {
        "url": entry["url"],
        "title": str(meta.get("page_title") or "")[:200],
        "is_runway_url": _is_runway_url(meta.get("page_url") or ""),
    }
    capture_warnings = validate_label_capture(label_name, entry)
    print_label_capture_warnings(label_name, capture_warnings)
    suggested = suggest_normalized_label_name(label_name)
    if suggested and suggested != label_name:
        print(
            f"[RunwayUIMapper] Normalization suggestion: save future captures as '{suggested}' "
            f"instead of '{label_name}'."
        )
    return label_name


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
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
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

    def pick_page(self, tab_index: int | None = None, *, require_runway: bool = True):
        tabs = self.list_tabs()
        if not tabs:
            raise RuntimeError("No open tabs in CDP browser. Open a page in Chrome first.")
        runway_indices = [t["index"] for t in tabs if t.get("is_runway_url")]
        if tab_index is not None:
            if tab_index < 0 or tab_index >= len(tabs):
                raise RuntimeError(f"tab_index {tab_index} out of range (0..{len(tabs) - 1})")
            chosen = tab_index
        elif require_runway:
            if not runway_indices:
                raise RuntimeError(
                    "No Runway tab detected. Open https://app.runwayml.com and log in manually."
                )
            chosen = runway_indices[0]
        else:
            chosen = 0
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


def _enqueue_popup_save(save_queue: list[dict[str, Any]], payload: Any) -> None:
    if isinstance(payload, dict):
        save_queue.append(payload)


def _parse_save_line(text: str, prefix: str = CLICK_LABEL_SAVE_PREFIX) -> dict[str, Any] | None:
    if prefix not in text:
        return None
    raw = text[text.index(prefix) + len(prefix) :].strip()
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None
    return data


def _ingest_save_payload(
    save_queue: list[dict[str, Any]],
    seen_ids: set[str],
    payload: dict[str, Any] | None,
) -> bool:
    if not payload:
        return False
    save_id = str(payload.get("_save_id") or "")
    if save_id:
        if save_id in seen_ids:
            return False
        seen_ids.add(save_id)
    _enqueue_popup_save(save_queue, payload)
    return True


def _install_cdp_console_listener(page, prefix: str, save_queue: list, seen_ids: set) -> Any | None:
    """Listen via CDP Runtime.consoleAPICalled (works on connect_over_cdp tabs)."""
    try:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Runtime.enable")

        def _on_console(params: dict[str, Any]) -> None:
            try:
                parts: list[str] = []
                for arg in params.get("args") or []:
                    if arg.get("type") == "string":
                        parts.append(str(arg.get("value") or ""))
                text = "".join(parts)
                if prefix not in text:
                    return
                payload = _parse_save_line(text, prefix)
                _ingest_save_payload(save_queue, seen_ids, payload)
            except Exception:
                pass

        cdp.on("Runtime.consoleAPICalled", _on_console)
        return cdp
    except Exception:
        return None


def _poll_dom_save_bridge(page, prefix: str, save_queue: list, seen_ids: set, last_line: str) -> str:
    """Read pending save line from DOM attribute (primary fallback for CDP tabs)."""
    try:
        line = page.evaluate(
            """() => document.documentElement.getAttribute('data-runway-mapper-pending-save') || ''"""
        )
        if not line or not isinstance(line, str) or line == last_line:
            return last_line
        if prefix not in line:
            return last_line
        payload = _parse_save_line(line, prefix)
        if _ingest_save_payload(save_queue, seen_ids, payload):
            page.evaluate(
                """() => {
                  document.documentElement.removeAttribute('data-runway-mapper-pending-save');
                }"""
            )
        return line
    except Exception:
        return last_line


def mode_click_label(
    mapper: RunwayUIMapper,
    *,
    tab_index: int | None = None,
    allow_safe_clicks: bool = False,
) -> int:
    """Alt+Click or Mapper ON opens in-page popup; normal clicks pass through."""
    import threading

    save_queue: list[dict[str, Any]] = []
    seen_save_ids: set[str] = set()
    prefix = CLICK_LABEL_SAVE_PREFIX
    last_dom_line = ""

    def _on_console(msg) -> None:
        try:
            text = msg.text or ""
            if prefix not in text:
                for arg in getattr(msg, "args", []) or []:
                    try:
                        val = arg.json_value()
                        if isinstance(val, str) and prefix in val:
                            text = val
                            break
                    except Exception:
                        pass
            payload = _parse_save_line(text, prefix)
            _ingest_save_payload(save_queue, seen_save_ids, payload)
        except Exception as exc:
            print(f"[RunwayUIMapper] Console parse warning: {exc}")

    def _binding_save(_source, payload: Any) -> None:
        if isinstance(payload, dict):
            _ingest_save_payload(save_queue, seen_save_ids, payload)

    mapper.connect()
    cdp_session = None
    try:
        page, tabs, chosen = mapper.pick_page(tab_index, require_runway=False)
        try:
            title = page.title()
        except Exception:
            title = ""
        print(f"[RunwayUIMapper] CLICK-LABEL tab={chosen} url={_safe_url(page.url)}")
        print("[RunwayUIMapper] Normal click = website works as usual.")
        print("[RunwayUIMapper] Alt+Click any element = label popup (blocks real click).")
        print("[RunwayUIMapper] Or use top-right 'Mapper: OFF/ON' then single-click to label.")
        print("[RunwayUIMapper] Ctrl+C here to stop (labels save immediately on Save).")
        if allow_safe_clicks:
            pass  # deprecated no-op

        ui_map = load_ui_map(allow_missing=True)
        if not ui_map:
            ui_map = init_v2_map(
                page={"url": _safe_url(page.url), "title": str(title)[:200]},
                elements={},
                open_tabs=tabs,
            )
        ui_map.setdefault("open_tabs", tabs)
        elements: dict[str, dict[str, Any]] = dict(ui_map.get("elements") or {})

        page.on("console", _on_console)
        cdp_session = _install_cdp_console_listener(page, prefix, save_queue, seen_save_ids)
        try:
            page.expose_binding("runwayMapperSaveLabel", _binding_save)
        except Exception:
            pass
        def _inject_click_label_frames() -> int:
            ok = 0
            for frame in page.frames:
                try:
                    if frame.evaluate(CLICK_LABEL_INSTALL_JS):
                        ok += 1
                except Exception:
                    pass
            return ok

        installed = _inject_click_label_frames()
        if installed < 1:
            raise RuntimeError("Failed to install Shift+Click label script on page.")
        page.on("framenavigated", lambda _frame: _inject_click_label_frames())
        print(
            f"[RunwayUIMapper] Alt+Click / Force-mode capture installed on {installed} frame(s). "
            "Debug: MAPPER_CLICK in page console."
        )
        print("[RunwayUIMapper] Save bridge: DOM attribute + CDP console + Playwright console.")

        stop_event = threading.Event()
        _start_quit_listener(stop_event)

        while not stop_event.is_set():
            last_dom_line = _poll_dom_save_bridge(
                page, prefix, save_queue, seen_save_ids, last_dom_line
            )
            while save_queue and not stop_event.is_set():
                payload = save_queue.pop(0)
                try:
                    label_name = process_popup_save_payload(ui_map, elements, payload)
                except (ValueError, json.JSONDecodeError) as exc:
                    print(f"[RunwayUIMapper] Save skipped: {exc}")
                    continue
                ui_map["elements"] = elements
                save_ui_map(ui_map)
                print(f"[RunwayUIMapper] Saved label '{label_name}' -> {JSON_PATH.name}")
                try:
                    page.evaluate(
                        "() => window.__runwayMapperDismissAfterSave && window.__runwayMapperDismissAfterSave()"
                    )
                except Exception:
                    pass

            time.sleep(0.08)

        try:
            page.evaluate("() => window.__runwayMapperTeardown && window.__runwayMapperTeardown()")
        except Exception:
            pass
        save_ui_map(ui_map)
        print(f"[RunwayUIMapper] Done. Labels: {len(ui_map.get('labels') or {})}")
        return 0
    finally:
        if cdp_session is not None:
            try:
                cdp_session.detach()
            except Exception:
                pass
        mapper.disconnect()


def mode_hover_label(
    mapper: RunwayUIMapper,
    *,
    tab_index: int | None = None,
) -> int:
    """Hover + L key opens label popup — no click, safe for Download / Generate / Buy controls."""
    import threading

    save_queue: list[dict[str, Any]] = []
    seen_save_ids: set[str] = set()
    prefix = CLICK_LABEL_SAVE_PREFIX
    last_dom_line = ""

    def _on_console(msg) -> None:
        try:
            text = msg.text or ""
            if text.startswith("MAPPER_"):
                print(f"[RunwayUIMapper][browser] {text}")
            if prefix not in text:
                for arg in getattr(msg, "args", []) or []:
                    try:
                        val = arg.json_value()
                        if isinstance(val, str) and prefix in val:
                            text = val
                            break
                    except Exception:
                        pass
            payload = _parse_save_line(text, prefix)
            _ingest_save_payload(save_queue, seen_save_ids, payload)
        except Exception as exc:
            print(f"[RunwayUIMapper] Console parse warning: {exc}")

    def _binding_save(_source, payload: Any) -> None:
        if isinstance(payload, dict):
            _ingest_save_payload(save_queue, seen_save_ids, payload)

    mapper.connect()
    cdp_session = None
    try:
        page, tabs, chosen = mapper.pick_page(tab_index, require_runway=False)
        try:
            title = page.title()
        except Exception:
            title = ""
        print(f"[RunwayUIMapper] HOVER-LABEL tab={chosen} url={_safe_url(page.url)}")
        print("[RunwayUIMapper] Badge on page: HOVER MODE ACTIVE")
        print("[RunwayUIMapper] Move mouse over target — press L (browser window must have focus).")
        print("[RunwayUIMapper] Debug: open DevTools Console — every key logs MAPPER_KEYDOWN; L logs MAPPER_L_DETECTED.")
        print("[RunwayUIMapper] If L shows MAPPER_L_BLOCKED typing_context — click outside prompt box first.")
        print("[RunwayUIMapper] Recommended for: download_mp4_button, generate_button, Buy, dangerous controls.")
        print("[RunwayUIMapper] Normal clicks pass through — downloads are NOT triggered by L.")
        print("[RunwayUIMapper] Ctrl+C here to stop (labels save immediately on Save).")

        ui_map = load_ui_map(allow_missing=True)
        if not ui_map:
            ui_map = init_v2_map(
                page={"url": _safe_url(page.url), "title": str(title)[:200]},
                elements={},
                open_tabs=tabs,
            )
        ui_map.setdefault("open_tabs", tabs)
        elements: dict[str, dict[str, Any]] = dict(ui_map.get("elements") or {})

        page.on("console", _on_console)
        cdp_session = _install_cdp_console_listener(page, prefix, save_queue, seen_save_ids)
        try:
            page.expose_binding("runwayMapperSaveLabel", _binding_save)
        except Exception:
            pass

        def _inject_hover_label_frames() -> int:
            ok = 0
            for frame in page.frames:
                try:
                    if frame.evaluate(HOVER_LABEL_INSTALL_JS):
                        ok += 1
                except Exception:
                    pass
            return ok

        installed = _inject_hover_label_frames()
        if installed < 1:
            raise RuntimeError("Failed to install hover-label script on page.")
        page.on("framenavigated", lambda _frame: _inject_hover_label_frames())
        print(
            f"[RunwayUIMapper] Hover-label (L key) installed on {installed} frame(s). "
            "Debug: MAPPER_KEYDOWN / MAPPER_L_DETECTED in browser console + terminal."
        )
        print("[RunwayUIMapper] Save bridge: DOM attribute + CDP console + Playwright console.")

        stop_event = threading.Event()
        _start_quit_listener(stop_event)

        while not stop_event.is_set():
            last_dom_line = _poll_dom_save_bridge(
                page, prefix, save_queue, seen_save_ids, last_dom_line
            )
            while save_queue and not stop_event.is_set():
                payload = save_queue.pop(0)
                try:
                    label_name = process_popup_save_payload(ui_map, elements, payload)
                except (ValueError, json.JSONDecodeError) as exc:
                    print(f"[RunwayUIMapper] Save skipped: {exc}")
                    continue
                ui_map["elements"] = elements
                save_ui_map(ui_map)
                print(f"[RunwayUIMapper] Saved label '{label_name}' -> {JSON_PATH.name}")
                try:
                    page.evaluate(
                        "() => window.__runwayMapperDismissAfterSave && window.__runwayMapperDismissAfterSave()"
                    )
                except Exception:
                    pass

            time.sleep(0.08)

        try:
            page.evaluate("() => window.__runwayMapperHoverTeardown && window.__runwayMapperHoverTeardown()")
        except Exception:
            pass
        save_ui_map(ui_map)
        print(f"[RunwayUIMapper] Done. Labels: {len(ui_map.get('labels') or {})}")
        return 0
    finally:
        if cdp_session is not None:
            try:
                cdp_session.detach()
            except Exception:
                pass
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
        help="Alt+Click or Mapper ON toggle opens label popup; normal click navigates",
    )
    mode.add_argument(
        "--hover-label",
        action="store_true",
        help="Hover target + press L — label popup without click (safe for Download/Generate)",
    )
    mode.add_argument(
        "--continuity-checklist",
        action="store_true",
        help="Print operator relabeling checklist for Gen-4.5 output controls (no browser)",
    )
    mode.add_argument(
        "--validate-continuity",
        action="store_true",
        help="Validate runway_ui_map.json continuity labels (no browser)",
    )
    mode.add_argument(
        "--normalize-continuity",
        action="store_true",
        help="Print canonical continuity label normalization view (no browser)",
    )
    parser.add_argument(
        "--allow-safe-clicks",
        action="store_true",
        help=argparse.SUPPRESS,
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

    if args.continuity_checklist:
        return mode_continuity_checklist()

    if args.validate_continuity:
        return mode_validate_continuity()

    if args.normalize_continuity:
        return mode_normalize_continuity()

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

    if args.hover_label:
        try:
            return mode_hover_label(mapper, tab_index=args.tab_index)
        except Exception as exc:
            print(f"[RunwayUIMapper] HOVER-LABEL FAILED: {exc}")
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
