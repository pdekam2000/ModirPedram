"""Validate Results run consistency — no mixed manifests across runs."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.results_run_loader import detect_mixed_manifests, load_run_results
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _seed_run(
    tmp: Path,
    *,
    folder: str,
    run_id: str,
    topic: str,
    clip_count: int,
    continuity_pass: bool,
) -> Path:
    run_dir = tmp / "outputs" / "runs" / folder
    publish_dir = run_dir / "publish"
    metadata_dir = run_dir / "metadata"
    publish_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    downloads = [str(tmp / "downloads" / f"{run_id}_clip_{index}.mp4") for index in range(1, clip_count + 1)]
    for path_text in downloads:
        Path(path_text).parent.mkdir(parents=True, exist_ok=True)
        Path(path_text).write_bytes(b"clip")

    branded = publish_dir / "FINAL_BRANDED_VIDEO.mp4"
    branded.write_bytes(b"branded")
    final_video = run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"final")

    _write(
        run_dir / "publish" / "metadata.json",
        {
            "run_id": run_id,
            "topic": topic,
            "clip_count": clip_count,
            "downloaded_file_paths": downloads,
            "branded_video_path": str(branded),
            "branding_status": "completed",
            "branding_enabled": True,
        },
    )
    _write(
        metadata_dir / "run_summary.json",
        {
            "run_id": run_id,
            "topic": topic,
            "run_dir": str(run_dir),
            "publish_dir": str(publish_dir),
            "assembly_status": "ASSEMBLED",
            "publish_status": "PUBLISHED_PACKAGE_CREATED",
        },
    )
    _write(
        metadata_dir / "visual_continuity_report.json",
        {
            "run_id": run_id,
            "topic": topic,
            "overall_pass": continuity_pass,
            "overall_score": 95 if continuity_pass else 40,
            "clips": [
                {"clip_index": index, "pass": continuity_pass, "score": 95 if continuity_pass else 40}
                for index in range(1, clip_count + 1)
            ],
        },
    )
    _write(
        metadata_dir / "assembly_manifest.json",
        {"run_id": run_id, "status": "ASSEMBLED", "clip_count": clip_count, "output_path": str(final_video)},
    )
    _write(
        metadata_dir / "publish_manifest.json",
        {"run_id": run_id, "status": "PUBLISHED_PACKAGE_CREATED", "package_folder": str(publish_dir)},
    )
    _write(
        run_dir / "raw_downloads_manifest.json",
        {"run_id": run_id, "downloaded_file_paths": downloads},
    )
    return run_dir


def test_mixed_manifests_detected() -> None:
    stale = detect_mixed_manifests(
        expected_run_id="run_a",
        publish_meta={"run_id": "run_b"},
        visual_continuity={"run_id": "run_a", "clips": [{}]},
        raw_downloads={"run_id": "run_a"},
        assembly_manifest={"run_id": "run_a"},
        publish_manifest={"run_id": "run_a"},
        runway_report={"content_brain_run_id": "run_b"},
    )
    _pass("mixed_publish_detected", "publish" in stale)
    _pass("mixed_runway_detected", "runway_report" in stale)


def test_stale_sections_hidden() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        latest_dir = _seed_run(tmp, folder="20260611_latest_run_a", run_id="run_a", topic="lion", clip_count=3, continuity_pass=False)
        _seed_run(tmp, folder="20260610_old_run_b", run_id="run_b", topic="grafig", clip_count=6, continuity_pass=True)

        _write(
            tmp / "outputs" / "runs" / "index.json",
            {
                "runs": [
                    {
                        "run_id": "run_a",
                        "topic": "lion",
                        "run_dir": str(latest_dir),
                        "assembly_status": "ASSEMBLED",
                        "publish_status": "PUBLISHED_PACKAGE_CREATED",
                    },
                    {
                        "run_id": "run_b",
                        "topic": "grafig",
                        "run_dir": str(tmp / "outputs" / "runs" / "20260610_old_run_b"),
                        "assembly_status": "ASSEMBLED",
                        "publish_status": "PUBLISHED_PACKAGE_CREATED",
                    },
                ]
            },
        )
        _write(
            tmp / "project_brain" / "runtime_state" / "visual_continuity_report.json",
            {
                "run_id": "run_b",
                "topic": "grafig",
                "overall_pass": True,
                "clips": [{"clip_index": i, "pass": True, "score": 99} for i in range(1, 7)],
            },
        )
        _write(
            tmp / "project_brain" / "runway_phase_i_3clip_last_report.json",
            {"content_brain_run_id": "run_b", "clip_count": 6, "downloaded_file_paths": [], "ok": True, "simulate": False},
        )
        (tmp / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        _write(tmp / "project_brain" / "product_settings" / "channel_profile.json", {"upload_platforms": ["youtube_shorts"]})

        latest = load_run_results(tmp)
        _pass("latest_run_id", latest.get("selected_run_id") == "run_a")
        _pass("latest_clip_count", latest.get("downloaded_clip_count") == 3, str(latest.get("downloaded_clip_count")))
        _pass("latest_continuity_clips", len((latest.get("visual_continuity") or {}).get("clips") or []) == 3)
        _pass("no_grafig_topic", latest.get("topic") == "lion")
        _pass("visual_not_hidden", latest.get("section_availability", {}).get("visual_continuity") == "available")


def test_latest_run_folder_is_canonical() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        latest_dir = _seed_run(tmp, folder="20260611_latest_run_a", run_id="run_a", topic="lion", clip_count=3, continuity_pass=True)
        _write(
            tmp / "outputs" / "runs" / "index.json",
            {"runs": [{"run_id": "run_a", "topic": "lion", "run_dir": str(latest_dir)}]},
        )
        (tmp / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        _write(tmp / "project_brain" / "product_settings" / "channel_profile.json", {})

        latest = load_run_results(tmp)
        _pass("canonical_latest", latest.get("is_canonical_latest") is True)
        _pass("run_folder_name", latest.get("run_folder") == "20260611_latest_run_a")
        _pass("publish_under_run", str(latest.get("publish_package_path") or "").endswith("publish"))


def test_selected_run_isolated() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        latest_dir = _seed_run(tmp, folder="20260611_latest_run_a", run_id="run_a", topic="lion", clip_count=3, continuity_pass=True)
        old_dir = _seed_run(tmp, folder="20260610_old_run_b", run_id="run_b", topic="grafig", clip_count=6, continuity_pass=True)
        _write(
            tmp / "outputs" / "runs" / "index.json",
            {
                "runs": [
                    {"run_id": "run_a", "topic": "lion", "run_dir": str(latest_dir)},
                    {"run_id": "run_b", "topic": "grafig", "run_dir": str(old_dir)},
                ]
            },
        )
        (tmp / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        _write(tmp / "project_brain" / "product_settings" / "channel_profile.json", {})

        selected = load_run_results(tmp, run_id="run_b")
        _pass("selected_run_b", selected.get("selected_run_id") == "run_b")
        _pass("selected_topic", selected.get("topic") == "grafig")
        _pass("selected_clip_count", selected.get("downloaded_clip_count") == 6)
        _pass("selected_continuity_clips", len((selected.get("visual_continuity") or {}).get("clips") or []) == 6)
        _pass("selected_publish_path", str(selected.get("publish_package_path") or "").startswith(str(old_dir)))


def test_no_stale_grafig_in_latest_run() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        latest_dir = _seed_run(tmp, folder="20260611_latest_run_a", run_id="run_a", topic="lion", clip_count=3, continuity_pass=False)
        _seed_run(tmp, folder="20260610_old_run_b", run_id="run_b", topic="grafig", clip_count=6, continuity_pass=True)
        _write(
            tmp / "outputs" / "runs" / "index.json",
            {
                "runs": [
                    {"run_id": "run_a", "topic": "lion", "run_dir": str(latest_dir)},
                    {"run_id": "run_b", "topic": "grafig", "run_dir": str(tmp / "outputs" / "runs" / "20260610_old_run_b")},
                ]
            },
        )
        _write(
            tmp / "project_brain" / "runtime_state" / "visual_continuity_report.json",
            {
                "run_id": "run_b",
                "topic": "grafig",
                "overall_pass": True,
                "clips": [{"clip_index": i, "pass": True, "score": 99} for i in range(1, 7)],
            },
        )
        (tmp / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        _write(tmp / "project_brain" / "product_settings" / "channel_profile.json", {})

        service = ProductStudioService(tmp)
        latest = service.get_results()
        summary = dict((latest.get("metadata") or {}).get("runway_report_summary") or {})
        _pass("summary_run_id", summary.get("run_id") == "run_a")
        _pass("summary_clip_count", summary.get("clip_count") == 3, str(summary.get("clip_count")))
        _pass("metadata_topic", (latest.get("metadata") or {}).get("topic") == "lion")
        _pass("continuity_run_id", (latest.get("visual_continuity") or {}).get("run_id") == "run_a")


def test_real_project_latest_run_consistency() -> None:
    index_path = ROOT / "outputs" / "runs" / "index.json"
    if not index_path.is_file():
        print("[SKIP] real_project_latest_run_consistency — no runs index")
        return
    service = ProductStudioService(ROOT)
    latest = service.get_results()
    selected_run_id = str(latest.get("selected_run_id") or "")
    continuity = latest.get("visual_continuity") or {}
    continuity_run_id = str(continuity.get("run_id") or "")
    clip_count = int(latest.get("downloaded_clip_count") or 0)
    continuity_clips = len(continuity.get("clips") or [])
    if selected_run_id and continuity_run_id:
        _pass("real_run_ids_match", selected_run_id == continuity_run_id, f"{selected_run_id} vs {continuity_run_id}")
    if clip_count and continuity_clips:
        _pass("real_clip_counts_match", clip_count == continuity_clips, f"{clip_count} vs {continuity_clips}")
    publish_path = str(latest.get("publish_package_path") or "")
    run_dir = str(latest.get("run_dir") or "")
    if publish_path and run_dir:
        _pass("real_publish_under_run", publish_path.startswith(run_dir), publish_path)


def main() -> None:
    test_mixed_manifests_detected()
    test_stale_sections_hidden()
    test_latest_run_folder_is_canonical()
    test_selected_run_isolated()
    test_no_stale_grafig_in_latest_run()
    test_real_project_latest_run_consistency()
    print("All results run consistency validations passed.")


if __name__ == "__main__":
    main()
