"""
Phase 12I-A — Runway browser launcher restoration validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from automation.browser_launcher import (
    DEFAULT_PROFILE_REL,
    launch_controlled_chrome,
    resolve_chrome_executable,
    resolve_runway_browser_config,
)
from ui.api.main import app


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    _ = include_regressions
    results: list[dict] = []
    root = Path(project_root).resolve()

    launcher_path = root / "automation" / "browser_launcher.py"
    results.append(_pass("browser_launcher_module_exists", launcher_path.is_file(), str(launcher_path)))

    main_src = (root / "ui" / "api" / "main.py").read_text(encoding="utf-8")
    results.append(
        _pass(
            "api_routes_registered",
            "/operations/browser/launch" in main_src and "/operations/browser/status" in main_src,
        )
    )

    panel_src = (root / "ui" / "web" / "src" / "components" / "RunwayBrowserPanel.tsx").read_text(
        encoding="utf-8"
    )
    results.append(
        _pass(
            "ui_open_runway_browser_button",
            "Open Runway Browser" in panel_src and "Runway Login Detected" in panel_src,
        )
    )

    app_src = (root / "ui" / "app.py").read_text(encoding="utf-8")
    results.append(
        _pass(
            "tk_app_delegates_launcher",
            "launch_controlled_chrome" in app_src and "chrome.exe" not in app_src.split("open_ai_browser")[1][:400],
        )
    )

    config = resolve_runway_browser_config(root)
    results.append(
        _pass(
            "canonical_profile_path",
            config["profile_path_relative"] == DEFAULT_PROFILE_REL
            and str(config["profile_path"]).endswith("real_chrome_profile"),
            str(config["profile_path"]),
        )
    )

    try:
        chrome = resolve_chrome_executable()
        edge_blocked = "msedge" not in chrome.name.lower()
    except FileNotFoundError as exc:
        chrome = None
        edge_blocked = "Edge is not supported" in str(exc) or "Chrome not found" in str(exc)
    results.append(
        _pass(
            "chrome_only_no_edge_fallback",
            edge_blocked,
            str(chrome) if chrome else "chrome missing on host (acceptable in CI)",
        )
    )

    with patch("automation.browser_launcher.is_cdp_reachable", return_value=False), patch(
        "automation.browser_launcher.subprocess.Popen"
    ) as mock_popen:
        mock_popen.return_value.pid = 4242
        launch_result = launch_controlled_chrome(root)
    results.append(
        _pass(
            "launch_uses_controlled_profile",
            launch_result.get("success")
            and "real_chrome_profile" in str(launch_result.get("profile_path")),
            json.dumps({k: launch_result[k] for k in launch_result if k != "profile_path"}, ensure_ascii=False),
        )
    )

    client = TestClient(app)
    status_resp = client.get("/operations/browser/status")
    results.append(
        _pass(
            "get_browser_status_200",
            status_resp.status_code == 200
            and "browser_running" in status_resp.json()
            and "runway_login_detected" in status_resp.json(),
            str(status_resp.status_code),
        )
    )

    with patch("automation.browser_launcher.launch_controlled_chrome") as mock_launch:
        mock_launch.return_value = {
            "success": True,
            "already_running": True,
            "message": "mock",
            "profile_path": str(root / "storage" / "real_chrome_profile"),
            "cdp_url": "http://127.0.0.1:9222",
            "cdp_port": 9222,
        }
        launch_resp = client.post("/operations/browser/launch")
    results.append(
        _pass(
            "post_browser_launch_200",
            launch_resp.status_code == 200 and launch_resp.json().get("success"),
            str(launch_resp.status_code),
        )
    )

    from project_brain.validation_policy import summarize_validation_report

    return summarize_validation_report(
        phase="12I-A",
        label="runway_browser_launcher",
        results=results,
        include_regressions=False,
    )


def main(argv: list[str] | None = None) -> int:
    from project_brain.validation_policy import (
        parse_include_regressions,
        print_validation_summary,
        validation_exit_code,
    )

    include_regressions = parse_include_regressions(argv)
    report = run_matrix(include_regressions=include_regressions)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print_validation_summary(report)
    return validation_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
