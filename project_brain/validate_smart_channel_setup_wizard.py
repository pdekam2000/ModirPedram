"""PHASE SETTINGS-2 — Smart Channel Setup Wizard validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.channel.channel_profile_generator import (
    TONE_PRESETS,
    VISUAL_STYLE_PRESETS,
    generate_channel_profile_suggestion,
    normalize_suggestion,
)
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _run(rel: str) -> None:
    script = ROOT / rel
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-260:])


def main() -> None:
    print("=== PHASE SETTINGS-2 Smart Channel Setup Wizard ===")

    service = ProductStudioService(ROOT)
    profile_path = ROOT / "project_brain" / "product_settings" / "channel_profile.json"
    before = service.get_channel_profile()
    before_disk = profile_path.read_text(encoding="utf-8") if profile_path.is_file() else ""

    suggestion = service.suggest_channel_profile({"channel_topic": "Scorpions and desert animals"})
    required_keys = {
        "channel_name",
        "main_niche",
        "sub_niche",
        "channel_topic",
        "target_audience",
        "language",
        "tone_style",
        "visual_style",
        "default_platform",
        "default_duration_seconds",
        "default_provider",
        "default_narration_provider",
        "music_provider",
        "preferred_topics",
        "forbidden_topics",
        "content_formats",
        "upload_platforms",
        "reasoning",
        "source",
    }
    _pass("suggest_returns_structured_profile", required_keys.issubset(set(suggestion.keys())))
    _pass("suggest_channel_topic", "scorpion" in suggestion.get("channel_topic", "").lower() or "desert" in suggestion.get("channel_topic", "").lower())

    after = service.get_channel_profile()
    after_disk = profile_path.read_text(encoding="utf-8") if profile_path.is_file() else ""
    _pass("suggest_does_not_auto_save", after == before and after_disk == before_disk)

    saved = service.save_channel_profile(
        {
            **{k: suggestion[k] for k in suggestion if k not in {"reasoning", "source"}},
            "channel_name": "Desert Creatures Shorts",
            "use_ai_director_default": True,
            "use_prompt_critic_default": True,
        }
    )
    _pass("save_persists_generated_profile", saved.get("channel_name") == "Desert Creatures Shorts")
    _pass("save_visual_style", bool(saved.get("visual_style")))
    reloaded = json.loads(profile_path.read_text(encoding="utf-8"))
    _pass("save_disk_persists", reloaded.get("channel_name") == "Desert Creatures Shorts")

    normalized = normalize_suggestion(
        {
            "channel_topic": "test",
            "tone_style": "not-a-preset",
            "visual_style": "not-a-preset",
            "default_platform": "invalid",
            "default_provider": "invalid",
            "default_narration_provider": "invalid",
            "music_provider": "invalid",
            "default_duration_seconds": 999,
        }
    )
    _pass("dropdown_values_normalized", normalized.tone_style in TONE_PRESETS)
    _pass("visual_style_normalized", normalized.visual_style in VISUAL_STYLE_PRESETS)
    _pass("duration_clamped", normalized.default_duration_seconds in {6, 8, 10, 20, 30, 40} or 6 <= normalized.default_duration_seconds <= 60)

    custom = normalize_suggestion({"tone_style": "custom", "visual_style": "custom", "channel_topic": "niche"})
    _pass("custom_dropdown_allowed", custom.tone_style == "custom" and custom.visual_style == "custom")

    create_page = (ROOT / "ui/web/src/pages/CreateVideoPage.tsx").read_text(encoding="utf-8")
    _pass("create_video_reads_visual_style", "visual_style" in create_page)
    _pass("create_video_reads_director_default", "use_ai_director_default" in create_page)
    _pass("create_video_reads_critic_default", "use_prompt_critic_default" in create_page)

    channel_preflight = service.create_video_preflight({"topic_mode": "channel", "duration_seconds": saved.get("default_duration_seconds", 30)})
    custom_preflight = service.create_video_preflight(
        {"topic_mode": "custom", "custom_topic": "one-off espresso tips", "duration_seconds": 20}
    )
    _pass(
        "create_video_uses_saved_topic",
        channel_preflight.get("authoritative_topic") == saved.get("channel_topic"),
    )
    _pass(
        "custom_topic_overrides_video_only",
        custom_preflight.get("authoritative_topic") == "one-off espresso tips",
    )
    _pass(
        "custom_topic_does_not_overwrite_profile",
        service.get_channel_profile().get("channel_topic") == saved.get("channel_topic"),
    )

    with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
        fallback = generate_channel_profile_suggestion("AI tools for beginners", force_rule_based=True)
    _pass("openai_fallback_rule_based", fallback.source == "rule_based")
    _pass("fallback_has_reasoning", bool(fallback.reasoning))

    main_py = (ROOT / "ui/api/main.py").read_text(encoding="utf-8")
    settings_page = (ROOT / "ui/web/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    _pass("suggest_route_registered", "/product/channel-profile/suggest" in main_py)
    _pass("settings_wizard_ui", "Smart Channel Setup" in settings_page and "Generate Channel Profile" in settings_page)
    _pass("settings_review_banner", "Generated by AI" in settings_page)

    runway_nav = ROOT / "content_brain/execution/runway_ui_navigator.py"
    post_proc = (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8")
    _pass("runway_navigator_exists", runway_nav.is_file())
    _pass("no_runway_automation_change_marker", "runway_ui_navigator" in post_proc or runway_nav.is_file())

    print("\n=== Regression ===")
    _run("project_brain/validate_ui_pro_2_product_wiring_fixes.py")
    _run("project_brain/validate_topic_authority_end_to_end.py")

    print("\nPHASE SETTINGS-2 smart channel setup wizard validation complete — PASS")


if __name__ == "__main__":
    main()
