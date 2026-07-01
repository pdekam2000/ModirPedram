"""Local-only username/password store for platform login gate."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_VERSION = "platform_local_user_v1"
USER_DIR = Path("project_brain") / "local_user"
USER_FILENAME = "user.local.json"
PBKDF2_ITERATIONS = 200_000


class LocalUserStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / USER_DIR / USER_FILENAME

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PBKDF2_ITERATIONS,
        )
        return digest.hex()

    def user_exists(self) -> bool:
        payload = self._load()
        return bool(payload.get("username") and payload.get("password_hash") and payload.get("salt"))

    def get_public_user(self) -> dict[str, Any]:
        payload = self._load()
        if not payload:
            return {"exists": False, "username": ""}
        return {
            "exists": True,
            "username": str(payload.get("username") or ""),
            "created_at": str(payload.get("created_at") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
        }

    def create_user(self, username: str, password: str) -> dict[str, Any]:
        if self.user_exists():
            raise ValueError("Local user already exists.")
        username = (username or "").strip()
        password = password or ""
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        salt = secrets.token_hex(16)
        now = self._now()
        payload = {
            "version": USER_VERSION,
            "username": username,
            "salt": salt,
            "password_hash": self._hash_password(password, salt),
            "created_at": now,
            "updated_at": now,
        }
        self._save(payload)
        return self.get_public_user()

    def verify_login(self, username: str, password: str) -> bool:
        payload = self._load()
        if not payload:
            return False
        if (username or "").strip() != str(payload.get("username") or ""):
            return False
        salt = str(payload.get("salt") or "")
        expected = str(payload.get("password_hash") or "")
        if not salt or not expected:
            return False
        computed = self._hash_password(password or "", salt)
        return secrets.compare_digest(computed, expected)
