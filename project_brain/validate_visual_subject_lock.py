"""Phase DIRECTOR-3 — Visual Subject Lock validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.director.director_models import CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT
from content_brain.director.director_pipeline import build_director_layer
from content_brain.director.prompt_critic import critique_prompts
from content_brain.director.visual_subject_lock import extract_visual_subject_lock
from content_brain.execution.runway_prompt_builder import build_continuity_prompts

SCORPION_TOPIC = "scorpion"
SCORPION_BRIEF = {
    "main_character": "Arachnologist",
    "logline": "A black scorpion specimen reveals survival secrets to an arachnologist.",
    "topic_story_detail": {"subject": "Scorpion", "objects": ["black scorpion specimen"]},
}


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _run(rel: str) -> None:
    script = ROOT / rel
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-240:])


def test_scorpion_lock_not_arachnologist() -> None:
    lock = extract_visual_subject_lock(topic=SCORPION_TOPIC, story_brief=SCORPION_BRIEF)
    _pass(
        "scorpion_lock_primary_subject",
        "scorpion" in lock.primary_visual_subject.lower(),
        lock.primary_visual_subject,
    )
    _pass(
        "scorpion_lock_not_arachnologist",
        lock.primary_visual_subject.lower() != "arachnologist",
        lock.primary_visual_subject,
    )
    _pass("scorpion_has_features", len(lock.required_visible_features) >= 3, str(len(lock.required_visible_features)))
    _pass("scorpion_forbids_spider", "spider" in lock.forbidden_confusions)


def test_scorpion_prompt_builder() -> None:
    bundle = build_continuity_prompts(
        SCORPION_TOPIC,
        clip_count=3,
        auto_story_brief=True,
        auto_director=True,
        director_dry_run=True,
        character="Arachnologist",
    )
    starter = bundle.starter_image_prompt.lower()
    _pass("starter_foregrounds_scorpion", "scorpion" in starter, starter[:180])
    _pass(
        "starter_not_arachnologist_primary",
        starter.find("scorpion") < starter.find("arachnologist") if "arachnologist" in starter else True,
        starter[:180],
    )
    for index, prompt in enumerate(bundle.clip_prompts, start=1):
        lowered = prompt.lower()
        _pass(f"clip_{index}_mentions_scorpion", "scorpion" in lowered, lowered[:160])
        _pass(
            f"clip_{index}_subject_identity_scorpion",
            "subject identity:" in lowered and "scorpion" in lowered.split("subject identity:", 1)[1][:120],
            lowered[:180],
        )
    _pass("bundle_has_visual_subject_lock", bundle.visual_subject_lock is not None)
    negatives = bundle.visual_subject_lock.strict_negative_fragment().lower() if bundle.visual_subject_lock else ""
    _pass("negatives_include_spider", "no spider" in negatives or "spider" in negatives, negatives)


def test_human_presenter_secondary() -> None:
    bundle = build_continuity_prompts(
        SCORPION_TOPIC,
        clip_count=2,
        auto_story_brief=True,
        auto_director=True,
        director_dry_run=True,
        character="Arachnologist",
    )
    combined = " ".join([bundle.starter_image_prompt, *bundle.clip_prompts]).lower()
    _pass("human_role_secondary", "human role:" in combined or "observer" in combined, combined[:220])
    _pass(
        "human_not_primary_subject_identity",
        "subject identity: arachnologist" not in combined,
        combined[:220],
    )


def test_topic_forbidden_confusions() -> None:
    snake = extract_visual_subject_lock(topic="snake")
    ant = extract_visual_subject_lock(topic="ants")
    _pass("snake_forbids_lizard", "lizard" in snake.forbidden_confusions)
    _pass("snake_forbids_worm", "worm" in snake.forbidden_confusions)
    _pass("snake_forbids_eel", "eel" in snake.forbidden_confusions)
    _pass("ant_forbids_termite", "termite" in ant.forbidden_confusions)
    _pass("ant_forbids_beetle", "beetle" in ant.forbidden_confusions)
    _pass("ant_forbids_spider", "spider" in ant.forbidden_confusions)


def test_director_metadata_and_critic() -> None:
    director = build_director_layer(topic=SCORPION_TOPIC, story_brief=SCORPION_BRIEF, clip_count=3, dry_run=True)
    payload = director.to_dict()
    _pass("director_stores_visual_subject_lock", "visual_subject_lock" in payload)
    lock = payload.get("visual_subject_lock") or {}
    _pass("director_lock_scorpion", "scorpion" in str(lock.get("primary_visual_subject", "")).lower())

    bad_starter = "Subject: Arachnologist in lab."
    bad_clips = [
        "Clip 1. Subject identity: Arachnologist. Location: lab.",
        "Clip 2. Subject identity: Arachnologist. Location: lab.",
        "Clip 3. Subject identity: Arachnologist. Location: lab.",
    ]
    report, _ = critique_prompts(
        topic=SCORPION_TOPIC,
        starter_image_prompt=bad_starter,
        clip_prompts=bad_clips,
        story_brief=SCORPION_BRIEF,
        dry_run=True,
    )
    _pass(
        "critic_rejects_missing_visual_subject",
        CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT in report.issues,
        str(report.issues),
    )
    _pass("critic_has_visual_subject_score", hasattr(report, "visual_subject_consistency_score"))


def test_runway_automation_untouched() -> None:
    protected = [
        ROOT / "content_brain" / "execution" / "runway_ui_navigator.py",
        ROOT / "content_brain" / "execution" / "runway_live_smoke_test.py",
        ROOT / "content_brain" / "execution" / "runway_live_post_processor.py",
        ROOT / "providers" / "runway_browser_provider.py",
    ]
    for path in protected:
        _pass(f"runway_exists_{path.name}", path.is_file())


def main() -> None:
    print("=== Phase DIRECTOR-3 Visual Subject Lock Validation ===")
    test_scorpion_lock_not_arachnologist()
    test_scorpion_prompt_builder()
    test_human_presenter_secondary()
    test_topic_forbidden_confusions()
    test_director_metadata_and_critic()
    test_runway_automation_untouched()
    print("\n=== Regression ===")
    _run("project_brain/validate_topic_authority_end_to_end.py")
    _run("project_brain/validate_director_layer_v2_prompt_critic.py")
    print("\nVisual Subject Lock validation complete — PASS")


if __name__ == "__main__":
    main()
