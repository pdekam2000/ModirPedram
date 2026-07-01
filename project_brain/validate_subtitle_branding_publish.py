"""Validation — Product Studio subtitle, branding, and publish runtime."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult  # noqa: E402
from content_brain.execution.product_assembly_bridge import FINAL_PUBLISH_READY_NAME  # noqa: E402
from content_brain.execution.product_subtitle_branding_publish import (  # noqa: E402
    FINAL_BRANDED_PUBLISH_READY_NAME,
    PUBLISH_PACKAGE_NAME,
    SUBTITLE_MODE_BURN_IN,
    SUBTITLE_MODE_GENERATED,
    SUBTITLE_MODE_NONE,
    load_product_publish_package_state,
    run_product_subtitle_branding_publish,
)
from content_brain.execution.pwmap_finalization import build_pwmap_results_payload  # noqa: E402
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _write_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * 1_100_000)


def _completed_copy(input_video_path, output_path, **_kwargs):
    src = Path(input_video_path)
    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(dst.resolve()),
        input_path=str(src.resolve()),
        ffmpeg_executed=True,
        ffmpeg_available=True,
    )


def _failed_burn(*_args, **_kwargs):
    return BrandingFfmpegResult(
        status="FAILED",
        output_path="",
        input_path="",
        error="mock_subtitle_burn_failed",
    )


def _intro_card(*, output_dir, intro_text, intro_duration, ffmpeg_probe=None):
    out = Path(output_dir) / "intro.mp4"
    _write_video(out)
    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(out.resolve()),
        input_path="",
        metadata={"intro_text": intro_text, "intro_duration": intro_duration},
    )


def _outro_card(*, output_dir, outro_text, outro_duration, ffmpeg_probe=None):
    out = Path(output_dir) / "outro.mp4"
    _write_video(out)
    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(out.resolve()),
        input_path="",
        metadata={"outro_text": outro_text, "outro_duration": outro_duration},
    )


def _merge_intro_outro(*, intro_path, main_video_path, outro_path, output_path, ffmpeg_probe=None):
    src = Path(main_video_path)
    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(dst.resolve()),
        input_path=str(src.resolve()),
    )


def _setup_publish_dir(tmp: Path) -> Path:
    run_dir = tmp / "pwmap_publish_test"
    publish = run_dir / "publish"
    publish.mkdir(parents=True)
    _write_video(publish / FINAL_PUBLISH_READY_NAME)
    (publish / "youtube_metadata.json").write_text(
        json.dumps({"title": "Test", "description": "desc", "tags": [], "hashtags": []}),
        encoding="utf-8",
    )
    return run_dir


def _run_case(name: str, run_dir: Path, overrides: dict) -> dict:
    with patch("content_brain.execution.product_subtitle_branding_publish.burn_subtitles", side_effect=_completed_copy), patch(
        "content_brain.execution.product_subtitle_branding_publish.apply_logo_overlay",
        side_effect=_completed_copy,
    ), patch(
        "content_brain.execution.product_subtitle_branding_publish.apply_cta_overlay",
        side_effect=_completed_copy,
    ), patch(
        "content_brain.execution.product_subtitle_branding_publish.generate_intro_card",
        side_effect=_intro_card,
    ), patch(
        "content_brain.execution.product_subtitle_branding_publish.generate_outro_card",
        side_effect=_outro_card,
    ), patch(
        "content_brain.execution.product_subtitle_branding_publish.merge_intro_outro",
        side_effect=_merge_intro_outro,
    ):
        return run_product_subtitle_branding_publish(
            project_root=ROOT,
            run_dir=run_dir,
            run_id="pwmap_publish_test",
            topic="Subtitle branding validation topic",
            preflight={"authoritative_topic": "Subtitle branding validation topic"},
            settings_overrides=overrides,
        )


def main() -> int:
    print("validate_subtitle_branding_publish")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _setup_publish_dir(Path(tmp))
        publish = run_dir / "publish"
        source_before = (publish / FINAL_PUBLISH_READY_NAME).read_bytes()
        disabled = _run_case(
            "subtitles_disabled",
            run_dir,
            {
                "subtitle_mode": SUBTITLE_MODE_NONE,
                "logo_enabled": False,
                "cta_enabled": False,
                "intro_enabled": False,
                "outro_enabled": False,
            },
        )
        _record("subtitles_disabled_works", disabled.get("subtitle_status") == "disabled", str(disabled.get("subtitle_status")))
        _record(
            "logo_disabled_works",
            disabled.get("ok") is True and (publish / FINAL_BRANDED_PUBLISH_READY_NAME).is_file(),
            str(disabled.get("logo_status")),
        )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _setup_publish_dir(Path(tmp))
        publish = run_dir / "publish"
        enabled = _run_case(
            "subtitles_enabled",
            run_dir,
            {
                "subtitle_mode": SUBTITLE_MODE_GENERATED,
                "logo_enabled": False,
                "cta_enabled": False,
            },
        )
        _record(
            "subtitles_enabled_works",
            enabled.get("subtitle_status") == "completed" and int(enabled.get("subtitle_count") or 0) >= 1,
            str(enabled.get("subtitle_count")),
        )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _setup_publish_dir(Path(tmp))
        logo = _run_case(
            "logo_enabled",
            run_dir,
            {"subtitle_mode": SUBTITLE_MODE_NONE, "logo_enabled": True, "watermark_enabled": False, "cta_enabled": False},
        )
        _record("logo_enabled_works", "logo" in (logo.get("branding_layers") or []), str(logo.get("branding_layers")))

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _setup_publish_dir(Path(tmp))
        cta = _run_case(
            "cta_enabled",
            run_dir,
            {"subtitle_mode": SUBTITLE_MODE_NONE, "logo_enabled": False, "watermark_enabled": False, "cta_enabled": True},
        )
        _record("cta_enabled_works", "cta" in (cta.get("branding_layers") or []), str(cta.get("branding_layers")))

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _setup_publish_dir(Path(tmp))
        intro_outro = _run_case(
            "intro_outro_enabled",
            run_dir,
            {
                "subtitle_mode": SUBTITLE_MODE_NONE,
                "logo_enabled": False,
                "watermark_enabled": False,
                "cta_enabled": False,
                "intro_enabled": True,
                "intro_text": "Intro",
                "outro_enabled": True,
                "outro_text": "Outro",
            },
        )
        _record(
            "intro_outro_enabled_works",
            "intro" in (intro_outro.get("branding_layers") or []) and "outro" in (intro_outro.get("branding_layers") or []),
            str(intro_outro.get("branding_layers")),
        )
        _record(
            "final_branded_publish_ready_created",
            (run_dir / "publish" / FINAL_BRANDED_PUBLISH_READY_NAME).is_file(),
            str(intro_outro.get("final_branded_publish_video_path")),
        )
        _record(
            "publish_package_json_created",
            (run_dir / "publish" / PUBLISH_PACKAGE_NAME).is_file(),
            str((run_dir / "publish" / PUBLISH_PACKAGE_NAME)),
        )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _setup_publish_dir(Path(tmp))
        publish = run_dir / "publish"
        source_before = (publish / FINAL_PUBLISH_READY_NAME).read_bytes()
        with patch("content_brain.execution.product_subtitle_branding_publish.burn_subtitles", side_effect=_failed_burn), patch(
            "content_brain.execution.product_subtitle_branding_publish.apply_logo_overlay",
            side_effect=_completed_copy,
        ):
            failed = run_product_subtitle_branding_publish(
                project_root=ROOT,
                run_dir=run_dir,
                run_id="pwmap_branding_fail",
                topic="Branding failure topic",
                settings_overrides={"subtitle_mode": SUBTITLE_MODE_BURN_IN, "logo_enabled": False, "cta_enabled": False},
            )
        source_after = (publish / FINAL_PUBLISH_READY_NAME).read_bytes()
        _record(
            "branding_failure_preserves_source",
            source_before == source_after and failed.get("branding_status") == "branding_failed",
            str(failed.get("error")),
        )
        _record(
            "branding_failure_no_branded_output",
            not (publish / FINAL_BRANDED_PUBLISH_READY_NAME).is_file(),
            "original preserved",
        )

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _setup_publish_dir(Path(tmp))
        result = _run_case(
            "results_payload",
            run_dir,
            {"subtitle_mode": SUBTITLE_MODE_NONE, "logo_enabled": False, "cta_enabled": True},
        )
        state = load_product_publish_package_state(run_dir)
        payload = build_pwmap_results_payload(
            run_dir,
            {
                "run_id": "pwmap_publish_test",
                "status": "completed",
                "preflight_snapshot": {"authoritative_topic": "Results topic"},
                **result,
            },
        )
        _record(
            "results_payload_displays_statuses",
            bool(payload.get("subtitle_status")) and bool(payload.get("branding_status")) and bool(payload.get("cta_status")),
            f"subtitle={payload.get('subtitle_status')} branding={payload.get('branding_status')}",
        )
        service = ProductStudioService(ROOT)
        merged = service._merge_pwmap_results(payload)
        _record(
            "results_service_displays_statuses",
            merged.get("publish_ready") is True
            and bool(merged.get("final_branded_publish_video_path"))
            and bool(merged.get("subtitle_status")),
            str(merged.get("branding_status")),
        )
        _record(
            "loader_publish_state",
            state.get("publish_ready") is True and bool(state.get("final_branded_publish_video_path")),
            str(state.get("branding_status")),
        )

    assembly_src = (ROOT / "content_brain" / "execution" / "product_assembly_bridge.py").read_text(encoding="utf-8")
    yt_src = (ROOT / "content_brain" / "publish" / "youtube_metadata_generator.py").read_text(encoding="utf-8")
    _record(
        "assembly_bridge_unmodified",
        "product_subtitle_branding_publish" not in assembly_src,
        "static scan",
    )
    _record(
        "youtube_metadata_unmodified",
        "product_subtitle_branding_publish" not in yt_src,
        "static scan",
    )

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"TOTAL: {len(results)}  PASS: {len(results) - len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return FAIL
    print("ALL PASS")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
