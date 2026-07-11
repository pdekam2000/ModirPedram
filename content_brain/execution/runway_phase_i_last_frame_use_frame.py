"""
Phase I — generic last-frame Use Frame continuity (clip N > 1 uses last frame of clip N-1).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from content_brain.execution.runway_phase_i_artifact_tracker import (
    PhaseIArtifactTracker,
)
from content_brain.execution.runway_phase_i_strict_completion_gate import (
    evaluate_strict_clip_completion,
)

if TYPE_CHECKING:
    from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAST_FRAME_USE_FRAME_DIAGNOSTICS = (
    ROOT / "project_brain" / "runway_phase_i_last_frame_use_frame_diagnostics.json"
)

USE_FRAME_SOURCE_LAST_SAFE = "last_safe_frame"
USE_FRAME_SOURCE_FIRST_FRAME_FALLBACK = "first_frame_fallback"
SEEK_STRATEGY_DURATION_MINUS_OFFSET = "duration_minus_0.7s"
SEEK_STRATEGY_TIMELINE_PERCENT = "timeline_90_95_percent"
SEEK_STRATEGY_SIMULATE = "simulate"

_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s", re.I)


@dataclass
class LastFrameUseFrameResult:
    target_clip_index: int = 0
    source_clip_index: int = 0
    use_frame_source_clip: int = 0
    use_frame_source: str = ""
    previous_clip_seeked_to_last_frame: bool = False
    seek_time_used: float = 0.0
    seek_strategy: str = ""
    playback_seek_method: str = ""
    generation_controls_avoided: bool = True
    video_duration_seconds: float = 0.0
    preview_not_first_frame: bool = False
    strict_previous_complete: bool = False
    scoped_card_fingerprint: str = ""
    use_frame_clicked: bool = False
    first_frame_fallback_used: bool = False
    fallback_requires_operator: bool = False
    notes: list[str] = field(default_factory=list)

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "use_frame_source_clip": self.use_frame_source_clip,
            "use_frame_source": self.use_frame_source,
            "previous_clip_seeked_to_last_frame": self.previous_clip_seeked_to_last_frame,
            "seek_time_used": self.seek_time_used,
            "seek_strategy": self.seek_strategy,
            "playback_seek_method": self.playback_seek_method,
            "generation_controls_avoided": self.generation_controls_avoided,
            "video_duration_seconds": self.video_duration_seconds,
            "preview_not_first_frame": self.preview_not_first_frame,
            "strict_previous_complete": self.strict_previous_complete,
            "scoped_card_fingerprint": self.scoped_card_fingerprint,
            "use_frame_clicked": self.use_frame_clicked,
            "first_frame_fallback_used": self.first_frame_fallback_used,
            "fallback_requires_operator": self.fallback_requires_operator,
            "notes": list(self.notes),
        }


def parse_duration_seconds(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        return seconds if seconds > 0 else None
    text = str(value).strip()
    if not text:
        return None
    match = _DURATION_RE.search(text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    try:
        seconds = float(text)
        return seconds if seconds > 0 else None
    except ValueError:
        return None


def compute_last_safe_seek_seconds(
    duration_seconds: float | None,
    *,
    default_duration: float = 10.0,
) -> tuple[float, str]:
    """Return seek time and strategy label."""
    duration = duration_seconds if duration_seconds and duration_seconds > 0 else default_duration
    if duration >= 9.0:
        seek = min(duration - 0.7, max(9.0, duration * 0.92))
        return round(seek, 2), SEEK_STRATEGY_DURATION_MINUS_OFFSET
    if duration >= 4.0:
        seek = min(duration - 0.5, max(4.3, duration * 0.9))
        return round(seek, 2), SEEK_STRATEGY_DURATION_MINUS_OFFSET
    seek = max(0.1, duration - 0.7)
    return round(seek, 2), SEEK_STRATEGY_DURATION_MINUS_OFFSET


def last_frame_seek_eval_script() -> str:
    return """({ cardFingerprint, seekSeconds, timelinePercent }) => {
        const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
        const buildFp = (root) => {
            const r = root.getBoundingClientRect();
            const t = normalize(root.innerText || root.textContent || '');
            const video = root.querySelector('video');
            const img = root.querySelector('img, canvas, picture');
            const cardType = video ? 'video' : (img ? 'image' : 'unknown');
            return [
                Math.round(r.left + window.scrollX),
                Math.round(r.top + window.scrollY),
                Math.round(r.width),
                Math.round(r.height),
                cardType,
                t.slice(0, 120),
            ].join('|');
        };
        const actionButtons = Array.from(document.querySelectorAll(
            'button[aria-label=\"Actions\"], [aria-label*=\"Actions\"]'
        ));
        let targetCard = null;
        for (const btn of actionButtons) {
            let card = btn;
            for (let depth = 0; depth < 12 && card; depth++) {
                if (card.querySelector && card.querySelector('video')) break;
                card = card.parentElement;
            }
            if (!card) card = btn.parentElement || btn;
            if (buildFp(card) === cardFingerprint) {
                targetCard = card;
                break;
            }
        }
        if (!targetCard) {
            return { ok: false, error: 'card_not_found' };
        }
        targetCard.scrollIntoView({ block: 'center', inline: 'nearest' });
        const video = targetCard.querySelector('video');
        if (!video) {
            return { ok: false, error: 'no_video_in_card' };
        }
        const duration = Number(video.duration) || 0;
        let strategy = 'currentTime';
        let track = null;
        const beforeTime = Number(video.currentTime) || 0;
        const waitForSeek = (targetTime) => new Promise((resolve) => {
            let settled = false;
            const finish = (payload) => {
                if (settled) return;
                settled = true;
                video.removeEventListener('seeked', onSeeked);
                clearTimeout(timer);
                resolve(payload);
            };
            const onSeeked = () => {
                const afterTime = Number(video.currentTime) || 0;
                finish({
                    ok: true,
                    strategy,
                    seekMethod: track ? 'timeline_range_in_card' : 'html_video_currentTime',
                    duration,
                    beforeTime,
                    afterTime,
                    previewNotFirstFrame: afterTime > 0.35 || (duration > 0 && afterTime >= duration * 0.85),
                    paused: video.paused,
                    pageButtonsClicked: false,
                    generationControlClickAttempted: false,
                });
            };
            const timer = setTimeout(() => {
                const afterTime = Number(video.currentTime) || 0;
                const closeEnough = Math.abs(afterTime - targetTime) <= 0.35
                    || afterTime >= targetTime * 0.85;
                finish({
                    ok: closeEnough,
                    strategy,
                    seekMethod: track ? 'timeline_range_in_card' : 'html_video_currentTime',
                    duration,
                    beforeTime,
                    afterTime,
                    previewNotFirstFrame: afterTime > 0.35 || (duration > 0 && afterTime >= duration * 0.85),
                    paused: video.paused,
                    pageButtonsClicked: false,
                    generationControlClickAttempted: false,
                    error: closeEnough ? '' : 'seek_timeout',
                });
            }, 2500);
            video.addEventListener('seeked', onSeeked);
            try {
                video.pause();
            } catch (_) {}
            try {
                video.currentTime = targetTime;
            } catch (err) {
                finish({ ok: false, error: 'seek_failed', detail: String(err) });
            }
        });
        if (duration > 0 && seekSeconds > 0) {
            const target = Math.min(Math.max(0, seekSeconds), Math.max(0, duration - 0.05));
            return waitForSeek(target);
        }
        if (timelinePercent > 0) {
            strategy = 'timeline_percent';
            track = targetCard.querySelector(
                'input[type=\"range\"], [role=\"slider\"], [class*=\"scrub\" i], [class*=\"timeline\" i]'
            );
            if (track) {
                const rect = track.getBoundingClientRect();
                const x = rect.left + rect.width * timelinePercent;
                const y = rect.top + rect.height / 2;
                track.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: x, clientY: y }));
                track.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: x, clientY: y }));
                track.click();
                const target = duration > 0 ? duration * timelinePercent : 0;
                return waitForSeek(target);
            }
            if (duration > 0) {
                return waitForSeek(duration * timelinePercent);
            }
        }
        return {
            ok: true,
            strategy,
            seekMethod: 'html_video_currentTime',
            duration,
            beforeTime,
            afterTime: beforeTime,
            previewNotFirstFrame: beforeTime > 0.35,
            paused: video.paused,
            pageButtonsClicked: false,
            generationControlClickAttempted: false,
        };
    }"""


def write_last_frame_use_frame_diagnostics(
    result: LastFrameUseFrameResult,
    *,
    context: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "context": context,
        "target_clip_index": result.target_clip_index,
        "source_clip_index": result.source_clip_index,
        "result": result.to_report_dict(),
        "extra": dict(extra or {}),
    }
    DEFAULT_LAST_FRAME_USE_FRAME_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_LAST_FRAME_USE_FRAME_DIAGNOSTICS.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def prepare_last_frame_use_frame_for_clip(
    navigator: MappedRunwayUINavigator,
    target_clip_index: int,
    *,
    allow_first_frame_fallback: bool = False,
) -> LastFrameUseFrameResult:
    """
    Generic: for target clip N (N>1), seek clip N-1 video to last safe frame then Use Frame.
    """
    target = max(2, int(target_clip_index))
    previous = target - 1
    result = LastFrameUseFrameResult(
        target_clip_index=target,
        source_clip_index=previous,
        use_frame_source_clip=previous,
    )

    strict = evaluate_strict_clip_completion(
        navigator,
        previous,
        test_override=getattr(navigator, "_strict_completion_test_override", None),
    )
    result.strict_previous_complete = bool(strict.complete)
    if not strict.complete:
        result.notes.append(f"previous_clip_not_complete:{strict.reason}")
        write_last_frame_use_frame_diagnostics(result, context="previous_not_complete")
        return result

    navigator.ensure_clip_video_card_assigned(previous)
    tracker = navigator.phase_i_artifact_tracker()
    source_role = PhaseIArtifactTracker.clip_video_role(previous)
    card = tracker.get_assigned(source_role)
    if card is None or not card.card_fingerprint:
        card = tracker.assign_new_card(source_role, prefer_type="video")
    if card is None or not card.card_fingerprint:
        result.notes.append("no_assigned_previous_clip_card")
        write_last_frame_use_frame_diagnostics(result, context="no_card")
        return result

    from content_brain.execution.runway_phase_i_strict_completion_gate import (
        card_text_matches_clip_index,
    )

    clip_count = int(getattr(navigator, "_phase_i_clip_count", 3) or 3)
    if not navigator.simulate:
        cards = tracker.scan_artifact_cards()
        raw_card = next(
            (
                item
                for item in cards
                if str(item.get("cardFingerprint") or "") == card.card_fingerprint
            ),
            {
                "cardFingerprint": card.card_fingerprint,
                "cardPromptText": card.card_prompt_text,
                "cardText": card.card_prompt_text,
            },
        )
        if not card_text_matches_clip_index(raw_card, previous, clip_count=clip_count):
            tracker.assignments.pop(source_role, None)
            refreshed = navigator.ensure_clip_video_card_assigned(previous)
            if refreshed is None or not refreshed.card_fingerprint:
                result.notes.append(f"source_clip_{previous}_card_marker_mismatch")
                write_last_frame_use_frame_diagnostics(result, context="source_card_marker_mismatch")
                return result
            card = refreshed
            raw_card = next(
                (
                    item
                    for item in tracker.scan_artifact_cards()
                    if str(item.get("cardFingerprint") or "") == card.card_fingerprint
                ),
                {
                    "cardFingerprint": card.card_fingerprint,
                    "cardPromptText": card.card_prompt_text,
                    "cardText": card.card_prompt_text,
                },
            )
            if not card_text_matches_clip_index(raw_card, previous, clip_count=clip_count):
                result.notes.append(f"source_clip_{previous}_card_still_mismatched_after_refresh")
                write_last_frame_use_frame_diagnostics(result, context="source_card_marker_mismatch")
                return result

    result.scoped_card_fingerprint = card.card_fingerprint
    tracker.ensure_starter_not_used_for_clip_ops(target)

    duration_seconds = _resolve_video_duration_seconds(navigator)
    seek_seconds, seek_strategy = compute_last_safe_seek_seconds(duration_seconds)
    result.video_duration_seconds = float(duration_seconds or 10.0)
    result.seek_strategy = seek_strategy

    if navigator.simulate:
        result.seek_time_used = seek_seconds
        result.previous_clip_seeked_to_last_frame = True
        result.preview_not_first_frame = True
        result.seek_strategy = SEEK_STRATEGY_SIMULATE
        result.playback_seek_method = "simulate"
        result.generation_controls_avoided = True
        result.notes.append("simulate_last_frame_seek")
    else:
        from content_brain.execution.runway_phase_i_video_playback_controls import (
            audit_card_playback_controls,
            write_playback_controls_diagnostics,
        )

        controls_audit = audit_card_playback_controls(
            navigator,
            clip_index=previous,
            card_fingerprint=card.card_fingerprint,
        )
        seek_payload = _seek_video_in_card(
            navigator,
            card_fingerprint=card.card_fingerprint,
            seek_seconds=seek_seconds,
            timeline_percent=0.92,
        )
        if not seek_payload.get("ok"):
            timeline_payload = _seek_video_in_card(
                navigator,
                card_fingerprint=card.card_fingerprint,
                seek_seconds=0.0,
                timeline_percent=0.93,
            )
            seek_payload = timeline_payload
            result.seek_strategy = SEEK_STRATEGY_TIMELINE_PERCENT
        result.playback_seek_method = str(seek_payload.get("seekMethod") or "html_video_currentTime")
        result.generation_controls_avoided = not bool(
            seek_payload.get("generationControlClickAttempted")
        )
        result.seek_time_used = float(seek_payload.get("afterTime") or seek_seconds)
        result.previous_clip_seeked_to_last_frame = bool(seek_payload.get("ok"))
        result.preview_not_first_frame = bool(seek_payload.get("previewNotFirstFrame"))
        if not seek_payload.get("ok"):
            result.notes.append(f"seek_failed:{seek_payload.get('error')}")
        elif not result.preview_not_first_frame and seek_seconds >= 4.0:
            retry_payload = _seek_video_in_card(
                navigator,
                card_fingerprint=card.card_fingerprint,
                seek_seconds=seek_seconds,
                timeline_percent=0.93,
            )
            if retry_payload.get("ok"):
                result.seek_strategy = SEEK_STRATEGY_TIMELINE_PERCENT
                result.playback_seek_method = str(
                    retry_payload.get("seekMethod") or result.playback_seek_method
                )
                result.seek_time_used = float(retry_payload.get("afterTime") or seek_seconds)
                result.previous_clip_seeked_to_last_frame = True
                result.preview_not_first_frame = bool(retry_payload.get("previewNotFirstFrame"))
            if not result.preview_not_first_frame:
                result.notes.append("seek_completed_but_preview_still_first_frame")
        write_playback_controls_diagnostics(
            controls_audit,
            seek_result=seek_payload,
            context=f"clip_{target}_use_frame",
        )

    if not result.previous_clip_seeked_to_last_frame:
        if allow_first_frame_fallback:
            result.first_frame_fallback_used = True
            result.use_frame_source = USE_FRAME_SOURCE_FIRST_FRAME_FALLBACK
            result.fallback_requires_operator = True
            result.notes.append("first_frame_fallback_requires_operator")
        else:
            result.notes.append("last_frame_seek_failed_no_fallback")
            write_last_frame_use_frame_diagnostics(result, context="seek_failed")
            return result
    else:
        result.use_frame_source = USE_FRAME_SOURCE_LAST_SAFE

    if not navigator.simulate:
        import time as _time

        tracker.refresh_assigned_card_from_scan(previous)
        _time.sleep(0.85)

    clicked = navigator.click_use_frame_for_next_clip(target)
    result.use_frame_clicked = clicked
    if not clicked:
        result.notes.append("use_frame_in_card_click_failed_no_global_fallback")
        write_last_frame_use_frame_diagnostics(result, context="use_frame_click_failed")
        return result

    write_last_frame_use_frame_diagnostics(
        result,
        context="use_frame_prepared",
        extra={"allow_first_frame_fallback": allow_first_frame_fallback},
    )
    return result


def _resolve_video_duration_seconds(navigator: MappedRunwayUINavigator) -> float | None:
    state = getattr(navigator, "last_video_settings", None)
    if state is not None:
        parsed = parse_duration_seconds(getattr(state, "detected_duration", ""))
        if parsed:
            return parsed
    try:
        row = navigator.read_toolbar_chip_row()
        parsed = parse_duration_seconds(row.get("duration"))
        if parsed:
            return parsed
    except Exception:
        pass
    return 10.0


def _seek_video_in_card(
    navigator: MappedRunwayUINavigator,
    *,
    card_fingerprint: str,
    seek_seconds: float,
    timeline_percent: float,
) -> dict[str, Any]:
    page = navigator.page
    if page is None:
        return {"ok": False, "error": "no_page"}
    try:
        payload = page.evaluate(
            last_frame_seek_eval_script(),
            {
                "cardFingerprint": card_fingerprint,
                "seekSeconds": seek_seconds,
                "timelinePercent": timeline_percent,
            },
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return payload if isinstance(payload, dict) else {"ok": False, "error": "invalid_payload"}


__all__ = [
    "DEFAULT_LAST_FRAME_USE_FRAME_DIAGNOSTICS",
    "LastFrameUseFrameResult",
    "compute_last_safe_seek_seconds",
    "last_frame_seek_eval_script",
    "parse_duration_seconds",
    "prepare_last_frame_use_frame_for_clip",
    "write_last_frame_use_frame_diagnostics",
]
