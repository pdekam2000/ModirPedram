#!/usr/bin/env python3
"""Kling Frame-to-Video live dry-run (P2) — validate UI prepare only. No Generate/credits/download."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_live_dry_run import (  # noqa: E402
    DEFAULT_CDP_URL,
    run_kling_frame_live_dry_run_p2,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402

SUMMARY_PATH = ROOT / "project_brain" / "kling_frame_live_dry_run_p2_summary.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling Frame-to-Video live dry-run P2")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))
    parser.add_argument("--map-only", action="store_true", help="Skip CDP; validate map + guards only")
    parser.add_argument("--starter-frame", default="", help="Path to starter_frame/frame_001.png")
    parser.add_argument("--starter-prompt", default="")
    parser.add_argument("--topic", default="")
    args = parser.parse_args()

    result = run_kling_frame_live_dry_run_p2(
        cdp_url=args.cdp_url,
        map_path=args.map_path,
        dry_run=True,
        connect_browser=not args.map_only,
        starter_frame_path=args.starter_frame or None,
        starter_image_prompt=args.starter_prompt,
        topic=args.topic,
    )
    SUMMARY_PATH.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), flush=True)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
