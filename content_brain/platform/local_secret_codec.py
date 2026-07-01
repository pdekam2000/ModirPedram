"""Minimal local secret encoding for platform credential storage."""

from __future__ import annotations

import base64
import hashlib
import secrets
from pathlib import Path


def local_key_path(project_root: Path) -> Path:
    return project_root / "project_brain" / "local_credentials" / ".local_key"


def load_or_create_local_key(project_root: Path) -> bytes:
    path = local_key_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        raw = path.read_bytes()
        if len(raw) >= 32:
            return raw[:32]
    key = secrets.token_bytes(32)
    path.write_bytes(key)
    return key


def _expand_key(key: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def encrypt_text(plain: str, key: bytes) -> str:
    data = (plain or "").encode("utf-8")
    stream = _expand_key(key, len(data))
    encoded = base64.urlsafe_b64encode(bytes(a ^ b for a, b in zip(data, stream))).decode("ascii")
    return encoded


def decrypt_text(cipher: str, key: bytes) -> str:
    raw = base64.urlsafe_b64decode((cipher or "").encode("ascii"))
    stream = _expand_key(key, len(raw))
    return bytes(a ^ b for a, b in zip(raw, stream)).decode("utf-8")


def mask_secret(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return f"{text[:2]}...{text[-1:]}"
    return f"{text[:3]}...{text[-4:]}"
