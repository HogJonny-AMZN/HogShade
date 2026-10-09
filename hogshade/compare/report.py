"""
HogShade: the report a comparison run writes: one JSON shape for every kind of case.
Package: hogshade/compare/report

``report.json`` holds the run (host, versions, capture level) and a ``CaseResult`` per case: its kind, its verdict, the
measurements (each carrying the ``data_range`` it was taken with), the thresholds, the capture and the hashes the
verdict and any acceptance depend on. The same shape serves the host oracles, the regression cases and the parity
runs, so a reader learns one page; the HTML view is a later increment and reads this file.

A **control** is a case that is supposed to fail. Its ``verdict`` is the raw outcome and ``control_ok`` says whether it
failed as it should; a control that passes means the instrument cannot tell right from wrong, so the report is not ok.
The report is ok when no ordinary case fails or still needs review and every control failed as it should.
"""

from __future__ import annotations

import json
import logging as _logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from hogshade.compare.cases import EXPECTATIONS, KINDS
from hogshade.compare.verdict import Threshold, Verdict, VerdictError

_MODULE_NAME = "hogshade.compare.report"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

REPORT_VERSION = 1
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ReportError(ValueError):
    """A report that does not match its schema; the message says where."""


@dataclass(frozen=True)
class Measurement:
    """One measured value and the data range it was taken with (null for a check that needs none)."""

    metric: str
    value: float
    data_range: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "value": self.value, "data_range": self.data_range}


@dataclass(frozen=True)
class CaseResult:
    id: str
    kind: str
    verdict: Verdict
    expect: str = "pass"
    accepted: bool = False
    control_ok: bool | None = None
    measurements: tuple[Measurement, ...] = ()
    thresholds: tuple[Threshold, ...] = ()
    capture: str | None = None
    capture_hash: str | None = None
    reference_hash: str | None = None
    notes: tuple[str, ...] = ()
    error: str | None = None

    @property
    def is_control(self) -> bool:
        return self.expect == "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "verdict": self.verdict.value,
            "expect": self.expect,
            "accepted": self.accepted,
            "control_ok": self.control_ok,
            "measurements": [m.to_dict() for m in self.measurements],
            "thresholds": [t.to_dict() for t in self.thresholds],
            "capture": self.capture,
            "capture_hash": self.capture_hash,
            "reference_hash": self.reference_hash,
            "notes": list(self.notes),
            "error": self.error,
        }


@dataclass(frozen=True)
class Report:
    host: str
    level: str
    versions: dict[str, str] = field(default_factory=dict)
    cases: tuple[CaseResult, ...] = ()

    @property
    def summary(self) -> dict[str, int]:
        ordinary = [c for c in self.cases if not c.is_control]
        controls = [c for c in self.cases if c.is_control]
        return {
            "cases": len(ordinary),
            "pass": sum(c.verdict is Verdict.PASS for c in ordinary),
            "needs-review": sum(c.verdict is Verdict.NEEDS_REVIEW for c in ordinary),
            "fail": sum(c.verdict is Verdict.FAIL for c in ordinary),
            "controls": len(controls),
            "controls_ok": sum(c.control_ok is True for c in controls),
        }

    @property
    def ok(self) -> bool:
        s = self.summary
        return s["fail"] == 0 and s["needs-review"] == 0 and s["controls_ok"] == s["controls"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": REPORT_VERSION,
            "run": {"host": self.host, "level": self.level, "versions": dict(self.versions)},
            "summary": self.summary,
            "ok": self.ok,
            "cases": [c.to_dict() for c in self.cases],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> Report:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ReportError(f"report: not valid JSON ({e})") from e
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: object) -> Report:
        top = _object(data, "report", {"version", "run", "summary", "ok", "cases"})
        if top["version"] != REPORT_VERSION:
            raise ReportError(f"report: version {REPORT_VERSION} is expected, got {top['version']!r}")
        run = _object(top["run"], "report.run", {"host", "level", "versions"})
        if not isinstance(run["host"], str) or not run["host"] or not isinstance(run["level"], str):
            raise ReportError("report.run: host and level are strings, host non-empty")
        if not isinstance(run["versions"], dict):
            raise ReportError("report.run.versions: an object is expected")
        if not isinstance(top["cases"], list):
            raise ReportError("report.cases: a list is expected")
        results = tuple(_result(c, f"report.cases[{i}]") for i, c in enumerate(top["cases"]))
        ids = [r.id for r in results]
        if len(set(ids)) != len(ids):
            raise ReportError(f"report.cases: duplicate case id(s) {sorted({i for i in ids if ids.count(i) > 1})}")
        report = cls(run["host"], run["level"], dict(run["versions"]), results)
        if top["summary"] != report.summary or top["ok"] != report.ok:
            raise ReportError("report: the stored summary or ok disagrees with the cases it summarises")
        return report


def _object(data: object, where: str, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(data, dict):
        raise ReportError(f"{where}: an object is expected, got {type(data).__name__}")
    unknown, missing = sorted(set(data) - fields), sorted(fields - set(data))
    if unknown or missing:
        raise ReportError(f"{where}: unknown field(s) {unknown}, missing field(s) {missing}")
    return data


def _hash_or_none(value: object, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ReportError(f"{where}: a SHA-256 in hex or null is expected, got {value!r}")
    return value


def _result(data: object, where: str) -> CaseResult:
    d = _object(
        data,
        where,
        {
            "id",
            "kind",
            "verdict",
            "expect",
            "accepted",
            "control_ok",
            "measurements",
            "thresholds",
            "capture",
            "capture_hash",
            "reference_hash",
            "notes",
            "error",
        },
    )
    if d["kind"] not in KINDS:
        raise ReportError(f"{where}.kind: one of {list(KINDS)} is expected, got {d['kind']!r}")
    if d["expect"] not in EXPECTATIONS:
        raise ReportError(f"{where}.expect: one of {list(EXPECTATIONS)} is expected, got {d['expect']!r}")
    try:
        verdict = Verdict(d["verdict"])
    except ValueError as e:
        raise ReportError(f"{where}.verdict: pass, needs-review or fail is expected, got {d['verdict']!r}") from e
    if not isinstance(d["accepted"], bool) or d["control_ok"] not in (True, False, None):
        raise ReportError(f"{where}: accepted is a boolean and control_ok a boolean or null")
    if (d["expect"] == "fail") != (d["control_ok"] is not None):
        raise ReportError(f"{where}: control_ok is set exactly for a control (expect 'fail')")
    if d["control_ok"] is not None and d["control_ok"] != (verdict is Verdict.FAIL and d["error"] is None):
        raise ReportError(
            f"{where}: control_ok must be true exactly when the control failed by measuring, not by erroring"
        )
    measurements = []
    if not isinstance(d["measurements"], list):
        raise ReportError(f"{where}.measurements: a list is expected")
    for j, m in enumerate(d["measurements"]):
        md = _object(m, f"{where}.measurements[{j}]", {"metric", "value", "data_range"})
        if (
            not isinstance(md["metric"], str)
            or isinstance(md["value"], bool)
            or not isinstance(md["value"], (int, float))
        ):
            raise ReportError(f"{where}.measurements[{j}]: a metric name and a numeric value are expected")
        dr = md["data_range"]
        if dr is not None and (isinstance(dr, bool) or not isinstance(dr, (int, float)) or dr <= 0):
            raise ReportError(
                f"{where}.measurements[{j}].data_range: a positive number or null is expected, got {dr!r}"
            )
        measurements.append(Measurement(md["metric"], md["value"], dr))
    if not isinstance(d["thresholds"], list):
        raise ReportError(f"{where}.thresholds: a list is expected")
    try:
        thresholds = tuple(Threshold.from_dict(t) for t in d["thresholds"])
    except VerdictError as e:
        raise ReportError(f"{where}.thresholds: {e}") from e
    if not isinstance(d["notes"], list) or not all(isinstance(n, str) for n in d["notes"]):
        raise ReportError(f"{where}.notes: a list of strings is expected")
    for key in ("capture", "error"):
        if d[key] is not None and not isinstance(d[key], str):
            raise ReportError(f"{where}.{key}: a string or null is expected")
    return CaseResult(
        id=d["id"],
        kind=d["kind"],
        verdict=verdict,
        expect=d["expect"],
        accepted=d["accepted"],
        control_ok=d["control_ok"],
        measurements=tuple(measurements),
        thresholds=thresholds,
        capture=d["capture"],
        capture_hash=_hash_or_none(d["capture_hash"], f"{where}.capture_hash"),
        reference_hash=_hash_or_none(d["reference_hash"], f"{where}.reference_hash"),
        notes=tuple(d["notes"]),
        error=d["error"],
    )
