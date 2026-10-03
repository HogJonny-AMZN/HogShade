"""
HogShade: mips average in linear space and end at 1x1; a normal mip is unit length; a DirectX normal flips; ORM packs
with the neutral fill; alpha carriers put a map in the alpha; the pack field's findings.
Package: tests/texture_cook/test_mips_normals_pack
"""

from __future__ import annotations

import numpy as np
import pytest

from hogshade.texture_cook import colour, mips, normals, pack


def test_colour_mip_is_the_linear_average_not_the_srgb_average():
    # a 2x2 checker of sRGB 0 and 1: the linear average is 0.5, re-encoded 0.735; the sRGB average would be 0.5
    checker = np.zeros((2, 2, 3), np.float32)
    checker[0, 1] = checker[1, 0] = 1.0
    chain = mips.colour_chain(checker)
    assert len(chain) == 2 and chain[-1].shape == (1, 1, 3)
    assert chain[-1][0, 0, 0] == pytest.approx(float(colour.linear_to_srgb(np.float32(0.5))), abs=1e-6)
    assert chain[-1][0, 0, 0] != pytest.approx(0.5, abs=0.05)


def test_chain_ends_at_one_by_one_with_dds_sizes():
    chain = mips.chain(np.ones((5, 3, 1), np.float32))
    assert [lvl.shape[:2] for lvl in chain] == [(5, 3), (2, 1), (1, 1)], "DDS sizes: max(side // 2, 1)"
    assert all(np.allclose(lvl, 1.0) for lvl in chain)


def test_normal_mips_stay_unit_length():
    rng = np.random.default_rng(1)
    xyz = rng.normal(size=(8, 8, 3)).astype(np.float32)
    xyz[..., 2] = np.abs(xyz[..., 2]) + 0.1
    xyz /= np.linalg.norm(xyz, axis=-1, keepdims=True)
    chain = mips.normal_chain(xyz)
    for lvl in chain[1:]:
        assert np.allclose(np.linalg.norm(lvl, axis=-1), 1.0, atol=1e-5)


def test_directx_normal_flips_green_and_opengl_does_not():
    enc = np.full((2, 2, 3), [0.5, 0.75, 1.0], np.float32)
    xyz = normals.decode(enc)
    gl = normals.to_opengl(xyz, "opengl+y")
    dx = normals.to_opengl(xyz, "directx-y")
    assert (
        np.allclose(gl, xyz)
        and np.allclose(dx[..., 1], -xyz[..., 1])
        and np.allclose(dx[..., [0, 2]], xyz[..., [0, 2]])
    )
    with pytest.raises(ValueError, match="normal convention"):
        normals.to_opengl(xyz, "y-down")
    rg = normals.to_rg(normals.encode(xyz))
    assert rg.shape == (2, 2, 2) and np.allclose(normals.reconstruct_z(rg), xyz, atol=2e-3)


def test_orm_packs_in_order_and_fills_a_missing_channel():
    ao = np.full((2, 2, 1), 0.25, np.float32)
    rough = np.full((2, 2, 1), 0.5, np.float32)
    packed, record = pack.pack_orm(ao, rough, None, (2, 2))
    assert packed.shape == (2, 2, 4)
    assert np.allclose(packed[..., 0], 0.25) and np.allclose(packed[..., 1], 0.5) and np.allclose(packed[..., 2], 1.0)
    assert record == {"R": "_AO", "G": "_R", "B": "filled 1.0"}
    with pytest.raises(ValueError, match="is 3x3, the set is 2x2"):
        pack.pack_orm(np.ones((3, 3, 1), np.float32), None, None, (2, 2))


def test_alpha_carrier_rules_and_put_alpha():
    available = {"_BC", "_O", "_H", "_N"}
    assert pack.check_pack({"a": "_O"}, "_BC", available) == []
    assert pack.check_pack({"a": "_H"}, "_ORM", available) == []
    assert any("not an alpha carrier" in m for m in pack.check_pack({"a": "_O"}, "_N", available))
    assert any("not a single-channel suffix" in m for m in pack.check_pack({"a": "_N"}, "_BC", available))
    assert any("the set has no T_<base>_C map" in m for m in pack.check_pack({"a": "_C"}, "_BC", available))
    assert any(
        "reserved for a later increment" in m
        for m in pack.check_pack({"a": {"from": "_H", "op": "invert"}}, "_BC", available)
    )
    assert any("one key, 'a'" in m for m in pack.check_pack({"b": "_O"}, "_BC", available))
    carrier = np.ones((2, 2, 4), np.float32)
    out = pack.put_alpha(carrier, np.full((2, 2), 0.3, np.float32))
    assert np.allclose(out[..., 3], 0.3) and np.allclose(out[..., :3], 1.0) and np.allclose(carrier[..., 3], 1.0)
    with pytest.raises(ValueError, match="four channels"):
        pack.put_alpha(np.ones((2, 2, 3), np.float32), np.ones((2, 2), np.float32))
