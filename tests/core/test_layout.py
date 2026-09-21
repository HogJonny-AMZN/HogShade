"""
HogShade: the LightSource field order in interface.wgsl is the ABI hogshade/core_layout.py records.
Package: tests/core/test_layout
"""

from __future__ import annotations

from pathlib import Path

from hogshade import core_layout as cl

ROOT = Path(__file__).resolve().parents[2]
WGSL = (ROOT / "core" / "interface.wgsl").read_text(encoding="utf-8")


def test_light_source_field_order_matches_the_mirror() -> None:
    fields = cl.parse_struct_fields(WGSL, "LightSource")
    assert [(f, t) for f, t, _ in cl.LIGHT_SOURCE_FIELDS] == fields


def test_light_source_offsets_are_consistent() -> None:
    sizes = {"f32": 4, "u32": 4, "vec2<f32>": 8, "vec3<f32>": 12}
    aligns = {"f32": 4, "u32": 4, "vec2<f32>": 8, "vec3<f32>": 16}
    offset = 0
    for name, typ, recorded in cl.LIGHT_SOURCE_FIELDS:
        a = aligns[typ]
        offset = (offset + a - 1) // a * a
        assert offset == recorded, (name, offset, recorded)
        offset += sizes[typ]
    assert (offset + 15) // 16 * 16 == cl.LIGHT_SOURCE_SIZE


def test_fixed_slots_wraps_sixteen_lights() -> None:
    fields = cl.parse_struct_fields(WGSL, "FixedSlots16")
    assert fields[0] == ("light", "array<LightSource, 16>")
    assert fields[1] == ("count", "u32")
