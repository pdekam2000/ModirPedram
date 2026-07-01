"""Validate duration preservation — narration merge must not truncate assembled video."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_merge_engine import merge_narration_into_video
from content_brain.audio.audio_mix_engine import mix_environment_and_sfx
from content_brain.platform.media_probe import duration_preserved, probe_duration_seconds


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_merge_engine_no_shortest_flag() -> None:
    source = (ROOT / "content_brain/audio/audio_merge_engine.py").read_text(encoding="utf-8")
    _pass("merge_engine_no_shortest", "-shortest" not in source)
    _pass("merge_engine_video_authoritative", "apad=whole_dur" in source)
    _pass("merge_engine_duration_check", "duration_preserved" in source or "Duration preservation failed" in source)


def test_mix_engine_no_shortest_flag() -> None:
    source = (ROOT / "content_brain/audio/audio_mix_engine.py").read_text(encoding="utf-8")
    _pass("mix_engine_no_shortest", "-shortest" not in source)
    _pass("mix_engine_uses_video_t", '"-t"' in source or "'-t'" in source)


def test_duration_preserved_helper() -> None:
    _pass("duration_within_tolerance", duration_preserved(assembled_seconds=40.17, deliverable_seconds=40.0))
    _pass("duration_truncation_detected", not duration_preserved(assembled_seconds=40.17, deliverable_seconds=18.46))


def test_merge_calls_probe_and_t() -> None:
    merge_source = inspect.getsource(merge_narration_into_video)
    _pass("merge_probes_video", "probe_duration_seconds" in merge_source)
    _pass("merge_uses_t_flag", '"-t"' in merge_source or "'-t'" in merge_source)


def test_assembly_manifest_records_duration() -> None:
    source = (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8")
    _pass("assembly_duration_probe", "assembled_duration = probe_duration_seconds" in source)


def main() -> None:
    test_merge_engine_no_shortest_flag()
    test_mix_engine_no_shortest_flag()
    test_duration_preserved_helper()
    test_merge_calls_probe_and_t()
    test_assembly_manifest_records_duration()
    print("validate_duration_preservation: all checks passed")


if __name__ == "__main__":
    main()
