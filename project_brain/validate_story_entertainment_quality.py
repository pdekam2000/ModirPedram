"""Story entertainment quality audit — human-review metrics, not file existence checks."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_VERSION = "validate_story_entertainment_quality_v1"
EXCITEMENT_MARKERS = ("!", "?", "whoa", "wow", "come on", "look", "did you", "let's")
STIFF_MARKERS = ("i think something", "we should investigate", "the adventure had begun beneath")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _probe_mean_volume(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(path),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", proc.stderr or "")
        return float(match.group(1)) if match else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


@dataclass
class EntertainmentAuditResult:
    status: str
    checks: dict[str, bool]
    metrics: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": AUDIT_VERSION,
            "status": self.status,
            "checks": dict(self.checks),
            "metrics": dict(self.metrics),
            "warnings": list(self.warnings),
            "audited_at": _now(),
        }


def audit_story_entertainment_quality(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    story_package: dict[str, Any] | None = None,
) -> EntertainmentAuditResult:
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve()
    package = dict(story_package or {})
    if not package:
        summary = _read_json(run_path / "metadata" / "run_summary.json")
        run_id = str(summary.get("run_id") or "")
        if run_id:
            from content_brain.story.story_package import load_story_package

            package = load_story_package(root, run_id)

    dialogue_plan = dict(package.get("dialogue_plan") or {})
    voice_cast = dict(package.get("voice_cast_plan") or {})
    music_plan = dict(package.get("music_plan") or {})
    environment_plan = dict(package.get("environment_plan") or {})
    metadata = dict(package.get("metadata") or {})

    spoken_lines: list[str] = []
    speakers: set[str] = set()
    for scene in dialogue_plan.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        narration = str(scene.get("narration") or "").strip()
        if narration:
            spoken_lines.append(narration)
            speakers.add("narrator")
        for line in scene.get("dialogue_lines") or []:
            if not isinstance(line, dict):
                continue
            text = str(line.get("line") or "").strip()
            speaker = str(line.get("speaker") or "").strip()
            if text:
                spoken_lines.append(text)
            if speaker:
                speakers.add(speaker.lower())

    runtime_timeline = _read_json(run_path / "timeline" / "dialogue_timeline.json")
    runtime_speakers = {
        str(line.get("speaker") or "").lower()
        for line in (runtime_timeline.get("lines") or [])
        if isinstance(line, dict) and line.get("speaker")
    }
    speakers.update(runtime_speakers)

    emotional_lines = sum(
        1
        for text in spoken_lines
        if any(marker in text.lower() for marker in EXCITEMENT_MARKERS)
    )
    stiff_lines = sum(1 for text in spoken_lines if any(marker in text.lower() for marker in STIFF_MARKERS))
    emotional_density = emotional_lines / max(1, len(spoken_lines))

    voice_ids = {
        str(voice_cast.get("narrator", {}).get("voice_id") or ""),
        *[
            str(row.get("voice_id") or "")
            for row in (voice_cast.get("characters") or [])
            if isinstance(row, dict)
        ],
    }
    voice_ids.discard("")
    voice_cast_runtime = _read_json(run_path / "audio" / "voice_cast_runtime.json")
    runtime_speakers = voice_cast_runtime.get("speaker_map") or {}
    voice_diversity = len(runtime_speakers) if runtime_speakers else len(voice_ids)
    if voice_diversity < 2 and runtime_speakers:
        voice_diversity = len(runtime_speakers)

    srt_path = run_path / "publish" / "subtitles" / "subtitles.srt"
    srt_text = srt_path.read_text(encoding="utf-8") if srt_path.is_file() else ""
    subtitle_styled = bool(
        any(token in srt_text.upper() for token in ("WOW!", "WHOA", "LOOK", "GO SEE", "HEAR THAT"))
        or bool(_read_json(run_path / "publish" / "subtitles" / "subtitles.ass"))
    )

    cinematic_audio = run_path / "audio" / "FINAL_CINEMATIC_AUDIO.mp3"
    music_mean = _probe_mean_volume(cinematic_audio) if cinematic_audio.is_file() else None
    music_present = music_mean is not None and music_mean > -42.0

    env_layers = _read_json(run_path / "timeline" / "environment_timeline.json").get("layers") or []
    env_volumes = [float(layer.get("volume") or 0) for layer in env_layers if isinstance(layer, dict)]
    env_presence = sum(env_volumes) / max(1, len(env_volumes)) if env_volumes else 0.0
    environment_audible = env_presence >= 0.14

    performance_profiles = list(metadata.get("character_performance") or [])
    story_arc = str((metadata.get("story_emotion_arc") or {}).get("arc_summary") or "")

    checks = {
        "character_count_ok": len(speakers) >= 3,
        "voice_diversity_ok": voice_diversity >= 3,
        "emotional_dialogue_density_ok": emotional_density >= 0.45 and stiff_lines == 0,
        "subtitle_styling_ok": subtitle_styled,
        "environment_presence_ok": environment_audible,
        "music_presence_ok": music_present,
        "story_emotion_arc_ok": "hook" in story_arc.lower() or "discovery" in story_arc.lower() or "→" in story_arc,
        "character_performance_profiles_ok": len(performance_profiles) >= 2,
    }
    warnings: list[str] = []
    music_meta = dict(music_plan.get("metadata") or {}).get("music_mood_selector") or {}
    if str(music_meta.get("asset_quality") or "") == "local_procedural":
        warnings.append("honest_report:music_asset_is_procedural_placeholder")
    if any("procedural" in str(item) for item in (metadata.get("environment_presence_warnings") or [])):
        warnings.append("honest_report:environment_assets_are_procedural_placeholders")

    status = "PASS" if all(checks.values()) else "FAIL"
    return EntertainmentAuditResult(
        status=status,
        checks=checks,
        metrics={
            "character_count": len(speakers),
            "spoken_line_count": len(spoken_lines),
            "emotional_dialogue_density": round(emotional_density, 3),
            "stiff_line_count": stiff_lines,
            "voice_diversity": voice_diversity,
            "environment_presence_avg_volume": round(env_presence, 4),
            "music_mean_volume_db": music_mean,
            "story_emotion_arc": story_arc,
            "music_mood": str(music_plan.get("mood") or ""),
            "music_style_label": str(music_meta.get("style_label") or ""),
        },
        warnings=warnings,
    )


def render_audit_markdown(result: EntertainmentAuditResult, *, run_id: str = "", final_video: str = "") -> str:
    lines = [
        "# Story Entertainment Audit",
        "",
        f"Audited: {result.to_dict().get('audited_at')}",
        f"Run ID: `{run_id}`",
        f"Status: **{result.status}**",
        "",
        f"Final video: `{final_video}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in result.checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    lines.extend(["", "## Metrics", ""])
    for key, value in result.metrics.items():
        lines.append(f"- {key}: `{value}`")
    if result.warnings:
        lines.extend(["", "## Honest warnings", ""])
        for item in result.warnings:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Audit story entertainment quality")
    parser.add_argument("--run-dir", default=str(ROOT / "outputs" / "runs"))
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if args.run_id:
        candidates = sorted((ROOT / "outputs" / "runs").glob(f"*{args.run_id[-8:]}*"))
        run_dir = candidates[0] if candidates else run_dir
    result = audit_story_entertainment_quality(project_root=ROOT, run_dir=run_dir)
    report_path = ROOT / "project_brain" / "STORY_ENTERTAINMENT_AUDIT.md"
    run_id = str(_read_json(run_dir / "metadata" / "run_summary.json").get("run_id") or "")
    video = run_dir / "publish" / "FINAL_BRANDED_VIDEO_v4.mp4"
    report_path.write_text(
        render_audit_markdown(result, run_id=run_id, final_video=str(video.resolve()) if video.is_file() else ""),
        encoding="utf-8",
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
