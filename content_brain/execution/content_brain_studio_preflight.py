"""
Pre-flight checks for Content Brain Test Studio.

Reports which trend/story providers are ready without exposing credentials.
"""

from __future__ import annotations

from typing import Any

LIVE_TREND_PROVIDERS = ("dataforseo", "serpapi", "dataforseo_youtube")
MOCK_ONLY_SOURCES = frozenset({"manual_seed", "mock_trend_provider", "simulated_local"})


def run_content_brain_studio_preflight() -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {
        "dataforseo": _provider_check("dataforseo", credential_keys=("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")),
        "serpapi": _provider_check("serpapi", credential_keys=("SERPAPI_API_KEY",)),
        "openai_story": _openai_story_check(),
        "openai_classification": _openai_classification_check(),
        "openai_quality": _openai_quality_check(),
        "openai_intent": _openai_intent_check(),
        "seo_provider_bridge": _seo_provider_bridge_check(),
        "mock_trend_fallback": {
            "ready": True,
            "mode": "local",
            "label": "Mock / related-topic fallback",
            "notes": "Always available when live trend APIs are not configured.",
        },
    }

    live_ready = [name for name in LIVE_TREND_PROVIDERS if checks.get(name, {}).get("ready")]
    try:
        from core.provider_registry_engine import ProviderRegistryEngine

        engine = ProviderRegistryEngine()
        credential_ready = engine.get_credential_ready_trend_sources()
        for name in credential_ready:
            if name not in live_ready:
                live_ready.append(name)
            check = checks.get(name)
            if check and check.get("ready") and not check.get("active"):
                check["notes"] = (
                    str(check.get("notes") or "")
                    + " Credentials ready; auto-enabled for SEO/trend bridge."
                ).strip()
    except Exception:
        credential_ready = []
    trend_mode = "live" if live_ready else "mock_fallback"
    openai_ready = bool(checks.get("openai_story", {}).get("ready"))

    return {
        "ok": True,
        "trend_mode": trend_mode,
        "live_trend_providers_ready": live_ready,
        "openai_story_ready": openai_ready,
        "recommended_mode": _recommended_mode(live_ready, openai_ready),
        "checks": checks,
    }


def _recommended_mode(live_ready: list[str], openai_ready: bool) -> str:
    if live_ready and openai_ready:
        return "live_trends_plus_openai_story"
    if live_ready:
        return "live_trends_rule_story"
    if openai_ready:
        return "mock_trends_openai_story"
    return "offline_rule_based"


def _provider_check(provider_name: str, *, credential_keys: tuple[str, ...]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ready": False,
        "mode": "api",
        "label": provider_name,
        "active": False,
        "notes": "",
    }
    try:
        from core.provider_registry_engine import ProviderRegistryEngine

        engine = ProviderRegistryEngine()
        ready_sources = engine.get_ready_trend_sources()
        item["active"] = provider_name in ready_sources
        item["ready"] = engine.credentials_ready(
            ProviderRegistryEngine.TREND_CATEGORY,
            provider_name,
        )
        if item["ready"] and item["active"]:
            item["notes"] = "Credentials found and provider is active."
        elif item["ready"]:
            item["notes"] = "Credentials found but provider is not in active trend sources."
        else:
            missing = [key for key in credential_keys if not _env_present(key)]
            item["notes"] = f"Missing: {', '.join(missing) if missing else 'configuration'}"
    except Exception as exc:
        item["notes"] = f"Check failed: {type(exc).__name__}"
    return item


def _openai_story_check() -> dict[str, Any]:
    item: dict[str, Any] = {
        "ready": False,
        "mode": "api",
        "label": "OpenAI story enrichment",
        "active": False,
        "notes": "",
    }
    try:
        from core.provider_registry_engine import ProviderRegistryEngine

        engine = ProviderRegistryEngine()
        active = engine.load_active()
        active_llm = str(active.get("llm") or "").strip().lower()
        item["active"] = active_llm == "openai"
        llm_ready = engine.credentials_ready("llm", "openai")
        enricher_ready = engine.credentials_ready(
            ProviderRegistryEngine.TREND_ENRICHMENT_CATEGORY,
            "openai_trend_enricher",
        )
        item["ready"] = llm_ready or enricher_ready
        if item["ready"]:
            item["notes"] = "OPENAI_API_KEY available for optional story enrichment."
        else:
            item["notes"] = "Set OPENAI_API_KEY to enable audience-friendly story polish."
    except Exception as exc:
        item["notes"] = f"Check failed: {type(exc).__name__}"
    return item


def _openai_classification_check() -> dict[str, Any]:
    item: dict[str, Any] = {
        "ready": False,
        "mode": "api",
        "label": "OpenAI classification enrichment",
        "active": False,
        "notes": "",
    }
    try:
        from content_brain.execution.content_brain_openai_classification_enricher import OpenAIClassificationEnricher

        enricher = OpenAIClassificationEnricher()
        item["ready"] = bool(enricher.enabled)
        item["active"] = item["ready"]
        if item["ready"]:
            item["notes"] = "OPENAI_API_KEY available for weak-local classification fallback."
        else:
            item["notes"] = "Set OPENAI_API_KEY to enable classification fallback for general/weak topics."
    except Exception as exc:
        item["notes"] = f"Check failed: {type(exc).__name__}"
    return item


def _openai_quality_check() -> dict[str, Any]:
    item: dict[str, Any] = {
        "ready": False,
        "mode": "api",
        "label": "OpenAI quality enhancement",
        "active": False,
        "notes": "",
    }
    try:
        from content_brain.execution.content_brain_openai_quality_enhancer import OpenAIQualityEnhancer

        enhancer = OpenAIQualityEnhancer()
        item["ready"] = bool(enhancer.enabled)
        item["active"] = item["ready"]
        if item["ready"]:
            item["notes"] = "OPENAI_API_KEY available for selective quality repair after audit."
        else:
            item["notes"] = "Set OPENAI_API_KEY to enable post-audit quality enhancement."
    except Exception as exc:
        item["notes"] = f"Check failed: {type(exc).__name__}"
    return item


def _openai_intent_check() -> dict[str, Any]:
    item: dict[str, Any] = {
        "ready": False,
        "mode": "api",
        "label": "OpenAI intent intelligence",
        "active": False,
        "notes": "",
    }
    try:
        from content_brain.execution.content_brain_intent_intelligence import OpenAIIntentEnricher

        enricher = OpenAIIntentEnricher()
        item["ready"] = bool(enricher.enabled)
        item["active"] = item["ready"]
        if item["ready"]:
            item["notes"] = "OPENAI_API_KEY available for intent-aware strategy selection."
        else:
            item["notes"] = "Set OPENAI_API_KEY to enable intent enrichment on ambiguous topics."
    except Exception as exc:
        item["notes"] = f"Check failed: {type(exc).__name__}"
    return item


def _seo_provider_bridge_check() -> dict[str, Any]:
    item: dict[str, Any] = {
        "ready": False,
        "mode": "api",
        "label": "SEO provider bridge",
        "active": False,
        "notes": "",
    }
    try:
        from core.provider_registry_engine import ProviderRegistryEngine

        engine = ProviderRegistryEngine()
        ready = engine.get_credential_ready_trend_sources()
        seo_ready = [name for name in ready if name in {"dataforseo", "serpapi", "dataforseo_youtube"}]
        item["ready"] = bool(seo_ready)
        item["active"] = bool(seo_ready)
        if seo_ready:
            item["notes"] = f"Live SEO sources available: {', '.join(seo_ready)}"
        else:
            item["notes"] = "No DataForSEO/SerpAPI credentials — SEO Director will use fallback templates."
    except Exception as exc:
        item["notes"] = f"Check failed: {type(exc).__name__}"
    return item


def _env_present(name: str) -> bool:
    import os

    return bool(str(os.getenv(name) or "").strip())


def classify_trend_sources(sources_used: list[str]) -> str:
    cleaned = [str(item).strip() for item in sources_used if str(item).strip()]
    if not cleaned:
        return "none"
    if any(source not in MOCK_ONLY_SOURCES for source in cleaned):
        return "live"
    return "mock"


__all__ = [
    "classify_trend_sources",
    "run_content_brain_studio_preflight",
]
