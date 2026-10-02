"""
HogShade: the generators: the host map passes its rules, the Maya block equals the committed shell's and
declares the schema's values, the docs reference equals the committed file.
Package: tests/material/test_material_generate
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

from hogshade.material import MaterialError, type_of, types
from hogshade.material.generators import (
    MAYA_BEGIN,
    MAYA_END,
    MAYA_TYPES,
    between,
    check_host_map,
    docs_reference,
    generate,
    host_map,
    hosts,
    maya_block,
    replace_between,
    union_of,
)

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / "hosts" / "maya_dx11" / "hogshade.fx"
REFERENCE = REPO / "Docs" / "reference" / "material-types.md"


def _map():
    return copy.deepcopy(host_map("maya_dx11"))


def _findings(hmap):
    return [f"{f.parameter}: {f.message}" for f in check_host_map(hmap, union_of(MAYA_TYPES))]


# ---------------------------------------------------------------------------------------------- the host map


def test_one_host_ships():
    assert hosts() == ["maya_dx11"]
    with pytest.raises(MaterialError, match="no host map"):
        host_map("blender")


def test_shipped_map_passes_and_covers_the_legacy_union():
    hmap = host_map("maya_dx11")
    union = union_of(MAYA_TYPES)
    assert _findings(hmap) == []
    assert set(hmap["parameters"]) == set(union)
    assert len(union) == 38


def test_shared_parameters_agree_on_the_emission_fields():
    v2, v1 = type_of("hogshade-legacy-v2").parameters, type_of("hogshade-legacy-v1").parameters
    shared = set(v2) & set(v1)
    assert "normal_map" in shared and v2["normal_map"].strength != v1["normal_map"].strength, (
        "doc and strength may differ"
    )
    union_of(MAYA_TYPES)  # raises if an emission field differs


def test_map_missing_and_unknown_parameters():
    hmap = _map()
    del hmap["parameters"]["roughness"]
    hmap["parameters"]["shininess"] = {"name": "x", "label": "x", "group": "Material Properties", "order": 999}
    msgs = _findings(hmap)
    assert "roughness: no host-map entry" in msgs
    assert "shininess: not a parameter of the types this host declares" in msgs


def test_map_duplicate_order_and_name():
    hmap = _map()
    hmap["parameters"]["metalness"]["order"] = 151  # roughness's
    hmap["parameters"]["ior"]["name"] = "materialRoughness"
    msgs = _findings(hmap)
    assert "metalness: order 151 is already used by 'roughness'" in msgs
    assert "ior: name 'materialRoughness' is already used by 'roughness'" in msgs


def test_map_flag_order_collides_with_a_map_order():
    hmap = _map()
    hmap["parameters"]["normal_map"]["map"]["order"] = 101  # baseColorMap's flag sits at 101
    assert any("map order 101 is already used by 'base_color'" in m for m in _findings(hmap))


def test_map_may_not_repeat_what_the_schema_knows():
    hmap = _map()
    hmap["parameters"]["roughness"]["default"] = 0.5
    hmap["parameters"]["roughness"]["range"] = [0, 1]
    msgs = _findings(hmap)
    assert "roughness: 'default' repeats what the schema knows; the map carries names only" in msgs
    assert "roughness: 'range' repeats what the schema knows; the map carries names only" in msgs


def test_map_texture_vector_and_semantic_rules():
    hmap = _map()
    hmap["parameters"]["normal_map"]["name"] = "x"
    hmap["parameters"]["normal_flip"]["name"] = "x"
    del hmap["parameters"]["normal_flip"]["components"][0]
    hmap["parameters"]["opacity"]["semantic"] = "COLOR0"
    hmap["parameters"]["specular_tint"]["map"] = {"name": "a", "flag": "b", "label": "c", "order": 500}
    hmap["parameters"]["sheen"]["group"] = "Coat"
    msgs = _findings(hmap)
    assert any(m.startswith("normal_map: a texture parameter carries only map") for m in msgs)
    assert "normal_flip: a vector3 carries three components" in msgs
    assert "normal_flip: a vector3 carries components, not 'name'" in msgs
    assert "opacity: semantic is one of ('OPACITY',)" in msgs
    assert "specular_tint: map on a parameter the schema does not let a texture bind to" in msgs
    assert "sheen: group 'Coat' is not one of the map's groups" in msgs


def test_maya_block_refuses_a_malformed_map():
    hmap = _map()
    del hmap["parameters"]["roughness"]
    with pytest.raises(MaterialError, match="malformed host map"):
        maya_block(hmap, union_of(MAYA_TYPES))


# ------------------------------------------------------------------------------------------- the Maya block

_DECL = re.compile(
    r"^(?P<type>float3|float|int|bool|Texture2D)\s+(?P<name>\w+)(?:\s*:\s*\w+)?"
    r"\s*<(?P<ann>[^>]*)>(?:\s*=\s*(?P<value>[^;]+))?;",
    re.MULTILINE | re.DOTALL,
)


def _declarations(text: str) -> dict[str, dict]:
    out = {}
    for m in _DECL.finditer(text):
        ann = m.group("ann")
        out[m.group("name")] = {
            "type": m.group("type"),
            "value": (m.group("value") or "").strip(),
            "min": re.search(r"UIMin = ([-\d.]+)", ann),
            "max": re.search(r"UIMax = ([-\d.]+)", ann),
            "group": (re.search(r'UIGroup = "([^"]+)"', ann) or re.search(r"(^)", "")).group(1),
            "fields": re.search(r'UIFieldNames = "([^"]+)"', ann),
        }
    return out


def test_generated_block_equals_the_committed_shell():
    shell = SHELL.read_text(encoding="utf-8")
    assert between(shell, MAYA_BEGIN, MAYA_END, "shell") == generate("maya_dx11")


def test_generated_block_declares_the_schema_values():
    block = generate("maya_dx11")
    decls = _declarations(block)
    hmap, union = host_map("maya_dx11"), union_of(MAYA_TYPES)
    for pname, p in union.items():
        e = hmap["parameters"][pname]
        if "map" in e:
            assert decls[e["map"]["name"]]["type"] == "Texture2D"
            assert decls[e["map"]["flag"]]["value"] == "false"
        if p.type == "texture":
            continue
        if p.type == "vector3":
            for c, default in zip(e["components"], p.default):
                d = decls[c["name"]]
                assert d["type"] == "int" and d["fields"].group(1) == e["component_choices"]
                assert int(d["value"]) == (0 if default > 0 else 1)
            continue
        d = decls[e["name"]]
        assert d["group"] == e["group"]
        if p.type == "color3":
            rgb = [float(v) for v in d["value"].strip("{} ").split(",")]
            assert rgb == [float(v) for v in p.default]
        elif p.type == "float":
            assert float(d["value"]) == p.default
            assert (float(d["min"].group(1)), float(d["max"].group(1))) == p.range
        elif p.type == "int":
            assert int(d["value"]) == p.default
            assert (float(d["min"].group(1)), float(d["max"].group(1))) == p.range
        elif p.type == "bool":
            assert d["value"] == ("true" if p.default else "false")
        elif p.type == "enum":
            assert d["fields"].group(1).split(":") == list(p.choices)
            assert list(p.choices)[int(d["value"])] == p.default


def test_every_identifier_the_shell_body_uses_is_declared():
    shell = SHELL.read_text(encoding="utf-8")
    block = between(shell, MAYA_BEGIN, MAYA_END, "shell")
    outside = shell.replace(block, "")
    declared = set(_declarations(block)) | set(_declarations(outside))
    hmap = host_map("maya_dx11")
    wanted = set()
    for e in hmap["parameters"].values():
        if "name" in e:
            wanted.add(e["name"])
        if "map" in e:
            wanted.update((e["map"]["name"], e["map"]["flag"]))
        for c in e.get("components", []):
            wanted.add(c["name"])
    missing = wanted - declared
    assert missing == set(), f"host-map identifiers not declared: {sorted(missing)}"
    body = re.sub(r"//[^\n]*", "", outside)  # the hand-written shell without comments; it declares none of these
    unused = {name for name in wanted if not re.search(rf"\b{name}\b", body)}
    assert unused == set(), f"declared but never read by the shell: {sorted(unused)}"


def test_shell_has_no_ui_macros_left():
    shell = SHELL.read_text(encoding="utf-8")
    assert re.search(r"^#define HOGSHADE_(SLIDER|BOOL|V1|MAP)\(", shell, re.MULTILINE) is None


def test_replace_between_and_missing_markers():
    text = f"a\n{MAYA_BEGIN}\nold\n{MAYA_END}\nz\n"
    assert replace_between(text, MAYA_BEGIN, MAYA_END, "new\n", "x") == f"a\n{MAYA_BEGIN}\nnew\n{MAYA_END}\nz\n"
    with pytest.raises(MaterialError, match="markers"):
        between("nothing", MAYA_BEGIN, MAYA_END, "x")


# ----------------------------------------------------------------------------------------------- the docs


def test_docs_reference_equals_the_committed_file_and_lists_every_parameter():
    text = generate("docs")
    assert REFERENCE.read_text(encoding="utf-8") == text
    for name in types():
        assert f"## `{name}`" in text
        for pname in type_of(name).parameters:
            assert f"| `{pname}` |" in text
    assert docs_reference(["hogshade-lambert"]).count("## `") == 1


def test_unknown_host_raises():
    with pytest.raises(MaterialError, match="no generator for host"):
        generate("blender")


def test_the_tool_check_is_clean():
    sys.path.insert(0, str(REPO / "tools"))
    import generate_material_ui as tool

    assert tool.check() == []


# ------------------------------------------------------------------------------- the pre-PR review's rules


def test_map_refuses_hlsl_words_and_broken_labels():
    hmap = _map()
    hmap["parameters"]["roughness"]["name"] = "float"
    hmap["parameters"]["metalness"]["label"] = 'Metal "ness" > 1'
    hmap["parameters"]["ior"]["label"] = "Index <of> Refraction"
    hmap["parameters"]["normal_flip"]["components"][0]["name"] = "sampler"
    msgs = _findings(hmap)
    assert "roughness: name is an identifier and not an HLSL word, got 'float'" in msgs
    assert "metalness: label is a string without quotes or angle brackets" in msgs
    assert "ior: label is a string without quotes or angle brackets" in msgs
    assert "normal_flip: component name is an identifier and not an HLSL word, got 'sampler'" in msgs


def test_maya_block_refuses_a_non_object_map():
    with pytest.raises(MaterialError, match="malformed host map"):
        maya_block([], union_of(MAYA_TYPES))


def test_markers_are_whole_lines_once_in_order_and_crlf_tolerant():
    crlf = f"a\r\n{MAYA_BEGIN}\r\nold\r\n{MAYA_END}\r\nz\r\n"
    assert between(crlf, MAYA_BEGIN, MAYA_END, "x") == "old\r\n"
    with pytest.raises(MaterialError, match="exactly once"):
        between(f"{MAYA_BEGIN}\nold\n{MAYA_END}X\n", MAYA_BEGIN, MAYA_END, "x")
    with pytest.raises(MaterialError, match="exactly once"):
        between(f"{MAYA_BEGIN}\n{MAYA_BEGIN}\nold\n{MAYA_END}\n", MAYA_BEGIN, MAYA_END, "x")
    with pytest.raises(MaterialError, match="precedes"):
        between(f"{MAYA_END}\nold\n{MAYA_BEGIN}\n", MAYA_BEGIN, MAYA_END, "x")


def test_write_is_idempotent(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "tools"))
    import generate_material_ui as tool

    shell = tmp_path / "hogshade.fx"
    shell.write_text(SHELL.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    reference = tmp_path / "material-types.md"
    monkeypatch.setattr(tool, "SHELL", shell)
    monkeypatch.setattr(tool, "REFERENCE", reference)
    tool.write()
    once = shell.read_bytes(), reference.read_bytes()
    tool.write()
    assert (shell.read_bytes(), reference.read_bytes()) == once
    assert tool.check() == []
    shell.write_text("no markers here\n", encoding="utf-8")
    assert tool.main(["--check"]) == 2
