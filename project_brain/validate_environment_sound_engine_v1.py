"""PHASE QUALITY-FIX-2 — environment sound engine validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.environment_sound_engine import build_environment_sound_plan, detect_environment_from_scene


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_environment_sound_engine_v1 ===")
    forest = detect_environment_from_scene(topic="cartoon cat in magical forest", scene_text="trees leaves wind")
    jungle = detect_environment_from_scene(topic="jungle adventure", scene_text="rainforest insects")
    _pass("forest_detected", forest == "forest", forest)
    _pass("jungle_detected", jungle == "jungle", jungle)

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        missing = build_environment_sound_plan(project_root=tmp, topic="cartoon cat forest explorer", environment="forest")
        _pass("missing_ambience_warning", missing.status == "warning_missing_assets", missing.status)
        _pass("missing_not_pass", "PASS" not in missing.status.upper())
        _pass("missing_warning_message", any("ambience" in item for item in missing.warnings))

    resolved = build_environment_sound_plan(project_root=ROOT, topic="cartoon cat forest explorer", environment="forest")
    if resolved.resolved_ambience_files:
        _pass("root_ambience_files_optional", True, str(len(resolved.resolved_ambience_files)))
    else:
        _pass("root_ambience_files_optional", True, "none configured")
    print("=== complete ===")


if __name__ == "__main__":
    main()
