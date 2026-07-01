"""Validate final deliverable quality signals — subtitles, narration, music, CTA, branding."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_RUN_ID = "cb_e2e_20260611_225308_dc20bc1f"
TARGET_RUN_DIR = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _run_validator(rel: str) -> None:
    proc = subprocess.run([sys.executable, str(ROOT / rel)], cwd=str(ROOT), capture_output=True, text=True)
    _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-220:])


def main() -> None:
    burn_src = (ROOT / "content_brain" / "branding" / "subtitle_burn_engine.py").read_text(encoding="utf-8")
    cta_src = (ROOT / "content_brain" / "branding" / "cta_engine.py").read_text(encoding="utf-8")
    narration_src = (ROOT / "content_brain" / "audio" / "narration_script_builder.py").read_text(encoding="utf-8")

    _pass("subtitle_runtime_v3", "subtitle_burn_engine_v3" in burn_src)
    _pass("narration_builder_v2", "narration_script_builder_v2" in narration_src)
    _pass("narration_guard_wired", "validate_narration_source" in narration_src)
    _pass("cta_runtime_v3", "cta_engine_v3" in cta_src)
    _pass("cta_fade_metadata", "cta_fade_seconds" in cta_src)

    print("\n=== Component validators ===")
    _run_validator("project_brain/validate_subtitle_visual_quality.py")
    _run_validator("project_brain/validate_narration_source_guard.py")
    _run_validator("project_brain/validate_music_runtime_local.py")

    from content_brain.platform.results_run_loader import load_run_results  # noqa: E402

    results = load_run_results(ROOT, run_id=TARGET_RUN_ID)
    branded = Path(str(results.get("video_path") or results.get("final_branded_video_path") or ""))
    _pass("branded_video_resolved", bool(str(branded)))
    if branded.is_file():
        _pass("branded_video_exists", True, str(branded))
    else:
        _pass("branded_video_exists", branded.is_file(), str(branded))

    publish_manifest = json.loads((TARGET_RUN_DIR / "metadata" / "publish_manifest.json").read_text(encoding="utf-8"))
    branding_status = str(publish_manifest.get("branding_status") or "")
    _pass("branding_completed", branding_status == "completed", branding_status)

    audio_manifest_path = ROOT / "project_brain" / "runtime_state" / "runway_phase_i_audio_manifest.json"
    if audio_manifest_path.is_file():
        audio_manifest = json.loads(audio_manifest_path.read_text(encoding="utf-8"))
        script_path = Path(str(audio_manifest.get("narration_script_path") or ""))
        if script_path.is_file():
            script_text = script_path.read_text(encoding="utf-8").lower()
            _pass("narration_no_runtime_leak", "runtime" not in script_text and "settings" not in script_text)
        music_label = str(audio_manifest.get("music_status") or (audio_manifest.get("music_runtime") or {}).get("status_label") or "")
        _pass("music_status_reported", bool(music_label), music_label)

    srt_path = TARGET_RUN_DIR / "publish" / "subtitles" / "subtitles.srt"
    if srt_path.is_file():
        srt_text = srt_path.read_text(encoding="utf-8")
        max_lines = max((len(block.splitlines()[2:]) for block in srt_text.strip().split("\n\n") if block.strip()), default=0)
        _pass("publish_srt_max_two_lines", max_lines <= 2, f"max_lines={max_lines}")

    print("\nAll final video quality validations passed.")


if __name__ == "__main__":
    main()
