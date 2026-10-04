"""
HogShade: 2D DDS with mips, DX10 header: the uncompressed formats the cook writes (R8, RG8, RGBA8 and its sRGB form,
R16_UNORM, R16_FLOAT, R32_FLOAT) and the block-compressed ones (BC4, BC5, BC7 and BC7 sRGB) from encoder bytes.
Package: hogshade/texture_cook/dds2d

A sibling of ``hogshade.ibl.dds`` (the cube writer), sharing its header constants. The reader is strict and exists
to verify this writer's output and let tests decode by hand, not to load arbitrary DDS files.
"""

from __future__ import annotations

import logging as _logging
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from hogshade.ibl.dds import (
    D3D10_RESOURCE_DIMENSION_TEXTURE2D,
    DDPF_FOURCC,
    DDS_MAGIC,
    DDSCAPS_COMPLEX,
    DDSCAPS_MIPMAP,
    DDSCAPS_TEXTURE,
    DDSD_CAPS,
    DDSD_HEIGHT,
    DDSD_MIPMAPCOUNT,
    DDSD_PITCH,
    DDSD_PIXELFORMAT,
    DDSD_WIDTH,
)

_MODULE_NAME = "hogshade.texture_cook.dds2d"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

DDSD_LINEARSIZE = 0x80000


@dataclass(frozen=True)
class Format:
    """One DXGI format the writer and reader know: its code, channels, sample dtype or block size."""

    name: str
    dxgi: int
    channels: int
    dtype: str | None  # numpy dtype of an uncompressed sample; None for a block format
    block_bytes: int = 0  # bytes per 4x4 block for a block format


#: DXGI_FORMAT values (d3d11.h / dxgiformat.h).
FORMATS: dict[str, Format] = {
    f.name: f
    for f in (
        Format("R8_UNORM", 61, 1, "u1"),
        Format("R8G8_UNORM", 49, 2, "u1"),
        Format("R8G8B8A8_UNORM", 28, 4, "u1"),
        Format("R8G8B8A8_UNORM_SRGB", 29, 4, "u1"),
        Format("R16_UNORM", 56, 1, "<u2"),
        Format("R16_FLOAT", 54, 1, "<f2"),
        Format("R32_FLOAT", 41, 1, "<f4"),
        Format("BC4_UNORM", 80, 1, None, 8),
        Format("BC5_UNORM", 83, 2, None, 16),
        Format("BC7_UNORM", 98, 4, None, 16),
        Format("BC7_UNORM_SRGB", 99, 4, None, 16),
    )
}
_BY_DXGI = {f.dxgi: f for f in FORMATS.values()}


def _header(width: int, height: int, mips: int, pitch_or_size: int, linear: bool) -> bytes:
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | (DDSD_LINEARSIZE if linear else DDSD_PITCH)
    caps = DDSCAPS_TEXTURE
    if mips > 1:
        flags |= DDSD_MIPMAPCOUNT
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    header = struct.pack(
        "<4s7I11I8I4II",
        DDS_MAGIC,
        124,
        flags,
        height,
        width,
        pitch_or_size,
        0,
        mips,
        *([0] * 11),
        32,
        DDPF_FOURCC,
        int.from_bytes(b"DX10", "little"),
        0,
        0,
        0,
        0,
        0,
        caps,
        0,
        0,
        0,
        0,
    )
    return header  # 128 bytes: the struct format fixes it


def _dx10(dxgi: int) -> bytes:
    """The DX10 extension header: the DXGI format, a 2D texture, one array slice."""
    return struct.pack("<5I", dxgi, D3D10_RESOURCE_DIMENSION_TEXTURE2D, 0, 1, 0)


def write_2d(path: Path, mips: list[NDArray], format_name: str) -> None:
    """
    An uncompressed 2D texture with mips: ``mips[m]`` is ``(H_m, W_m)`` or ``(H_m, W_m, C)`` in the format's dtype
    and channel count (uint8 for the 8-bit formats, uint16, float16 or float32 for the 16 and 32-bit ones).
    """
    fmt = FORMATS[format_name]
    if fmt.dtype is None:
        raise ValueError(f"{format_name} is a block format; use write_2d_blocks")
    if not mips:
        raise ValueError("at least one level")
    chunks: list[bytes] = []
    for m, level in enumerate(mips):
        a = np.asarray(level)
        if a.ndim == 2:
            a = a[..., None]
        expect_h, expect_w = max(mips[0].shape[0] >> m, 1), max(mips[0].shape[1] >> m, 1)
        if a.shape[:2] != (expect_h, expect_w) or a.shape[2] != fmt.channels:
            raise ValueError(f"mip {m} is {a.shape}, expected ({expect_h}, {expect_w}, {fmt.channels})")
        chunks.append(np.ascontiguousarray(a.astype(fmt.dtype)).tobytes())
    h, w = mips[0].shape[:2]
    bpp = np.dtype(fmt.dtype).itemsize * fmt.channels
    Path(path).write_bytes(_header(w, h, len(mips), w * bpp, linear=False) + _dx10(fmt.dxgi) + b"".join(chunks))


def write_2d_blocks(path: Path, block_mips: list[bytes], width: int, height: int, format_name: str) -> None:
    """A block-compressed 2D texture with mips: ``block_mips[m]`` is the encoder's bytes for level ``m``."""
    fmt = FORMATS[format_name]
    if fmt.dtype is not None:
        raise ValueError(f"{format_name} is not a block format; use write_2d")
    if not block_mips:
        raise ValueError("at least one level")
    for m, blocks in enumerate(block_mips):
        w_m, h_m = max(width >> m, 1), max(height >> m, 1)
        expect = ((w_m + 3) // 4) * ((h_m + 3) // 4) * fmt.block_bytes
        if len(blocks) != expect:
            raise ValueError(f"mip {m} holds {len(blocks)} bytes, expected {expect} for {w_m}x{h_m} {format_name}")
    Path(path).write_bytes(
        _header(width, height, len(block_mips), len(block_mips[0]), linear=True)
        + _dx10(fmt.dxgi)
        + b"".join(block_mips)
    )


@dataclass(frozen=True)
class Dds2d:
    """A 2D DDS as read: the format, the size, and the levels (arrays uncompressed, bytes per level for blocks)."""

    format: Format
    width: int
    height: int
    levels: list[NDArray] | list[bytes]  # uncompressed: arrays (H_m, W_m, C); block: the bytes of each level


def read_2d(path: Path) -> Dds2d:
    """Read what ``write_2d`` or ``write_2d_blocks`` wrote; strict about the header."""
    data = Path(path).read_bytes()
    if data[:4] != DDS_MAGIC:
        raise ValueError("not a DDS file")
    size, _flags, height, width, _pitch, _depth, mips = struct.unpack_from("<7I", data, 4)
    _pf_size, pf_flags, fourcc = struct.unpack_from("<3I", data, 76)
    if size != 124 or pf_flags != DDPF_FOURCC or fourcc != int.from_bytes(b"DX10", "little"):
        raise ValueError("not a DX10 DDS")
    dxgi, dim, _misc, _array, _misc2 = struct.unpack_from("<5I", data, 128)
    if dim != D3D10_RESOURCE_DIMENSION_TEXTURE2D or dxgi not in _BY_DXGI:
        raise ValueError(f"not a 2D texture in a format this reader knows (dxgi {dxgi})")
    fmt = _BY_DXGI[dxgi]
    mips = max(mips, 1)
    offset = 148
    levels: list = []
    for m in range(mips):
        w_m, h_m = max(width >> m, 1), max(height >> m, 1)
        if fmt.dtype is None:
            n = ((w_m + 3) // 4) * ((h_m + 3) // 4) * fmt.block_bytes
            levels.append(data[offset : offset + n])
        else:
            n = w_m * h_m * fmt.channels * np.dtype(fmt.dtype).itemsize
            levels.append(
                np.frombuffer(data, dtype=fmt.dtype, count=w_m * h_m * fmt.channels, offset=offset).reshape(
                    h_m, w_m, fmt.channels
                )
            )
        offset += n
    if offset != len(data):
        raise ValueError(f"trailing bytes: {len(data) - offset}")
    return Dds2d(format=fmt, width=width, height=height, levels=levels)


def decode_bc4_block(block: bytes) -> NDArray[np.uint8]:
    """One BC4 block (8 bytes) to its 4x4 values: the reference decoder the tests hold the encoder to."""
    b = np.frombuffer(block, np.uint8)
    r0, r1 = int(b[0]), int(b[1])
    bits = int.from_bytes(bytes(b[2:8]), "little")
    if r0 > r1:
        pal = [r0, r1] + [((7 - i) * r0 + i * r1) // 7 for i in range(1, 7)]
    else:
        pal = [r0, r1] + [((5 - i) * r0 + i * r1) // 5 for i in range(1, 5)] + [0, 255]
    return np.array([pal[(bits >> (3 * i)) & 7] for i in range(16)], np.uint8).reshape(4, 4)
