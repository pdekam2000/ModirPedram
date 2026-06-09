"""
Phase I — strict clip generation completion gate (before download / use-frame release).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from content_brain.execution.runway_phase_i_artifact_tracker import (
    ROLE_LATEST_VIDEO,
    ROLE_STARTER_IMAGE,
    PhaseIArtifactCard,
    PhaseIArtifactTracker,
)

if TYPE_CHECKING:
    from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPLETION_GATE_DIAGNOSTICS = (
    ROOT / "project_brain" / "runway_phase_i_completion_gate_diagnostics.json"
)

_PROGRESS_PERCENT_RE = re.compile(r"(\d+)\s*%")
_IN_PROGRESS_TEXT_RE = re.compile(
    r"(generat|processing|rendering|queued|in\s+progress)",
    re.I,
)
_NOTIFICATION_BANNER_RE = re.compile(
    r"(get notifications|don't show again|enable notifications|later enable)",
    re.I,
)
_STALE_TOPIC_MARKERS = (
    "quiet beach",
    "an old man",
    "cyberpunk city",
    "lone astronaut",
)


@dataclass
class StrictClipCompletionResult:
    clip_index: int = 1
    complete: bool = False
    reason: str = ""
    generation_in_progress: bool = False
    progress_text: str = ""
    progress_percent: int | None = None
    spinner_visible: bool = False
    stop_cancel_visible: bool = False
    output_loading: bool = False
    completed_card_fingerprint: str = ""
    download_in_assigned_card: bool = False
    playable_video_in_card: bool = False
    use_frame_in_prior_card: bool = False
    ignored_global_download: bool = False
    artifact_cards: list[dict[str, Any]] = field(default_factory=list)
    download_button_candidates: list[str] = field(default_factory=list)
    use_frame_candidates: list[str] = field(default_factory=list)
    assigned_card_fingerprint: str = ""
    candidate_cards: list[dict[str, Any]] = field(default_factory=list)
    rejected_cards: list[dict[str, Any]] = field(default_factory=list)
    card_scoped_state: dict[str, Any] = field(default_factory=dict)
    global_generation_state: dict[str, Any] = field(default_factory=dict)
    persisted_assignment_fingerprint: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "complete": self.complete,
            "reason": self.reason,
            "generation_in_progress": self.generation_in_progress,
            "progress_text": self.progress_text,
            "progress_percent": self.progress_percent,
            "spinner_visible": self.spinner_visible,
            "stop_cancel_visible": self.stop_cancel_visible,
            "output_loading": self.output_loading,
            "completed_card_fingerprint": self.completed_card_fingerprint,
            "download_in_assigned_card": self.download_in_assigned_card,
            "playable_video_in_card": self.playable_video_in_card,
            "use_frame_in_prior_card": self.use_frame_in_prior_card,
            "ignored_global_download": self.ignored_global_download,
            "artifact_cards": list(self.artifact_cards),
            "download_button_candidates": list(self.download_button_candidates),
            "use_frame_candidates": list(self.use_frame_candidates),
            "assigned_card_fingerprint": self.assigned_card_fingerprint,
            "candidate_cards": list(self.candidate_cards),
            "rejected_cards": list(self.rejected_cards),
            "card_scoped_state": dict(self.card_scoped_state),
            "global_generation_state": dict(self.global_generation_state),
            "persisted_assignment_fingerprint": self.persisted_assignment_fingerprint,
            "notes": list(self.notes),
        }


def parse_progress_percent(progress_text: str) -> int | None:
    text = str(progress_text or "").strip()
    if not text:
        return None
    match = _PROGRESS_PERCENT_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def progress_blocks_completion(progress_text: str) -> bool:
    text = str(progress_text or "").strip()
    if not text:
        return False
    if _NOTIFICATION_BANNER_RE.search(text) and not _IN_PROGRESS_TEXT_RE.search(text):
        return False
    percent = parse_progress_percent(text)
    if percent is not None and percent < 100:
        return True
    if percent == 100:
        return False
    if _IN_PROGRESS_TEXT_RE.search(text) and "complete" not in text.lower():
        return True
    return False


def fingerprint_document_top(card_fingerprint: str) -> float | None:
    parts = str(card_fingerprint or "").split("|")
    if len(parts) < 2:
        return None
    try:
        return float(parts[1])
    except ValueError:
        return None


def card_is_viewport_visible(card: dict[str, Any]) -> bool:
    if card.get("cardViewportVisible") is True:
        return True
    if card.get("cardViewportVisible") is False:
        return False
    top = float(card.get("cardViewportTop", card.get("cardTop", 0)) or 0)
    bottom = float(card.get("cardViewportBottom", card.get("cardBottom", 0)) or 0)
    width = float(card.get("cardWidth", 0) or 0)
    height = float(card.get("cardHeight", 0) or 0)
    if width >= 80 and height >= 80 and bottom > 0 and top < 9000:
        return True
    doc_top = fingerprint_document_top(str(card.get("cardFingerprint") or ""))
    if doc_top is not None and doc_top < 0:
        return False
    return width >= 80 and height >= 80


def build_clip_match_tokens(clip_index: int, clip_count: int = 3) -> list[str]:
    """Tokens used to match Runway output cards to clip N (card title / fingerprint)."""
    index = max(1, int(clip_index))
    total = max(index, int(clip_count or index))
    return [
        f"clip {index} of",
        f"clip {index} of {total}",
        f"clip_{index}_of",
        f"clip {index}/",
    ]


def card_text_matches_clip_index(
    card: dict[str, Any],
    clip_index: int,
    *,
    clip_count: int = 3,
) -> bool:
    """Return True when card label/fingerprint clearly belongs to clip N."""
    index = max(1, int(clip_index))
    blob = " ".join(
        [
            str(card.get("cardPromptText") or ""),
            str(card.get("cardText") or ""),
            str(card.get("cardFingerprint") or ""),
        ]
    ).lower()
    blob_compact = blob.replace(" ", "").replace("_", "")
    for token in build_clip_match_tokens(index, clip_count):
        normalized = token.lower()
        if normalized in blob:
            return True
        if normalized.replace(" ", "") in blob_compact:
            return True
    return False


def card_is_offscreen_or_stale(
    card: dict[str, Any],
    *,
    expected_prompt_tokens: list[str] | None = None,
) -> tuple[bool, str]:
    fp = str(card.get("cardFingerprint") or "")
    doc_top = fingerprint_document_top(fp)
    if doc_top is not None and doc_top < 0:
        return True, "negative_document_y"
    top = float(card.get("cardViewportTop", card.get("cardTop", 0)) or 0)
    if top < -40:
        return True, "negative_viewport_y"
    if not card_is_viewport_visible(card):
        return True, "offscreen_or_not_viewport_visible"
    text = str(card.get("cardPromptText") or card.get("cardText") or "").lower()
    fp_lower = fp.lower()
    for marker in _STALE_TOPIC_MARKERS:
        if marker in text or marker in fp_lower:
            if expected_prompt_tokens:
                if any(marker.split()[0] in token for token in expected_prompt_tokens):
                    continue
            return True, f"stale_topic_marker:{marker}"
    if expected_prompt_tokens:
        hits = sum(1 for token in expected_prompt_tokens if token in text or token in fp_lower)
        if len(expected_prompt_tokens) >= 3 and hits == 0:
            return True, "prompt_token_mismatch"
    return False, ""


def card_has_completion_controls(card: dict[str, Any]) -> bool:
    return bool(
        card.get("hasDownload")
        or card.get("hasAppsMenu")
        or card.get("hasUseFrame")
    )


def card_is_complete_candidate(card: dict[str, Any]) -> bool:
    if str(card.get("cardType") or "") != "video":
        return False
    if card.get("cardLoading") or card.get("videoLoading"):
        return False
    if card.get("cardSpinnerVisible") or card.get("cardProgressVisible"):
        return False
    if not card.get("playableVideo"):
        return False
    if not card_has_completion_controls(card):
        return False
    return True


def card_scoped_state_dict(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "cardFingerprint": str(card.get("cardFingerprint") or ""),
        "cardType": str(card.get("cardType") or ""),
        "playableVideo": bool(card.get("playableVideo")),
        "videoLoading": bool(card.get("videoLoading")),
        "cardLoading": bool(card.get("cardLoading")),
        "cardSpinnerVisible": bool(card.get("cardSpinnerVisible")),
        "cardProgressVisible": bool(card.get("cardProgressVisible")),
        "hasDownload": bool(card.get("hasDownload")),
        "hasAppsMenu": bool(card.get("hasAppsMenu")),
        "hasUseFrame": bool(card.get("hasUseFrame")),
        "cardViewportVisible": card.get("cardViewportVisible"),
        "cardViewportTop": card.get("cardViewportTop"),
        "cardViewportBottom": card.get("cardViewportBottom"),
        "cardBottom": card.get("cardBottom"),
        "completeCandidate": card_is_complete_candidate(card),
    }


def strict_completion_eval_script() -> str:
    return """({ excludeFingerprints, requireUseFrameOnPrior, expectedPromptTokens }) => {
        const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
        const lower = (v) => normalize(v).toLowerCase();
        const exclude = new Set((excludeFingerprints || []).filter(Boolean));
        const downloadLabels = ['download mp4', 'download', 'mp4'];
        const useFrameLabels = ['use frame'];
        const downloadCandidates = [];
        const useFrameCandidates = [];
        let ignoredGlobalDownload = false;

        const buttons = Array.from(document.querySelectorAll('button, [role=\"button\"]'));
        for (const button of buttons) {
            const rect = button.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) continue;
            const text = lower(button.innerText || button.textContent || button.getAttribute('aria-label') || '');
            if (downloadLabels.some((l) => text === l || text.includes(l))) {
                downloadCandidates.push(text.slice(0, 80));
            }
            if (useFrameLabels.some((l) => text.includes(l))) {
                useFrameCandidates.push(text.slice(0, 80));
            }
        }
        if (downloadCandidates.length > 0) {
            ignoredGlobalDownload = true;
        }

        const cards = [];
        const rejected = [];
        const actionButtons = Array.from(document.querySelectorAll(
            'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
        ));
        const buildCard = (root, actionsBtn) => {
            const cardRect = root.getBoundingClientRect();
            if (cardRect.width <= 0 || cardRect.height <= 0) return null;
            const cardText = normalize(root.innerText || root.textContent || '');
            const video = root.querySelector('video');
            const img = root.querySelector('img, canvas, picture');
            let cardType = 'unknown';
            if (video) cardType = 'video';
            else if (img) cardType = 'image';
            const cardButtons = [];
            for (const b of root.querySelectorAll('button, [role=\"button\"], a[href]')) {
                const br = b.getBoundingClientRect();
                if (br.width <= 0 || br.height <= 0) continue;
                const t = normalize(b.innerText || b.textContent || b.getAttribute('aria-label') || '');
                if (t) cardButtons.push(t.slice(0, 80));
            }
            const fp = [
                Math.round(cardRect.left + window.scrollX),
                Math.round(cardRect.top + window.scrollY),
                Math.round(cardRect.width),
                Math.round(cardRect.height),
                cardType,
                cardText.slice(0, 120).toLowerCase(),
            ].join('|');
            let hasDownload = false;
            let hasUseFrame = false;
            let hasAppsMenu = false;
            for (const label of cardButtons) {
                const l = lower(label);
                if (downloadLabels.some((d) => l === d || l.includes(d))) hasDownload = true;
                if (useFrameLabels.some((u) => l.includes(u))) hasUseFrame = true;
                if (l === 'apps') hasAppsMenu = true;
            }
            let playableVideo = false;
            let videoLoading = false;
            let cardSpinnerVisible = false;
            let cardProgressVisible = false;
            if (video) {
                const vr = video.getBoundingClientRect();
                playableVideo = vr.width > 0 && vr.height > 0
                    && (video.readyState >= 2 || Boolean(video.currentSrc || video.src));
                const vcls = String(video.className || '').toLowerCase();
                videoLoading = vcls.includes('loading') || vcls.includes('pending')
                    || video.getAttribute('data-state') === 'loading';
            }
            const cls = String(root.className || '').toLowerCase();
            const cardLoading = cls.includes('loading') || cls.includes('pending') || cls.includes('skeleton');
            for (const node of root.querySelectorAll('[role=\"progressbar\"], [aria-busy=\"true\"], [class*=\"spinner\" i], [class*=\"loading\" i]')) {
                const rr = node.getBoundingClientRect();
                if (rr.width > 0 && rr.height > 0) {
                    cardSpinnerVisible = true;
                    break;
                }
            }
            for (const node of root.querySelectorAll('span, div, p, [role=\"status\"]')) {
                const rr = node.getBoundingClientRect();
                if (rr.width <= 0 || rr.height <= 0) continue;
                const t = normalize(node.innerText || node.textContent || '');
                if (/generat|processing|rendering|queued|in progress|\\d+\\s*%/i.test(t) && t.length <= 120) {
                    cardProgressVisible = true;
                    break;
                }
            }
            const cardViewportTop = cardRect.top;
            const cardViewportBottom = cardRect.bottom;
            const cardViewportVisible = cardViewportBottom > 0
                && cardViewportTop < window.innerHeight
                && cardRect.width >= 80
                && cardRect.height >= 80;
            let rejectedReason = '';
            if (exclude.has(fp)) rejectedReason = 'excluded_fingerprint';
            else if (!cardViewportVisible) rejectedReason = 'offscreen_or_not_viewport_visible';
            else if (cardViewportTop < -40) rejectedReason = 'negative_viewport_y';
            const payload = {
                cardFingerprint: fp,
                cardType,
                cardText: cardText.slice(0, 200),
                cardPromptText: cardText.slice(0, 500),
                cardTop: cardRect.top + window.scrollY,
                cardBottom: cardRect.bottom + window.scrollY,
                cardViewportTop,
                cardViewportBottom,
                cardViewportVisible,
                cardWidth: cardRect.width,
                cardHeight: cardRect.height,
                buttonsVisible: cardButtons,
                hasDownload,
                hasUseFrame,
                hasAppsMenu,
                playableVideo,
                videoLoading,
                cardLoading,
                cardSpinnerVisible,
                cardProgressVisible,
                excluded: exclude.has(fp) || Boolean(rejectedReason),
                rejectedReason,
                completeCandidate: false,
            };
            payload.completeCandidate = payload.cardType === 'video'
                && !payload.excluded
                && !payload.cardLoading
                && !payload.videoLoading
                && !payload.cardSpinnerVisible
                && !payload.cardProgressVisible
                && payload.playableVideo
                && (payload.hasDownload || payload.hasAppsMenu || payload.hasUseFrame);
            return payload;
        };
        const pushCard = (root, actionsBtn) => {
            const payload = buildCard(root, actionsBtn);
            if (!payload) return;
            if (payload.rejectedReason) {
                rejected.push({ cardFingerprint: payload.cardFingerprint, reason: payload.rejectedReason });
            }
            if (!cards.some((c) => c.cardFingerprint === payload.cardFingerprint)) {
                cards.push(payload);
            }
        };
        for (const btn of actionButtons) {
            let card = btn;
            for (let depth = 0; depth < 12 && card; depth++) {
                if (card.querySelector && card.querySelector('img, canvas, video, picture')) break;
                card = card.parentElement;
            }
            if (!card) card = btn.parentElement || btn;
            pushCard(card, btn);
        }
        const looseMedia = Array.from(document.querySelectorAll('video, picture, [class*=\"output\" i]'));
        for (const node of looseMedia) {
            const rect = node.getBoundingClientRect();
            if (rect.width < 80 || rect.height < 80) continue;
            let root = node;
            for (let d = 0; d < 6 && root; d++) {
                if (root.querySelector && root.querySelector('button[aria-label*=\"Actions\"]')) break;
                root = root.parentElement;
            }
            if (!root) continue;
            pushCard(root, null);
        }
        cards.sort((a, b) => b.cardBottom - a.cardBottom || b.cardViewportBottom - a.cardViewportBottom);
        rejected.sort((a, b) => String(a.cardFingerprint).localeCompare(String(b.cardFingerprint)));
        const videoCards = cards.filter((c) => c.cardType === 'video' && !c.excluded);
        let completedCard = null;
        for (const card of videoCards) {
            if (card.completeCandidate) {
                completedCard = card;
                break;
            }
        }
        let useFrameInPrior = false;
        if (requireUseFrameOnPrior) {
            const prior = videoCards.find((c) => c.hasUseFrame);
            useFrameInPrior = Boolean(prior);
        }
        return {
            artifactCards: cards,
            rejectedCards: rejected,
            downloadButtonCandidates: downloadCandidates,
            useFrameCandidates: useFrameCandidates,
            ignoredGlobalDownload,
            completedCard,
            useFrameInPrior,
        };
    }"""


def _prompt_tokens(navigator: MappedRunwayUINavigator, clip_index: int) -> list[str]:
    getter = getattr(navigator, "clip_prompt_match_tokens", None)
    if callable(getter):
        tokens = getter(clip_index)
        if isinstance(tokens, list):
            parsed = [str(item).lower() for item in tokens if str(item).strip()]
            if parsed:
                return parsed
    clip_count = int(getattr(navigator, "_phase_i_clip_count", 3) or 3)
    return [token.lower() for token in build_clip_match_tokens(clip_index, clip_count)]


def _apply_global_generation_state(
    result: StrictClipCompletionResult,
    navigator: MappedRunwayUINavigator,
) -> None:
    gen = navigator.detect_video_generation_in_progress(result.clip_index)
    result.generation_in_progress = gen.in_progress
    result.progress_text = gen.progress_text
    result.spinner_visible = gen.spinner_visible
    result.stop_cancel_visible = gen.stop_cancel_visible
    result.output_loading = gen.output_loading
    result.progress_percent = parse_progress_percent(gen.progress_text)
    result.global_generation_state = gen.to_dict() if hasattr(gen, "to_dict") else {
        "in_progress": gen.in_progress,
        "progress_text": gen.progress_text,
        "spinner_visible": gen.spinner_visible,
        "stop_cancel_visible": gen.stop_cancel_visible,
        "output_loading": gen.output_loading,
        "signals": list(getattr(gen, "signals", []) or []),
    }
    if progress_blocks_completion(gen.progress_text):
        result.global_generation_state["progress_blocks_completion"] = True


def _persist_assignment_from_card(
    navigator: MappedRunwayUINavigator,
    clip_index: int,
    card: dict[str, Any],
) -> str:
    tracker = navigator.phase_i_artifact_tracker()
    role = PhaseIArtifactTracker.clip_video_role(clip_index)
    artifact = tracker._card_from_raw(card, role=role)
    tracker.assignments[role] = artifact
    tracker.assignments[ROLE_LATEST_VIDEO] = PhaseIArtifactCard(
        card_index=artifact.card_index,
        card_fingerprint=artifact.card_fingerprint,
        card_type=artifact.card_type,
        card_prompt_text=artifact.card_prompt_text,
        bounding_box=dict(artifact.bounding_box),
        buttons_visible=list(artifact.buttons_visible),
        media_src=artifact.media_src,
        media_urls=list(artifact.media_urls),
        role=ROLE_LATEST_VIDEO,
        consumed=artifact.consumed,
    )
    if artifact.card_fingerprint:
        tracker._snapshot_fps.add(artifact.card_fingerprint)
    return artifact.card_fingerprint


def _partition_video_cards(
    cards: list[dict[str, Any]],
    *,
    expected_prompt_tokens: list[str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for card in cards:
        if str(card.get("cardType") or "") != "video":
            continue
        stale, reason = card_is_offscreen_or_stale(
            card,
            expected_prompt_tokens=expected_prompt_tokens,
        )
        if stale:
            rejected.append(
                {
                    "cardFingerprint": str(card.get("cardFingerprint") or ""),
                    "reason": reason,
                    "cardBottom": card.get("cardBottom"),
                }
            )
            continue
        candidates.append(card)
    candidates.sort(
        key=lambda c: (
            float(c.get("cardBottom") or 0),
            float(c.get("cardViewportBottom") or 0),
        ),
        reverse=True,
    )
    return candidates, rejected


def _resolve_target_card(
    *,
    candidates: list[dict[str, Any]],
    assigned_fingerprint: str,
    clip_index: int = 0,
    clip_count: int = 3,
) -> dict[str, Any] | None:
    scoped = list(candidates)
    if clip_index >= 1:
        marker_matches = [
            card
            for card in scoped
            if card_text_matches_clip_index(card, clip_index, clip_count=clip_count)
        ]
        if marker_matches:
            scoped = marker_matches

    if assigned_fingerprint:
        for card in scoped:
            if str(card.get("cardFingerprint") or "") == assigned_fingerprint:
                if clip_index <= 1 or card_text_matches_clip_index(
                    card, clip_index, clip_count=clip_count
                ):
                    return card
    for card in scoped:
        if card_is_complete_candidate(card):
            if clip_index <= 1 or card_text_matches_clip_index(
                card, clip_index, clip_count=clip_count
            ):
                return card
    if assigned_fingerprint:
        for card in scoped:
            if str(card.get("cardFingerprint") or "") == assigned_fingerprint:
                return card
    return scoped[0] if scoped else None


def _card_failure_reason(card: dict[str, Any]) -> str:
    if not card.get("playableVideo"):
        return "video_not_playable"
    if card.get("videoLoading") or card.get("cardLoading"):
        return "output_loading"
    if card.get("cardSpinnerVisible"):
        return "spinner_visible"
    if card.get("cardProgressVisible"):
        return "progress_not_complete"
    if not card_has_completion_controls(card):
        return "download_not_in_card"
    return "card_not_ready"


def evaluate_strict_clip_completion(
    navigator: MappedRunwayUINavigator,
    clip_index: int,
    *,
    test_override: dict[str, Any] | None = None,
) -> StrictClipCompletionResult:
    """Return whether clip N is truly complete and safe for download gate release."""
    index = max(1, int(clip_index))
    result = StrictClipCompletionResult(clip_index=index)

    if test_override is not None:
        return _evaluate_from_override(index, test_override)

    tracker = navigator.phase_i_artifact_tracker()
    role = PhaseIArtifactTracker.clip_video_role(index)
    assigned = tracker.get_assigned(role) or tracker.get_assigned(ROLE_LATEST_VIDEO)
    if assigned and assigned.card_fingerprint:
        result.assigned_card_fingerprint = assigned.card_fingerprint
        result.persisted_assignment_fingerprint = assigned.card_fingerprint

    _apply_global_generation_state(result, navigator)

    exclude: list[str] = []
    starter = tracker.get_assigned(ROLE_STARTER_IMAGE)
    if starter and starter.card_fingerprint:
        exclude.append(starter.card_fingerprint)
    for prior in range(1, index):
        prior_card = tracker.get_assigned(PhaseIArtifactTracker.clip_video_role(prior))
        if prior_card and prior_card.card_fingerprint:
            exclude.append(prior_card.card_fingerprint)
    exclude.extend(list(tracker._consumed_fingerprints))

    require_use_frame = index >= 2 and navigator.simulate is False
    prompt_tokens = _prompt_tokens(navigator, index)

    if navigator.simulate:
        return _evaluate_simulate_strict(
            navigator,
            result,
            index,
            exclude,
            assigned,
            require_use_frame,
        )

    page = navigator._require_page()
    try:
        payload = page.evaluate(
            strict_completion_eval_script(),
            {
                "excludeFingerprints": exclude,
                "requireUseFrameOnPrior": require_use_frame,
                "expectedPromptTokens": prompt_tokens,
            },
        )
    except Exception as exc:
        result.reason = f"eval_error:{exc}"
        return result

    if not isinstance(payload, dict):
        payload = {}

    return _evaluate_payload(
        navigator,
        result,
        payload,
        clip_index=index,
        assigned_fingerprint=result.assigned_card_fingerprint,
        require_use_frame=require_use_frame,
        expected_prompt_tokens=prompt_tokens,
    )


def _evaluate_simulate_strict(
    navigator: MappedRunwayUINavigator,
    result: StrictClipCompletionResult,
    clip_index: int,
    exclude: list[str],
    assigned: PhaseIArtifactCard | None,
    require_use_frame: bool,
) -> StrictClipCompletionResult:
    pending = getattr(navigator, "_simulate_clip_generating", None) or {}
    if pending.get(clip_index):
        result.reason = "simulate_generation_in_progress"
        result.generation_in_progress = True
        return result

    tracker = navigator.phase_i_artifact_tracker()
    role = PhaseIArtifactTracker.clip_video_role(clip_index)
    if assigned is None or not assigned.card_fingerprint:
        tracker.simulate_add_card(
            card_type="video",
            prompt_text=f"clip_{clip_index}_completed",
            buttons=["Download MP4", "Use Frame", "Apps"],
        )
        tracker.assign_new_card(role, prefer_type="video")

    card = tracker.get_assigned(role)
    if card is None:
        result.reason = "simulate_no_video_card"
        return result

    result.completed_card_fingerprint = card.card_fingerprint
    result.download_in_assigned_card = True
    result.playable_video_in_card = True
    result.use_frame_in_prior_card = not require_use_frame or clip_index == 1
    result.card_scoped_state = {
        "cardFingerprint": card.card_fingerprint,
        "completeCandidate": True,
        "hasDownload": True,
        "hasAppsMenu": True,
    }
    result.complete = True
    result.reason = "simulate_strict_complete"
    result.persisted_assignment_fingerprint = card.card_fingerprint
    return result


def _evaluate_from_override(
    clip_index: int,
    override: dict[str, Any],
) -> StrictClipCompletionResult:
    result = StrictClipCompletionResult(clip_index=clip_index)
    result.generation_in_progress = bool(override.get("generation_in_progress"))
    result.progress_text = str(override.get("progress_text") or "")
    result.progress_percent = parse_progress_percent(result.progress_text)
    result.spinner_visible = bool(override.get("spinner_visible"))
    result.stop_cancel_visible = bool(override.get("stop_cancel_visible"))
    result.output_loading = bool(override.get("output_loading"))
    result.ignored_global_download = bool(override.get("ignored_global_download"))
    result.global_generation_state = {
        "in_progress": result.generation_in_progress,
        "progress_text": result.progress_text,
        "spinner_visible": result.spinner_visible,
        "stop_cancel_visible": result.stop_cancel_visible,
        "output_loading": result.output_loading,
    }
    if result.generation_in_progress or progress_blocks_completion(result.progress_text):
        result.reason = str(override.get("reason") or "generation_in_progress")
        return result
    if result.spinner_visible:
        result.reason = "spinner_visible"
        return result
    if result.stop_cancel_visible:
        result.reason = "stop_cancel_visible"
        return result
    if result.output_loading:
        result.reason = "output_loading"
        return result
    completed = override.get("completed_card") or {}
    if isinstance(completed, dict) and completed.get("cardFingerprint"):
        result.completed_card_fingerprint = str(completed["cardFingerprint"])
        result.download_in_assigned_card = bool(
            completed.get("hasDownload")
            or completed.get("hasAppsMenu")
            or completed.get("hasUseFrame")
        )
        result.playable_video_in_card = bool(completed.get("playableVideo"))
        result.card_scoped_state = card_scoped_state_dict(completed)
        result.complete = bool(
            override.get("complete")
            and result.download_in_assigned_card
            and result.playable_video_in_card
        )
        result.reason = str(
            override.get("reason") or ("strict_complete" if result.complete else "card_not_ready")
        )
    else:
        result.reason = str(override.get("reason") or "no_completed_video_card")
    return result


def _evaluate_payload(
    navigator: MappedRunwayUINavigator,
    result: StrictClipCompletionResult,
    payload: dict[str, Any],
    *,
    clip_index: int,
    assigned_fingerprint: str,
    require_use_frame: bool,
    expected_prompt_tokens: list[str] | None,
) -> StrictClipCompletionResult:
    result.artifact_cards = list(payload.get("artifactCards") or [])
    result.download_button_candidates = list(payload.get("downloadButtonCandidates") or [])
    result.use_frame_candidates = list(payload.get("useFrameCandidates") or [])
    result.ignored_global_download = bool(payload.get("ignoredGlobalDownload"))
    result.use_frame_in_prior_card = bool(payload.get("useFrameInPrior"))

    dom_rejected = list(payload.get("rejectedCards") or [])
    all_video = [
        card
        for card in result.artifact_cards
        if str(card.get("cardType") or "") == "video"
    ]
    candidates, py_rejected = _partition_video_cards(
        all_video,
        expected_prompt_tokens=expected_prompt_tokens,
    )
    result.candidate_cards = [card_scoped_state_dict(card) for card in candidates]
    result.rejected_cards = dom_rejected + py_rejected

    clip_count = int(getattr(navigator, "_phase_i_clip_count", 3) or 3)
    target = _resolve_target_card(
        candidates=candidates,
        assigned_fingerprint=assigned_fingerprint,
        clip_index=clip_index,
        clip_count=clip_count,
    )

    if target is None:
        result.reason = "no_completed_video_card"
        if result.ignored_global_download:
            result.notes.append("ignored_global_download_only")
        if result.generation_in_progress:
            result.notes.append("global_generation_in_progress_no_card")
        return result

    target_fp = str(target.get("cardFingerprint") or "")
    assigned_stale = False
    if assigned_fingerprint:
        assigned_raw = next(
            (card for card in all_video if str(card.get("cardFingerprint") or "") == assigned_fingerprint),
            {"cardFingerprint": assigned_fingerprint},
        )
        assigned_stale, stale_reason = card_is_offscreen_or_stale(
            assigned_raw,
            expected_prompt_tokens=expected_prompt_tokens,
        )
        if assigned_stale:
            result.rejected_cards.append(
                {
                    "cardFingerprint": assigned_fingerprint,
                    "reason": f"assigned_stale:{stale_reason}",
                }
            )

    if target_fp and (not assigned_fingerprint or assigned_stale or target_fp != assigned_fingerprint):
        persisted = _persist_assignment_from_card(navigator, clip_index, target)
        result.assigned_card_fingerprint = persisted
        result.persisted_assignment_fingerprint = persisted
        if assigned_fingerprint and target_fp != assigned_fingerprint:
            result.notes.append("refreshed_assignment_from_visible_candidate")

    result.card_scoped_state = card_scoped_state_dict(target)
    result.completed_card_fingerprint = target_fp
    result.playable_video_in_card = bool(target.get("playableVideo"))
    result.download_in_assigned_card = card_has_completion_controls(target)

    if clip_index >= 2 and not getattr(navigator, "simulate", False) and not card_text_matches_clip_index(
        target, clip_index, clip_count=clip_count
    ):
        result.reason = "clip_marker_mismatch"
        result.notes.append(
            f"expected_clip_{clip_index}_marker_not_found_in_target_card"
        )
        return result

    if card_is_complete_candidate(target):
        result.complete = True
        result.reason = "strict_complete"
        if result.generation_in_progress or progress_blocks_completion(result.progress_text):
            result.notes.append("card_complete_overrides_global_generation")
        if result.stop_cancel_visible:
            result.notes.append("card_complete_overrides_stop_cancel_visible")
        return result

    result.reason = _card_failure_reason(target)
    if require_use_frame and not result.use_frame_in_prior_card:
        result.notes.append("use_frame_on_prior_not_required_for_download_gate")

    if (
        result.reason in {"no_completed_video_card", "card_not_ready"}
        and result.generation_in_progress
        and not progress_blocks_completion(result.progress_text)
        and result.stop_cancel_visible
    ):
        result.notes.append("global_stop_cancel_visible_card_not_ready")

    return result


def write_strict_completion_diagnostics(
    navigator: MappedRunwayUINavigator,
    result: StrictClipCompletionResult,
    *,
    context: str = "",
    screenshot_path: str = "",
) -> None:
    action_log = []
    try:
        action_log = [entry.to_dict() for entry in navigator.action_log[-20:]]
    except Exception:
        pass
    payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "context": context,
        "clip_index": result.clip_index,
        "complete": result.complete,
        "reason": result.reason,
        "progress_text": result.progress_text,
        "progress_percent": result.progress_percent,
        "spinner_visible": result.spinner_visible,
        "stop_cancel_visible": result.stop_cancel_visible,
        "generation_in_progress": result.generation_in_progress,
        "artifact_cards": result.artifact_cards,
        "assigned_card_fingerprint": result.assigned_card_fingerprint,
        "completed_card_fingerprint": result.completed_card_fingerprint,
        "download_button_candidates": result.download_button_candidates,
        "use_frame_candidates": result.use_frame_candidates,
        "ignored_global_download": result.ignored_global_download,
        "candidate_cards": result.candidate_cards,
        "rejected_cards": result.rejected_cards,
        "card_scoped_state": result.card_scoped_state,
        "global_generation_state": result.global_generation_state,
        "persisted_assignment_fingerprint": result.persisted_assignment_fingerprint,
        "current_url": navigator._current_page_url(),
        "screenshot_path": screenshot_path,
        "last_20_action_logs": action_log,
        "result": result.to_dict(),
    }
    DEFAULT_COMPLETION_GATE_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_COMPLETION_GATE_DIAGNOSTICS.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


__all__ = [
    "DEFAULT_COMPLETION_GATE_DIAGNOSTICS",
    "StrictClipCompletionResult",
    "build_clip_match_tokens",
    "card_has_completion_controls",
    "card_is_complete_candidate",
    "card_is_offscreen_or_stale",
    "card_is_viewport_visible",
    "card_scoped_state_dict",
    "card_text_matches_clip_index",
    "evaluate_strict_clip_completion",
    "fingerprint_document_top",
    "parse_progress_percent",
    "progress_blocks_completion",
    "strict_completion_eval_script",
    "write_strict_completion_diagnostics",
]
