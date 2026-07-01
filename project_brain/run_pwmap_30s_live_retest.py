"""Execute PWMAP 30s two-clip live retest with safety + forensic capture."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHANNEL_TOPIC = "dark fantasy analog horror stories"
REPORT_PATH = ROOT / "project_brain" / "PWMAP_30S_TWO_CLIP_LIVE_RETEST_REPORT.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    from content_brain.execution.credit_safety_guard import evaluate_credit_safety
    from ui.api.product_studio_service import ProductStudioService

    print("PWMAP 30s live retest — preflight")
    service = ProductStudioService(ROOT)

    payload = {
        "topic_mode": "custom",
        "custom_topic": CHANNEL_TOPIC,
        "specific_story_override": "",
        "duration_seconds": 30,
        "provider": "kling_3_0_pro_native_audio",
        "audio_strategy": "kling_native_audio",
        "story_diversity_mode": "safe_variety",
        "free_credit_mode": True,
        "live_retest": True,
        "phase": "PWMAP-30S-TWO-CLIP-LIVE-RETEST",
        "use_ai_director": True,
        "use_prompt_critic": True,
    }

    credit = evaluate_credit_safety(
        payload=payload,
        provider="runway",
        model="Kling 3.0 Pro",
        duration_seconds=30,
        clip_count=2,
        live_retest=True,
    )
    print("credit_mode:", credit.credit_mode)
    print("paid_credit_risk:", credit.paid_credit_risk)
    print("allowed:", credit.allowed)
    if credit.blocked:
        print("BLOCKED:", credit.block_reason)
        return 1

    preflight = service.create_video_preflight(payload)
    print("story_title:", (preflight.get("channel_story_idea") or {}).get("title"))
    print("ideation_version:", preflight.get("story_ideation_version"))

    print("Starting live generation (this may take 20-40 minutes)...")
    result = service.create_video_generate(payload, runway_service=None)
    run_id = str(result.get("run_id") or "")
    run_dir = Path(str(result.get("run_dir") or result.get("output_folder") or ""))
    print("run_id:", run_id)
    print("status:", result.get("status"))
    print("ok:", result.get("ok"))

    forensic: dict = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "generate_result": {k: result.get(k) for k in sorted(result.keys()) if k != "pwmap_agent"},
        "credit_safety": credit.to_report(),
        "preflight_story": preflight.get("channel_story_idea"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if run_dir.is_dir():
        clip1 = run_dir / "clip_1.mp4"
        clip2 = run_dir / "clip_2.mp4"
        stdout = (run_dir / "subprocess_stdout.log").read_text(encoding="utf-8") if (run_dir / "subprocess_stdout.log").is_file() else ""
        job = json.loads((run_dir / "job.json").read_text(encoding="utf-8")) if (run_dir / "job.json").is_file() else {}
        prompts = list(job.get("prompts") or [])
        forensic["clip_1_exists"] = clip1.is_file()
        forensic["clip_2_exists"] = clip2.is_file()
        forensic["clip_3_exists"] = (run_dir / "clip_3.mp4").is_file()
        if clip1.is_file() and clip2.is_file():
            forensic["clip_1_sha256"] = _sha256(clip1)
            forensic["clip_2_sha256"] = _sha256(clip2)
            forensic["hashes_differ"] = forensic["clip_1_sha256"] != forensic["clip_2_sha256"]
        if len(prompts) >= 2:
            forensic["clip_1_prompt_hash"] = _prompt_hash(prompts[0])
            forensic["clip_2_prompt_hash"] = _prompt_hash(prompts[1])
            forensic["prompts_differ"] = prompts[0] != prompts[1]
        forensic["use_frame_evidence"] = "Use frame clicked" in stdout and "CLIP 2/2" in stdout
        forensic["generation_success"] = result.get("ok")
        forensic["download_success"] = clip1.is_file() and clip2.is_file()

        merged = service._merge_pwmap_results(
            service.get_results(run_id=run_id, run_dir=str(run_dir).replace("\\", "/"))
        )
        forensic["results_truth"] = {
            "downloaded_clip_count": merged.get("downloaded_clip_count"),
            "expected_clip_count": merged.get("expected_clip_count"),
            "clip_3_not_applicable": merged.get("clip_3_not_applicable"),
            "duplicate_chain_failed": merged.get("duplicate_chain_failed"),
            "video_approved": merged.get("video_approved"),
            "youtube_upload_allowed": merged.get("youtube_upload_allowed"),
            "delivery_truth_status": merged.get("delivery_truth_status"),
        }

    out = run_dir / "live_retest_forensic.json" if run_dir.is_dir() else ROOT / "project_brain" / "live_retest_forensic.json"
    out.write_text(json.dumps(forensic, indent=2), encoding="utf-8")
    print("forensic:", out)
    return 0 if forensic.get("hashes_differ") else 2


if __name__ == "__main__":
    raise SystemExit(main())
