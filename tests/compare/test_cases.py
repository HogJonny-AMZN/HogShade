"""
HogShade: the case table: schema, controls, the explicit data range and the registry.
Package: tests/compare/test_cases
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hogshade.compare import cases
from hogshade.compare.cases import CaseError, CheckSpec

REGISTRY = {
    "texel": CheckSpec("texel", ("oracle",), needs_data_range=True, description="the texel a pixel must show"),
    "coverage": CheckSpec("coverage", ("oracle", "parity"), needs_data_range=False, description="mask overlap"),
}
REQUEST = {
    "id": "quad-sphere-roughness",
    "mesh": "quad-sphere",
    "camera": {
        "eye": [1.6, 1.0, 3.8],
        "target": [0.0, 0.05, 0.0],
        "up": [0.0, 1.0, 0.0],
        "fov_y_deg": 32.0,
        "near": 0.05,
        "far": 50.0,
    },
    "rig": {"environment": "studio_small_09"},
    "size": [512, 512],
}
CASE = {
    "id": "texel-roughness",
    "kind": "oracle",
    "request": REQUEST,
    "check": {"name": "texel", "data_range": 1.0, "params": {"map": "_R"}},
    "thresholds": [{"metric": "agreement", "pass_at": 0.99, "fail_at": 0.9, "direction": "higher"}],
}


def _write(tmp_path: Path, *case_list, name: str = "c.json", version: int = 1) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"version": version, "cases": list(case_list)}), encoding="utf-8")
    return path


def _bad(path: str, value) -> dict:
    data = copy.deepcopy(CASE)
    node = data
    *head, last = path.split(".")
    for key in head:
        node = node[key]
    if value is ...:
        del node[last]
    else:
        node[last] = value
    return data


def test_a_case_file_loads_and_round_trips(tmp_path: Path) -> None:
    got = cases.load_file(_write(tmp_path, CASE), REGISTRY)
    assert len(got) == 1 and got[0].id == "texel-roughness" and got[0].kind == "oracle" and not got[0].is_control
    assert got[0].check.data_range == 1.0 and got[0].thresholds[0].pass_at == 0.99
    again = tmp_path / "again.json"
    again.write_text(cases.dump(got), encoding="utf-8")
    assert cases.load_file(again, REGISTRY) == got


def test_a_control_is_a_case_that_expects_to_fail(tmp_path: Path) -> None:
    control = {
        **CASE,
        "id": "texel-roughness-v-flipped",
        "expect": "fail",
        "check": {**CASE["check"], "params": {"flip_v": True}},
    }
    (loaded,) = cases.load_file(_write(tmp_path, control), REGISTRY)
    assert loaded.is_control and loaded.expect == "fail" and loaded.check.params == {"flip_v": True}


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("id", "Not Valid", "id: lowercase letters"),
        ("kind", "magic", "kind: one of"),
        ("expect", "maybe", "expect: one of"),
        ("thresholds", [], "at least one is expected; a case with none proves nothing"),
        ("thresholds", "x", "at least one is expected"),
        (
            "thresholds",
            [{"metric": "m", "pass_at": 0.5, "fail_at": 0.9}],
            "thresholds: threshold m: for higher-is-better",
        ),
        ("check", {"name": ""}, "check.name"),
        ("check", {"data_range": 1.0}, "check: an object with 'name'"),
        ("check", {"name": "texel", "extra": 1}, "check: an object with 'name'"),
        ("check.data_range", 0, "check.data_range: a positive finite number"),
        ("check.data_range", -1.0, "check.data_range: a positive finite number"),
        ("check.data_range", float("inf"), "check.data_range: a positive finite number"),
        ("check.data_range", True, "check.data_range: a positive finite number"),
        ("check.params", [1], "check.params: an object"),
        ("request.mesh", "polar", "request: mesh: one of"),
        ("request.host", "maya", "request: request: unknown field"),
    ],
)
def test_a_malformed_case_is_refused_with_its_file_and_field(tmp_path: Path, path: str, value, message: str) -> None:
    file = _write(tmp_path, _bad(path, value))
    with pytest.raises(CaseError, match=message) as info:
        cases.load_file(file, REGISTRY)
    assert str(file) in str(info.value)


def test_a_check_that_measures_a_float_frame_needs_its_data_range(tmp_path: Path) -> None:
    missing = _bad("check.data_range", ...)
    with pytest.raises(
        CaseError, match="check.data_range: check 'texel' measures a float frame and needs an explicit peak"
    ):
        cases.load_file(_write(tmp_path, missing), REGISTRY)
    structural = {**CASE, "check": {"name": "coverage"}, "id": "mask"}
    assert cases.load_file(_write(tmp_path, structural, name="s.json"), REGISTRY)[0].check.data_range is None


def test_the_registry_decides_which_checks_exist_and_which_kinds_they_serve(tmp_path: Path) -> None:
    with pytest.raises(CaseError, match=r"no check named 'nope'"):
        cases.load_file(_write(tmp_path, _bad("check.name", "nope")), REGISTRY)
    with pytest.raises(CaseError, match=r"check 'texel' serves \['oracle'\], not kind 'parity'"):
        cases.load_file(_write(tmp_path, _bad("kind", "parity")), REGISTRY)
    # without a registry the structure alone is validated (a table can be written ahead of the code that runs it)
    assert cases.load_file(_write(tmp_path, _bad("check.name", "nope"), name="n.json"))[0].check.name == "nope"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{nope", "not valid JSON"),
        ("[]", "exactly 'version' and 'cases'"),
        (json.dumps({"version": 2, "cases": [CASE]}), "version 1 is expected"),
        (json.dumps({"version": 1, "cases": []}), "non-empty list"),
        (json.dumps({"version": 1, "cases": [7]}), "an object is expected"),
    ],
)
def test_a_malformed_file_is_refused(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CaseError, match=message):
        cases.load_file(path)


def test_a_directory_loads_in_order_and_case_ids_are_unique_across_files(tmp_path: Path) -> None:
    _write(tmp_path, CASE, name="a.json")
    _write(tmp_path, {**CASE, "id": "second"}, name="b.json")
    assert [c.id for c in cases.load(tmp_path, REGISTRY)] == ["texel-roughness", "second"]
    _write(tmp_path, CASE, name="c.json")
    with pytest.raises(CaseError, match="case 'texel-roughness' is already defined in"):
        cases.load(tmp_path, REGISTRY)
    with pytest.raises(CaseError, match="not a directory"):
        cases.load(tmp_path / "missing")
