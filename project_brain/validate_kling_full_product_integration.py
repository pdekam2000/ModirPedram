"""Validate Kling full Product Studio integration."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_config import MULTISHOT_STRATEGY  # noqa: E402
from content_brain.execution.kling_multishot_live_engine import (  # noqa: E402
    KlingMultishotLiveResult,
    STATUS_AWAITING_APPROVAL,
    STATUS_COMPLETED,
)
from content_brain.execution.kling_native_audio_models import KLING_AUDIO_STRATEGY, KLING_PROVIDER_ID  # noqa: E402
from content_brain.execution.kling_product_run import (  # noqa: E402
    load_kling_product_run_results,
    run_kling_product_studio_generate,
    write_kling_output_package,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

DRAGON_TOPIC = (
    "A young boy discovers an injured baby dragon under twisted forest roots in a fantasy cinematic story"
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _kling_payload(**overrides: object) -> dict:
    payload = {
        "topic_mode": "custom",
        "custom_topic": DRAGON_TOPIC,
        "duration_seconds": 30,
        "provider": "auto",
        "audio_strategy": "auto",
    }
    payload.update(overrides)
    return payload


def test_create_video_preflight_integration() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    _pass("preflight_provider", pre.get("provider") == KLING_PROVIDER_ID)
    _pass("preflight_kling_plan", bool(pre.get("kling_native_audio_plan")))
    _pass("preflight_clip_prompts", bool(pre.get("kling_clip_prompts")))


def test_router_auto_fantasy_to_kling() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    route = dict(pre.get("audio_strategy_route") or {})
    _pass("router_strategy", route.get("audio_strategy") == KLING_AUDIO_STRATEGY)


def test_generate_routing_awaiting_approval() -> None:
    service = ProductStudioService(ROOT)
    result = service.create_video_generate(_kling_payload(), runway_service=object())
    _pass("generate_kling_wired", result.get("wired") is True)
    _pass("generate_status", result.get("status") == STATUS_AWAITING_APPROVAL)
    _pass("generate_provider", result.get("provider") == KLING_PROVIDER_ID)
    _pass("approval_required", result.get("approval_required") is True)
    run_dir = Path(str(result.get("output_folder") or ""))
    _pass("output_folder_exists", run_dir.is_dir(), str(run_dir))


def test_approval_gate_requires_fields() -> None:
    service = ProductStudioService(ROOT)
    blocked = service.create_video_generate(
        _kling_payload(approve_generate=True, approved_by="", confirm_credit_spend=False),
        runway_service=object(),
    )
    _pass("approval_blocked", blocked.get("status") == STATUS_AWAITING_APPROVAL)
    _pass("approval_required", blocked.get("approval_required") is True)


def test_output_package_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "kling_ms_test"
        preflight = {
            "provider": KLING_PROVIDER_ID,
            "audio_strategy": KLING_AUDIO_STRATEGY,
            "kling_clip_count": 2,
            "kling_shot_mode": MULTISHOT_STRATEGY,
            "authoritative_topic": DRAGON_TOPIC,
        }
        write_kling_output_package(
            run_dir,
            run_id="kling_ms_test",
            preflight=preflight,
            continuity_chain={"version": "kling_continuity_chain_v1", "links": [{"from_clip_index": 1, "to_clip_index": 2}]},
        )
        for name in ("preflight.json", "approval.json", "metadata.json", "continuity_chain.json"):
            _pass(f"package_{name}", (run_dir / name).is_file())


def test_continuity_metadata_in_package() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "kling_ms_chain"
        chain = {
            "version": "kling_continuity_chain_v1",
            "run_id": "kling_ms_chain",
            "clip_count": 2,
            "links": [{"from_clip_index": 1, "to_clip_index": 2, "continuity_anchor": "dragon looks toward cave"}],
        }
        write_kling_output_package(
            run_dir,
            run_id="kling_ms_chain",
            preflight={"authoritative_topic": DRAGON_TOPIC, "kling_clip_count": 2},
            continuity_chain=chain,
        )
        loaded = json.loads((run_dir / "continuity_chain.json").read_text(encoding="utf-8"))
        _pass("continuity_version", loaded.get("version") == "kling_continuity_chain_v1")
        _pass("continuity_links", len(loaded.get("links") or []) == 1)


def test_results_loader_kling_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "kling_ms_results_test"
        run_dir = root / "outputs" / "kling_multishot_live" / run_id
        preflight = {
            "authoritative_topic": DRAGON_TOPIC,
            "provider": KLING_PROVIDER_ID,
            "audio_strategy": KLING_AUDIO_STRATEGY,
            "kling_clip_count": 2,
            "kling_shot_mode": MULTISHOT_STRATEGY,
        }
        write_kling_output_package(
            run_dir,
            run_id=run_id,
            preflight=preflight,
            metadata={
                "provider": KLING_PROVIDER_ID,
                "audio_strategy": KLING_AUDIO_STRATEGY,
                "native_audio_status": "planned",
                "clip_count": 2,
                "shot_mode": MULTISHOT_STRATEGY,
            },
        )
        payload = load_kling_product_run_results(root, run_id=run_id)
        _pass("results_found", bool(payload and payload.get("found")))
        _pass("results_provider", payload.get("provider_used") == KLING_PROVIDER_ID)
        _pass("results_shot_mode", payload.get("shot_mode") == MULTISHOT_STRATEGY)


def test_service_results_merge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "kling_ms_service_results"
        run_dir = root / "outputs" / "kling_multishot_live" / run_id
        write_kling_output_package(
            run_dir,
            run_id=run_id,
            preflight={
                "authoritative_topic": DRAGON_TOPIC,
                "provider": KLING_PROVIDER_ID,
                "audio_strategy": KLING_AUDIO_STRATEGY,
                "kling_clip_count": 1,
                "kling_shot_mode": MULTISHOT_STRATEGY,
            },
            metadata={
                "provider": KLING_PROVIDER_ID,
                "audio_strategy": KLING_AUDIO_STRATEGY,
                "native_audio_status": "completed",
                "clip_count": 1,
            },
        )
        service = ProductStudioService(root)
        merged = service.get_results(run_id=run_id)
        _pass("service_results_found", merged.get("found") is True)
        _pass("service_kling_block", bool(merged.get("kling_native_audio")))


def test_runway_narrator_generate_unchanged() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "Educational documentary mystery about science facts",
            "audio_strategy": "narrator",
            "provider": "runway",
            "duration_seconds": 30,
        }
    )
    _pass("narrator_preflight_strategy", pre.get("audio_strategy") == "narrator")
    _pass("narrator_no_kling_plan", not pre.get("kling_native_audio_plan"))
    _pass("narrator_runway_provider", pre.get("provider") == "runway")


def test_create_video_ui_wiring() -> None:
    ui_path = ROOT / "ui" / "web" / "src" / "pages" / "CreateVideoPage.tsx"
    text = ui_path.read_text(encoding="utf-8")
    _pass("ui_audio_strategy", "AUDIO_STRATEGY_OPTIONS" in text)
    _pass("ui_provider_options", "PROVIDER_OPTIONS" in text)
    _pass("ui_kling_durations", "KLING_DURATION_PRESETS" in text)
    _pass("ui_approval_gate", "Approval Gate" in text)
    _pass("ui_kling_clip_prompts", "kling_clip_prompts" in text)


def test_results_ui_wiring() -> None:
    ui_path = ROOT / "ui" / "web" / "src" / "pages" / "ResultsPage.tsx"
    text = ui_path.read_text(encoding="utf-8")
    _pass("results_kling_section", "Kling Native Audio" in text)
    _pass("results_kling_native_audio", "kling_native_audio" in text)


def test_approved_generate_mock_execution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        mock_video = Path(tmp) / "mock.mp4"
        mock_video.write_bytes(b"\x00" * 32)
        mock_result = KlingMultishotLiveResult(
            ok=True,
            status=STATUS_COMPLETED,
            run_id="mock",
            dry_run_prepare=False,
            generate_clicked=True,
            credits_spent=True,
            approved_by="operator",
            approved_at="now",
            download_path=str(mock_video),
            output_path=str(mock_video),
        )
        service = ProductStudioService(ROOT)
        preflight = service.create_video_preflight(_kling_payload(duration_seconds=15))
        run_id = "kling_ms_mock_exec"
        with patch("content_brain.execution.kling_product_run.run_kling_multishot_live", return_value=mock_result):
            result = service.create_video_generate(
                _kling_payload(
                    duration_seconds=15,
                    approve_generate=True,
                    approved_by="operator",
                    confirm_credit_spend=True,
                    run_id=run_id,
                ),
                runway_service=object(),
            )
        _pass("mock_generate_ok", result.get("ok") is True)
        _pass("mock_generate_completed", result.get("status") == STATUS_COMPLETED)


def test_regressions() -> None:
    scripts = (
        "project_brain/validate_kling_native_audio_schema_p0.py",
        "project_brain/validate_kling_native_audio_duration_planner_p1.py",
        "project_brain/validate_kling_native_audio_router_p2.py",
        "project_brain/validate_kling_native_audio_content_planner_p3.py",
        "project_brain/validate_kling_native_audio_preflight_api_p4.py",
    )
    for script in scripts:
        proc = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        _pass(f"regression_{Path(script).stem}", proc.returncode == 0, proc.stderr.strip()[-120:])


def main() -> int:
    print("validate_kling_full_product_integration")
    test_create_video_preflight_integration()
    test_router_auto_fantasy_to_kling()
    test_generate_routing_awaiting_approval()
    test_approval_gate_requires_fields()
    test_output_package_files()
    test_continuity_metadata_in_package()
    test_results_loader_kling_metadata()
    test_service_results_merge()
    test_runway_narrator_generate_unchanged()
    test_create_video_ui_wiring()
    test_results_ui_wiring()
    test_approved_generate_mock_execution()
    test_regressions()
    print("All Kling full product integration checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
