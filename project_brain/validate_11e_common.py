"""Shared helpers for Phase 11E validation scripts."""

from __future__ import annotations

import os
from collections.abc import Callable

from project_brain.validate_registry_cleanup import cleanup_validation_registry


def matrix_child() -> bool:
    """True when invoked by validate_11e_matrix (nested regressions run once at matrix level)."""
    return os.environ.get("VALIDATE_11E_MATRIX") == "1"


def append_regression_checks(
    results: list[dict],
    _pass: Callable[..., dict],
    _run_module: Callable[[str], bool],
    checks: list[tuple[str, str]],
) -> None:
    if matrix_child():
        for name, _module in checks:
            results.append(_pass(name, True, "deferred to validate_11e_matrix"))
        return
    for name, module in checks:
        cleanup_validation_registry()
        ok = _run_module(module)
        cleanup_validation_registry()
        results.append(_pass(name, ok))


__all__ = ["matrix_child", "append_regression_checks"]
