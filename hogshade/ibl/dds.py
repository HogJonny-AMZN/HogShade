"""
HogShade: a minimal DDS writer and reader for RGBA16F cube maps with mips (DX10 header).
Package: hogshade/ibl/dds

Layout follows the DDS file format: 'DDS ' magic, a 124-byte header, a 20-byte DX10 header, then
pixel data face-major (all mips of +X, then all mips of -X, ...), each mip's rows top to bottom.
"""

from __future__ import annotations

import logging as _logging
import struct
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.ibl.dds"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

DDS_MAGIC = b"DDS "
DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH, DDSD_PITCH, DDSD_PIXELFORMAT, DDSD_MIPMAPCOUNT = 0x1, 0x2, 0x4, 0x8, 0x1000, 0x20000
DDPF_FOURCC = 0x4
DDSCAPS_COMPLEX, DDSCAPS_TEXTURE, DDSCAPS_MIPMAP = 0x8, 0x1000, 0x400000
DDSCAPS2_CUBEMAP = 0x200
DDSCAPS2_CUBEMAP_ALLFACES = 0x400 | 0x800 | 0x1000 | 0x2000 | 0x4000 | 0x8000
DXGI_FORMAT_R16G16B16A16_FLOAT = 10
D3D10_RESOURCE_DIMENSION_TEXTURE2D = 3
D3D10_RESOURCE_MISC_TEXTURECUBE = 0x4
BYTES_PER_PIXEL = 8


D3DFMT_A16B16G16R16F = 113  # legacy-header fourCC for RGBA16F, read by loaders that predate DX10 headers


def write_cube_rgba16f(path: Path, mips: list[NDArray], legacy_header: bool = False) -> None:
    """Write a cube map with mips. ``mips[m]`` has shape (6, n_m, n_m, 3 or 4), any float dtype.

    Alpha is set to 1 when only RGB is given. Values are cast to float16 on write. With
    ``legacy_header`` the pixel format is the pre-DX10 fourCC 113 (D3DFMT_A16B16G16R16F) and no
    DX10 block follows; the pixel data is identical. Some DCC image loaders read only that form.
    """
    if not mips or mips[0].shape[0] != 6:
        raise ValueError("expected a non-empty list of (6, n, n, C) arrays")
    base = mips[0].shape[1]
    for m, level in enumerate(mips):
        expect = max(base >> m, 1)
        if level.shape[:3] != (6, expect, expect):
            raise ValueError(f"mip {m} has shape {level.shape[:3]}, expected (6, {expect}, {expect})")

    header = struct.pack(
        "<4s7I11I8I4II",
        DDS_MAGIC,
        124,
        DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT,
        base,
        base,
        base * BYTES_PER_PIXEL,
        0,
        len(mips),
        *([0] * 11),
        32,
        DDPF_FOURCC,
        D3DFMT_A16B16G16R16F if legacy_header else int.from_bytes(b"DX10", "little"),
        0,
        0,
        0,
        0,
        0,
        DDSCAPS_COMPLEX | DDSCAPS_TEXTURE | DDSCAPS_MIPMAP,
        DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_ALLFACES,
        0,
        0,
        0,  # dwReserved2
    )
    dx10 = (
        b""
        if legacy_header
        else struct.pack(
            "<5I",
            DXGI_FORMAT_R16G16B16A16_FLOAT,
            D3D10_RESOURCE_DIMENSION_TEXTURE2D,
            D3D10_RESOURCE_MISC_TEXTURECUBE,
            1,
            0,
        )
    )
    assert len(header) == 128 and len(dx10) in (0, 20)

    chunks = [header, dx10]
    for face in range(6):
        for level in mips:
            rgb = np.asarray(level[face])
            if rgb.shape[-1] == 3:
                rgba = np.concatenate([rgb, np.ones(rgb.shape[:-1] + (1,), dtype=rgb.dtype)], axis=-1)
            else:
                rgba = rgb
            chunks.append(np.ascontiguousarray(rgba.astype(np.float16)).tobytes())
    Path(path).write_bytes(b"".join(chunks))


def write_2d_rgba16f(path: Path, rgb: NDArray) -> None:
    """Write a single 2D RGBA16F texture, no mips, shape (H, W, 3 or 4). Used for the BRDF LUT."""
    h, w = rgb.shape[:2]
    header = struct.pack(
        "<4s7I11I8I4II",
        DDS_MAGIC,
        124,
        DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT,
        h,
        w,
        w * BYTES_PER_PIXEL,
        0,
        1,
        *([0] * 11),
        32,
        DDPF_FOURCC,
        int.from_bytes(b"DX10", "little"),
        0,
        0,
        0,
        0,
        0,
        DDSCAPS_TEXTURE,
        0,
        0,
        0,
        0,  # dwReserved2
    )
    assert len(header) == 128
    dx10 = struct.pack("<5I", DXGI_FORMAT_R16G16B16A16_FLOAT, D3D10_RESOURCE_DIMENSION_TEXTURE2D, 0, 1, 0)
    if rgb.shape[-1] == 3:
        rgb = np.concatenate([rgb, np.ones(rgb.shape[:-1] + (1,), dtype=rgb.dtype)], axis=-1)
    Path(path).write_bytes(header + dx10 + np.ascontiguousarray(rgb.astype(np.float16)).tobytes())


def read_cube_rgba16f(path: Path) -> list[NDArray]:
    """Read a file written by ``write_cube_rgba16f``. Returns ``mips[m]`` of shape (6, n_m, n_m, 4) float32.

    Deliberately strict: it exists to verify our own output, not to load arbitrary DDS files.
    """
    data = Path(path).read_bytes()
    if data[:4] != DDS_MAGIC:
        raise ValueError("not a DDS file")
    size, _flags, height, width, _pitch, _depth, mip_count = struct.unpack_from("<7I", data, 4)
    _pf_size, pf_flags, fourcc = struct.unpack_from("<3I", data, 76)
    _caps, caps2 = struct.unpack_from("<2I", data, 108)
    if size != 124 or pf_flags != DDPF_FOURCC:
        raise ValueError("not a fourCC DDS")
    if fourcc == int.from_bytes(b"DX10", "little"):
        dxgi, _dim, misc, _array_size, _misc2 = struct.unpack_from("<5I", data, 128)
        if dxgi != DXGI_FORMAT_R16G16B16A16_FLOAT or not (misc & D3D10_RESOURCE_MISC_TEXTURECUBE):
            raise ValueError("not an RGBA16F cube")
        offset = 148
    elif fourcc == D3DFMT_A16B16G16R16F:
        offset = 128
    else:
        raise ValueError(f"unsupported fourCC {fourcc}")
    if not (caps2 & DDSCAPS2_CUBEMAP) or (caps2 & DDSCAPS2_CUBEMAP_ALLFACES) != DDSCAPS2_CUBEMAP_ALLFACES:
        raise ValueError("cube caps missing")
    if width != height:
        raise ValueError("cube faces must be square")

    faces: list[list[NDArray]] = [[] for _ in range(6)]
    for face in range(6):
        for m in range(mip_count):
            n = max(width >> m, 1)
            count = n * n * 4
            arr = np.frombuffer(data, dtype=np.float16, count=count, offset=offset).reshape(n, n, 4)
            faces[face].append(arr.astype(np.float32))
            offset += count * 2
    if offset != len(data):
        raise ValueError(f"trailing bytes: {len(data) - offset}")
    return [np.stack([faces[f][m] for f in range(6)], axis=0) for m in range(mip_count)]


if __name__ == "__main__":
    import tempfile

    mips = [np.full((6, 4 >> m, 4 >> m, 3), m + 1, dtype=np.float32) for m in range(3)]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.dds"
        write_cube_rgba16f(p, mips)
        back = read_cube_rgba16f(p)
        print("round trip:", [float(b[0, 0, 0, 0]) for b in back], "bytes:", p.stat().st_size)
