"""
HogShade: documentation consistency checks, the mechanised half of the definition of done.
Package: tools/check_docs

A port of SpriteJammer's ``scripts/check_docs.py`` by way of LargeWorlds' cut-down copy. Every check
exists because a drift happened in one of those repositories: a renamed file left links dangling, a
document without a status read as live long after it was not, a journal entry linked from nowhere.

Checks:

- **links**: every relative markdown link resolves to a file with that exact spelling (a case-insensitive
  file system says yes where Linux CI says no); fenced code is skipped
- **status**: every document in the governed directories carries ``**Status:**`` in its first 12 lines,
  with one of `STATUS_WORDS`; a ``Superseded`` document says by what
- **journal-index**: every ``Docs/journal/YYYY-MM-DD-session-NN.md`` has a row in ``Docs/journal/README.md``
- **journal-day**: the handoff's ``**Last updated:** YYYY-MM-DD`` date has a journal file of that date or later;
  a day that changed the state has its own file (the per-day rule, owner, 2026-10-03)
- **adr-index**: every ``Docs/decisions/ADR-*.md`` has a row in ``Docs/decisions/README.md`` (none yet)
- **board**: ``Docs/plan/BOARD.md`` exists and keeps its five sections (Gates, Now, Next, Blocked, Icebox),
  so the tracker cannot be deleted or quietly collapsed into a list
- **vocabulary**: a term the glossary has retired (a struck-through row, ``~~**Term**~~``) is not used as
  current anywhere else in the corpus; SpriteJammer boarded this check, this repo built it
- **terms**: every design, spec and plan carries a ``## Terms introduced`` section naming the glossary terms it
  introduces (``**Term**``, each with a row in ``Docs/glossary.md``) or saying ``None``; the documents that
  predate the rule (2026-10-08) are listed in ``TERMS_GRANDFATHERED`` and that set only shrinks (ledger entry 20)
- **fences**: a fenced code block that never closes; without this the links and status checks would be
  silently vacuous for the rest of that file (local review, 2026-09-27)

A link may not climb above the repository root: what lies beside the checkout differs per machine, so
such a link would pass here and fail on CI, or the reverse.

Run standalone (exit code 1 on findings)::

    uv run python tools/check_docs.py

CI runs it as a step; ``tests/test_check_docs.py`` runs each check on fixtures and the whole corpus.
"""

import logging as _logging
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

_MODULE_NAME = "tools.check_docs"
__version__ = "0.1.0"
__updated__ = "2026-09-27"  # local review: unclosed fences, links above the root, BOM, index rows
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: Repository root, derived from this file's location.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: Path parts that put a file outside the corpus: other checkouts, environments, caches, the legacy
#: shaders (frozen record), spikes (frozen evidence), LFS content and verification captures.
EXCLUDED_PARTS = {
    ".git",
    ".claude",
    ".worktrees",
    ".venv",
    ".temp",
    "node_modules",
    "__pycache__",
    "Spikes",
    "legacy",
    "verification",
}

#: Directories (repo-relative, POSIX) whose documents must carry a status header: all of ``Docs/`` since
#: the standards pass (2026-09-27). Journal session files are the exemption; they are dated entries.
STATUS_REQUIRED_DIRS = ("Docs",)  # all of Docs/ since the standards pass; journal session files exempt

#: The vocabulary (SpriteJammer ``documentation.md``): a reader must be able to tell a decision from a
#: hypothesis, and a live document from a stale one.
STATUS_WORDS = ("Proposed", "Accepted", "Living", "Superseded", "Abandoned")

#: Files in governed directories that carry no status on purpose (indexes and session files).
STATUS_EXEMPT = {"Docs/decisions/README.md"}

ADR_INDEX = "Docs/decisions/README.md"
JOURNAL_INDEX = "Docs/journal/README.md"
JOURNAL_DIR = "Docs/journal"
HANDOFF = "Docs/handoffs/CURRENT.md"
BOARD = "Docs/plan/BOARD.md"
BOARD_SECTIONS = ("## Gates", "## Now", "## Next", "## Blocked", "## Icebox")
GLOSSARY = "Docs/glossary.md"

#: Where the terms rule applies, and the documents that predate it (2026-10-08, the owner: "oracle is not a term in the
#: glossary"). Do not add to this set: a document written after the rule carries its section, and one that is
#: substantially revised earns the section and leaves the set.
TERMS_DIRS = ("Docs/design/", "Docs/superpowers/specs/", "Docs/superpowers/plans/")
TERMS_GRANDFATHERED = frozenset(
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
_RETIRED_RE = re.compile(r"^\| ~~\*\*([^*]+)\*\*~~ \|", re.MULTILINE)
_GLOSSARY_ROW_RE = re.compile(r"^\|\s*\*\*([^*]+)\*\*", re.MULTILINE)
_TERMS_HEADING_RE = re.compile(r"^(#{2,4})\s+Terms introduced\s*$", re.MULTILINE | re.IGNORECASE)
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")

#: An inline link: the destination is ``<...>`` or a run without whitespace or ``)``; an optional title
#: (``"..."`` or ``'...'``) may follow. Titles are not paths.
_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(\S+)", re.MULTILINE)
_ADR_FILE_RE = re.compile(r"^ADR-(\d{3})-")
_SESSION_FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-session-\d{2}\.md$")
_LAST_UPDATED_RE = re.compile(r"^\*\*Last updated:\*\*\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")  # any URL scheme, not a path


def _read(path: Path) -> str:
    """A document's text; a UTF-8 byte-order mark is not part of its first line."""
    return path.read_text(encoding="utf-8-sig", errors="replace")


@dataclass(frozen=True)
class Finding:
    """One documentation inconsistency."""

    check: str
    location: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.location}: {self.detail}"


def split_fences(text: str) -> tuple[str, int | None]:
    """
    The prose of a markdown document with fenced code blocks removed, and the line number of a fence
    that never closed (``None`` when every fence closes). Line-oriented, as CommonMark reads them: a
    fence opens with three or more backticks or tildes and closes with a fence of the same character at
    least as long; a fence of the other character inside stays code. An unclosed fence's lines are kept
    as prose, so the checks stay live for the rest of the file and the caller can report the fence.
    """
    out: list[str] = []
    held: list[str] = []
    fence_char, fence_len, opened_at = None, 0, None
    for number, line in enumerate(text.splitlines(), start=1):
        m = _FENCE_OPEN_RE.match(line)
        if fence_char is None:
            if m:
                fence_char, fence_len, opened_at = m.group(1)[0], len(m.group(1)), number
                held = []
                continue
            out.append(line)
        elif m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len and not line.strip().strip(fence_char):
            fence_char = None
        else:
            held.append(line)
    if fence_char is not None:
        out.extend(held)
        return "\n".join(out), opened_at
    return "\n".join(out), None


def strip_fences(text: str) -> str:
    """The prose of a markdown document, fenced code blocks removed; see ``split_fences``."""
    return split_fences(text)[0]


def _exists_exact(base: Path, target: str, root: Path) -> bool:
    """
    ``target``, relative to ``base``, names a file with exactly this spelling, inside ``root``. On a
    case-insensitive file system ``exists()`` says yes to ``docs/`` when the directory is ``Docs/``; CI
    on Linux says no. Each component is checked against its parent's listing. A ``..`` that would leave
    the root is a broken link: what lies beside the checkout differs per machine.
    """
    current = base
    for part in target.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if current == root:
                return False
            current = current.parent
            continue
        try:
            if part not in {p.name for p in current.iterdir()}:
                return False
        except OSError:
            return False
        current = current / part
    return current.exists()


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return bool(EXCLUDED_PARTS & set(parts))


def markdown_files(root: Path = REPO_ROOT) -> list[Path]:
    """Every markdown file in the corpus under ``root``, sorted."""
    return sorted(p for p in root.rglob("*.md") if not _is_excluded(p, root))


# -------------------------------------------------------------------------
def check_links(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """Every relative markdown link resolves to an existing file; fenced code is not prose."""
    findings: list[Finding] = []
    for path in files:
        prose, unclosed = split_fences(_read(path))
        if unclosed is not None:
            findings.append(Finding("fences", _rel(path, root), f"fence opened at line {unclosed} never closes"))
        for match in _LINK_RE.finditer(prose):
            target = match.group(1).strip().strip("<>").split("#")[0].strip()
            if not target or _SCHEME_RE.match(target):
                continue
            if not _exists_exact(path.parent, target, root):
                findings.append(Finding("links", _rel(path, root), f"broken link -> {target}"))
    return findings


def _governed(rel: str) -> bool:
    if rel in STATUS_EXEMPT or _SESSION_FILE_RE.match(rel.rsplit("/", 1)[-1]):
        return False
    return rel.startswith(tuple(d + "/" for d in STATUS_REQUIRED_DIRS))


def check_status_headers(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """Governed documents declare ``**Status:** <word>``; a Superseded one says by what."""
    findings: list[Finding] = []
    for path in files:
        rel = _rel(path, root)
        if not _governed(rel):
            continue
        head = "\n".join(strip_fences(_read(path)).splitlines()[:12])
        match = _STATUS_RE.search(head)
        if match is None:
            findings.append(Finding("status", rel, "no `**Status:**` line in the first 12 lines"))
            continue
        word = match.group(1).strip(".,;:")
        if word not in STATUS_WORDS:
            findings.append(Finding("status", rel, f"status {word!r} is not one of {'|'.join(STATUS_WORDS)}"))
            continue
        line = head[match.start() :].splitlines()[0]
        if word == "Superseded" and not re.search(r"\bby\b", line):
            findings.append(Finding("status", rel, "Superseded, but the line does not say by what"))
    return findings


def _check_index(files: list[Path], root: Path, index_rel: str, name_re: re.Pattern[str], check: str) -> list[Finding]:
    """Every file matching ``name_re`` beside the index is linked from it, and every linked one exists."""
    index_path = root / index_rel
    members = {p.name for p in files if name_re.match(p.name) and p.parent == index_path.parent}
    if not members:
        return []
    if not index_path.exists():
        return [Finding(check, index_rel, "missing; every entry needs a row here")]
    linked = set()
    for match in _LINK_RE.finditer(strip_fences(_read(index_path))):
        target = match.group(1).strip().strip("<>").split("#")[0].strip()
        target = target.removeprefix("./")
        if "/" not in target and name_re.match(target):
            linked.add(target)
    findings = [Finding(check, index_rel, f"no row links {name}") for name in sorted(members - linked)]
    findings += [
        Finding(check, index_rel, f"row links {name}, which does not exist") for name in sorted(linked - members)
    ]
    return findings


def check_adr_index(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """Every ADR file is a row in the decisions index, and every indexed ADR exists."""
    return _check_index(list(files), root, ADR_INDEX, _ADR_FILE_RE, "adr-index")


def check_journal_index(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """Every session file is a row in the journal index, and every indexed session exists."""
    return _check_index(list(files), root, JOURNAL_INDEX, _SESSION_FILE_RE, "journal-index")


def check_journal_day(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """
    The day the handoff was last updated has a journal file: the newest session file's date is that date
    or later, and a dated handoff with no session file at all is a finding. A handoff without a dated
    *Last updated* line is not checked (the fixture corpora have none).
    """
    handoff = root / HANDOFF
    if not handoff.exists():
        return []
    match = _LAST_UPDATED_RE.search(strip_fences(_read(handoff)))
    if match is None:
        return []
    updated = match.group(1)
    journal_dir = root / JOURNAL_DIR
    dates = sorted(p.name[:10] for p in files if _SESSION_FILE_RE.match(p.name) and p.parent == journal_dir)
    if not dates:
        return [Finding("journal-day", HANDOFF, f"last updated {updated} but there is no journal session file at all")]
    newest = dates[-1]
    if newest < updated:
        return [
            Finding(
                "journal-day",
                HANDOFF,
                f"last updated {updated} but the newest journal file is {newest}; a new day starts a new session file",
            )
        ]
    return []


def check_board(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """The board exists and keeps every section a reader looks for; a section missing is a tracker degrading."""
    path = root / BOARD
    if not path.exists():
        return [Finding("board", BOARD, "missing; the tracker lives here")]
    text = path.read_text(encoding="utf-8", errors="replace")
    return [Finding("board", BOARD, f"no {name!r} section") for name in BOARD_SECTIONS if name not in text]


Check = Callable[[Iterable[Path], Path], list[Finding]]


def glossary_terms(root: Path = REPO_ROOT) -> set[str]:
    """The glossary's current terms (the bold first cell of each row), lowercase; retired ones are not current."""
    path = root / GLOSSARY
    if not path.exists():
        return set()
    return {m.group(1).strip().lower() for m in _GLOSSARY_ROW_RE.finditer(strip_fences(_read(path)))}


def _terms_section(text: str) -> str | None:
    """The body of the ``Terms introduced`` section (to the next heading of the same or a higher level), or None."""
    match = _TERMS_HEADING_RE.search(text)
    if match is None:
        return None
    level = len(match.group(1))
    rest = text[match.end() :]
    end = re.search(rf"^#{{1,{level}}}\s", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def check_terms_introduced(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """
    A design, spec or plan written after the rule ends with its terms: a ``## Terms introduced`` section that says
    ``None`` or lists each as ``**Term**``, every one with a row in the glossary. The word is added to the glossary in
    the same change, before the code that uses it (ledger entry 20).
    """
    findings: list[Finding] = []
    known = glossary_terms(root)
    for path in files:
        rel = _rel(path, root)
        if not rel.startswith(TERMS_DIRS) or rel in TERMS_GRANDFATHERED:
            continue
        section = _terms_section(strip_fences(_read(path)))
        if section is None:
            findings.append(
                Finding(
                    "terms",
                    rel,
                    "no `## Terms introduced` section: list the glossary terms this introduces, or say None",
                )
            )
            continue
        body = section.strip()
        if body.lower().startswith("none"):
            continue
        terms = [t.strip() for t in _BOLD_RE.findall(body)]
        if not terms:
            findings.append(Finding("terms", rel, "`Terms introduced` lists no `**Term**` and does not say None"))
        for term in terms:
            if term.lower() not in known:
                findings.append(
                    Finding("terms", rel, f"term {term!r} has no row in {GLOSSARY}; add it before using it")
                )
    return findings


def retired_terms(root: Path = REPO_ROOT) -> list[str]:
    """The glossary's struck-through terms, lowercase."""
    path = root / GLOSSARY
    if not path.exists():
        return []
    return [m.group(1).strip().lower() for m in _RETIRED_RE.finditer(strip_fences(_read(path)))]


def check_vocabulary(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """A retired term is not used as current outside the glossary; a line that says it is retired is allowed."""
    terms = retired_terms(root)
    if not terms:
        return []
    patterns = [
        (t, re.compile(r"(?<![\w-])" + re.escape(t).replace(r"\ ", r"[\s-]+") + r"(?![\w-])", re.IGNORECASE))
        for t in terms
    ]
    findings: list[Finding] = []
    for path in files:
        rel = _rel(path, root)
        if rel == GLOSSARY:
            continue
        for number, line in enumerate(strip_fences(_read(path)).splitlines(), start=1):
            if "retired" in line.lower() or "do not say" in line.lower() or "never " in line.lower():
                continue
            for term, pat in patterns:
                if pat.search(line):
                    findings.append(
                        Finding(
                            "vocabulary",
                            f"{rel}:{number}",
                            f"retired term {term!r}; the glossary says what replaced it",
                        )
                    )
    return findings


CHECKS: tuple[Check, ...] = (
    check_links,
    check_status_headers,
    check_journal_index,
    check_journal_day,
    check_adr_index,
    check_board,
    check_vocabulary,
    check_terms_introduced,
)


def run(root: Path = REPO_ROOT, checks: Sequence[Check] = CHECKS) -> list[Finding]:
    """Run every check over the corpus under ``root``."""
    files = markdown_files(root)
    findings: list[Finding] = []
    for check in checks:
        found = check(files, root)
        _LOGGER.debug(f"{check.__name__}: {len(found)} finding(s)")
        findings.extend(found)
    return findings


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else REPO_ROOT
    files = markdown_files(root)
    findings = run(root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"docs check: {len(files)} files, {len(findings)} finding(s)")
        return 1
    print(f"docs check: {len(files)} files, no drift")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
