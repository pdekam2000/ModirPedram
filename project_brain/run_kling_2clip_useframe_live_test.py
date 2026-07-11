"""PHASE 2-CLIP-USE-FRAME-LIVE-TEST — one real 2×15s Use Frame chain via validated runtime."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_PATH = ROOT / "project_brain" / "KLING_2CLIP_USEFRAME_LIVE_TEST_REPORT.md"
OUTPUT_ROOT = ROOT / "outputs" / "kling_2clip_useframe"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
APPROVED_BY = "kling_2clip_useframe_live_test"
CLIP_COUNT = 2

TOPIC = (
    "A mysterious young woman in a black futuristic coat on a rain-soaked cyberpunk rooftop "
    "at night. She notices a glowing blue signal in a puddle and follows it across the rooftop "
    "while search drones sweep the sky. Cinematic, emotional, dark neon, realistic tension. "
    "Native in-scene audio: rain, city hum, drone rotors, her breathing — no narration."
)

CLIP2_CONTINUATION = (
    "Continuation from the prior frame on the same rain-soaked cyberpunk rooftop. "
    "The same woman reaches the roof edge; the blue signal rises from the puddle trail and "
    "forms a giant luminous symbol hovering above the skyline. She stops, wind and rain whipping "
    "her coat, staring up as the symbol pulses. Maintain identical character, location, lighting, "
    "and 9:16 cinematic neon realism. Native in-scene audio only — intensifying rain, rising "
    "synthetic tone, fading drone rotors, whispered reaction, no narration."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"kling_uf_{stamp}_{uuid.uuid4().hex[:8]}"


def _run_dir(run_id: str) -> Path:
    path = OUTPUT_ROOT / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clip_dir(run_id: str, clip_index: int) -> Path:
    from content_brain.execution.kling_starter_frame_generator import kling_frame_clip_dir, kling_frame_run_dir

    return kling_frame_clip_dir(kling_frame_run_dir(ROOT, run_id), clip_index)


def _resolve_mp4_for_clip(*, run_id: str, clip_index: int, live_result: dict, cdp_url: str) -> tuple[Path | None, dict]:
    from content_brain.execution.kling_frame_to_video_live_engine import recover_kling_frame_output
    from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4

    audit: dict = {"attempted": [], "candidates": [], "extractor_methods": [], "poll_report": {}}
    live_clip = _clip_dir(run_id, clip_index)

    def _try(label: str, path: Path) -> Path | None:
        audit["attempted"].append(label)
        if not path.is_file():
            audit["candidates"].append({"path": str(path), "exists": False, "label": label})
            return None
        verify = verify_extracted_kling_mp4(path)
        audit["candidates"].append(
            {
                "path": str(path.resolve()),
                "exists": True,
                "label": label,
                "is_real_mp4": bool(verify.get("is_real_mp4")),
                "size_bytes": verify.get("size_bytes"),
                "duration_seconds": verify.get("duration_seconds"),
            }
        )
        return path if verify.get("is_real_mp4") else None

    for key in ("clip_output_path", "output_path", "download_path"):
        value = str(live_result.get(key) or "").strip()
        if value:
            found = _try(f"live_result.{key}", Path(value))
            if found:
                return found, audit

    for name in ("clip_1.mp4", "video.mp4"):
        found = _try(f"canonical.clips/c{clip_index}/{name}", live_clip / name)
        if found:
            return found, audit

    if live_result.get("generation_completed") or live_result.get("generate_clicked"):
        audit["attempted"].append("recover_kling_frame_output")
        recover = recover_kling_frame_output(run_id=run_id, cdp_url=cdp_url, clip_index=clip_index)
        recover_dict = recover.to_dict() if hasattr(recover, "to_dict") else {}
        audit["extractor_methods"] = list(recover_dict.get("download_strategies") or [])
        poll_path = live_clip / "mp4_recovery_poll_report.json"
        if poll_path.is_file():
            try:
                audit["poll_report"] = json.loads(poll_path.read_text(encoding="utf-8"))
            except Exception:
                audit["poll_report"] = {"error": "could_not_read_poll_report"}
        for key in ("clip_output_path", "output_path", "download_path"):
            value = str(recover_dict.get(key) or "").strip()
            if value:
                found = _try(f"post_recovery.{key}", Path(value))
                if found:
                    return found, audit
        for name in ("clip_1.mp4", "video.mp4"):
            found = _try(f"post_recovery.canonical/{name}", live_clip / name)
            if found:
                return found, audit

    return None, audit


def _merge_clips(clip_paths: list[Path], dest: Path) -> tuple[bool, str]:
    if len(clip_paths) < 2:
        return False, "need_at_least_2_clips"
    try:
        from utils.ffmpeg_stitcher import FFmpegStitcher

        stitcher = FFmpegStitcher()
        if not stitcher.check_ffmpeg():
            return False, "ffmpeg_not_available"
        stitcher.stitch_clips([str(p) for p in clip_paths], str(dest))
        return dest.is_file(), "ffmpeg_concat"
    except Exception as exc:
        return False, str(exc)[:200]


def _build_report(
    *,
    run_id: str,
    clip_results: list[dict],
    generation_report: dict,
    download_report: dict,
    continuity_chain: dict,
    clip_mp4s: dict[int, Path | None],
    recovery_audits: dict[int, dict],
    merged_path: Path | None,
    merge_detail: str,
    final_status: str,
) -> str:
    use_frame = continuity_chain.get("use_frame_chain") or generation_report.get("use_frame_chain") or {}
    clip1 = clip_results[0] if len(clip_results) > 0 else {}
    clip2 = clip_results[1] if len(clip_results) > 1 else {}

    def _recovery_methods(audit: dict) -> list[str]:
        methods = list(audit.get("extractor_methods") or [])
        methods.extend(audit.get("attempted") or [])
        return methods

    lines = [
        "# KLING 2-CLIP USE FRAME LIVE TEST REPORT",
        "",
        f"Generated: {_now_iso()}",
        "",
        "## Summary",
        "",
        f"- **run_id:** `{run_id}`",
        f"- **FINAL STATUS:** {final_status}",
        f"- **continuity method:** {use_frame.get('continuity_method', 'use_frame')}",
        f"- **fallback used:** {use_frame.get('fallback_used', False)}",
        f"- **chain complete:** {generation_report.get('chain_complete', False)}",
        "",
        "## Clip 1",
        "",
        f"- **generation status:** {clip1.get('status')}",
        f"- **generate clicked:** {clip1.get('generate_clicked')}",
        f"- **generation completed:** {clip1.get('generation_completed')}",
        f"- **mp4 path:** `{clip_mp4s.get(1) or 'none'}`",
        f"- **recovery methods:** {_recovery_methods(recovery_audits.get(1, {}))}",
        "",
        "## Use Frame handoff",
        "",
    ]
    handoff_clips = use_frame.get("clips") or []
    if handoff_clips:
        for item in handoff_clips:
            lines.append(
                f"- clip {item.get('clip_index')}: method={item.get('continuity_method')} "
                f"status={item.get('use_frame_status')} ok={item.get('ok')}"
            )
    else:
        lines.append(f"- use_frame_status: {use_frame.get('story_progression_status', 'unknown')}")

    lines.extend(
        [
            "",
            "## Clip 2",
            "",
            f"- **generation status:** {clip2.get('status')}",
            f"- **generate clicked:** {clip2.get('generate_clicked')}",
            f"- **generation completed:** {clip2.get('generation_completed')}",
            f"- **mp4 path:** `{clip_mp4s.get(2) or 'none'}`",
            f"- **recovery methods:** {_recovery_methods(recovery_audits.get(2, {}))}",
            "",
            "## Merged output",
            "",
            f"- **path:** `{merged_path or 'none'}`",
            f"- **merge detail:** {merge_detail}",
            "",
            "## Errors",
            "",
        ]
    )
    errors: list[str] = []
    for idx, live in enumerate(clip_results, start=1):
        for err in live.get("errors") or []:
            errors.append(f"clip{idx}: {err}")
        if live.get("download_verify_error"):
            errors.append(f"clip{idx} download: {live.get('download_verify_error')}")
    stop = generation_report.get("continuity_status")
    if stop and stop not in {"chain_complete", "completed"}:
        errors.append(f"continuity: {stop}")
    if errors:
        lines.extend(f"- {e}" for e in errors)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- output dir: `{_run_dir(run_id)}`",
            f"- live engine dir: `{ROOT / 'outputs' / 'kling_frame_to_video' / run_id}`",
            f"- download report status: {download_report.get('status')}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling 2-clip Use Frame live test")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--approved-by", default=APPROVED_BY)
    parser.add_argument("--topic", default=TOPIC)
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()

    if not args.skip_preflight:
        from content_brain.execution.browser_connectivity_probe import run_browser_probes

        probe = run_browser_probes({"cdp_url": args.cdp_url}, project_root=ROOT)
        if not probe.passed:
            REPORT_PATH.write_text(
                f"# KLING 2-CLIP USE FRAME LIVE TEST REPORT\n\nFINAL STATUS: FAIL\n\nPreflight: {probe.message}\n",
                encoding="utf-8",
            )
            print(f"Preflight failed: {probe.message}")
            return 1

    from content_brain.execution.kling_frame_continuity_runtime import run_kling_frame_continuity_chain
    from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content
    from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4
    from content_brain.execution.kling_starter_frame_generator import kling_frame_run_dir

    run_id = _create_run_id()
    out_dir = _run_dir(run_id)
    live_run_dir = kling_frame_run_dir(ROOT, run_id)

    plan = plan_kling_frame_to_video_content(
        topic=args.topic,
        planned_duration_seconds=15,
        clip_count=CLIP_COUNT,
        mood="cinematic emotional dark neon",
        environment="rain-soaked cyberpunk rooftop at night",
    )
    if len(plan.clips) >= 2:
        plan.clips[1].prompt = CLIP2_CONTINUATION

    (out_dir / "run_config.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "clip_count": CLIP_COUNT,
                "aspect_ratio": "9:16",
                "duration_seconds": 15,
                "provider": "kling_3_pro",
                "continuity_method": "use_frame",
                "topic": args.topic,
            },
            indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"run_id={run_id}")
    print("2-clip Use Frame live test — max 2 Generate clicks, 15s each, 9:16, Kling 3.0 Pro")
    print("Watch Runway Chrome — Clip 1 Generate, Use Frame handoff, Clip 2 Generate")

    clip_results, generation_report, download_report, final_video, _, continuity_chain = run_kling_frame_continuity_chain(
        project_root=ROOT,
        run_id=run_id,
        run_dir=live_run_dir,
        plan=plan,
        approved_by=args.approved_by,
        confirm_credit_spend=True,
        starter_frame_path=None,
        cdp_url=args.cdp_url,
        payload={
            "approve_generate": True,
            "approve_all_clips": True,
            "aspect_ratio": "9:16",
        },
    )

    (out_dir / "generation_report.json").write_text(json.dumps(generation_report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "continuity_chain.json").write_text(json.dumps(continuity_chain, indent=2, ensure_ascii=False), encoding="utf-8")

    clip_mp4s: dict[int, Path | None] = {}
    recovery_audits: dict[int, dict] = {}
    dest_clips: dict[int, Path] = {}

    for clip_index in (1, 2):
        live = clip_results[clip_index - 1] if len(clip_results) >= clip_index else {}
        mp4_src, audit = _resolve_mp4_for_clip(
            run_id=run_id,
            clip_index=clip_index,
            live_result=live,
            cdp_url=args.cdp_url,
        )
        recovery_audits[clip_index] = audit
        clip_mp4s[clip_index] = mp4_src
        dest = out_dir / f"clip_{clip_index}.mp4"
        if mp4_src and mp4_src.is_file():
            shutil.copy2(mp4_src, dest)
            verify = verify_extracted_kling_mp4(dest)
            (out_dir / f"clip_{clip_index}_verify.json").write_text(json.dumps(verify, indent=2, ensure_ascii=False), encoding="utf-8")
            if verify.get("is_real_mp4"):
                dest_clips[clip_index] = dest
        (out_dir / f"clip_{clip_index}_recovery_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    merged_path: Path | None = None
    merge_detail = "not_attempted"
    if 1 in dest_clips and 2 in dest_clips:
        merged_dest = out_dir / "merged_30s.mp4"
        ok, merge_detail = _merge_clips([dest_clips[1], dest_clips[2]], merged_dest)
        if ok:
            merged_path = merged_dest
            verify = verify_extracted_kling_mp4(merged_dest)
            (out_dir / "merged_verify.json").write_text(json.dumps(verify, indent=2, ensure_ascii=False), encoding="utf-8")

    clip1_ok = 1 in dest_clips
    clip2_ok = 2 in dest_clips
    use_frame_ok = bool(
        (continuity_chain.get("use_frame_chain") or {}).get("continuity_method") == "use_frame"
        and not (continuity_chain.get("use_frame_chain") or {}).get("fallback_used")
    ) or any(
        (c.get("continuity_method") == "use_frame" and c.get("use_frame_status") == "activated")
        for c in ((continuity_chain.get("use_frame_chain") or {}).get("clips") or [])
    )

    success = clip1_ok and clip2_ok and bool(clip_results[0].get("generate_clicked")) and bool(
        clip_results[1].get("generate_clicked") if len(clip_results) > 1 else False
    )
    final_status = "SUCCESS" if success else "FAIL"

    report = _build_report(
        run_id=run_id,
        clip_results=clip_results,
        generation_report=generation_report,
        download_report=download_report,
        continuity_chain=continuity_chain,
        clip_mp4s=clip_mp4s,
        recovery_audits=recovery_audits,
        merged_path=merged_path,
        merge_detail=merge_detail,
        final_status=final_status,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"FINAL STATUS: {final_status}")
    print(f"Clip 1 MP4: {dest_clips.get(1, 'missing')}")
    print(f"Clip 2 MP4: {dest_clips.get(2, 'missing')}")
    print(f"Merged: {merged_path or 'missing'}")
    print(f"Use Frame path: {'ok' if use_frame_ok else 'check report'}")
    print(f"Report: {REPORT_PATH}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
