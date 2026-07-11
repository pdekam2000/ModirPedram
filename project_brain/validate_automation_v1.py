"""Validate automation v1 foundation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.automation.automation_job_runner import AutomationJobRunner
from content_brain.automation.automation_queue import AutomationQueue, JOB_COMPLETED, JOB_FAILED, JOB_PLANNED
from content_brain.comments.comment_agent import draft_comment_reply
from content_brain.upload.upload_manager import UploadManager
from ui.api.automation_service import AutomationService
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_job_can_be_created() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        queue = AutomationQueue(tmp)
        job = queue.create_job({"topic": "automation test topic", "title": "Test", "duration": 30, "clip_count": 2})
        _pass("job_created", job.status == JOB_PLANNED)
        _pass("job_has_id", bool(job.job_id))


def test_start_next_calls_generation_pipeline() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "project_brain/product_settings").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain/product_settings/channel_profile.json").write_text(
            json.dumps({"default_duration_seconds": 30, "use_ai_director_default": True}, ensure_ascii=False),
            encoding="utf-8",
        )
        (tmp / "project_brain/platform").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain/platform/automation_center.json").write_text(
            json.dumps({"enabled": True, "paused": False, "feature_flags": {"auto_upload": False}}, ensure_ascii=False),
            encoding="utf-8",
        )
        queue = AutomationQueue(tmp)
        queue.create_job({"topic": "gpu review topic", "duration": 20, "clip_count": 2})

        product_service = MagicMock()
        product_service.create_video_generate.return_value = {
            "ok": True,
            "session_id": "cb_auto_test",
            "content_brain_run_id": "cb_auto_test",
        }
        runway_service = MagicMock()
        runway_service.snapshot.return_value = {
            "active": False,
            "report": {
                "ok": True,
                "content_brain_run_id": "cb_auto_test",
                "final_branded_video_path": str(tmp / "outputs/final/FINAL_BRANDED_VIDEO.mp4"),
                "publish_package_folder": str(tmp / "outputs/publish/runway_phase_i"),
            },
        }

        runner = AutomationJobRunner(tmp)
        with patch("content_brain.automation.automation_job_runner.get_browser_health", return_value={"connected": True}):
            with patch("core.env_bootstrap.bootstrap_project_env", return_value={"loaded": True}):
                with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
                    result = runner.start_next_job(
                        product_service=product_service,
                        runway_service=runway_service,
                        poll_interval_seconds=0,
                        max_wait_seconds=1,
                    )
        _pass("start_next_ok", result.get("ok") is True, str(result))
        product_service.create_video_generate.assert_called_once()


def test_job_status_updates() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        queue = AutomationQueue(tmp)
        job = queue.create_job({"topic": "status test"})
        queue.update_job(job.job_id, status="running")
        updated = queue.get_job(job.job_id)
        _pass("status_running", updated is not None and updated.status == "running")
        queue.update_job(job.job_id, status=JOB_COMPLETED, output_path="/tmp/out.mp4")
        done = queue.get_job(job.job_id)
        _pass("status_completed", done is not None and done.status == JOB_COMPLETED)


def test_pause_resume_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        runner = AutomationJobRunner(tmp)
        runner.pause()
        status = runner.get_status()
        _pass("paused_true", status.get("paused") is True)
        runner.resume()
        status = runner.get_status()
        _pass("paused_false", status.get("paused") is False)


def test_failed_job_records_error() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        queue = AutomationQueue(tmp)
        job = queue.create_job({"topic": "fail test"})
        runner = AutomationJobRunner(tmp)
        result = runner._finalize_job(job.job_id, {"ok": False, "error": "simulated_failure"})
        _pass("failed_status", result.get("status") == JOB_FAILED)
        stored = queue.get_job(job.job_id)
        _pass("failed_error", stored is not None and stored.error == "simulated_failure")


def test_upload_package_created() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "project_brain/product_settings").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain/product_settings/channel_profile.json").write_text(
            json.dumps({"youtube_default_description": "desc", "youtube_default_hashtags": ["#shorts"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        video = tmp / "video.mp4"
        video.write_bytes(b"video")
        manager = UploadManager(tmp)
        package = manager.prepare_upload_package(
            topic="test topic",
            platform_targets=["youtube_shorts", "tiktok", "instagram_reels"],
            video_path=str(video),
            run_id="run_test",
        )
        _pass("upload_package_dir", Path(str(package.get("package_dir"))).is_dir())
        _pass("upload_targets", len(package.get("targets") or []) >= 3)


def test_youtube_upload_defaults_private() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "project_brain/product_settings").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain/product_settings/channel_profile.json").write_text(
            json.dumps({"youtube_upload_enabled": True, "youtube_privacy": "private"}, ensure_ascii=False),
            encoding="utf-8",
        )
        manager = UploadManager(tmp)
        blocked = manager.submit_youtube_upload(confirmed=False)
        _pass("confirmation_required", blocked.get("status") == "confirmation_required")
        _pass("privacy_private", blocked.get("privacy") == "private")


def test_comment_agent_creates_draft_only() -> None:
    draft = draft_comment_reply(
        comment_text="What GPU should I buy?",
        video_topic="best graphics cards",
        channel_tone="friendly",
        use_openai=False,
    )
    _pass("draft_reply", bool(draft.get("suggested_reply")))
    _pass("approve_required", draft.get("approve_required") is True)
    _pass("no_auto_post", draft.get("auto_posted") is False)


def test_no_auto_comment_posting() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        service = AutomationService(tmp)
        service.draft_comment_reply({"comment_text": "Nice video!", "use_openai": False})
        approved = service.approve_comment_draft({"index": 0})
        _pass("approve_not_post", approved.get("posted") is False)


def test_no_auto_upload_unless_enabled() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "project_brain/product_settings").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain/product_settings/channel_profile.json").write_text(
            json.dumps({"youtube_upload_enabled": False}, ensure_ascii=False),
            encoding="utf-8",
        )
        manager = UploadManager(tmp)
        result = manager.submit_youtube_upload(confirmed=True)
        _pass("upload_blocked", result.get("status") == "blocked")


def test_manual_generate_still_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "project_brain/product_settings").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain/product_settings/channel_profile.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
        service = ProductStudioService(tmp)
        preflight = service.create_video_preflight(
            {"topic_mode": "custom", "custom_topic": "manual topic", "duration_seconds": 30, "provider": "runway"}
        )
        _pass("manual_preflight_ok", bool(preflight.get("authoritative_topic")))


def test_runway_automation_unchanged() -> None:
    smoke_source = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator_source = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("smoke_no_automation_runner", "automation_job_runner" not in smoke_source)
    _pass("navigator_untouched", "automation_job_runner" not in navigator_source)


def main() -> None:
    test_job_can_be_created()
    test_start_next_calls_generation_pipeline()
    test_job_status_updates()
    test_pause_resume_works()
    test_failed_job_records_error()
    test_upload_package_created()
    test_youtube_upload_defaults_private()
    test_comment_agent_creates_draft_only()
    test_no_auto_comment_posting()
    test_no_auto_upload_unless_enabled()
    test_manual_generate_still_works()
    test_runway_automation_unchanged()
    print("All automation v1 validations passed.")


if __name__ == "__main__":
    main()
