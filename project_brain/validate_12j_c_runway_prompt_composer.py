"""
Phase 12J-C — RunwayPromptComposer validation (flag off unchanged, flag on composes).
"""

from __future__ import annotations

import copy
import json
from hashlib import sha256
from pathlib import Path

from content_brain.execution.runway_prompt_composer import (
    COMPOSER_VERSION,
    RunwayPromptComposer,
    apply_runway_prompt_composer_to_session,
)
from content_brain.execution.runway_prompt_composer_config import enable_runway_prompt_composer
from content_brain.execution.session_prompt_adapter import SessionPromptAdapter


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _load_fixture_session(root: Path) -> dict | None:
    candidate = root / "storage" / "content_brain" / "execution" / "sessions" / "exec_uat_20260602_055459.json"
    if candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return None


def _prompt_hash(prompts: list[str]) -> str:
    joined = "\n".join(prompts)
    return sha256(joined.encode("utf-8")).hexdigest()


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    composer_path = root / "content_brain" / "execution" / "runway_prompt_composer.py"
    config_path = root / "content_brain" / "execution" / "runway_prompt_composer_config.py"
    engine_path = root / "content_brain" / "execution" / "provider_runtime_engine.py"
    adapter_path = root / "content_brain" / "execution" / "session_prompt_adapter.py"

    results.append(_pass("composer_module_exists", composer_path.is_file()))
    results.append(_pass("config_module_exists", config_path.is_file()))

    engine_src = engine_path.read_text(encoding="utf-8")
    results.append(_pass("dispatch_wires_composer", "apply_runway_prompt_composer_to_session" in engine_src))
    results.append(_pass("dispatch_checks_flag", "enable_runway_prompt_composer" in engine_src))

    config_src = config_path.read_text(encoding="utf-8")
    results.append(_pass("flag_name_present", "enable_runway_prompt_composer" in config_src))

    adapter_src = adapter_path.read_text(encoding="utf-8")
    results.append(_pass("adapter_lineage_passthrough", "prompt_lineage" in adapter_src))
    results.append(_pass("adapter_priority_truncate", "_truncate_runway_with_priority" in adapter_src))

    session = _load_fixture_session(root)
    if not session:
        results.append(_pass("fixture_session_loaded", False, "exec_uat_20260602_055459.json missing"))
        passed = sum(1 for item in results if item["pass"])
        return {"passed": passed, "total": len(results), "results": results}

    results.append(_pass("fixture_session_loaded", True))

    session_off = copy.deepcopy(session)
    session_off.pop("enable_runway_prompt_composer", None)
    brief_off = session_off.setdefault("brief_snapshot", {})
    run_off = brief_off.setdefault("run_context", {})
    run_off.pop("enable_runway_prompt_composer", None)
    run_off.pop("runway_composed_clips", None)
    run_off.pop("runway_composer_version", None)

    adapter = SessionPromptAdapter()
    bundle_off = adapter.build(session_off, "runway_browser")
    hash_off = _prompt_hash(bundle_off.prompts)
    results.append(_pass("flag_off_adapter_builds", len(bundle_off.prompts) >= 1))
    results.append(_pass("flag_off_no_lineage_metadata", "prompt_lineage" not in bundle_off.metadata))

    session_on = copy.deepcopy(session_off)
    session_on["enable_runway_prompt_composer"] = True
    session_on = apply_runway_prompt_composer_to_session(session_on)
    brief_on = session_on.get("brief_snapshot") or {}
    run_on = brief_on.get("run_context") or {}
    clips = run_on.get("runway_composed_clips") or []

    results.append(_pass("flag_on_composes_clips", isinstance(clips, list) and len(clips) == 2))
    results.append(_pass("flag_on_version", run_on.get("runway_composer_version") == COMPOSER_VERSION))

    required_fields = {
        "clip_index",
        "hook_payload",
        "retention_payload",
        "architecture_payload",
        "thumbnail_payload",
        "continuity_payload",
        "emotional_arc",
        "payoff_payload",
        "composed_prompt",
        "lineage",
        "quality_score",
    }
    schema_ok = bool(clips) and all(required_fields.issubset(set(c)) for c in clips if isinstance(c, dict))
    results.append(_pass("composed_clip_schema", schema_ok))

    clip2 = clips[1] if len(clips) > 1 else {}
    payoff = clip2.get("payoff_payload") or {}
    folded = set(payoff.get("folded_beat_ids") or [])
    results.append(
        _pass(
            "clip2_payoff_fold",
            payoff.get("applies") is True
            and {"PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"}.issubset(folded),
            f"folded={sorted(folded)}",
        )
    )

    bundle_on = adapter.build(session_on, "runway_browser")
    hash_on = _prompt_hash(bundle_on.prompts)
    results.append(_pass("flag_on_adapter_builds", len(bundle_on.prompts) == 2))
    results.append(_pass("flag_on_prompts_differ", hash_on != hash_off, f"off={hash_off[:12]} on={hash_on[:12]}"))
    results.append(_pass("flag_on_lineage_metadata", len(bundle_on.metadata.get("prompt_lineage") or []) == 2))

    clip1_prompt = (clips[0] or {}).get("composed_prompt") or ""
    results.append(
        _pass(
            "clip1_retention_or_architecture_merged",
            "close-up" in clip1_prompt.lower()
            or "hook" in clip1_prompt.lower()
            or "motion" in clip1_prompt.lower(),
            clip1_prompt[:120],
        )
    )

    results.append(_pass("default_flag_disabled", not enable_runway_prompt_composer(session_off)))
    results.append(_pass("session_flag_enabled", enable_runway_prompt_composer(session_on)))

    idempotent = apply_runway_prompt_composer_to_session(copy.deepcopy(session_on))
    idem_clips = (idem_session_brief := (idempotent.get("brief_snapshot") or {})).get("run_context", {}).get(
        "runway_composed_clips"
    )
    results.append(
        _pass(
            "idempotent_compose",
            idem_clips == clips,
        )
    )

    try:
        RunwayPromptComposer().compose({"video_format_plan": {"clip_count": 0}})
        results.append(_pass("composer_rejects_zero_clips", False))
    except ValueError as exc:
        results.append(_pass("composer_rejects_zero_clips", "CLIP_COUNT" in str(exc), str(exc)))

    passed = sum(1 for item in results if item["pass"])
    return {"passed": passed, "total": len(results), "results": results}


if __name__ == "__main__":
    summary = run_matrix()
    for item in summary["results"]:
        status = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{status}] {item['test']}{detail}")
    print(f"\n{summary['passed']}/{summary['total']} passed")
    raise SystemExit(0 if summary["passed"] == summary["total"] else 1)
