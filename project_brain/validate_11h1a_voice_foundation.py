"""
Phase 11H-1a — voice foundation validation (no live ElevenLabs API calls).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.audio_artifact_validator import AudioArtifactValidator
from content_brain.execution.session_narration_adapter import (
    SOURCE_BEAT_PLANS,
    SessionNarrationAdapter,
)
from content_brain.execution.voice_provider_router import VoiceProviderRouter
from providers.elevenlabs_config import ElevenLabsConfigResolver
from providers.elevenlabs_preflight import CODE_CREDENTIALS_MISSING, ElevenLabsPreflight


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []
    adapter = SessionNarrationAdapter()
    router = VoiceProviderRouter(root)

    supported = router.list_supported_providers()
    session_with_narration = {
        "provider_selection": {
            "category_selections": {
                "voice_generation": {"provider": "elevenlabs"},
            }
        },
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {
                                "beat_id": "HOOK_BEAT",
                                "narration": "This is the hook narration line.",
                                "start_second": 0,
                                "end_second": 3,
                            }
                        ]
                    },
                    "schema_director_shots": [
                        {"clip_number": 1, "prompt": "Visual only prompt must be ignored."}
                    ],
                }
            }
        },
    }
    results.append(
        _pass(
            "router_lists_supported_providers",
            supported == ["elevenlabs", "minimax_tts", "openai_tts"],
            ",".join(supported),
        )
    )

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-real"}, clear=False):
        route_result = router.route(session_with_narration, dry_run=True)
    results.append(
        _pass(
            "router_does_not_call_live_tts",
            route_result.executed is False
            and route_result.dry_run is True
            and route_result.metadata.get("live_tts") is False,
            f"executed={route_result.executed}, dry_run={route_result.dry_run}",
        )
    )

    env_without_key = {k: v for k, v in os.environ.items() if k != "ELEVENLABS_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        preflight = ElevenLabsPreflight(root).run({})
    results.append(
        _pass(
            "missing_api_key_credentials_missing",
            preflight.status == "failed" and preflight.code == CODE_CREDENTIALS_MISSING,
            preflight.code or "",
        )
    )

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "super-secret-key-value"}, clear=False):
        summary = ElevenLabsConfigResolver(root).resolve({}).to_summary()
    secret_leaked = "super-secret-key-value" in json.dumps(summary)
    results.append(
        _pass(
            "config_summary_never_exposes_secret",
            summary.get("has_api_key") is True and not secret_leaked,
            str(summary.keys()),
        )
    )

    bundle = adapter.build(session_with_narration)
    results.append(
        _pass(
            "adapter_extracts_beat_narration",
            bundle.segment_count == 1
            and bundle.segments[0].text == "This is the hook narration line."
            and bundle.source_path == SOURCE_BEAT_PLANS,
            bundle.source_path,
        )
    )

    visual_only_session = {
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "schema_director_shots": [
                        {"clip_number": 1, "prompt": "Only a visual prompt here."}
                    ]
                }
            }
        }
    }
    visual_bundle = adapter.build(visual_only_session)
    results.append(
        _pass(
            "adapter_ignores_visual_prompt_fields",
            visual_bundle.skipped is True and visual_bundle.segment_count == 0,
            str(visual_bundle.warnings),
        )
    )

    import re

    adapter_source = (root / "content_brain" / "execution" / "session_narration_adapter.py").read_text(encoding="utf-8")
    forbidden_import = bool(
        re.search(r"^\s*(from|import)\s+.*TimelineEngine", adapter_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*full_video_pipeline", adapter_source, re.MULTILINE)
    )
    results.append(
        _pass(
            "adapter_no_legacy_pipeline_imports",
            not forbidden_import,
            "forbidden import found" if forbidden_import else "clean",
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = Path(tmpdir) / "segment_01.mp3"
        mp3_path.write_bytes(b"ID3fake-mp3-content")
        ok_result = AudioArtifactValidator().validate(
            [{"file_path": str(mp3_path), "artifact_type": "narration_audio"}],
            dry_run=False,
        )
        results.append(
            _pass(
                "audio_validator_passes_fake_mp3",
                ok_result.passed is True and ok_result.valid_count == 1,
                str(ok_result.valid_count),
            )
        )

        missing_result = AudioArtifactValidator().validate(
            [{"file_path": str(Path(tmpdir) / "missing.mp3")}],
            dry_run=False,
        )
        results.append(
            _pass(
                "audio_validator_fails_missing_file",
                missing_result.passed is False and missing_result.reject_code == "ARTIFACT_VALIDATION_FAILED",
                missing_result.reject_code or "",
            )
        )

    legacy_path = root / "storage/content_brain/execution/sessions/exec_10i_completed_demo.json"
    legacy_session = json.loads(legacy_path.read_text(encoding="utf-8"))
    legacy_bundle = adapter.build(legacy_session)
    results.append(
        _pass(
            "legacy_session_no_narration_skipped_not_crash",
            legacy_bundle.skipped is True
            and legacy_bundle.segment_count == 0
            and any("No narration" in w or "ignored" in w for w in legacy_bundle.warnings),
            str(legacy_bundle.warnings[:2]),
        )
    )

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11H-1a",
        "label": "voice_foundation",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def main() -> int:
    report = run_matrix()
    print(json.dumps(report, indent=2))
    for item in report["results"]:
        mark = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] {item['test']}{detail}")
    print(f"\n{report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
