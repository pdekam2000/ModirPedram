"""UTF-8 safe JSON persistence — always preserve Unicode characters in files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _latin1_mojibake(char: str) -> str:
    return char.encode("utf-8").decode("latin-1")


MOJIBAKE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (_latin1_mojibake("—"), "—"),
    (_latin1_mojibake("–"), "–"),
    (_latin1_mojibake("\u2019"), "'"),
    (_latin1_mojibake("\u2018"), "'"),
    (_latin1_mojibake("\u201c"), '"'),
    (_latin1_mojibake("\u201d"), '"'),
)


def repair_mojibake_text(value: Any) -> Any:
    """Fix common UTF-8-as-Latin-1 mojibake in strings and nested JSON structures."""
    if isinstance(value, str):
        text = value
        for bad, good in MOJIBAKE_REPLACEMENTS:
            text = text.replace(bad, good)
        return text
    if isinstance(value, dict):
        return {key: repair_mojibake_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [repair_mojibake_text(item) for item in value]
    return value


def dumps_json(data: Any, *, indent: int | None = 2, **kwargs: Any) -> str:
    options = {"ensure_ascii": False, **kwargs}
    if indent is not None and "indent" not in options:
        options["indent"] = indent
    return json.dumps(data, **options)


def dump_json(path: str | Path, data: Any, *, indent: int | None = 2, **kwargs: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps_json(data, indent=indent, **kwargs), encoding="utf-8")
    return target


def load_json(path: str | Path, *, default: Any = None, repair: bool = True) -> Any:
    target = Path(path)
    if not target.is_file():
        return default
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return repair_mojibake_text(payload) if repair else payload


__all__ = [
    "MOJIBAKE_REPLACEMENTS",
    "dump_json",
    "dumps_json",
    "load_json",
    "repair_mojibake_text",
]
