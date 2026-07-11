"""Fail-closed run isolation — no cross-run fallback without explicit reuse."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.runway_live_post_processor import collect_valid_download_paths
from content_brain.platform.run_output_versioning import create_versioned_run_layout

RUN_ISOLATION_VERSION = "run_isolation_v1"
RUN_CONTEXTS_DIR = Path("project_brain") / "runtime_state" / "run_contexts"
LATEST_ATTEMPT_PATH = Path("project_brain") / "runtime_state" / "latest_run_attempt.json"

FAIL_MESSAGE = "Run failed before video generation — no final video created."

CARTOON_CHARACTER_KEYS = frozenset({"whiskers", "sage"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_topic(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _is_cartoon_topic(topic: str) -> bool:
    lowered = _normalize_topic(topic)
    markers = ("cartoon", "whisker", "whiskers", "sage the fox", "crystal jungle", "cat explorer", "orange cat")
    return any(marker in lowered for marker in markers)


@dataclass
class RunContext:
    run_id: str
    topic: str
    story_package_path: str = ""
    visual_memory_path: str = ""
    voice_registry_scope: str = ""
    output_run_folder: str = ""
    downloaded_clip_paths: list[str] = field(default_factory=list)
    clip_count: int = 0
    status: str = "pending"
    failure_reason: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RUN_ISOLATION_VERSION,
            "run_id": self.run_id,
            "topic": self.topic,
            "story_package_path": self.story_package_path,
            "visual_memory_path": self.visual_memory_path,
            "voice_registry_scope": self.voice_registry_scope,
            "output_run_folder": self.output_run_folder,
            "downloaded_clip_paths": list(self.downloaded_clip_paths),
            "clip_count": self.clip_count,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


def run_context_path(project_root: str | Path, run_id: str) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(run_id or "run")).strip("_") or "run"
    return Path(project_root).resolve() / RUN_CONTEXTS_DIR / f"{slug}.json"


def load_run_context(project_root: str | Path, run_id: str) -> dict[str, Any]:
    path = run_context_path(project_root, run_id)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_run_context(project_root: str | Path, context: RunContext | dict[str, Any]) -> Path:
    root = Path(project_root).resolve()
    payload = context.to_dict() if isinstance(context, RunContext) else dict(context)
    run_id = str(payload.get("run_id") or "")
    path = run_context_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["version"] = RUN_ISOLATION_VERSION
    payload["updated_at"] = _now()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def create_isolated_run_context(
    project_root: str | Path,
    *,
    run_id: str,
    topic: str,
    clip_count: int = 3,
    story_brief: dict[str, Any] | None = None,
) -> RunContext:
    """Create per-run folders, story package, and scoped paths. No reuse of prior runs."""
    root = Path(project_root).resolve()
    if not str(run_id or "").strip():
        raise ValueError("run_id is required for isolated run context")
    if not str(topic or "").strip():
        raise ValueError("topic is required for isolated run context")

    layout = create_versioned_run_layout(root, run_id=str(run_id), topic=str(topic))
    from content_brain.story.story_package import build_and_save_story_package

    purge_story_package_for_run(root, run_id)
    brief = _fresh_story_brief(str(topic), story_brief)
    package, package_path = build_and_save_story_package(
        project_root=root,
        topic=str(topic),
        run_id=str(run_id),
        clip_count=max(1, int(clip_count)),
        duration_seconds=max(10, int(clip_count) * 10),
        story_brief=brief,
        run_dir=layout.run_dir,
    )

    ok, reason, _ = require_story_package_for_run(root, run_id, topic=str(topic))
    if not ok and reason in {"story_package_cartoon_character_leak", "story_package_topic_mismatch"}:
        purge_story_package_for_run(root, run_id)
        brief = _fresh_story_brief(str(topic), brief)
        package, package_path = build_and_save_story_package(
            project_root=root,
            topic=str(topic),
            run_id=str(run_id),
            clip_count=max(1, int(clip_count)),
            duration_seconds=max(10, int(clip_count) * 10),
            story_brief=brief,
            run_dir=layout.run_dir,
        )

    visual_memory_path = root / "project_brain" / "visual_memory" / f"run_{run_id}.json"
    context = RunContext(
        run_id=str(run_id),
        topic=str(topic),
        story_package_path=str(package_path.resolve()),
        visual_memory_path=str(visual_memory_path),
        voice_registry_scope=str(run_id),
        output_run_folder=str(layout.run_dir.resolve()),
        clip_count=max(1, int(clip_count)),
        status="pending",
        metadata={
            "story_package_version": package.to_dict().get("version"),
            "genre": package.story_blueprint.genre,
        },
    )
    (layout.metadata_dir / "run_context.json").write_text(
        json.dumps(context.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    save_run_context(root, context)
    return context


def classify_runway_report_outcome(report: dict[str, Any] | Any) -> tuple[str, str]:
    """Return (status, reason) where status is completed|failed|skipped."""
    if isinstance(report, dict):
        data = report
    elif hasattr(report, "to_dict"):
        data = report.to_dict()
    else:
        data = {}

    if bool(data.get("simulate", True)):
        return "skipped", "simulate_skipped"

    clips_completed = int(data.get("clips_completed") or 0)
    downloaded = [str(item) for item in (data.get("downloaded_file_paths") or []) if item]
    valid, _missing = collect_valid_download_paths(downloaded)
    if clips_completed <= 0 or not valid:
        return "failed", FAIL_MESSAGE

    if not bool(data.get("ok", False)):
        return "failed", str(data.get("stopped_reason") or data.get("final_status") or "run_not_ok")

    return "completed", "clips_downloaded"


def record_latest_run_attempt(project_root: str | Path, report: dict[str, Any] | Any) -> dict[str, Any]:
    """Persist latest attempt separately from approved delivery registry."""
    root = Path(project_root).resolve()
    if isinstance(report, dict):
        data = dict(report)
    elif hasattr(report, "to_dict"):
        data = report.to_dict()
    else:
        data = {}

    status, reason = classify_runway_report_outcome(data)
    run_id = str(
        data.get("content_brain_run_id")
        or data.get("run_id")
        or ""
    ).strip()
    topic = str(
        data.get("content_brain_topic")
        or data.get("topic_label")
        or data.get("story_idea")
        or ""
    ).strip()
    clips_completed = int(data.get("clips_completed") or 0)
    downloaded = [str(item) for item in (data.get("downloaded_file_paths") or []) if item]
    valid, _ = collect_valid_download_paths(downloaded)

    payload = {
        "version": RUN_ISOLATION_VERSION,
        "run_id": run_id,
        "topic": topic,
        "status": status,
        "clips_completed": clips_completed,
        "downloaded_clip_count": len(valid),
        "downloaded_clip_paths": valid,
        "message": reason if status == "failed" else "Run completed with downloadable clips.",
        "run_ok": bool(data.get("ok", False)),
        "versioned_run_dir": str(data.get("versioned_run_dir") or data.get("post_processing_versioned_run_dir") or ""),
        "final_branded_video_path": str(data.get("final_branded_video_path") or ""),
        "canonical_deliverable_path": str(data.get("canonical_deliverable_path") or ""),
        "delivery_status": str(data.get("delivery_status") or ""),
        "delivery_gate_failures": list(data.get("delivery_gate_failures") or []),
        "updated_at": _now(),
    }

    path = root / LATEST_ATTEMPT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if run_id:
        existing = load_run_context(root, run_id)
        if existing:
            existing["status"] = status
            existing["failure_reason"] = "" if status == "completed" else reason
            existing["downloaded_clip_paths"] = valid
            save_run_context(root, existing)

    return payload


def load_latest_run_attempt(project_root: str | Path) -> dict[str, Any]:
    path = Path(project_root).resolve() / LATEST_ATTEMPT_PATH
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def purge_story_package_for_run(project_root: str | Path, run_id: str) -> list[str]:
    """Delete run-scoped story package files that may contain stale topic/genre data."""
    root = Path(project_root).resolve()
    removed: list[str] = []
    from content_brain.story.story_package import story_package_path

    candidates = [
        story_package_path(root, run_id),
        root / "project_brain" / "story_packages" / f"{run_id}.json",
    ]
    context = load_run_context(root, run_id)
    context_path = str(context.get("story_package_path") or "")
    if context_path:
        candidates.append(Path(context_path))

    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            path.unlink(missing_ok=True)
            removed.append(str(path.resolve()))
    return removed


def _fresh_story_brief(topic: str, story_brief: dict[str, Any] | None = None) -> dict[str, Any]:
    from content_brain.story.story_niche import detect_genre

    brief = dict(story_brief or {})
    if str(brief.get("genre") or "").lower() == "cartoon" and not _is_cartoon_topic(topic):
        brief.pop("genre", None)
    brief.setdefault("genre", detect_genre(topic, brief))
    return brief


def require_story_package_for_run(project_root: str | Path, run_id: str, *, topic: str = "") -> tuple[bool, str, str]:
    """Fail closed if run-scoped story package missing. Never fall back to another run."""
    root = Path(project_root).resolve()
    context = load_run_context(root, run_id)
    package_path = str(context.get("story_package_path") or "")
    if not package_path:
        candidate = root / "project_brain" / "story_packages" / f"{run_id}.json"
        if candidate.is_file():
            package_path = str(candidate)
    path = Path(package_path)
    if not path.is_file():
        return False, "story_package_missing", ""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "story_package_unreadable", str(path)

    package_topic = str(payload.get("topic") or "")
    if topic and package_topic and _normalize_topic(package_topic) != _normalize_topic(topic):
        purge_story_package_for_run(root, run_id)
        return False, "story_package_topic_mismatch", str(path)

    genre = str((payload.get("story_blueprint") or {}).get("genre") or "")
    names = {
        str(item.get("name") or "").lower()
        for item in (payload.get("character_profiles") or [])
        if isinstance(item, dict)
    }
    if not _is_cartoon_topic(topic or package_topic) and names.intersection(CARTOON_CHARACTER_KEYS):
        purge_story_package_for_run(root, run_id)
        return False, "story_package_cartoon_character_leak", str(path)

    return True, "ok", str(path)


def voice_registry_scope_path(project_root: str | Path, run_id: str) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(run_id or "scope")).strip("_") or "scope"
    return Path(project_root).resolve() / "project_brain" / "runtime_state" / "voice_scopes" / f"{slug}.json"


def should_reuse_global_voice_character(*, topic: str, character_key: str) -> bool:
    key = str(character_key or "").lower()
    if key not in CARTOON_CHARACTER_KEYS:
        return True
    return _is_cartoon_topic(topic)


__all__ = [
    "FAIL_MESSAGE",
    "RUN_ISOLATION_VERSION",
    "RunContext",
    "classify_runway_report_outcome",
    "create_isolated_run_context",
    "load_latest_run_attempt",
    "load_run_context",
    "purge_story_package_for_run",
    "record_latest_run_attempt",
    "require_story_package_for_run",
    "run_context_path",
    "save_run_context",
    "should_reuse_global_voice_character",
    "voice_registry_scope_path",
]
