"""Recover real Kling MP4 from current browser output — no Generate, no credits."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CDP_URL = "http://127.0.0.1:9222"
REPORT_PATH = ROOT / "project_brain" / "KLING_REAL_MP4_DOWNLOAD_EXTRACTOR_REPORT.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover real Kling MP4 from visible Runway output")
    parser.add_argument("--run-id", required=True, help="Kling frame run id")
    parser.add_argument("--clip-index", type=int, default=1, help="Clip index (default: 1)")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL, help="Chrome CDP URL")
    args = parser.parse_args()

    from content_brain.execution.browser_connectivity_probe import probe_cdp_socket
    from content_brain.execution.kling_frame_to_video_live_engine import recover_kling_frame_output
    from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4
    from content_brain.execution.kling_starter_frame_generator import kling_frame_clip_dir, kling_frame_run_dir

    ok, msg = probe_cdp_socket(args.cdp_url)
    if not ok:
        print(f"CDP preflight failed: {msg}")
        return 1

    run_dir = kling_frame_run_dir(ROOT, args.run_id)
    clip_dir = kling_frame_clip_dir(run_dir, args.clip_index)
    dest = clip_dir / f"clip_{args.clip_index}.mp4"

    print(f"Recovery run_id={args.run_id} clip={args.clip_index}")
    print(f"Target: {dest}")
    print("No Generate click — extracting from current browser output only.")

    result = recover_kling_frame_output(
        run_id=args.run_id,
        cdp_url=args.cdp_url,
        clip_index=args.clip_index,
    )

    payload = result.to_dict()
    report_json = clip_dir / "recovery_report.json"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    verify = verify_extracted_kling_mp4(dest) if dest.is_file() else {"is_real_mp4": False}
    recovery_run_md = clip_dir / "recovery_run_summary.md"
    lines = [
        "# KLING REAL MP4 RECOVERY RUN",
        "",
        f"Generated: {_now_iso()}",
        "",
        f"- **run_id:** `{args.run_id}`",
        f"- **clip_index:** {args.clip_index}",
        f"- **recovery ok:** {result.ok}",
        f"- **output:** `{result.clip_output_path or dest}`",
        f"- **is_real_mp4:** {verify.get('is_real_mp4')}",
        f"- **attempted methods:** {', '.join(result.download_strategies or []) or 'none'}",
        f"- **errors:** {result.errors or []}",
        "",
        f"Report JSON: `{report_json}`",
    ]
    recovery_run_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Recovery ok={result.ok}")
    if result.errors:
        print("Errors:", result.errors)
    print(f"Summary: {recovery_run_md}")
    print(f"Full report: {REPORT_PATH}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
