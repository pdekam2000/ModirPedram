"""
Phase 11X-1 — ElevenLabs env loading diagnostic (no secrets, no TTS).

Run: python -m project_brain.diagnose_elevenlabs_env_loading
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.env_bootstrap import bootstrap_project_env, detect_project_root
from providers.elevenlabs_config import API_KEY_ENV, ElevenLabsConfigResolver

PROJECT_ROOT = detect_project_root()


def _env_file_has_nonempty_key(env_path: Path, key: str = API_KEY_ENV) -> bool:
    if not env_path.is_file():
        return False
    prefix = f"{key}="
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(prefix):
            return bool(line[len(prefix) :].strip().strip('"').strip("'"))
    return False


def diagnose() -> dict[str, Any]:
    cwd = Path.cwd().resolve()
    env_path = PROJECT_ROOT / ".env"
    bootstrap = bootstrap_project_env(project_root=PROJECT_ROOT)

    resolver = ElevenLabsConfigResolver(PROJECT_ROOT)
    config = resolver.resolve({})

    return {
        "cwd": str(cwd),
        "project_root_detected": str(PROJECT_ROOT),
        "cwd_is_project_root": cwd == PROJECT_ROOT,
        "env_bootstrap": bootstrap,
        "env_file_contains_elevenlabs_key": _env_file_has_nonempty_key(env_path),
        "elevenlabs_api_key_in_os_environ": bool(os.getenv(API_KEY_ENV, "").strip()),
        "elevenlabs_config_resolver_has_api_key": config.has_api_key,
        "config_summary_safe": config.to_summary(),
    }


def _print_safe(result: dict[str, Any]) -> None:
    bootstrap = dict(result.get("env_bootstrap") or {})
    output = {
        "cwd": result["cwd"],
        "project_root_detected": result["project_root_detected"],
        "env_file_found": bootstrap.get("env_found"),
        "env_file_contains_elevenlabs_key": result["env_file_contains_elevenlabs_key"],
        "python_dotenv_available": bootstrap.get("dotenv_available"),
        "env_bootstrap_loaded": bootstrap.get("loaded"),
        "ELEVENLABS_API_KEY_in_os_environ": result["elevenlabs_api_key_in_os_environ"],
        "ElevenLabsConfigResolver_has_api_key": result["elevenlabs_config_resolver_has_api_key"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def _infer_cause(result: dict[str, Any]) -> str:
    bootstrap = dict(result.get("env_bootstrap") or {})
    if not bootstrap.get("env_found"):
        return "Project root `.env` file not found."
    if not result["env_file_contains_elevenlabs_key"]:
        return "`.env` exists but ELEVENLABS_API_KEY is missing or empty."
    if not bootstrap.get("dotenv_available"):
        return (
            "`.env` contains ELEVENLABS_API_KEY but python-dotenv is not installed. "
            "Run: pip install -r requirements.txt"
        )
    if not bootstrap.get("loaded"):
        return "python-dotenv is available but `.env` was not loaded."
    if not result["elevenlabs_api_key_in_os_environ"]:
        return "`.env` loaded but ELEVENLABS_API_KEY is not in os.environ."
    if not result["elevenlabs_config_resolver_has_api_key"]:
        return "Key is in os.environ but ElevenLabsConfigResolver still reports has_api_key=false."
    return "Env bootstrap succeeded; ElevenLabs preflight should see credentials."


def _recommended_fix(result: dict[str, Any]) -> str:
    bootstrap = dict(result.get("env_bootstrap") or {})
    if not bootstrap.get("dotenv_available"):
        return "Install dependencies: pip install -r requirements.txt"
    if not bootstrap.get("loaded"):
        return "Ensure `.env` exists at project root and call bootstrap_project_env() before preflight."
    if result["elevenlabs_config_resolver_has_api_key"]:
        return "No further env bootstrap changes required for runners using core.env_bootstrap."
    return "Verify ELEVENLABS_API_KEY is set in project `.env`."


def write_report(result: dict[str, Any], *, dry_run_rerun: dict[str, Any] | None = None) -> Path:
    report_path = PROJECT_ROOT / "project_brain" / "PHASE_11X1_ELEVENLABS_ENV_LOADING_DIAGNOSTIC_REPORT.md"
    cause = _infer_cause(result)
    fix = _recommended_fix(result)
    bootstrap = dict(result.get("env_bootstrap") or {})

    lines = [
        "# Phase 11X-1 — ElevenLabs Env Loading Diagnostic Report",
        "",
        "**Scope:** Diagnostic only — no live TTS, no paid API, no secret values logged.",
        "",
        "## Env Bootstrap",
        "",
        "```json",
        json.dumps(bootstrap, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Diagnostic Output",
        "",
        "| Check | Result |",
        "|-------|--------|",
        f"| cwd | `{result['cwd']}` |",
        f"| project root detected | `{result['project_root_detected']}` |",
        f"| `.env` found | `{bootstrap.get('env_found')}` |",
        f"| `.env` contains ELEVENLABS_API_KEY (non-empty) | `{result['env_file_contains_elevenlabs_key']}` |",
        f"| python-dotenv available | `{bootstrap.get('dotenv_available')}` |",
        f"| bootstrap loaded | `{bootstrap.get('loaded')}` |",
        f"| ELEVENLABS_API_KEY in os.environ | `{result['elevenlabs_api_key_in_os_environ']}` |",
        f"| ElevenLabsConfigResolver has_api_key | `{result['elevenlabs_config_resolver_has_api_key']}` |",
        "",
        "## Cause",
        "",
        cause,
        "",
        "## Recommended Fix",
        "",
        fix,
        "",
        "## Safety Confirmations",
        "",
        "| Item | Status |",
        "|------|--------|",
        "| API key value printed | **No** |",
        "| Live TTS executed | **No** |",
        "| Paid ElevenLabs API call | **No** |",
        "",
    ]

    if dry_run_rerun is not None:
        lines.extend(
            [
                "## 11X Dry Run Re-run",
                "",
                f"- **Executed:** `{dry_run_rerun.get('executed')}`",
                f"- **Exit code:** `{dry_run_rerun.get('exit_code')}`",
                f"- **Reason skipped:** `{dry_run_rerun.get('reason_skipped', '')}`",
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    result = diagnose()
    _print_safe(result)

    dry_run_rerun: dict[str, Any] | None = None
    if result["elevenlabs_config_resolver_has_api_key"]:
        proc = subprocess.run(
            [sys.executable, "-m", "project_brain.run_11x_end_to_end_topic_to_voice_dry_run"],
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        dry_run_rerun = {
            "executed": True,
            "exit_code": proc.returncode,
        }
    else:
        dry_run_rerun = {
            "executed": False,
            "exit_code": None,
            "reason_skipped": "ElevenLabsConfigResolver has_api_key=false after bootstrap",
        }

    report_path = write_report(result, dry_run_rerun=dry_run_rerun)
    print(f"\nReport: {report_path}")

    if dry_run_rerun.get("executed"):
        print(f"Dry run re-run exit code: {dry_run_rerun['exit_code']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
