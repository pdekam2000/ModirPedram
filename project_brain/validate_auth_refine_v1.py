"""Validate AUTH-REFINE-1 — local single-user mode + SaaS auth preserved."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.local_credentials_store import LocalCredentialsStore
from content_brain.platform.local_user_store import LocalUserStore
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from ui.api.platform_service import PlatformService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _save_profile(root: Path, **overrides: object) -> None:
    store = ProductChannelProfileStore(root)
    profile = store.load()
    profile.update(overrides)
    store.save(profile)


def test_local_mode_default_enabled() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        profile = ProductChannelProfileStore(tmp).load()
        _pass("local_mode_default", profile.get("local_mode") is True)


def test_local_mode_starts_without_login() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _save_profile(tmp, local_mode=True)
        service = PlatformService(tmp)
        config = service.get_auth_config()
        _pass("config_local_mode", config.get("local_mode") is True)
        session = service.auto_login_local()
        _pass("auto_login_ok", session.get("ok") is True, session.get("username", ""))
        me = service.me(session["token"])
        _pass("auto_login_authenticated", me.get("authenticated") is True)


def test_local_mode_creates_default_user() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _save_profile(tmp, local_mode=True)
        service = PlatformService(tmp)
        session = service.auto_login_local()
        _pass("default_user_created", LocalUserStore(tmp).user_exists())
        _pass("default_username", bool(session.get("username")))


def test_saas_mode_blocks_auto_login() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _save_profile(tmp, local_mode=False)
        LocalUserStore(tmp).create_user("saas_user", "secret-pass-1")
        service = PlatformService(tmp)
        blocked = service.auto_login_local()
        _pass("auto_login_blocked", blocked.get("ok") is False)


def test_saas_mode_password_login_still_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        _save_profile(tmp, local_mode=False)
        LocalUserStore(tmp).create_user("saas_user", "secret-pass-1")
        service = PlatformService(tmp)
        session = service.login("saas_user", "secret-pass-1")
        _pass("saas_login_ok", session.get("ok") is True)
        me = service.me(session["token"])
        _pass("saas_me_authenticated", me.get("authenticated") is True)
        bad = service.login("saas_user", "wrong-password")
        _pass("saas_login_rejects_bad_password", bad.get("ok") is False)


def test_credentials_remain_protected() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        creds = LocalCredentialsStore(tmp)
        saved = creds.save_provider_secret("openai", "sk-test-secret-key-abcdef")
        masked = str(saved.get("masked_value") or "")
        payload = json.loads((tmp / "project_brain/local_credentials/credentials.local.json").read_text(encoding="utf-8"))
        stored_cipher = str(payload.get("providers", {}).get("openai", {}).get("value") or "")
        _pass("credential_masked", bool(masked) and "sk-test-secret-key-abcdef" not in masked, masked)
        _pass("credential_not_plain_on_disk", stored_cipher != "sk-test-secret-key-abcdef" and bool(stored_cipher))


def test_auth_backend_endpoints_present() -> None:
    main_py = (ROOT / "ui/api/main.py").read_text(encoding="utf-8")
    _pass("login_endpoint", "/platform/auth/login" in main_py)
    _pass("logout_endpoint", "/platform/auth/logout" in main_py)
    _pass("local_auto_login_endpoint", "/platform/auth/local-auto-login" in main_py)
    _pass("auth_config_endpoint", "/platform/auth/config" in main_py)


def test_ui_local_mode_wiring() -> None:
    app_tsx = (ROOT / "ui/web/src/App.tsx").read_text(encoding="utf-8")
    auth_tsx = (ROOT / "ui/web/src/context/AuthContext.tsx").read_text(encoding="utf-8")
    settings_tsx = (ROOT / "ui/web/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    _pass("app_hides_user_banner", "localMode" in app_tsx and "Signed in as" in app_tsx)
    _pass("auth_auto_login", "localAutoLogin" in auth_tsx and "localMode" in auth_tsx)
    _pass("settings_toggle", "local_mode" in settings_tsx and "Local Single User Mode" in settings_tsx)


def main() -> None:
    test_local_mode_default_enabled()
    test_local_mode_starts_without_login()
    test_local_mode_creates_default_user()
    test_saas_mode_blocks_auto_login()
    test_saas_mode_password_login_still_works()
    test_credentials_remain_protected()
    test_auth_backend_endpoints_present()
    test_ui_local_mode_wiring()
    print("All AUTH-REFINE-1 validations passed.")


if __name__ == "__main__":
    main()
