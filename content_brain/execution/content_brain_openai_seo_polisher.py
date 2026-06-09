"""
OpenAI SEO Polisher — refine provider-derived SEO titles without inventing from raw topic only.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]

POLISHER_ID = "openai_seo_polisher"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_OUTPUT_TOKENS = 900


@dataclass
class SeoPolishResult:
    applied: bool = False
    enabled: bool = False
    titles: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "enabled": self.enabled,
            "titles": list(self.titles),
            "notes": list(self.notes),
            "usage": dict(self.usage),
        }


class OpenAISeoPolisher:
    def __init__(
        self,
        *,
        model: str | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.model = (model or os.getenv("OPENAI_SEO_MODEL") or DEFAULT_MODEL).strip()
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("OPENAI_SEO_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        self._api_key = ""
        self.enabled = self._resolve_enabled_state() or self.dry_run
        self._client: Any | None = None

    def polish_titles(
        self,
        *,
        topic: str,
        language_code: str,
        provider_titles: list[str],
        seo_keywords: list[str] | None = None,
        related_queries: list[str] | None = None,
        people_also_ask: list[str] | None = None,
        search_intent: str = "",
        strategy_id: str = "",
    ) -> SeoPolishResult:
        cleaned_candidates = [str(item).strip() for item in provider_titles if str(item).strip()]
        if not cleaned_candidates:
            return SeoPolishResult(enabled=self.enabled, notes=["openai_seo_no_provider_titles"])
        if not self.enabled:
            return SeoPolishResult(
                enabled=False,
                titles=cleaned_candidates[:6],
                notes=["openai_seo_polisher_disabled"],
            )
        if self.dry_run:
            titles = _build_dry_run_titles(
                topic,
                cleaned_candidates,
                seo_keywords=list(seo_keywords or []),
                related_queries=list(related_queries or []),
            )
            return SeoPolishResult(
                applied=True,
                enabled=True,
                titles=titles,
                notes=["openai_seo_dry_run"],
            )
        if not self._api_key or OpenAI is None:
            return SeoPolishResult(
                enabled=True,
                titles=cleaned_candidates[:6],
                notes=["openai_client_unavailable"],
            )
        titles, usage = self._call_openai(
            topic=topic,
            language_code=language_code,
            provider_titles=cleaned_candidates,
            seo_keywords=list(seo_keywords or []),
            related_queries=list(related_queries or []),
            people_also_ask=list(people_also_ask or []),
            search_intent=search_intent,
            strategy_id=strategy_id,
        )
        if not titles:
            return SeoPolishResult(
                enabled=True,
                titles=cleaned_candidates[:6],
                notes=["openai_seo_polish_failed"],
            )
        return SeoPolishResult(
            applied=True,
            enabled=True,
            titles=titles,
            notes=["openai_seo_polish_applied"],
            usage=usage,
        )

    def _call_openai(
        self,
        *,
        topic: str,
        language_code: str,
        provider_titles: list[str],
        seo_keywords: list[str],
        related_queries: list[str],
        people_also_ask: list[str],
        search_intent: str,
        strategy_id: str,
    ) -> tuple[list[str], dict[str, Any]]:
        client = self._client
        if client is None:
            client = OpenAI(api_key=self._api_key, timeout=45.0)
            self._client = client
        system_prompt = (
            "You polish short-form video SEO titles. Return JSON only. "
            "Use the provider keywords, related queries, and People Also Ask data provided. "
            "Do NOT simply repeat the raw topic question verbatim. "
            "Keep titles natural, specific, and under 72 characters when possible. "
            "Write in the requested language_code."
        )
        user_payload = {
            "topic": topic,
            "language_code": language_code,
            "search_intent": search_intent,
            "strategy_id": strategy_id,
            "provider_titles": provider_titles[:8],
            "seo_keywords": seo_keywords[:10],
            "related_queries": related_queries[:10],
            "people_also_ask": people_also_ask[:8],
            "required_output": {"seo_titles": "array of 5 polished titles"},
        }
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                temperature=0.35,
                max_tokens=MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception:
            return [], {}
        content = response.choices[0].message.content if response.choices else ""
        usage_obj = getattr(response, "usage", None)
        usage = {
            "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
        }
        if not content:
            return [], usage
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return [], usage
        titles = parsed.get("seo_titles") if isinstance(parsed, dict) else []
        cleaned = [re.sub(r"\s+", " ", str(item).strip()) for item in titles or [] if str(item).strip()]
        return cleaned[:6], usage

    def _resolve_enabled_state(self) -> bool:
        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        if api_key:
            self._api_key = api_key
            return True
        try:
            if ProviderRegistryEngine is None:
                return False
            engine = ProviderRegistryEngine()
            for category, provider in (("llm", "openai"), (ProviderRegistryEngine.TREND_ENRICHMENT_CATEGORY, "openai_trend_enricher")):
                if engine.credentials_ready(category, provider):
                    creds = engine.get_provider_credentials(category, provider)
                    key = creds.get("OPENAI_API_KEY", "").strip()
                    if key:
                        self._api_key = key
                        return True
        except Exception:
            return False
        return False


def polish_provider_seo_titles(**kwargs: Any) -> SeoPolishResult:
    return OpenAISeoPolisher().polish_titles(**kwargs)


def _build_dry_run_titles(
    topic: str,
    provider_titles: list[str],
    *,
    seo_keywords: list[str],
    related_queries: list[str],
) -> list[str]:
    lowered = topic.lower()
    if "marketing" in lowered and "agenc" in lowered:
        curated = [
            "Will AI Replace Marketing Agencies by 2026?",
            "The AI Threat Most Agencies Ignore",
            "Can Agencies Survive the AI Revolution?",
            "Why AI Could Disrupt the Marketing Industry",
            "What AI Automation Means for Agencies in 2026",
        ]
        return list(dict.fromkeys(curated + provider_titles))[:6]
    merged = list(dict.fromkeys(provider_titles + related_queries[:3] + seo_keywords[:2]))
    return merged[:6]


__all__ = ["OpenAISeoPolisher", "SeoPolishResult", "polish_provider_seo_titles"]
