"""Compile gettext ``.po`` catalogs to ``.mo`` without GNU gettext (works on Windows).

Usage: python scripts/compile_messages.py [--check]
  --check  exit 1 if any .mo is missing/stale or any msgstr is empty (used by CI and tests)
"""

from __future__ import annotations

import ast
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIRS = [ROOT / "backend" / "locale"]


def parse_po(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    msgid: list[str] | None = None
    msgstr: list[str] | None = None
    current: list[str] | None = None

    def flush() -> None:
        if msgid is not None and msgstr is not None:
            entries["".join(msgid)] = "".join(msgstr)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            msgid, msgstr = [ast.literal_eval(line[6:])], None
            current = msgid
        elif line.startswith("msgstr "):
            msgstr = [ast.literal_eval(line[7:])]
            current = msgstr
        elif line.startswith('"') and current is not None:
            current.append(ast.literal_eval(line))
        else:
            raise ValueError(f"unsupported .po line: {raw!r}")
    flush()
    return entries


def build_mo(entries: dict[str, str]) -> bytes:
    keys = sorted(entries)
    ids = b""
    strs = b""
    offsets: list[tuple[int, int, int, int]] = []
    for key in keys:
        k, v = key.encode("utf-8"), entries[key].encode("utf-8")
        offsets.append((len(ids), len(k), len(strs), len(v)))
        ids += k + b"\0"
        strs += v + b"\0"
    n = len(keys)
    key_start = 7 * 4 + 16 * n
    value_start = key_start + len(ids)
    koffsets: list[int] = []
    voffsets: list[int] = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + key_start]
        voffsets += [l2, o2 + value_start]
    header = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    return (
        header
        + struct.pack(f"{len(koffsets)}i", *koffsets)
        + struct.pack(f"{len(voffsets)}i", *voffsets)
        + ids
        + strs
    )


def main(argv: list[str]) -> int:
    check = "--check" in argv
    problems: list[str] = []
    for locale_dir in LOCALE_DIRS:
        for po in sorted(locale_dir.glob("*/LC_MESSAGES/*.po")):
            entries = parse_po(po.read_text(encoding="utf-8"))
            empty = [k for k, v in entries.items() if k and not v]
            if empty:
                problems.append(f"{po}: untranslated: {empty}")
            data = build_mo(entries)
            mo = po.with_suffix(".mo")
            if check:
                if not mo.exists() or mo.read_bytes() != data:
                    problems.append(f"{mo}: stale or missing (run scripts/compile_messages.py)")
            else:
                mo.write_bytes(data)
                print(f"compiled {mo.relative_to(ROOT)} ({len(entries) - 1} messages)")
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
