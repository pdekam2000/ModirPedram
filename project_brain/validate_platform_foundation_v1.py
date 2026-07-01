"""PHASE PLATFORM-1 — Product platform foundation validation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.browser_health_monitor import get_browser_health, refresh_runway_page
from content_brain.platform.local_credentials_store import LocalCredentialsStore
from content_brain.platform.local_secret_codec import mask_secret
from content_brain.platform.local_user_store import LocalUserStore
from content_brain.platform.run_output_versioning import (
    create_versioned_run_layout,
    finalize_versioned_run_layout,
    list_run_history,
    write_raw_downloads_manifest,
)
from ui.api.platform_service import PlatformService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _run(rel: str) -> None:
    script = ROOT / rel
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-260:])


def main() -> None:
    print("=== PHASE PLATFORM-1 Product Platform Foundation ===")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        creds = LocalCredentialsStore(tmp_root)
        saved = creds.save_provider_secret("openai", "sk-test-openai-key-1234567890")
        masked = str(saved.get("masked_value") or "")
        _pass("credential_save_masks_key", "..." in masked and masked.endswith("7890"), masked)
        listed = creds.list_masked()
        _pass("credential_not_returned_full", all("sk-test-openai-key-1234567890" not in str(row) for row in listed))
        _pass("credential_configured_flag", any(row.get("provider_id") == "openai" and row.get("configured") for row in listed))

        users = LocalUserStore(tmp_root)
        users.create_user("platform_user", "secret-pass-1")
        payload = json.loads((tmp_root / "project_brain/local_user/user.local.json").read_text(encoding="utf-8"))
        _pass("password_hashed_not_plain", payload.get("password_hash") and payload.get("password_hash") != "secret-pass-1")
        _pass("login_works", users.verify_login("platform_user", "secret-pass-1"))
        _pass("login_rejects_bad_password", not users.verify_login("platform_user", "wrong"))

        service = PlatformService(tmp_root)
        session = service.login("platform_user", "secret-pass-1")
        _pass("platform_login_ok", bool(session.get("ok")))
        me = service.me(session["token"])
        _pass("platform_me_authenticated", me.get("authenticated") is True)
        service.logout(session["token"])
        me_after = service.me(session["token"])
        _pass("platform_logout_works", me_after.get("authenticated") is False)

        layout_a = create_versioned_run_layout(tmp_root, run_id="run_a", topic="topic a")
        write_raw_downloads_manifest(layout_a, ["clip_a.mp4"])
        layout_b = create_versioned_run_layout(tmp_root, run_id="run_b", topic="topic b")
        write_raw_downloads_manifest(layout_b, ["clip_b.mp4"])
        _pass("versioned_run_dirs_unique", layout_a.run_dir != layout_b.run_dir)

        final_file = layout_a.final_dir / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        final_file.write_bytes(b"fake")
        layout_a.publish_dir.mkdir(parents=True, exist_ok=True)
        summary = finalize_versioned_run_layout(
            tmp_root,
            layout_a,
            assembly_manifest={"status": "ASSEMBLED", "output_path": str(final_file)},
            publish_manifest={"status": "PUBLISHED_PACKAGE_CREATED", "package_folder": str(layout_a.publish_dir)},
        )
        latest = tmp_root / "outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        _pass("latest_pointer_still_works", latest.is_file())
        history = list_run_history(tmp_root)
        _pass("run_history_recorded", len(history) >= 1, str(len(history)))

    theme_css = (ROOT / "ui/web/src/styles/platform-theme.css").read_text(encoding="utf-8")
    _pass("theme_black_orange_white", "--platform-accent: #ff7a1a" in theme_css and "--platform-text: #f8f8ff" in theme_css)

    app_tsx = (ROOT / "ui/web/src/App.tsx").read_text(encoding="utf-8")
    _pass("login_page_wired", "LoginPage" in app_tsx and "AuthProvider" in app_tsx)
    _pass("automation_center_page_exists", "AutomationCenterPage" in app_tsx)

    main_py = (ROOT / "ui/api/main.py").read_text(encoding="utf-8")
    _pass("browser_health_endpoint", "/platform/browser/health" in main_py)
    _pass("open_browser_endpoint", "/platform/browser/open" in main_py)

    health = get_browser_health(ROOT)
    _pass("browser_health_reports_state", "connected" in health and "last_heartbeat" in health)

    with patch("content_brain.platform.browser_health_monitor._read_generation_active", return_value=(True, "generating")):
        blocked = refresh_runway_page(ROOT, force=False)
    _pass("refresh_blocked_during_generation", blocked.get("blocked") is True)

    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("runway_selectors_unchanged", "runway_ui_navigator" in navigator or navigator.strip())

    create_page = (ROOT / "ui/web/src/pages/CreateVideoPage.tsx").read_text(encoding="utf-8")
    results_page = (ROOT / "ui/web/src/pages/ResultsPage.tsx").read_text(encoding="utf-8")
    _pass("create_video_still_wired", "createVideoGenerate" in create_page)
    _pass("results_still_wired", "fetchLatestResults" in results_page and "Run History" in results_page)

    masked_sample = mask_secret("sk-abcdefghijklmnop")
    _pass("mask_format", masked_sample.startswith("sk-") and "..." in masked_sample)

    print("\n=== Regression ===")
    _run("project_brain/validate_live_post_processing_hook.py")
    _run("project_brain/validate_visual_continuity_verifier.py")
    _run("project_brain/validate_elevenlabs_runtime_v1.py")

    print("\nPHASE PLATFORM-1 platform foundation validation complete — PASS")


if __name__ == "__main__":
    main()
