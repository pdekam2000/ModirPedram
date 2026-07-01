"""Validate MODIR-PWMAP-RUNWAY-AGENT-ADAPTER."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
PWMAP_ROOT = Path(r"C:\Users\kaman\Desktop\pwmap")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_product_run import (  # noqa: E402
    LEGACY_PRODUCT_EXECUTION,
    LEGACY_PRODUCT_EXECUTION_NOTE,
)
from content_brain.execution.pwmap_runway_agent_adapter import (  # noqa: E402
    ADAPTER_VERSION,
    PwmapAdapterError,
    build_pwmap_job,
    build_subprocess_command,
    copy_mp4_outputs,
    load_pwmap_agent_run_results,
    parse_last_result,
    resolve_pwmap_root,
    run_pwmap_agent,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_adapter_version() -> None:
    _pass("adapter_version", ADAPTER_VERSION == "pwmap_runway_agent_adapter_v1")


def test_build_job_json_single() -> None:
    job = build_pwmap_job(prompt="Neon city rain test.", duration=15, aspect="9:16", native_audio=True)
    _pass("job_prompt", job["prompt"] == "Neon city rain test.")
    _pass("job_model_default", job.get("model", "Kling 3.0 Pro") == "Kling 3.0 Pro")
    _pass("job_duration", job["duration"] == 15)
    _pass("job_aspect", job["aspect"] == "9:16")
    _pass("job_native_audio", job["native_audio"] is True)


def test_build_job_json_batch() -> None:
    job = build_pwmap_job(
        prompts=["clip one", "clip two"],
        duration=15,
        aspect="9:16",
        use_frame_second=14,
    )
    _pass("batch_prompts", job["prompts"] == ["clip one", "clip two"])
    _pass("batch_use_frame", job["use_frame_second"] == 14)


def test_subprocess_command() -> None:
    if not PWMAP_ROOT.is_dir():
        _pass("subprocess_command", True, "skipped — pwmap not installed locally")
        return
    root = resolve_pwmap_root(PWMAP_ROOT)
    cmd = build_subprocess_command(pwmap_root=root, job_path=root / "agent_inbox" / "job.json")
    _pass("cmd_has_python", cmd[0] in {"python", Path(cmd[0]).name} or "python" in cmd[0].lower())
    _pass("cmd_has_runway_agent", any("runway_agent.py" in part for part in cmd))
    _pass("cmd_has_job_flag", "--job" in cmd)


def test_missing_pwmap_clear_error() -> None:
    try:
        resolve_pwmap_root(Path(tempfile.gettempdir()) / "missing_pwmap_root_xyz")
        _pass("missing_pwmap_error", False)
    except PwmapAdapterError as exc:
        _pass("missing_pwmap_error", "pwmap root not found" in str(exc).lower())


def test_parse_last_result_fixture() -> None:
    if not (PWMAP_ROOT / "runway_downloads" / "last_result.json").is_file():
        _pass("parse_last_result", True, "skipped — no pwmap fixture")
        return
    payload = parse_last_result(PWMAP_ROOT / "runway_downloads" / "last_result.json")
    _pass("parse_status", payload.get("status") == "ok")
    _pass("parse_clips", isinstance(payload.get("clips"), list))


def test_copy_mp4_into_modir_folder() -> None:
    tmp = Path(tempfile.mkdtemp())
    src = tmp / "source.mp4"
    src.write_bytes(b"\x00" * (MIN := 1_100_000))
    last_result = {"clips": [{"clip": 1, "download": str(src)}]}
    copied, final = copy_mp4_outputs(last_result=last_result, run_dir=tmp)
    _pass("copy_count", len(copied) == 1)
    _pass("final_video", Path(final).is_file())
    _pass("clip_copy", (tmp / "clip_1.mp4").is_file())
    _pass("canonical_video", (tmp / "video.mp4").is_file())


def test_run_pwmap_agent_dry_run() -> None:
    if not PWMAP_ROOT.is_dir():
        _pass("dry_run", True, "skipped — pwmap not installed locally")
        return
    result = run_pwmap_agent(
        project_root=ROOT,
        job=build_pwmap_job(prompt="dry run prompt", duration=15),
        pwmap_root=PWMAP_ROOT,
        dry_run=True,
    )
    _pass("dry_run_ok", result.ok)
    run_dir = Path(result.run_dir)
    _pass("job_written", (run_dir / "job.json").is_file())
    _pass("normalized_written", (run_dir / "normalized_result.json").is_file())


def test_normalized_result_stable() -> None:
    tmp = Path(tempfile.mkdtemp())
    run_id = "pwmap_test_stable"
    run_dir = tmp / run_id
    run_dir.mkdir(parents=True)
    payload = {
        "version": ADAPTER_VERSION,
        "ok": True,
        "run_id": run_id,
        "status": "completed",
        "provider_runtime": "pwmap_agent",
        "video_path": str((run_dir / "video.mp4").resolve()).replace("\\", "/"),
        "clip_count": 1,
        "clips": [],
        "preflight_snapshot": {"authoritative_topic": "test topic"},
    }
    (run_dir / "video.mp4").write_bytes(b"\x00" * 1_100_000)
    (run_dir / "normalized_result.json").write_text(json.dumps(payload), encoding="utf-8")
    with patch("content_brain.execution.pwmap_runway_agent_adapter.pwmap_run_dir", return_value=run_dir):
        loaded = load_pwmap_agent_run_results(ROOT, run_id=run_id)
    _pass("loader_found", bool(loaded and loaded.get("found")))
    _pass("loader_video", bool(loaded and loaded.get("video_path")))
    _pass("loader_runtime", loaded.get("provider_runtime") == "pwmap_agent")


def test_legacy_runtime_not_deleted() -> None:
    kling_path = ROOT / "content_brain" / "execution" / "kling_product_run.py"
    frame_path = ROOT / "content_brain" / "execution" / "kling_frame_to_video_live_engine.py"
    _pass("kling_product_run_exists", kling_path.is_file())
    _pass("kling_frame_engine_exists", frame_path.is_file())
    _pass("legacy_flag", LEGACY_PRODUCT_EXECUTION is True)
    _pass("legacy_note", "pwmap_runway_agent_adapter" in LEGACY_PRODUCT_EXECUTION_NOTE)


def test_product_studio_wiring() -> None:
    src = (ROOT / "ui" / "api" / "product_studio_service.py").read_text(encoding="utf-8")
    _pass("product_uses_pwmap", "run_pwmap_product_studio_generate" in src)
    _pass("product_provider_runtime", "provider_runtime" in src)
    _pass("product_results_pwmap", "_merge_pwmap_results" in src)


def main() -> int:
    from content_brain.execution.pwmap_runway_agent_adapter import MIN_REAL_MP4_BYTES as MIN_BYTES

    globals()["MIN"] = MIN_BYTES
    print("validate_pwmap_runway_agent_adapter")
    test_adapter_version()
    test_build_job_json_single()
    test_build_job_json_batch()
    test_subprocess_command()
    test_missing_pwmap_clear_error()
    test_parse_last_result_fixture()
    test_copy_mp4_into_modir_folder()
    test_run_pwmap_agent_dry_run()
    test_normalized_result_stable()
    test_legacy_runtime_not_deleted()
    test_product_studio_wiring()
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
