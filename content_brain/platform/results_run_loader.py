"""Run-scoped Results loader — one canonical run folder, no mixed manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from content_brain.execution.runway_live_post_processor import collect_valid_download_paths
from content_brain.platform.canonical_delivery import resolve_canonical_final_video
from content_brain.platform.canonical_run import load_canonical_run
from content_brain.platform.delivery_truth_loader import build_delivery_truth_panel
from content_brain.platform.final_delivery_registry import resolve_approved_delivery
from content_brain.platform.run_isolation import FAIL_MESSAGE, load_latest_run_attempt, load_run_context
from content_brain.platform.run_output_versioning import list_run_history

RESULTS_RUN_LOADER_VERSION = "results_run_loader_v3"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_id_matches(payload: dict[str, Any], expected_run_id: str) -> bool:
    if not expected_run_id:
        return True
    stored = str(payload.get("run_id") or payload.get("content_brain_run_id") or "").strip()
    if not stored:
        return True
    return stored == expected_run_id


def _path_under_run(path_text: str, run_dir: Path) -> bool:
    if not path_text:
        return False
    try:
        resolved = Path(path_text).resolve()
        run_resolved = run_dir.resolve()
        return run_resolved == resolved or run_resolved in resolved.parents
    except OSError:
        return str(run_dir) in path_text


def find_run_entry(
    project_root: str | Path,
    *,
    run_id: str = "",
    run_dir: str = "",
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    root = Path(project_root).resolve()
    history = list_run_history(root, limit=100)
    run_id_text = str(run_id or "").strip()
    run_dir_text = str(run_dir or "").strip()

    if run_dir_text:
        for item in history:
            item_dir = str(item.get("run_dir") or "")
            if item_dir == run_dir_text or item_dir.endswith(run_dir_text) or run_dir_text in item_dir:
                return item, history
        candidate = Path(run_dir_text)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.is_dir():
            return _entry_from_run_dir(candidate), history

    if run_id_text:
        for item in history:
            if str(item.get("run_id") or "") == run_id_text:
                return item, history
        runs_root = root / "outputs" / "runs"
        if runs_root.is_dir():
            suffix = run_id_text[-12:] if len(run_id_text) > 12 else run_id_text
            matches = sorted(
                [path for path in runs_root.iterdir() if path.is_dir() and (run_id_text in path.name or path.name.endswith(suffix))],
                reverse=True,
            )
            if matches:
                return _entry_from_run_dir(matches[0]), history

    if history:
        return history[0], history
    return None, history


def _entry_from_run_dir(run_dir: Path) -> dict[str, Any]:
    summary = _read_json(run_dir / "metadata" / "run_summary.json")
    publish_meta = _read_json(run_dir / "publish" / "metadata.json")
    run_id = str(summary.get("run_id") or publish_meta.get("run_id") or "").strip()
    topic = str(summary.get("topic") or publish_meta.get("topic") or "").strip()
    return {
        "run_id": run_id,
        "topic": topic,
        "run_dir": str(run_dir),
        "final_video_path": str(summary.get("final_video_path") or run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"),
        "publish_dir": str(summary.get("publish_dir") or run_dir / "publish"),
        "assembly_status": str(summary.get("assembly_status") or ""),
        "publish_status": str(summary.get("publish_status") or ""),
        "created_at": str(summary.get("created_at") or ""),
        "runway_report_path": str(summary.get("runway_report_path") or ""),
    }


def _resolve_visual_memory_report(root: Path, run_dir: Path, expected_run_id: str) -> dict[str, Any]:
    candidates = [
        run_dir / "metadata" / "visual_memory_report.json",
        root / "project_brain" / "runtime_state" / f"visual_memory_report_{expected_run_id}.json",
    ]
    if expected_run_id:
        candidates.append(root / "project_brain" / "visual_memory" / f"run_{expected_run_id}.json")
    for path in candidates:
        if not path.is_file():
            continue
        payload = _read_json(path)
        if not payload:
            continue
        if path.name.startswith("run_") and "visual_memory_status" not in payload:
            payload = {
                "version": "visual_memory_store_v1",
                "run_id": expected_run_id,
                "subject": str(payload.get("subject_name") or ""),
                "visual_memory_status": "PASS" if payload.get("subject_name") else "FAIL",
                "consistency_score": None,
                "continuity_status": "UNKNOWN",
                "memory_path": str(path),
            }
        stored_run = str(payload.get("run_id") or "").strip()
        if expected_run_id and stored_run and stored_run != expected_run_id:
            continue
        return payload
    return {}


def _resolve_ai_director_v2_report(root: Path, run_dir: Path, expected_run_id: str) -> dict[str, Any]:
    candidates = [
        run_dir / "metadata" / "ai_director_v2_report.json",
        root / "project_brain" / "runtime_state" / f"ai_director_v2_report_{expected_run_id}.json",
    ]
    if expected_run_id:
        graph_path = root / "project_brain" / "runtime_state" / "shot_graph" / expected_run_id / "shot_graph.json"
        candidates.append(graph_path)
    for path in candidates:
        if not path.is_file():
            continue
        payload = _read_json(path)
        if not payload:
            continue
        if path.name == "shot_graph.json" and "shot_plan" not in payload:
            payload = {
                "version": "ai_director_v2_v1",
                "run_id": expected_run_id,
                "director_version": "AI Director V2",
                "shot_plan": list(payload.get("nodes") or []),
                "shot_plan_summary": [
                    f"Clip {node.get('clip_index')}: {node.get('shot_type')}"
                    for node in list(payload.get("nodes") or [])
                    if isinstance(node, dict)
                ],
                "rhythm_score": None,
                "shot_graph_status": "PASS",
                "shot_graph_path": str(path),
                "camera_language": [],
            }
        stored_run = str(payload.get("run_id") or "").strip()
        if expected_run_id and stored_run and stored_run != expected_run_id:
            continue
        return payload
    return {}


def _empty_visual(run_id: str, *, hidden: bool = False) -> dict[str, Any]:
    return {
        "version": "visual_continuity_pipeline_v1",
        "status": "hidden_stale" if hidden else "not_available_for_run",
        "message": "Visual continuity hidden due to run_id mismatch." if hidden else "Visual continuity not available for this run.",
        "run_id": run_id,
        "overall_pass": None,
        "overall_score": None,
        "clips": [],
        "warnings": [],
        "created_at": "",
    }


def _resolve_global_runway_report(root: Path, expected_run_id: str) -> dict[str, Any]:
    for relative in (
        Path("project_brain") / "runway_phase_i_3clip_last_report.json",
        Path("project_brain") / "runway_live_smoke_last_report.json",
    ):
        path = root / relative
        if not path.is_file():
            continue
        payload = _read_json(path)
        report_run_id = str(payload.get("content_brain_run_id") or payload.get("run_id") or "").strip()
        if expected_run_id and report_run_id and report_run_id != expected_run_id:
            continue
        return payload
    return {}


def _resolve_assembly_manifest(root: Path, run_dir: Path, expected_run_id: str) -> tuple[dict[str, Any], bool]:
    run_manifest = _read_json(run_dir / "metadata" / "assembly_manifest.json")
    if run_manifest and _run_id_matches(run_manifest, expected_run_id):
        return run_manifest, False

    global_manifest = _read_json(root / "project_brain" / "runtime_state" / "runway_phase_i_assembly_manifest.json")
    if global_manifest and _path_under_run(str(global_manifest.get("output_path") or ""), run_dir):
        return global_manifest, False
    if global_manifest and expected_run_id:
        return {}, True
    return run_manifest, False


def _resolve_publish_manifest(root: Path, run_dir: Path, expected_run_id: str) -> tuple[dict[str, Any], bool]:
    run_manifest = _read_json(run_dir / "metadata" / "publish_manifest.json")
    if run_manifest and _run_id_matches(run_manifest, expected_run_id):
        return run_manifest, False

    global_manifest = _read_json(root / "project_brain" / "runtime_state" / "runway_phase_i_publish_manifest.json")
    package_folder = str(global_manifest.get("package_folder") or "")
    if global_manifest and _path_under_run(package_folder, run_dir):
        return global_manifest, False
    if global_manifest and expected_run_id:
        return {}, True
    return run_manifest, False


def _resolve_branding_status(
    *,
    root: Path,
    run_dir: Path,
    publish_meta: dict[str, Any],
    runway_report: dict[str, Any],
    expected_run_id: str,
    stale: bool,
) -> dict[str, Any]:
    if stale:
        return {
            "status": "hidden_stale",
            "branding_enabled": False,
            "final_branded_video_path": "",
            "subtitled_video_path": "",
            "subtitles": "SKIP",
            "logo": "SKIP",
            "cta": "SKIP",
            "intro": "SKIP",
            "outro": "SKIP",
        }

    branding_manifest = _read_json(root / "project_brain" / "runtime_state" / "runway_phase_i_branding_manifest.json")
    if branding_manifest and not _run_id_matches(branding_manifest, expected_run_id):
        if not _path_under_run(str(branding_manifest.get("final_branded_video_path") or ""), run_dir):
            branding_manifest = {}

    steps = dict(branding_manifest.get("steps") or runway_report.get("branding_steps") or publish_meta.get("branding_steps") or {})

    def step_label(key: str) -> str:
        step = steps.get(key) if isinstance(steps.get(key), dict) else {}
        return str(step.get("status") or runway_report.get(f"branding_{key}_status") or "SKIP")

    branded_path = str(
        resolve_approved_delivery(root, run_id=expected_run_id).get("canonical_final_video_path")
        or resolve_canonical_final_video(root, run_dir=run_dir, run_id=expected_run_id)
        or ""
    )
    if branded_path and not Path(branded_path).is_file():
        branded_path = ""

    return {
        "status": str(
            publish_meta.get("branding_status")
            or branding_manifest.get("status")
            or runway_report.get("branding_status")
            or ""
        ),
        "branding_enabled": bool(
            publish_meta.get("branding_enabled", branding_manifest.get("branding_enabled", runway_report.get("branding_enabled", False)))
        ),
        "final_branded_video_path": branded_path,
        "subtitled_video_path": str(branding_manifest.get("subtitled_video_path") or run_dir / "publish" / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4"),
        "subtitles": step_label("subtitles"),
        "logo": step_label("logo"),
        "cta": step_label("cta"),
        "intro": step_label("intro"),
        "outro": step_label("outro"),
    }


def detect_mixed_manifests(
    *,
    expected_run_id: str,
    publish_meta: dict[str, Any],
    visual_continuity: dict[str, Any],
    raw_downloads: dict[str, Any],
    assembly_manifest: dict[str, Any],
    publish_manifest: dict[str, Any],
    runway_report: dict[str, Any],
) -> list[str]:
    stale: list[str] = []
    if publish_meta and not _run_id_matches(publish_meta, expected_run_id):
        stale.append("publish")
    if visual_continuity and not _run_id_matches(visual_continuity, expected_run_id):
        stale.append("visual_continuity")
    if raw_downloads and not _run_id_matches(raw_downloads, expected_run_id):
        stale.append("pipeline")
    if assembly_manifest and expected_run_id:
        manifest_run = str(assembly_manifest.get("run_id") or "").strip()
        if manifest_run and manifest_run != expected_run_id:
            stale.append("assembly")
    if publish_manifest and expected_run_id:
        manifest_run = str(publish_manifest.get("run_id") or "").strip()
        if manifest_run and manifest_run != expected_run_id:
            stale.append("publish")
    if runway_report:
        report_run_id = str(runway_report.get("content_brain_run_id") or runway_report.get("run_id") or "").strip()
        if expected_run_id and report_run_id and report_run_id != expected_run_id:
            stale.append("runway_report")
    return sorted(set(stale))


def load_run_results(
    project_root: str | Path,
    *,
    run_id: str = "",
    run_dir: str = "",
    profile_upload_platforms: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    canonical = load_canonical_run(root)
    canonical_run_id = str(canonical.get("run_id") or "").strip()
    if not str(run_id or "").strip() and canonical_run_id:
        run_id = canonical_run_id
    entry, history = find_run_entry(root, run_id=run_id, run_dir=run_dir)
    canonical_entry = history[0] if history else None
    canonical_run_id = str((canonical_entry or {}).get("run_id") or "").strip()

    if entry is None:
        return _legacy_empty_results(root, history, profile_upload_platforms or [])

    run_dir_path = Path(str(entry.get("run_dir") or ""))
    selected_run_id = str(entry.get("run_id") or "").strip()
    run_folder = run_dir_path.name
    is_canonical_latest = bool(canonical_entry and str(canonical_entry.get("run_dir") or "") == str(entry.get("run_dir") or ""))

    run_summary = _read_json(run_dir_path / "metadata" / "run_summary.json") or dict(entry)
    publish_meta = _read_json(run_dir_path / "publish" / "metadata.json")
    raw_downloads = _read_json(run_dir_path / "raw_downloads_manifest.json")
    visual_continuity = _read_json(run_dir_path / "metadata" / "visual_continuity_report.json")
    visual_memory = _resolve_visual_memory_report(root, run_dir_path, selected_run_id)
    ai_director_v2 = _resolve_ai_director_v2_report(root, run_dir_path, selected_run_id)
    assembly_manifest, assembly_stale = _resolve_assembly_manifest(root, run_dir_path, selected_run_id)
    publish_manifest, publish_manifest_stale = _resolve_publish_manifest(root, run_dir_path, selected_run_id)
    runway_report = _resolve_global_runway_report(root, selected_run_id)
    audio_manifest = _read_json(root / "project_brain" / "runtime_state" / "runway_phase_i_audio_manifest.json")
    delivery_gate = _read_json(run_dir_path / "metadata" / "delivery_quality_gate.json")
    if not delivery_gate:
        delivery_gate = _read_json(root / "project_brain" / "runtime_state" / "delivery_quality_gate.json")
    video_quality_judge = _read_json(run_dir_path / "quality" / "video_quality_judge.json")
    if video_quality_judge and selected_run_id:
        judge_run_id = str(video_quality_judge.get("run_id") or "").strip()
        if judge_run_id and judge_run_id != selected_run_id:
            video_quality_judge = {}
    video_quality_judge_p1 = _read_json(run_dir_path / "quality" / "video_quality_judge_p1.json")
    if video_quality_judge_p1 and selected_run_id:
        judge_p1_run_id = str(video_quality_judge_p1.get("run_id") or "").strip()
        if judge_p1_run_id and judge_p1_run_id != selected_run_id:
            video_quality_judge_p1 = {}
    video_quality_proposed_updates_path = root / "project_brain" / "quality_learning" / "proposed_updates" / f"{selected_run_id}.json"
    video_quality_learning_proposed = video_quality_proposed_updates_path.is_file()
    video_quality_proposed_updates_p1_path = root / "project_brain" / "quality_learning" / "proposed_updates_p1" / f"{selected_run_id}.json"
    video_quality_learning_p1_proposed = video_quality_proposed_updates_p1_path.is_file()

    stale_sections = detect_mixed_manifests(
        expected_run_id=selected_run_id,
        publish_meta=publish_meta,
        visual_continuity=visual_continuity,
        raw_downloads=raw_downloads,
        assembly_manifest=assembly_manifest,
        publish_manifest=publish_manifest,
        runway_report=runway_report,
    )
    if assembly_stale:
        stale_sections.append("assembly")
    if publish_manifest_stale:
        stale_sections.append("publish")
    stale_sections = sorted(set(stale_sections))

    if "visual_continuity" in stale_sections or not visual_continuity.get("clips"):
        if "visual_continuity" in stale_sections:
            visual_continuity = _empty_visual(selected_run_id, hidden=True)
        elif not visual_continuity:
            visual_continuity = _empty_visual(selected_run_id)

    if "publish" in stale_sections:
        publish_meta = {}
        publish_manifest = {}
        delivery_gate = {}

    if "assembly" in stale_sections:
        assembly_manifest = {}

    downloaded_paths = list(
        raw_downloads.get("downloaded_file_paths")
        or publish_meta.get("downloaded_file_paths")
        or []
    )
    if "pipeline" in stale_sections:
        downloaded_paths = []

    valid_downloads, _ = collect_valid_download_paths([str(item) for item in downloaded_paths if item])
    downloaded_clip_count = len(valid_downloads) if valid_downloads else len(downloaded_paths)

    assembly_status = str(run_summary.get("assembly_status") or assembly_manifest.get("status") or "")
    publish_status = str(run_summary.get("publish_status") or publish_manifest.get("status") or "")
    if "assembly" in stale_sections:
        assembly_status = ""
    if "publish" in stale_sections:
        publish_status = ""

    post_processing_status = ""
    post_processing_missing = False
    if assembly_status == "ASSEMBLED" and publish_status == "PUBLISHED_PACKAGE_CREATED":
        if str(delivery_gate.get("delivery_status") or "") == "FAIL":
            post_processing_status = "failed"
        else:
            post_processing_status = "completed"
    elif downloaded_clip_count > 0 and not assembly_status:
        post_processing_status = ""
        post_processing_missing = True
    elif runway_report and _run_id_matches(runway_report, selected_run_id):
        post_processing_status = str(runway_report.get("post_processing_status") or "")
        post_processing_missing = post_processing_status in {"", "skipped"}

    branding_stale = "publish" in stale_sections
    branding_status = _resolve_branding_status(
        root=root,
        run_dir=run_dir_path,
        publish_meta=publish_meta,
        runway_report=runway_report if "runway_report" not in stale_sections else {},
        expected_run_id=selected_run_id,
        stale=branding_stale,
    )

    approved_delivery = resolve_approved_delivery(root)
    delivery_truth = build_delivery_truth_panel(
        root,
        run_id=selected_run_id,
        run_dir=str(run_dir_path),
    )
    unified_run_id = canonical_run_id or selected_run_id
    if unified_run_id and selected_run_id and unified_run_id != selected_run_id:
        selected_run_id = unified_run_id
    latest_attempt = load_latest_run_attempt(root)
    if str(latest_attempt.get("run_id") or "") != unified_run_id:
        latest_attempt = {
            "run_id": unified_run_id,
            "topic": str(entry.get("topic") or canonical.get("topic") or ""),
            "status": "completed" if downloaded_clip_count else "failed",
            "clips_completed": downloaded_clip_count,
            "message": "Canonical run — no separate attempt lane.",
        }
    approved_run_id = unified_run_id if delivery_truth.get("approved") else ""
    canonical_video = resolve_canonical_final_video(root, run_dir=run_dir_path, run_id=selected_run_id)
    approved_video = str(canonical_video) if canonical_video is not None and delivery_truth.get("approved") else ""
    delivery = approved_delivery if approved_delivery and str(approved_delivery.get("latest_run_id") or "") == unified_run_id else {}
    if canonical_video is not None:
        video_path = str(canonical_video)
    else:
        intermediate_candidates = [
            str(run_dir_path / "publish" / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4"),
            str(run_dir_path / "publish" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"),
            str(run_summary.get("final_video_path") or ""),
            str(run_dir_path / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"),
        ]
        video_path = next((item for item in intermediate_candidates if item and Path(item).is_file()), "")
    publish_package_path = str(run_dir_path / "publish") if (run_dir_path / "publish").exists() else str(entry.get("publish_dir") or "")
    if approved_run_id == selected_run_id and approved_delivery and approved_delivery.get("latest_publish_package"):
        publish_package_path = str(approved_delivery.get("latest_publish_package") or publish_package_path)

    youtube_metadata: dict[str, Any] = {}
    if publish_package_path:
        try:
            from content_brain.publish.youtube_metadata_generator import load_youtube_metadata

            youtube_metadata = load_youtube_metadata(publish_package_path) or {}
        except Exception:
            youtube_metadata = {}

    runway_completed = bool(downloaded_clip_count > 0 or assembly_status or publish_status)
    has_downloads_only = runway_completed and publish_status != "PUBLISHED_PACKAGE_CREATED"

    section_availability = {
        "pipeline": "hidden_stale" if "pipeline" in stale_sections else ("available" if downloaded_clip_count else "missing"),
        "visual_continuity": (
            "hidden_stale"
            if visual_continuity.get("status") == "hidden_stale"
            else ("available" if visual_continuity.get("clips") else "missing")
        ),
        "branding": "hidden_stale" if branding_stale else ("available" if branding_status.get("status") else "missing"),
        "assembly": "hidden_stale" if "assembly" in stale_sections else ("available" if assembly_status else "missing"),
        "publish": "hidden_stale" if "publish" in stale_sections else ("available" if publish_status else "missing"),
        "runway_report": "hidden_stale" if "runway_report" in stale_sections else ("available" if runway_report else "missing"),
        "video_quality_judge": "available" if video_quality_judge.get("version") else "missing",
        "video_quality_judge_p1": "available" if video_quality_judge_p1.get("version") else "missing",
    }

    metadata: dict[str, Any] = {}
    if publish_meta:
        metadata.update(publish_meta)
    if assembly_manifest and "assembly" not in stale_sections:
        metadata["assembly_manifest"] = assembly_manifest
    if publish_manifest and "publish" not in stale_sections:
        metadata["publish_manifest"] = publish_manifest
    metadata["run_summary"] = run_summary
    if runway_report and "runway_report" not in stale_sections:
        metadata["runway_report_summary"] = {
            "ok": bool(runway_report.get("ok")),
            "simulate": bool(runway_report.get("simulate", True)),
            "run_id": selected_run_id,
            "clip_count": runway_report.get("clip_count"),
            "downloaded_file_paths": list(runway_report.get("downloaded_file_paths") or []),
            "post_processing_status": runway_report.get("post_processing_status"),
            "assembly_status": runway_report.get("assembly_status"),
            "publish_package_status": runway_report.get("publish_package_status"),
            "visual_continuity_status": runway_report.get("visual_continuity_status"),
            "visual_continuity_overall_pass": runway_report.get("visual_continuity_overall_pass"),
        }
    else:
        metadata["runway_report_summary"] = {
            "run_id": selected_run_id,
            "clip_count": publish_meta.get("clip_count") or downloaded_clip_count,
            "downloaded_file_paths": downloaded_paths,
            "post_processing_status": post_processing_status,
            "assembly_status": assembly_status,
            "publish_package_status": publish_status,
            "visual_continuity_status": visual_continuity.get("status"),
            "visual_continuity_overall_pass": visual_continuity.get("overall_pass"),
            "source": "run_folder",
        }

    if stale_sections:
        metadata["stale_sections"] = stale_sections
        metadata["stale_manifest_note"] = f"Stale sections hidden for run {selected_run_id}: {', '.join(stale_sections)}."

    post_processing_warnings: list[str] = []
    if runway_report and "runway_report" not in stale_sections:
        post_processing_warnings = list(runway_report.get("post_processing_warnings") or [])

    music_status = str(
        publish_meta.get("music_status")
        or publish_manifest.get("music_status")
        or audio_manifest.get("music_status")
        or (audio_manifest.get("music_runtime") or {}).get("status_label")
        or ""
    )
    if not music_status:
        music_code = str((audio_manifest.get("music_runtime") or {}).get("status") or publish_meta.get("music_provider") or "")
        music_runtime = dict(audio_manifest.get("music_runtime") or publish_meta.get("music_runtime") or {})
        if music_code == "completed" and music_runtime.get("audibility_pass"):
            track = str(music_runtime.get("music_track_path") or "")
            music_status = f"PASS — mixed track: {track}" if track else "PASS"
        elif music_code == "completed" and not music_runtime.get("audibility_pass"):
            music_status = "FAILED — music inaudible"
        elif music_code == "failed_inaudible":
            music_status = "FAILED — merge succeeded but music inaudible"
        elif music_code == "skipped_no_local_track":
            music_status = "Music: SKIPPED — no usable music file configured"
        elif music_code == "skipped_silent_source":
            music_status = "Music: FAILED — music source silent / too quiet"
        elif music_code == "skipped_provider_disabled":
            music_status = "Music: SKIPPED — music provider disabled"

    ambience_status = str(
        publish_meta.get("ambience_status")
        or audio_manifest.get("ambience_status")
        or "Ambience skipped: no ambience files found."
    )
    sfx_status = str(publish_meta.get("sfx_status") or audio_manifest.get("sfx_status") or "SFX skipped: no sfx files found.")
    subtitle_style_status = str(
        publish_meta.get("subtitle_style_status")
        or audio_manifest.get("subtitle_style_status")
        or "Subtitle style: not reported"
    )
    character_voice_status = str(
        publish_meta.get("character_voice_status")
        or audio_manifest.get("character_voice_status")
        or "Character voices: not reported"
    )

    truth_checks = dict(delivery_truth.get("checks") or {})
    if truth_checks:
        subtitle_status = f"Subtitles: {truth_checks.get('subtitles', {}).get('status', 'FAIL')} (final MP4 audit)"
        music_status = f"Music: {truth_checks.get('music', {}).get('status', 'FAIL')} (final MP4 audit)"
        ambience_status = f"Ambience: {truth_checks.get('ambience', {}).get('status', 'FAIL')} (final MP4 audit)"
        character_voice_status = f"Dialogue: {truth_checks.get('dialogue', {}).get('status', 'FAIL')} (final MP4 audit)"

    subtitle_status = str(
        publish_meta.get("subtitle_status")
        or publish_manifest.get("subtitle_status")
        or branding_status.get("subtitle_status")
        or audio_manifest.get("subtitle_status")
        or ""
    )
    if not subtitle_status:
        subtitle_step = dict((branding_status.get("steps") or {}).get("subtitles") or {})
        subtitle_meta = dict(subtitle_step.get("metadata") or {})
        burn_visible = subtitle_step.get("burn_visible_enough", subtitle_meta.get("burn_visible_enough"))
        if burn_visible:
            subtitle_status = "Subtitle: PASS — visible lower-third subtitles burned"
        elif subtitle_step.get("status") == "PASS" and burn_visible is False:
            subtitle_status = "Subtitle: FAILED — burn ran but text not visible"
        elif subtitle_step.get("status") == "PASS":
            subtitle_status = "Subtitle: PASS — visible lower-third subtitles burned"
        elif subtitle_step.get("status") == "FAIL":
            subtitle_status = "Subtitle: FAILED — burn failed"

    from content_brain.platform.asset_library import asset_library_root, list_latest_assets
    from content_brain.quality.story_audio_auditor import audit_story_package_dict
    from content_brain.story.story_package import load_story_package

    story_package_payload = load_story_package(root, selected_run_id)
    run_context = load_run_context(root, selected_run_id)
    if not story_package_payload and run_context.get("story_package_path"):
        story_package_payload = _read_json(Path(str(run_context["story_package_path"])))
    if not story_package_payload:
        pkg_path = Path(str(audio_manifest.get("story_package_path") or ""))
        manifest_run = str(audio_manifest.get("run_id") or audio_manifest.get("content_brain_run_id") or "")
        if pkg_path.is_file() and (not manifest_run or manifest_run == selected_run_id):
            story_package_payload = _read_json(pkg_path)
    story_audit_raw = audit_story_package_dict(story_package_payload) if story_package_payload else None
    if story_audit_raw is None:
        story_audit: dict[str, Any] = {}
    elif isinstance(story_audit_raw, dict):
        story_audit = story_audit_raw
    elif hasattr(story_audit_raw, "__dataclass_fields__"):
        from dataclasses import asdict

        story_audit = asdict(story_audit_raw)
    else:
        story_audit = {}
    cinematic_manifest = _read_json(Path(str(run_dir_path / "audio" / "cinematic_audio_manifest.json")))
    audio_manifest_cinematic = dict(audio_manifest.get("cinematic_audio") or {})
    cinematic_payload = audio_manifest_cinematic or cinematic_manifest
    story_audio_director = {
        "status": str(story_audit.get("status") or "NOT_RUN"),
        "story_score": int(story_audit.get("story_score") or 0),
        "dialogue_score": int(story_audit.get("dialogue_score") or 0),
        "emotion_score": int(story_audit.get("emotion_score") or 0),
        "character_count": int(story_audit.get("character_count") or 0),
        "voice_count": int(story_audit.get("voice_count") or 0),
        "environment_plan": dict((story_package_payload or {}).get("environment_plan") or {}),
        "music_plan": dict((story_package_payload or {}).get("music_plan") or {}),
        "story_package_path": str(
            audio_manifest.get("story_package_path")
            or (root / "project_brain" / "story_packages" / f"{selected_run_id}.json")
        ),
        "checks": dict(story_audit.get("checks") or {}),
        "failures": list(story_audit.get("failures") or []),
    }
    run_visual: dict[str, Any] = {}
    story_visual_quality = dict(
        ((story_package_payload or {}).get("metadata") or {}).get("story_visual_quality") or {}
    )
    if not story_visual_quality:
        run_visual = _read_json(run_dir_path / "debug" / "story_visual_1" / "story_visual_summary.json")
        story_visual_quality = dict(run_visual.get("story_visual_quality") or {})
    if not story_visual_quality:
        emotion_plan = _read_json(run_dir_path / "metadata" / "character_emotion_plan.json")
        repetition = _read_json(run_dir_path / "metadata" / "visual_repetition_report.json")
        diversity = _read_json(run_dir_path / "debug" / "story_visual_1" / "scene_diversity_report.json")
        if diversity or emotion_plan or repetition:
            story_visual_quality = {
                "scene_diversity_score": int((diversity or {}).get("scene_diversity_score") or 0),
                "emotion_coverage_score": int((emotion_plan or {}).get("emotion_coverage_score") or 0),
                "story_progression_score": int(
                    ((run_visual or {}).get("visual_progression") or {}).get("story_progression_score") or 0
                ),
                "repetition_score": int((repetition or {}).get("repetition_score") or 0),
                "pass_visual_diversity": bool((repetition or {}).get("pass_visual_diversity")),
                "unique_locations": list((diversity or {}).get("unique_locations") or []),
                "clip_objectives": list((diversity or {}).get("clip_objectives") or []),
            }
    cinematic_audio = {
        "status": str(cinematic_payload.get("status") or audio_manifest.get("status") or "NOT_RUN"),
        "character_count": int(cinematic_payload.get("character_count") or 0),
        "voice_count": int(cinematic_payload.get("voice_count") or 0),
        "dialogue_line_count": int(cinematic_payload.get("dialogue_line_count") or 0),
        "emotion_states": list(cinematic_payload.get("emotion_states") or []),
        "environment_layers": int(cinematic_payload.get("environment_layers") or 0),
        "music_layers": int(cinematic_payload.get("music_layers") or 0),
        "audio_quality_score": int(
            (cinematic_payload.get("audio_reality_audit") or {}).get("quality_score")
            or cinematic_payload.get("audio_quality_score")
            or 0
        ),
        "cinematic_audio_path": str(
            cinematic_payload.get("cinematic_audio_path") or audio_manifest.get("cinematic_audio_path") or ""
        ),
        "cinematic_video_path": str(
            cinematic_payload.get("cinematic_video_path") or audio_manifest.get("cinematic_video_path") or ""
        ),
        "audio_reality_audit": dict(cinematic_payload.get("audio_reality_audit") or audio_manifest.get("audio_reality_audit") or {}),
        "voice_presence_audit": dict(cinematic_payload.get("voice_presence_audit") or audio_manifest.get("voice_presence_audit") or {}),
    }

    return {
        "version": RESULTS_RUN_LOADER_VERSION,
        "found": bool(video_path or publish_package_path or downloaded_clip_count),
        "video_path": video_path,
        "publish_package_path": publish_package_path,
        "youtube_metadata": youtube_metadata,
        "youtube_title": str(youtube_metadata.get("title") or ""),
        "youtube_hashtags": list(youtube_metadata.get("hashtags") or []),
        "youtube_tags_count": len(list(youtube_metadata.get("tags") or [])),
        "youtube_category": str(youtube_metadata.get("category") or ""),
        "youtube_thumbnail_prompt": str(youtube_metadata.get("thumbnail_prompt") or ""),
        "platform_targets": list(profile_upload_platforms or []),
        "metadata": metadata,
        "runway_completed": runway_completed,
        "has_downloads_only": has_downloads_only,
        "assembly_status": assembly_status,
        "publish_status": publish_status,
        "downloaded_clip_count": downloaded_clip_count,
        "post_processing_status": post_processing_status,
        "post_processing_missing": post_processing_missing,
        "stale_manifest_ignored": bool(stale_sections),
        "stale_sections": stale_sections,
        "section_availability": section_availability,
        "selected_run_id": selected_run_id,
        "run_folder": run_folder,
        "run_dir": str(run_dir_path),
        "canonical_run_id": canonical_run_id,
        "is_canonical_latest": is_canonical_latest,
        "latest_run_id": selected_run_id,
        "stored_manifest_run_id": selected_run_id,
        "topic": str(entry.get("topic") or publish_meta.get("topic") or run_summary.get("topic") or ""),
        "post_processing_warnings": post_processing_warnings,
        "music_status": music_status,
        "subtitle_status": subtitle_status,
        "ambience_status": ambience_status,
        "sfx_status": sfx_status,
        "subtitle_style_status": subtitle_style_status,
        "character_voice_status": character_voice_status,
        "final_branded_video_v2_path": "",
        "final_branded_video_v3_path": "",
        "branding_status": branding_status,
        "final_branded_video_path": approved_video,
        "latest_approved_video_path": approved_video,
        "latest_run_attempt": latest_attempt,
        "latest_attempt_status": str(latest_attempt.get("status") or ""),
        "latest_attempt_message": str(
            latest_attempt.get("message") or (FAIL_MESSAGE if latest_attempt.get("status") == "failed" else "")
        ),
        "latest_attempt_run_id": str(latest_attempt.get("run_id") or ""),
        "latest_attempt_topic": str(latest_attempt.get("topic") or ""),
        "latest_attempt_clips_completed": int(latest_attempt.get("clips_completed") or 0),
        "approved_run_id": approved_run_id,
        "delivery_registry": delivery,
        "delivery_truth": delivery_truth,
        "delivery_truth_status": str(delivery_truth.get("status") or "FAIL"),
        "delivery_truth_checks": dict(delivery_truth.get("checks") or {}),
        "delivery_status": str(delivery_gate.get("delivery_status") or latest_attempt.get("delivery_status") or ""),
        "delivery_gate_failures": list(delivery_gate.get("failures") or latest_attempt.get("delivery_gate_failures") or []),
        "canonical_deliverable_path": str(
            delivery_gate.get("canonical_video_path")
            or latest_attempt.get("canonical_deliverable_path")
            or approved_video
            or ""
        ),
        "assembled_duration_seconds": delivery_gate.get("assembled_duration_seconds"),
        "deliverable_duration_seconds": delivery_gate.get("deliverable_duration_seconds"),
        "visual_continuity": visual_continuity,
        "visual_continuity_report": visual_continuity,
        "visual_memory": visual_memory,
        "visual_memory_report": visual_memory,
        "ai_director_v2": ai_director_v2,
        "ai_director_v2_report": ai_director_v2,
        "run_history": history,
        "asset_library_path": str(asset_library_root(root)),
        "latest_assets": list_latest_assets(root, limit=12),
        "story_audio_director": story_audio_director,
        "story_visual_quality": story_visual_quality,
        "cinematic_audio": cinematic_audio,
        "video_quality_judge": video_quality_judge,
        "video_quality_judge_p1": video_quality_judge_p1,
        "video_quality_learning_proposed": video_quality_learning_proposed,
        "video_quality_proposed_updates_path": str(video_quality_proposed_updates_path.resolve()).replace("\\", "/")
        if video_quality_learning_proposed
        else "",
        "video_quality_learning_p1_proposed": video_quality_learning_p1_proposed,
        "video_quality_proposed_updates_p1_path": str(video_quality_proposed_updates_p1_path.resolve()).replace("\\", "/")
        if video_quality_learning_p1_proposed
        else "",
    }


def _legacy_empty_results(root: Path, history: list[dict[str, Any]], platform_targets: list[str]) -> dict[str, Any]:
    canonical = load_canonical_run(root)
    delivery_truth = build_delivery_truth_panel(root)
    approved_delivery = resolve_approved_delivery(root)
    latest_attempt = load_latest_run_attempt(root)
    unified_run_id = str(canonical.get("run_id") or "")
    if str(latest_attempt.get("run_id") or "") != unified_run_id:
        latest_attempt = {"run_id": unified_run_id, "topic": str(canonical.get("topic") or ""), "status": "failed"}
    return {
        "version": RESULTS_RUN_LOADER_VERSION,
        "found": False,
        "video_path": "",
        "publish_package_path": "",
        "platform_targets": platform_targets,
        "metadata": {},
        "runway_completed": False,
        "has_downloads_only": False,
        "assembly_status": "",
        "publish_status": "",
        "downloaded_clip_count": 0,
        "post_processing_status": "",
        "post_processing_missing": False,
        "stale_manifest_ignored": False,
        "stale_sections": [],
        "section_availability": {},
        "selected_run_id": "",
        "run_folder": "",
        "run_dir": "",
        "canonical_run_id": str((history[0] or {}).get("run_id") or "") if history else "",
        "is_canonical_latest": False,
        "latest_run_id": "",
        "stored_manifest_run_id": "",
        "topic": "",
        "post_processing_warnings": [],
        "branding_status": {},
        "final_branded_video_path": "",
        "visual_continuity": _empty_visual(""),
        "visual_continuity_report": _empty_visual(""),
        "visual_memory": {},
        "visual_memory_report": {},
        "ai_director_v2": {},
        "ai_director_v2_report": {},
        "run_history": history,
        "asset_library_path": "",
        "latest_assets": [],
        "story_audio_director": {
            "status": "NOT_RUN",
            "story_score": 0,
            "dialogue_score": 0,
            "emotion_score": 0,
            "character_count": 0,
            "voice_count": 0,
            "environment_plan": {},
            "music_plan": {},
            "story_package_path": "",
            "checks": {},
            "failures": [],
        },
        "story_visual_quality": {},
        "cinematic_audio": {
            "status": "NOT_RUN",
            "character_count": 0,
            "voice_count": 0,
            "dialogue_line_count": 0,
            "emotion_states": [],
            "environment_layers": 0,
            "music_layers": 0,
            "audio_quality_score": 0,
            "cinematic_audio_path": "",
            "cinematic_video_path": "",
            "audio_reality_audit": {},
            "voice_presence_audit": {},
        },
        "video_quality_judge": {},
        "video_quality_judge_p1": {},
        "video_quality_learning_proposed": False,
        "video_quality_proposed_updates_path": "",
        "video_quality_learning_p1_proposed": False,
        "video_quality_proposed_updates_p1_path": "",
        "latest_approved_video_path": str((approved_delivery or {}).get("canonical_final_video_path") or ""),
        "latest_run_attempt": latest_attempt,
        "latest_attempt_status": str(latest_attempt.get("status") or ""),
        "latest_attempt_message": str(
            latest_attempt.get("message") or (FAIL_MESSAGE if latest_attempt.get("status") == "failed" else "")
        ),
        "latest_attempt_run_id": str(latest_attempt.get("run_id") or ""),
        "latest_attempt_topic": str(latest_attempt.get("topic") or ""),
        "latest_attempt_clips_completed": int(latest_attempt.get("clips_completed") or 0),
        "approved_run_id": unified_run_id if delivery_truth.get("approved") else "",
        "delivery_registry": approved_delivery if approved_delivery else {},
        "delivery_truth": delivery_truth,
        "delivery_truth_status": str(delivery_truth.get("status") or "FAIL"),
        "delivery_truth_checks": dict(delivery_truth.get("checks") or {}),
    }


__all__ = [
    "RESULTS_RUN_LOADER_VERSION",
    "detect_mixed_manifests",
    "find_run_entry",
    "load_run_results",
]
