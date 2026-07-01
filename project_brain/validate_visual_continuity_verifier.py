"""Phase DIRECTOR-4 — Visual Continuity Verifier validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.director.visual_subject_lock import extract_visual_subject_lock
from content_brain.vision.frame_extractor import ExtractedFrames
from content_brain.vision.openai_vision_reviewer import review_frames_with_openai
from content_brain.vision.visual_continuity_pipeline import run_visual_continuity_verification, visual_continuity_report_path
from content_brain.vision.visual_continuity_verifier import ISSUE_FORBIDDEN_CONFUSION, verify_clip_frames
from ui.api.product_studio_service import ProductStudioService

SCORPION_TOPIC = "scorpion"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _run(rel: str) -> None:
    script = ROOT / rel
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-240:])


def _dummy_frames(tmp: Path) -> ExtractedFrames:
    frame_dir = tmp / "clip_1"
    frame_dir.mkdir(parents=True, exist_ok=True)
    for name in ("frame_first.jpg", "frame_middle.jpg", "frame_last.jpg"):
        path = frame_dir / name
        path.write_bytes(b"\xff\xd8\xff\xd9")
    return ExtractedFrames(
        video_path=str(tmp / "clip.mp4"),
        output_dir=str(frame_dir),
        first_frame=str(frame_dir / "frame_first.jpg"),
        middle_frame=str(frame_dir / "frame_middle.jpg"),
        last_frame=str(frame_dir / "frame_last.jpg"),
    )


def test_subject_match_pass() -> None:
    lock = extract_visual_subject_lock(topic=SCORPION_TOPIC)
    frames = _dummy_frames(ROOT / "outputs" / "vision" / "validator_tmp_pass")
    result = verify_clip_frames(
        clip_index=1,
        topic=SCORPION_TOPIC,
        video_path=str(frames.video_path),
        frames=frames,
        visual_subject_lock=lock,
        dry_run=True,
    )
    _pass("subject_match_pass", result.pass_, str(result.score))


def test_forbidden_confusion_fail() -> None:
    lock = extract_visual_subject_lock(topic=SCORPION_TOPIC)
    frames = _dummy_frames(ROOT / "outputs" / "vision" / "validator_tmp_fail")

    def _spider_review(**kwargs):
        return (
            {
                "primary_subject": "spider",
                "matches_expected": False,
                "forbidden_confusion_detected": True,
                "forbidden_confusion_label": "spider",
                "same_species_or_object": False,
                "confidence_score": 88.0,
                "notes": "Spider detected.",
                "source": "mock",
            },
            ["mock_spider_review"],
        )

    with patch("content_brain.vision.visual_continuity_verifier.review_frames_with_openai", side_effect=_spider_review):
        result = verify_clip_frames(
            clip_index=2,
            topic=SCORPION_TOPIC,
            video_path=str(frames.video_path),
            frames=frames,
            visual_subject_lock=lock,
            dry_run=False,
        )
    _pass("forbidden_confusion_fail", not result.pass_, str(result.issues))
    _pass("forbidden_issue_present", ISSUE_FORBIDDEN_CONFUSION in result.issues)
    _pass("detected_spider", "spider" in result.detected_subject.lower())


def test_visual_report_generated() -> None:
    tmp_video = ROOT / "outputs" / "vision" / "validator_tmp_report" / "clip.mp4"
    tmp_video.parent.mkdir(parents=True, exist_ok=True)
    tmp_video.write_bytes(b"not-a-real-video")

    frames = _dummy_frames(tmp_video.parent)

    def _fake_extract(video_path, *, output_dir, clip_index=1):
        return frames

    with patch("content_brain.vision.visual_continuity_pipeline.extract_analysis_frames", side_effect=_fake_extract):
        report = run_visual_continuity_verification(
            project_root=ROOT,
            topic=SCORPION_TOPIC,
            clip_video_paths=[str(tmp_video)],
            run_id="validator_report_test",
            dry_run=True,
        )
    report_path = visual_continuity_report_path(ROOT)
    _pass("report_generated", report_path.is_file())
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    _pass("report_has_clips", len(payload.get("clips") or []) == 1, str(payload.get("overall_score")))


def test_openai_vision_dry_run() -> None:
    frames = _dummy_frames(ROOT / "outputs" / "vision" / "validator_tmp_vision")
    review, notes = review_frames_with_openai(
        topic=SCORPION_TOPIC,
        expected_subject="black scorpion",
        forbidden_confusions=["spider"],
        frame_paths=frames.frame_paths(),
        dry_run=True,
    )
    _pass("openai_vision_dry_run", review.get("matches_expected") is True, ",".join(notes))


def test_runway_automation_untouched() -> None:
    protected = [
        ROOT / "content_brain" / "execution" / "runway_ui_navigator.py",
        ROOT / "content_brain" / "execution" / "runway_live_smoke_test.py",
    ]
    smoke_text = protected[1].read_text(encoding="utf-8")
    _pass("runway_ui_navigator_exists", protected[0].is_file())
    _pass("runway_smoke_exists", protected[1].is_file())
    _pass("no_selector_changes_in_smoke", "visual_continuity_verifier" not in smoke_text)


def test_latest_results_visual_continuity_wiring() -> None:
    service = ProductStudioService(ROOT)
    results = service.latest_results()
    report = results.get("visual_continuity_report") or results.get("visual_continuity") or {}
    _pass("latest_results_has_visual_continuity", bool(results.get("visual_continuity")))
    _pass("latest_results_has_visual_continuity_report", bool(results.get("visual_continuity_report")))
    _pass("latest_results_clips_present", bool(report.get("clips")), str(len(report.get("clips") or [])))


def main() -> None:
    print("=== Phase DIRECTOR-4 Visual Continuity Verifier Validation ===")
    test_subject_match_pass()
    test_forbidden_confusion_fail()
    test_visual_report_generated()
    test_openai_vision_dry_run()
    test_latest_results_visual_continuity_wiring()
    test_runway_automation_untouched()
    print("\n=== Regression ===")
    _run("project_brain/validate_visual_subject_lock.py")
    print("\nVisual Continuity Verifier validation complete — PASS")


if __name__ == "__main__":
    main()
