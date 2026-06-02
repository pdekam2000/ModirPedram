"""
Phase 12J-D-B — Topic class visual grammar validator.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.engines.story_intelligence_engine import (
    StoryIntelligenceEngine,
    VisualOriginalityEngine,
)
from content_brain.engines.topic_class_grammar_engine import (
    GRAMMAR_VERSION,
    LEGACY_GENERAL_INVESTIGATION,
    TopicClassGrammarEngine,
)
from content_brain.schemas.content_brief import DirectorShot


def _check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return ok


def _resolve(topic: str, niche: str = "general") -> TopicClassGrammarEngine:
    engine = TopicClassGrammarEngine()
    engine.resolve_topic_class(topic, niche, {"niche": niche})
    return engine


def main() -> int:
    passed = 0
    total = 0

    def record(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, total
        total += 1
        if _check(name, ok, detail):
            passed += 1

    config_path = ROOT / "content_brain" / "config" / "topic_class_grammar_v1.json"
    record("grammar_config_exists", config_path.is_file())

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    classes = raw.get("classes") or {}
    record("grammar_config_has_11_classes", len(classes) >= 11, f"count={len(classes)}")

    required_classes = {
        "animal",
        "football",
        "mystery",
        "horror",
        "history",
        "science",
        "finance",
        "self_care",
        "travel",
        "technology",
        "general_investigation",
    }
    record("all_topic_classes_present", required_classes.issubset(set(classes.keys())))

    required_beats = {
        "HOOK_BEAT",
        "ESCALATION_BEAT",
        "PAYOFF_BEAT",
        "PATTERN_BREAK",
        "LOOP_SEED",
    }
    animal_beats = set((classes.get("animal") or {}).keys())
    record(
        "animal_required_beats",
        required_beats.issubset(animal_beats),
        f"keys={sorted(animal_beats)}",
    )

    dog = _resolve("why this dog behaves strangely")
    record("dog_resolves_animal", dog.resolved_topic_class == "animal", dog.resolution_source)

    cat = _resolve("cat worked and feels wrong")
    record("cat_resolves_animal", cat.resolved_topic_class == "animal", cat.resolution_source)

    fb = _resolve("VAR controversy in premier league football")
    record("football_resolves_football", fb.resolved_topic_class == "football", fb.resolution_source)

    hist = _resolve("forgotten archival letter from 1942")
    record("history_resolves_history", hist.resolved_topic_class == "history", hist.resolution_source)

    sci = _resolve("lab experiment with chemical reaction")
    record("science_resolves_science", sci.resolved_topic_class == "science", sci.resolution_source)

    fin = _resolve("stock market crash portfolio loss")
    record("finance_resolves_finance", fin.resolved_topic_class == "finance", fin.resolution_source)

    trav = _resolve("hidden city travel destination guide")
    record("travel_resolves_travel", trav.resolved_topic_class == "travel", trav.resolution_source)

    unknown = _resolve("xyzzy qwerty unknowntopic999")
    record(
        "unknown_resolves_general_investigation",
        unknown.resolved_topic_class == "general_investigation",
        unknown.resolution_source,
    )

    animal_hook = dog.get_grammar("animal", "HOOK_BEAT").get("camera", "")
    football_hook = fb.get_grammar("football", "HOOK_BEAT").get("camera", "")
    record(
        "animal_hook_differs_from_football_hook",
        animal_hook != football_hook,
        f"animal={animal_hook[:40]!r} football={football_hook[:40]!r}",
    )

    animal_esc = cat.get_grammar("animal", "ESCALATION_BEAT").get("camera", "")
    mystery_esc = _resolve("unsolved mystery cold case clue").get_grammar("mystery", "ESCALATION_BEAT").get(
        "camera", ""
    )
    record(
        "animal_escalation_differs_from_mystery_escalation",
        animal_esc != mystery_esc,
        f"animal={animal_esc[:40]!r} mystery={mystery_esc[:40]!r}",
    )

    legacy_hook = _resolve("unknown").get_grammar("general_investigation", "HOOK_BEAT")
    record(
        "general_investigation_hook_camera_legacy",
        legacy_hook.get("camera") == LEGACY_GENERAL_INVESTIGATION["HOOK_BEAT"]["camera"],
    )
    record(
        "general_investigation_escalation_camera_legacy",
        _resolve("unknown").get_grammar("general_investigation", "ESCALATION_BEAT").get("camera")
        == LEGACY_GENERAL_INVESTIGATION["ESCALATION_BEAT"]["camera"],
    )

    vis = VisualOriginalityEngine()
    vis._grammar_engine.resolve_topic_class("dog", "general", {"niche": "general"})
    record(
        "visual_engine_camera_delegates",
        "Eye-level" in vis._camera_for_beat("HOOK_BEAT")
        or "macro" not in vis._camera_for_beat("HOOK_BEAT").lower()
        or vis._camera_for_beat("HOOK_BEAT") != LEGACY_GENERAL_INVESTIGATION["HOOK_BEAT"]["camera"],
    )

    # schema_director_shots shape via minimal scene enrich path
    from content_brain.engines.story_intelligence_engine import NarrativeContext

    context = NarrativeContext(
        profile={"niche": "general"},
        topic="dog",
        hook="hook",
        hook_class="curiosity",
        niche="general",
        niche_label="General",
        story_mode="explainer",
        reveal_type="hidden_detail",
        loop_seed="loop",
        sensory_anchor="fur texture",
        topic_tokens=["dog"],
        semantic_clusters=[],
    )
    scenes = [
        {
            "scene_id": "scene_01",
            "beat_id": "HOOK_BEAT",
            "beat_role": "hook",
            "connects_from": "",
            "connects_to": "ESCALATION_BEAT",
        }
    ]
    enriched, _ = vis.enrich_scenes(scenes, context, ["topic-specific object in sharp focus"])
    meta = vis.get_visual_grammar_metadata()
    record("metadata_present", bool(meta.get("topic_class") and meta.get("beat_grammar_used")))
    record("metadata_topic_class_animal", meta.get("topic_class") == "animal")

    # DirectorShot field contract unchanged
    shot_fields = set(DirectorShot.__dataclass_fields__.keys())
    expected = {
        "clip_number",
        "duration_seconds",
        "prompt",
        "camera_shot",
        "camera_movement",
        "lighting",
        "pacing",
        "continuity_notes",
    }
    record("director_shot_schema_unchanged", expected.issubset(shot_fields))

    si_path = ROOT / "content_brain" / "engines" / "story_intelligence_engine.py"
    si_src = si_path.read_text(encoding="utf-8")
    record("story_intelligence_wires_grammar", "TopicClassGrammarEngine" in si_src)
    record("visual_grammar_metadata_payload", "visual_grammar_metadata" in si_src)

    runway_orch = ROOT / "orchestrators" / "runway_browser_orchestrator.py"
    record(
        "runway_orchestrator_unchanged",
        "topic_class_grammar" not in runway_orch.read_text(encoding="utf-8").lower(),
    )

    composer_validator = ROOT / "project_brain" / "validate_12j_c_runway_prompt_composer.py"
    if composer_validator.is_file():
        proc = subprocess.run(
            [sys.executable, str(composer_validator)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        composer_ok = proc.returncode == 0
        record("composer_validator_passes", composer_ok, proc.stdout[-200:] if not composer_ok else "")
    else:
        record("composer_validator_passes", False, "missing validator script")

    record("grammar_version_constant", GRAMMAR_VERSION == raw.get("grammar_version"))

    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
