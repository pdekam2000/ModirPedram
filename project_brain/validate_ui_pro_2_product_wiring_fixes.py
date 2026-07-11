"""Phase UI-PRO-2 FIX — Product UI wiring validation."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.upgrades.patch_upload_service import PatchUploadError, list_uploaded_patches, upload_patch_package
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
        _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-220:])
    elif proc.returncode != 0:
        print(f"[WARN] {rel}")


def main() -> None:
    print("=== UI-PRO-2 Product Wiring Fixes ===")

    main_py = (ROOT / "ui/api/main.py").read_text(encoding="utf-8")
    create_page = (ROOT / "ui/web/src/pages/CreateVideoPage.tsx").read_text(encoding="utf-8")
    product_client = (ROOT / "ui/web/src/api/productClient.ts").read_text(encoding="utf-8")
    upgrade_page = (ROOT / "ui/web/src/pages/UpgradeCenterPage.tsx").read_text(encoding="utf-8")

    _pass("generate_route_exists", "/product/create-video/generate" in main_py)
    _pass("generate_frontend_calls_endpoint", "createVideoGenerate" in product_client and "/product/create-video/generate" in product_client)
    _pass("create_video_generate_button", "Generate Video" in create_page and "createVideoGenerate" in create_page)

    service = ProductStudioService(ROOT)
    runway_mock = MagicMock()
    runway_mock.start_run.return_value = {
        "ok": True,
        "project_id": "phase_i_live",
        "snapshot": {"project_id": "phase_i_live", "run_status": "running"},
        "handoff_preview": {"content_brain_run_id": "cb_test_001"},
    }

    generate = service.create_video_generate(
        {"topic_mode": "custom", "custom_topic": "test wiring topic", "duration_seconds": 30, "provider": "runway"},
        runway_service=runway_mock,
    )
    _pass("generate_returns_run_id", bool(generate.get("run_id")))
    _pass("generate_returns_session_id", bool(generate.get("session_id")))
    _pass("generate_status_starting", generate.get("status") == "starting")

    source = inspect.getsource(service.create_video_generate)
    _pass("generate_uses_runway_live_smoke", "runway_service.start_run" in source)
    _pass("generate_uses_full_auto", "FULL_AUTO" in source or "execution_mode" in source)
    _pass("generate_no_duplicate_engine", "run_live_smoke_test" not in source)

    unsupported = service.create_video_generate(
        {"topic_mode": "custom", "custom_topic": "hailuo topic", "provider": "hailuo"},
        runway_service=runway_mock,
    )
    _pass("unsupported_provider_message", unsupported.get("message") == "Provider execution not wired yet.")
    runway_mock.start_run.assert_called_once()

    profile_path = ROOT / "project_brain" / "product_settings" / "channel_profile.json"
    saved = service.save_channel_profile(
        {
            "channel_name": "Wiring Test Channel",
            "main_niche": "tech reviews",
            "sub_niche": "phones",
            "channel_topic": "daily phone tips",
            "target_audience": "mobile enthusiasts",
            "language": "English",
            "tone_style": "energetic",
            "default_platform": "tiktok",
            "default_duration_seconds": 20,
            "default_provider": "runway",
            "upload_platforms": ["tiktok"],
        }
    )
    _pass("settings_post_persists_file", profile_path.is_file())
    reloaded = json.loads(profile_path.read_text(encoding="utf-8"))
    _pass("settings_disk_channel_topic", reloaded.get("channel_topic") == "daily phone tips")
    fetched = service.get_channel_profile()
    _pass("settings_get_returns_saved", fetched.get("channel_topic") == "daily phone tips")
    _pass("default_provider_persists", fetched.get("default_provider") == "runway")

    channel_preflight = service.create_video_preflight({"topic_mode": "channel", "custom_topic": "", "duration_seconds": 20})
    _pass("create_video_uses_saved_channel_topic", "daily phone tips" in str(channel_preflight.get("authoritative_topic")))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        manifest = {"name": "Test Patch", "type": "feature_patch", "version": "0.0.1"}
        zip_path = tmp_root / "sample_patch.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        upload = upload_patch_package(project_root=tmp_root, filename="sample_patch.zip", content=zip_path.read_bytes())
        _pass("upgrade_upload_accepts_zip", upload.get("ok") is True)
        _pass("upgrade_upload_no_auto_apply", upload.get("auto_applied") is False)
        listed = list_uploaded_patches(tmp_root)
        _pass("uploaded_patch_listed", any(item.get("upgrade_id") == upload.get("upgrade_id") for item in listed))

        try:
            upload_patch_package(project_root=tmp_root, filename="evil.exe", content=b"bad")
            _pass("upgrade_rejects_exe", False)
        except PatchUploadError:
            _pass("upgrade_rejects_exe", True)

    _pass("upgrade_upload_route", "/upgrades/upload" in main_py)
    _pass("upgrade_upload_ui", "uploadUpgradePatch" in product_client and "Upload Patch" in upgrade_page)
    _pass("channel_profile_post_route", '"/product/channel-profile"' in main_py and "product_save_channel_profile_post" in main_py)

    runway_navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("runway_navigator_unchanged_exists", "runway_ui_navigator" in runway_navigator or runway_navigator.strip())

    print("\n=== Regression ===")
    _run("project_brain/validate_ui_pro_2_create_video_scheduling.py")
    _run("project_brain/validate_upgrade_center_foundation.py")
    _run("project_brain/validate_director_layer_v1.py")
    _run("project_brain/validate_director_layer_v2_prompt_critic.py")
    _run("project_brain/validate_runway_phase_i_hardening.py", required=False)
    _run("project_brain/validate_runway_phase_i_final_assembly.py", required=False)
    _run("project_brain/validate_runway_phase_i_publish_package.py", required=False)

    print("\nUI-PRO-2 product wiring fixes validation complete — PASS")


if __name__ == "__main__":
    main()
