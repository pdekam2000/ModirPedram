"""Product studio service — channel profile, create video preflight, scheduling."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from content_brain.branding.channel_assets_store import ChannelAssetsStore
from content_brain.channel.channel_profile_generator import generate_channel_profile_suggestion
from content_brain.execution.runway_live_post_processor import collect_valid_download_paths
from content_brain.product.topic_authority_trace import TopicAuthorityTrace
from content_brain.platform.results_run_loader import load_run_results
from content_brain.platform.run_isolation import (
    create_isolated_run_context,
    require_story_package_for_run,
)
from content_brain.platform.run_output_versioning import list_run_history
from content_brain.vision.visual_continuity_pipeline import (
    run_visual_continuity_verification,
    visual_continuity_report_path,
)
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.product_settings.last_topic_store import ProductLastTopicStore
from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test
from content_brain.execution.content_brain_live_smoke_handoff import (
    clear_registered_e2e_result,
    register_e2e_result,
    resolve_live_smoke_prompts,
)
from content_brain.profiles.channel_identity_store import ChannelIdentity, ChannelIdentityStore
from content_brain.scheduling.duration_planner import (
    duration_plan_to_dict,
    is_kling_native_audio_route,
    kling_duration_preflight_metadata,
    plan_duration,
    validate_duration_seconds,
)
from content_brain.audio.audio_strategy_router import route_audio_strategy
from content_brain.execution.kling_product_run import (
    PRODUCT_STUDIO_APPROVED_BY,
    run_kling_product_studio_generate,
)
from content_brain.execution.kling_native_audio_models import KLING_AUDIO_STRATEGY, KLING_PROVIDER_ID
from content_brain.execution.kling_native_audio_planner import (
    build_kling_frame_preflight_api_payload,
    build_kling_preflight_api_payload,
    collect_kling_preflight_warnings,
    plan_kling_frame_from_audio_route,
    plan_kling_from_audio_route,
)
from content_brain.execution.product_multiclip_execution_plan import (
    apply_product_duration_to_preflight_dict,
    plan_product_duration,
)
from content_brain.upgrades import list_upgrade_center_patches
from content_brain.scheduling.schedule_models import VideoSchedulePlan
from content_brain.scheduling.schedule_planner import SchedulePlannerError, generate_jobs_for_plan, preview_schedule, validate_schedule_plan
from content_brain.scheduling.schedule_store import ScheduleStore


PIPELINE_STEPS = [
    "Topic",
    "Content Brain",
    "Director",
    "Critic",
    "Runway",
    "Assembly",
    "Publish Package",
]

FUTURE_PATCHES = [
    "Auto Upload Patch",
    "Real ElevenLabs Voice Patch",
    "Burned Subtitle Patch",
    "TikTok Upload Patch",
    "YouTube Upload Patch",
    "Instagram Upload Patch",
    "Advanced Calendar Automation Patch",
    "Multi-channel Management Patch",
    "Music/SFX Patch",
    "Suno Music Patch",
]

ELEVENLABS_STATUS_FILENAME = "elevenlabs_connection_status.json"


def _format_elevenlabs_error(message: str, code: str | None = None) -> str:
    text = str(message or "").strip()
    if "401" in text:
        return "401 Unauthorized"
    if code and text:
        return f"{code}: {text}"
    return text or str(code or "Connection failed")


class ProductStudioService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.channel_store = ChannelIdentityStore(self.project_root)
        self.profile_store = ProductChannelProfileStore(self.project_root)
        self.last_topic_store = ProductLastTopicStore(self.project_root)
        self.schedule_store = ScheduleStore(self.project_root)

    def get_last_topic(self) -> dict[str, Any]:
        return self.last_topic_store.load()

    def save_last_topic(self, *, topic: str, topic_mode: str = "custom") -> dict[str, Any]:
        return self.last_topic_store.save(topic=topic, topic_mode=topic_mode)

    @staticmethod
    def _apply_product_studio_kling_defaults(payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload)
        merged.setdefault("free_credit_first", True)
        merged.setdefault("operator_paid_approval", False)
        merged.setdefault("approve_generate", False)
        merged.setdefault("approved_by", "")
        merged.setdefault("confirm_credit_spend", False)
        return merged

    def _resolve_product_provider_runtime(self, payload: dict[str, Any]) -> str:
        from content_brain.execution.pwmap_runway_agent_adapter import resolve_product_provider_runtime

        return resolve_product_provider_runtime(payload, self.get_channel_profile())

    def _default_channel(self) -> ChannelIdentity:
        active = self.channel_store.load_active()
        if active:
            return active
        return ChannelIdentity(
            channel_name="My Channel",
            main_niche="selfcare",
            sub_niche="women skincare",
            audience="young women interested in skincare routines",
            tone_story_style="cinematic",
            platform="youtube_shorts",
            language="English",
            default_duration_seconds=30,
            default_provider="runway",
            metadata={"channel_topic": "women skincare", "upload_platforms": ["tiktok", "instagram_reels", "youtube_shorts"]},
        )

    def get_channel_profile(self) -> dict[str, Any]:
        saved = self.profile_store.load()
        return {
            "channel_name": str(saved.get("channel_name") or ""),
            "main_niche": str(saved.get("main_niche") or ""),
            "sub_niche": str(saved.get("sub_niche") or ""),
            "channel_topic": str(saved.get("channel_topic") or saved.get("sub_niche") or saved.get("main_niche") or ""),
            "youtube_channel_topic": str(
                saved.get("youtube_channel_topic") or saved.get("channel_topic") or saved.get("sub_niche") or ""
            ),
            "tiktok_channel_topic": str(saved.get("tiktok_channel_topic") or ""),
            "instagram_channel_topic": str(saved.get("instagram_channel_topic") or ""),
            "target_audience": str(saved.get("target_audience") or ""),
            "language": str(saved.get("language") or "English"),
            "tone_style": str(saved.get("tone_style") or "cinematic"),
            "visual_style": str(saved.get("visual_style") or saved.get("tone_style") or "cinematic realistic"),
            "youtube_video_style": str(saved.get("youtube_video_style") or saved.get("visual_style") or "cinematic realistic"),
            "instagram_video_style": str(saved.get("instagram_video_style") or "aesthetic"),
            "instagram_filter_mood": str(saved.get("instagram_filter_mood") or "neutral"),
            "tiktok_video_style": str(saved.get("tiktok_video_style") or "energetic"),
            "tiktok_pace": str(saved.get("tiktok_pace") or "medium"),
            "default_platform": str(saved.get("default_platform") or "youtube_shorts"),
            "default_duration_seconds": int(saved.get("default_duration_seconds") or 30),
            "default_provider": str(saved.get("default_provider") or "runway"),
            "default_voice": str(saved.get("default_voice") or ""),
            "default_narration_provider": str(saved.get("default_narration_provider") or "elevenlabs"),
            "audio_source": str(saved.get("audio_source") or "runway_native"),
            "music_provider": str(saved.get("music_provider") or "none"),
            "preferred_topics": list(saved.get("preferred_topics") or []),
            "forbidden_topics": list(saved.get("forbidden_topics") or []),
            "content_formats": list(saved.get("content_formats") or []),
            "upload_platforms": list(saved.get("upload_platforms") or ["tiktok", "instagram_reels", "youtube_shorts"]),
            "use_ai_director_default": bool(saved.get("use_ai_director_default", True)),
            "use_prompt_critic_default": bool(saved.get("use_prompt_critic_default", True)),
            "branding_enabled": bool(saved.get("branding_enabled", True)),
            "logo_enabled": bool(saved.get("logo_enabled", True)),
            "logo_position": str(saved.get("logo_position") or "top_right"),
            "logo_scale": float(saved.get("logo_scale") or 0.12),
            "subtitle_enabled": bool(saved.get("subtitle_enabled", True)),
            "subtitle_style": str(saved.get("subtitle_style") or "tiktok"),
            "subtitle_position": str(saved.get("subtitle_position") or "bottom_center"),
            "cta_enabled": bool(saved.get("cta_enabled", True)),
            "cta_text": str(saved.get("cta_text") or "Subscribe"),
            "cta_position": str(saved.get("cta_position") or "top_right"),
            "cta_start_seconds": float(saved.get("cta_start_seconds") or 5),
            "cta_end_seconds": float(saved.get("cta_end_seconds") or 24),
            "cta_frequency": str(saved.get("cta_frequency") or "end"),
            "cta_style": str(saved.get("cta_style") or "text_only"),
            "cta_graphic_path": str(saved.get("cta_graphic_path") or ""),
            "cta_graphic_position": str(saved.get("cta_graphic_position") or "bottom_center"),
            "cta_graphic_duration_seconds": float(saved.get("cta_graphic_duration_seconds") or 5),
            "logo_path": str(saved.get("logo_path") or ""),
            "intro_enabled": bool(saved.get("intro_enabled", False)),
            "intro_text": str(saved.get("intro_text") or ""),
            "intro_duration": float(saved.get("intro_duration") or 2.0),
            "intro_type": str(saved.get("intro_type") or "none"),
            "intro_image_path": str(saved.get("intro_image_path") or ""),
            "intro_video_path": str(saved.get("intro_video_path") or ""),
            "intro_fade_effect": str(saved.get("intro_fade_effect") or "fade_in"),
            "outro_enabled": bool(saved.get("outro_enabled", False)),
            "outro_text": str(saved.get("outro_text") or ""),
            "outro_duration": float(saved.get("outro_duration") or 3.0),
            "outro_type": str(saved.get("outro_type") or "none"),
            "outro_image_path": str(saved.get("outro_image_path") or ""),
            "outro_video_path": str(saved.get("outro_video_path") or ""),
            "outro_fade_effect": str(saved.get("outro_fade_effect") or "fade_out"),
            "outro_subscribe_enabled": bool(saved.get("outro_subscribe_enabled", True)),
            "outro_subscribe_style": str(saved.get("outro_subscribe_style") or "classic_red"),
            "outro_subscribe_custom_color": str(saved.get("outro_subscribe_custom_color") or "#E62117"),
            "youtube_upload_enabled": bool(saved.get("youtube_upload_enabled", False)),
            "youtube_privacy": str(saved.get("youtube_privacy") or "public"),
            "youtube_default_description": str(saved.get("youtube_default_description") or ""),
            "youtube_default_hashtags": list(saved.get("youtube_default_hashtags") or []),
            "youtube_upload_confirmed": bool(saved.get("youtube_upload_confirmed", False)),
            "youtube_credentials_configured": bool(saved.get("youtube_credentials_configured", False)),
            "youtube_oauth_client_path": str(saved.get("youtube_oauth_client_path") or ""),
            "youtube_made_for_kids": bool(saved.get("youtube_made_for_kids", False)),
            "youtube_require_confirmation": bool(saved.get("youtube_require_confirmation", False)),
            "youtube_playlist_id": str(saved.get("youtube_playlist_id") or ""),
            "instagram_upload_enabled": bool(saved.get("instagram_upload_enabled", False)),
            "instagram_app_id": str(saved.get("instagram_app_id") or ""),
            "instagram_app_secret": str(saved.get("instagram_app_secret") or ""),
            "instagram_access_token": str(saved.get("instagram_access_token") or ""),
            "instagram_account_id": str(saved.get("instagram_account_id") or ""),
            "instagram_token_expires_at": str(saved.get("instagram_token_expires_at") or ""),
            "instagram_token_exchange_message": "",
            "instagram_public_base_url": str(saved.get("instagram_public_base_url") or ""),
            "instagram_privacy": str(saved.get("instagram_privacy") or "public"),
            "tiktok_upload_enabled": bool(saved.get("tiktok_upload_enabled", False)),
            "tiktok_client_key": str(saved.get("tiktok_client_key") or ""),
            "tiktok_client_secret": str(saved.get("tiktok_client_secret") or ""),
            "tiktok_access_token": str(saved.get("tiktok_access_token") or ""),
            "tiktok_privacy": str(saved.get("tiktok_privacy") or "PUBLIC_TO_EVERYONE"),
            "local_mode": bool(saved.get("local_mode", True)),
            "updated_at": str(saved.get("updated_at") or ""),
        }

    def suggest_channel_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return AI/rule-based suggestions without persisting."""
        suggestion = generate_channel_profile_suggestion(
            str(payload.get("channel_topic") or ""),
            language_preference=str(payload.get("language_preference") or "") or None,
            platform_preference=str(payload.get("platform_preference") or "") or None,
            force_rule_based=bool(payload.get("force_rule_based")),
        )
        return suggestion.to_dict()

    def save_channel_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self.profile_store.load()
        exchange_message = ""

        store_payload = {
            "channel_name": str(payload.get("channel_name") or ""),
            "main_niche": str(payload.get("main_niche") or ""),
            "sub_niche": str(payload.get("sub_niche") or ""),
            "channel_topic": str(payload.get("channel_topic") or payload.get("youtube_channel_topic") or ""),
            "youtube_channel_topic": str(payload.get("youtube_channel_topic") or payload.get("channel_topic") or ""),
            "tiktok_channel_topic": str(payload.get("tiktok_channel_topic") or ""),
            "instagram_channel_topic": str(payload.get("instagram_channel_topic") or ""),
            "target_audience": str(payload.get("target_audience") or ""),
            "language": str(payload.get("language") or "English"),
            "tone_style": str(payload.get("tone_style") or "cinematic"),
            "visual_style": str(payload.get("visual_style") or payload.get("tone_style") or "cinematic realistic"),
            "youtube_video_style": str(
                payload.get("youtube_video_style")
                or payload.get("visual_style")
                or previous.get("youtube_video_style")
                or "cinematic realistic"
            ),
            "instagram_video_style": str(
                payload.get("instagram_video_style") or previous.get("instagram_video_style") or "aesthetic"
            ),
            "instagram_filter_mood": str(
                payload.get("instagram_filter_mood") or previous.get("instagram_filter_mood") or "neutral"
            ),
            "tiktok_video_style": str(
                payload.get("tiktok_video_style") or previous.get("tiktok_video_style") or "energetic"
            ),
            "tiktok_pace": str(payload.get("tiktok_pace") or previous.get("tiktok_pace") or "medium"),
            "default_platform": str(payload.get("default_platform") or "youtube_shorts"),
            "default_duration_seconds": int(payload.get("default_duration_seconds") or 30),
            "default_provider": str(payload.get("default_provider") or "runway"),
            "default_voice": str(payload.get("default_voice") or ""),
            "default_narration_provider": str(payload.get("default_narration_provider") or "elevenlabs"),
            "audio_source": str(payload.get("audio_source") or "runway_native"),
            "music_provider": str(payload.get("music_provider") or "none"),
            "preferred_topics": list(payload.get("preferred_topics") or []),
            "forbidden_topics": list(payload.get("forbidden_topics") or []),
            "content_formats": list(payload.get("content_formats") or []),
            "upload_platforms": list(payload.get("upload_platforms") or []),
            "use_ai_director_default": bool(payload.get("use_ai_director_default", True)),
            "use_prompt_critic_default": bool(payload.get("use_prompt_critic_default", True)),
            "branding_enabled": bool(payload.get("branding_enabled", True)),
            "logo_enabled": bool(payload.get("logo_enabled", True)),
            "logo_position": str(payload.get("logo_position") or "top_right"),
            "logo_scale": float(payload.get("logo_scale") or 0.12),
            "subtitle_enabled": bool(payload.get("subtitle_enabled", True)),
            "subtitle_style": str(payload.get("subtitle_style") or "tiktok"),
            "subtitle_position": str(payload.get("subtitle_position") or "bottom_center"),
            "cta_enabled": bool(payload.get("cta_enabled", True)),
            "cta_text": str(payload.get("cta_text") or "Subscribe"),
            "cta_position": str(payload.get("cta_position") or "top_right"),
            "cta_start_seconds": float(payload.get("cta_start_seconds") or 5),
            "cta_end_seconds": float(payload.get("cta_end_seconds") or 24),
            "cta_frequency": str(payload.get("cta_frequency") or "end"),
            "cta_style": str(payload.get("cta_style") or "text_only"),
            "cta_graphic_path": str(payload.get("cta_graphic_path") or ""),
            "cta_graphic_position": str(payload.get("cta_graphic_position") or "bottom_center"),
            "cta_graphic_duration_seconds": float(payload.get("cta_graphic_duration_seconds") or 5),
            "logo_path": str(payload.get("logo_path") or ""),
            "intro_enabled": bool(payload.get("intro_enabled", False)),
            "intro_text": str(payload.get("intro_text") or ""),
            "intro_duration": float(payload.get("intro_duration") or 2.0),
            "intro_type": str(payload.get("intro_type") or "none"),
            "intro_image_path": str(payload.get("intro_image_path") or ""),
            "intro_video_path": str(payload.get("intro_video_path") or ""),
            "intro_fade_effect": str(payload.get("intro_fade_effect") or "fade_in"),
            "outro_enabled": bool(payload.get("outro_enabled", False)),
            "outro_text": str(payload.get("outro_text") or ""),
            "outro_duration": float(payload.get("outro_duration") or 3.0),
            "outro_type": str(payload.get("outro_type") or "none"),
            "outro_image_path": str(payload.get("outro_image_path") or ""),
            "outro_video_path": str(payload.get("outro_video_path") or ""),
            "outro_fade_effect": str(payload.get("outro_fade_effect") or "fade_out"),
            "outro_subscribe_enabled": bool(payload.get("outro_subscribe_enabled", True)),
            "outro_subscribe_style": str(payload.get("outro_subscribe_style") or "classic_red"),
            "outro_subscribe_custom_color": str(payload.get("outro_subscribe_custom_color") or "#E62117"),
            "youtube_upload_enabled": bool(payload.get("youtube_upload_enabled", False)),
            "youtube_privacy": str(payload.get("youtube_privacy") or "public"),
            "youtube_default_description": str(payload.get("youtube_default_description") or ""),
            "youtube_default_hashtags": list(payload.get("youtube_default_hashtags") or []),
            "youtube_upload_confirmed": bool(payload.get("youtube_upload_confirmed", False)),
            "youtube_credentials_configured": bool(payload.get("youtube_credentials_configured", False)),
            "youtube_oauth_client_path": str(payload.get("youtube_oauth_client_path") or ""),
            "youtube_made_for_kids": bool(payload.get("youtube_made_for_kids", False)),
            "youtube_require_confirmation": bool(payload.get("youtube_require_confirmation", False)),
            "youtube_playlist_id": str(payload.get("youtube_playlist_id") or ""),
            "instagram_upload_enabled": bool(payload.get("instagram_upload_enabled", False)),
            "instagram_app_id": str(payload.get("instagram_app_id") or ""),
            "instagram_app_secret": str(payload.get("instagram_app_secret") or ""),
            "instagram_access_token": str(payload.get("instagram_access_token") or ""),
            "instagram_account_id": str(payload.get("instagram_account_id") or ""),
            "instagram_token_expires_at": str(payload.get("instagram_token_expires_at") or previous.get("instagram_token_expires_at") or ""),
            "instagram_public_base_url": str(payload.get("instagram_public_base_url") or ""),
            "instagram_privacy": str(payload.get("instagram_privacy") or "public"),
            "tiktok_upload_enabled": bool(payload.get("tiktok_upload_enabled", False)),
            "tiktok_client_key": str(payload.get("tiktok_client_key") or ""),
            "tiktok_client_secret": str(payload.get("tiktok_client_secret") or ""),
            "tiktok_access_token": str(payload.get("tiktok_access_token") or ""),
            "tiktok_privacy": str(payload.get("tiktok_privacy") or "PUBLIC_TO_EVERYONE"),
            "local_mode": bool(payload.get("local_mode", True)),
        }

        new_token = str(store_payload.get("instagram_access_token") or "").strip()
        old_token = str(previous.get("instagram_access_token") or "").strip()
        if new_token and new_token != old_token:
            from content_brain.upload.instagram_token_exchange import maybe_exchange_instagram_token

            exchange = maybe_exchange_instagram_token(short_lived_token=new_token, profile=store_payload)
            if exchange.get("ok"):
                store_payload["instagram_access_token"] = str(exchange.get("access_token") or new_token)
                store_payload["instagram_token_expires_at"] = str(exchange.get("expires_at") or "")
                exchange_message = str(exchange.get("message") or "Long-lived token saved.")
            else:
                exchange_message = str(exchange.get("message") or "Token exchange skipped.")
        elif new_token:
            from content_brain.upload.instagram_auth import refresh_instagram_profile_ids

            store_payload = refresh_instagram_profile_ids(store_payload)

        self.profile_store.save(store_payload)

        current = self._default_channel()
        meta = dict(current.metadata or {})
        meta["channel_topic"] = store_payload["channel_topic"]
        meta["upload_platforms"] = store_payload["upload_platforms"]
        channel = ChannelIdentity(
            channel_id=current.channel_id,
            channel_name=store_payload["channel_name"] or current.channel_name,
            main_niche=store_payload["main_niche"] or current.main_niche,
            sub_niche=store_payload["sub_niche"] or current.sub_niche,
            audience=store_payload["target_audience"] or current.audience,
            tone_story_style=store_payload["tone_style"] or current.tone_story_style,
            platform=store_payload["default_platform"] or current.platform,
            language=store_payload["language"] or current.language,
            default_duration_seconds=store_payload["default_duration_seconds"],
            default_provider=store_payload["default_provider"],
            created_at=current.created_at,
            metadata=meta,
        )
        self.channel_store.save(channel, set_active=True)
        profile = self.get_channel_profile()
        if exchange_message:
            profile["instagram_token_exchange_message"] = exchange_message
        return profile

    def get_channel_logo_status(self) -> dict[str, Any]:
        return ChannelAssetsStore(self.project_root).logo_status()

    def save_channel_logo(self, payload: bytes, *, content_type: str = "", filename: str = "") -> dict[str, Any]:
        store = ChannelAssetsStore(self.project_root)
        path = store.save_logo_bytes(payload, content_type=content_type, filename=filename)
        ProductChannelProfileStore(self.project_root).save({"logo_path": path})
        return {"ok": True, "logo_path": path, "logo_exists": True}

    def save_branding_asset(
        self,
        kind: str,
        payload: bytes,
        *,
        content_type: str = "",
        filename: str = "",
    ) -> dict[str, Any]:
        store = ChannelAssetsStore(self.project_root)
        path = store.save_asset(kind, payload, content_type=content_type, filename=filename)
        profile_key = {
            "logo": "logo_path",
            "cta_graphic": "cta_graphic_path",
            "intro_image": "intro_image_path",
            "intro_video": "intro_video_path",
            "outro_image": "outro_image_path",
            "outro_video": "outro_video_path",
        }.get(kind)
        if profile_key:
            ProductChannelProfileStore(self.project_root).save({profile_key: path})
        return {"ok": True, "kind": kind, "asset_path": path, "exists": True}

    def get_branding_asset_path(self, asset_kind: str) -> Path | None:
        from content_brain.branding.branding_assets_store import ASSET_KINDS

        if asset_kind == "logo":
            return ChannelAssetsStore(self.project_root).asset_path("logo")
        if asset_kind not in ASSET_KINDS:
            raise ValueError(f"Unsupported branding asset kind: {asset_kind}")
        return ChannelAssetsStore(self.project_root).asset_path(asset_kind)

    def _elevenlabs_status_path(self) -> Path:
        return self.project_root / "project_brain" / "runtime_state" / ELEVENLABS_STATUS_FILENAME

    def _load_elevenlabs_last_test(self) -> dict[str, Any]:
        path = self._elevenlabs_status_path()
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_elevenlabs_last_test(self, payload: dict[str, Any]) -> None:
        path = self._elevenlabs_status_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _elevenlabs_config_snapshot(self) -> dict[str, Any]:
        from core.env_bootstrap import bootstrap_project_env
        from providers.elevenlabs_config import ElevenLabsConfigResolver

        bootstrap_project_env(project_root=self.project_root)

        profile = self.profile_store.load()
        voice_id = str(profile.get("default_voice") or "").strip() or None
        config = ElevenLabsConfigResolver(self.project_root).resolve(voice_id=voice_id)
        return config.to_summary()

    def get_elevenlabs_connection_status(self) -> dict[str, Any]:
        config = self._elevenlabs_config_snapshot()
        last = self._load_elevenlabs_last_test()
        key_detected = bool(config.get("has_api_key"))
        probe_status = str(last.get("voices_probe_status") or "not_tested")
        last_error = str(last.get("last_error") or "")
        message = "API key not detected in server environment."
        if key_detected and probe_status == "passed":
            message = "ElevenLabs voices probe passed."
        elif key_detected and probe_status == "failed":
            message = last_error or "ElevenLabs voices probe failed."
        elif key_detected:
            message = "API key detected. Run connection test to probe ElevenLabs voices API."
        return {
            "ok": True,
            "key_detected": key_detected,
            "api_key_env": str(config.get("api_key_env") or "ELEVENLABS_API_KEY"),
            "provider_enabled": bool(config.get("enabled_in_registry", True)),
            "voices_probe_status": probe_status,
            "last_error": last_error,
            "last_tested_at": str(last.get("last_tested_at") or ""),
            "voice_count": last.get("voice_count"),
            "message": message,
        }

    def test_elevenlabs_connection(self) -> dict[str, Any]:
        from providers.audio.elevenlabs_provider import ElevenLabsNarrationProvider

        config = self._elevenlabs_config_snapshot()
        profile = self.profile_store.load()
        voice_id = str(profile.get("default_voice") or "").strip() or None
        provider = ElevenLabsNarrationProvider(self.project_root, voice_id=voice_id)
        validation = provider.validate_connection()
        tested_at = datetime.now(timezone.utc).isoformat()

        if validation.get("ok"):
            voices = provider.get_available_voices()
            saved = {
                "voices_probe_status": "passed",
                "last_error": "",
                "last_tested_at": tested_at,
                "voice_count": len(voices),
            }
            self._save_elevenlabs_last_test(saved)
            result = self.get_elevenlabs_connection_status()
            result["message"] = f"ElevenLabs voices probe passed ({len(voices)} voices)."
            return result

        error = _format_elevenlabs_error(
            str(validation.get("message") or ""),
            str(validation.get("code") or "") or None,
        )
        saved = {
            "voices_probe_status": "failed",
            "last_error": error,
            "last_tested_at": tested_at,
            "voice_count": None,
        }
        self._save_elevenlabs_last_test(saved)
        result = self.get_elevenlabs_connection_status()
        result["message"] = error
        return result

    def create_video_preflight(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self.get_channel_profile()
        topic_mode = str(payload.get("topic_mode") or payload.get("topic_source") or "channel")
        custom_topic = str(payload.get("custom_topic") or "").strip()
        platform = str(payload.get("platform") or profile.get("default_platform") or "youtube_shorts")
        from content_brain.automation.platform_daily_scheduler import resolve_platform_topic
        from content_brain.automation.platform_daily_scheduler_store import resolve_platform_duration_seconds

        automation_mode = bool(payload.get("automation_mode"))
        if topic_mode == "custom" and custom_topic and not automation_mode:
            channel_topic = custom_topic
        else:
            channel_topic = resolve_platform_topic(
                platform,
                profile,
                entry_topic=str(payload.get("scheduler_topic") or custom_topic or ""),
                use_global_fallback=not automation_mode,
            )
        authoritative_topic = channel_topic

        provider_request = str(payload.get("provider") or profile.get("default_provider") or "runway").strip().lower()
        provider = provider_request
        audio_strategy_request = str(
            payload.get("audio_strategy")
            or payload.get("audio_strategy_override")
            or "auto"
        )
        duration_seconds = int(
            payload.get("duration_seconds")
            or resolve_platform_duration_seconds(self.project_root, platform, profile=profile)
        )
        from content_brain.execution.platform_video_style import resolve_platform_mood, resolve_platform_video_style

        style = resolve_platform_video_style(platform, profile, payload)
        story_package = payload.get("story_package")
        if isinstance(story_package, dict):
            story_package_dict: dict[str, Any] | None = story_package
        else:
            story_package_dict = None
        story_summary = str(payload.get("story_summary") or "").strip()
        characters = payload.get("characters")
        character_list = [str(item) for item in characters] if isinstance(characters, list) else None
        environment = str(payload.get("environment") or "").strip()
        mood = resolve_platform_mood(platform, profile, payload) or str(
            payload.get("mood") or payload.get("tone") or ""
        ).strip()

        route_audio_strategy_value = audio_strategy_request
        route_provider_value = provider_request
        if is_kling_native_audio_route(provider=provider_request, audio_strategy=audio_strategy_request):
            route_audio_strategy_value = KLING_AUDIO_STRATEGY
            route_provider_value = KLING_PROVIDER_ID

        audio_route = route_audio_strategy(
            topic=authoritative_topic,
            niche=str(profile.get("main_niche") or profile.get("sub_niche") or ""),
            platform=platform,
            style=style,
            duration_seconds=duration_seconds,
            character_count=int(payload.get("character_count") or 0),
            dialogue_count=int(payload.get("dialogue_count") or 0),
            audio_strategy=route_audio_strategy_value,
            video_provider=route_provider_value,
            narration_provider_disabled=bool(profile.get("narration_provider_disabled")),
            block_kling_native=bool(profile.get("block_kling_native")),
        )

        resolved_audio_strategy = audio_route.audio_strategy
        if is_kling_native_audio_route(provider=provider_request, audio_strategy=audio_strategy_request):
            resolved_audio_strategy = KLING_AUDIO_STRATEGY
            provider = KLING_PROVIDER_ID
        elif audio_strategy_request.strip().lower() == "auto":
            provider = audio_route.provider_recommendation
            if resolved_audio_strategy == KLING_AUDIO_STRATEGY:
                provider = KLING_PROVIDER_ID
        elif resolved_audio_strategy == KLING_AUDIO_STRATEGY:
            provider = KLING_PROVIDER_ID

        duration_plan = plan_duration(
            duration_seconds=duration_seconds,
            provider=provider,
            audio_strategy=resolved_audio_strategy,
        )
        from content_brain.platform.platform_aspect_defaults import resolve_aspect_ratio

        aspect_ratio = resolve_aspect_ratio(
            platform=platform,
            aspect_ratio=str(payload.get("aspect_ratio") or "").strip() or None,
            aspect_ratio_manual=bool(payload.get("aspect_ratio_manual")),
        )
        if duration_plan.kling_native_audio:
            provider = KLING_PROVIDER_ID
            resolved_audio_strategy = KLING_AUDIO_STRATEGY

        steps = list(PIPELINE_STEPS)
        if not payload.get("use_ai_director"):
            steps = [s for s in steps if s != "Director"]
        if not payload.get("use_prompt_critic"):
            steps = [s for s in steps if s != "Critic"]

        warnings = list(duration_plan.warnings)
        if topic_mode == "channel" and custom_topic:
            warnings.append("custom_topic ignored because channel topic mode is selected")

        from content_brain.execution.product_multiclip_execution_plan import plan_product_duration

        product_duration = plan_product_duration(duration_seconds)
        ideation_clip_count = int(product_duration.get("clip_count") or duration_plan.clip_count or 1)
        from content_brain.execution.channel_story_ideation import apply_channel_story_ideation

        story_ideation = apply_channel_story_ideation(
            project_root=self.project_root,
            payload=payload,
            channel_topic=channel_topic,
            niche=str(profile.get("main_niche") or profile.get("sub_niche") or ""),
            target_platform=platform,
            style=style,
            mood=mood or str(profile.get("tone_style") or ""),
            duration_seconds=duration_seconds,
            clip_count=ideation_clip_count,
        )
        authoritative_topic = str(story_ideation.get("authoritative_topic") or authoritative_topic)
        story_package_dict = dict(story_ideation.get("story_package") or story_package_dict or {})
        story_summary = str(story_ideation.get("story_summary") or story_summary or "")
        if story_ideation.get("story_repetition_warning"):
            warnings.append(f"story_repetition_warning:{story_ideation['story_repetition_warning']}")

        kling_preflight_active = is_kling_native_audio_route(
            provider=provider,
            audio_strategy=resolved_audio_strategy,
        ) or duration_plan.kling_native_audio
        pwmap_kling_path = bool(
            payload.get("browser_automation")
            or str(payload.get("provider_runtime") or "").strip().lower() == "pwmap_agent"
            or automation_mode
            or bool(payload.get("execute_preflight"))
        )
        if pwmap_kling_path:
            kling_preflight_active = True
            provider = KLING_PROVIDER_ID
            resolved_audio_strategy = KLING_AUDIO_STRATEGY

        response: dict[str, Any] = {
            "ok": True,
            "authoritative_topic": authoritative_topic,
            "provider": provider,
            "audio_strategy": resolved_audio_strategy,
            "audio_strategy_request": audio_strategy_request,
            "audio_strategy_route": audio_route.to_dict(),
            "duration_plan": duration_plan_to_dict(duration_plan),
            "topic_mode": topic_mode,
            "platform": platform,
            "aspect_ratio": aspect_ratio,
            "platform_targets": list(payload.get("platform_targets") or ([platform] if platform else [])),
            "style": style,
            "visual_style": style,
            "pipeline_steps": steps,
            "warnings": warnings,
            "preflight_mode": "preview_only",
        }

        if kling_preflight_active:
            product_duration = plan_product_duration(duration_seconds)
            kling_duration_meta = audio_route.kling_native_audio or kling_duration_preflight_metadata(duration_plan)
            kling_duration_meta = dict(kling_duration_meta)
            kling_duration_meta["clip_count"] = product_duration["clip_count"]
            kling_duration_meta["planned_duration_seconds"] = product_duration["duration_seconds"]
            kling_duration_meta["requested_duration_seconds"] = duration_seconds
            resolved_clip_count = int(
                payload.get("clip_count") or product_duration["clip_count"] or ideation_clip_count or 1
            )
            resolved_duration_seconds = int(
                payload.get("duration_seconds") or product_duration["duration_seconds"] or duration_seconds
            )
            kling_plan = plan_kling_frame_from_audio_route(
                topic=channel_topic,
                audio_route=audio_route,
                story_package=story_package_dict,
                story_summary=story_summary,
                platform=platform,
                mood=mood,
                style=style,
                characters=character_list,
                environment=environment,
                youtube_genre=str(profile.get("youtube_genre") or ""),
                instagram_genre=str(profile.get("instagram_genre") or ""),
                tiktok_genre=str(profile.get("tiktok_genre") or ""),
                genre=str(profile.get("genre") or ""),
                planned_duration_seconds=resolved_duration_seconds,
                clip_count=resolved_clip_count,
            )
            kling_block = build_kling_frame_preflight_api_payload(
                plan=kling_plan,
                kling_duration_plan=kling_duration_meta,
            )
            kling_block["kling_native_audio_plan"] = plan_kling_from_audio_route(
                topic=channel_topic,
                audio_route=audio_route,
                story_package=story_package_dict,
                story_summary=story_summary,
                platform=platform,
                mood=mood,
                style=style,
                characters=character_list,
                environment=environment,
            ).to_dict()
            response.update(kling_block)
            response = apply_product_duration_to_preflight_dict(response, duration_seconds=duration_seconds)
            response["provider"] = KLING_PROVIDER_ID
            response["audio_strategy"] = KLING_AUDIO_STRATEGY
            response["use_elevenlabs"] = kling_block["use_elevenlabs"]
            response["use_external_music"] = kling_block["use_external_music"]
            response["native_audio_required"] = kling_block["native_audio_required"]
            response["subtitle_required"] = kling_block["subtitle_required"]
            warnings.extend(
                collect_kling_preflight_warnings(
                    plan=kling_plan,
                    authoritative_topic=authoritative_topic,
                    story_package=story_package_dict,
                    story_summary=story_summary,
                    require_story_package=bool(payload.get("require_story_package")),
                )
            )
            response["warnings"] = warnings
        response.update(
            {
                "channel_topic": channel_topic,
                "authoritative_topic": authoritative_topic,
                "specific_story_override": str(story_ideation.get("specific_story_override") or ""),
                "story_override_active": bool(story_ideation.get("story_override_active")),
                "story_diversity_mode": str(story_ideation.get("story_diversity_mode") or "safe_variety"),
                "channel_story_idea": dict(story_ideation.get("channel_story_idea") or {}),
                "runway_story_brief": dict(story_ideation.get("runway_story_brief") or {}),
                "story_summary": story_summary,
                "story_repetition_warning": str(story_ideation.get("story_repetition_warning") or ""),
                "story_ideation_version": str(story_ideation.get("story_ideation_version") or ""),
            }
        )
        return response

    def save_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = VideoSchedulePlan.from_dict(payload)
        if not plan.start_date:
            plan.start_date = date.today().isoformat()
        if not plan.end_date:
            plan.end_date = (date.today() + timedelta(days=6)).isoformat()
        errors = validate_schedule_plan(plan)
        if errors:
            raise SchedulePlannerError("; ".join(errors))
        duration_plan = plan_duration(duration_seconds=plan.duration_seconds, provider=plan.provider)
        plan.clip_count = duration_plan.clip_count
        self.schedule_store.save_plan(plan)
        return plan.to_dict()

    def preview_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = VideoSchedulePlan.from_dict(payload)
        profile = self.get_channel_profile()
        return preview_schedule(
            plan,
            channel_niche=str(profile.get("main_niche") or ""),
            channel_topic=str(profile.get("channel_topic") or ""),
            tiktok_channel_topic=str(profile.get("tiktok_channel_topic") or ""),
            instagram_channel_topic=str(profile.get("instagram_channel_topic") or ""),
        )

    def generate_schedule_jobs(self, schedule_id: str, *, only_date: str | None = None) -> dict[str, Any]:
        plan = self.schedule_store.load_plan(schedule_id)
        profile = self.get_channel_profile()
        jobs = generate_jobs_for_plan(
            plan,
            channel_niche=str(profile.get("main_niche") or ""),
            channel_topic=str(profile.get("channel_topic") or ""),
            tiktok_channel_topic=str(profile.get("tiktok_channel_topic") or ""),
            instagram_channel_topic=str(profile.get("instagram_channel_topic") or ""),
            only_date=only_date,
        )
        self.schedule_store.save_jobs(schedule_id, jobs)
        return {"schedule_id": schedule_id, "job_count": len(jobs), "jobs": [job.to_dict() for job in jobs]}

    def list_schedules(self) -> list[dict[str, Any]]:
        return [plan.to_dict() for plan in self.schedule_store.list_plans()]

    def disable_schedule(self, schedule_id: str) -> dict[str, Any]:
        plan = self.schedule_store.load_plan(schedule_id)
        plan.enabled = False
        self.schedule_store.save_plan(plan)
        return plan.to_dict()

    @staticmethod
    def _read_json_file(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _visual_continuity_report_is_stale(visual_continuity: dict[str, Any]) -> bool:
        clips = list(visual_continuity.get("clips") or [])
        if not clips:
            return True
        for clip in clips:
            issues = list(clip.get("issues") or [])
            frame_paths = clip.get("frame_paths") or {}
            if "verification_error" in issues and not frame_paths:
                return True
            if clip.get("score") in (0, 0.0) and not clip.get("vision_review"):
                return True
        return False

    @staticmethod
    def _visual_continuity_not_available(expected_run_id: str) -> dict[str, Any]:
        return {
            "version": "visual_continuity_pipeline_v1",
            "status": "not_available_for_latest_run",
            "message": "Visual continuity not available for latest run.",
            "run_id": expected_run_id,
            "overall_pass": None,
            "overall_score": None,
            "clips": [],
            "warnings": [],
            "created_at": "",
        }

    @staticmethod
    def _resolve_stored_manifest_run_id(
        project_root: Path,
        *,
        checkpoint: dict[str, Any],
        publish_dir: Path,
    ) -> str:
        run_id = str(checkpoint.get("run_id") or "").strip()
        metadata_path = publish_dir / "metadata.json"
        if metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = {}
            if isinstance(metadata, dict):
                run_id = str(metadata.get("run_id") or run_id).strip()
        return run_id

    def _resolve_visual_continuity_report(
        self,
        *,
        runway_report: dict[str, Any],
        runway_completed: bool,
        downloaded_paths: list[str],
    ) -> dict[str, Any]:
        """Load visual continuity report for latest run; backfill if missing or stale."""
        report_path = visual_continuity_report_path(self.project_root)
        visual_continuity = self._read_json_file(report_path)

        runway_report_path_text = str(runway_report.get("visual_continuity_report_path") or "").strip()
        if runway_report_path_text:
            alternate = self._read_json_file(Path(runway_report_path_text))
            if alternate.get("clips") and not visual_continuity.get("clips"):
                visual_continuity = alternate

        expected_run_id = str(
            runway_report.get("content_brain_run_id")
            or runway_report.get("run_id")
            or ""
        ).strip()
        requested = int(runway_report.get("clip_count") or 0)
        valid_downloads, _ = collect_valid_download_paths([str(item) for item in downloaded_paths if item])
        downloads_ready = requested > 0 and len(valid_downloads) == requested
        post_processing_status = str(runway_report.get("post_processing_status") or "")
        post_processing_done = post_processing_status == "completed"

        stored_run_id = str(visual_continuity.get("run_id") or "").strip()
        run_id_matches = not expected_run_id or stored_run_id == expected_run_id
        has_clips = bool(visual_continuity.get("clips"))

        if expected_run_id and stored_run_id and not run_id_matches:
            if not downloads_ready:
                return self._visual_continuity_not_available(expected_run_id)
            visual_continuity = {}
            has_clips = False
            run_id_matches = False

        should_backfill = (
            runway_completed
            and downloads_ready
            and (post_processing_done or post_processing_status == "skipped")
            and (not has_clips or not run_id_matches or self._visual_continuity_report_is_stale(visual_continuity))
        )
        if not should_backfill:
            if expected_run_id and stored_run_id and not run_id_matches:
                return self._visual_continuity_not_available(expected_run_id)
            return visual_continuity

        topic = str(
            runway_report.get("content_brain_topic")
            or runway_report.get("topic_label")
            or runway_report.get("story_idea")
            or ""
        )
        try:
            return run_visual_continuity_verification(
                project_root=self.project_root,
                topic=topic,
                clip_video_paths=valid_downloads,
                run_id=expected_run_id,
            )
        except Exception as exc:
            return {
                "version": "visual_continuity_pipeline_v1",
                "status": "failed",
                "run_id": expected_run_id,
                "topic": topic,
                "overall_pass": False,
                "overall_score": 0.0,
                "clips": [],
                "warnings": [f"backfill_error:{exc}"],
                "created_at": "",
            }

    @staticmethod
    def _resolve_branding_status(
        *,
        runway_report: dict[str, Any],
        branding_manifest: dict[str, Any],
        publish_metadata: dict[str, Any],
        stale_manifest_ignored: bool,
    ) -> dict[str, Any]:
        if stale_manifest_ignored:
            return {
                "status": "not_available",
                "branding_enabled": False,
                "final_branded_video_path": "",
                "subtitled_video_path": "",
                "subtitles": "SKIP",
                "logo": "SKIP",
                "cta": "SKIP",
                "intro": "SKIP",
                "outro": "SKIP",
            }

        source = branding_manifest if branding_manifest else {}
        steps = dict(source.get("steps") or runway_report.get("branding_steps") or publish_metadata.get("branding_steps") or {})

        def step_label(key: str) -> str:
            step = steps.get(key) if isinstance(steps.get(key), dict) else {}
            return str(step.get("status") or runway_report.get(f"branding_{key}_status") or "SKIP")

        return {
            "status": str(source.get("status") or runway_report.get("branding_status") or publish_metadata.get("branding_status") or ""),
            "branding_enabled": bool(
                source.get("branding_enabled", publish_metadata.get("branding_enabled", runway_report.get("branding_enabled", False)))
            ),
            "final_branded_video_path": str(
                source.get("final_branded_video_path")
                or runway_report.get("final_branded_video_path")
                or publish_metadata.get("branded_video_path")
                or ""
            ),
            "subtitled_video_path": str(source.get("subtitled_video_path") or ""),
            "subtitles": step_label("subtitles"),
            "logo": step_label("logo"),
            "cta": step_label("cta"),
            "intro": step_label("intro"),
            "outro": step_label("outro"),
        }

    def _merge_kling_results(self, kling_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "found": True,
            "video_path": kling_payload.get("video_path") or "",
            "publish_package_path": "",
            "platform_targets": [],
            "metadata": dict(kling_payload.get("metadata") or {}),
            "runway_completed": kling_payload.get("native_audio_status") == "completed",
            "has_downloads_only": bool(kling_payload.get("download_path")),
            "assembly_status": "KLING_NATIVE",
            "publish_status": "KLING_OUTPUT_PACKAGE",
            "downloaded_clip_count": int(kling_payload.get("clip_count") or 0),
            "selected_run_id": kling_payload.get("selected_run_id") or "",
            "run_folder": kling_payload.get("run_folder") or "",
            "run_dir": kling_payload.get("run_dir") or "",
            "topic": kling_payload.get("topic") or "",
            "latest_approved_video_path": kling_payload.get("video_path") or "",
            "final_branded_video_path": kling_payload.get("video_path") or "",
            "kling_native_audio": {
                "provider_used": kling_payload.get("provider_used"),
                "audio_strategy_used": kling_payload.get("audio_strategy_used"),
                "native_audio_status": kling_payload.get("native_audio_status"),
                "generation_status": kling_payload.get("generation_status"),
                "output_ready": bool(kling_payload.get("output_ready")),
                "recovery_available": bool(kling_payload.get("recovery_available")),
                "legacy_run_folders": list(kling_payload.get("legacy_run_folders") or []),
                "clip_count": kling_payload.get("clip_count"),
                "shot_mode": kling_payload.get("shot_mode"),
                "continuity_status": kling_payload.get("continuity_status"),
                "frames_extracted_count": kling_payload.get("frames_extracted_count"),
                "frames_uploaded_count": kling_payload.get("frames_uploaded_count"),
                "chain_complete": kling_payload.get("chain_complete"),
                "output_folder": kling_payload.get("output_folder"),
                "download_path": kling_payload.get("download_path"),
                "generation_time_seconds": kling_payload.get("generation_time_seconds"),
                "approval_information": kling_payload.get("approval_information"),
                "continuity_chain": kling_payload.get("continuity_chain"),
                "use_frame_chain": kling_payload.get("use_frame_chain"),
                "continuity_method": kling_payload.get("continuity_method"),
                "use_frame_status": kling_payload.get("use_frame_status"),
                "fallback_used": kling_payload.get("fallback_used"),
                "story_progression_status": kling_payload.get("story_progression_status"),
                "story_progression": kling_payload.get("story_progression"),
                "kling_clip_prompts": kling_payload.get("kling_clip_prompts") or [],
            },
            "output_ready": bool(kling_payload.get("output_ready")),
            "recovery_available": bool(kling_payload.get("recovery_available")),
            "generation_status": kling_payload.get("generation_status") or "",
            "legacy_run_folders": list(kling_payload.get("legacy_run_folders") or []),
            "video_quality_judge": dict(kling_payload.get("video_quality_judge") or {}),
            "video_quality_judge_p1": dict(kling_payload.get("video_quality_judge_p1") or {}),
            "video_quality_learning_proposed": bool(kling_payload.get("video_quality_learning_proposed")),
            "video_quality_proposed_updates_path": str(kling_payload.get("video_quality_proposed_updates_path") or ""),
            "video_quality_learning_p1_proposed": bool(kling_payload.get("video_quality_learning_p1_proposed")),
            "video_quality_proposed_updates_p1_path": str(kling_payload.get("video_quality_proposed_updates_p1_path") or ""),
            "section_availability": {
                "video_quality_judge": "available"
                if dict(kling_payload.get("video_quality_judge") or {}).get("version")
                else "missing",
                "video_quality_judge_p1": "available"
                if dict(kling_payload.get("video_quality_judge_p1") or {}).get("version")
                else "missing",
            },
            "generation_report": kling_payload.get("generation_report") or {},
            "download_report": kling_payload.get("download_report") or {},
            "continuity_chain": kling_payload.get("continuity_chain") or {},
            "preflight": kling_payload.get("preflight") or {},
        }

    def _attach_youtube_oauth_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return payload
        try:
            from content_brain.upload.youtube_first_authorization import get_youtube_oauth_readiness

            readiness = get_youtube_oauth_readiness(self.project_root, self.get_channel_profile())
            merged = dict(payload)
            merged.update(readiness)
            return merged
        except Exception:
            return payload

    def get_results(self, *, run_id: str = "", run_dir: str = "") -> dict[str, Any]:
        profile = self.get_channel_profile()
        from content_brain.execution.kling_product_run import load_kling_product_run_results
        from content_brain.execution.pwmap_finalization import load_latest_product_studio_pwmap_results
        from content_brain.execution.pwmap_runway_agent_adapter import load_pwmap_agent_run_results

        run_id_text = str(run_id or "").strip()
        run_dir_text = str(run_dir or "").replace("\\", "/")

        if run_id_text.startswith("pwmap_") or "pwmap_agent_runs" in run_dir_text:
            pwmap_payload = load_pwmap_agent_run_results(
                self.project_root,
                run_id=run_id_text or run_dir_text.split("/")[-1],
            )
            if pwmap_payload:
                return self._attach_youtube_oauth_fields(self._merge_pwmap_results(pwmap_payload))

        if not run_id_text and not run_dir_text:
            latest_pwmap = load_latest_product_studio_pwmap_results(self.project_root)
            if latest_pwmap:
                return self._attach_youtube_oauth_fields(self._merge_pwmap_results(latest_pwmap))

        kling_hint = (
            run_id_text.startswith("kling_ms")
            or run_id_text.startswith("kling_ft")
            or "kling_multishot_live" in run_dir_text
            or "kling_frame_to_video" in run_dir_text
        )

        if kling_hint:
            kling_payload = load_kling_product_run_results(self.project_root, run_id=run_id_text or run_dir_text.split("/")[-1])
            if kling_payload:
                if run_dir_text and run_dir_text not in str(kling_payload.get("run_dir") or "").replace("\\", "/"):
                    pass
                else:
                    return self._attach_youtube_oauth_fields(self._merge_kling_results(kling_payload))

        runway_results = load_run_results(
            self.project_root,
            run_id=run_id,
            run_dir=run_dir,
            profile_upload_platforms=list(profile.get("upload_platforms") or []),
        )
        if runway_results.get("found"):
            return self._attach_youtube_oauth_fields(runway_results)

        kling_payload = load_kling_product_run_results(self.project_root, run_id=run_id_text)
        if kling_payload:
            return self._attach_youtube_oauth_fields(self._merge_kling_results(kling_payload))

        pwmap_payload = load_pwmap_agent_run_results(self.project_root, run_id=run_id_text)
        if pwmap_payload:
            return self._attach_youtube_oauth_fields(self._merge_pwmap_results(pwmap_payload))
        return self._attach_youtube_oauth_fields(runway_results)

    def _merge_pwmap_results(self, pwmap_payload: dict[str, Any]) -> dict[str, Any]:
        from content_brain.execution.pwmap_finalization import list_pwmap_product_studio_run_history
        from content_brain.platform.run_isolation import load_latest_run_attempt

        video_path = str(pwmap_payload.get("video_path") or "")
        metadata = dict(pwmap_payload.get("metadata") or {})
        multiclip_plan = dict(
            pwmap_payload.get("multiclip_execution_plan")
            or metadata.get("multiclip_execution_plan")
            or {}
        )
        runtime_status = dict(
            pwmap_payload.get("generation_runtime_status")
            or metadata.get("generation_runtime_status")
            or {}
        )
        finalization = dict(
            pwmap_payload.get("finalization")
            or metadata.get("finalization")
            or {}
        )
        execution_mode = str(
            pwmap_payload.get("execution_mode")
            or multiclip_plan.get("execution_mode")
            or metadata.get("execution_mode")
            or ""
        )
        generation_time = (
            pwmap_payload.get("generation_time_seconds")
            or metadata.get("generation_time_seconds")
        )
        final_duration = (
            pwmap_payload.get("final_video_duration_seconds")
            or metadata.get("final_video_duration_seconds")
        )
        clip_count = int(
            pwmap_payload.get("clip_count")
            or multiclip_plan.get("clip_count")
            or metadata.get("clip_count")
            or 0
        )
        expected_clip_count = int(
            pwmap_payload.get("expected_clip_count")
            or multiclip_plan.get("clip_count")
            or metadata.get("expected_clip_count")
            or clip_count
        )
        clips_completed = int(
            pwmap_payload.get("clips_completed")
            or metadata.get("clips_completed")
            or clip_count
        )
        selected_run_id = pwmap_payload.get("selected_run_id") or pwmap_payload.get("run_id") or ""
        latest_attempt = load_latest_run_attempt(self.project_root)
        pwmap_history = list_pwmap_product_studio_run_history(self.project_root, limit=20)
        is_product_pwmap = bool(pwmap_payload.get("is_product_studio_pwmap"))
        run_dir_text = str(pwmap_payload.get("run_dir") or pwmap_payload.get("run_folder") or "")
        publish_package_path = str(pwmap_payload.get("publish_package_path") or "")
        if not publish_package_path and run_dir_text:
            candidate = Path(run_dir_text) / "publish"
            if candidate.is_dir():
                publish_package_path = str(candidate.resolve()).replace("\\", "/")
        youtube_metadata = dict(pwmap_payload.get("youtube_metadata") or {})
        assembly_state: dict[str, Any] = {}
        publish_package_state: dict[str, Any] = {}
        if run_dir_text:
            try:
                from content_brain.execution.product_assembly_bridge import load_product_assembly_state

                assembly_state = load_product_assembly_state(run_dir_text)
                if assembly_state.get("publish_package_path"):
                    publish_package_path = str(assembly_state.get("publish_package_path") or publish_package_path)
            except Exception:
                assembly_state = {}
            try:
                from content_brain.execution.product_subtitle_branding_publish import load_product_publish_package_state

                publish_package_state = load_product_publish_package_state(run_dir_text)
                if publish_package_state.get("publish_package_path"):
                    publish_package_path = str(publish_package_state.get("publish_package_path") or publish_package_path)
            except Exception:
                publish_package_state = {}
        youtube_upload: dict[str, Any] = {}
        if publish_package_path:
            try:
                from content_brain.upload.youtube_upload_runtime import load_youtube_upload_result

                youtube_upload = load_youtube_upload_result(publish_package_path) or {}
            except Exception:
                youtube_upload = {}
        if not youtube_metadata and publish_package_path:
            try:
                from content_brain.publish.youtube_metadata_generator import load_youtube_metadata

                youtube_metadata = load_youtube_metadata(publish_package_path) or {}
            except Exception:
                youtube_metadata = {}
        from content_brain.execution.product_visual_diversity_guard import (
            load_visual_diversity_report,
            merge_results_visual_diversity_fields,
        )

        visual_report = dict(pwmap_payload.get("visual_diversity") or {})
        run_dir_for_diversity = str(pwmap_payload.get("run_dir") or "")
        if not visual_report and run_dir_for_diversity:
            visual_report = load_visual_diversity_report(run_dir_for_diversity) or {}

        pipeline_trace: dict[str, Any] = dict(pwmap_payload.get("pipeline_trace") or {})
        if not pipeline_trace and run_dir_text:
            try:
                from content_brain.execution.product_publish_pipeline_trace import load_pipeline_trace

                pipeline_trace = load_pipeline_trace(run_dir_text) or {}
            except Exception:
                pipeline_trace = {}

        from content_brain.platform.api_runtime_diagnostics import (
            compute_api_build_id,
            get_live_runtime_diagnostics,
            is_api_process_stale,
        )

        api_runtime = get_live_runtime_diagnostics(self.project_root)
        current_build_id = compute_api_build_id(self.project_root)
        api_process_stale = is_api_process_stale(
            self.project_root,
            live_build_id=str(api_runtime.get("api_build_id") or ""),
        )

        resolved_assembly_status = str(
            assembly_state.get("assembly_status") or pwmap_payload.get("assembly_status") or ""
        )
        publish_package_ready = bool(
            publish_package_state.get("publish_ready")
            or assembly_state.get("publish_package_ready")
            or pwmap_payload.get("publish_package_ready")
        )
        resolved_publish_status = (
            "PUBLISHED_PACKAGE_CREATED"
            if publish_package_ready
            else ("PWMAP_OUTPUT" if bool(video_path) else "")
        )

        from content_brain.automation.youtube_auto_upload_config import load_youtube_auto_upload_config

        youtube_auto_config = load_youtube_auto_upload_config(self.project_root)
        upload_trace_stage = dict((pipeline_trace.get("stages") or {}).get("youtube_upload_runtime") or {})
        auto_upload_enabled = bool(
            youtube_auto_config.get("auto_upload_enabled")
            or pwmap_payload.get("auto_upload_enabled")
            or youtube_upload.get("auto_upload_enabled")
        )
        auto_upload_started = bool(
            pwmap_payload.get("auto_upload_started")
            or youtube_upload.get("auto_upload_started")
            or upload_trace_stage.get("status") in {"completed", "failed", "blocked"}
        )
        youtube_upload_blocked_reason = str(
            pwmap_payload.get("youtube_upload_blocked_reason")
            or youtube_upload.get("blocked_reason")
            or upload_trace_stage.get("error")
            or (upload_trace_stage.get("reason") if upload_trace_stage.get("status") == "skipped" else "")
            or ""
        )

        merged_payload = {
            "found": True,
            "video_path": video_path,
            "publish_package_path": publish_package_path,
            "youtube_metadata": youtube_metadata,
            "youtube_title": str(youtube_metadata.get("title") or ""),
            "youtube_hashtags": list(youtube_metadata.get("hashtags") or []),
            "youtube_tags_count": len(list(youtube_metadata.get("tags") or [])),
            "youtube_category": str(youtube_metadata.get("category") or ""),
            "youtube_thumbnail_prompt": str(youtube_metadata.get("thumbnail_prompt") or ""),
            "assembly_status": resolved_assembly_status,
            "assembly_complete": bool(
                assembly_state.get("assembly_complete") or pwmap_payload.get("assembly_complete")
            ),
            "publish_package_ready": publish_package_ready,
            "final_publish_video_path": str(
                assembly_state.get("final_publish_video_path")
                or pwmap_payload.get("final_publish_video_path")
                or ""
            ),
            "source_clip_count": int(
                assembly_state.get("source_clip_count")
                or pwmap_payload.get("source_clip_count")
                or clip_count
            ),
            "missing_clip_index": assembly_state.get("missing_clip_index") or pwmap_payload.get("missing_clip_index"),
            "assembly_recovery_possible": bool(
                assembly_state.get("recovery_possible") or pwmap_payload.get("recovery_possible")
            ),
            "assembly_manifest": assembly_state.get("assembly_manifest") or pwmap_payload.get("assembly_manifest") or {},
            "publish_metadata": assembly_state.get("publish_metadata") or pwmap_payload.get("publish_metadata") or {},
            "publish_ready": bool(
                publish_package_state.get("publish_ready") or pwmap_payload.get("publish_ready")
            ),
            "final_branded_publish_video_path": str(
                publish_package_state.get("final_branded_publish_video_path")
                or pwmap_payload.get("final_branded_publish_video_path")
                or ""
            ),
            "subtitle_status": str(
                publish_package_state.get("subtitle_status") or pwmap_payload.get("subtitle_status") or ""
            ),
            "branding_status": {
                "status": str(
                    publish_package_state.get("branding_status") or pwmap_payload.get("branding_status") or ""
                ),
                "branding_enabled": bool(
                    publish_package_state.get("publish_ready") or pwmap_payload.get("publish_ready")
                ),
                "final_branded_video_path": str(
                    publish_package_state.get("final_branded_publish_video_path")
                    or pwmap_payload.get("final_branded_publish_video_path")
                    or ""
                ),
                "subtitled_video_path": "",
                "subtitles": str(
                    publish_package_state.get("subtitle_status") or pwmap_payload.get("subtitle_status") or "SKIP"
                ),
                "logo": str(publish_package_state.get("logo_status") or pwmap_payload.get("logo_status") or "SKIP"),
                "cta": str(publish_package_state.get("cta_status") or pwmap_payload.get("cta_status") or "SKIP"),
                "intro": str(publish_package_state.get("intro_status") or pwmap_payload.get("intro_status") or "SKIP"),
                "outro": str(publish_package_state.get("outro_status") or pwmap_payload.get("outro_status") or "SKIP"),
            },
            "branding_publish_status": str(
                publish_package_state.get("branding_status") or pwmap_payload.get("branding_status") or ""
            ),
            "audio_status": str(
                publish_package_state.get("audio_status") or pwmap_payload.get("audio_status") or ""
            ),
            "logo_status": str(publish_package_state.get("logo_status") or pwmap_payload.get("logo_status") or ""),
            "cta_status": str(publish_package_state.get("cta_status") or pwmap_payload.get("cta_status") or ""),
            "intro_status": str(publish_package_state.get("intro_status") or pwmap_payload.get("intro_status") or ""),
            "outro_status": str(publish_package_state.get("outro_status") or pwmap_payload.get("outro_status") or ""),
            "subtitle_count": int(
                publish_package_state.get("subtitle_count") or pwmap_payload.get("subtitle_count") or 0
            ),
            "subtitle_language": str(
                publish_package_state.get("subtitle_language") or pwmap_payload.get("subtitle_language") or ""
            ),
            "normalization_applied": bool(
                publish_package_state.get("normalization_applied") or pwmap_payload.get("normalization_applied")
            ),
            "lufs_value": publish_package_state.get("lufs_value") or pwmap_payload.get("lufs_value"),
            "branding_layers": list(
                publish_package_state.get("branding_layers") or pwmap_payload.get("branding_layers") or []
            ),
            "publish_package": publish_package_state.get("publish_package") or pwmap_payload.get("publish_package") or {},
            "youtube_upload": youtube_upload,
            "youtube_upload_status": str(youtube_upload.get("upload_status") or pwmap_payload.get("youtube_upload_status") or ""),
            "youtube_video_id": str(youtube_upload.get("youtube_video_id") or pwmap_payload.get("youtube_video_id") or ""),
            "youtube_url": str(youtube_upload.get("youtube_url") or pwmap_payload.get("youtube_url") or ""),
            "youtube_visibility": str(youtube_upload.get("visibility") or pwmap_payload.get("youtube_visibility") or ""),
            "youtube_publish_time": str(youtube_upload.get("publish_time") or pwmap_payload.get("youtube_publish_time") or ""),
            "youtube_upload_time": str(youtube_upload.get("upload_time") or pwmap_payload.get("youtube_upload_time") or ""),
            "auto_upload_enabled": auto_upload_enabled,
            "auto_upload_started": auto_upload_started,
            "youtube_upload_blocked_reason": youtube_upload_blocked_reason,
            "youtube_auto_upload_config": youtube_auto_config,
            "platform_targets": [],
            "metadata": metadata,
            "runway_completed": bool(video_path),
            "has_downloads_only": bool(video_path) and not publish_package_ready,
            "publish_status": resolved_publish_status,
            "post_processing_status": str(
                pipeline_trace.get("last_completed_stage")
                or pwmap_payload.get("last_completed_stage")
                or ""
            ),
            "post_processing_missing": bool(pipeline_trace.get("stop_stage")),
            "pipeline_trace": pipeline_trace,
            "stop_stage": str(
                pipeline_trace.get("stop_stage") or pwmap_payload.get("stop_stage") or ""
            ),
            "last_completed_stage": str(
                pipeline_trace.get("last_completed_stage")
                or pwmap_payload.get("last_completed_stage")
                or ""
            ),
            "orchestrator_version": str(
                pipeline_trace.get("orchestrator_version")
                or pwmap_payload.get("orchestrator_version")
                or api_runtime.get("orchestrator_version")
                or ""
            ),
            "api_runtime_diagnostics": {
                **api_runtime,
                "current_build_id": current_build_id,
                "api_process_stale": api_process_stale,
            },
            "api_build_id": str(api_runtime.get("api_build_id") or current_build_id),
            "api_process_stale": api_process_stale,
            "assembly_bridge_enabled": bool(api_runtime.get("assembly_bridge_enabled")),
            "branding_publish_enabled": bool(api_runtime.get("branding_publish_enabled")),
            "youtube_metadata_enabled": bool(api_runtime.get("youtube_metadata_enabled")),
            "downloaded_clip_count": clip_count,
            "selected_run_id": selected_run_id,
            "canonical_run_id": selected_run_id if is_product_pwmap else "",
            "is_canonical_latest": is_product_pwmap,
            "run_folder": pwmap_payload.get("run_folder") or "",
            "run_dir": pwmap_payload.get("run_dir") or "",
            "topic": pwmap_payload.get("topic") or "",
            "latest_approved_video_path": video_path,
            "final_branded_video_path": video_path,
            "output_ready": bool(pwmap_payload.get("output_ready")),
            "recovery_available": bool(pwmap_payload.get("recovery_available")),
            "generation_status": pwmap_payload.get("generation_status") or "",
            "status": pwmap_payload.get("generation_status") or metadata.get("status") or "",
            "expected_clip_count": expected_clip_count,
            "selected_duration_seconds": int(
                multiclip_plan.get("requested_duration_seconds")
                or multiclip_plan.get("duration_seconds")
                or metadata.get("requested_duration_seconds")
                or 0
            ),
            "clips_completed": clips_completed,
            "failure_stage": pwmap_payload.get("failure_stage") or metadata.get("failure_stage") or "",
            "failed_clip_index": pwmap_payload.get("failed_clip_index") or metadata.get("failed_clip_index"),
            "error": pwmap_payload.get("error") or metadata.get("error") or "",
            "provider_runtime": pwmap_payload.get("provider_runtime") or "pwmap_agent",
            "execution_mode": execution_mode,
            "clip_count": clip_count,
            "planned_duration_seconds": multiclip_plan.get("duration_seconds"),
            "generation_time_seconds": generation_time,
            "final_video_duration_seconds": final_duration,
            "generation_runtime_status": runtime_status,
            "multiclip_execution_plan": multiclip_plan,
            "finalization": finalization,
            "latest_run_attempt": latest_attempt,
            "latest_attempt_run_id": latest_attempt.get("run_id") or selected_run_id,
            "latest_attempt_status": latest_attempt.get("status") or pwmap_payload.get("generation_status") or "",
            "latest_attempt_topic": latest_attempt.get("topic") or pwmap_payload.get("topic") or "",
            "latest_attempt_clips_completed": latest_attempt.get("clips_completed") or clip_count,
            "run_history": pwmap_history,
            "pwmap_agent": {
                "provider_runtime": pwmap_payload.get("provider_runtime"),
                "clip_count": clip_count,
                "clips": pwmap_payload.get("clips") or [],
                "output_folder": pwmap_payload.get("output_folder"),
                "native_audio_status": pwmap_payload.get("native_audio_status"),
                "execution_mode": execution_mode,
                "generation_time_seconds": generation_time,
                "final_video_duration_seconds": final_duration,
                "generation_runtime_status": runtime_status,
                "finalization": finalization,
                "recovery_available": bool(pwmap_payload.get("recovery_available")),
            },
        }
        from content_brain.platform.run_truth_resolver import enrich_pwmap_results_truth

        merged_payload = merge_results_visual_diversity_fields(merged_payload, visual_report)
        return enrich_pwmap_results_truth(
            self.project_root,
            merged_payload,
            run_dir=run_dir_text,
            run_id=selected_run_id,
            visual_report=visual_report,
        )

    def latest_results(self, *, run_id: str = "", run_dir: str = "") -> dict[str, Any]:
        return self.get_results(run_id=run_id, run_dir=run_dir)

    def get_asset_library(self, *, limit: int = 20) -> dict[str, Any]:
        from content_brain.platform.asset_library import asset_library_root, ensure_asset_library_structure, list_latest_assets, load_asset_index

        ensure_asset_library_structure(self.project_root)
        profile = self.get_channel_profile()
        index = load_asset_index(self.project_root)
        assets = list_latest_assets(self.project_root, limit=max(1, int(limit)))
        library = asset_library_root(self.project_root)
        return {
            "library_path": str(library.resolve()),
            "vault_videos_path": str((library / "videos").resolve()),
            "asset_count": len(list(index.get("assets") or [])),
            "assets": assets,
            "vault_enabled": bool(profile.get("asset_vault_enabled", True)),
            "copy_mode": str(profile.get("asset_copy_mode") or "copy"),
        }

    def list_future_patches(self) -> list[str]:
        return list(FUTURE_PATCHES)

    def list_upgrade_patches(self) -> dict[str, Any]:
        return list_upgrade_center_patches(self.project_root)

    def _resolve_requested_clip_count(self, payload: dict[str, Any], preflight: dict[str, Any]) -> int:
        if payload.get("clip_count") not in (None, ""):
            return max(1, min(6, int(payload.get("clip_count"))))
        multiclip = preflight.get("multiclip_execution_plan") or {}
        if multiclip.get("clip_count") not in (None, ""):
            return max(1, min(6, int(multiclip.get("clip_count"))))
        return max(1, min(6, int((preflight.get("duration_plan") or {}).get("clip_count") or 1)))

    def _extract_e2e_prompt_metrics(self, e2e_result: dict[str, Any]) -> dict[str, Any]:
        topic = str((e2e_result.get("input") or {}).get("topic") or "")
        steps = e2e_result.get("steps") or []
        duration_step = next(
            (
                dict(step.get("payload") or {})
                for step in steps
                if isinstance(step, dict) and step.get("step_key") == "duration_planner"
            ),
            {},
        )
        cleanup = next(
            (
                dict(step.get("payload") or {})
                for step in steps
                if isinstance(step, dict) and step.get("step_key") == "prompt_cleanup"
            ),
            {},
        )
        if not cleanup:
            cleanup = next(
                (
                    dict(step.get("payload") or {})
                    for step in steps
                    if isinstance(step, dict) and step.get("step_key") == "prompt_generation"
                ),
                {},
            )
        requested = int((e2e_result.get("input") or {}).get("requested_clip_count") or 0)
        planned = int(duration_step.get("clip_count") or cleanup.get("clip_count") or 0)
        clip_prompts = cleanup.get("clip_prompts") or []
        prompt_list_length = len(clip_prompts) if isinstance(clip_prompts, list) else 0
        clip_count = requested or planned or prompt_list_length
        return {
            "topic": topic,
            "clip_count": clip_count,
            "planned_clip_count": planned,
            "prompt_list_length": prompt_list_length,
            "run_id": str(e2e_result.get("run_id") or ""),
        }

    def create_video_generate(self, payload: dict[str, Any], *, runway_service: Any) -> dict[str, Any]:
        topic_mode = str(payload.get("topic_mode") or payload.get("topic_source") or "custom")
        custom_topic = str(payload.get("custom_topic") or "").strip()
        if custom_topic:
            self.save_last_topic(topic=custom_topic, topic_mode=topic_mode)

        preflight = self.create_video_preflight(payload)
        provider = str(preflight.get("provider") or preflight["duration_plan"]["provider"]).lower()
        audio_strategy = str(preflight.get("audio_strategy") or "").lower()
        execution_mode = str(payload.get("execution_mode") or "FULL_AUTO").upper()
        clip_count = self._resolve_requested_clip_count(payload, preflight)
        provider_runtime = self._resolve_product_provider_runtime(payload)
        generate_payload = dict(payload)
        use_browser_automation = provider_runtime != "legacy_internal"

        if use_browser_automation and (
            provider == "runway"
            or is_kling_native_audio_route(provider=provider, audio_strategy=audio_strategy)
        ):
            from content_brain.automation.runway_session_manager import require_runway_session_for_generation
            from content_brain.execution.product_multiclip_orchestrator import run_product_multiclip_generate
            from content_brain.execution.pwmap_runway_agent_adapter import (
                LEGACY_INTERNAL_RUNTIME,
                PWMAP_AGENT_RUNTIME,
            )

            session_check = require_runway_session_for_generation(self.project_root, validate=True)
            if not session_check.get("ok"):
                return {
                    "ok": False,
                    "wired": True,
                    "status": "runway_session_required",
                    "message": str(session_check.get("message") or ""),
                    "runway_session": session_check,
                    "provider_runtime": PWMAP_AGENT_RUNTIME,
                    "execution_engine": "pwmap/runway_agent.py",
                    "subprocess_exit_code": int(session_check.get("exit_code") or 2),
                }

            generate_payload.setdefault("browser_automation", True)
            generate_payload.setdefault("skip_credit_guard", True)
            generate_payload.setdefault("provider_runtime", PWMAP_AGENT_RUNTIME)
            pwmap_result = run_product_multiclip_generate(
                project_root=self.project_root,
                payload=generate_payload,
                preflight=preflight,
            )
            pwmap_result["pipeline_execution_mode"] = execution_mode
            pwmap_result["requested_clip_count"] = clip_count
            pwmap_result["actual_clip_count"] = int(pwmap_result.get("clip_count") or clip_count)
            pwmap_result["provider_runtime"] = PWMAP_AGENT_RUNTIME
            pwmap_result["legacy_internal_runtime"] = LEGACY_INTERNAL_RUNTIME
            pwmap_result["execution_engine"] = "pwmap/runway_agent.py"
            return pwmap_result

        if is_kling_native_audio_route(provider=provider, audio_strategy=audio_strategy):
            generate_payload.setdefault("free_credit_first", True)
            generate_payload.setdefault("operator_paid_approval", False)
            generate_payload.setdefault("free_credit_mode", False)
            kling_payload = self._apply_product_studio_kling_defaults(payload)
            kling_result = run_kling_product_studio_generate(
                project_root=self.project_root,
                payload=kling_payload,
                preflight=preflight,
            )
            kling_result["execution_mode"] = execution_mode
            kling_result["requested_clip_count"] = clip_count
            kling_result["actual_clip_count"] = int(kling_result.get("kling_clip_count") or clip_count)
            kling_result["provider_runtime"] = provider_runtime or "legacy_internal"
            kling_result["legacy_internal_runtime"] = "legacy_internal"
            kling_result["legacy_note"] = (
                "Internal Kling runtime used (diagnostics/override). "
                "Default Product path is provider_runtime=pwmap_agent."
            )
            return kling_result

        topic_mode = str(payload.get("topic_mode") or payload.get("topic_source") or "channel")

        trace = TopicAuthorityTrace(
            authoritative_topic=str(preflight.get("authoritative_topic") or ""),
            requested_clip_count=clip_count,
            topic_mode=topic_mode,
        )
        trace.record(
            "ui_request",
            topic=str(payload.get("custom_topic") or preflight.get("authoritative_topic") or ""),
            clip_count=clip_count,
            source="create_video_payload",
            extra={
                "topic_mode": topic_mode,
                "duration_seconds": payload.get("duration_seconds"),
            },
        )

        if provider != "runway":
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": False,
                "status": "unsupported_provider",
                "message": "Provider execution not wired yet.",
                "provider": provider,
                "authoritative_topic": preflight.get("authoritative_topic") or "",
                "clip_count": clip_count,
                "duration_plan": preflight.get("duration_plan") or {},
                "topic_authority_trace": trace.to_dict(),
            }

        if provider_runtime != "legacy_internal":
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": True,
                "status": "legacy_internal_disabled",
                "message": (
                    "Legacy internal Runway API runtime is disabled. "
                    "Use browser automation (provider_runtime=pwmap_agent, default)."
                ),
                "provider": provider,
                "authoritative_topic": preflight.get("authoritative_topic") or "",
                "clip_count": clip_count,
                "duration_plan": preflight.get("duration_plan") or {},
                "topic_authority_trace": trace.to_dict(),
            }

        topic = str(preflight.get("authoritative_topic") or "").strip()
        trace.record("generate_endpoint", topic=topic, clip_count=clip_count, source="preflight")
        if not topic:
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": True,
                "status": "failed",
                "message": "Authoritative topic is required.",
                "topic_authority_trace": trace.to_dict(),
            }

        profile = self.get_channel_profile()
        if payload.get("clip_count") not in (None, ""):
            duration_seconds = clip_count * 10
        else:
            duration_seconds = int(
                payload.get("duration_seconds")
                or resolve_platform_duration_seconds(self.project_root, platform, profile=profile)
            )
        use_director = bool(payload.get("use_ai_director", True))
        use_critic = bool(payload.get("use_prompt_critic", True))
        requested_clip_count = clip_count if payload.get("clip_count") not in (None, "") else None

        clear_registered_e2e_result()
        try:
            e2e_result = run_content_brain_e2e_micro_test(
                topic=topic,
                duration_seconds=duration_seconds,
                platform=str(payload.get("platform") or profile.get("default_platform") or "youtube_shorts"),
                niche=str(profile.get("main_niche") or "general"),
                mood=str(profile.get("tone_style") or "cinematic"),
                clip_length_preference=10,
                requested_clip_count=requested_clip_count,
                project_root=self.project_root,
            )
        except Exception as exc:
            trace.record("content_brain_e2e", topic=topic, clip_count=clip_count, extra={"error": str(exc)})
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": True,
                "status": "failed",
                "message": f"Content Brain pipeline failed: {exc}",
                "authoritative_topic": topic,
                "clip_count": clip_count,
                "topic_authority_trace": trace.to_dict(),
            }

        e2e_metrics = self._extract_e2e_prompt_metrics(e2e_result)
        trace.record(
            "content_brain_e2e",
            topic=e2e_metrics["topic"],
            clip_count=e2e_metrics["clip_count"],
            source="prompt_cleanup",
            extra={"run_id": e2e_metrics["run_id"]},
        )

        if not trace.validate_topic("content_brain_e2e", e2e_metrics["topic"]):
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": True,
                "status": "failed",
                "message": "Topic authority mismatch after Content Brain pipeline.",
                "authoritative_topic": topic,
                "clip_count": clip_count,
                "topic_authority_trace": trace.to_dict(),
            }
        if e2e_metrics["clip_count"] and not trace.validate_clip_count("content_brain_e2e", e2e_metrics["clip_count"]):
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": True,
                "status": "failed",
                "message": (
                    f"Clip count mismatch after Content Brain pipeline "
                    f"({e2e_metrics['clip_count']} != {clip_count})."
                ),
                "authoritative_topic": topic,
                "clip_count": clip_count,
                "topic_authority_trace": trace.to_dict(),
            }

        isolated_run_id = str(e2e_metrics.get("run_id") or "").strip()
        run_context_payload: dict[str, Any] = {}
        if isolated_run_id:
            try:
                run_context = create_isolated_run_context(
                    self.project_root,
                    run_id=isolated_run_id,
                    topic=topic,
                    clip_count=clip_count,
                )
                run_context_payload = run_context.to_dict()
            except Exception as exc:
                trace.record(
                    "run_isolation",
                    topic=topic,
                    clip_count=clip_count,
                    extra={"error": str(exc)},
                )
                trace.write(self.project_root)
                return {
                    "ok": False,
                    "wired": True,
                    "status": "failed",
                    "message": f"Failed to create isolated run context: {exc}",
                    "authoritative_topic": topic,
                    "clip_count": clip_count,
                    "topic_authority_trace": trace.to_dict(),
                }

            ok_story, story_reason, story_path = require_story_package_for_run(
                self.project_root,
                isolated_run_id,
                topic=topic,
            )
            trace.record(
                "story_package",
                topic=topic,
                clip_count=clip_count,
                extra={"reason": story_reason, "path": story_path},
            )
            if not ok_story:
                trace.write(self.project_root)
                return {
                    "ok": False,
                    "wired": True,
                    "status": "failed",
                    "message": f"Story package required for run — {story_reason}.",
                    "authoritative_topic": topic,
                    "clip_count": clip_count,
                    "run_id": isolated_run_id,
                    "run_context": run_context_payload,
                    "topic_authority_trace": trace.to_dict(),
                }

        bundle, handoff = resolve_live_smoke_prompts(
            story_idea=topic,
            project_id="phase_i_live",
            clip_count=clip_count,
            e2e_result=e2e_result,
            project_root=self.project_root,
            strict_topic_authority=True,
            auto_director=use_director,
            auto_prompt_critic=use_critic,
        )
        trace.record(
            "prompt_builder",
            topic=bundle.story_idea,
            clip_count=bundle.clip_count,
            source=handoff.loaded_from,
            extra={
                "prompt_source": handoff.prompt_source,
                "content_brain_topic": handoff.content_brain_topic,
            },
        )

        if not trace.validate_topic("prompt_builder", bundle.story_idea):
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": True,
                "status": "failed",
                "message": "Topic authority mismatch in Prompt Builder handoff.",
                "authoritative_topic": topic,
                "clip_count": clip_count,
                "topic_authority_trace": trace.to_dict(),
            }
        if not trace.validate_clip_count("prompt_builder", bundle.clip_count):
            trace.write(self.project_root)
            return {
                "ok": False,
                "wired": True,
                "status": "failed",
                "message": f"Clip count mismatch in Prompt Builder ({bundle.clip_count} != {clip_count}).",
                "authoritative_topic": topic,
                "clip_count": clip_count,
                "topic_authority_trace": trace.to_dict(),
            }

        register_e2e_result(e2e_result)

        result = runway_service.start_run(
            story_idea=topic,
            project_id="phase_i_live",
            operator="product_ui",
            simulate=False,
            clip_count=clip_count,
            execution_mode=execution_mode,
            e2e_result=e2e_result,
            strict_topic_authority=True,
            auto_director=use_director,
            auto_prompt_critic=use_critic,
        )

        trace.record(
            "runway_runtime_start",
            topic=topic,
            clip_count=clip_count,
            source="runway_live_smoke_service.start_run",
        )
        trace_path = trace.write(self.project_root)

        snapshot = dict(result.get("snapshot") or {})
        run_id = str(snapshot.get("project_id") or result.get("project_id") or "phase_i_live")
        session_id = str(
            snapshot.get("content_brain_run_id")
            or (result.get("handoff_preview") or {}).get("content_brain_run_id")
            or run_id
        )

        if not result.get("ok"):
            return {
                "ok": False,
                "wired": True,
                "status": "failed",
                "message": str(result.get("message") or "Failed to start Phase I run"),
                "run_id": run_id,
                "session_id": session_id,
                "provider": provider,
                "execution_mode": execution_mode,
                "authoritative_topic": topic,
                "clip_count": clip_count,
                "duration_plan": preflight.get("duration_plan") or {},
                "topic_authority_trace": trace.to_dict(),
                "topic_authority_trace_path": str(trace_path.relative_to(self.project_root)).replace("\\", "/"),
            }

        return {
            "ok": True,
            "wired": True,
            "status": "starting",
            "run_id": run_id,
            "session_id": session_id,
            "run_context": run_context_payload,
            "project_id": run_id,
            "provider": provider,
            "execution_mode": execution_mode,
            "authoritative_topic": topic,
            "clip_count": clip_count,
            "requested_clip_count": clip_count,
            "actual_clip_count": bundle.clip_count,
            "duration_plan": preflight.get("duration_plan") or {},
            "pipeline_steps": preflight.get("pipeline_steps") or [],
            "snapshot": snapshot,
            "handoff_preview": result.get("handoff_preview"),
            "topic_authority_trace": trace.to_dict(),
            "topic_authority_trace_path": str(trace_path.relative_to(self.project_root)).replace("\\", "/"),
            "prompt_builder_topic": bundle.story_idea,
            "content_brain_run_id": e2e_metrics["run_id"],
        }


def get_product_studio_service(project_root: str | Path | None = None) -> ProductStudioService:
    if project_root is None:
        from ui.api.dependencies import get_project_root

        project_root = get_project_root()
    return ProductStudioService(project_root)
