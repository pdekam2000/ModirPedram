"""Validation — PHASE PRODUCT-VISUAL-DIVERSITY-GUARD."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.product_visual_diversity_guard import (  # noqa: E402
    VisualDiversityReport,
    append_visual_diversity_rules,
    build_use_frame_variation_directive,
    detect_post_generation_visual_repetition,
    detect_prompt_repetition_risk,
    merge_results_visual_diversity_fields,
    run_pre_generation_diversity_gate,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402
from ui.api.upload_service import UploadService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def main() -> int:
    print("validate_product_visual_diversity_guard")
    print("=" * 60)

    identical = [
        "Wide cinematic shot of a hero discovering a glowing artifact in the rain.",
        "Wide cinematic shot of a hero discovering a glowing artifact in the rain.",
        "Wide cinematic shot of a hero discovering a glowing artifact in the rain.",
        "Wide cinematic shot of a hero discovering a glowing artifact in the rain.",
    ]
    blocked = run_pre_generation_diversity_gate(identical)
    _record(
        "near_identical_prompts_blocked",
        blocked.get("ok") is False and blocked.get("repetition_risk") == "high",
        str(blocked.get("status")),
    )

    diverse = [
        append_visual_diversity_rules("Clip one establishing wide shot.", clip_index=1, clip_count=4),
        append_visual_diversity_rules("Clip two medium pursuit through corridor.", clip_index=2, clip_count=4),
        append_visual_diversity_rules("Clip three close-up reveal on object.", clip_index=3, clip_count=4),
        append_visual_diversity_rules("Clip four resolution pullback.", clip_index=4, clip_count=4),
    ]
    passed = run_pre_generation_diversity_gate(diverse)
    _record(
        "diverse_prompts_pass",
        passed.get("ok") is True and not passed.get("blocked"),
        str(passed.get("repetition_risk")),
    )

    use_frame = build_use_frame_variation_directive(clip_index=2, clip_count=4)
    _record(
        "use_frame_continuity_allowed",
        "Use Frame" in use_frame and "preserve character identity" in use_frame and "new action" in use_frame,
        use_frame[:120],
    )

    failed_report = VisualDiversityReport(
        visual_diversity_score=20,
        repetition_risk="high",
        status="visual_repetition_failed",
        publish_ready=False,
        youtube_upload_allowed=False,
        repeated_clip_warning=True,
    )
    upload_service = UploadService(ROOT)
    with patch(
        "content_brain.upload.youtube_upload_runtime.run_youtube_upload_from_publish_package",
        return_value={"uploaded": True},
    ), patch(
        "content_brain.upload.youtube_upload_runtime.resolve_publish_dir_for_run",
        return_value=Path(tempfile.gettempdir()),
    ), patch(
        "content_brain.execution.product_visual_diversity_guard.load_visual_diversity_report",
        return_value=failed_report.to_dict(),
    ):
        blocked_upload = upload_service.submit_publish_package_upload(
            {"run_id": "test", "publish_package_path": str(Path(tempfile.gettempdir())), "confirmed": True}
        )
    _record(
        "upload_blocked_when_visual_repetition_failed",
        blocked_upload.get("error") == "visual_repetition_blocked",
        str(blocked_upload.get("error")),
    )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        for index in range(1, 5):
            path = run_dir / f"clip_{index}.mp4"
            path.write_bytes(bytes([index]) * 1_200_000)
        with patch(
            "content_brain.execution.product_visual_diversity_guard._extract_frame_signature",
            side_effect=lambda video_path: [1.0, 0.2, 0.3] if "clip_1" in str(video_path) else [1.0, 0.2, 0.29],
        ):
            post = detect_post_generation_visual_repetition(run_dir=run_dir, clip_count=4)
        _record(
            "post_generation_visual_repetition_detected",
            post.status == "visual_repetition_failed" and post.publish_ready is False,
            str(post.status),
        )

    orchestrator_src = (ROOT / "content_brain" / "execution" / "product_multiclip_orchestrator.py").read_text(encoding="utf-8")
    _record(
        "repetitive_video_skips_publish_pipeline",
        "visual_repetition_failed" in orchestrator_src and "return pwmap_result" in orchestrator_src,
        "orchestrator gate",
    )

    service = ProductStudioService(ROOT)
    merged = service._merge_pwmap_results(
        {
            "run_id": "pwmap_test",
            "visual_diversity": failed_report.to_dict(),
            "publish_ready": True,
        }
    )
    _record(
        "results_displays_visual_diversity_warnings",
        merged.get("visual_diversity_score") == 20
        and merged.get("repeated_clip_warning") is True
        and merged.get("publish_ready") is False,
        str(merged.get("visual_diversity_status")),
    )

    merged_fields = merge_results_visual_diversity_fields({"publish_ready": True}, failed_report.to_dict())
    _record(
        "publish_ready_cleared_on_repetition",
        merged_fields.get("publish_ready") is False and merged_fields.get("youtube_upload_allowed") is False,
        str(merged_fields.get("visual_diversity_status")),
    )

    adapter_src = (ROOT / "content_brain" / "execution" / "pwmap_runway_agent_adapter.py").read_text(encoding="utf-8")
    assembly_src = (ROOT / "content_brain" / "execution" / "product_assembly_bridge.py").read_text(encoding="utf-8")
    upload_runtime_src = (ROOT / "content_brain" / "upload" / "youtube_upload_runtime.py").read_text(encoding="utf-8")
    _record("pwmap_browser_mappings_unmodified", "product_visual_diversity_guard" not in adapter_src, "static scan")
    _record("assembly_bridge_unmodified", "product_visual_diversity_guard" not in assembly_src, "static scan")
    _record("youtube_upload_runtime_unmodified", "product_visual_diversity_guard" not in upload_runtime_src, "static scan")

    results_page = (ROOT / "ui" / "web" / "src" / "pages" / "ResultsPage.tsx").read_text(encoding="utf-8")
    _record("results_ui_visual_diversity_panel", "Visual Diversity" in results_page and "similar_clip_pairs" in results_page, "ui")

    failed_items = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"TOTAL: {len(results)}  PASS: {len(results) - len(failed_items)}  FAIL: {len(failed_items)}")
    if failed_items:
        print("FAILED:", ", ".join(failed_items))
        return FAIL
    print("ALL PASS")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
