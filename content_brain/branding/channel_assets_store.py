"""Channel asset storage — logo upload path."""

from __future__ import annotations

from pathlib import Path

CHANNEL_ASSETS_SUBDIR = Path("project_brain") / "channel_assets"
LOGO_FILENAME = "logo.png"


class ChannelAssetsStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.assets_dir = self.project_root / CHANNEL_ASSETS_SUBDIR
        self.logo_path = self.assets_dir / LOGO_FILENAME

    def logo_exists(self) -> bool:
        return self.logo_path.is_file() and self.logo_path.stat().st_size > 0

    def save_logo_bytes(self, payload: bytes) -> str:
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.logo_path.write_bytes(payload)
        return str(self.logo_path.resolve())

    def logo_status(self) -> dict[str, str | bool]:
        return {
            "logo_path": str(self.logo_path) if self.logo_exists() else "",
            "logo_exists": self.logo_exists(),
        }


__all__ = ["CHANNEL_ASSETS_SUBDIR", "ChannelAssetsStore", "LOGO_FILENAME"]
