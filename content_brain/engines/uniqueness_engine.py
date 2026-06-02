"""
Uniqueness Engine V1 for the Viral Content Brain.

Prevents repetitive, generic, or too-similar content before production.
Uses JSON-backed memory only (no external DB in V1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import md5
from pathlib import Path
import json
import re
import uuid
from typing import Any, Optional

from content_brain.schemas.content_brief import (
    HookClass,
    HookPackage,
    StoryBlueprint,
    StoryMode,
    TrendSignal,
    UniquenessLayer,
    UniquenessReport,
)


DEFAULT_MEMORY_PATH = Path("storage/content_brain/memory/uniqueness/content_history.json")

VAGUE_WORDS = {
    "something",
    "someone",
    "anything",
    "everything",
    "very",
    "really",
    "interesting",
    "amazing",
    "incredible",
    "stuff",
    "things",
}


@dataclass
class ContentFingerprint:
    niche: str
    topic: str
    hook_text: str
    hook_class: str
    story_mode: str
    reveal_type: str
    loop_seed: str
    sensory_anchor: str
    beat_sequence: list[str]
    mechanic_sequence: list[str]
    topic_tokens: list[str] = field(default_factory=list)
    hook_fingerprint: str = ""
    beat_fingerprint: str = ""
    twist_fingerprint: str = ""

    @classmethod
    def from_inputs(
        cls,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
    ) -> ContentFingerprint:
        hook_text = hook_package.best_hook_text.strip()
        if not hook_text and hook_package.variants:
            hook_text = hook_package.variants[0].text

        hook_class = hook_package.hook_class
        if hook_class is None and hook_package.variants:
            hook_class = hook_package.variants[0].hook_class

        beat_sequence = [_normalize_beat_id(beat.beat_id) for beat in story_blueprint.beats]
        mechanic_sequence = [beat.retention_mechanic or "unknown" for beat in story_blueprint.beats]
        topic = trend_signal.topic.strip()

        fingerprint = cls(
            niche=str(profile.get("niche", "general")),
            topic=topic,
            hook_text=hook_text,
            hook_class=hook_class.value if hook_class else "unknown",
            story_mode=story_blueprint.story_mode.value,
            reveal_type=story_blueprint.reveal_type,
            loop_seed=story_blueprint.loop_seed,
            sensory_anchor=story_blueprint.sensory_anchor,
            beat_sequence=beat_sequence,
            mechanic_sequence=mechanic_sequence,
            topic_tokens=_tokenize(topic),
        )
        fingerprint.hook_fingerprint = build_hook_fingerprint(
            fingerprint.hook_class,
            fingerprint.hook_text,
        )
        fingerprint.beat_fingerprint = build_beat_fingerprint(
            beat_sequence,
            mechanic_sequence,
        )
        fingerprint.twist_fingerprint = build_twist_fingerprint(
            fingerprint.reveal_type,
            fingerprint.loop_seed,
        )
        return fingerprint

    def to_record(self) -> dict[str, Any]:
        return {
            "record_id": f"uniq_{uuid.uuid4().hex[:10]}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "niche": self.niche,
            "topic": self.topic,
            "hook_text": self.hook_text,
            "hook_class": self.hook_class,
            "story_mode": self.story_mode,
            "reveal_type": self.reveal_type,
            "loop_seed": self.loop_seed,
            "sensory_anchor": self.sensory_anchor,
            "beat_sequence": self.beat_sequence,
            "mechanic_sequence": self.mechanic_sequence,
            "topic_tokens": self.topic_tokens,
            "hook_fingerprint": self.hook_fingerprint,
            "beat_fingerprint": self.beat_fingerprint,
            "twist_fingerprint": self.twist_fingerprint,
        }


@dataclass
class UniquenessEvaluationResult:
    report: UniquenessReport
    fingerprint: ContentFingerprint
    failed_layers: list[str]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "fingerprint": self.fingerprint.to_record(),
            "failed_layers": self.failed_layers,
            "reasoning": self.reasoning,
        }


class UniquenessMemoryStore:
    """JSON-backed store for prior content fingerprints."""

    def __init__(self, memory_path: str | Path = DEFAULT_MEMORY_PATH):
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self.load()

    def load(self) -> dict[str, Any]:
        if not self.memory_path.exists():
            return {"records": []}

        try:
            payload = json.loads(self.memory_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"records": []}

        if not isinstance(payload, dict):
            return {"records": []}

        payload.setdefault("records", [])
        return payload

    def save(self) -> None:
        self.memory_path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_records(
        self,
        niche: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        records = list(self.data.get("records", []))
        if niche:
            records = [item for item in records if item.get("niche") == niche]
        if limit is not None:
            records = records[-limit:]
        return records

    def add_record(self, record: dict[str, Any]) -> None:
        self.data.setdefault("records", []).append(record)
        self.save()


class UniquenessEngine:
    """
    Evaluate content uniqueness against profile rules and JSON memory.

    Usage:
        engine = UniquenessEngine()
        result = engine.evaluate(profile, trend, hooks, story)
        if result.report.passed:
            engine.record(result.fingerprint)
    """

    LAYER_DIRECTIVE_MAP = {
        "topic_similarity": "topic_collision",
        "hook_fingerprint": "hook_collision",
        "beat_sequence_fingerprint": "beat_collision",
        "twist_type_collision": "twist_collision",
        "generic_pattern_detection": "generic_pattern_hit",
        "niche_banned_patterns": "generic_pattern_hit",
    }

    def __init__(self, memory_path: str | Path | None = None):
        path = memory_path or DEFAULT_MEMORY_PATH
        self.memory = UniquenessMemoryStore(path)

    def evaluate(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
    ) -> UniquenessEvaluationResult:
        fingerprint = ContentFingerprint.from_inputs(
            profile=profile,
            trend_signal=trend_signal,
            hook_package=hook_package,
            story_blueprint=story_blueprint,
        )
        uniqueness_rules = profile.get("uniqueness_rules", {})
        layer_configs = uniqueness_rules.get("layers", [])
        directives = uniqueness_rules.get("regeneration_directives", {})
        gate_minimum = float(uniqueness_rules.get("uniqueness_gate_minimum_score", 65))

        layers: list[UniquenessLayer] = []
        failed_layers: list[str] = []

        for config in layer_configs:
            layer = self._evaluate_config_layer(config, fingerprint, profile)
            layers.append(layer)
            if not layer.passed:
                failed_layers.append(layer.layer_name)

        twist_layer = self._evaluate_twist_collision(fingerprint, profile)
        layers.append(twist_layer)
        if not twist_layer.passed:
            failed_layers.append(twist_layer.layer_name)

        niche_layer = self._evaluate_niche_banned_patterns(fingerprint, profile)
        layers.append(niche_layer)
        if not niche_layer.passed:
            failed_layers.append(niche_layer.layer_name)

        max_similarity = max((layer.similarity_score for layer in layers), default=0.0)
        uniqueness_score = round(max(0.0, 100.0 - (max_similarity * 100.0)), 2)

        passed = (
            not failed_layers
            and uniqueness_score >= gate_minimum
        )

        regeneration_directive = ""
        if not passed:
            regeneration_directive = self._build_regeneration_directive(
                failed_layers,
                directives,
            )

        report = UniquenessReport(
            passed=passed,
            layers=layers,
            max_similarity=round(max_similarity, 4),
            uniqueness_score=uniqueness_score,
            regeneration_directive=regeneration_directive,
        )

        reasoning = (
            f"Uniqueness {'passed' if passed else 'failed'} for niche "
            f"{fingerprint.niche} with score {uniqueness_score}. "
            f"Max similarity {max_similarity:.4f}."
        )

        return UniquenessEvaluationResult(
            report=report,
            fingerprint=fingerprint,
            failed_layers=failed_layers,
            reasoning=reasoning,
        )

    def record(self, fingerprint: ContentFingerprint) -> dict[str, Any]:
        record = fingerprint.to_record()
        self.memory.add_record(record)
        return record

    def evaluate_and_record_if_passed(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
    ) -> UniquenessEvaluationResult:
        result = self.evaluate(profile, trend_signal, hook_package, story_blueprint)
        if result.report.passed:
            self.record(result.fingerprint)
        return result

    def _evaluate_config_layer(
        self,
        config: dict[str, Any],
        fingerprint: ContentFingerprint,
        profile: dict[str, Any],
    ) -> UniquenessLayer:
        layer_name = str(config.get("layer_name", "unknown"))
        threshold = float(config.get("threshold", 0.72))
        lookback = int(config.get("lookback_count", 50))
        method = str(config.get("method", ""))

        if layer_name == "generic_pattern_detection":
            return self._evaluate_generic_patterns(fingerprint, profile, threshold)

        records = self.memory.get_records(niche=fingerprint.niche, limit=lookback)
        if not records:
            records = self.memory.get_records(limit=lookback)

        if method == "normalized_topic_jaccard":
            similarity = max_topic_similarity(fingerprint, records)
            detail = f"Compared topic against {len(records)} prior records."
        elif method == "hook_class_plus_structure_hash":
            similarity = max_hook_similarity(fingerprint, records)
            detail = f"Compared hook fingerprint against {len(records)} prior records."
        elif method == "story_beat_sequence_hash":
            similarity = max_beat_similarity(fingerprint, records)
            detail = f"Compared beat sequence against {len(records)} prior records."
        else:
            similarity = 0.0
            detail = f"Unknown method '{method}'."

        return UniquenessLayer(
            layer_name=layer_name,
            similarity_score=round(similarity, 4),
            threshold=threshold,
            passed=similarity <= threshold,
            detail=detail,
        )

    def _evaluate_generic_patterns(
        self,
        fingerprint: ContentFingerprint,
        profile: dict[str, Any],
        threshold: float,
    ) -> UniquenessLayer:
        del threshold
        combined_text = self._collect_text_corpus(fingerprint, story_text_only=False)
        hits = scan_generic_patterns(combined_text, profile)

        similarity = 1.0 if hits else 0.0
        detail = "No generic patterns detected."
        if hits:
            detail = "Generic pattern hits: " + "; ".join(hits[:5])

        return UniquenessLayer(
            layer_name="generic_pattern_detection",
            similarity_score=similarity,
            threshold=0.0,
            passed=similarity <= 0.0,
            detail=detail,
        )

    def _evaluate_twist_collision(
        self,
        fingerprint: ContentFingerprint,
        profile: dict[str, Any],
    ) -> UniquenessLayer:
        threshold = 0.65
        for config in profile.get("uniqueness_rules", {}).get("layers", []):
            if config.get("layer_name") == "twist_type_collision":
                threshold = float(config.get("threshold", threshold))
                break

        lookback = 10
        records = self.memory.get_records(niche=fingerprint.niche, limit=lookback)
        similarity = max_twist_similarity(fingerprint, records)

        return UniquenessLayer(
            layer_name="twist_type_collision",
            similarity_score=round(similarity, 4),
            threshold=threshold,
            passed=similarity <= threshold,
            detail=f"Compared reveal/loop fingerprint against {len(records)} prior records.",
        )

    def _evaluate_niche_banned_patterns(
        self,
        fingerprint: ContentFingerprint,
        profile: dict[str, Any],
    ) -> UniquenessLayer:
        banned = profile.get("banned_generic_patterns", {}).get("banned_phrases", [])
        combined_text = self._collect_text_corpus(fingerprint, story_text_only=False).lower()

        hits = [phrase for phrase in banned if phrase.lower() in combined_text]
        similarity = 1.0 if hits else 0.0

        return UniquenessLayer(
            layer_name="niche_banned_patterns",
            similarity_score=similarity,
            threshold=0.0,
            passed=similarity <= 0.0,
            detail=(
                "No niche banned phrases detected."
                if not hits
                else "Banned phrase hits: " + "; ".join(hits[:5])
            ),
        )

    def _collect_text_corpus(
        self,
        fingerprint: ContentFingerprint,
        story_text_only: bool = False,
    ) -> str:
        parts = [
            fingerprint.topic,
            fingerprint.hook_text,
            fingerprint.loop_seed,
            fingerprint.sensory_anchor,
        ]
        if not story_text_only:
            parts.extend(fingerprint.beat_sequence)
        return " ".join(part for part in parts if part).lower()

    def _build_regeneration_directive(
        self,
        failed_layers: list[str],
        directives: dict[str, str],
    ) -> str:
        if not failed_layers:
            return ""

        priority = [
            "generic_pattern_detection",
            "niche_banned_patterns",
            "topic_similarity",
            "hook_fingerprint",
            "beat_sequence_fingerprint",
            "twist_type_collision",
        ]
        for layer_name in priority:
            if layer_name in failed_layers:
                directive_key = self.LAYER_DIRECTIVE_MAP.get(layer_name, "generic_pattern_hit")
                return directives.get(
                    directive_key,
                    "Rewrite with a new angle, hook structure, or story beat sequence.",
                )

        primary = failed_layers[0]
        directive_key = self.LAYER_DIRECTIVE_MAP.get(primary, "generic_pattern_hit")
        return directives.get(
            directive_key,
            "Rewrite with a new angle, hook structure, or story beat sequence.",
        )


def build_hook_fingerprint(hook_class: str, hook_text: str) -> str:
    tokens = _tokenize(hook_text)
    structure = " ".join(tokens[:8])
    digest = md5(structure.encode("utf-8")).hexdigest()[:10]
    return f"{hook_class}:{digest}"


def build_beat_fingerprint(
    beat_sequence: list[str],
    mechanic_sequence: list[str],
) -> str:
    payload = "|".join(
        f"{beat}:{mechanic}"
        for beat, mechanic in zip(beat_sequence, mechanic_sequence)
    )
    return md5(payload.encode("utf-8")).hexdigest()[:12]


def build_twist_fingerprint(reveal_type: str, loop_seed: str) -> str:
    payload = f"{reveal_type}|{_normalize_text(loop_seed)}"
    return md5(payload.encode("utf-8")).hexdigest()[:12]


def max_topic_similarity(
    fingerprint: ContentFingerprint,
    records: list[dict[str, Any]],
) -> float:
    if not records:
        return 0.0

    current = set(fingerprint.topic_tokens)
    max_score = 0.0
    for record in records:
        prior_tokens = set(record.get("topic_tokens") or _tokenize(record.get("topic", "")))
        max_score = max(max_score, jaccard_similarity(current, prior_tokens))
    return max_score


def max_hook_similarity(
    fingerprint: ContentFingerprint,
    records: list[dict[str, Any]],
) -> float:
    if not records:
        return 0.0

    max_score = 0.0
    current_tokens = set(_tokenize(fingerprint.hook_text))

    for record in records:
        class_match = 1.0 if record.get("hook_class") == fingerprint.hook_class else 0.0
        if record.get("hook_fingerprint") == fingerprint.hook_fingerprint:
            max_score = max(max_score, 1.0)
            continue

        prior_tokens = set(_tokenize(record.get("hook_text", "")))
        text_sim = jaccard_similarity(current_tokens, prior_tokens)
        combined = (class_match * 0.35) + (text_sim * 0.65)
        max_score = max(max_score, combined)

    return max_score


def max_beat_similarity(
    fingerprint: ContentFingerprint,
    records: list[dict[str, Any]],
) -> float:
    if not records:
        return 0.0

    max_score = 0.0
    for record in records:
        if record.get("beat_fingerprint") == fingerprint.beat_fingerprint:
            max_score = max(max_score, 1.0)
            continue

        prior_beats = record.get("beat_sequence", [])
        prior_mechanics = record.get("mechanic_sequence", [])
        sequence_sim = sequence_similarity(fingerprint.beat_sequence, prior_beats)
        mechanic_sim = sequence_similarity(fingerprint.mechanic_sequence, prior_mechanics)
        combined = (sequence_sim * 0.6) + (mechanic_sim * 0.4)
        max_score = max(max_score, combined)

    return max_score


def max_twist_similarity(
    fingerprint: ContentFingerprint,
    records: list[dict[str, Any]],
) -> float:
    if not records:
        return 0.0

    max_score = 0.0
    for record in records:
        if record.get("twist_fingerprint") == fingerprint.twist_fingerprint:
            max_score = max(max_score, 1.0)
            continue

        reveal_match = 1.0 if record.get("reveal_type") == fingerprint.reveal_type else 0.0
        loop_sim = jaccard_similarity(
            set(_tokenize(fingerprint.loop_seed)),
            set(_tokenize(record.get("loop_seed", ""))),
        )
        combined = (reveal_match * 0.55) + (loop_sim * 0.45)
        max_score = max(max_score, combined)

    return max_score


def scan_generic_patterns(text: str, profile: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    lower = text.lower()
    banned = profile.get("banned_generic_patterns", {})

    for phrase in banned.get("banned_phrases", []):
        if phrase.lower() in lower:
            hits.append(f"banned_phrase:{phrase}")

    for pattern in banned.get("ai_tell_patterns", []):
        tokens = _tokenize(pattern)
        if tokens and all(token in lower for token in tokens[:2]):
            hits.append(f"ai_tell:{pattern}")

    vague_count = sum(1 for word in VAGUE_WORDS if f" {word} " in f" {lower} ")
    if vague_count >= 3:
        hits.append("ai_tell:too_many_vague_words")

    tokens = _tokenize(lower)
    has_number = any(re.search(r"\d", token) for token in tokens)
    has_specific_word = any(len(token) >= 5 for token in tokens)
    if not has_number and not has_specific_word:
        hits.append("missing_concrete_anchor")

    return hits


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(intersection) / len(union)


def sequence_similarity(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    matches = sum(1 for item in left if item in right)
    return matches / max(len(left), len(right))


def _tokenize(text: str) -> list[str]:
    cleaned = _normalize_text(text)
    return [token for token in cleaned.split() if token]


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_beat_id(beat_id: str) -> str:
    normalized = beat_id.upper().replace("STORY_", "")
    if not normalized.endswith("_BEAT") and normalized not in {"LOOP_SEED", "PATTERN_BREAK"}:
        if normalized.endswith("_BEAT") is False and normalized:
            return f"{normalized}_BEAT"
    return normalized


__all__ = [
    "ContentFingerprint",
    "UniquenessEngine",
    "UniquenessEvaluationResult",
    "UniquenessMemoryStore",
    "DEFAULT_MEMORY_PATH",
]


if __name__ == "__main__":
    import tempfile

    from content_brain.profiles.profile_loader import ProfileLoader
    from content_brain.schemas.content_brief import (
        HookClass,
        HookVariant,
        Platform,
        StoryBeat,
        TrendSignal,
    )

    loader = ProfileLoader()
    profile = loader.resolve(niche="football")

    trend = TrendSignal(
        topic="VAR decisions in the 89th minute changed the result",
        velocity=80.0,
        saturation=35.0,
        virality_score=78.0,
        platform=Platform.TIKTOK,
        source="manual_seed",
    )
    hooks = HookPackage(
        variants=[
            HookVariant(
                variant_id="hook_1",
                hook_class=HookClass.INCOMPLETE_TRUTH,
                text="Everyone saw the goal. Nobody checked the replay angle in the 89th minute.",
                curiosity_gap_score=82.0,
                interrupt_power=80.0,
                specificity_score=78.0,
            )
        ],
        selected_variant_id="hook_1",
        best_hook_text="Everyone saw the goal. Nobody checked the replay angle in the 89th minute.",
        hook_class=HookClass.INCOMPLETE_TRUTH,
        composite_score=80.0,
    )
    story = StoryBlueprint(
        story_mode=StoryMode.CONFESSION,
        beats=[
            StoryBeat(
                beat_id="HOOK_BEAT",
                act=1,
                start_second=0.0,
                end_second=3.0,
                description="PURPOSE: Hook | NARRATION: Replay angle matters | VISUAL: Monitor close-up",
                emotional_tone="hook (0.90)",
                retention_mechanic="pattern_interrupt",
            ),
            StoryBeat(
                beat_id="PAYOFF_BEAT",
                act=3,
                start_second=18.0,
                end_second=25.0,
                description="PURPOSE: Payoff | NARRATION: One frame line decides it | VISUAL: Freeze frame",
                emotional_tone="payoff (0.92)",
                retention_mechanic="peak_moment",
            ),
        ],
        reveal_type="comparison_reveal",
        loop_seed="Was the monitor angle the one broadcast used?",
        total_duration_seconds=30,
        sensory_anchor="Stadium monitor glow on the referee's face",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        memory_path = Path(tmp_dir) / "content_history.json"
        engine = UniquenessEngine(memory_path=memory_path)

        first = engine.evaluate(profile, trend, hooks, story)
        print("\n" + "=" * 72)
        print("NON-DUPLICATE (empty memory)")
        print("PASSED:", first.report.passed)
        print("SCORE:", first.report.uniqueness_score)
        print("VALID:", first.report.validate().is_valid)

        engine.record(first.fingerprint)

        duplicate = engine.evaluate(profile, trend, hooks, story)
        print("\n" + "=" * 72)
        print("DUPLICATE (same content in memory)")
        print("PASSED:", duplicate.report.passed)
        print("MAX SIM:", duplicate.report.max_similarity)
        print("DIRECTIVE:", duplicate.report.regeneration_directive)

        generic_hooks = HookPackage(
            variants=[
                HookVariant(
                    variant_id="hook_bad",
                    hook_class=HookClass.OPEN_LOOP_SEED,
                    text="You won't believe what happened next in football.",
                    curiosity_gap_score=40.0,
                    interrupt_power=40.0,
                    specificity_score=30.0,
                )
            ],
            selected_variant_id="hook_bad",
            best_hook_text="You won't believe what happened next in football.",
            hook_class=HookClass.OPEN_LOOP_SEED,
            composite_score=35.0,
        )
        generic = engine.evaluate(profile, trend, generic_hooks, story)
        print("\n" + "=" * 72)
        print("GENERIC PHRASE CASE")
        print("PASSED:", generic.report.passed)
        print("FAILED LAYERS:", generic.failed_layers)
        print("DIRECTIVE:", generic.report.regeneration_directive)
