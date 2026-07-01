"""Runway focus/visibility forensic probes — detect Generate delay vs browser focus."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROBE_VERSION = "runway_focus_dependency_probe_v2"
DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parents[2] / "project_brain" / "runway_focus_dependency_last_probe.json"
)

_FOCUS_SNAPSHOT_JS = """() => {
    const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
    const overlays = [];
    for (const node of document.querySelectorAll(
        '[role="dialog"], [aria-modal="true"], [data-state="open"], .modal, [class*="overlay" i]'
    )) {
        const rect = node.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) continue;
        const style = window.getComputedStyle(node);
        if (style.visibility === 'hidden' || style.display === 'none') continue;
        overlays.push({
            tag: String(node.tagName || '').toLowerCase(),
            role: node.getAttribute('role') || '',
            ariaModal: node.getAttribute('aria-modal') || '',
            text: normalize(node.innerText || node.textContent || '').slice(0, 120),
            zIndex: style.zIndex,
            pointerEvents: style.pointerEvents,
            opacity: style.opacity,
        });
    }
    let generateProbe = null;
    const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
    for (const btn of buttons) {
        const label = normalize(btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '');
        if (!/^generate$/i.test(label)) continue;
        const rect = btn.getBoundingClientRect();
        const style = window.getComputedStyle(btn);
        generateProbe = {
            label,
            disabled: Boolean(btn.disabled),
            ariaDisabled: btn.getAttribute('aria-disabled'),
            visible: rect.width > 0 && rect.height > 0,
            pointerEvents: style.pointerEvents,
            opacity: style.opacity,
            inViewport: rect.top >= 0 && rect.left >= 0 && rect.bottom <= window.innerHeight,
        };
        break;
    }
    return {
        pageUrl: location.href,
        visibilityState: document.visibilityState,
        documentHidden: document.hidden,
        hasFocus: document.hasFocus(),
        readyState: document.readyState,
        overlayCount: overlays.length,
        overlays: overlays.slice(0, 8),
        generateButton: generateProbe,
    };
}"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _monotonic_ms() -> float:
    return time.monotonic() * 1000.0


@dataclass
class GenerateClickProbeResult:
    queued_at: str
    click_started_at: str
    click_finished_at: str
    queued_to_click_start_ms: float
    click_duration_ms: float
    before: dict[str, Any]
    after: dict[str, Any]
    page_activated: bool = False
    click_error: str = ""
    generate_state_changed: bool = False
    focus_likely_blocker: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PROBE_VERSION,
            "queued_at": self.queued_at,
            "click_started_at": self.click_started_at,
            "click_finished_at": self.click_finished_at,
            "queued_to_click_start_ms": self.queued_to_click_start_ms,
            "click_duration_ms": self.click_duration_ms,
            "before": dict(self.before),
            "after": dict(self.after),
            "page_activated": self.page_activated,
            "click_error": self.click_error,
            "generate_state_changed": self.generate_state_changed,
            "focus_likely_blocker": self.focus_likely_blocker,
            "notes": list(self.notes),
        }


def snapshot_page_focus_state(page: Any) -> dict[str, Any]:
    """Capture visibility, focus, URL, overlays, and Generate button interactability."""
    payload: dict[str, Any] = {
        "timestamp": _now_iso(),
        "page_url": "",
        "visibility_state": "unknown",
        "document_hidden": None,
        "has_focus": None,
        "ready_state": "unknown",
        "overlay_count": 0,
        "overlays": [],
        "generate_button": None,
        "tab_active_hint": "unknown",
        "errors": [],
    }
    try:
        payload["page_url"] = str(page.url or "")
    except Exception as exc:
        payload["errors"].append(f"page_url:{exc}")

    try:
        evaluated = page.evaluate(_FOCUS_SNAPSHOT_JS)
        if isinstance(evaluated, dict):
            payload.update(
                {
                    "visibility_state": evaluated.get("visibilityState"),
                    "document_hidden": evaluated.get("documentHidden"),
                    "has_focus": evaluated.get("hasFocus"),
                    "ready_state": evaluated.get("readyState"),
                    "overlay_count": int(evaluated.get("overlayCount") or 0),
                    "overlays": list(evaluated.get("overlays") or []),
                    "generate_button": evaluated.get("generateButton"),
                }
            )
            if evaluated.get("pageUrl"):
                payload["page_url"] = evaluated.get("pageUrl")
    except Exception as exc:
        payload["errors"].append(f"evaluate:{exc}")

    try:
        payload["tab_active_hint"] = "foreground" if page.evaluate("() => document.hasFocus()") else "background"
    except Exception:
        payload["tab_active_hint"] = "unknown"

    return payload


def _generate_button_disabled(snapshot: dict[str, Any]) -> bool | None:
    btn = snapshot.get("generate_button") or {}
    if not btn:
        return None
    if btn.get("disabled"):
        return True
    if str(btn.get("ariaDisabled") or "").lower() == "true":
        return True
    return False


def _focus_blocker_heuristic(before: dict[str, Any]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    blocker = False
    if before.get("visibility_state") == "hidden" or before.get("document_hidden") is True:
        notes.append("document_hidden_or_visibility_hidden")
        blocker = True
    if before.get("has_focus") is False:
        notes.append("document_hasFocus_false")
        blocker = True
    if int(before.get("overlay_count") or 0) > 0:
        notes.append(f"overlays_present:{before.get('overlay_count')}")
    btn = before.get("generate_button") or {}
    if btn and btn.get("pointerEvents") == "none":
        notes.append("generate_pointer_events_none")
        blocker = True
    if btn and btn.get("visible") is False:
        notes.append("generate_not_visible")
        blocker = True
    return blocker, notes


def activate_page_for_interaction(page: Any) -> bool:
    """Best-effort foreground activation before dangerous UI clicks."""
    activated = False
    try:
        page.bring_to_front()
        activated = True
    except Exception:
        pass
    try:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Page.bringToFront")
        activated = True
    except Exception:
        pass
    return activated


def is_page_ready_for_generate_click(snapshot: dict[str, Any]) -> bool:
    if snapshot.get("visibility_state") != "visible":
        return False
    if snapshot.get("document_hidden") is True:
        return False
    btn = snapshot.get("generate_button") or {}
    if btn and btn.get("visible") is False:
        return False
    if btn and btn.get("disabled"):
        return False
    return True


def wait_for_page_ready_for_generate(
    page: Any,
    *,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Wait until tab is visible and Generate appears interactable."""
    deadline = time.monotonic() + max(0.5, timeout_seconds)
    snapshot = snapshot_page_focus_state(page)
    while time.monotonic() < deadline:
        if is_page_ready_for_generate_click(snapshot):
            return snapshot
        time.sleep(0.25)
        snapshot = snapshot_page_focus_state(page)
    return snapshot


def prepare_page_for_auto_generate_click(page: Any) -> dict[str, Any]:
    """Activate Runway tab/window before Generate so click is not deferred until operator focus."""
    activate_page_for_interaction(page)
    time.sleep(0.35)
    return wait_for_page_ready_for_generate(page)


def execute_generate_click_with_focus_probe(
    page: Any,
    locator: Any,
    *,
    activate_before_click: bool = True,
    click_timeout_ms: int = 10_000,
) -> GenerateClickProbeResult:
    """
    Log focus snapshot before/after Generate click with queue vs execute timestamps.
    Auto-activates page by default so Generate is not stuck waiting for operator focus.
    """
    queued_mono = _monotonic_ms()
    queued_at = _now_iso()
    before = snapshot_page_focus_state(page)
    focus_blocker, notes = _focus_blocker_heuristic(before)

    page_activated = False
    if activate_before_click:
        before = prepare_page_for_auto_generate_click(page)
        page_activated = True
        notes.append("auto_generate_page_prepared")
        focus_blocker, extra = _focus_blocker_heuristic(before)
        notes.extend(extra)

    click_started_at = _now_iso()
    click_start_mono = _monotonic_ms()
    click_error = ""
    used_force = False
    try:
        locator.click(timeout=click_timeout_ms)
    except Exception as exc:
        click_error = str(exc)[:300]
        notes.append(f"click_error:{click_error}")
        if activate_before_click:
            try:
                used_force = True
                notes.append("auto_generate_force_click_retry")
                locator.click(timeout=click_timeout_ms, force=True)
                click_error = ""
            except Exception as force_exc:
                click_error = str(force_exc)[:300]
                notes.append(f"force_click_error:{click_error}")

    click_finished_at = _now_iso()
    click_end_mono = _monotonic_ms()
    time.sleep(0.35)
    after = snapshot_page_focus_state(page)

    before_disabled = _generate_button_disabled(before)
    after_disabled = _generate_button_disabled(after)
    state_changed = (
        before_disabled is not None
        and after_disabled is not None
        and before_disabled != after_disabled
    ) or (
        (before.get("generate_button") or {}).get("label")
        != (after.get("generate_button") or {}).get("label")
    )

    if focus_blocker and not click_error and not page_activated:
        notes.append("click_dispatched_while_focus_blocked")
    elif page_activated and not focus_blocker:
        notes.append("auto_generate_no_stuck_click")

    if used_force and not click_error:
        notes.append("force_click_succeeded")

    return GenerateClickProbeResult(
        queued_at=queued_at,
        click_started_at=click_started_at,
        click_finished_at=click_finished_at,
        queued_to_click_start_ms=round(click_start_mono - queued_mono, 2),
        click_duration_ms=round(click_end_mono - click_start_mono, 2),
        before=before,
        after=after,
        page_activated=page_activated,
        click_error=click_error,
        generate_state_changed=state_changed,
        focus_likely_blocker=focus_blocker,
        notes=notes,
    )


def analyze_live_run_artifacts(project_root: str | Path) -> list[dict[str, Any]]:
    """Collect focus_probe payloads from recent live_run_result.json files."""
    root = Path(project_root).resolve()
    findings: list[dict[str, Any]] = []
    patterns = (
        root / "outputs" / "kling_frame_to_video",
        root / "outputs" / "kling_multishot_live",
    )
    for base in patterns:
        if not base.is_dir():
            continue
        for path in sorted(base.glob("**/live_run_result.json"), reverse=True)[:40]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            probe = payload.get("focus_probe") or payload.get("generate_focus_probe")
            if not probe:
                continue
            findings.append(
                {
                    "path": str(path),
                    "run_id": payload.get("run_id"),
                    "generate_clicked": payload.get("generate_clicked"),
                    "focus_probe": probe,
                }
            )
    return findings


def static_code_forensic() -> dict[str, Any]:
    """Code-path review for focus/tab activation gaps."""
    root = Path(__file__).resolve().parents[2]
    frame_src = (root / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    multishot_src = (root / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    dry_src = (root / "content_brain/execution/kling_frame_to_video_live_dry_run.py").read_text(encoding="utf-8")
    return {
        "bring_to_front_used": "bring_to_front" in frame_src or "bring_to_front" in multishot_src,
        "cdp_page_bring_to_front_used": "Page.bringToFront" in frame_src or "Page.bringToFront" in multishot_src,
        "visibility_state_checked": "visibilityState" in frame_src or "visibilityState" in multishot_src,
        "connect_over_cdp": "connect_over_cdp" in frame_src,
        "ensure_generate_page_navigates": "page.goto" in frame_src.split("_ensure_runway_generate_page", 1)[-1][:600],
        "generate_click_instrumented": "execute_generate_click_with_focus_probe" in frame_src
        or "execute_generate_click_with_focus_probe" in multishot_src,
        "auto_generate_prepare": "prepare_page_for_auto_generate_click" in frame_src
        or "prepare_page_for_auto_generate_click" in (root / "content_brain/execution/runway_focus_dependency_probe.py").read_text(encoding="utf-8"),
        "auto_activate_default_true": "activate_before_click: bool = True" in (root / "content_brain/execution/runway_focus_dependency_probe.py").read_text(encoding="utf-8"),
        "find_page_no_activation": "_find_runway_generate_page" in dry_src and "bring_to_front" not in dry_src,
    }


def build_forensic_conclusion(
    *,
    static: dict[str, Any],
    artifact_findings: list[dict[str, Any]],
    live_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    focus_dependent = "likely_yes"
    queued_before_focus = "unknown"
    delay_cause = "background_tab_or_hidden_document_no_activation"
    notes: list[str] = []

    if not static.get("bring_to_front_used") and not static.get("cdp_page_bring_to_front_used"):
        notes.append("no_page_activation_before_generate_in_code")
        queued_before_focus = "likely_yes"
        focus_dependent = "likely_yes"
        delay_cause = "background_tab_or_hidden_document_no_activation"
    if static.get("connect_over_cdp"):
        notes.append("runtime_attaches_via_cdp_to_existing_chrome_tab")
    if static.get("find_page_no_activation"):
        notes.append("generate_tab_selected_without_foreground_activation")

    blocked_runs = []
    for item in artifact_findings:
        probe = item.get("focus_probe") or {}
        before = probe.get("before") or {}
        if before.get("visibility_state") == "hidden" or before.get("has_focus") is False:
            blocked_runs.append(item)
        if probe.get("focus_likely_blocker"):
            blocked_runs.append(item)

    if blocked_runs:
        queued_before_focus = "yes"
        notes.append(f"artifact_runs_with_focus_blocker:{len(blocked_runs)}")

    if live_snapshot:
        if live_snapshot.get("visibility_state") == "hidden" or live_snapshot.get("has_focus") is False:
            focus_dependent = "yes"
            queued_before_focus = "yes"
            notes.append("live_cdp_snapshot_shows_unfocused_page")

    if artifact_findings and not blocked_runs and live_snapshot is None:
        focus_dependent = "inconclusive_artifacts_show_focused"
        queued_before_focus = "no_in_logged_runs"

    return {
        "focus_dependent": focus_dependent,
        "generate_queued_before_operator_click": queued_before_focus,
        "delay_cause": delay_cause,
        "recommended_fix": (
            "Before Generate: call page.bring_to_front() + CDP Page.bringToFront, "
            "wait until document.visibilityState==='visible' && document.hasFocus(), "
            "log focus_probe (now instrumented), retry click with force=true only if probe still blocked."
        ),
        "notes": notes,
    }


def write_probe_report(
    *,
    report_path: Path,
    static: dict[str, Any],
    artifact_findings: list[dict[str, Any]],
    live_snapshot: dict[str, Any] | None,
    conclusion: dict[str, Any],
) -> None:
    lines = [
        "# RUNWAY FOCUS DEPENDENCY REPORT",
        "",
        f"Generated: {_now_iso()}",
        f"Probe version: {PROBE_VERSION}",
        "",
        "## Conclusion",
        "",
        f"- **focus dependent:** {conclusion.get('focus_dependent')}",
        f"- **generate queued before operator click:** {conclusion.get('generate_queued_before_operator_click')}",
        f"- **delay cause:** {conclusion.get('delay_cause')}",
        f"- **recommended fix:** {conclusion.get('recommended_fix')}",
        "",
        "## Static code forensic",
        "",
    ]
    for key, value in static.items():
        lines.append(f"- **{key}:** {value}")
    lines.extend(["", "## Live CDP snapshot", ""])
    if live_snapshot:
        for key, value in live_snapshot.items():
            if key == "overlays":
                lines.append(f"- **{key}:** {len(value or [])} item(s)")
            else:
                lines.append(f"- **{key}:** {value}")
    else:
        lines.append("- CDP snapshot not collected (browser unavailable or probe skipped)")
    lines.extend(["", "## Artifact focus probes", ""])
    if artifact_findings:
        for item in artifact_findings[:10]:
            probe = item.get("focus_probe") or {}
            before = probe.get("before") or {}
            lines.append(
                f"- `{item.get('run_id')}` visibility={before.get('visibility_state')} "
                f"hasFocus={before.get('has_focus')} blocker={probe.get('focus_likely_blocker')}"
            )
    else:
        lines.append("- No instrumented live_run_result.json files found yet (re-run live engine after probe wiring)")
    lines.extend(
        [
            "",
            "## Operator observation (reported)",
            "",
            "Sometimes automation appears idle until the operator clicks the Chrome window; "
            "Generate then executes immediately. This matches a focus/visibility-triggered UI wake-up: "
            "CDP attaches to an existing tab without `bring_to_front`, Chrome may keep "
            "`document.visibilityState='hidden'` while unfocused, and React handlers or rAF-throttled "
            "render can defer the Generate effect until the window is activated.",
            "",
            "## Instrumentation added",
            "",
            "- `content_brain/execution/runway_focus_dependency_probe.py`",
            "- Before every Generate: logs `visibilityState`, `hasFocus`, overlays, Generate interactability",
            "- Timestamps: `queued_at`, `click_started_at`, `click_finished_at` in `live_run_result.json` → `focus_probe`",
            "- Forensic runner: `python project_brain/run_runway_focus_dependency_forensic.py`",
            "",
            "## Notes",
            "",
        ]
    )
    for note in conclusion.get("notes") or []:
        lines.append(f"- {note}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "PROBE_VERSION",
    "DEFAULT_REPORT_PATH",
    "GenerateClickProbeResult",
    "prepare_page_for_auto_generate_click",
    "wait_for_page_ready_for_generate",
    "is_page_ready_for_generate_click",
    "analyze_live_run_artifacts",
    "build_forensic_conclusion",
    "execute_generate_click_with_focus_probe",
    "snapshot_page_focus_state",
    "static_code_forensic",
    "write_probe_report",
]
