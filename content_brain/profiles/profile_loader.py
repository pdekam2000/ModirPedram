"""
Profile loader for the Viral Content Brain multi-niche system.

Loads base and specialized profiles, resolves inheritance chains,
and supports future auto-generated profiles from user-defined niches.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import json
import re
import uuid

from content_brain.schemas.content_brief import ContentDomain

try:
    from content_brain.engines.semantic_universe_engine import SemanticUniverseEngine
    from content_brain.schemas.semantic_universe import SemanticUniverseRequest

    SEMANTIC_UNIVERSE_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive fallback
    SemanticUniverseEngine = None  # type: ignore[assignment,misc]
    SemanticUniverseRequest = None  # type: ignore[assignment,misc]
    SEMANTIC_UNIVERSE_AVAILABLE = False

if TYPE_CHECKING:
    from content_brain.profiles.channel_identity_store import ChannelIdentity


DEFAULT_PROFILE_NAME = "default_profile.json"
LEGACY_DARK_MYSTERY_POINTER = "dark_mystery_profile.json"
SEMANTIC_UNIVERSE_SEED_SOURCE = "semantic_universe_engine_v1"


class ProfileLoadError(Exception):
    pass


class ProfileLoader:
    """
    Loads and merges Content Brain profiles.

    Resolution order for resolve():
      1. explicit profile_name
      2. niche_registry match
      3. saved generated profile for niche slug
      4. auto-generated overlay on default
    """

    def __init__(self, project_root: str | Path = "."):
        self.project_root = Path(project_root).resolve()
        self.profiles_dir = self.project_root / "config" / "content_brain" / "profiles"
        self.legacy_profiles_dir = self.project_root / "config" / "content_brain"
        self.generated_dir = self.project_root / "storage" / "content_brain" / "generated_profiles"
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self._semantic_universe_engine = (
            SemanticUniverseEngine() if SEMANTIC_UNIVERSE_AVAILABLE else None
        )

    def load_profile(self, profile_name: str = DEFAULT_PROFILE_NAME) -> dict[str, Any]:
        raw = self._load_raw_profile(profile_name)
        return self._resolve_inheritance(raw, seen=set())

    def resolve(
        self,
        niche: Optional[str] = None,
        profile_name: Optional[str] = None,
        allow_generated: bool = True,
        save_generated: bool = False,
        attach_semantic_universe: bool = True,
    ) -> dict[str, Any]:
        if profile_name:
            profile = self.load_profile(profile_name)
            return self._resolve_result(
                profile,
                niche=niche,
                niche_input=niche,
                attach_semantic_universe=attach_semantic_universe,
            )

        normalized_niche = self.normalize_niche(niche) if niche else "general"

        if normalized_niche != "general":
            pack_name = self.lookup_niche_pack(normalized_niche)
            if pack_name:
                profile = self.load_profile(pack_name)
                return self._resolve_result(
                    profile,
                    niche=normalized_niche,
                    niche_input=niche,
                    attach_semantic_universe=attach_semantic_universe,
                )

            if allow_generated:
                generated_path = self._generated_profile_path(normalized_niche)
                if generated_path.exists():
                    profile = self._resolve_inheritance(
                        self._load_raw_profile(str(generated_path)),
                        seen=set(),
                    )
                    return self._resolve_result(
                        profile,
                        niche=normalized_niche,
                        niche_input=niche,
                        attach_semantic_universe=attach_semantic_universe,
                    )

                profile = self.build_profile_from_niche(normalized_niche)
                if save_generated:
                    self.save_generated_profile(profile, normalized_niche)
                return self._resolve_result(
                    profile,
                    niche=normalized_niche,
                    niche_input=niche,
                    attach_semantic_universe=attach_semantic_universe,
                )

        profile = self.load_profile(DEFAULT_PROFILE_NAME)
        return self._resolve_result(
            profile,
            niche=normalized_niche,
            niche_input=niche,
            attach_semantic_universe=attach_semantic_universe,
        )

    def resolve_from_channel_identity(
        self,
        channel_identity: ChannelIdentity | Any,
        allow_generated: bool = True,
    ) -> dict[str, Any]:
        """
        Resolve a Content Brain profile from a saved channel identity.

        Uses main_niche with existing resolve() logic, then merges the channel
        overlay (audience, tone, language, visual style, platform defaults).
        """
        try:
            from content_brain.profiles.channel_identity_store import ChannelIdentity
        except ImportError as exc:  # pragma: no cover - defensive fallback
            raise ProfileLoadError(
                "Channel identity support requires content_brain.profiles.channel_identity_store."
            ) from exc

        if not isinstance(channel_identity, ChannelIdentity):
            raise ProfileLoadError(
                "resolve_from_channel_identity() expects a ChannelIdentity instance."
            )

        try:
            channel_identity.validate()
        except Exception as exc:
            raise ProfileLoadError(f"Invalid channel identity: {exc}") from exc

        main_niche = channel_identity.main_niche.strip()
        if not main_niche:
            raise ProfileLoadError("ChannelIdentity.main_niche is required.")

        base_profile = self.resolve(
            niche=main_niche,
            allow_generated=allow_generated,
            save_generated=False,
            attach_semantic_universe=False,
        )
        overlay = channel_identity.to_profile_overlay()
        merged = deep_merge(base_profile, overlay)
        merged = self._finalize_profile(merged, niche=main_niche)

        merged["niche_label"] = main_niche
        merged.setdefault("metadata", {})
        merged["metadata"]["channel_id"] = channel_identity.channel_id
        merged["metadata"]["channel_name"] = channel_identity.channel_name.strip()
        merged["metadata"]["channel_identity_applied"] = True
        merged["metadata"]["resolved_domain"] = self.resolve_content_domain(merged).value

        return self._attach_semantic_universe(
            merged,
            universe_request=self._semantic_universe_request_from_channel(channel_identity),
        )

    def lookup_niche_pack(self, niche: str) -> Optional[str]:
        base = self.load_profile(DEFAULT_PROFILE_NAME)
        registry = base.get("niche_registry", {})
        slug = self.normalize_niche(niche)
        pack = registry.get(slug)
        if pack:
            return pack

        for key, value in registry.items():
            if self.normalize_niche(key) == slug:
                return value

        return None

    def build_profile_from_niche(self, niche: str) -> dict[str, Any]:
        slug = self.normalize_niche(niche)
        label = niche.strip() or slug.replace("_", " ").title()

        overlay = {
            "profile_id": f"generated_{slug}_{uuid.uuid4().hex[:8]}",
            "profile_version": "1.0.0",
            "profile_type": "generated",
            "extends": DEFAULT_PROFILE_NAME,
            "niche": slug,
            "niche_label": label,
            "domain": "custom",
            "audience": {
                "primary": f"Viewers interested in {label} short-form content",
                "psychographic": "high-intent niche scrollers, savers, and commenters",
                "avoid": "generic audiences with no connection to the niche",
            },
            "tone_rules": {
                "primary_tone": f"{label.lower()}-native, specific, retention-first",
                "must_include": [
                    f"at least one detail that only makes sense in {label.lower()} content",
                    "one concrete hook anchor in the first 3 seconds",
                ],
            },
            "visual_dna": {
                "core_aesthetic": f"{label.lower()}-appropriate short-form visual style",
            },
            "example_seed_topics": [],
            "metadata": {
                "profile_role": "generated",
                "source_niche_input": niche,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "generator": "ProfileLoader.build_profile_from_niche",
            },
        }

        base = self.load_profile(DEFAULT_PROFILE_NAME)
        return deep_merge(base, overlay)

    def save_generated_profile(self, profile: dict[str, Any], niche: str) -> Path:
        slug = self.normalize_niche(niche)
        path = self._generated_profile_path(slug)

        payload = deepcopy(profile)
        payload.pop("extends", None)
        payload["profile_type"] = "generated_saved"
        payload.setdefault("metadata", {})
        payload["metadata"]["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload["metadata"]["saved_path"] = str(path)

        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def resolve_content_domain(self, profile: dict[str, Any]) -> ContentDomain:
        domain_value = profile.get("domain", "general")
        mapping = {
            "general": ContentDomain.GENERAL,
            "custom": ContentDomain.CUSTOM,
            "dark_mystery": ContentDomain.DARK_MYSTERY,
            "psychological": ContentDomain.PSYCHOLOGICAL,
            "disturbing_cinematic": ContentDomain.DISTURBING_CINEMATIC,
        }

        if domain_value in mapping:
            return mapping[domain_value]

        try:
            return ContentDomain(domain_value)
        except ValueError:
            return ContentDomain.CUSTOM

    @staticmethod
    def normalize_niche(niche: str) -> str:
        cleaned = niche.strip().lower()
        cleaned = re.sub(r"[^a-z0-9\s\-_]", "", cleaned)
        cleaned = re.sub(r"[\s\-]+", "_", cleaned)
        return cleaned or "general"

    def _finalize_profile(
        self,
        profile: dict[str, Any],
        niche: Optional[str] = None,
    ) -> dict[str, Any]:
        finalized = deepcopy(profile)
        finalized.pop("extends", None)

        if niche:
            finalized["niche"] = self.normalize_niche(niche)
            if not finalized.get("niche_label"):
                finalized["niche_label"] = niche.strip()

        finalized.setdefault("metadata", {})
        finalized["metadata"]["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        finalized["metadata"]["resolved_domain"] = self.resolve_content_domain(finalized).value
        return finalized

    def _resolve_result(
        self,
        profile: dict[str, Any],
        niche: Optional[str] = None,
        niche_input: Optional[str] = None,
        attach_semantic_universe: bool = True,
    ) -> dict[str, Any]:
        finalized = self._finalize_profile(profile, niche=niche)
        if not attach_semantic_universe:
            return finalized
        return self._attach_semantic_universe(finalized, niche_input=niche_input)

    def _attach_semantic_universe(
        self,
        profile: dict[str, Any],
        universe_request: Any | None = None,
        niche_input: Optional[str] = None,
    ) -> dict[str, Any]:
        if self._semantic_universe_engine is None or SemanticUniverseRequest is None:
            return profile

        enriched = deepcopy(profile)
        request = universe_request or self._semantic_universe_request_from_profile(
            enriched,
            niche_input=niche_input,
        )

        try:
            universe = self._semantic_universe_engine.build(request)
        except Exception:
            return profile

        enriched["semantic_universe"] = universe.to_dict()
        trend_discovery = dict(enriched.get("trend_discovery", {}))
        trend_discovery["manual_seed_topics"] = list(universe.topic_seed_pool)
        trend_discovery["semantic_universe_id"] = universe.universe_id
        trend_discovery["seed_source"] = SEMANTIC_UNIVERSE_SEED_SOURCE
        enriched["trend_discovery"] = trend_discovery
        return enriched

    def _semantic_universe_request_from_profile(
        self,
        profile: dict[str, Any],
        niche_input: Optional[str] = None,
    ) -> Any:
        if SemanticUniverseRequest is None:
            raise ProfileLoadError("SemanticUniverseRequest is unavailable.")

        metadata = profile.get("metadata", {})
        trend_discovery = profile.get("trend_discovery", {})
        audience_block = profile.get("audience", {})
        tone_rules = profile.get("tone_rules", {})
        visual_dna = profile.get("visual_dna", {})

        main_niche = (
            str(niche_input or "").strip()
            or str(profile.get("niche_label", "")).strip()
            or str(profile.get("niche", "general")).replace("_", " ").strip()
            or "general"
        )
        sub_niche = str(
            metadata.get("sub_niche")
            or metadata.get("topic_area")
            or trend_discovery.get("sub_niche")
            or ""
        ).strip()

        return SemanticUniverseRequest(
            main_niche=main_niche,
            sub_niche=sub_niche,
            audience=str(audience_block.get("primary", "")).strip(),
            tone=str(
                metadata.get("tone_story_style")
                or tone_rules.get("primary_tone", "")
            ).strip(),
            visual_style=str(visual_dna.get("core_aesthetic", "")).strip(),
        )

    def _semantic_universe_request_from_channel(self, channel_identity: Any) -> Any:
        if SemanticUniverseRequest is None:
            raise ProfileLoadError("SemanticUniverseRequest is unavailable.")

        return SemanticUniverseRequest(
            main_niche=channel_identity.main_niche.strip(),
            sub_niche=channel_identity.sub_niche.strip(),
            audience=channel_identity.audience.strip(),
            tone=channel_identity.tone_story_style.strip(),
            visual_style=channel_identity.visual_style.strip(),
        )

    def _resolve_inheritance(
        self,
        profile: dict[str, Any],
        seen: set[str],
    ) -> dict[str, Any]:
        extends = profile.get("extends")
        if not extends:
            return deepcopy(profile)

        parent_name = self._normalize_profile_ref(extends)
        if parent_name in seen:
            raise ProfileLoadError(f"Circular profile inheritance detected: {parent_name}")

        seen.add(parent_name)
        parent = self._load_raw_profile(parent_name)
        merged_parent = self._resolve_inheritance(parent, seen)

        child = deepcopy(profile)
        child.pop("extends", None)
        return deep_merge(merged_parent, child)

    def _load_raw_profile(self, profile_name: str) -> dict[str, Any]:
        path = self._resolve_profile_path(profile_name)
        if not path.exists():
            raise ProfileLoadError(f"Profile not found: {profile_name} ({path})")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProfileLoadError(f"Invalid JSON profile: {path}") from exc

        if not isinstance(data, dict):
            raise ProfileLoadError(f"Profile root must be an object: {path}")

        if data.get("metadata", {}).get("deprecated_path") and "extends" in data:
            return self._load_raw_profile(data["extends"])

        return data

    def _resolve_profile_path(self, profile_name: str) -> Path:
        candidate = Path(profile_name)
        if candidate.is_absolute() and candidate.exists():
            return candidate

        if candidate.exists():
            return candidate.resolve()

        profiles_path = self.profiles_dir / profile_name
        if profiles_path.exists():
            return profiles_path

        legacy_path = self.legacy_profiles_dir / profile_name
        if legacy_path.exists():
            return legacy_path

        generated_path = self.generated_dir / profile_name
        if generated_path.exists():
            return generated_path

        if not profile_name.endswith(".json"):
            return self._resolve_profile_path(f"{profile_name}.json")

        return profiles_path

    def _generated_profile_path(self, niche_slug: str) -> Path:
        return self.generated_dir / f"{niche_slug}.json"

    @staticmethod
    def _normalize_profile_ref(profile_ref: str) -> str:
        ref = profile_ref.replace("\\", "/")
        if ref.startswith("profiles/"):
            ref = ref[len("profiles/"):]
        return ref


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge override into base.

    Rules:
    - dict + dict  -> recursive merge
    - list + list  -> override replaces base
    - scalar/other -> override replaces base
    """
    merged = deepcopy(base)

    for key, override_value in override.items():
        base_value = merged.get(key)

        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = deep_merge(base_value, override_value)
        else:
            merged[key] = deepcopy(override_value)

    return merged


__all__ = [
    "DEFAULT_PROFILE_NAME",
    "ProfileLoadError",
    "ProfileLoader",
    "deep_merge",
]


if __name__ == "__main__":
    import json

    from content_brain.profiles.channel_identity_store import ChannelIdentity

    loader = ProfileLoader()

    default = loader.load_profile()
    horror = loader.load_profile("dark_mystery_profile.json")
    football = loader.resolve(niche="football")
    mapped = loader.resolve(niche="horror")

    print("Default niche:", default.get("niche"))
    print("Dark mystery niche:", horror.get("niche"))
    print("Football domain:", loader.resolve_content_domain(football).value)
    print("Horror resolved niche:", mapped.get("niche"))
    print("Horror lore enabled:", mapped.get("lore_continuity_rules", {}).get("enabled"))

    print("\n" + "=" * 72)
    print("CHANNEL IDENTITY RESOLVE SMOKE TEST")

    channel_cases = [
        ChannelIdentity(
            channel_name="VAR Decisions Daily",
            main_niche="football VAR controversy",
            audience="Football fans who debate referee calls",
            tone_story_style="documentary_style",
            platform="TikTok",
            language="English",
            visual_style="broadcast replay frames, stadium close-ups",
        ),
        ChannelIdentity(
            channel_name="Scent Signal",
            main_niche="perfume niche reviews",
            sub_niche="airport duty-free scent testing",
            platform="Instagram Reels",
        ),
        ChannelIdentity(
            channel_name="Study Sprint",
            main_niche="AI education",
            tone_story_style="educational_clean",
            platform="YouTube Shorts",
        ),
    ]

    for channel in channel_cases:
        profile = loader.resolve_from_channel_identity(channel)
        metadata = profile.get("metadata", {})
        semantic_universe = profile.get("semantic_universe", {})
        trend_discovery = profile.get("trend_discovery", {})
        print(f"\n{channel.channel_name}")
        print("  niche:", profile.get("niche"))
        print("  niche_label:", profile.get("niche_label"))
        print("  platform:", profile.get("target_platforms"))
        print("  audience:", profile.get("audience", {}).get("primary", "")[:60])
        print("  tone:", profile.get("tone_rules", {}).get("primary_tone", "")[:60])
        print("  visual:", profile.get("visual_dna", {}).get("core_aesthetic", "")[:60])
        print("  channel_identity_applied:", metadata.get("channel_identity_applied"))
        print("  channel_id:", metadata.get("channel_id"))
        print("  semantic_universe_id:", semantic_universe.get("universe_id", "none"))
        print("  semantic_domain:", semantic_universe.get("domain", "none"))
        print("  seed_source:", trend_discovery.get("seed_source", "none"))
        print("  seed_count:", len(trend_discovery.get("manual_seed_topics", [])))
        sample_seeds = trend_discovery.get("manual_seed_topics", [])[:3]
        print("  sample_seeds:", sample_seeds)
        print("  JSON OK:", json.dumps(profile)[:120] + "...")

    print("\n" + "=" * 72)
    print("SEMANTIC UNIVERSE RESOLVE SMOKE TEST")
    football_profile = loader.resolve(niche="football VAR controversy")
    football_universe = football_profile.get("semantic_universe", {})
    football_seeds = football_profile.get("trend_discovery", {}).get("manual_seed_topics", [])
    print("FOOTBALL NICHE:", football_profile.get("niche_label"))
    print("UNIVERSE DOMAIN:", football_universe.get("domain"))
    print("SEED COUNT:", len(football_seeds))
    print("SAMPLE SEEDS:", football_seeds[:4])
    print("SEMANTIC UNIVERSE ATTACHED:", bool(football_universe))
