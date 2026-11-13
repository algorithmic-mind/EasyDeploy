"""Fail if Python sources use shell execution (§10.2).

Usage: python scripts/check_no_shell.py [files...]   (no args: scan backend, agent, cli)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOTS = ("backend", "agent", "cli")
BANNED_CALLS = {("os", "system"), ("os", "popen"), ("os", "execl"), ("os", "execlp")}


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: syntax error"]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and (func.value.id, func.attr) in BANNED_CALLS
        ):
            problems.append(f"{path}:{node.lineno}: {func.value.id}.{func.attr}() is forbidden")
        for kw in node.keywords:
            if kw.arg == "shell" and not (
                isinstance(kw.value, ast.Constant) and kw.value.value is False
            ):
                problems.append(f"{path}:{node.lineno}: shell=... must be False or absent")
    return problems


def main(argv: list[str]) -> int:
    if argv:
        files = [Path(a) for a in argv if a.endswith(".py")]
    else:
        files = [p for root in ROOTS for p in Path(root).rglob("*.py") if ".venv" not in p.parts]
    problems = [msg for f in files for msg in check_file(f)]
    for msg in problems:
        print(msg)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
