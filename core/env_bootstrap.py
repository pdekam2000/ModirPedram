"""
Central project `.env` bootstrap for CLI runners and diagnostics.

Never prints or returns secret values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

ENV_BOOTSTRAP_VERSION = "11x1b_v1"
ENV_FILENAME = ".env"


class EnvBootstrapError(RuntimeError):
    """Raised when env bootstrap cannot proceed safely."""


def detect_project_root(start: Path | str | None = None) -> Path:
    """
    Resolve ModirAgentOS project root.

    Walks upward from `start`, cwd, or this module's parent directory.
    """
    seeds: list[Path] = []
    if start is not None:
        seeds.append(Path(start))
    seeds.append(Path.cwd())
    seeds.append(Path(__file__).resolve().parent.parent)

    seen: set[Path] = set()
    for seed in seeds:
        current = seed.resolve()
        for _ in range(8):
            if current in seen:
                break
            seen.add(current)
            if _is_project_root(current):
                return current
            if current.parent == current:
                break
            current = current.parent

    return Path(__file__).resolve().parent.parent


def _is_project_root(path: Path) -> bool:
    return (
        (path / "project_brain").is_dir()
        and (path / "requirements.txt").is_file()
        and (path / "core").is_dir()
    )


def bootstrap_project_env(
    *,
    project_root: Path | str | None = None,
    require_dotenv: bool = False,
) -> dict[str, Any]:
    """
    Load project `.env` into os.environ when python-dotenv is available.

    Returns a safe summary only — never includes secret values.
    """
    root = detect_project_root(project_root)
    env_path = root / ENV_FILENAME
    env_found = env_path.is_file()

    try:
        from dotenv import load_dotenv
    except ImportError:
        if require_dotenv:
            raise EnvBootstrapError(
                "python-dotenv is not installed. Install project dependencies: "
                "pip install -r requirements.txt"
            ) from None
        return {
            "project_root": str(root),
            "env_found": env_found,
            "dotenv_available": False,
            "loaded": False,
        }

    loaded = bool(load_dotenv(env_path, override=False)) if env_found else False
    return {
        "project_root": str(root),
        "env_found": env_found,
        "dotenv_available": True,
        "loaded": loaded,
    }


__all__ = [
    "ENV_BOOTSTRAP_VERSION",
    "EnvBootstrapError",
    "detect_project_root",
    "bootstrap_project_env",
]
