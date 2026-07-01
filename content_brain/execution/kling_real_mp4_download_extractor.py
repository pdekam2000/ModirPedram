"""Kling real MP4 download/recovery — reject placeholders, require ffprobe-valid MP4."""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from content_brain.execution.kling_multishot_live_engine import (
    MIN_REAL_MP4_BYTES,
    _collect_performance_media_urls,
    _collect_video_source_urls,
    _fetch_blob_via_page,
    _fetch_http_via_page,
    _fetch_via_page_request,
    _probe_video_metadata,
    _try_ui_download,
    _write_binary_payload,
    verify_recovered_mp4,
)
from content_brain.execution.runway_phase_i_artifact_tracker import (
    DOWNLOAD_LABELS,
    DOWNLOAD_SCOPED_ENTRY_LABELS,
    ROLE_LATEST_VIDEO,
    PhaseIArtifactCard,
    PhaseIArtifactTracker,
)
from content_brain.execution.runway_phase_i_download_tracker import (
    RunwayPhaseIDownloadTracker,
    default_runway_download_dir,
)

ROOT = Path(__file__).resolve().parents[2]
EXTRACTOR_VERSION = "kling_real_mp4_download_extractor_v2"
MIN_EXTRACT_DURATION_SECONDS = 5.0
QUARANTINE_DIRNAME = "quarantine"
MP4_RECOVERY_POLL_INTERVAL_SECONDS = 10
MP4_RECOVERY_POLL_MAX_SECONDS = 300

PLACEHOLDER_URL_MARKERS = (
    "empty-state",
    "studio-empty",
    "/app/empty",
    "placeholder",
    "empty_state",
    "empty-states",
    "edit-studio-empty-state",
)

PLACEHOLDER_CARD_TEXT_MARKERS = (
    "empty state",
    "no generations",
    "generate your first",
    "studio empty",
    "nothing here yet",
)

PREFERRED_URL_MARKERS = (
    "kling-3-0-pro",
    "kling-3",
    "/kling",
    ".mp4",
    "mime_type=video",
)


@dataclass
class ExtractMethodAttempt:
    method: str
    ok: bool
    detail: str = ""
    candidate_path: str = ""
    verify: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "ok": self.ok,
            "detail": self.detail,
            "candidate_path": self.candidate_path,
            "verify": dict(self.verify),
        }


@dataclass
class KlingRealMp4ExtractResult:
    ok: bool
    output_path: str = ""
    attempted_methods: list[str] = field(default_factory=list)
    method_attempts: list[ExtractMethodAttempt] = field(default_factory=list)
    quarantined_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recovery_mode: bool = False
    card_selection: dict[str, Any] = field(default_factory=dict)
    poll_attempts: list[dict[str, Any]] = field(default_factory=list)
    poll_elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": EXTRACTOR_VERSION,
            "ok": self.ok,
            "output_path": self.output_path,
            "attempted_methods": list(self.attempted_methods),
            "method_attempts": [item.to_dict() for item in self.method_attempts],
            "quarantined_paths": list(self.quarantined_paths),
            "errors": list(self.errors),
            "recovery_mode": self.recovery_mode,
            "card_selection": dict(self.card_selection),
            "poll_attempts": list(self.poll_attempts),
            "poll_elapsed_seconds": self.poll_elapsed_seconds,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_rejected_placeholder_url(url: str) -> bool:
    cleaned = str(url or "").strip().lower()
    if not cleaned:
        return True
    return any(marker in cleaned for marker in PLACEHOLDER_URL_MARKERS)


def is_rejected_placeholder_card(raw: dict[str, Any]) -> bool:
    text = str(raw.get("cardPromptText") or raw.get("cardText") or "").lower()
    if any(marker in text for marker in PLACEHOLDER_CARD_TEXT_MARKERS):
        return True
    if is_rejected_placeholder_url(str(raw.get("mediaSrc") or "")):
        return True
    for url in raw.get("mediaUrls") or []:
        if is_rejected_placeholder_url(str(url)):
            return True
    return False


def card_has_visible_video_preview(raw: dict[str, Any]) -> bool:
    if str(raw.get("cardType") or "") != "video":
        return False
    media = str(raw.get("mediaSrc") or "").strip()
    if not media:
        for url in raw.get("mediaUrls") or []:
            candidate = str(url or "").strip()
            if candidate and not is_rejected_placeholder_url(candidate):
                media = candidate
                break
    if not media or is_rejected_placeholder_url(media):
        return False
    return True


def rank_video_artifact_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _score(card: dict[str, Any]) -> tuple[int, float]:
        score = 0
        if card.get("selected"):
            score += 50
        if card_has_visible_video_preview(card):
            score += 100
        return score, float(card.get("cardBottom") or 0)

    eligible = [
        card
        for card in cards
        if str(card.get("cardType") or "") == "video"
        and not is_rejected_placeholder_card(card)
        and card_has_visible_video_preview(card)
    ]
    return sorted(eligible, key=_score, reverse=True)


def resolve_scoped_video_card_for_extraction(
    tracker: PhaseIArtifactTracker,
    clip_index: int,
    *,
    exclude_signatures: list[dict[str, Any]] | None = None,
    require_new_artifact: bool = False,
    baseline_video_card_count: int = 0,
    baseline_card_fingerprints: list[str] | None = None,
) -> tuple[PhaseIArtifactCard | None, dict[str, Any]]:
    """Pick newest/current video artifact card; reject placeholder / empty-state cards."""
    from content_brain.execution.kling_useframe_generation_completion_gate import (
        artifact_signature_from_card,
        find_new_artifact_candidate,
        is_duplicate_artifact,
    )
    cards = tracker.scan_artifact_cards()
    rejected: list[dict[str, Any]] = []
    video_candidates: list[dict[str, Any]] = []

    for card in cards:
        if is_rejected_placeholder_card(card):
            rejected.append(
                {
                    "card_fingerprint": str(card.get("cardFingerprint") or "")[:80],
                    "card_type": str(card.get("cardType") or ""),
                    "reason": "placeholder_card",
                }
            )
            continue
        if str(card.get("cardType") or "") != "video":
            continue
        if not card_has_visible_video_preview(card):
            rejected.append(
                {
                    "card_fingerprint": str(card.get("cardFingerprint") or "")[:80],
                    "card_type": "video",
                    "reason": "no_visible_video_preview",
                }
            )
            continue
        video_candidates.append(card)

    meta: dict[str, Any] = {
        "card_count": len(cards),
        "video_card_count": len(video_candidates),
        "rejected_cards": rejected,
        "selected_card": None,
        "selection_strategy": "newest_visible_video_card",
    }

    if require_new_artifact and exclude_signatures:
        new_sig, selection_meta = find_new_artifact_candidate(
            cards=video_candidates,
            prior_artifacts=list(exclude_signatures),
            baseline_video_card_count=baseline_video_card_count,
            baseline_fingerprints=list(baseline_card_fingerprints or []),
        )
        meta["new_artifact_selection"] = selection_meta
        if new_sig:
            fp = str(new_sig.get("card_fingerprint") or "")
            selected_raw = next(
                (card for card in video_candidates if str(card.get("cardFingerprint") or "") == fp),
                None,
            )
            if selected_raw is None:
                selected_raw = next(
                    (
                        card
                        for card in video_candidates
                        if not is_duplicate_artifact(artifact_signature_from_card(card), exclude_signatures)[0]
                    ),
                    None,
                )
            meta["selection_strategy"] = "new_non_duplicate_artifact"
        else:
            selected_raw = None
    else:
        ranked = rank_video_artifact_cards(video_candidates)
        selected_raw = ranked[0] if ranked else None
        if selected_raw is not None and exclude_signatures:
            duplicate, reason = is_duplicate_artifact(artifact_signature_from_card(selected_raw), exclude_signatures)
            if duplicate:
                rejected.append(
                    {
                        "card_fingerprint": str(selected_raw.get("cardFingerprint") or "")[:80],
                        "card_type": "video",
                        "reason": f"duplicate_prior_clip:{reason}",
                    }
                )
                selected_raw = next(
                    (
                        card
                        for card in rank_video_artifact_cards(video_candidates)
                        if not is_duplicate_artifact(artifact_signature_from_card(card), exclude_signatures)[0]
                    ),
                    None,
                )
                if selected_raw is not None:
                    meta["selection_strategy"] = "newest_non_duplicate_video_card"
    if selected_raw is None:
        if require_new_artifact:
            return None, meta
        fallback = tracker.assign_latest_video_card_for_clip(clip_index)
        if fallback is None:
            fallback = tracker.refresh_assigned_card_from_scan(clip_index)
        if fallback is not None:
            meta["selected_card"] = fallback.to_dict()
            meta["selection_strategy"] = "tracker_fallback"
        return fallback, meta

    clip_role = PhaseIArtifactTracker.clip_video_role(clip_index)
    card = tracker._card_from_raw(selected_raw, role=clip_role)
    tracker.assignments[clip_role] = card
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
    tracker.assignments[ROLE_LATEST_VIDEO] = latest
    meta["selected_card"] = latest.to_dict()
    return latest, meta


def score_media_url(url: str) -> int:
    cleaned = str(url or "").strip()
    if not cleaned or is_rejected_placeholder_url(cleaned):
        return -1000
    score = 0
    lowered = cleaned.lower()
    if lowered.startswith("blob:"):
        score += 40
    for marker in PREFERRED_URL_MARKERS:
        if marker in lowered:
            score += 30
    if lowered.endswith(".mp4") or ".mp4?" in lowered:
        score += 50
    if "cloudfront.net" in lowered:
        score += 10
    if lowered.endswith(".webm") or ".webm?" in lowered:
        score -= 20
    return score


def sort_media_urls(urls: list[str]) -> list[str]:
    ranked = sorted(
        {str(url).strip() for url in urls if str(url).strip()},
        key=lambda item: (-score_media_url(item), item),
    )
    return [url for url in ranked if score_media_url(url) > -1000]


def inspect_file_candidate(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    result: dict[str, Any] = {
        "path": str(target),
        "exists": target.is_file(),
        "size_bytes": 0,
        "header_hex": "",
        "container": "missing",
        "mime_guess": "unknown",
    }
    if not target.is_file():
        return result
    size = target.stat().st_size
    result["size_bytes"] = size
    head = target.read_bytes()[:64]
    result["header_hex"] = head[:16].hex()
    if len(head) >= 12 and head[4:8] == b"ftyp":
        result["container"] = "mp4"
        result["mime_guess"] = "video/mp4"
    elif head[:4] == b"\x1a\x45\xdf\xa3":
        result["container"] = "webm"
        result["mime_guess"] = "video/webm"
    elif head[:5].lower().startswith(b"<!doc") or head[:6].lower().startswith(b"<html"):
        result["container"] = "html"
        result["mime_guess"] = "text/html"
    elif size <= 4096:
        result["container"] = "tiny"
        result["mime_guess"] = "placeholder"
    else:
        result["container"] = "unknown"
    return result


def is_mp4_container(path: str | Path) -> bool:
    return inspect_file_candidate(path).get("container") == "mp4"


def verify_extracted_kling_mp4(path: str | Path) -> dict[str, Any]:
    """Stricter than verify_recovered_mp4: MP4 container, >1MB, ffprobe, duration >= 5s."""
    target = Path(path)
    inspect = inspect_file_candidate(target)
    base = verify_recovered_mp4(target)
    duration = float(base.get("duration_seconds") or 0)
    container_ok = is_mp4_container(target)
    duration_ok = duration >= MIN_EXTRACT_DURATION_SECONDS
    is_real = (
        bool(base.get("exists"))
        and int(base.get("size_bytes") or 0) >= MIN_REAL_MP4_BYTES
        and bool(base.get("ffprobe_ok"))
        and container_ok
        and duration_ok
        and not bool(base.get("is_placeholder"))
    )
    merged = dict(base)
    merged.update(
        {
            "inspect": inspect,
            "container_ok": container_ok,
            "duration_ok": duration_ok,
            "min_duration_seconds": MIN_EXTRACT_DURATION_SECONDS,
            "is_real_mp4": is_real,
        }
    )
    return merged


def quarantine_invalid_candidate(path: str | Path, clip_dir: Path) -> str:
    src = Path(path)
    if not src.is_file():
        return ""
    quarantine = clip_dir / QUARANTINE_DIRNAME
    quarantine.mkdir(parents=True, exist_ok=True)
    inspect = inspect_file_candidate(src)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    dest = quarantine / f"invalid_{stamp}_{src.name}"
    try:
        if src.resolve() != dest.resolve():
            shutil.move(str(src), str(dest))
    except OSError:
        try:
            shutil.copy2(src, dest)
            src.unlink(missing_ok=True)
        except OSError:
            return ""
    meta_path = dest.with_suffix(dest.suffix + ".inspect.json")
    meta_path.write_text(json.dumps(inspect, indent=2), encoding="utf-8")
    return str(dest.resolve()).replace("\\", "/")


def _record_attempt(
    result: KlingRealMp4ExtractResult,
    *,
    method: str,
    ok: bool,
    detail: str = "",
    candidate: Path | None = None,
    verify: dict[str, Any] | None = None,
) -> None:
    result.attempted_methods.append(method)
    result.method_attempts.append(
        ExtractMethodAttempt(
            method=method,
            ok=ok,
            detail=detail,
            candidate_path=str(candidate.resolve()) if candidate and candidate.is_file() else "",
            verify=dict(verify or {}),
        )
    )


def _accept_candidate(
    *,
    candidate: Path,
    dest: Path,
    clip_dir: Path,
    result: KlingRealMp4ExtractResult,
    method: str,
    gate_context: Any | None = None,
) -> Path | None:
    if not candidate.is_file():
        _record_attempt(result, method=method, ok=False, detail="candidate_missing")
        return None
    if gate_context is not None and getattr(gate_context, "require_new_artifact", False):
        from content_brain.execution.kling_useframe_generation_completion_gate import (
            is_duplicate_artifact,
            sha256_file,
        )

        candidate_sig = {"file_hash": sha256_file(candidate), "media_urls": [], "media_src": ""}
        duplicate, reason = is_duplicate_artifact(candidate_sig, gate_context.prior_artifact_signatures)
        if duplicate:
            quarantined = quarantine_invalid_candidate(candidate, clip_dir)
            if quarantined:
                result.quarantined_paths.append(quarantined)
            _record_attempt(result, method=method, ok=False, detail=f"duplicate_prior_clip:{reason}")
            result.errors.append(f"{method}:duplicate_prior_clip:{reason}")
            return None
    verify = verify_extracted_kling_mp4(candidate)
    if verify.get("is_real_mp4"):
        dest.parent.mkdir(parents=True, exist_ok=True)
        if candidate.resolve() != dest.resolve():
            shutil.copy2(candidate, dest)
        _record_attempt(result, method=method, ok=True, detail="real_mp4", candidate=dest, verify=verify)
        result.output_path = str(dest.resolve()).replace("\\", "/")
        result.ok = True
        return dest
    inspect = inspect_file_candidate(candidate)
    quarantined = quarantine_invalid_candidate(candidate, clip_dir)
    if quarantined:
        result.quarantined_paths.append(quarantined)
    detail = (
        f"rejected container={inspect.get('container')} size={inspect.get('size_bytes')} "
        f"duration={verify.get('duration_seconds')} header={inspect.get('header_hex')}"
    )
    _record_attempt(result, method=method, ok=False, detail=detail, candidate=candidate, verify=verify)
    result.errors.append(f"{method}:{detail}")
    return None


def _fetch_url_to_candidate(page: Any, url: str, dest: Path) -> Path | None:
    if is_rejected_placeholder_url(url):
        return None
    if url.startswith("blob:"):
        return _fetch_blob_via_page(page, url, dest)
    if url.startswith("http"):
        fetched = _fetch_http_via_page(page, url, dest)
        if fetched is None:
            fetched = _fetch_via_page_request(page, url, dest)
        return fetched
    return None


def _resolve_kwargs_from_gate(gate_context: Any | None) -> dict[str, Any]:
    if gate_context is None or not getattr(gate_context, "require_new_artifact", False):
        return {}
    return {
        "exclude_signatures": list(gate_context.prior_artifact_signatures or []),
        "require_new_artifact": True,
        "baseline_video_card_count": int(gate_context.baseline_video_card_count or 0),
        "baseline_card_fingerprints": list(gate_context.baseline_card_fingerprints or []),
    }


def _method_artifact_card_cdp_urls(
    page: Any,
    *,
    tracker: PhaseIArtifactTracker,
    clip_index: int,
    dest: Path,
    clip_dir: Path,
    result: KlingRealMp4ExtractResult,
    session_id: str,
    gate_context: Any | None = None,
) -> Path | None:
    from content_brain.execution.runway_phase_i_cdp_download import (
        RunwayPhaseICdpDownloadConfig,
        RunwayPhaseICdpDownloader,
    )

    card, card_meta = resolve_scoped_video_card_for_extraction(
        tracker,
        clip_index,
        **_resolve_kwargs_from_gate(gate_context),
    )
    result.card_selection = dict(card_meta)
    if card is None:
        _record_attempt(result, method="artifact_card_cdp_urls", ok=False, detail="no_video_card")
        return None

    role = PhaseIArtifactTracker.clip_video_role(clip_index)
    urls = sort_media_urls(tracker.extract_media_urls_for_role(role))
    if not urls:
        urls = sort_media_urls(list(card.media_urls or []))
    if not urls:
        _record_attempt(result, method="artifact_card_cdp_urls", ok=False, detail="no_urls_on_card")
        return None

    downloader = RunwayPhaseICdpDownloader(
        download_dir=clip_dir,
        tracker=tracker,
        page=page,
        config=RunwayPhaseICdpDownloadConfig(session_id=session_id, fallback_to_ui_download=False),
    )

    for index, url in enumerate(urls):
        if is_rejected_placeholder_url(url):
            _record_attempt(
                result,
                method=f"artifact_card_cdp_urls:skip_url_{index}",
                ok=False,
                detail=f"placeholder_url:{url[:120]}",
            )
            continue
        candidate = clip_dir / f"fetch_candidate_{index}.mp4"
        fetched = _fetch_url_to_candidate(page, url, candidate)
        if fetched is None:
            _record_attempt(
                result,
                method=f"artifact_card_cdp_urls:fetch_{index}",
                ok=False,
                detail=f"fetch_failed:{url[:120]}",
            )
            continue
        accepted = _accept_candidate(
            candidate=fetched,
            dest=dest,
            clip_dir=clip_dir,
            result=result,
            method=f"artifact_card_cdp_urls:verify_{index}",
            gate_context=gate_context,
        )
        if accepted is not None:
            return accepted

    _record_attempt(result, method="artifact_card_cdp_urls", ok=False, detail="all_urls_rejected")
    return None


def _method_scoped_card_browser_download(
    page: Any,
    *,
    tracker: PhaseIArtifactTracker,
    clip_index: int,
    dest: Path,
    clip_dir: Path,
    result: KlingRealMp4ExtractResult,
    gate_context: Any | None = None,
) -> Path | None:
    tracker.assign_latest_video_card_for_clip(clip_index)
    tracker.refresh_assigned_card_from_scan(clip_index)
    card, card_meta = resolve_scoped_video_card_for_extraction(
        tracker,
        clip_index,
        **_resolve_kwargs_from_gate(gate_context),
    )
    result.card_selection = dict(card_meta)

    download_dir = default_runway_download_dir(ROOT)
    dir_tracker = RunwayPhaseIDownloadTracker(download_dir)
    baseline = set(dir_tracker._baseline.keys())

    def _save_download(download: Any) -> Path | None:
        candidate = clip_dir / f"browser_download_{int(time.time())}.mp4"
        try:
            download.save_as(str(candidate))
        except Exception as exc:
            _record_attempt(result, method="scoped_card_browser_download", ok=False, detail=f"save_failed:{exc}")
            return None
        return candidate

    try:
        if tracker.click_label_on_assigned_card(ROLE_LATEST_VIDEO, DOWNLOAD_SCOPED_ENTRY_LABELS):
            time.sleep(0.45)
            for label in ("Download MP4", "Download", "MP4"):
                try:
                    menu_item = page.get_by_role("menuitem", name=re.compile(re.escape(label), re.I))
                    if menu_item.count() > 0 and menu_item.first.is_visible():
                        with page.expect_download(timeout=120_000) as dl_info:
                            menu_item.first.click(timeout=10_000)
                        candidate = _save_download(dl_info.value)
                        if candidate is not None:
                            accepted = _accept_candidate(
                                candidate=candidate,
                                dest=dest,
                                clip_dir=clip_dir,
                                result=result,
                                method="scoped_card_browser_download:apps_menu",
                                gate_context=gate_context,
                            )
                            if accepted is not None:
                                return accepted
                except Exception:
                    continue
    except Exception as exc:
        _record_attempt(result, method="scoped_card_browser_download:apps", ok=False, detail=str(exc)[:200])

    try:
        with page.expect_download(timeout=120_000) as dl_info:
            if tracker.click_label_on_latest_video_card(DOWNLOAD_LABELS):
                time.sleep(0.2)
            else:
                raise RuntimeError("scoped_download_label_not_clicked")
        candidate = _save_download(dl_info.value)
        if candidate is not None:
            accepted = _accept_candidate(
                candidate=candidate,
                dest=dest,
                clip_dir=clip_dir,
                result=result,
                method="scoped_card_browser_download:card_label",
                gate_context=gate_context,
            )
            if accepted is not None:
                return accepted
    except Exception as exc:
        _record_attempt(
            result,
            method="scoped_card_browser_download:card_label",
            ok=False,
            detail=str(exc)[:200],
        )

    record = dir_tracker.verify_clip_download(clip_index)
    if record.downloaded and record.file_path:
        candidate = Path(record.file_path)
        accepted = _accept_candidate(
            candidate=candidate,
            dest=dest,
            clip_dir=clip_dir,
            result=result,
            method="scoped_card_browser_download:download_dir",
            gate_context=gate_context,
        )
        if accepted is not None:
            return accepted

    new_files = [
        Path(path)
        for path in dir_tracker._baseline.keys()
        if path not in baseline and Path(path).is_file()
    ]
    for candidate in sorted(new_files, key=lambda p: p.stat().st_mtime, reverse=True):
        accepted = _accept_candidate(
            candidate=candidate,
            dest=dest,
            clip_dir=clip_dir,
            result=result,
            method="scoped_card_browser_download:download_dir_new",
            gate_context=gate_context,
        )
        if accepted is not None:
            return accepted

    _record_attempt(result, method="scoped_card_browser_download", ok=False, detail="no_valid_browser_download")
    return None


def _method_page_video_sources(
    page: Any,
    *,
    dest: Path,
    clip_dir: Path,
    result: KlingRealMp4ExtractResult,
    gate_context: Any | None = None,
) -> Path | None:
    urls = sort_media_urls(_collect_video_source_urls(page) + _collect_performance_media_urls(page))
    for index, url in enumerate(urls[:12]):
        candidate = clip_dir / f"page_video_{index}.mp4"
        fetched = _fetch_url_to_candidate(page, url, candidate)
        if fetched is None:
            continue
        accepted = _accept_candidate(
            candidate=fetched,
            dest=dest,
            clip_dir=clip_dir,
            result=result,
            method=f"page_video_sources:{index}",
            gate_context=gate_context,
        )
        if accepted is not None:
            return accepted
    _record_attempt(result, method="page_video_sources", ok=False, detail="no_valid_page_video")
    return None


def _method_global_ui_download(
    page: Any,
    *,
    dest: Path,
    clip_dir: Path,
    result: KlingRealMp4ExtractResult,
    gate_context: Any | None = None,
) -> Path | None:
    candidate = clip_dir / "ui_download_global.mp4"
    ui_dest, strategy = _try_ui_download(page, candidate)
    if ui_dest is None:
        _record_attempt(result, method="global_ui_download", ok=False, detail="ui_click_failed")
        return None
    return _accept_candidate(
        candidate=ui_dest,
        dest=dest,
        clip_dir=clip_dir,
        result=result,
        method=f"global_ui_download:{strategy or 'unknown'}",
        gate_context=gate_context,
    )


def _write_extract_reports(
    result: KlingRealMp4ExtractResult,
    *,
    clip_dir: Path,
    run_id: str,
    clip_index: int,
    dest: Path,
) -> None:
    payload = result.to_dict()
    payload["run_id"] = run_id
    payload["clip_index"] = clip_index
    payload["dest"] = str(dest)
    payload["finished_at"] = _now_iso()
    (clip_dir / "mp4_extract_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if result.poll_attempts:
        poll_payload = {
            "version": EXTRACTOR_VERSION,
            "run_id": run_id,
            "clip_index": clip_index,
            "poll_interval_seconds": MP4_RECOVERY_POLL_INTERVAL_SECONDS,
            "poll_max_seconds": MP4_RECOVERY_POLL_MAX_SECONDS,
            "poll_elapsed_seconds": result.poll_elapsed_seconds,
            "valid_mp4_found": result.ok,
            "attempts": list(result.poll_attempts),
            "finished_at": _now_iso(),
        }
        (clip_dir / "mp4_recovery_poll_report.json").write_text(json.dumps(poll_payload, indent=2), encoding="utf-8")


def extract_real_kling_mp4(
    page: Any,
    dest: Path,
    *,
    run_id: str,
    clip_index: int = 1,
    clip_dir: Path | None = None,
    recovery_mode: bool = False,
    write_report: bool = True,
    gate_context: Any | None = None,
) -> KlingRealMp4ExtractResult:
    """
    Try all safe extraction methods once; return only ffprobe-valid MP4 (>1MB, >=5s).
    Never clicks Generate.
    """
    from content_brain.execution.kling_useframe_generation_completion_gate import recovery_blocked_by_gate

    clip_dir = clip_dir or dest.parent
    clip_dir.mkdir(parents=True, exist_ok=True)
    result = KlingRealMp4ExtractResult(ok=False, recovery_mode=recovery_mode)
    blocked, block_reason = recovery_blocked_by_gate(page, gate_context)
    if blocked:
        _record_attempt(result, method="generation_completion_gate", ok=False, detail=block_reason)
        result.errors.append(f"recovery_locked:{block_reason}")
        if write_report:
            _write_extract_reports(
                result,
                clip_dir=clip_dir,
                run_id=run_id,
                clip_index=clip_index,
                dest=dest,
            )
        return result
    tracker = PhaseIArtifactTracker(page=page, project_id=run_id or "kling_extract")

    methods = (
        _method_artifact_card_cdp_urls,
        _method_scoped_card_browser_download,
        _method_page_video_sources,
        _method_global_ui_download,
    )
    for method in methods:
        if result.ok:
            break
        try:
            if method is _method_page_video_sources or method is _method_global_ui_download:
                method(page, dest=dest, clip_dir=clip_dir, result=result, gate_context=gate_context)
            else:
                method(
                    page,
                    tracker=tracker,
                    clip_index=clip_index,
                    dest=dest,
                    clip_dir=clip_dir,
                    result=result,
                    session_id=run_id,
                    gate_context=gate_context,
                )
        except Exception as exc:
            _record_attempt(result, method=method.__name__, ok=False, detail=str(exc)[:200])
            result.errors.append(f"{method.__name__}:{exc}")

    if write_report:
        _write_extract_reports(
            result,
            clip_dir=clip_dir,
            run_id=run_id,
            clip_index=clip_index,
            dest=dest,
        )
    return result


def poll_extract_real_kling_mp4(
    page: Any,
    dest: Path,
    *,
    run_id: str,
    clip_index: int = 1,
    clip_dir: Path | None = None,
    recovery_mode: bool = False,
    poll_interval_seconds: int = MP4_RECOVERY_POLL_INTERVAL_SECONDS,
    max_wait_seconds: int = MP4_RECOVERY_POLL_MAX_SECONDS,
    gate_context: Any | None = None,
) -> KlingRealMp4ExtractResult:
    """
    Poll MP4 extraction until valid file found or timeout. Never clicks Generate.
    """
    from content_brain.execution.kling_useframe_generation_completion_gate import recovery_blocked_by_gate

    clip_dir = clip_dir or dest.parent
    clip_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + max(1, int(max_wait_seconds))
    attempt = 0
    poll_attempts: list[dict[str, Any]] = []
    final = KlingRealMp4ExtractResult(ok=False, recovery_mode=recovery_mode)

    while True:
        attempt += 1
        ts = _now_iso()
        blocked, block_reason = recovery_blocked_by_gate(page, gate_context)
        if blocked:
            poll_attempts.append(
                {
                    "attempt": attempt,
                    "timestamp": ts,
                    "recovery_locked": True,
                    "block_reason": block_reason,
                    "valid_mp4_found": False,
                    "detail": "recovery_locked",
                }
            )
            final = KlingRealMp4ExtractResult(ok=False, recovery_mode=recovery_mode)
            final.errors.append(f"recovery_locked:{block_reason}")
        else:
            cycle = extract_real_kling_mp4(
                page,
                dest,
                run_id=run_id,
                clip_index=clip_index,
                clip_dir=clip_dir,
                recovery_mode=recovery_mode,
                write_report=False,
                gate_context=gate_context,
            )
            card_sel = dict(cycle.card_selection or {})
            poll_attempts.append(
                {
                    "attempt": attempt,
                    "timestamp": ts,
                    "recovery_locked": False,
                    "card_count": int(card_sel.get("card_count") or 0),
                    "video_card_count": int(card_sel.get("video_card_count") or 0),
                    "selected_card": card_sel.get("selected_card"),
                    "selection_strategy": card_sel.get("selection_strategy"),
                    "rejected_cards": list(card_sel.get("rejected_cards") or []),
                    "methods_tried": list(cycle.attempted_methods),
                    "rejected_files": list(cycle.quarantined_paths),
                    "valid_mp4_found": bool(cycle.ok),
                    "detail": "valid_mp4_found" if cycle.ok else "retry",
                }
            )
            if cycle.ok:
                final = cycle
                break
            final = cycle
        elapsed = time.monotonic() - started
        if elapsed >= max_wait_seconds:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(float(poll_interval_seconds), remaining))

    final.poll_attempts = poll_attempts
    final.poll_elapsed_seconds = round(time.monotonic() - started, 2)
    _write_extract_reports(
        final,
        clip_dir=clip_dir,
        run_id=run_id,
        clip_index=clip_index,
        dest=dest,
    )
    return final


__all__ = [
    "EXTRACTOR_VERSION",
    "KlingRealMp4ExtractResult",
    "ExtractMethodAttempt",
    "MP4_RECOVERY_POLL_INTERVAL_SECONDS",
    "MP4_RECOVERY_POLL_MAX_SECONDS",
    "card_has_visible_video_preview",
    "extract_real_kling_mp4",
    "inspect_file_candidate",
    "is_mp4_container",
    "is_rejected_placeholder_card",
    "is_rejected_placeholder_url",
    "poll_extract_real_kling_mp4",
    "quarantine_invalid_candidate",
    "rank_video_artifact_cards",
    "resolve_scoped_video_card_for_extraction",
    "score_media_url",
    "sort_media_urls",
    "verify_extracted_kling_mp4",
]
