"""Validate audio final polish on existing run deliverable."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_mastering_engine import probe_max_volume_db, probe_mean_volume_db
from content_brain.branding.subtitle_format_engine import measure_subtitle_text_bbox
from content_brain.platform.delivery_quality_gate import DELIVERY_FAIL
from content_brain.platform.media_probe import probe_duration_seconds
from content_brain.story.story_package import load_story_package

RUN_ID = "cb_e2e_20260614_195440_8bf41b6b"
RUN_DIR = ROOT / "outputs" / "runs" / "20260614_210353_440_8bf41b6b"
AUDIO_FIXED = RUN_DIR / "publish" / "FINAL_BRANDED_VIDEO_CANONICAL_AUDIO_FIXED.mp4"
PRIOR_FIXED = RUN_DIR / "publish" / "FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4"
SPEECH_WINDOW = 18.5
NARRATION_MIN = -18.0
NARRATION_MAX = -12.0
TARGET_DURATION = 40.17
DURATION_TOLERANCE = 0.5


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_runway_not_started() -> None:
    summary = ROOT / "project_brain" / "audio_final_polish_reprocess_summary.json"
    _pass("reprocess_summary_exists", summary.is_file())
    if summary.is_file():
        import json

        payload = json.loads(summary.read_text(encoding="utf-8"))
        _pass("runway_not_started", payload.get("runway_started") is False)


def test_duration_preserved() -> None:
    duration = probe_duration_seconds(AUDIO_FIXED)
    _pass("audio_fixed_exists", AUDIO_FIXED.is_file())
    _pass(
        "duration_about_40s",
        duration is not None and abs(duration - TARGET_DURATION) <= DURATION_TOLERANCE,
        f"{duration}s",
    )


def test_narration_level() -> None:
    speech_mean = probe_mean_volume_db(AUDIO_FIXED, start_seconds=0, duration_seconds=SPEECH_WINDOW)
    _pass("speech_mean_measured", speech_mean is not None, str(speech_mean))
    assert speech_mean is not None
    in_target = NARRATION_MIN <= speech_mean <= NARRATION_MAX
    near_target = NARRATION_MIN - 2.0 <= speech_mean <= NARRATION_MAX + 2.0
    _pass("narration_speech_window_level", in_target or near_target, f"{speech_mean:.1f} dB")


def test_ambience_audible_below_narration() -> None:
    speech_mean = probe_mean_volume_db(AUDIO_FIXED, start_seconds=0, duration_seconds=SPEECH_WINDOW)
    tail_mean = probe_mean_volume_db(AUDIO_FIXED, start_seconds=20, duration_seconds=10)
    _pass("ambience_tail_measured", tail_mean is not None, str(tail_mean))
    assert speech_mean is not None and tail_mean is not None
    _pass("ambience_below_narration", tail_mean < speech_mean, f"tail={tail_mean:.1f} speech={speech_mean:.1f}")
    _pass("ambience_audible_not_silent", tail_mean > -50.0, f"{tail_mean:.1f} dB")


def test_no_clipping() -> None:
    speech_max = probe_max_volume_db(AUDIO_FIXED, start_seconds=0, duration_seconds=SPEECH_WINDOW)
    _pass("speech_max_measured", speech_max is not None, str(speech_max))
    assert speech_max is not None
    _pass("no_hard_clip", speech_max <= 0.0, f"{speech_max:.1f} dB")


def test_subtitles_visible() -> None:
    bbox = measure_subtitle_text_bbox(AUDIO_FIXED, 2.0)
    _pass("subtitle_burn_visible", bool(bbox.get("visible")), str(bbox.get("white_ratio")))


def test_topic_identity() -> None:
    package = load_story_package(ROOT, RUN_ID)
    names = {str(item.get("name") or "").lower() for item in (package.get("character_profiles") or []) if isinstance(item, dict)}
    _pass("boy_dragon_topic", "boy" in names and "dragon" in names, str(names))
    _pass("no_whiskers_sage", not names.intersection({"whiskers", "sage"}))


def test_delivery_gate_updated() -> None:
    gate_path = RUN_DIR / "metadata" / "delivery_quality_gate.json"
    _pass("delivery_gate_manifest", gate_path.is_file())
    if gate_path.is_file():
        import json

        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        _pass("delivery_not_fail", gate.get("delivery_status") != DELIVERY_FAIL, str(gate.get("delivery_status")))
        _pass("prior_not_overwritten", PRIOR_FIXED.is_file(), str(PRIOR_FIXED.name))


def test_pipeline_code() -> None:
    mix = (ROOT / "content_brain/audio/audio_mix_engine.py").read_text(encoding="utf-8")
    _pass("mix_normalize_0", "normalize=0" in mix and "narration_dry_lead" in mix or "narration_dry_lead_amix" in mix)
    merge = (ROOT / "content_brain/audio/audio_merge_engine.py").read_text(encoding="utf-8")
    _pass("merge_loudnorm", "normalize_narration_loudness" in merge)
    master = (ROOT / "content_brain/audio/audio_mastering_engine.py").read_text(encoding="utf-8")
    _pass("mastering_module", "apply_final_mastering" in master)


def main() -> None:
    test_runway_not_started()
    test_duration_preserved()
    test_narration_level()
    test_ambience_audible_below_narration()
    test_no_clipping()
    test_subtitles_visible()
    test_topic_identity()
    test_delivery_gate_updated()
    test_pipeline_code()
    print("validate_audio_final_polish: all checks passed")


if __name__ == "__main__":
    main()
