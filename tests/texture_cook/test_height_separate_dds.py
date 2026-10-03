"""
HogShade: height keeps the source's precision (16-bit PNG, half and float EXR) and normalises only when asked; the
separation's halves tile and recombine exactly; the 2D DDS writer round-trips every uncompressed format and the
encoder's BC4 blocks decode by hand.
Package: tests/texture_cook/test_height_separate_dds
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hogshade.texture_cook import dds2d, height, separate
from hogshade.texture_cook.encoders import IspcEncoder, default_encoder, pad_to_blocks

# ------------------------------------------------------------------------------------------------ height


def _exr(path: Path, samples: np.ndarray) -> None:
    import OpenEXR

    chan = {"R": samples}
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    with OpenEXR.File(header, chan) as f:
        f.write(str(path))


def test_sixteen_bit_png_keeps_every_step():
    ramp = np.arange(0, 65536, 257, dtype=np.uint16).reshape(16, 16)
    h = height.from_array(ramp)
    assert (h.precision, h.runtime) == ("16-bit", "R16_UNORM")
    chain = height.chain(h)
    assert chain[0].dtype == np.uint16 and np.array_equal(chain[0], ramp) and chain[-1].shape == (1, 1)


def test_half_and_float_exr_keep_their_precision(tmp_path: Path):
    half = (np.arange(64, dtype=np.float32).reshape(8, 8) / 7.0).astype(np.float16)
    _exr(tmp_path / "h.exr", half)
    samples, precision = height.read_exr_channel(tmp_path / "h.exr")
    assert precision == "half" and samples.dtype == np.float16 and np.array_equal(samples, half)
    assert height.from_array(samples).runtime == "R16_FLOAT"
    flt = np.arange(64, dtype=np.float32).reshape(8, 8) * 1234.5678
    _exr(tmp_path / "f.exr", flt)
    samples, precision = height.read_exr_channel(tmp_path / "f.exr")
    assert precision == "float" and samples.dtype == np.float32 and np.array_equal(samples, flt)
    assert height.from_array(samples).runtime == "R32_FLOAT"
    with pytest.raises(ValueError, match="no channel 'Z'"):
        height.read_exr_channel(tmp_path / "f.exr", "Z")


def test_normalise_maps_the_range_and_records_it():
    flt = np.linspace(-2.0, 6.0, 16, dtype=np.float32).reshape(4, 4)
    h, rng = height.normalise(height.from_array(flt))
    assert rng == {"min": -2.0, "max": 6.0} and h.runtime == "R16_UNORM"
    assert h.samples.min() == 0 and h.samples.max() == 65535
    unchanged, empty = height.normalise(height.from_array(np.zeros((2, 2), np.uint16)))
    assert empty == {} and unchanged.runtime == "R16_UNORM"
    assert height.from_array(np.zeros((2, 2), np.uint8)).runtime == "R8_UNORM"


# ------------------------------------------------------------------------------------------- separation


def _tile(n: int = 32) -> np.ndarray:
    rng = np.random.default_rng(5)
    base = rng.random((n // 4, n // 4, 3)).astype(np.float32)
    big = np.kron(base, np.ones((4, 4, 1), np.float32))  # blocky, so it tiles by construction
    return np.clip(big + rng.normal(0, 0.05, big.shape).astype(np.float32), 0, 1)


def test_separation_recombines_exactly_and_both_halves_tile():
    src = _tile()
    r = separate.separate(src, radius=8)
    assert r.sigma == 4.0 and r.radius == 8.0
    assert r.error_max <= 1.0 / 255.0 + 1e-6, "within one 8-bit step: the quantisation of the written high-pass"
    assert np.allclose(separate.recombine(r.low, r.high), r.recon)
    # tiling: the low-pass of the tile equals the low-pass of the 2x2-tiled image, cropped
    tiled = np.tile(src, (2, 2, 1))
    low_tiled = separate.lowpass(tiled, 4.0, wrap=True)[: src.shape[0], : src.shape[1]]
    assert np.allclose(low_tiled, r.low, atol=1e-5)
    m = separate.macro(r.low, 8)
    assert m.shape == (8, 8, 3)
    with pytest.raises(ValueError, match="positive"):
        separate.separate(src, radius=0)


def test_separation_error_comes_from_quantisation_only():
    src = np.zeros((16, 16, 3), np.float32)
    src[8, 8] = 1.0  # a lone white texel: the sharpest high-pass there is
    r = separate.separate(src, radius=2)
    assert 0.0 < r.error_max <= 1.0 / 255.0 + 1e-6 and r.error_mean < r.error_max
    assert r.clipped_texels >= 0


def test_kernel_is_normalised_and_symmetric():
    k = separate.gaussian_kernel(2.0)
    assert np.isclose(k.sum(), 1.0) and np.allclose(k, k[::-1]) and len(k) == 13


# -------------------------------------------------------------------------------------------------- dds


@pytest.mark.parametrize(
    "name", ["R8_UNORM", "R8G8_UNORM", "R8G8B8A8_UNORM", "R8G8B8A8_UNORM_SRGB", "R16_UNORM", "R16_FLOAT", "R32_FLOAT"]
)
def test_uncompressed_dds_round_trips_with_mips(tmp_path: Path, name: str):
    fmt = dds2d.FORMATS[name]
    rng = np.random.default_rng(3)
    shape = (6, 10, fmt.channels)
    if fmt.dtype == "u1":
        top = rng.integers(0, 256, shape, dtype=np.uint8)
    elif fmt.dtype == "<u2":
        top = rng.integers(0, 65536, shape, dtype=np.uint16)
    else:
        top = rng.random(shape).astype(np.float16 if fmt.dtype == "<f2" else np.float32)
    levels = [top]
    while levels[-1].shape[0] > 1 or levels[-1].shape[1] > 1:
        h, w = levels[-1].shape[:2]
        levels.append(np.ascontiguousarray(levels[-1][: max(h // 2, 1), : max(w // 2, 1)]))
    dds2d.write_2d(tmp_path / "t.dds", levels, name)
    back = dds2d.read_2d(tmp_path / "t.dds")
    assert back.format.name == name and (back.width, back.height) == (10, 6) and len(back.levels) == len(levels)
    for a, b in zip(levels, back.levels):
        assert np.array_equal(np.asarray(a).reshape(b.shape), b)


def test_block_dds_round_trips_and_bc4_blocks_decode_by_hand(tmp_path: Path):
    enc = default_encoder()
    if enc is None:
        pytest.skip("ispc_texcomp not installed (uv sync --extra textures)")
    assert isinstance(enc, IspcEncoder)
    ramp = (np.arange(16, dtype=np.uint8).reshape(4, 4) * 17)[..., None]
    blocks = enc.encode(ramp, "bc4")
    assert len(blocks) == 8
    decoded = dds2d.decode_bc4_block(blocks)
    assert np.abs(decoded.astype(int) - ramp[..., 0].astype(int)).max() <= 18, "the 8-level palette's quantisation"
    rg = np.dstack([ramp[..., 0], ramp[..., 0][::-1]]).astype(np.uint8)
    b5 = enc.encode(rg, "bc5")
    assert len(b5) == 16 and np.abs(dds2d.decode_bc4_block(b5[8:]).astype(int) - rg[..., 1].astype(int)).max() <= 18
    rgba = np.dstack([ramp[..., 0]] * 4).astype(np.uint8)
    b7 = enc.encode(rgba, "bc7", alpha=True, profile="fast")
    assert len(b7) == 16
    small = enc.encode(np.full((1, 1, 1), 200, np.uint8), "bc4")
    assert len(small) == 8, "a 1x1 mip is one padded block"
    assert pad_to_blocks(np.zeros((2, 3, 4), np.uint8)).shape == (4, 4, 4)
    dds2d.write_2d_blocks(
        tmp_path / "b.dds",
        [
            b7,
            small and enc.encode(np.full((2, 2, 4), 9, np.uint8), "bc7"),
            enc.encode(np.full((1, 1, 4), 9, np.uint8), "bc7"),
        ],
        4,
        4,
        "BC7_UNORM",
    )
    back = dds2d.read_2d(tmp_path / "b.dds")
    assert back.format.name == "BC7_UNORM" and len(back.levels) == 3 and back.levels[0] == b7
    with pytest.raises(ValueError, match="expected 16"):
        dds2d.write_2d_blocks(tmp_path / "x.dds", [b"\0" * 8], 4, 4, "BC7_UNORM")
    with pytest.raises(ValueError, match="block format"):
        dds2d.write_2d(tmp_path / "x.dds", [np.zeros((4, 4, 4), np.uint8)], "BC7_UNORM")
    with pytest.raises(ValueError, match="bc7 takes"):
        enc.encode(np.zeros((4, 4, 3), np.uint8), "bc7")
