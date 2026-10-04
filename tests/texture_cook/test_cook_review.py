"""
HogShade: the cook's review round: a set with mis-sized or mis-shaped maps is refused before anything is written,
a pack target in another variant is a finding, a grey colour map cooks and an RGBA one logs its dropped alpha, the
sidecars stay untouched when a write fails, a re-cook keeps the separation record and the manifest stays one, the
tool turns a stray ValueError into exit 2, the job warns on an unknown compress value.
Package: tests/texture_cook/test_cook_review
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pytest

from hogshade.jobs import cook_textures as job
from hogshade.texture_cook import cook, dds2d

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def _set(tmp_path: Path, name: str) -> Path:
    s = tmp_path / name
    s.mkdir()
    (s / "LICENSE.md").write_text(f"# {name}\n", encoding="utf-8")
    return s


def test_a_pack_target_of_another_size_is_a_finding_and_nothing_is_written(tmp_path: Path, texture_writer):
    s = _set(tmp_path, "mis")
    texture_writer(s, "T_mis_BC", np.zeros((8, 8, 3), np.uint8), {"pack": {"a": "_O"}})
    texture_writer(s, "T_mis_O", np.zeros((4, 4, 1), np.uint8))
    before = (s / "T_mis_BC.texture.json").read_bytes()
    with pytest.raises(cook.CookError, match="one size per set and variant") as e:
        cook.cook_set(s, compress=False)
    assert "T_mis_BC.png 8x8" in str(e.value) and "T_mis_O.png 4x4" in str(e.value)
    assert not (s / "cooked").exists() and (s / "T_mis_BC.texture.json").read_bytes() == before


def test_orm_parts_of_two_sizes_are_the_same_finding(tmp_path: Path, texture_writer):
    s = _set(tmp_path, "orm")
    texture_writer(s, "T_orm_AO", np.zeros((8, 8, 1), np.uint8))
    texture_writer(s, "T_orm_R", np.zeros((8, 4, 1), np.uint8))
    with pytest.raises(cook.CookError, match="one size per set and variant"):
        cook.cook_set(s, compress=False)


def test_a_pack_target_in_another_variant_is_a_finding(tmp_path: Path, texture_writer):
    s = _set(tmp_path, "var")
    texture_writer(s, "T_var_BC_wet", np.zeros((4, 4, 3), np.uint8), {"pack": {"a": "_O"}})
    texture_writer(s, "T_var_O", np.zeros((4, 4, 1), np.uint8))  # the unvarianted one; the carrier is _wet
    with pytest.raises(cook.CookError, match="variant 'wet' has no such map"):
        cook.cook_set(s, compress=False)


def test_a_grey_alpha_colour_map_is_a_finding(tmp_path: Path, texture_writer):
    s = _set(tmp_path, "ga")
    texture_writer(s, "T_ga_BC", np.zeros((4, 4, 2), np.uint8))
    with pytest.raises(cook.CookError, match="grey-alpha"):
        cook.cook_set(s, compress=False)


def test_a_grey_colour_map_is_broadcast_and_an_rgba_one_logs_its_dropped_alpha(tmp_path: Path, texture_writer, caplog):
    s = _set(tmp_path, "grey")
    texture_writer(s, "T_grey_BC", np.full((4, 4, 1), 100, np.uint8))
    rgba = np.full((4, 4, 4), 50, np.uint8)
    rgba[..., 3] = 7
    texture_writer(s, "T_grey_E", rgba)
    with caplog.at_level(logging.INFO, logger=cook._MODULE_NAME):
        m = cook.cook_set(s, compress=False).manifest
    assert "T_grey_BC.png: a grey map, broadcast to RGB" in caplog.text
    assert "T_grey_E.png: the source alpha is dropped (the runtime alpha is 1.0)" in caplog.text
    bc = dds2d.read_2d(s / "cooked" / "T_grey_BC.dds").levels[0]
    assert bc.shape[-1] == 4 and np.all(bc[..., :3] == 100) and np.all(bc[..., 3] == 255)
    e = dds2d.read_2d(s / "cooked" / "T_grey_E.dds").levels[0]
    assert np.all(e[..., 3] == 255), "the source alpha never reaches the runtime map unless packed"
    assert set(m["textures"]) == {"T_grey_BC.dds", "T_grey_E.dds"}
    # a written texture, a filled sidecar: one INFO line each
    assert "wrote T_grey_BC.dds: R8G8B8A8_UNORM_SRGB, 3 mip(s)" in caplog.text
    assert "wrote T_grey_BC.texture.json: derived" in caplog.text


def test_a_failed_write_leaves_the_sidecars_and_writes_no_manifest(brick: Path, monkeypatch):
    before = {p.name: p.read_bytes() for p in brick.glob("*.texture.json")}

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(cook.dds2d, "write_2d", boom)
    with pytest.raises(OSError, match="disk full"):
        cook.cook_set(brick, compress=False)
    assert {p.name: p.read_bytes() for p in brick.glob("*.texture.json")} == before, "nothing derived was written"
    assert not (brick / "cooked" / "manifest.json").exists()


def test_a_recook_keeps_the_separation_record_and_the_manifest_stays_one(brick: Path, caplog):
    cook.cook_set(brick, compress=False)
    cook.separate_set(brick, radius=4, macro_size=8, compress=False)
    with caplog.at_level(logging.INFO, logger=cook._MODULE_NAME):
        second = cook.cook_set(brick, compress=False).manifest
    assert second["separation"]["source"] == "T_brick_BC.png" and "T_brick_DH.dds" in second["separation"]["outputs"]
    assert "the earlier separation record is kept" in caplog.text
    on_disk = json.loads((brick / "cooked" / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk == second
    third = cook.cook_set(brick, compress=False).manifest
    assert third == second, "cooking again with the separation in place is the same manifest"


def test_a_separation_whose_files_are_gone_is_dropped_and_a_stray_dds_is_warned_about(brick: Path, caplog):
    cook.cook_set(brick, compress=False)
    cook.separate_set(brick, radius=4, macro_size=8, compress=False)
    (brick / "cooked" / "T_brick_DH.dds").unlink()
    (brick / "cooked" / "T_brick_stray.dds").write_bytes(b"DDS ")
    with caplog.at_level(logging.WARNING, logger=cook._MODULE_NAME):
        m = cook.cook_set(brick, compress=False).manifest
    assert "separation" not in m
    assert "separation record is dropped" in caplog.text and "T_brick_DH.dds" in caplog.text
    assert "no record names, left alone: T_brick_BC_macro.dds, T_brick_stray.dds" in caplog.text
    assert (brick / "cooked" / "T_brick_stray.dds").exists(), "the cook never deletes"


def test_the_tool_turns_a_stray_error_into_exit_2(brick: Path, monkeypatch, caplog):
    import cook_textures as tool

    def boom(*_args, **_kwargs):
        raise ValueError("a defect past the checks")

    monkeypatch.setattr(cook.dds2d, "write_2d", boom)
    with caplog.at_level(logging.ERROR, logger=tool._MODULE_NAME):
        assert tool.main(["cook", str(brick), "--no-compress"]) == 2
    assert "texture cook failed on" in caplog.text and "ValueError: a defect past the checks" in caplog.text


def test_the_job_warns_on_an_unknown_compress_value_and_treats_it_as_auto(brick: Path, caplog, monkeypatch):
    from hogshade.texture_cook import encoders

    monkeypatch.setattr(encoders, "default_encoder", lambda: None)  # the job binds it at call time
    with caplog.at_level(logging.WARNING, logger=job._MODULE_NAME):
        m = job.main({"set_dir": str(brick), "compress": "maybe"})
    assert "compress='maybe' is not one of" in caplog.text
    assert m["compression"]["encoder"] is None


def test_a_missing_encoder_warns_once_across_the_job(brick: Path, monkeypatch, caplog):
    from hogshade.texture_cook import encoders

    monkeypatch.setattr(encoders, "IspcEncoder", lambda: (_ for _ in ()).throw(ImportError("no ispc_texcomp")))
    with caplog.at_level(logging.WARNING, logger=encoders._MODULE_NAME):
        job.main({"set_dir": str(brick), "separate": "1", "radius": "4", "macro": "8"})
    assert caplog.text.count("no block encoder") == 1


def test_a_single_channel_map_with_three_channels_takes_r_and_says_so(tmp_path: Path, texture_writer, caplog):
    s = _set(tmp_path, "r3")
    rgb = np.zeros((4, 4, 3), np.uint8)
    rgb[..., 0] = 200
    texture_writer(s, "T_r3_O", rgb)
    with caplog.at_level(logging.INFO, logger=cook._MODULE_NAME):
        cook.cook_set(s, compress=False)
    assert "T_r3_O.png: 3 channels in a single-channel map; R is taken" in caplog.text
    assert np.all(dds2d.read_2d(s / "cooked" / "T_r3_O.dds").levels[0] == 200)
