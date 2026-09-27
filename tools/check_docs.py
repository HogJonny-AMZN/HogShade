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
- **adr-index**: every ``Docs/decisions/ADR-*.md`` has a row in ``Docs/decisions/README.md`` (none yet)

Run standalone (exit code 1 on findings)::

    uv run python tools/check_docs.py

CI runs it as a step; ``tests/test_check_docs.py`` runs each check on fixtures and the whole corpus.
"""

import logging as _logging
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

_MODULE_NAME = "tools.check_docs"
__version__ = "0.1.0"
__updated__ = "2026-09-27"
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

#: Directories (repo-relative, POSIX) whose documents must carry a status header. The design, spec
#: and plan folders join in the standards pass, once every file there has one.
STATUS_REQUIRED_DIRS = ("Docs/decisions", "Docs/handoffs", "Docs/journal", "Docs/knowledge", "Docs/standards")

#: The vocabulary (SpriteJammer ``documentation.md``): a reader must be able to tell a decision from a
#: hypothesis, and a live document from a stale one.
STATUS_WORDS = ("Proposed", "Accepted", "Living", "Superseded", "Abandoned")

#: Files in governed directories that carry no status on purpose (indexes and session files).
STATUS_EXEMPT = {"Docs/decisions/README.md"}

ADR_INDEX = "Docs/decisions/README.md"
JOURNAL_INDEX = "Docs/journal/README.md"

#: An inline link: the destination is ``<...>`` or a run without whitespace or ``)``; an optional title
#: (``"..."`` or ``'...'``) may follow. Titles are not paths.
_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(\S+)", re.MULTILINE)
_ADR_FILE_RE = re.compile(r"^ADR-(\d{3})-")
_SESSION_FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-session-\d{2}\.md$")


@dataclass(frozen=True)
class Finding:
    """One documentation inconsistency."""

    check: str
    location: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.location}: {self.detail}"


def strip_fences(text: str) -> str:
    """
    The prose of a markdown document: fenced code blocks removed. Line-oriented, as CommonMark reads
    them: a fence opens with three or more backticks or tildes and closes with a fence of the same
    character at least as long; a fence of the other character inside stays code.
    """
    out: list[str] = []
    fence_char, fence_len = None, 0
    for line in text.splitlines():
        m = _FENCE_OPEN_RE.match(line)
        if fence_char is None:
            if m:
                fence_char, fence_len = m.group(1)[0], len(m.group(1))
                continue
            out.append(line)
        elif m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len and not line.strip().strip(fence_char):
            fence_char = None
    return "\n".join(out)


def _exists_exact(base: Path, target: str) -> bool:
    """
    ``target``, relative to ``base``, names a file with exactly this spelling. On a case-insensitive
    file system ``exists()`` says yes to ``docs/`` when the directory is ``Docs/``; CI on Linux says
    no. Each component is checked against its parent's listing.
    """
    current = base
    for part in target.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
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
        prose = strip_fences(path.read_text(encoding="utf-8", errors="replace"))
        for match in _LINK_RE.finditer(prose):
            target = match.group(1).strip().strip("<>").split("#")[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not _exists_exact(path.parent, target):
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
        head = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:12])
        match = _STATUS_RE.search(head)
        if match is None:
            findings.append(Finding("status", rel, "no `**Status:**` line in the first 12 lines"))
            continue
        word = match.group(1).strip(".,;:")
        if word not in STATUS_WORDS:
            findings.append(Finding("status", rel, f"status {word!r} is not one of {'|'.join(STATUS_WORDS)}"))
            continue
        line = head[match.start() :].splitlines()[0]
        if word == "Superseded" and " by " not in line:
            findings.append(Finding("status", rel, "Superseded, but the line does not say by what"))
    return findings


def _check_index(files: list[Path], root: Path, index_rel: str, name_re: re.Pattern, check: str) -> list[Finding]:
    """Every file matching ``name_re`` beside the index is linked from it, and every linked one exists."""
    index_path = root / index_rel
    members = {p.name for p in files if name_re.match(p.name) and p.parent == index_path.parent}
    if not members:
        return []
    if not index_path.exists():
        return [Finding(check, index_rel, "missing; every entry needs a row here")]
    text = index_path.read_text(encoding="utf-8", errors="replace")
    findings = [
        Finding(check, index_rel, f"no row links {name}") for name in sorted(members) if f"({name})" not in text
    ]
    for linked in re.findall(r"\(([^)/#]+\.md)\)", text):
        if name_re.match(linked) and linked not in members:
            findings.append(Finding(check, index_rel, f"row links {linked}, which does not exist"))
    return findings


def check_adr_index(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """Every ADR file is a row in the decisions index, and every indexed ADR exists."""
    return _check_index(list(files), root, ADR_INDEX, _ADR_FILE_RE, "adr-index")


def check_journal_index(files: Iterable[Path], root: Path = REPO_ROOT) -> list[Finding]:
    """Every session file is a row in the journal index, and every indexed session exists."""
    return _check_index(list(files), root, JOURNAL_INDEX, _SESSION_FILE_RE, "journal-index")


CHECKS = (check_links, check_status_headers, check_journal_index, check_adr_index)


def run(root: Path = REPO_ROOT, checks: Sequence = CHECKS) -> list[Finding]:
    """Run every check over the corpus under ``root``."""
    files = markdown_files(root)
    findings: list[Finding] = []
    for check in checks:
        findings.extend(check(files, root))
    return findings


def main(argv: list[str] | None = None) -> int:
    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
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
