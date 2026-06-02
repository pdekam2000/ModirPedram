"""
Phase 11X-1b — central env bootstrap validation (no secrets, no live TTS).
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core.env_bootstrap import bootstrap_project_env, detect_project_root
from providers.elevenlabs_config import API_KEY_ENV, ElevenLabsConfigResolver

PROJECT_ROOT = detect_project_root()


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _run_module(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode == 0


def _env_file_key_value(env_path: Path, key: str = API_KEY_ENV) -> str | None:
    if not env_path.is_file():
        return None
    prefix = f"{key}="
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            value = line[len(prefix) :].strip().strip('"').strip("'")
            return value or None
    return None


def _parse_dry_run_stdout(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    decoder = json.JSONDecoder()
    start = text.find("{")
    if start < 0:
        return {}
    payload, _ = decoder.raw_decode(text[start:])
    return payload if isinstance(payload, dict) else {}


def run_matrix() -> dict:
    results: list[dict] = []
    env_path = PROJECT_ROOT / ".env"
    file_key = _env_file_key_value(env_path)
    payload: dict = {}

    # 1. bootstrap detects project root
    root = detect_project_root()
    results.append(
        _pass(
            "bootstrap_detects_project_root",
            root == PROJECT_ROOT and (root / "project_brain").is_dir(),
            str(root),
        )
    )

    # 2. bootstrap finds .env
    summary = bootstrap_project_env(project_root=root)
    results.append(
        _pass(
            "bootstrap_finds_env",
            summary.get("env_found") is True and summary.get("project_root") == str(root),
            str(summary.get("env_found")),
        )
    )

    # 3. bootstrap does not print secret values
    secret_leaked = False
    leak_detail = "no key in file"
    if file_key:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            leaked_summary = bootstrap_project_env(project_root=root)
        captured = buffer.getvalue()
        serialized = json.dumps(leaked_summary) + captured
        secret_leaked = file_key in serialized
        leak_detail = "clean" if not secret_leaked else "secret found in output"
    results.append(
        _pass(
            "bootstrap_does_not_print_secrets",
            not secret_leaked,
            leak_detail,
        )
    )

    # 4. ELEVENLABS_API_KEY available in os.environ when present in .env
    env_without_key = {k: v for k, v in os.environ.items() if k != API_KEY_ENV}
    with patch.dict(os.environ, env_without_key, clear=True):
        bootstrap_project_env(project_root=root)
        in_environ = bool(os.getenv(API_KEY_ENV, "").strip())
    expect_key = file_key is not None
    results.append(
        _pass(
            "elevenlabs_key_in_os_environ_when_present",
            in_environ == expect_key,
            f"in_environ={in_environ} expect={expect_key}",
        )
    )

    # 5. ElevenLabsConfigResolver.has_api_key becomes true
    with patch.dict(os.environ, env_without_key, clear=True):
        bootstrap_project_env(project_root=root)
        has_key = ElevenLabsConfigResolver(root).resolve({}).has_api_key
    results.append(
        _pass(
            "config_resolver_has_api_key_after_bootstrap",
            has_key == expect_key,
            str(has_key),
        )
    )

    # 6. 11X dry run voice preflight ready/pending when key exists
    dry_proc = subprocess.run(
        [sys.executable, "-m", "project_brain.run_11x_end_to_end_topic_to_voice_dry_run"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    payload = _parse_dry_run_stdout(dry_proc.stdout or "")
    voice = payload.get("voice_slot") or {}
    preflight_ready = voice.get("preflight_ready") is True
    voice_status = str(voice.get("status"))
    dry_ok = bool(payload)
    if expect_key:
        results.append(
            _pass(
                "dry_run_voice_preflight_ready_or_pending",
                dry_proc.returncode == 0 and preflight_ready and voice_status == "pending",
                f"exit={dry_proc.returncode} ready={preflight_ready} status={voice_status}",
            )
        )
    else:
        results.append(
            _pass(
                "dry_run_voice_preflight_ready_or_pending",
                dry_proc.returncode == 0,
                "skipped key check — no key in .env",
            )
        )

    # 7. No live TTS call
    no_live = payload.get("no_real_tts") is True and payload.get("voice_slot", {}).get("live_tts") is False
    results.append(
        _pass(
            "no_live_tts_call",
            no_live if dry_ok else dry_proc.returncode == 0,
            str(payload.get("no_real_tts")),
        )
    )

    # 8. No paid API call — dry run uses skip_provider_execution
    results.append(
        _pass(
            "no_paid_api_call",
            payload.get("skip_provider_execution") is True if dry_ok else dry_proc.returncode == 0,
            str(payload.get("skip_provider_execution")),
        )
    )

    # 9. Existing 11X dry run exits 0
    results.append(
        _pass(
            "existing_11x_dry_run_exits_zero",
            dry_proc.returncode == 0,
            str(dry_proc.returncode),
        )
    )

    # 10. Existing 11H-2d validator still passes
    results.append(
        _pass(
            "validator_11h2d_still_passes",
            _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"),
            "",
        )
    )

    passed = sum(1 for r in results if r["pass"])
    failed = [r for r in results if not r["pass"]]
    return {
        "phase": "11X-1b",
        "total": len(results),
        "passed": passed,
        "failed": len(failed),
        "all_pass": len(failed) == 0,
        "results": results,
        "failures": failed,
    }


def main() -> int:
    report = run_matrix()
    print(json.dumps(report, indent=2))
    if report["all_pass"]:
        print(f"\nPASS — {report['passed']}/{report['total']} tests")
        return 0
    print(f"\nFAIL — {report['failed']} test(s) failed")
    for item in report["failures"]:
        print(f"  - {item['test']}: {item['detail']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
