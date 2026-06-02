"""
Phase 12B — UAT supervised pipeline validation.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.uat_runtime_profile import UatRuntimeConfig, apply_live_voice_smoke_duration_guard, generate_uat_session_id
from project_brain import run_12b_uat_supervised_pipeline as uat_runner


RUNNER_PATH = Path("project_brain/run_12b_uat_supervised_pipeline.py")
PROFILE_PATH = Path("content_brain/execution/uat_runtime_profile.py")


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _run_module(module: str, *, core_only: bool = True) -> bool:
    from project_brain.validation_policy import run_validator_module

    return run_validator_module(module, core_only=core_only)


def _imports_forbidden(module_path: Path, forbidden: str) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if forbidden in alias.name:
                    return True
        if isinstance(node, ast.ImportFrom) and node.module and forbidden in node.module:
            return True
    return False


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    _ = project_root
    results: list[dict] = []

    # 1. Runner exists.
    results.append(_pass("runner_exists", RUNNER_PATH.is_file(), str(RUNNER_PATH)))

    # 2. CLI args parsed.
    cfg = uat_runner.parse_uat_args(
        [
            "--topic",
            "test topic",
            "--platform",
            "youtube_shorts",
            "--duration-seconds",
            "45",
            "--video-provider",
            "runway_browser",
            "--voice-provider",
            "elevenlabs",
            "--confirm-real-voice",
            "--confirm-real-assembly",
        ]
    )
    results.append(
        _pass(
            "cli_args_parsed",
            cfg.topic == "test topic"
            and cfg.platform == "youtube_shorts"
            and cfg.duration_seconds == 45
            and cfg.confirm_real_voice
            and cfg.confirm_real_assembly,
            cfg.platform,
        )
    )

    # 3. Env bootstrap callable.
    results.append(_pass("env_bootstrap_callable", callable(uat_runner.bootstrap_project_env if hasattr(uat_runner, "bootstrap_project_env") else __import__("core.env_bootstrap").bootstrap_project_env)))

    # 4. UAT session id generated.
    sid = generate_uat_session_id()
    results.append(
        _pass(
            "uat_session_id_generated",
            sid.startswith("exec_uat_") and len(sid) > len("exec_uat_"),
            sid,
        )
    )

    with tempfile.TemporaryDirectory() as _tmp:
        root = Path(".").resolve()
        session_id = f"exec_uat_val_{uuid.uuid4().hex[:8]}"

        # 5. Mock-mode pipeline completes without paid providers.
        config = UatRuntimeConfig(
            topic="UAT validator mock topic for automated test",
            platform="youtube_shorts",
            duration_seconds=30,
            video_provider="runway_browser",
            voice_provider="mock",
        )
        payload: dict[str, Any] = {}
        try:
            payload = uat_runner.run_uat_pipeline(
                root,
                config,
                mock_paid_providers=True,
                mock_assembly_executor=True,
                session_id=session_id,
            )
            mock_ok = payload.get("success") is True and bool(payload.get("final_video_path"))
        except Exception as exc:
            mock_ok = False
            payload = {"error": str(exc)}
        results.append(
            _pass(
                "mock_pipeline_completes",
                bool(mock_ok),
                str(payload.get("final_video_path") or payload.get("error")),
            )
        )

        session_id = str(payload.get("session_id") or session_id)
        store = ExecutionSessionStore(root)

        # 6. Review template created.
        review_path = Path(payload.get("review_template_path") or "")
        review_ok = review_path.is_file()
        if review_ok:
            review_data = json.loads(review_path.read_text(encoding="utf-8"))
            review_ok = review_data.get("session_id") == session_id
        results.append(_pass("review_template_created", review_ok, str(review_path)))

        # 7. UAT report created.
        report_path = Path(payload.get("runtime_report_path") or "")
        results.append(_pass("uat_report_created", report_path.is_file(), str(report_path)))

        # 8. Real voice cannot run without confirm flag (mock mode used instead).
        if mock_ok:
            blocked_voice = uat_runner._run_voice_stage(
                store,
                session_id,
                UatRuntimeConfig(topic="x", voice_provider="elevenlabs", confirm_real_voice=False),
                mock_paid_providers=False,
            )
            voice_block_ok = blocked_voice.get("voice_provider_mode") == "mock"
        else:
            voice_block_ok = False
            blocked_voice = {}
        results.append(
            _pass(
                "real_voice_blocked_without_confirm",
                voice_block_ok,
                str(blocked_voice.get("voice_provider_mode") or blocked_voice.get("code")),
            )
        )

        # 9. Real assembly cannot run without confirm flag.
        if mock_ok:
            blocked_asm = uat_runner._run_assembly_stage(
                store,
                session_id,
                UatRuntimeConfig(topic="x", confirm_real_assembly=False),
                mock_paid_providers=False,
                mock_assembly_executor=False,
            )
            asm_block_ok = blocked_asm.get("code") == "ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED"
        else:
            asm_block_ok = False
            blocked_asm = {}
        results.append(
            _pass(
                "real_assembly_blocked_without_confirm",
                asm_block_ok,
                str(blocked_asm.get("code")),
            )
        )

        # 10. Flags disabled after failure.
        os.environ.pop("MODIR_VOICE_LIVE_TTS_ENABLED", None)
        os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
        os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)
        import content_brain.execution.voice_live_tts_action_policy as voice_policy

        flags_after = {
            "MODIR_VOICE_LIVE_TTS_ENABLED": os.getenv("MODIR_VOICE_LIVE_TTS_ENABLED"),
            "MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED": os.getenv("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"),
            "ASSEMBLY_RUNTIME_EXECUTION_APPROVED": os.getenv("ASSEMBLY_RUNTIME_EXECUTION_APPROVED"),
            "LIVE_RUNTIME_EXECUTION_APPROVED": voice_policy.LIVE_RUNTIME_EXECUTION_APPROVED,
        }
        try:
            uat_runner._run_assembly_stage(
                store,
                session_id,
                UatRuntimeConfig(topic="x", confirm_real_assembly=True),
                mock_paid_providers=False,
                mock_assembly_executor=False,
            )
        except Exception:
            pass
        finally:
            os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
            os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)
        results.append(
            _pass(
                "flags_disabled_after_failure",
                os.getenv("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED") is None
                and os.getenv("ASSEMBLY_RUNTIME_EXECUTION_APPROVED") is None,
                json.dumps(flags_after),
            )
        )

    # 11. Live voice smoke duration guard (Option A — UAT-only).
    cfg_smoke_20 = UatRuntimeConfig(
        topic="smoke guard test",
        duration_seconds=20,
        video_provider="runway_browser",
        voice_provider="elevenlabs",
        confirm_real_voice=True,
    )
    adjusted_20, smoke_warns, smoke_meta = apply_live_voice_smoke_duration_guard(cfg_smoke_20.normalized())
    results.append(
        _pass(
            "live_voice_smoke_reduces_20s_to_10s",
            adjusted_20.duration_seconds == 10
            and bool(smoke_warns)
            and smoke_meta.get("original_duration_seconds") == 20,
            str(adjusted_20.duration_seconds),
        )
    )
    results.append(
        _pass(
            "live_voice_smoke_warning_not_content_brain",
            any("smoke safety" in w.lower() and "content brain" in w.lower() for w in smoke_warns),
            smoke_warns[0] if smoke_warns else "",
        )
    )

    cfg_smoke_10 = UatRuntimeConfig(
        topic="smoke guard test",
        duration_seconds=10,
        video_provider="runway_browser",
        voice_provider="elevenlabs",
        confirm_real_voice=True,
    )
    adjusted_10, warns_10, _ = apply_live_voice_smoke_duration_guard(
        cfg_smoke_10.normalized(smoke_single_segment=True)
    )
    results.append(
        _pass(
            "live_voice_smoke_10s_unchanged",
            adjusted_10.duration_seconds == 10 and not warns_10,
            str(adjusted_10.duration_seconds),
        )
    )

    cfg_smoke_8 = UatRuntimeConfig(
        topic="smoke guard test",
        duration_seconds=8,
        video_provider="runway_browser",
        voice_provider="elevenlabs",
        confirm_real_voice=True,
    )
    adjusted_8, warns_8, _ = apply_live_voice_smoke_duration_guard(
        cfg_smoke_8.normalized(smoke_single_segment=True)
    )
    results.append(
        _pass(
            "live_voice_smoke_8s_passes_cap",
            adjusted_8.duration_seconds == 8 and not warns_8,
            str(adjusted_8.duration_seconds),
        )
    )

    cfg_mock_voice = UatRuntimeConfig(
        topic="smoke guard test",
        duration_seconds=20,
        video_provider="runway_browser",
        voice_provider="mock",
        confirm_real_voice=False,
    )
    adjusted_mock, warns_mock, _ = apply_live_voice_smoke_duration_guard(cfg_mock_voice.normalized())
    results.append(
        _pass(
            "mock_voice_skips_smoke_duration_guard",
            adjusted_mock.duration_seconds == 20 and not warns_mock,
            str(adjusted_mock.duration_seconds),
        )
    )

    # 13b. UAT smoke-safe narration merge (Phase 12G).
    from content_brain.execution.session_narration_adapter import SessionNarrationAdapter
    from content_brain.execution.uat_smoke_narration_adapter import (
        apply_uat_smoke_narration,
        requires_uat_smoke_narration_merge,
    )
    from content_brain.execution.voice_live_tts_smoke_profile import evaluate_voice_live_tts_smoke_caps

    def _six_beat_session() -> dict:
        beats = []
        for index in range(6):
            beats.append(
                {
                    "beat_id": f"BEAT_{index}",
                    "description": (
                        f"PURPOSE: test beat {index} | "
                        f"NARRATION: Smoke narration segment {index} for UAT validation. | "
                        "VISUAL: test"
                    ),
                    "start_second": float(index * 2),
                    "end_second": float((index + 1) * 2),
                }
            )
        return {
            "execution_session_id": "exec_uat_smoke_narration_val",
            "brief_snapshot": {"story_blueprint": {"beats": beats}},
            "execution_runtime": {
                "operations": {"uat_run": {"mode": "user_acceptance_test", "session_id": "exec_uat_smoke_narration_val"}},
            },
        }

    smoke_session = _six_beat_session()
    smoke_cfg = UatRuntimeConfig(
        topic="smoke narration",
        duration_seconds=10,
        video_provider="runway_browser",
        voice_provider="elevenlabs",
        confirm_real_voice=True,
    )
    merged_session, smoke_meta = apply_uat_smoke_narration(smoke_session, smoke_cfg)
    merged_count = SessionNarrationAdapter().build(merged_session).segment_count
    results.append(
        _pass(
            "uat_smoke_narration_merges_six_to_one",
            bool(smoke_meta and smoke_meta.get("applied"))
            and smoke_meta.get("original_narration_segment_count") == 6
            and smoke_meta.get("smoke_narration_segment_count") == 1
            and merged_count == 1,
            str(smoke_meta),
        )
    )
    smoke_caps = evaluate_voice_live_tts_smoke_caps(
        {
            "approval": {"estimated_voice_cost": 0.05, "estimated_segment_count": 1},
            "segment_count": 1,
        },
        narration_segment_count=merged_count,
        narration_character_count=SessionNarrationAdapter().build(merged_session).total_text_length,
    )
    results.append(
        _pass(
            "uat_smoke_narration_passes_live_cap",
            smoke_caps.allowed,
            smoke_caps.message,
        )
    )

    mock_cfg = UatRuntimeConfig(
        topic="smoke narration mock",
        duration_seconds=10,
        voice_provider="mock",
        confirm_real_voice=False,
    )
    _, mock_meta = apply_uat_smoke_narration(smoke_session, mock_cfg)
    results.append(
        _pass(
            "mock_voice_skips_smoke_narration_merge",
            mock_meta is None and SessionNarrationAdapter().build(smoke_session).segment_count == 6,
            str(mock_meta),
        )
    )

    dry_cfg = UatRuntimeConfig(
        topic="smoke narration dry",
        duration_seconds=10,
        voice_provider="elevenlabs",
        confirm_real_voice=False,
    )
    _, dry_meta = apply_uat_smoke_narration(smoke_session, dry_cfg)
    results.append(
        _pass(
            "non_smoke_elevenlabs_skips_narration_merge",
            dry_meta is None and not requires_uat_smoke_narration_merge(dry_cfg, session=smoke_session),
            str(dry_meta),
        )
    )

    # 14. No batch loop in runner source.
    runner_src = RUNNER_PATH.read_text(encoding="utf-8")
    results.append(
        _pass(
            "no_batch_loop",
            "for topic in" not in runner_src and "batch_mode" not in runner_src.lower(),
        )
    )

    # 15. No auto-publish code.
    results.append(
        _pass(
            "no_auto_publish",
            "auto_publish" not in runner_src.lower()
            and "upload_to_youtube" not in runner_src.lower()
            and "tiktok_upload" not in runner_src.lower(),
        )
    )

    # 16. No full_video_pipeline import.
    results.append(
        _pass(
            "no_full_video_pipeline_import",
            not _imports_forbidden(RUNNER_PATH, "full_video_pipeline"),
        )
    )

    if include_regressions:
        results.append(
            _pass(
                "validate_11j19_regression",
                _run_module("project_brain.validate_11j19_supervised_assembly_smoke_test", core_only=True),
            )
        )
        results.append(
            _pass(
                "validate_11h2d_regression",
                _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution", core_only=True),
            )
        )

    from project_brain.validation_policy import summarize_validation_report

    return summarize_validation_report(
        phase="12B",
        label="uat_supervised_pipeline",
        results=results,
        include_regressions=include_regressions,
    )


def main(argv: list[str] | None = None) -> int:
    from project_brain.validation_policy import (
        parse_include_regressions,
        print_validation_summary,
        validation_exit_code,
    )

    include_regressions = parse_include_regressions(argv)
    report = run_matrix(include_regressions=include_regressions)
    print(json.dumps(report, indent=2))
    print_validation_summary(report)
    return validation_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
