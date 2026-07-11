#!/usr/bin/env python3
"""Kling Frame-to-Video live runner (P4) — approval-gated Generate + CDP download recovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_live_engine import (  # noqa: E402
    DEFAULT_CDP_URL,
    DEFAULT_STARTER_RUN_ID,
    OUTPUT_ROOT,
    recover_kling_frame_output,
    run_kling_frame_to_video_live,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402

SUMMARY_PATH = ROOT / "project_brain" / "kling_frame_live_p4_summary.json"
DEFAULT_STARTER_FRAME = (
    ROOT
    / "outputs"
    / "kling_frame_to_video"
    / DEFAULT_STARTER_RUN_ID
    / "starter_frame"
    / "frame_001.png"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling Frame-to-Video live runner P4 (approval-gated)")
    parser.add_argument("--starter-frame", default=str(DEFAULT_STARTER_FRAME))
    parser.add_argument("--frame-prompt", default="", help="Override P3/planner frame prompt")
    parser.add_argument("--topic", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))
    parser.add_argument("--max-wait-minutes", type=int, default=25)
    parser.add_argument(
        "--recover-output",
        action="store_true",
        help="Recover/download already-generated output without clicking Generate",
    )
    parser.add_argument(
        "--approve-generate",
        action="store_true",
        help="Explicit operator approval to click Generate (spends credits)",
    )
    parser.add_argument(
        "--approved-by",
        default="",
        help='Operator name — required with --approve-generate (e.g. "Pedram")',
    )
    parser.add_argument(
        "--confirm-credit-spend",
        action="store_true",
        help="Second explicit confirmation that credits will be spent",
    )
    args = parser.parse_args()

    if args.recover_output:
        if not args.run_id:
            print("ERROR: --recover-output requires --run-id", file=sys.stderr)
            return 2
        result = recover_kling_frame_output(run_id=args.run_id, cdp_url=args.cdp_url)
        SUMMARY_PATH.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0 if result.ok else 1

    result = run_kling_frame_to_video_live(
        starter_frame_path=args.starter_frame,
        frame_prompt=args.frame_prompt,
        topic=args.topic,
        run_id=args.run_id,
        approve_generate=args.approve_generate,
        approved_by=args.approved_by,
        confirm_credit_spend=args.confirm_credit_spend,
        cdp_url=args.cdp_url,
        map_path=Path(args.map_path),
        max_wait_minutes=args.max_wait_minutes,
    )

    SUMMARY_PATH.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    run_dir = OUTPUT_ROOT / result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "live_run_summary.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    if result.status == "awaiting_approval":
        print("\n--- APPROVAL CHECKLIST ---")
        print(json.dumps(result.approval_checklist, indent=2, ensure_ascii=False))
        print("\nTo proceed (spends credits):")
        print(
            '  python tools/kling_frame_to_video_live_p4.py '
            f'--starter-frame "{args.starter_frame}" '
            '--approve-generate --approved-by "Pedram" --confirm-credit-spend'
        )
    if result.status == "download_failed":
        print("\n--- DOWNLOAD FAILED — RECOVERY AVAILABLE ---")
        print(
            "  python tools/kling_frame_to_video_live_p4.py "
            f'--recover-output --run-id "{result.run_id}"'
        )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
