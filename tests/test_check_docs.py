"""
HogShade: tests for tools/check_docs.py, on fixtures and on the corpus itself.
Package: tests/test_check_docs
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_docs


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    _write(tmp_path, "README.md", "[handoff](Docs/handoffs/CURRENT.md) [journal](Docs/journal/README.md)\n")
    _write(tmp_path, "Docs/handoffs/CURRENT.md", "# Handoff\n\n**Status:** Living\n")
    _write(
        tmp_path,
        "Docs/journal/README.md",
        "# Journal\n\n**Status:** Living\n\n| [Session 01](2026-09-27-session-01.md) |\n",
    )
    _write(tmp_path, "Docs/journal/2026-09-27-session-01.md", "# Session 01\n")
    return tmp_path


def test_clean_corpus_has_no_findings(corpus: Path) -> None:
    assert check_docs.run(corpus) == []


def test_broken_link_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/handoffs/CURRENT.md", "**Status:** Living\n\n[gone](../missing.md)\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["links"]
    assert "missing.md" in findings[0].detail


def test_link_case_must_match_the_file(corpus: Path) -> None:
    _write(corpus, "README.md", "[handoff](docs/handoffs/CURRENT.md)\n")
    assert [f.check for f in check_docs.run(corpus)] == ["links"]


def test_links_inside_fences_are_ignored(corpus: Path) -> None:
    _write(corpus, "Docs/handoffs/CURRENT.md", "**Status:** Living\n\n```markdown\n[x](nowhere.md)\n```\n")
    assert check_docs.run(corpus) == []


def test_missing_status_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/knowledge/topic.md", "# Topic\n\nno status here\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["status"]
    assert findings[0].location == "Docs/knowledge/topic.md"


def test_unknown_status_word_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/standards/x.md", "**Status:** Draft\n")
    assert [f.detail for f in check_docs.run(corpus)] == [
        "status 'Draft' is not one of " + "|".join(check_docs.STATUS_WORDS)
    ]


def test_superseded_must_say_by_what(corpus: Path) -> None:
    _write(corpus, "Docs/standards/x.md", "**Status:** Superseded\n")
    assert "by what" in check_docs.run(corpus)[0].detail
    _write(corpus, "Docs/standards/x.md", "**Status:** Superseded by y.md\n")
    assert check_docs.run(corpus) == []


def test_session_files_carry_no_status(corpus: Path) -> None:
    assert check_docs.run(corpus) == []  # 2026-09-27-session-01.md has none and is not governed


def test_unindexed_session_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/journal/2026-09-28-session-02.md", "# Session 02\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["journal-index"]
    assert "2026-09-28-session-02.md" in findings[0].detail


def test_indexed_session_that_does_not_exist_is_found(corpus: Path) -> None:
    _write(
        corpus,
        "Docs/journal/README.md",
        "**Status:** Living\n\n| [S1](2026-09-27-session-01.md) | [S2](2026-09-28-session-02.md) |\n",
    )
    checks = [f.check for f in check_docs.run(corpus)]
    assert checks == ["links", "journal-index"]


def test_unindexed_adr_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/decisions/ADR-001-core-in-wgsl.md", "**Status:** Accepted\n")
    _write(corpus, "Docs/decisions/README.md", "# ADRs\n")
    assert [f.check for f in check_docs.run(corpus)] == ["adr-index"]


def test_the_corpus_itself_is_clean() -> None:
    findings = check_docs.run(ROOT)
    assert findings == [], "\n".join(str(f) for f in findings)
