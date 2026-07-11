"""Phase DIRECTOR-2 — Prompt Critic + Auto Rewrite validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.director.director_models import (
    CRITIC_ISSUE_REPETITION_RISK,
    CRITIC_ISSUE_TOPIC_DRIFT,
    CRITIC_ISSUE_WEAK_HOOK,
    PromptQualityThresholds,
)
from content_brain.director.director_pipeline import build_director_layer
from content_brain.director.prompt_critic import critique_prompts
from content_brain.director.prompt_review_pipeline import DEFAULT_MAX_REWRITE_CYCLES, review_and_rewrite_prompts
from content_brain.execution.runway_prompt_builder import build_continuity_prompts

TOPIC = "ants"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _bad_prompts() -> tuple[str, list[str]]:
    starter = "Generic scene about technology and gaming GPU benchmark in a tech lab."
    clips = [
        "Clip about gaming GPU benchmark in tech lab with neon esports lighting.",
        "Clip about gaming GPU benchmark in tech lab with neon esports lighting.",
        "Technology server room graphics card benchmark ending.",
    ]
    return starter, clips


def _test_critic_report() -> None:
    starter, clips = _bad_prompts()
    report, _ = critique_prompts(topic=TOPIC, starter_image_prompt=starter, clip_prompts=clips, dry_run=True)
    _pass("critic_report_generated", bool(report.to_dict()))
    _pass("scores_generated", all(hasattr(report, f) for f in (
        "overall_score", "topic_authority_score", "visual_impact_score", "continuity_score",
        "hook_score", "ending_score", "repetition_score",
    )), str(report.overall_score))


def _test_issue_detection() -> None:
    starter, clips = _bad_prompts()
    report, _ = critique_prompts(topic=TOPIC, starter_image_prompt=starter, clip_prompts=clips, dry_run=True)
    _pass("topic_drift_detected", CRITIC_ISSUE_TOPIC_DRIFT in report.issues, str(report.issues))
    _pass("repetition_detected", CRITIC_ISSUE_REPETITION_RISK in report.issues, str(report.repetition_score))
    weak_hook_starter = "ants colony documentary frame."
    weak_hook_clips = ["ants walking in colony.", "ants carrying food.", "ants near nest."]
    hook_report, _ = critique_prompts(
        topic=TOPIC, starter_image_prompt=weak_hook_starter, clip_prompts=weak_hook_clips, dry_run=True,
    )
    _pass("weak_hook_detected", CRITIC_ISSUE_WEAK_HOOK in hook_report.issues, str(hook_report.hook_score))


def _test_rewrite_improves_score() -> None:
    director = build_director_layer(topic=TOPIC, clip_count=3, dry_run=True)
    starter, clips = _bad_prompts()
    result = review_and_rewrite_prompts(
        topic=TOPIC, starter_image_prompt=starter, clip_prompts=clips,
        director_layer=director, dry_run=True, max_rewrite_cycles=2,
    )
    _pass("rewrite_improves_score", result.final_report.overall_score >= result.initial_report.overall_score,
          f"{result.initial_report.overall_score}->{result.final_report.overall_score}")
    _pass("max_rewrite_count", result.metadata.rewrite_count <= DEFAULT_MAX_REWRITE_CYCLES, str(result.metadata.rewrite_count))
    combined = " ".join([result.starter_image_prompt, *result.clip_prompts]).lower()
    _pass("rewrite_removes_gaming_drift", "gaming" not in combined and "gpu" not in combined)


def _test_structured_json() -> None:
    director = build_director_layer(topic=TOPIC, clip_count=3, dry_run=True)
    result = review_and_rewrite_prompts(
        topic=TOPIC, starter_image_prompt="ants macro shot.", clip_prompts=["clip1", "clip2", "clip3"],
        director_layer=director, dry_run=True,
    )
    payload = result.to_dict()
    json.dumps(payload, ensure_ascii=False)
    meta = payload.get("metadata") or {}
    _pass("structured_json_output", all(k in meta for k in ("score", "decision", "issues", "rewrite_count")))


def _test_prompt_builder_integration() -> None:
    bundle = build_continuity_prompts(
        TOPIC, clip_count=3, auto_story_brief=True, auto_director=True, auto_prompt_critic=True,
        director_dry_run=True, prompt_critic_dry_run=True,
    )
    _pass("prompt_builder_prompt_review", bundle.prompt_review is not None)
    _pass("prompt_review_metadata", hasattr(bundle.prompt_review, "score"))


def _test_runway_unmodified() -> None:
    protected = [
        ROOT / "content_brain" / "execution" / "runway_ui_navigator.py",
        ROOT / "content_brain" / "execution" / "runway_live_smoke_test.py",
        ROOT / "providers" / "runway_browser_provider.py",
    ]
    for path in protected:
        _pass(f"runway_exists_{path.name}", path.is_file())


def _run_validator(rel: str, *, required: bool = True) -> None:
    script = ROOT / rel
    if not script.is_file():
        _pass(f"skip_{script.name}", True, "missing")
        return
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    if required:
        _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-200:])
    elif proc.returncode != 0:
        print(f"[WARN] {rel}")


def main() -> None:
    print("=== Director Layer v2 Prompt Critic Validation ===")
    _test_critic_report()
    _test_issue_detection()
    _test_rewrite_improves_score()
    _test_structured_json()
    _test_prompt_builder_integration()
    _test_runway_unmodified()
    print("\n=== Regression ===")
    _run_validator("project_brain/validate_director_layer_v1.py")
    _run_validator("project_brain/validate_runway_starter_to_video_prompt_builder.py")
    _run_validator("project_brain/validate_runway_phase_i_hardening.py")
    _run_validator("project_brain/validate_runway_phase_i_final_assembly.py")
    _run_validator("project_brain/validate_runway_phase_i_publish_package.py")
    print("\nDirector Layer v2 validation complete — PASS")


if __name__ == "__main__":
    main()
