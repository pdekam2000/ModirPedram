"""Validate Prompt Builder topic authority alignment — PHASE TOPIC-AUTHORITY-REPAIR-1."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_topic_authority import (
    TOPIC_FIDELITY_MIN_SCORE,
    is_generic_subject_replacement,
    score_topic_fidelity,
)
from content_brain.execution.runway_prompt_builder import build_continuity_prompts
from content_brain.product.topic_authority_trace import TopicAuthorityTrace, normalize_topic


BOXING_TOPIC = "how to be legende in boxing"
CAT_TOPIC = "Cute orange cartoon cat explorer Whiskers in crystal jungle"
PARK_TOPIC = "fantezy girl and man talking together in park"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _build(topic: str) -> object:
    return build_continuity_prompts(
        topic,
        project_id="topic_authority_alignment_test",
        clip_count=3,
        auto_story_brief=True,
        auto_director=False,
        auto_prompt_critic=False,
    )


def test_boxing_topic_remains_boxing() -> None:
    bundle = _build(BOXING_TOPIC)
    _pass("boxing_story_idea_preserved", normalize_topic(bundle.story_idea) == normalize_topic(BOXING_TOPIC))
    _pass("boxing_topic_field", normalize_topic(bundle.topic) == normalize_topic(BOXING_TOPIC))
    corpus = f"{bundle.subject} {bundle.visual_subject} {bundle.starter_image_prompt[:400]}"
    _pass("boxing_subject_markers", "box" in corpus.lower(), bundle.subject)
    _pass("boxing_no_presenter_subject", "knowledgeable presenter" not in bundle.subject.lower())


def test_cat_topic_remains_cat() -> None:
    bundle = _build(CAT_TOPIC)
    _pass("cat_story_idea_preserved", normalize_topic(bundle.story_idea) == normalize_topic(CAT_TOPIC))
    cat_corpus = f"{bundle.subject} {bundle.visual_subject} {bundle.starter_image_prompt[:300]}".lower()
    _pass("cat_subject_markers", any(marker in cat_corpus for marker in ("cat", "whisker", "whiskers")), bundle.subject)


def test_park_topic_remains_park() -> None:
    bundle = _build(PARK_TOPIC)
    _pass("park_story_idea_preserved", normalize_topic(bundle.story_idea) == normalize_topic(PARK_TOPIC))
    park_corpus = f"{bundle.subject} {bundle.visual_subject} {bundle.starter_image_prompt[:300]}".lower()
    _pass(
        "park_subject_markers",
        any(marker in park_corpus for marker in ("park", "girl", "man", "couple")),
        bundle.subject,
    )


def test_no_generic_presenter_replacement() -> None:
    for topic in (BOXING_TOPIC, PARK_TOPIC):
        bundle = _build(topic)
        _pass(
            f"no_generic_presenter_{topic[:20]}",
            not is_generic_subject_replacement(bundle.subject)
            and not is_generic_subject_replacement(bundle.visual_subject),
            f"subject={bundle.subject!r}",
        )


def test_topic_fidelity_at_least_80() -> None:
    for topic in (BOXING_TOPIC, CAT_TOPIC, PARK_TOPIC):
        bundle = _build(topic)
        score = int(bundle.topic_fidelity_score or 0)
        recomputed = score_topic_fidelity(
            topic,
            subject=bundle.subject,
            visual_subject=bundle.visual_subject,
            generated_texts=[bundle.starter_image_prompt, *bundle.clip_prompts[:1]],
        )
        _pass(f"fidelity_score_{topic[:18]}", score >= TOPIC_FIDELITY_MIN_SCORE, str(score))
        _pass(f"fidelity_recomputed_{topic[:18]}", recomputed >= TOPIC_FIDELITY_MIN_SCORE, str(recomputed))


def test_prompt_builder_passes_topic_authority_trace() -> None:
    trace = TopicAuthorityTrace(authoritative_topic=BOXING_TOPIC, requested_clip_count=3, topic_mode="custom")
    bundle = _build(BOXING_TOPIC)
    trace.record("prompt_builder", topic=bundle.story_idea, clip_count=bundle.clip_count)
    _pass("trace_validate_topic", trace.validate_topic("prompt_builder", bundle.story_idea))


def main() -> None:
    tests = [
        test_boxing_topic_remains_boxing,
        test_cat_topic_remains_cat,
        test_park_topic_remains_park,
        test_no_generic_presenter_replacement,
        test_topic_fidelity_at_least_80,
        test_prompt_builder_passes_topic_authority_trace,
    ]
    print("PHASE TOPIC-AUTHORITY-REPAIR-1 — alignment validation")
    print("=" * 60)
    for test in tests:
        test()
    print("=" * 60)
    print(f"ALL {len(tests)} CHECKS PASSED")


if __name__ == "__main__":
    main()
