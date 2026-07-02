#!/usr/bin/env python3
"""I11 gate: donor repos must be bit-identical to their Stage-0 state.

Checks, for each donor pinned in scripts/donor_pins.json:
  1. the donor directory exists and is a git repo,
  2. `git status --porcelain` is empty (no created/modified/deleted files,
     including untracked strays such as caches we might have dropped),
  3. `HEAD` equals the pinned Stage-0 SHA.

Exit code 0 iff every check passes. Run before every commit (installed as
.git/hooks/pre-commit; also invoked explicitly at every stage gate).
Cross-platform: pathlib + subprocess only, no shell.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PINS_FILE = REPO_ROOT / "scripts" / "donor_pins.json"


def _git(donor: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(donor), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    pins = json.loads(PINS_FILE.read_text(encoding="utf-8"))
    failures: list[str] = []

    for name, info in pins["donors"].items():
        donor = (REPO_ROOT / info["path"]).resolve()
        if not donor.is_dir():
            failures.append(f"{name}: donor directory missing at {donor}")
            continue

        head = _git(donor, "rev-parse", "HEAD")
        if head.returncode != 0:
            failures.append(f"{name}: git rev-parse failed: {head.stderr.strip()}")
        elif head.stdout.strip() != info["sha"]:
            failures.append(
                f"{name}: HEAD {head.stdout.strip()} != pinned {info['sha']}"
            )

        status = _git(donor, "status", "--porcelain")
        if status.returncode != 0:
            failures.append(f"{name}: git status failed: {status.stderr.strip()}")
        elif status.stdout.strip():
            failures.append(
                f"{name}: working tree not clean:\n{status.stdout.rstrip()}"
            )

    if failures:
        print("I11 GATE FAIL — donor repos must stay untouched:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("I11 gate: donors clean and pinned OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
