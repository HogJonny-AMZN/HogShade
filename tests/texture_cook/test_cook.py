"""
HogShade: the cook on a scratch set: the files it writes, the manifest's hashes, byte-identical reruns, the sidecars'
derived fields, the T1 rules applied first, uncompressed on request, the separation outputs, the content check clean
on the cooked set.
Package: tests/texture_cook/test_cook
"""

from __future__ import annotations

import json
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
    result = cook.cook_set(brick, compress=False)
    names = sorted(p.name for p in (brick / "cooked").iterdir())
    assert names == ["T_brick_BC.dds", "T_brick_N.dds", "T_brick_ORM.dds", "manifest.json", "provenance.json"]
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
    hashes = {p.name: cook.sha256_file(p) for p in first.written if p.name != "provenance.json"}
    second = cook.cook_set(brick, compress=False)
    assert {p.name: cook.sha256_file(p) for p in second.written if p.name != "provenance.json"} == hashes
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
    assert _manifest(brick)["separation"]["source"] == "T_brick_BC.png"
    assert sorted(p.name for p in pictures.iterdir()) == ["high.png", "low.png", "recombined.png", "source.png"]
    dn = cook.separate_set(brick, radius=4, macro_size=8, source_suffix="_N", compress=False)
    assert set(dn["outputs"]) == {"T_brick_DN.dds", "T_brick_N_macro.dds"}
    with pytest.raises(cook.CookError, match="no _E map"):
        cook.separate_set(brick, source_suffix="_E")


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
