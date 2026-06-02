"""
Phase 11A — provider capability registry validation.
"""

from __future__ import annotations

import json
from pathlib import Path

from content_brain.execution.provider_mode_catalog import ProviderModeCatalog
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.providers.provider_capability_registry import (
    ALL_CAPABILITIES,
    CAPABILITY_MUSIC_GENERATION,
    CAPABILITY_NARRATION,
    CAPABILITY_TEXT_TO_VIDEO,
    ProviderCapabilityRegistry,
    normalize_provider_id,
)
from core.provider_registry_engine import ProviderRegistryEngine
from core.video_provider_router import VideoProviderRouter


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    registry = ProviderCapabilityRegistry.load(root)
    results: list[dict] = []

    runway = registry.get_provider("runway")
    results.append(_pass("get_provider_runway", runway is not None and runway.provider_name == "Runway API"))
    results.append(
        _pass(
            "get_provider_alias_runway_api",
            registry.get_provider("runway_api") is not None,
        )
    )
    results.append(
        _pass(
            "get_provider_alias_hailuo",
            registry.get_provider("hailuo") is not None
            and registry.get_provider("hailuo").provider_id == "hailuo_browser",
        )
    )
    results.append(_pass("get_provider_unknown", registry.get_provider("not_a_provider") is None))

    runway_caps = registry.list_capabilities("runway")
    results.append(
        _pass(
            "list_capabilities_runway",
            CAPABILITY_TEXT_TO_VIDEO in runway_caps and CAPABILITY_NARRATION not in runway_caps,
            ",".join(runway_caps),
        )
    )
    results.append(_pass("list_capabilities_unknown", registry.list_capabilities("missing") == []))

    video_providers = registry.providers_for_capability(CAPABILITY_TEXT_TO_VIDEO)
    results.append(
        _pass(
            "providers_for_capability_text_to_video",
            "runway" in video_providers and "hailuo_browser" in video_providers,
            ",".join(video_providers),
        )
    )
    music_providers = registry.providers_for_capability(CAPABILITY_MUSIC_GENERATION)
    results.append(_pass("providers_for_capability_music", "suno" in music_providers))

    results.append(_pass("supports_runway_t2v", registry.supports("runway", CAPABILITY_TEXT_TO_VIDEO)))
    results.append(
        _pass(
            "supports_elevenlabs_not_t2v",
            registry.supports("elevenlabs", CAPABILITY_TEXT_TO_VIDEO) is False
            and registry.supports("elevenlabs", CAPABILITY_NARRATION) is True,
        )
    )
    results.append(
        _pass(
            "supports_unknown_capability",
            registry.supports("runway", "fly_to_moon") is False,
        )
    )
    results.append(
        _pass(
            "providers_for_unknown_capability",
            registry.providers_for_capability("fly_to_moon") == [],
        )
    )

    coverage = registry.capability_coverage()
    results.append(_pass("registry_has_all_capability_keys", set(coverage.keys()) == set(ALL_CAPABILITIES)))
    results.append(
        _pass(
            "registry_completeness_video_voice_music",
            len(video_providers) >= 3
            and len(registry.providers_for_capability(CAPABILITY_NARRATION)) >= 1
            and len(music_providers) >= 1,
        )
    )
    subtitle_providers = registry.providers_for_capability("subtitle_generation")
    results.append(
        _pass(
            "subtitle_generation_explicitly_empty_ok",
            isinstance(subtitle_providers, list),
            f"count={len(subtitle_providers)}",
        )
    )

    invalid_records: list[str] = []
    for record in registry.list_providers():
        invalid = [cap for cap in record.capabilities if cap not in ALL_CAPABILITIES]
        if invalid:
            invalid_records.append(f"{record.provider_id}:{invalid}")
    results.append(
        _pass(
            "all_records_valid_capabilities",
            not invalid_records,
            "; ".join(invalid_records),
        )
    )

    legacy = registry.legacy_registry_coverage(root)
    results.append(
        _pass(
            "legacy_registry_video_mapped",
            not legacy.get("legacy_missing"),
            json.dumps(legacy.get("legacy_missing") or []),
        )
    )
    results.append(
        _pass(
            "mode_catalog_families_mapped",
            len(legacy.get("mode_catalog_families_mapped") or []) >= 2,
            json.dumps(legacy.get("mode_catalog_families_mapped") or []),
        )
    )

    mode_catalog = ProviderModeCatalog.load(root)
    results.append(_pass("mode_catalog_still_loads", len(mode_catalog.families()) >= 3))

    pre_engine = ProviderRegistryEngine()
    results.append(_pass("legacy_registry_engine_loads", bool(pre_engine.load_registry())))

    results.append(_pass("runtime_engine_importable", ProviderRuntimeEngine is not None))
    results.append(_pass("video_router_importable", VideoProviderRouter is not None))

    serialized = registry.to_dict()
    results.append(
        _pass(
            "serialization_roundtrip",
            serialized.get("registry_version") == "11a_v1"
            and len(serialized.get("providers") or []) >= 10,
        )
    )

    normalize_check = normalize_provider_id("RUNWAY_API")
    results.append(_pass("normalize_provider_id", normalize_check == "runway"))

    passed = sum(1 for item in results if item["pass"])
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_pass": passed == len(results),
        },
    }


if __name__ == "__main__":
    report = run_matrix(".")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
