"""Validate E2E topic authority — no Whiskers/Sage overwrite on human narratives."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.story.character_director import build_character_profiles
from content_brain.story.story_architect import build_story_blueprint
from content_brain.story.story_niche import detect_genre


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


DRAGON_TOPIC = "A boy finds a dragon egg in the forest and hides it from everyone"
DRAGON_BRIEF = {
    "main_character": "Boy",
    "clip_beats": [
        "A boy discovers a glowing egg beneath forest leaves.",
        "He wraps the egg and hides it from passing travelers.",
        "Footsteps approach as the egg begins to warm.",
        "He escapes deeper into the trees clutching the secret.",
    ],
}


def test_genre_not_cartoon_for_dragon_story() -> None:
    genre = detect_genre(DRAGON_TOPIC, DRAGON_BRIEF)
    _pass("genre_not_cartoon", genre != "cartoon", genre)


def test_blueprint_uses_topic_and_beats() -> None:
    blueprint = build_story_blueprint(topic=DRAGON_TOPIC, clip_count=4, story_brief=DRAGON_BRIEF)
    _pass("title_from_topic", "dragon" in blueprint.title.lower() or "boy" in blueprint.title.lower(), blueprint.title)
    _pass("progression_from_beats", blueprint.scene_progression[0].startswith("A boy discovers"))
    _pass("no_whiskers_title", "whiskers" not in blueprint.title.lower())


def test_characters_not_cartoon_cast() -> None:
    blueprint = build_story_blueprint(topic=DRAGON_TOPIC, clip_count=4, story_brief=DRAGON_BRIEF)
    profiles = build_character_profiles(blueprint=blueprint, topic=DRAGON_TOPIC, story_brief=DRAGON_BRIEF)
    names = {profile.name.lower() for profile in profiles}
    _pass("no_whiskers", "whiskers" not in names, str(names))
    _pass("no_sage", "sage" not in names, str(names))
    _pass("has_boy_or_protagonist", bool(names.intersection({"boy", "protagonist", "narrator"})))


def test_run_isolation_cartoon_leak_guard() -> None:
    source = (ROOT / "content_brain/platform/run_isolation.py").read_text(encoding="utf-8")
    _pass("cartoon_leak_guard", "story_package_cartoon_character_leak" in source)


def main() -> None:
    test_genre_not_cartoon_for_dragon_story()
    test_blueprint_uses_topic_and_beats()
    test_characters_not_cartoon_cast()
    test_run_isolation_cartoon_leak_guard()
    print("validate_topic_identity_authority: all checks passed")


if __name__ == "__main__":
    main()
