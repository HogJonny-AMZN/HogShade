"""
HogShade: the PNG reader round-trips every colour type at 8 and 16 bits under each of the five filters, through
both unfilter backends; interlaced and palette PNGs are refused with their reason.
Package: tests/texture_cook/test_png
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from hogshade.texture_cook import png


@pytest.mark.parametrize("channels", [1, 2, 3, 4], ids=["grey", "grey-alpha", "rgb", "rgba"])
@pytest.mark.parametrize("dtype", [np.uint8, np.uint16], ids=["8-bit", "16-bit"])
@pytest.mark.parametrize("filter_type", range(5), ids=png.FILTERS)
def test_round_trip_every_colour_type_depth_and_filter(tmp_path: Path, channels, dtype, filter_type):
    rng = np.random.default_rng(filter_type * 10 + channels)
    high = 256 if dtype == np.uint8 else 65536
    img = rng.integers(0, high, (13, 11, channels), dtype=dtype)
    path = tmp_path / "t.png"
    png.write_png(path, img, filter_type)
    back = png.read_png(path)
    assert back.dtype == dtype and back.shape == img.shape
    assert np.array_equal(back, img)
    assert np.array_equal(png.read_png(path, backend="numpy"), img), "the Python twin agrees with the kernel"


def test_a_two_dimensional_array_writes_as_grey(tmp_path: Path):
    img = np.arange(20, dtype=np.uint8).reshape(4, 5)
    png.write_png(tmp_path / "g.png", img, 1)
    assert png.read_png(tmp_path / "g.png").shape == (4, 5, 1)


def _png_with_ihdr(path: Path, width: int, height: int, depth: int, colour: int, interlace: int, raw: bytes) -> None:
    ihdr = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, interlace)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    path.write_bytes(png.SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_interlaced_palette_and_odd_depths_are_refused(tmp_path: Path):
    raw = bytes([0, 1, 2, 3, 4])
    _png_with_ihdr(tmp_path / "i.png", 4, 1, 8, 0, 1, raw)
    with pytest.raises(png.PngError, match="interlaced"):
        png.read_png(tmp_path / "i.png")
    _png_with_ihdr(tmp_path / "p.png", 4, 1, 8, 3, 0, raw)
    with pytest.raises(png.PngError, match="palette"):
        png.read_png(tmp_path / "p.png")
    _png_with_ihdr(tmp_path / "d.png", 4, 1, 4, 0, 0, raw)
    with pytest.raises(png.PngError, match="bit depth 4"):
        png.read_png(tmp_path / "d.png")
    (tmp_path / "n.png").write_bytes(b"not a png")
    with pytest.raises(png.PngError, match="not a PNG"):
        png.read_png(tmp_path / "n.png")


def test_a_bad_filter_byte_and_a_short_stream_are_refused(tmp_path: Path):
    _png_with_ihdr(tmp_path / "f.png", 2, 1, 8, 0, 0, bytes([9, 1, 2]))
    with pytest.raises(png.PngError, match="filter type 9 at row 0"):
        png.read_png(tmp_path / "f.png")
    _png_with_ihdr(tmp_path / "s.png", 2, 2, 8, 0, 0, bytes([0, 1, 2]))
    with pytest.raises(png.PngError, match="IDAT holds 3 bytes"):
        png.read_png(tmp_path / "s.png")


def test_writer_refuses_what_it_cannot_encode(tmp_path: Path):
    with pytest.raises(png.PngError, match="uint8 or uint16"):
        png.write_png(tmp_path / "x.png", np.zeros((2, 2, 3), np.float32))
    with pytest.raises(png.PngError, match="C in"):
        png.write_png(tmp_path / "x.png", np.zeros((2, 2, 5), np.uint8))
    with pytest.raises(png.PngError, match="filter type 7"):
        png.write_png(tmp_path / "x.png", np.zeros((2, 2, 3), np.uint8), 7)


@pytest.mark.skipif(not png.HAVE_NUMBA, reason="numba not installed")
def test_numba_backend_is_used_when_present(tmp_path: Path):
    img = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    png.write_png(tmp_path / "k.png", img, 4)
    assert np.array_equal(png.read_png(tmp_path / "k.png", backend="numba"), img)
