#!/usr/bin/env python3
"""Repair malformed ensure_ascii=False insertions from bulk patch."""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {".git", "venv", "node_modules", "external", "dist", "chrome_mapper_profile", "__pycache__"}

PATTERNS = [
    (re.compile(r"(indent\s*=\s*2),?\s*\n\s*,\s*ensure_ascii=False\)"), r"\1, ensure_ascii=False)"),
    (re.compile(r"^\s*,\s*ensure_ascii=False\),\s*$", re.MULTILINE), "                ensure_ascii=False,\n            ),"),
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fixed_files = 0
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        original = path.read_text(encoding="utf-8")
        text = original
        for pattern, replacement in PATTERNS:
            text = pattern.sub(replacement, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            fixed_files += 1
            print(path.relative_to(root))
    print(f"repaired {fixed_files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
