"""
HogShade: validate(): one test per rule, each asserting the finding's parameter; the good fixtures are clean.
Package: tests/material/test_material_validate
"""

from __future__ import annotations

import pytest

from hogshade.material import Document, Finding, load, resolve, validate
from hogshade.material.document import from_data


def _parameters(findings: list[Finding]) -> list[str]:
    return [f.parameter for f in findings]


@pytest.mark.parametrize("name", ["base/steel", "child", "grandchild", "legacy/brick_v2"])
def test_good_fixtures_have_no_findings(fixtures, name):
    doc = load(fixtures / f"{name}.material.json", root=fixtures)
    assert validate(doc) == []


@pytest.mark.parametrize(
    ("name", "parameter", "fragment"),
    [
        ("unknown_parameter", "shininess", "not a parameter"),
        ("wrong_type", "base_metalness", "is not float"),
        ("out_of_range", "specular_roughness", "outside range"),
        ("blend_without_texture", "base_color", "blend only with both"),
        ("bad_blend", "base_color", "is not one of"),
        ("strength_on_float", "specular_roughness", "strength only on a normal-map"),
        ("strength_without_texture", "geometry_normal", "strength only with a texture"),
        ("texture_on_untexturable", "specular_ior", "not texturable"),
        ("unknown_value_key", "base_metalness", "unknown value key 'amount'"),
        ("empty_value", "base_metalness", "factor, texture or both"),
        ("bad_enum", "alpha_mode", "is not one of"),
    ],
)
def test_broken_fixture_names_the_parameter(fixtures, name, parameter, fragment):
    doc = load(fixtures / "broken" / f"{name}.material.json")
    findings = validate(doc)
    assert set(_parameters(findings)) == {parameter}, findings
    assert any(fragment in f.message for f in findings), findings
    assert str(findings[0]).endswith(findings[0].message)


def test_soft_range_admits_a_value_above_it():
    doc = from_data(
        {
            "material_type": "hogshade-standard",
            "material_type_version": 1,
            "values": {"emission_luminance": {"factor": 50000.0}},
        }
    )
    assert validate(doc) == []


def test_int_parameter_refuses_a_float():
    doc = from_data(
        {"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": {"min_samples": {"factor": 2.5}}}
    )
    assert _parameters(validate(doc)) == ["min_samples"]


def test_colour_component_out_of_range_and_wrong_arity():
    values = {"base_color": {"factor": [1.0, 2.0, 0.0]}, "emission_color": {"factor": [1.0, 1.0]}}
    doc = from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": values})
    assert _parameters(validate(doc)) == ["base_color", "emission_color"]


def test_texture_parameter_takes_no_factor():
    doc = from_data(
        {
            "material_type": "hogshade-standard",
            "material_type_version": 1,
            "values": {"geometry_normal": {"factor": [0, 0, 1]}},
        }
    )
    assert _parameters(validate(doc)) == ["geometry_normal"]


def test_strength_must_be_at_or_above_zero():
    values = {"geometry_normal": {"texture": "n.png", "strength": -1.0}}
    doc = from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": values})
    assert [f.message for f in validate(doc)] == ["strength is a number at or above 0"]


def test_blend_only_on_colour_or_slider_widgets(fake_type):
    def vector_texture(data):
        data["parameters"]["normal_flip"] = {
            "type": "vector3", "default": [1.0, 1.0, 1.0], "range": [-1.0, 1.0], "group": "geometry",
            "widget": "vector",
            "semantic": "normal_flip", "colour_space": "raw", "overridable": True, "tier": 1, "hosts": {}, "doc": "x",
        }  # fmt: skip

    fake_type(vector_texture)
    values = {"normal_flip": {"factor": [1.0, 1.0, 1.0], "texture": "f.png", "blend": "multiply"}}
    doc = Document("hogshade-standard", 1, None, values)
    assert [f.message for f in validate(doc)] == ["blend only on a color or slider parameter"]


def test_child_may_not_set_a_non_overridable_parameter(fake_type):
    def lock_metalness(data):
        data["parameters"]["base_metalness"]["overridable"] = False

    fake_type(lock_metalness)
    values = {"base_metalness": {"factor": 1.0}}
    assert validate(Document("hogshade-standard", 1, None, values)) == []
    findings = validate(Document("hogshade-standard", 1, "base/x.material.json", values))
    assert _parameters(findings) == ["base_metalness"] and "not overridable" in findings[0].message


def test_ext_blocks_are_namespaces_not_validated_inside():
    doc = from_data(
        {
            "material_type": "hogshade-standard",
            "material_type_version": 1,
            "values": {},
            "ext": {"sj": {"anything": [1, 2]}, "bad": 3},
        }
    )
    findings = validate(doc)
    assert _parameters(findings) == ["ext"] and "ext.bad" in findings[0].message


def test_validate_refuses_other_objects():
    assert _parameters(validate("not a document")) == [""]


# ---------------------------------------------------------------------------------------------- resolved


def test_resolved_grandchild_is_complete(fixtures):
    res = resolve(load(fixtures / "grandchild.material.json", root=fixtures))
    assert validate(res) == []


def test_resolved_mask_with_a_constant_opacity_below_the_cut_is_a_finding():
    values = {"alpha_mode": {"factor": "mask"}, "geometry_opacity": {"factor": 0.2}}
    res = resolve(from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": values}))
    findings = validate(res)
    assert _parameters(findings) == ["alpha_mode"] and "nothing renders" in findings[0].message


def test_resolved_mask_with_an_opacity_texture_or_blend_is_fine():
    for values in (
        {"alpha_mode": {"factor": "mask"}, "geometry_opacity": {"factor": 0.2, "texture": "o.png"}},
        {"alpha_mode": {"factor": "blend"}, "geometry_opacity": {"factor": 0.2}},
        {"alpha_mode": {"factor": "mask"}},
    ):
        res = resolve(from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": values}))
        assert validate(res) == [], values


def test_resolved_reports_a_parameter_with_no_factor_and_no_default():
    res = resolve(Document("hogshade-standard", 1, None, {}))
    res.values["base_metalness"]["factor"] = None
    res.values["shininess"] = {"factor": 1.0}
    assert _parameters(validate(res)) == ["base_metalness", "shininess"]


# -------------------------------------------------------------------------------- the path rules on raw documents


@pytest.mark.parametrize("texture", ["../escape.png", "/abs.png", "C:/abs.png", "//server/share/x.png", ""])
def test_raw_document_texture_paths_are_checked_as_strings(texture):
    values = {"geometry_normal": {"texture": texture}}
    doc = from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": values})
    findings = validate(doc)
    assert _parameters(findings) == ["geometry_normal"], findings
    assert any(word in findings[0].message for word in ("absolute", "climbs", "non-empty"))


def test_raw_document_parent_path_is_checked_as_a_string():
    doc = Document("hogshade-standard", 1, "../other.material.json", {})
    findings = validate(doc)
    assert _parameters(findings) == [""] and "climbs" in findings[0].message


def test_in_memory_document_with_good_relative_paths_is_clean():
    values = {"geometry_normal": {"texture": "textures/n.png", "strength": 1.5}}
    doc = Document("hogshade-standard", 1, "base/steel.material.json", values)
    assert validate(doc) == []
