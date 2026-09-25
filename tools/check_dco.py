#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DCO check: every commit in a pull request must carry a `Signed-off-by:` trailer.

The Developer Certificate of Origin is how a project without a CLA knows a contributor was
allowed to contribute what they sent. Enforcing it here (rather than via a bot) keeps the check
visible and auditable, and lets a fork run it without installing anything.

    python tools/check_dco.py --base <sha>            # base..HEAD, the PR's commits
    python tools/check_dco.py --range HEAD~3..HEAD
    python tools/check_dco.py --commit <sha>

Rules applied (the strict-but-fair subset):
  * a `Signed-off-by: Name <email>` trailer must exist;
  * its email must match the commit author email (case-insensitive), so a sign-off cannot be
    borrowed from someone else;
  * merge commits are skipped (they carry other people's sign-offs).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

SOB = re.compile(r"^Signed-off-by:\s*(?P<name>[^<]*?)\s*<(?P<email>[^>]+)>\s*$", re.MULTILINE)
FORMAT = "%H%x1f%an%x1f%ae%x1f%P%x1f%B%x1e"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def commits(rev_range: str) -> list[dict[str, str]]:
    raw = git("log", f"--format={FORMAT}", rev_range)
    out = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        sha, an, ae, parents, body = record.split("\x1f")
        out.append(
            {
                "sha": sha,
                "author": an,
                "author_email": ae,
                "parents": parents.split(),
                "body": body,
            }
        )
    return out


def check(commits_: list[dict[str, str]]) -> list[str]:
    problems = []
    for c in commits_:
        short = c["sha"][:9]
        if len(c.get("parents", [])) > 1:  # merge commit: carries no sign-off of its own
            continue
        signs = [m.group("email").lower() for m in SOB.finditer(c["body"])]
        if not signs:
            problems.append(f"{short}  no Signed-off-by trailer (fix: git commit --amend -s)")
            continue
        if c["author_email"].lower() not in signs:
            problems.append(
                f"{short}  signed off as {signs[0]!r} but authored by "
                f"{c['author_email']!r} - sign-offs must come from the author"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--base", help="base SHA; checks base..HEAD (what a PR contains)")
    group.add_argument("--range", dest="rev_range", help="any git rev range")
    group.add_argument("--commit", help="a single commit")
    ap.add_argument("--head", default="HEAD", help="defaults to HEAD")
    args = ap.parse_args(argv)

    if args.commit:
        rev_range = f"{args.commit}~1..{args.commit}" if args.commit not in ("",) else args.head
    elif args.rev_range:
        rev_range = args.rev_range
    elif args.base:
        rev_range = f"{args.base}..{args.head}"
    else:
        print("nothing to check: pass --base, --range or --commit", file=sys.stderr)
        return 2

    todo = commits(rev_range)
    if not todo:
        print("no commits in range - nothing to check")
        return 0

    problems = check(todo)
    if problems:
        print(
            f"{len(problems)} of {len(todo)} commits are not signed off (see CONTRIBUTING.md, DCO):",
            file=sys.stderr,
        )
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print(
            "\n  re-sign everything in the branch:\n"
            "    git rebase --exec 'git commit --amend --no-edit -s' <base>\n",
            file=sys.stderr,
        )
        return 1

    print(f"{len(todo)} commits signed off")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
