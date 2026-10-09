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
    _write(
        tmp_path,
        "Docs/plan/BOARD.md",
        "# The Board\n\n**Status:** Living\n\n## Gates\n\n## Now\n\n## Next\n\n## Blocked\n\n## Icebox\n",
    )
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


def test_status_inside_a_fence_does_not_count(corpus: Path) -> None:
    _write(corpus, "Docs/standards/x.md", "# X\n\n```markdown\n**Status:** Living\n```\n")
    assert [f.check for f in check_docs.run(corpus)] == ["status"]


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


def test_handoff_day_without_a_journal_file_is_found(corpus: Path) -> None:
    _write(
        corpus, "Docs/handoffs/CURRENT.md", "# Handoff\n\n**Status:** Living\n**Last updated:** 2026-09-28, noon: x\n"
    )
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["journal-day"]
    assert "2026-09-28" in findings[0].detail and "2026-09-27" in findings[0].detail


def test_handoff_day_with_its_journal_file_is_clean(corpus: Path) -> None:
    _write(corpus, "Docs/handoffs/CURRENT.md", "# Handoff\n\n**Status:** Living\n**Last updated:** 2026-09-28: x\n")
    _write(corpus, "Docs/journal/2026-09-28-session-01.md", "# Session 01\n")
    _write(
        corpus,
        "Docs/journal/README.md",
        "**Status:** Living\n\n| [S1](2026-09-27-session-01.md) | [S2](2026-09-28-session-01.md) |\n",
    )
    assert check_docs.run(corpus) == []
    # a journal file newer than the handoff is fine: the handoff lags a journal, never the reverse
    _write(corpus, "Docs/handoffs/CURRENT.md", "# Handoff\n\n**Status:** Living\n**Last updated:** 2026-09-27: x\n")
    assert check_docs.run(corpus) == []


def test_dated_handoff_with_no_journal_files_is_found(corpus: Path) -> None:
    (corpus / "Docs" / "journal" / "2026-09-27-session-01.md").unlink()
    _write(corpus, "Docs/journal/README.md", "**Status:** Living\n")
    _write(corpus, "Docs/handoffs/CURRENT.md", "# Handoff\n\n**Status:** Living\n**Last updated:** 2026-09-28: x\n")
    findings = check_docs.check_journal_day(check_docs.markdown_files(corpus), corpus)
    assert [f.check for f in findings] == ["journal-day"] and "no journal session file" in findings[0].detail


def test_handoff_without_a_dated_line_is_not_checked(corpus: Path) -> None:
    assert check_docs.check_journal_day(check_docs.markdown_files(corpus), corpus) == []


def test_unindexed_adr_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/decisions/ADR-001-core-in-wgsl.md", "**Status:** Accepted\n")
    _write(corpus, "Docs/decisions/README.md", "# ADRs\n")
    assert [f.check for f in check_docs.run(corpus)] == ["adr-index"]


def test_missing_board_is_found(corpus: Path) -> None:
    (corpus / "Docs/plan/BOARD.md").unlink()
    assert [f.check for f in check_docs.run(corpus)] == ["board"]


def test_board_without_an_icebox_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/plan/BOARD.md", "**Status:** Living\n\n## Gates\n## Now\n## Next\n## Blocked\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["board"] and "Icebox" in findings[0].detail


def test_unclosed_fence_is_reported_and_its_links_still_checked(corpus: Path) -> None:
    _write(corpus, "Docs/handoffs/CURRENT.md", "**Status:** Living\n\n```\n[x](gone.md)\nafter\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["fences", "links"]
    assert "line 3" in findings[0].detail


def test_link_climbing_above_the_root_is_broken(corpus: Path) -> None:
    (corpus.parent / "beside.md").write_text("outside\n", encoding="utf-8")
    _write(corpus, "Docs/handoffs/CURRENT.md", "**Status:** Living\n\n[out](../../beside.md)\n")
    assert [f.check for f in check_docs.run(corpus)] == ["links"]


def test_status_after_a_byte_order_mark(corpus: Path) -> None:
    (corpus / "Docs/standards").mkdir(parents=True, exist_ok=True)
    (corpus / "Docs/standards/x.md").write_bytes(b"\xef\xbb\xbf**Status:** Living\n")
    assert check_docs.run(corpus) == []


def test_superseded_by_in_parentheses(corpus: Path) -> None:
    _write(corpus, "Docs/standards/x.md", "**Status:** Superseded (by y.md)\n")
    assert check_docs.run(corpus) == []


def test_index_rows_may_use_dot_slash_and_fragments_and_fences_do_not_count(corpus: Path) -> None:
    _write(
        corpus,
        "Docs/journal/README.md",
        "**Status:** Living\n\n| [S1](./2026-09-27-session-01.md#top) |\n\n"
        "```\n[ghost](2026-01-01-session-99.md)\n```\n",
    )
    assert check_docs.run(corpus) == []


def test_external_schemes_are_not_paths(corpus: Path) -> None:
    _write(corpus, "Docs/handoffs/CURRENT.md", "**Status:** Living\n\n[a](ftp://x/y.md) [b](mailto:x@y.z)\n")
    assert check_docs.run(corpus) == []


def test_main_reports_and_exits_nonzero_on_a_finding(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check_docs.main([str(corpus)]) == 0
    _write(corpus, "Docs/handoffs/CURRENT.md", "**Status:** Living\n\n[gone](../missing.md)\n")
    assert check_docs.main([str(corpus)]) == 1
    assert "broken link" in capsys.readouterr().out


def test_retired_term_used_as_current_is_found(corpus: Path) -> None:
    _write(
        corpus,
        "Docs/glossary.md",
        "**Status:** Living\n\n| Term | Meaning |\n| --- | --- |\n"
        "| ~~**Master material**~~ | **RETIRED.** A Material Prime. |\n",
    )
    _write(corpus, "Docs/handoffs/CURRENT.md", "**Status:** Living\n\nBuild the master material first.\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["vocabulary"] and "master material" in findings[0].detail


def test_retired_term_mentioned_as_retired_or_in_a_fence_is_allowed(corpus: Path) -> None:
    _write(corpus, "Docs/glossary.md", "**Status:** Living\n\n| ~~**Master material**~~ | **RETIRED.** |\n")
    _write(
        corpus,
        "Docs/handoffs/CURRENT.md",
        "**Status:** Living\n\nDo not say master material (retired).\n\n```\nmaster material\n```\n",
    )
    assert check_docs.run(corpus) == []


def test_the_corpus_itself_is_clean() -> None:
    findings = check_docs.run(ROOT)
    assert findings == [], "\n".join(str(f) for f in findings)


def _glossary(corpus: Path, *terms: str) -> None:
    rows = "".join(f"| **{t}** | A meaning. |\n" for t in terms)
    _write(corpus, "Docs/glossary.md", "**Status:** Living\n\n| Term | Meaning |\n| --- | --- |\n" + rows)


def test_a_new_design_without_a_terms_section_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/design/2026-10-09-new.md", "# New\n\n**Status:** Proposed\n\nIt introduces things.\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["terms"] and "no `## Terms introduced` section" in findings[0].detail


@pytest.mark.parametrize(
    "rel", ["Docs/design/2026-10-09-new.md", "Docs/superpowers/specs/new.md", "Docs/superpowers/plans/new.md"]
)
def test_the_rule_covers_designs_specs_and_plans(corpus: Path, rel: str) -> None:
    _write(corpus, rel, "# New\n\n**Status:** Proposed\n")
    assert [f.check for f in check_docs.run(corpus)] == ["terms"]


def test_none_and_listed_glossary_terms_pass(corpus: Path) -> None:
    _glossary(corpus, "Capture set", "Oracle")
    _write(corpus, "Docs/design/2026-10-09-a.md", "**Status:** Proposed\n\n## Terms introduced\n\nNone.\n")
    _write(
        corpus,
        "Docs/design/2026-10-09-b.md",
        "**Status:** Proposed\n\n## Terms introduced\n\n**Capture set** and **oracle** (any case), in the glossary.\n",
    )
    assert check_docs.run(corpus) == []


def test_a_listed_term_with_no_glossary_row_is_found(corpus: Path) -> None:
    _glossary(corpus, "Oracle")
    _write(
        corpus,
        "Docs/superpowers/specs/new.md",
        "**Status:** Proposed\n\n## Terms introduced\n\n**Oracle** and **Frobnicator**.\n",
    )
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["terms"] and "'Frobnicator' has no row" in findings[0].detail


def test_a_section_that_lists_nothing_and_does_not_say_none_is_found(corpus: Path) -> None:
    _write(corpus, "Docs/design/2026-10-09-c.md", "**Status:** Proposed\n\n## Terms introduced\n\nSome words.\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["terms"] and "lists no `**Term**`" in findings[0].detail


def test_the_section_ends_at_the_next_heading_and_a_fence_does_not_count(corpus: Path) -> None:
    _glossary(corpus, "Oracle")
    _write(
        corpus,
        "Docs/design/2026-10-09-d.md",
        "**Status:** Proposed\n\n## Terms introduced\n\n**Oracle**.\n\n## Later\n\n**Frobnicator** is bold only.\n",
    )
    _write(
        corpus,
        "Docs/design/2026-10-09-e.md",
        "**Status:** Proposed\n\n```\n## Terms introduced\n\nNone\n```\n",
    )
    findings = check_docs.run(corpus)
    assert [(f.check, f.location) for f in findings] == [("terms", "Docs/design/2026-10-09-e.md")]


def test_a_grandfathered_document_is_exempt_and_other_directories_are_not_governed(corpus: Path) -> None:
    old = min(check_docs.TERMS_GRANDFATHERED)
    _write(corpus, old, "**Status:** Accepted\n\nWritten before the rule.\n")
    _write(corpus, "Docs/standards/new.md", "**Status:** Accepted\n\nA standard is not a design.\n")
    _write(corpus, "Docs/knowledge/new.md", "**Status:** Living\n")
    assert check_docs.run(corpus) == []


#: The documents that predated the rule on 2026-10-08, frozen here independently of the set under test. The set in
#: ``check_docs`` may lose members (a document earns its section); it may never gain one.
ORIGINALLY_GRANDFATHERED = frozenset(
    {
        "Docs/design/2026-09-20-game-shading-feature-catalogue.md",
        "Docs/design/2026-09-20-modernization-direction.md",
        "Docs/design/2026-09-20-wysiwyg-blindspots.md",
        "Docs/design/2026-09-26-decision-log-and-working-knowledge.md",
        "Docs/design/2026-09-27-material-schema.md",
        "Docs/design/2026-09-27-pitch-bats-as-the-agents-body.md",
        "Docs/design/2026-10-02-material-library.md",
        "Docs/design/2026-10-03-content-conventions.md",
        "Docs/superpowers/plans/e1-ibl-cook.md",
        "Docs/superpowers/plans/e2-cook-performance.md",
        "Docs/superpowers/plans/phase-1-hygiene.md",
        "Docs/superpowers/plans/phase-2-restructure.md",
        "Docs/superpowers/plans/s1-material-schema.md",
        "Docs/superpowers/plans/s2-material-generators.md",
        "Docs/superpowers/plans/s3-wgpu-binding.md",
        "Docs/superpowers/plans/s4a-material-library.md",
        "Docs/superpowers/plans/t1-content-standard.md",
        "Docs/superpowers/plans/t2-texture-cook.md",
        "Docs/superpowers/plans/t3-first-texture-set.md",
        "Docs/superpowers/plans/t3b-wgpu-textures.md",
        "Docs/superpowers/plans/t4-procedural-set.md",
        "Docs/superpowers/specs/e1-ibl-cook.md",
        "Docs/superpowers/specs/e2-cook-performance.md",
        "Docs/superpowers/specs/phase-1-hygiene.md",
        "Docs/superpowers/specs/phase-2-restructure.md",
        "Docs/superpowers/specs/s1-material-schema.md",
        "Docs/superpowers/specs/s2-material-generators.md",
        "Docs/superpowers/specs/s3-wgpu-binding.md",
        "Docs/superpowers/specs/s4a-material-library.md",
        "Docs/superpowers/specs/t1-content-standard.md",
        "Docs/superpowers/specs/t2-texture-cook.md",
        "Docs/superpowers/specs/t3-first-texture-set.md",
        "Docs/superpowers/specs/t3b-wgpu-textures.md",
        "Docs/superpowers/specs/t4-procedural-set.md",
    }
)


def test_the_grandfathered_set_only_shrinks() -> None:
    """Adding a path to ``TERMS_GRANDFATHERED`` would exempt a new document: this fails unless it was original."""
    gained = sorted(check_docs.TERMS_GRANDFATHERED - ORIGINALLY_GRANDFATHERED)
    assert gained == [], f"TERMS_GRANDFATHERED may only shrink; it gained {gained}"
    assert len(ORIGINALLY_GRANDFATHERED) == 34


def test_every_grandfathered_document_still_exists() -> None:
    missing = sorted(p for p in check_docs.TERMS_GRANDFATHERED if not (ROOT / p).exists())
    assert missing == [], f"remove from TERMS_GRANDFATHERED (it only shrinks): {missing}"
    assert all(p.startswith(check_docs.TERMS_DIRS) for p in check_docs.TERMS_GRANDFATHERED)


@pytest.mark.parametrize("heading", ["### Terms introduced", "#### Terms introduced", "# Terms introduced"])
def test_only_a_level_two_heading_counts(corpus: Path, heading: str) -> None:
    """The contract names the literal ``## Terms introduced``; a deeper (or shallower) heading is not it."""
    _write(corpus, "Docs/design/2026-10-09-f.md", f"**Status:** Proposed\n\n{heading}\n\nNone.\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["terms"] and "no `## Terms introduced` section" in findings[0].detail


@pytest.mark.parametrize(
    "first", ["Nonetheless this has no list.", "None of these are new, honestly", "Nothing new.", "none-ish"]
)
def test_prose_that_merely_starts_with_none_does_not_exempt_a_document(corpus: Path, first: str) -> None:
    _write(corpus, "Docs/design/2026-10-09-g.md", f"**Status:** Proposed\n\n## Terms introduced\n\n{first}\n")
    findings = check_docs.run(corpus)
    assert [f.check for f in findings] == ["terms"] and "lists no `**Term**`" in findings[0].detail


@pytest.mark.parametrize("first", ["None", "None.", "none", "NONE."])
def test_the_whole_first_line_being_none_exempts_a_document(corpus: Path, first: str) -> None:
    _write(corpus, "Docs/design/2026-10-09-h.md", f"**Status:** Proposed\n\n## Terms introduced\n\n{first}\n")
    assert check_docs.run(corpus) == []


def test_the_section_may_sit_anywhere_in_the_document(corpus: Path) -> None:
    """The rule is that the document carries the section, not where; later amendments may follow it."""
    _glossary(corpus, "Oracle")
    text = "**Status:** Proposed\n\n## Terms introduced\n\n**Oracle**.\n\n## Amendments after acceptance\n\nWords.\n"
    _write(corpus, "Docs/design/2026-10-09-i.md", text)
    assert check_docs.run(corpus) == []
