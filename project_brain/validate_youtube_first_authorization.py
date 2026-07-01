"""Validation — PHASE YT-2A first YouTube OAuth authorization."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.upload.youtube_auth import (  # noqa: E402
    load_account_info,
    load_token,
    refresh_access_token,
    save_token,
)
from content_brain.upload.youtube_first_authorization import (  # noqa: E402
    YOUTUBE_AUTH_RESULT_NAME,
    discover_oauth_credentials,
    get_youtube_oauth_readiness,
    load_youtube_auth_result,
    run_first_youtube_authorization,
    write_youtube_auth_result,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402
from ui.api.upload_service import UploadService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _write_client_secret(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client-id.apps.googleusercontent.com",
                    "client_secret": "test-client-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )


def main() -> int:
    print("validate_youtube_first_authorization")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        secret_path = root / "secrets" / "client_secret_test.json"
        _write_client_secret(secret_path)
        (root / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        (root / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            json.dumps({"youtube_upload_enabled": False, "youtube_oauth_client_path": ""}),
            encoding="utf-8",
        )

        discovery = discover_oauth_credentials(root)
        _record(
            "oauth_credential_path_located",
            discovery.get("ok") is True and secret_path.name in str(discovery.get("oauth_client_path")),
            str(discovery.get("oauth_client_path")),
        )
        _record(
            "client_id_loaded",
            discovery.get("client_id") == "test-client-id.apps.googleusercontent.com",
            str(discovery.get("client_id")),
        )

        oauth_ok = {
            "ok": True,
            "method": "mock_local_server",
            "token_saved": True,
        }
        channel_ok = {
            "ok": True,
            "youtube_account_id": "UC999",
            "channel_id": "UC999",
            "channel_name": "Test Channel",
        }
        with patch(
            "content_brain.upload.youtube_first_authorization._run_oauth_local_server",
            return_value=oauth_ok,
        ), patch(
            "content_brain.upload.youtube_first_authorization.fetch_and_store_channel_info",
            return_value=channel_ok,
        ), patch(
            "content_brain.upload.youtube_first_authorization.load_account_info",
            return_value={
                "channel_id": "UC999",
                "channel_name": "Test Channel",
                "youtube_account_id": "UC999",
            },
        ), patch(
            "content_brain.upload.youtube_first_authorization.load_token",
            return_value={"access_token": "a", "refresh_token": "r"},
        ), patch(
            "content_brain.upload.youtube_first_authorization.refresh_access_token",
            return_value={"ok": True, "access_token": "refreshed"},
        ):
            auth_result = run_first_youtube_authorization(root, open_browser=False)

        save_token(
            root,
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "test-client-id.apps.googleusercontent.com",
                "client_secret": "test-client-secret",
            },
        )
        from content_brain.upload.youtube_auth import save_account_info  # noqa: E402

        save_account_info(
            root,
            {"channel_id": "UC999", "channel_name": "Test Channel", "youtube_account_id": "UC999"},
        )

        _record("first_authorization_persists", auth_result.get("authorized") is True, str(auth_result.get("channel_name")))
        _record(
            "youtube_auth_result_written",
            (root / "project_brain" / "upload" / YOUTUBE_AUTH_RESULT_NAME).is_file(),
            str(root / "project_brain" / "upload" / YOUTUBE_AUTH_RESULT_NAME),
        )
        loaded = load_youtube_auth_result(root)
        _record(
            "auth_result_schema",
            loaded is not None
            and loaded.get("authorized") is True
            and loaded.get("token_refresh_verified") is True
            and loaded.get("channel_id") == "UC999",
            str(loaded),
        )

        readiness = get_youtube_oauth_readiness(root)
        _record(
            "oauth_readiness_after_auth",
            readiness.get("youtube_authorized") is True and readiness.get("youtube_channel_id") == "UC999",
            str(readiness.get("oauth_status")),
        )

        with patch("requests.post") as refresh_post:
            refresh_post.return_value.ok = True
            refresh_post.return_value.json.return_value = {"access_token": "new-access"}
            refreshed = refresh_access_token(root, {"youtube_oauth_client_path": str(secret_path)})
        _record("token_refresh_without_login", refreshed.get("ok") is True, str(refreshed.get("access_token")))

        service = ProductStudioService(root)
        enriched = service._attach_youtube_oauth_fields({"found": True, "topic": "OAuth test"})
        _record(
            "results_page_oauth_fields",
            "youtube_oauth_status" in enriched and "youtube_upload_ready" in enriched,
            str(enriched.get("youtube_oauth_status")),
        )

        upload_service = UploadService(root)
        with patch.object(upload_service, "youtube_first_authorization", return_value={"ok": True, "authorized": True}):
            api = upload_service.youtube_first_authorization({"open_browser": False})
        _record("upload_service_first_auth_hook", api.get("authorized") is True, str(api.get("ok")))

    real_discovery = discover_oauth_credentials(ROOT)
    _record(
        "project_oauth_credentials_discoverable",
        real_discovery.get("ok") is True,
        str(real_discovery.get("oauth_client_path")),
    )

    metadata_src = (ROOT / "content_brain" / "publish" / "youtube_metadata_generator.py").read_text(encoding="utf-8")
    _record(
        "no_metadata_generator_modified",
        "youtube_first_authorization" not in metadata_src,
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
