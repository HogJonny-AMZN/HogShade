"""
HogShade: the Maya host map's packed maps (T3): the shipped ``orm`` entry validates and generates ``ormMap`` with
its flag, a malformed packed entry is a finding, the binder exposes the packed slots and writes the flag off, and
the shell samples the packed map first.
Package: tests/material/test_material_packed
"""

from __future__ import annotations

import copy
from pathlib import Path

from hogshade.material import check_host_map, generate, host_map, union_of
from hogshade.material.binding import maya_attributes, maya_packed_slots
from hogshade.material.generators import MAYA_TYPES, packed_maps

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / "hosts" / "maya_dx11" / "hogshade.fx"


def _findings(hmap) -> list[str]:
    return [f"{f.parameter}: {f.message}" for f in check_host_map(hmap, union_of(MAYA_TYPES))]


def test_the_shipped_orm_entry_validates_and_generates():
    hmap = host_map("maya_dx11")
    assert _findings(hmap) == []
    orm = packed_maps(hmap)["orm"]
    assert orm["channels"] == {"ambient_occlusion_map": "r", "roughness": "g", "metalness": "b"}
    block = generate("maya_dx11")
    assert "Texture2D ormMap" in block and "bool useOrmMap" in block
    assert block.index("Texture2D ormMap") > block.index("Texture2D emissiveMap"), "after the separate maps"
    assert 'string ColorSpace = "Raw"' in block.split("Texture2D ormMap")[1].split(">;")[0]


def test_a_malformed_packed_entry_is_a_finding():
    hmap = copy.deepcopy(host_map("maya_dx11"))
    hmap["packed"]["orm"]["channels"]["opacity"] = "a"  # opacity has no map entry
    hmap["packed"]["orm"]["channels"]["roughness"] = "x"
    del hmap["packed"]["orm"]["label"]
    hmap["packed"]["orm"]["order"] = 104  # roughnessMap's order
    found = _findings(hmap)
    assert any("'opacity', which has no map entry" in f for f in found)
    assert any("channel for 'roughness' is one of r, g, b, a" in f for f in found)
    assert any("missing 'label'" in f for f in found)
    assert any("order 104 is already used" in f for f in found)
    hmap["packed"] = []
    assert _findings(hmap) == ["packed: packed is an object keyed by the packed map's short name"]


def test_the_binder_exposes_the_packed_slot_and_writes_its_flag_off():
    slots = maya_packed_slots()
    assert slots == {
        "orm": {
            "name": "ormMap",
            "flag": "useOrmMap",
            "channels": {"ambient_occlusion_map": "r", "roughness": "g", "metalness": "b"},
        }
    }
    attrs = maya_attributes(host_map("maya_dx11"), "hogshade-legacy-v2", {}, {"roughness": "x.png"})
    assert attrs["useOrmMap"] == [0.0] and attrs["useRoughnessMap"] == [1.0], (
        "the job turns the packed flag on when the runtime set packs the three"
    )


def test_the_shell_samples_the_packed_map_first():
    text = SHELL.read_text(encoding="utf-8")
    assert "float4 orm = useOrmMap ? ormMap.Sample(SamplerAnisoWrap, uv)" in text
    assert "s.metalness = useOrmMap ? orm.b :" in text, "metalness from blue, the ORM packing"
    assert "s.roughness = useOrmMap ? orm.g :" in text and "s.ao = useOrmMap ? orm.r :" in text
