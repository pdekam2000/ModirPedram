"""YouTube upload diagnostic — token, credentials, and optional live upload test."""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.automation.platform_upload_guard import normalize_platform
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.youtube_auth import (
    get_valid_access_token,
    get_youtube_auth_status,
    resolve_oauth_client_path,
    resolve_token_paths,
)
from content_brain.upload.youtube_uploader import upload_video_to_youtube

DO_UPLOAD = "--upload" in sys.argv
YOUTUBE_PLATFORM = "youtube_shorts"
AUTOMATION_JOBS_PATH = ROOT / "project_brain" / "automation" / "automation_jobs.json"


def extract_run_id_from_path(video_path: str | Path) -> str:
    parts = Path(video_path).parts
    for index, part in enumerate(parts):
        if part == "pwmap_agent_runs" and index + 1 < len(parts):
            return parts[index + 1]
        if str(part).startswith("pwmap_"):
            return str(part)
    return ""


def load_automation_jobs() -> list[dict]:
    if not AUTOMATION_JOBS_PATH.is_file():
        return []
    try:
        payload = json.loads(AUTOMATION_JOBS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    return [item for item in jobs if isinstance(item, dict)] if isinstance(jobs, list) else []


def find_job_by_run_id(run_id: str, jobs: list[dict]) -> dict | None:
    needle = str(run_id or "").strip()
    if not needle:
        return None
    for job in jobs:
        if str(job.get("run_id") or "").strip() == needle:
            return job
    return None


def job_platform(job: dict | None) -> str:
    if not job:
        return ""
    return normalize_platform(
        str(job.get("platform") or (job.get("platform_targets") or [""])[0] or "")
    )


def _extract_platform_from_payload(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    direct = str(payload.get("platform") or "").strip()
    if direct:
        return normalize_platform(direct)
    preflight = payload.get("preflight_snapshot")
    if isinstance(preflight, dict):
        platform = str(preflight.get("platform") or "").strip()
        if platform:
            return normalize_platform(platform)
    targets = payload.get("targets") or payload.get("platform_targets") or []
    if isinstance(targets, list) and targets:
        first = targets[0]
        if isinstance(first, dict):
            platform = str(first.get("platform") or "").strip()
            if platform:
                return normalize_platform(platform)
        elif isinstance(first, str) and first.strip():
            return normalize_platform(first)
    trace = payload.get("pipeline_trace")
    if isinstance(trace, dict):
        stages = trace.get("stages") or {}
        if isinstance(stages, dict):
            for stage_name in ("instagram_upload_runtime", "youtube_upload_runtime"):
                stage = stages.get(stage_name) or {}
                if isinstance(stage, dict):
                    platform = str(stage.get("platform") or "").strip()
                    if platform:
                        return normalize_platform(platform)
                    reason = str(stage.get("reason") or "")
                    if reason.startswith("platform_not_youtube:"):
                        return normalize_platform(reason.split(":", 1)[1])
    for key in ("multiclip_execution_plan", "generation_runtime"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            platform = _extract_platform_from_payload(nested)
            if platform:
                return platform
    return ""


def resolve_run_platform_from_artifacts(project_root: Path, run_id: str) -> str:
    run_dir = project_root / "outputs" / "pwmap_agent_runs" / run_id
    for filename in ("normalized_result.json", "product_multiclip_runtime.json"):
        path = run_dir / filename
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        platform = _extract_platform_from_payload(payload)
        if platform:
            return platform

    upload_root = project_root / "outputs" / "upload_packages"
    if upload_root.is_dir():
        run_key = str(run_id or "").strip().lower()
        for package_dir in upload_root.iterdir():
            if not package_dir.is_dir() or package_dir.name.lower() != run_key:
                continue
            package_path = package_dir / "upload_package.json"
            if not package_path.is_file():
                continue
            try:
                payload = json.loads(package_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            platform = _extract_platform_from_payload(payload)
            if platform:
                return platform
    return ""


def resolve_video_platform(project_root: Path, video_path: str | Path, jobs: list[dict]) -> str:
    run_id = extract_run_id_from_path(video_path)
    if not run_id:
        return ""
    job = find_job_by_run_id(run_id, jobs)
    platform = job_platform(job)
    if platform:
        return platform
    return resolve_run_platform_from_artifacts(project_root, run_id)


def filter_youtube_videos(project_root: Path, all_videos: list[str], jobs: list[dict]) -> list[str]:
    youtube_videos: list[str] = []
    for video_path in all_videos:
        run_id = extract_run_id_from_path(video_path)
        if not run_id:
            continue
        job = find_job_by_run_id(run_id, jobs)
        platform = job_platform(job) or resolve_run_platform_from_artifacts(project_root, run_id)
        if platform == YOUTUBE_PLATFORM:
            youtube_videos.append(video_path)
    return youtube_videos


def main() -> int:
    project_root = ROOT
    profile = ProductChannelProfileStore(project_root).load()
    auth = get_youtube_auth_status(project_root, profile)

    print("=== YouTube Upload Diagnostic ===")
    print("OAuth path:", profile.get("youtube_oauth_client_path") or "NOT SET")
    print("Resolved OAuth client:", resolve_oauth_client_path(project_root, profile) or "NOT FOUND")
    print("Token search paths:")
    for path in resolve_token_paths(project_root):
        exists = path.is_file()
        print(f"  {'[OK]' if exists else '[--]'} {path}")
    print("Upload enabled:", profile.get("youtube_upload_enabled"))
    print("YouTube privacy:", profile.get("youtube_privacy", "public"))
    print("Auto upload (center):", end=" ")
    try:
        from content_brain.platform.automation_center_store import is_auto_upload_enabled

        print(is_auto_upload_enabled(project_root))
    except Exception as exc:
        print(f"check failed: {exc}")

    print()
    print("Auth status:")
    print("  credentials_configured:", auth.get("credentials_configured"))
    print("  authenticated:", auth.get("authenticated"))
    print("  refreshable:", auth.get("refreshable"))
    print("  connect_required:", auth.get("connect_required"))
    print("  channel_name:", auth.get("channel_name") or "NOT SET")
    print("  token_path:", auth.get("token_path"))

    token = get_valid_access_token(project_root, profile)
    print()
    print("Token valid:", bool(token))
    if token:
        print("Token prefix:", token[:12] + "...")

    all_videos = sorted(
        glob.glob(str(project_root / "outputs" / "pwmap_agent_runs" / "**" / "FINAL*.mp4"), recursive=True),
        key=lambda p: Path(p).stat().st_mtime if Path(p).is_file() else 0,
        reverse=True,
    )
    if not all_videos:
        all_videos = sorted(
            glob.glob(str(project_root / "outputs" / "**" / "*.mp4"), recursive=True),
            key=lambda p: Path(p).stat().st_mtime if Path(p).is_file() else 0,
            reverse=True,
        )

    jobs = load_automation_jobs()
    youtube_videos = filter_youtube_videos(project_root, all_videos, jobs)

    print()
    print("Available videos (all):", len(all_videos))
    print("Available videos (youtube_shorts only):", len(youtube_videos))
    if youtube_videos:
        test_video = youtube_videos[0]
        run_id = extract_run_id_from_path(test_video)
        platform = resolve_video_platform(project_root, test_video, jobs)
        size_mb = Path(test_video).stat().st_size / (1024 * 1024)
        print("Test video:", test_video)
        print("Run ID:", run_id)
        print("Run platform:", platform or "unknown")
        print("Size MB:", round(size_mb, 2))
    else:
        print("Test video: NONE — no YouTube Shorts runs found")
        if all_videos:
            rejected = all_videos[0]
            rejected_run = extract_run_id_from_path(rejected)
            rejected_platform = resolve_video_platform(project_root, rejected, jobs) or "unknown"
            print("Latest non-YouTube video skipped:", rejected)
            print("  run_id:", rejected_run)
            print("  platform:", rejected_platform)
        return 1 if not token else 0

    if not token:
        print()
        print("BLOCKER: No valid OAuth token. Connect YouTube:")
        print("  http://127.0.0.1:8765/upload/youtube/auth")
        return 1

    if not DO_UPLOAD:
        print()
        print("Dry run only. Re-run with --upload to attempt a private YouTube upload.")
        return 0

    print()
    print("Attempting upload (private)...")
    result = upload_video_to_youtube(
        project_root=project_root,
        profile=profile,
        video_path=test_video,
        title="ModirAgentOS Upload Diagnostic",
        description="Automated diagnostic upload test — safe to delete.",
        privacy="private",
        publish_now=True,
    )
    print("Upload result:")
    for key in ("ok", "status", "reason", "uploaded", "video_id", "video_url", "error", "details"):
        if key in result:
            value = result.get(key)
            if value:
                print(f"  {key}: {value}")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
