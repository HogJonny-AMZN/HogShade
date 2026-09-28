"""
HogShade: resolve(): the grandchild resolves with every parameter and the expected winners; cycles and
cross-type parents raise.
Package: tests/material/test_material_resolve
"""

from __future__ import annotations

import pytest

from hogshade.material import Document, MaterialError, load, resolve, type_of
from hogshade.material.document import from_data


def test_grandchild_resolves_with_every_parameter_and_child_wins(fixtures):
    res = resolve(load(fixtures / "grandchild.material.json", root=fixtures))
    std = type_of("hogshade-standard")
    assert res.material_type == "hogshade-standard" and res.version == 1
    assert set(res.values) == set(std.parameters)
    assert res.values["specular_roughness"]["factor"] == 0.2, "the grandchild's own value"
    assert res.values["base_color"] == {
        "factor": [1.0, 1.0, 1.0],
        "texture": "textures/steel_basecolor.png",
        "blend": "multiply",
    }, "the child's"
    assert res.values["base_metalness"]["factor"] == 1.0, "the base's"
    assert res.values["specular_weight"] == {"factor": 1.0, "texture": None, "blend": None}, "the type's default"
    assert res.values["geometry_normal"] == {
        "factor": None,
        "texture": "textures/steel_normal.png",
        "blend": None,
        "strength": 0.8,
    }
    assert res.values["cavity"] == {"factor": None, "texture": None, "blend": None}, "an unbound texture"


def test_ext_merges_child_over_parent_per_namespace(fixtures):
    res = resolve(load(fixtures / "grandchild.material.json", root=fixtures))
    assert res.ext == {"spritejammer": {"tier_cap": 1, "tag": "base"}, "other": {"x": 1}}


def test_chain_is_child_first(fixtures):
    res = resolve(load(fixtures / "grandchild.material.json", root=fixtures))
    names = [p.name for p in res.chain]
    assert names == ["grandchild.material.json", "child.material.json", "steel.material.json"]


def test_a_document_without_parent_resolves_alone(fixtures):
    res = resolve(load(fixtures / "base" / "steel.material.json"))
    assert len(res.chain) == 1 and res.values["specular_roughness"]["factor"] == 0.4


def test_in_memory_document_resolves_to_defaults():
    res = resolve(from_data({"material_type": "hogshade-lambert", "material_type_version": 1, "values": {}}))
    assert res.chain == () and res.values["base_color"]["factor"] == [0.6, 0.6, 0.6]


def test_cycle_raises(fixtures):
    with pytest.raises(MaterialError, match="parent cycle"):
        resolve(load(fixtures / "broken" / "cycle_a.material.json"))


def test_parent_of_another_type_raises(fixtures):
    with pytest.raises(MaterialError, match="a chain resolves to one type"):
        resolve(load(fixtures / "broken" / "cross_type_parent.material.json"))


def test_parent_without_a_document_path_raises():
    doc = from_data(
        {"material_type": "hogshade-standard", "material_type_version": 1, "parent": "x.material.json", "values": {}}
    )
    with pytest.raises(MaterialError, match="needs a document path"):
        resolve(doc)


def test_default_strength_on_normal_maps_only():
    res = resolve(from_data({"material_type": "hogshade-legacy-v1", "material_type_version": 1, "values": {}}))
    assert res.values["normal_map"]["strength"] == 1.0
    assert "strength" not in res.values["ambient_occlusion_map"]


def test_resolved_values_do_not_alias_the_cached_type():
    res = resolve(from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": {}}))
    res.values["base_color"]["factor"][0] = 9.0
    assert type_of("hogshade-standard").parameters["base_color"].default == [0.8, 0.8, 0.8]
    again = resolve(from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": {}}))
    assert again.values["base_color"]["factor"] == [0.8, 0.8, 0.8]


def test_resolved_values_do_not_alias_the_documents(fixtures):
    doc = load(fixtures / "base" / "steel.material.json")
    res = resolve(doc)
    res.values["base_color"]["factor"][0] = 9.0
    res.ext["spritejammer"]["tier_cap"] = 99
    assert doc.values["base_color"]["factor"] == [0.18, 0.21, 0.24]
    assert doc.ext["spritejammer"]["tier_cap"] == 2


def test_malformed_known_value_survives_resolution_for_validate_to_report():
    from hogshade.material import validate

    doc = Document("hogshade-standard", 1, None, {"base_metalness": "high"})
    res = resolve(doc)
    assert res.values["base_metalness"]["factor"] == "high", "not silently replaced by the default"
    findings = validate(res)
    assert [f.parameter for f in findings] == ["base_metalness"] and "is not float" in findings[0].message
