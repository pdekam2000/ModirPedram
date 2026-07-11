#!/usr/bin/env python3
"""Add ensure_ascii=False to json.dump/json.dumps calls missing it."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git",
    "venv",
    "node_modules",
    "external",
    "dist",
    "chrome_mapper_profile",
    "__pycache__",
    ".cursor",
}

CALL_PATTERN = re.compile(r"json\.dumps?\(")


def _find_call_end(text: str, start: int) -> int | None:
    depth = 0
    in_string: str | None = None
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == in_string:
                in_string = None
            continue
        if char in {"'", '"'}:
            in_string = char
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def patch_content(content: str) -> tuple[str, int]:
    changed = 0
    text = content
    search_from = 0
    while True:
        match = CALL_PATTERN.search(text, search_from)
        if not match:
            break
        start = match.start()
        end = _find_call_end(text, match.end() - 1)
        if end is None:
            search_from = match.end()
            continue
        call = text[start : end + 1]
        if "ensure_ascii" in call:
            search_from = end + 1
            continue
        paren = call.find("(")
        if paren < 0:
            search_from = match.end()
            continue
        inner = call[paren + 1 : -1].rstrip()
        if not inner:
            replacement = call[:-1] + "ensure_ascii=False)"
        else:
            replacement = call[:-1] + ", ensure_ascii=False)"
        text = text[:start] + replacement + text[end + 1 :]
        changed += 1
        search_from = start + len(replacement)
    return text, changed


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    total_files = 0
    total_calls = 0
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == "fix_json_ensure_ascii.py":
            continue
        original = path.read_text(encoding="utf-8")
        if "json.dump" not in original:
            continue
        patched, count = patch_content(original)
        if count:
            path.write_text(patched, encoding="utf-8")
            total_files += 1
            total_calls += count
            print(f"{path.relative_to(root)}: {count}")
    print(f"patched {total_calls} calls in {total_files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
