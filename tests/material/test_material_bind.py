"""
HogShade: the wgpu host map passes its rules and covers its types; bind() packs a resolved material into the
frame fields the map names, derives the model, lists textures and the unsupported parameters.
Package: tests/material/test_material_bind
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from hogshade.material import (
    Binding,
    MaterialError,
    Unbound,
    bind,
    check_host_map,
    entries_for,
    from_data,
    host_map,
    hosts,
    load,
    resolve,
    type_of,
    union_of,
)
from hogshade.material.binding import WGPU_MODEL_IDS, pack_fields

REPO = Path(__file__).resolve().parents[2]
CONTENT = REPO / "content" / "materials"
WGPU_TYPES = ("hogshade-legacy-v2", "hogshade-legacy-v1", "hogshade-lambert")


def _map():
    return copy.deepcopy(host_map("wgpu"))


def _findings(hmap):
    return [f"{f.parameter}: {f.message}" for f in check_host_map(hmap, union_of(WGPU_TYPES))]


def _doc(type_name, values=None):
    return resolve(from_data({"material_type": type_name, "material_type_version": 1, "values": values or {}}))


# ----------------------------------------------------------------------------------------------- the map


def test_two_hosts_ship():
    assert hosts() == ["maya_dx11", "wgpu"]


def test_shipped_wgpu_map_passes_and_covers_its_types():
    hmap = host_map("wgpu")
    assert hmap["types"] == list(WGPU_TYPES)
    assert _findings(hmap) == []
    for tname in WGPU_TYPES:
        assert set(entries_for(hmap, tname)) == set(type_of(tname).parameters), tname


def test_entries_for_resolves_the_type_suffix():
    hmap = host_map("wgpu")
    assert entries_for(hmap, "hogshade-legacy-v2")["specular_tint"] == {
        "field": "material",
        "components": [2],
        "types": ["hogshade-legacy-v2"],
    }
    assert entries_for(hmap, "hogshade-legacy-v1")["specular_tint"] == {"field": "params_a", "components": [1]}
    assert "subsurface" not in entries_for(hmap, "hogshade-legacy-v2")


def test_map_double_write_and_width():
    hmap = _map()
    hmap["parameters"]["ior"]["components"] = [0]  # metalness's slot
    hmap["parameters"]["sheen"]["components"] = [7]
    msgs = _findings(hmap)
    assert (
        "ior: material[0] is already written by 'metalness@hogshade-legacy-v2'" in msgs
    )  # the v2 entry wrote it first
    assert "sheen: component 7 is outside 'params_a' (width 4)" in msgs


def test_map_bound_and_unsupported_are_exclusive_and_reasons_required():
    hmap = _map()
    hmap["parameters"]["ior"]["unsupported"] = "no"
    hmap["parameters"]["bump_intensity"]["unsupported"] = ""
    msgs = _findings(hmap)
    assert "ior: a parameter is bound or unsupported, not both" in msgs
    assert "bump_intensity: unsupported carries a reason" in msgs


def test_map_unknown_field_missing_entry_and_texture_binding():
    hmap = _map()
    hmap["parameters"]["metalness"]["field"] = "params_c"
    del hmap["parameters"]["sheen"]
    hmap["parameters"]["normal_map"] = {"field": "material", "components": [0]}
    msgs = _findings(hmap)
    assert "metalness: field 'params_c' is not one of the map's fields" in msgs
    assert "sheen: no entry for hogshade-legacy-v1" in msgs
    assert "normal_map: a texture parameter is unsupported in the wgpu host, or bound to a slot" in msgs


def test_texture_entries_are_scoped_to_legacy_v2_and_validated():
    hmap = host_map("wgpu")
    v2 = entries_for(hmap, "hogshade-legacy-v2")
    assert v2["normal_map"] == {"texture": "normal"}
    assert v2["ambient_occlusion_map"] == {"texture": "orm", "channel": "r"}
    assert v2["roughness"]["texture"] == "orm" and v2["roughness"]["channel"] == "g" and v2["roughness"]["field"]
    assert v2["metalness"]["channel"] == "b" and v2["base_color"]["texture"] == "base_color"
    for tname in ("hogshade-legacy-v1", "hogshade-lambert"):
        for pname, e in entries_for(hmap, tname).items():
            assert "texture" not in e, (tname, pname, "host_inputs() samples for legacy v2 only")
    bad = _map()
    bad["parameters"]["normal_map@hogshade-legacy-v2"]["texture"] = "height"
    bad["parameters"]["roughness@hogshade-legacy-v2"]["channel"] = "x"
    bad["parameters"]["ior@hogshade-legacy-v2"] = {**bad["parameters"]["ior"], "texture": "orm"}
    bad["parameters"]["ior"]["types"] = ["hogshade-legacy-v1"]
    bad["parameters"]["metalness@hogshade-legacy-v2"]["channel"] = "b"
    del bad["parameters"]["metalness@hogshade-legacy-v2"]["texture"]
    msgs = _findings(bad)
    assert "normal_map@hogshade-legacy-v2: texture names slot 'height', not one of the map's slots" in " ".join(msgs)
    assert "roughness@hogshade-legacy-v2: channel is one of r, g, b, a, got 'x'" in msgs
    assert "ior@hogshade-legacy-v2: texture on a parameter the schema does not let a texture bind to" in msgs
    assert "metalness@hogshade-legacy-v2: channel goes with texture" in msgs
    # binding a textured v2 document still packs the factors and carries the paths
    values = {"roughness": {"factor": 1.0, "texture": "x/T_x_R.png"}, "normal_map": {"texture": "x/T_x_N.png"}}
    b = bind(_doc("hogshade-legacy-v2", values), "wgpu")
    assert b.textures == {"roughness": "x/T_x_R.png", "normal_map": "x/T_x_N.png"}
    assert b.fields["base_color"][3] == 1.0 and not any(u.parameter == "normal_map" for u in b.unsupported)


def test_map_refuses_what_the_schema_knows_and_a_bad_suffix():
    hmap = _map()
    hmap["parameters"]["ior"]["default"] = 1.5
    hmap["parameters"]["sheen@hogshade-legacy-v2"] = {"field": "params_a", "components": [3]}
    msgs = _findings(hmap)
    assert "ior: 'default' repeats what the schema knows; the map carries the frame layout only" in msgs
    assert "sheen@hogshade-legacy-v2: the suffix names a type that does not carry 'sheen'" in msgs


# ---------------------------------------------------------------------------------------------- bind()


def test_v2_default_document_binds_to_the_schema_defaults():
    doc = load(CONTENT / "legacy-v2" / "default.material.json")
    b = bind(resolve(doc), "wgpu")
    assert isinstance(b, Binding) and b.host == "wgpu" and b.model == "legacy-v2"
    assert b.fields["base_color"] == (0.6, 0.6, 0.6, 0.5)
    assert b.fields["material"] == (0.0, 1.0, 0.0, 1.45)
    assert b.fields["model"] == (float(WGPU_MODEL_IDS["legacy-v2"]), 0.0, 0.0, 0.0)
    assert b.fields["params_a"] == (0.0, 0.0, 0.0, 0.0) and b.fields["params_b"] == (0.0, 0.0, 0.0, 0.0)
    assert b.textures == {}
    assert {u.parameter for u in b.unsupported} == {
        name for name, e in entries_for(host_map("wgpu"), "hogshade-legacy-v2").items() if "unsupported" in e
    }
    assert b == bind(_doc("hogshade-legacy-v2"), "wgpu"), "the document spells out the type's defaults"


def test_v1_document_binds_the_lobes_and_the_tint_into_params():
    values = {
        "specular_tint": {"factor": 0.25},
        "subsurface": {"factor": 0.1},
        "anisotropic": {"factor": 0.2},
        "sheen": {"factor": 0.3},
        "sheen_tint": {"factor": 0.4},
        "clearcoat": {"factor": 0.5},
        "clearcoat_gloss": {"factor": 0.6},
        "rough_is_gloss": {"factor": True},
    }
    b = bind(_doc("hogshade-legacy-v1", values), "wgpu")
    assert b.model == "legacy-v1"
    assert b.fields["params_a"] == (0.1, 0.25, 0.2, 0.3)
    assert b.fields["params_b"] == (0.4, 0.5, 0.6, 0.0)
    assert b.fields["material"][2] == 0.0, "v1's tint lives in params_a[1], not material[2]"
    assert b.fields["model"] == (1.0, 1.0, 0.0, 0.0)


def test_lambert_binds_base_color_only():
    b = bind(_doc("hogshade-lambert", {"base_color": {"factor": [0.1, 0.2, 0.3]}}), "wgpu")
    assert b.model == "lambert" and b.fields["base_color"] == (0.1, 0.2, 0.3, 0.0)
    assert b.fields["material"] == (0.0, 0.0, 0.0, 0.0) and b.fields["model"] == (0.0, 0.0, 0.0, 0.0)
    assert {u.parameter for u in b.unsupported} == {"ambient_occlusion_map", "emission_color"}


def test_textures_are_listed_and_unsupported():
    values = {"height_map": {"texture": "h.png"}, "base_color": {"factor": [1, 1, 1], "texture": "b.png"}}
    b = bind(_doc("hogshade-legacy-v2", values), "wgpu")
    assert b.textures == {"height_map": "h.png", "base_color": "b.png"}
    assert (
        Unbound("height_map", entries_for(host_map("wgpu"), "hogshade-legacy-v2")["height_map"]["unsupported"])
        in b.unsupported
    )
    assert b.fields["base_color"][:3] == (1.0, 1.0, 1.0), "the factor still binds; the texture is carried"


def test_bind_refusals():
    with pytest.raises(MaterialError, match="C3"):
        bind(_doc("hogshade-standard"), "wgpu")
    with pytest.raises(MaterialError, match="takes a Resolved"):
        bind(from_data({"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": {}}), "wgpu")
    with pytest.raises(MaterialError, match="no binder for host"):
        bind(_doc("hogshade-legacy-v2"), "blender")
    res = _doc("hogshade-legacy-v2")
    res.values["roughness"]["factor"] = "high"
    with pytest.raises(MaterialError, match="cannot bind an invalid material"):
        bind(res, "wgpu")


def test_pack_fields_is_the_one_path_and_ignores_none():
    hmap = host_map("wgpu")
    packed = pack_fields(hmap, "hogshade-legacy-v2", {"roughness": 0.3, "ior": None, "metalness": True})
    assert packed["base_color"] == [0.0, 0.0, 0.0, 0.3] and packed["material"] == [1.0, 0.0, 0.0, 0.0]


def test_the_two_default_documents_validate_and_resolve():
    for name in ("legacy-v2", "legacy-v1"):
        doc = load(CONTENT / name / "default.material.json")
        assert doc.material_type == f"hogshade-{name}"
        res = resolve(doc)
        assert all(
            v.get("factor") is not None or type_of(doc.material_type).parameters[k].type == "texture"
            for k, v in res.values.items()
        )


# ------------------------------------------------------------------------------ the pre-PR review's rules


def test_the_metal_document_binds_differently_from_the_default():
    default = bind(resolve(load(CONTENT / "legacy-v2" / "default.material.json")), "wgpu")
    metal = bind(resolve(load(CONTENT / "legacy-v2" / "metal.material.json")), "wgpu")
    assert metal != default and metal.fields["material"][0] == 1.0 and metal.fields["base_color"][3] == 0.2


def test_map_types_rules():
    hmap = _map()
    hmap["types"] = ["hogshade-legacy-v2", "hogshade-legacy-v2"]
    assert _findings(hmap) == [": types lists a type twice: ['hogshade-legacy-v2', 'hogshade-legacy-v2']"]
    hmap = _map()
    hmap["parameters"]["ior"]["types"] = ["hogshade-standard"]
    msgs = _findings(hmap)
    assert "ior: types names 'hogshade-standard', which this host does not carry" in msgs
    hmap = _map()
    hmap["parameters"]["metalness@hogshade-legacy-v1"] = {"field": "params_b", "components": [3]}
    msgs = _findings(hmap)
    assert "metalness: two entries select it for hogshade-legacy-v1: the plain one and the suffixed one" in msgs


def test_pack_fields_refuses_a_value_of_the_wrong_width():
    hmap = _map()
    hmap["parameters"]["base_color@hogshade-legacy-v2"]["components"] = [0, 1, 2, 3]  # the checker would refuse
    with pytest.raises(MaterialError, match=r"3 value\(s\) for 4 component"):
        pack_fields(hmap, "hogshade-legacy-v2", {"base_color": [1, 1, 1]})


def test_host_map_hands_out_copies():
    a, b = host_map("wgpu"), host_map("wgpu")
    a["parameters"].clear()
    assert b["parameters"] and host_map("wgpu")["parameters"]


def test_the_host_scene_takes_a_binding_directly():
    wgpu_host = pytest.importorskip("hogshade.wgpu_host")
    metal = bind(resolve(load(CONTENT / "legacy-v2" / "metal.material.json")), "wgpu")
    scene = wgpu_host.Scene(width=32, height=32, material=metal)
    assert scene.model == "legacy-v2"
    assert scene.frame_bytes(9) != wgpu_host.Scene(width=32, height=32).frame_bytes(9)
    with pytest.raises(ValueError, match="not one of"):
        wgpu_host.MaterialBinding(model="standard").fields()
    assert wgpu_host.MODELS is wgpu_host.WGPU_MODEL_IDS


def test_map_may_not_target_the_binder_slot_and_survives_a_malformed_types():
    hmap = _map()
    hmap["parameters"]["ior"] = {"field": "model", "components": [0]}
    assert "ior: model[0] is already written by 'the binder (the model id)'" in _findings(hmap)
    hmap = _map()
    hmap["parameters"]["ior"]["types"] = None
    msgs = _findings(hmap)  # no TypeError: a malformed types selects no type, and is reported
    assert "ior: types is a non-empty list of type names" in msgs
    assert "ior: no entry for hogshade-legacy-v2" in msgs


def test_bind_leaves_a_record(caplog):
    import logging

    with caplog.at_level(logging.DEBUG, logger="hogshade.material.binding"):
        bind(resolve(load(CONTENT / "legacy-v2" / "default.material.json")), "wgpu")
    messages = [r.getMessage() for r in caplog.records if r.name == "hogshade.material.binding"]
    assert any(
        "bound" in m and "hogshade-legacy-v2" in m and "legacy-v2" in m and "21 parameter(s)" in m for m in messages
    )
    assert sum("height_map" in m for m in messages) == 1, "each unsupported parameter is one DEBUG line"
    assert sum("normal_map" in m for m in messages) == 0, "T3b: the normal map is a slot, not an unsupported parameter"
