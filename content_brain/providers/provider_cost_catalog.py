"""
Phase 11B — provider cost catalog and pre-dispatch cost estimator.

Metadata + estimation only. Placeholder values are internal estimates, not official pricing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from content_brain.providers.provider_capability_registry import (
    CAPABILITY_IMAGE_GENERATION,
    CAPABILITY_MUSIC_GENERATION,
    CAPABILITY_NARRATION,
    CAPABILITY_TEXT_TO_IMAGE,
    CAPABILITY_TEXT_TO_VIDEO,
    CAPABILITY_VOICE_CLONE,
    ProviderCapabilityRegistry,
    normalize_provider_id,
)

CATALOG_VERSION = "11b_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# --- Cost models ---

COST_MODEL_PER_CLIP = "per_clip"
COST_MODEL_PER_SECOND = "per_second"
COST_MODEL_PER_MINUTE = "per_minute"
COST_MODEL_PER_CHARACTER = "per_character"
COST_MODEL_PER_REQUEST = "per_request"
COST_MODEL_FREE = "free"
COST_MODEL_UNKNOWN = "unknown"

ALL_COST_MODELS: tuple[str, ...] = (
    COST_MODEL_PER_CLIP,
    COST_MODEL_PER_SECOND,
    COST_MODEL_PER_MINUTE,
    COST_MODEL_PER_CHARACTER,
    COST_MODEL_PER_REQUEST,
    COST_MODEL_FREE,
    COST_MODEL_UNKNOWN,
)

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_UNKNOWN = "unknown"

ALL_CONFIDENCE_LEVELS: tuple[str, ...] = (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_UNKNOWN,
)

PLACEHOLDER_NOTE = "Internal placeholder estimate — not official provider pricing."

DEFAULT_11A_PROVIDER_IDS: tuple[str, ...] = (
    "runway",
    "runway_browser",
    "hailuo_api",
    "hailuo_browser",
    "minimax_api",
    "luma",
    "kling",
    "elevenlabs",
    "openai_tts",
    "suno",
    "generic_image",
)


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _entry(
    provider_id: str,
    capability: str,
    cost_model: str,
    *,
    unit_cost: float | None = None,
    currency: str = "USD",
    unit: str | None = None,
    min_billable_units: float = 1.0,
    notes: str = "",
    confidence: str = CONFIDENCE_UNKNOWN,
) -> dict[str, Any]:
    note_text = notes or PLACEHOLDER_NOTE
    if confidence in {CONFIDENCE_LOW, CONFIDENCE_UNKNOWN} and PLACEHOLDER_NOTE not in note_text:
        note_text = f"{note_text} {PLACEHOLDER_NOTE}".strip()
    return {
        "provider_id": provider_id,
        "capability": capability,
        "cost_model": cost_model,
        "unit_cost": unit_cost,
        "currency": currency,
        "unit": unit or _default_unit_for_model(cost_model),
        "min_billable_units": min_billable_units,
        "notes": note_text,
        "updated_at": _now(),
        "confidence": confidence,
    }


def _default_unit_for_model(cost_model: str) -> str | None:
    return {
        COST_MODEL_PER_CLIP: "clip",
        COST_MODEL_PER_SECOND: "second",
        COST_MODEL_PER_MINUTE: "minute",
        COST_MODEL_PER_CHARACTER: "character",
        COST_MODEL_PER_REQUEST: "request",
        COST_MODEL_FREE: "unit",
        COST_MODEL_UNKNOWN: None,
    }.get(cost_model)


_DEFAULT_COST_ENTRIES: tuple[dict[str, Any], ...] = (
    _entry(
        "hailuo_browser",
        CAPABILITY_TEXT_TO_VIDEO,
        COST_MODEL_PER_CLIP,
        unit_cost=1.0,
        currency="CREDITS",
        confidence=CONFIDENCE_LOW,
        notes="Internal credit placeholder aligned with simulation heuristic (~1 credit/clip).",
    ),
    _entry(
        "hailuo_api",
        CAPABILITY_TEXT_TO_VIDEO,
        COST_MODEL_UNKNOWN,
        currency="USD",
        confidence=CONFIDENCE_UNKNOWN,
        notes="API pricing not verified in ModirAgentOS.",
    ),
    _entry(
        "runway_browser",
        CAPABILITY_TEXT_TO_VIDEO,
        COST_MODEL_FREE,
        unit_cost=0.0,
        currency="USD",
        confidence=CONFIDENCE_MEDIUM,
        notes="Subscription/browser path — opportunity cost only; no per-clip API charge modeled.",
    ),
    _entry(
        "runway",
        CAPABILITY_TEXT_TO_VIDEO,
        COST_MODEL_PER_SECOND,
        unit_cost=0.05,
        currency="USD",
        confidence=CONFIDENCE_LOW,
        notes="Placeholder USD/second for API text-to-video — verify against Runway billing.",
    ),
    _entry(
        "minimax_api",
        CAPABILITY_TEXT_TO_VIDEO,
        COST_MODEL_UNKNOWN,
        currency="USD",
        confidence=CONFIDENCE_UNKNOWN,
    ),
    _entry(
        "luma",
        CAPABILITY_TEXT_TO_VIDEO,
        COST_MODEL_PER_REQUEST,
        unit_cost=None,
        currency="USD",
        confidence=CONFIDENCE_UNKNOWN,
        notes="Luma API pricing not verified.",
    ),
    _entry(
        "kling",
        CAPABILITY_TEXT_TO_VIDEO,
        COST_MODEL_PER_CLIP,
        unit_cost=None,
        currency="USD",
        confidence=CONFIDENCE_UNKNOWN,
        notes="Kling pricing not verified.",
    ),
    _entry(
        "elevenlabs",
        CAPABILITY_NARRATION,
        COST_MODEL_PER_CHARACTER,
        unit_cost=0.00003,
        currency="USD",
        confidence=CONFIDENCE_LOW,
        notes="Placeholder character rate — verify against ElevenLabs plan.",
    ),
    _entry(
        "elevenlabs",
        CAPABILITY_VOICE_CLONE,
        COST_MODEL_PER_REQUEST,
        unit_cost=None,
        currency="USD",
        confidence=CONFIDENCE_UNKNOWN,
        notes="Voice clone pricing varies by plan; not verified.",
    ),
    _entry(
        "openai_tts",
        CAPABILITY_NARRATION,
        COST_MODEL_PER_CHARACTER,
        unit_cost=0.000015,
        currency="USD",
        confidence=CONFIDENCE_MEDIUM,
        notes="Placeholder based on public TTS tiers — verify current OpenAI pricing.",
    ),
    _entry(
        "suno",
        CAPABILITY_MUSIC_GENERATION,
        COST_MODEL_PER_REQUEST,
        unit_cost=None,
        currency="USD",
        confidence=CONFIDENCE_UNKNOWN,
        notes="Suno pricing not verified; provider module not present in repo.",
    ),
    _entry(
        "generic_image",
        CAPABILITY_TEXT_TO_IMAGE,
        COST_MODEL_PER_REQUEST,
        unit_cost=0.04,
        currency="USD",
        confidence=CONFIDENCE_LOW,
    ),
    _entry(
        "generic_image",
        CAPABILITY_IMAGE_GENERATION,
        COST_MODEL_PER_REQUEST,
        unit_cost=0.04,
        currency="USD",
        confidence=CONFIDENCE_LOW,
    ),
)


@dataclass(frozen=True)
class CostCatalogEntry:
    provider_id: str
    capability: str
    cost_model: str
    unit_cost: float | None
    currency: str
    unit: str | None
    min_billable_units: float
    notes: str
    updated_at: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "capability": self.capability,
            "cost_model": self.cost_model,
            "unit_cost": self.unit_cost,
            "currency": self.currency,
            "unit": self.unit,
            "min_billable_units": self.min_billable_units,
            "notes": self.notes,
            "updated_at": self.updated_at,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostCatalogEntry:
        cost_model = str(data.get("cost_model") or COST_MODEL_UNKNOWN).lower()
        if cost_model not in ALL_COST_MODELS:
            raise ValueError(f"Unknown cost_model: {cost_model}")

        confidence = str(data.get("confidence") or CONFIDENCE_UNKNOWN).lower()
        if confidence not in ALL_CONFIDENCE_LEVELS:
            raise ValueError(f"Unknown confidence: {confidence}")

        provider_id = normalize_provider_id(str(data.get("provider_id") or ""))
        capability = str(data.get("capability") or "").strip().lower()
        if not provider_id or not capability:
            raise ValueError("provider_id and capability are required")

        unit_cost_raw = data.get("unit_cost")
        unit_cost = None if unit_cost_raw is None else float(unit_cost_raw)

        return cls(
            provider_id=provider_id,
            capability=capability,
            cost_model=cost_model,
            unit_cost=unit_cost,
            currency=str(data.get("currency") or "USD"),
            unit=data.get("unit") if data.get("unit") is not None else _default_unit_for_model(cost_model),
            min_billable_units=float(data.get("min_billable_units") or 1.0),
            notes=str(data.get("notes") or PLACEHOLDER_NOTE),
            updated_at=str(data.get("updated_at") or _now()),
            confidence=confidence,
        )


@dataclass(frozen=True)
class CostEstimateResult:
    provider_id: str
    capability: str
    estimated_cost: float | None
    currency: str
    cost_model: str
    billable_units: float | None
    confidence: str
    notes: str
    is_estimate: bool
    blocked: bool = False
    block_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "capability": self.capability,
            "estimated_cost": self.estimated_cost,
            "currency": self.currency,
            "cost_model": self.cost_model,
            "billable_units": self.billable_units,
            "confidence": self.confidence,
            "notes": self.notes,
            "is_estimate": self.is_estimate,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


class ProviderCostCatalog:
    """Read-only catalog of provider/capability cost metadata."""

    def __init__(self, entries: Iterable[CostCatalogEntry]):
        self._entries: dict[tuple[str, str], CostCatalogEntry] = {}
        self._by_provider: dict[str, list[CostCatalogEntry]] = {}

        for entry in entries:
            key = (entry.provider_id, entry.capability)
            if key in self._entries:
                raise ValueError(f"Duplicate cost entry: {entry.provider_id}/{entry.capability}")
            self._entries[key] = entry
            self._by_provider.setdefault(entry.provider_id, []).append(entry)

        for provider_id in self._by_provider:
            self._by_provider[provider_id] = sorted(
                self._by_provider[provider_id],
                key=lambda item: item.capability,
            )

    @classmethod
    def load(cls, project_root: str | Path | None = None) -> ProviderCostCatalog:
        entries = [CostCatalogEntry.from_dict(item) for item in _DEFAULT_COST_ENTRIES]

        if project_root is not None:
            override_path = Path(project_root).resolve() / "config" / "provider_cost_catalog.json"
            if override_path.exists():
                payload = json.loads(override_path.read_text(encoding="utf-8"))
                extra = payload.get("entries") or payload.get("cost_entries") or []
                if isinstance(extra, list):
                    by_key = {(e.provider_id, e.capability): e for e in entries}
                    for item in extra:
                        if isinstance(item, dict):
                            record = CostCatalogEntry.from_dict(item)
                            by_key[(record.provider_id, record.capability)] = record
                    entries = list(by_key.values())

        return cls(entries)

    @classmethod
    def default(cls) -> ProviderCostCatalog:
        return cls.load()

    def get_entry(self, provider_id: str, capability: str) -> CostCatalogEntry | None:
        key = (normalize_provider_id(provider_id), str(capability or "").strip().lower())
        return self._entries.get(key)

    def list_entries_for_provider(self, provider_id: str) -> list[CostCatalogEntry]:
        return list(self._by_provider.get(normalize_provider_id(provider_id), []))

    def list_provider_ids(self) -> list[str]:
        return sorted(self._by_provider.keys())

    def has_entry(self, provider_id: str, capability: str) -> bool:
        return self.get_entry(provider_id, capability) is not None

    def providers_with_entries(self) -> list[str]:
        return self.list_provider_ids()

    def coverage_for_default_providers(self) -> dict[str, bool]:
        return {
            provider_id: bool(self.list_entries_for_provider(provider_id))
            for provider_id in DEFAULT_11A_PROVIDER_IDS
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_version": CATALOG_VERSION,
            "cost_models": list(ALL_COST_MODELS),
            "entries": [entry.to_dict() for entry in sorted(self._entries.values(), key=lambda e: (e.provider_id, e.capability))],
        }


class ProviderCostEstimator:
    """Estimate usage cost using capability registry + cost catalog."""

    def __init__(
        self,
        catalog: ProviderCostCatalog | None = None,
        capability_registry: ProviderCapabilityRegistry | None = None,
        *,
        project_root: str | Path | None = None,
    ):
        root = project_root
        self.catalog = catalog or ProviderCostCatalog.load(root)
        self.capabilities = capability_registry or ProviderCapabilityRegistry.load(root)

    @classmethod
    def load(cls, project_root: str | Path | None = None) -> ProviderCostEstimator:
        return cls(project_root=project_root)

    def estimate(
        self,
        provider_id: str,
        capability: str,
        quantity: float,
        *,
        unit: str | None = None,
    ) -> CostEstimateResult:
        canonical = normalize_provider_id(provider_id)
        cap = str(capability or "").strip().lower()

        if not self.capabilities.supports(canonical, cap):
            return CostEstimateResult(
                provider_id=canonical,
                capability=cap,
                estimated_cost=None,
                currency="USD",
                cost_model=COST_MODEL_UNKNOWN,
                billable_units=None,
                confidence=CONFIDENCE_UNKNOWN,
                notes="Provider does not support requested capability.",
                is_estimate=False,
                blocked=True,
                block_reason="CAPABILITY_UNSUPPORTED",
            )

        entry = self.catalog.get_entry(canonical, cap)
        if entry is None:
            return CostEstimateResult(
                provider_id=canonical,
                capability=cap,
                estimated_cost=None,
                currency="USD",
                cost_model=COST_MODEL_UNKNOWN,
                billable_units=None,
                confidence=CONFIDENCE_UNKNOWN,
                notes="No cost catalog entry for provider/capability pair.",
                is_estimate=False,
                blocked=True,
                block_reason="COST_ENTRY_MISSING",
            )

        return self._estimate_from_entry(entry, quantity, unit=unit)

    def estimate_video(
        self,
        provider_id: str,
        *,
        seconds: float | None = None,
        clips: float | None = None,
        capability: str = CAPABILITY_TEXT_TO_VIDEO,
    ) -> CostEstimateResult:
        entry = self.catalog.get_entry(provider_id, capability)
        if entry is None:
            quantity = clips if clips is not None else seconds
            if quantity is None:
                quantity = 1.0
            return self.estimate(provider_id, capability, float(quantity))

        if entry.cost_model == COST_MODEL_PER_SECOND:
            quantity = float(seconds if seconds is not None else (clips or 1) * 5.0)
            return self._estimate_from_entry(entry, quantity, unit="second")
        if entry.cost_model == COST_MODEL_PER_CLIP:
            quantity = float(clips if clips is not None else 1.0)
            return self._estimate_from_entry(entry, quantity, unit="clip")
        if entry.cost_model == COST_MODEL_PER_MINUTE:
            quantity = float((seconds or 60.0) / 60.0)
            return self._estimate_from_entry(entry, quantity, unit="minute")
        quantity = float(clips if clips is not None else seconds if seconds is not None else 1.0)
        return self._estimate_from_entry(entry, quantity, unit=entry.unit)

    def estimate_voice(
        self,
        provider_id: str,
        *,
        characters: float | None = None,
        minutes: float | None = None,
        capability: str = CAPABILITY_NARRATION,
    ) -> CostEstimateResult:
        entry = self.catalog.get_entry(provider_id, capability)
        if entry and entry.cost_model == COST_MODEL_PER_MINUTE and minutes is not None:
            return self._estimate_from_entry(entry, float(minutes), unit="minute")
        if entry and entry.cost_model == COST_MODEL_PER_CHARACTER:
            quantity = float(characters if characters is not None else (minutes or 1) * 900.0)
            return self._estimate_from_entry(entry, quantity, unit="character")
        quantity = float(characters if characters is not None else (minutes or 1) * 900.0)
        return self.estimate(provider_id, capability, quantity, unit="character")

    def estimate_music(
        self,
        provider_id: str,
        *,
        tracks: float | None = None,
        seconds: float | None = None,
        capability: str = CAPABILITY_MUSIC_GENERATION,
    ) -> CostEstimateResult:
        entry = self.catalog.get_entry(provider_id, capability)
        if entry and entry.cost_model == COST_MODEL_PER_SECOND and seconds is not None:
            return self._estimate_from_entry(entry, float(seconds), unit="second")
        if entry and entry.cost_model == COST_MODEL_PER_MINUTE and seconds is not None:
            return self._estimate_from_entry(entry, float(seconds) / 60.0, unit="minute")
        quantity = float(tracks if tracks is not None else 1.0)
        return self.estimate(provider_id, capability, quantity, unit="request")

    def compare(
        self,
        provider_ids: Iterable[str],
        capability: str,
        quantity: float,
    ) -> list[CostEstimateResult]:
        results: list[CostEstimateResult] = []
        for provider_id in provider_ids:
            results.append(self.estimate(provider_id, capability, quantity))
        return sorted(
            results,
            key=lambda item: (
                item.blocked,
                item.estimated_cost is None,
                item.estimated_cost if item.estimated_cost is not None else float("inf"),
            ),
        )

    def _estimate_from_entry(
        self,
        entry: CostCatalogEntry,
        quantity: float,
        *,
        unit: str | None = None,
    ) -> CostEstimateResult:
        billable_units = max(float(quantity), float(entry.min_billable_units))

        if entry.cost_model == COST_MODEL_FREE:
            return CostEstimateResult(
                provider_id=entry.provider_id,
                capability=entry.capability,
                estimated_cost=0.0,
                currency=entry.currency,
                cost_model=entry.cost_model,
                billable_units=billable_units,
                confidence=entry.confidence,
                notes=entry.notes,
                is_estimate=True,
            )

        if entry.cost_model == COST_MODEL_UNKNOWN or entry.unit_cost is None:
            return CostEstimateResult(
                provider_id=entry.provider_id,
                capability=entry.capability,
                estimated_cost=None,
                currency=entry.currency,
                cost_model=entry.cost_model,
                billable_units=billable_units,
                confidence=entry.confidence,
                notes=entry.notes,
                is_estimate=True,
            )

        estimated_cost = round(billable_units * float(entry.unit_cost), 6)
        unit_note = f" unit={unit}" if unit else ""
        notes = f"{entry.notes}{unit_note}".strip()

        return CostEstimateResult(
            provider_id=entry.provider_id,
            capability=entry.capability,
            estimated_cost=estimated_cost,
            currency=entry.currency,
            cost_model=entry.cost_model,
            billable_units=billable_units,
            confidence=entry.confidence,
            notes=notes,
            is_estimate=True,
        )


__all__ = [
    "CATALOG_VERSION",
    "ALL_COST_MODELS",
    "ALL_CONFIDENCE_LEVELS",
    "COST_MODEL_PER_CLIP",
    "COST_MODEL_PER_SECOND",
    "COST_MODEL_PER_MINUTE",
    "COST_MODEL_PER_CHARACTER",
    "COST_MODEL_PER_REQUEST",
    "COST_MODEL_FREE",
    "COST_MODEL_UNKNOWN",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_LOW",
    "CONFIDENCE_UNKNOWN",
    "DEFAULT_11A_PROVIDER_IDS",
    "PLACEHOLDER_NOTE",
    "CostCatalogEntry",
    "CostEstimateResult",
    "ProviderCostCatalog",
    "ProviderCostEstimator",
]
