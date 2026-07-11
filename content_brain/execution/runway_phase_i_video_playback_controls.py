"""
Phase I — video playback control mapping for last-frame seek (artifact card scoped).

Last-frame seek uses HTMLVideoElement APIs inside the assigned card. It does not click
composer Generate / Stop / Cancel generation controls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAYBACK_CONTROLS_DIAGNOSTICS = (
    ROOT / "project_brain" / "runway_phase_i_video_playback_controls_diagnostics.json"
)

# Methods used by last-frame seek (safe — scoped to card <video> or in-card scrubber)
SEEK_METHOD_HTML_VIDEO_CURRENT_TIME = "html_video_currentTime"
SEEK_METHOD_TIMELINE_RANGE_IN_CARD = "timeline_range_in_card"
SEEK_METHOD_TIMELINE_VIDEO_PERCENT = "timeline_video_currentTime_percent"
SEEK_METHOD_SIMULATE = "simulate"

# Labels that indicate generation abort — must never be clicked during playback seek
GENERATION_ABORT_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"cancel", re.I),
    re.compile(r"stop", re.I),
    re.compile(r"abort", re.I),
)

GENERATION_ABORT_CONTEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"generat", re.I),
    re.compile(r"render", re.I),
    re.compile(r"queue", re.I),
)

# Playback-safe: API-only pause on <video>, not composer transport labeled Stop/Cancel
PLAYBACK_SAFE_APIS: tuple[str, ...] = (
    "HTMLVideoElement.currentTime",
    "HTMLVideoElement.pause",
)


@dataclass
class CardPlaybackControlsAudit:
    clip_index: int = 0
    card_fingerprint: str = ""
    video_element_present: bool = False
    video_duration: float = 0.0
    video_paused: bool = False
    in_card_playback_buttons: list[str] = field(default_factory=list)
    in_card_generation_abort_buttons: list[str] = field(default_factory=list)
    global_generation_abort_visible: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "card_fingerprint": self.card_fingerprint,
            "video_element_present": self.video_element_present,
            "video_duration": self.video_duration,
            "video_paused": self.video_paused,
            "in_card_playback_buttons": list(self.in_card_playback_buttons),
            "in_card_generation_abort_buttons": list(self.in_card_generation_abort_buttons),
            "global_generation_abort_visible": list(self.global_generation_abort_visible),
            "notes": list(self.notes),
        }


def is_generation_abort_button_label(label: str) -> bool:
    text = str(label or "").strip()
    if not text:
        return False
    if not any(pattern.search(text) for pattern in GENERATION_ABORT_LABEL_PATTERNS):
        return False
    return any(pattern.search(text) for pattern in GENERATION_ABORT_CONTEXT_PATTERNS)


def card_playback_controls_audit_script() -> str:
    """Probe playback vs generation-abort controls for diagnostics (read-only)."""
    return """({ cardFingerprint }) => {
        const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
        const lower = (v) => normalize(v).toLowerCase();
        const buildFp = (root) => {
            const r = root.getBoundingClientRect();
            const t = lower(root.innerText || root.textContent || '');
            const video = root.querySelector('video');
            const cardType = video ? 'video' : 'unknown';
            return [
                Math.round(r.left + window.scrollX),
                Math.round(r.top + window.scrollY),
                Math.round(r.width),
                Math.round(r.height),
                cardType,
                t.slice(0, 120),
            ].join('|');
        };
        const isGenAbort = (label) => {
            const l = lower(label);
            if (!l) return false;
            const hasStop = l.includes('cancel') || l.includes('stop') || l.includes('abort');
            if (!hasStop) return false;
            return l.includes('generat') || l.includes('render') || l.includes('queue');
        };
        const isPlayback = (label) => {
            const l = lower(label);
            return l.includes('play') || l.includes('pause') || l === 'mute' || l.includes('volume');
        };
        let targetCard = null;
        const actionButtons = Array.from(document.querySelectorAll(
            'button[aria-label=\"Actions\"], [aria-label*=\"Actions\"]'
        ));
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
        const inCardPlayback = [];
        const inCardGenAbort = [];
        let videoPresent = false;
        let duration = 0;
        let paused = false;
        if (targetCard) {
            const video = targetCard.querySelector('video');
            if (video) {
                videoPresent = true;
                duration = Number(video.duration) || 0;
                paused = Boolean(video.paused);
            }
            for (const b of targetCard.querySelectorAll('button, [role=\"button\"]')) {
                const rect = b.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const label = normalize(b.innerText || b.textContent || b.getAttribute('aria-label') || '');
                if (!label) continue;
                if (isGenAbort(label)) inCardGenAbort.push(label.slice(0, 80));
                else if (isPlayback(label)) inCardPlayback.push(label.slice(0, 80));
            }
        }
        const globalGenAbort = [];
        for (const b of document.querySelectorAll('button, [role=\"button\"]')) {
            const rect = b.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) continue;
            const label = normalize(b.innerText || b.textContent || b.getAttribute('aria-label') || '');
            if (isGenAbort(label)) globalGenAbort.push(label.slice(0, 80));
        }
        return {
            cardFound: Boolean(targetCard),
            videoPresent,
            duration,
            paused,
            inCardPlayback,
            inCardGenAbort,
            globalGenAbort: globalGenAbort.slice(0, 12),
        };
    }"""


def audit_card_playback_controls(
    navigator: MappedRunwayUINavigator,
    *,
    clip_index: int,
    card_fingerprint: str,
) -> CardPlaybackControlsAudit:
    audit = CardPlaybackControlsAudit(
        clip_index=clip_index,
        card_fingerprint=card_fingerprint,
    )
    if navigator.simulate or not card_fingerprint:
        audit.video_element_present = True
        audit.notes.append("simulate_skip_dom_audit")
        return audit
    page = navigator.page
    if page is None:
        audit.notes.append("no_page")
        return audit
    try:
        payload = page.evaluate(
            card_playback_controls_audit_script(),
            {"cardFingerprint": card_fingerprint},
        )
    except Exception as exc:
        audit.notes.append(f"audit_error:{exc}")
        return audit
    if not isinstance(payload, dict):
        audit.notes.append("invalid_audit_payload")
        return audit
    audit.video_element_present = bool(payload.get("videoPresent"))
    audit.video_duration = float(payload.get("duration") or 0)
    audit.video_paused = bool(payload.get("paused"))
    audit.in_card_playback_buttons = list(payload.get("inCardPlayback") or [])
    audit.in_card_generation_abort_buttons = list(payload.get("inCardGenAbort") or [])
    audit.global_generation_abort_visible = list(payload.get("globalGenAbort") or [])
    return audit


def write_playback_controls_diagnostics(
    audit: CardPlaybackControlsAudit,
    *,
    seek_result: dict[str, Any] | None = None,
    context: str = "",
) -> None:
    payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "context": context,
        "audit": audit.to_dict(),
        "seek_result": dict(seek_result or {}),
        "mapping": {
            "safe_apis": list(PLAYBACK_SAFE_APIS),
            "seek_methods": [
                SEEK_METHOD_HTML_VIDEO_CURRENT_TIME,
                SEEK_METHOD_TIMELINE_RANGE_IN_CARD,
                SEEK_METHOD_TIMELINE_VIDEO_PERCENT,
            ],
            "generation_abort_never_clicked": True,
        },
    }
    DEFAULT_PLAYBACK_CONTROLS_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PLAYBACK_CONTROLS_DIAGNOSTICS.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def seek_script_uses_only_safe_playback() -> bool:
    """Static check: last-frame seek script must not click generation abort buttons."""
    from content_brain.execution.runway_phase_i_last_frame_use_frame import (
        last_frame_seek_eval_script,
    )

    script = last_frame_seek_eval_script()
    if re.search(r"\bbutton\b[^;{]{0,80}\.click\(", script):
        return False
    if "video.currentTime" not in script:
        return False
    if "video.pause" not in script:
        return False
    return True


__all__ = [
    "CardPlaybackControlsAudit",
    "DEFAULT_PLAYBACK_CONTROLS_DIAGNOSTICS",
    "GENERATION_ABORT_LABEL_PATTERNS",
    "PLAYBACK_SAFE_APIS",
    "SEEK_METHOD_HTML_VIDEO_CURRENT_TIME",
    "SEEK_METHOD_SIMULATE",
    "SEEK_METHOD_TIMELINE_RANGE_IN_CARD",
    "SEEK_METHOD_TIMELINE_VIDEO_PERCENT",
    "audit_card_playback_controls",
    "card_playback_controls_audit_script",
    "is_generation_abort_button_label",
    "seek_script_uses_only_safe_playback",
    "write_playback_controls_diagnostics",
]
