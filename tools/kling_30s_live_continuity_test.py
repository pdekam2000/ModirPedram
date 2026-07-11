#!/usr/bin/env python3
"""Run KLING-30S-LIVE-CONTINUITY-TEST via Product Studio pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_last_frame_extractor import continuity_frame_path  # noqa: E402
from content_brain.execution.kling_multishot_live_engine import verify_recovered_mp4  # noqa: E402
from content_brain.execution.kling_native_audio_models import KLING_AUDIO_STRATEGY, KLING_PROVIDER_ID  # noqa: E402
from content_brain.execution.kling_product_run import (  # noqa: E402
    kling_run_dir,
    load_kling_product_run_results,
    run_kling_product_studio_generate,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

TEST_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpers. "
    'The woman whispers: "Stay with me... we\'re almost safe." '
    "Police drones search the streets with blue lights. Rain hits metal rooftops. "
    "The robot dog looks up at her and trusts her. Cinematic emotional sci-fi story. "
    "Native audio. Rain, footsteps, breathing, robot sounds, drone hum, distant sirens."
)
DEFAULT_CDP = "http://127.0.0.1:9222"
REPORT_PATH = ROOT / "project_brain" / "KLING_30S_LIVE_CONTINUITY_TEST_REPORT.md"


def _payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "topic_mode": "custom",
        "custom_topic": TEST_TOPIC,
        "duration_seconds": 30,
        "platform": "youtube_shorts",
        "provider": KLING_PROVIDER_ID,
        "audio_strategy": KLING_AUDIO_STRATEGY,
        "characters": ["young woman", "wounded robot dog"],
        "environment": "neon cyberpunk city during heavy rain with blue police drone lights",
        "mood": "cinematic emotional sci-fi",
    }
    base.update(overrides)
    return base


def _ffprobe_audio(video_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        return {"ok": False, "detail": proc.stderr or proc.stdout}
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or []
    has_audio = any(str(s.get("codec_type") or "") == "audio" for s in streams)
    duration = float((data.get("format") or {}).get("duration") or 0)
    return {"ok": True, "has_audio": has_audio, "duration_seconds": duration}


def run_preflight() -> dict[str, Any]:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_payload())
    clip_count = int(pre.get("kling_clip_count") or 0)
    if clip_count != 2:
        raise SystemExit(f"Preflight expected 2 clips, got {clip_count}")
    return pre


def run_generate(*, approved_by: str, cdp_url: str, approve_all: bool) -> dict[str, Any]:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_payload())
    gen_payload = _payload(
        approve_generate=True,
        approved_by=approved_by,
        confirm_credit_spend=True,
        cdp_url=cdp_url,
    )
    if approve_all:
        gen_payload["approve_all_clips"] = True
    else:
        gen_payload["approved_clips"] = [1, 2]
    return run_kling_product_studio_generate(
        project_root=ROOT,
        payload=gen_payload,
        preflight=pre,
    )


def validate_run(run_id: str) -> dict[str, Any]:
    run_dir = kling_run_dir(ROOT, run_id)
    results = load_kling_product_run_results(ROOT, run_id=run_id) or {}
    continuity_path = run_dir / "continuity_chain.json"
    if not continuity_path.is_file():
        continuity_path = run_dir / "continuity" / "continuity_chain_v1.json"
    continuity = {}
    if continuity_path.is_file():
        continuity = json.loads(continuity_path.read_text(encoding="utf-8"))

    checks: dict[str, Any] = {}
    for clip_index in (1, 2):
        video = run_dir / "clips" / f"c{clip_index}" / "video.mp4"
        verify = verify_recovered_mp4(str(video)) if video.is_file() else {"is_real_mp4": False}
        probe = _ffprobe_audio(video) if video.is_file() else {"ok": False}
        checks[f"c{clip_index}_video_exists"] = video.is_file()
        checks[f"c{clip_index}_size_ok"] = bool(verify.get("is_real_mp4"))
        checks[f"c{clip_index}_ffprobe_ok"] = probe.get("ok") is True
        checks[f"c{clip_index}_native_audio"] = probe.get("has_audio") is True

    frame_c1 = continuity_frame_path(run_dir, 1)
    frame_c2 = continuity_frame_path(run_dir, 2)
    checks["frame_c1_exists"] = frame_c1.is_file()
    checks["frame_c2_exists"] = frame_c2.is_file()

    clip2_live = run_dir / "clips" / "c2" / "live_run_result.json"
    uploaded = False
    if clip2_live.is_file():
        live = json.loads(clip2_live.read_text(encoding="utf-8"))
        upload = live.get("first_frame_upload") or {}
        uploaded = bool(upload.get("uploaded")) or bool(
            (live.get("approval_checklist") or {}).get("first_frame_uploaded")
        )
    checks["frame_c1_uploaded_before_clip2"] = uploaded
    checks["chain_complete"] = bool(continuity.get("chain_complete"))
    checks["all_pass"] = all(checks.values())

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "checks": checks,
        "continuity": continuity,
        "results": results,
        "clip_paths": {
            "c1": str((run_dir / "clips" / "c1" / "video.mp4").resolve()),
            "c2": str((run_dir / "clips" / "c2" / "video.mp4").resolve()),
        },
        "frame_paths": {
            "c1": str(frame_c1.resolve()) if frame_c1.is_file() else "",
            "c2": str(frame_c2.resolve()) if frame_c2.is_file() else "",
        },
    }


def write_report(
    *,
    preflight: dict[str, Any] | None,
    generate_result: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    operator_notes: str = "",
) -> None:
    run_id = str((generate_result or validation or {}).get("run_id") or "")
    lines = [
        "# Kling 30s Live Continuity Test — Report",
        "",
        f"**Phase:** `KLING-30S-LIVE-CONTINUITY-TEST`",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Topic",
        "",
        TEST_TOPIC,
        "",
        "## Settings",
        "",
        "| Setting | Value |",
        "|---------|-------|",
        f"| Provider | {KLING_PROVIDER_ID} |",
        f"| Audio Strategy | {KLING_AUDIO_STRATEGY} |",
        "| Platform | youtube_shorts |",
        "| Duration | 30s |",
        "| Expected clips | 2 |",
        "",
    ]
    if preflight:
        lines.extend(
            [
                "## Preflight",
                "",
                f"- **Clip count:** {preflight.get('kling_clip_count')}",
                f"- **Shot mode:** {preflight.get('kling_shot_mode')}",
                f"- **Authoritative topic:** {preflight.get('authoritative_topic', '')[:120]}…",
                "",
            ]
        )
    if generate_result:
        lines.extend(
            [
                "## Execution",
                "",
                f"- **Run ID:** `{run_id}`",
                f"- **Output folder:** `{generate_result.get('output_folder')}`",
                f"- **Status:** {generate_result.get('status')}",
                f"- **Continuity status:** {generate_result.get('continuity_status') or (generate_result.get('continuity_chain') or {}).get('continuity_status')}",
                f"- **Chain complete:** {generate_result.get('chain_complete') or (generate_result.get('continuity_chain') or {}).get('chain_complete')}",
                f"- **Frames extracted:** {generate_result.get('frames_extracted_count')}",
                f"- **Frames uploaded:** {generate_result.get('frames_uploaded_count')}",
                f"- **Generate clicked:** {generate_result.get('generate_clicked')}",
                f"- **Credits spent:** {generate_result.get('credits_spent')}",
                "",
            ]
        )
    if validation:
        lines.extend(["## Validation", ""])
        for key, ok in validation.get("checks", {}).items():
            lines.append(f"- {'PASS' if ok else 'FAIL'} — `{key}`")
        lines.extend(
            [
                "",
                "## Paths",
                "",
                f"- Clip 1: `{validation.get('clip_paths', {}).get('c1')}`",
                f"- Clip 2: `{validation.get('clip_paths', {}).get('c2')}`",
                f"- Frame C1: `{validation.get('frame_paths', {}).get('c1')}`",
                f"- Frame C2: `{validation.get('frame_paths', {}).get('c2')}`",
                "",
            ]
        )
        results = validation.get("results") or {}
        lines.extend(
            [
                "## Audio / Continuity Status",
                "",
                f"- Native audio status: {results.get('native_audio_status')}",
                f"- Continuity status: {results.get('continuity_status')}",
                f"- Chain complete: {results.get('chain_complete')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Operator Notes",
            "",
            operator_notes or "_Pending operator playback review for visual continuity._",
            "",
            "## Visual Continuity",
            "",
            "_Operator: confirm Clip 2 opens on the same neon-rain frame as Clip 1 bridge ending — no abrupt scene reset._",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="30s Kling live continuity test")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--validate-only", metavar="RUN_ID")
    parser.add_argument("--approved-by", default="operator")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    parser.add_argument("--approve-all-clips", action="store_true", default=True)
    args = parser.parse_args()

    if args.validate_only:
        validation = validate_run(args.validate_only)
        write_report(preflight=None, generate_result={"run_id": args.validate_only}, validation=validation)
        print(json.dumps(validation, indent=2, ensure_ascii=False))
        return 0 if validation.get("checks", {}).get("all_pass") else 1

    pre = run_preflight()
    print(json.dumps({"step": "preflight", "kling_clip_count": pre.get("kling_clip_count"), "ok": True}, indent=2, ensure_ascii=False))
    if args.preflight_only:
        write_report(preflight=pre, generate_result=None, validation=None)
        return 0

    result = run_generate(
        approved_by=args.approved_by,
        cdp_url=args.cdp_url,
        approve_all=args.approve_all_clips,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    run_id = str(result.get("run_id") or "")
    validation = validate_run(run_id) if run_id else None
    write_report(preflight=pre, generate_result=result, validation=validation)
    ok = bool(result.get("ok")) and bool((validation or {}).get("checks", {}).get("all_pass"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
