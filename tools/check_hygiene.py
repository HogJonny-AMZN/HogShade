"""
HogShade: the hygiene check, mechanised: no studio identifier in any tracked file outside the allowlist.
Package: tools/check_hygiene

The rule (ADR-008): nothing in this repository names the owner's employer or a studio codebase. The
identifiers live in this one file so that every document can say "run the hygiene check" without
repeating them, which would make the grep flag the document (Copilot on PR #25). The allowlist names
the tracked files that may carry a match and why; a match anywhere else is a finding.

Run standalone (exit code 1 on findings)::

    uv run python tools/check_hygiene.py

CI runs it as a step; ``tests/test_check_hygiene.py`` runs it on the tree and on fixtures.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_MODULE_NAME = "tools.check_hygiene"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The identifiers, case-insensitive. Kept here and nowhere else.
PATTERN = re.compile("bluepoint|sony|bp_py|bp_color", re.IGNORECASE)

#: Tracked paths (repo-relative, POSIX) that may carry a match, and the reason each may.
ALLOWLIST: dict[str, str] = {
    "tools/check_hygiene.py": "holds the pattern",
    "tests/test_check_hygiene.py": "tests the pattern",
    "Docs/ROADMAP.md": "track A, the clearance conversation, names what is being cleared",
    "Docs/plan/BOARD.md": "gate G1 and its Icebox row describe the clearance work",
    "Docs/reviews/2026-09-27-standards-pass-project-review.md": "records the profile finding below",
    "tools/bats/orchestrator_config_hogshade.json": "a path from the dev checkout's canon config; the owner's call under G1",
}

#: Path prefixes outside the corpus: the legacy shaders are a frozen record.
EXCLUDED_PREFIXES = ("legacy/",)


@dataclass(frozen=True)
class Match:
    path: str
    line: int
    text: str


def tracked_matches(root: Path = REPO_ROOT) -> list[Match]:
    """Every match in a git-tracked text file, via ``git grep`` so untracked scratch never counts."""
    proc = subprocess.run(
        ["git", "grep", "-n", "-I", "-i", "-E", PATTERN.pattern, "--", "."],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode not in (0, 1):  # 1 is "no match"
        raise RuntimeError(f"git grep failed in {root}: {proc.stderr.strip()}")
    out: list[Match] = []
    for raw in proc.stdout.splitlines():
        path, line, text = raw.split(":", 2)
        out.append(Match(path.replace("\\", "/"), int(line), text.strip()))
    return out


def findings(matches: list[Match], allowlist: dict[str, str] = ALLOWLIST) -> list[Match]:
    """The matches that are neither excluded nor allowlisted."""
    return [m for m in matches if not m.path.startswith(EXCLUDED_PREFIXES) and m.path not in allowlist]


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else REPO_ROOT
    matches = tracked_matches(root)
    bad = findings(matches)
    allowed = [m for m in matches if m.path in ALLOWLIST]
    for m in bad:
        print(f"[hygiene] {m.path}:{m.line}: {m.text[:100]}")
    for path in sorted({m.path for m in allowed}):
        print(f"[allowed] {path}: {ALLOWLIST[path]}")
    if bad:
        print(f"hygiene check: {len(bad)} finding(s)")
        return 1
    print(f"hygiene check: clean ({len(allowed)} allowlisted match(es))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
