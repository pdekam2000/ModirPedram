"""PHASE CONTINUITY-DIRECTOR-V1-LIVE-SMOKE — 2-clip live chain via ContinuityDirectorAgent."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_PATH = ROOT / "project_brain" / "CONTINUITY_DIRECTOR_V1_LIVE_SMOKE_REPORT.md"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
APPROVED_BY = "continuity_director_v1_live_smoke"

STORY_IDEA = (
    "A mysterious young woman in a black futuristic coat on a rain-soaked cyberpunk rooftop "
    "follows a glowing blue signal while drones search the sky; she reaches the roof edge as the "
    "signal becomes a giant symbol above the city. Cinematic, emotional, dark neon, realistic, high tension."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip_result(chain: dict, index: int) -> dict:
    for item in chain.get("clip_results") or []:
        if int(item.get("clip_index") or 0) == index:
            return dict(item)
    return {}


def _live_payload(clip: dict) -> dict:
    return dict(clip.get("live_payload") or {})


def _clip_generated(clip: dict) -> bool:
    if not clip:
        return False
    live = _live_payload(clip)
    if clip.get("ok"):
        return True
    if clip.get("generate_clicked"):
        return True
    if live.get("generation_completed"):
        return True
    if live.get("generate_clicked"):
        return True
    return str(live.get("status") or "").lower() in {"completed", "download_failed", "generation_completed"}


def _mp4_ok(clip: dict) -> bool:
    from agents.continuity_director_agent import validate_real_mp4

    path = str(clip.get("mp4_path") or "").strip()
    if not path:
        return False
    return bool(validate_real_mp4(path).get("is_real_mp4"))


def _png_uploaded_for_clip2(clip2: dict) -> bool:
    if not clip2:
        return False
    input_path = str(clip2.get("first_frame_input_path") or "").strip()
    if input_path and Path(input_path).is_file():
        return True
    live = _live_payload(clip2)
    checklist = dict(live.get("approval_checklist") or {})
    if checklist.get("first_frame_uploaded"):
        return True
    starter = str(live.get("starter_frame_path") or live.get("first_frame_path") or "").strip()
    return bool(starter and Path(starter).is_file())


def _failure_point(*, chain: dict, clip1: dict, clip2: dict) -> str:
    stop_reason = str(chain.get("stop_reason") or "").strip()
    stopped_at = chain.get("stopped_at_clip")
    if stop_reason:
        return f"clip {stopped_at or '?'}: {stop_reason}"
    if not _clip_generated(clip1):
        return "clip 1: generation not completed"
    if not _mp4_ok(clip1):
        return "clip 1: MP4 missing or invalid"
    if not str(clip1.get("last_frame_path") or "").strip():
        return "clip 1: last frame PNG not extracted"
    if not _png_uploaded_for_clip2(clip2):
        return "clip 2: continuity PNG not uploaded"
    if not _clip_generated(clip2):
        return "clip 2: generation not completed"
    if not _mp4_ok(clip2):
        return "clip 2: MP4 missing or invalid"
    if chain.get("ok"):
        return "none"
    return str(chain.get("status") or "unknown")


def _build_report(*, run_id: str, chain: dict, preflight: dict, topic_guard: dict | None = None) -> str:
    clip1 = _clip_result(chain, 1)
    clip2 = _clip_result(chain, 2)
    live1 = _live_payload(clip1)
    live2 = _live_payload(clip2)

    agent_run_dir = ROOT / "outputs" / "continuity_director_v1" / run_id
    live_run_dir = ROOT / "outputs" / "kling_frame_to_video" / run_id

    clip1_generated = _clip_generated(clip1)
    clip1_mp4 = _mp4_ok(clip1)
    last_frame = bool(str(clip1.get("last_frame_path") or "").strip() and Path(str(clip1.get("last_frame_path"))).is_file())
    png_uploaded = _png_uploaded_for_clip2(clip2)
    clip2_generated = _clip_generated(clip2)
    clip2_mp4 = _mp4_ok(clip2)
    final_status = "pass" if chain.get("ok") else "fail"
    failure = _failure_point(chain=chain, clip1=clip1, clip2=clip2)

    topic_guard = topic_guard or {}
    clip1_audit = dict(clip1.get("mp4_recovery_audit") or {})
    clip2_audit = dict(clip2.get("mp4_recovery_audit") or {})

    lines = [
        "# CONTINUITY DIRECTOR V1 LIVE SMOKE REPORT",
        "",
        f"Generated: {_now_iso()}",
        "",
        "## Summary",
        "",
        f"- **run_id:** `{run_id}`",
        f"- **clip 1 generated:** {'yes' if clip1_generated else 'no'}",
        f"- **clip 1 MP4 recovered/downloaded:** {'yes' if clip1_mp4 else 'no'}",
        f"- **last frame extracted:** {'yes' if last_frame else 'no'}",
        f"- **PNG uploaded for clip 2:** {'yes' if png_uploaded else 'no'}",
        f"- **clip 2 generated:** {'yes' if clip2_generated else 'no'}",
        f"- **clip 2 MP4 recovered/downloaded:** {'yes' if clip2_mp4 else 'no'}",
        f"- **final status:** {final_status}",
        f"- **failure point:** {failure}",
        "",
        "## Topic Guard",
        "",
        f"- **passed:** {topic_guard.get('topic_guard_passed', chain.get('topic_guard_passed'))}",
        f"- **starter_image_prompt chars:** {len(str(topic_guard.get('starter_image_prompt') or chain.get('starter_image_prompt') or ''))}",
        "",
        "## MP4 recovery (Clip 1)",
        "",
        f"- **methods attempted:** {', '.join(clip1_audit.get('attempted_methods') or []) or 'none'}",
        f"- **quarantined:** {clip1_audit.get('quarantined_paths') or []}",
        f"- **final path:** `{clip1_audit.get('final_path') or clip1.get('mp4_path') or 'none'}`",
        f"- **failure reason:** {clip1_audit.get('failure_reason') or 'none'}",
        "",
        "## MP4 recovery (Clip 2)",
        "",
        f"- **methods attempted:** {', '.join(clip2_audit.get('attempted_methods') or []) or 'none'}",
        f"- **final path:** `{clip2_audit.get('final_path') or clip2.get('mp4_path') or 'none'}`",
        "",
        "## Constraints",
        "",
        "- continuity method: last_frame_extract_upload (no Use Frame)",
        "- max clips: 2",
        "- max generate clicks: 2",
        "- provider: Kling 3.0 Pro via Frame-to-Video live engine",
        "- aspect: 9:16 / 15s per clip",
        "",
        "## Preflight",
        "",
        f"- passed: {preflight.get('passed')}",
        f"- message: {preflight.get('message') or 'ok'}",
    ]
    for check in preflight.get("checks") or []:
        lines.append(f"- {check.get('id')}: {'pass' if check.get('passed') else 'fail'} — {check.get('message')}")

    lines.extend(
        [
            "",
            "## Chain",
            "",
            f"- status: {chain.get('status')}",
            f"- clips_completed: {chain.get('clips_completed')}",
            f"- generate_clicks: {chain.get('generate_clicks')}",
            f"- stop_reason: {chain.get('stop_reason') or 'none'}",
            f"- stopped_at_clip: {chain.get('stopped_at_clip')}",
            f"- chain_path: `{chain.get('chain_path') or agent_run_dir / 'continuity_director_chain.json'}`",
            "",
            "## Clip 1",
            "",
            f"- generate_clicked: {clip1.get('generate_clicked') or live1.get('generate_clicked')}",
            f"- mp4_path: `{clip1.get('mp4_path') or 'none'}`",
            f"- last_frame_path: `{clip1.get('last_frame_path') or 'none'}`",
            f"- live status: {live1.get('status') or 'n/a'}",
            f"- errors: {clip1.get('errors') or live1.get('errors') or []}",
            "",
            "## Clip 2",
            "",
            f"- first_frame_input_path: `{clip2.get('first_frame_input_path') or 'none'}`",
            f"- generate_clicked: {clip2.get('generate_clicked') or live2.get('generate_clicked')}",
            f"- mp4_path: `{clip2.get('mp4_path') or 'none'}`",
            f"- live status: {live2.get('status') or 'n/a'}",
            f"- first_frame_uploaded: {_png_uploaded_for_clip2(clip2)}",
            f"- errors: {clip2.get('errors') or live2.get('errors') or []}",
            "",
            "## Artifacts",
            "",
            f"- agent run dir: `{agent_run_dir}`",
            f"- live engine run dir: `{live_run_dir}`",
            "",
        ]
    )
    return "\n".join(lines)


def _preflight(cdp_url: str) -> dict:
    from content_brain.execution.browser_connectivity_probe import run_browser_probes

    result = run_browser_probes({"cdp_url": cdp_url}, project_root=ROOT, require_playwright_attach=True)
    return {
        "passed": result.passed,
        "message": result.message,
        "reject_code": result.reject_code,
        "checks": list(result.checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuity Director V1 live 2-clip smoke test")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL, help="Chrome CDP URL (default: :9222)")
    parser.add_argument("--approved-by", default=APPROVED_BY, help="Approval actor label for live engine")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip CDP preflight (not recommended)",
    )
    args = parser.parse_args()

    preflight = {"passed": True, "message": "skipped", "checks": []}
    if not args.skip_preflight:
        print(f"Preflight CDP at {args.cdp_url} ...")
        preflight = _preflight(args.cdp_url)
        if not preflight["passed"]:
            report = _build_report(
                run_id="preflight_failed",
                chain={
                    "ok": False,
                    "status": "stopped",
                    "stop_reason": preflight.get("reject_code") or "preflight_failed",
                    "clip_results": [],
                },
                preflight=preflight,
            )
            REPORT_PATH.write_text(report, encoding="utf-8")
            print(f"Preflight failed: {preflight.get('message')}")
            print(f"Report written: {REPORT_PATH}")
            return 1

    from agents.continuity_director_agent import (
        ContinuityDirectorAgent,
        build_frame_live_generate_hook,
        build_frame_live_recover_hook,
        ensure_kling_frame_metadata_for_plan,
        plan_clip_chain,
    )
    from content_brain.execution.kling_starter_frame_generator import create_kling_frame_run_id

    run_id = create_kling_frame_run_id()
    run_dir = ROOT / "outputs" / "continuity_director_v1" / run_id
    print(f"run_id={run_id}")
    print("Watch Runway Chrome — 2 clips, max 2 Generate clicks, no Use Frame.")

    plan = plan_clip_chain(
        run_id=run_id,
        topic=STORY_IDEA,
        clip_count=2,
        planned_duration_seconds=30,
        mood="cinematic emotional dark neon",
        environment="rain-soaked cyberpunk rooftop at night",
    )
    topic_guard = ensure_kling_frame_metadata_for_plan(plan, ROOT)

    agent = ContinuityDirectorAgent(project_root=ROOT)
    generate_hook = build_frame_live_generate_hook(
        approved_by=args.approved_by,
        confirm_credit_spend=True,
        cdp_url=args.cdp_url,
        aspect_ratio="9:16",
        topic=STORY_IDEA,
    )
    recover_hook = build_frame_live_recover_hook(cdp_url=args.cdp_url, project_root=ROOT)

    result = agent.run_chain(
        plan=plan,
        run_dir=run_dir,
        generate_clip=generate_hook,
        recover_mp4=recover_hook,
        dry_run=False,
    )

    chain = result.to_dict()
    chain_path = run_dir / "continuity_director_chain.json"
    chain_path.write_text(json.dumps(chain, indent=2), encoding="utf-8")

    report = _build_report(run_id=run_id, chain=chain, preflight=preflight, topic_guard=topic_guard)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"Chain status: {result.status} ok={result.ok} clips={result.clips_completed}/{result.clip_count}")
    print(f"Generate clicks: {result.generate_clicks}")
    if result.stop_reason:
        print(f"Stop reason: {result.stop_reason} at clip {result.stopped_at_clip}")
    print(f"Report written: {REPORT_PATH}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
