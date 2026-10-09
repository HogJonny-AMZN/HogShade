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


def _check(line: str) -> list[check_log_format.Finding]:
    return check_log_format.check_source(f"def f():\n    {line}\n")


@pytest.mark.parametrize(
    "line",
    [
        '_LOGGER.info("wrote %s", path)',
        '_LOGGER.warning("%d of %d", a, b)',
        '_LOGGER.error("failed on %s: %s" % (a, b))',
        'logging.debug("value %.2f", x)',
        'logger.info("%(name)s ready", {"name": n})',
        'self._log.exception("boom %r", e)',
        '_LOGGER.fatal("gone %s", why)',
        '_LOGGER.log(logging.INFO, "x %s", value)',
        '_LOGGER.log(logging.INFO, "x %s" % value)',
        '_LOGGER.info("mode %o", mode)',
        '_LOGGER.info("count %u", n)',
        '_LOGGER.info("text %a", s)',
        '_LOGGER.info("pi %.*f", 3, x)',
        '_LOGGER.info("big %ld", n)',
        '_LOGGER.info("pad %-8.3f|", x)',
        '_LOGGER.info("100%%%s", x)',
        'logging.getLogger("a").info("x %s", y)',
        '_LOGGER.info("# lazy-log: %s", value)',
        '_LOGGER.info("wrote %s", path)  # lazy-log:',
        '_LOGGER.info("wrote %s", path)  # lazy-log:   ',
    ],
)
def test_a_lazy_percent_log_call_is_a_finding(line: str) -> None:
    assert [f.line for f in _check(line)] == [2], line


@pytest.mark.parametrize(
    "line",
    [
        '_LOGGER.info(f"wrote {path}")',
        '_LOGGER.info("a plain message")',
        '_LOGGER.info("100%% sure")',
        '_LOGGER.info("100%%s of them", x)',
        '_LOGGER.log(logging.INFO, f"x {value}")',
        '_LOGGER.log(logging.INFO, "no arguments, 100% sure")',
        '_LOGGER.info("100% sure, nothing to format")',
        'registry.info("wrote %s", path)',
        'blog.info("wrote %s", path)',
        'dialog.warning("wrote %s", path)',
        "_LOGGER.debug(i % 10)",
        "_LOGGER.info(str(e))",
        '_LOGGER.info("wrote %s", path)  #   lazy-log: 40 ms a frame',
        '_LOGGER.info("wrote %s", path)  # lazy-log: measured at 40 ms a frame in the cook loop',
        '_LOGGER.info("wrote %s", path)  # noqa: E501  # lazy-log: 40 ms a frame',
    ],
)
def test_f_strings_plain_messages_other_objects_and_marked_hot_paths_pass(line: str) -> None:
    assert _check(line) == [], line


@pytest.mark.parametrize(
    "source",
    [
        'def f():\n    out.info("wrote %s", path)\n',
        'def f():\n    log_it = _LOGGER.info\n    log_it("wrote %s", path)\n',
        'def f():\n    template = "wrote %s"\n    _LOGGER.info(template, path)\n',
    ],
    ids=["another-name", "method-as-variable", "template-in-a-variable"],
)
def test_the_known_gaps_stay_gaps_until_someone_decides_otherwise(source: str) -> None:
    """The module docstring lists these as not seen; a test pins them so closing one is a deliberate change."""
    assert check_log_format.check_source(source) == []


def test_the_wrong_marker_finding_says_what_is_missing() -> None:
    (finding,) = _check('_LOGGER.info("wrote %s", path)  # lazy-log:')
    assert "needs the measurement" in finding.reason
    (finding,) = _check('_LOGGER.info("wrote %s", path)')
    assert "f-string" in finding.reason


def test_a_multi_line_call_is_found_at_its_first_line_and_marked_there() -> None:
    source = 'def f():\n    _LOGGER.info(\n        "a %s and %s",\n        a,\n        b,\n    )\n'
    assert [f.line for f in check_log_format.check_source(source)] == [2]
    marked = source.replace("_LOGGER.info(\n", "_LOGGER.info(  # lazy-log: measured\n")
    assert check_log_format.check_source(marked) == []


def test_a_file_that_does_not_parse_is_a_finding_not_a_pass() -> None:
    (finding,) = check_log_format.check_source("def f(:\n", "bad.py")
    assert finding.path == "bad.py" and "does not parse" in finding.reason
    assert check_log_format.check_source('x = "\x00"\n', "nul.py"), "a null byte must not pass silently either"


def test_a_byte_order_mark_does_not_hide_a_lazy_call(tmp_path: Path) -> None:
    (tmp_path / "hogshade").mkdir()
    (tmp_path / "hogshade" / "bom.py").write_bytes(b'\xef\xbb\xbf_LOGGER.info("x %s", y)\n')
    assert [f.line for f in check_log_format.check_tree(tmp_path)] == [1]


def test_a_file_that_is_not_utf8_is_a_finding_not_a_traceback(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "latin.py").write_bytes(b"# caf\xe9\n")
    (finding,) = check_log_format.check_tree(tmp_path)
    assert finding.path == "tools/latin.py" and "cannot be decoded" in finding.reason


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
