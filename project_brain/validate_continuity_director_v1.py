"""Validate CONTINUITY-DIRECTOR-V1 — last-frame PNG chain, no Use Frame."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.continuity_director_agent import (  # noqa: E402
    AGENT_VERSION,
    CONTINUITY_METHOD_LAST_FRAME,
    STOP_MP4_MISSING,
    ClipExecutionResult,
    ContinuityDirectorAgent,
    ContinuityDirectorClipPlan,
    plan_clip_chain,
    quarantine_invalid_mp4,
    validate_real_mp4,
)
from content_brain.execution.kling_frame_to_video_models import FIRST_FRAME_PRIOR_CLIP  # noqa: E402
from content_brain.execution.kling_last_frame_extractor import continuity_frame_path  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))


def _make_test_mp4(path: Path, *, seconds: float = 60.0) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required for test MP4 synthesis")
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=720x1280:d={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-c:v",
            "libx264",
            "-b:v",
            "900k",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0 or not path.is_file():
        raise RuntimeError(proc.stderr or proc.stdout or "ffmpeg test mp4 failed")
    if path.stat().st_size < 1_048_576:
        raise RuntimeError(f"test mp4 too small for verify_recovered_mp4: {path.stat().st_size}")


def test_clip_plan_created() -> None:
    plan = plan_clip_chain(
        run_id="cd_plan_test",
        topic="neon city escape with robot dog",
        clip_count=2,
        planned_duration_seconds=30,
        mood="cinematic emotional",
    )
    _pass("plan_version", plan.version == AGENT_VERSION)
    _pass("two_clips", plan.clip_count == 2, f"count={plan.clip_count}")
    _pass("continuity_method", plan.continuity_method == CONTINUITY_METHOD_LAST_FRAME)
    _pass("clip1_prompt_only", plan.clips[0].first_frame_source == "prompt_only")
    _pass("clip2_prior_frame_source", plan.clips[1].first_frame_source == FIRST_FRAME_PRIOR_CLIP)
    _pass("character_continuity_present", bool(plan.clips[0].character_continuity or plan.clips[1].character_continuity))


def test_fake_mp4_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "fake.mp4"
        fake.write_bytes(b"not-an-mp4")
        verify = validate_real_mp4(fake)
        _pass("fake_not_real", verify.get("is_real_mp4") is False)
        clip_dir = Path(tmp) / "c1"
        clip_dir.mkdir()
        quarantined = quarantine_invalid_mp4(fake, clip_dir)
        _pass("fake_quarantined", bool(quarantined))
        _pass("fake_removed", not fake.is_file())


def test_no_use_frame_in_agent() -> None:
    src = (ROOT / "agents/continuity_director_agent.py").read_text(encoding="utf-8")
    _pass("no_use_frame_symbol", "use_frame" not in src.lower())
    _pass("last_frame_method", CONTINUITY_METHOD_LAST_FRAME in src)
    core = src.split("def build_frame_live_generate_hook", 1)[0]
    _pass("core_no_continuity_frame_in_ui", "continuity_frame_in_ui" not in core)
    hook_block = src.split("def build_frame_live_generate_hook", 1)[1].split("\ndef ", 1)[0]
    _pass("live_hook_forces_file_upload", "continuity_frame_in_ui=False" in hook_block)


def test_chain_stops_without_mp4() -> None:
    agent = ContinuityDirectorAgent(ROOT)
    plan = plan_clip_chain(
        run_id="cd_stop_test",
        topic="stop without mp4",
        clip_count=2,
        planned_duration_seconds=30,
    )

    def _gen_no_mp4(**kwargs: object) -> ClipExecutionResult:
        clip = kwargs["clip"]
        return ClipExecutionResult(
            clip_index=clip.clip_index,
            ok=True,
            generate_clicked=True,
            mp4_path="",
        )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "cd_stop"
        result = agent.run_chain(
            plan=plan,
            run_dir=run_dir,
            generate_clip=_gen_no_mp4,
            dry_run=True,
        )
    _pass("stopped_not_complete", result.status == "stopped")
    _pass("stop_mp4_missing", result.stop_reason == STOP_MP4_MISSING)
    _pass("one_clip_attempted", len(result.clip_results) == 1)
    _pass("clip2_not_started", result.clips_completed < 2)


def test_two_clip_dry_run_with_last_frame_handoff() -> None:
    if not _ffmpeg_available():
        print("[SKIP] two_clip_dry_run — ffmpeg not available")
        return

    agent = ContinuityDirectorAgent(ROOT)
    plan = plan_clip_chain(
        run_id="cd_dry_2clip",
        topic="two clip dry run continuity director",
        clip_count=2,
        planned_duration_seconds=30,
    )
    calls: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mp4_store = tmp_path / "mp4s"
        mp4_store.mkdir()

        def _gen(**kwargs: object) -> ClipExecutionResult:
            clip: ContinuityDirectorClipPlan = kwargs["clip"]  # type: ignore[assignment]
            clip_dir: Path = kwargs["clip_dir"]  # type: ignore[assignment]
            first_frame_path = kwargs.get("first_frame_path")
            calls.append(
                {
                    "clip_index": clip.clip_index,
                    "first_frame_path": first_frame_path,
                }
            )
            mp4 = mp4_store / f"c{clip.clip_index}.mp4"
            _make_test_mp4(mp4)
            dest = clip_dir / "video.mp4"
            shutil.copy2(mp4, dest)
            return ClipExecutionResult(
                clip_index=clip.clip_index,
                ok=True,
                generate_clicked=True,
                mp4_path=str(dest.resolve()),
            )

        run_dir = tmp_path / "cd_dry_2clip"
        result = agent.run_chain(
            plan=plan,
            run_dir=run_dir,
            generate_clip=_gen,
            dry_run=True,
        )

        frame_c1 = continuity_frame_path(run_dir, 1)
        _pass("chain_complete", result.status == "complete", result.status)
        _pass("two_generate_clicks", result.generate_clicks == 2, str(result.generate_clicks))
        _pass("two_clips_completed", result.clips_completed == 2)
        _pass("last_frame_png_exists", frame_c1.is_file(), str(frame_c1))
        _pass("clip2_received_png", calls[1].get("first_frame_path") == str(frame_c1.resolve()))
        _pass("clip1_no_input_frame", not calls[0].get("first_frame_path"))
        _pass("max_clicks_not_exceeded", result.generate_clicks <= plan.clip_count)


def test_mp4_required_before_next_clip() -> None:
    agent = ContinuityDirectorAgent(ROOT)
    plan = plan_clip_chain(
        run_id="cd_gate_test",
        topic="mp4 gate",
        clip_count=2,
        planned_duration_seconds=30,
    )
    call_count = 0

    def _gen_once(**kwargs: object) -> ClipExecutionResult:
        nonlocal call_count
        call_count += 1
        clip: ContinuityDirectorClipPlan = kwargs["clip"]  # type: ignore[assignment]
        return ClipExecutionResult(
            clip_index=clip.clip_index,
            ok=True,
            generate_clicked=True,
            mp4_path="",
        )

    with tempfile.TemporaryDirectory() as tmp:
        result = agent.run_chain(
            plan=plan,
            run_dir=Path(tmp) / "gate",
            generate_clip=_gen_once,
            dry_run=True,
        )
    _pass("only_one_generate", call_count == 1)
    _pass("blocked_before_clip2", result.stopped_at_clip == 1)


def test_last_frame_extracted_from_real_mp4() -> None:
    if not _ffmpeg_available():
        print("[SKIP] last_frame_extract — ffmpeg not available")
        return

    agent = ContinuityDirectorAgent(ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "extract"
        mp4 = run_dir / "clips" / "c1" / "video.mp4"
        _make_test_mp4(mp4)
        verify = validate_real_mp4(mp4)
        _pass("synthetic_mp4_real", verify.get("is_real_mp4") is True, str(verify.get("size_bytes")))
        frame = agent.prepare_next_clip_first_frame(
            run_dir=run_dir,
            from_clip_index=1,
            video_path=mp4,
        )
        _pass("frame_path_png", frame.endswith(".png"), frame)
        _pass("frame_exists", Path(frame).is_file())


def main() -> None:
    print("Continuity Director V1 validation")
    print(f"agent: {AGENT_VERSION}")
    test_clip_plan_created()
    test_fake_mp4_rejected()
    test_no_use_frame_in_agent()
    test_mp4_required_before_next_clip()
    test_chain_stops_without_mp4()
    test_last_frame_extracted_from_real_mp4()
    test_two_clip_dry_run_with_last_frame_handoff()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
