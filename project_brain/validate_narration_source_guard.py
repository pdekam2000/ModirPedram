"""Validate narration source guard — story-only scripts, no runtime/prompt leakage."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.narration_script_builder import build_narration_script  # noqa: E402
from content_brain.audio.narration_source_guard import (  # noqa: E402
    NarrationSourceGuardError,
    find_forbidden_narration_terms,
    validate_narration_source,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    bad_script = (
        "In the next few seconds, watch closely. Today: Cute orange cartoon cat explorer. "
        "a knowledgeable presenter in a single continuous environment with strong depth and readable vertical framing. "
        "Scene 1 explores settings and runtime pipeline metadata validation json config."
    )
    hits = find_forbidden_narration_terms(bad_script)
    _pass("bad_script_detected", len(hits) >= 3, ",".join(hits[:5]))

    try:
        validate_narration_source(bad_script)
        _pass("bad_script_raises", False, "expected guard failure")
    except NarrationSourceGuardError:
        _pass("bad_script_raises", True)

    good_script = (
        "Meet our cute orange explorer cat. "
        "The cat discovers a glowing forest trail. "
        "It crosses a mossy bridge with confident steps. "
        "A hidden treasure sparkles at the waterfall. "
        "Follow for more adventures."
    )
    validate_narration_source(good_script)
    _pass("good_script_passes", True)

    result = build_narration_script(
        project_root=ROOT,
        topic="Cute orange cartoon cat explorer",
        platform="youtube_shorts",
        clip_count=3,
        run_id="cb_e2e_20260611_225308_dc20bc1f",
    )
    _pass("cartoon_run_script_builds", bool(result.script))
    _pass("story_source", result.source.startswith("story_brief"), result.source)
    validate_narration_source(result.script, segments=result.segments)
    _pass("cartoon_script_guard_clean", "knowledge" not in result.script.lower())
    _pass("no_platform_hook", "in the next few seconds" not in result.script.lower())

    print("\nAll narration source guard validations passed.")


if __name__ == "__main__":
    main()
