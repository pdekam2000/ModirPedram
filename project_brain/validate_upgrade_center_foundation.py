"""Upgrade Center foundation validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.upgrades import FUTURE_PATCHES, UPGRADE_CENTER_VERSION, list_future_patches


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("[validate_upgrade_center_foundation] Upgrade Center")
    ui_page = ROOT / "ui" / "web" / "src" / "pages" / "UpgradeCenterPage.tsx"
    api_route = (ROOT / "ui" / "api" / "main.py").read_text(encoding="utf-8")
    _pass("upgrade_page_exists", ui_page.is_file())
    _pass("upgrade_api_route", "/product/upgrade-center/patches" in api_route)
    _pass("upgrade_upload_route", "/upgrades/upload" in api_route)
    _pass("version_defined", bool(UPGRADE_CENTER_VERSION))
    _pass("future_patches", len(list_future_patches()) >= 5, str(len(FUTURE_PATCHES)))
    print("[validate_upgrade_center_foundation] All checks PASS")


if __name__ == "__main__":
    main()
