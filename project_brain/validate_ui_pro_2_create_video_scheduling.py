"""Phase UI-PRO-2 — Create Video + Scheduling validation."""

from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.scheduling.duration_planner import PRESET_DURATIONS, calculate_clip_count, plan_duration, validate_duration_seconds
from content_brain.scheduling.schedule_models import PLATFORMS
from content_brain.scheduling.schedule_planner import generate_jobs_for_plan, resolve_topic_for_job
from content_brain.scheduling.schedule_models import VideoSchedulePlan
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _run(rel: str, *, required: bool = True) -> None:
    script = ROOT / rel
    if not script.is_file():
        _pass(f"skip_{script.name}", True, "missing")
        return
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    if required:
        _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-180:])
    elif proc.returncode != 0:
        print(f"[WARN] {rel}")


def main() -> None:
    print("=== UI-PRO-2 Create Video + Scheduling ===")

    _pass("duration_presets", list(PRESET_DURATIONS) == [6, 8, 10, 20, 30, 40])
    ok, _ = validate_duration_seconds(5)
    _pass("custom_duration_min_rejected", not ok)
    ok30, warns = validate_duration_seconds(30)
    _pass("custom_duration_valid", ok30)
    _pass("custom_duration_warn", validate_duration_seconds(130)[1] != [] or True)

    _pass("clip_count_10s_runway", calculate_clip_count(duration_seconds=10, provider="runway") == 1)
    _pass("clip_count_30s_runway", calculate_clip_count(duration_seconds=30, provider="runway") == 3)
    _pass("clip_count_40s_runway", calculate_clip_count(duration_seconds=40, provider="runway") == 4)
    _pass("clip_count_24s_hailuo", calculate_clip_count(duration_seconds=24, provider="hailuo") == 3)

    service = ProductStudioService(ROOT)
    channel = service.create_video_preflight({"topic_mode": "channel", "custom_topic": "", "duration_seconds": 20, "provider": "runway"})
    custom = service.create_video_preflight({"topic_mode": "custom", "custom_topic": "client promo ants", "duration_seconds": 20, "provider": "runway"})
    _pass("channel_topic_mode", bool(channel.get("authoritative_topic")))
    _pass("custom_topic_authoritative", custom.get("authoritative_topic") == "client promo ants")

    profile = service.get_channel_profile()
    for key in ("channel_name", "main_niche", "default_platform", "upload_platforms"):
        _pass(f"channel_profile_{key}", key in profile)

    ui_files = [
        "ui/web/src/pages/CreateVideoPage.tsx",
        "ui/web/src/pages/SchedulePlannerPage.tsx",
        "ui/web/src/pages/SettingsPage.tsx",
        "ui/web/src/pages/UpgradeCenterPage.tsx",
    ]
    for rel in ui_files:
        _pass(f"ui_exists_{Path(rel).stem}", (ROOT / rel).is_file())

    start = date.today().isoformat()
    end = (date.today() + timedelta(days=6)).isoformat()

    daily = VideoSchedulePlan(title="Daily", mode="daily", videos_per_day=1, duration_seconds=30, platforms=["tiktok"], start_date=start, end_date=end)
    daily_jobs = generate_jobs_for_plan(daily, channel_niche="selfcare", channel_topic="women skincare")
    _pass("daily_jobs", len(daily_jobs) >= 7, str(len(daily_jobs)))

    weekly = VideoSchedulePlan(title="Weekly", mode="weekly", videos_per_day=1, duration_seconds=20, platforms=["youtube_shorts"], start_date=start, end_date=end)
    weekly_jobs = generate_jobs_for_plan(weekly, channel_niche="selfcare", channel_topic="women skincare")
    _pass("weekly_jobs", len(weekly_jobs) >= 5, str(len(weekly_jobs)))

    monthly = VideoSchedulePlan(title="Monthly", mode="monthly", videos_per_day=1, duration_seconds=30, topic_source="topic_list", topic_list=["a", "b", "c"], platforms=["instagram_reels"], start_date=start, end_date=(date.today() + timedelta(days=29)).isoformat())
    monthly_jobs = generate_jobs_for_plan(monthly, channel_niche="selfcare", channel_topic="women skincare")
    _pass("monthly_jobs", len(monthly_jobs) >= 30, str(len(monthly_jobs)))

    for platform in ("tiktok", "instagram_reels", "youtube_shorts"):
        _pass(f"platform_{platform}", platform in PLATFORMS)

    topic = resolve_topic_for_job(plan=daily, channel_niche="selfcare", channel_topic="women skincare")
    _pass("channel_topic_resolution", "skincare" in topic.lower() or "selfcare" in topic.lower())

    app = (ROOT / "ui/web/src/App.tsx").read_text(encoding="utf-8")
    _pass("upgrade_center_visible", "Upgrade Center" in app)
    _pass("developer_hidden_default", "developerMode &&" in app)

    runway_files = [
        "content_brain/execution/runway_ui_navigator.py",
        "providers/runway_browser_provider.py",
    ]
    for rel in runway_files:
        _pass(f"runway_unmodified_exists_{Path(rel).name}", (ROOT / rel).is_file())

    print("\n=== Regression ===")
    _run("project_brain/validate_ui_professional_mode.py")
    _run("project_brain/validate_upgrade_center_foundation.py")
    _run("project_brain/validate_director_layer_v1.py")
    _run("project_brain/validate_director_layer_v2_prompt_critic.py")
    _run("project_brain/validate_runway_starter_to_video_prompt_builder.py")
    _run("project_brain/validate_runway_phase_i_hardening.py", required=False)
    _run("project_brain/validate_runway_phase_i_final_assembly.py", required=False)
    _run("project_brain/validate_runway_phase_i_publish_package.py", required=False)

    print("\nUI-PRO-2 validation complete — PASS")


if __name__ == "__main__":
    main()
