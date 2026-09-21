"""
HogShade: the buffer ABI of the core's host-facing structs, mirrored from core/interface.wgsl.
Package: hogshade/core_layout

A host that packs LightSource or FixedSlots16 into a uniform or storage buffer uses these offsets.
A test parses interface.wgsl and checks the field order matches; the offsets follow WGSL's
std430-style rules for the types involved (vec3 aligned to 16, scalars to 4, vec2 to 8).
"""

from __future__ import annotations

import re
from pathlib import Path

_MODULE_NAME = "hogshade.core_layout"
__version__ = "0.1.0"
__updated__ = "2026-09-21"

# (field, wgsl type, byte offset) in declaration order
LIGHT_SOURCE_FIELDS: list[tuple[str, str, int]] = [
    ("position_ws", "vec3<f32>", 0),
    ("kind", "u32", 12),
    ("direction_ws", "vec3<f32>", 16),
    ("intensity", "f32", 28),
    ("color", "vec3<f32>", 32),
    ("range", "f32", 44),
    ("cone_cos", "vec2<f32>", 48),
    ("shadow", "f32", 56),
    ("_pad", "f32", 60),
]
LIGHT_SOURCE_SIZE = 64
FIXED_SLOTS = 16
FIXED_SLOTS16_SIZE = FIXED_SLOTS * LIGHT_SOURCE_SIZE + 16  # count + three pads

_STRUCT = re.compile(r"struct\s+(\w+)\s*\{(.*?)\}", re.DOTALL)
_FIELD = re.compile(r"^\s*(\w+)\s*:\s*(.+?)\s*,\s*$", re.MULTILINE)  # comments are stripped first


def parse_struct_fields(wgsl: str, name: str) -> list[tuple[str, str]]:
    """(field, type) pairs of ``struct name`` in declaration order, comments ignored."""
    for m in _STRUCT.finditer(wgsl):
        if m.group(1) == name:
            body = re.sub(r"//[^\n]*", "", m.group(2))
            return [(f, t.strip()) for f, t in _FIELD.findall(body)]
    raise KeyError(name)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    fields = parse_struct_fields((root / "core" / "interface.wgsl").read_text(encoding="utf-8"), "LightSource")
    for (f, t), (mf, mt, off) in zip(fields, LIGHT_SOURCE_FIELDS, strict=True):
        print(f"{f:14s} {t:12s} offset {off:3d}   mirror {'ok' if (f, t) == (mf, mt) else 'MISMATCH'}")
