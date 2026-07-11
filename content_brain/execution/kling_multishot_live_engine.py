"""Kling Multishot live engine — prepare, approval gate, optional Generate/download."""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.kling_multishot_config import (
    CLIP_DURATION_SECONDS,
    MULTISHOT_STRATEGY,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_multishot_locator import locate_control, resolve_kling_3_pro_provider, try_locate_control
from content_brain.execution.kling_multishot_map_loader import load_kling_ui_map
from content_brain.execution.runway_continuity_approval_guard import (
    can_execute_dangerous_action,
    grant_continuity_approval,
)
from content_brain.execution.runway_continuity_models import RunwayContinuityApprovalRecord
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH

ROOT = Path(__file__).resolve().parents[2]
LIVE_ENGINE_VERSION = "kling_multishot_live_v1"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
OUTPUT_ROOT = ROOT / "outputs" / "kling_multishot_live"
SCREENSHOT_DIR = ROOT / "project_brain" / "runway_ui_mapping" / "screenshots" / "kling_multishot_live"
RUNWAY_URL_MARKER = "app.runwayml.com"
MIN_REAL_MP4_BYTES = 1_048_576
MIN_REAL_MP4_SECONDS = 1.0
PLACEHOLDER_MAX_BYTES = 4096

STATUS_AWAITING_APPROVAL = "awaiting_approval"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_PREPARED = "prepared"
STATUS_DOWNLOAD_FAILED = "download_failed"

DOWNLOAD_STATUS_PENDING = "pending"
DOWNLOAD_STATUS_PASSED = "passed"
DOWNLOAD_STATUS_FAILED = "failed"

ESTIMATED_CREDIT_RISK = (
    "Kling 3.0 Pro Multishot 15s (12s+3s) — Runway subscription credits consumed on Generate"
)

BENCHMARK_SHOT_1 = (
    'A young boy discovers an injured baby dragon under twisted tree roots in a deep forest. '
    'The dragon is frightened, breathing nervously and growling softly. The boy slowly kneels and whispers, '
    '"Don\'t worry... I won\'t hurt you." Cinematic emotional fantasy scene, natural character voices, '
    "breathing, forest ambience, distant thunder, native audio."
)

BENCHMARK_SHOT_2 = (
    "The boy gently covers the baby dragon with his jacket. The dragon calms down and looks at him with trust "
    "as wind moves through the forest. This moment should bridge into the next scene where they walk deeper "
    "into the woods together. Native cinematic audio, soft breathing, leaves, wind."
)


@dataclass
class KlingMultishotApprovalChecklist:
    provider_selected: str = ""
    model_already_selected: bool = False
    multishot_selected: bool = False
    audio_on: bool = False
    shot_1_duration_seconds: int = 0
    shot_2_duration_seconds: int = 0
    shot_1_prompt_filled: bool = False
    shot_2_prompt_filled: bool = False
    shot_1_prompt_chars: int = 0
    shot_2_prompt_chars: int = 0
    first_frame_uploaded: bool = False
    first_frame_path: str = ""
    estimated_credit_risk: str = ESTIMATED_CREDIT_RISK
    confirmation_required: bool = True

    def all_ready(self) -> bool:
        return (
            bool(self.provider_selected)
            and self.multishot_selected
            and self.audio_on
            and self.shot_1_duration_seconds == SHOT_1_DURATION_SECONDS
            and self.shot_2_duration_seconds == SHOT_2_DURATION_SECONDS
            and self.shot_1_prompt_filled
            and self.shot_2_prompt_filled
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_selected": self.provider_selected,
            "model_already_selected": self.model_already_selected,
            "multishot_selected": self.multishot_selected,
            "audio_on": self.audio_on,
            "shot_1_duration_seconds": self.shot_1_duration_seconds,
            "shot_2_duration_seconds": self.shot_2_duration_seconds,
            "shot_1_prompt_filled": self.shot_1_prompt_filled,
            "shot_2_prompt_filled": self.shot_2_prompt_filled,
            "shot_1_prompt_chars": self.shot_1_prompt_chars,
            "shot_2_prompt_chars": self.shot_2_prompt_chars,
            "first_frame_uploaded": self.first_frame_uploaded,
            "first_frame_path": self.first_frame_path,
            "estimated_credit_risk": self.estimated_credit_risk,
            "confirmation_required": self.confirmation_required,
            "all_ready": self.all_ready(),
        }


@dataclass
class KlingMultishotLiveStep:
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
class KlingMultishotLiveResult:
    ok: bool
    status: str
    run_id: str
    dry_run_prepare: bool
    generate_clicked: bool
    credits_spent: bool
    approved_by: str | None
    approved_at: str | None
    generation_completed: bool = False
    download_status: str = DOWNLOAD_STATUS_PENDING
    recovery_mode: bool = False
    download_strategies: list[str] = field(default_factory=list)
    approval_checklist: dict[str, Any] = field(default_factory=dict)
    output_path: str = ""
    download_path: str = ""
    duration_seconds: float | None = None
    audio_present: bool | None = None
    native_audio_notes: str = ""
    steps: list[KlingMultishotLiveStep] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    locator_strategies: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    page_url: str = ""
    focus_probe: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": LIVE_ENGINE_VERSION,
            "ok": self.ok,
            "status": self.status,
            "run_id": self.run_id,
            "dry_run_prepare": self.dry_run_prepare,
            "generate_clicked": self.generate_clicked,
            "credits_spent": self.credits_spent,
            "generation_completed": self.generation_completed,
            "download_status": self.download_status,
            "recovery_mode": self.recovery_mode,
            "download_strategies": list(self.download_strategies),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "approval_checklist": dict(self.approval_checklist),
            "output_path": self.output_path,
            "download_path": self.download_path,
            "duration_seconds": self.duration_seconds,
            "audio_present": self.audio_present,
            "native_audio_notes": self.native_audio_notes,
            "multishot_strategy": MULTISHOT_STRATEGY,
            "clip_duration_seconds": CLIP_DURATION_SECONDS,
            "steps": [step.to_dict() for step in self.steps],
            "screenshots": list(self.screenshots),
            "locator_strategies": dict(self.locator_strategies),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "page_url": self.page_url,
            "focus_probe": dict(self.focus_probe),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


def _is_runway_url(url: str) -> bool:
    return RUNWAY_URL_MARKER in str(url or "").lower()


def _record_step(result: KlingMultishotLiveResult, step_id: str, label: str, status: str, detail: str = "") -> None:
    result.steps.append(KlingMultishotLiveStep(step_id=step_id, label=label, status=status, detail=detail))


def _fail(result: KlingMultishotLiveResult, step_id: str, label: str, message: str) -> KlingMultishotLiveResult:
    result.ok = False
    result.status = STATUS_FAILED
    result.errors.append(message)
    _record_step(result, step_id, label, "failed", message)
    return result


def _capture_screenshot(page: Any, result: KlingMultishotLiveResult, step_id: str, label: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = SCREENSHOT_DIR / f"{result.run_id}_{step_id}_{label}_{stamp}.png"
    try:
        page.screenshot(path=str(path), full_page=False, timeout=15000)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        result.screenshots.append(rel)
        return rel
    except Exception as exc:
        result.warnings.append(f"screenshot_failed:{label}:{exc}")
        return ""


def _duration_token(seconds: int) -> str:
    return f"{seconds}s"


def _text_has_duration(text: str, seconds: int) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower())
    token = _duration_token(seconds).lower()
    long_form = f"{seconds} second"
    return token in normalized or long_form in normalized


def _read_locator_text(located: Any) -> str:
    loc = located.locator
    try:
        return str(loc.inner_text(timeout=3000) or "").strip()
    except Exception:
        return str(loc.text_content(timeout=3000) or "").strip()


def _safe_click(page: Any, located: Any) -> None:
    try:
        located.locator.click(timeout=8000)
    except Exception:
        page.keyboard.press("Escape")
        time.sleep(0.2)
        located.locator.click(timeout=8000, force=True)


def _multishot_already_selected(located: Any) -> bool:
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


def _locate_or_fail(
    page: Any,
    result: KlingMultishotLiveResult,
    step_id: str,
    label: str,
    entry: dict[str, Any],
    *,
    require_stable: bool = True,
) -> Any | None:
    try:
        located = locate_control(page, label, entry, require_stable=require_stable)
        result.locator_strategies[label] = located.strategy
        return located
    except RuntimeError as exc:
        return _fail(result, step_id, label, f"Unstable/missing selector for {label}: {exc}")


def _detect_output_ready(page: Any) -> tuple[bool, str]:
    """Detect whether generated output appears ready for recovery/download."""
    try:
        download_btn = page.get_by_role("button", name=re.compile(r"download", re.I))
        if download_btn.count() > 0 and download_btn.first.is_visible():
            return True, "download_button_visible"
    except Exception:
        pass
    try:
        videos = page.locator("video")
        count = videos.count()
        for idx in range(count):
            video = videos.nth(idx)
            src = str(video.get_attribute("src") or "").strip()
            if src.startswith("http") or src.startswith("blob:"):
                return True, "video_element_ready"
            try:
                source_count = video.locator("source").count()
                for source_idx in range(source_count):
                    source_src = str(video.locator("source").nth(source_idx).get_attribute("src") or "").strip()
                    if source_src.startswith("http") or source_src.startswith("blob:"):
                        return True, "video_source_ready"
            except Exception:
                pass
    except Exception:
        pass
    try:
        anchors = page.locator('a[href*=".mp4"], a[download], a[href*="video"]')
        if anchors.count() > 0:
            return True, "download_link_visible"
    except Exception:
        pass
    return False, "output_not_ready"


def _wait_for_generation_complete(page: Any, *, max_wait_minutes: int = 20) -> tuple[bool, str]:
    deadline = time.monotonic() + max(1, max_wait_minutes) * 60
    last_reason = "waiting"
    while time.monotonic() < deadline:
        ready, reason = _detect_output_ready(page)
        if ready:
            return True, reason
        try:
            stop_btn = page.get_by_role("button", name=re.compile(r"stop|cancel", re.I))
            if stop_btn.count() == 0 or not stop_btn.first.is_visible():
                gen = page.get_by_role("button", name=re.compile(r"^generate$", re.I))
                if gen.count() > 0 and gen.first.is_enabled():
                    last_reason = "generate_re_enabled_without_output"
        except Exception:
            pass
        last_reason = "generation_in_progress"
        time.sleep(5)
    return False, f"timeout:{last_reason}"


def _collect_video_source_urls(page: Any) -> list[str]:
    urls: list[str] = []
    try:
        videos = page.locator("video")
        for idx in range(videos.count()):
            video = videos.nth(idx)
            src = str(video.get_attribute("src") or "").strip()
            if src:
                urls.append(src)
            for source_idx in range(video.locator("source").count()):
                source_src = str(video.locator("source").nth(source_idx).get_attribute("src") or "").strip()
                if source_src:
                    urls.append(source_src)
    except Exception:
        pass
    try:
        anchors = page.locator('a[href*=".mp4"], a[download], a[href*="video"]')
        for idx in range(min(anchors.count(), 8)):
            href = str(anchors.nth(idx).get_attribute("href") or "").strip()
            if href:
                urls.append(href)
    except Exception:
        pass
    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def _write_binary_payload(dest: Path, raw: bytes) -> Path | None:
    if not raw:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    return None


def _fetch_blob_via_page(page: Any, blob_url: str, dest: Path) -> Path | None:
    payload = page.evaluate(
        """async (mediaUrl) => {
            try {
                const response = await fetch(mediaUrl);
                if (!response.ok) {
                    return { ok: false, error: `http_${response.status}` };
                }
                const blob = await response.blob();
                const buffer = await blob.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                let binary = '';
                const chunk = 0x8000;
                for (let i = 0; i < bytes.length; i += chunk) {
                    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                }
                return { ok: true, data: btoa(binary), size: bytes.length };
            } catch (err) {
                return { ok: false, error: String(err) };
            }
        }""",
        blob_url,
    )
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    import base64

    raw = base64.b64decode(str(payload.get("data") or ""))
    return _write_binary_payload(dest, raw)


def _fetch_http_via_page(page: Any, url: str, dest: Path) -> Path | None:
    payload = page.evaluate(
        """async (mediaUrl) => {
            try {
                const response = await fetch(mediaUrl, { credentials: 'include' });
                if (!response.ok) {
                    return { ok: false, error: `http_${response.status}` };
                }
                const blob = await response.blob();
                const buffer = await blob.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                let binary = '';
                const chunk = 0x8000;
                for (let i = 0; i < bytes.length; i += chunk) {
                    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                }
                return { ok: true, data: btoa(binary), size: bytes.length };
            } catch (err) {
                return { ok: false, error: String(err) };
            }
        }""",
        url,
    )
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    import base64

    raw = base64.b64decode(str(payload.get("data") or ""))
    return _write_binary_payload(dest, raw)


def _try_ui_download(page: Any, dest: Path) -> tuple[Path | None, str]:
    selectors = [
        ("button_download", lambda p: p.get_by_role("button", name=re.compile(r"download", re.I)).first),
        ("anchor_download", lambda p: p.locator('a[download]').first),
        ("aria_download", lambda p: p.locator('[aria-label*="Download" i]').first),
        ("menuitem_download", lambda p: p.get_by_role("menuitem", name=re.compile(r"download", re.I)).first),
    ]
    menu_triggers = [
        lambda p: p.get_by_role("button", name=re.compile(r"more|options|menu|\.\.\.", re.I)).first,
        lambda p: p.locator('[aria-label*="More" i]').first,
    ]
    for trigger in menu_triggers:
        try:
            loc = trigger(page)
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=5000)
                time.sleep(0.35)
                break
        except Exception:
            continue

    for strategy, factory in selectors:
        try:
            loc = factory(page)
            if loc.count() <= 0 or not loc.is_visible():
                continue
            with page.expect_download(timeout=120000) as dl_info:
                loc.click(timeout=10000)
            download = dl_info.value
            download.save_as(str(dest))
            if dest.is_file() and dest.stat().st_size > 0:
                return dest, strategy
        except Exception:
            continue
    return None, ""


def _fetch_via_page_request(page: Any, url: str, dest: Path) -> Path | None:
    try:
        response = page.context.request.get(
            url,
            timeout=300_000,
            headers={"Accept": "video/mp4,*/*"},
        )
        if not response.ok:
            return None
        body = response.body()
        return _write_binary_payload(dest, body)
    except Exception:
        return None


def _collect_performance_media_urls(page: Any) -> list[str]:
    payload = page.evaluate(
        """() => {
            const urls = [];
            for (const entry of performance.getEntriesByType('resource')) {
                const name = String(entry.name || '');
                if (/\\.mp4|video|m3u8|mime_type=video/i.test(name)) {
                    urls.push(name);
                }
            }
            return Array.from(new Set(urls)).slice(0, 20);
        }"""
    )
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if item]


def verify_recovered_mp4(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    result: dict[str, Any] = {
        "path": str(target.resolve()) if target.is_file() else str(target),
        "exists": target.is_file(),
        "size_bytes": target.stat().st_size if target.is_file() else 0,
        "duration_seconds": None,
        "ffprobe_ok": False,
        "is_placeholder": True,
        "is_real_mp4": False,
    }
    if not target.is_file():
        return result
    size = target.stat().st_size
    result["is_placeholder"] = size <= PLACEHOLDER_MAX_BYTES
    duration, _audio, _notes = _probe_video_metadata(target)
    result["duration_seconds"] = duration
    result["ffprobe_ok"] = duration is not None and duration >= MIN_REAL_MP4_SECONDS
    result["is_real_mp4"] = (
        size >= MIN_REAL_MP4_BYTES
        and bool(result["ffprobe_ok"])
        and not result["is_placeholder"]
    )
    return result


def _download_via_runway_phase_i(
    page: Any,
    dest: Path,
    *,
    clip_index: int = 1,
    session_id: str = "",
) -> tuple[Path | None, list[str]]:
    from content_brain.execution.runway_phase_i_artifact_tracker import PhaseIArtifactTracker
    from content_brain.execution.runway_phase_i_cdp_download import (
        RunwayPhaseICdpDownloadConfig,
        RunwayPhaseICdpDownloader,
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    strategies: list[str] = []
    tracker = PhaseIArtifactTracker(page=page, project_id=session_id or "kling_recovery")
    card = tracker.assign_latest_video_card_for_clip(clip_index)
    if card is None:
        card = tracker.refresh_assigned_card_from_scan(clip_index)
    if card is None:
        return None, ["runway_artifact_card_missing"]

    downloader = RunwayPhaseICdpDownloader(
        download_dir=dest.parent,
        tracker=tracker,
        page=page,
        config=RunwayPhaseICdpDownloadConfig(
            session_id=session_id or "kling_recovery",
            fallback_to_ui_download=True,
        ),
    )
    attempt = downloader.download_clip(clip_index)
    strategies.append(f"runway_cdp:{attempt.strategy or 'none'}")
    strategies.extend([f"runway_note:{note}" for note in attempt.notes[:6]])

    candidate_paths: list[Path] = []
    if attempt.file_path:
        candidate_paths.append(Path(attempt.file_path))
    candidate_paths.extend(Path(item) for item in dest.parent.glob("runway_clip_*.mp4"))
    candidate_paths.append(dest)

    for candidate in candidate_paths:
        if not candidate.is_file() or candidate.stat().st_size <= 0:
            continue
        if candidate.resolve() != dest.resolve():
            shutil.copy2(candidate, dest)
        verify = verify_recovered_mp4(dest)
        if verify.get("is_real_mp4"):
            strategies.append("runway_cdp_real_mp4")
            return dest, strategies
    return None, strategies


def _download_output(
    page: Any,
    run_dir: Path,
    run_id: str,
    *,
    clip_index: int = 1,
    gate_context: Any | None = None,
) -> tuple[Path | None, list[str]]:
    from content_brain.execution.kling_real_mp4_download_extractor import poll_extract_real_kling_mp4

    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / "video.mp4"
    extracted = poll_extract_real_kling_mp4(
        page,
        dest,
        run_id=run_id,
        clip_index=clip_index,
        clip_dir=run_dir,
        recovery_mode=False,
        gate_context=gate_context,
    )
    if extracted.ok and extracted.output_path:
        return Path(extracted.output_path), list(extracted.attempted_methods)
    return None, list(extracted.attempted_methods)


def _probe_video_metadata(path: Path) -> tuple[float | None, bool | None, str]:
    try:
        import subprocess

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if probe.returncode != 0:
            return None, None, "ffprobe unavailable or failed — manual QA required for native audio"
        payload = json.loads(probe.stdout or "{}")
        duration = float((payload.get("format") or {}).get("duration") or 0) or 0.0
        streams = payload.get("streams") or []
        has_audio = any(str(s.get("codec_type") or "") == "audio" for s in streams)
        notes = "Native audio track detected via ffprobe" if has_audio else "No audio stream detected in downloaded file"
        return duration or None, has_audio, notes
    except Exception as exc:
        return None, None, f"metadata probe skipped: {exc}"


def run_kling_multishot_live(
    *,
    shot_1_prompt: str = BENCHMARK_SHOT_1,
    shot_2_prompt: str = BENCHMARK_SHOT_2,
    first_frame_path: str | Path | None = None,
    approve_generate: bool = False,
    approved_by: str = "",
    confirm_credit_spend: bool = False,
    cdp_url: str = DEFAULT_CDP_URL,
    map_path: Path | str | None = None,
    max_wait_minutes: int = 20,
    run_id: str | None = None,
    output_dir: str | Path | None = None,
) -> KlingMultishotLiveResult:
    if not str(shot_1_prompt or "").strip() or not str(shot_2_prompt or "").strip():
        raise ValueError("shot_1_prompt and shot_2_prompt are required")

    run_id = run_id or f"kling_ms_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    run_dir = Path(output_dir).resolve() if output_dir else OUTPUT_ROOT / run_id

    result = KlingMultishotLiveResult(
        ok=False,
        status=STATUS_PREPARED,
        run_id=run_id,
        dry_run_prepare=not approve_generate,
        generate_clicked=False,
        credits_spent=False,
        approved_by=None,
        approved_at=None,
        native_audio_notes="Audio ON in UI; native audio quality requires post-download probe",
    )

    ui_map = load_kling_ui_map(map_path=map_path)
    labels = dict(ui_map.get("labels") or {})
    checklist = KlingMultishotApprovalChecklist()

    playwright = None
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
            shot = _capture_screenshot(page, result, step_id, label)
            merged = detail if not shot else f"{detail}; screenshot={shot}"
            _record_step(result, step_id, label, "passed", merged)

        try:
            provider, model_detection = resolve_kling_3_pro_provider(page, entry("provider_kling_3_pro"))
        except RuntimeError as exc:
            return _fail(result, "01", "provider_kling_3_pro", f"Unstable/missing selector for provider_kling_3_pro: {exc}")
        result.locator_strategies["provider_kling_3_pro"] = provider.strategy
        checklist.model_already_selected = bool(model_detection.get("model_already_selected"))
        if checklist.model_already_selected:
            provider_text = str(model_detection.get("detected_text") or "Kling 3.0 Pro")
            step_detail = (
                f"strategy={provider.strategy}; model_already_selected=True; text={provider_text[:40]}"
            )
        else:
            provider_text = _read_locator_text(provider)
            if "kling 3" not in provider_text.lower():
                _safe_click(page, provider)
                time.sleep(0.35)
                page.keyboard.press("Escape")
                time.sleep(0.2)
                provider_text = _read_locator_text(provider)
            step_detail = f"strategy={provider.strategy}; text={provider_text[:40]}"
        checklist.provider_selected = provider_text or "Kling 3.0 Pro"
        step_pass("01", "provider_kling_3_pro", step_detail)

        multishot = _locate_or_fail(page, result, "02", "multishot_tab", entry("multishot_tab"))
        if multishot is None:
            return result
        checklist.multishot_selected = _multishot_already_selected(multishot)
        if not checklist.multishot_selected:
            _safe_click(page, multishot)
            time.sleep(0.5)
            checklist.multishot_selected = _multishot_already_selected(multishot) or True
        step_pass("02", "multishot_tab", f"strategy={multishot.strategy}; selected={checklist.multishot_selected}")

        audio = _locate_or_fail(page, result, "03", "audio_toggle_on", entry("audio_toggle_on"))
        if audio is None:
            return result
        audio_text = _read_locator_text(audio)
        checklist.audio_on = "on" in audio_text.lower()
        if not checklist.audio_on:
            return _fail(result, "03", "audio_toggle_on", f"Audio toggle not ON (read: {audio_text!r})")
        step_pass("03", "audio_toggle_on", f"{audio_text[:40]}; strategy={audio.strategy}")

        first_frame_entry = entry("first_frame_upload")
        first_frame_detected = try_locate_control(page, "first_frame_upload", first_frame_entry, timeout_ms=4000)
        if first_frame_path:
            upload_path = Path(first_frame_path).resolve()
            if not upload_path.is_file():
                return _fail(result, "04", "first_frame_upload", f"first_frame_path missing: {upload_path}")
            if first_frame_detected is None:
                return _fail(result, "04", "first_frame_upload", "first_frame_upload control not found")
            try:
                with page.expect_file_chooser(timeout=8000) as fc_info:
                    first_frame_detected.locator.click(timeout=8000)
                fc_info.value.set_files(str(upload_path))
            except Exception:
                page.locator('input[type="file"]').first.set_input_files(str(upload_path))
            checklist.first_frame_uploaded = True
            checklist.first_frame_path = str(upload_path)
            step_pass("04", "first_frame_upload", str(upload_path))
        elif first_frame_detected is not None:
            _record_step(result, "04", "first_frame_upload", "detected", f"strategy={first_frame_detected.strategy}")
        else:
            _record_step(result, "04", "first_frame_upload", "skipped", "no first_frame_path provided")

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
            return _fail(result, "05", "shot_1_duration_12s", f"Shot 1 not 12s (read: {shot1_text!r})")
        checklist.shot_1_duration_seconds = SHOT_1_DURATION_SECONDS
        step_pass("05", "shot_1_duration_12s", shot1_text)

        shot2_menu = _locate_or_fail(page, result, "06", "shot_2_duration_menu", entry("shot_2_duration_menu"))
        if shot2_menu is None:
            return result
        shot2_text = _read_locator_text(shot2_menu)
        if not _text_has_duration(shot2_text, SHOT_2_DURATION_SECONDS):
            _safe_click(page, shot2_menu)
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
            return _fail(result, "06", "shot_2_duration_3s", f"Shot 2 not 3s (read: {shot2_text!r})")
        checklist.shot_2_duration_seconds = SHOT_2_DURATION_SECONDS
        step_pass("06", "shot_2_duration_3s", shot2_text)

        checklist.shot_1_prompt_chars = len(shot_1_prompt.strip())
        checklist.shot_2_prompt_chars = len(shot_2_prompt.strip())
        for idx, (label, text) in enumerate(
            (("shot_1_prompt", shot_1_prompt), ("shot_2_prompt", shot_2_prompt)),
            start=7,
        ):
            located = _locate_or_fail(page, result, f"{idx:02d}", label, entry(label))
            if located is None:
                return result
            located.locator.click(timeout=8000)
            located.locator.fill(text.strip(), timeout=8000)
            if label == "shot_1_prompt":
                checklist.shot_1_prompt_filled = True
            else:
                checklist.shot_2_prompt_filled = True
            step_pass(f"{idx:02d}", label, f"{len(text.strip())} chars")

        generate = _locate_or_fail(page, result, "10", "generate_button", entry("generate_button"))
        if generate is None:
            return result

        result.approval_checklist = checklist.to_dict()
        approval_shot = _capture_screenshot(page, result, "10", "approval_checklist")
        _record_step(
            result,
            "10",
            "approval_checklist",
            "ready",
            json.dumps(checklist.to_dict(), ensure_ascii=False) + (f"; screenshot={approval_shot}" if approval_shot else ""),
        )

        if not checklist.all_ready():
            return _fail(result, "10", "approval_checklist", "Approval checklist incomplete — stopping safely")

        if not approve_generate:
            result.ok = True
            result.status = STATUS_AWAITING_APPROVAL
            _record_step(result, "10", "generate_button", "blocked", "awaiting explicit operator approval")
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "approval_checklist.json").write_text(
                json.dumps(checklist.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (run_dir / "live_run_prepare.json").write_text(
                json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return result

        if not approved_by.strip():
            return _fail(result, "10", "generate_button", "approve_generate requires --approved-by")
        if not confirm_credit_spend:
            return _fail(
                result,
                "10",
                "generate_button",
                "approve_generate requires --confirm-credit-spend",
            )

        approvals: dict[str, RunwayContinuityApprovalRecord] = grant_continuity_approval(
            control_key="generate_button",
            step_id="11_generate",
            approved_by=approved_by.strip(),
            reason="explicit operator approval — Kling multishot live",
        )
        if not can_execute_dangerous_action("generate_button", step_id="11_generate", approvals=approvals):
            return _fail(result, "11", "generate_button", "Approval gate rejected Generate execution")

        result.approved_by = approved_by.strip()
        result.approved_at = approvals["generate_button"].approved_at

        from content_brain.execution.runway_focus_dependency_probe import execute_generate_click_with_focus_probe

        probe = execute_generate_click_with_focus_probe(page, generate.locator)
        result.focus_probe = probe.to_dict()
        if probe.click_error:
            return _fail(result, "11", "generate_button", probe.click_error)
        result.generate_clicked = True
        result.credits_spent = True
        _record_step(
            result,
            "11",
            "generate_button",
            "clicked",
            (
                f"approved_by={result.approved_by}; "
                f"visibility={probe.before.get('visibility_state')}; "
                f"hasFocus={probe.before.get('has_focus')}; "
                f"focus_blocker={probe.focus_likely_blocker}; "
                f"click_ms={probe.click_duration_ms}"
            ),
        )
        _capture_screenshot(page, result, "11", "generate_clicked")

        complete, reason = _wait_for_generation_complete(page, max_wait_minutes=max_wait_minutes)
        if not complete:
            return _fail(result, "12", "generation_wait", f"Generation did not complete: {reason}")
        result.generation_completed = True
        _record_step(result, "12", "generation_wait", "passed", reason)
        _capture_screenshot(page, result, "12", "generation_complete")

        run_dir.mkdir(parents=True, exist_ok=True)
        downloaded, download_strategies = _download_output(page, run_dir, run_id, clip_index=1)
        result.download_strategies = list(download_strategies)
        if downloaded is None:
            result.generation_completed = True
            result.download_status = DOWNLOAD_STATUS_FAILED
            result.status = STATUS_DOWNLOAD_FAILED
            result.ok = False
            (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            return _fail(result, "13", "download", "Could not download MP4 output")
        result.download_path = str(downloaded.resolve())
        result.output_path = result.download_path
        result.download_status = DOWNLOAD_STATUS_PASSED
        _record_step(result, "13", "download", "passed", ";".join(download_strategies) or result.download_path)

        duration, audio_present, notes = _probe_video_metadata(downloaded)
        result.duration_seconds = duration
        result.audio_present = audio_present
        result.native_audio_notes = notes

        metadata = {
            "run_id": run_id,
            "approved_by": result.approved_by,
            "approved_at": result.approved_at,
            "shot_1_prompt": shot_1_prompt,
            "shot_2_prompt": shot_2_prompt,
            "generate_clicked": True,
            "output_path": result.output_path,
            "duration_seconds": duration,
            "audio_present": audio_present,
            "native_audio_notes": notes,
        }
        (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        ref = ROOT / "project_brain" / "kling_multishot_live_run_summary.json"
        if ref.is_file():
            shutil.copy2(ref, run_dir / "prepare_reference.json")

        result.ok = True
        result.status = STATUS_COMPLETED
        result.generation_completed = True
        result.download_status = DOWNLOAD_STATUS_PASSED
        result.dry_run_prepare = False
        (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return result

    except Exception as exc:
        result.ok = False
        result.status = STATUS_FAILED
        result.errors.append(str(exc))
        _record_step(result, "runtime", "live_engine", "failed", str(exc)[:300])
        return result
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def recover_kling_multishot_output(
    *,
    run_id: str,
    output_dir: str | Path,
    cdp_url: str = DEFAULT_CDP_URL,
    clip_index: int = 1,
) -> KlingMultishotLiveResult:
    """Recover/download an already-generated Kling output without clicking Generate."""
    run_dir = Path(output_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    result = KlingMultishotLiveResult(
        ok=False,
        status=STATUS_FAILED,
        run_id=run_id,
        dry_run_prepare=False,
        generate_clicked=False,
        credits_spent=False,
        generation_completed=False,
        download_status=DOWNLOAD_STATUS_PENDING,
        recovery_mode=True,
        approved_by=None,
        approved_at=None,
        native_audio_notes="Recovery mode — no new credits spent",
    )

    playwright = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        _record_step(result, "recover", "cdp", "passed", cdp_url)

        page = None
        for context in browser.contexts:
            for candidate in context.pages:
                if _is_runway_url(candidate.url):
                    page = candidate
                    break
            if page:
                break
        if page is None:
            return _fail(result, "recover", "runway_tab", "No Runway tab found in CDP browser")

        result.page_url = page.url
        ready, reason = _detect_output_ready(page)
        if not ready:
            return _fail(result, "recover", "output_detect", f"No ready output found for recovery: {reason}")
        _record_step(result, "recover", "output_detect", "passed", reason)
        result.generation_completed = True

        downloaded, download_strategies = _download_output(page, run_dir, run_id, clip_index=clip_index)
        result.download_strategies = list(download_strategies)
        if downloaded is None:
            result.download_status = DOWNLOAD_STATUS_FAILED
            result.status = STATUS_DOWNLOAD_FAILED
            (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            return _fail(result, "recover", "download", "Could not recover/download MP4 output")

        verify = verify_recovered_mp4(downloaded)
        if not verify.get("is_real_mp4"):
            result.download_status = DOWNLOAD_STATUS_FAILED
            result.status = STATUS_DOWNLOAD_FAILED
            result.ok = False
            detail = (
                f"Recovered file is not a real MP4 "
                f"(size={verify.get('size_bytes')}, duration={verify.get('duration_seconds')})"
            )
            (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            return _fail(result, "recover", "download_verify", detail)

        result.download_path = str(downloaded.resolve())
        result.output_path = result.download_path
        result.download_status = DOWNLOAD_STATUS_PASSED
        duration, audio_present, notes = _probe_video_metadata(downloaded)
        result.duration_seconds = duration
        result.audio_present = audio_present
        result.native_audio_notes = notes
        _record_step(result, "recover", "download", "passed", ";".join(download_strategies) or result.download_path)

        metadata = {
            "run_id": run_id,
            "clip_index": clip_index,
            "recovery_mode": True,
            "generate_clicked": False,
            "credits_spent": False,
            "output_path": result.output_path,
            "duration_seconds": duration,
            "audio_present": audio_present,
            "native_audio_notes": notes,
            "legacy_note": "Recovered without Generate click",
        }
        (run_dir / "recovery_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        result.ok = True
        result.status = STATUS_COMPLETED
        (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return result
    except Exception as exc:
        result.ok = False
        result.status = STATUS_FAILED
        result.errors.append(str(exc))
        _record_step(result, "recover", "live_engine", "failed", str(exc)[:300])
        return result
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


__all__ = [
    "BENCHMARK_SHOT_1",
    "BENCHMARK_SHOT_2",
    "DOWNLOAD_STATUS_FAILED",
    "DOWNLOAD_STATUS_PASSED",
    "DOWNLOAD_STATUS_PENDING",
    "KlingMultishotApprovalChecklist",
    "KlingMultishotLiveResult",
    "OUTPUT_ROOT",
    "STATUS_DOWNLOAD_FAILED",
    "recover_kling_multishot_output",
    "run_kling_multishot_live",
    "verify_recovered_mp4",
]
