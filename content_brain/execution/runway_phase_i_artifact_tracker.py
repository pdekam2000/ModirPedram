"""
Phase I — session artifact card tracking (starter image + clip videos).

Tracks fingerprints and assigns roles so Use Frame / Download target the correct card.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

ROLE_STARTER_IMAGE = "starter_image_card"
ROLE_LATEST_VIDEO = "latest_video_card"
ROLE_CLIP_VIDEO = "clip_{}_video_card"

PLAYBACK_LABELS = ("Play", "Pause", "play", "pause", "PLAY", "PAUSE")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_CARD_DIAGNOSTICS = (
    ROOT / "project_brain" / "runway_phase_i_artifact_card_diagnostics.json"
)

USE_FRAME_LABELS = ("Use Frame", "USE FRAME", "Use frame")
DOWNLOAD_LABELS = ("Download MP4", "Download", "DOWNLOAD MP4", "MP4")
# In-card Apps menu is the scoped Runway download entry (not global "Download all").
DOWNLOAD_SCOPED_ENTRY_LABELS = ("Apps",)


class PageLike(Protocol):
    def evaluate(self, script: str, arg: Any = None) -> Any: ...


@dataclass
class PhaseIArtifactCard:
    card_index: int = -1
    card_fingerprint: str = ""
    card_type: str = "unknown"
    card_prompt_text: str = ""
    bounding_box: dict[str, float] = field(default_factory=dict)
    buttons_visible: list[str] = field(default_factory=list)
    media_src: str = ""
    media_urls: list[str] = field(default_factory=list)
    role: str = ""
    consumed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_index": self.card_index,
            "card_fingerprint": self.card_fingerprint,
            "card_type": self.card_type,
            "card_prompt_text": self.card_prompt_text,
            "bounding_box": dict(self.bounding_box),
            "buttons_visible": list(self.buttons_visible),
            "media_src": self.media_src,
            "media_urls": list(self.media_urls),
            "role": self.role,
            "consumed": self.consumed,
        }


@dataclass
class PhaseIArtifactTracker:
    simulate: bool = False
    page: PageLike | None = None
    project_id: str = "phase_i"
    _snapshot_fps: set[str] = field(default_factory=set)
    _last_scan: list[dict[str, Any]] = field(default_factory=list)
    assignments: dict[str, PhaseIArtifactCard] = field(default_factory=dict)
    _consumed_fingerprints: set[str] = field(default_factory=set)
    _simulated_cards: list[dict[str, Any]] = field(default_factory=list)
    ambiguity_notes: list[str] = field(default_factory=list)

    @staticmethod
    def clip_video_role(clip_index: int) -> str:
        return ROLE_CLIP_VIDEO.format(max(1, int(clip_index)))

    @staticmethod
    def _artifact_cards_eval_script() -> str:
        return """() => {
            const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
            const lower = (v) => normalize(v).toLowerCase();
            const cards = [];
            const actionButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
            ));
            const buildCard = (root, actionsBtn) => {
                const cardRect = root.getBoundingClientRect();
                if (cardRect.width <= 0 || cardRect.height <= 0) return null;
                const cardText = normalize(root.innerText || root.textContent || '');
                const video = root.querySelector('video');
                const img = root.querySelector('img, picture img, canvas');
                let cardType = 'unknown';
                if (video) cardType = 'video';
                else if (img) cardType = 'image';
                const buttons = [];
                for (const b of root.querySelectorAll('button, [role=\"button\"], a[href]')) {
                    const br = b.getBoundingClientRect();
                    if (br.width <= 0 || br.height <= 0) continue;
                    const t = normalize(b.innerText || b.textContent || b.getAttribute('aria-label') || '');
                    if (t) buttons.push(t.slice(0, 80));
                }
                let mediaSrc = '';
                const mediaUrls = [];
                if (video) {
                    mediaSrc = video.currentSrc || video.src || '';
                    if (mediaSrc) mediaUrls.push(mediaSrc);
                }
                if (img) {
                    const src = img.currentSrc || img.src || '';
                    if (src) {
                        if (!mediaSrc) mediaSrc = src;
                        mediaUrls.push(src);
                    }
                }
                for (const a of root.querySelectorAll('a[download], a[href*=\".mp4\"], a[href*=\"video\"]')) {
                    const href = a.href || '';
                    if (href) mediaUrls.push(href);
                }
                const fp = [
                    Math.round(cardRect.left + window.scrollX),
                    Math.round(cardRect.top + window.scrollY),
                    Math.round(cardRect.width),
                    Math.round(cardRect.height),
                    cardType,
                    cardText.slice(0, 120).toLowerCase(),
                ].join('|');
                return {
                    cardTop: cardRect.top + window.scrollY,
                    cardBottom: cardRect.bottom + window.scrollY,
                    cardLeft: cardRect.left + window.scrollX,
                    cardWidth: cardRect.width,
                    cardHeight: cardRect.height,
                    cardPromptText: cardText.slice(0, 500),
                    cardFingerprint: fp,
                    cardType,
                    buttonsVisible: buttons.slice(0, 20),
                    mediaSrc: mediaSrc.slice(0, 500),
                    mediaUrls: Array.from(new Set(mediaUrls)).slice(0, 8),
                    hasAppMenu: Boolean(actionsBtn),
                    selected: root.getAttribute('aria-selected') === 'true'
                        || String(root.className || '').toLowerCase().includes('selected'),
                };
            };
            for (const btn of actionButtons) {
                let card = btn;
                for (let depth = 0; depth < 12 && card; depth++) {
                    if (card.querySelector && card.querySelector('img, canvas, video, picture')) break;
                    card = card.parentElement;
                }
                if (!card) card = btn.parentElement || btn;
                const payload = buildCard(card, btn);
                if (payload) cards.push(payload);
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
                const payload = buildCard(root, null);
                if (!payload) continue;
                if (!cards.some((c) => c.cardFingerprint === payload.cardFingerprint)) {
                    cards.push(payload);
                }
            }
            cards.sort((a, b) => b.cardBottom - a.cardBottom || b.cardTop - a.cardTop);
            return cards.map((c, index) => ({ ...c, cardIndex: index }));
        }"""

    @staticmethod
    def _card_dom_helpers_js() -> str:
        return """
        const __normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
        const __buildCardFingerprint = (root) => {
            const r = root.getBoundingClientRect();
            const t = __normalize(root.innerText || root.textContent || '');
            const video = root.querySelector('video');
            const img = root.querySelector('img, picture img, canvas');
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
        const __findCardByFingerprint = (cardFingerprint) => {
            const seen = new Set();
            const candidates = [];
            const actionButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
            ));
            for (const btn of actionButtons) {
                let card = btn;
                for (let depth = 0; depth < 12 && card; depth++) {
                    if (card.querySelector && card.querySelector('img, canvas, video, picture')) break;
                    card = card.parentElement;
                }
                if (!card) card = btn.parentElement || btn;
                const fp = __buildCardFingerprint(card);
                if (!seen.has(fp)) {
                    seen.add(fp);
                    candidates.push(card);
                }
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
                const fp = __buildCardFingerprint(root);
                if (!seen.has(fp)) {
                    seen.add(fp);
                    candidates.push(root);
                }
            }
            for (const card of candidates) {
                if (__buildCardFingerprint(card) === cardFingerprint) return card;
            }
            const parts = String(cardFingerprint || '').split('|');
            if (parts.length >= 6) {
                const tail = parts.slice(4).join('|');
                for (const card of candidates) {
                    const fp = __buildCardFingerprint(card);
                    if (fp.endsWith(tail) || fp.split('|').slice(4).join('|') === tail) {
                        return card;
                    }
                }
            }
            return null;
        };
        const __primeVideoForUseFrame = (card) => {
            if (!card) return false;
            try {
                card.scrollIntoView({ block: 'center', inline: 'nearest' });
            } catch (_err) {}
            const video = card.querySelector('video');
            if (!video) return false;
            try {
                video.pause();
            } catch (_err) {}
            try {
                const vr = video.getBoundingClientRect();
                if (vr.width > 0 && vr.height > 0) {
                    video.dispatchEvent(new MouseEvent('mousemove', {
                        bubbles: true,
                        cancelable: true,
                        clientX: vr.left + vr.width / 2,
                        clientY: vr.top + vr.height * 0.75,
                    }));
                }
            } catch (_err) {}
            return true;
        };
        const __dispatchClick = (node) => {
            if (!node) return false;
            try {
                node.scrollIntoView({ block: 'center', inline: 'nearest' });
            } catch (_err) {}
            try {
                node.focus({ preventScroll: true });
            } catch (_err) {}
            const opts = { bubbles: true, cancelable: true, view: window };
            try {
                node.dispatchEvent(new PointerEvent('pointerdown', opts));
                node.dispatchEvent(new PointerEvent('pointerup', opts));
            } catch (_err) {}
            try {
                node.dispatchEvent(new MouseEvent('mousedown', opts));
                node.dispatchEvent(new MouseEvent('mouseup', opts));
                node.dispatchEvent(new MouseEvent('click', opts));
            } catch (_err) {}
            try {
                node.click();
            } catch (_err) {}
            return true;
        };
        const __nodeLabelText = (node) => __normalize(
            node.innerText || node.textContent || node.getAttribute('aria-label') || ''
        );
        const __matchesLabelTargets = (text, targets) => {
            if (!text) return false;
            for (const label of targets) {
                if (text === label || text.includes(label)) return true;
            }
            return false;
        };
        const __matchesUseFrameLabel = (text) => text.includes('use frame');
        const __scopeHasUseFrame = (root) => {
            if (!root) return false;
            return Array.from(root.querySelectorAll(
                'button, [role=\"button\"], a[href], span, div, [aria-label]'
            )).some((node) => {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return false;
                return __matchesUseFrameLabel(__nodeLabelText(node));
            });
        };
        const __expandCardControlScope = (card) => {
            if (!card) return null;
            if (__scopeHasUseFrame(card)) return card;
            let expanded = card;
            for (let depth = 0; depth < 6 && expanded.parentElement; depth++) {
                const parent = expanded.parentElement;
                if (__scopeHasUseFrame(parent)) {
                    expanded = parent;
                    break;
                }
                expanded = parent;
            }
            return expanded;
        };
        const __anchorRectForCard = (card) => {
            if (!card) return null;
            const video = card.querySelector('video');
            if (video) {
                const vr = video.getBoundingClientRect();
                if (vr.width > 0 && vr.height > 0) return vr;
            }
            return card.getBoundingClientRect();
        };
        const __nodesBelowVideoBand = (card, maxBelowPx) => {
            const anchor = __anchorRectForCard(card);
            if (!anchor || anchor.width <= 0 || anchor.height <= 0) return [];
            const below = Math.max(80, Number(maxBelowPx) || 180);
            const bandLeft = anchor.left - 24;
            const bandRight = anchor.right + 24;
            const bandTop = anchor.bottom - 4;
            const bandBottom = anchor.bottom + below;
            const hits = [];
            for (const node of document.querySelectorAll(
                'button, [role=\"button\"], a[href], span, div, [aria-label]'
            )) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                if (cx < bandLeft || cx > bandRight) continue;
                if (cy < bandTop || cy > bandBottom) continue;
                hits.push({ node, rect, cy });
            }
            hits.sort((a, b) => a.cy - b.cy);
            return hits.map((item) => item.node);
        };
        const __collectScopedNodes = (card) => {
            const scope = __expandCardControlScope(card) || card;
            const nodes = Array.from(scope.querySelectorAll(
                'button, [role=\"button\"], a[href], span, div, [aria-label]'
            ));
            for (const node of __nodesBelowVideoBand(card, 280)) {
                if (!nodes.includes(node)) nodes.push(node);
            }
            return { scope, nodes };
        };
        const __clickMatchingNode = (nodes, targets, useFrameMode) => {
            for (const node of nodes) {
                const text = __nodeLabelText(node);
                if (useFrameMode) {
                    if (!__matchesUseFrameLabel(text)) continue;
                } else if (!__matchesLabelTargets(text, targets)) {
                    continue;
                }
                try {
                    node.scrollIntoView({ block: 'center', inline: 'nearest' });
                } catch (_err) {}
                __dispatchClick(node);
                return true;
            }
            return false;
        };
        const __clickAppsMenuUseFrame = (scope) => {
            const appsBtn = Array.from(scope.querySelectorAll('button, [role=\"button\"], span')).find((node) => {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return false;
                return __nodeLabelText(node) === 'apps';
            });
            if (!appsBtn) return false;
            __dispatchClick(appsBtn);
            const deadline = Date.now() + 2200;
            while (Date.now() < deadline) {
                for (const item of document.querySelectorAll(
                    'button, [role=\"menuitem\"], [role=\"button\"], a[href], span, div'
                )) {
                    const rect = item.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;
                    if (__matchesUseFrameLabel(__nodeLabelText(item))) {
                        __dispatchClick(item);
                        return true;
                    }
                }
            }
            return false;
        };
        const __locateUseFrameButton = (cardFingerprint) => {
            const targetCard = __findCardByFingerprint(cardFingerprint);
            if (!targetCard) return { found: false, reason: 'card_not_found' };
            __primeVideoForUseFrame(targetCard);
            const { scope, nodes } = __collectScopedNodes(targetCard);
            for (const node of nodes) {
                const text = __nodeLabelText(node);
                if (!__matchesUseFrameLabel(text)) continue;
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                return {
                    found: true,
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                    label: text.slice(0, 80),
                };
            }
            return { found: false, reason: 'use_frame_not_visible', cardFound: true };
        };
        """

    @staticmethod
    def _find_card_fn_js() -> str:
        return "(cardFingerprint) => __findCardByFingerprint(cardFingerprint)"

    @staticmethod
    def _find_card_by_fingerprint_eval_script() -> str:
        return (
            PhaseIArtifactTracker._card_dom_helpers_js()
            + PhaseIArtifactTracker._find_card_fn_js()
        )

    @staticmethod
    def _scoped_label_match_eval_script() -> str:
        return """(labelKind, text, node) => {
            const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            const t = normalize(text || '');
            const tag = String((node && node.tagName) || '').toUpperCase();
            if (!t && tag !== 'VIDEO') return false;
            if (labelKind === 'download') {
                if (!t || t.includes('downloaded') || t.includes('download all')) return false;
                // Apps is an in-card-only download entry; never count globally.
                if (t === 'apps') return false;
                if (t === 'download mp4' || t === 'download' || (t.includes('download') && t.includes('mp4'))) {
                    return true;
                }
                return false;
            }
            if (labelKind === 'playback') {
                if (tag === 'VIDEO') return false;
                if (t === 'play' || t === 'pause') return true;
                if (t.includes('playback') || t.includes('playback rate')) return true;
                return false;
            }
            if (labelKind === 'use_frame') {
                return t.includes('use frame');
            }
            return false;
        }"""

    @staticmethod
    def control_scope_audit_eval_script() -> str:
        return PhaseIArtifactTracker._card_dom_helpers_js() + """
        ({ cardFingerprint, labelKind }) => {
            const matchesScoped = %s;
            const targetCard = __findCardByFingerprint(cardFingerprint);
            const nodeInsideCard = (node, card) => {
                if (!node || !card) return false;
                const nr = node.getBoundingClientRect();
                if (nr.width <= 0 || nr.height <= 0) return false;
                if (labelKind === 'use_frame') {
                    const scoped = __collectScopedNodes(card);
                    return scoped.nodes.includes(node);
                }
                const cr = card.getBoundingClientRect();
                if (cr.width <= 0 || cr.height <= 0) return false;
                const cx = nr.left + nr.width / 2;
                const cy = nr.top + nr.height / 2;
                return cx >= cr.left && cx <= cr.right && cy >= cr.top && cy <= cr.bottom;
            };
            const globalNodes = Array.from(document.querySelectorAll(
                'button, [role=\"button\"], a[href], span, [aria-label], media-play-button, media-time-display'
            ));
            let globalMatches = 0;
            let inCardMatches = 0;
            let leakedGlobalMatches = 0;
            const globalSamples = [];
            const inCardSamples = [];
            const leakedSamples = [];
            for (const node of globalNodes) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const text = node.innerText || node.textContent || node.getAttribute('aria-label') || '';
                if (!matchesScoped(labelKind, text, node)) continue;
                globalMatches += 1;
                if (globalSamples.length < 8) globalSamples.push(String(text).trim().slice(0, 60));
                if (targetCard && nodeInsideCard(node, targetCard)) {
                    inCardMatches += 1;
                    if (inCardSamples.length < 8) inCardSamples.push(String(text).trim().slice(0, 60));
                } else {
                    leakedGlobalMatches += 1;
                    if (leakedSamples.length < 8) leakedSamples.push(String(text).trim().slice(0, 60));
                }
            }
            let inCardOperational = inCardMatches > 0;
            if (labelKind === 'download' && targetCard) {
                const scoped = __collectScopedNodes(targetCard);
                const hasVideo = Boolean(targetCard.querySelector('video'));
                const hasApps = scoped.nodes.some((b) => __nodeLabelText(b) === 'apps');
                if (hasVideo && hasApps) inCardOperational = true;
            }
            if (labelKind === 'playback' && targetCard) {
                const hasVideo = Boolean(targetCard.querySelector('video'));
                const hasPlay = Array.from(targetCard.querySelectorAll(
                    'media-play-button, button, [role=\"button\"], [aria-label]'
                )).some((b) => matchesScoped('playback', b.getAttribute('aria-label') || b.innerText || '', b));
                if (hasVideo && hasPlay) inCardOperational = true;
            }
            if (labelKind === 'use_frame' && targetCard) {
                const scoped = __collectScopedNodes(targetCard);
                const hasUseFrame = scoped.nodes.some((node) => __matchesUseFrameLabel(__nodeLabelText(node)));
                if (hasUseFrame) inCardOperational = true;
            }
            return {
                cardFound: Boolean(targetCard),
                labelKind,
                globalMatches,
                inCardMatches,
                leakedGlobalMatches,
                globalSamples,
                inCardSamples,
                leakedSamples,
                inCardOperational,
                scopedOk: Boolean(targetCard) && leakedGlobalMatches === 0 && inCardOperational,
            };
        }""" % PhaseIArtifactTracker._scoped_label_match_eval_script().strip()

    @staticmethod
    def _click_label_in_card_eval_script() -> str:
        return PhaseIArtifactTracker._card_dom_helpers_js() + """({ cardFingerprint, labels }) => {
            const targets = (labels || []).map((l) => __normalize(l)).filter(Boolean);
            const useFrameMode = targets.some((label) => label.includes('use frame'));
            const targetCard = __findCardByFingerprint(cardFingerprint);
            if (!targetCard) return false;
            __primeVideoForUseFrame(targetCard);
            const { scope, nodes } = __collectScopedNodes(targetCard);
            const clickables = nodes.slice().sort((a, b) => {
                const score = (node) => {
                    const tag = String(node.tagName || '').toLowerCase();
                    if (tag === 'button' || node.getAttribute('role') === 'button') return 0;
                    if (tag === 'a') return 1;
                    return 2;
                };
                return score(a) - score(b);
            });
            if (__clickMatchingNode(clickables, targets, useFrameMode)) return true;
            if (useFrameMode && __clickAppsMenuUseFrame(scope || targetCard)) return true;
            return false;
        }"""

    @staticmethod
    def _locate_use_frame_button_eval_script() -> str:
        return PhaseIArtifactTracker._card_dom_helpers_js() + """({ cardFingerprint }) => {
            return __locateUseFrameButton(cardFingerprint);
        }"""

    @staticmethod
    def _label_visible_in_card_eval_script() -> str:
        return PhaseIArtifactTracker._card_dom_helpers_js() + """
        ({ cardFingerprint, labels, labelKind }) => {
            const matchesScoped = %s;
            const kind = labelKind || 'generic';
            const targets = (labels || []).map((l) => __normalize(l)).filter(Boolean);
            const targetCard = __findCardByFingerprint(cardFingerprint);
            if (!targetCard) {
                return { visible: false, matchedLabel: '', scope: 'card_not_found' };
            }
            const { scope, nodes } = kind === 'use_frame'
                ? __collectScopedNodes(targetCard)
                : { scope: targetCard, nodes: Array.from(targetCard.querySelectorAll(
                    'button, [role=\"button\"], a[href], span, [aria-label], media-play-button'
                )) };
            for (const node of nodes) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const text = node.innerText || node.textContent || node.getAttribute('aria-label') || '';
                if (kind !== 'generic' && matchesScoped(kind, text, node)) {
                    const scopeName = kind === 'use_frame' ? 'below_video_band' : 'inside_card';
                    return { visible: true, matchedLabel: String(text).trim().slice(0, 80), scope: scopeName };
                }
                const lowered = __nodeLabelText(node);
                if (!lowered) continue;
                for (const label of targets) {
                    if (lowered === label || lowered.includes(label)) {
                        const scopeName = kind === 'use_frame' ? 'below_video_band' : 'inside_card';
                        return { visible: true, matchedLabel: lowered.slice(0, 80), scope: scopeName };
                    }
                }
            }
            if (kind === 'download') {
                const hasVideo = Boolean(targetCard.querySelector('video'));
                const hasApps = nodes.some((b) => __nodeLabelText(b) === 'apps');
                if (hasVideo && hasApps) {
                    return { visible: true, matchedLabel: 'Apps', scope: 'inside_card_download_entry' };
                }
            }
            return { visible: false, matchedLabel: '', scope: 'inside_card' };
        }""" % PhaseIArtifactTracker._scoped_label_match_eval_script().strip()

    @staticmethod
    def _media_urls_for_card_eval_script() -> str:
        return """({ cardFingerprint }) => {
            const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
            const cards = [];
            const actionButtons = Array.from(document.querySelectorAll('[aria-label*=\"Actions\"]'));
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
            for (const btn of actionButtons) {
                let card = btn;
                for (let depth = 0; depth < 12 && card; depth++) {
                    if (card.querySelector && card.querySelector('img, canvas, video, picture')) break;
                    card = card.parentElement;
                }
                if (!card) card = btn.parentElement || btn;
                cards.push({ card, fp: buildFp(card) });
            }
            const match = cards.find((item) => item.fp === cardFingerprint);
            if (!match || !match.card) return { urls: [] };
            const urls = [];
            const video = match.card.querySelector('video');
            if (video) {
                const src = video.currentSrc || video.src || '';
                if (src) urls.push(src);
            }
            for (const a of match.card.querySelectorAll('a[href]')) {
                const href = a.href || '';
                if (href && (/\\.mp4|video|download|blob:/i.test(href))) urls.push(href);
            }
            return { urls: Array.from(new Set(urls)).filter(Boolean).slice(0, 10) };
        }"""

    def scan_artifact_cards(self) -> list[dict[str, Any]]:
        if self.simulate:
            return [dict(card) for card in self._simulated_cards]

        if self.page is None:
            return []
        try:
            payload = self.page.evaluate(self._artifact_cards_eval_script())
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def snapshot_before_generation(self, *, phase: str) -> list[str]:
        cards = self.scan_artifact_cards()
        self._last_scan = cards
        self._snapshot_fps = {
            str(card.get("cardFingerprint") or "") for card in cards if card.get("cardFingerprint")
        }
        return list(self._snapshot_fps)

    def _card_from_raw(self, raw: dict[str, Any], *, role: str) -> PhaseIArtifactCard:
        bbox = {
            "x": float(raw.get("cardLeft") or 0),
            "y": float(raw.get("cardTop") or 0),
            "width": float(raw.get("cardWidth") or 0),
            "height": float(raw.get("cardHeight") or 0),
        }
        urls = raw.get("mediaUrls") or []
        if not isinstance(urls, list):
            urls = []
        return PhaseIArtifactCard(
            card_index=int(raw.get("cardIndex", -1)),
            card_fingerprint=str(raw.get("cardFingerprint") or ""),
            card_type=str(raw.get("cardType") or "unknown"),
            card_prompt_text=str(raw.get("cardPromptText") or "")[:500],
            bounding_box=bbox,
            buttons_visible=[str(b) for b in (raw.get("buttonsVisible") or [])][:20],
            media_src=str(raw.get("mediaSrc") or ""),
            media_urls=[str(u) for u in urls if u],
            role=role,
        )

    def _diff_new_cards(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fresh: list[dict[str, Any]] = []
        for card in cards:
            fp = str(card.get("cardFingerprint") or "")
            if not fp or fp in self._snapshot_fps:
                continue
            if fp in self._consumed_fingerprints:
                continue
            fresh.append(card)
        return fresh

    def assign_new_card(
        self,
        role: str,
        *,
        prefer_type: str = "",
        exclude_roles: tuple[str, ...] = (),
    ) -> PhaseIArtifactCard | None:
        cards = self.scan_artifact_cards()
        self._last_scan = cards
        candidates = self._diff_new_cards(cards)
        assigned_fps = {
            card.card_fingerprint
            for key, card in self.assignments.items()
            if key not in exclude_roles and card.card_fingerprint
        }

        def _ok(card: dict[str, Any]) -> bool:
            fp = str(card.get("cardFingerprint") or "")
            if not fp or fp in assigned_fps:
                return False
            if prefer_type and str(card.get("cardType") or "") != prefer_type:
                return False
            return True

        filtered = [card for card in candidates if _ok(card)]
        if not filtered:
            filtered = [card for card in cards if _ok(card)]

        if not filtered and self.simulate:
            self.simulate_add_card(
                card_type=prefer_type or "video",
                prompt_text=role,
                buttons=list(USE_FRAME_LABELS) + list(DOWNLOAD_LABELS),
            )
            cards = self.scan_artifact_cards()
            filtered = self._diff_new_cards(cards)

        if not filtered:
            self.ambiguity_notes.append(f"no_card_for_role:{role}")
            return None

        best = max(filtered, key=lambda c: float(c.get("cardBottom") or 0))
        artifact = self._card_from_raw(best, role=role)
        self.assignments[role] = artifact
        self._snapshot_fps.add(artifact.card_fingerprint)
        if role.startswith("clip_") and role.endswith("_video_card"):
            try:
                clip_index = int(role.split("_")[1])
                self.assign_latest_video_card_for_clip(clip_index, allow_new_card=False)
            except ValueError:
                pass
        return artifact

    def get_assigned(self, role: str) -> PhaseIArtifactCard | None:
        return self.assignments.get(role)

    @staticmethod
    def _fingerprint_document_top(card_fingerprint: str) -> float | None:
        parts = str(card_fingerprint or "").split("|")
        if len(parts) < 2:
            return None
        try:
            return float(parts[1])
        except ValueError:
            return None

    @classmethod
    def _raw_card_is_stale(cls, card: dict[str, Any]) -> bool:
        fp = str(card.get("cardFingerprint") or "")
        doc_top = cls._fingerprint_document_top(fp)
        if doc_top is not None and doc_top < 0:
            return True
        return False

    def _pick_latest_video_card_raw(
        self,
        *,
        exclude_roles: tuple[str, ...] = (),
    ) -> dict[str, Any] | None:
        cards = self.scan_artifact_cards()
        self._last_scan = cards
        exclude_fps: set[str] = set(self._consumed_fingerprints)
        for key, assigned in self.assignments.items():
            if key in exclude_roles:
                continue
            if assigned.card_fingerprint:
                exclude_fps.add(assigned.card_fingerprint)
        starter = self.assignments.get(ROLE_STARTER_IMAGE)
        if starter and starter.card_fingerprint:
            exclude_fps.add(starter.card_fingerprint)

        video_cards = [
            card
            for card in cards
            if str(card.get("cardType") or "") == "video"
            and str(card.get("cardFingerprint") or "") not in exclude_fps
            and not self._raw_card_is_stale(card)
        ]
        if not video_cards:
            return None
        return max(video_cards, key=lambda c: float(c.get("cardBottom") or 0))

    def _pick_video_card_for_clip_index(self, clip_index: int) -> dict[str, Any] | None:
        """Prefer the output card whose prompt label matches clip N."""
        index = max(1, int(clip_index))
        cards = self.scan_artifact_cards()
        self._last_scan = cards
        exclude_fps: set[str] = set(self._consumed_fingerprints)
        for key, assigned in self.assignments.items():
            if key == ROLE_STARTER_IMAGE:
                continue
            if assigned.card_fingerprint:
                exclude_fps.add(assigned.card_fingerprint)
        starter = self.assignments.get(ROLE_STARTER_IMAGE)
        if starter and starter.card_fingerprint:
            exclude_fps.add(starter.card_fingerprint)

        marker = f"clip {index} of"
        alt_marker = f"clip {index}/"
        video_cards = [
            card
            for card in cards
            if str(card.get("cardType") or "") == "video"
            and str(card.get("cardFingerprint") or "") not in exclude_fps
            and not self._raw_card_is_stale(card)
        ]
        if not video_cards:
            return None

        def _score(card: dict[str, Any]) -> tuple[int, float]:
            text = str(card.get("cardPromptText") or "").lower()
            marker_hit = 0
            if marker in text:
                marker_hit = 2
            elif alt_marker in text or f"clip_{index}" in text.replace(" ", ""):
                marker_hit = 1
            return (marker_hit, float(card.get("cardBottom") or 0))

        ranked = sorted(video_cards, key=_score, reverse=True)
        best_score = _score(ranked[0])[0]
        if best_score > 0:
            return ranked[0]
        return None

    def assign_latest_video_card_for_clip(
        self,
        clip_index: int,
        *,
        allow_new_card: bool = True,
    ) -> PhaseIArtifactCard | None:
        """Detect/assign clip N video card and mirror as latest_video_card for scoped controls."""
        from content_brain.execution.runway_phase_i_strict_completion_gate import (
            card_text_matches_clip_index,
        )

        index = max(1, int(clip_index))
        clip_count = int(getattr(self, "_phase_i_clip_count", 3) or 3)
        clip_role = self.clip_video_role(index)
        card = self.assignments.get(clip_role)
        if card is not None and self._fingerprint_document_top(card.card_fingerprint) is not None:
            if self._fingerprint_document_top(card.card_fingerprint) < 0:
                card = None
                self.assignments.pop(clip_role, None)
        if card is not None and card.card_fingerprint and index >= 2 and not self.simulate:
            cards = self.scan_artifact_cards()
            raw = next(
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
            if not card_text_matches_clip_index(raw, index, clip_count=clip_count):
                self.assignments.pop(clip_role, None)
                card = None
        if card is None:
            raw = self._pick_video_card_for_clip_index(index)
            if raw is None:
                raw = self._pick_latest_video_card_raw()
                if raw is not None and index >= 2 and not self.simulate and not card_text_matches_clip_index(
                    raw, index, clip_count=clip_count
                ):
                    raw = None
            if raw is not None:
                card = self._card_from_raw(raw, role=clip_role)
                self.assignments[clip_role] = card
                self._snapshot_fps.add(card.card_fingerprint)
            elif allow_new_card:
                card = self.assign_new_card(clip_role, prefer_type="video")
        if card is None:
            self.ambiguity_notes.append(f"latest_video_card_missing:clip_{index}")
            return None
        latest = PhaseIArtifactCard(
            card_index=card.card_index,
            card_fingerprint=card.card_fingerprint,
            card_type=card.card_type,
            card_prompt_text=card.card_prompt_text,
            bounding_box=dict(card.bounding_box),
            buttons_visible=list(card.buttons_visible),
            media_src=card.media_src,
            media_urls=list(card.media_urls),
            role=ROLE_LATEST_VIDEO,
            consumed=card.consumed,
        )
        self.assignments[ROLE_LATEST_VIDEO] = latest
        return card

    def get_latest_video_card(self) -> PhaseIArtifactCard | None:
        return self.assignments.get(ROLE_LATEST_VIDEO)

    @staticmethod
    def _label_kind_for(labels: tuple[str, ...]) -> str:
        blob = " ".join(labels).lower()
        if "use frame" in blob:
            return "use_frame"
        if "download" in blob or "mp4" in blob:
            return "download"
        if "play" in blob or "pause" in blob:
            return "playback"
        return "generic"

    def label_visible_on_latest_video_card(self, labels: tuple[str, ...]) -> bool:
        """Scoped visibility inside latest_video_card only (never global)."""
        return self.label_visible_on_assigned_card(ROLE_LATEST_VIDEO, labels)

    def audit_control_scope(self, card_fingerprint: str, *, label_kind: str) -> dict[str, Any]:
        """Audit global vs in-card control matches; PASS when no leaks outside card."""
        empty: dict[str, Any] = {
            "cardFound": False,
            "labelKind": label_kind,
            "globalMatches": 0,
            "inCardMatches": 0,
            "leakedGlobalMatches": 0,
            "globalSamples": [],
            "inCardSamples": [],
            "leakedSamples": [],
            "inCardOperational": False,
            "scopedOk": False,
        }
        if not card_fingerprint:
            return empty
        if self.simulate:
            return {
                **empty,
                "cardFound": True,
                "inCardMatches": 1,
                "inCardOperational": True,
                "scopedOk": True,
            }
        if self.page is None:
            return empty
        try:
            payload = self.page.evaluate(
                self.control_scope_audit_eval_script(),
                {"cardFingerprint": card_fingerprint, "labelKind": label_kind},
            )
        except Exception as exc:
            empty["error"] = str(exc)
            return empty
        if isinstance(payload, dict):
            return payload
        return empty

    def click_label_on_latest_video_card(self, labels: tuple[str, ...]) -> bool:
        """Scoped click inside latest_video_card only (never global)."""
        return self.click_label_on_assigned_card(ROLE_LATEST_VIDEO, labels)

    def label_visible_on_assigned_card(self, role: str, labels: tuple[str, ...]) -> bool:
        """True only if label exists on buttons inside the assigned card (not global)."""
        card = self.get_assigned(role)
        if card is None or not card.card_fingerprint:
            return False
        if self.simulate:
            lowered = [label.lower() for label in labels]
            for button in card.buttons_visible:
                text = str(button).lower()
                if any(target in text or text == target for target in lowered):
                    return True
            return False
        if self.page is None:
            return False
        try:
            payload = self.page.evaluate(
                self._label_visible_in_card_eval_script(),
                {
                    "cardFingerprint": card.card_fingerprint,
                    "labels": list(labels),
                    "labelKind": self._label_kind_for(labels),
                },
            )
        except Exception:
            return False
        if isinstance(payload, dict):
            return bool(payload.get("visible"))
        return False

    def mark_consumed(self, role: str) -> None:
        card = self.assignments.get(role)
        if card is None:
            return
        card.consumed = True
        if card.card_fingerprint:
            self._consumed_fingerprints.add(card.card_fingerprint)

    def ensure_starter_not_used_for_clip_ops(self, clip_index: int) -> None:
        starter = self.assignments.get(ROLE_STARTER_IMAGE)
        clip_role = self.clip_video_role(clip_index)
        clip_card = self.assignments.get(clip_role)
        if starter and clip_card and starter.card_fingerprint == clip_card.card_fingerprint:
            raise ValueError(
                f"clip {clip_index} card fingerprint matches starter image card — mis-scoped"
            )

    def refresh_assigned_card_from_scan(self, clip_index: int) -> PhaseIArtifactCard | None:
        """Re-resolve clip N card fingerprint after scroll/layout shifts."""
        from content_brain.execution.runway_phase_i_strict_completion_gate import (
            card_text_matches_clip_index,
        )

        index = max(1, int(clip_index))
        clip_count = int(getattr(self, "_phase_i_clip_count", 3) or 3)
        role = self.clip_video_role(index)
        raw = self._pick_video_card_for_clip_index(index)
        if raw is None:
            return self.assignments.get(role)
        if index >= 2 and not self.simulate and not card_text_matches_clip_index(
            raw, index, clip_count=clip_count
        ):
            return self.assignments.get(role)
        artifact = self._card_from_raw(raw, role=role)
        self.assignments[role] = artifact
        if artifact.card_fingerprint:
            self._snapshot_fps.add(artifact.card_fingerprint)
        latest = PhaseIArtifactCard(
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
        self.assignments[ROLE_LATEST_VIDEO] = latest
        return artifact

    def click_label_on_assigned_card(self, role: str, labels: tuple[str, ...]) -> bool:
        card = self.get_assigned(role)
        if card is None or not card.card_fingerprint:
            return False
        if self.simulate:
            return True
        if self.page is None:
            return False
        use_frame_mode = any("use frame" in str(label).lower() for label in labels)
        try:
            clicked = self.page.evaluate(
                self._click_label_in_card_eval_script(),
                {"cardFingerprint": card.card_fingerprint, "labels": list(labels)},
            )
            if clicked:
                return True
        except Exception:
            clicked = False
        if use_frame_mode:
            return self._playwright_click_use_frame_in_card(card.card_fingerprint)
        return False

    def _playwright_click_use_frame_in_card(self, card_fingerprint: str) -> bool:
        if self.page is None:
            return False
        try:
            payload = self.page.evaluate(
                self._locate_use_frame_button_eval_script(),
                {"cardFingerprint": card_fingerprint},
            )
        except Exception:
            return False
        if not isinstance(payload, dict) or not payload.get("found"):
            return False
        try:
            x = float(payload.get("x") or 0)
            y = float(payload.get("y") or 0)
        except (TypeError, ValueError):
            return False
        if x <= 0 or y <= 0:
            return False
        try:
            self.page.mouse.move(x, y)
            self.page.mouse.click(x, y)
            return True
        except Exception:
            return False

    def extract_media_urls_for_role(self, role: str) -> list[str]:
        card = self.get_assigned(role)
        if card is None:
            return []
        if card.media_urls:
            return list(card.media_urls)
        if self.simulate:
            return [str(u) for u in card.media_urls if u]
        if self.page is None or not card.card_fingerprint:
            return []
        try:
            payload = self.page.evaluate(
                self._media_urls_for_card_eval_script(),
                {"cardFingerprint": card.card_fingerprint},
            )
        except Exception:
            return []
        if isinstance(payload, dict):
            urls = payload.get("urls") or []
            if isinstance(urls, list):
                card.media_urls = [str(u) for u in urls if u]
                return card.media_urls
        return []

    def simulate_add_card(
        self,
        *,
        card_type: str,
        prompt_text: str = "",
        buttons: list[str] | None = None,
    ) -> str:
        index = len(self._simulated_cards)
        fp = f"sim|{card_type}|{index}|{prompt_text[:40]}"
        self._simulated_cards.append(
            {
                "cardIndex": index,
                "cardFingerprint": fp,
                "cardType": card_type,
                "cardPromptText": prompt_text,
                "cardTop": 100 + index * 120,
                "cardBottom": 200 + index * 120,
                "cardLeft": 20,
                "cardWidth": 260,
                "cardHeight": 100,
                "buttonsVisible": buttons or [],
                "mediaSrc": f"https://simulate.runway/{card_type}_{index}.mp4",
                "mediaUrls": [f"https://simulate.runway/{card_type}_{index}.mp4"],
                "hasAppMenu": True,
            }
        )
        return fp

    def write_diagnostics(self, *, context: str, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "context": context,
            "project_id": self.project_id,
            "snapshot_fingerprints": sorted(self._snapshot_fps),
            "last_scan": self._last_scan,
            "assignments": {k: v.to_dict() for k, v in self.assignments.items()},
            "ambiguity_notes": list(self.ambiguity_notes),
        }
        if extra:
            payload.update(extra)
        DEFAULT_ARTIFACT_CARD_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_ARTIFACT_CARD_DIAGNOSTICS.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def to_report_summary(self) -> dict[str, Any]:
        return {
            "assignments": {k: v.to_dict() for k, v in self.assignments.items()},
            "ambiguity_notes": list(self.ambiguity_notes),
        }


__all__ = [
    "DEFAULT_ARTIFACT_CARD_DIAGNOSTICS",
    "DOWNLOAD_LABELS",
    "PLAYBACK_LABELS",
    "PhaseIArtifactCard",
    "PhaseIArtifactTracker",
    "ROLE_CLIP_VIDEO",
    "ROLE_LATEST_VIDEO",
    "ROLE_STARTER_IMAGE",
    "USE_FRAME_LABELS",
]
