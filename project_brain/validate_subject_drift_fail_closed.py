"""Validate fail-closed run isolation for PHASE SUBJECT-DRIFT-REPAIR-1."""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.voice_identity_registry import apply_voice_identity_registry, save_voice_identity_registry
from content_brain.execution.runway_live_post_processor import evaluate_post_processing_eligibility, run_live_post_processing
from content_brain.platform.final_delivery_registry import load_final_delivery_registry, save_final_delivery_registry, try_update_final_delivery_registry
from content_brain.platform.results_run_loader import load_run_results
from content_brain.platform.run_isolation import (
    FAIL_MESSAGE,
    classify_runway_report_outcome,
    create_isolated_run_context,
    load_latest_run_attempt,
    load_run_context,
    record_latest_run_attempt,
    require_story_package_for_run,
)
from content_brain.platform.run_output_versioning import finalize_versioned_run_layout, create_versioned_run_layout
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@dataclass
class FakeReport:
    ok: bool = False
    simulate: bool = False
    clip_count: int = 3
    clips_completed: int = 0
    total_downloads_completed: int = 0
    downloaded_file_paths: list[str] = field(default_factory=list)
    content_brain_run_id: str = "cb_park_fail"
    content_brain_topic: str = "fantezy girl and man talking together in park"
    post_processing_status: str = ""
    post_processing_warnings: list[str] = field(default_factory=list)


PARK_TOPIC = "fantezy girl and man talking together in park"
CAT_TOPIC = "Cute orange cartoon cat explorer Whiskers in crystal jungle"
APPROVED_RUN = "cb_sv1_20260613_095159_5fdbc1ce"
PARK_RUN = "cb_e2e_20260613_120215_7eda6674"


def test_isolated_run_context_for_park_topic() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        context = create_isolated_run_context(
            tmp,
            run_id=PARK_RUN,
            topic=PARK_TOPIC,
            clip_count=3,
        )
        _pass("context_run_id", context.run_id == PARK_RUN)
        _pass("context_topic", context.topic == PARK_TOPIC)
        _pass("story_package_exists", Path(context.story_package_path).is_file())
        _pass("voice_scope", context.voice_registry_scope == PARK_RUN)
        _pass("output_folder", Path(context.output_run_folder).is_dir())
        stored = load_run_context(tmp, PARK_RUN)
        _pass("context_persisted", stored.get("run_id") == PARK_RUN)


def test_zero_clips_skips_post_processing() -> None:
    report = FakeReport(ok=False, clips_completed=0, downloaded_file_paths=[])
    eligible, reason, _ = evaluate_post_processing_eligibility(report)
    _pass("zero_clips_not_eligible", eligible is False)
    _pass("zero_clips_reason", reason in {"run_not_ok", "zero_clips_completed", "zero_valid_downloads"})
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = run_live_post_processing(report, project_root=Path(tmp_dir))
        _pass("post_processing_skipped", result.get("enabled") is False)
        _pass("post_processing_status_skipped", result.get("status") == "skipped")


def test_registry_keeps_previous_approved_on_failed_run() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        approved_video = tmp / "approved" / "cat_final.mp4"
        approved_video.parent.mkdir(parents=True, exist_ok=True)
        approved_video.write_bytes(b"approved-cat")
        save_final_delivery_registry(
            tmp,
            {
                "version": "final_delivery_registry_v1",
                "latest_run_id": APPROVED_RUN,
                "latest_video": str(approved_video),
                "latest_publish_package": str(tmp / "approved" / "publish"),
                "approved": True,
                "topic": CAT_TOPIC,
            },
        )
        updated, registry, reason = try_update_final_delivery_registry(
            tmp,
            run_id=PARK_RUN,
            latest_video=tmp / "should_not_exist.mp4",
            latest_publish_package=tmp / "should_not_publish",
            approved=True,
            topic=PARK_TOPIC,
            clips_completed=0,
            assembly_status="",
            reality_audit_passed=False,
        )
        _pass("registry_not_updated", updated is False, reason)
        _pass("registry_run_id_preserved", registry.get("latest_run_id") == APPROVED_RUN)
        _pass("registry_video_preserved", registry.get("latest_video") == str(approved_video.resolve()))


def test_latest_attempt_marked_failed() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        payload = record_latest_run_attempt(
            tmp,
            {
                "ok": False,
                "simulate": False,
                "clips_completed": 0,
                "downloaded_file_paths": [],
                "content_brain_run_id": PARK_RUN,
                "content_brain_topic": PARK_TOPIC,
            },
        )
        _pass("attempt_status_failed", payload.get("status") == "failed")
        _pass("attempt_message", FAIL_MESSAGE in str(payload.get("message") or ""))
        loaded = load_latest_run_attempt(tmp)
        _pass("attempt_persisted", loaded.get("run_id") == PARK_RUN)


def test_results_separate_approved_and_attempt() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        run_dir = tmp / "outputs" / "runs" / "20260613_park_fail"
        run_dir.mkdir(parents=True, exist_ok=True)
        _write(
            run_dir / "metadata" / "run_summary.json",
            {"run_id": PARK_RUN, "topic": PARK_TOPIC, "run_dir": str(run_dir)},
        )
        _write(
            tmp / "outputs" / "runs" / "index.json",
            {
                "version": "platform_run_index_v1",
                "runs": [{"run_id": PARK_RUN, "topic": PARK_TOPIC, "run_dir": str(run_dir)}],
            },
        )
        approved_video = tmp / "approved" / "cat_final.mp4"
        approved_video.parent.mkdir(parents=True, exist_ok=True)
        approved_video.write_bytes(b"approved-cat")
        save_final_delivery_registry(
            tmp,
            {
                "version": "final_delivery_registry_v1",
                "latest_run_id": APPROVED_RUN,
                "latest_video": str(approved_video),
                "latest_publish_package": str(tmp / "approved" / "publish"),
                "approved": True,
                "topic": CAT_TOPIC,
            },
        )
        record_latest_run_attempt(
            tmp,
            {
                "ok": False,
                "simulate": False,
                "clips_completed": 0,
                "downloaded_file_paths": [],
                "content_brain_run_id": PARK_RUN,
                "content_brain_topic": PARK_TOPIC,
            },
        )
        results = load_run_results(tmp)
        _pass("results_no_name_error", isinstance(results, dict))
        _pass("approved_video_path", results.get("latest_approved_video_path") == str(approved_video.resolve()))
        _pass("approved_run_id", results.get("approved_run_id") == APPROVED_RUN)
        _pass("attempt_failed", results.get("latest_attempt_status") == "failed")
        _pass("attempt_run_id", results.get("latest_attempt_run_id") == PARK_RUN)
        _pass("attempt_topic", results.get("latest_attempt_topic") == PARK_TOPIC)
        _pass("attempt_not_approved_run", results.get("latest_attempt_run_id") != results.get("approved_run_id"))


def test_story_package_missing_no_cat_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        cat_pkg = tmp / "project_brain" / "story_packages" / f"{APPROVED_RUN}.json"
        _write(
            cat_pkg,
            {
                "topic": CAT_TOPIC,
                "character_profiles": [{"name": "Whiskers"}, {"name": "Sage"}],
                "story_blueprint": {"genre": "cartoon"},
            },
        )
        ok, reason, path = require_story_package_for_run(tmp, PARK_RUN, topic=PARK_TOPIC)
        _pass("missing_story_package", ok is False)
        _pass("missing_reason", reason == "story_package_missing")
        _pass("no_cat_path", path == "")


def test_voice_registry_no_whiskers_sage_for_park() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        save_voice_identity_registry(
            tmp,
            {
                "version": "voice_identity_registry_v1",
                "characters": {
                    "whiskers": {"character": "Whiskers", "voice_id": "voice_whiskers"},
                    "sage": {"character": "Sage", "voice_id": "voice_sage"},
                },
            },
        )
        cast = apply_voice_identity_registry(
            project_root=tmp,
            voice_cast_plan={
                "narrator": {"voice_id": "voice_narrator"},
                "characters": [
                    {"character": "Girl", "voice_id": "voice_girl"},
                    {"character": "Man", "voice_id": "voice_man"},
                ],
            },
            run_id=PARK_RUN,
            topic=PARK_TOPIC,
        )
        names = {str(row.get("character") or "").lower() for row in cast.get("characters") or []}
        voice_ids = {str(row.get("voice_id") or "") for row in cast.get("characters") or []}
        _pass("park_cast_names", "girl" in names and "man" in names)
        _pass("no_whiskers_voice", "voice_whiskers" not in voice_ids)
        _pass("no_sage_voice", "voice_sage" not in voice_ids)
        scope_path = Path(str(cast.get("voice_registry_scope_path") or ""))
        _pass("scope_file_written", scope_path.is_file())


def test_asset_library_not_updated_for_failed_run() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        from content_brain.platform.asset_library import load_asset_index

        before = len(list(load_asset_index(tmp).get("assets") or []))
        layout = create_versioned_run_layout(tmp, run_id=PARK_RUN, topic=PARK_TOPIC)
        finalize_versioned_run_layout(
            tmp,
            layout,
            assembly_manifest={"status": "FAILED", "clip_count": 0},
            publish_manifest={"status": "SKIPPED"},
        )
        after = len(list(load_asset_index(tmp).get("assets") or []))
        _pass("asset_count_unchanged", before == after)


def test_results_endpoint_no_collect_valid_download_paths_error() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        service = ProductStudioService(tmp)
        try:
            payload = service.latest_results()
        except NameError as exc:
            _pass("results_endpoint_name_error", False, str(exc))
            return
        _pass("results_endpoint_name_error", True)
        _pass("results_endpoint_returns_dict", isinstance(payload, dict))


def test_prompt_builder_subject_matches_run_topic() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        context = create_isolated_run_context(tmp, run_id=PARK_RUN, topic=PARK_TOPIC, clip_count=3)
        package = json.loads(Path(context.story_package_path).read_text(encoding="utf-8"))
        _pass("story_package_topic", str(package.get("topic") or "").lower() == PARK_TOPIC.lower())
        status, _ = classify_runway_report_outcome(
            {
                "ok": True,
                "simulate": False,
                "clips_completed": 3,
                "downloaded_file_paths": [],
                "content_brain_topic": PARK_TOPIC,
            }
        )
        _pass("zero_downloads_fail_closed", status == "failed")


def main() -> None:
    tests = [
        test_isolated_run_context_for_park_topic,
        test_zero_clips_skips_post_processing,
        test_registry_keeps_previous_approved_on_failed_run,
        test_latest_attempt_marked_failed,
        test_results_separate_approved_and_attempt,
        test_story_package_missing_no_cat_fallback,
        test_voice_registry_no_whiskers_sage_for_park,
        test_asset_library_not_updated_for_failed_run,
        test_results_endpoint_no_collect_valid_download_paths_error,
        test_prompt_builder_subject_matches_run_topic,
    ]
    print("PHASE SUBJECT-DRIFT-REPAIR-1 — fail-closed validation")
    print("=" * 60)
    for test in tests:
        test()
    print("=" * 60)
    print(f"ALL {len(tests)} CHECKS PASSED")


if __name__ == "__main__":
    main()
