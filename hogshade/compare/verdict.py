"""
HogShade: the verdict: pass, needs-review or fail, and the accepted-differences file a human writes.
Package: hogshade/compare/verdict

The model is the one LargeWorlds uses for its noise oracle vectors (owner, 2026-09-26): a measurement inside its pass
bound passes, one past its hard bound fails, and one between the two is **needs-review**, which writes the diff
artifacts for a person and waits. A person records the verdict in ``verification/accepted.json`` with a reason and the
hashes of the capture and of what it was compared against; the acceptance holds **only while both hashes match**, so
a later change re-opens it. A fail is never rescued by an acceptance.

Bounds are inclusive on the pass and needs-review side: for a metric where higher is better (``direction="higher"``) a
value at or above ``pass_at`` passes and one below ``fail_at`` fails; for lower-is-better the mirror image. A case with
no thresholds proves nothing and is refused, and a metric that was not measured, or is not a finite number, fails.
"""

from __future__ import annotations

import json
import logging as _logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

_MODULE_NAME = "hogshade.compare.verdict"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

ACCEPTED_VERSION = 1
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class VerdictError(ValueError):
    """A threshold or an accepted-differences file that is malformed; the message says where."""


class Verdict(str, Enum):
    PASS = "pass"
    NEEDS_REVIEW = "needs-review"
    FAIL = "fail"

    @property
    def severity(self) -> int:
        return {"pass": 0, "needs-review": 1, "fail": 2}[self.value]


def worst(verdicts: Sequence[Verdict]) -> Verdict:
    """The most severe of ``verdicts`` (fail over needs-review over pass); pass for none."""
    return max(verdicts, key=lambda v: v.severity, default=Verdict.PASS)


@dataclass(frozen=True)
class Threshold:
    """One metric's bounds. ``direction`` is ``"higher"`` or ``"lower"``, meaning which way is better."""

    metric: str
    pass_at: float
    fail_at: float
    direction: str = "higher"

    def __post_init__(self) -> None:
        if not self.metric or not isinstance(self.metric, str):
            raise VerdictError(f"threshold: a metric name is expected, got {self.metric!r}")
        if self.direction not in ("higher", "lower"):
            raise VerdictError(f"threshold {self.metric}: direction is 'higher' or 'lower', got {self.direction!r}")
        for name, value in (("pass_at", self.pass_at), ("fail_at", self.fail_at)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value):
                raise VerdictError(f"threshold {self.metric}: {name} is a number, got {value!r}")
        if self.direction == "higher" and self.fail_at > self.pass_at:
            raise VerdictError(
                f"threshold {self.metric}: for higher-is-better fail_at ({self.fail_at}) is at most "
                f"pass_at ({self.pass_at})"
            )
        if self.direction == "lower" and self.fail_at < self.pass_at:
            raise VerdictError(
                f"threshold {self.metric}: for lower-is-better fail_at ({self.fail_at}) is at least "
                f"pass_at ({self.pass_at})"
            )

    def judge(self, value: float) -> Verdict:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            return Verdict.FAIL
        if self.direction == "higher":
            if value >= self.pass_at:
                return Verdict.PASS
            return Verdict.FAIL if value < self.fail_at else Verdict.NEEDS_REVIEW
        if value <= self.pass_at:
            return Verdict.PASS
        return Verdict.FAIL if value > self.fail_at else Verdict.NEEDS_REVIEW

    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "pass_at": self.pass_at, "fail_at": self.fail_at, "direction": self.direction}

    @classmethod
    def from_dict(cls, data: object) -> Threshold:
        if not isinstance(data, Mapping):
            raise VerdictError(f"threshold: an object is expected, got {type(data).__name__}")
        unknown = sorted(set(data) - {"metric", "pass_at", "fail_at", "direction"})
        missing = sorted({"metric", "pass_at", "fail_at"} - set(data))
        if unknown or missing:
            raise VerdictError(f"threshold: unknown field(s) {unknown}, missing field(s) {missing}")
        return cls(data["metric"], data["pass_at"], data["fail_at"], data.get("direction", "higher"))


@dataclass(frozen=True)
class MetricVerdict:
    metric: str
    value: float | None
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class Judgement:
    """The verdict of one case's measurements against its thresholds: overall, and metric by metric."""

    verdict: Verdict
    metrics: tuple[MetricVerdict, ...]


def judge(measurements: Mapping[str, float], thresholds: Sequence[Threshold]) -> Judgement:
    """The worst of the per-metric verdicts. A metric that was not measured fails, as does a non-finite one."""
    if not thresholds:
        raise VerdictError("a case with no thresholds proves nothing; at least one is expected")
    out = []
    for t in thresholds:
        if t.metric not in measurements:
            out.append(MetricVerdict(t.metric, None, Verdict.FAIL, "not measured"))
            continue
        value = measurements[t.metric]
        verdict = t.judge(value)
        reason = (
            "not a finite number"
            if verdict is Verdict.FAIL and not (isinstance(value, (int, float)) and math.isfinite(value))
            else f"{value:g} against pass {t.pass_at:g}, fail {t.fail_at:g} ({t.direction} is better)"
        )
        out.append(MetricVerdict(t.metric, value, verdict, reason))
    return Judgement(worst([m.verdict for m in out]), tuple(out))


@dataclass(frozen=True)
class Acceptance:
    """A person's recorded verdict on one case: valid only for these two hashes."""

    capture_hash: str
    reference_hash: str
    reason: str
    date: str

    def __post_init__(self) -> None:
        for name, value in (("capture_hash", self.capture_hash), ("reference_hash", self.reference_hash)):
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise VerdictError(f"acceptance: {name} is a SHA-256 in hex, got {value!r}")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise VerdictError("acceptance: a reason is required; an accepted difference with no why is a silent one")
        if not isinstance(self.date, str) or not _DATE.fullmatch(self.date):
            raise VerdictError(f"acceptance: date is YYYY-MM-DD, got {self.date!r}")


@dataclass
class AcceptedDifferences:
    """``verification/accepted.json``: case id to its acceptance."""

    entries: dict[str, Acceptance] = field(default_factory=dict)

    def accept(self, case_id: str, capture_hash: str, reference_hash: str, reason: str, date: str) -> None:
        """Record (or replace) the acceptance of ``case_id``."""
        if not case_id or not isinstance(case_id, str):
            raise VerdictError(f"acceptance: a case id is expected, got {case_id!r}")
        self.entries[case_id] = Acceptance(capture_hash, reference_hash, reason, date)

    def applies(self, case_id: str, capture_hash: str, reference_hash: str) -> bool:
        """Whether ``case_id`` is accepted for exactly these two hashes."""
        found = self.entries.get(case_id)
        return found is not None and found.capture_hash == capture_hash and found.reference_hash == reference_hash

    def to_json(self) -> str:
        body = {
            "version": ACCEPTED_VERSION,
            "accepted": {
                cid: {
                    "capture_hash": a.capture_hash,
                    "reference_hash": a.reference_hash,
                    "reason": a.reason,
                    "date": a.date,
                }
                for cid, a in sorted(self.entries.items())
            },
        }
        return json.dumps(body, indent=2, sort_keys=True) + "\n"

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8", newline="\n")

    @classmethod
    def from_json(cls, text: str, where: str = "accepted.json") -> AcceptedDifferences:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise VerdictError(f"{where}: not valid JSON ({e})") from e
        if not isinstance(data, dict) or set(data) != {"version", "accepted"}:
            raise VerdictError(f"{where}: an object with exactly 'version' and 'accepted' is expected")
        if data["version"] != ACCEPTED_VERSION:
            raise VerdictError(f"{where}: version {ACCEPTED_VERSION} is expected, got {data['version']!r}")
        if not isinstance(data["accepted"], dict):
            raise VerdictError(f"{where}: 'accepted' is an object of case ids")
        out = cls()
        for cid, entry in data["accepted"].items():
            if not isinstance(entry, dict) or set(entry) != {"capture_hash", "reference_hash", "reason", "date"}:
                raise VerdictError(f"{where}: {cid!r}: capture_hash, reference_hash, reason and date are expected")
            try:
                out.accept(cid, entry["capture_hash"], entry["reference_hash"], entry["reason"], entry["date"])
            except VerdictError as e:
                raise VerdictError(f"{where}: {cid!r}: {e}") from e
        return out

    @classmethod
    def load(cls, path: Path) -> AcceptedDifferences:
        """Read ``path``; a missing file is no acceptances (the first run has none)."""
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise VerdictError(f"{path}: not valid JSON ({e})") from e
        return cls.from_json(text, str(path))


@dataclass(frozen=True)
class Outcome:
    """A case's final verdict after acceptances: ``accepted`` is true when needs-review was resolved by a person."""

    verdict: Verdict
    accepted: bool
    reason: str | None = None


def resolve(
    judgement: Judgement,
    case_id: str,
    capture_hash: str,
    reference_hash: str,
    accepted: AcceptedDifferences,
) -> Outcome:
    """
    Apply the acceptances. Only needs-review can be accepted, and only for the exact hashes recorded; a fail stays a
    fail, and a needs-review whose hashes moved is needs-review again.
    """
    if judgement.verdict is Verdict.NEEDS_REVIEW and accepted.applies(case_id, capture_hash, reference_hash):
        return Outcome(Verdict.PASS, True, accepted.entries[case_id].reason)
    return Outcome(judgement.verdict, False, None)
