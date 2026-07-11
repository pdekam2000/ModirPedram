"""Upload manager — metadata, packages, and gated YouTube upload."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.automation_center_store import AutomationCenterStore
from content_brain.platform.final_delivery_registry import resolve_approved_delivery
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.platform_metadata_agent import generate_all_platform_metadata
from content_brain.upload.upload_models import (
    PLATFORM_INSTAGRAM,
    PLATFORM_TIKTOK,
    PLATFORM_YOUTUBE,
    PRIVACY_PRIVATE,
    UploadPackage,
    UploadTarget,
)
from content_brain.upload.upload_package_builder import build_upload_packages, resolve_run_dir
from content_brain.upload.youtube_auth import get_youtube_auth_status, resolve_oauth_client_path
from content_brain.upload.instagram_uploader import upload_reel_to_instagram
from content_brain.upload.tiktok_uploader import upload_video_to_tiktok
from content_brain.upload.youtube_uploader import upload_video_to_youtube

UPLOAD_MANAGER_VERSION = "upload_manager_v2"
UPLOAD_ROOT = Path("outputs") / "upload_packages"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(text or "upload").strip().lower())
    return cleaned[:48] or "upload"


def _load_context_files(
    project_root: Path,
    *,
    publish_package_path: str,
    run_id: str,
) -> tuple[str, list[str]]:
    narration = ""
    prompts: list[str] = []
    candidates: list[Path] = []
    if publish_package_path:
        publish = Path(publish_package_path)
        candidates.extend(
            [
                publish / "narration_script.txt",
                publish / "NARRATION_SCRIPT.txt",
                publish / "script.txt",
            ]
        )
    run_dir = resolve_run_dir(project_root, run_id)
    candidates.extend(
        [
            run_dir / "publish" / "narration_script.txt",
            run_dir / "audio" / "narration_script.txt",
            run_dir / "metadata" / "narration_script.txt",
        ]
    )
    for candidate in candidates:
        resolved = candidate if candidate.is_absolute() else (project_root / candidate)
        if resolved.is_file():
            narration = resolved.read_text(encoding="utf-8").strip()
            break

    prompt_dirs = []
    if publish_package_path:
        prompt_dirs.append(Path(publish_package_path))
    prompt_dirs.append(run_dir / "prompts")
    for prompt_dir in prompt_dirs:
        resolved = prompt_dir if prompt_dir.is_absolute() else (project_root / prompt_dir)
        if not resolved.is_dir():
            continue
        for path in sorted(resolved.glob("*.txt"))[:12]:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                prompts.append(text[:500])
    return narration, prompts


class UploadManager:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()

    def _profile(self) -> dict[str, Any]:
        return ProductChannelProfileStore(self.project_root).load()

    def get_upload_center_status(self, *, run_id: str = "") -> dict[str, Any]:
        profile = self._profile()
        auth = get_youtube_auth_status(self.project_root, profile)
        if resolve_oauth_client_path(self.project_root, profile):
            profile_credentials = True
        else:
            profile_credentials = bool(profile.get("youtube_credentials_configured"))
        auth["credentials_configured"] = profile_credentials or auth.get("credentials_configured")

        delivery = resolve_approved_delivery(self.project_root, run_id=run_id)
        latest_manifest = self._latest_run_upload_manifest(run_id)
        if delivery:
            latest_manifest.setdefault("approved_video_path", delivery.get("canonical_final_video_path") or "")
            latest_manifest.setdefault("publish_package_path", delivery.get("latest_publish_package") or "")
        legacy_packages = self._list_legacy_packages(limit=5)
        return {
            "version": UPLOAD_MANAGER_VERSION,
            "run_id": str(latest_manifest.get("run_id") or run_id or ""),
            "topic": str(latest_manifest.get("topic") or profile.get("channel_topic") or ""),
            "platform_targets": list(profile.get("upload_platforms") or [PLATFORM_YOUTUBE]),
            "upload_manifest": latest_manifest,
            "latest_legacy_package": legacy_packages[0] if legacy_packages else {},
            "youtube_auth": auth,
            "instagram_auth": {
                "enabled": bool(profile.get("instagram_upload_enabled")),
                "configured": bool(profile.get("instagram_access_token") and profile.get("instagram_account_id")),
            },
            "tiktok_auth": {
                "enabled": bool(profile.get("tiktok_upload_enabled")),
                "configured": bool(profile.get("tiktok_access_token")),
            },
            "auto_upload_enabled": bool(profile.get("youtube_upload_enabled")),
        }

    def generate_metadata(
        self,
        *,
        topic: str,
        platform_targets: list[str] | None = None,
        video_path: str = "",
        publish_package_path: str = "",
        run_id: str = "",
        use_openai: bool = True,
    ) -> dict[str, Any]:
        profile = self._profile()
        targets = list(platform_targets or profile.get("upload_platforms") or [PLATFORM_YOUTUBE])
        narration, prompts = _load_context_files(
            self.project_root,
            publish_package_path=publish_package_path,
            run_id=run_id,
        )
        bundle = generate_all_platform_metadata(
            video_topic=topic,
            channel_profile=profile,
            platform_targets=targets,
            final_video_path=video_path,
            narration_script=narration,
            prompts=prompts,
            content_language=str(profile.get("language") or "English"),
            use_openai=use_openai,
        )
        run_dir = resolve_run_dir(self.project_root, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir = run_dir / "upload" / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = metadata_dir / "platform_metadata.json"
        metadata_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        bundle["metadata_path"] = str(metadata_path)
        return bundle

    def build_upload_packages(
        self,
        *,
        topic: str,
        platform_targets: list[str],
        metadata_bundle: dict[str, Any] | None = None,
        video_path: str = "",
        publish_package_path: str = "",
        run_id: str = "",
        use_openai: bool = True,
        automation_mode: bool = False,
    ) -> dict[str, Any]:
        bundle = metadata_bundle or self.generate_metadata(
            topic=topic,
            platform_targets=platform_targets,
            video_path=video_path,
            publish_package_path=publish_package_path,
            run_id=run_id,
            use_openai=use_openai,
        )
        manifest = build_upload_packages(
            project_root=self.project_root,
            run_id=run_id,
            topic=topic,
            platform_targets=platform_targets,
            metadata_bundle=bundle,
            video_path=video_path,
            publish_package_path=publish_package_path,
        )
        legacy = self.prepare_upload_package(
            topic=topic,
            platform_targets=platform_targets,
            video_path=video_path,
            publish_package_path=publish_package_path,
            run_id=run_id,
            metadata_bundle=bundle,
            skip_metadata=True,
            automation_mode=automation_mode,
        )
        manifest["legacy_package"] = legacy
        return manifest

    def prepare_upload_package(
        self,
        *,
        topic: str,
        platform_targets: list[str],
        video_path: str,
        publish_package_path: str = "",
        run_id: str = "",
        title: str = "",
        metadata_bundle: dict[str, Any] | None = None,
        skip_metadata: bool = False,
        use_openai: bool = True,
        automation_mode: bool = False,
    ) -> dict[str, Any]:
        profile = self._profile()
        center = AutomationCenterStore(self.project_root).load()
        flags = dict(center.get("feature_flags") or {})
        auto_upload_enabled = bool(profile.get("youtube_upload_enabled")) and (
            bool(flags.get("auto_upload", True)) or bool(automation_mode)
        )

        bundle = metadata_bundle
        if bundle is None and not skip_metadata:
            bundle = self.generate_metadata(
                topic=topic,
                platform_targets=platform_targets,
                video_path=video_path,
                publish_package_path=publish_package_path,
                run_id=run_id,
                use_openai=use_openai,
            )

        package_dir = self.project_root / UPLOAD_ROOT / _slug(run_id or topic)
        package_dir.mkdir(parents=True, exist_ok=True)

        resolved_video = video_path
        if not resolved_video and publish_package_path:
            candidate = Path(publish_package_path) / "FINAL_BRANDED_VIDEO_CANONICAL.mp4"
            if candidate.is_file():
                resolved_video = str(candidate)
            else:
                candidate = Path(publish_package_path) / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4"
                if candidate.is_file():
                    resolved_video = str(candidate)
                else:
                    candidate = Path(publish_package_path) / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
                    if candidate.is_file():
                        resolved_video = str(candidate)

        platforms_meta = dict((bundle or {}).get("platforms") or {})
        targets: list[UploadTarget] = []
        for platform in platform_targets or [PLATFORM_YOUTUBE]:
            normalized = str(platform or "").strip().lower()
            meta = dict(platforms_meta.get(normalized) or {})
            if normalized == PLATFORM_YOUTUBE:
                target = UploadTarget(
                    platform=PLATFORM_YOUTUBE,
                    enabled=bool(profile.get("youtube_upload_enabled")),
                    status="prepared",
                    video_path=resolved_video,
                    title=str(meta.get("title") or title or topic),
                    description=str(meta.get("description") or profile.get("youtube_default_description") or topic),
                    hashtags=[str(item) for item in (meta.get("hashtags") or [])],
                    privacy=str(meta.get("privacy") or profile.get("youtube_privacy") or PRIVACY_PUBLIC),
                )
            elif normalized == PLATFORM_TIKTOK:
                tiktok_ready = bool(profile.get("tiktok_upload_enabled")) and bool(profile.get("tiktok_access_token"))
                target = UploadTarget(
                    platform=PLATFORM_TIKTOK,
                    enabled=tiktok_ready,
                    status="prepared" if tiktok_ready else "manual_upload_ready",
                    video_path=resolved_video,
                    title=str(meta.get("caption") or title or topic),
                    description=str(meta.get("caption") or topic),
                    hashtags=[str(item) for item in (meta.get("hashtags") or [])],
                    warnings=[] if tiktok_ready else ["tiktok_upload_not_configured"],
                )
            elif normalized == PLATFORM_INSTAGRAM:
                credentials_ready = bool(
                    profile.get("instagram_access_token") and profile.get("instagram_account_id")
                )
                instagram_ready = credentials_ready and (
                    bool(profile.get("instagram_upload_enabled")) or bool(automation_mode)
                )
                target = UploadTarget(
                    platform=PLATFORM_INSTAGRAM,
                    enabled=instagram_ready,
                    status="prepared" if instagram_ready else "manual_upload_ready",
                    video_path=resolved_video,
                    title=str(meta.get("caption") or title or topic),
                    description=str(meta.get("caption") or topic),
                    hashtags=[str(item) for item in (meta.get("hashtags") or [])],
                    warnings=[] if instagram_ready else ["instagram_upload_not_configured"],
                )
            else:
                continue
            metadata_path = package_dir / f"{target.platform}_metadata.json"
            metadata_path.write_text(json.dumps({**target.to_dict(), **meta}, indent=2, ensure_ascii=False), encoding="utf-8")
            target.metadata_path = str(metadata_path)
            targets.append(target)

        package = UploadPackage(
            run_id=run_id,
            topic=topic,
            package_dir=str(package_dir),
            video_path=resolved_video,
            publish_package_path=publish_package_path,
            auto_upload_enabled=auto_upload_enabled,
            targets=targets,
            created_at=_now(),
        )
        manifest_path = package_dir / "upload_package.json"
        manifest_path.write_text(json.dumps(package.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        payload = package.to_dict()
        payload["manifest_path"] = str(manifest_path)
        if bundle:
            payload["platform_metadata"] = bundle
        return payload

    def prepare_full_upload_workflow(
        self,
        *,
        topic: str,
        platform_targets: list[str],
        video_path: str,
        publish_package_path: str = "",
        run_id: str = "",
        use_openai: bool = True,
        automation_mode: bool = False,
    ) -> dict[str, Any]:
        manifest = self.build_upload_packages(
            topic=topic,
            platform_targets=platform_targets,
            video_path=video_path,
            publish_package_path=publish_package_path,
            run_id=run_id,
            use_openai=use_openai,
            automation_mode=automation_mode,
        )
        manifest["upload_center_ready"] = True
        manifest["auto_upload"] = bool(automation_mode) or bool(
            (manifest.get("legacy_package") or {}).get("auto_upload_enabled")
        )
        return manifest

    def submit_youtube_upload(
        self,
        *,
        upload_package: dict[str, Any] | None = None,
        package_dir: str = "",
        run_id: str = "",
        confirmed: bool = False,
        automation_mode: bool = False,
    ) -> dict[str, Any]:
        profile = self._profile()
        enabled = bool(profile.get("youtube_upload_enabled"))
        privacy = str(profile.get("youtube_privacy") or PRIVACY_PRIVATE)
        if privacy not in {PRIVACY_PRIVATE, "unlisted", "public"}:
            privacy = PRIVACY_PRIVATE

        if not enabled:
            return {
                "ok": False,
                "status": "blocked",
                "reason": "youtube_upload_disabled",
                "privacy": privacy,
                "auto_upload": False,
            }

        require_confirmation = bool(profile.get("youtube_require_confirmation", True))
        if automation_mode:
            require_confirmation = False
        if require_confirmation and not confirmed and not bool(profile.get("youtube_upload_confirmed")):
            return {
                "ok": False,
                "status": "confirmation_required",
                "reason": "first_upload_requires_confirmation",
                "privacy": privacy,
                "requires_confirmation": True,
                "auto_upload": False,
            }

        package = dict(upload_package or {})
        upload_topic = str(package.get("topic") or "")
        if upload_topic:
            from content_brain.automation.platform_upload_guard import validate_platform_match

            try:
                validate_platform_match(
                    {"topic": upload_topic, "platform_targets": ["youtube_shorts"]},
                    "youtube_shorts",
                )
            except Exception as exc:
                return {
                    "ok": False,
                    "status": "blocked",
                    "reason": str(exc),
                    "privacy": privacy,
                    "auto_upload": bool(automation_mode),
                }

        if not package and package_dir:
            manifest = Path(package_dir) / "upload_package.json"
            if manifest.is_file():
                package = json.loads(manifest.read_text(encoding="utf-8"))

        youtube_meta: dict[str, Any] = {}
        video_path = ""
        if run_id:
            run_manifest_path = resolve_run_dir(self.project_root, run_id) / "upload" / "youtube" / "metadata.json"
            if run_manifest_path.is_file():
                youtube_meta = json.loads(run_manifest_path.read_text(encoding="utf-8"))
                candidate = run_manifest_path.parent / "video.mp4"
                if candidate.is_file():
                    video_path = str(candidate)

        youtube_target = next((item for item in (package.get("targets") or []) if item.get("platform") == PLATFORM_YOUTUBE), {})
        if not video_path:
            video_path = str(youtube_target.get("video_path") or package.get("video_path") or "")
        if not youtube_meta and youtube_target:
            youtube_meta = dict(youtube_target)

        if not video_path or not Path(video_path).is_file():
            return {"ok": False, "status": "failed", "reason": "video_missing", "privacy": privacy, "auto_upload": False}

        auth = get_youtube_auth_status(self.project_root, profile)
        credentials_ready = bool(auth.get("credentials_configured")) or resolve_oauth_client_path(self.project_root, profile) is not None
        if not credentials_ready:
            return {
                "ok": False,
                "status": "blocked",
                "reason": "youtube_credentials_missing",
                "privacy": privacy,
                "connect_required": True,
                "prepared_only": True,
                "auto_upload": False,
            }

        if not auth.get("authenticated"):
            return {
                "ok": False,
                "status": "blocked",
                "reason": "youtube_connect_required",
                "privacy": privacy,
                "connect_required": True,
                "auto_upload": False,
            }

        upload_result = upload_video_to_youtube(
            project_root=self.project_root,
            profile=profile,
            video_path=video_path,
            title=str(youtube_meta.get("title") or youtube_target.get("title") or package.get("topic") or "Short"),
            description=str(youtube_meta.get("description") or youtube_target.get("description") or ""),
            tags=list(youtube_meta.get("tags") or []),
            privacy=privacy,
        )

        out_dir = Path(str(package.get("package_dir") or package_dir or self.project_root / UPLOAD_ROOT))
        out_dir.mkdir(parents=True, exist_ok=True)
        submit_path = out_dir / "youtube_submit_manifest.json"
        submit_manifest = {
            "version": UPLOAD_MANAGER_VERSION,
            "platform": PLATFORM_YOUTUBE,
            "confirmed": bool(confirmed),
            "privacy": privacy,
            "video_path": video_path,
            "upload_result": upload_result,
            "submitted_at": _now(),
        }
        submit_path.write_text(json.dumps(submit_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        if upload_result.get("ok"):
            return {
                "ok": True,
                "status": "uploaded",
                "privacy": privacy,
                "manifest_path": str(submit_path),
                "video_id": upload_result.get("video_id", ""),
                "video_url": upload_result.get("video_url", ""),
                "auto_upload": False,
            }

        return {
            "ok": False,
            "status": str(upload_result.get("status") or "failed"),
            "reason": str(upload_result.get("reason") or "youtube_upload_failed"),
            "privacy": privacy,
            "manifest_path": str(submit_path),
            "details": upload_result,
            "auto_upload": False,
        }

    def submit_instagram_upload(
        self,
        *,
        upload_package: dict[str, Any] | None = None,
        video_path: str = "",
        run_id: str = "",
        title: str = "",
        caption: str = "",
        hashtags: list[str] | None = None,
        automation_mode: bool = False,
    ) -> dict[str, Any]:
        profile = self._profile()
        credentials_ready = bool(profile.get("instagram_access_token") and profile.get("instagram_account_id"))
        if not credentials_ready:
            return {
                "ok": False,
                "uploaded": False,
                "status": "blocked",
                "reason": "instagram_credentials_missing",
                "platform": PLATFORM_INSTAGRAM,
            }
        if not bool(profile.get("instagram_upload_enabled")) and not automation_mode:
            return {
                "ok": False,
                "uploaded": False,
                "status": "blocked",
                "reason": "instagram_upload_disabled",
                "platform": PLATFORM_INSTAGRAM,
            }

        upload_topic = str(title or caption or (upload_package or {}).get("topic") or "")
        if upload_topic:
            from content_brain.automation.platform_upload_guard import validate_platform_match

            try:
                validate_platform_match(
                    {"topic": upload_topic, "platform_targets": ["instagram_reels"]},
                    "instagram_reels",
                )
            except Exception as exc:
                return {
                    "ok": False,
                    "uploaded": False,
                    "status": "blocked",
                    "reason": str(exc),
                    "platform": PLATFORM_INSTAGRAM,
                }

        package = dict(upload_package or {})
        instagram_target = next(
            (item for item in (package.get("targets") or []) if item.get("platform") == PLATFORM_INSTAGRAM),
            {},
        )
        resolved_video = str(video_path or instagram_target.get("video_path") or package.get("video_path") or "")
        if not resolved_video or not Path(resolved_video).is_file():
            return {"ok": False, "uploaded": False, "status": "failed", "reason": "video_missing", "platform": PLATFORM_INSTAGRAM}

        upload_result = upload_reel_to_instagram(
            profile=profile,
            video_path=resolved_video,
            title=str(title or instagram_target.get("title") or package.get("topic") or "Reel"),
            caption=str(caption or instagram_target.get("description") or ""),
            hashtags=list(hashtags or instagram_target.get("hashtags") or []),
            run_id=run_id,
            project_root=self.project_root,
        )

        out_dir = Path(str(package.get("package_dir") or self.project_root / UPLOAD_ROOT))
        out_dir.mkdir(parents=True, exist_ok=True)
        submit_path = out_dir / "instagram_submit_manifest.json"
        submit_path.write_text(
            json.dumps(
                {
                    "version": UPLOAD_MANAGER_VERSION,
                    "platform": PLATFORM_INSTAGRAM,
                    "automation_mode": bool(automation_mode),
                    "video_path": resolved_video,
                    "run_id": run_id,
                    "upload_result": upload_result,
                    "submitted_at": _now(),
                },
                indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if upload_result.get("ok"):
            return {
                "ok": True,
                "uploaded": True,
                "status": "uploaded",
                "platform": PLATFORM_INSTAGRAM,
                "manifest_path": str(submit_path),
                "post_url": upload_result.get("post_url", ""),
                "media_id": upload_result.get("media_id", ""),
            }

        return {
            "ok": False,
            "uploaded": False,
            "status": str(upload_result.get("status") or "failed"),
            "reason": str(upload_result.get("reason") or "instagram_upload_failed"),
            "platform": PLATFORM_INSTAGRAM,
            "manifest_path": str(submit_path),
            "details": upload_result,
        }

    def submit_tiktok_upload(
        self,
        *,
        upload_package: dict[str, Any] | None = None,
        video_path: str = "",
        run_id: str = "",
        title: str = "",
        caption: str = "",
        automation_mode: bool = False,
    ) -> dict[str, Any]:
        profile = self._profile()
        if not bool(profile.get("tiktok_upload_enabled")):
            return {
                "ok": False,
                "uploaded": False,
                "status": "blocked",
                "reason": "tiktok_upload_disabled",
                "platform": PLATFORM_TIKTOK,
            }

        package = dict(upload_package or {})
        tiktok_target = next(
            (item for item in (package.get("targets") or []) if item.get("platform") == PLATFORM_TIKTOK),
            {},
        )
        resolved_video = str(video_path or tiktok_target.get("video_path") or package.get("video_path") or "")
        if not resolved_video or not Path(resolved_video).is_file():
            return {"ok": False, "uploaded": False, "status": "failed", "reason": "video_missing", "platform": PLATFORM_TIKTOK}

        privacy = str(profile.get("tiktok_privacy") or "PUBLIC_TO_EVERYONE")
        upload_result = upload_video_to_tiktok(
            profile=profile,
            video_path=resolved_video,
            title=str(title or tiktok_target.get("title") or package.get("topic") or "Short"),
            caption=str(caption or tiktok_target.get("description") or ""),
            privacy_level=privacy,
            project_root=self.project_root,
        )

        out_dir = Path(str(package.get("package_dir") or self.project_root / UPLOAD_ROOT))
        out_dir.mkdir(parents=True, exist_ok=True)
        submit_path = out_dir / "tiktok_submit_manifest.json"
        submit_path.write_text(
            json.dumps(
                {
                    "version": UPLOAD_MANAGER_VERSION,
                    "platform": PLATFORM_TIKTOK,
                    "automation_mode": bool(automation_mode),
                    "video_path": resolved_video,
                    "run_id": run_id,
                    "upload_result": upload_result,
                    "submitted_at": _now(),
                },
                indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if upload_result.get("ok"):
            return {
                "ok": True,
                "uploaded": True,
                "status": "uploaded",
                "platform": PLATFORM_TIKTOK,
                "manifest_path": str(submit_path),
                "post_url": upload_result.get("post_url", ""),
                "publish_id": upload_result.get("publish_id", ""),
            }

        return {
            "ok": False,
            "uploaded": False,
            "status": str(upload_result.get("status") or "failed"),
            "reason": str(upload_result.get("reason") or "tiktok_upload_failed"),
            "platform": PLATFORM_TIKTOK,
            "manifest_path": str(submit_path),
            "details": upload_result,
        }

    def _latest_run_upload_manifest(self, run_id: str = "") -> dict[str, Any]:
        if run_id:
            manifest_path = resolve_run_dir(self.project_root, run_id) / "upload" / "upload_manifest.json"
            if manifest_path.is_file():
                try:
                    return json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return {}
        runs_root = self.project_root / "outputs" / "runs"
        if not runs_root.is_dir():
            return {}
        manifests = sorted(runs_root.glob("*/upload/upload_manifest.json"), reverse=True)
        for path in manifests[:1]:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
        return {}

    def _list_legacy_packages(self, *, limit: int = 5) -> list[dict[str, Any]]:
        root = self.project_root / UPLOAD_ROOT
        if not root.is_dir():
            return []
        packages: list[dict[str, Any]] = []
        for manifest in sorted(root.glob("*/upload_package.json"), reverse=True)[:limit]:
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                packages.append(payload)
        return packages


__all__ = ["UPLOAD_MANAGER_VERSION", "UploadManager"]
