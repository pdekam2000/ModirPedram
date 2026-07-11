"""Local encrypted credential storage for platform Settings."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.local_secret_codec import (
    decrypt_text,
    encrypt_text,
    load_or_create_local_key,
    mask_secret,
)

CREDENTIALS_VERSION = "platform_credentials_v1"
CREDENTIALS_DIR = Path("project_brain") / "local_credentials"
CREDENTIALS_FILENAME = "credentials.local.json"

PROVIDER_FIELDS: dict[str, dict[str, Any]] = {
    "openai": {"label": "OpenAI API", "env": ["OPENAI_API_KEY"], "testable": True},
    "elevenlabs": {"label": "ElevenLabs API", "env": ["ELEVENLABS_API_KEY"], "testable": True},
    "dataforseo_login": {"label": "DataForSEO Login", "env": ["DATAFORSEO_LOGIN"], "testable": False},
    "dataforseo_password": {"label": "DataForSEO Password", "env": ["DATAFORSEO_PASSWORD"], "testable": False},
    "serpapi": {"label": "SerpAPI", "env": ["SERPAPI_API_KEY"], "testable": False},
    "hailuo": {"label": "Hailuo / MiniMax API", "env": ["HAILUO_API_KEY", "MINIMAX_API_KEY"], "testable": False},
    "runway": {"label": "Runway API", "env": ["RUNWAY_API_KEY"], "testable": False},
    "veed": {"label": "Veed AI API", "env": ["VEED_API_KEY"], "testable": False},
}


class LocalCredentialsStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / CREDENTIALS_DIR / CREDENTIALS_FILENAME
        self._key = load_or_create_local_key(self.project_root)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": CREDENTIALS_VERSION, "providers": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": CREDENTIALS_VERSION, "providers": {}}
        if not isinstance(payload, dict):
            return {"version": CREDENTIALS_VERSION, "providers": {}}
        payload.setdefault("version", CREDENTIALS_VERSION)
        payload.setdefault("providers", {})
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _apply_to_env(self, provider_id: str, plain: str) -> None:
        meta = PROVIDER_FIELDS.get(provider_id) or {}
        env_names = list(meta.get("env") or [])
        if not env_names:
            return
        value = (plain or "").strip()
        for index, env_name in enumerate(env_names):
            if not env_name:
                continue
            os.environ[env_name] = value if index == 0 else os.environ.get(env_name, value)

    def apply_all_to_env(self) -> None:
        payload = self._load()
        for provider_id, item in (payload.get("providers") or {}).items():
            cipher = str((item or {}).get("value") or "")
            if not cipher:
                continue
            try:
                plain = decrypt_text(cipher, self._key)
            except Exception:
                continue
            self._apply_to_env(str(provider_id), plain)

    def list_masked(self) -> list[dict[str, Any]]:
        payload = self._load()
        rows: list[dict[str, Any]] = []
        for provider_id, meta in PROVIDER_FIELDS.items():
            item = dict((payload.get("providers") or {}).get(provider_id) or {})
            masked = ""
            configured = False
            if item.get("value"):
                configured = True
                try:
                    masked = mask_secret(decrypt_text(str(item["value"]), self._key))
                except Exception:
                    masked = "configured"
            rows.append(
                {
                    "provider_id": provider_id,
                    "label": meta.get("label") or provider_id,
                    "configured": configured,
                    "masked_value": masked,
                    "testable": bool(meta.get("testable")),
                    "updated_at": str(item.get("updated_at") or ""),
                }
            )
        return rows

    def save_provider_secret(self, provider_id: str, secret: str) -> dict[str, Any]:
        provider_id = str(provider_id or "").strip()
        if provider_id not in PROVIDER_FIELDS:
            raise ValueError(f"unsupported provider: {provider_id}")
        plain = (secret or "").strip()
        payload = self._load()
        providers = dict(payload.get("providers") or {})
        if not plain:
            providers.pop(provider_id, None)
        else:
            providers[provider_id] = {
                "value": encrypt_text(plain, self._key),
                "updated_at": self._now(),
            }
            self._apply_to_env(provider_id, plain)
        payload["providers"] = providers
        payload["updated_at"] = self._now()
        self._save(payload)
        return self.get_provider_status(provider_id)

    def get_provider_status(self, provider_id: str) -> dict[str, Any]:
        for row in self.list_masked():
            if row["provider_id"] == provider_id:
                return row
        meta = PROVIDER_FIELDS.get(provider_id) or {}
        return {
            "provider_id": provider_id,
            "label": meta.get("label") or provider_id,
            "configured": False,
            "masked_value": "",
            "testable": bool(meta.get("testable")),
            "updated_at": "",
        }

    def test_provider_connection(self, provider_id: str) -> dict[str, Any]:
        provider_id = str(provider_id or "").strip()
        status = self.get_provider_status(provider_id)
        if not status.get("configured"):
            return {"ok": False, "provider_id": provider_id, "message": "No credential saved."}
        if provider_id == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                return {"ok": False, "provider_id": provider_id, "message": "OpenAI key not loaded."}
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                client.models.list(limit=1)
                return {"ok": True, "provider_id": provider_id, "message": "OpenAI connection OK."}
            except Exception as exc:
                return {"ok": False, "provider_id": provider_id, "message": str(exc)[:200]}
        if provider_id == "elevenlabs":
            try:
                from providers.audio.elevenlabs_provider import ElevenLabsNarrationProvider

                provider = ElevenLabsNarrationProvider(self.project_root)
                validation = provider.validate_connection()
                ok = bool(validation.get("ok"))
                return {
                    "ok": ok,
                    "provider_id": provider_id,
                    "message": str(validation.get("message") or ("ElevenLabs OK" if ok else "ElevenLabs failed")),
                }
            except Exception as exc:
                return {"ok": False, "provider_id": provider_id, "message": str(exc)[:200]}
        return {
            "ok": True,
            "provider_id": provider_id,
            "message": "Saved locally. Connection test not implemented for this provider yet.",
        }
