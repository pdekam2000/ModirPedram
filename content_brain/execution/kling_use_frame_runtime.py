"""Kling Use Frame continuity runtime — primary handoff between Frame-to-Video clips."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.kling_continuity_runtime import (
    record_upload_status,
    upload_frame_for_next_clip,
)
from content_brain.execution.kling_frame_to_video_locator import try_locate_frame_control
from content_brain.execution.kling_frame_to_video_map_loader import load_kling_frame_ui_map
from content_brain.execution.kling_last_frame_extractor import (
    continuity_dir,
    extract_and_save_continuity_frame,
)
from content_brain.execution.kling_multishot_live_engine import verify_recovered_mp4
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH
from content_brain.story.story_progression_engine import story_chapter_for_clip

RUNTIME_VERSION = "kling_use_frame_runtime_v2"
USE_FRAME_CHAIN_FILENAME = "use_frame_chain.json"

CONTINUITY_METHOD_USE_FRAME = "use_frame"
CONTINUITY_METHOD_EXTRACT_UPLOAD = "extract_last_frame_upload"
CONTINUITY_METHOD_STARTER_FRAME = "starter_frame"


@dataclass
class UseFrameChainState:
    run_id: str
    continuity_method: str = CONTINUITY_METHOD_USE_FRAME
    clip_count: int = 1
    chain_complete: bool = False
    fallback_used: bool = False
    story_progression_status: str = "pending"
    clips: list[dict[str, Any]] = field(default_factory=list)
    version: str = RUNTIME_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "continuity_method": self.continuity_method,
            "clip_count": self.clip_count,
            "chain_complete": self.chain_complete,
            "fallback_used": self.fallback_used,
            "story_progression_status": self.story_progression_status,
            "clips": list(self.clips),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def use_frame_chain_path(run_dir: str | Path) -> Path:
    return continuity_dir(run_dir) / USE_FRAME_CHAIN_FILENAME


def load_use_frame_chain(run_dir: str | Path) -> dict[str, Any]:
    path = use_frame_chain_path(run_dir)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_use_frame_chain(run_dir: str | Path, state: UseFrameChainState | dict[str, Any]) -> dict[str, Any]:
    payload = state.to_dict() if isinstance(state, UseFrameChainState) else dict(state)
    payload["updated_at"] = _now_iso()
    path = use_frame_chain_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (Path(run_dir).resolve() / USE_FRAME_CHAIN_FILENAME).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["use_frame_chain_path"] = str(path.resolve()).replace("\\", "/")
    return payload


def detect_use_frame_button(
    page: Any,
    *,
    map_path: Path | str | None = None,
    timeout_ms: int = 4000,
) -> dict[str, Any]:
    ui_map = load_kling_frame_ui_map(map_path=map_path or DEFAULT_MAP_PATH)
    labels = dict(ui_map.get("labels") or {})
    entry = labels.get("use_frame_button") or {}
    located = try_locate_frame_control(page, "use_frame_button", entry, timeout_ms=timeout_ms)
    if located is None:
        for clicker in (
            lambda: page.get_by_text("Use frame", exact=False).first,
            lambda: page.locator('span:has-text("Use frame")').first,
        ):
            try:
                loc = clicker()
                if loc.count() > 0 and loc.is_visible():
                    return {
                        "detected": True,
                        "strategy": "text_use_frame_fallback",
                        "locator": loc,
                        "detail": "Use frame visible via text fallback",
                    }
            except Exception:
                continue
        return {"detected": False, "strategy": "", "detail": "Use frame control not found"}
    return {
        "detected": True,
        "strategy": located.strategy,
        "locator": located.locator,
        "detail": "Use frame mapped control visible",
    }


def validate_use_frame_availability(
    page: Any,
    *,
    map_path: Path | str | None = None,
) -> dict[str, Any]:
    detection = detect_use_frame_button(page, map_path=map_path)
    return {
        "ok": bool(detection.get("detected")),
        "available": bool(detection.get("detected")),
        "strategy": str(detection.get("strategy") or ""),
        "detail": str(detection.get("detail") or ""),
    }


def activate_use_frame(
    page: Any,
    *,
    from_clip_index: int,
    map_path: Path | str | None = None,
) -> dict[str, Any]:
    detection = detect_use_frame_button(page, map_path=map_path)
    if not detection.get("detected"):
        return {
            "ok": False,
            "activated": False,
            "from_clip_index": from_clip_index,
            "detail": detection.get("detail") or "Use frame not available",
        }
    locator = detection.get("locator")
    try:
        locator.click(timeout=8000, force=True)
        time.sleep(0.6)
        from content_brain.execution.kling_post_generation_mode_recovery import (
            select_use_frame_dropdown_option,
        )

        dropdown = select_use_frame_dropdown_option(page)
        return {
            "ok": True,
            "activated": True,
            "from_clip_index": from_clip_index,
            "strategy": str(detection.get("strategy") or ""),
            "detail": "Use frame clicked",
            "dropdown": dropdown,
            "activated_at": _now_iso(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "activated": False,
            "from_clip_index": from_clip_index,
            "detail": str(exc)[:200],
        }


def verify_reference_transferred(
    page: Any,
    *,
    map_path: Path | str | None = None,
) -> dict[str, Any]:
    ui_map = load_kling_frame_ui_map(map_path=map_path or DEFAULT_MAP_PATH)
    labels = dict(ui_map.get("labels") or {})
    upload_entry = labels.get("first_frame_upload") or {}
    upload = try_locate_frame_control(page, "first_frame_upload", upload_entry, timeout_ms=3000)
    upload_ok = upload is not None
    panel_hint = False
    try:
        panel_text = page.locator('[class*="left-panel"]').first.inner_text(timeout=2500).lower()
        panel_hint = "first video frame" in panel_text or "upload" in panel_text
    except Exception:
        pass
    ok = upload_ok or panel_hint
    return {
        "ok": ok,
        "reference_transferred": ok,
        "first_frame_upload_visible": upload_ok,
        "panel_hint": panel_hint,
        "strategy": upload.strategy if upload else "",
        "detail": "first frame slot ready after Use frame" if ok else "reference transfer not confirmed",
    }


def _fallback_extract_and_upload(
    page: Any,
    *,
    video_path: str | Path,
    run_dir: str | Path,
    from_clip_index: int,
    to_clip_index: int,
    map_path: Path | str | None = None,
) -> dict[str, Any]:
    video = Path(video_path).resolve()
    if not video.is_file():
        return {
            "ok": False,
            "continuity_method": CONTINUITY_METHOD_EXTRACT_UPLOAD,
            "detail": f"video missing for extract: {video}",
        }
    verify = verify_recovered_mp4(video)
    if not verify.get("is_real_mp4") and video.stat().st_size < 100_000:
        return {
            "ok": False,
            "continuity_method": CONTINUITY_METHOD_EXTRACT_UPLOAD,
            "detail": "video too small for last-frame extraction",
        }
    extracted = extract_and_save_continuity_frame(
        video_path=video,
        run_dir=run_dir,
        clip_index=from_clip_index,
    )
    upload = upload_frame_for_next_clip(
        page,
        frame_path=extracted.frame_path,
        clip_index=to_clip_index,
        map_path=map_path,
    )
    upload["continuity_method"] = CONTINUITY_METHOD_EXTRACT_UPLOAD
    upload["extracted_from_clip"] = from_clip_index
    upload["extracted_frame_path"] = extracted.frame_path
    upload["fallback"] = True
    return upload


def apply_continuity_for_next_clip(
    page: Any,
    *,
    run_dir: str | Path,
    from_clip_index: int,
    to_clip_index: int,
    video_path: str | Path,
    map_path: Path | str | None = None,
    starter_frame_path: str | Path | None = None,
) -> dict[str, Any]:
    """Priority: Use Frame → extract last frame + upload → starter frame fallback."""
    from content_brain.execution.kling_post_generation_mode_recovery import (
        detect_clip_output_visible,
        recover_video_kling_mode_after_generation,
        wait_for_continuity_frame_populated,
    )

    run_dir_path = Path(run_dir).resolve()
    chapter = story_chapter_for_clip(to_clip_index, clip_count=to_clip_index)
    output_probe = detect_clip_output_visible(page)

    availability = validate_use_frame_availability(page, map_path=map_path)
    if availability.get("available"):
        activation = activate_use_frame(page, from_clip_index=from_clip_index, map_path=map_path)
        if activation.get("activated"):
            mode_recovery = recover_video_kling_mode_after_generation(page, map_path=map_path)
            frame_wait = wait_for_continuity_frame_populated(page, map_path=map_path)
            verify = verify_reference_transferred(page, map_path=map_path)
            continuity_frame_in_ui = bool(
                frame_wait.get("continuity_frame_in_ui")
                or verify.get("ok")
            )
            if continuity_frame_in_ui and mode_recovery.get("recovered"):
                return {
                    "ok": True,
                    "continuity_method": CONTINUITY_METHOD_USE_FRAME,
                    "from_clip_index": from_clip_index,
                    "to_clip_index": to_clip_index,
                    "used_for_next_clip": True,
                    "continuity_frame_in_ui": True,
                    "story_chapter": chapter,
                    "use_frame_status": "activated",
                    "fallback_used": False,
                    "activation": activation,
                    "verify": verify,
                    "output_probe": output_probe,
                    "mode_recovery": mode_recovery,
                    "frame_wait": frame_wait,
                    "detail": "Use Frame continuity applied with post-generation mode recovery",
                }
            if continuity_frame_in_ui and not mode_recovery.get("recovered"):
                return {
                    "ok": False,
                    "continuity_method": CONTINUITY_METHOD_USE_FRAME,
                    "from_clip_index": from_clip_index,
                    "to_clip_index": to_clip_index,
                    "used_for_next_clip": False,
                    "continuity_frame_in_ui": continuity_frame_in_ui,
                    "story_chapter": chapter,
                    "use_frame_status": "mode_recovery_failed",
                    "fallback_used": False,
                    "activation": activation,
                    "mode_recovery": mode_recovery,
                    "frame_wait": frame_wait,
                    "detail": mode_recovery.get("detail") or "Video/Kling mode recovery failed after Use Frame",
                }

    extract_result = _fallback_extract_and_upload(
        page,
        video_path=video_path,
        run_dir=run_dir_path,
        from_clip_index=from_clip_index,
        to_clip_index=to_clip_index,
        map_path=map_path,
    )
    if extract_result.get("ok") or extract_result.get("uploaded"):
        extract_result.setdefault("continuity_method", CONTINUITY_METHOD_EXTRACT_UPLOAD)
        extract_result["used_for_next_clip"] = True
        extract_result["story_chapter"] = chapter
        extract_result["use_frame_status"] = "fallback_extract_upload"
        extract_result["fallback_used"] = True
        return extract_result

    starter = Path(starter_frame_path).resolve() if starter_frame_path else None
    if starter and starter.is_file():
        upload = upload_frame_for_next_clip(
            page,
            frame_path=starter,
            clip_index=to_clip_index,
            map_path=map_path,
        )
        upload["continuity_method"] = CONTINUITY_METHOD_STARTER_FRAME
        upload["used_for_next_clip"] = bool(upload.get("uploaded"))
        upload["story_chapter"] = chapter
        upload["use_frame_status"] = "fallback_starter_frame"
        upload["fallback_used"] = True
        return upload

    return {
        "ok": False,
        "continuity_method": "",
        "from_clip_index": from_clip_index,
        "to_clip_index": to_clip_index,
        "used_for_next_clip": False,
        "story_chapter": chapter,
        "use_frame_status": "failed",
        "fallback_used": True,
        "detail": "All continuity methods failed",
    }


def record_clip_continuity_metadata(
    state: UseFrameChainState,
    *,
    clip_index: int,
    handoff: dict[str, Any],
    video_path: str = "",
    story_chapter: str = "",
) -> None:
    method = str(handoff.get("continuity_method") or CONTINUITY_METHOD_USE_FRAME)
    if handoff.get("fallback_used"):
        state.fallback_used = True
        if state.continuity_method == CONTINUITY_METHOD_USE_FRAME and method != CONTINUITY_METHOD_USE_FRAME:
            state.continuity_method = method
    entry = {
        "clip": clip_index,
        "story_chapter": story_chapter or handoff.get("story_chapter") or story_chapter_for_clip(clip_index),
        "continuity_method": method,
        "used_for_next_clip": bool(handoff.get("used_for_next_clip")),
        "use_frame_status": handoff.get("use_frame_status") or ("activated" if method == CONTINUITY_METHOD_USE_FRAME else "fallback"),
        "fallback_used": bool(handoff.get("fallback_used")),
        "video_path": video_path,
        "handoff_to_clip": handoff.get("to_clip_index"),
        "detail": handoff.get("detail") or "",
        "recorded_at": _now_iso(),
    }
    state.clips = [item for item in state.clips if int(item.get("clip") or 0) != clip_index]
    state.clips.append(entry)
    state.clips.sort(key=lambda item: int(item.get("clip") or 0))


def finalize_story_progression(state: UseFrameChainState, *, completed_clips: int, target_clips: int) -> None:
    if completed_clips >= target_clips and target_clips > 0:
        state.story_progression_status = "complete"
        state.chain_complete = True
    elif completed_clips > 0:
        state.story_progression_status = "in_progress"
    else:
        state.story_progression_status = "pending"


__all__ = [
    "CONTINUITY_METHOD_EXTRACT_UPLOAD",
    "CONTINUITY_METHOD_STARTER_FRAME",
    "CONTINUITY_METHOD_USE_FRAME",
    "RUNTIME_VERSION",
    "USE_FRAME_CHAIN_FILENAME",
    "UseFrameChainState",
    "activate_use_frame",
    "apply_continuity_for_next_clip",
    "detect_use_frame_button",
    "finalize_story_progression",
    "load_use_frame_chain",
    "record_clip_continuity_metadata",
    "story_chapter_for_clip",
    "use_frame_chain_path",
    "validate_use_frame_availability",
    "verify_reference_transferred",
    "write_use_frame_chain",
]
