"""Validation — PHASE PRODUCT-30S-MULTICLIP."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution import pwmap_runway_agent_adapter as pwmap_adapter
from content_brain.execution.product_multiclip_execution_plan import (
    EXECUTION_MODE_SINGLE,
    EXECUTION_MODE_USE_FRAME,
    build_multiclip_execution_plan,
    calculate_product_clip_count,
    plan_product_duration,
)
from ui.api.product_studio_service import ProductStudioService

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def main() -> int:
    print("validate_product_30s_multiclip")
    print("=" * 60)

    mapping_cases = [
        (15, 1, EXECUTION_MODE_SINGLE),
        (30, 2, EXECUTION_MODE_USE_FRAME),
        (40, 3, EXECUTION_MODE_USE_FRAME),
        (60, 4, EXECUTION_MODE_USE_FRAME),
    ]
    for duration, expected_clips, expected_mode in mapping_cases:
        plan = plan_product_duration(duration)
        _record(
            f"duration_{duration}s_clip_count",
            plan["clip_count"] == expected_clips and plan["duration_seconds"] == duration,
            f"clip_count={plan['clip_count']} mode={plan['execution_mode']}",
        )
        _record(
            f"duration_{duration}s_execution_mode",
            plan["execution_mode"] == expected_mode,
            plan["execution_mode"],
        )

    custom_cases = [(22, 2), (45, 3), (75, 5)]
    for duration, expected in custom_cases:
        clips = calculate_product_clip_count(duration)
        _record(
            f"custom_duration_{duration}s",
            clips == expected,
            f"clip_count={clips}",
        )

    preflight_payload = {
        "authoritative_topic": "A dragon and a boy explore a forest",
        "provider": "kling_3_0_pro_native_audio",
        "aspect_ratio": "9:16",
        "duration_plan": {"duration_seconds": 30, "clip_count": 2},
        "kling_frame_to_video_plan": {
            "clips": [
                {"clip_index": 1, "prompt": "Clip one prompt"},
                {"clip_index": 2, "prompt": "Clip two prompt"},
            ]
        },
    }
    plan_obj = build_multiclip_execution_plan(preflight_payload, duration_seconds=30)
    _record(
        "product_studio_execution_plan",
        plan_obj.clip_count == 2 and plan_obj.execution_mode == EXECUTION_MODE_USE_FRAME and len(plan_obj.prompts) == 2,
        plan_obj.to_dict().__str__(),
    )

    service = ProductStudioService(ROOT)
    preflight = service.create_video_preflight(
        {
            "custom_topic": "Product multiclip validation topic",
            "duration_seconds": 40,
            "provider": "kling_3_0_pro_native_audio",
            "audio_strategy": "kling_native_audio",
            "platform": "youtube_shorts",
        }
    )
    multiclip = preflight.get("multiclip_execution_plan") or {}
    _record(
        "preflight_multiclip_plan_40s",
        multiclip.get("clip_count") == 3 and multiclip.get("execution_mode") == EXECUTION_MODE_USE_FRAME,
        str(multiclip),
    )
    _record(
        "preflight_duration_plan_clip_count",
        (preflight.get("duration_plan") or {}).get("clip_count") == 3,
        str(preflight.get("duration_plan")),
    )

    _record(
        "single_clip_mode_15s",
        plan_product_duration(15)["execution_mode"] == EXECUTION_MODE_SINGLE,
        plan_product_duration(15)["execution_mode"],
    )
    _record(
        "use_frame_chain_30s",
        plan_product_duration(30)["execution_mode"] == EXECUTION_MODE_USE_FRAME,
        plan_product_duration(30)["execution_mode"],
    )

    adapter_source = inspect.getsource(pwmap_adapter.build_pwmap_job_from_preflight)
    _record(
        "pwmap_adapter_single_vs_multi_routing_preserved",
        "if len(prompts) == 1" in adapter_source and "use_frame_second" in adapter_source,
        "build_pwmap_job_from_preflight unchanged routing",
    )
    _record(
        "pwmap_adapter_not_replaced",
        hasattr(pwmap_adapter, "run_pwmap_product_studio_generate"),
        pwmap_adapter.ADAPTER_VERSION,
    )

    merge = service._merge_pwmap_results(
        {
            "video_path": "/tmp/video.mp4",
            "clip_count": 2,
            "execution_mode": EXECUTION_MODE_USE_FRAME,
            "generation_time_seconds": 120.5,
            "multiclip_execution_plan": {"clip_count": 2, "duration_seconds": 30, "execution_mode": EXECUTION_MODE_USE_FRAME},
            "metadata": {},
        }
    )
    _record(
        "results_page_clip_count_metadata",
        merge.get("clip_count") == 2 and merge.get("execution_mode") == EXECUTION_MODE_USE_FRAME,
        str({k: merge.get(k) for k in ("clip_count", "execution_mode", "generation_time_seconds")}),
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
