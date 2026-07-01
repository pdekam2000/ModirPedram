"""Validate Kling starter frame generator P3 + handoff to Frame dry-run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_live_dry_run import run_kling_frame_live_dry_run_p2  # noqa: E402
from content_brain.execution.kling_starter_frame_generator import (  # noqa: E402
    STARTER_FRAME_GENERATOR_VERSION,
    generate_kling_starter_frame,
    is_valid_image_file,
    prompt_matches_topic,
    starter_frame_path,
    validate_starter_frame_for_upload,
)

DEFAULT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpsers. "
    'The woman whispers: "Stay with me... we\'re almost safe." '
    "Cinematic emotional sci-fi. Native audio."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_generator_module() -> None:
    src = (ROOT / "content_brain" / "execution" / "kling_starter_frame_generator.py").read_text(encoding="utf-8")
    _pass("generator_version", STARTER_FRAME_GENERATOR_VERSION.endswith("_p3_v1"))
    _pass("no_credits_flag", "credits_spent: bool = False" in src)
    _pass("no_generate_flag", "runway_generate_clicked: bool = False" in src)
    _pass("frame_001_path", 'STARTER_FRAME_FILENAME = "frame_001.png"' in src)


def test_generate_starter_frame(*, topic: str) -> dict:
    result = generate_kling_starter_frame(
        topic=topic,
        mood="cinematic emotional sci-fi",
        environment="neon cyberpunk city during heavy rain",
        characters=["young woman", "wounded robot dog"],
    )
    summary_path = ROOT / "project_brain" / "kling_starter_frame_p3_summary.json"
    summary_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

    frame = Path(result.starter_frame_path)
    _pass("starter_ok", result.ok, str(result.errors))
    _pass("frame_exists", frame.is_file(), result.starter_frame_path)
    _pass("frame_is_image", is_valid_image_file(frame))
    _pass("prompt_matches_topic", result.prompt_matches_topic)
    _pass("ready_for_upload", result.ready_for_first_frame_upload)
    _pass("no_credits", result.credits_spent is False)
    _pass("no_generate", result.runway_generate_clicked is False)
    _pass("path_has_starter_frame", "/starter_frame/frame_001.png" in result.starter_frame_path.replace("\\", "/"))
    return result.to_dict()


def test_validate_helper(*, frame_path: str, topic: str, prompt: str) -> None:
    ok, checks, errors = validate_starter_frame_for_upload(
        frame_path=frame_path,
        topic=topic,
        starter_image_prompt=prompt,
    )
    _pass("validate_helper_ok", ok, str(errors))
    _pass("check_frame_exists", checks.get("frame_exists") is True)
    _pass("check_frame_is_image", checks.get("frame_is_image") is True)
    _pass("check_prompt_topic", checks.get("prompt_matches_topic") is True)
    _pass("check_upload_ready", checks.get("ready_for_first_frame_upload") is True)


def test_handoff_to_frame_dry_run(*, frame_path: str, topic: str, prompt: str) -> None:
    dry = run_kling_frame_live_dry_run_p2(
        dry_run=True,
        connect_browser=False,
        starter_frame_path=frame_path,
        starter_image_prompt=prompt,
        topic=topic,
    )
    _pass("dry_run_handoff_ok", dry.ok)
    _pass("dry_run_starter_ready", dry.starter_frame_ready is True)
    path_text = dry.starter_frame_path.replace("\\", "/")
    _pass("dry_run_starter_path", path_text.endswith("starter_frame/frame_001.png"))


def test_prompt_topic_matcher() -> None:
    prompt = "Cinematic hero starter frame with young woman and wounded robot dog in neon city rain."
    _pass("topic_matcher", prompt_matches_topic(prompt=prompt, topic=DEFAULT_TOPIC))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate starter frame generator P3")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    args = parser.parse_args()

    print("validate_starter_frame_generator_p3")
    test_generator_module()
    test_prompt_topic_matcher()
    payload = test_generate_starter_frame(topic=args.topic)
    test_validate_helper(
        frame_path=payload["starter_frame_path"],
        topic=payload["topic"],
        prompt=payload["starter_image_prompt"],
    )
    test_handoff_to_frame_dry_run(
        frame_path=payload["starter_frame_path"],
        topic=payload["topic"],
        prompt=payload["starter_image_prompt"],
    )
    print("All starter frame generator P3 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
