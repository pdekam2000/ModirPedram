#!/usr/bin/env python3
"""Recover first real Kling MP4 for a completed run without re-generating."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_product_run import recover_kling_product_run, resolve_kling_parent_run_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover first real Kling MP4 from existing Runway output")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--clip-index", type=int, default=1)
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    args = parser.parse_args()

    result = recover_kling_product_run(
        project_root=ROOT,
        run_id=resolve_kling_parent_run_id(args.run_id),
        clip_index=max(1, int(args.clip_index)),
        cdp_url=args.cdp_url,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
