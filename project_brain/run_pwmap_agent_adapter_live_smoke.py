"""Live smoke — ModirAgentOS pwmap Runway Agent adapter (one 15s Kling clip)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_PATH = ROOT / "project_brain" / "PWMAP_RUNWAY_AGENT_ADAPTER_REPORT.md"
DEFAULT_PROMPT = (
    "A cinematic vertical shot of a neon cyberpunk rooftop at night, rain reflections, "
    "slow camera push-in, native in-scene audio only — rain and city hum, 15 seconds."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="pwmap agent adapter live smoke")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--dry-run", action="store_true", help="Write job only, do not execute pwmap agent")
    parser.add_argument("--pwmap-root", default="")
    args = parser.parse_args()

    from content_brain.execution.pwmap_runway_agent_adapter import (
        build_pwmap_job,
        run_pwmap_agent,
    )

    job = build_pwmap_job(prompt=args.prompt, duration=15, aspect="9:16", native_audio=True)
    result = run_pwmap_agent(
        project_root=ROOT,
        job=job,
        pwmap_root=args.pwmap_root or None,
        dry_run=args.dry_run,
        timeout_seconds=3600,
    )
    print(f"run_id={result.run_id}")
    print(f"status={result.status}")
    print(f"ok={result.ok}")
    print(f"video_path={result.video_path or 'none'}")
    print(f"output_folder={result.output_folder}")

    _append_live_section(result.to_dict(), dry_run=args.dry_run)
    return 0 if result.ok else 1


def _append_live_section(payload: dict, *, dry_run: bool) -> None:
    lines = [
        "",
        "## Live smoke",
        "",
        f"- **mode:** {'dry_run' if dry_run else 'live'}",
        f"- **run_id:** `{payload.get('run_id')}`",
        f"- **status:** {payload.get('status')}",
        f"- **ok:** {payload.get('ok')}",
        f"- **final MP4:** `{payload.get('video_path') or 'none'}`",
        f"- **output folder:** `{payload.get('output_folder')}`",
        f"- **subprocess command:** `{' '.join(payload.get('subprocess_command') or [])}`",
        "",
    ]
    if REPORT_PATH.is_file():
        existing = REPORT_PATH.read_text(encoding="utf-8")
        if "## Live smoke" in existing:
            existing = existing.split("## Live smoke")[0].rstrip()
        REPORT_PATH.write_text(existing + "\n".join(lines), encoding="utf-8")
    else:
        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
