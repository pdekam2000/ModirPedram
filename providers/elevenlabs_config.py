"""
Phase 11H-1a — ElevenLabs configuration resolution (read-only, no API calls).

Never prints or persists API key values.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_VERSION = "11h1a_v1"
API_KEY_ENV = "ELEVENLABS_API_KEY"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_registry_voice_entry(project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or Path(__file__).resolve().parents[1]
    registry_path = root / "config" / "provider_registry.json"
    if not registry_path.is_file():
        return {}
    try:
        catalog = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    for entry in catalog.get("voice") or []:
        if isinstance(entry, dict) and str(entry.get("name", "")).lower() == "elevenlabs":
            return entry
    return {}


@dataclass(frozen=True)
class ElevenLabsConfigSnapshot:
    config_version: str
    provider_id: str
    api_key_env: str
    has_api_key: bool
    voice_id: str
    model_id: str
    output_format: str
    enabled_in_registry: bool

    def to_summary(self) -> dict[str, Any]:
        """Safe summary — never includes secret values."""
        return {
            "config_version": self.config_version,
            "provider_id": self.provider_id,
            "api_key_env": self.api_key_env,
            "has_api_key": self.has_api_key,
            "voice_id": self.voice_id,
            "model_id": self.model_id,
            "output_format": self.output_format,
            "enabled_in_registry": self.enabled_in_registry,
        }


class ElevenLabsConfigResolver:
    """Resolve ElevenLabs settings from env and registry without side effects."""

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()

    def resolve(
        self,
        session: dict[str, Any] | None = None,
        *,
        voice_id: str | None = None,
        model_id: str | None = None,
    ) -> ElevenLabsConfigSnapshot:
        session = session or {}
        registry_entry = _load_registry_voice_entry(self.project_root)
        api_key_env = str(registry_entry.get("api_key_env") or API_KEY_ENV).strip()
        key_value = os.getenv(api_key_env, "").strip()

        selection = _dict(_dict(session.get("provider_selection")).get("category_selections"))
        voice_sel = _dict(selection.get("voice_generation"))

        resolved_voice = (
            voice_id
            or voice_sel.get("voice_id")
            or registry_entry.get("default_voice_id")
            or DEFAULT_VOICE_ID
        )
        resolved_model = model_id or voice_sel.get("model_id") or DEFAULT_MODEL_ID

        return ElevenLabsConfigSnapshot(
            config_version=CONFIG_VERSION,
            provider_id="elevenlabs",
            api_key_env=api_key_env,
            has_api_key=bool(key_value),
            voice_id=str(resolved_voice).strip(),
            model_id=str(resolved_model).strip(),
            output_format=DEFAULT_OUTPUT_FORMAT,
            enabled_in_registry=bool(registry_entry.get("enabled", True)),
        )


__all__ = [
    "CONFIG_VERSION",
    "API_KEY_ENV",
    "DEFAULT_VOICE_ID",
    "DEFAULT_MODEL_ID",
    "ElevenLabsConfigSnapshot",
    "ElevenLabsConfigResolver",
]
