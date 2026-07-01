"""PHASE STORY-AUDIO-2 — voice presence auditor validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.quality.voice_presence_auditor import VOICE_PRESENCE_AUDITOR_VERSION, audit_voice_presence


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_voice_presence_auditor ===")
    run_dir = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"
    manifest_path = run_dir / "audio" / "cinematic_audio_manifest.json"
    if not manifest_path.is_file():
        print("[SKIP] cinematic manifest missing — run recover_story_audio_v1.py first")
        raise SystemExit(0)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    context = {
        "dialogue_dir": manifest.get("dialogue_dir"),
        "speech_result": manifest.get("speech_result"),
        "performance_plan": manifest.get("performance_plan"),
    }
    audit = audit_voice_presence(context)
    _pass("version", VOICE_PRESENCE_AUDITOR_VERSION == "voice_presence_auditor_v1")
    _pass("pass", audit.status == "PASS", str(audit.failures))
    _pass("whiskers_sage", audit.character_count >= 2, str(audit.detected_speakers))
    _pass("not_single_track", audit.checks.get("not_single_narration_track") is True)
    print("=== complete ===")


if __name__ == "__main__":
    main()
