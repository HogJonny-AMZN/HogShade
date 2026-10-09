"""
HogShade: tools/check_log_format.py on fixtures and on the tree.
Package: tests/test_check_log_format
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_log_format


@pytest.mark.parametrize(
    "line",
    [
        '_LOGGER.info("wrote %s", path)',
        '_LOGGER.warning("%d of %d", a, b)',
        '_LOGGER.error("failed on %s: %s" % (a, b))',
        'logging.debug("value %.2f", x)',
        'logger.info("%(name)s ready", {"name": n})',
        'self._log.exception("boom %r", e)',
    ],
)
def test_a_lazy_percent_log_call_is_a_finding(line: str) -> None:
    findings = check_log_format.check_source(f"def f():\n    {line}\n")
    assert [f.line for f in findings] == [2], line


@pytest.mark.parametrize(
    "line",
    [
        '_LOGGER.info(f"wrote {path}")',
        '_LOGGER.info("a plain message")',
        '_LOGGER.info("100%% sure")',
        '_LOGGER.info("100% sure, nothing to format")',
        'registry.info("wrote %s", path)',
        "_LOGGER.info(str(e))",
        '_LOGGER.info("wrote %s", path)  # lazy-log: measured at 40 ms a frame in the cook loop',
    ],
)
def test_f_strings_plain_messages_other_objects_and_marked_hot_paths_pass(line: str) -> None:
    assert check_log_format.check_source(f"def f():\n    {line}\n") == [], line


def test_a_multi_line_call_is_found_at_its_first_line_and_marked_there() -> None:
    source = 'def f():\n    _LOGGER.info(\n        "a %s and %s",\n        a,\n        b,\n    )\n'
    assert [f.line for f in check_log_format.check_source(source)] == [2]
    marked = source.replace("_LOGGER.info(\n", "_LOGGER.info(  # lazy-log: measured\n")
    assert check_log_format.check_source(marked) == []


def test_a_file_that_does_not_parse_is_not_a_finding() -> None:
    assert check_log_format.check_source("def f(:\n") == []


def test_main_exits_one_on_a_finding_and_zero_when_clean(tmp_path: Path) -> None:
    (tmp_path / "hogshade").mkdir()
    bad = tmp_path / "hogshade" / "bad.py"
    bad.write_text('_LOGGER.info("x %s", y)\n', encoding="utf-8")
    assert check_log_format.main([str(tmp_path)]) == 1
    bad.write_text('_LOGGER.info(f"x {y}")\n', encoding="utf-8")
    assert check_log_format.main([str(tmp_path)]) == 0


def test_the_tree_is_clean() -> None:
    bad = check_log_format.check_tree(ROOT)
    assert bad == [], "\n".join(f"{f.path}:{f.line}: {f.reason}" for f in bad)
