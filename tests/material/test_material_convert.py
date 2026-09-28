"""
HogShade: the conversion tables cover every source parameter; convert() v2 to standard yields the mapped
values, the losses and a document that validates against the standard.
Package: tests/material/test_material_convert
"""

from __future__ import annotations

import copy

import pytest

from hogshade.material import (
    Loss,
    MaterialError,
    check_table,
    convert,
    load,
    load_table,
    resolve,
    table_names,
    type_of,
    validate,
)
from hogshade.material.conversion import _apply
from hogshade.material.document import from_data

PAIRS = [
    ("hogshade-legacy-v2", "hogshade-standard"),
    ("hogshade-legacy-v1", "hogshade-standard"),
    ("hogshade-lambert", "hogshade-standard"),
]


def test_three_tables_ship():
    assert table_names() == [f"{a}-to-{b}" for a, b in sorted(PAIRS)]


@pytest.mark.parametrize(("src", "dst"), PAIRS)
def test_table_covers_every_source_parameter(src, dst):
    table = load_table(src, dst)
    assert table["version"] == 1
    assert check_table(table, type_of(src), type_of(dst)) == []
    mapped = {e["from"] for e in table["map"]}
    dropped = {e["from"] for e in table["dropped"]}
    assert mapped | dropped == set(type_of(src).parameters) and not (mapped & dropped)


def test_missing_table_raises():
    with pytest.raises(MaterialError, match="no conversion table"):
        load_table("hogshade-standard", "hogshade-lambert")


def _v2_table():
    return copy.deepcopy(load_table("hogshade-legacy-v2", "hogshade-standard"))


def _messages(table):
    return [
        f"{f.parameter}: {f.message}"
        for f in check_table(table, type_of("hogshade-legacy-v2"), type_of("hogshade-standard"))
    ]


def test_coverage_check_finds_a_forgotten_parameter():
    table = _v2_table()
    table["dropped"] = [d for d in table["dropped"] if d["from"] != "specular_tint"]
    assert _messages(table) == ["specular_tint: neither mapped nor dropped"]


def test_coverage_check_finds_a_duplicate_and_an_unknown_target():
    table = _v2_table()
    table["map"].append({"from": "roughness", "to": "coat_roughness", "transform": "identity"})
    msgs = _messages(table)
    assert any("coat_roughness" in m for m in msgs) and "roughness: appears 2 times" in msgs


def test_coverage_check_payloads():
    table = _v2_table()
    for entry in table["map"]:
        if entry["from"] == "emission_intensity":
            del entry["by"]
        if entry["from"] == "bump_intensity":
            entry["range"] = [0.0]
        if entry["from"] == "opacity":
            entry["value"] = 1.0
        if entry["from"] == "use_cutout_alpha":
            entry["value"] = "dither"
    msgs = _messages(table)
    assert "emission_intensity: transform 'scale' carries 'by'" in msgs
    assert "bump_intensity: range is [min, max]" in msgs
    assert "opacity: transform 'identity' does not carry 'value'" in msgs
    assert any(m.startswith("use_cutout_alpha: constant 'dither' is not a enum") for m in msgs)


def test_coverage_check_bool_needs_constant_and_field_needs_strength():
    table = _v2_table()
    for entry in table["map"]:
        if entry["from"] == "use_cutout_alpha":
            entry["transform"] = "identity"
            del entry["value"]
        if entry["from"] == "bump_intensity":
            entry["to"] = "height"
    msgs = _messages(table)
    assert "use_cutout_alpha: a bool or enum converts only through 'constant'" in msgs
    assert "bump_intensity: target 'height' does not admit field 'strength'" in msgs


def test_dropped_entries_need_a_reason():
    table = _v2_table()
    table["dropped"][0]["reason"] = ""
    assert any(m.endswith("a dropped parameter carries a reason") for m in _messages(table))


@pytest.mark.parametrize(
    ("transform", "entry", "factor", "expected"),
    [
        ("identity", {}, 0.3, 0.3),
        ("invert", {}, 0.3, 0.7),
        ("invert", {}, [0.0, 1.0, 0.5], [1.0, 0.0, 0.5]),
        ("scale", {"by": 100.0}, 3.0, 300.0),
        ("clamp", {"range": [0.0, 4.0]}, 6.0, 4.0),
        ("clamp", {"range": [0.0, 1.0]}, [-1.0, 0.5, 2.0], [0.0, 0.5, 1.0]),
        ("constant", {"value": "mask"}, True, "mask"),
        ("constant", {"value": "mask"}, None, "mask"),
        ("scale", {"by": 2.0}, None, None),
    ],
)
def test_transforms(transform, entry, factor, expected):
    assert _apply(transform, entry, factor) == expected


def test_convert_v2_brick_to_standard(fixtures):
    doc = load(fixtures / "legacy" / "brick_v2.material.json")
    out, losses = convert(doc, "hogshade-standard")
    assert out.material_type == "hogshade-standard" and out.material_type_version == 1 and out.parent is None
    v = out.values
    assert v["base_color"] == {"factor": [0.5, 0.3, 0.2], "texture": "brick_basecolor.png"}
    assert v["specular_roughness"] == {"factor": 0.8}
    assert v["base_metalness"] == {"factor": 0.0}
    assert v["specular_ior"] == {"factor": 1.6}
    assert v["geometry_normal"] == {"texture": "brick_normal.png", "strength": 2.5}
    assert v["cavity"] == {"texture": "brick_cavity.png"}
    assert v["emission_luminance"] == {"factor": 300.0}
    assert v["geometry_opacity"] == {"factor": 0.9}
    assert v["alpha_mode"] == {"factor": "mask"}
    assert "specular_color" not in v, "the F0 map was unbound, so nothing arrives"
    assert "ambient_occlusion" not in v and "height" not in v
    assert Loss("specular_tint", losses[0].reason) == losses[0]
    lost = {loss.parameter for loss in losses}
    assert {"specular_tint", "height_scale", "parallax_enabled", "use_vertex_ao", "normal_flip"} <= lost
    assert lost.isdisjoint(v)
    assert validate(out) == []
    assert validate(resolve(out)) == []


def test_convert_a_resolved_material_and_keep_ext(fixtures):
    res = resolve(load(fixtures / "legacy" / "brick_v2.material.json"))
    res.ext["sj"] = {"tier_cap": 1}
    out, _ = convert(res, "hogshade-standard")
    assert out.ext == {"sj": {"tier_cap": 1}}


def test_convert_v1_and_lambert_defaults_validate():
    for name in ("hogshade-legacy-v1", "hogshade-lambert"):
        out, losses = convert(
            from_data({"material_type": name, "material_type_version": 1, "values": {}}), "hogshade-standard"
        )
        assert validate(out) == [] and validate(resolve(out)) == [], name
    assert losses == []


def test_convert_refuses_a_malformed_table(monkeypatch):
    table = _v2_table()
    table["map"].pop()
    monkeypatch.setattr("hogshade.material.conversion.load_table", lambda a, b: table)
    with pytest.raises(MaterialError, match="malformed conversion table"):
        convert(
            from_data({"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": {}}),
            "hogshade-standard",
        )
