"""
HogShade: the verdict model and the accepted-differences file.
Package: tests/compare/test_verdict
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from hogshade.compare.verdict import (
    AcceptedDifferences,
    Threshold,
    Verdict,
    VerdictError,
    judge,
    resolve,
    worst,
)

H1, H2, H3 = "1" * 64, "2" * 64, "3" * 64


@pytest.mark.parametrize(
    ("value", "want"),
    [
        (1.0, Verdict.PASS),
        (0.99, Verdict.PASS),  # at the pass bound: inclusive
        (0.989, Verdict.NEEDS_REVIEW),
        (0.90, Verdict.NEEDS_REVIEW),  # at the fail bound: still needs review
        (0.8999, Verdict.FAIL),
        (0.0, Verdict.FAIL),
    ],
)
def test_higher_is_better_passes_at_the_bound_and_fails_only_below_the_hard_one(value: float, want: Verdict) -> None:
    assert Threshold("agreement", pass_at=0.99, fail_at=0.90, direction="higher").judge(value) is want


@pytest.mark.parametrize(
    ("value", "want"),
    [
        (0.0, Verdict.PASS),
        (0.01, Verdict.PASS),
        (0.011, Verdict.NEEDS_REVIEW),
        (0.05, Verdict.NEEDS_REVIEW),
        (0.0501, Verdict.FAIL),
        (3.0, Verdict.FAIL),
    ],
)
def test_lower_is_better_is_the_mirror_image(value: float, want: Verdict) -> None:
    assert Threshold("max_abs", pass_at=0.01, fail_at=0.05, direction="lower").judge(value) is want


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, None, "0.5", True])
def test_a_value_that_is_not_a_finite_number_fails(bad) -> None:
    assert Threshold("agreement", 0.99, 0.9).judge(bad) is Verdict.FAIL
    assert Threshold("max_abs", 0.01, 0.05, "lower").judge(bad) is Verdict.FAIL


def test_thresholds_are_validated() -> None:
    with pytest.raises(VerdictError, match="direction is 'higher' or 'lower'"):
        Threshold("m", 1, 0, "up")
    with pytest.raises(VerdictError, match="for higher-is-better fail_at"):
        Threshold("m", pass_at=0.5, fail_at=0.9)
    with pytest.raises(VerdictError, match="for lower-is-better fail_at"):
        Threshold("m", pass_at=0.5, fail_at=0.1, direction="lower")
    with pytest.raises(VerdictError, match="pass_at is a number"):
        Threshold("m", float("nan"), 0.1)
    with pytest.raises(VerdictError, match="a metric name"):
        Threshold("", 1, 0)
    assert Threshold("m", 0.5, 0.5).judge(0.5) is Verdict.PASS  # a single bound: no needs-review band


def test_the_overall_verdict_is_the_worst_metric_and_each_metric_is_reported() -> None:
    thresholds = [Threshold("agreement", 0.99, 0.90), Threshold("max_abs", 0.01, 0.05, "lower")]
    assert judge({"agreement": 1.0, "max_abs": 0.0}, thresholds).verdict is Verdict.PASS
    middle = judge({"agreement": 0.95, "max_abs": 0.0}, thresholds)
    assert middle.verdict is Verdict.NEEDS_REVIEW and [m.verdict for m in middle.metrics] == [
        Verdict.NEEDS_REVIEW,
        Verdict.PASS,
    ]
    assert judge({"agreement": 0.95, "max_abs": 0.9}, thresholds).verdict is Verdict.FAIL
    assert worst([Verdict.PASS, Verdict.NEEDS_REVIEW]) is Verdict.NEEDS_REVIEW and worst([]) is Verdict.PASS


def test_a_metric_that_was_not_measured_fails_and_a_case_without_thresholds_is_refused() -> None:
    result = judge({"agreement": 1.0}, [Threshold("agreement", 0.99, 0.9), Threshold("max_abs", 0.01, 0.05, "lower")])
    assert result.verdict is Verdict.FAIL and result.metrics[1].reason == "not measured"
    with pytest.raises(VerdictError, match="no thresholds proves nothing"):
        judge({"agreement": 1.0}, [])
    assert (
        judge({"agreement": math.nan}, [Threshold("agreement", 0.99, 0.9)]).metrics[0].reason == "not a finite number"
    )


def test_a_threshold_round_trips_through_a_dict_and_refuses_unknown_fields() -> None:
    t = Threshold("agreement", 0.99, 0.9)
    assert Threshold.from_dict(t.to_dict()) == t
    with pytest.raises(VerdictError, match=r"unknown field\(s\) \['tolerance'\]"):
        Threshold.from_dict({**t.to_dict(), "tolerance": 1})
    with pytest.raises(VerdictError, match=r"missing field\(s\) \['fail_at'\]"):
        Threshold.from_dict({"metric": "m", "pass_at": 1})


def _review():
    return judge({"agreement": 0.95}, [Threshold("agreement", 0.99, 0.90)])


def test_an_acceptance_resolves_needs_review_only_while_both_hashes_match() -> None:
    accepted = AcceptedDifferences()
    accepted.accept("case-a", H1, H2, "Maya's playblast clamps the highlight; looked at, fine", "2026-10-08")
    outcome = resolve(_review(), "case-a", H1, H2, accepted)
    assert outcome.verdict is Verdict.PASS and outcome.accepted and "playblast" in (outcome.reason or "")
    moved_capture = resolve(_review(), "case-a", H3, H2, accepted)
    moved_reference = resolve(_review(), "case-a", H1, H3, accepted)
    other_case = resolve(_review(), "case-b", H1, H2, accepted)
    for reopened in (moved_capture, moved_reference, other_case):
        assert reopened.verdict is Verdict.NEEDS_REVIEW and not reopened.accepted


def test_a_fail_is_never_rescued_by_an_acceptance_and_a_pass_stays_a_pass() -> None:
    accepted = AcceptedDifferences()
    accepted.accept("case-a", H1, H2, "reason", "2026-10-08")
    failing = judge({"agreement": 0.1}, [Threshold("agreement", 0.99, 0.90)])
    assert resolve(failing, "case-a", H1, H2, accepted).verdict is Verdict.FAIL
    passing = judge({"agreement": 1.0}, [Threshold("agreement", 0.99, 0.90)])
    outcome = resolve(passing, "case-a", H1, H2, accepted)
    assert outcome.verdict is Verdict.PASS and not outcome.accepted


def test_an_acceptance_needs_valid_hashes_a_reason_and_a_date() -> None:
    accepted = AcceptedDifferences()
    with pytest.raises(VerdictError, match="capture_hash is a SHA-256"):
        accepted.accept("c", "abc", H2, "r", "2026-10-08")
    with pytest.raises(VerdictError, match="a reason is required"):
        accepted.accept("c", H1, H2, "   ", "2026-10-08")
    with pytest.raises(VerdictError, match="date is YYYY-MM-DD"):
        accepted.accept("c", H1, H2, "r", "yesterday")
    with pytest.raises(VerdictError, match="a case id"):
        accepted.accept("", H1, H2, "r", "2026-10-08")
    assert accepted.entries == {}


def test_accepting_again_replaces_the_earlier_acceptance() -> None:
    accepted = AcceptedDifferences()
    accepted.accept("c", H1, H2, "first", "2026-10-08")
    accepted.accept("c", H3, H2, "second", "2026-10-09")
    assert not accepted.applies("c", H1, H2) and accepted.applies("c", H3, H2)


def test_the_file_round_trips_and_a_missing_one_is_no_acceptances(tmp_path: Path) -> None:
    accepted = AcceptedDifferences()
    accepted.accept("b-case", H1, H2, "reason b", "2026-10-08")
    accepted.accept("a-case", H2, H3, "reason a", "2026-10-09")
    path = tmp_path / "accepted.json"
    accepted.save(path)
    text = path.read_text(encoding="utf-8")
    assert text.index("a-case") < text.index("b-case"), "sorted, so a diff of the file reads"
    assert AcceptedDifferences.load(path).entries == accepted.entries
    assert AcceptedDifferences.load(tmp_path / "none.json").entries == {}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{nope", "not valid JSON"),
        ("[]", "exactly 'version' and 'accepted'"),
        (json.dumps({"version": 2, "accepted": {}}), "version 1 is expected"),
        (json.dumps({"version": 1, "accepted": []}), "'accepted' is an object"),
        (
            json.dumps({"version": 1, "accepted": {"c": {"reason": "r"}}}),
            "capture_hash, reference_hash, reason and date",
        ),
        (
            json.dumps(
                {
                    "version": 1,
                    "accepted": {"c": {"capture_hash": "x", "reference_hash": H1, "reason": "r", "date": "2026-10-08"}},
                }
            ),
            "'c': acceptance: capture_hash is a SHA-256",
        ),
    ],
)
def test_a_malformed_accepted_file_is_refused_with_where(text: str, message: str) -> None:
    with pytest.raises(VerdictError, match=message):
        AcceptedDifferences.from_json(text)


def test_an_accepted_file_that_is_not_utf8_is_a_typed_error(tmp_path: Path) -> None:
    path = tmp_path / "accepted.json"
    path.write_bytes(b'{"version": 1, "accepted": {}, "x": "caf' + bytes([233]) + b'"}')
    with pytest.raises(VerdictError, match="not valid JSON"):
        AcceptedDifferences.load(path)
