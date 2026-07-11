#!/usr/bin/env python3
"""Report json.dump(s) calls with duplicate ensure_ascii keywords."""

from __future__ import annotations

import ast
from pathlib import Path

SKIP = {".git", "venv", "node_modules", "external", "dist", "__pycache__"}


class EnsureAsciiCounter(ast.NodeVisitor):
    def __init__(self) -> None:
        self.issues: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "json":
            if func.attr in {"dump", "dumps"}:
                count = sum(
                    1
                    for kw in node.keywords
                    if kw.arg == "ensure_ascii"
                )
                if count > 1:
                    self.issues.append((node.lineno, ast.get_source_segment("", node) or "json call"))
        self.generic_visit(node)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP for part in path.parts):
            continue
        source = path.read_text(encoding="utf-8")
        if "ensure_ascii" not in source:
            continue
        if ", encoding=\"utf-8\", ensure_ascii=False)" in source:
            problems.append(f"{path}: write_text trailing ensure_ascii")
        if "), ensure_ascii=False)" in source and "print(json.dumps" in source:
            for i, line in enumerate(source.splitlines(), 1):
                if "print(json.dumps" in line and "), ensure_ascii=False)" in line:
                    problems.append(f"{path}:{i}: print trailing ensure_ascii")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        counter = EnsureAsciiCounter()
        counter.visit(tree)
        for lineno, _ in counter.issues:
            problems.append(f"{path}:{lineno}: duplicate ensure_ascii in json.dump(s)")
    if problems:
        print("\n".join(problems))
        return 1
    print("no duplicate ensure_ascii issues found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
