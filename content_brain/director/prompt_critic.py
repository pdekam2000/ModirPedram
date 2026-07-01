"""Director Layer V2 — Prompt Critic Engine (Phase 2A/2B + Visual Subject Lock)."""

from __future__ import annotations

import re
from typing import Any

from content_brain.director.director_models import (
    CRITIC_DECISION_IMPROVE,
    CRITIC_DECISION_PASS,
    CRITIC_DECISION_REWRITE_REQUIRED,
    CRITIC_ISSUE_CONTINUITY_RISK,
    CRITIC_ISSUE_REPETITION_RISK,
    CRITIC_ISSUE_TOPIC_DRIFT,
    CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT,
    CRITIC_ISSUE_WEAK_ENDING,
    CRITIC_ISSUE_WEAK_HOOK,
    CRITIC_ISSUE_WEAK_VISUALS,
    PromptCriticReport,
    PromptQualityThresholds,
)
from content_brain.director.director_topic_authority import DIRECTOR_FORBIDDEN_DRIFT
from content_brain.director.openai_director_client import openai_json_completion
from content_brain.director.visual_subject_lock import VisualSubjectLock, extract_visual_subject_lock

CRITIC_SYSTEM_PROMPT = """You are a senior cinematic prompt critic for multi-clip Runway video generation.
Return ONLY valid JSON with scores 0-100:
overall_score, topic_authority_score, visual_impact_score, continuity_score, visual_subject_consistency_score,
hook_score, ending_score, repetition_score.
Also return issues[] (topic_drift, weak_visuals, weak_hook, weak_ending, continuity_risk, repetition_risk, visual_subject_drift),
decision (PASS|IMPROVE|REWRITE_REQUIRED), weaknesses[], improvements[].
User topic is authoritative. Flag topic_drift for gaming/GPU/technology drift.
Flag visual_subject_drift when human presenter overrides animal/object topic subject or forbidden confusions are missing.
repetition_score: higher means LESS repetition."""

VISUAL_KW = ("camera", "shot", "lighting", "cinematic", "visual", "frame", "lens", "tracking", "close-up", "wide")
HOOK_KW = ("hook", "open", "establish", "discover", "introduce", "immediate", "reveal")
END_KW = ("payoff", "resolve", "resolution", "final", "conclude", "handoff", "ending")
CONT_KW = (
    "continuity",
    "same character",
    "same location",
    "same primary visual subject",
    "visual subject lock",
    "no scene jump",
    "use frame",
    "wardrobe",
)
VISUAL_SUBJECT_KW = ("visual subject", "subject identity", "same", "specimen", "primary visual subject")


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _topic_tokens(topic: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _norm(topic).lower()) if len(t) >= 3}


def _uniq_ratio(texts: list[str]) -> float:
    sentences: list[str] = []
    for text in texts:
        for part in re.split(r"(?<=[.!?])\s+", _norm(text)):
            if len(part.strip()) > 28:
                sentences.append(part.strip().lower())
    return 100.0 if not sentences else round(100.0 * len(set(sentences)) / len(sentences), 2)


def _kw_score(text: str, keywords: tuple[str, ...], base: float, step: float) -> float:
    return min(100.0, base + sum(1 for k in keywords if k in text.lower()) * step)


def _resolve_visual_subject_lock(
    *,
    topic: str,
    story_brief: dict[str, Any] | None,
    storyboard: dict[str, Any] | None,
    scene_breakdown: dict[str, Any] | None,
    continuity_plan: dict[str, Any] | None,
    visual_subject_lock: VisualSubjectLock | dict[str, Any] | None,
) -> VisualSubjectLock | None:
    if visual_subject_lock is not None:
        if isinstance(visual_subject_lock, VisualSubjectLock):
            return visual_subject_lock
        parsed = VisualSubjectLock.from_dict(dict(visual_subject_lock))
        if parsed and parsed.primary_visual_subject:
            return parsed
    return extract_visual_subject_lock(
        topic=topic,
        story_brief=story_brief,
        storyboard=storyboard,
        scene_breakdown=scene_breakdown,
    )


def _score_visual_subject_consistency(
    *,
    topic: str,
    starter_image_prompt: str,
    clip_prompts: list[str],
    visual_subject_lock: VisualSubjectLock | None,
    story_brief: dict[str, Any] | None,
) -> tuple[float, list[str], list[str]]:
    issues: list[str] = []
    weaknesses: list[str] = []
    if visual_subject_lock is None or not visual_subject_lock.primary_visual_subject:
        return 100.0, issues, weaknesses

    primary = visual_subject_lock.primary_visual_subject.lower()
    primary_tokens = [token for token in re.findall(r"[a-z0-9]+", primary) if len(token) >= 4]
    human_presenter = _norm((story_brief or {}).get("main_character") or visual_subject_lock.human_presenter_role)
    human_lower = human_presenter.lower()
    all_prompts = [starter_image_prompt, *clip_prompts]
    combined = " ".join(all_prompts).lower()

    score = 100.0
    missing_clips: list[int] = []
    for index, prompt in enumerate(all_prompts):
        lowered = prompt.lower()
        has_primary = primary in lowered or any(token in lowered for token in primary_tokens)
        if not has_primary:
            missing_clips.append(index)
            score -= 18.0 if index == 0 else 14.0

    if missing_clips:
        issues.append(CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT)
        weaknesses.append(
            f"Primary visual subject '{visual_subject_lock.primary_visual_subject}' missing in prompts: {missing_clips}"
        )

    if visual_subject_lock.subject_type != "person" and human_lower:
        starter_lower = starter_image_prompt.lower()
        if starter_lower.startswith("subject:") or "subject identity:" in starter_lower:
            subject_chunk = starter_lower.split("subject identity:", 1)[0]
        else:
            subject_chunk = starter_lower[:240]
        if human_lower in subject_chunk and primary not in subject_chunk[:120]:
            score -= 25.0
            issues.append(CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT)
            weaknesses.append("Human presenter overrides topic visual subject in starter or identity line")

        for index, prompt in enumerate(clip_prompts, start=1):
            match = re.search(r"subject identity:\s*([^.]{0,120})", prompt, re.I)
            if match and human_lower in match.group(1).lower() and primary not in match.group(1).lower():
                score -= 20.0
                issues.append(CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT)
                weaknesses.append(f"Clip {index} Subject identity uses human presenter instead of visual subject")
                break

    forbidden_missing: list[str] = []
    for confusion in visual_subject_lock.forbidden_confusions[:4]:
        token = str(confusion).lower()
        if token and f"no {token}" not in combined and token not in combined:
            forbidden_missing.append(token)
    if forbidden_missing and visual_subject_lock.subject_type == "animal":
        score -= min(30.0, 8.0 * len(forbidden_missing))
        issues.append(CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT)
        weaknesses.append(f"Forbidden confusion negatives missing: {', '.join(forbidden_missing[:4])}")

    if not issues and (primary in combined or primary_tokens):
        score = max(score, 92.0)
    return max(0.0, min(100.0, score)), list(dict.fromkeys(issues)), weaknesses


def _score_topic_authority(*, topic: str, combined: str) -> tuple[float, list[str], list[str]]:
    lowered = combined.lower()
    issues: list[str] = []
    weaknesses: list[str] = []
    score = 100.0
    drift = [t for t in DIRECTOR_FORBIDDEN_DRIFT if t in lowered and t not in _norm(topic).lower()]
    drift.extend(t for t in ("gpu", "gaming", "technology", "tech lab", "graphics card") if t in lowered and t not in drift)
    if drift:
        issues.append(CRITIC_ISSUE_TOPIC_DRIFT)
        weaknesses.append(f"Topic drift detected: {', '.join(drift[:4])}")
        score -= min(55.0, 20.0 * len(drift))
    hits = _topic_tokens(topic)
    if hits and not any(t in lowered for t in hits):
        score -= 35.0
        weaknesses.append(f"Topic '{topic}' not anchored in prompt corpus")
    if (not hits or any(t in lowered for t in hits)) and not drift:
        score = max(score, 92.0)
    return max(0.0, min(100.0, score)), issues, weaknesses


def _weighted_overall(report: PromptCriticReport) -> float:
    return round(min(100.0, max(0.0,
        report.topic_authority_score * 0.22 + report.visual_impact_score * 0.13 + report.continuity_score * 0.18
        + report.visual_subject_consistency_score * 0.12 + report.hook_score * 0.13 + report.ending_score * 0.09
        + report.repetition_score * 0.13)), 2)


def decide_critic_action(report: PromptCriticReport, thresholds: PromptQualityThresholds | None = None) -> str:
    limits = thresholds or PromptQualityThresholds()
    if CRITIC_ISSUE_TOPIC_DRIFT in report.issues or CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT in report.issues:
        if report.overall_score < 60.0 or report.visual_subject_consistency_score < 50.0:
            return CRITIC_DECISION_REWRITE_REQUIRED
    if CRITIC_ISSUE_TOPIC_DRIFT in report.issues or report.overall_score < 60.0:
        return CRITIC_DECISION_REWRITE_REQUIRED
    if (report.overall_score >= limits.overall_min and report.topic_authority_score >= limits.topic_authority_min
            and report.continuity_score >= limits.continuity_min
            and report.visual_subject_consistency_score >= limits.visual_subject_min
            and report.hook_score >= limits.hook_min
            and report.ending_score >= limits.ending_min
            and report.repetition_score >= limits.repetition_min):
        return CRITIC_DECISION_PASS
    return CRITIC_DECISION_IMPROVE


def _deterministic_critic_report(
    *, topic: str, starter_image_prompt: str, clip_prompts: list[str],
    story_brief: dict[str, Any] | None = None,
    visual_subject_lock: VisualSubjectLock | None = None,
    thresholds: PromptQualityThresholds | None = None,
) -> PromptCriticReport:
    combined = " ".join([starter_image_prompt, *clip_prompts])
    topic_score, topic_issues, topic_weak = _score_topic_authority(topic=topic, combined=combined)
    visual_score = _kw_score(combined, VISUAL_KW, 35.0, 9.0)
    continuity_score = _kw_score(combined, CONT_KW, 30.0, 10.0)
    visual_subject_score, visual_subject_issues, visual_subject_weak = _score_visual_subject_consistency(
        topic=topic,
        starter_image_prompt=starter_image_prompt,
        clip_prompts=clip_prompts,
        visual_subject_lock=visual_subject_lock,
        story_brief=story_brief,
    )
    hook_score = _kw_score((clip_prompts[0] if clip_prompts else "")[:400], HOOK_KW, 40.0, 12.0)
    ending_score = _kw_score((clip_prompts[-1] if clip_prompts else "")[-500:], END_KW, 40.0, 12.0)
    repetition_score = _uniq_ratio(clip_prompts)
    issues = list(dict.fromkeys(topic_issues + visual_subject_issues
        + ([CRITIC_ISSUE_WEAK_VISUALS] if visual_score < 60 else [])
        + ([CRITIC_ISSUE_CONTINUITY_RISK] if continuity_score < 80 else [])
        + ([CRITIC_ISSUE_WEAK_HOOK] if hook_score < 75 else [])
        + ([CRITIC_ISSUE_WEAK_ENDING] if ending_score < 75 else [])
        + ([CRITIC_ISSUE_REPETITION_RISK] if repetition_score < 70 else [])))
    weaknesses = list(topic_weak + visual_subject_weak)
    improvements: list[str] = []
    if CRITIC_ISSUE_TOPIC_DRIFT in issues:
        improvements.append(f"Re-anchor prompts to topic '{topic}'")
    if CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT in issues:
        improvements.append("Lock primary visual subject in every clip and add forbidden confusion negatives")
    if CRITIC_ISSUE_WEAK_HOOK in issues:
        improvements.append("Strengthen clip 1 visual hook")
    if CRITIC_ISSUE_WEAK_ENDING in issues:
        improvements.append("Add decisive final payoff frame")
    if CRITIC_ISSUE_WEAK_VISUALS in issues:
        improvements.append("Inject camera and lighting direction")
    if CRITIC_ISSUE_CONTINUITY_RISK in issues:
        improvements.append("Reinforce continuity lock language")
    if CRITIC_ISSUE_REPETITION_RISK in issues:
        improvements.append("Differentiate clip action beats")
    report = PromptCriticReport(
        topic_authority_score=topic_score,
        visual_impact_score=visual_score,
        continuity_score=continuity_score,
        visual_subject_consistency_score=visual_subject_score,
        hook_score=hook_score,
        ending_score=ending_score,
        repetition_score=repetition_score,
        issues=issues,
        weaknesses=weaknesses,
        improvements=improvements,
        source="deterministic",
    )
    report.overall_score = _weighted_overall(report)
    report.decision = decide_critic_action(report, thresholds)
    return report


def critique_prompts(
    *, topic: str, starter_image_prompt: str, clip_prompts: list[str],
    story_brief: dict[str, Any] | None = None, storyboard: dict[str, Any] | None = None,
    scene_breakdown: dict[str, Any] | None = None, continuity_plan: dict[str, Any] | None = None,
    visual_subject_lock: VisualSubjectLock | dict[str, Any] | None = None,
    thresholds: PromptQualityThresholds | None = None, dry_run: bool = False,
) -> tuple[PromptCriticReport, list[str]]:
    notes: list[str] = []
    limits = thresholds or PromptQualityThresholds()
    lock = _resolve_visual_subject_lock(
        topic=topic,
        story_brief=story_brief,
        storyboard=storyboard,
        scene_breakdown=scene_breakdown,
        continuity_plan=continuity_plan,
        visual_subject_lock=visual_subject_lock,
    )
    raw, model, client_notes = openai_json_completion(
        system_prompt=CRITIC_SYSTEM_PROMPT,
        user_payload={
            "topic": topic, "thresholds": limits.to_dict(), "story_brief": story_brief or {},
            "storyboard": storyboard or {}, "scene_breakdown": scene_breakdown or {},
            "continuity_plan": continuity_plan or {},
            "visual_subject_lock": lock.to_dict() if lock else {},
            "starter_image_prompt": starter_image_prompt,
            "clip_prompts": list(clip_prompts),
        },
        dry_run=dry_run,
    )
    notes.extend(client_notes)
    if raw:
        report = PromptCriticReport.from_dict(raw)
        report.model = model
        report.source = "openai"
        if not raw.get("overall_score"):
            report.overall_score = _weighted_overall(report)
        if not raw.get("visual_subject_consistency_score") and lock:
            report.visual_subject_consistency_score, _, _ = _score_visual_subject_consistency(
                topic=topic,
                starter_image_prompt=starter_image_prompt,
                clip_prompts=clip_prompts,
                visual_subject_lock=lock,
                story_brief=story_brief,
            )
        report.decision = decide_critic_action(report, limits)
        notes.append("prompt_critic_openai")
        return report, notes
    report = _deterministic_critic_report(
        topic=topic,
        starter_image_prompt=starter_image_prompt,
        clip_prompts=clip_prompts,
        story_brief=story_brief,
        visual_subject_lock=lock,
        thresholds=limits,
    )
    notes.append("prompt_critic_deterministic_fallback")
    return report, notes
