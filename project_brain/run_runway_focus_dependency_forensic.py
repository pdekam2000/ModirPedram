"""PHASE RUNWAY-FOCUS-DEPENDENCY-FORENSIC — probe CDP page + write report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_PATH = ROOT / "project_brain" / "RUNWAY_FOCUS_DEPENDENCY_REPORT.md"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


def _live_snapshot(cdp_url: str) -> dict | None:
    from content_brain.execution.browser_connectivity_probe import probe_cdp_socket
    from content_brain.execution.kling_frame_to_video_live_dry_run import _find_runway_generate_page
    from content_brain.execution.runway_focus_dependency_probe import snapshot_page_focus_state

    ok, _ = probe_cdp_socket(cdp_url)
    if not ok:
        return None
    playwright = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        page = _find_runway_generate_page(browser)
        if page is None:
            return {"error": "no_runway_generate_page"}
        return snapshot_page_focus_state(page)
    except Exception as exc:
        return {"error": str(exc)[:300]}
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Runway focus dependency forensic")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    from content_brain.execution.runway_focus_dependency_probe import (
        DEFAULT_REPORT_PATH,
        analyze_live_run_artifacts,
        build_forensic_conclusion,
        static_code_forensic,
        write_probe_report,
    )

    static = static_code_forensic()
    artifacts = analyze_live_run_artifacts(ROOT)
    live = None if args.skip_live else _live_snapshot(args.cdp_url)
    conclusion = build_forensic_conclusion(static=static, artifact_findings=artifacts, live_snapshot=live)

    write_probe_report(
        report_path=REPORT_PATH,
        static=static,
        artifact_findings=artifacts,
        live_snapshot=live,
        conclusion=conclusion,
    )

    payload = {
        "static": static,
        "artifact_count": len(artifacts),
        "live_snapshot": live,
        "conclusion": conclusion,
    }
    DEFAULT_REPORT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Report: {REPORT_PATH}")
    print(f"focus_dependent={conclusion.get('focus_dependent')}")
    print(f"generate_queued_before_operator_click={conclusion.get('generate_queued_before_operator_click')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
