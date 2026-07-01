"""Output snapshot tracking and stale-safe download selection for multi-clip runs."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

GUARD_VERSION = "pwmap_download_selection_v1"

STALE_SOURCE_ERROR = "Selected video source matches previous clip; refusing stale download."
NO_NEW_OUTPUT_ERROR = "Could not prove downloaded output belongs to current clip attempt."
DUPLICATE_MP4_ERROR = (
    "Downloaded MP4 is byte-identical to a previous clip; duplicate download rejected."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_source_identity(video_entry: dict[str, Any]) -> str:
    for key in ("currentSrc", "src", "poster"):
        value = str(video_entry.get(key) or "").strip()
        if value.startswith("http") or value.startswith("blob:"):
            return value
    return ""


def output_card_fingerprint(video_entry: dict[str, Any]) -> str:
    identity = video_source_identity(video_entry)
    parts = [
        identity,
        str(video_entry.get("data_index") or ""),
        str(video_entry.get("card_text_hash") or ""),
        str(video_entry.get("index") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def collect_prior_identities(prior_clips: list[dict[str, Any]]) -> tuple[set[str], set[str], set[str]]:
    sources: set[str] = set()
    fingerprints: set[str] = set()
    hashes: set[str] = set()
    for clip in prior_clips:
        if clip.get("download_success") is False:
            continue
        src = str(clip.get("selected_source") or clip.get("video_url") or "").strip()
        if src:
            sources.add(src)
        fp = str(clip.get("output_card_fingerprint") or "").strip()
        if fp:
            fingerprints.add(fp)
        file_hash = str(clip.get("sha256") or "").strip()
        if file_hash:
            hashes.add(file_hash)
    return sources, fingerprints, hashes


def detect_new_output(
    *,
    pre_snapshot: dict[str, Any],
    post_snapshot: dict[str, Any],
    prior_clips: list[dict[str, Any]],
) -> dict[str, Any]:
    pre_videos = list(pre_snapshot.get("videos") or [])
    post_videos = list(post_snapshot.get("videos") or [])
    prior_sources, prior_fingerprints, _ = collect_prior_identities(prior_clips)

    pre_sources = {video_source_identity(v) for v in pre_videos if video_source_identity(v)}
    pre_fingerprints = {output_card_fingerprint(v) for v in pre_videos}

    if not post_videos:
        return {
            "ok": False,
            "status": "no_new_output_detected",
            "detail": NO_NEW_OUTPUT_ERROR,
            "selected_video": None,
        }

    if len(post_videos) > len(pre_videos):
        top = post_videos[0]
        src = video_source_identity(top)
        fp = output_card_fingerprint(top)
        if src and src not in prior_sources and fp not in prior_fingerprints:
            return {
                "ok": True,
                "status": "new_output_detected",
                "detail": "video_count_increased",
                "selected_video": top,
                "selection_reason": "video_count_increased",
                "selected_source": src,
                "output_card_fingerprint": fp,
            }

    top = post_videos[0]
    top_src = video_source_identity(top)
    top_fp = output_card_fingerprint(top)
    if top_src and top_src not in pre_sources and top_src not in prior_sources and top_fp not in prior_fingerprints:
        return {
            "ok": True,
            "status": "new_output_detected",
            "detail": "top_src_changed",
            "selected_video": top,
            "selection_reason": "top_src_changed",
            "selected_source": top_src,
            "output_card_fingerprint": top_fp,
        }

    for video in post_videos:
        src = video_source_identity(video)
        fp = output_card_fingerprint(video)
        if not src or src in prior_sources or fp in prior_fingerprints:
            continue
        if src in pre_sources and fp in pre_fingerprints:
            continue
        return {
            "ok": True,
            "status": "new_output_detected",
            "detail": "alternate_feed_card",
            "selected_video": video,
            "selection_reason": "alternate_feed_card",
            "selected_source": src,
            "output_card_fingerprint": fp,
        }

    return {
        "ok": False,
        "status": "no_new_output_detected",
        "detail": NO_NEW_OUTPUT_ERROR,
        "selected_video": None,
    }


def reject_stale_source(
    *,
    selected_source: str,
    output_card_fingerprint: str,
    prior_clips: list[dict[str, Any]],
) -> dict[str, Any]:
    prior_sources, prior_fingerprints, _ = collect_prior_identities(prior_clips)
    if selected_source and selected_source in prior_sources:
        return {
            "ok": False,
            "status": "stale_source_rejected",
            "download_status": "stale_source_rejected",
            "detail": STALE_SOURCE_ERROR,
            "selected_source": selected_source,
        }
    if output_card_fingerprint and output_card_fingerprint in prior_fingerprints:
        return {
            "ok": False,
            "status": "stale_source_rejected",
            "download_status": "stale_source_rejected",
            "detail": STALE_SOURCE_ERROR,
            "output_card_fingerprint": output_card_fingerprint,
        }
    return {"ok": True, "status": "selected_output_fresh", "download_status": "fresh"}


def reject_duplicate_mp4(
    *,
    downloaded_path: Path,
    prior_clips: list[dict[str, Any]],
    quarantine_dir: Path,
) -> dict[str, Any]:
    if not downloaded_path.is_file():
        return {
            "ok": False,
            "status": "download_missing",
            "download_status": "download_failed",
            "detail": f"Downloaded file missing: {downloaded_path}",
        }

    file_hash = sha256_file(downloaded_path)
    _prior_sources, _prior_fps, prior_hashes = collect_prior_identities(prior_clips)
    if file_hash in prior_hashes:
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        quarantined = quarantine_dir / f"{downloaded_path.stem}_dup_{file_hash[:12]}{downloaded_path.suffix}"
        if quarantined.exists():
            quarantined.unlink()
        shutil.move(str(downloaded_path), str(quarantined))
        return {
            "ok": False,
            "status": "duplicate_mp4_rejected",
            "download_status": "duplicate_mp4_rejected",
            "detail": DUPLICATE_MP4_ERROR,
            "sha256": file_hash,
            "quarantine_path": str(quarantined.resolve()),
        }

    return {
        "ok": True,
        "status": "download_verified",
        "download_status": "fresh",
        "sha256": file_hash,
    }


def build_clip_status(
    *,
    clip_index: int,
    use_frame_required: bool,
    generation_started: bool = True,
    generation_success: bool = False,
    use_frame_success: bool | None = None,
    pre_snapshot: dict[str, Any] | None = None,
    post_snapshot: dict[str, Any] | None = None,
    new_output: dict[str, Any] | None = None,
    source_check: dict[str, Any] | None = None,
    download_attempted: bool = False,
    download_path: str = "",
    download_method: str = "",
    mp4_check: dict[str, Any] | None = None,
    final_clip_registered: bool = False,
) -> dict[str, Any]:
    new_output = dict(new_output or {})
    source_check = dict(source_check or {})
    mp4_check = dict(mp4_check or {})

    download_success = bool(
        download_attempted
        and mp4_check.get("ok")
        and source_check.get("ok", True)
        and new_output.get("ok", True)
        and download_path
    )

    duplicate_guard_status = "pass"
    if mp4_check.get("status") == "duplicate_mp4_rejected":
        duplicate_guard_status = "duplicate_mp4_rejected"
    elif source_check.get("status") == "stale_source_rejected":
        duplicate_guard_status = "stale_source_rejected"
    elif new_output.get("status") == "no_new_output_detected":
        duplicate_guard_status = "no_new_output_detected"

    return {
        "version": GUARD_VERSION,
        "clip": clip_index,
        "generation_started": generation_started,
        "generation_success": generation_success,
        "use_frame_required": use_frame_required,
        "use_frame_success": use_frame_success,
        "pre_generation_snapshot": pre_snapshot,
        "post_generation_snapshot": post_snapshot,
        "new_output_detected": bool(new_output.get("ok")),
        "new_output_status": new_output.get("status") or "",
        "selected_output_fresh": bool(source_check.get("ok")) if source_check else False,
        "selected_source": new_output.get("selected_source") or source_check.get("selected_source") or "",
        "output_card_fingerprint": new_output.get("output_card_fingerprint") or "",
        "selection_reason": new_output.get("selection_reason") or "",
        "download_attempted": download_attempted,
        "download_success": download_success,
        "download_method": download_method,
        "download_status": (
            mp4_check.get("download_status")
            or source_check.get("download_status")
            or new_output.get("status")
            or ("fresh" if download_success else "ambiguous_stale_output")
        ),
        "download": download_path,
        "duplicate_guard_status": duplicate_guard_status,
        "final_clip_registered": final_clip_registered and download_success,
        "sha256": mp4_check.get("sha256") or "",
        "error": (
            mp4_check.get("detail")
            or source_check.get("detail")
            or new_output.get("detail")
            or ""
        ),
    }


def write_inspection_report(*, report_path: Path, snapshot: dict[str, Any]) -> None:
    payload = {
        "version": GUARD_VERSION,
        "mode": "inspect_existing_outputs",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "snapshot": snapshot,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def feed_download_pattern() -> re.Pattern[str]:
    return re.compile(r"download", re.I)
