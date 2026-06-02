"""
OpenAI post-fetch trend enricher for the Viral Content Brain.

Refines existing NormalizedTrendSignal items only — no trend generation.
Credentials via ProviderRegistryEngine. One enrichment call maximum per run.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import replace
from typing import Any

from content_brain.providers.real_trend_provider import (
    NormalizedTrendSignal,
    TrendProviderContext,
)

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover - defensive import
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - defensive import
    OpenAI = None  # type: ignore[misc, assignment]


ENRICHMENT_PROVIDER_NAME = "openai_trend_enricher"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_ENRICHMENT_SIGNALS = 12
MAX_SIGNALS_IN = MAX_ENRICHMENT_SIGNALS
MAX_TOPIC_CHARS = 120
MAX_OUTPUT_TOKENS = 2000
REQUEST_TIMEOUT_SECONDS = 45.0
MAX_SCORE_DELTA = 0.05

DRY_RUN_RESPONSE: dict[str, Any] = {
    "ordered_signal_ids": ["sig_0", "sig_2", "sig_1"],
    "clusters": [
        {
            "cluster_id": "c1",
            "label": "VAR decisions",
            "signal_ids": ["sig_0", "sig_1", "sig_2"],
        }
    ],
    "cleaned_topics": [
        {
            "signal_id": "sig_1",
            "trend_topic": "VAR penalty controversy",
        }
    ],
    "duplicates_removed": [],
    "score_deltas": [
        {"signal_id": "sig_2", "enrichment_score_delta": 0.03},
        {"signal_id": "sig_1", "enrichment_score_delta": 0.01},
    ],
}


class OpenAITrendEnricher:
    """Validation-first enricher for merged provider trend signals."""

    enricher_id = ENRICHMENT_PROVIDER_NAME

    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        model: str | None = None,
        max_signals_in: int = MAX_SIGNALS_IN,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
        request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        dry_run: bool | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.model = (model or os.getenv("OPENAI_TREND_MODEL") or DEFAULT_MODEL).strip()
        self.max_signals_in = max(1, int(max_signals_in))
        self.max_output_tokens = max(256, int(max_output_tokens))
        self.request_timeout_seconds = request_timeout_seconds
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("OPENAI_TREND_ENRICH_DRY_RUN", "").strip().lower()
            in {"1", "true", "yes"}
        )
        self._api_key = ""
        credential_enabled = self._resolve_enabled_state()
        self.enabled = credential_enabled or self.dry_run
        self._client: Any | None = None

    def _get_registry_engine(self) -> Any:
        if self.registry_engine is not None:
            return self.registry_engine
        if ProviderRegistryEngine is None:
            raise RuntimeError("ProviderRegistryEngine is unavailable.")
        return ProviderRegistryEngine()

    def _resolve_enabled_state(self) -> bool:
        try:
            engine = self._get_registry_engine()
        except Exception:
            return False

        if engine.get_ready_trend_enrichment() != ENRICHMENT_PROVIDER_NAME:
            return False

        credentials = engine.get_provider_credentials(
            ProviderRegistryEngine.TREND_ENRICHMENT_CATEGORY,
            ENRICHMENT_PROVIDER_NAME,
        )
        api_key = credentials.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            return False

        self._api_key = api_key
        return True

    def enrich(
        self,
        signals: list[NormalizedTrendSignal],
        context: TrendProviderContext,
    ) -> list[NormalizedTrendSignal]:
        if not self.enabled or len(signals) <= 1:
            return signals

        try:
            return self._enrich_safe(signals, context)
        except Exception:
            return signals

    def _enrich_safe(
        self,
        signals: list[NormalizedTrendSignal],
        context: TrendProviderContext,
    ) -> list[NormalizedTrendSignal]:
        working = [_clone_signal(signal) for signal in signals[: self.max_signals_in]]
        indexed = _assign_signal_ids(working)

        if self._should_skip(indexed):
            return signals

        payload = _build_request_payload(indexed, context)
        if self.dry_run:
            response_data = DRY_RUN_RESPONSE
        else:
            if not self._api_key or OpenAI is None:
                return signals
            response_data = self._call_openai(payload)
            if not response_data:
                return signals

        if not _validate_enrichment_response(response_data, indexed):
            return signals

        enriched = _apply_enrichment_response(indexed, response_data, self.model)
        if not _validate_output_signals(enriched, indexed):
            return signals

        if len(signals) > len(enriched):
            tail = signals[len(enriched) :]
            return enriched + tail

        return enriched

    def _should_skip(
        self,
        indexed: list[tuple[str, NormalizedTrendSignal]],
    ) -> bool:
        if len(indexed) <= 1:
            return True

        authoritative = [
            signal
            for _, signal in indexed
            if _is_user_topic_authoritative(signal)
        ]
        if len(authoritative) == len(indexed):
            return True

        return False

    def _call_openai(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._client
        if client is None:
            client = OpenAI(api_key=self._api_key, timeout=self.request_timeout_seconds)
            self._client = client

        system_prompt = (
            "You refine existing short-form trend signal lists. "
            "Return JSON only. Never invent new signal_id values. "
            "Never add topics that are not refinements of provided signals. "
            "Preserve user_topic_authoritative signals exactly."
        )
        user_prompt = json.dumps(payload, ensure_ascii=False)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=self.max_output_tokens,
                response_format={"type": "json_object"},
            )
        except Exception:
            return {}

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            return {}

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}

        return parsed if isinstance(parsed, dict) else {}


def _clone_signal(signal: NormalizedTrendSignal) -> NormalizedTrendSignal:
    return replace(
        signal,
        platforms=list(signal.platforms),
        metadata=dict(signal.metadata),
    )


def _assign_signal_ids(
    signals: list[NormalizedTrendSignal],
) -> list[tuple[str, NormalizedTrendSignal]]:
    indexed: list[tuple[str, NormalizedTrendSignal]] = []
    for index, signal in enumerate(signals):
        signal_id = f"sig_{index}"
        metadata = dict(signal.metadata)
        metadata["enrichment_signal_id"] = signal_id
        indexed.append(
            (
                signal_id,
                replace(signal, metadata=metadata),
            )
        )
    return indexed


def _build_request_payload(
    indexed: list[tuple[str, NormalizedTrendSignal]],
    context: TrendProviderContext,
) -> dict[str, Any]:
    profile = context.profile if isinstance(context.profile, dict) else {}
    semantic_universe = profile.get("semantic_universe", {})
    universe_id = ""
    if isinstance(semantic_universe, dict):
        universe_id = str(semantic_universe.get("universe_id", ""))

    return {
        "task": "refine_existing_trend_signals",
        "niche": context.niche,
        "user_topic": context.topic.strip(),
        "semantic_universe_id": universe_id,
        "instructions": {
            "allowed_actions": [
                "semantic_deduplication",
                "clustering",
                "topic_cleanup",
                "ranking_assistance",
            ],
            "forbidden_actions": [
                "generate_new_topics",
                "override_user_topic_authority",
            ],
            "output_schema": {
                "ordered_signal_ids": "list[str]",
                "clusters": "list[{cluster_id,label,signal_ids}]",
                "cleaned_topics": "list[{signal_id,trend_topic}]",
                "duplicates_removed": "list[str]",
                "score_deltas": "list[{signal_id,enrichment_score_delta}]",
            },
        },
        "signals": [
            {
                "signal_id": signal_id,
                "trend_topic": _truncate_topic(signal.trend_topic),
                "provider_id": signal.provider_id,
                "confidence": signal.confidence,
                "momentum": signal.momentum,
                "user_topic_authoritative": _is_user_topic_authoritative(signal),
            }
            for signal_id, signal in indexed
        ],
    }


def _validate_enrichment_response(
    response: dict[str, Any],
    indexed: list[tuple[str, NormalizedTrendSignal]],
) -> bool:
    if not isinstance(response, dict):
        return False

    valid_ids = {signal_id for signal_id, _ in indexed}
    ordered = response.get("ordered_signal_ids", [])
    if not isinstance(ordered, list) or not ordered:
        return False

    if len(ordered) > len(valid_ids):
        return False

    if any(str(item) not in valid_ids for item in ordered):
        return False

    if len(set(str(item) for item in ordered)) != len(ordered):
        return False

    duplicates_removed = response.get("duplicates_removed", [])
    if duplicates_removed is not None:
        if not isinstance(duplicates_removed, list):
            return False
        if any(str(item) not in valid_ids for item in duplicates_removed):
            return False

    cleaned_topics = response.get("cleaned_topics", [])
    if cleaned_topics is not None:
        if not isinstance(cleaned_topics, list):
            return False
        for item in cleaned_topics:
            if not isinstance(item, dict):
                return False
            signal_id = str(item.get("signal_id", ""))
            trend_topic = str(item.get("trend_topic", "")).strip()
            if signal_id not in valid_ids or not trend_topic:
                return False
            original = _signal_by_id(indexed, signal_id)
            if original is None:
                return False
            if _is_user_topic_authoritative(original):
                if trend_topic.lower() != original.trend_topic.strip().lower():
                    return False
            elif not _topics_compatible(original.trend_topic, trend_topic):
                return False

    score_deltas = response.get("score_deltas", [])
    if score_deltas is not None:
        if not isinstance(score_deltas, list):
            return False
        for item in score_deltas:
            if not isinstance(item, dict):
                return False
            signal_id = str(item.get("signal_id", ""))
            if signal_id not in valid_ids:
                return False
            delta = item.get("enrichment_score_delta")
            if not isinstance(delta, (int, float)):
                return False
            if abs(float(delta)) > MAX_SCORE_DELTA:
                return False

    clusters = response.get("clusters", [])
    if clusters is not None:
        if not isinstance(clusters, list):
            return False
        for cluster in clusters:
            if not isinstance(cluster, dict):
                return False
            cluster_ids = cluster.get("signal_ids", [])
            if not isinstance(cluster_ids, list):
                return False
            if any(str(item) not in valid_ids for item in cluster_ids):
                return False

    return True


def _validate_output_signals(
    enriched: list[NormalizedTrendSignal],
    indexed: list[tuple[str, NormalizedTrendSignal]],
) -> bool:
    if len(enriched) > len(indexed):
        return False

    original_by_id = {signal_id: signal for signal_id, signal in indexed}
    seen_ids: set[str] = set()

    for signal in enriched:
        signal_id = str(signal.metadata.get("enrichment_signal_id", ""))
        if not signal_id or signal_id in seen_ids:
            return False
        seen_ids.add(signal_id)

        original = original_by_id.get(signal_id)
        if original is None:
            return False

        if original.provider_id != signal.provider_id:
            return False
        if original.source != signal.source:
            return False
        if original.attribution != signal.attribution:
            return False
        if original.collected_at != signal.collected_at:
            return False

        if _is_user_topic_authoritative(original):
            if signal.trend_topic.strip().lower() != original.trend_topic.strip().lower():
                return False

    return True


def _apply_enrichment_response(
    indexed: list[tuple[str, NormalizedTrendSignal]],
    response: dict[str, Any],
    model: str,
) -> list[NormalizedTrendSignal]:
    by_id = {signal_id: signal for signal_id, signal in indexed}

    duplicates_removed = {
        str(item) for item in response.get("duplicates_removed", []) if str(item)
    }
    ordered_ids = [str(item) for item in response.get("ordered_signal_ids", [])]
    ordered_ids = [signal_id for signal_id in ordered_ids if signal_id not in duplicates_removed]

    for signal_id in by_id:
        if signal_id not in ordered_ids and signal_id not in duplicates_removed:
            ordered_ids.append(signal_id)

    cleaned_map = {
        str(item.get("signal_id")): str(item.get("trend_topic", "")).strip()
        for item in response.get("cleaned_topics", [])
        if isinstance(item, dict)
    }

    delta_map = {
        str(item.get("signal_id")): float(item.get("enrichment_score_delta", 0.0))
        for item in response.get("score_deltas", [])
        if isinstance(item, dict)
    }

    cluster_map: dict[str, dict[str, Any]] = {}
    for cluster in response.get("clusters", []):
        if not isinstance(cluster, dict):
            continue
        cluster_id = str(cluster.get("cluster_id", "")).strip()
        label = str(cluster.get("label", "")).strip()
        for signal_id in cluster.get("signal_ids", []):
            cluster_map[str(signal_id)] = {
                "enrichment_cluster_id": cluster_id,
                "enrichment_cluster": label,
            }

    enriched: list[NormalizedTrendSignal] = []
    for signal_id in ordered_ids:
        original = by_id.get(signal_id)
        if original is None or signal_id in duplicates_removed:
            continue

        metadata = dict(original.metadata)
        metadata["enrichment_applied"] = True
        metadata["enrichment_provider"] = ENRICHMENT_PROVIDER_NAME
        metadata["enrichment_model"] = model

        cluster_meta = cluster_map.get(signal_id)
        if cluster_meta:
            metadata.update(cluster_meta)

        delta = delta_map.get(signal_id)
        if delta is not None:
            metadata["enrichment_score_delta"] = round(float(delta), 4)

        trend_topic = original.trend_topic
        if not _is_user_topic_authoritative(original):
            cleaned = cleaned_map.get(signal_id)
            if cleaned:
                metadata["enrichment_source_topic"] = original.trend_topic
                trend_topic = cleaned
        else:
            metadata["user_topic_authoritative"] = True

        enriched.append(
            replace(
                original,
                trend_topic=trend_topic,
                metadata=metadata,
            )
        )

    authoritative = [signal for signal in enriched if _is_user_topic_authoritative(signal)]
    non_authoritative = [
        signal for signal in enriched if not _is_user_topic_authoritative(signal)
    ]
    return authoritative + non_authoritative


def _signal_by_id(
    indexed: list[tuple[str, NormalizedTrendSignal]],
    signal_id: str,
) -> NormalizedTrendSignal | None:
    for current_id, signal in indexed:
        if current_id == signal_id:
            return signal
    return None


def _is_user_topic_authoritative(signal: NormalizedTrendSignal) -> bool:
    metadata = signal.metadata if isinstance(signal.metadata, dict) else {}
    return bool(
        metadata.get("user_topic_authoritative")
        or metadata.get("priority") == "user_topic"
    )


def _truncate_topic(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip())
    if len(cleaned) <= MAX_TOPIC_CHARS:
        return cleaned
    return cleaned[:MAX_TOPIC_CHARS].rsplit(" ", 1)[0].strip()


def _tokenize(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return {token for token in cleaned.split() if token}


def _topics_compatible(original: str, candidate: str) -> bool:
    original_tokens = _tokenize(original)
    candidate_tokens = _tokenize(candidate)
    if not original_tokens or not candidate_tokens:
        return original.strip().lower() == candidate.strip().lower()

    overlap = len(original_tokens.intersection(candidate_tokens))
    minimum = min(len(original_tokens), len(candidate_tokens))
    if minimum == 0:
        return False

    ratio = overlap / minimum
    return ratio >= 0.6 or original.strip().lower() == candidate.strip().lower()


__all__ = [
    "DEFAULT_MODEL",
    "ENRICHMENT_PROVIDER_NAME",
    "MAX_ENRICHMENT_SIGNALS",
    "MAX_SIGNALS_IN",
    "OpenAITrendEnricher",
]


if __name__ == "__main__":
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    engine = ProviderRegistryEngine() if ProviderRegistryEngine is not None else None
    enricher = OpenAITrendEnricher(registry_engine=engine, dry_run=True)

    football_profile = loader.resolve(niche="football")
    context = TrendProviderContext(
        niche="football",
        topic="late VAR replay angle",
        profile=football_profile,
        max_results=5,
    )

    sample_signals = [
        NormalizedTrendSignal(
            trend_topic="late VAR replay angle",
            source="mock_local_seed",
            confidence=0.91,
            freshness_score=0.92,
            niche_match=0.9,
            momentum="spiking",
            provider_id="mock_trend_provider",
            metadata={"user_topic_authoritative": True, "priority": "user_topic"},
        ),
        NormalizedTrendSignal(
            trend_topic="var penalty controversy",
            source="serpapi_google_trends",
            confidence=0.75,
            freshness_score=0.86,
            niche_match=0.66,
            momentum="rising",
            provider_id="serpapi",
        ),
        NormalizedTrendSignal(
            trend_topic="offside line disputes",
            source="dataforseo_google_ads",
            confidence=0.81,
            freshness_score=0.82,
            niche_match=0.82,
            momentum="rising",
            provider_id="dataforseo",
        ),
    ]

    print("=" * 72)
    print("OPENAI TREND ENRICHER SMOKE")
    print("=" * 72)
    print("ENABLED:", enricher.enabled)
    print("MODEL:", enricher.model)
    if engine is not None:
        print(
            "ENRICHMENT READY:",
            engine.get_ready_trend_enrichment(),
        )

    enriched = enricher.enrich(sample_signals, context)
    print("INPUT COUNT:", len(sample_signals))
    print("OUTPUT COUNT:", len(enriched))
    for signal in enriched:
        print(
            f"- {signal.trend_topic} | confidence={signal.confidence} | "
            f"delta={signal.metadata.get('enrichment_score_delta')} | "
            f"authoritative={signal.metadata.get('user_topic_authoritative')}"
        )

    user_signal = enriched[0]
    assert user_signal.trend_topic == "late VAR replay angle"
    assert user_signal.confidence == 0.91
    print("USER TOPIC PRESERVED: True")
