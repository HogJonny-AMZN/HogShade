"""
HogShade: the log-format check: no lazy ``%``-formatted log call; the message is an f-string.
Package: tools/check_log_format

The rule (Docs/standards/python.md, the owner, 2026-10-04): log calls use f-strings, because a message you can
read in the source is a message a person can troubleshoot. ``_LOGGER.info("wrote %s", path)`` and
``_LOGGER.info("wrote %s" % path)`` are findings. The one exception is a measured hot path, marked on the call's
first line with ``# lazy-log: <the measurement>``; a tight loop should not log at all (collect, then log once).

Only calls on a name containing ``log`` count (``_LOGGER``, ``logging``, ``log``, ``logger``), so a method that happens
to be called ``info`` elsewhere is not flagged. Run standalone (exit code 1 on findings)::

    uv run tools/check_log_format.py

CI runs it as a step; ``tests/test_check_log_format.py`` runs it on fixtures and on the tree.
"""

from __future__ import annotations

import ast
import logging as _logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_MODULE_NAME = "tools.check_log_format"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The directories scanned, repo-relative.
SCANNED = ("hogshade", "tools", "tests", "hosts")

#: Directories never scanned.
SKIPPED_PARTS = frozenset({".venv", "build", ".git", "node_modules", "legacy"})

#: The logging methods that take a message.
LEVELS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical"})

#: A ``%`` conversion in a message (``%s``, ``%d``, ``%.2f``, ``%(name)s``), not a literal ``%%``.
_PLACEHOLDER = re.compile(r"(?<!%)%[#0\- +]*(\d+|\*)?(\.\d+)?[sdrifxXeEgGc]|%\(")

#: The marker that lets a measured hot path keep a lazy call.
MARKER = "# lazy-log:"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    reason: str


def _logger_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def check_source(source: str, path: str = "<source>") -> list[Finding]:
    """The findings in ``source``: a lazy ``%`` log call without the hot-path marker. A syntax error is not ours."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    out: list[Finding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in LEVELS or "log" not in _logger_name(node.func.value).lower() or not node.args:
            continue
        first = node.args[0]
        if (
            isinstance(first, ast.Constant)
            and isinstance(first.value, str)
            and len(node.args) > 1
            and _PLACEHOLDER.search(first.value)
        ):
            reason = "a lazy %-format log call with arguments"
        elif isinstance(first, ast.BinOp) and isinstance(first.op, ast.Mod):
            reason = "a %-operator log message"
        else:
            continue
        if MARKER in lines[node.lineno - 1]:
            continue
        out.append(Finding(path, node.lineno, f"{reason}: write the message as an f-string"))
    return out


def check_tree(root: Path = REPO_ROOT) -> list[Finding]:
    """Every finding under the scanned directories of ``root``."""
    out: list[Finding] = []
    for name in SCANNED:
        for path in sorted((root / name).rglob("*.py")):
            if SKIPPED_PARTS & set(path.relative_to(root).parts):
                continue
            out.extend(check_source(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()))
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
    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
    sys.exit(main(sys.argv[1:]))
