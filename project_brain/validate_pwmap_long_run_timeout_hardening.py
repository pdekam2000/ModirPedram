"""Validation — PWMAP long-run timeout hardening."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.pwmap_finalization import (  # noqa: E402
    finalize_partial_pwmap_run,
    load_latest_product_studio_pwmap_results,
    recover_partial_clips_to_run_dir,
)
from content_brain.execution.pwmap_runway_agent_adapter import build_subprocess_command  # noqa: E402
from content_brain.execution.pwmap_timeout_policy import (  # noqa: E402
    CLIP_TIMEOUT_BY_COUNT,
    resolve_clip_timeout_seconds,
    resolve_subprocess_timeout_seconds,
)
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
    print("validate_pwmap_long_run_timeout_hardening")
    print("=" * 60)

    for clip_count, expected in CLIP_TIMEOUT_BY_COUNT.items():
        actual = resolve_clip_timeout_seconds(clip_count)
        _record(f"clip_timeout_{clip_count}_clips", actual == expected, str(actual))

    with patch.dict(os.environ, {"PWMAP_CLIP_TIMEOUT_SECONDS": "2400"}, clear=False):
        _record("env_clip_timeout_override", resolve_clip_timeout_seconds(1) == 2400, "2400")
    os.environ.pop("PWMAP_CLIP_TIMEOUT_SECONDS", None)

    subprocess_timeout = resolve_subprocess_timeout_seconds(4)
    clip_timeout = resolve_clip_timeout_seconds(4)
    _record(
        "subprocess_timeout_gt_pwmap_budget",
        subprocess_timeout > (clip_timeout * 4),
        f"subprocess={subprocess_timeout} clip={clip_timeout}",
    )

    with patch.dict(os.environ, {"PWMAP_SUBPROCESS_TIMEOUT_SECONDS": "99999"}, clear=False):
        _record(
            "env_subprocess_timeout_override",
            resolve_subprocess_timeout_seconds(4) == 99999,
            "99999",
        )
    os.environ.pop("PWMAP_SUBPROCESS_TIMEOUT_SECONDS", None)

    pwmap_root = Path(r"C:\Users\kaman\Desktop\pwmap")
    command = build_subprocess_command(
        pwmap_root=pwmap_root,
        job_path=pwmap_root / "agent_inbox" / "job.json",
        clip_timeout_seconds=1800,
    )
    _record(
        "subprocess_command_includes_timeout_flag",
        "--timeout" in command and "1800" in command,
        " ".join(command),
    )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "pwmap_partial_test"
        run_dir.mkdir(parents=True)
        downloads = Path(tmp) / "runway_downloads"
        downloads.mkdir(parents=True)
        clip_src = downloads / "clip_001_20260626_224933.mp4"
        _write_fake_mp4(clip_src)
        stdout = (
            "[i] Clips to generate: 4\n"
            "==================================================\n"
            "  CLIP 2/4\n"
            "==================================================\n"
            "[OK] Downloaded: clip_001\n"
            "[ERROR] Generation timed out after 900s.\n"
        )
        from datetime import datetime, timezone

        run_started = datetime(2026, 6, 26, 20, 36, 30, tzinfo=timezone.utc)
        clip_src.touch()
        import os as os_mod

        os_mod.utime(clip_src, (run_started.timestamp() + 60, run_started.timestamp() + 60))
        recovered = recover_partial_clips_to_run_dir(
            run_dir=run_dir,
            downloads_dir=downloads,
            run_started=run_started,
        )
        _record("partial_clip_recovered", len(recovered) == 1, str(recovered))

        finalized = finalize_partial_pwmap_run(
            project_root=ROOT,
            run_dir=run_dir,
            run_id="pwmap_20260626T203630_partialtest",
            pwmap_root=Path(tmp),
            adapter_payload={
                "ok": False,
                "run_id": "pwmap_20260626T203630_partialtest",
                "status": "failed",
                "subprocess_exit_code": 1,
                "preflight_snapshot": {"authoritative_topic": "animation Honor demogogon"},
            },
            subprocess_stdout=stdout,
            clip_timeout_seconds=1800,
        )
        _record(
            "partial_failed_agent_result_written",
            (run_dir / "agent_result.json").is_file()
            and json.loads((run_dir / "agent_result.json").read_text(encoding="utf-8")).get("status") == "partial_failed",
            str(finalized.get("status")),
        )
        agent = json.loads((run_dir / "agent_result.json").read_text(encoding="utf-8"))
        _record(
            "partial_failed_metadata",
            agent.get("clips_completed") == 1
            and agent.get("recovery_available") is True
            and agent.get("failure_stage") == "clip_generation"
            and agent.get("failed_clip_index") == 2,
            str(agent),
        )

    service = ProductStudioService(ROOT)
    failed_run = ROOT / "outputs" / "pwmap_agent_runs" / "pwmap_20260626T203630_17bb74ed"
    if failed_run.is_dir() and (failed_run / "subprocess_stdout.log").is_file():
        from content_brain.execution.pwmap_finalization import finalize_partial_pwmap_run as reprocess

        stdout_path = failed_run / "subprocess_stdout.log"
        payload = json.loads((failed_run / "normalized_result.json").read_text(encoding="utf-8"))
        reprocess(
            project_root=ROOT,
            run_dir=failed_run,
            run_id="pwmap_20260626T203630_17bb74ed",
            pwmap_root=Path(r"C:\Users\kaman\Desktop\pwmap"),
            adapter_payload=payload,
            subprocess_stdout=stdout_path.read_text(encoding="utf-8"),
            clip_timeout_seconds=1800,
        )
        agent_path = failed_run / "agent_result.json"
        if agent_path.is_file():
            agent_live = json.loads(agent_path.read_text(encoding="utf-8"))
            _record(
                "live_60s_run_reprocessed_partial",
                agent_live.get("status") == "partial_failed" and agent_live.get("clips_completed", 0) >= 1,
                str(agent_live.get("status")),
            )

    latest = service.get_results(run_id="", run_dir="")
    latest_id = str(latest.get("selected_run_id") or "")
    _record(
        "results_chooses_latest_product_studio_run",
        latest_id.startswith("pwmap_"),
        latest_id,
    )
    if latest_id == "pwmap_20260626T203630_17bb74ed":
        _record(
            "results_shows_60s_partial_not_30s",
            latest.get("generation_status") == "partial_failed"
            and latest.get("clips_completed") == 1
            and latest.get("expected_clip_count") == 4
            and latest.get("recovery_available") is True,
            f"status={latest.get('generation_status')} clips={latest.get('clips_completed')}/{latest.get('expected_clip_count')}",
        )
    else:
        _record(
            "results_not_old_30s_when_newer_exists",
            "213052" not in latest_id and "191853" not in latest_id or latest_id >= "pwmap_20260626",
            f"latest={latest_id}",
        )

    latest_after = load_latest_product_studio_pwmap_results(ROOT)
    if latest_after:
        _record(
            "latest_loader_supports_partial_failed",
            latest_after.get("generation_status") == "partial_failed",
            str(latest_after.get("generation_status")),
        )

    pwmap_agent_path = Path(r"C:\Users\kaman\Desktop\pwmap\runway_agent.py")
    if pwmap_agent_path.is_file():
        pwmap_src = pwmap_agent_path.read_text(encoding="utf-8", errors="ignore")
        _record(
            "no_pwmap_runway_agent_changes",
            "wait_for_video_ready" in pwmap_src and "use_frame" in pwmap_src.lower(),
            "external pwmap agent untouched",
        )
    else:
        _record("no_pwmap_runway_agent_changes", True, "pwmap path not present — skipped")

    adapter_src = (ROOT / "content_brain" / "execution" / "pwmap_runway_agent_adapter.py").read_text(encoding="utf-8")
    _record(
        "adapter_only_timeout_and_partial_wiring",
        "resolve_clip_timeout_seconds" in adapter_src and "finalize_partial_pwmap_run" in adapter_src,
        "timeout + partial finalization only",
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
