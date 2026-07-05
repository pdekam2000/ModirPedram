"""Upload Center API service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from content_brain.comments.comment_agent import draft_pinned_comments_from_metadata
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.upload_manager import UploadManager
from content_brain.upload.upload_package_builder import resolve_run_dir
from content_brain.upload.youtube_auth import (
    build_oauth_authorization_url,
    exchange_authorization_code,
    get_youtube_auth_status,
)


class UploadService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.upload_manager = UploadManager(self.project_root)
        self.profile_store = ProductChannelProfileStore(self.project_root)

    def get_status(self, *, run_id: str = "") -> dict[str, Any]:
        status = self.upload_manager.get_upload_center_status(run_id=run_id)
        manifest = dict(status.get("upload_manifest") or {})
        packages = list(manifest.get("packages") or [])
        metadata_by_platform: dict[str, Any] = {}
        for package in packages:
            platform = str(package.get("platform") or "")
            meta_path = Path(str(package.get("metadata_path") or ""))
            if meta_path.is_file():
                try:
                    metadata_by_platform[platform] = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    metadata_by_platform[platform] = {}
        status["metadata_by_platform"] = metadata_by_platform
        status["publish_package_path"] = str(manifest.get("publish_package_path") or "")
        status["upload_root"] = str(manifest.get("upload_root") or "")
        try:
            from content_brain.automation.platform_daily_scheduler import get_platform_scheduler_status

            status["platform_scheduler"] = get_platform_scheduler_status(self.project_root)
        except Exception:
            status["platform_scheduler"] = {}
        return status

    def generate_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self.profile_store.load()
        bundle = self.upload_manager.generate_metadata(
            topic=str(payload.get("topic") or profile.get("channel_topic") or ""),
            platform_targets=list(payload.get("platform_targets") or payload.get("platforms") or profile.get("upload_platforms") or []),
            video_path=str(payload.get("video_path") or ""),
            publish_package_path=str(payload.get("publish_package_path") or ""),
            run_id=str(payload.get("run_id") or ""),
            use_openai=bool(payload.get("use_openai", True)),
        )
        pinned = draft_pinned_comments_from_metadata(bundle)
        return {"ok": True, "metadata": bundle, "pinned_comment_drafts": pinned}

    def prepare_packages(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self.profile_store.load()
        topic = str(payload.get("topic") or profile.get("channel_topic") or "")
        platform_targets = list(payload.get("platform_targets") or payload.get("platforms") or profile.get("upload_platforms") or [])
        metadata_bundle = payload.get("metadata")
        if metadata_bundle:
            manifest = self.upload_manager.build_upload_packages(
                topic=topic,
                platform_targets=platform_targets,
                metadata_bundle=dict(metadata_bundle),
                video_path=str(payload.get("video_path") or ""),
                publish_package_path=str(payload.get("publish_package_path") or ""),
                run_id=str(payload.get("run_id") or ""),
                use_openai=bool(payload.get("use_openai", True)),
            )
        else:
            manifest = self.upload_manager.prepare_full_upload_workflow(
                topic=topic,
                platform_targets=platform_targets,
                video_path=str(payload.get("video_path") or ""),
                publish_package_path=str(payload.get("publish_package_path") or ""),
                run_id=str(payload.get("run_id") or ""),
                use_openai=bool(payload.get("use_openai", True)),
            )
        pinned = draft_pinned_comments_from_metadata(dict(manifest.get("legacy_package", {}).get("platform_metadata") or {}))
        if not pinned.get("pinned_comments"):
            meta_path = resolve_run_dir(self.project_root, str(payload.get("run_id") or "")) / "upload" / "metadata" / "platform_metadata.json"
            if meta_path.is_file():
                pinned = draft_pinned_comments_from_metadata(json.loads(meta_path.read_text(encoding="utf-8")))
        return {"ok": True, "upload_manifest": manifest, "pinned_comment_drafts": pinned, "upload_center_ready": True}

    def submit_youtube(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.upload_manager.submit_youtube_upload(
            upload_package=dict(payload.get("upload_package") or {}),
            package_dir=str(payload.get("package_dir") or ""),
            run_id=str(payload.get("run_id") or ""),
            confirmed=bool(payload.get("confirmed")),
            automation_mode=bool(payload.get("automation_mode")),
        )
        if result.get("ok") and bool(payload.get("confirmed")):
            self.profile_store.save({"youtube_upload_confirmed": True})
        return result

    def submit_instagram(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.upload_manager.submit_instagram_upload(
            upload_package=dict(payload.get("upload_package") or {}),
            video_path=str(payload.get("video_path") or ""),
            run_id=str(payload.get("run_id") or ""),
            title=str(payload.get("title") or ""),
            caption=str(payload.get("caption") or ""),
            hashtags=list(payload.get("hashtags") or []),
            automation_mode=bool(payload.get("automation_mode")),
        )

    def submit_tiktok(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.upload_manager.submit_tiktok_upload(
            upload_package=dict(payload.get("upload_package") or {}),
            video_path=str(payload.get("video_path") or ""),
            run_id=str(payload.get("run_id") or ""),
            title=str(payload.get("title") or ""),
            caption=str(payload.get("caption") or ""),
            automation_mode=bool(payload.get("automation_mode")),
        )

    def youtube_auth_status(self) -> dict[str, Any]:
        profile = self.profile_store.load()
        return get_youtube_auth_status(self.project_root, profile)

    def youtube_auth_start(self) -> dict[str, Any]:
        profile = self.profile_store.load()
        return build_oauth_authorization_url(self.project_root, profile)

    def youtube_auth_exchange(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self.profile_store.load()
        result = exchange_authorization_code(self.project_root, profile, str(payload.get("code") or ""))
        if result.get("ok"):
            self.profile_store.save({"youtube_credentials_configured": True})
            channel = dict(result.get("channel") or {})
            if channel.get("channel_id"):
                self.profile_store.save(
                    {
                        "youtube_channel_id": channel.get("channel_id"),
                        "youtube_channel_name": channel.get("channel_name"),
                    }
                )
            self._finalize_auth_result_from_exchange(result, channel)
        return result

    def _finalize_auth_result_from_exchange(self, exchange_result: dict[str, Any], channel: dict[str, Any]) -> None:
        from content_brain.upload.youtube_first_authorization import write_youtube_auth_result
        from content_brain.upload.youtube_auth import load_token, refresh_access_token

        profile = self.profile_store.load()
        token = load_token(self.project_root) or {}
        refresh_verified = False
        if token.get("refresh_token"):
            refresh_verified = bool(refresh_access_token(self.project_root, profile).get("ok"))
        write_youtube_auth_result(
            self.project_root,
            {
                "authorized": bool(exchange_result.get("ok")),
                "channel_name": str(channel.get("channel_name") or ""),
                "channel_id": str(channel.get("channel_id") or ""),
                "token_refresh_verified": refresh_verified,
                "oauth_method": "auth_code_exchange",
                "refresh_token_present": bool(token.get("refresh_token")),
            },
        )

    def youtube_first_authorization(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from content_brain.upload.youtube_first_authorization import run_first_youtube_authorization

        payload = payload or {}
        result = run_first_youtube_authorization(
            self.project_root,
            open_browser=bool(payload.get("open_browser", True)),
            port=int(payload.get("port") or 8080),
            enable_upload=bool(payload.get("enable_upload", True)),
        )
        if result.get("authorized"):
            self.profile_store.save(
                {
                    "youtube_credentials_configured": True,
                    "youtube_upload_enabled": bool(payload.get("enable_upload", True)),
                    "youtube_channel_id": result.get("channel_id") or "",
                    "youtube_channel_name": result.get("channel_name") or "",
                }
            )
        return {"ok": bool(result.get("authorized")), **result}

    def youtube_auth_result(self) -> dict[str, Any]:
        from content_brain.upload.youtube_first_authorization import (
            get_youtube_oauth_readiness,
            load_youtube_auth_result,
        )

        profile = self.profile_store.load()
        stored = load_youtube_auth_result(self.project_root)
        readiness = get_youtube_oauth_readiness(self.project_root, profile)
        return {
            "found": stored is not None,
            "result": stored or {},
            **readiness,
        }

    def youtube_oauth_readiness(self) -> dict[str, Any]:
        from content_brain.upload.youtube_first_authorization import get_youtube_oauth_readiness

        profile = self.profile_store.load()
        return get_youtube_oauth_readiness(self.project_root, profile)

    def submit_publish_package_upload(self, payload: dict[str, Any]) -> dict[str, Any]:
        from content_brain.upload.youtube_upload_runtime import (
            resolve_publish_dir_for_run,
            run_youtube_upload_from_publish_package,
        )

        run_id = str(payload.get("run_id") or "")
        publish_dir = str(payload.get("publish_package_path") or payload.get("publish_dir") or "")
        if not publish_dir:
            resolved = resolve_publish_dir_for_run(
                self.project_root,
                run_id,
                run_dir=str(payload.get("run_dir") or ""),
            )
            publish_dir = str(resolved) if resolved else ""
        if not publish_dir:
            return {"ok": False, "upload_status": "upload_failed", "error": "publish_package_missing"}

        from content_brain.execution.product_visual_diversity_guard import load_visual_diversity_report

        run_dir = str(payload.get("run_dir") or "")
        diversity = load_visual_diversity_report(publish_dir) or (load_visual_diversity_report(run_dir) if run_dir else None)
        if diversity and not bool(diversity.get("youtube_upload_allowed", True)):
            return {
                "ok": False,
                "uploaded": False,
                "upload_status": "upload_failed",
                "error": "visual_repetition_blocked",
                "visual_diversity_status": str(diversity.get("status") or ""),
                "repetition_risk": str(diversity.get("repetition_risk") or ""),
            }

        result = run_youtube_upload_from_publish_package(
            project_root=self.project_root,
            publish_dir=publish_dir,
            run_id=run_id,
            visibility=str(payload.get("visibility") or payload.get("privacy") or ""),
            publish_now=bool(payload.get("publish_now", True)),
            publish_at=str(payload.get("publish_at") or payload.get("publish_at_datetime") or ""),
            confirmed=bool(payload.get("confirmed")),
            upload_thumbnail=bool(payload.get("upload_thumbnail", True)),
        )
        if result.get("uploaded") and bool(payload.get("confirmed")):
            self.profile_store.save({"youtube_upload_confirmed": True})
        if result.get("uploaded") or result.get("upload_status") == "upload_failed" or result.get("error"):
            self._record_youtube_upload_history(payload, result)
        return {"ok": bool(result.get("uploaded")), **result}

    def _record_youtube_upload_history(self, payload: dict[str, Any], result: dict[str, Any]) -> None:
        from content_brain.automation.upload_history_store import UploadHistoryStore

        title = str(result.get("title") or payload.get("title") or payload.get("topic") or "YouTube upload")
        UploadHistoryStore(self.project_root).record(
            platform="youtube_shorts",
            title=title,
            success=bool(result.get("uploaded")),
            run_id=str(payload.get("run_id") or result.get("run_id") or ""),
            youtube_url=str(result.get("youtube_url") or result.get("video_url") or ""),
            post_url=str(result.get("youtube_url") or result.get("video_url") or ""),
            error=str(result.get("error") or result.get("upload_status") or ""),
        )

    def get_publish_upload_result(self, *, run_id: str = "", publish_dir: str = "") -> dict[str, Any]:
        from content_brain.upload.youtube_upload_runtime import load_youtube_upload_result, resolve_publish_dir_for_run

        target = publish_dir
        if not target:
            resolved = resolve_publish_dir_for_run(self.project_root, run_id)
            target = str(resolved) if resolved else ""
        if not target:
            return {"found": False}
        payload = load_youtube_upload_result(target)
        if not payload:
            return {"found": False, "publish_dir": target}
        return {"found": True, "publish_dir": target, **payload}

    def get_platform_caption(self, *, run_id: str, platform: str) -> dict[str, Any]:
        folder_map = {
            "youtube_shorts": "youtube",
            "youtube": "youtube",
            "tiktok": "tiktok",
            "instagram_reels": "instagram",
            "instagram": "instagram",
        }
        folder = folder_map.get(str(platform or "").strip().lower(), "")
        if not folder:
            return {"ok": False, "message": "unsupported_platform"}
        caption_path = resolve_run_dir(self.project_root, run_id) / "upload" / folder / "caption.txt"
        if not caption_path.is_file():
            return {"ok": False, "message": "caption_not_found", "path": str(caption_path)}
        return {"ok": True, "platform": platform, "caption": caption_path.read_text(encoding="utf-8"), "path": str(caption_path)}


def get_upload_service(project_root: str | Path | None = None) -> UploadService:
    if project_root is None:
        from ui.api.dependencies import get_project_root

        project_root = get_project_root()
    return UploadService(project_root)
