"""
HogShade: a PNG reader and writer of this repository's: 8 and 16-bit grey, grey-alpha, RGB and RGBA, the five
scanline filters, non-interlaced. No Pillow (the T2 spec, question 1).
Package: hogshade/texture_cook/png

``read_png`` returns ``(H, W, C)`` ``uint8`` or ``uint16``; ``write_png`` takes the same and a filter type for the
whole image (the cook writes filter 0; the tests write every filter). Interlaced and palette PNGs are refused
with a message. Unfiltering is sequential by its definition (Sub, Average and Paeth read the pixel to the
left), so it runs as a numba kernel when numba is installed and as the same loops in Python when it is not;
the two agree byte for byte (a test says so).
"""

from __future__ import annotations

import logging as _logging
import struct
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.texture_cook.png"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SIGNATURE = b"\x89PNG\r\n\x1a\n"
#: PNG colour type to channel count; 3 (palette) is refused.
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}
COLOUR_TYPES = {1: 0, 2: 4, 3: 2, 4: 6}
FILTERS = ("none", "sub", "up", "average", "paeth")

try:
    from numba import njit

    HAVE_NUMBA = True
except ImportError:  # pragma: no cover - exercised on a machine without the jit extra
    HAVE_NUMBA = False

    def njit(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
            return fn

        return wrap if not (args and callable(args[0])) else args[0]


class PngError(ValueError):
    """A PNG this reader does not take, or a malformed one."""


def _unfilter_py(data: NDArray[np.uint8], height: int, stride: int, bpp: int) -> NDArray[np.uint8]:
    out = np.zeros((height, stride), dtype=np.uint8)
    pos = 0
    for y in range(height):
        ft = int(data[pos])
        pos += 1
        for x in range(stride):
            raw = int(data[pos + x])
            a = int(out[y, x - bpp]) if x >= bpp else 0
            b = int(out[y - 1, x]) if y > 0 else 0
            c = int(out[y - 1, x - bpp]) if (y > 0 and x >= bpp) else 0
            if ft == 0:
                v = raw
            elif ft == 1:
                v = raw + a
            elif ft == 2:
                v = raw + b
            elif ft == 3:
                v = raw + ((a + b) >> 1)
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                v = raw + pred
            else:
                raise PngError(f"filter type {ft} at row {y}")
            out[y, x] = v & 255
        pos += stride
    return out


@njit(cache=True)
def _unfilter_nb(data, height, stride, bpp):  # pragma: no cover - the Python twin is the covered one
    out = np.zeros((height, stride), dtype=np.uint8)
    pos = 0
    for y in range(height):
        ft = data[pos]
        pos += 1
        for x in range(stride):
            raw = int(data[pos + x])
            a = int(out[y, x - bpp]) if x >= bpp else 0
            b = int(out[y - 1, x]) if y > 0 else 0
            c = int(out[y - 1, x - bpp]) if (y > 0 and x >= bpp) else 0
            if ft == 0:
                v = raw
            elif ft == 1:
                v = raw + a
            elif ft == 2:
                v = raw + b
            elif ft == 3:
                v = raw + ((a + b) >> 1)
            else:
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                v = raw + pred
            out[y, x] = v & 255
        pos += stride
    return out


def unfilter(data: bytes, height: int, stride: int, bpp: int, backend: str = "auto") -> NDArray[np.uint8]:
    """The unfiltered scanlines of a decompressed IDAT stream, ``(height, stride)`` bytes."""
    arr = np.frombuffer(data, dtype=np.uint8)
    if arr.size != height * (stride + 1):
        raise PngError(f"IDAT holds {arr.size} bytes, expected {height * (stride + 1)}")
    if np.any(arr[:: stride + 1] > 4):
        bad = int(np.argmax(arr[:: stride + 1] > 4))
        raise PngError(f"filter type {int(arr[bad * (stride + 1)])} at row {bad}")
    if backend == "numba" and not HAVE_NUMBA:
        raise RuntimeError("numba backend requested but numba is not installed (uv sync --extra jit)")
    if backend == "numpy" or not HAVE_NUMBA:
        if height * stride > 1 << 22 and not HAVE_NUMBA:
            _LOGGER.warning(
                f"unfiltering {height}x{stride} bytes in Python; install the jit extra for the numba kernel"
            )
        return _unfilter_py(arr, height, stride, bpp)
    return _unfilter_nb(arr, height, stride, bpp)


def read_png(path: Path, backend: str = "auto") -> NDArray[np.uint8] | NDArray[np.uint16]:
    """
    The image as ``(H, W, C)``: ``uint8`` for an 8-bit PNG, ``uint16`` for a 16-bit one. Grey, grey-alpha, RGB
    and RGBA, non-interlaced; anything else is ``PngError`` naming what it is.
    """
    data = Path(path).read_bytes()
    if not data.startswith(SIGNATURE):
        raise PngError(f"{path}: not a PNG")
    pos = len(SIGNATURE)
    ihdr: tuple | None = None
    idat: list[bytes] = []
    while pos + 8 <= len(data):
        length, kind = struct.unpack_from(">I4s", data, pos)
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            if len(chunk) != 13:
                raise PngError(f"{path}: IHDR is {len(chunk)} bytes, not 13")
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            break
    if ihdr is None:
        raise PngError(f"{path}: no IHDR")
    width, height, depth, colour, compression, filter_method, interlace = ihdr
    if interlace:
        raise PngError(f"{path}: interlaced (Adam7); this reader takes non-interlaced PNG only")
    if colour == 3:
        raise PngError(f"{path}: palette (colour type 3); this reader takes grey, grey-alpha, RGB and RGBA")
    if colour not in CHANNELS:
        raise PngError(f"{path}: colour type {colour} is not one of {sorted(CHANNELS)}")
    if depth not in (8, 16):
        raise PngError(f"{path}: bit depth {depth}; this reader takes 8 and 16")
    if compression or filter_method:
        raise PngError(f"{path}: compression {compression} / filter method {filter_method} are not the PNG defaults")
    channels = CHANNELS[colour]
    bpp = channels * (depth // 8)
    stride = width * bpp
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as e:
        raise PngError(f"{path}: IDAT does not inflate ({e})") from e
    rows = unfilter(raw, height, stride, bpp, backend)
    if depth == 8:
        return rows.reshape(height, width, channels)
    return rows.reshape(height, width * channels * 2).view(">u2").astype("<u2").reshape(height, width, channels)


def _filter_rows(rows: NDArray[np.uint8], bpp: int, filter_type: int) -> bytes:
    """Every row filtered with one filter type, each prefixed by its type byte (the writer's side, vectorised)."""
    h = rows.shape[0]
    r = rows.astype(np.int16)
    left = np.zeros_like(r)
    left[:, bpp:] = r[:, :-bpp]
    up = np.zeros_like(r)
    up[1:] = r[:-1]
    upleft = np.zeros_like(r)
    upleft[1:, bpp:] = r[:-1, :-bpp]
    if filter_type == 0:
        out = r
    elif filter_type == 1:
        out = r - left
    elif filter_type == 2:
        out = r - up
    elif filter_type == 3:
        out = r - ((left + up) >> 1)
    elif filter_type == 4:
        p = left + up - upleft
        pa, pb, pc = np.abs(p - left), np.abs(p - up), np.abs(p - upleft)
        pred = np.where((pa <= pb) & (pa <= pc), left, np.where(pb <= pc, up, upleft))
        out = r - pred
    else:
        raise PngError(f"filter type {filter_type} is not one of 0 to 4")
    out = (out & 255).astype(np.uint8)
    return b"".join(bytes([filter_type]) + out[y].tobytes() for y in range(h))


def write_png(path: Path, image: NDArray, filter_type: int = 0) -> None:
    """Write ``(H, W)`` or ``(H, W, C)`` ``uint8`` or ``uint16`` as a non-interlaced PNG with one filter type."""
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = arr[..., None]
    if arr.ndim != 3 or arr.shape[2] not in COLOUR_TYPES:
        raise PngError(f"an image is (H, W, C) with C in {sorted(COLOUR_TYPES)}, got shape {arr.shape}")
    if arr.dtype == np.uint8:
        depth, rows = 8, np.ascontiguousarray(arr).reshape(arr.shape[0], -1)
    elif arr.dtype == np.uint16:
        depth = 16
        rows = np.ascontiguousarray(arr.astype(">u2")).view(np.uint8).reshape(arr.shape[0], -1)
    else:
        raise PngError(f"an image is uint8 or uint16, got {arr.dtype}")
    h, w, c = arr.shape
    bpp = c * (depth // 8)
    ihdr = struct.pack(">IIBBBBB", w, h, depth, COLOUR_TYPES[c], 0, 0, 0)
    body = zlib.compress(_filter_rows(rows, bpp, filter_type), 9)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    Path(path).write_bytes(SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", body) + chunk(b"IEND", b""))


if __name__ == "__main__":
    import tempfile

    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)
    with tempfile.TemporaryDirectory() as d:
        for ft in range(5):
            p = Path(d) / f"f{ft}.png"
            write_png(p, img, ft)
            print(FILTERS[ft], "round trip:", bool(np.array_equal(read_png(p), img)), "numba:", HAVE_NUMBA)
