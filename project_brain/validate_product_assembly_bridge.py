"""Validation — Product Studio assembly bridge."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.product_assembly_bridge import (  # noqa: E402
    ASSEMBLY_STATUS_COMPLETED,
    ASSEMBLY_STATUS_FAILED,
    FINAL_PUBLISH_READY_NAME,
    discover_product_studio_clips,
    run_product_assembly_bridge,
)
from content_brain.publish.youtube_metadata_generator import load_youtube_metadata  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _write_clip(path: Path, *, tag: bytes = b"clip") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tag * 1_100_000)


def _fake_stitch_clips(_self, clip_paths, output_path: str) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        for clip in clip_paths:
            handle.write(Path(clip).read_bytes())
    return str(output)


def _run_assembly_case(clip_count: int, test_name: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "pwmap_test_assembly"
        run_dir.mkdir(parents=True)
        for index in range(1, clip_count + 1):
            _write_clip(run_dir / f"clip_{index}.mp4", tag=f"c{index}".encode())
        with patch("content_brain.execution.product_assembly_bridge.FFmpegStitcher.stitch_clips", _fake_stitch_clips):
            result = run_product_assembly_bridge(
            project_root=ROOT,
            run_dir=run_dir,
            run_id="pwmap_test_assembly",
            topic="Assembly bridge validation topic",
            expected_clip_count=clip_count,
            preflight={"authoritative_topic": "Assembly bridge validation topic", "upload_platforms": ["youtube_shorts"]},
            invoke_youtube_metadata=True,
            )
        publish_dir = run_dir / "publish"
        _record(
            f"{test_name}_manifest_written",
            (publish_dir / "assembly_manifest.json").is_file() and (publish_dir / "publish_metadata.json").is_file(),
            str(publish_dir),
        )
        _record(
            f"{test_name}_publish_folder_created",
            publish_dir.is_dir(),
            str(publish_dir),
        )
        final_video = publish_dir / FINAL_PUBLISH_READY_NAME
        _record(
            f"{test_name}_final_publish_ready_created",
            final_video.is_file() and final_video.stat().st_size > 0,
            str(final_video),
        )
        _record(
            f"{test_name}_assembly_completed",
            result.get("assembly_status") == ASSEMBLY_STATUS_COMPLETED and result.get("ok") is True,
            str(result.get("assembly_status")),
        )
        manifest = json.loads((publish_dir / "assembly_manifest.json").read_text(encoding="utf-8"))
        _record(
            f"{test_name}_clips_sorted",
            manifest.get("input_clips") == sorted(manifest.get("input_clips") or [], key=lambda p: int(Path(p).stem.split("_")[-1])),
            str(len(manifest.get("input_clips") or [])),
        )
        return result


def main() -> int:
    print("validate_product_assembly_bridge")
    print("=" * 60)

    _run_assembly_case(2, "two_clip")
    _run_assembly_case(3, "three_clip")
    _run_assembly_case(4, "four_clip")

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "pwmap_fail_assembly"
        run_dir.mkdir(parents=True)
        _write_clip(run_dir / "clip_1.mp4")
        _write_clip(run_dir / "clip_2.mp4")
        discovery = discover_product_studio_clips(run_dir, expected_clip_count=4)
        _record(
            "missing_clip_detected",
            discovery.get("ok") is False and 3 in (discovery.get("missing_clip_indices") or []),
            str(discovery.get("missing_clip_indices")),
        )
        failed = run_product_assembly_bridge(
            project_root=ROOT,
            run_dir=run_dir,
            run_id="pwmap_fail_assembly",
            topic="Missing clip test",
            expected_clip_count=4,
            invoke_youtube_metadata=False,
        )
        _record(
            "assembly_failure_status",
            failed.get("assembly_status") == ASSEMBLY_STATUS_FAILED,
            str(failed.get("assembly_status")),
        )
        _record(
            "assembly_failure_missing_index",
            failed.get("missing_clip_index") == 3,
            str(failed.get("missing_clip_index")),
        )
        _record(
            "assembly_failure_recovery_flag",
            failed.get("recovery_possible") is True,
            str(failed.get("recovery_possible")),
        )
        _record(
            "assembly_failure_no_final_video",
            not (run_dir / "publish" / FINAL_PUBLISH_READY_NAME).is_file(),
            "no silent continue",
        )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "pwmap_yt1_bridge"
        run_dir.mkdir(parents=True)
        _write_clip(run_dir / "clip_1.mp4")
        _write_clip(run_dir / "clip_2.mp4")
        with patch("content_brain.execution.product_assembly_bridge.FFmpegStitcher.stitch_clips", _fake_stitch_clips):
            result = run_product_assembly_bridge(
                project_root=ROOT,
                run_dir=run_dir,
                run_id="pwmap_yt1_bridge",
                topic="YT metadata bridge topic",
                expected_clip_count=2,
                preflight={"authoritative_topic": "YT metadata bridge topic"},
                invoke_youtube_metadata=True,
            )
        publish_dir = Path(str(result.get("publish_package_path") or ""))
        yt_meta = load_youtube_metadata(publish_dir) if publish_dir.is_dir() else None
        _record(
            "yt1_metadata_consumes_publish_output",
            yt_meta is not None and bool(yt_meta.get("title")),
            str(yt_meta.get("title") if yt_meta else ""),
        )

    adapter_src = (ROOT / "content_brain" / "execution" / "pwmap_runway_agent_adapter.py").read_text(encoding="utf-8")
    planner_src = (ROOT / "content_brain" / "execution" / "product_multiclip_execution_plan.py").read_text(encoding="utf-8")
    _record(
        "no_provider_logic_modified",
        "product_assembly_bridge" not in adapter_src and "FINAL_PUBLISH_READY" not in planner_src,
        "pwmap adapter + planner untouched",
    )

    failed_tests = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"TOTAL: {len(results)}  PASS: {len(results) - len(failed_tests)}  FAIL: {len(failed_tests)}")
    if failed_tests:
        print("FAILED:", ", ".join(failed_tests))
        return FAIL
    print("ALL PASS")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
