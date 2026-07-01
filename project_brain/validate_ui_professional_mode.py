"""Professional User Mode validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("[validate_ui_professional_mode] UI Professional Mode")
    app = (ROOT / "ui" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    mode_ctx = (ROOT / "ui" / "web" / "src" / "context" / "AppModeContext.tsx").read_text(encoding="utf-8")

    required_pages = [
        "ProductDashboardPage",
        "CreateVideoPage",
        "SchedulePlannerPage",
        "ResultsPage",
        "UpgradeCenterPage",
        "SettingsPage",
        "DeveloperConsolePage",
    ]
    for page in required_pages:
        _pass(f"page_import_{page}", page in app)

    user_nav = ["Dashboard", "Create Video", "Schedule Planner", "Results", "Upgrade Center", "Settings"]
    for label in user_nav:
        _pass(f"user_nav_{label.replace(' ', '_').lower()}", label in app)

    _pass("developer_mode_toggle", "Developer Mode" in app and "developerMode" in mode_ctx)
    _pass("developer_console_hidden_by_default", "developerMode &&" in app)
    _pass("execution_center_not_default", "ExecutionCenterPage" not in app.split("renderPage")[0])
    print("[validate_ui_professional_mode] All checks PASS")


if __name__ == "__main__":
    main()
