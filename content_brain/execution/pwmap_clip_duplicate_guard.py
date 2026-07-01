"""pwmap clip duplicate, download freshness, and Use Frame registration guards."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.kling_useframe_generation_completion_gate import sha256_file
from content_brain.execution.pwmap_runway_agent_adapter import validate_mp4_path

GUARD_VERSION = "pwmap_clip_duplicate_guard_v1"
DUPLICATE_ERROR = (
    "Downloaded clip is byte-identical to a previous clip; possible stale output/download selection."
)
USE_FRAME_MISSING_ERROR = "Use Frame prerequisites not satisfied for clip 2+; continuation blocked."
AMBIGUOUS_STALE_ERROR = "Download freshness could not be proven; possible stale output selection."


def _parse_finished_at(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text.replace("Z", "+0000"), fmt)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            continue
    return None


def verify_use_frame_gate(
    *,
    clip_index: int,
    last_result_clip: dict[str, Any] | None,
    subprocess_stdout: str = "",
) -> dict[str, Any]:
    """For clip 2+, require Use Frame evidence from last_result or subprocess log."""
    if clip_index <= 1:
        return {"ok": True, "status": "not_required", "detail": "clip_1"}

    clip = dict(last_result_clip or {})
    used_frame = bool(clip.get("used_frame_from_previous"))
    use_frame_second = clip.get("use_frame_second")
    stdout = subprocess_stdout or ""
    log_used_frame = "Use frame clicked" in stdout and f"CLIP {clip_index}/" in stdout

    ok = used_frame and use_frame_second is not None and log_used_frame
    return {
        "ok": ok,
        "status": "pass" if ok else "use_frame_missing",
        "detail": USE_FRAME_MISSING_ERROR if not ok else "",
        "used_frame_from_previous": used_frame,
        "use_frame_second": use_frame_second,
        "log_used_frame": log_used_frame,
    }


def verify_download_freshness(
    *,
    clip_index: int,
    clip_path: str | Path,
    prior_clips: list[dict[str, Any]],
    last_result_clip: dict[str, Any] | None,
) -> dict[str, Any]:
    """For clip 2+, verify download is not stale relative to prior clip."""
    path = Path(clip_path)
    verify = validate_mp4_path(path)
    if not verify.get("valid"):
        return {"ok": False, "status": "invalid_mp4", "detail": f"Invalid MP4: {path}"}

    file_hash = sha256_file(path)
    prior_hashes = [str(item.get("sha256") or "") for item in prior_clips if item.get("sha256")]
    if clip_index > 1 and file_hash and file_hash in prior_hashes:
        return {
            "ok": False,
            "status": "duplicate_hash",
            "detail": DUPLICATE_ERROR,
            "sha256": file_hash,
            "download_status": "ambiguous_stale_output",
        }

    if clip_index <= 1:
        return {"ok": True, "status": "pass", "sha256": file_hash, "download_status": "fresh"}

    clip = dict(last_result_clip or {})
    prior = prior_clips[-1] if prior_clips else {}
    current_finished = _parse_finished_at(str(clip.get("finished_at") or ""))
    prior_finished = _parse_finished_at(str(prior.get("finished_at") or ""))
    current_mtime = datetime.fromtimestamp(path.stat().st_mtime) if path.is_file() else None

    freshness_signals: list[str] = []
    if current_finished and prior_finished and current_finished > prior_finished:
        freshness_signals.append("finished_at_after_prior")
    if current_mtime and prior_finished and current_mtime >= prior_finished:
        freshness_signals.append("mtime_after_prior_finished")
    if verify.get("size_bytes") and prior.get("size_bytes") and verify["size_bytes"] != prior["size_bytes"]:
        freshness_signals.append("size_differs_from_prior")

    if file_hash and prior.get("sha256") and file_hash != prior["sha256"]:
        freshness_signals.append("hash_differs_from_prior")

    if clip_index > 1 and not freshness_signals:
        return {
            "ok": False,
            "status": "ambiguous_stale_output",
            "detail": AMBIGUOUS_STALE_ERROR,
            "sha256": file_hash,
            "download_status": "ambiguous_stale_output",
            "freshness_signals": freshness_signals,
        }

    return {
        "ok": True,
        "status": "pass",
        "sha256": file_hash,
        "download_status": "fresh",
        "freshness_signals": freshness_signals,
    }


def verify_clip_not_duplicate(
    *,
    clip_index: int,
    clip_path: str | Path,
    prior_clips: list[dict[str, Any]],
) -> dict[str, Any]:
    path = Path(clip_path)
    file_hash = sha256_file(path)
    for prior in prior_clips:
        if str(prior.get("sha256") or "") == file_hash and file_hash:
            return {
                "ok": False,
                "status": "duplicate_failed",
                "detail": DUPLICATE_ERROR,
                "sha256": file_hash,
                "duplicate_of_clip": int(prior.get("clip") or prior.get("clip_index") or 0),
            }
    return {"ok": True, "status": "pass", "sha256": file_hash}


def apply_pwmap_clip_registration_guards(
    *,
    copied_clips: list[dict[str, Any]],
    last_result: dict[str, Any],
    subprocess_stdout: str = "",
    expected_clip_count: int = 0,
) -> dict[str, Any]:
    """Run duplicate, freshness, and Use Frame guards before clip registration."""
    last_clips = last_result.get("clips") or []
    if not isinstance(last_clips, list):
        last_clips = []

    guarded: list[dict[str, Any]] = []
    prior_valid: list[dict[str, Any]] = []
    duplicate_pairs: list[dict[str, Any]] = []
    blocked_clips: list[int] = []

    for index, item in enumerate(copied_clips, start=1):
        entry = dict(item)
        clip_index = int(entry.get("clip") or index)
        modir_path = str(entry.get("modir_path") or "")
        last_clip = last_clips[index - 1] if index - 1 < len(last_clips) else {}

        use_frame = verify_use_frame_gate(
            clip_index=clip_index,
            last_result_clip=last_clip if isinstance(last_clip, dict) else {},
            subprocess_stdout=subprocess_stdout,
        )
        freshness = verify_download_freshness(
            clip_index=clip_index,
            clip_path=modir_path,
            prior_clips=prior_valid,
            last_result_clip=last_clip if isinstance(last_clip, dict) else {},
        )
        duplicate = verify_clip_not_duplicate(
            clip_index=clip_index,
            clip_path=modir_path,
            prior_clips=prior_valid,
        )

        entry["sha256"] = duplicate.get("sha256") or freshness.get("sha256") or ""
        entry["download_status"] = freshness.get("download_status") or ""
        entry["use_frame_gate"] = use_frame
        entry["freshness_gate"] = freshness
        entry["duplicate_gate"] = duplicate

        failed_gate = None
        if clip_index > 1 and not use_frame.get("ok"):
            failed_gate = use_frame
            entry["valid"] = False
            entry["status"] = "use_frame_missing"
            entry["error"] = use_frame.get("detail") or USE_FRAME_MISSING_ERROR
        elif not duplicate.get("ok"):
            failed_gate = duplicate
            entry["valid"] = False
            entry["status"] = "duplicate_failed"
            entry["error"] = duplicate.get("detail") or DUPLICATE_ERROR
            duplicate_pairs.append(
                {
                    "clip_a": int(duplicate.get("duplicate_of_clip") or clip_index - 1),
                    "clip_b": clip_index,
                    "sha256": entry["sha256"],
                }
            )
        elif not freshness.get("ok"):
            failed_gate = freshness
            entry["valid"] = False
            entry["status"] = str(freshness.get("status") or "ambiguous_stale_output")
            entry["error"] = freshness.get("detail") or AMBIGUOUS_STALE_ERROR
        else:
            entry["valid"] = bool(entry.get("valid", True))
            entry["status"] = "completed"
            prior_valid.append(entry)

        if failed_gate:
            blocked_clips.append(clip_index)

        guarded.append(entry)

    valid_count = sum(1 for clip in guarded if clip.get("valid"))
    requested = int(expected_clip_count or len(copied_clips) or len(last_clips) or 0)
    duplicate_chain_failed = bool(duplicate_pairs) or any(
        clip.get("status") == "duplicate_failed" for clip in guarded
    )

    return {
        "version": GUARD_VERSION,
        "guarded_clips": guarded,
        "valid_clip_count": valid_count,
        "expected_clip_count": requested,
        "duplicate_pairs": duplicate_pairs,
        "duplicate_chain_failed": duplicate_chain_failed,
        "blocked_clips": blocked_clips,
        "clip_3_not_applicable": requested <= 2,
        "registration_allowed": valid_count > 0 and not duplicate_chain_failed,
        "error": DUPLICATE_ERROR if duplicate_chain_failed else "",
    }


__all__ = [
    "AMBIGUOUS_STALE_ERROR",
    "DUPLICATE_ERROR",
    "GUARD_VERSION",
    "USE_FRAME_MISSING_ERROR",
    "apply_pwmap_clip_registration_guards",
    "verify_clip_not_duplicate",
    "verify_download_freshness",
    "verify_use_frame_gate",
]
