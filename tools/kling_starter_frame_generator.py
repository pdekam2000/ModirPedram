#!/usr/bin/env python3
"""Generate Kling Frame-to-Video Clip 1 starter frame (P3) — no Generate, no credits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_starter_frame_generator import (  # noqa: E402
    create_kling_frame_run_id,
    generate_kling_starter_frame,
)

DEFAULT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpsers. "
    'The woman whispers: "Stay with me... we\'re almost safe." '
    "Cinematic emotional sci-fi. Native audio."
)

SUMMARY_PATH = ROOT / "project_brain" / "kling_starter_frame_p3_summary.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling starter frame generator P3")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--mood", default="cinematic emotional sci-fi")
    parser.add_argument("--environment", default="neon cyberpunk city during heavy rain")
    parser.add_argument("--reference-image", default="")
    args = parser.parse_args()

    run_id = args.run_id.strip() or create_kling_frame_run_id()
    result = generate_kling_starter_frame(
        topic=args.topic,
        run_id=run_id,
        mood=args.mood,
        environment=args.environment,
        characters=["young woman", "wounded robot dog"],
        reference_image_path=args.reference_image or None,
    )
    SUMMARY_PATH.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), flush=True)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
