"""
HogShade: the runner: cases in, captures made, checks run, verdicts judged, a report out.
Package: hogshade/compare/runner

One capture is made per distinct request, however many cases read it (a control reads its twin's capture). Each case's
check measures, the thresholds judge, and a person's acceptance (``accepted.json``) resolves a needs-review only while
the hashes match. C-2 runs oracle cases; regression and parity cases validate but are refused here, by name, naming the
increment that will run them, rather than skipped quietly.

**A run always yields a report.** A host that fails to capture (a lost device, a full disk, a bug in an adapter), a
capture that is not of the request asked for, or a check that cannot measure fails its case with the reason and the
run goes on, so one bad capture does not cost the results already gathered. The runner takes a ``capture`` callable and
never imports a host: ``capture(request, directory) -> CaptureSet``.
"""

from __future__ import annotations

import hashlib
import json
import logging as _logging
import math
from collections.abc import Callable, Sequence
from pathlib import Path

from hogshade.compare import oracles
from hogshade.compare.captureset import CaptureSet, pixel_hash
from hogshade.compare.cases import Case
from hogshade.compare.report import CaseResult, Measurement, Report
from hogshade.compare.request import CaptureRequest
from hogshade.compare.verdict import AcceptedDifferences, Judgement, Verdict, VerdictError, judge, resolve

_MODULE_NAME = "hogshade.compare.runner"
__version__ = "0.2.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The increments that will run the kinds this one refuses.
LATER = {"regression": "C-3", "parity": "C-5"}

Capture = Callable[[CaptureRequest, Path], CaptureSet]


class RunnerError(ValueError):
    """A run that cannot start; the message says which case and why."""


def check_runnable(cases: Sequence[Case]) -> None:
    """Refuse, by name, a table this runner cannot run, before any capture is made."""
    if not cases:
        raise RunnerError("no cases to run: an empty table proves nothing")
    later = [c for c in cases if c.kind != "oracle"]
    if later:
        listing = ", ".join(f"{c.id} ({c.kind}, increment {LATER[c.kind]})" for c in later)
        raise RunnerError(f"this runner runs oracle cases only; not yet runnable: {listing}")


def reference_hash(case: Case) -> str:
    """
    What an oracle case was compared against, as a hash: the check's name and parameters, the data range, the
    thresholds, and the identity of the oracle code (a hash of its source, so no one has to remember to bump a version).
    An acceptance is tied to it, so changing any of these re-opens a needs-review.
    """
    identity = {
        "check": case.check.name,
        "params": case.check.params,
        "data_range": case.check.data_range,
        "thresholds": [t.to_dict() for t in case.thresholds],
        "code": oracles.code_identity(),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _slug(request: CaptureRequest) -> str:
    return f"{request.id}-{request.content_hash()[:8]}"


def run(
    cases: Sequence[Case],
    capture: Capture,
    out_dir: Path,
    host: str,
    level: str,
    versions: dict[str, str] | None = None,
    accepted: AcceptedDifferences | None = None,
) -> Report:
    """
    Run oracle ``cases``: capture each distinct request once into ``out_dir/<request id>-<hash>/``, measure, judge,
    resolve acceptances, and return the report (the caller writes it). Whatever goes wrong with one capture or one check
    fails that case with the reason; nothing is skipped quietly and the rest of the table still runs.
    """
    check_runnable(cases)
    accepted = accepted or AcceptedDifferences()
    out_dir = Path(out_dir)
    captured: dict[str, CaptureSet | str] = {}  # a capture, or the reason it could not be made
    results: list[CaseResult] = []
    _LOGGER.info(f"running {len(cases)} case(s) on {host} at level {level}, captures under {out_dir}")
    for case in cases:
        key = case.request.content_hash()
        if key not in captured:
            captured[key] = _capture_once(capture, case, out_dir, host, level)
        got = captured[key]
        if isinstance(got, str):
            results.append(_failed(case, got))
        else:
            results.append(_run_case(case, got, accepted, out_dir))
    report = Report(host, level, dict(versions or {}), tuple(results))
    s = report.summary
    _LOGGER.info(
        f"ran {s['cases']} case(s): {s['pass']} pass, {s['needs-review']} needs-review, {s['fail']} fail; "
        f"{s['controls_ok']} of {s['controls']} control(s) failed as they should"
    )
    return report


def _capture_once(capture: Capture, case: Case, out_dir: Path, host: str, level: str) -> CaptureSet | str:
    """
    The capture of ``case``'s request, or the reason there is none: it raised, it is of another request, or its manifest
    names a different host or level than the run reports (an L1 capture must not be reported as L2p).
    """
    directory = out_dir / _slug(case.request)
    _LOGGER.info(f"capturing {case.request.id} for case {case.id} into {directory}")
    try:
        got = capture(case.request, directory)
    except Exception as e:  # noqa: BLE001 - log whatever a host throws and keep going: one bad capture is one failed case
        reason = f"the capture failed: {type(e).__name__}: {e}"
        _LOGGER.error(f"{case.request.id}: {reason}")
        return reason
    if got.request.content_hash() != case.request.content_hash():
        reason = f"the capture is of request {got.request.id!r}, not the {case.request.id!r} that was asked for"
        _LOGGER.error(reason)
        return reason
    if got.manifest.host != host or got.manifest.level != level:
        reason = (
            f"the capture's manifest says host {got.manifest.host!r} at level {got.manifest.level}, "
            f"but the run is {host!r} at level {level}"
        )
        _LOGGER.error(f"{case.request.id}: {reason}")
        return reason
    return got


def _failed(case: Case, reason: str, capture: str | None = None, capture_hash: str | None = None) -> CaseResult:
    """A case that produced no measurement: it fails with the reason, and a control that does so proved nothing."""
    return CaseResult(
        id=case.id,
        kind=case.kind,
        verdict=Verdict.FAIL,
        expect=case.expect,
        control_ok=(False if case.is_control else None),
        thresholds=case.thresholds,
        capture=capture,
        capture_hash=capture_hash,
        reference_hash=reference_hash(case),
        notes=("no measurement was made",),
        error=reason,
    )


def _control_ok(case: Case, judgement: Judgement) -> bool:
    """A control is ok when it failed, and on the metrics it names (any, when it names none)."""
    if judgement.verdict is not Verdict.FAIL:
        return False
    failing = {m.metric for m in judgement.metrics if m.verdict is Verdict.FAIL}
    return set(case.fails_on) <= failing


def _run_case(case: Case, got: CaptureSet, accepted: AcceptedDifferences, out_dir: Path) -> CaseResult:
    try:
        rel = got.path.relative_to(out_dir).as_posix()
    except ValueError:
        rel = str(got.path)
    capture_hash = pixel_hash(got.path)
    try:
        measured = oracles.run(case, got)
    except oracles.OracleError as e:
        _LOGGER.error(f"case {case.id}: the check could not measure: {e}")
        return _failed(case, str(e), rel, capture_hash)
    try:
        judgement = judge(measured, case.thresholds)
    except VerdictError as e:  # unreachable for a loaded case (thresholds are validated), kept for a hand-built one
        raise RunnerError(f"case {case.id}: {e}") from e
    ref_hash = reference_hash(case)
    measurements = tuple(
        Measurement(
            m, float(v) if math.isfinite(v) else None, case.check.data_range
        )  # JSON cannot hold NaN or infinity
        for m, v in sorted(measured.items())
    )
    notes = tuple(f"{m.metric}: {m.verdict.value} ({m.reason})" for m in judgement.metrics)
    base = {
        "id": case.id,
        "kind": case.kind,
        "expect": case.expect,
        "thresholds": case.thresholds,
        "capture": rel,
        "capture_hash": capture_hash,
        "reference_hash": ref_hash,
        "measurements": measurements,
    }
    if case.is_control:
        ok = _control_ok(case, judgement)
        how = "failed as it should" if ok else "DID NOT fail as it should"
        _LOGGER.info(f"control {case.id}: {judgement.verdict.value}, {how}")
        return CaseResult(verdict=judgement.verdict, control_ok=ok, notes=notes, **base)
    outcome = resolve(judgement, case.id, capture_hash, ref_hash, accepted)
    if outcome.accepted:
        notes = (*notes, f"accepted: {outcome.reason}")
    shown = ", ".join(
        f"{m.metric} {'n/a' if m.value is None else format(m.value, 'g')}" for m in measurements if m.metric != "probed"
    )
    _LOGGER.info(f"case {case.id}: {outcome.verdict.value}{' (accepted)' if outcome.accepted else ''} ({shown})")
    return CaseResult(verdict=outcome.verdict, accepted=outcome.accepted, notes=notes, **base)
