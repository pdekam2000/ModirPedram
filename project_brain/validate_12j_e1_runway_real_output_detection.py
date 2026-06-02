"""
Phase 12J-E1 — Runway real output URL detection and placeholder rejection (unit/mocks).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrators.runway_browser_orchestrator import RunwayBrowserOrchestrator
from providers.runway_api_errors import RunwayProviderError
from providers.runway_artifact_utils import MIN_ARTIFACT_BYTES, finalize_download_artifact
from providers.runway_output_url_classifier import (
    RUNWAY_PLACEHOLDER_OUTPUT_REJECTED,
    RUNWAY_REAL_OUTPUT_NOT_DETECTED,
    is_real_runway_output_url,
    runway_output_rejection_reason,
)


EMPTY_STATE_URL = (
    "https://d3phaj0sisr2ct.cloudfront.net/app/mira/empty-states/"
    "edit-studio-empty-state.webm"
)
REAL_LOOKING_URL = (
    "https://dnznrvs05pmza.cloudfront.net/generated/clip_abc123/output.mp4"
    "?X-Amz-Signature=abc"
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


class _FakePage:
    def __init__(self, body_text: str = "", video_sources=None):
        self.body_text = body_text
        self.video_sources = list(video_sources or [])

    def evaluate(self, script):
        if "innerText" in script:
            return self.body_text
        if "querySelectorAll" in script and "visible" in script:
            return [
                {
                    "index": 0,
                    "src": src,
                    "width": 200,
                    "height": 200,
                    "top": 100,
                    "left": 0,
                    "visible": True,
                }
                for src in self.video_sources
            ]
        if "querySelectorAll" in script:
            return list(self.video_sources)
        return None


def main() -> int:
    # 1. edit-studio-empty-state.webm rejected
    _pass(
        "reject_edit_studio_empty_state",
        not is_real_runway_output_url(EMPTY_STATE_URL),
        runway_output_rejection_reason(EMPTY_STATE_URL) or "",
    )

    # 2. empty-states URLs rejected
    _pass(
        "reject_empty_states_path",
        not is_real_runway_output_url("https://cdn.example.com/app/empty-states/demo.webm"),
    )

    # 3. generic placeholder URLs rejected
    _pass(
        "reject_placeholder_marker",
        not is_real_runway_output_url("https://cdn.example.com/assets/placeholder.mp4"),
    )

    # 4. real-looking generated media URL accepted
    _pass("accept_real_looking_url", is_real_runway_output_url(REAL_LOOKING_URL))

    # 5–8. wait loop: no placeholder return; fails with RUNWAY_REAL_OUTPUT_NOT_DETECTED
    page = _FakePage(body_text="ready", video_sources=[EMPTY_STATE_URL])
    orch = RunwayBrowserOrchestrator(wait_seconds=0)
    os.environ["RUNWAY_BROWSER_POLL_INTERVAL"] = "0"
    try:
        try:
            orch.wait_for_generated_video_url(
                page,
                [],
                clip_index=2,
                max_wait_seconds=0.05,
            )
            _pass("fallback_does_not_accept_placeholder", False, "returned URL")
        except RunwayProviderError as exc:
            _pass(
                "fallback_does_not_accept_placeholder",
                exc.code == RUNWAY_REAL_OUTPUT_NOT_DETECTED,
                exc.code,
            )
            rejected = list((exc.details or {}).get("rejected_candidates") or [])
            _pass("failure_code_real_output_not_detected", exc.code == RUNWAY_REAL_OUTPUT_NOT_DETECTED)
            _pass(
                "rejected_candidates_recorded",
                len(rejected) >= 1,
                str(len(rejected)),
            )
            _pass(
                "wait_kept_rejecting_placeholder",
                any(EMPTY_STATE_URL in str(item.get("url", "")) for item in rejected),
            )
    finally:
        os.environ.pop("RUNWAY_BROWSER_POLL_INTERVAL", None)

    # 6. download validator rejects placeholder even if size > 100KB
    with tempfile.TemporaryDirectory() as tmp:
        big_path = Path(tmp) / "edit-studio-empty-state_download.mp4"
        big_path.write_bytes(b"x" * (MIN_ARTIFACT_BYTES + 500))
        try:
            finalize_download_artifact(
                big_path,
                mode="browser",
                provider_id="runway_browser",
                source_url=EMPTY_STATE_URL,
                clip_index=1,
            )
            _pass("download_rejects_placeholder_despite_size", False)
        except RunwayProviderError as exc:
            _pass(
                "download_rejects_placeholder_despite_size",
                exc.code == RUNWAY_PLACEHOLDER_OUTPUT_REJECTED,
                exc.code,
            )

    # 10. no changes to prompt/generate logic (static guard)
    provider_src = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    orch_src = (ROOT / "orchestrators/runway_browser_orchestrator.py").read_text(encoding="utf-8")
    _pass("wait_uses_classifier", "is_real_runway_output_url" in orch_src)
    _pass("artifact_uses_assert_real", "assert_real_runway_output_source" in (
        ROOT / "providers/runway_artifact_utils.py"
    ).read_text(encoding="utf-8"))
    _pass(
        "generate_click_still_verifies_prompt",
        "_verify_prompt_injection" in provider_src
        and "prepare_clip_for_generate" in orch_src,
    )

    print("[OK] validate_12j_e1_runway_real_output_detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
