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
    conditions_of,
    convert,
    from_data,
    load,
    load_table,
    resolve,
    table_names,
    type_of,
    validate,
)
from hogshade.material.conversion import _apply

PAIRS = [
    ("hogshade-legacy-v2", "hogshade-standard"),
    ("hogshade-legacy-v1", "hogshade-standard"),
    ("hogshade-lambert", "hogshade-standard"),
    ("hogshade-standard", "hogshade-legacy-v2"),  # the reverse table (S4a)
]


def test_four_tables_ship():
    assert table_names() == [f"{a}-to-{b}" for a, b in sorted(PAIRS)]


@pytest.mark.parametrize(("src", "dst"), PAIRS)
def test_table_covers_every_source_parameter(src, dst):
    table = load_table(src, dst)
    assert table["version"] == 1
    assert check_table(table, type_of(src), type_of(dst)) == []
    mapped = {e["from"] for e in table["map"]}
    dropped = {e["from"] for e in table["dropped"]}
    consulted = {name for e in table["map"] if isinstance(e.get("when"), dict) for name in e["when"]}
    assert mapped | dropped | consulted == set(type_of(src).parameters) and not (mapped & dropped)


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
    assert _messages(table) == ["specular_tint: neither mapped, consulted nor dropped"]


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


@pytest.mark.parametrize(
    ("name", "expected_losses"),
    [
        ("hogshade-legacy-v1", 12),
        ("hogshade-lambert", 0),
    ],
)
def test_convert_v1_and_lambert_defaults_validate(name, expected_losses):
    out, losses = convert(
        from_data({"material_type": name, "material_type_version": 1, "values": {}}), "hogshade-standard"
    )
    assert validate(out) == [] and validate(resolve(out)) == [], name
    assert len(losses) == expected_losses
    assert {loss.parameter for loss in losses} == {d["from"] for d in load_table(name, "hogshade-standard")["dropped"]}


def test_conditional_constant_fires_only_when_the_source_matches():
    def brick(cutout):
        values = {"use_cutout_alpha": {"factor": cutout}}
        return from_data({"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": values})

    on, _ = convert(brick(True), "hogshade-standard")
    off, _ = convert(brick(False), "hogshade-standard")
    assert on.values["alpha_mode"] == {"factor": "mask"}
    assert off.values["alpha_mode"] == {"factor": "opaque"}, "cutout off and has_alpha off: the opaque entry fires"


def test_coverage_check_when_only_on_constant_and_of_the_source_type():
    table = _v2_table()
    for entry in table["map"]:
        if entry["from"] == "roughness":
            entry["when"] = 0.5
        if entry["from"] == "use_cutout_alpha":
            entry["when"] = "yes"
    msgs = _messages(table)
    assert "roughness: transform 'identity' does not carry 'when'" in msgs
    assert "use_cutout_alpha: when 'yes' is not a bool value of 'use_cutout_alpha'" in msgs


def test_transforms_accept_tuples_and_return_copies():
    assert _apply("invert", {}, (0.0, 1.0, 0.5)) == [1.0, 0.0, 0.5]
    source = [0.5, 0.3, 0.2]
    out = _apply("identity", {}, source)
    assert out == source and out is not source
    constant = {"value": [1.0, 1.0, 1.0]}
    assert _apply("constant", constant, None) is not constant["value"]


def test_converted_values_do_not_alias_the_source(fixtures):
    res = resolve(load(fixtures / "legacy" / "brick_v2.material.json"))
    out, _ = convert(res, "hogshade-standard")
    out.values["base_color"]["factor"][0] = 9.0
    assert res.values["base_color"]["factor"] == [0.5, 0.3, 0.2]


def test_convert_refuses_a_malformed_table(monkeypatch):
    table = _v2_table()
    table["map"] = [e for e in table["map"] if e["from"] != "roughness"]
    monkeypatch.setattr("hogshade.material.conversion.load_table", lambda a, b: table)
    with pytest.raises(MaterialError, match="malformed conversion table"):
        convert(
            from_data({"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": {}}),
            "hogshade-standard",
        )


def test_the_tables_cover_every_alpha_case():
    for src in ("hogshade-legacy-v2", "hogshade-legacy-v1"):
        entries = [e for e in load_table(src, "hogshade-standard")["map"] if e["from"] == "use_cutout_alpha"]
        cases = {frozenset(conditions_of(e).items()): e["value"] for e in entries}
        assert cases == {
            frozenset({("use_cutout_alpha", True)}): "mask",
            frozenset({("use_cutout_alpha", False), ("has_alpha", True)}): "blend",
            frozenset({("use_cutout_alpha", False), ("has_alpha", False)}): "opaque",
        }, src


def test_coverage_check_conditional_entries_are_distinct_and_unmixed():
    table = _v2_table()
    cutout = [e for e in table["map"] if e["from"] == "use_cutout_alpha"]
    table["map"].append(dict(cutout[0]))
    assert "use_cutout_alpha: when True appears twice" in _messages(table)
    table = _v2_table()
    table["map"].append({"from": "use_cutout_alpha", "to": "alpha_mode", "transform": "constant", "value": "opaque"})
    assert "use_cutout_alpha: mixes conditional and unconditional entries" in _messages(table)


# ------------------------------------------------------------------------------ the second review round


def _v2(values):
    return from_data({"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": values})


@pytest.mark.parametrize(
    ("cutout", "has_alpha", "expected"),
    [(True, False, "mask"), (True, True, "mask"), (False, True, "blend"), (False, False, "opaque")],
)
def test_alpha_mode_follows_both_legacy_flags(cutout, has_alpha, expected):
    out, losses = convert(
        _v2({"use_cutout_alpha": {"factor": cutout}, "has_alpha": {"factor": has_alpha}}), "hogshade-standard"
    )
    assert out.values["alpha_mode"] == {"factor": expected}
    assert "has_alpha" not in {loss.parameter for loss in losses}, "consulted by a condition, not dropped"


def test_an_opaque_legacy_material_converts_to_opaque():
    out, _ = convert(_v2({}), "hogshade-standard")
    assert out.values["alpha_mode"] == {"factor": "opaque"}


def test_when_object_names_source_parameters_of_the_right_type():
    table = _v2_table()
    table["map"].append(
        {
            "from": "use_cutout_alpha",
            "to": "alpha_mode",
            "transform": "constant",
            "when": {"nope": True, "opacity": "x", "normal_map": 1},
            "value": "mask",
        }
    )
    msgs = _messages(table)
    assert "use_cutout_alpha: when names 'nope', not a parameter of hogshade-legacy-v2" in msgs
    assert "use_cutout_alpha: when 'x' is not a float value of 'opacity'" in msgs
    assert "use_cutout_alpha: when cannot test the texture parameter 'normal_map'" in msgs


def test_a_malformed_factor_does_not_fire_a_bool_condition():
    res = resolve(_v2({}))
    res.values["use_cutout_alpha"]["factor"] = 1  # not a bool; validate(resolved) reports it and convert refuses
    with pytest.raises(MaterialError, match="cannot convert an invalid material"):
        convert(res, "hogshade-standard")


def test_convert_refuses_an_invalid_resolved_material():
    res = resolve(_v2({}))
    res.values["emission_intensity"]["factor"] = "high"
    with pytest.raises(MaterialError, match="emission_intensity"):
        convert(res, "hogshade-standard")


def test_apply_on_a_non_numeric_factor_is_a_material_error():
    with pytest.raises(MaterialError, match="not numeric"):
        _apply("invert", {"from": "x"}, "high")


def test_identity_keeps_the_type():
    table = _v2_table()
    for entry in table["map"]:
        if entry["from"] == "roughness":
            entry["to"] = "base_color"
    assert "roughness: float 'roughness' cannot map to color3 'base_color' by 'identity'" in _messages(table)


def test_v1_normal_strength_survives_conversion():
    doc = from_data(
        {
            "material_type": "hogshade-legacy-v1",
            "material_type_version": 1,
            "values": {"normal_map": {"texture": "n.png", "strength": 3.0}},
        }
    )
    out, _ = convert(doc, "hogshade-standard")
    assert out.values["geometry_normal"] == {"texture": "n.png", "strength": 3.0}


def test_v2_normal_strength_is_bump_intensity_only():
    assert type_of("hogshade-legacy-v2").parameters["normal_map"].strength is False
    doc = _v2({"normal_map": {"texture": "n.png"}, "bump_intensity": {"factor": 2.0}})
    out, _ = convert(doc, "hogshade-standard")
    assert out.values["geometry_normal"] == {"texture": "n.png", "strength": 2.0}


def test_non_object_table_entries_are_findings_not_errors():
    table = _v2_table()
    table["map"].append("roughness")
    table["dropped"].append(3)
    msgs = _messages(table)
    assert any("a map entry is an object" in m for m in msgs) and any("a dropped entry is an object" in m for m in msgs)


def test_load_table_is_a_registry_lookup():
    with pytest.raises(MaterialError, match="no conversion table"):
        load_table("../../x", "y")


# -------------------------------------------------------------------- the condition-set rules (third review)


def _cutout(when, value):
    return {"from": "use_cutout_alpha", "to": "alpha_mode", "transform": "constant", "when": when, "value": value}


def test_overlapping_conditions_are_a_finding():
    table = _v2_table()
    table["map"].append(_cutout({"use_cutout_alpha": True, "has_alpha": True}, "blend"))
    msgs = _messages(table)
    assert any(m.startswith("use_cutout_alpha: 2 entries match") and "table order would decide" in m for m in msgs)


def test_a_condition_set_that_covers_no_case_is_a_finding():
    table = _v2_table()
    table["map"] = [e for e in table["map"] if e.get("value") != "opaque"]
    msgs = _messages(table)
    assert any(m.startswith("use_cutout_alpha: no entry matches") and "'has_alpha': False" in m for m in msgs)


def test_a_when_object_names_its_own_source():
    table = _v2_table()
    table["map"] = [e for e in table["map"] if e["from"] != "use_cutout_alpha"]
    table["map"].append(_cutout({"has_alpha": True}, "blend"))
    assert "use_cutout_alpha: a when object names its own source 'use_cutout_alpha' among its conditions" in _messages(
        table
    )


@pytest.mark.parametrize("when", [{}, [True]])
def test_when_is_a_value_or_a_non_empty_object(when):
    table = _v2_table()
    table["map"].append(_cutout(when, "blend"))
    assert any("when is a value of the source, or a non-empty object" in m for m in _messages(table))


def test_a_consulted_parameter_is_not_a_loss():
    table = _v2_table()
    table["dropped"].append({"from": "has_alpha", "reason": "x"})
    assert "has_alpha: consulted by a when condition; a parameter that shapes the output is not a loss" in _messages(
        table
    )


def test_a_constant_into_the_strength_field_is_a_float():
    table = _v2_table()
    table["map"] = [e for e in table["map"] if e["from"] != "bump_intensity"]
    table["map"].append(
        {"from": "bump_intensity", "to": "geometry_normal", "transform": "constant", "field": "strength", "value": "x"}
    )
    assert "bump_intensity: constant 'x' is not a float for 'geometry_normal'" in _messages(table)
    table["map"][-1]["value"] = 2.0
    assert _messages(table) == []


def test_two_sources_onto_one_target_factor_are_refused(monkeypatch):
    table = _v2_table()
    table["map"].append({"from": "specular_tint", "to": "specular_roughness", "transform": "identity"})
    table["dropped"] = [d for d in table["dropped"] if d["from"] != "specular_tint"]
    assert _messages(table) == [], "the coverage rule alone cannot see a collision"
    monkeypatch.setattr("hogshade.material.conversion.load_table", lambda a, b: table)
    with pytest.raises(MaterialError, match="written twice"):
        convert(_v2({}), "hogshade-standard")


def test_unhashable_names_in_a_table_are_findings_not_errors():
    table = _v2_table()
    table["map"].append({"from": [], "to": "alpha_mode", "transform": "identity"})
    table["map"].append({"from": "roughness", "to": {"x": 1}, "transform": "identity"})
    table["dropped"].append({"from": ["specular_tint"], "reason": "x"})
    msgs = _messages(table)
    assert any("from and to are parameter names, got []" in m for m in msgs)
    assert any("got 'roughness' and {'x': 1}" in m for m in msgs)
    assert any("a dropped entry's from is a parameter name" in m for m in msgs)
