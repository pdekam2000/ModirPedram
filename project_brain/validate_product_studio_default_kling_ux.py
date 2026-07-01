"""Validate Product Studio default Kling UX — defaults, topic persistence, auto approval, starter frame."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_TO_VIDEO_MODE  # noqa: E402
from content_brain.execution.kling_product_run import (  # noqa: E402
    PRODUCT_STUDIO_APPROVED_BY,
    run_kling_product_studio_generate,
)
from content_brain.execution.kling_native_audio_models import KLING_AUDIO_STRATEGY, KLING_PROVIDER_ID  # noqa: E402
from content_brain.product_settings.last_topic_store import ProductLastTopicStore  # noqa: E402
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

TOPIC = "A boy finds a dragon egg in a glowing forest"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _kling_payload(**overrides: object) -> dict:
    base = {
        "topic_mode": "custom",
        "custom_topic": TOPIC,
        "duration_seconds": 30,
        "platform": "youtube_shorts",
        "provider": KLING_PROVIDER_ID,
        "audio_strategy": KLING_AUDIO_STRATEGY,
    }
    base.update(overrides)
    return base


def test_kling_default_provider_preflight() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    _pass("provider", pre.get("provider") == KLING_PROVIDER_ID)
    _pass("frame_mode", pre.get("kling_shot_mode") == KLING_FRAME_TO_VIDEO_MODE)


def test_kling_default_audio_strategy() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    _pass("audio_strategy", pre.get("audio_strategy") == KLING_AUDIO_STRATEGY)


def test_last_topic_persists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = ProductLastTopicStore(tmp)
        saved = store.save(topic=TOPIC, topic_mode="custom")
        loaded = store.load()
        _pass("topic_saved", saved.get("topic") == TOPIC)
        _pass("topic_reloaded", loaded.get("topic") == TOPIC)


def test_last_topic_service_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        service = ProductStudioService(tmp)
        service.save_last_topic(topic=TOPIC, topic_mode="custom")
        loaded = service.get_last_topic()
        _pass("service_topic", loaded.get("topic") == TOPIC)


def test_generate_without_manual_approval_fields() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    executed = {"called": False, "first_frame": ""}

    def _fake_execute(**kwargs: object) -> tuple:
        executed["called"] = True
        executed["first_frame"] = str(kwargs.get("first_frame_path") or "")
        return (
            [{"clip_index": 1, "generate_clicked": True, "credits_spent": True, "ok": True}],
            {"status": "completed"},
            {"status": "completed", "final_video_path": "/tmp/video.mp4"},
            "/tmp/video.mp4",
            {},
            {"continuity_status": "complete"},
        )

    with patch("content_brain.execution.kling_product_run._execute_kling_clips", side_effect=_fake_execute):
        result = run_kling_product_studio_generate(
            project_root=ROOT,
            payload=ProductStudioService._apply_product_studio_kling_defaults(_kling_payload()),
            preflight=pre,
        )
    _pass("auto_execute", executed["called"] is True)
    _pass("clip1_no_starter_frame", not executed["first_frame"], executed["first_frame"] or "(empty)")


def test_service_applies_auto_approval_defaults() -> None:
    merged = ProductStudioService._apply_product_studio_kling_defaults({})
    _pass("approve_generate", merged.get("approve_generate") is True)
    _pass("approved_by", merged.get("approved_by") == PRODUCT_STUDIO_APPROVED_BY)
    _pass("confirm_credit_spend", merged.get("confirm_credit_spend") is True)


def test_generate_service_auto_approval() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    with patch("content_brain.execution.kling_product_run._execute_kling_clips") as mock_exec:
        mock_exec.return_value = (
            [{"clip_index": 1, "generate_clicked": True, "ok": True}],
            {"status": "completed"},
            {"status": "completed"},
            "/tmp/video.mp4",
            {},
            {"continuity_status": "complete"},
        )
        result = service.create_video_generate(_kling_payload(), runway_service=object())
    _pass("service_generate_ok", result.get("approved_by") == PRODUCT_STUDIO_APPROVED_BY)
    _pass("service_generate_clicked", mock_exec.called is True)


def test_clip1_prompt_only_no_auto_starter() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    _pass("clip1_mode", pre.get("clip1_generation_mode") == "text_to_video_prompt_only")
    _pass("clip1_no_starter", pre.get("clip1_starter_frame_required") is False)
    plan = pre.get("kling_frame_to_video_plan") or {}
    clips = list(plan.get("clips") or [])
    if clips:
        _pass("clip1_source", clips[0].get("first_frame_source") == "prompt_only")


def test_generate_reaches_live_runtime() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    with patch("content_brain.execution.kling_product_run._execute_kling_clips") as mock_exec:
        mock_exec.return_value = (
            [{"clip_index": 1, "generate_clicked": True, "ok": False, "status": "failed"}],
            {"status": "failed"},
            {"status": "failed"},
            "",
            {},
            {"continuity_status": "stopped"},
        )
        result = run_kling_product_studio_generate(
            project_root=ROOT,
            payload=ProductStudioService._apply_product_studio_kling_defaults(_kling_payload()),
            preflight=pre,
        )
    _pass("runtime_called", mock_exec.called is True)
    _pass("not_starter_blocked", result.get("precondition") != "starter_frame_required")


def test_runway_optional_path() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "Ancient Rome vault secrets",
            "duration_seconds": 30,
            "platform": "youtube",
            "provider": "runway",
            "audio_strategy": "narrator",
        }
    )
    _pass("runway_provider", str(pre.get("provider") or "").lower() == "runway")
    _pass("runway_not_kling", pre.get("provider") != KLING_PROVIDER_ID)


def test_ui_constants_default_kling() -> None:
    constants_path = ROOT / "ui" / "web" / "src" / "product" / "constants.ts"
    text = constants_path.read_text(encoding="utf-8")
    provider_block = text.split("PROVIDER_OPTIONS")[1].split("] as const")[0]
    _pass("provider_list_kling_first", provider_block.index("kling_3_0_pro_native_audio") < provider_block.index('"auto"'))


def main() -> int:
    print("validate_product_studio_default_kling_ux")
    test_kling_default_provider_preflight()
    test_kling_default_audio_strategy()
    test_last_topic_persists()
    test_last_topic_service_roundtrip()
    test_generate_without_manual_approval_fields()
    test_service_applies_auto_approval_defaults()
    test_generate_service_auto_approval()
    test_clip1_prompt_only_no_auto_starter()
    test_generate_reaches_live_runtime()
    test_runway_optional_path()
    test_ui_constants_default_kling()
    print("All Product Studio default Kling UX checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
