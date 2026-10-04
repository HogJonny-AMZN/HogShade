"""
HogShade: the material plan a document's runtime textures become on the wgpu host (T3b), without a device: the
format table covers the cook's output, a plan sets a bit per parameter and a slot-and-channel selector per scalar,
roughness alone leaves metalness and AO unbound, a packed cavity reads the carrier's alpha, two plans over one set
differ by their keys, the uniform bytes lay out as the WGSL expects, and a format the host has no slot for is refused.
Package: tests/host/test_wgpu_textures
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from hogshade.material.runtime import RuntimeTexture
from hogshade.texture_cook import dds2d
from hogshade.wgpu_textures import (
    BITS,
    NOT_SLOTS,
    SLOTS,
    UNIFORM_BYTES,
    WGPU_FORMATS,
    MaterialPlan,
    TextureError,
    material_plan,
)


def _rt(parameter: str, name: str, channels: str, fmt: str, packed: bool = False) -> RuntimeTexture:
    return RuntimeTexture(parameter, name.replace(".dds", ".png"), Path("set/cooked") / name, channels, fmt, packed)


def test_the_format_table_covers_what_the_cook_writes():
    cooked = {f.name for f in dds2d.FORMATS.values()}
    assert cooked == set(WGPU_FORMATS) | set(NOT_SLOTS)
    assert all(v.startswith("bc") for k, v in WGPU_FORMATS.items() if k.startswith("BC"))


def test_a_full_plan_sets_every_bit_and_selector():
    runtime = {
        "base_color": _rt("base_color", "T_x_BC.dds", "rgb", "BC7_UNORM_SRGB"),
        "normal_map": _rt("normal_map", "T_x_N.dds", "rg", "BC5_UNORM"),
        "roughness": _rt("roughness", "T_x_ORM.dds", "g", "BC7_UNORM", True),
        "metalness": _rt("metalness", "T_x_ORM.dds", "b", "BC7_UNORM", True),
        "ambient_occlusion_map": _rt("ambient_occlusion_map", "T_x_ORM.dds", "r", "BC7_UNORM", True),
        "cavity_map": _rt("cavity_map", "T_x_C.dds", "r", "BC4_UNORM"),
        "height_map": _rt("height_map", "T_x_H.dds", "r", "R16_UNORM"),  # no slot: logged, the factor stands
    }
    plan = material_plan(runtime)
    assert set(plan.sources) == set(SLOTS)
    assert plan.bound == sum(BITS.values())
    assert plan.selectors == {
        "roughness": (SLOTS.index("orm"), 1),
        "metalness": (SLOTS.index("orm"), 2),
        "ambient_occlusion_map": (SLOTS.index("orm"), 0),
        "cavity_map": (SLOTS.index("cavity"), 0),
    }
    values = struct.unpack("<12I", plan.uniform_bytes())
    assert values[0] == plan.bound and values[4:] == (2, 1, 2, 2, 2, 0, 3, 0), "sel_a at 16, sel_b at 32"
    assert len(plan.uniform_bytes()) == UNIFORM_BYTES


def test_roughness_alone_leaves_metalness_and_ao_unbound():
    plan = material_plan({"roughness": _rt("roughness", "T_x_ORM.dds", "g", "BC7_UNORM", True)})
    assert plan.bound == BITS["roughness"] and set(plan.sources) == {"orm"}
    assert plan.selectors == {"roughness": (SLOTS.index("orm"), 1)}


def test_a_packed_cavity_reads_the_carrier_alpha_and_two_documents_differ():
    plan = material_plan(
        {
            "roughness": _rt("roughness", "T_x_ORM.dds", "g", "BC7_UNORM", True),
            "cavity_map": _rt("cavity_map", "T_x_ORM.dds", "a", "BC7_UNORM", True),
        }
    )
    assert plan.selectors["cavity_map"] == (SLOTS.index("orm"), 3) and "cavity" not in plan.sources
    other = material_plan({"roughness": _rt("roughness", "T_x_ORM.dds", "g", "BC7_UNORM", True)})
    assert plan.key != other.key, "one set, two documents, two bind groups"
    blue = material_plan({"base_color": _rt("base_color", "T_x_BC_blue.dds", "rgb", "BC7_UNORM_SRGB")})
    red = material_plan({"base_color": _rt("base_color", "T_x_BC.dds", "rgb", "BC7_UNORM_SRGB")})
    assert blue.key != red.key


def test_a_format_without_a_slot_and_a_slot_conflict_are_refused():
    with pytest.raises(TextureError, match="R16_UNORM, which this host has no slot for"):
        material_plan({"roughness": _rt("roughness", "T_x_R.dds", "r", "R16_UNORM")})
    with pytest.raises(TextureError, match="both want the orm slot"):
        material_plan(
            {
                "roughness": _rt("roughness", "T_x_ORM.dds", "g", "BC7_UNORM", True),
                "metalness": _rt("metalness", "T_y_ORM.dds", "b", "BC7_UNORM", True),
            }
        )
    assert MaterialPlan().uniform_bytes()[:4] == b"\x00\x00\x00\x00"
