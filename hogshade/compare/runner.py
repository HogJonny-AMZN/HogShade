"""
HogShade: the runner: cases in, captures made, checks run, verdicts judged, a report out.
Package: hogshade/compare/runner

One capture is made per distinct request, however many cases read it (a control reads its twin's capture). Each case's
check measures, the thresholds judge, and a person's acceptance (``accepted.json``) resolves a needs-review only while
the hashes match. C-2 runs oracle cases; regression and parity cases validate but are refused here, by name, naming the
increment that will run them, rather than skipped quietly.

The runner takes a ``capture`` callable and never imports a host: ``capture(request, directory) -> CaptureSet``.
"""

from __future__ import annotations

import hashlib
import json
import logging as _logging
from collections.abc import Callable, Sequence
from pathlib import Path

from hogshade.compare import oracles
from hogshade.compare.captureset import CaptureSet, pixel_hash
from hogshade.compare.cases import Case
from hogshade.compare.report import CaseResult, Measurement, Report
from hogshade.compare.request import CaptureRequest
from hogshade.compare.verdict import AcceptedDifferences, Verdict, VerdictError, judge, resolve

_MODULE_NAME = "hogshade.compare.runner"
__version__ = "0.1.0"
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
    What an oracle case was compared against, as a hash: the check's name, its version and its parameters. An
    acceptance is tied to it, so changing the check or its parameters re-opens a needs-review.
    """
    identity = {"check": case.check.name, "version": oracles.__version__, "params": case.check.params}
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
    resolve acceptances, and return the report (the caller writes it). A check that cannot measure fails its case with
    the reason; nothing is skipped quietly.
    """
    check_runnable(cases)
    accepted = accepted or AcceptedDifferences()
    out_dir = Path(out_dir)
    captured: dict[str, CaptureSet] = {}
    results: list[CaseResult] = []
    for case in cases:
        key = case.request.content_hash()
        if key not in captured:
            directory = out_dir / _slug(case.request)
            _LOGGER.info(f"capturing {case.request.id} for case {case.id} into {directory}")
            captured[key] = capture(case.request, directory)
        results.append(_run_case(case, captured[key], accepted, out_dir))
    return Report(host, level, dict(versions or {}), tuple(results))


def _run_case(case: Case, got: CaptureSet, accepted: AcceptedDifferences, out_dir: Path) -> CaseResult:
    try:
        rel = got.path.relative_to(out_dir).as_posix() if got.path is not None else None
    except ValueError:
        rel = str(got.path)
    capture_hash, ref_hash = pixel_hash(got.path), reference_hash(case)
    base = {
        "id": case.id,
        "kind": case.kind,
        "expect": case.expect,
        "thresholds": case.thresholds,
        "capture": rel,
        "capture_hash": capture_hash,
        "reference_hash": ref_hash,
    }
    try:
        measured = oracles.run(case, got)
    except (oracles.OracleError, KeyError) as e:
        verdict = Verdict.FAIL
        _LOGGER.error(f"case {case.id}: the check could not measure: {e}")
        return CaseResult(
            verdict=verdict,
            control_ok=(False if case.is_control else None),  # a control that cannot measure proved nothing
            notes=("the check could not measure",),
            error=str(e),
            **base,
        )
    try:
        judgement = judge(measured, case.thresholds)
    except VerdictError as e:  # unreachable for a loaded case (thresholds are validated), kept for a hand-built one
        raise RunnerError(f"case {case.id}: {e}") from e
    measurements = tuple(Measurement(m, float(v), case.check.data_range) for m, v in sorted(measured.items()))
    notes = tuple(f"{m.metric}: {m.verdict.value} ({m.reason})" for m in judgement.metrics)
    if case.is_control:
        return CaseResult(
            verdict=judgement.verdict,
            control_ok=judgement.verdict is Verdict.FAIL,
            measurements=measurements,
            notes=notes,
            **base,
        )
    outcome = resolve(judgement, case.id, capture_hash, ref_hash, accepted)
    if outcome.accepted:
        notes = (*notes, f"accepted: {outcome.reason}")
    return CaseResult(
        verdict=outcome.verdict,
        accepted=outcome.accepted,
        measurements=measurements,
        notes=notes,
        **base,
    )
