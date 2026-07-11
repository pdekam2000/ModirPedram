#!/usr/bin/env python3
"""
Kling Multishot shadow runner — 2-shot continuity (12s + 3s).

Connects to Chrome CDP, configures Multishot UI from runway_ui_map.json, stops before Generate.
Never clicks Generate when dry_run=True (default). No credits spent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_config import (  # noqa: E402
    BLOCKED_CLICK_LABELS,
    CLIP_DURATION_SECONDS,
    MULTISHOT_STRATEGY,
    OPTIONAL_KLING_LABELS,
    REQUIRED_KLING_LABELS,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_multishot_map_loader import (  # noqa: E402
    load_kling_ui_map,
    resolve_kling_multishot_controls,
    verify_generate_approval_gate,
)
from content_brain.execution.kling_multishot_locator import (  # noqa: E402
    LocatedControl,
    css_selector_is_unstable,
    locate_control,
    try_locate_control,
)
from content_brain.execution.runway_continuity_approval_guard import (  # noqa: E402
    can_execute_dangerous_action,
    is_approval_gated_control,
)

from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402

RUNNER_VERSION = "kling_multishot_shadow_runner_v2"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
RUNWAY_URL_MARKER = "app.runwayml.com"
SCREENSHOT_DIR = ROOT / "project_brain" / "runway_ui_mapping" / "screenshots" / "kling_multishot_live_dry_run"


@dataclass
class ShadowStep:
    step_id: str
    label: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "step_id": self.step_id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class KlingMultishotShadowResult:
    ok: bool
    dry_run: bool
    connect_browser: bool
    multishot_strategy: str
    shot_1_duration_seconds: int
    shot_2_duration_seconds: int
    clip_duration_seconds: int
    add_shot_used: bool
    generate_clicked: bool
    credits_spent: bool
    steps: list[ShadowStep] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    map_snapshot: dict[str, Any] = field(default_factory=dict)
    page_url: str = ""
    screenshots: list[str] = field(default_factory=list)
    locator_strategies: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RUNNER_VERSION,
            "ok": self.ok,
            "dry_run": self.dry_run,
            "connect_browser": self.connect_browser,
            "multishot_strategy": self.multishot_strategy,
            "shot_1_duration_seconds": self.shot_1_duration_seconds,
            "shot_2_duration_seconds": self.shot_2_duration_seconds,
            "clip_duration_seconds": self.clip_duration_seconds,
            "add_shot_used": self.add_shot_used,
            "generate_clicked": self.generate_clicked,
            "credits_spent": self.credits_spent,
            "steps": [step.to_dict() for step in self.steps],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "map_snapshot": dict(self.map_snapshot),
            "page_url": self.page_url,
            "screenshots": list(self.screenshots),
            "locator_strategies": dict(self.locator_strategies),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


def _is_runway_url(url: str) -> bool:
    return RUNWAY_URL_MARKER in str(url or "").lower()


def _record_step(result: KlingMultishotShadowResult, step_id: str, label: str, status: str, detail: str = "") -> None:
    result.steps.append(ShadowStep(step_id=step_id, label=label, status=status, detail=detail))


def _fail(result: KlingMultishotShadowResult, step_id: str, label: str, message: str) -> KlingMultishotShadowResult:
    result.ok = False
    result.errors.append(message)
    _record_step(result, step_id, label, "failed", message)
    return result


def _capture_step_screenshot(page: Any, result: KlingMultishotShadowResult, step_id: str, label: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = SCREENSHOT_DIR / f"{step_id}_{label}_{stamp}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        result.screenshots.append(rel)
        return rel
    except Exception as exc:
        result.warnings.append(f"screenshot_failed:{label}:{exc}")
        return ""


def _locate_or_fail(
    page: Any,
    result: KlingMultishotShadowResult,
    step_id: str,
    label: str,
    entry: dict[str, Any],
    *,
    require_stable: bool = True,
) -> LocatedControl | None:
    try:
        located = locate_control(page, label, entry, require_stable=require_stable)
        result.locator_strategies[label] = located.strategy
        return located
    except RuntimeError as exc:
        _fail(result, step_id, label, f"Unstable/missing selector for {label}: {exc}")
        return None


def _read_locator_text(located: LocatedControl) -> str:
    loc = located.locator
    try:
        return str(loc.inner_text(timeout=3000) or "").strip()
    except Exception:
        return str(loc.text_content(timeout=3000) or "").strip()


def _safe_click(page: Any, located: LocatedControl, *, timeout_ms: int = 8000) -> None:
    try:
        located.locator.click(timeout=timeout_ms)
    except Exception:
        page.keyboard.press("Escape")
        time.sleep(0.2)
        located.locator.click(timeout=timeout_ms, force=True)


def _multishot_already_selected(located: LocatedControl) -> bool:
    try:
        return bool(
            located.locator.evaluate(
                """(el) => {
                    if (el.getAttribute('data-selected') === 'true') return true;
                    if (el.matches('input[type="radio"]')) return el.checked === true;
                    const radio = el.querySelector('input[type="radio"]');
                    if (radio && radio.checked) return true;
                    return false;
                }"""
            )
        )
    except Exception:
        return False


def _duration_token(seconds: int) -> str:
    return f"{seconds}s"


def _text_has_duration(text: str, seconds: int) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower())
    token = _duration_token(seconds).lower()
    long_form = f"{seconds} second"
    return token in normalized or long_form in normalized


def validate_map_preconditions(
    *,
    map_path: Path | str | None = None,
) -> tuple[KlingMultishotShadowResult, dict[str, Any], Any]:
    result = KlingMultishotShadowResult(
        ok=False,
        dry_run=True,
        connect_browser=False,
        multishot_strategy=MULTISHOT_STRATEGY,
        shot_1_duration_seconds=SHOT_1_DURATION_SECONDS,
        shot_2_duration_seconds=SHOT_2_DURATION_SECONDS,
        clip_duration_seconds=CLIP_DURATION_SECONDS,
        add_shot_used=False,
        generate_clicked=False,
        credits_spent=False,
    )
    ui_map = load_kling_ui_map(map_path=map_path)
    snapshot = resolve_kling_multishot_controls(ui_map, map_path=map_path)
    result.map_snapshot = snapshot.to_dict()

    if not snapshot.ok:
        missing = ", ".join(snapshot.missing) or "none"
        invalid = ", ".join(f"{i['label']}:{i['reason']}" for i in snapshot.invalid) or "none"
        return _fail(
            result,
            "map_validate",
            "runway_ui_map",
            f"Kling map invalid — missing=[{missing}] invalid=[{invalid}]",
        ), ui_map, snapshot

    gate_ok, gate_reason = verify_generate_approval_gate(ui_map)
    if not gate_ok:
        return _fail(result, "approval_gate", "generate_button", gate_reason), ui_map, snapshot

    if not is_approval_gated_control("generate_button"):
        return _fail(
            result,
            "approval_gate",
            "generate_button",
            "generate_button is not marked approval-gated in continuity guard",
        ), ui_map, snapshot

    if can_execute_dangerous_action("generate_button"):
        return _fail(
            result,
            "approval_gate",
            "generate_button",
            "generate_button must not be executable without operator approval",
        ), ui_map, snapshot

    _record_step(result, "map_validate", "runway_ui_map", "passed", f"{len(REQUIRED_KLING_LABELS)} required labels")
    _record_step(result, "approval_gate", "generate_button", "passed", "requires_approval=true")
    result.ok = True
    return result, ui_map, snapshot


def run_kling_multishot_shadow(
    *,
    shot_1_prompt: str,
    shot_2_prompt: str,
    first_frame_path: str | Path | None = None,
    dry_run: bool = True,
    connect_browser: bool = True,
    cdp_url: str = DEFAULT_CDP_URL,
    map_path: Path | str | None = None,
) -> KlingMultishotShadowResult:
    if not dry_run:
        raise ValueError("Only dry_run=True is supported in shadow mode (Generate never clicked).")

    if not str(shot_1_prompt or "").strip() or not str(shot_2_prompt or "").strip():
        raise ValueError("shot_1_prompt and shot_2_prompt are required")

    pre, ui_map, snapshot = validate_map_preconditions(map_path=map_path)
    if not pre.ok:
        pre.dry_run = dry_run
        pre.connect_browser = connect_browser
        return pre

    result = KlingMultishotShadowResult(
        ok=True,
        dry_run=dry_run,
        connect_browser=connect_browser,
        multishot_strategy=MULTISHOT_STRATEGY,
        shot_1_duration_seconds=SHOT_1_DURATION_SECONDS,
        shot_2_duration_seconds=SHOT_2_DURATION_SECONDS,
        clip_duration_seconds=CLIP_DURATION_SECONDS,
        add_shot_used=False,
        generate_clicked=False,
        credits_spent=False,
        steps=list(pre.steps),
        map_snapshot=pre.map_snapshot,
    )

    if not connect_browser:
        _record_step(result, "browser", "cdp", "skipped", "map-only mode")
        result.warnings.append("browser_not_connected_map_only")
        return result

    labels = dict(ui_map.get("labels") or {})

    playwright = None
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        _record_step(result, "browser", "cdp", "passed", cdp_url)

        page = None
        for context in browser.contexts:
            for candidate in context.pages:
                if _is_runway_url(candidate.url):
                    page = candidate
                    break
            if page:
                break
        if page is None:
            return _fail(result, "browser", "runway_tab", "No Runway tab found in CDP browser")

        result.page_url = page.url
        _record_step(result, "browser", "runway_tab", "passed", page.url[:120])

        def entry(label: str) -> dict[str, Any]:
            raw = labels.get(label)
            if not isinstance(raw, dict):
                raise RuntimeError(f"Missing map entry for {label}")
            return raw

        def step_pass(step_id: str, label: str, detail: str) -> None:
            shot = _capture_step_screenshot(page, result, step_id, label)
            merged = detail if not shot else f"{detail}; screenshot={shot}"
            _record_step(result, step_id, label, "passed", merged)

        # 1 — Provider Kling 3.0 Pro
        provider = _locate_or_fail(page, result, "01", "provider_kling_3_pro", entry("provider_kling_3_pro"))
        if provider is None:
            return result
        provider_text = _read_locator_text(provider)
        if "kling 3" not in provider_text.lower():
            _safe_click(page, provider)
            time.sleep(0.35)
            page.keyboard.press("Escape")
            time.sleep(0.2)
        step_pass("01", "provider_kling_3_pro", f"strategy={provider.strategy}; text={provider_text[:30]}")

        # 2 — Multishot tab
        multishot = _locate_or_fail(page, result, "02", "multishot_tab", entry("multishot_tab"))
        if multishot is None:
            return result
        if not _multishot_already_selected(multishot):
            _safe_click(page, multishot)
            time.sleep(0.5)
        step_pass("02", "multishot_tab", f"strategy={multishot.strategy}; already_selected={_multishot_already_selected(multishot)}")

        # 3 — Audio ON
        audio = _locate_or_fail(page, result, "03", "audio_toggle_on", entry("audio_toggle_on"))
        if audio is None:
            return result
        audio_text = _read_locator_text(audio)
        if "on" not in audio_text.lower():
            return _fail(
                result,
                "03",
                "audio_toggle_on",
                f"Audio toggle not ON (read: {audio_text!r})",
            )
        step_pass("03", "audio_toggle_on", f"{audio_text[:40]}; strategy={audio.strategy}")

        # 4 — First frame upload (optional detect / upload)
        first_frame_entry = entry("first_frame_upload")
        first_frame_detected = try_locate_control(page, "first_frame_upload", first_frame_entry, timeout_ms=4000)
        if first_frame_path:
            if first_frame_detected is None:
                return _fail(result, "04", "first_frame_upload", "first_frame_upload control not found")
            upload_path = Path(first_frame_path).resolve()
            if not upload_path.is_file():
                return _fail(result, "04", "first_frame_upload", f"first_frame_path missing: {upload_path}")
            upload_btn = first_frame_detected.locator
            try:
                with page.expect_file_chooser(timeout=8000) as fc_info:
                    upload_btn.click(timeout=8000)
                fc_info.value.set_files(str(upload_path))
            except Exception:
                page.locator('input[type="file"]').first.set_input_files(str(upload_path))
            step_pass("04", "first_frame_upload", str(upload_path))
        elif first_frame_detected is not None:
            step_pass("04", "first_frame_upload", f"detected; strategy={first_frame_detected.strategy}")
        else:
            _record_step(result, "04", "first_frame_upload", "skipped", "control not visible")

        # 5 — Shot 1 duration → 12s
        shot1_menu = _locate_or_fail(page, result, "05", "shot_1_duration_menu", entry("shot_1_duration_menu"))
        if shot1_menu is None:
            return result
        _safe_click(page, shot1_menu)
        time.sleep(0.35)
        shot1_12 = _locate_or_fail(page, result, "05", "shot_1_duration_12s", entry("shot_1_duration_12s"), require_stable=False)
        if shot1_12 is None:
            return result
        shot1_12.locator.click(timeout=8000)
        time.sleep(0.45)
        shot1_menu_after = _locate_or_fail(page, result, "05", "shot_1_duration_menu", entry("shot_1_duration_menu"))
        if shot1_menu_after is None:
            return result
        shot1_text = _read_locator_text(shot1_menu_after)
        if not _text_has_duration(shot1_text, SHOT_1_DURATION_SECONDS):
            return _fail(
                result,
                "05",
                "shot_1_duration_menu",
                f"Shot 1 duration not verified as {SHOT_1_DURATION_SECONDS}s (read: {shot1_text!r})",
            )
        step_pass("05", "shot_1_duration_12s", f"{shot1_text[:40]}; strategy={shot1_12.strategy}")

        # 6 — Shot 2 duration → 3s (confirm default or select)
        shot2_menu = _locate_or_fail(page, result, "06", "shot_2_duration_menu", entry("shot_2_duration_menu"))
        if shot2_menu is None:
            return result
        shot2_text = _read_locator_text(shot2_menu)
        if not _text_has_duration(shot2_text, SHOT_2_DURATION_SECONDS):
            shot2_menu.locator.click(timeout=8000)
            time.sleep(0.35)
            shot2_3 = _locate_or_fail(page, result, "06", "shot_2_duration_3s", entry("shot_2_duration_3s"), require_stable=False)
            if shot2_3 is None:
                return result
            shot2_3.locator.click(timeout=8000)
            time.sleep(0.45)
            shot2_menu = _locate_or_fail(page, result, "06", "shot_2_duration_menu", entry("shot_2_duration_menu"))
            if shot2_menu is None:
                return result
            shot2_text = _read_locator_text(shot2_menu)
        if not _text_has_duration(shot2_text, SHOT_2_DURATION_SECONDS):
            return _fail(
                result,
                "06",
                "shot_2_duration_3s",
                f"Shot 2 duration not verified as {SHOT_2_DURATION_SECONDS}s (read: {shot2_text!r})",
            )
        step_pass("06", "shot_2_duration_3s", f"{shot2_text[:40]}")

        # 7 — Prompts
        for idx, (label, text) in enumerate(
            (("shot_1_prompt", shot_1_prompt), ("shot_2_prompt", shot_2_prompt)),
            start=7,
        ):
            located = _locate_or_fail(page, result, f"{idx:02d}", label, entry(label))
            if located is None:
                return result
            located.locator.click(timeout=8000)
            located.locator.fill(text.strip(), timeout=8000)
            step_pass(f"{idx:02d}", label, f"{len(text.strip())} chars; strategy={located.strategy}")

        # 8 — Generate exists, approval-gated, NOT clicked
        generate = _locate_or_fail(page, result, "09", "generate_button", entry("generate_button"))
        if generate is None:
            return result
        if generate.strategy == "map_css_unstable_fallback":
            return _fail(
                result,
                "09",
                "generate_button",
                "generate_button resolved only via unstable React ID — stopping before Generate",
            )
        if dry_run and "generate_button" in BLOCKED_CLICK_LABELS:
            shot = _capture_step_screenshot(page, result, "09", "generate_button")
            detail = f"dry_run — not clicked; strategy={generate.strategy}"
            if shot:
                detail = f"{detail}; screenshot={shot}"
            _record_step(result, "09", "generate_button", "blocked", detail)
        else:
            return _fail(result, "09", "generate_button", "dry_run guard failed")

        # Confirm optional 5-shot labels were not used
        for optional in OPTIONAL_KLING_LABELS:
            if optional in labels and optional.startswith("shot_") and optional not in REQUIRED_KLING_LABELS:
                result.warnings.append(f"optional_label_present_not_used:{optional}")

        result.ok = True
        return result

    except Exception as exc:
        result.ok = False
        result.errors.append(str(exc))
        _record_step(result, "runtime", "shadow_runner", "failed", str(exc)[:200])
        return result
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling Multishot shadow runner (2-shot continuity)")
    parser.add_argument("--shot-1-prompt", required=True)
    parser.add_argument("--shot-2-prompt", required=True)
    parser.add_argument("--first-frame-path", default="")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))
    parser.add_argument("--map-only", action="store_true", help="Validate map only; do not connect CDP")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    summary = run_kling_multishot_shadow(
        shot_1_prompt=args.shot_1_prompt,
        shot_2_prompt=args.shot_2_prompt,
        first_frame_path=args.first_frame_path or None,
        dry_run=True,
        connect_browser=not args.map_only,
        cdp_url=args.cdp_url,
        map_path=Path(args.map_path),
    )
    out = ROOT / "project_brain" / "kling_multishot_shadow_run_summary.json"
    out.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
