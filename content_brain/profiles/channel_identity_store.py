"""
Persistent channel identity store for the Viral Content Brain.

User-defined channel profiles (name, niche, audience, tone, platform, etc.)
are saved here and later consumed by ProfileLoader / ContentBriefOrchestrator.

Phase 1: persistence + JSON-safe contracts only (no UI wiring yet).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json
import re
import uuid

from content_brain.profiles.profile_loader import ProfileLoader
from content_brain.schemas.content_brief import Platform


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
STORE_VERSION = "channel_identity_v1"
ACTIVE_POINTER_FILE = "active_channel.json"
CHANNELS_SUBDIR = "channels"

PLATFORM_ALIASES = {
    "tiktok": Platform.TIKTOK.value,
    "instagram reels": Platform.INSTAGRAM_REELS.value,
    "instagram_reels": Platform.INSTAGRAM_REELS.value,
    "youtube shorts": Platform.YOUTUBE_SHORTS.value,
    "youtube_shorts": Platform.YOUTUBE_SHORTS.value,
}


class ChannelIdentityError(Exception):
    """Raised when channel identity persistence or validation fails."""


@dataclass
class ChannelIdentity:
    """
    User-facing channel identity saved once and reused across Content Brain runs.

    `main_niche` is free-form (e.g. "football VAR controversy", "AI education").
    """

    channel_name: str
    main_niche: str
    sub_niche: str = ""
    audience: str = ""
    tone_story_style: str = "cinematic_professional"
    platform: str = Platform.TIKTOK.value
    language: str = "English"
    visual_style: str = ""
    default_duration_seconds: int = 30
    default_provider: str = "hailuo"
    channel_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.channel_id:
            self.channel_id = self.generate_channel_id(self.channel_name, self.main_niche)
        if not self.created_at:
            self.created_at = _now_timestamp()
        if not self.updated_at:
            self.updated_at = self.created_at

        self.platform = normalize_platform(self.platform)
        self.default_duration_seconds = int(self.default_duration_seconds)
        if self.default_duration_seconds <= 0:
            raise ChannelIdentityError("default_duration_seconds must be positive.")

    @staticmethod
    def generate_channel_id(channel_name: str, main_niche: str) -> str:
        base = ProfileLoader.normalize_niche(channel_name or main_niche or "channel")
        suffix = uuid.uuid4().hex[:8]
        slug = base[:48].strip("_") or "channel"
        return f"{slug}_{suffix}"

    @property
    def niche_slug(self) -> str:
        return ProfileLoader.normalize_niche(self.main_niche)

    @property
    def display_label(self) -> str:
        name = self.channel_name.strip() or self.main_niche.strip() or self.channel_id
        niche = self.main_niche.strip()
        if niche and niche.lower() not in name.lower():
            return f"{name} ({niche})"
        return name

    def validate(self) -> None:
        if not self.channel_name.strip():
            raise ChannelIdentityError("channel_name is required.")
        if not self.main_niche.strip():
            raise ChannelIdentityError("main_niche is required.")

    def touch(self) -> None:
        self.updated_at = _now_timestamp()

    def to_dict(self) -> dict[str, Any]:
        return {
            "store_version": STORE_VERSION,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "main_niche": self.main_niche,
            "sub_niche": self.sub_niche,
            "audience": self.audience,
            "tone_story_style": self.tone_story_style,
            "platform": self.platform,
            "language": self.language,
            "visual_style": self.visual_style,
            "default_duration_seconds": self.default_duration_seconds,
            "default_provider": self.default_provider,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChannelIdentity:
        if not isinstance(data, dict):
            raise ChannelIdentityError("ChannelIdentity.from_dict() expects a dict.")

        return cls(
            channel_id=str(data.get("channel_id", "")),
            channel_name=str(data.get("channel_name", "")),
            main_niche=str(data.get("main_niche", "")),
            sub_niche=str(data.get("sub_niche", "")),
            audience=str(data.get("audience", "")),
            tone_story_style=str(data.get("tone_story_style", "cinematic_professional")),
            platform=str(data.get("platform", Platform.TIKTOK.value)),
            language=str(data.get("language", "English")),
            visual_style=str(data.get("visual_style", "")),
            default_duration_seconds=int(data.get("default_duration_seconds", 30)),
            default_provider=str(data.get("default_provider", "hailuo")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_run_request_overrides(
        self,
        topic: str = "",
    ) -> dict[str, Any]:
        """
        Map this channel identity to ContentBriefRunRequest-compatible kwargs.

        Topic is passed separately so User Topic Authority stays explicit:
        empty topic => caller/orchestrator handles auto-topic inside niche.
        """
        return {
            "niche": self.main_niche.strip(),
            "topic": topic.strip(),
            "platform": self.platform,
            "user_duration_seconds": self.default_duration_seconds,
            "provider_name": self.default_provider.strip() or "hailuo",
            "channel_id": self.channel_id,
        }

    def to_profile_overlay(self) -> dict[str, Any]:
        """
        Build a Content Brain profile overlay from this channel identity.

        Intended for merge into ProfileLoader output in a later phase.
        """
        niche_label = self.main_niche.strip()
        sub_niche = self.sub_niche.strip()
        audience_primary = self.audience.strip() or (
            f"Viewers interested in {niche_label} short-form content"
        )
        tone_primary = self.tone_story_style.strip() or "retention-first, niche-native"
        visual_style = self.visual_style.strip() or (
            f"{niche_label.lower()}-appropriate short-form visual style"
        )

        overlay: dict[str, Any] = {
            "profile_type": "channel_identity",
            "niche": self.niche_slug,
            "niche_label": niche_label,
            "domain": "custom",
            "language": self.language.strip() or "English",
            "language_rules": {
                "output_language": self.language.strip() or "English",
                "caption_language": self.language.strip() or "English",
                "narration_language": self.language.strip() or "English",
                "title_language": self.language.strip() or "English",
            },
            "target_platforms": [self.platform],
            "audience": {
                "primary": audience_primary,
                "psychographic": "high-intent niche scrollers, savers, and commenters",
                "avoid": "generic audiences with no connection to the channel niche",
            },
            "tone_rules": {
                "primary_tone": tone_primary,
                "secondary_tone": "curiosity-led, emotionally intentional, non-generic",
                "voice_style": f"{tone_primary}, platform-native, concrete",
                "must_include": [
                    f"at least one detail specific to {niche_label.lower()}",
                    "one concrete hook anchor in the first 3 seconds",
                ],
            },
            "visual_dna": {
                "core_aesthetic": visual_style,
            },
            "production_defaults": {
                "default_provider": self.default_provider.strip() or "hailuo",
            },
            "metadata": {
                "profile_role": "channel_identity",
                "channel_id": self.channel_id,
                "channel_name": self.channel_name.strip(),
                "main_niche": self.main_niche.strip(),
                "sub_niche": sub_niche,
                "tone_story_style": self.tone_story_style.strip(),
                "resolved_from": "channel_identity_store",
            },
        }

        if sub_niche:
            overlay["metadata"]["topic_area"] = sub_niche
            overlay.setdefault("trend_discovery", {})
            overlay["trend_discovery"]["manual_seed_topics"] = [sub_niche]

        return overlay


class ChannelIdentityStore:
    """Load, save, list, and track the active channel identity."""

    def __init__(self, project_root: str | Path = "."):
        self.project_root = Path(project_root).resolve()
        self.store_dir = self.project_root / "storage" / "content_brain" / "channel_identities"
        self.channels_dir = self.store_dir / CHANNELS_SUBDIR
        self.active_path = self.store_dir / ACTIVE_POINTER_FILE
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.channels_dir.mkdir(parents=True, exist_ok=True)

    def save(self, channel: ChannelIdentity, set_active: bool = False) -> Path:
        channel.validate()
        channel.touch()

        path = self._channel_path(channel.channel_id)
        payload = channel.to_dict()
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if set_active:
            self.set_active(channel.channel_id)

        return path

    def load(self, channel_id: str) -> ChannelIdentity:
        cleaned = channel_id.strip()
        if not cleaned:
            raise ChannelIdentityError("channel_id is required.")

        path = self._channel_path(cleaned)
        if not path.exists():
            raise ChannelIdentityError(f"Channel identity not found: {cleaned}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ChannelIdentityError(f"Invalid channel identity JSON: {path}") from exc

        channel = ChannelIdentity.from_dict(data)
        if channel.channel_id != cleaned:
            channel.channel_id = cleaned
        return channel

    def delete(self, channel_id: str) -> bool:
        path = self._channel_path(channel_id.strip())
        if not path.exists():
            return False

        path.unlink()

        active = self.get_active_channel_id()
        if active == channel_id.strip():
            if self.active_path.exists():
                self.active_path.unlink()

        return True

    def list_channels(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []

        for path in sorted(self.channels_dir.glob("*.json")):
            try:
                channel = ChannelIdentity.from_dict(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except (json.JSONDecodeError, ChannelIdentityError, ValueError):
                continue

            summaries.append(
                {
                    "channel_id": channel.channel_id,
                    "channel_name": channel.channel_name,
                    "main_niche": channel.main_niche,
                    "sub_niche": channel.sub_niche,
                    "platform": channel.platform,
                    "language": channel.language,
                    "display_label": channel.display_label,
                    "updated_at": channel.updated_at,
                    "path": str(path),
                }
            )

        summaries.sort(
            key=lambda item: item.get("updated_at", ""),
            reverse=True,
        )
        return summaries

    def set_active(self, channel_id: str) -> None:
        cleaned = channel_id.strip()
        if not cleaned:
            raise ChannelIdentityError("channel_id is required to set active channel.")

        if not self._channel_path(cleaned).exists():
            raise ChannelIdentityError(
                f"Cannot set active channel; identity not found: {cleaned}"
            )

        payload = {
            "store_version": STORE_VERSION,
            "channel_id": cleaned,
            "updated_at": _now_timestamp(),
        }
        self.active_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_active_channel_id(self) -> Optional[str]:
        if not self.active_path.exists():
            return None

        try:
            data = json.loads(self.active_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        channel_id = str(data.get("channel_id", "")).strip()
        return channel_id or None

    def load_active(self) -> Optional[ChannelIdentity]:
        channel_id = self.get_active_channel_id()
        if not channel_id:
            return None

        try:
            return self.load(channel_id)
        except ChannelIdentityError:
            return None

    def _channel_path(self, channel_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", channel_id.strip())
        return self.channels_dir / f"{safe_id}.json"


def normalize_platform(platform: str) -> str:
    raw = str(platform or Platform.TIKTOK.value).strip()
    alias = PLATFORM_ALIASES.get(raw.lower())
    if alias:
        return alias

    normalized = raw.lower().replace(" ", "_")
    try:
        return Platform(normalized).value
    except ValueError:
        return Platform.TIKTOK.value


def _now_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


__all__ = [
    "ACTIVE_POINTER_FILE",
    "STORE_VERSION",
    "ChannelIdentity",
    "ChannelIdentityError",
    "ChannelIdentityStore",
    "normalize_platform",
]


if __name__ == "__main__":
    import tempfile

    examples = [
        ChannelIdentity(
            channel_name="VAR Decisions Daily",
            main_niche="football VAR controversy",
            sub_niche="Premier League replay decisions",
            audience="Football fans who debate referee calls and replay angles",
            tone_story_style="documentary_style",
            platform="TikTok",
            language="English",
            visual_style="broadcast replay frames, stadium close-ups, mobile-first contrast",
        ),
        ChannelIdentity(
            channel_name="Scent Signal",
            main_niche="perfume niche reviews",
            sub_niche="airport duty-free scent testing",
            audience="Fragrance enthusiasts comparing dupes and skin chemistry",
            tone_story_style="luxury_brand",
            platform="Instagram Reels",
            language="English",
            visual_style="clean product close-ups, skin swatches, soft neutral backgrounds",
        ),
        ChannelIdentity(
            channel_name="Study Sprint",
            main_niche="AI education",
            sub_niche="exam cram frameworks",
            audience="Students looking for fast, practical study systems",
            tone_story_style="educational_clean",
            platform="YouTube Shorts",
            language="English",
            visual_style="whiteboard overlays, desk setup, readable text on mobile",
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        store = ChannelIdentityStore(project_root=tmp_dir)

        print("CHANNEL IDENTITY STORE SMOKE TEST")
        print("=" * 72)

        last_id = ""
        for index, channel in enumerate(examples, start=1):
            path = store.save(channel, set_active=(index == len(examples)))
            last_id = channel.channel_id
            roundtrip = ChannelIdentity.from_dict(channel.to_dict())
            overrides = channel.to_run_request_overrides(topic="")
            overlay = channel.to_profile_overlay()

            print(f"\n[{index}] {channel.display_label}")
            print("  ID:", channel.channel_id)
            print("  PATH:", path)
            print("  RUN OVERRIDES:", json.dumps(overrides, ensure_ascii=False))
            print("  PROFILE NICHE:", overlay.get("niche"))
            print("  PROFILE LABEL:", overlay.get("niche_label"))
            print("  ROUNDTRIP OK:", roundtrip.channel_name == channel.channel_name)

        active = store.load_active()
        listed = store.list_channels()
        print("\n" + "=" * 72)
        print("ACTIVE:", active.channel_id if active else "none")
        print("LIST COUNT:", len(listed))
        print("ACTIVE MATCH:", active.channel_id == last_id if active else False)

        reloaded = store.load(last_id)
        print("RELOAD OK:", reloaded.main_niche == examples[-1].main_niche)
