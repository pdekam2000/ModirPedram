"""Validate SETTINGS-3 clean Settings UX — accordion, credential table, modals."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _run(rel: str) -> None:
    proc = subprocess.run([sys.executable, str(ROOT / rel)], cwd=str(ROOT), capture_output=True, text=True)
    _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-260:])


def main() -> None:
    settings_page = _read("ui/web/src/pages/SettingsPage.tsx")
    cred_table = _read("ui/web/src/components/settings/CredentialTable.tsx")
    accordion = _read("ui/web/src/components/settings/SettingsAccordion.tsx")
    modal = _read("ui/web/src/components/settings/SettingsModal.tsx")
    app_css = _read("ui/web/src/App.css")
    cred_store = _read("content_brain/platform/local_credentials_store.py")

    sections = [
        "Channel Setup",
        "API Credentials",
        "Providers",
        "Branding",
        "Voice & Music",
        "Upload & Platforms",
        "Automation",
        "Local Access",
        "Advanced / Developer",
    ]
    for section in sections:
        _pass(f"section_{section.lower().replace(' ', '_')}", section in settings_page, section)

    _pass("accordion_component", "SettingsAccordion" in settings_page and "settings-accordion" in accordion)
    _pass("accordion_css", ".settings-accordion-stack" in app_css)
    _pass("max_two_sections_logic", "slice(-2)" in settings_page)

    _pass("credential_table_component", "settings-cred-table" in cred_table)
    _pass("credential_columns", all(token in cred_table for token in ("Provider", "Status", "Masked Key", "Actions")))
    _pass("add_modal", "SettingsModal" in cred_table and 'modalMode === "add"' in cred_table)
    _pass("edit_modal", 'modalMode === "edit"' in cred_table)
    _pass("remove_confirm", "window.confirm" in cred_table)
    _pass("test_action", "testCredential" in cred_table)
    _pass("password_input_only", 'type="password"' in cred_table)
    _pass("masked_key_display", "masked_value" in cred_table and "Full secrets are never displayed" in cred_table)

    _pass("save_channel_profile", "saveChannelProfile" in settings_page)
    _pass("branding_toggles", "Branding enabled" in settings_page and "Subtitles enabled" in settings_page)
    _pass("voice_music_rows", "Narration provider" in settings_page and "Music provider" in settings_page)
    _pass("upload_rows", "YouTube upload enabled" in settings_page and "upload_platforms" in settings_page)
    _pass("automation_daily_limit", "Daily job limit" in settings_page and "fetchAutomationStatus" in settings_page)
    _pass("logo_preview", "settings-logo-preview" in settings_page)
    _pass("local_mode_toggle", "local_mode" in settings_page and "Local Single User Mode" in settings_page)

    _pass("developer_gate", "developerMode" in settings_page and "Advanced / Developer" in settings_page)
    _pass("developer_hidden_without_mode", "developerMode ?" in settings_page)

    _pass("credential_backend_unchanged", "encrypt_text" in cred_store and "mask_secret" in cred_store)
    _pass("no_full_secret_in_ui", "sk-test" not in cred_table and "password_hash" not in cred_table)

    _pass("modal_component_exists", "settings-modal-overlay" in modal)
    _pass("compact_channel_setup", "Show generated profile fields" in settings_page)

    print("\n=== Regression ===")
    _run("project_brain/validate_auth_refine_v1.py")

    print("\nAll SETTINGS-3 clean UX validations passed.")
    print("Note: also run python project_brain/validate_platform_foundation_v1.py separately (environment-dependent).")


if __name__ == "__main__":
    main()
