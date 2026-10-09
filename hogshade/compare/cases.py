"""
HogShade: the case table: what to render, what to check about it, and where each metric's bounds are.
Package: hogshade/compare/cases

A case is a request, a check and thresholds. There is no global tolerance: each case names the metric and the bounds
it holds, and the verdict record repeats them. Three kinds share the machinery (``oracle``: the answer is computable;
``regression``: against the host's own baseline; ``parity``: against another host), but C-2 runs only oracles, and
``load`` accepts the other two so a table can be written ahead of the code that runs it.

A **control** is a case with ``"expect": "fail"``: the same check with its expectation wrong on purpose.
It must fail.
A control that passes means the instrument cannot tell right from wrong, and the run fails.

``check.data_range`` is the explicit peak any check that measures a float frame needs; the registry says which checks
do, and a missing or non-positive range is refused here, before anything renders. Files are JSON under
``verification/cases/``::

    {"version": 1, "cases": [{"id": ..., "kind": "oracle", "request": {...},
                               "check": {"name": ..., "data_range": 1.0, "params": {...}},
                               "thresholds": [{"metric": ..., "pass_at": ..., "fail_at": ..., "direction": ...}],
                               "expect": "pass"}]}
"""

from __future__ import annotations

import json
import logging as _logging
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hogshade.compare.request import CaptureRequest, RequestError
from hogshade.compare.verdict import Threshold, VerdictError

_MODULE_NAME = "hogshade.compare.cases"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

CASES_VERSION = 1
KINDS = ("oracle", "regression", "parity")
EXPECTATIONS = ("pass", "fail")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")


class CaseError(ValueError):
    """A case or case file that is malformed; the message names the file and the field."""


@dataclass(frozen=True)
class CheckSpec:
    """What the registry knows about a check: the kinds it serves and whether it needs an explicit data range."""

    name: str
    kinds: tuple[str, ...]
    needs_data_range: bool
    description: str


@dataclass(frozen=True)
class Check:
    name: str
    data_range: float | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name, "params": dict(self.params)}
        if self.data_range is not None:
            out["data_range"] = self.data_range
        return out


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    request: CaptureRequest
    check: Check
    thresholds: tuple[Threshold, ...]
    expect: str = "pass"

    @property
    def is_control(self) -> bool:
        return self.expect == "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "request": self.request.to_dict(),
            "check": self.check.to_dict(),
            "thresholds": [t.to_dict() for t in self.thresholds],
            "expect": self.expect,
        }


def _case(data: object, where: str, registry: Mapping[str, CheckSpec] | None) -> Case:
    if not isinstance(data, dict):
        raise CaseError(f"{where}: an object is expected, got {type(data).__name__}")
    unknown = sorted(set(data) - {"id", "kind", "request", "check", "thresholds", "expect"})
    missing = sorted({"id", "kind", "request", "check", "thresholds"} - set(data))
    if unknown or missing:
        raise CaseError(f"{where}: unknown field(s) {unknown}, missing field(s) {missing}")
    cid = data["id"]
    if not isinstance(cid, str) or not _ID.fullmatch(cid):
        raise CaseError(f"{where}: id: lowercase letters, digits, '.', '_' or '-' are expected, got {cid!r}")
    where = f"{where}: case {cid!r}"
    if data["kind"] not in KINDS:
        raise CaseError(f"{where}: kind: one of {list(KINDS)} is expected, got {data['kind']!r}")
    expect = data.get("expect", "pass")
    if expect not in EXPECTATIONS:
        raise CaseError(f"{where}: expect: one of {list(EXPECTATIONS)} is expected, got {expect!r}")
    try:
        request = CaptureRequest.from_dict(data["request"])
    except RequestError as e:
        raise CaseError(f"{where}: request: {e}") from e
    check_data = data["check"]
    if (
        not isinstance(check_data, dict)
        or set(check_data) - {"name", "data_range", "params"}
        or "name" not in check_data
    ):
        raise CaseError(f"{where}: check: an object with 'name' and optionally 'data_range' and 'params' is expected")
    name = check_data["name"]
    if not isinstance(name, str) or not name:
        raise CaseError(f"{where}: check.name: a name is expected, got {name!r}")
    params = check_data.get("params", {})
    if not isinstance(params, dict):
        raise CaseError(f"{where}: check.params: an object is expected, got {type(params).__name__}")
    data_range = check_data.get("data_range")
    if data_range is not None and (
        isinstance(data_range, bool)
        or not isinstance(data_range, (int, float))
        or not math.isfinite(data_range)
        or data_range <= 0
    ):
        raise CaseError(f"{where}: check.data_range: a positive finite number is expected, got {data_range!r}")
    thresholds_data = data["thresholds"]
    if not isinstance(thresholds_data, list) or not thresholds_data:
        raise CaseError(f"{where}: thresholds: at least one is expected; a case with none proves nothing")
    try:
        thresholds = tuple(Threshold.from_dict(t) for t in thresholds_data)
    except VerdictError as e:
        raise CaseError(f"{where}: thresholds: {e}") from e
    if registry is not None:
        spec = registry.get(name)
        if spec is None:
            raise CaseError(f"{where}: check.name: no check named {name!r}; the registry has {sorted(registry)}")
        if data["kind"] not in spec.kinds:
            raise CaseError(f"{where}: check {name!r} serves {list(spec.kinds)}, not kind {data['kind']!r}")
        if spec.needs_data_range and data_range is None:
            raise CaseError(
                f"{where}: check.data_range: check {name!r} measures a float frame and needs an explicit peak"
            )
    return Case(
        cid,
        data["kind"],
        request,
        Check(name, None if data_range is None else float(data_range), dict(params)),
        thresholds,
        expect,
    )


def load_file(path: Path, registry: Mapping[str, CheckSpec] | None = None) -> list[Case]:
    """The cases in one JSON file, validated; ``registry`` (check name to ``CheckSpec``) validates the checks too."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CaseError(f"{path}: not valid JSON ({e})") from e
    if not isinstance(data, dict) or set(data) != {"version", "cases"}:
        raise CaseError(f"{path}: an object with exactly 'version' and 'cases' is expected")
    if data["version"] != CASES_VERSION:
        raise CaseError(f"{path}: version {CASES_VERSION} is expected, got {data['version']!r}")
    if not isinstance(data["cases"], list) or not data["cases"]:
        raise CaseError(f"{path}: 'cases' is a non-empty list")
    return [_case(c, str(path), registry) for c in data["cases"]]


def load(directory: Path, registry: Mapping[str, CheckSpec] | None = None) -> list[Case]:
    """Every case under ``directory`` (``*.json``, sorted), with ids unique across files."""
    directory = Path(directory)
    if not directory.is_dir():
        raise CaseError(f"{directory}: not a directory")
    cases: list[Case] = []
    seen: dict[str, Path] = {}
    for path in sorted(directory.glob("*.json")):
        for case in load_file(path, registry):
            if case.id in seen:
                raise CaseError(f"{path}: case {case.id!r} is already defined in {seen[case.id]}")
            seen[case.id] = path
            cases.append(case)
    return cases


def dump(cases: list[Case]) -> str:
    """A case file's text for ``cases``: the canonical form ``load_file`` reads back."""
    body = {"version": CASES_VERSION, "cases": [c.to_dict() for c in cases]}
    return json.dumps(body, indent=2, sort_keys=True) + "\n"
