"""Validate Kling download recovery fix — no re-generate, folder consolidation, Results clarity."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_live_engine import (  # noqa: E402
    STATUS_DOWNLOAD_FAILED,
    recover_kling_multishot_output,
    run_kling_multishot_live,
)
from content_brain.execution.kling_product_run import (  # noqa: E402
    STATUS_DOWNLOAD_FAILED_REPORT,
    _summarize_generation_status,
    kling_clip_dir,
    kling_run_dir,
    legacy_sibling_run_dir,
    load_kling_product_run_results,
    recover_kling_product_run,
    resolve_kling_parent_run_id,
    write_kling_output_package,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_recover_mode_never_clicks_generate() -> None:
    source = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    recover_block = source.split("def recover_kling_multishot_output", 1)[1].split("def ", 1)[0]
    _pass("recover_no_generate_click", "generate.locator.click" not in recover_block)
    _pass("recover_no_approval_gate", "grant_continuity_approval" not in recover_block)


def test_recover_mode_never_spends_credits() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "kling_ms_recover_test"
        run_dir = kling_run_dir(root, run_id)
        clip_dir = kling_clip_dir(run_dir, 1)
        fake_video = clip_dir / "video.mp4"
        fake_video.write_bytes(b"\x00" * 64)

        def _fake_recover(**kwargs: object):
            from content_brain.execution.kling_multishot_live_engine import KlingMultishotLiveResult, STATUS_COMPLETED

            return KlingMultishotLiveResult(
                ok=True,
                status=STATUS_COMPLETED,
                run_id=run_id,
                dry_run_prepare=False,
                generate_clicked=False,
                credits_spent=False,
                generation_completed=True,
                download_status="passed",
                recovery_mode=True,
                approved_by=None,
                approved_at=None,
                download_path=str(fake_video),
                output_path=str(fake_video),
            )

        with patch("content_brain.execution.kling_product_run.recover_kling_multishot_output", side_effect=_fake_recover):
            result = recover_kling_product_run(project_root=root, run_id=f"{run_id}_c1", clip_index=1)
        _pass("recover_generate_clicked_false", result.get("generate_clicked") is False)
        _pass("recover_credits_spent_false", result.get("credits_spent") is False)
        _pass("recover_mode_flag", result.get("recovery_mode") is True)


def test_failed_download_status_reported_clearly() -> None:
    clip_results = [
        {
            "ok": False,
            "status": STATUS_DOWNLOAD_FAILED,
            "generate_clicked": True,
            "credits_spent": True,
            "generation_completed": True,
            "download_status": "failed",
            "steps": [
                {"label": "generation_wait", "status": "passed"},
                {"label": "download", "status": "failed", "detail": "Could not download MP4 output"},
            ],
        }
    ]
    status = _summarize_generation_status(clip_results, final_video="")
    _pass("download_failed_status", status == STATUS_DOWNLOAD_FAILED_REPORT)


def test_parent_clip_folder_structure_correct() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "kling_ms_folder_test"
        run_dir = kling_run_dir(root, run_id)
        clip_dir = kling_clip_dir(run_dir, 1)
        (clip_dir / "video.mp4").write_bytes(b"\x00" * 32)
        _pass("parent_run_dir", run_dir.is_dir(), str(run_dir))
        _pass("clip_dir_c1", clip_dir.is_dir() and clip_dir.name == "c1", str(clip_dir))
        _pass("clip_under_parent", "clips" in clip_dir.parts)


def test_sibling_c1_not_canonical_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent_id = "kling_ms_legacy_test"
        sibling = legacy_sibling_run_dir(root, parent_id, 1)
        sibling.mkdir(parents=True)
        (sibling / "video.mp4").write_bytes(b"\x00" * 16)

        run_dir = kling_run_dir(root, parent_id)
        run_dir.mkdir(parents=True)
        write_kling_output_package(
            run_dir,
            run_id=parent_id,
            preflight={"authoritative_topic": "Legacy test", "kling_clip_count": 1},
            generation_report={"status": STATUS_DOWNLOAD_FAILED_REPORT, "recovery_available": True},
            download_report={"status": "failed", "recovery_available": True},
            metadata={
                "native_audio_status": "download_failed",
                "generation_status": STATUS_DOWNLOAD_FAILED_REPORT,
                "recovery_available": True,
                "output_ready": False,
            },
        )
        payload = load_kling_product_run_results(root, run_id=f"{parent_id}_c1")
        assert payload is not None
        _pass("resolve_parent_from_sibling", payload.get("selected_run_id") == parent_id)
        _pass("legacy_folder_recorded", sibling.as_posix() in "".join(payload.get("legacy_run_folders") or []))
        _pass("canonical_not_sibling_video", not str(payload.get("video_path") or "").endswith(f"{parent_id}_c1/video.mp4"))


def test_generation_success_download_failure_not_final_success() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "kling_ms_partial_success"
        run_dir = kling_run_dir(root, run_id)
        run_dir.mkdir(parents=True)
        write_kling_output_package(
            run_dir,
            run_id=run_id,
            preflight={"authoritative_topic": "Partial", "kling_clip_count": 1},
            generation_report={
                "status": STATUS_DOWNLOAD_FAILED_REPORT,
                "recovery_available": True,
                "output_ready": False,
                "clip_results": [{"generate_clicked": True, "generation_completed": True, "download_status": "failed"}],
            },
            download_report={"status": "failed", "recovery_available": True, "final_video_path": ""},
            metadata={
                "native_audio_status": "download_failed",
                "generation_status": STATUS_DOWNLOAD_FAILED_REPORT,
                "recovery_available": True,
                "output_ready": False,
            },
        )
        payload = load_kling_product_run_results(root, run_id=run_id)
        assert payload is not None
        _pass("not_output_ready", payload.get("output_ready") is False)
        _pass("recovery_available_true", payload.get("recovery_available") is True)
        _pass("native_status_download_failed", payload.get("native_audio_status") == "download_failed")


def test_results_page_shows_pending_recovery() -> None:
    page = (ROOT / "ui/web/src/pages/ResultsPage.tsx").read_text(encoding="utf-8")
    _pass("results_recovery_available", "Recovery Available" in page)
    _pass("results_output_ready", "Output Ready" in page)
    _pass("results_download_failed_message", "Download failed after generation completed" in page)
    _pass("results_output_not_ready_message", "Output not ready until MP4 exists" in page)


def test_download_engine_has_blob_and_http_fallback() -> None:
    source = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    _pass("blob_fetch_present", "_fetch_blob_via_page" in source)
    _pass("http_fetch_present", "_fetch_http_via_page" in source)
    _pass("menu_download_present", "menuitem_download" in source)


def test_runner_has_recover_flag() -> None:
    source = (ROOT / "tools/kling_multishot_live_runner.py").read_text(encoding="utf-8")
    _pass("runner_recover_flag", "--recover-latest-output" in source)
    _pass("runner_recover_requires_run_id", "requires --run-id" in source)


def test_product_run_uses_parent_clip_dirs() -> None:
    source = (ROOT / "content_brain/execution/kling_product_run.py").read_text(encoding="utf-8")
    _pass("no_sibling_run_id_in_execute", 'f"{run_id}_c{clip.clip_index}"' not in source.split("def _execute_kling_clips", 1)[1].split("def run_kling_product_studio_generate", 1)[0])
    _pass("output_dir_passed", "output_dir=clip_dir" in source)


def main() -> None:
    test_recover_mode_never_clicks_generate()
    test_recover_mode_never_spends_credits()
    test_failed_download_status_reported_clearly()
    test_parent_clip_folder_structure_correct()
    test_sibling_c1_not_canonical_output()
    test_generation_success_download_failure_not_final_success()
    test_results_page_shows_pending_recovery()
    test_download_engine_has_blob_and_http_fallback()
    test_runner_has_recover_flag()
    test_product_run_uses_parent_clip_dirs()
    print("validate_kling_download_recovery_fix: all checks passed")


if __name__ == "__main__":
    main()
