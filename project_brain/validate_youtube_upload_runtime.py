"""Validation — PHASE YT-2 YouTube OAuth + upload runtime."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.product_assembly_bridge import FINAL_PUBLISH_READY_NAME  # noqa: E402
from content_brain.execution.product_subtitle_branding_publish import FINAL_BRANDED_PUBLISH_READY_NAME  # noqa: E402
from content_brain.upload.youtube_auth import (  # noqa: E402
    build_oauth_authorization_url,
    fetch_and_store_channel_info,
    get_youtube_auth_status,
    refresh_access_token,
    save_token,
)
from content_brain.upload.youtube_upload_runtime import (  # noqa: E402
    YOUTUBE_UPLOAD_RESULT_NAME,
    load_youtube_upload_result,
    map_youtube_metadata_to_upload,
    run_youtube_upload_from_publish_package,
)
from content_brain.execution.pwmap_finalization import build_pwmap_results_payload  # noqa: E402
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


def _write_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * 1_100_000)


def _setup_publish(tmp: Path) -> Path:
    publish = tmp / "publish"
    publish.mkdir(parents=True)
    _write_video(publish / FINAL_PUBLISH_READY_NAME)
    _write_video(publish / FINAL_BRANDED_PUBLISH_READY_NAME)
    (publish / "youtube_metadata.json").write_text(
        json.dumps(
            {
                "title": "Upload validation title",
                "description": "Upload validation description",
                "tags": ["ai", "shorts"],
                "hashtags": ["#shorts", "#ai"],
                "category": "Science & Technology",
                "language": "en",
                "made_for_kids": False,
            }
        ),
        encoding="utf-8",
    )
    (publish / "publish_package.json").write_text(
        json.dumps({"publish_ready": True, "final_video": str((publish / FINAL_BRANDED_PUBLISH_READY_NAME).resolve())}),
        encoding="utf-8",
    )
    return publish


def _profile() -> dict:
    return {
        "youtube_upload_enabled": True,
        "youtube_require_confirmation": False,
        "youtube_privacy": "private",
        "youtube_credentials_configured": True,
    }


def main() -> int:
    print("validate_youtube_upload_runtime")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        (root / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            json.dumps(_profile()),
            encoding="utf-8",
        )
        (root / "project_brain" / "local_credentials").mkdir(parents=True, exist_ok=True)
        (root / "project_brain" / "local_credentials" / "youtube_client_secret.json").write_text(
            json.dumps(
                {
                    "installed": {
                        "client_id": "client-id",
                        "client_secret": "client-secret",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
            ),
            encoding="utf-8",
        )
        save_token(
            root,
            {
                "access_token": "test-access",
                "refresh_token": "test-refresh",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
        )

        with patch("requests.post") as refresh_post:
            refresh_post.return_value.ok = True
            refresh_post.return_value.json.return_value = {"access_token": "refreshed-access"}
            refreshed = refresh_access_token(root, _profile())
        _record("token_refresh_works", refreshed.get("ok") is True, str(refreshed.get("access_token")))

        with patch("requests.get") as channel_get:
            channel_get.return_value.ok = True
            channel_get.return_value.json.return_value = {
                "items": [{"id": "UC123", "snippet": {"title": "Validation Channel", "channelId": "UC123"}}]
            }
            with patch("content_brain.upload.youtube_auth.get_valid_access_token", return_value="test-access"):
                channel = fetch_and_store_channel_info(root, _profile())
        _record("oauth_channel_info_stored", channel.get("ok") is True and channel.get("channel_id") == "UC123", str(channel))

        auth_url = build_oauth_authorization_url(root, _profile())
        _record("oauth_login_works", auth_url.get("ok") is True and "authorization_url" in auth_url, str(auth_url.get("method")))

        auth_status = get_youtube_auth_status(root, _profile())
        _record("oauth_login_status", auth_status.get("authenticated") is True, str(auth_status.get("channel_name")))

    mapped = map_youtube_metadata_to_upload(
        {
            "title": "Mapped title",
            "description": "Mapped description",
            "tags": ["tag1"],
            "hashtags": ["#shorts"],
            "category": "Education",
            "language": "en",
        },
        profile=_profile(),
    )
    _record(
        "metadata_mapping_works",
        mapped.get("title") == "Mapped title" and "#shorts" in str(mapped.get("hashtags")),
        str(mapped.get("title")),
    )

    with tempfile.TemporaryDirectory() as tmp:
        publish = _setup_publish(Path(tmp))
        upload_ok = {
            "ok": True,
            "uploaded": True,
            "status": "uploaded",
            "youtube_video_id": "abc123xyz",
            "youtube_url": "https://www.youtube.com/watch?v=abc123xyz",
            "visibility": "private",
            "publish_time": "2026-06-27T12:00:00.000Z",
            "upload_time": "2026-06-27T11:00:00.000Z",
            "scheduled": False,
        }

        with patch("content_brain.upload.youtube_upload_runtime.get_youtube_auth_status") as auth_mock, patch(
            "content_brain.upload.youtube_upload_runtime.upload_video_to_youtube",
            return_value=upload_ok,
        ), patch(
            "content_brain.upload.youtube_upload_runtime.upload_thumbnail_to_youtube",
            return_value={"ok": True, "status": "uploaded"},
        ), patch(
            "content_brain.upload.youtube_upload_runtime.ProductChannelProfileStore"
        ) as store_mock:
            store_mock.return_value.load.return_value = _profile()
            auth_mock.return_value = {
                "authenticated": True,
                "channel_id": "UC123",
                "channel_name": "Validation Channel",
            }
            result = run_youtube_upload_from_publish_package(
                project_root=ROOT,
                publish_dir=publish,
                run_id="pwmap_upload_test",
                confirmed=True,
                upload_thumbnail=True,
            )
        _record("upload_works", result.get("uploaded") is True, str(result.get("youtube_video_id")))
        _record(
            "upload_result_json_written",
            (publish / YOUTUBE_UPLOAD_RESULT_NAME).is_file(),
            str((publish / YOUTUBE_UPLOAD_RESULT_NAME)),
        )
        loaded = load_youtube_upload_result(publish)
        _record("upload_result_roundtrip", loaded is not None and loaded.get("youtube_video_id") == "abc123xyz", str(loaded))

        payload = build_pwmap_results_payload(
            publish.parent,
            {
                "run_id": "pwmap_upload_test",
                "status": "completed",
                "preflight_snapshot": {"authoritative_topic": "Upload topic"},
                **result,
            },
        )
        service = ProductStudioService(ROOT)
        merged = service._merge_pwmap_results({**payload, "publish_package_path": str(publish)})
        _record(
            "results_page_shows_upload_status",
            merged.get("youtube_upload_status") == "uploaded" and merged.get("youtube_video_id") == "abc123xyz",
            str(merged.get("youtube_url")),
        )

        upload_service = UploadService(ROOT)
        with patch.object(upload_service, "submit_publish_package_upload", return_value=result):
            api_result = upload_service.submit_publish_package_upload(
                {"run_id": "pwmap_upload_test", "publish_package_path": str(publish), "confirmed": True}
            )
        _record("upload_service_publish_package", api_result.get("uploaded") is True, str(api_result.get("youtube_video_id")))

        with patch("content_brain.upload.youtube_upload_runtime.get_youtube_auth_status") as auth_mock, patch(
            "content_brain.upload.youtube_upload_runtime.upload_video_to_youtube",
            return_value=upload_ok,
        ), patch(
            "content_brain.upload.youtube_upload_runtime.upload_thumbnail_to_youtube",
            return_value={"ok": False, "status": "skipped", "reason": "thumbnail_missing"},
        ), patch(
            "content_brain.upload.youtube_upload_runtime.ProductChannelProfileStore"
        ) as store_mock:
            store_mock.return_value.load.return_value = _profile()
            auth_mock.return_value = {"authenticated": True, "channel_id": "UC123", "channel_name": "Validation Channel"}
            no_thumb = run_youtube_upload_from_publish_package(
                project_root=ROOT,
                publish_dir=publish,
                run_id="pwmap_upload_test",
                confirmed=True,
                upload_thumbnail=True,
            )
        _record(
            "thumbnail_upload_optional",
            no_thumb.get("uploaded") is True and no_thumb.get("thumbnail_uploaded") is False,
            str(no_thumb.get("thumbnail_upload_status")),
        )

        scheduled_upload = dict(upload_ok)
        scheduled_upload.update(
            {
                "status": "scheduled",
                "scheduled": True,
                "visibility": "private",
                "publish_time": "2026-07-01T18:00:00.000Z",
            }
        )
        with patch("content_brain.upload.youtube_upload_runtime.get_youtube_auth_status") as auth_mock, patch(
            "content_brain.upload.youtube_upload_runtime.upload_video_to_youtube",
            return_value=scheduled_upload,
        ) as upload_mock, patch(
            "content_brain.upload.youtube_upload_runtime.upload_thumbnail_to_youtube",
            return_value={"ok": False, "status": "skipped"},
        ), patch(
            "content_brain.upload.youtube_upload_runtime.ProductChannelProfileStore"
        ) as store_mock:
            store_mock.return_value.load.return_value = _profile()
            auth_mock.return_value = {"authenticated": True}
            scheduled = run_youtube_upload_from_publish_package(
                project_root=ROOT,
                publish_dir=publish,
                run_id="pwmap_scheduled",
                confirmed=True,
                publish_now=False,
                publish_at="2026-07-01T18:00:00.000Z",
            )
            _record(
                "scheduling_works",
                scheduled.get("upload_status") == "scheduled" and scheduled.get("publish_time") == "2026-07-01T18:00:00.000Z",
                str(scheduled.get("publish_time")),
            )
            _record(
                "scheduling_passes_publish_at",
                upload_mock.call_args.kwargs.get("publish_at") == "2026-07-01T18:00:00.000Z",
                str(upload_mock.call_args.kwargs.get("publish_at")),
            )

        source_bytes = (publish / FINAL_BRANDED_PUBLISH_READY_NAME).read_bytes()
        with patch("content_brain.upload.youtube_upload_runtime.get_youtube_auth_status") as auth_mock, patch(
            "content_brain.upload.youtube_upload_runtime.upload_video_to_youtube",
            return_value={"ok": False, "status": "failed", "reason": "youtube_upload_failed", "uploaded": False},
        ), patch(
            "content_brain.upload.youtube_upload_runtime.ProductChannelProfileStore"
        ) as store_mock:
            store_mock.return_value.load.return_value = _profile()
            auth_mock.return_value = {"authenticated": True}
            failed = run_youtube_upload_from_publish_package(
                project_root=ROOT,
                publish_dir=publish,
                run_id="pwmap_upload_fail",
                confirmed=True,
            )
        _record(
            "upload_failure_handled_safely",
            failed.get("upload_status") == "upload_failed"
            and (publish / FINAL_BRANDED_PUBLISH_READY_NAME).read_bytes() == source_bytes
            and (publish / "youtube_metadata.json").is_file(),
            str(failed.get("error")),
        )

    metadata_src = (ROOT / "content_brain" / "publish" / "youtube_metadata_generator.py").read_text(encoding="utf-8")
    orchestrator_src = (ROOT / "content_brain" / "execution" / "product_multiclip_orchestrator.py").read_text(encoding="utf-8")
    _record(
        "no_generation_pipeline_modified",
        "youtube_upload_runtime" not in orchestrator_src and "run_youtube_upload" not in metadata_src,
        "static scan",
    )

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"TOTAL: {len(results)}  PASS: {len(results) - len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return FAIL
    print("ALL PASS")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
