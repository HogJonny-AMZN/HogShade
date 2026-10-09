"""
HogShade: the report: its schema, its round trip, and the rule that a control which passes makes the run not ok.
Package: tests/compare/test_report
"""

from __future__ import annotations

import copy
import json

import pytest

from hogshade.compare.report import CaseResult, Measurement, Report, ReportError
from hogshade.compare.verdict import Threshold, Verdict

H = "c" * 64


def _result(cid: str = "texel", verdict: Verdict = Verdict.PASS, **kw) -> CaseResult:
    fields = {
        "id": cid,
        "kind": "oracle",
        "verdict": verdict,
        "measurements": (Measurement("agreement", 1.0, 1.0),),
        "thresholds": (Threshold("agreement", 0.99, 0.9),),
        "capture": "captures/wgpu/texel",
        "capture_hash": H,
        "reference_hash": H,
    }
    fields.update(kw)
    return CaseResult(**fields)


def _control(passed: bool = False) -> CaseResult:
    verdict = Verdict.PASS if passed else Verdict.FAIL
    return _result("texel-v-flipped", verdict, expect="fail", control_ok=(not passed))


def _report(*results: CaseResult) -> Report:
    return Report("wgpu", "L2p", {"wgpu": "1.0"}, tuple(results))


def test_a_report_round_trips_through_its_json() -> None:
    report = _report(_result(), _control())
    again = Report.from_json(report.to_json())
    assert again == report and again.to_json() == report.to_json()
    data = json.loads(report.to_json())
    assert data["run"] == {"host": "wgpu", "level": "L2p", "versions": {"wgpu": "1.0"}}
    assert data["cases"][0]["measurements"] == [{"metric": "agreement", "value": 1.0, "data_range": 1.0}]


def test_the_summary_counts_ordinary_cases_and_controls_apart() -> None:
    passing_control = _result("x", Verdict.PASS, expect="fail", control_ok=False)
    report = _report(
        _result("a"), _result("b", Verdict.NEEDS_REVIEW), _result("c", Verdict.FAIL), _control(), passing_control
    )
    assert report.summary == {"cases": 3, "pass": 1, "needs-review": 1, "fail": 1, "controls": 2, "controls_ok": 1}
    assert not report.ok


def test_the_report_is_ok_only_when_every_case_passes_and_every_control_fails() -> None:
    assert _report(_result(), _control()).ok
    assert not _report().ok, "an empty report proves nothing"
    assert not _report(_control()).ok, "controls alone prove nothing about a host"
    assert not _report(_result("a", Verdict.FAIL), _control()).ok
    assert not _report(_result("a", Verdict.NEEDS_REVIEW), _control()).ok


def test_a_control_that_passes_makes_the_report_not_ok() -> None:
    """The instrument could not tell right from wrong: the expectation was wrong on purpose and it still passed."""
    report = _report(_result(), _control(passed=True))
    assert not report.ok and report.summary["controls_ok"] == 0
    assert Report.from_json(report.to_json()).ok is False


def test_an_accepted_difference_is_recorded_and_passes() -> None:
    report = _report(_result("a", Verdict.PASS, accepted=True, notes=("accepted: Maya clamps the highlight",)))
    assert report.ok and Report.from_json(report.to_json()).cases[0].accepted


def _doc() -> dict:
    return json.loads(_report(_result(), _control()).to_json())


def _break(path: str, value) -> str:
    data = _doc()
    node = data
    *head, last = path.split(".")
    for key in head:
        node = node[int(key)] if key.isdigit() else node[key]
    if value is ...:
        del node[last]
    else:
        node[last] = value
    return json.dumps(data)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("version", 2, "version 1 is expected"),
        ("extra", 1, r"report: unknown field\(s\) \['extra'\]"),
        ("run.host", "", "report.run.host: a non-empty string"),
        ("run.versions", [], "report.run.versions"),
        ("cases", {}, "report.cases: a list"),
        ("cases.0.kind", "magic", r"report.cases\[0\].kind"),
        ("cases.0.verdict", "maybe", r"report.cases\[0\].verdict"),
        ("cases.0.expect", "maybe", r"report.cases\[0\].expect"),
        ("cases.0.control_ok", True, "control_ok is set exactly for a control"),
        ("cases.1.control_ok", None, "control_ok is set exactly for a control"),
        ("cases.1.verdict", "pass", "control_ok is true only when the control failed by measuring"),
        ("cases.1.error", "boom", "control_ok is true only when the control failed by measuring"),
        ("cases.0.capture_hash", "short", r"capture_hash: a SHA-256"),
        ("cases.0.measurements", {}, r"measurements: a list"),
        ("cases.0.measurements.0.data_range", 0, r"data_range: a positive number or null"),
        ("cases.0.measurements.0.value", True, "a finite number or null"),
        ("cases.0.thresholds", [{"metric": "m"}], r"thresholds: threshold: unknown field"),
        ("cases.0.notes", "x", r"notes: a list of strings"),
        ("cases.0.capture", 5, r"capture: a string or null"),
        ("cases.0.error", "boom", "means no measurement was made, so the verdict is fail"),
        ("run.level", "L9", r"report.run.level: one of \['L2', 'L2p', 'L1', 'L0'\]"),
        ("run.level", "", r"report.run.level"),
        ("run.versions", {"a": 1}, "report.run.versions: an object of strings"),
        ("run.versions", {"a": None}, "report.run.versions: an object of strings"),
        ("run.host", "", "report.run.host"),
        ("cases.0.measurements.0.value", float("inf"), "a finite number or null"),
        ("cases.0.id", [1], r"\.id: a case id"),
        ("cases.0.id", 7, r"\.id: a case id"),
        ("cases.0.id", "", r"\.id: a case id"),
        ("cases.0.control_ok", 1, "control_ok a boolean or null"),
        ("cases.0.accepted", 1, "accepted is a boolean"),
        ("ok", False, "disagrees with the cases it summarises"),
        ("summary.pass", 9, "disagrees with the cases it summarises"),
    ],
)
def test_a_report_that_does_not_match_its_schema_is_refused_with_where(path: str, value, message: str) -> None:
    with pytest.raises(ReportError, match=message):
        Report.from_json(_break(path, value))


def test_duplicate_case_ids_and_bad_json_are_refused() -> None:
    data = _doc()
    data["cases"].append(copy.deepcopy(data["cases"][0]))
    with pytest.raises(ReportError, match=r"duplicate case id\(s\) \['texel'\]"):
        Report.from_json(json.dumps(data))
    with pytest.raises(ReportError, match="not valid JSON"):
        Report.from_json("{nope")
    with pytest.raises(ReportError, match="an object is expected"):
        Report.from_json("[]")


def test_a_measurement_that_was_not_a_finite_number_is_null_and_the_json_is_standard() -> None:
    """A NaN or infinity cannot be written as JSON: the measurement is recorded as null and the case fails."""
    report = _report(_result("a", Verdict.FAIL, measurements=(Measurement("agreement", None, 1.0),)))
    text = report.to_json()
    assert "NaN" not in text and "Infinity" not in text and '"value": null' in text
    assert Report.from_json(text) == report
    with pytest.raises(ValueError, match="Out of range float values"):
        _report(_result("b", measurements=(Measurement("agreement", float("nan"), 1.0),))).to_json()
