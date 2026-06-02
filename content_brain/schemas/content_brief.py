"""
Canonical schema contracts for the Viral Content Brain pipeline.

All agents and engines read/write these dataclasses.
Serialization is JSON-safe and compatible with runtime_state_manager persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Optional, Union, get_args, get_origin, get_type_hints
import uuid


# ---------------------------------------------------------------------------
# Timestamp helpers (matches runtime_state_manager format)
# ---------------------------------------------------------------------------

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _parse_timestamp(value: str) -> str:
    datetime.strptime(value, TIMESTAMP_FORMAT)
    return value


def generate_brief_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return f"brief_{timestamp}_{short_id}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Platform(str, Enum):
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM_REELS = "instagram_reels"


class ContentDomain(str, Enum):
    GENERAL = "general"
    CUSTOM = "custom"
    DARK_MYSTERY = "dark_mystery"
    PSYCHOLOGICAL = "psychological"
    DISTURBING_CINEMATIC = "disturbing_cinematic"


class HookClass(str, Enum):
    VIOLATION = "violation"
    INCOMPLETE_TRUTH = "incomplete_truth"
    PERSONAL_THREAT = "personal_threat"
    MORAL_DISCOMFORT = "moral_discomfort"
    FALSE_SAFETY = "false_safety"
    OPEN_LOOP_SEED = "open_loop_seed"


class StoryMode(str, Enum):
    FOUND_FOOTAGE = "found_footage"
    CONFESSION = "confession"
    MISSING_PERSON = "missing_person"
    WRONG_HOUSE = "wrong_house"
    PSYCHOLOGICAL_UNRAVELING = "psychological_unraveling"
    LORE_EPISODE = "lore_episode"


class ProductionTier(str, Enum):
    S = "S"
    A = "A"
    B = "B"
    F = "F"


class PipelineStage(str, Enum):
    CREATED = "created"
    TREND_SELECT = "trend_select"
    HOOK_ENGINEER = "hook_engineer"
    STORY_ARCHITECT = "story_architect"
    RETENTION_MAP = "retention_map"
    UNIQUENESS_GATE = "uniqueness_gate"
    VIRAL_SCORE_GATE = "viral_score_gate"
    TITLE_THUMBNAIL = "title_thumbnail"
    PLATFORM_ADAPT = "platform_adapt"
    DIRECTOR_HANDOFF = "director_handoff"
    COMPLETED = "completed"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls) -> ValidationResult:
        return cls(is_valid=True, errors=[])

    @classmethod
    def fail(cls, errors: list[str]) -> ValidationResult:
        return cls(is_valid=False, errors=errors)

    def merge(self, other: ValidationResult) -> ValidationResult:
        if other.is_valid:
            return self
        return ValidationResult(
            is_valid=False,
            errors=self.errors + other.errors,
        )


def _require_non_empty(value: str, label: str, errors: list[str]) -> None:
    if not value or not str(value).strip():
        errors.append(f"{label} must be a non-empty string.")


def _require_range(
    value: float,
    label: str,
    low: float,
    high: float,
    errors: list[str],
) -> None:
    if value < low or value > high:
        errors.append(f"{label} must be between {low} and {high}, got {value}.")


def _require_positive_int(value: int, label: str, errors: list[str]) -> None:
    if value <= 0:
        errors.append(f"{label} must be a positive integer, got {value}.")


def _require_non_negative_int(value: int, label: str, errors: list[str]) -> None:
    if value < 0:
        errors.append(f"{label} must be >= 0, got {value}.")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _is_enum(value: Any) -> bool:
    return isinstance(value, Enum)


def _enum_value(value: Enum) -> str:
    return value.value


def _to_plain(value: Any) -> Any:
    if _is_enum(value):
        return _enum_value(value)
    if is_dataclass(value):
        return {
            key: _to_plain(item)
            for key, item in value.__dict__.items()
        }
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _to_plain(item)
            for key, item in value.items()
        }
    return value


def _coerce_enum(enum_cls: type[Enum], raw: Any, label: str) -> Enum:
    if isinstance(raw, enum_cls):
        return raw
    if isinstance(raw, str):
        try:
            return enum_cls(raw)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in enum_cls)
            raise ValueError(
                f"{label} must be one of [{allowed}], got {raw!r}."
            ) from exc
    raise ValueError(f"{label} must be a string or {enum_cls.__name__}, got {type(raw).__name__}.")


def _coerce_optional_enum(
    enum_cls: type[Enum],
    raw: Any,
    label: str,
) -> Optional[Enum]:
    if raw is None:
        return None
    return _coerce_enum(enum_cls, raw, label)


def _resolve_type_hints(cls: type) -> dict[str, Any]:
    module = __import__(cls.__module__, fromlist=["_dummy"])
    globalns = vars(module)
    localns = dict(globalns)
    localns[cls.__name__] = cls
    return get_type_hints(cls, globalns=globalns, localns=localns)


def _build_from_dict(cls: type, data: dict[str, Any]) -> Any:
    if not is_dataclass(cls):
        raise TypeError(f"{cls} is not a dataclass.")

    kwargs: dict[str, Any] = {}
    field_types = _resolve_type_hints(cls)
    valid_names = {item.name for item in fields(cls)}

    for key, raw_value in data.items():
        if key not in valid_names:
            continue

        field_type = field_types[key]
        kwargs[key] = _coerce_field_value(field_type, raw_value, key)

    return cls(**kwargs)


def _coerce_field_value(field_type: Any, raw_value: Any, label: str) -> Any:
    origin = get_origin(field_type)

    if origin is list:
        inner_type = get_args(field_type)[0]
        if raw_value is None:
            return []
        if not isinstance(raw_value, list):
            raise ValueError(f"{label} must be a list.")
        return [_coerce_field_value(inner_type, item, f"{label}[]") for item in raw_value]

    if origin is dict:
        key_type, value_type = get_args(field_type)
        if raw_value is None:
            return {}
        if not isinstance(raw_value, dict):
            raise ValueError(f"{label} must be a dict.")
        return {
            _coerce_field_value(key_type, key, f"{label} key"): _coerce_field_value(
                value_type, value, f"{label}[{key}]"
            )
            for key, value in raw_value.items()
        }

    if origin is Union:
        if raw_value is None and type(None) in get_args(field_type):
            return None
        non_none = [arg for arg in get_args(field_type) if arg is not type(None)]
        if non_none:
            return _coerce_field_value(non_none[0], raw_value, label)
        return raw_value

    if isinstance(field_type, type) and issubclass(field_type, Enum):
        return _coerce_enum(field_type, raw_value, label)

    if isinstance(field_type, type) and is_dataclass(field_type):
        if raw_value is None:
            return None
        if not isinstance(raw_value, dict):
            raise ValueError(f"{label} must be a dict.")
        return _build_from_dict(field_type, raw_value)

    return raw_value


# ---------------------------------------------------------------------------
# Schema base mixin
# ---------------------------------------------------------------------------

class SchemaMixin:
    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        if not isinstance(data, dict):
            raise ValueError(f"{cls.__name__}.from_dict() expects a dict.")
        return _build_from_dict(cls, data)


# ---------------------------------------------------------------------------
# Leaf / nested schemas
# ---------------------------------------------------------------------------

@dataclass
class TrendSignal(SchemaMixin):
    topic: str
    velocity: float
    saturation: float
    virality_score: float
    platform: Platform
    source: str = "manual_seed"
    emotional_vector: dict[str, float] = field(default_factory=dict)
    platform_fit: dict[str, float] = field(default_factory=dict)
    expiry_window_hours: int = 72

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.topic, "TrendSignal.topic", errors)
        _require_range(self.velocity, "TrendSignal.velocity", 0.0, 100.0, errors)
        _require_range(self.saturation, "TrendSignal.saturation", 0.0, 100.0, errors)
        _require_range(self.virality_score, "TrendSignal.virality_score", 0.0, 100.0, errors)
        _require_positive_int(self.expiry_window_hours, "TrendSignal.expiry_window_hours", errors)

        for name, score in self.emotional_vector.items():
            _require_non_empty(name, "TrendSignal.emotional_vector key", errors)
            _require_range(score, f"TrendSignal.emotional_vector[{name}]", 0.0, 1.0, errors)

        for platform_name, fit_score in self.platform_fit.items():
            _require_non_empty(platform_name, "TrendSignal.platform_fit key", errors)
            _require_range(fit_score, f"TrendSignal.platform_fit[{platform_name}]", 0.0, 100.0, errors)

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class HookVariant(SchemaMixin):
    variant_id: str
    hook_class: HookClass
    text: str
    curiosity_gap_score: float = 0.0
    interrupt_power: float = 0.0
    specificity_score: float = 0.0
    emotional_vector: dict[str, float] = field(default_factory=dict)

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.variant_id, "HookVariant.variant_id", errors)
        _require_non_empty(self.text, "HookVariant.text", errors)
        _require_range(self.curiosity_gap_score, "HookVariant.curiosity_gap_score", 0.0, 100.0, errors)
        _require_range(self.interrupt_power, "HookVariant.interrupt_power", 0.0, 100.0, errors)
        _require_range(self.specificity_score, "HookVariant.specificity_score", 0.0, 100.0, errors)

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class HookPackage(SchemaMixin):
    variants: list[HookVariant]
    selected_variant_id: str = ""
    best_hook_text: str = ""
    hook_class: Optional[HookClass] = None
    composite_score: float = 0.0

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        if not self.variants:
            errors.append("HookPackage.variants must contain at least one hook variant.")

        variant_ids: set[str] = set()
        result = ValidationResult.ok()

        for index, variant in enumerate(self.variants):
            variant_result = variant.validate()
            result = result.merge(variant_result)
            if variant.variant_id in variant_ids:
                errors.append(f"Duplicate HookVariant.variant_id: {variant.variant_id}.")
            variant_ids.add(variant.variant_id)

        if self.selected_variant_id:
            _require_non_empty(self.selected_variant_id, "HookPackage.selected_variant_id", errors)
            if self.selected_variant_id not in variant_ids:
                errors.append(
                    f"HookPackage.selected_variant_id {self.selected_variant_id!r} "
                    "does not match any variant."
                )

        if self.best_hook_text:
            _require_non_empty(self.best_hook_text, "HookPackage.best_hook_text", errors)

        _require_range(self.composite_score, "HookPackage.composite_score", 0.0, 100.0, errors)

        if errors:
            result = result.merge(ValidationResult.fail(errors))
        return result


@dataclass
class StoryBeat(SchemaMixin):
    beat_id: str
    act: int
    start_second: float
    end_second: float
    description: str
    emotional_tone: str
    retention_mechanic: str = ""

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.beat_id, "StoryBeat.beat_id", errors)
        _require_non_empty(self.description, "StoryBeat.description", errors)
        _require_non_empty(self.emotional_tone, "StoryBeat.emotional_tone", errors)
        _require_positive_int(self.act, "StoryBeat.act", errors)

        if self.end_second <= self.start_second:
            errors.append(
                f"StoryBeat.end_second ({self.end_second}) must be greater than "
                f"start_second ({self.start_second})."
            )

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class StoryBlueprint(SchemaMixin):
    story_mode: StoryMode
    beats: list[StoryBeat]
    reveal_type: str
    loop_seed: str
    total_duration_seconds: int
    emotional_curve: list[float] = field(default_factory=list)
    lore_refs: list[str] = field(default_factory=list)
    sensory_anchor: str = ""

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.reveal_type, "StoryBlueprint.reveal_type", errors)
        _require_non_empty(self.loop_seed, "StoryBlueprint.loop_seed", errors)
        _require_positive_int(self.total_duration_seconds, "StoryBlueprint.total_duration_seconds", errors)

        if not self.beats:
            errors.append("StoryBlueprint.beats must contain at least one beat.")

        result = ValidationResult.ok()
        for beat in self.beats:
            result = result.merge(beat.validate())

        for index, intensity in enumerate(self.emotional_curve):
            _require_range(
                intensity,
                f"StoryBlueprint.emotional_curve[{index}]",
                0.0,
                1.0,
                errors,
            )

        if errors:
            result = result.merge(ValidationResult.fail(errors))
        return result


@dataclass
class RetentionBeat(SchemaMixin):
    block_label: str
    start_second: float
    end_second: float
    mechanic: str
    implementation_note: str
    required: bool = True

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.block_label, "RetentionBeat.block_label", errors)
        _require_non_empty(self.mechanic, "RetentionBeat.mechanic", errors)
        _require_non_empty(self.implementation_note, "RetentionBeat.implementation_note", errors)

        if self.end_second <= self.start_second:
            errors.append(
                f"RetentionBeat.end_second ({self.end_second}) must be greater than "
                f"start_second ({self.start_second})."
            )

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class RetentionMap(SchemaMixin):
    beats: list[RetentionBeat]
    retention_score_estimate: float = 0.0
    pattern_break_count: int = 0
    loop_seed_present: bool = False

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        if not self.beats:
            errors.append("RetentionMap.beats must contain at least one retention beat.")

        _require_range(
            self.retention_score_estimate,
            "RetentionMap.retention_score_estimate",
            0.0,
            100.0,
            errors,
        )
        _require_non_negative_int(self.pattern_break_count, "RetentionMap.pattern_break_count", errors)

        result = ValidationResult.ok()
        for beat in self.beats:
            result = result.merge(beat.validate())

        if errors:
            result = result.merge(ValidationResult.fail(errors))
        return result


@dataclass
class ScoreDimension(SchemaMixin):
    name: str
    score: float
    weight: float
    notes: str = ""

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.name, "ScoreDimension.name", errors)
        _require_range(self.score, f"ScoreDimension.score[{self.name}]", 0.0, 100.0, errors)
        _require_range(self.weight, f"ScoreDimension.weight[{self.name}]", 0.0, 1.0, errors)

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class ViralScorecard(SchemaMixin):
    dimensions: list[ScoreDimension]
    composite_score: float
    production_tier: ProductionTier
    passed_gate: bool
    minimum_gate_score: float = 65.0

    VIRAL_GATE_SCORE: ClassVar[float] = 65.0

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        if not self.dimensions:
            errors.append("ViralScorecard.dimensions must contain at least one score dimension.")

        _require_range(self.composite_score, "ViralScorecard.composite_score", 0.0, 100.0, errors)
        _require_range(self.minimum_gate_score, "ViralScorecard.minimum_gate_score", 0.0, 100.0, errors)

        total_weight = sum(item.weight for item in self.dimensions)
        if self.dimensions and abs(total_weight - 1.0) > 0.01:
            errors.append(
                f"ViralScorecard dimension weights must sum to 1.0, got {total_weight:.4f}."
            )

        if self.passed_gate and self.composite_score < self.minimum_gate_score:
            errors.append(
                "ViralScorecard.passed_gate is True but composite_score is below minimum_gate_score."
            )

        result = ValidationResult.ok()
        for dimension in self.dimensions:
            result = result.merge(dimension.validate())

        if errors:
            result = result.merge(ValidationResult.fail(errors))
        return result


@dataclass
class PlatformVariant(SchemaMixin):
    platform: Platform
    title: str
    caption: str
    duration_seconds: int
    hashtags: list[str] = field(default_factory=list)
    hook_overlay: str = ""
    cta: str = ""

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.title, f"PlatformVariant[{self.platform.value}].title", errors)
        _require_non_empty(self.caption, f"PlatformVariant[{self.platform.value}].caption", errors)
        _require_positive_int(
            self.duration_seconds,
            f"PlatformVariant[{self.platform.value}].duration_seconds",
            errors,
        )

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class DirectorShot(SchemaMixin):
    clip_number: int
    duration_seconds: int
    prompt: str
    camera_shot: str
    camera_movement: str
    lighting: str
    pacing: str
    continuity_notes: str = ""

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_positive_int(self.clip_number, "DirectorShot.clip_number", errors)
        _require_positive_int(self.duration_seconds, "DirectorShot.duration_seconds", errors)
        _require_non_empty(self.prompt, "DirectorShot.prompt", errors)
        _require_non_empty(self.camera_shot, "DirectorShot.camera_shot", errors)
        _require_non_empty(self.camera_movement, "DirectorShot.camera_movement", errors)
        _require_non_empty(self.lighting, "DirectorShot.lighting", errors)
        _require_non_empty(self.pacing, "DirectorShot.pacing", errors)

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class UniquenessLayer(SchemaMixin):
    layer_name: str
    similarity_score: float
    threshold: float
    passed: bool
    detail: str = ""

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        _require_non_empty(self.layer_name, "UniquenessLayer.layer_name", errors)
        _require_range(self.similarity_score, f"UniquenessLayer[{self.layer_name}].similarity_score", 0.0, 1.0, errors)
        _require_range(self.threshold, f"UniquenessLayer[{self.layer_name}].threshold", 0.0, 1.0, errors)

        if self.passed and self.similarity_score > self.threshold:
            errors.append(
                f"UniquenessLayer[{self.layer_name}] passed=True but "
                f"similarity_score ({self.similarity_score}) exceeds threshold ({self.threshold})."
            )

        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()


@dataclass
class UniquenessReport(SchemaMixin):
    passed: bool
    layers: list[UniquenessLayer]
    max_similarity: float
    uniqueness_score: float
    regeneration_directive: str = ""

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        if not self.layers:
            errors.append("UniquenessReport.layers must contain at least one layer.")

        _require_range(self.max_similarity, "UniquenessReport.max_similarity", 0.0, 1.0, errors)
        _require_range(self.uniqueness_score, "UniquenessReport.uniqueness_score", 0.0, 100.0, errors)

        if not self.passed and not self.regeneration_directive.strip():
            errors.append(
                "UniquenessReport.regeneration_directive is required when passed=False."
            )

        result = ValidationResult.ok()
        for layer in self.layers:
            result = result.merge(layer.validate())

        if errors:
            result = result.merge(ValidationResult.fail(errors))
        return result


# ---------------------------------------------------------------------------
# Root contract
# ---------------------------------------------------------------------------

@dataclass
class ContentBrief(SchemaMixin):
    brief_id: str
    domain: ContentDomain
    platforms: list[Platform]
    created_at: str
    updated_at: str
    current_stage: PipelineStage = PipelineStage.CREATED
    trend_context: Optional[TrendSignal] = None
    hook_package: Optional[HookPackage] = None
    story_blueprint: Optional[StoryBlueprint] = None
    retention_map: Optional[RetentionMap] = None
    viral_scorecard: Optional[ViralScorecard] = None
    platform_variants: dict[str, PlatformVariant] = field(default_factory=dict)
    director_shots: list[DirectorShot] = field(default_factory=list)
    uniqueness_report: Optional[UniquenessReport] = None
    lore_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        domain: ContentDomain,
        platforms: list[Platform],
        brief_id: Optional[str] = None,
    ) -> ContentBrief:
        timestamp = _now_timestamp()
        return cls(
            brief_id=brief_id or generate_brief_id(),
            domain=domain,
            platforms=platforms,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def touch(self) -> None:
        self.updated_at = _now_timestamp()

    def validate(self, strict: bool = False) -> ValidationResult:
        errors: list[str] = []
        result = ValidationResult.ok()

        _require_non_empty(self.brief_id, "ContentBrief.brief_id", errors)
        _require_non_empty(self.created_at, "ContentBrief.created_at", errors)
        _require_non_empty(self.updated_at, "ContentBrief.updated_at", errors)

        try:
            _parse_timestamp(self.created_at)
        except ValueError:
            errors.append(
                f"ContentBrief.created_at must match format {TIMESTAMP_FORMAT!r}."
            )

        try:
            _parse_timestamp(self.updated_at)
        except ValueError:
            errors.append(
                f"ContentBrief.updated_at must match format {TIMESTAMP_FORMAT!r}."
            )

        if not self.platforms:
            errors.append("ContentBrief.platforms must contain at least one platform.")

        platform_values = [platform.value for platform in self.platforms]
        if len(platform_values) != len(set(platform_values)):
            errors.append("ContentBrief.platforms contains duplicate platform entries.")

        nested_checks = [
            self.trend_context,
            self.hook_package,
            self.story_blueprint,
            self.retention_map,
            self.viral_scorecard,
            self.uniqueness_report,
        ]
        for nested in nested_checks:
            if nested is not None:
                result = result.merge(nested.validate())

        for platform_key, variant in self.platform_variants.items():
            try:
                _coerce_enum(Platform, platform_key, "ContentBrief.platform_variants key")
            except ValueError as exc:
                errors.append(str(exc))
            result = result.merge(variant.validate())
            if variant.platform.value != platform_key:
                errors.append(
                    f"PlatformVariant key {platform_key!r} does not match "
                    f"variant.platform {variant.platform.value!r}."
                )

        for shot in self.director_shots:
            result = result.merge(shot.validate())

        if strict:
            required_for_production = [
                ("trend_context", self.trend_context),
                ("hook_package", self.hook_package),
                ("story_blueprint", self.story_blueprint),
                ("retention_map", self.retention_map),
                ("viral_scorecard", self.viral_scorecard),
                ("uniqueness_report", self.uniqueness_report),
            ]
            for label, value in required_for_production:
                if value is None:
                    errors.append(f"ContentBrief.{label} is required in strict validation mode.")

            if not self.director_shots:
                errors.append("ContentBrief.director_shots is required in strict validation mode.")

            if not self.platform_variants:
                errors.append("ContentBrief.platform_variants is required in strict validation mode.")

        if errors:
            result = result.merge(ValidationResult.fail(errors))
        return result


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "TIMESTAMP_FORMAT",
    "ContentBrief",
    "ContentDomain",
    "DirectorShot",
    "HookClass",
    "HookPackage",
    "HookVariant",
    "PipelineStage",
    "Platform",
    "PlatformVariant",
    "ProductionTier",
    "RetentionBeat",
    "RetentionMap",
    "ScoreDimension",
    "StoryBeat",
    "StoryBlueprint",
    "StoryMode",
    "TrendSignal",
    "UniquenessLayer",
    "UniquenessReport",
    "ValidationResult",
    "ViralScorecard",
    "generate_brief_id",
]


if __name__ == "__main__":
    brief = ContentBrief.create(
        domain=ContentDomain.DARK_MYSTERY,
        platforms=[Platform.TIKTOK, Platform.YOUTUBE_SHORTS],
    )

    brief.trend_context = TrendSignal(
        topic="The room that wasn't on the blueprint",
        velocity=78.0,
        saturation=34.0,
        virality_score=82.0,
        platform=Platform.TIKTOK,
        emotional_vector={"fear": 0.8, "curiosity": 0.9},
        platform_fit={"tiktok": 91.0, "youtube_shorts": 74.0},
    )

    brief.hook_package = HookPackage(
        variants=[
            HookVariant(
                variant_id="hook_1",
                hook_class=HookClass.INCOMPLETE_TRUTH,
                text="They found the room. They didn't find what was under the floor.",
                curiosity_gap_score=88.0,
                interrupt_power=84.0,
                specificity_score=79.0,
            )
        ],
        selected_variant_id="hook_1",
        best_hook_text="They found the room. They didn't find what was under the floor.",
        hook_class=HookClass.INCOMPLETE_TRUTH,
        composite_score=86.0,
    )

    validation = brief.validate()
    roundtrip = ContentBrief.from_dict(brief.to_dict())

    print("Brief ID:", brief.brief_id)
    print("Valid:", validation.is_valid)
    print("Roundtrip brief_id:", roundtrip.brief_id)
    print("Roundtrip valid:", roundtrip.validate().is_valid)
