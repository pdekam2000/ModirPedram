"""
Story Memory Engine — Phase 9B.

Persistent cross-video story/scene/visual memory for Story Intelligence.
JSON-backed; story_history.json is source of truth; other files are derived indexes.
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

GENERIC_VISUAL_PATTERNS = [
    "person looking shocked",
    "person shocked",
    "dark room",
    "walking alone",
    "generic b-roll",
    "cinematic b-roll",
    "slow motion walk",
    "talking head",
    "random footage",
]

STORE_VERSION = "story_memory_v1"
DEFAULT_MEMORY_DIR = Path("storage/content_brain/memory/story_intelligence")

RECENT_WINDOW = 30
LIFETIME_WINDOW = 200

MAX_RECORDS_PER_CHANNEL = 200
MAX_RECORDS_PER_NICHE = 300

STORY_HISTORY_FILE = "story_history.json"
SCENE_FINGERPRINTS_FILE = "scene_fingerprints.json"
VISUAL_FINGERPRINTS_FILE = "visual_fingerprints.json"
NARRATIVE_PATTERNS_FILE = "narrative_patterns.json"

VISUAL_FATIGUE_TOKENS = {
    "mirror",
    "hallway",
    "corridor",
    "radio",
    "signal",
    "dark room",
    "walking alone",
    "person shocked",
    "abandoned",
    "static",
}

MEMORY_DECISION_SAFE = "SAFE"
MEMORY_DECISION_WARNING = "WARNING"
MEMORY_DECISION_HIGH_RISK = "HIGH_RISK"

SUGGESTION_TEMPLATES: dict[str, str] = {
    "mirror": "Replace mirror motif with annotated document, screen capture, or texture evidence.",
    "hallway": "Shift pattern_break to exterior threshold or annotated floor plan.",
    "corridor": "Move setting from interior corridor to a topic-specific evidence location.",
    "radio": "Replace audio/radio motif with written log, timestamp artifact, or screen record.",
    "signal": "Swap signal motif for concrete physical evidence tied to the topic.",
    "dark room": "Use motivated practical lighting with a specific evidence object in frame.",
    "person shocked": "Show evidence reaction through object focus, not generic facial shock.",
    "twist_structure": "Switch reveal_type to the least-used twist in recent channel history.",
    "setting_cluster": "Shift environment to the least-used setting cluster for this channel.",
    "emotional_arc": "Flatten mid-section tension and spike payoff later in the arc.",
    "exact_story": "Change hook angle or story mode before reusing this narrative frame.",
    "scene_fingerprint": "Redesign the matching scene with a new subject and camera setup.",
}


def _now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fingerprint(text: str, length: int = 12) -> str:
    return md5(text.encode("utf-8")).hexdigest()[:length]


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return [token for token in cleaned.split() if len(token) >= 3]


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(intersection) / len(union)


def _classify_emotional_arc_type(emotional_arc: list[dict[str, Any]]) -> str:
    if not emotional_arc:
        return "unknown"

    intensities = [float(item.get("intensity", 0.0)) for item in emotional_arc]
    if len(intensities) < 2:
        return "single_beat"

    rise = intensities[-1] - intensities[0]
    mid = intensities[len(intensities) // 2]
    early_peak = intensities[0] >= max(intensities[1:]) if len(intensities) > 1 else False

    if early_peak and rise < 0:
        return "front_loaded_hook_decay"
    if any(
        intensities[index] > intensities[index - 1]
        and index + 1 < len(intensities)
        and intensities[index + 1] < intensities[index]
        for index in range(1, len(intensities) - 1)
    ):
        return "tension_release_rehook"
    if rise >= 0.15:
        return "escalation_peak_open_loop"
    if mid < intensities[-1] - 0.1:
        return "slow_burn_reversal"
    return "balanced_progression"


def _emotional_arc_signature(emotional_arc: list[dict[str, Any]]) -> str:
    targets = [str(item.get("emotion_target", "")) for item in emotional_arc if item.get("emotion_target")]
    return "→".join(targets) if targets else "unknown"


def _extract_visual_tokens(payload: dict[str, Any]) -> list[str]:
    tokens: set[str] = set()
    blueprint = payload.get("story_blueprint", {})
    for scene in blueprint.get("scene_plan", []):
        for field_name in ("visual_description", "subject", "environment", "action"):
            tokens.update(_tokenize(str(scene.get(field_name, ""))))
    for shot in blueprint.get("director_shots", []):
        for field_name in ("subject", "environment", "action", "mood"):
            tokens.update(_tokenize(str(shot.get(field_name, ""))))
    return sorted(tokens)


def _extract_setting_tokens(payload: dict[str, Any]) -> list[str]:
    settings: set[str] = set()
    for scene in payload.get("story_blueprint", {}).get("scene_plan", []):
        environment = str(scene.get("environment", "")).lower().strip()
        if environment:
            settings.add(environment)
        for token in _tokenize(environment):
            if token in {"hallway", "corridor", "room", "interior", "stadium", "monitor", "broadcast"}:
                settings.add(token)
    return sorted(settings)


def _camera_family(camera: str) -> str:
    lower = camera.lower()
    if "macro" in lower or "close" in lower:
        return "macro_evidence"
    if "push" in lower or "dolly" in lower:
        return "push_in"
    if "split" in lower or "whip" in lower:
        return "perspective_shift"
    if "pull" in lower:
        return "pull_back"
    return "standard_framing"


def _build_record_from_payload(
    payload: dict[str, Any],
    profile: dict[str, Any],
    brief_id: str = "",
    channel_id: str = "",
    topic: str = "",
) -> dict[str, Any]:
    blueprint = payload.get("story_blueprint", {})
    emotional_arc = blueprint.get("emotional_arc", [])
    twist = blueprint.get("twist_or_reveal", {})
    quality = blueprint.get("story_quality_score", {})

    scene_plan = blueprint.get("scene_plan", [])
    director_shots = blueprint.get("director_shots", [])

    return {
        "record_id": f"smem_{uuid.uuid4().hex[:10]}",
        "brief_id": brief_id,
        "channel_id": channel_id.strip(),
        "niche": str(profile.get("niche", "general")),
        "topic": (topic or str(blueprint.get("narrative_premise", "")))[:240],
        "story_signature": payload.get("story_signature", ""),
        "story_mode": payload.get("explainability", {}).get("story_mode", "")
        or profile.get("story_modes", {}).get("enabled_modes", ["storytime"])[0]
        if isinstance(profile.get("story_modes", {}).get("enabled_modes"), list)
        else "",
        "twist_or_reveal_type": twist.get("reveal_type", ""),
        "emotional_arc_type": _classify_emotional_arc_type(emotional_arc),
        "emotional_arc_signature": _emotional_arc_signature(emotional_arc),
        "scene_fingerprints": list(payload.get("scene_fingerprints", [])),
        "visual_fingerprints": list(payload.get("visual_fingerprints", [])),
        "visual_tokens": _extract_visual_tokens(payload),
        "setting_tokens": _extract_setting_tokens(payload),
        "director_shot_summaries": [
            {
                "shot_id": shot.get("shot_id", ""),
                "scene_id": shot.get("scene_id", ""),
                "subject": str(shot.get("subject", ""))[:120],
                "environment": str(shot.get("environment", ""))[:120],
                "mood": str(shot.get("mood", ""))[:60],
                "camera_family": _camera_family(str(shot.get("camera", ""))),
            }
            for shot in director_shots
        ],
        "quality_scores": {
            "composite": quality.get("composite", 0.0),
            "originality_score": quality.get("originality_score", 0.0),
            "scene_necessity_score": quality.get("scene_necessity_score", 0.0),
        },
        "repeated_risk_score_at_record": payload.get("repeated_risk_score", 0.0),
        "memory_decision_at_record": payload.get("memory", {}).get("memory_decision", MEMORY_DECISION_SAFE),
        "scene_count": len(scene_plan),
        "created_at": _now_timestamp(),
    }


class StoryMemoryStore:
    """JSON store with story_history as source of truth and derived indexes."""

    def __init__(self, memory_dir: str | Path = DEFAULT_MEMORY_DIR):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.memory_dir / STORY_HISTORY_FILE
        self.scene_index_path = self.memory_dir / SCENE_FINGERPRINTS_FILE
        self.visual_index_path = self.memory_dir / VISUAL_FINGERPRINTS_FILE
        self.narrative_index_path = self.memory_dir / NARRATIVE_PATTERNS_FILE

    def load_history(self) -> dict[str, Any]:
        return self._load_json(
            self.history_path,
            {"store_version": STORE_VERSION, "updated_at": "", "records": []},
        )

    def save_history(self, data: dict[str, Any]) -> None:
        data["store_version"] = STORE_VERSION
        data["updated_at"] = _now_timestamp()
        self._write_json(self.history_path, data)
        self.rebuild_indexes(data)

    def load_scene_index(self) -> dict[str, Any]:
        return self._load_json(
            self.scene_index_path,
            {"store_version": STORE_VERSION, "index": {}},
        )

    def load_visual_index(self) -> dict[str, Any]:
        return self._load_json(
            self.visual_index_path,
            {"store_version": STORE_VERSION, "token_frequency": {}, "fingerprint_hits": {}},
        )

    def load_narrative_index(self) -> dict[str, Any]:
        return self._load_json(
            self.narrative_index_path,
            {"store_version": STORE_VERSION, "channels": {}, "niches": {}},
        )

    def rebuild_indexes(self, history: dict[str, Any] | None = None) -> None:
        history = history or self.load_history()
        records = history.get("records", [])

        scene_index: dict[str, Any] = {}
        visual_index: dict[str, Any] = {
            "store_version": STORE_VERSION,
            "token_frequency": {},
            "fingerprint_hits": {},
        }
        narrative_index: dict[str, Any] = {
            "store_version": STORE_VERSION,
            "channels": {},
            "niches": {},
        }

        for record in records:
            record_id = record.get("record_id", "")
            channel_id = record.get("channel_id", "")
            niche = record.get("niche", "general")
            created_at = record.get("created_at", "")

            for scene_fp in record.get("scene_fingerprints", []):
                entry = scene_index.setdefault(
                    scene_fp,
                    {
                        "count": 0,
                        "last_seen_at": created_at,
                        "channel_ids": [],
                        "niches": [],
                        "record_ids": [],
                        "subject_hint": "",
                        "beat_role": "",
                    },
                )
                entry["count"] = int(entry.get("count", 0)) + 1
                entry["last_seen_at"] = created_at
                if channel_id and channel_id not in entry["channel_ids"]:
                    entry["channel_ids"].append(channel_id)
                if niche and niche not in entry["niches"]:
                    entry["niches"].append(niche)
                if record_id and record_id not in entry["record_ids"]:
                    entry["record_ids"].append(record_id)

            niche_tokens = visual_index["token_frequency"].setdefault(niche, {})
            for token in record.get("visual_tokens", []):
                token_entry = niche_tokens.setdefault(
                    token,
                    {"count": 0, "channels": [], "last_seen_at": created_at},
                )
                token_entry["count"] = int(token_entry.get("count", 0)) + 1
                token_entry["last_seen_at"] = created_at
                if channel_id and channel_id not in token_entry["channels"]:
                    token_entry["channels"].append(channel_id)

            for visual_fp in record.get("visual_fingerprints", []):
                fp_entry = visual_index["fingerprint_hits"].setdefault(
                    visual_fp,
                    {"count": 0, "last_seen_at": created_at, "record_ids": []},
                )
                fp_entry["count"] = int(fp_entry.get("count", 0)) + 1
                fp_entry["last_seen_at"] = created_at
                if record_id and record_id not in fp_entry["record_ids"]:
                    fp_entry["record_ids"].append(record_id)

            scope_key = channel_id or f"niche:{niche}"
            scope_bucket = "channels" if channel_id else "niches"
            scope_root = narrative_index[scope_bucket].setdefault(
                scope_key if scope_bucket == "channels" else niche,
                {
                    "twist_counts": {},
                    "emotional_arc_counts": {},
                    "setting_cluster_counts": {},
                    "last_updated_at": created_at,
                },
            )
            twist_type = record.get("twist_or_reveal_type", "unknown")
            arc_type = record.get("emotional_arc_type", "unknown")
            scope_root["twist_counts"][twist_type] = (
                int(scope_root["twist_counts"].get(twist_type, 0)) + 1
            )
            scope_root["emotional_arc_counts"][arc_type] = (
                int(scope_root["emotional_arc_counts"].get(arc_type, 0)) + 1
            )
            for setting in record.get("setting_tokens", []):
                scope_root["setting_cluster_counts"][setting] = (
                    int(scope_root["setting_cluster_counts"].get(setting, 0)) + 1
                )
            scope_root["last_updated_at"] = created_at

        self._write_json(
            self.scene_index_path,
            {"store_version": STORE_VERSION, "index": scene_index},
        )
        self._write_json(self.visual_index_path, visual_index)
        self._write_json(self.narrative_index_path, narrative_index)

    def get_records(
        self,
        channel_id: str = "",
        niche: str = "",
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        records = list(self.load_history().get("records", []))
        if channel_id:
            records = [item for item in records if item.get("channel_id") == channel_id]
        elif niche:
            records = [item for item in records if item.get("niche") == niche]
        if limit is not None:
            records = records[-limit:]
        return records

    def add_record(self, record: dict[str, Any]) -> dict[str, Any]:
        history = self.load_history()
        history.setdefault("records", []).append(record)
        self.cleanup(history)
        self.save_history(history)
        return record

    def cleanup(self, history: dict[str, Any] | None = None) -> int:
        history = history or self.load_history()
        records = list(history.get("records", []))
        if not records:
            return 0

        trimmed: list[dict[str, Any]] = []
        channel_counts: dict[str, int] = {}
        niche_counts: dict[str, int] = {}
        removed = 0

        for record in reversed(records):
            channel_id = record.get("channel_id", "")
            niche = record.get("niche", "general")
            keep = True

            if channel_id:
                channel_counts[channel_id] = channel_counts.get(channel_id, 0) + 1
                if channel_counts[channel_id] > MAX_RECORDS_PER_CHANNEL:
                    keep = False
            else:
                niche_counts[niche] = niche_counts.get(niche, 0) + 1
                if niche_counts[niche] > MAX_RECORDS_PER_NICHE:
                    keep = False

            if keep:
                trimmed.append(record)
            else:
                removed += 1

        history["records"] = list(reversed(trimmed))
        return removed

    def _load_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return dict(default)

        if not isinstance(payload, dict):
            return dict(default)
        return payload

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


@dataclass
class StoryMemoryComparisonResult:
    repeated_risk_score: float
    recent_repetition_score: float
    lifetime_repetition_score: float
    repeated_elements: list[dict[str, Any]]
    suggested_variations: list[str]
    memory_decision: str
    compare_failed: bool = False
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repeated_risk_score": self.repeated_risk_score,
            "recent_repetition_score": self.recent_repetition_score,
            "lifetime_repetition_score": self.lifetime_repetition_score,
            "repeated_elements": self.repeated_elements,
            "suggested_variations": self.suggested_variations,
            "memory_decision": self.memory_decision,
            "compare_failed": self.compare_failed,
            "reasoning": self.reasoning,
        }


class StoryMemoryEngine:
    """
    Compare and record Story Intelligence payloads against channel history.

    Usage:
        engine = StoryMemoryEngine()
        result = engine.compare(payload, profile, channel_id="...")
        if decision == PROCEED:
            engine.record(payload, profile, brief_id="...", channel_id="...")
    """

    def __init__(self, memory_dir: str | Path | None = None):
        self.store = StoryMemoryStore(memory_dir or DEFAULT_MEMORY_DIR)

    def compare(
        self,
        payload: dict[str, Any],
        profile: dict[str, Any],
        channel_id: str = "",
        recent_window: int = RECENT_WINDOW,
        lifetime_window: int = LIFETIME_WINDOW,
    ) -> StoryMemoryComparisonResult:
        try:
            niche = str(profile.get("niche", "general"))
            recent_records = self.store.get_records(
                channel_id=channel_id,
                niche="" if channel_id else niche,
                limit=recent_window,
            )
            lifetime_records = self.store.get_records(
                channel_id=channel_id,
                niche="" if channel_id else niche,
                limit=lifetime_window,
            )

            recent_score, recent_elements = self._score_against_records(payload, recent_records, recent_window)
            lifetime_score, lifetime_elements = self._score_against_records(
                payload,
                lifetime_records,
                lifetime_window,
            )

            repeated_elements = self._merge_elements(recent_elements, lifetime_elements)
            repeated_risk_score = round(max(recent_score, lifetime_score), 4)
            memory_decision = self._decide(repeated_risk_score, repeated_elements)

            suggestions = self._build_suggestions(repeated_elements, payload, recent_records)

            reasoning = (
                f"Story memory compared against {len(recent_records)} recent and "
                f"{len(lifetime_records)} lifetime records "
                f"(channel={channel_id or 'none'}, niche={niche})."
            )

            return StoryMemoryComparisonResult(
                repeated_risk_score=repeated_risk_score,
                recent_repetition_score=round(recent_score, 4),
                lifetime_repetition_score=round(lifetime_score, 4),
                repeated_elements=repeated_elements,
                suggested_variations=suggestions,
                memory_decision=memory_decision,
                compare_failed=False,
                reasoning=reasoning,
            )
        except Exception as exc:
            return StoryMemoryComparisonResult(
                repeated_risk_score=0.0,
                recent_repetition_score=0.0,
                lifetime_repetition_score=0.0,
                repeated_elements=[],
                suggested_variations=[],
                memory_decision=MEMORY_DECISION_SAFE,
                compare_failed=True,
                reasoning=f"Story memory compare failed safely: {exc}",
            )

    def record(
        self,
        payload: dict[str, Any],
        profile: dict[str, Any],
        brief_id: str = "",
        channel_id: str = "",
        topic: str = "",
    ) -> dict[str, Any] | None:
        try:
            record = _build_record_from_payload(
                payload, profile, brief_id, channel_id, topic=topic
            )
            return self.store.add_record(record)
        except Exception:
            return None

    def _score_against_records(
        self,
        payload: dict[str, Any],
        records: list[dict[str, Any]],
        window: int,
    ) -> tuple[float, list[dict[str, Any]]]:
        if not records:
            return 0.0, []

        elements: list[dict[str, Any]] = []
        story_signature = payload.get("story_signature", "")
        scene_fps = set(payload.get("scene_fingerprints", []))
        visual_fps = set(payload.get("visual_fingerprints", []))
        visual_tokens = set(_extract_visual_tokens(payload))
        setting_tokens = set(_extract_setting_tokens(payload))

        blueprint = payload.get("story_blueprint", {})
        emotional_arc = blueprint.get("emotional_arc", [])
        arc_signature = _emotional_arc_signature(emotional_arc)
        twist_type = blueprint.get("twist_or_reveal", {}).get("reveal_type", "")

        exact_story_hit = 0.0
        if story_signature and any(item.get("story_signature") == story_signature for item in records):
            exact_story_hit = 1.0
            elements.append(
                {
                    "type": "exact_story",
                    "element": story_signature,
                    "count_in_window": sum(
                        1 for item in records if item.get("story_signature") == story_signature
                    ),
                    "severity": "high",
                    "window": window,
                    "detail": "Exact story signature match in memory window.",
                }
            )

        scene_hits = 0
        for scene_fp in scene_fps:
            count = sum(1 for item in records if scene_fp in set(item.get("scene_fingerprints", [])))
            if count:
                scene_hits = max(scene_hits, count)
                elements.append(
                    {
                        "type": "scene_fingerprint",
                        "element": scene_fp,
                        "count_in_window": count,
                        "severity": "high" if count >= 2 else "medium",
                        "window": window,
                        "detail": f"Scene fingerprint seen {count} times in last {window} records.",
                    }
                )
        max_scene_hit_rate = min(1.0, scene_hits / max(len(records), 1))

        visual_fp_hits = 0
        for visual_fp in visual_fps:
            count = sum(
                1 for item in records if visual_fp in set(item.get("visual_fingerprints", []))
            )
            if count:
                visual_fp_hits = max(visual_fp_hits, count)
        visual_fp_rate = min(1.0, visual_fp_hits / max(len(records), 1))

        token_fatigue_scores: list[float] = []
        for token in visual_tokens:
            if token in VISUAL_FATIGUE_TOKENS or any(
                marker in token for marker in ("mirror", "hallway", "radio", "corridor")
            ):
                count = sum(1 for item in records if token in set(item.get("visual_tokens", [])))
                if count >= 2:
                    token_fatigue_scores.append(min(1.0, count / 5.0))
                    elements.append(
                        {
                            "type": "visual_token",
                            "element": token,
                            "count_in_window": count,
                            "severity": "high" if count >= 3 else "medium",
                            "window": window,
                            "detail": f"Visual token '{token}' appears in {count} prior videos.",
                        }
                    )
        visual_token_fatigue = max(token_fatigue_scores) if token_fatigue_scores else 0.0

        twist_count = sum(1 for item in records if item.get("twist_or_reveal_type") == twist_type) if twist_type else 0
        twist_repetition = min(1.0, twist_count / 5.0) if twist_type else 0.0
        if twist_count >= 3 and twist_type:
            elements.append(
                {
                    "type": "twist_structure",
                    "element": twist_type,
                    "count_in_window": twist_count,
                    "severity": "medium",
                    "window": window,
                    "detail": f"Reveal type '{twist_type}' used {twist_count} times in window.",
                }
            )

        setting_overlap = 0.0
        for setting in setting_tokens:
            count = sum(1 for item in records if setting in set(item.get("setting_tokens", [])))
            if count >= 2:
                setting_overlap = max(setting_overlap, min(1.0, count / 5.0))
                elements.append(
                    {
                        "type": "setting_cluster",
                        "element": setting,
                        "count_in_window": count,
                        "severity": "medium",
                        "window": window,
                        "detail": f"Setting '{setting}' repeated across {count} videos.",
                    }
                )

        arc_count = sum(
            1 for item in records if item.get("emotional_arc_signature") == arc_signature
        )
        emotional_arc_repeat = 1.0 if arc_count >= 3 and arc_signature != "unknown" else min(
            1.0, arc_count / 3.0
        )
        if arc_count >= 3 and arc_signature != "unknown":
            elements.append(
                {
                    "type": "emotional_arc",
                    "element": arc_signature,
                    "count_in_window": arc_count,
                    "severity": "medium",
                    "window": window,
                    "detail": f"Emotional arc signature repeated {arc_count} times.",
                }
            )

        for pattern in GENERIC_VISUAL_PATTERNS:
            if any(pattern in token for token in visual_tokens):
                elements.append(
                    {
                        "type": "generic_visual_pattern",
                        "element": pattern,
                        "count_in_window": 1,
                        "severity": "medium",
                        "window": window,
                        "detail": f"Generic visual pattern '{pattern}' detected in current blueprint.",
                    }
                )

        score = min(
            1.0,
            exact_story_hit * 0.35
            + max_scene_hit_rate * 0.25
            + max(visual_token_fatigue, visual_fp_rate) * 0.20
            + twist_repetition * 0.10
            + setting_overlap * 0.05
            + emotional_arc_repeat * 0.05,
        )
        return round(score, 4), elements

    def _merge_elements(
        self,
        recent: list[dict[str, Any]],
        lifetime: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for item in recent + lifetime:
            key = (item.get("type", ""), item.get("element", ""))
            existing = merged.get(key)
            if existing is None or item.get("count_in_window", 0) > existing.get("count_in_window", 0):
                merged[key] = dict(item)
        return list(merged.values())

    def _decide(self, repeated_risk_score: float, elements: list[dict[str, Any]]) -> str:
        if any(item.get("type") == "exact_story" for item in elements):
            return MEMORY_DECISION_HIGH_RISK
        if repeated_risk_score >= 0.55:
            return MEMORY_DECISION_HIGH_RISK
        if repeated_risk_score >= 0.25:
            return MEMORY_DECISION_WARNING
        if any(
            item.get("type") == "visual_token" and item.get("count_in_window", 0) >= 3
            for item in elements
        ):
            return MEMORY_DECISION_WARNING
        return MEMORY_DECISION_SAFE

    def _build_suggestions(
        self,
        elements: list[dict[str, Any]],
        payload: dict[str, Any],
        recent_records: list[dict[str, Any]],
    ) -> list[str]:
        suggestions: list[str] = []
        seen: set[str] = set()

        for element in elements:
            element_type = element.get("type", "")
            value = str(element.get("element", "")).lower()

            if element_type == "exact_story":
                suggestion = SUGGESTION_TEMPLATES["exact_story"]
            elif element_type == "scene_fingerprint":
                suggestion = SUGGESTION_TEMPLATES["scene_fingerprint"]
            elif element_type == "twist_structure":
                suggestion = SUGGESTION_TEMPLATES["twist_structure"]
            elif element_type == "setting_cluster":
                suggestion = SUGGESTION_TEMPLATES["setting_cluster"]
            elif element_type == "emotional_arc":
                suggestion = SUGGESTION_TEMPLATES["emotional_arc"]
            else:
                suggestion = ""
                for token, template in SUGGESTION_TEMPLATES.items():
                    if token in value:
                        suggestion = template
                        break

            if suggestion and suggestion not in seen:
                suggestions.append(suggestion)
                seen.add(suggestion)

        if not suggestions and recent_records:
            suggestions.append(
                "Current blueprint is memory-safe; preserve topic-specific visual anchors."
            )
        elif not suggestions:
            suggestions.append(
                "No prior story memory for this channel; establish a distinctive visual motif."
            )

        twist_type = payload.get("story_blueprint", {}).get("twist_or_reveal", {}).get("reveal_type", "")
        if twist_type and recent_records:
            twist_counts: dict[str, int] = {}
            for record in recent_records:
                key = record.get("twist_or_reveal_type", "unknown")
                twist_counts[key] = twist_counts.get(key, 0) + 1
            least_used = min(twist_counts, key=twist_counts.get, default="")
            if least_used and least_used != twist_type:
                suggestion = f"Consider switching reveal_type from '{twist_type}' to less-used '{least_used}'."
                if suggestion not in seen:
                    suggestions.append(suggestion)

        return suggestions[:6]


def _run_smoke_test() -> None:
    import tempfile

    from content_brain.engines.story_intelligence_engine import StoryIntelligenceEngine
    from content_brain.engines.story_architecture_engine import StoryArchitectureEngine
    from content_brain.engines.hook_engineering_engine import HookEngineeringEngine
    from content_brain.engines.video_format_planner import VideoFormatPlanner
    from content_brain.profiles.profile_loader import ProfileLoader
    from content_brain.schemas.content_brief import Platform

    with tempfile.TemporaryDirectory() as tmp_dir:
        memory_dir = Path(tmp_dir) / "story_intelligence"
        memory_engine = StoryMemoryEngine(memory_dir=memory_dir)
        loader = ProfileLoader()
        profile = loader.resolve(niche="dark_mystery")
        trend = __import__(
            "content_brain.schemas.content_brief",
            fromlist=["TrendSignal"],
        ).TrendSignal(
            topic="the room that was not on the blueprint",
            velocity=80.0,
            saturation=30.0,
            virality_score=82.0,
            platform=Platform.TIKTOK,
            source="smoke_test",
        )
        hook_package = HookEngineeringEngine().generate_hook_package(
            profile=profile,
            topic=trend.topic,
            platforms=[Platform.TIKTOK],
        )
        story_blueprint = StoryArchitectureEngine().build_blueprint(profile, trend, hook_package)
        format_plan = VideoFormatPlanner().plan(
            profile=profile,
            platform=Platform.TIKTOK,
            user_duration_seconds=30,
            provider_name="hailuo",
        )
        si_payload = StoryIntelligenceEngine().enhance(
            profile=profile,
            trend_signal=trend,
            hook_package=hook_package,
            story_blueprint=story_blueprint,
            video_format_plan=format_plan,
        )

        print("\n" + "=" * 72)
        print("STORY MEMORY ENGINE SMOKE TEST")
        print("=" * 72)

        first = memory_engine.compare(si_payload, profile, channel_id="test_channel")
        print("\n[1] EMPTY MEMORY COMPARE")
        print("decision:", first.memory_decision)
        print("recent:", first.recent_repetition_score)
        print("lifetime:", first.lifetime_repetition_score)
        print("repeated_risk_score:", first.repeated_risk_score)

        recorded = memory_engine.record(
            si_payload,
            profile,
            brief_id="brief_smoke_1",
            channel_id="test_channel",
        )
        print("\n[2] RECORDED")
        print("record_id:", recorded.get("record_id") if recorded else None)
        print("story_signature:", recorded.get("story_signature") if recorded else None)

        second = memory_engine.compare(si_payload, profile, channel_id="test_channel")
        print("\n[3] DUPLICATE COMPARE")
        print("decision:", second.memory_decision)
        print("recent:", second.recent_repetition_score)
        print("lifetime:", second.lifetime_repetition_score)
        print("repeated_risk_score:", second.repeated_risk_score)
        print("repeated_elements:", json.dumps(second.repeated_elements[:3], indent=2))
        print("suggestions:", second.suggested_variations[:2])

        store = StoryMemoryStore(memory_dir)
        print("\n[4] STORAGE FILES")
        for name in (
            STORY_HISTORY_FILE,
            SCENE_FINGERPRINTS_FILE,
            VISUAL_FINGERPRINTS_FILE,
            NARRATIVE_PATTERNS_FILE,
        ):
            path = memory_dir / name
            print(f"  {name}: exists={path.exists()} bytes={path.stat().st_size if path.exists() else 0}")

        history = store.load_history()
        print("\n[5] SAMPLE HISTORY RECORD KEYS")
        if history.get("records"):
            print(json.dumps(list(history["records"][0].keys()), indent=2))

        print("\n[6] INDEX COUNTS")
        print("scene fingerprints:", len(store.load_scene_index().get("index", {})))
        print("visual tokens:", len(store.load_visual_index().get("token_frequency", {}).get("dark_mystery", {})))
        print("narrative channels:", len(store.load_narrative_index().get("channels", {})))


if __name__ == "__main__":
    _run_smoke_test()
