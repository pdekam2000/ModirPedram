#!/usr/bin/env python3
"""Validate auto YouTube upload after publish (PHASE AUTO-YOUTUBE-UPLOAD-AFTER-PUBLISH)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.automation.auto_youtube_upload_after_publish import (  # noqa: E402
    evaluate_auto_youtube_upload_eligibility,
    maybe_auto_youtube_upload_after_publish,
)
from content_brain.execution.product_subtitle_branding_publish import (  # noqa: E402
    FINAL_BRANDED_PUBLISH_READY_NAME,
    PUBLISH_PACKAGE_NAME,
)
from content_brain.execution.product_publish_pipeline_trace import (  # noqa: E402
    run_publish_post_processing_chain,
)
from content_brain.publish.youtube_metadata_generator import YOUTUBE_METADATA_FILENAME  # noqa: E402
from content_brain.upload.youtube_upload_runtime import YOUTUBE_UPLOAD_RESULT_NAME  # noqa: E402

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark}] {name}{suffix}")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_publish_ready(tmp: Path) -> tuple[Path, Path]:
    run_dir = tmp / "outputs" / "pwmap_agent_runs" / "pwmap_test_auto_upload"
    publish = run_dir / "publish"
    publish.mkdir(parents=True, exist_ok=True)
    branded = publish / FINAL_BRANDED_PUBLISH_READY_NAME
    branded.write_bytes(b"\x00" * 2048)
    _write_json(
        publish / PUBLISH_PACKAGE_NAME,
        {"publish_ready": True, "run_id": "pwmap_test_auto_upload"},
    )
    _write_json(
        publish / YOUTUBE_METADATA_FILENAME,
        {"title": "Test title", "description": "Test", "tags": ["test"], "hashtags": ["#test"]},
    )
    _write_json(
        tmp / "project_brain" / "automation_center.json",
        {
            "youtube": {
                "auto_upload_enabled": True,
                "default_visibility": "private",
                "publish_now": True,
                "allow_public_auto_upload": False,
                "require_manual_public_approval": True,
            }
        },
    )
    _write_json(
        tmp / "project_brain" / "product_settings" / "channel_profile.json",
        {
            "youtube_upload_enabled": True,
            "youtube_privacy": "private",
            "youtube_require_confirmation": True,
            "youtube_upload_confirmed": False,
        },
    )
    _write_json(
        tmp / "project_brain" / "upload" / "youtube_oauth_token.json",
        {"refresh_token": "test", "access_token": "test-access", "token": "test"},
    )
    _write_json(
        tmp / "project_brain" / "upload" / "youtube_account.json",
        {"channel_id": "UCtest", "channel_name": "Test Channel"},
    )
    return run_dir, publish


def test_private_auto_upload_triggers() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        run_dir, publish = _seed_publish_ready(tmp)
        branding = {"publish_ready": True, "branding_status": "completed", "publish_package_path": str(publish)}
        assembly = {"ok": True, "source_clip_count": 2}

        with patch(
            "content_brain.automation.auto_youtube_upload_after_publish.get_youtube_auth_status",
            return_value={"authenticated": True, "channel_id": "UCtest"},
        ), patch(
            "content_brain.upload.youtube_upload_runtime.validate_mp4_path",
            return_value={"valid": True, "size_bytes": 2048},
        ), patch(
            "content_brain.upload.youtube_upload_runtime.upload_video_to_youtube",
            return_value={
                "ok": True,
                "youtube_video_id": "abc123",
                "youtube_url": "https://www.youtube.com/watch?v=abc123",
                "visibility": "private",
                "upload_time": "2026-06-27T00:00:00+00:00",
            },
        ):
            result = maybe_auto_youtube_upload_after_publish(
                project_root=tmp,
                run_dir=run_dir,
                run_id="pwmap_test_auto_upload",
                publish_dir=publish,
                branding_publish_result=branding,
                assembly_result=assembly,
                expected_clip_count=2,
            )
        record("private_auto_upload_triggers", bool(result.get("uploaded")), str(result.get("upload_status")))
        record("upload_result_written", (publish / YOUTUBE_UPLOAD_RESULT_NAME).is_file())
        record("upload_confirmed_private", result.get("uploaded") and result.get("visibility") == "private")


def test_public_auto_upload_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        run_dir, publish = _seed_publish_ready(tmp)
        config_path = tmp / "project_brain" / "automation_center.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["youtube"]["default_visibility"] = "public"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        eligibility = evaluate_auto_youtube_upload_eligibility(
            project_root=tmp,
            run_dir=run_dir,
            publish_dir=publish,
            branding_publish_result={"publish_ready": True, "branding_status": "completed"},
            assembly_result={"ok": True, "source_clip_count": 2},
            expected_clip_count=2,
        )
        record(
            "public_auto_upload_blocked",
            not eligibility.get("eligible")
            and eligibility.get("blocked_reason") == "public_upload_requires_manual_approval",
            str(eligibility.get("blocked_reason")),
        )


def test_visual_diversity_blocks_upload() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        run_dir, publish = _seed_publish_ready(tmp)
        eligibility = evaluate_auto_youtube_upload_eligibility(
            project_root=tmp,
            run_dir=run_dir,
            publish_dir=publish,
            branding_publish_result={"publish_ready": True, "branding_status": "completed"},
            assembly_result={"ok": True, "source_clip_count": 2},
            visual_diversity={"status": "visual_repetition_failed", "youtube_upload_allowed": False},
            expected_clip_count=2,
        )
        record(
            "visual_diversity_blocks_upload",
            eligibility.get("blocked_reason") == "upload_blocked_visual_diversity",
            str(eligibility.get("blocked_reason")),
        )


def test_missing_publish_package_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        run_dir, publish = _seed_publish_ready(tmp)
        (publish / PUBLISH_PACKAGE_NAME).unlink()
        eligibility = evaluate_auto_youtube_upload_eligibility(
            project_root=tmp,
            run_dir=run_dir,
            publish_dir=publish,
            branding_publish_result={"publish_ready": False, "branding_status": "completed"},
            assembly_result={"ok": True},
        )
        record(
            "missing_publish_package_blocks",
            not eligibility.get("eligible") and eligibility.get("blocked_reason") == "publish_not_ready",
            str(eligibility.get("blocked_reason")),
        )


def test_missing_oauth_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        run_dir, publish = _seed_publish_ready(tmp)
        with patch(
            "content_brain.automation.auto_youtube_upload_after_publish.get_youtube_auth_status",
            return_value={"authenticated": False},
        ):
            eligibility = evaluate_auto_youtube_upload_eligibility(
                project_root=tmp,
                run_dir=run_dir,
                publish_dir=publish,
                branding_publish_result={"publish_ready": True, "branding_status": "completed"},
                assembly_result={"ok": True, "source_clip_count": 2},
                expected_clip_count=2,
            )
        record(
            "missing_oauth_blocks",
            eligibility.get("blocked_reason") == "oauth_not_available",
            str(eligibility.get("blocked_reason")),
        )


def test_static_wiring() -> None:
    pipeline_src = (ROOT / "content_brain" / "execution" / "product_publish_pipeline_trace.py").read_text(
        encoding="utf-8"
    )
    orchestrator_src = (ROOT / "content_brain" / "execution" / "product_multiclip_orchestrator.py").read_text(
        encoding="utf-8"
    )
    service_src = (ROOT / "ui" / "api" / "product_studio_service.py").read_text(encoding="utf-8")
    results_src = (ROOT / "ui" / "web" / "src" / "pages" / "ResultsPage.tsx").read_text(encoding="utf-8")
    config_path = ROOT / "project_brain" / "automation_center.json"

    record("pipeline_calls_auto_upload", "maybe_auto_youtube_upload_after_publish" in pipeline_src)
    record("orchestrator_attempt_auto_upload", "attempt_auto_youtube_upload=True" in orchestrator_src)
    record("generation_path_unchanged", "run_pwmap_product_studio_generate" in orchestrator_src)
    record("results_auto_upload_fields", "auto_upload_enabled" in service_src and "auto_upload_started" in results_src)
    record("automation_center_config_exists", config_path.is_file(), str(config_path))
    record(
        "publish_chain_still_has_assembly",
        "run_product_assembly_bridge" in pipeline_src and "run_product_subtitle_branding_publish" in pipeline_src,
    )


def main() -> int:
    print("validate_auto_youtube_upload_after_publish")
    test_static_wiring()
    test_private_auto_upload_triggers()
    test_public_auto_upload_blocked()
    test_visual_diversity_blocks_upload()
    test_missing_publish_package_blocks()
    test_missing_oauth_blocks()
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\nSummary: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
