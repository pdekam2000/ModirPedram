"""
Validation policy helpers — core-only by default; avoid nested long regression chains.

Phase validators should test their own logic by default. Full regression sweeps run
separately, one command at a time, not recursively inside every validator.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REGRESSION_TEST_SUFFIX = "_regression"


def is_regression_test(test_name: str) -> bool:
    """True for nested validator reruns (not core phase logic)."""
    name = str(test_name or "")
    if name.endswith(REGRESSION_TEST_SUFFIX):
        return True
    if name.startswith("validator_") and name.endswith("_still_passes"):
        return True
    return False


def parse_include_regressions(argv: list[str] | None = None) -> bool:
    """
    Parse --full / --core-only from argv.

    Default: core-only (include_regressions=False).
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include nested regression validators (slow; run separately when possible)",
    )
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Core phase tests only (default)",
    )
    args, _ = parser.parse_known_args(argv)
    return bool(args.full)


def run_validator_module(module: str, *, core_only: bool = True, cwd: Path | None = None) -> bool:
    """Invoke another validator module; prefer core-only to avoid deep nesting."""
    cmd = [sys.executable, "-m", module]
    if core_only:
        cmd.append("--core-only")
    else:
        cmd.append("--full")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd or Path(".").resolve()),
    )
    return result.returncode == 0


def split_core_regression(results: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    core = [item for item in results if not is_regression_test(item.get("test", ""))]
    regression = [item for item in results if is_regression_test(item.get("test", ""))]
    return core, regression


def summarize_validation_report(
    *,
    phase: str,
    label: str,
    results: list[dict[str, Any]],
    include_regressions: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    core_results, regression_results = split_core_regression(results)
    core_passed = sum(1 for item in core_results if item.get("pass"))
    regression_passed = sum(1 for item in regression_results if item.get("pass"))

    payload: dict[str, Any] = {
        "phase": phase,
        "label": label,
        "mode": "full" if include_regressions else "core_only",
        "include_regressions": include_regressions,
        "passed": sum(1 for item in results if item.get("pass")),
        "total": len(results),
        "all_pass": all(item.get("pass") for item in results),
        "core": {
            "passed": core_passed,
            "total": len(core_results),
            "all_pass": core_passed == len(core_results) if core_results else True,
        },
        "regression": {
            "passed": regression_passed,
            "total": len(regression_results),
            "all_pass": regression_passed == len(regression_results) if regression_results else True,
            "skipped": not include_regressions,
        },
        "acceptance_status": "ACCEPTED" if core_passed == len(core_results) else "REJECTED",
        "results": results,
    }
    if extra:
        payload.update(extra)
    return payload


def validation_exit_code(report: dict[str, Any]) -> int:
    """
    Exit 0 when core passes (default acceptance).
    With --full, also require regression slice to pass.
    """
    core = report.get("core") or {}
    if not core.get("all_pass", False):
        return 1
    if report.get("include_regressions") and not (report.get("regression") or {}).get("all_pass", True):
        return 1
    return 0


def print_validation_summary(report: dict[str, Any]) -> None:
    core = report.get("core") or {}
    regression = report.get("regression") or {}
    mode = report.get("mode", "core_only")

    print(f"\nMode: {mode}")
    print(f"CORE: {core.get('passed', 0)}/{core.get('total', 0)} PASS — {report.get('acceptance_status', 'UNKNOWN')}")
    if regression.get("skipped"):
        print("REGRESSION: SKIPPED (use --full to include nested regressions)")
    else:
        reg_status = "PASS" if regression.get("all_pass") else "FAIL"
        print(f"REGRESSION: {regression.get('passed', 0)}/{regression.get('total', 0)} {reg_status}")

    for item in report.get("results") or []:
        mark = "PASS" if item.get("pass") else "FAIL"
        tier = "REGRESSION" if is_regression_test(item.get("test", "")) else "CORE"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] [{tier}] {item.get('test')}{detail}")

    print(f"\nOverall: {report.get('passed', 0)}/{report.get('total', 0)} PASS")


__all__ = [
    "REGRESSION_TEST_SUFFIX",
    "is_regression_test",
    "parse_include_regressions",
    "run_validator_module",
    "split_core_regression",
    "summarize_validation_report",
    "validation_exit_code",
    "print_validation_summary",
]
