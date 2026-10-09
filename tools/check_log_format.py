"""
HogShade: the log-format check: no lazy ``%``-formatted log call; the message is an f-string.
Package: tools/check_log_format

The rule (Docs/standards/python.md, the owner, 2026-10-04): log calls use f-strings, because a message you can
read in the source is a message a person can troubleshoot. ``_LOGGER.info("wrote %s", path)`` and
``_LOGGER.info("wrote %s" % path)`` are findings. The one exception is a measured hot path, marked on the call's
first line with a comment ``# lazy-log: <the measurement>`` (it may follow another comment such as ``# noqa``); a
bare marker with no measurement is itself a finding. A tight loop should not log at all (collect, then log once).

What counts as a log call: ``<receiver>.<level>(...)`` where the receiver is a name or attribute that is ``log``,
``logger``, ``logging`` or ends in ``logger`` (any case, leading underscores ignored: ``_LOGGER``, ``self._log``), or a
``logging.getLogger(...)`` call; and ``<receiver>.log(level, message, ...)``. **Known gaps**, pinned by tests so
they are decisions and not surprises: a logger held under another name (``out.info(...)``), a method taken as a variable
(``f = _LOGGER.info``), and a message template held in a variable (``_LOGGER.info(template, x)``) are not seen.

A file that does not parse, or cannot be decoded, is a finding, never a silent pass. Run standalone (exit code 1 on
findings)::

    uv run tools/check_log_format.py

CI runs it as a step; ``tests/test_check_log_format.py`` runs it on fixtures and on the tree.
"""

from __future__ import annotations

import ast
import io
import logging as _logging
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

_MODULE_NAME = "tools.check_log_format"
__version__ = "0.2.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The directories scanned, repo-relative; the same set CI lints, plus ``hosts``.
SCANNED = ("hogshade", "tests", "tools", "hosts", "Spikes")

#: Directories never scanned.
SKIPPED_PARTS = frozenset({".venv", "build", ".git", "node_modules", "legacy"})

#: The logging methods that take a message first.
LEVELS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal"})

#: ``Logger.log(level, message, ...)`` takes the message second.
LEVEL_FIRST = "log"

#: A ``%`` conversion in a message, the whole of ``str``'s grammar (``%s``, ``%d``, ``%.2f``, ``%-8.3f``, ``%*d``,
#: ``%.*f``, ``%ld``, ``%o``, ``%u``, ``%a``, ``%(name)s``), or a literal ``%%`` (matched first, so ``%%%s`` is a
#: literal percent followed by a placeholder).
_CONVERSION = re.compile(r"%%|%(?:\([^)]*\))?[#0\- +]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGcrsa]")

#: The comment that lets a measured hot path keep a lazy call: ``# lazy-log: <the measurement>``, alone or after
#: another comment on the same line.
MARKER = re.compile(r"(?:^|#)\s*lazy-log:\s*(?P<measurement>.*)$")

#: A receiver name that is a logger: ``log``, ``logger``, ``logging``, or ending in ``logger``.
_LOGGER_NAME = re.compile(r"^_*(log|logger|logging|\w*logger)$", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    reason: str


def _is_logger(node: ast.expr) -> bool:
    """Whether ``node`` (the receiver of a method call) is a logger by its name, or ``logging.getLogger(...)``."""
    if isinstance(node, ast.Name):
        return bool(_LOGGER_NAME.match(node.id))
    if isinstance(node, ast.Attribute):
        return bool(_LOGGER_NAME.match(node.attr))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "getLogger"
    return False


def _has_placeholder(message: str) -> bool:
    return any(m.group(0) != "%%" for m in _CONVERSION.finditer(message))


def _comments(source: str) -> dict[int, str]:
    """The comment on each line that has one, by line number, from the tokenizer (never from string contents)."""
    out: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                out[tok.start[0]] = tok.string
    except (tokenize.TokenError, IndentationError):
        pass
    return out


def check_source(source: str, path: str = "<source>") -> list[Finding]:
    """
    The findings in ``source``: a lazy ``%`` log call without the hot-path marker, a marker with no measurement, and a
    source that does not parse (a file that cannot be read must not pass for one that is clean).
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as e:  # ValueError: source with null bytes
        return [Finding(path, getattr(e, "lineno", None) or 1, f"does not parse, so its log calls are unchecked: {e}")]
    comments = _comments(source)
    out: list[Finding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        attr = node.func.attr
        if (attr not in LEVELS and attr != LEVEL_FIRST) or not _is_logger(node.func.value):
            continue
        args = node.args[1:] if attr == LEVEL_FIRST else node.args
        if not args:
            continue
        first = args[0]
        text = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
        if text is not None and len(args) > 1 and _has_placeholder(text):
            reason = "a lazy %-format log call with arguments"
        elif isinstance(first, ast.BinOp) and isinstance(first.op, ast.Mod):
            left = first.left
            if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                continue  # numeric modulo, or a template we cannot see: not a message
            reason = "a %-operator log message"
        else:
            continue
        marker = MARKER.search(comments.get(node.lineno, ""))
        if marker and marker.group("measurement").strip():
            continue
        if marker:
            out.append(Finding(path, node.lineno, "the lazy-log marker needs the measurement after the colon"))
            continue
        out.append(Finding(path, node.lineno, f"{reason}: write the message as an f-string"))
    return out


def check_tree(root: Path = REPO_ROOT) -> list[Finding]:
    """Every finding under the scanned directories of ``root``."""
    out: list[Finding] = []
    for name in SCANNED:
        for path in sorted((root / name).rglob("*.py")):
            rel = path.relative_to(root)
            if SKIPPED_PARTS & set(rel.parts):
                continue
            try:
                source = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError as e:
                out.append(
                    Finding(rel.as_posix(), 1, f"cannot be decoded as UTF-8, so its log calls are unchecked: {e}")
                )
                continue
            out.extend(check_source(source, rel.as_posix()))
    return out


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else REPO_ROOT
    findings = check_tree(root)
    for f in findings:
        _LOGGER.error(f"{f.path}:{f.line}: {f.reason}")
    if findings:
        _LOGGER.error(f"log-format check: {len(findings)} finding(s); see Docs/standards/python.md")
        return 1
    _LOGGER.info(f"log-format check: clean under {', '.join(SCANNED)}")
    return 0


if __name__ == "__main__":
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(main(sys.argv[1:]))
