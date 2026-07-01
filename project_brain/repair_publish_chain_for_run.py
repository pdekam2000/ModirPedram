#!/usr/bin/env python3
"""Repair publish post-processing chain for an existing pwmap Product Studio run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.product_publish_pipeline_trace import repair_publish_chain_for_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair publish chain for a pwmap run")
    parser.add_argument("--run-id", default="pwmap_20260627T153920_b27a7273")
    parser.add_argument("--run-dir", default="")
    args = parser.parse_args()

    result = repair_publish_chain_for_run(
        project_root=ROOT,
        run_id=str(args.run_id or ""),
        run_dir=str(args.run_dir or ""),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
