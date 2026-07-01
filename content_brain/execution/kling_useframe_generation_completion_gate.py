"""Use Frame generation completion gate — wait for new artifact before recovery/download."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.runway_phase_i_artifact_tracker import PhaseIArtifactTracker

GATE_VERSION = "kling_useframe_generation_completion_gate_v1"
GATE_POLL_INTERVAL_SECONDS = 5
GATE_DEFAULT_MAX_WAIT_SECONDS = 1200

QUEUE_WARNING_PATTERNS = (
    "please wait for your last generation",
    "wait for your last generation",
    "wait for your last generation to complete",
)

GENERATION_ACTIVE_PATTERNS = (
    "generating",
    "processing",
    "in progress",
    "creating your",
)


@dataclass
class GenerationCompletionGateContext:
    require_new_artifact: bool = False
    generate_clicked_at: str = ""
    prior_artifact_signatures: list[dict[str, Any]] = field(default_factory=list)
    baseline_video_card_count: int = 0
    baseline_card_fingerprints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": GATE_VERSION,
            "require_new_artifact": self.require_new_artifact,
            "generate_clicked_at": self.generate_clicked_at,
            "prior_artifact_signatures": list(self.prior_artifact_signatures),
            "baseline_video_card_count": self.baseline_video_card_count,
            "baseline_card_fingerprints": list(self.baseline_card_fingerprints),
        }


@dataclass
class GenerationCompletionGateResult:
    gate_passed: bool = False
    detail: str = ""
    queue_warning_visible: bool = False
    generation_active: bool = False
    new_artifact_confirmed: bool = False
    confirmed_artifact: dict[str, Any] = field(default_factory=dict)
    poll_elapsed_seconds: float = 0.0
    poll_attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": GATE_VERSION,
            "gate_passed": self.gate_passed,
            "detail": self.detail,
            "queue_warning_visible": self.queue_warning_visible,
            "generation_active": self.generation_active,
            "new_artifact_confirmed": self.new_artifact_confirmed,
            "confirmed_artifact": dict(self.confirmed_artifact),
            "poll_elapsed_seconds": self.poll_elapsed_seconds,
            "poll_attempts": list(self.poll_attempts),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_url(url: str) -> str:
    cleaned = str(url or "").strip()
    if "?" in cleaned:
        cleaned = cleaned.split("?", 1)[0]
    return cleaned.lower()


def _primary_media_url(signature: dict[str, Any]) -> str:
    urls = signature.get("media_urls") or []
    if urls:
        return _normalize_url(str(urls[0]))
    return _normalize_url(str(signature.get("media_src") or ""))


def sha256_file(path: str | Path) -> str:
    target = Path(path)
    if not target.is_file():
        return ""
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_signature_from_card(raw: dict[str, Any], *, captured_at: str | None = None) -> dict[str, Any]:
    media_urls = [str(url).strip() for url in (raw.get("mediaUrls") or raw.get("media_urls") or []) if str(url).strip()]
    media_src = str(raw.get("mediaSrc") or raw.get("media_src") or "").strip()
    if media_src and media_src not in media_urls:
        media_urls.insert(0, media_src)
    return {
        "card_fingerprint": str(raw.get("cardFingerprint") or raw.get("card_fingerprint") or ""),
        "card_index": int(raw.get("cardIndex") or raw.get("card_index") or -1),
        "card_prompt_text": str(raw.get("cardPromptText") or raw.get("card_prompt_text") or "")[:200],
        "media_src": media_src,
        "media_urls": media_urls,
        "file_hash": str(raw.get("file_hash") or ""),
        "captured_at": captured_at or _now_iso(),
    }


def capture_artifact_signatures(page: Any, *, run_id: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tracker = PhaseIArtifactTracker(page=page, project_id=run_id or "kling_gate")
    cards = tracker.scan_artifact_cards()
    video_cards = [
        card
        for card in cards
        if str(card.get("cardType") or "") == "video"
        and str(card.get("mediaSrc") or "").strip()
    ]
    signatures = [artifact_signature_from_card(card) for card in video_cards]
    meta = {
        "card_count": len(cards),
        "video_card_count": len(video_cards),
        "fingerprints": [sig.get("card_fingerprint") for sig in signatures if sig.get("card_fingerprint")],
        "captured_at": _now_iso(),
    }
    return signatures, meta


def build_prior_artifact_signatures_from_clip(clip_dir: Path) -> list[dict[str, Any]]:
    signatures: list[dict[str, Any]] = []
    report_path = clip_dir / "mp4_extract_report.json"
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            selected = dict((report.get("card_selection") or {}).get("selected_card") or {})
            if selected:
                sig = artifact_signature_from_card(selected)
                video_path = clip_dir / "video.mp4"
                if video_path.is_file():
                    sig["file_hash"] = sha256_file(video_path)
                signatures.append(sig)
        except (OSError, json.JSONDecodeError):
            pass
    video_path = clip_dir / "video.mp4"
    if video_path.is_file():
        file_hash = sha256_file(video_path)
        if not any(sig.get("file_hash") == file_hash for sig in signatures):
            signatures.append(
                {
                    "card_fingerprint": "",
                    "card_index": -1,
                    "media_src": "",
                    "media_urls": [],
                    "file_hash": file_hash,
                    "captured_at": _now_iso(),
                    "source": "clip_video_file",
                }
            )
    return signatures


def detect_queue_warning_visible(page: Any) -> tuple[bool, str]:
    try:
        body_text = str(page.evaluate("() => document.body ? document.body.innerText : ''") or "").lower()
        for pattern in QUEUE_WARNING_PATTERNS:
            if pattern in body_text:
                return True, pattern
    except Exception:
        pass
    try:
        overlays = page.locator("li, [role='alert'], [role='status']")
        for idx in range(min(overlays.count(), 12)):
            text = str(overlays.nth(idx).inner_text() or "").lower()
            for pattern in QUEUE_WARNING_PATTERNS:
                if pattern in text:
                    return True, pattern
    except Exception:
        pass
    return False, ""


def detect_generation_active(page: Any) -> tuple[bool, str]:
    queue_visible, queue_reason = detect_queue_warning_visible(page)
    if queue_visible:
        return True, f"queue_warning:{queue_reason}"
    try:
        stop_btn = page.get_by_role("button", name=re.compile(r"stop|cancel generation", re.I))
        if stop_btn.count() > 0 and stop_btn.first.is_visible():
            return True, "stop_button_visible"
    except Exception:
        pass
    try:
        body_text = str(page.evaluate("() => document.body ? document.body.innerText : ''") or "").lower()
        for pattern in GENERATION_ACTIVE_PATTERNS:
            if pattern in body_text and "please wait for your last generation" in body_text:
                return True, f"body:{pattern}"
    except Exception:
        pass
    try:
        progress = page.locator('[role="progressbar"], [aria-busy="true"], [data-testid*="progress"]')
        if progress.count() > 0:
            for idx in range(min(progress.count(), 4)):
                if progress.nth(idx).is_visible():
                    return True, "progress_indicator_visible"
    except Exception:
        pass
    return False, ""


def is_duplicate_artifact(candidate: dict[str, Any], prior: list[dict[str, Any]]) -> tuple[bool, str]:
    if not prior:
        return False, ""
    cand_fp = str(candidate.get("card_fingerprint") or "")
    cand_url = _primary_media_url(candidate)
    cand_hash = str(candidate.get("file_hash") or "")
    for prior_sig in prior:
        prior_fp = str(prior_sig.get("card_fingerprint") or "")
        prior_url = _primary_media_url(prior_sig)
        prior_hash = str(prior_sig.get("file_hash") or "")
        if cand_fp and prior_fp and cand_fp == prior_fp:
            return True, "same_card_fingerprint"
        if cand_url and prior_url and cand_url == prior_url:
            return True, "same_media_url"
        if cand_hash and prior_hash and cand_hash == prior_hash:
            return True, "same_file_hash"
    return False, ""


def _video_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        card
        for card in cards
        if str(card.get("cardType") or "") == "video"
        and str(card.get("mediaSrc") or "").strip()
    ]


def find_new_artifact_candidate(
    *,
    cards: list[dict[str, Any]],
    prior_artifacts: list[dict[str, Any]],
    baseline_video_card_count: int,
    baseline_fingerprints: list[str],
    generate_clicked_at: str = "",
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    video_cards = _video_cards(cards)
    meta: dict[str, Any] = {
        "video_card_count": len(video_cards),
        "baseline_video_card_count": baseline_video_card_count,
        "baseline_fingerprints": list(baseline_fingerprints),
        "rejected_duplicates": [],
        "selection_reason": "",
    }
    if len(video_cards) > baseline_video_card_count:
        meta["selection_reason"] = "video_card_count_increased"
    ranked = sorted(
        video_cards,
        key=lambda card: float(card.get("cardBottom") or 0),
        reverse=True,
    )
    for card in ranked:
        sig = artifact_signature_from_card(card)
        duplicate, reason = is_duplicate_artifact(sig, prior_artifacts)
        if duplicate:
            meta["rejected_duplicates"].append(
                {"card_fingerprint": sig.get("card_fingerprint"), "reason": reason}
            )
            continue
        fp = str(sig.get("card_fingerprint") or "")
        if fp and fp in baseline_fingerprints and len(video_cards) <= baseline_video_card_count:
            meta["rejected_duplicates"].append(
                {"card_fingerprint": fp, "reason": "baseline_fingerprint_no_count_increase"}
            )
            continue
        meta["selection_reason"] = meta["selection_reason"] or "new_non_duplicate_card"
        return sig, meta
    return None, meta


def recovery_blocked_by_gate(page: Any, gate: GenerationCompletionGateContext | None) -> tuple[bool, str]:
    if gate is None or not gate.require_new_artifact:
        return False, ""
    queue_visible, queue_reason = detect_queue_warning_visible(page)
    if queue_visible:
        return True, f"queue_warning_visible:{queue_reason}"
    generation_active, active_reason = detect_generation_active(page)
    if generation_active:
        return True, f"generation_active:{active_reason}"
    cards = PhaseIArtifactTracker(page=page, project_id="kling_gate").scan_artifact_cards()
    candidate, _meta = find_new_artifact_candidate(
        cards=cards,
        prior_artifacts=gate.prior_artifact_signatures,
        baseline_video_card_count=gate.baseline_video_card_count,
        baseline_fingerprints=gate.baseline_card_fingerprints,
        generate_clicked_at=gate.generate_clicked_at,
    )
    if candidate is None:
        return True, "new_artifact_not_confirmed"
    return False, ""


def wait_for_generation_completion_gate(
    page: Any,
    *,
    generate_clicked_at: str,
    prior_artifact_signatures: list[dict[str, Any]],
    baseline_video_card_count: int = 0,
    baseline_card_fingerprints: list[str] | None = None,
    max_wait_seconds: int = GATE_DEFAULT_MAX_WAIT_SECONDS,
    poll_interval_seconds: int = GATE_POLL_INTERVAL_SECONDS,
) -> GenerationCompletionGateResult:
    """Wait until queue clears and a new non-duplicate artifact card exists."""
    started = time.monotonic()
    deadline = started + max(1, int(max_wait_seconds))
    baseline_fps = list(baseline_card_fingerprints or [])
    result = GenerationCompletionGateResult()
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        ts = _now_iso()
        queue_visible, queue_reason = detect_queue_warning_visible(page)
        generation_active, active_reason = detect_generation_active(page)
        cards = PhaseIArtifactTracker(page=page, project_id="kling_gate").scan_artifact_cards()
        candidate, selection_meta = find_new_artifact_candidate(
            cards=cards,
            prior_artifacts=prior_artifact_signatures,
            baseline_video_card_count=baseline_video_card_count,
            baseline_fingerprints=baseline_fps,
            generate_clicked_at=generate_clicked_at,
        )
        attempt_detail = {
            "attempt": attempt,
            "timestamp": ts,
            "queue_warning_visible": queue_visible,
            "queue_reason": queue_reason,
            "generation_active": generation_active,
            "active_reason": active_reason,
            "video_card_count": selection_meta.get("video_card_count"),
            "new_artifact_found": candidate is not None,
            "selection_meta": selection_meta,
        }
        result.poll_attempts.append(attempt_detail)

        if queue_visible or generation_active:
            result.queue_warning_visible = queue_visible
            result.generation_active = generation_active
            time.sleep(min(float(poll_interval_seconds), max(0.0, deadline - time.monotonic())))
            continue

        if candidate is not None:
            result.gate_passed = True
            result.new_artifact_confirmed = True
            result.confirmed_artifact = dict(candidate)
            result.detail = (
                f"new_artifact_confirmed:{selection_meta.get('selection_reason')};"
                f"fp={candidate.get('card_fingerprint', '')[:40]}"
            )
            result.poll_elapsed_seconds = round(time.monotonic() - started, 2)
            return result

        time.sleep(min(float(poll_interval_seconds), max(0.0, deadline - time.monotonic())))

    result.poll_elapsed_seconds = round(time.monotonic() - started, 2)
    result.detail = (
        f"timeout:queue={result.queue_warning_visible};"
        f"active={result.generation_active};new_artifact={result.new_artifact_confirmed}"
    )
    return result


__all__ = [
    "GATE_DEFAULT_MAX_WAIT_SECONDS",
    "GATE_POLL_INTERVAL_SECONDS",
    "GATE_VERSION",
    "GenerationCompletionGateContext",
    "GenerationCompletionGateResult",
    "artifact_signature_from_card",
    "build_prior_artifact_signatures_from_clip",
    "capture_artifact_signatures",
    "detect_generation_active",
    "detect_queue_warning_visible",
    "find_new_artifact_candidate",
    "is_duplicate_artifact",
    "recovery_blocked_by_gate",
    "sha256_file",
    "wait_for_generation_completion_gate",
]
