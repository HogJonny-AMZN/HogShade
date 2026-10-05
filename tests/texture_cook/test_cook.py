"""
HogShade: the cook on a scratch set: the files it writes, the manifest's hashes, byte-identical reruns, the sidecars'
derived fields, the T1 rules applied first, uncompressed on request, the separation outputs, the content check clean
on the cooked set.
Package: tests/texture_cook/test_cook
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pytest

from hogshade.texture_cook import cook, dds2d, png
from hogshade.texture_cook.encoders import default_encoder

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

HAVE_ENCODER = default_encoder() is not None


def _manifest(set_dir: Path) -> dict:
    return json.loads((set_dir / "cooked" / "manifest.json").read_text(encoding="utf-8"))


def test_cook_writes_the_runtime_set_and_the_records(brick: Path):
    """The packaged-game form: ``individual_outputs=False`` writes the packed runtime set alone."""
    result = cook.cook_set(brick, compress=False, individual_outputs=False)
    names = sorted(p.name for p in (brick / "cooked").iterdir())
    assert names == ["T_brick_BC.dds", "T_brick_N.dds", "T_brick_ORM.dds", "manifest.json", "provenance.json"]
    assert result.manifest["individual_outputs"] is False
    m = result.manifest
    assert m["set"] == "brick" and m["compression"] == {"encoder": None, "bc7_profile": None}
    bc = m["textures"]["T_brick_BC.dds"]
    assert bc["format"] == "R8G8B8A8_UNORM_SRGB" and bc["packed"] == {"A": "T_brick_O.png"} and bc["mips"] == 5
    n = m["textures"]["T_brick_N.dds"]
    assert n["format"] == "R8G8_UNORM" and n["flipped_y"] is True and n["normal_convention_in"] == "directx-y"
    orm = m["textures"]["T_brick_ORM.dds"]
    assert orm["packed"] == {"R": "_AO", "G": "_R", "B": "filled 1.0", "A": "T_brick_H.png"}
    assert set(m["inputs"]) >= {"T_brick_BC.png", "T_brick_BC.texture.json", "LICENSE.md"}
    for name, entry in m["textures"].items():
        assert entry["sha256"] == cook.sha256_file(brick / "cooked" / name)
    assert "T_brick_BC.png" in m["not_power_of_two"]  # 24x16
    prov = json.loads((brick / "cooked" / "provenance.json").read_text(encoding="utf-8"))
    assert {"cooked_at", "git_hash", "numpy", "wall_seconds"} <= set(prov)


def test_the_packed_alpha_and_the_flip_reach_the_pixels(brick: Path):
    cook.cook_set(brick, compress=False)
    bc = dds2d.read_2d(brick / "cooked" / "T_brick_BC.dds")
    o = png.read_png(brick / "T_brick_O.png")[..., 0]
    assert np.array_equal(bc.levels[0][..., 3], o), "the opacity map rides in the colour's alpha, untouched at level 0"
    n = dds2d.read_2d(brick / "cooked" / "T_brick_N.dds")
    assert n.levels[0].shape[-1] == 2
    # the source (128, 64, 255) points y down; renormalised and flipped it points y up: green above 128
    g = int(n.levels[0][0, 0, 1])
    assert g > 128 and abs(g - 184) <= 1, "green inverted (0.4457 after renormalisation, encoded 184)"


def test_cooking_twice_is_byte_identical_and_sidecars_gain_only_derived_fields(brick: Path):
    before = json.loads((brick / "T_brick_BC.texture.json").read_text(encoding="utf-8"))
    first = cook.cook_set(brick, compress=False)
    assert {p.name for p in first.written if p.name.endswith(".texture.json")} == {
        p.name for p in brick.glob("*.texture.json")
    }, "the first cook filled every sidecar and lists them"
    hashes = {p.name: cook.sha256_file(p) for p in first.written if p.suffix == ".dds" or p.name == "manifest.json"}
    second = cook.cook_set(brick, compress=False)
    assert not [p for p in second.written if p.name.endswith(".texture.json")], "nothing left to fill"
    assert {
        p.name: cook.sha256_file(p) for p in second.written if p.suffix == ".dds" or p.name == "manifest.json"
    } == hashes
    after = json.loads((brick / "T_brick_BC.texture.json").read_text(encoding="utf-8"))
    assert after["provenance"] == before["provenance"] and after["pack"] == before["pack"], "authored fields untouched"
    assert set(after["derived"]) == {"preset", "colour_space", "mips", "runtime", "resolution"}
    assert after["preset"] == "base_color" and after["colour_space"] == "srgb" and after["resolution"] == 24
    assert after["runtime"] == {"format": "bc7", "container": "dds"}


def test_a_set_with_a_finding_is_refused_before_anything_is_written(tmp_path: Path, texture_writer):
    write_texture = texture_writer
    s = tmp_path / "bad"
    write_texture(s, "T_bad_BC", np.zeros((4, 4, 3), np.uint8))
    with pytest.raises(cook.CookError, match="no LICENSE.md"):
        cook.cook_set(s)
    (s / "LICENSE.md").write_text("# bad\n", encoding="utf-8")
    write_texture(s, "T_bad_N", np.zeros((4, 4, 3), np.uint8))  # no normal_convention
    (s / "T_bad_X.png").write_bytes(b"\x89PNG")
    (s / "T_bad_ORM.png").write_bytes(b"\x89PNG")
    (s / "T_bad_H.tif").write_bytes(b"II*\0")
    with pytest.raises(cook.CookError) as e:
        cook.cook_set(s)
    msg = str(e.value)
    assert (
        "normal_convention" in msg and "_X" in msg and "_ORM is the cook's output" in msg and "TIFF is not read" in msg
    )
    assert not (s / "cooked").exists()


def test_a_pack_naming_a_missing_map_is_refused(tmp_path: Path, texture_writer):
    write_texture = texture_writer
    s = tmp_path / "p"
    s.mkdir()
    (s / "LICENSE.md").write_text("# p\n", encoding="utf-8")
    write_texture(s, "T_p_BC", np.zeros((4, 4, 3), np.uint8), {"pack": {"a": "_O"}})
    with pytest.raises(cook.CookError, match="the set has no T_<base>_O map"):
        cook.cook_set(s)


def test_compress_required_without_an_encoder_is_an_error(brick: Path, monkeypatch):
    monkeypatch.setattr(cook, "default_encoder", lambda: None)
    with pytest.raises(cook.CookError, match="uv sync --extra textures"):
        cook.cook_set(brick, compress=True)
    result = cook.cook_set(brick)  # implicit: uncompressed, no error
    assert result.manifest["compression"]["encoder"] is None


@pytest.mark.skipif(not HAVE_ENCODER, reason="ispc_texcomp not installed (uv sync --extra textures)")
def test_compressed_cook_writes_block_formats_with_the_alpha_profile(brick: Path):
    m = cook.cook_set(brick, bc7_profile="fast").manifest
    t = m["textures"]
    assert t["T_brick_BC.dds"]["format"] == "BC7_UNORM_SRGB" and t["T_brick_BC.dds"]["bc7_profile"] == "alpha_fast"
    assert t["T_brick_N.dds"]["format"] == "BC5_UNORM" and t["T_brick_ORM.dds"]["bc7_profile"] == "alpha_fast"
    assert m["compression"] == {"encoder": "ispc_texcomp", "bc7_profile": "fast"}
    back = dds2d.read_2d(brick / "cooked" / "T_brick_N.dds")
    assert back.format.name == "BC5_UNORM" and len(back.levels) == 5


def test_height_at_the_source_precision_and_normalised(tmp_path: Path, texture_writer):
    write_texture = texture_writer
    s = tmp_path / "ground"
    s.mkdir()
    (s / "LICENSE.md").write_text("# ground\n", encoding="utf-8")
    write_texture(s, "T_ground_H", np.arange(0, 65536, 4096, dtype=np.uint16).reshape(4, 4)[..., None])
    m = cook.cook_set(s, compress=False).manifest
    assert (
        m["textures"]["T_ground_H.dds"]["format"] == "R16_UNORM"
        and m["textures"]["T_ground_H.dds"]["precision"] == "16-bit"
    )
    back = dds2d.read_2d(s / "cooked" / "T_ground_H.dds")
    assert back.levels[0].dtype == np.uint16 and back.levels[0][0, 0, 0] == 0 and back.levels[0][3, 3, 0] == 61440


def test_separation_writes_the_detail_pair_and_records_the_error(brick: Path, tmp_path: Path):
    cook.cook_set(brick, compress=False)
    pictures = tmp_path / "pictures"
    sep = cook.separate_set(brick, radius=4, macro_size=8, compress=False, picture_dir=pictures)
    assert set(sep["outputs"]) == {"T_brick_DH.dds", "T_brick_BC_macro.dds"}
    assert sep["sigma"] == 2.0 and sep["macro_size"] == [6, 4], "24x16 halved until the longer side is at most 8"
    assert sep["error_max"] <= 1.0 / 255.0 + 1e-6
    assert _manifest(brick)["separation"]["_BC"]["source"] == "T_brick_BC.png"
    assert sorted(p.name for p in pictures.iterdir()) == ["high.png", "low.png", "recombined.png", "source.png"]
    dn = cook.separate_set(brick, radius=4, macro_size=8, source_suffix="_N", compress=False)
    assert set(dn["outputs"]) == {"T_brick_DN.dds", "T_brick_N_macro.dds"}
    assert set(_manifest(brick)["separation"]) == {"_BC", "_N"}, "one record per separated suffix"
    for level in dds2d.read_2d(brick / "cooked" / "T_brick_DN.dds").levels[:2]:
        xyz = cook.normals.reconstruct_z(level.astype(np.float32) / 255.0)
        assert np.allclose(np.linalg.norm(xyz, axis=-1), 1.0, atol=0.02), "the detail normal's levels are unit length"
    with pytest.raises(cook.CookError, match="separate takes one of"):
        cook.separate_set(brick, source_suffix="_E")
    for bad in ({"macro_size": 0}, {"radius": 0}, {"picture_size": 0}):
        with pytest.raises(cook.CookError, match="at least 1|positive"):
            cook.separate_set(brick, **bad)


def test_the_content_check_passes_on_a_cooked_set(brick: Path, tmp_path: Path):
    import check_content

    cook.cook_set(brick, compress=False)
    cook.separate_set(brick, radius=4, macro_size=8, compress=False)
    root = tmp_path / "repo"
    dest = root / "content" / "textures" / "brick"
    dest.parent.mkdir(parents=True)
    import shutil

    shutil.copytree(brick, dest)
    assert [str(f) for f in check_content.run(root)] == []


# ----------------------------------------------------------------------------- individual_outputs (T4, 2026-10-04)


def test_the_default_also_writes_every_packed_map_on_its_own_marked_with_its_carrier(brick: Path):
    """The owner: write all individual outputs AND the packed outputs; a development default."""
    result = cook.cook_set(brick, compress=False)
    m = result.manifest
    assert m["individual_outputs"] is True
    names = sorted(p.name for p in (brick / "cooked").iterdir() if p.suffix == ".dds")
    assert names == [
        "T_brick_AO.dds",
        "T_brick_BC.dds",
        "T_brick_H.dds",
        "T_brick_N.dds",
        "T_brick_O.dds",
        "T_brick_ORM.dds",
        "T_brick_R.dds",
    ], "the packed ones and every map that was packed"
    t = m["textures"]
    assert t["T_brick_AO.dds"]["also_in"] == t["T_brick_R.dds"]["also_in"] == "T_brick_ORM.dds"
    assert t["T_brick_H.dds"]["also_in"] == "T_brick_ORM.dds", "the height riding in the ORM alpha"
    assert t["T_brick_O.dds"]["also_in"] == "T_brick_BC.dds", "the opacity riding in the colour alpha"
    assert all("also_in" not in t[k] for k in ("T_brick_BC.dds", "T_brick_N.dds", "T_brick_ORM.dds"))
    for name, entry in t.items():
        assert entry["sha256"] == cook.sha256_file(brick / "cooked" / name)


def test_an_individual_map_is_the_same_pixels_as_its_channel_in_the_carrier(brick: Path):
    cook.cook_set(brick, compress=False)
    orm = dds2d.read_2d(brick / "cooked" / "T_brick_ORM.dds").levels[0]
    ao = dds2d.read_2d(brick / "cooked" / "T_brick_AO.dds").levels[0]
    rough = dds2d.read_2d(brick / "cooked" / "T_brick_R.dds").levels[0]
    opacity = dds2d.read_2d(brick / "cooked" / "T_brick_O.dds").levels[0]
    colour = dds2d.read_2d(brick / "cooked" / "T_brick_BC.dds").levels[0]
    np.testing.assert_array_equal(ao.reshape(orm.shape[:2]), orm[..., 0])
    np.testing.assert_array_equal(rough.reshape(orm.shape[:2]), orm[..., 1])
    np.testing.assert_array_equal(opacity.reshape(colour.shape[:2]), colour[..., 3])


def test_the_resolver_still_prefers_the_carrier_and_individual_for_finds_the_standalone(brick: Path):
    from hogshade.material.runtime import individual_for, locate, manifest_for

    cook.cook_set(brick, compress=False)
    manifest = manifest_for(brick)
    rough = locate(manifest, brick, "T_brick_R.png")
    assert (rough.path.name, rough.channels, rough.packed) == ("T_brick_ORM.dds", "g", True)
    alone = individual_for(manifest, brick, "T_brick_R.png")
    assert alone is not None and (alone.path.name, alone.channels, alone.packed) == ("T_brick_R.dds", "r", False)
    assert individual_for(manifest, brick, "T_brick_BC.png") is None, "a map that was never packed has no copy"
    cook.cook_set(brick, compress=False, individual_outputs=False)
    assert individual_for(manifest_for(brick), brick, "T_brick_R.png") is None, "the packaged form has none"


def test_both_forms_recook_byte_identically(brick: Path):
    cook.cook_set(brick, compress=False)
    first = {p.name: p.read_bytes() for p in (brick / "cooked").iterdir() if p.name != "provenance.json"}
    cook.cook_set(brick, compress=False)
    second = {p.name: p.read_bytes() for p in (brick / "cooked").iterdir() if p.name != "provenance.json"}
    assert first == second


def test_the_off_cook_after_an_on_cook_drops_the_individual_copies_it_wrote(brick: Path, caplog):
    cook.cook_set(brick, compress=False)
    assert (brick / "cooked" / "T_brick_AO.dds").exists()
    (brick / "cooked" / "T_brick_stray.dds").write_bytes(b"not ours")  # an unrecorded file is never ours to delete
    with caplog.at_level(logging.INFO, logger=cook._MODULE_NAME):
        m = cook.cook_set(brick, compress=False, individual_outputs=False).manifest
    names = sorted(p.name for p in (brick / "cooked").iterdir() if p.suffix == ".dds")
    assert names == ["T_brick_BC.dds", "T_brick_N.dds", "T_brick_ORM.dds", "T_brick_stray.dds"], names
    assert m["individual_outputs"] is False and "individual outputs off (the packed-only form)" in caplog.text
    assert "dropped 4 individual copy file(s) an earlier cook wrote: T_brick_AO.dds" in caplog.text
    assert "T_brick_stray.dds" in caplog.text and "no record names" in caplog.text


def test_an_individual_height_is_never_normalised_so_it_matches_the_carrier_alpha(brick: Path):
    """The review: with height_normalise the standalone _H would have been rescaled while the ORM alpha was not."""
    m = cook.cook_set(brick, compress=False, height_normalise=True).manifest
    assert "normalised" not in m["textures"]["T_brick_H.dds"], "the copy keeps the source range"
    orm = dds2d.read_2d(brick / "cooked" / "T_brick_ORM.dds").levels[0]
    height = dds2d.read_2d(brick / "cooked" / "T_brick_H.dds").levels[0]
    assert m["textures"]["T_brick_H.dds"]["format"] == "R16_UNORM", "the copy keeps the 16-bit source's precision"
    as_8bit = np.rint(height.reshape(orm.shape[:2]).astype(np.float64) / 65535.0 * 255.0)
    np.testing.assert_allclose(as_8bit, orm[..., 3], atol=1.0)  # the same range, quantised to the alpha's 8 bits


@pytest.mark.parametrize("individual", [True, False])
def test_each_form_recooks_byte_identically(brick: Path, individual: bool):
    cook.cook_set(brick, compress=False, individual_outputs=individual)
    first = {p.name: p.read_bytes() for p in (brick / "cooked").iterdir() if p.name != "provenance.json"}
    cook.cook_set(brick, compress=False, individual_outputs=individual)
    second = {p.name: p.read_bytes() for p in (brick / "cooked").iterdir() if p.name != "provenance.json"}
    assert first == second


def test_individual_for_finds_the_alpha_packed_maps_and_refuses_a_crafted_key(brick: Path):
    from hogshade.material.runtime import CookedSetError, individual_for, manifest_for

    cook.cook_set(brick, compress=False)
    manifest = manifest_for(brick)
    height = individual_for(manifest, brick, "T_brick_H.png", "height")
    opacity = individual_for(manifest, brick, "T_brick_O.png", "geometry_opacity")
    assert height is not None and (height.path.name, height.packed, height.parameter) == (
        "T_brick_H.dds",
        False,
        "height",
    )
    assert opacity is not None and (opacity.path.name, opacity.channels) == ("T_brick_O.dds", "r")
    for key in ("../../outside.dds", "C:/outside.dds", "/outside.dds"):  # traversal, a drive and a rooted path
        crafted = {**manifest, "textures": {**manifest["textures"], key: dict(manifest["textures"]["T_brick_R.dds"])}}
        with pytest.raises(CookedSetError, match="is not a .dds file name under cooked"):
            individual_for(crafted, brick, "T_brick_R.png")
