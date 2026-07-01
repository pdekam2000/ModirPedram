"""PHASE KLING-SINGLE-CLIP-ONLY — one 15s Kling clip, real MP4, then stop."""

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

REPORT_PATH = ROOT / "project_brain" / "KLING_SINGLE_CLIP_15S_REPORT.md"
OUTPUT_ROOT = ROOT / "outputs" / "kling_single_clip"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
APPROVED_BY = "kling_single_clip_15s"
CLIP_COUNT = 1

TOPIC = (
    "A mysterious young woman in a black futuristic coat on a rain-soaked cyberpunk rooftop "
    "at night. She notices a glowing blue signal in a puddle and follows it across the rooftop "
    "while search drones sweep the sky. Cinematic, emotional, dark neon, realistic tension. "
    "Native in-scene audio: rain, city hum, drone rotors, her breathing — no narration."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"kling_sc_{stamp}_{uuid.uuid4().hex[:8]}"


def _run_dir(run_id: str) -> Path:
    path = OUTPUT_ROOT / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _canonical_live_clip_dir(run_id: str) -> Path:
    from content_brain.execution.kling_starter_frame_generator import kling_frame_clip_dir, kling_frame_run_dir

    return kling_frame_clip_dir(kling_frame_run_dir(ROOT, run_id), 1)


def _load_poll_report(clip_dir: Path) -> dict:
    report_path = clip_dir / "mp4_recovery_poll_report.json"
    if not report_path.is_file():
        return {}
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return {"error": "could_not_read_poll_report"}


def _merge_extractor_methods(audit: dict, methods: list[str]) -> None:
    bucket = audit.setdefault("extractor_methods", [])
    seen = set(bucket)
    for method in methods:
        cleaned = str(method or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            bucket.append(cleaned)


def _ingest_poll_report(audit: dict, clip_dir: Path) -> None:
    poll_report = _load_poll_report(clip_dir)
    if poll_report:
        audit["poll_report"] = poll_report
    for attempt in poll_report.get("attempts") or []:
        _merge_extractor_methods(audit, list(attempt.get("methods_tried") or []))


def _direct_poll_extract(
    *,
    run_id: str,
    cdp_url: str,
    clip_dir: Path,
    clip_index: int,
    audit: dict,
) -> Path | None:
    from content_brain.execution.kling_frame_to_video_live_engine import _ensure_runway_generate_page
    from content_brain.execution.kling_real_mp4_download_extractor import poll_extract_real_kling_mp4

    playwright = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        page = _ensure_runway_generate_page(browser)
        if page is None:
            audit.setdefault("errors", []).append("direct_poll:no_runway_tab")
            return None
        dest = clip_dir / f"clip_{clip_index}.mp4"
        extracted = poll_extract_real_kling_mp4(
            page,
            dest,
            run_id=run_id,
            clip_index=clip_index,
            clip_dir=clip_dir,
            recovery_mode=True,
        )
        _merge_extractor_methods(audit, list(extracted.attempted_methods))
        _ingest_poll_report(audit, clip_dir)
        if extracted.ok and extracted.output_path:
            return Path(extracted.output_path)
        return None
    except Exception as exc:
        audit.setdefault("errors", []).append(f"direct_poll:{exc}")
        return None
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def _resolve_mp4(*, run_id: str, live_result: dict, cdp_url: str) -> tuple[Path | None, dict]:
    from content_brain.execution.kling_frame_to_video_live_engine import recover_kling_frame_output
    from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4

    audit: dict = {"attempted": [], "candidates": [], "extractor_methods": [], "poll_report": {}}
    live_clip = _canonical_live_clip_dir(run_id)
    valid: Path | None = None

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

    # A. live_result paths
    for key in ("clip_output_path", "output_path", "download_path"):
        value = str(live_result.get(key) or "").strip()
        if not value:
            continue
        found = _try(f"live_result.{key}", Path(value))
        if found is not None and valid is None:
            valid = found

    # B. canonical live engine paths
    for name in ("clip_1.mp4", "video.mp4"):
        found = _try(f"canonical_live_engine.clips/c1/{name}", live_clip / name)
        if found is not None and valid is None:
            valid = found

    if valid is not None:
        return valid, audit

    should_recover = bool(live_result.get("generation_completed")) or bool(live_result.get("generate_clicked"))
    if not should_recover:
        return None, audit

    # C. recover_kling_frame_output (includes poll + extractor methods)
    audit["attempted"].append("recover_kling_frame_output")
    recover = recover_kling_frame_output(run_id=run_id, cdp_url=cdp_url, clip_index=1)
    recover_dict = recover.to_dict() if hasattr(recover, "to_dict") else {}
    _merge_extractor_methods(audit, list(recover_dict.get("download_strategies") or []))
    _ingest_poll_report(audit, live_clip)

    for key in ("clip_output_path", "output_path", "download_path"):
        value = str(recover_dict.get(key) or "").strip()
        if not value:
            continue
        found = _try(f"post_recovery.{key}", Path(value))
        if found is not None:
            return found, audit

    for name in ("clip_1.mp4", "video.mp4"):
        found = _try(f"post_recovery.canonical.clips/c1/{name}", live_clip / name)
        if found is not None:
            return found, audit

    # D/E. direct polled extractor fallback when recover did not yield valid MP4
    if not recover_dict.get("ok") or not audit.get("extractor_methods"):
        audit["attempted"].append("poll_extract_real_kling_mp4_direct")
        found = _direct_poll_extract(
            run_id=run_id,
            cdp_url=cdp_url,
            clip_dir=live_clip,
            clip_index=1,
            audit=audit,
        )
        if found is not None:
            verified = _try("post_direct_poll.clip_1.mp4", found)
            if verified is not None:
                return verified, audit

    return None, audit


def _build_report(
    *,
    run_id: str,
    live: dict,
    mp4_path: Path | None,
    verify: dict,
    recovery_audit: dict,
    final_status: str,
) -> str:
    size = int(verify.get("size_bytes") or 0) if verify else 0
    duration = verify.get("duration_seconds")
    lines = [
        "# KLING SINGLE CLIP 15S REPORT",
        "",
        f"Generated: {_now_iso()}",
        "",
        "## Summary",
        "",
        f"- **run_id:** `{run_id}`",
        f"- **FINAL STATUS:** {final_status}",
        f"- **clip_count:** {CLIP_COUNT}",
        f"- **generate clicked:** {live.get('generate_clicked')}",
        f"- **generation completed:** {live.get('generation_completed')}",
        f"- **generation status:** {live.get('status')}",
        "",
        "## MP4",
        "",
        f"- **path:** `{mp4_path or 'none'}`",
        f"- **size bytes:** {size}",
        f"- **duration seconds:** {duration}",
        f"- **validation is_real_mp4:** {verify.get('is_real_mp4') if verify else False}",
        f"- **ffprobe_ok:** {verify.get('ffprobe_ok') if verify else False}",
        "",
        "## Recovery",
        "",
        f"- **attempted:** {recovery_audit.get('attempted') or []}",
        f"- **extractor methods:** {recovery_audit.get('extractor_methods') or []}",
        "",
    ]
    poll_report = recovery_audit.get("poll_report") or {}
    poll_attempts = list(poll_report.get("attempts") or [])
    if poll_attempts:
        lines.extend(["## MP4 recovery polling", ""])
        lines.append(f"- **poll attempts:** {len(poll_attempts)}")
        lines.append(f"- **poll elapsed seconds:** {poll_report.get('poll_elapsed_seconds')}")
        lines.append(f"- **valid mp4 found:** {poll_report.get('valid_mp4_found')}")
        lines.append("")
        for item in poll_attempts[:12]:
            lines.append(
                f"- attempt {item.get('attempt')} @ {item.get('timestamp')}: "
                f"cards={item.get('card_count')} selected={bool(item.get('selected_card'))} "
                f"valid={item.get('valid_mp4_found')} methods={len(item.get('methods_tried') or [])}"
            )
        if len(poll_attempts) > 12:
            lines.append(f"- … and {len(poll_attempts) - 12} more attempts")
        lines.append("")
    lines.extend(
        [
        "## Settings",
        "",
        "- provider: Kling 3.0 Pro",
        "- aspect: 9:16",
        "- duration: 15s",
        "- native audio: ON",
        "- no clip 2 / no continuity / no frame extract",
        "",
        "## Artifacts",
        "",
        f"- run dir: `{_run_dir(run_id)}`",
        f"- live engine dir: `{ROOT / 'outputs' / 'kling_frame_to_video' / run_id}`",
        "",
        ]
    )
    if live.get("errors"):
        lines.extend(["## Errors", ""] + [f"- {e}" for e in live.get("errors") or []] + [""])
    if live.get("focus_probe"):
        probe = live["focus_probe"]
        before = probe.get("before") or {}
        lines.extend(
            [
                "## Focus probe",
                "",
                f"- visibility: {before.get('visibility_state')}",
                f"- hasFocus: {before.get('has_focus')}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling single 15s clip — generate once, save MP4, stop")
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
                f"# KLING SINGLE CLIP 15S REPORT\n\nFINAL STATUS: FAIL\n\nPreflight: {probe.message}\n",
                encoding="utf-8",
            )
            print(f"Preflight failed: {probe.message}")
            return 1

    from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content
    from content_brain.execution.kling_frame_to_video_live_engine import run_kling_frame_to_video_live
    from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4

    run_id = _create_run_id()
    run_dir = _run_dir(run_id)
    dest = run_dir / "clip_1.mp4"

    plan = plan_kling_frame_to_video_content(
        topic=args.topic,
        planned_duration_seconds=15,
        clip_count=CLIP_COUNT,
        mood="cinematic emotional dark neon",
        environment="rain-soaked cyberpunk rooftop at night",
    )
    clip_prompt = plan.clips[0].prompt

    (run_dir / "clip_prompt.txt").write_text(clip_prompt, encoding="utf-8")
    (run_dir / "run_config.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "clip_count": CLIP_COUNT,
                "aspect_ratio": "9:16",
                "duration_seconds": 15,
                "provider": "kling_3_pro",
                "topic": args.topic,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"run_id={run_id}")
    print("Single clip only — 1 Generate click, 15s, 9:16, Kling 3.0 Pro")

    live = run_kling_frame_to_video_live(
        starter_frame_path=None,
        frame_prompt=clip_prompt,
        topic=args.topic,
        run_id=run_id,
        clip_index=1,
        aspect_ratio="9:16",
        approve_generate=True,
        approved_by=args.approved_by,
        confirm_credit_spend=True,
        cdp_url=args.cdp_url,
        continuity_frame_in_ui=False,
    )
    live_dict = live.to_dict()
    (run_dir / "live_run_result.json").write_text(json.dumps(live_dict, indent=2), encoding="utf-8")

    mp4_src, recovery_audit = _resolve_mp4(run_id=run_id, live_result=live_dict, cdp_url=args.cdp_url)
    (run_dir / "recovery_audit.json").write_text(json.dumps(recovery_audit, indent=2), encoding="utf-8")
    verify: dict = {}
    final_status = "FAIL"

    if mp4_src and mp4_src.is_file():
        shutil.copy2(mp4_src, dest)
        verify = verify_extracted_kling_mp4(dest)
        (run_dir / "mp4_verify.json").write_text(json.dumps(verify, indent=2), encoding="utf-8")

    success = (
        bool(live_dict.get("generate_clicked"))
        and bool(live_dict.get("generation_completed"))
        and dest.is_file()
        and bool(verify.get("is_real_mp4"))
    )
    if success:
        final_status = "SUCCESS"

    report = _build_report(
        run_id=run_id,
        live=live_dict,
        mp4_path=dest if dest.is_file() else None,
        verify=verify,
        recovery_audit=recovery_audit,
        final_status=final_status,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"FINAL STATUS: {final_status}")
    print(f"MP4: {dest if dest.is_file() else 'missing'}")
    print(f"Report: {REPORT_PATH}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
