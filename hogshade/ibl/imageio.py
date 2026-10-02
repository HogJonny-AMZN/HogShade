"""
HogShade: EXR read and write through the OpenEXR package, and a dependency-free 8-bit PNG writer.
Package: hogshade/ibl/imageio
"""

from __future__ import annotations

import logging as _logging
import struct
import zlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.ibl.imageio"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)


def read_exr_rgb(path: Path) -> NDArray[np.float32]:
    """RGB channels of an EXR as float32 (H, W, 3), scene-linear as stored."""
    import OpenEXR

    with OpenEXR.File(str(path)) as f:
        channels = f.channels()
        if "RGB" in channels:
            rgb = channels["RGB"].pixels
        elif "RGBA" in channels:
            rgb = channels["RGBA"].pixels[..., :3]
        else:
            try:
                rgb = np.stack([channels[c].pixels for c in ("R", "G", "B")], axis=-1)
            except KeyError as e:
                raise ValueError(f"EXR {path} has no RGB channels: {list(channels)}") from e
    return np.asarray(rgb, dtype=np.float32)


def write_exr_rgb(path: Path, rgb: NDArray, half: bool = True) -> None:
    """Write (H, W, 3) as an RGB EXR, half-float by default, PIZ. Quantise first if you report statistics."""
    import OpenEXR

    data = np.ascontiguousarray(rgb.astype(np.float16 if half else np.float32))
    header = {"compression": OpenEXR.PIZ_COMPRESSION, "type": OpenEXR.scanlineimage}
    with OpenEXR.File(header, {"RGB": data}) as f:
        f.write(str(path))


def write_png_rgb8(path: Path, rgb8: NDArray[np.uint8]) -> None:
    """Write an (H, W, 3) uint8 array as a PNG. No dependencies beyond zlib."""
    h, w, c = rgb8.shape
    if c != 3 or rgb8.dtype != np.uint8:
        raise ValueError("expected (H, W, 3) uint8")
    raw = b"".join(b"\x00" + rgb8[y].tobytes() for y in range(h))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def preview_srgb8(rgb: NDArray, exposure_ev: float = 0.0) -> NDArray[np.uint8]:
    """A display preview only: exposure, Reinhard, sRGB encode, 8-bit. Never used for cooking."""
    x = np.maximum(rgb.astype(np.float64) * (2.0**exposure_ev), 0.0)
    x = x / (1.0 + x)
    srgb = np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.png"
        write_png_rgb8(p, preview_srgb8(np.random.default_rng(0).random((8, 16, 3)).astype(np.float32)))
        print("png bytes:", p.stat().st_size, "magic ok:", p.read_bytes()[:4] == b"\x89PNG")
