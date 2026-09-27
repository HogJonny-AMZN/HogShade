"""
HogShade: tools/check_hygiene.py on fixtures and on the tree.
Package: tests/test_check_hygiene
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_hygiene


def test_allowlisted_and_legacy_matches_are_not_findings() -> None:
    matches = [
        check_hygiene.Match("legacy/v2.0/some.fx", 1, "x"),
        check_hygiene.Match("Docs/ROADMAP.md", 44, "x"),
        check_hygiene.Match("hogshade/new.py", 3, "x"),
    ]
    assert [m.path for m in check_hygiene.findings(matches)] == ["hogshade/new.py"]


def test_the_pattern_is_case_insensitive_and_matches_each_identifier() -> None:
    for word in ("bluepoint", "SONY", "Bp_Py", "bp_color"):
        assert check_hygiene.PATTERN.search(f"x {word} y")
    assert not check_hygiene.PATTERN.search("hogshade sprite jammer large worlds")


def test_the_tree_is_clean() -> None:
    bad = check_hygiene.findings(check_hygiene.tracked_matches(ROOT))
    assert bad == [], "\n".join(f"{m.path}:{m.line}: {m.text}" for m in bad)


def test_every_allowlisted_path_still_carries_a_match_or_is_the_tool() -> None:
    """An allowlist entry that matches nothing is stale and should go."""
    present = {m.path for m in check_hygiene.tracked_matches(ROOT)}
    for path in check_hygiene.ALLOWLIST:
        assert path in present or path.startswith(("tools/", "tests/")), path
