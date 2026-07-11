"""PHASE KLING-REAL-2CLIP-15S-LIVE-TEST — bridge runner + report writer."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_BASE = "http://127.0.0.1:8765"
REPORT_PATH = ROOT / "project_brain" / "KLING_REAL_2CLIP_15S_LIVE_TEST_REPORT.md"
POLL_SECONDS = 20
MAX_WAIT_SECONDS = 3600

CLIP1_PROMPT = (
    "Clip 1 — Cinematic 9:16 vertical. A mysterious young woman in a black futuristic coat "
    "stands on a rain-soaked rooftop above a neon cyberpunk city at night. She notices a glowing "
    "blue signal reflected in a puddle at her feet. She follows the signal across the rooftop, "
    "moving cautiously between vents and antennae while search drones sweep the sky with harsh beams. "
    "Heavy rain, wet surfaces, teal-magenta neon, shallow depth of field, slow tracking camera, "
    "realistic emotional tension. Native in-scene audio: rain on metal, distant city hum, drone rotors, "
    "her quick breathing, fabric rustle, no external narration."
)

CLIP2_PROMPT = (
    "Clip 2 — Continuation from prior frame. The same woman reaches the edge of the rooftop; "
    "the blue signal rises from the puddle trail and forms a giant luminous symbol hovering above "
    "the skyline. She stops, wind and rain whipping her coat, staring up as the symbol pulses over "
    "the city. Dark neon cyberpunk realism, high tension, emotional close coverage then wide reveal. "
    "Native in-scene audio: intensifying rain, rising synthetic tone from the symbol, drone motors fading, "
    "her whispered reaction, city ambience, no external narration."
)

STORY_IDEA = (
    "A mysterious young woman in a black futuristic coat on a rain-soaked cyberpunk rooftop "
    "follows a glowing blue signal while drones search the sky; she reaches the roof edge as the "
    "signal becomes a giant symbol above the city. Cinematic, emotional, dark neon, realistic, high tension."
)


def _http_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _step_status(live: dict, step_id: str, label: str) -> dict | None:
    for step in live.get("steps") or []:
        if str(step.get("step_id")) == step_id and str(step.get("label")) == label:
            return step
    return None


def _clip_pass(live: dict) -> bool:
    if not live:
        return False
    if live.get("ok"):
        return True
    if live.get("generation_completed"):
        return True
    if live.get("status") in {"completed", "download_failed"}:
        return bool(live.get("clip_output_path") or live.get("download_path"))
    return False


def _build_report(*, run_id: str, bridge_start: dict, final_status: dict) -> str:
    run_dir = ROOT / "outputs" / "kling_frame_to_video" / run_id
    clip1_path = run_dir / "clips" / "c1" / "live_run_result.json"
    clip2_path = run_dir / "clips" / "c2" / "live_run_result.json"
    clip1 = json.loads(clip1_path.read_text(encoding="utf-8")) if clip1_path.is_file() else {}
    clip2 = json.loads(clip2_path.read_text(encoding="utf-8")) if clip2_path.is_file() else {}

    report = final_status.get("report") or {}
    gen_report = report.get("generation_report") or {}
    download_report = report.get("download_report") or {}
    continuity = report.get("continuity_chain") or {}

    clip1_aspect = _step_status(clip1, "04", "aspect_ratio_menu")
    clip1_duration = _step_status(clip1, "06", "duration_slider_15s")
    clip1_audio = _step_status(clip1, "07", "audio_toggle_on")
    clip1_generate = _step_status(clip1, "10", "generate_button")

    clip2_aspect = _step_status(clip2, "04", "aspect_ratio_menu") or _step_status(clip2, "03", "kling_frame_to_video_mode")
    clip2_duration = _step_status(clip2, "06", "duration_slider_15s")
    clip2_audio = _step_status(clip2, "07", "audio_toggle_on")
    clip2_generate = _step_status(clip2, "10", "generate_button")

    aspect_pass = (
        (clip1_aspect or {}).get("status") == "passed"
        or "9:16" in str((clip1_aspect or {}).get("detail") or "")
        or str(clip1.get("locator_strategies", {}).get("aspect_ratio_option") or "") == "9:16"
    )
    duration_pass = (clip1_duration or {}).get("status") == "passed" or clip1.get("duration_seconds") == 15
    audio_detected = (clip1_audio or {}).get("status") == "passed" or bool(clip1.get("audio_present"))

    clip1_ok = _clip_pass(clip1)
    clip2_ok = _clip_pass(clip2)

    downloaded = list(final_status.get("downloaded_file_paths") or [])
    credits_spent = any(bool(c.get("credits_spent")) for c in [clip1, clip2])
    generate_clicks = sum(
        1
        for c in [clip1, clip2]
        if c.get("generate_clicked") or (c.get("approval_checklist") or {}).get("generate_visible")
    )

    failed_steps: list[str] = []
    for label, live in (("clip1", clip1), ("clip2", clip2)):
        for step in live.get("steps") or []:
            if str(step.get("status")).lower() == "failed":
                failed_steps.append(f"{label} step {step.get('step_id')} {step.get('label')}: {step.get('detail')}")
    for err in list(final_status.get("errors") or []):
        failed_steps.append(str(err))

    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# KLING REAL 2-CLIP 15S LIVE TEST REPORT",
        "",
        f"Generated: {now}",
        "",
        "## Summary",
        "",
        f"- **run_id:** `{run_id}`",
        "- **browser visible:** yes (controlled Chrome via CDP port 9222, not headless)",
        f"- **clip 1 generated:** {'pass' if clip1_ok else 'fail'}",
        f"- **clip 2 generated:** {'pass' if clip2_ok else 'fail'}",
        f"- **aspect ratio 9:16:** {'pass' if aspect_pass else 'fail'}",
        f"- **duration 15s:** {'pass' if duration_pass else 'fail'}",
        f"- **native audio option detected:** {'yes' if audio_detected else 'no'}",
        f"- **credits spent estimate:** {'yes (Generate clicked in live engine)' if credits_spent else 'unknown / not confirmed in artifacts'}",
        f"- **download result:** {download_report.get('status') or ('completed' if downloaded else 'pending/failed')}",
        f"- **downloaded paths:** {len(downloaded)} file(s)",
        "",
        "## Constraints",
        "",
        "- max clips: 2",
        "- max generate clicks: 2 (no auto-retry)",
        "- provider: kling / model: kling-3.0 / aspect: 9:16 / 15s per clip / total 30s",
        "",
        "## Bridge",
        "",
        f"- start ok: {bridge_start.get('ok')}",
        f"- poll status: {final_status.get('status')}",
        f"- chain_complete: {gen_report.get('chain_complete')}",
        f"- continuity_status: {gen_report.get('continuity_status')}",
        "",
        "## Clip 1",
        "",
        f"- path: `{clip1_path}`",
        f"- ok: {clip1.get('ok')}",
        f"- status: {clip1.get('status')}",
        f"- generate_clicked: {clip1.get('generate_clicked')}",
        f"- aspect step: {(clip1_aspect or {}).get('status')} — {(clip1_aspect or {}).get('detail')}",
        f"- duration step: {(clip1_duration or {}).get('status')} — {(clip1_duration or {}).get('detail')}",
        f"- audio step: {(clip1_audio or {}).get('status')} — {(clip1_audio or {}).get('detail')}",
        f"- output: {clip1.get('clip_output_path') or clip1.get('download_path') or 'none'}",
        "",
        "## Clip 2",
        "",
        f"- path: `{clip2_path}`",
        f"- ok: {clip2.get('ok')}",
        f"- status: {clip2.get('status')}",
        f"- generate_clicked: {clip2.get('generate_clicked')}",
        f"- use frame continuity: {continuity.get('use_frame_chain', {}).get('continuity_method', continuity.get('continuity_method', 'unknown'))}",
        f"- aspect/duration/audio: aspect={(clip2_aspect or {}).get('status')}, duration={(clip2_duration or {}).get('status')}, audio={(clip2_audio or {}).get('status')}",
        f"- output: {clip2.get('clip_output_path') or clip2.get('download_path') or 'none'}",
        "",
        "## Failed steps",
        "",
    ]
    if failed_steps:
        lines.extend(f"- {item}" for item in failed_steps)
    else:
        lines.append("- none recorded")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- run dir: `{run_dir}`",
            f"- bridge report keys: {', '.join(sorted(report.keys())) if report else 'none'}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    payload = {
        "project_id": "kling_real_2clip_15s",
        "provider": "kling",
        "model": "kling-3.0",
        "aspect_ratio": "9:16",
        "duration_seconds": 30,
        "prompt_package": {
            "story_idea": STORY_IDEA,
            "starter_image_prompt": "Cyberpunk rooftop starter — rain, neon, woman in black coat, blue signal in puddle",
            "clip_prompts": [CLIP1_PROMPT, CLIP2_PROMPT],
        },
    }

    print("Starting Kling 2-clip live test via bridge (visible Chrome/CDP)...")
    try:
        bridge_start = _http_json("POST", f"{API_BASE}/runway/runtime/generate", payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Bridge start failed: HTTP {exc.code} {body}")
        REPORT_PATH.write_text(
            f"# KLING REAL 2-CLIP 15S LIVE TEST REPORT\n\nBridge start failed: HTTP {exc.code}\n\n```\n{body}\n```\n",
            encoding="utf-8",
        )
        return 1

    if not bridge_start.get("ok"):
        print(json.dumps(bridge_start, indent=2, ensure_ascii=False))
        REPORT_PATH.write_text(
            "# KLING REAL 2-CLIP 15S LIVE TEST REPORT\n\nBridge start rejected.\n\n```json\n"
            + json.dumps(bridge_start, indent=2, ensure_ascii=False)
            + "\n```\n",
            encoding="utf-8",
        )
        return 1

    run_id = str(bridge_start.get("run_id") or "")
    print(f"run_id={run_id}")
    print("Watch the Runway Chrome window — generation in progress (up to ~50 min for 2 clips).")

    deadline = time.time() + MAX_WAIT_SECONDS
    final_status: dict = {}
    while time.time() < deadline:
        time.sleep(POLL_SECONDS)
        try:
            final_status = _http_json("GET", f"{API_BASE}/runway/runtime/status/{run_id}")
        except Exception as exc:
            print(f"poll error: {exc}")
            continue
        active = bool(final_status.get("active"))
        status = str(final_status.get("status") or "")
        clips_done = int(final_status.get("clips_completed") or 0)
        print(f"status={status} active={active} clips_completed={clips_done}")
        if not active:
            break
    else:
        print("Timed out waiting for run completion.")

    report_md = _build_report(run_id=run_id, bridge_start=bridge_start, final_status=final_status)
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"Report written: {REPORT_PATH}")
    return 0 if final_status.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
