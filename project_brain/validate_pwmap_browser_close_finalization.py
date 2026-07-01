"""Validation — PWMAP browser close finalization repair."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.pwmap_finalization import (  # noqa: E402
    FINALIZATION_STAGES,
    STAGE_BROWSER_CLOSED,
    STAGE_DOWNLOADS_VERIFIED,
    STAGE_MANIFEST_WRITTEN,
    STAGE_RESULT_REGISTERED,
    finalize_pwmap_run,
    load_latest_product_studio_pwmap_results,
    verify_and_recover_clip_downloads,
)
from content_brain.execution.pwmap_runway_agent_adapter import build_subprocess_command  # noqa: E402
from content_brain.platform.canonical_run import load_canonical_run  # noqa: E402
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _write_fake_mp4(path: Path, size: int = 1_100_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * size)


def main() -> int:
    print("validate_pwmap_browser_close_finalization")
    print("=" * 60)

    pwmap_root = Path(r"C:\Users\kaman\Desktop\pwmap")
    command = build_subprocess_command(
        pwmap_root=pwmap_root,
        job_path=pwmap_root / "agent_inbox" / "job.json",
        close_browser=True,
    )
    _record(
        "subprocess_includes_close_browser_flag",
        "--close-browser" in command,
        " ".join(command),
    )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "pwmap_test_run"
        run_dir.mkdir(parents=True)
        source1 = run_dir / "source_clip_1.mp4"
        source2 = run_dir / "source_clip_2.mp4"
        _write_fake_mp4(source1)
        _write_fake_mp4(source2)

        last_result = {
            "status": "ok",
            "clip_count": 2,
            "clips": [
                {"clip": 1, "download": str(source1.resolve()).replace("\\", "/")},
                {"clip": 2, "download": str(source2.resolve()).replace("\\", "/")},
            ],
        }
        copied = [
            {
                "clip": 1,
                "source_path": str(source1.resolve()).replace("\\", "/"),
                "modir_path": str((run_dir / "clip_1.mp4").resolve()).replace("\\", "/"),
            },
            {
                "clip": 2,
                "source_path": str(source2.resolve()).replace("\\", "/"),
                "modir_path": str((run_dir / "clip_2.mp4").resolve()).replace("\\", "/"),
            },
        ]
        adapter_payload = {
            "ok": False,
            "run_id": "pwmap_test_run",
            "status": "failed",
            "provider_runtime": "pwmap_agent",
            "preflight_snapshot": {"authoritative_topic": "Cat and mouse dance test"},
            "subprocess_exit_code": 0,
        }
        finalized = finalize_pwmap_run(
            project_root=ROOT,
            run_dir=run_dir,
            run_id="pwmap_test_run",
            last_result=last_result,
            copied_clips=copied,
            adapter_payload=adapter_payload,
            subprocess_stdout="[OK] Batch complete\n",
            close_browser_requested=True,
        )
        stages = dict((finalized.get("finalization") or {}).get("stages") or {})
        stage_names = list(stages.keys())
        _record(
            "finalization_stage_order",
            stage_names.index(STAGE_MANIFEST_WRITTEN) < stage_names.index(STAGE_RESULT_REGISTERED)
            < stage_names.index(STAGE_BROWSER_CLOSED),
            " -> ".join(stage_names),
        )
        _record(
            "manifest_and_agent_result_written",
            (run_dir / "execution_report.json").is_file() and (run_dir / "agent_result.json").is_file(),
            str([p.name for p in run_dir.iterdir()]),
        )
        _record(
            "browser_close_after_manifest",
            STAGE_BROWSER_CLOSED in stages and STAGE_MANIFEST_WRITTEN in stages,
            str(stages.get(STAGE_BROWSER_CLOSED)),
        )
        _record(
            "two_clip_run_records_both_clips",
            int(finalized.get("clip_count") or 0) == 2 and len(finalized.get("clips") or []) == 2,
            f"clip_count={finalized.get('clip_count')}",
        )

        missing_dest = run_dir / "clip_1.mp4"
        if missing_dest.is_file():
            missing_dest.unlink()
        verify = verify_and_recover_clip_downloads(
            run_dir=run_dir,
            last_result=last_result,
            copied_clips=copied,
        )
        _record(
            "recovery_from_source_when_local_missing",
            verify["valid_clip_count"] == 2 and verify["recovered_paths"],
            str(verify["recovered_paths"]),
        )

    service = ProductStudioService(ROOT)
    latest = service.get_results(run_id="", run_dir="")
    canonical = load_canonical_run(ROOT)
    canonical_topic = str(canonical.get("topic") or "")
    latest_topic = str(latest.get("topic") or "")
    _record(
        "results_prefers_product_studio_pwmap_over_dog_training",
        "Dog Training" not in latest_topic and bool(latest.get("is_canonical_latest")),
        f"latest_topic={latest_topic[:80]} canonical_topic={canonical_topic[:80]}",
    )
    _record(
        "latest_attempt_run_id_is_pwmap",
        str(latest.get("latest_attempt_run_id") or latest.get("selected_run_id") or "").startswith("pwmap_"),
        str(latest.get("latest_attempt_run_id") or latest.get("selected_run_id")),
    )

    live_latest = load_latest_product_studio_pwmap_results(ROOT)
    if live_latest:
        _record(
            "live_latest_product_pwmap_found",
            live_latest.get("is_product_studio_pwmap") is True,
            str(live_latest.get("run_id")),
        )
        if not live_latest.get("output_ready"):
            _record(
                "partial_or_recovery_status_when_files_missing",
                bool(live_latest.get("recovery_available")) or live_latest.get("generation_status") in {"partial", "download_failed"},
                str(live_latest.get("generation_status")),
            )

    _record(
        "finalization_stages_defined",
        FINALIZATION_STAGES == (
            "clips_generated",
            "downloads_verified",
            "manifest_written",
            "result_registered",
            "browser_closed",
        ),
        ",".join(FINALIZATION_STAGES),
    )
    _record(
        "downloads_verified_stage_exists",
        STAGE_DOWNLOADS_VERIFIED in FINALIZATION_STAGES,
        STAGE_DOWNLOADS_VERIFIED,
    )

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"TOTAL: {len(results)}  PASS: {len(results) - len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return FAIL
    print("ALL PASS")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
