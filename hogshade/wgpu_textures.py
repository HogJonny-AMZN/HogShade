"""
HogShade: the cooked runtime set on a wgpu device: DDS to textures, the neutral slots, and the material plan a
document's bindings turn into (T3b).
Package: hogshade/wgpu_textures

The host's material bind group has four texture slots (base colour, normal, ORM, cavity), one sampler and a
small uniform: a bound bit per textured parameter and, for each scalar parameter, the slot and channel it reads.
``material_plan`` builds that from ``hogshade.material.runtime.runtime_textures`` (the paths and channels the
cook's manifest reports); ``upload_dds`` puts one DDS on the device with every mip; ``neutral_texture`` fills a
slot no document binds. The bits are per parameter, as the Maya shell's ``use<Map>`` flags are, so roughness
alone reads ``_ORM``'s green and leaves metalness and AO unbound. numpy and wgpu; imported by the host only.
"""

from __future__ import annotations

import logging as _logging
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from hogshade.material.runtime import RuntimeTexture
from hogshade.material.textures import PACKED
from hogshade.texture_cook import dds2d

_MODULE_NAME = "hogshade.wgpu_textures"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The cook's DXGI names to wgpu texture formats; the block formats need the ``texture-compression-bc`` feature.
WGPU_FORMATS: dict[str, str] = {
    "R8_UNORM": "r8unorm",
    "R8G8_UNORM": "rg8unorm",
    "R8G8B8A8_UNORM": "rgba8unorm",
    "R8G8B8A8_UNORM_SRGB": "rgba8unorm-srgb",
    "BC4_UNORM": "bc4-r-unorm",
    "BC5_UNORM": "bc5-rg-unorm",
    "BC7_UNORM": "bc7-rgba-unorm",
    "BC7_UNORM_SRGB": "bc7-rgba-unorm-srgb",
}
#: Formats the cook writes that are not slots in T3b (height is not sampled by this host).
NOT_SLOTS = ("R16_UNORM", "R16_FLOAT", "R32_FLOAT")
BC_FEATURE = "texture-compression-bc"
UNCOMPRESSED_HINT = "uv run tools/cook_textures.py cook <set_dir> --no-compress"

#: The material slots in bind-group order, and what fills one nobody binds (RGBA8 texels).
SLOTS = ("base_color", "normal", "orm", "cavity")
NEUTRAL: dict[str, tuple[int, int, int, int]] = {
    "base_color": (255, 255, 255, 255),
    "normal": (128, 128, 255, 255),
    "orm": (255, 255, 255, 255),
    "cavity": (255, 255, 255, 255),
}
#: Legacy v2 parameter to the bit the uniform carries.
BITS = {"base_color": 1, "normal_map": 2, "roughness": 4, "metalness": 8, "ambient_occlusion_map": 16, "cavity_map": 32}
#: Legacy v2 parameter to the slot its map lives in (standalone), and the scalars that carry a channel selector.
PARAMETER_SLOT = {
    "base_color": "base_color",
    "normal_map": "normal",
    "roughness": "orm",
    "metalness": "orm",
    "ambient_occlusion_map": "orm",
    "cavity_map": "cavity",
}
SCALARS = ("roughness", "metalness", "ambient_occlusion_map", "cavity_map")
CHANNEL_INDEX = {"r": 0, "g": 1, "b": 2, "a": 3}
#: ``host_Textures`` as WGSL lays it out: ``bound`` u32 at 0, then ``sel_a`` vec4<u32> at 16 (roughness slot and
#: channel, metalness slot and channel) and ``sel_b`` vec4<u32> at 32 (AO, cavity): 48 bytes.
UNIFORM_BYTES = 48


class TextureError(ValueError):
    """A runtime texture the host cannot take: a format outside the slots, a block format without the feature."""


@dataclass(frozen=True)
class SlotSource:
    """One slot's file (resolved once, here, so a key or a cache lookup touches no filesystem) and format."""

    path: Path
    format: str


@dataclass
class MaterialPlan:
    """What a document's bindings become on the device: a source per bound slot, the bits, the selectors."""

    sources: dict[str, SlotSource] = field(default_factory=dict)  # slot -> file
    bound: int = 0
    selectors: dict[str, tuple[int, int]] = field(default_factory=dict)  # scalar parameter -> (slot index, channel)

    @property
    def key(self) -> tuple:
        """What identifies a bind group: the slot files (resolved, so two spellings of one DDS are one), the bits
        and the selectors, which is everything two documents over one set can differ in."""
        return (
            tuple(sorted((slot, str(src.path)) for slot, src in self.sources.items())),
            self.bound,
            tuple(sorted(self.selectors.items())),
        )

    def uniform_bytes(self) -> bytes:
        """
        The ``host_Textures`` uniform: ``bound`` and its padding to 16, then roughness, metalness, AO, cavity as
        (slot, channel) pairs in two vec4<u32>.
        """
        values = [self.bound, 0, 0, 0]
        for name in SCALARS:
            slot, channel = self.selectors.get(name, (SLOTS.index(PARAMETER_SLOT[name]), 0))
            values += [slot, channel]
        raw = struct.pack("<12I", *values)
        assert len(raw) == UNIFORM_BYTES, len(raw)
        return raw


def material_plan(runtime: dict[str, RuntimeTexture]) -> MaterialPlan:
    """
    The plan for a legacy v2 document's runtime textures (``runtime_textures`` of its ``Binding.textures``): each
    bound parameter sets its bit, puts its file in its slot (a packed scalar names the slot its file is in: an
    ``_ORM`` channel, or a carrier's alpha, which the selector then reads) and the scalars record (slot, channel).
    A parameter the host has no slot for (height, emission, specular F0) is logged and left to the frame's factor.
    """
    plan = MaterialPlan()
    for parameter, rt in runtime.items():
        if parameter not in PARAMETER_SLOT:
            _LOGGER.info(f"{parameter}: bound to {rt.path.name}, which this host has no slot for; the factor stands")
            continue
        if rt.format in NOT_SLOTS or rt.format not in WGPU_FORMATS:
            raise TextureError(f"{parameter}: {rt.path.name} is {rt.format}, which this host has no slot for")
        slot = _slot_for(parameter, rt)
        existing = plan.sources.get(slot)
        if existing is not None and existing.path != rt.path.resolve():
            raise TextureError(f"{parameter}: {rt.path.name} and {existing.path.name} both want the {slot} slot")
        plan.sources[slot] = SlotSource(rt.path.resolve(), rt.format)
        plan.bound |= BITS[parameter]
        if parameter in SCALARS:
            if rt.channels not in CHANNEL_INDEX:
                raise TextureError(
                    f"{parameter}: {rt.path.name} holds {rt.channels!r}; a scalar parameter reads one channel"
                )
            plan.selectors[parameter] = (SLOTS.index(slot), CHANNEL_INDEX[rt.channels])
        _LOGGER.debug(f"  {parameter}: slot {slot}, channels {rt.channels}, {rt.format}")
    _LOGGER.info(
        f"material plan: {len(plan.sources)} slot(s) bound ({', '.join(sorted(plan.sources))}), bits {plan.bound:#x}"
    )
    return plan


def _slot_for(parameter: str, rt: RuntimeTexture) -> str:
    """The slot a runtime texture occupies: its parameter's, or the carrier's when the map rides in its alpha."""
    if rt.packed and rt.channels == "a":  # a single channel in a carrier's alpha: the carrier's slot
        from hogshade.texture_cook.cook import COLOUR_SUFFIXES, DATA_RGB_SUFFIXES  # the cook owns the carrier names

        stem = rt.path.stem
        if stem.endswith(tuple(s for s, p in PACKED.items() if p.channels)):  # the channel-packed carrier: _ORM
            return "orm"
        if stem.endswith(COLOUR_SUFFIXES + DATA_RGB_SUFFIXES):
            return "base_color"
    return PARAMETER_SLOT[parameter]


def upload_dds(device: Any, path: Path, usage: int | None = None) -> tuple[Any, str, int]:
    """
    One cooked DDS on the device with every mip: ``(texture, wgpu format, mip count)``. A block format without
    ``texture-compression-bc`` is ``TextureError`` naming the cook's uncompressed form.
    """
    import wgpu

    dds = dds2d.read_2d(Path(path))
    name = dds.format.name
    if name not in WGPU_FORMATS:
        raise TextureError(f"{Path(path).name}: {name} is not a format this host samples")
    if name.startswith("BC") and BC_FEATURE not in set(getattr(device, "features", ())):
        raise TextureError(
            f"{Path(path).name} is {name} and this device has no {BC_FEATURE}; cook the set uncompressed "
            f"({UNCOMPRESSED_HINT}) or run on a device with the feature"
        )
    fmt = WGPU_FORMATS[name]
    mips = len(dds.levels)
    texture = device.create_texture(
        size=(dds.width, dds.height, 1),
        mip_level_count=mips,
        sample_count=1,
        dimension="2d",
        format=fmt,
        usage=usage if usage is not None else (wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST),
    )
    for level, data in enumerate(dds.levels):
        w, h = max(dds.width >> level, 1), max(dds.height >> level, 1)
        if dds.format.dtype is None:  # block format: whole 4x4 blocks, the block row pitch
            blocks_w, blocks_h = (w + 3) // 4, (h + 3) // 4
            payload = bytes(data)
            layout = {"offset": 0, "bytes_per_row": blocks_w * dds.format.block_bytes, "rows_per_image": blocks_h}
            size = (blocks_w * 4, blocks_h * 4, 1)
        else:
            arr = np.ascontiguousarray(data)
            payload = arr.tobytes()
            layout = {"offset": 0, "bytes_per_row": w * dds.format.channels * arr.dtype.itemsize, "rows_per_image": h}
            size = (w, h, 1)
        device.queue.write_texture({"texture": texture, "mip_level": level, "origin": (0, 0, 0)}, payload, layout, size)
    _LOGGER.info(f"uploaded {Path(path).name}: {dds.width}x{dds.height} {fmt}, {mips} mip(s)")
    return texture, fmt, mips


def neutral_texture(device: Any, slot: str) -> Any:
    """A 1x1 RGBA8 texture with the slot's neutral value (white, a flat normal, white ORM, white cavity)."""
    import wgpu

    texture = device.create_texture(
        size=(1, 1, 1),
        mip_level_count=1,
        sample_count=1,
        dimension="2d",
        format="rgba8unorm",
        usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
    )
    device.queue.write_texture(
        {"texture": texture, "mip_level": 0, "origin": (0, 0, 0)},
        bytes(NEUTRAL[slot]),
        {"offset": 0, "bytes_per_row": 4, "rows_per_image": 1},
        (1, 1, 1),
    )
    return texture


def material_sampler(device: Any) -> Any:
    """The one sampler the material slots share: linear, mipmap linear, repeat, anisotropy 8."""
    return device.create_sampler(
        address_mode_u="repeat",
        address_mode_v="repeat",
        mag_filter="linear",
        min_filter="linear",
        mipmap_filter="linear",
        max_anisotropy=8,
    )


def bind_group_entries(
    device: Any, plan: MaterialPlan, cache: dict[str, Any], neutral: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    The bind-group entries for a plan: slots 0 to 3 as texture views (an upload per distinct path, cached by
    path in ``cache``; the neutral texture where the plan has no source), 4 the sampler (``neutral["sampler"]``),
    5 the uniform buffer the caller writes from ``plan.uniform_bytes()``.
    """
    entries = []
    for i, slot in enumerate(SLOTS):
        src = plan.sources.get(slot)
        if src is None:
            tex = neutral[slot]
        else:
            key = str(src.path)  # resolved at plan time: one upload per file, however a document spells it
            if key not in cache:
                cache[key] = upload_dds(device, src.path)[0]
            tex = cache[key]
        entries.append({"binding": i, "resource": tex.create_view()})
    entries.append({"binding": 4, "resource": neutral["sampler"]})
    return entries


if __name__ == "__main__":
    print(WGPU_FORMATS)
    print(MaterialPlan().uniform_bytes().hex())
