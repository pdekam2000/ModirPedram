"""Video learning loop P0 — propose weight updates without mutating live Content Brain state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEARNING_LOOP_VERSION = "video_learning_loop_p0"
DEFAULT_OVERALL_THRESHOLD = 70
REINFORCEMENT_THRESHOLD = 85
LIVE_WEIGHTS_PATH = Path("project_brain/runtime_state/channel_quality_learning.json")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _aggregate_deltas(actions: list[dict[str, Any]]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for action in actions:
        delta = action.get("suggested_delta") or {}
        if not isinstance(delta, dict):
            continue
        for key, value in delta.items():
            if isinstance(value, (int, float)):
                merged[str(key)] = merged.get(str(key), 0.0) + float(value)
    return merged


def propose_learning_updates(
    judge_result: dict[str, Any],
    *,
    project_root: str | Path,
    channel_id: str = "default",
    overall_threshold: int = DEFAULT_OVERALL_THRESHOLD,
) -> dict[str, Any]:
    """Map judge output to proposed learning deltas. Does not apply them."""
    root = Path(project_root).resolve()
    run_id = str(judge_result.get("run_id") or "unknown_run")
    overall_score = int(judge_result.get("overall_score") or 0)
    improvement_actions = list(judge_result.get("improvement_actions") or [])
    strengths = list(judge_result.get("strengths") or [])
    weaknesses = list(judge_result.get("weaknesses") or [])

    mode = "skip"
    proposed_actions: list[dict[str, Any]] = []
    if overall_score < overall_threshold:
        mode = "corrective"
        proposed_actions = improvement_actions
    elif overall_score >= REINFORCEMENT_THRESHOLD:
        mode = "reinforcement"
        for strength in strengths[:3]:
            proposed_actions.append(
                {
                    "action_id": "reinforce_strength",
                    "reason": strength,
                    "target_score": "overall_score",
                    "current_score": overall_score,
                    "suggested_delta": {"quality_reinforcement": 0.05},
                }
            )

    payload = {
        "version": LEARNING_LOOP_VERSION,
        "run_id": run_id,
        "channel_id": channel_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "judge_version": judge_result.get("version"),
        "overall_score": overall_score,
        "mode": mode,
        "overall_threshold": overall_threshold,
        "proposed_actions": proposed_actions,
        "aggregated_deltas": _aggregate_deltas(proposed_actions),
        "weaknesses": weaknesses,
        "strengths": strengths,
        "applied": False,
        "note": "Proposed updates only — live Content Brain weights were not mutated.",
    }
    return payload


def persist_proposed_updates(
    proposed: dict[str, Any],
    *,
    project_root: str | Path,
) -> Path:
    root = Path(project_root).resolve()
    run_id = str(proposed.get("run_id") or "unknown_run")
    out_dir = root / "project_brain" / "quality_learning" / "proposed_updates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(proposed, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def run_video_learning_loop(
    judge_result: dict[str, Any],
    *,
    project_root: str | Path,
    channel_id: str = "default",
    overall_threshold: int = DEFAULT_OVERALL_THRESHOLD,
) -> dict[str, Any]:
    """Read judge output and persist proposed learning updates only."""
    proposed = propose_learning_updates(
        judge_result,
        project_root=project_root,
        channel_id=channel_id,
        overall_threshold=overall_threshold,
    )
    out_path = persist_proposed_updates(proposed, project_root=project_root)
    proposed["proposed_updates_path"] = str(out_path)
    return proposed


def live_weights_snapshot(project_root: str | Path) -> dict[str, Any]:
    """Return current live weights file contents for validation comparisons."""
    root = Path(project_root).resolve()
    return _read_json(root / LIVE_WEIGHTS_PATH)


__all__ = [
    "LEARNING_LOOP_VERSION",
    "LIVE_WEIGHTS_PATH",
    "live_weights_snapshot",
    "persist_proposed_updates",
    "propose_learning_updates",
    "run_video_learning_loop",
]
