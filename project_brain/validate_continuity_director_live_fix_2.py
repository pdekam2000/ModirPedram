"""Validate CONTINUITY-DIRECTOR-LIVE-FIX-2 — topic guard + MP4 recovery."""

from __future__ import annotations

import json
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
    ClipExecutionResult,
    ContinuityDirectorAgent,
    ContinuityDirectorClipPlan,
    ContinuityDirectorPlan,
    build_frame_live_recover_hook,
    ensure_kling_frame_metadata_for_plan,
    plan_clip_chain,
    resolve_real_clip_mp4,
    validate_real_mp4,
)
from content_brain.execution.kling_multishot_live_engine import MIN_REAL_MP4_BYTES  # noqa: E402
from content_brain.execution.kling_starter_frame_generator import (  # noqa: E402
    STARTER_FRAME_PROMPT_JSON,
    prompt_matches_topic,
    starter_frame_dir,
)
from content_brain.execution.kling_last_frame_extractor import continuity_frame_path  # noqa: E402

STORY_IDEA = (
    "A mysterious young woman in a black futuristic coat on a rain-soaked cyberpunk rooftop "
    "follows a glowing blue signal while drones search the sky."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))


def _make_test_mp4(path: Path, *, seconds: float = 60.0) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required")
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
        raise RuntimeError(proc.stderr or proc.stdout or "ffmpeg failed")
    if path.stat().st_size < MIN_REAL_MP4_BYTES:
        raise RuntimeError(f"test mp4 too small: {path.stat().st_size}")


def test_smoke_starter_prompt_matches_topic() -> None:
    plan = plan_clip_chain(
        run_id="cd_fix2_topic",
        topic=STORY_IDEA,
        clip_count=2,
        planned_duration_seconds=30,
        mood="cinematic emotional dark neon",
        environment="rain-soaked cyberpunk rooftop at night",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        meta = ensure_kling_frame_metadata_for_plan(plan, root)
        starter = str(meta.get("starter_image_prompt") or "")
        _pass("starter_prompt_nonempty", bool(starter))
        _pass("starter_matches_topic", prompt_matches_topic(prompt=starter, topic=STORY_IDEA))
        _pass("topic_guard_passed_flag", meta.get("topic_guard_passed") is True)
        prompt_path = starter_frame_dir(root / "outputs" / "kling_frame_to_video" / plan.run_id) / STARTER_FRAME_PROMPT_JSON
        _pass("metadata_written", prompt_path.is_file())


def test_topic_guard_does_not_fail_smoke_payload() -> None:
    from project_brain.run_continuity_director_v1_live_smoke import STORY_IDEA as smoke_story

    plan = plan_clip_chain(run_id="cd_fix2_smoke", topic=smoke_story, clip_count=2)
    with tempfile.TemporaryDirectory() as tmp:
        meta = ensure_kling_frame_metadata_for_plan(plan, Path(tmp))
        starter = str(meta.get("starter_image_prompt") or "")
        _pass("smoke_payload_guard", prompt_matches_topic(prompt=starter, topic=smoke_story))


def test_existing_recovered_mp4_reused() -> None:
    if not _ffmpeg_available():
        print("[SKIP] existing_recovered_mp4_reused — ffmpeg unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "cd_fix2_reuse"
        from content_brain.execution.kling_starter_frame_generator import kling_frame_clip_dir, kling_frame_run_dir

        live_clip = kling_frame_clip_dir(kling_frame_run_dir(root, run_id), 1)
        live_clip.mkdir(parents=True, exist_ok=True)
        mp4 = live_clip / "clip_1.mp4"
        _make_test_mp4(mp4)
        agent_clip = root / "agent" / "c1"
        agent_clip.mkdir(parents=True, exist_ok=True)
        exec_result = ClipExecutionResult(clip_index=1, ok=True, generate_clicked=True)
        path, audit = resolve_real_clip_mp4(
            project_root=root,
            run_id=run_id,
            clip_index=1,
            agent_clip_dir=agent_clip,
            exec_result=exec_result,
            recover_mp4=None,
        )
        _pass("reused_existing_clip1", bool(path))
        _pass("no_recovery_needed", "recover_kling_frame_output" not in (audit.get("attempted_methods") or []))
        _pass("audit_final_path", bool(audit.get("final_path")))


def test_recovery_extractor_called_when_missing() -> None:
    called = {"recover": False}

    def _fake_recover(**kwargs: object) -> str:
        called["recover"] = True
        return ""

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        exec_result = ClipExecutionResult(clip_index=1, ok=True, generate_clicked=True)
        exec_result.live_payload = {"generation_completed": True, "status": "download_failed"}
        _, audit = resolve_real_clip_mp4(
            project_root=root,
            run_id="cd_fix2_call",
            clip_index=1,
            agent_clip_dir=root / "c1",
            exec_result=exec_result,
            recover_mp4=_fake_recover,
        )
        _pass("recover_called", called["recover"])
        _pass("audit_lists_recovery", "recover_kling_frame_output" in (audit.get("attempted_methods") or []))


def test_fake_mp4_still_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "fake.mp4"
        fake.write_bytes(b"not-an-mp4" * 2000)
        verify = validate_real_mp4(fake)
        _pass("fake_rejected", not verify.get("is_real_mp4"))


def test_last_frame_extracted_from_valid_mp4() -> None:
    if not _ffmpeg_available():
        print("[SKIP] last_frame_extracted — ffmpeg unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        clip_dir = run_dir / "clips" / "c1"
        clip_dir.mkdir(parents=True, exist_ok=True)
        mp4 = clip_dir / "video.mp4"
        _make_test_mp4(mp4, seconds=60.0)
        agent = ContinuityDirectorAgent(project_root=root)
        frame = agent.prepare_next_clip_first_frame(
            run_dir=run_dir,
            from_clip_index=1,
            video_path=mp4,
        )
        _pass("frame_extracted", Path(frame).is_file())
        expected = continuity_frame_path(run_dir, 1)
        _pass("frame_at_continuity_path", Path(frame) == expected)


def test_clip2_can_start_after_valid_png() -> None:
    if not _ffmpeg_available():
        print("[SKIP] clip2_start — ffmpeg unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        plan = plan_clip_chain(run_id="cd_fix2_chain", topic=STORY_IDEA, clip_count=2)
        ensure_kling_frame_metadata_for_plan(plan, root)
        mp4 = run_dir / "clips" / "c1" / "video.mp4"
        mp4.parent.mkdir(parents=True, exist_ok=True)
        _make_test_mp4(mp4, seconds=60.0)

        generate_calls: list[int] = []

        def _generate(**kwargs: object) -> ClipExecutionResult:
            clip = kwargs["clip"]
            generate_calls.append(int(clip.clip_index))
            if clip.clip_index == 1:
                return ClipExecutionResult(
                    clip_index=1,
                    ok=True,
                    generate_clicked=True,
                    mp4_path=str(mp4),
                )
            first = kwargs.get("first_frame_path")
            _pass("clip2_has_png", bool(first) and Path(str(first)).is_file())
            return ClipExecutionResult(clip_index=2, ok=True, generate_clicked=True, mp4_path=str(mp4))

        agent = ContinuityDirectorAgent(project_root=root)
        result = agent.run_chain(
            plan=plan,
            run_dir=run_dir,
            generate_clip=_generate,
            recover_mp4=None,
            dry_run=False,
        )
        _pass("chain_complete", result.ok)
        _pass("two_clips_started", generate_calls == [1, 2])


def test_recover_hook_no_generate() -> None:
    src = (ROOT / "agents/continuity_director_agent.py").read_text(encoding="utf-8")
    block = src.split("def build_frame_live_recover_hook", 1)[1].split("def ", 1)[0]
    _pass("recover_hook_no_generate", "generate.locator.click" not in block)


def main() -> None:
    test_smoke_starter_prompt_matches_topic()
    test_topic_guard_does_not_fail_smoke_payload()
    test_existing_recovered_mp4_reused()
    test_recovery_extractor_called_when_missing()
    test_fake_mp4_still_rejected()
    test_last_frame_extracted_from_valid_mp4()
    test_clip2_can_start_after_valid_png()
    test_recover_hook_no_generate()
    print("validate_continuity_director_live_fix_2: all checks passed")


if __name__ == "__main__":
    main()
