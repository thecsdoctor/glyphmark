#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check that every source file declares its licence with an SPDX header.

Why this exists: a repo that asks to be reviewed as a foundation-grade project has to answer
"what licence applies to this file?" without a lawyer guessing. A single LICENSE file answers it
for the whole tree, but only for people who look at the root - per-file SPDX identifiers survive
vendoring, copying and license scanners.

    python tools/check_license_headers.py            # exit 1 listing offenders
    python tools/check_license_headers.py --fix      # insert the header where missing

Scope is deliberately source code, not prose: Python, JavaScript/CSS shipped to the browser, and
the Jinja templates. Markdown, YAML and config files are covered by LICENSE + NOTICE.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: filename suffix -> (comment form, where to put it)
HEADER_FOR = {
    ".py": "# SPDX-License-Identifier: MIT",
    ".mjs": "/* SPDX-License-Identifier: MIT */",
    ".js": "/* SPDX-License-Identifier: MIT */",
    ".cjs": "/* SPDX-License-Identifier: MIT */",
    ".css": "/* SPDX-License-Identifier: MIT */",
}
HTML_HEADER = "<!-- SPDX-License-Identifier: MIT -->"

#: Files that legitimately carry no header (generated, vendored, or third-party).
EXEMPT: tuple[str, ...] = ()

PATTERNS = ("*.py", "*.js", "*.mjs", "*.cjs", "*.css", "*.html")


def tracked_files() -> list[Path]:
    """Source files under version control, so generated and ignored trees are skipped."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", *PATTERNS],
        capture_output=True,
        check=True,
        text=True,
    )
    return [REPO / p for p in out.stdout.split("\0") if p]


def has_header(text: str) -> bool:
    head = "\n".join(text.splitlines()[:12])
    return bool(re.search(r"SPDX[- ]L[i]cense[- ]I[dD]entifier\s*:\s*MIT", head))


def insert_header(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        # Keep <!DOCTYPE html> first: a comment before the doctype is tolerated by modern
        # browsers but can flip legacy rendering modes, so the header goes after it.
        lines = text.splitlines(keepends=True)
        header = HTML_HEADER + "\n"
        for i, line in enumerate(lines):
            if line.lstrip().lower().startswith("<!doctype"):
                lines.insert(i + 1, header)
                break
        else:
            lines.insert(0, header)
        path.write_text("".join(lines), encoding="utf-8")
        return

    header = HEADER_FOR[path.suffix] + "\n"
    lines = text.splitlines(keepends=True)
    at = 0
    if lines and lines[0].startswith("#!"):  # keep any shebang first
        at = 1
    lines.insert(at, header)
    path.write_text("".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fix", action="store_true", help="insert missing headers instead of failing")
    ap.add_argument("--list", action="store_true", help="print every checked file")
    args = ap.parse_args(argv)

    missing: list[Path] = []
    checked = 0
    for path in tracked_files():
        rel = str(path.relative_to(REPO))
        if rel in EXEMPT:
            continue
        checked += 1
        if args.list:
            print(rel)
        if has_header(path.read_text(encoding="utf-8")):
            continue
        if args.fix:
            insert_header(path)
            print(f"fixed  {rel}")
        else:
            missing.append(path)

    if args.fix:
        print(f"checked {checked} files")
        return 0

    if missing:
        print(
            f"{len(missing)} of {checked} source files have no SPDX licence header:",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  {path.relative_to(REPO)}", file=sys.stderr)
        print("\nfix with:  python tools/check_license_headers.py --fix", file=sys.stderr)
        return 1

    print(f"all {checked} source files declare SPDX-License-Identifier: MIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
