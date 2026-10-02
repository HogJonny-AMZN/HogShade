"""
HogShade: the shipped material-type files pass the meta-check; the standard's names are the spec's; each legacy
type is exactly the union of its model's structs and the Maya shell's material block.
Package: tests/material/test_material_schema
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from hogshade.material import MaterialError, check_type_data, type_of, types
from hogshade.material.schema import parse_type_data, read_type_data

REPO = Path(__file__).resolve().parents[2]

STANDARD_NAMES = {
    # OpenPBR's names, as the spec fixes them
    "base_color",
    "base_metalness",
    "specular_weight",
    "specular_color",
    "specular_roughness",
    "specular_ior",
    "specular_anisotropy",
    "specular_rotation",
    "emission_luminance",
    "emission_color",
    "geometry_opacity",
    "geometry_normal",
    # the one non-OpenPBR parameter (the alpha decision)
    "alpha_mode",
    # the surface opt-ins of version 1
    "ambient_occlusion",
    "cavity",
    "specular_occlusion",
    "height",
}


def test_four_types_ship():
    assert types() == ["hogshade-lambert", "hogshade-legacy-v1", "hogshade-legacy-v2", "hogshade-standard"]


@pytest.mark.parametrize("name", types())
def test_shipped_file_passes_meta_check(name):
    assert check_type_data(read_type_data(name), name) == []
    mtype = type_of(name)
    assert mtype.name == name and mtype.version == 1 and mtype.migrations == ()
    for p in mtype.parameters.values():
        assert p.group in mtype.groups


def test_standard_names_are_the_spec_list():
    assert set(type_of("hogshade-standard").parameters) == STANDARD_NAMES


def test_standard_alpha_mode_and_emission():
    std = type_of("hogshade-standard")
    assert std.parameters["alpha_mode"].choices == ("opaque", "mask", "blend")
    assert std.parameters["alpha_mode"].default == "mask"
    assert std.parameters["emission_luminance"].semantic == "emission_luminance_nits"
    assert std.parameters["geometry_normal"].strength is True
    assert std.parameters["specular_ior"].texturable is False


def test_legacy_v2_parallax_is_the_only_opt_in_group():
    assert type_of("hogshade-legacy-v2").optional_groups == ("parallax",)
    assert type_of("hogshade-standard").optional_groups == ()


def test_unknown_type_raises():
    with pytest.raises(MaterialError, match="unknown material type"):
        type_of("hogshade-phong")


# ------------------------------------------------------------------------------------------ the meta-check


def _standard():
    return copy.deepcopy(read_type_data("hogshade-standard"))


def _findings(data):
    return [(f.parameter, f.message) for f in check_type_data(data)]


def test_meta_check_missing_field():
    data = _standard()
    del data["parameters"]["base_color"]["doc"]
    assert ("base_color", "missing field 'doc'") in _findings(data)


def test_meta_check_unknown_field():
    data = _standard()
    data["parameters"]["base_color"]["ui_hint"] = "x"
    assert ("base_color", "unknown field 'ui_hint'") in _findings(data)


def test_meta_check_group_not_declared():
    data = _standard()
    data["parameters"]["base_color"]["group"] = "coat"
    assert any(p == "base_color" and "not declared" in m for p, m in _findings(data))


def test_meta_check_default_outside_range_and_type():
    data = _standard()
    data["parameters"]["specular_roughness"]["default"] = 4.0
    assert ("specular_roughness", "default outside range") in _findings(data)
    data["parameters"]["specular_roughness"]["default"] = "half"
    assert any(p == "specular_roughness" and "does not match type" in m for p, m in _findings(data))


def test_meta_check_texture_has_no_default_and_needs_colour_space():
    data = _standard()
    data["parameters"]["geometry_normal"]["default"] = [0, 0, 1]
    del data["parameters"]["geometry_normal"]["colour_space"]
    found = _findings(data)
    assert ("geometry_normal", "a texture parameter has no default factor") in found
    assert ("geometry_normal", "a texture parameter carries colour_space") in found


def test_meta_check_strength_only_on_normal_maps():
    data = _standard()
    data["parameters"]["height"]["strength"] = True
    assert ("height", "strength is only for a normal-map texture") in _findings(data)


def test_meta_check_enabled_flag_rule():
    data = _standard()
    data["parameters"]["coat_enabled"] = dict(data["parameters"]["alpha_mode"], type="bool", default=False, choices=[])
    del data["parameters"]["coat_enabled"]["choices"]
    assert any(p == "coat_enabled" and "not one" in m for p, m in _findings(data))
    data["groups"].append("coat")
    data["parameters"]["coat_enabled"]["group"] = "geometry"
    assert any(p == "coat_enabled" and "is a bool in that group" in m for p, m in _findings(data))
    data["parameters"]["coat_enabled"]["group"] = "coat"
    assert _findings(data) == []
    assert parse_type_data(data).optional_groups == ("coat",)


def test_meta_check_migrations_shape():
    data = _standard()
    data["migrations"] = [{"from": 1, "to": 3, "ops": []}]
    assert any("migration 0" in m for _, m in _findings(data))
    data["migrations"] = [{"from": 1, "to": 2, "ops": [{"op": "rename", "from": "a", "to": "b"}]}]
    assert _findings(data) == []


def test_parse_refuses_a_faulty_file():
    data = _standard()
    del data["title"]
    with pytest.raises(MaterialError, match="missing top-level field 'title'"):
        parse_type_data(data)


# --------------------------------------------------------------------- the legacy types against the code

# Struct fields named differently from the schema, and why.
STRUCT_TO_SCHEMA = {
    "use_vertex_alpha": "has_vertex_alpha",  # the shell's hasVertexAlpha
    "use_vertex_color_ao": "use_vertex_ao",  # v1's name for the shell's useVertexC1_AO
    "specular_f0": "specular_f0_map",  # the sample of specularF0Map
    "specular_amount": "specular",  # the sample of specularMap, red
    "ao": "ambient_occlusion_map",
    "cavity": "cavity_map",
    "emissive": "emission_color",  # the sample of emissiveMap multiplies the colour
    "normal_ts": "normal_map",
}
# Struct fields the host derives from a bound texture; never a parameter (the spec's use<Map> rule).
DERIVED = {
    "specular_f0_from_map",
    "use_base_map",
    "use_specular_map",
    "use_roughness_map",
    "use_metalness_map",
    "use_normal_map",
}
# Shell parameters that are not material: the model selector, the display gamma, the shadow strength (declared with
# the material slider macro but part of the Shadows block).
SHELL_HOST_ONLY = {"shadingModel", "linearSpaceLighting", "gammaCorrectionValue", "shadowMultiplier"}
# Every material-block, normal, v1 and parallax parameter and every map of the shell, by schema name.
SHELL_TO_SCHEMA = {
    "materialBaseColor": "base_color",
    "materialRoughness": "roughness",
    "materialMetalness": "metalness",
    "materialSpecular": "specular",
    "materialSpecTint": "specular_tint",
    "materialIOR": "ior",
    "materialBumpIntensity": "bump_intensity",
    "materialEmissive": "emission_color",
    "materialEmissiveIntensity": "emission_intensity",
    "useVertexC0_RGBA": "use_vertex_color",
    "hasVertexAlpha": "has_vertex_alpha",
    "useVertexC1_AO": "use_vertex_ao",
    "hasAlpha": "has_alpha",
    "useCutoutAlpha": "use_cutout_alpha",
    "opacityMaskBias": "opacity_mask_bias",
    "opacity": "opacity",
    "flipBackfaceNormals": "flip_backface_normals",
    "NormalCoordsysX": "normal_flip",
    "NormalCoordsysY": "normal_flip",
    "NormalCoordsysZ": "normal_flip",
    "materialSubsurface": "subsurface",
    "materialAnisotropic": "anisotropic",
    "materialSheen": "sheen",
    "materialSheenTint": "sheen_tint",
    "materialClearcoat": "clearcoat",
    "materialClearcoatGloss": "clearcoat_gloss",
    "roughIsGloss": "rough_is_gloss",
    "useSpecularMask": "use_specular_mask",
    "useParallaxOcclusionMapping": "parallax_enabled",
    "materialPomHeightScale": "height_scale",
    "pomMinSamples": "min_samples",
    "pomMaxSamples": "max_samples",
    "parallaxOccShadowType": "self_shadow",
    "selfOccShadowStrength": "self_shadow_strength",
    "pomShadowMultiplier": "self_shadow_multiplier",
    "baseColorMap": "base_color",
    "baseNormalMap": "normal_map",
    "roughnessMap": "roughness",
    "metalnessMap": "metalness",
    "specularF0Map": "specular_f0_map",
    "specularMap": "specular",
    "heightMap": "height_map",
    "ambOccMap": "ambient_occlusion_map",
    "cavityMap": "cavity_map",
    "emissiveMap": "emission_color",
}
# Shell parameters the v1 model does not read (the v1 structs have no field for them).
V1_DOES_NOT_READ = {
    "materialIOR",
    "materialBumpIntensity",
    "materialEmissive",
    "materialEmissiveIntensity",
    "opacityMaskBias",
    "useVertexC0_RGBA",
    "specularF0Map",
    "heightMap",
    "cavityMap",
    "emissiveMap",
    "useParallaxOcclusionMapping",
    "materialPomHeightScale",
    "pomMinSamples",
    "pomMaxSamples",
    "parallaxOccShadowType",
    "selfOccShadowStrength",
    "pomShadowMultiplier",
}
V1_GROUP = "Legacy v1 Disney"
# Every UI group of the shell: the material groups the schema covers, and the host groups it does not. A
# group the shell adds that is in neither set fails the test below, so a new material group cannot slip by.
MATERIAL_GROUPS = ("Material Maps", "Material Properties", "Normal Params", V1_GROUP, "Parallax Occlusion")
HOST_GROUPS = ("Environment Lighting", "Shadows", "DEBUG [Preview]")
# Every HOGSHADE_* macro the shell defines; a new one is unknown to the parser until it is classified here. The
# material UI macros retired with S2 (the block is generated as explicit declarations).
MATERIAL_MACROS = ()
HOST_MACROS = ("HOGSHADE_LIGHT_SLOT", "HOGSHADE_FILL_SLOT")  # the light slots and the G-buffer fill, never material


def _struct_fields(model: str, struct: str) -> set[str]:
    text = (REPO / "core" / "models" / f"{model}.wgsl").read_text(encoding="utf-8")
    m = re.search(rf"^struct {model}_{struct} \{{(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert m, f"{model}_{struct} not found"
    return set(re.findall(r"^\s+(\w+):", m.group(1), re.MULTILINE))


def _shell_parameters() -> dict[str, str]:
    """
    Shell parameter name to its UI group ("maps" for the Material Maps textures). A `bool` in Material Maps is
    a texture's use flag, derived from the binding, never a parameter (the S1 spec's use<Map> rule).
    """
    text = (REPO / "hosts" / "maya_dx11" / "hogshade.fx").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    pattern = (
        r"^(?P<type>Texture2D|float3|float|int|bool)\s+(?P<name>\w+)\s*(?::\s*\w+)?"
        r'\s*<[^>]*?UIGroup = "(?P<group>[^"]+)"'
    )
    for m in re.finditer(pattern, text, re.MULTILINE | re.DOTALL):
        kind, name, group = m.group("type"), m.group("name"), m.group("group")
        if group == "Material Maps":
            if kind == "Texture2D":
                out[name] = "maps"
        elif group in MATERIAL_GROUPS:
            out[name] = group
    return out


def test_shell_groups_and_macros_are_all_classified():
    text = (REPO / "hosts" / "maya_dx11" / "hogshade.fx").read_text(encoding="utf-8")
    groups = set(re.findall(r'UIGroup = "([^"]+)"', text))
    assert groups == set(MATERIAL_GROUPS) | set(HOST_GROUPS), f"unclassified shell groups: {sorted(groups)}"
    macros = set(re.findall(r"^#define (HOGSHADE_\w+)\(", text, re.MULTILINE))
    assert macros == set(MATERIAL_MACROS) | set(HOST_MACROS), f"unclassified shell macros: {sorted(macros)}"


def test_shell_parameters_are_all_named():
    shell = _shell_parameters()
    assert len(shell) > 40, "the shell parser found too little; the .fx layout changed"
    unnamed = set(shell) - SHELL_HOST_ONLY - set(SHELL_TO_SCHEMA)
    assert unnamed == set(), f"shell parameters with no schema name: {sorted(unnamed)}"


def test_meta_check_tier_semantic_and_soft_types():
    data = _standard()
    data["parameters"]["base_color"]["tier"] = True
    data["parameters"]["base_color"]["semantic"] = ""
    data["parameters"]["specular_roughness"]["soft"] = "yes"
    found = _findings(data)
    assert ("base_color", "tier is an integer or a named tier") in found
    assert ("base_color", "semantic is a name") in found
    assert ("specular_roughness", "soft is a bool") in found
    data["parameters"]["base_color"]["tier"] = "forward"
    data["parameters"]["base_color"]["semantic"] = "base_color_linear"
    data["parameters"]["specular_roughness"]["soft"] = True
    assert _findings(data) == []


def test_meta_check_migration_op_payloads():
    data = _standard()
    data["migrations"] = [
        {"from": 1, "to": 2, "ops": [{"op": "rename", "from": "a"}, {"op": "remove"}, {"op": "default", "name": "x"}]}
    ]
    msgs = [m for _, m in _findings(data)]
    assert "migration 0 op 0: 'rename' carries 'to'" in msgs
    assert "migration 0 op 1: 'remove' carries 'name'" in msgs
    assert "migration 0 op 2: 'default' carries 'value'" in msgs


def _shell_schema_names(v1: bool) -> set[str]:
    shell = _shell_parameters()
    names = set()
    for name, group in shell.items():
        if name in SHELL_HOST_ONLY:
            continue
        if v1 and name in V1_DOES_NOT_READ:
            continue
        if not v1 and group == V1_GROUP:
            continue
        names.add(SHELL_TO_SCHEMA[name])
    return names


def _struct_schema_names(model: str) -> set[str]:
    fields = (_struct_fields(model, "Material") | _struct_fields(model, "Samples")) - DERIVED
    return {STRUCT_TO_SCHEMA.get(f, f) for f in fields}


@pytest.mark.parametrize(
    ("type_name", "model", "v1"),
    [("hogshade-legacy-v2", "legacy_v2", False), ("hogshade-legacy-v1", "legacy_v1", True)],
)
def test_legacy_type_is_the_union_of_structs_and_shell(type_name, model, v1):
    expected = _struct_schema_names(model) | _shell_schema_names(v1)
    actual = set(type_of(type_name).parameters)
    assert actual == expected, (
        f"schema minus code: {sorted(actual - expected)}; code minus schema: {sorted(expected - actual)}"
    )


def test_legacy_textures_are_the_shell_maps():
    v2 = type_of("hogshade-legacy-v2")
    textured = {n for n, p in v2.parameters.items() if p.texturable}
    maps = {SHELL_TO_SCHEMA[n] for n, g in _shell_parameters().items() if g == "maps"}
    assert textured == maps


def test_meta_check_int_default_must_be_an_int():
    data = copy.deepcopy(read_type_data("hogshade-legacy-v2"))
    data["parameters"]["min_samples"]["default"] = 2.5
    assert any(p == "min_samples" and "does not match type 'int'" in m for p, m in _findings(data))


def test_meta_check_colour_range_shape_and_default_components():
    data = _standard()
    data["parameters"]["base_color"]["range"] = [0.0]
    assert ("base_color", "range is [min, max]") in _findings(data)
    data["parameters"]["base_color"]["range"] = [0.0, 1.0]
    data["parameters"]["base_color"]["default"] = [0.5, 2.0, 0.5]
    assert ("base_color", "a default component is outside range") in _findings(data)
