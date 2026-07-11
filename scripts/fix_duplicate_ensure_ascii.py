#!/usr/bin/env python3
"""Remove duplicate ensure_ascii keyword arguments introduced by bulk patch."""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {".git", "venv", "node_modules", "external", "dist", "chrome_mapper_profile", "__pycache__"}

REPLACEMENTS = [
    # json.dumps(..., **options, ensure_ascii=False) when options already sets it
    (re.compile(r"json\.dumps\(data, \*\*options, ensure_ascii=False\)"), "json.dumps(data, **options)"),
    # write_text(..., encoding="utf-8") — invalid kwarg on write_text
    (re.compile(r'(write_text\([^)]+encoding="utf-8"), ensure_ascii=False\)'), r"\1)"),
    # print(json.dumps(...))
    (re.compile(r"(print\(json\.dumps\([^)]+\)), ensure_ascii=False\)"), r"\1)"),
    # json.dumps(..., ensure_ascii=False, ..., ) on one line
    (
        re.compile(r"(json\.dumps\([^)]*?)ensure_ascii=(?:False|True),\s*([^)]*?)ensure_ascii=(?:False|True)"),
        r"\1ensure_ascii=False, \2",
    ),
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fixed: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        original = path.read_text(encoding="utf-8")
        text = original
        for pattern, replacement in REPLACEMENTS:
            text = pattern.sub(replacement, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            fixed.append(str(path.relative_to(root)))
    for item in fixed:
        print(item)
    print(f"fixed {len(fixed)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
