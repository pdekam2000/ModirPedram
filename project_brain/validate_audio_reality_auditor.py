"""PHASE STORY-AUDIO-2 — audio reality auditor validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.quality.audio_reality_auditor import AUDIO_REALITY_AUDITOR_VERSION, audit_audio_reality


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_audio_reality_auditor ===")
    run_dir = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"
    manifest_path = run_dir / "audio" / "cinematic_audio_manifest.json"
    if not manifest_path.is_file():
        print("[SKIP] cinematic manifest missing — run recover_story_audio_v1.py first")
        raise SystemExit(0)
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    context = {
        "run_dir": str(run_dir),
        "dialogue_dir": manifest.get("dialogue_dir"),
        "timeline_dir": manifest.get("timeline_dir"),
        "cinematic_audio_path": (manifest.get("mix_result") or {}).get("output_path"),
        "cinematic_video_path": (manifest.get("video_result") or {}).get("output_path"),
        "speech_result": manifest.get("speech_result"),
        "dialogue_timeline": json.loads((run_dir / "timeline" / "dialogue_timeline.json").read_text(encoding="utf-8")),
        "environment_timeline": json.loads((run_dir / "timeline" / "environment_timeline.json").read_text(encoding="utf-8")),
        "music_timeline": json.loads((run_dir / "timeline" / "music_timeline.json").read_text(encoding="utf-8")),
    }
    audit = audit_audio_reality(context)
    empty = audit_audio_reality({})
    _pass("version", AUDIO_REALITY_AUDITOR_VERSION == "audio_reality_auditor_v1")
    _pass("cartoon_pass", audit.status == "PASS", str(audit.failures))
    _pass("quality_score", audit.quality_score >= 80, str(audit.quality_score))
    _pass("empty_fail", empty.status == "FAIL")
    print("=== complete ===")


if __name__ == "__main__":
    main()
