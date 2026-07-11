"""Validate upload agent v1 — metadata, packages, YouTube safety, automation hook."""

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
from content_brain.automation.automation_queue import AutomationQueue, JOB_PLANNED
from content_brain.upload.platform_metadata_agent import generate_platform_metadata
from content_brain.upload.upload_manager import UploadManager
from content_brain.upload.upload_models import PLATFORM_INSTAGRAM, PLATFORM_TIKTOK, PLATFORM_YOUTUBE
from content_brain.upload.upload_package_builder import build_upload_packages


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write_profile(tmp: Path, payload: dict) -> None:
    path = tmp / "project_brain/product_settings/channel_profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_youtube_metadata_generated() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _write_profile(tmp, {"channel_name": "Tech Lab", "youtube_default_hashtags": ["shorts"]})
        meta = generate_platform_metadata(
            video_topic="GPU benchmark tips",
            channel_profile=json.loads((tmp / "project_brain/product_settings/channel_profile.json").read_text(encoding="utf-8")),
            platform=PLATFORM_YOUTUBE,
            use_openai=False,
        )
        _pass("youtube_title", bool(meta.get("title")))
        _pass("youtube_description", bool(meta.get("description")))
        _pass("youtube_hashtags", bool(meta.get("hashtags")))
        _pass("youtube_pinned_comment", bool(meta.get("pinned_comment")))


def test_tiktok_metadata_generated() -> None:
    meta = generate_platform_metadata(
        video_topic="Skincare routine",
        channel_profile={"main_niche": "beauty"},
        platform=PLATFORM_TIKTOK,
        use_openai=False,
    )
    _pass("tiktok_caption", bool(meta.get("caption")))
    _pass("tiktok_hook", bool(meta.get("hook_text")))


def test_instagram_metadata_generated() -> None:
    meta = generate_platform_metadata(
        video_topic="Morning routine",
        channel_profile={"channel_name": "Glow"},
        platform=PLATFORM_INSTAGRAM,
        use_openai=False,
    )
    _pass("instagram_caption", bool(meta.get("caption")))
    _pass("instagram_alt_text", bool(meta.get("alt_text")))


def test_upload_package_folders_created() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video = tmp / "video.mp4"
        video.write_bytes(b"fake-video")
        bundle = {
            "platforms": {
                PLATFORM_YOUTUBE: {"title": "YT", "description": "desc", "hashtags": ["#shorts"], "pinned_comment": "pin"},
                PLATFORM_TIKTOK: {"caption": "tiktok", "hashtags": ["#fyp"], "pinned_comment": "pin"},
                PLATFORM_INSTAGRAM: {"caption": "ig", "hashtags": ["#reels"], "pinned_comment": "pin"},
            }
        }
        manifest = build_upload_packages(
            project_root=tmp,
            run_id="run_upload_test",
            topic="upload topic",
            platform_targets=[PLATFORM_YOUTUBE, PLATFORM_TIKTOK, PLATFORM_INSTAGRAM],
            metadata_bundle=bundle,
            video_path=str(video),
        )
        upload_root = Path(str(manifest.get("upload_root")))
        _pass("youtube_folder", (upload_root / "youtube").is_dir())
        _pass("tiktok_folder", (upload_root / "tiktok").is_dir())
        _pass("instagram_folder", (upload_root / "instagram").is_dir())


def test_captions_and_hashtags_saved() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video = tmp / "video.mp4"
        video.write_bytes(b"fake-video")
        manifest = build_upload_packages(
            project_root=tmp,
            run_id="run_caption_test",
            topic="caption topic",
            platform_targets=[PLATFORM_YOUTUBE, PLATFORM_TIKTOK, PLATFORM_INSTAGRAM],
            metadata_bundle={
                "platforms": {
                    PLATFORM_YOUTUBE: {"title": "YT", "description": "desc", "hashtags": ["#shorts"], "pinned_comment": "yt pin"},
                    PLATFORM_TIKTOK: {"caption": "tiktok caption", "hashtags": ["#fyp"], "pinned_comment": "tt pin"},
                    PLATFORM_INSTAGRAM: {"caption": "ig caption", "hashtags": ["#reels"], "pinned_comment": "ig pin"},
                }
            },
            video_path=str(video),
        )
        upload_root = Path(str(manifest.get("upload_root")))
        for folder in ("youtube", "tiktok", "instagram"):
            platform_dir = upload_root / folder
            _pass(f"{folder}_caption", (platform_dir / "caption.txt").is_file())
            _pass(f"{folder}_hashtags", (platform_dir / "hashtags.txt").is_file())
            _pass(f"{folder}_metadata", (platform_dir / "metadata.json").is_file())
            _pass(f"{folder}_readme", (platform_dir / "upload_readme.md").is_file())


def test_youtube_upload_defaults_private() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _write_profile(tmp, {"youtube_upload_enabled": True, "youtube_privacy": "private"})
        manager = UploadManager(tmp)
        blocked = manager.submit_youtube_upload(confirmed=False)
        _pass("confirmation_required", blocked.get("status") == "confirmation_required")
        _pass("privacy_private", blocked.get("privacy") == "private")


def test_youtube_upload_requires_confirmation() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _write_profile(tmp, {"youtube_upload_enabled": True, "youtube_require_confirmation": True})
        manager = UploadManager(tmp)
        blocked = manager.submit_youtube_upload(confirmed=False)
        _pass("requires_confirmation", blocked.get("requires_confirmation") is True)


def test_tiktok_instagram_no_auto_upload() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video = tmp / "video.mp4"
        video.write_bytes(b"fake-video")
        manifest = build_upload_packages(
            project_root=tmp,
            run_id="run_manual_only",
            topic="manual topic",
            platform_targets=[PLATFORM_TIKTOK, PLATFORM_INSTAGRAM],
            metadata_bundle={
                "platforms": {
                    PLATFORM_TIKTOK: {"caption": "tiktok", "hashtags": ["#fyp"], "pinned_comment": "pin"},
                    PLATFORM_INSTAGRAM: {"caption": "ig", "hashtags": ["#reels"], "pinned_comment": "pin"},
                }
            },
            video_path=str(video),
        )
        packages = list(manifest.get("packages") or [])
        tiktok = next(item for item in packages if item.get("platform") == PLATFORM_TIKTOK)
        instagram = next(item for item in packages if item.get("platform") == PLATFORM_INSTAGRAM)
        _pass("tiktok_manual", tiktok.get("status") == "manual_upload_ready" and tiktok.get("auto_upload") is False)
        _pass("instagram_manual", instagram.get("status") == "manual_upload_ready" and instagram.get("auto_upload") is False)


def test_automation_creates_upload_packages_after_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _write_profile(tmp, {"default_duration_seconds": 30, "use_ai_director_default": True})
        (tmp / "project_brain/platform").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain/platform/automation_center.json").write_text(
            json.dumps({"enabled": True, "paused": False, "feature_flags": {"auto_upload": False}}, ensure_ascii=False),
            encoding="utf-8",
        )
        video = tmp / "outputs/final/FINAL_BRANDED_VIDEO.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        publish = tmp / "outputs/publish/runway_phase_i"
        publish.mkdir(parents=True, exist_ok=True)

        queue = AutomationQueue(tmp)
        queue.create_job(
            {
                "topic": "automation upload topic",
                "duration": 20,
                "clip_count": 2,
                "platform_targets": [PLATFORM_YOUTUBE, PLATFORM_TIKTOK, PLATFORM_INSTAGRAM],
            }
        )

        product_service = MagicMock()
        product_service.create_video_generate.return_value = {"ok": True, "session_id": "cb_upload_auto", "content_brain_run_id": "cb_upload_auto"}
        runway_service = MagicMock()
        runway_service.snapshot.return_value = {
            "active": False,
            "report": {
                "ok": True,
                "content_brain_run_id": "cb_upload_auto",
                "final_branded_video_path": str(video),
                "publish_package_folder": str(publish),
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
        upload_manifest = dict((result.get("result") or {}).get("upload_package") or {})
        _pass("automation_ok", result.get("ok") is True)
        _pass("upload_manifest_present", bool(upload_manifest.get("upload_root") or upload_manifest.get("packages")))


def test_runway_automation_unchanged() -> None:
    smoke_source = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator_source = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    branding_source = (ROOT / "content_brain/branding/branding_runtime.py").read_text(encoding="utf-8")
    _pass("smoke_no_upload_agent", "platform_metadata_agent" not in smoke_source)
    _pass("navigator_untouched", "upload_package_builder" not in navigator_source)
    _pass("branding_untouched", "upload_manager" not in branding_source)


def main() -> None:
    test_youtube_metadata_generated()
    test_tiktok_metadata_generated()
    test_instagram_metadata_generated()
    test_upload_package_folders_created()
    test_captions_and_hashtags_saved()
    test_youtube_upload_defaults_private()
    test_youtube_upload_requires_confirmation()
    test_tiktok_instagram_no_auto_upload()
    test_automation_creates_upload_packages_after_publish()
    test_runway_automation_unchanged()
    print("All upload agent v1 validations passed.")


if __name__ == "__main__":
    main()
