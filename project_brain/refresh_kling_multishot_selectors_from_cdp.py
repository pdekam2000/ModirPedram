"""Refresh Kling Multishot selectors from live Runway CDP page (read-only discovery)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_config import REQUIRED_KLING_LABELS  # noqa: E402
from content_brain.execution.kling_multishot_locator import (  # noqa: E402
    css_selector_is_unstable,
    locate_control,
)
from content_brain.execution.kling_multishot_map_loader import load_kling_ui_map  # noqa: E402
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402

PHASE = "KLING-MULTISHOT-LIVE-DRY-RUN-STABILIZATION"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
RUNWAY_URL_MARKER = "app.runwayml.com"
REFRESH_LABELS: tuple[str, ...] = (
    "provider_kling_3_pro",
    "multishot_tab",
    "audio_toggle_on",
    "first_frame_upload",
    "shot_1_prompt",
    "shot_2_prompt",
    "shot_1_duration_menu",
    "shot_2_duration_menu",
    "generate_button",
)

STABLE_CSS_OVERRIDES: dict[str, str] = {
    "provider_kling_3_pro": 'button:has-text("Kling 3.0 Pro")',
    "multishot_tab": 'label:has-text("Multishot")',
    "audio_toggle_on": 'button[aria-label="Audio settings"]',
    "first_frame_upload": 'button[aria-label="Upload"]',
    "shot_1_prompt": 'div[aria-label="Shot 1 prompt"][contenteditable="true"]',
    "shot_2_prompt": 'div[aria-label="Shot 2 prompt"][contenteditable="true"]',
    "shot_1_duration_menu": 'button[aria-label="Shot duration"]:nth-of-type(1)',
    "shot_2_duration_menu": 'button[aria-label="Shot duration"]:nth-of-type(2)',
    "generate_button": 'button:has-text("Generate")',
}


def _is_runway_url(url: str) -> bool:
    return RUNWAY_URL_MARKER in str(url or "").lower()


def _patch_entry_css(entry: dict[str, Any], *, css: str, strategy: str, page_url: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    updated = dict(entry)
    candidates = dict(updated.get("selector_candidates") or {})
    candidates["css"] = css
    candidates["refresh_strategy"] = strategy
    updated["selector_candidates"] = candidates
    metadata = dict(updated.get("metadata") or {})
    metadata["css_selector"] = css
    metadata["page_url"] = page_url
    metadata["live_refresh_strategy"] = strategy
    metadata["live_refresh_at"] = now
    updated["metadata"] = metadata
    updated["capture_mode"] = "live_cdp_refresh"
    updated["confirmed_at"] = now
    updated["confirmed_by"] = PHASE
    updated["relabel_phase"] = PHASE
    return updated


def refresh_kling_multishot_selectors_from_cdp(
    *,
    cdp_url: str = DEFAULT_CDP_URL,
    map_path: Path | str | None = None,
) -> dict[str, Any]:
    ui_map = load_kling_ui_map(map_path=map_path)
    labels: dict[str, Any] = dict(ui_map.get("labels") or {})
    path = Path(map_path) if map_path else DEFAULT_MAP_PATH

    summary: dict[str, Any] = {
        "phase": PHASE,
        "cdp_url": cdp_url,
        "map_path": str(path.resolve()),
        "refreshed": {},
        "skipped_unstable": [],
        "errors": [],
        "generate_clicked": False,
        "credits_spent": False,
    }

    playwright = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        page = None
        for context in browser.contexts:
            for candidate in context.pages:
                if _is_runway_url(candidate.url):
                    page = candidate
                    break
            if page:
                break
        if page is None:
            summary["errors"].append("No Runway tab found in CDP browser")
            return summary

        summary["page_url"] = page.url

        for label in REFRESH_LABELS:
            entry = labels.get(label)
            if not isinstance(entry, dict):
                summary["errors"].append(f"missing map entry: {label}")
                continue
            try:
                located = locate_control(page, label, entry, timeout_ms=8000, require_stable=True)
                fresh_css = located.css_hint()
                override = STABLE_CSS_OVERRIDES.get(label)
                if override:
                    fresh_css = override
                elif not fresh_css or css_selector_is_unstable(fresh_css):
                    fresh_css = STABLE_CSS_OVERRIDES.get(label, fresh_css or "")
                if not fresh_css or css_selector_is_unstable(fresh_css):
                    summary["skipped_unstable"].append(
                        {"label": label, "strategy": located.strategy, "css": fresh_css or ""}
                    )
                    continue
                labels[label] = _patch_entry_css(
                    entry,
                    css=fresh_css,
                    strategy=located.strategy,
                    page_url=page.url,
                )
                summary["refreshed"][label] = {
                    "strategy": located.strategy,
                    "css": fresh_css,
                }
            except Exception as exc:
                summary["errors"].append(f"{label}: {exc}")

        if summary["refreshed"]:
            ui_map["labels"] = labels
            ui_map["updated_at"] = datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(ui_map, indent=2), encoding="utf-8")

        summary["ok"] = not summary["errors"]
        return summary
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Refresh Kling Multishot selectors from live CDP")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))
    args = parser.parse_args()

    summary = refresh_kling_multishot_selectors_from_cdp(
        cdp_url=args.cdp_url,
        map_path=Path(args.map_path),
    )
    out = ROOT / "project_brain" / "kling_multishot_selector_refresh_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
