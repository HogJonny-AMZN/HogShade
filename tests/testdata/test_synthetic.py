"""
HogShade: the synthetic texture set (T4 tier 1): the generator is deterministic and covers every suffix the standard
names, the named points hold the values a person would work out by hand, the cook carries them through to the DDS (the
carriers and the individual copies, the alpha-packed cutout, the 16-bit height), and a document binds every map.
Package: tests/testdata/test_synthetic
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hogshade.material.runtime import individual_for, input_digest, locate, manifest_for, runtime_textures
from hogshade.material.sets import document_for_set
from hogshade.material.textures import SUFFIXES
from hogshade.testdata import synthetic
from hogshade.texture_cook import cook, dds2d, png

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "content" / "textures" / "synthetic"
N = synthetic.SIZE


def _points() -> dict[tuple[str, str | None, str], dict]:
    return {(p["map"], p["variant"], p["name"]): p for p in synthetic.known_points()}


@pytest.fixture(scope="module")
def points() -> dict[tuple[str, str | None, str], dict]:
    return _points()


@pytest.fixture
def authoring(tmp_path: Path) -> Path:
    """The generated set in a scratch directory, no ``cooked/``."""
    synthetic.generate(tmp_path / "set")
    return tmp_path / "set"


# ----------------------------------------------------------------------------- the generator


def test_the_set_has_a_map_for_every_suffix_the_standard_names_and_one_variant():
    assert {s.suffix for s in synthetic.SPECS} == set(SUFFIXES)
    assert [s.stem for s in synthetic.SPECS if s.variant] == ["T_synthetic_BC_blue"]
    assert len(synthetic.SPECS) == len(SUFFIXES) + 1


def test_generation_is_deterministic_and_the_files_read_back_as_the_arrays(authoring: Path, tmp_path: Path):
    synthetic.generate(tmp_path / "again")
    for spec in synthetic.SPECS:
        a = (authoring / f"{spec.stem}.png").read_bytes()
        b = (tmp_path / "again" / f"{spec.stem}.png").read_bytes()
        assert a == b, spec.stem
        np.testing.assert_array_equal(
            png.read_png(authoring / f"{spec.stem}.png").squeeze(), synthetic.render_map(spec.suffix, spec.variant)
        )
    assert (authoring / "LICENSE.md").read_text(encoding="utf-8").startswith("# synthetic")


def test_the_sidecars_carry_provenance_the_normal_convention_and_the_cutout_pack(authoring: Path):
    def sidecar(stem: str) -> dict:
        return json.loads((authoring / f"{stem}.texture.json").read_text(encoding="utf-8"))

    assert sidecar("T_synthetic_N")["normal_convention"] == "opengl+y"
    assert sidecar("T_synthetic_BC")["pack"] == {"a": "_O"} and "pack" not in sidecar("T_synthetic_BC_blue")
    for spec in synthetic.SPECS:
        prov = sidecar(spec.stem)["provenance"]
        assert prov["origin"] == "author" and prov["generator"].startswith("hogshade.testdata.synthetic")


def test_a_size_the_layout_does_not_support_is_refused(tmp_path: Path):
    for size in (32, 64, 100, 4096):
        with pytest.raises(synthetic.SyntheticError, match="power of two between 128 and 2048"):
            synthetic.render_map("_R", None, size)
    with pytest.raises(synthetic.SyntheticError, match="power of two"):
        synthetic.generate(tmp_path / "never", 100)
    assert not (tmp_path / "never").exists(), "a refused size leaves no directory behind"
    small = synthetic.render_map("_R", None, 128)
    assert small.shape == (128, 128) and small.dtype == np.uint8
    with pytest.raises(synthetic.SyntheticError, match="no _ZZ"):
        synthetic.spec_for("_ZZ")


def test_the_legend_fits_the_strip_at_every_size_and_is_cut_with_a_dot_where_it_cannot():
    from hogshade.bitmap_font import text_width

    widest = max(synthetic.SPECS, key=lambda s: len(synthetic.legend_label(s, 2048)))
    assert synthetic.legend_label(widest, N) == "_AX specular_anisotropy", "the longest label is whole at 512"
    for size in (128, 256, 512, 1024, 2048):
        for spec in synthetic.SPECS:
            label = synthetic.legend_label(spec, size)
            scale = max(1, round(2 * size / 512))
            assert text_width(label, scale) <= size - 2 * max(1, round(8 * size / 512)), (size, label)
    assert synthetic.legend_label(widest, 128).endswith("."), "cut, never silently clipped"
    strip = 128 // synthetic.STRIP_DIV
    img = synthetic.render_map("_AX", None, 128)
    assert img[128 - strip :].max() == 255, "the label's ink is inside the strip at the smallest size"


def test_a_draw_function_returning_the_wrong_dtype_is_refused(monkeypatch):
    wrong = lambda f: np.zeros((f.size, f.size))
    bad = synthetic.MapSpec("_R", "bad", "specular_roughness", wrong, "gray8", 0, 255, {})
    monkeypatch.setattr(synthetic, "SPECS", (*synthetic.SPECS, bad))
    with pytest.raises(synthetic.SyntheticError, match="draw returned float64 rank 2; the gray8 kind is"):
        synthetic.render_map("_R", "bad")


def test_every_map_names_itself_in_a_legend_strip():
    strip = N // synthetic.STRIP_DIV
    for spec in synthetic.SPECS:
        img = synthetic.render_map(spec.suffix, spec.variant)
        below = img[N - strip :]
        assert len(np.unique(below.reshape(strip, -1), axis=0)) >= 2, f"{spec.stem}: the strip holds a label"
    colour = synthetic.render_map("_BC")
    assert not np.array_equal(colour[: N - strip], synthetic.render_map("_BC", "blue")[: N - strip]), (
        "the variant differs"
    )


def test_the_contact_sheet_shows_every_map_within_the_gallerys_limit():
    sheet = synthetic.contact_sheet()
    assert sheet.shape == (1024, 1024, 3) and sheet.dtype == np.uint8
    k = [s.suffix for s in synthetic.SPECS].index("_R")
    r, c = divmod(k, 4)
    tile = sheet[r * 256 : (r + 1) * 256, c * 256 : (c + 1) * 256]
    np.testing.assert_array_equal(tile[..., 0], synthetic.render_map("_R", None, 256))
    assert not sheet[3 * 256 :, 3 * 256 :].any(), (
        "the sixteenth tile of the 4 x 4 is empty (fifteen maps: fourteen suffixes and the variant)"
    )


def test_the_orientation_arrows_point_along_plus_u_and_plus_v():
    img = synthetic.render_map("_BC")
    yellow = np.all(img == (255, 255, 0), axis=-1)
    cyan = np.all(img == (0, 255, 255), axis=-1)
    _rows_y, cols_y = np.nonzero(yellow)
    rows_c, _cols_c = np.nonzero(cyan)
    # the head is the heavy end: more arrow pixels in the last quarter of the span than the first
    span = cols_y.max() - cols_y.min()
    assert (cols_y > cols_y.min() + 0.75 * span).sum() > (cols_y < cols_y.min() + 0.25 * span).sum(), "+U points right"
    span = rows_c.max() - rows_c.min()
    assert (rows_c < rows_c.min() + 0.25 * span).sum() > (rows_c > rows_c.min() + 0.75 * span).sum(), "+V points up"


def test_the_named_points_hold_the_values_worked_out_by_hand(points):
    r = [points[("_R", None, f"band {b} of 8")]["value"][0] for b in range(8)]
    assert r == [round(b / 7 * 255) for b in range(8)] == [0, 36, 73, 109, 146, 182, 219, 255]
    assert points[("_M", None, "checker block 0,0 (metal)")]["value"] == [255]
    assert points[("_M", None, "checker block 1,0 (dielectric)")]["value"] == [0]
    assert points[("_BC", None, "patch red")]["value"] == [200, 40, 40]
    assert points[("_BC", "blue", "patch red")]["value"] == [40, 40, 200], "R takes G, G takes B, B takes R"
    assert points[("_BC", None, "arrow +U")]["value"] == [255, 255, 0]
    assert points[("_BC", None, "arrow +V")]["value"] == [0, 255, 255]
    tilt = {name: p["value"] for (m, _v, name), p in points.items() if m == "_N"}
    assert tilt["flat (top left)"] == [128, 128, 255]
    assert tilt["leans +U (top right)"] == [191, 128, 238], "sin 30, 0, cos 30"
    assert tilt["leans +V (bottom left)"] == [128, 191, 238]
    assert tilt["leans -U (bottom right)"] == [64, 128, 238]
    up = tilt["bump, half way toward +V"]
    assert up[1] > 128 and abs(up[0] - 128) <= 1, "OpenGL +Y: green above 128 where the surface leans toward +V"
    right = tilt["bump, half way toward +U"]
    assert right[0] > 128 and abs(right[1] - 128) <= 1
    cx, cy = N / 2, (N - N // 16) / 2
    for suffix, centre, corner in (("_AO", 255, None), ("_SO", 64, None)):
        c = points[(suffix, None, "centre")]["value"][0]
        assert abs(c - centre) <= 2, (suffix, c)
        k = points[(suffix, None, "near a corner")]
        d = np.hypot(k["col"] + 0.5 - cx, k["row"] + 0.5 - cy) / np.hypot(cx, cy)
        want = 255 * (1 - 0.75 * d) if suffix == "_AO" else 255 * (0.25 + 0.75 * d)
        assert abs(k["value"][0] - want) <= 1.5, (suffix, k, want)
    assert points[("_C", None, "between lines")]["value"] == [255]
    for u in (0.125, 0.375, 0.625):
        p = points[("_H", None, f"ramp at u={u}")]
        h = 0.5 * (p["col"] + 0.5) / N + (0.25 if (p["col"] + 0.5) / N >= 0.5 else 0.0)
        assert abs(p["value"][0] - round(h * 65535)) <= 1, p
    apex = points[("_H", None, "cone apex")]["value"][0] / 65535
    assert 0.80 < apex < 0.83, "0.75 ramp + 0.25 step is 0.625; plus the cone's 0.2 is 0.825 less the pixel offset"
    assert points[("_O", None, "inside the disc")]["value"] == [255]
    assert points[("_O", None, "outside the disc")]["value"] == [0]
    assert [points[("_SC", None, f"band {k}")]["value"] for k in range(3)] == [
        list(c) for c in synthetic.SPECULAR_BANDS
    ]
    assert points[("_E", None, "inside the stem of the E")]["value"] == list(synthetic.EMISSION)
    assert points[("_E", None, "outside the E")]["value"] == [0, 0, 0]
    sw, ar, ax = (points[(s, None, "at 0.25")]["value"][0] for s in ("_SW", "_AR", "_AX"))
    assert abs(sw - 64) <= 1 and abs(ar - 191) <= 1 and abs(ax - 64) <= 1, "SW up the V, AR down it, AX along U"


# ----------------------------------------------------------------------------- the cook carries them through


def _texel(path: Path, col: int, row: int) -> list[int]:
    level = dds2d.read_2d(path).levels[0]
    return [int(x) for x in np.atleast_1d(level[row, col])]


def test_the_cooked_carriers_and_individual_copies_hold_the_known_texels(authoring: Path, points):
    result = cook.cook_set(authoring, compress=False)
    cooked = authoring / "cooked"
    assert result.manifest["individual_outputs"] is True
    t = result.manifest["textures"]
    assert t["T_synthetic_BC.dds"]["packed"] == {"A": "T_synthetic_O.png"}
    assert t["T_synthetic_ORM.dds"]["packed"] == {"R": "_AO", "G": "_R", "B": "_M"}
    for individual in ("AO", "R", "M"):
        assert t[f"T_synthetic_{individual}.dds"]["also_in"] == "T_synthetic_ORM.dds"
    assert t["T_synthetic_O.dds"]["also_in"] == "T_synthetic_BC.dds"
    for (suffix, variant, name), p in points.items():
        col, row, value = p["col"], p["row"], p["value"]
        if suffix == "_BC" and variant is None:
            texel = _texel(cooked / "T_synthetic_BC.dds", col, row)
            assert texel[:3] == value, (name, texel)
            assert texel[3] == synthetic.render_map("_O")[row, col], "the cutout rides in the alpha"
        elif suffix == "_BC":
            assert _texel(cooked / "T_synthetic_BC_blue.dds", col, row)[:3] == value, name
        elif suffix == "_N":
            texel = _texel(cooked / "T_synthetic_N.dds", col, row)
            assert max(abs(a - b) for a, b in zip(texel[:2], value[:2], strict=True)) <= 1, (name, texel, value)
        elif suffix in ("_R", "_M", "_AO"):
            channel = {"_AO": 0, "_R": 1, "_M": 2}[suffix]
            assert _texel(cooked / "T_synthetic_ORM.dds", col, row)[channel] == value[0], (suffix, name)
            assert _texel(cooked / f"T_synthetic{suffix}.dds", col, row) == value, (suffix, name)
        elif suffix == "_O":
            assert _texel(cooked / "T_synthetic_BC.dds", col, row)[3] == value[0], name
            assert _texel(cooked / "T_synthetic_O.dds", col, row) == value, name
        elif suffix == "_H":
            assert _texel(cooked / "T_synthetic_H.dds", col, row) == value, "R16_UNORM keeps all 16 bits"
        else:
            assert _texel(cooked / f"T_synthetic{suffix}.dds", col, row)[: len(value)] == value, (suffix, name)


def test_the_variant_differs_from_the_base_on_every_colour_patch_and_not_on_the_greys(points):
    for name in ("red", "green", "blue"):
        assert points[("_BC", None, f"patch {name}")]["value"] != points[("_BC", "blue", f"patch {name}")]["value"]
    for name in ("white", "mid grey", "dark grey"):
        assert points[("_BC", None, f"patch {name}")]["value"] == points[("_BC", "blue", f"patch {name}")]["value"]


# ----------------------------------------------------------------------------- a document binds every map


def test_a_document_binds_every_map_of_the_set_and_the_variant_binds_the_colour_alone(authoring: Path):
    doc = document_for_set(authoring)
    assert set(doc.values) == {s.parameter for s in synthetic.SPECS if s.variant is None}
    assert len(doc.values) == len(SUFFIXES)
    blue = document_for_set(authoring, synthetic.VARIANT)
    assert set(blue.values) == {"base_color"}
    assert blue.values["base_color"]["texture"] == "T_synthetic_BC_blue.png"


needs_cooked = pytest.mark.skipif(
    not (SET / "cooked" / "T_synthetic_ORM.dds").is_file()
    or (SET / "cooked" / "T_synthetic_ORM.dds").stat().st_size < 1024,
    reason="the committed cooked set is not hydrated (LFS)",
)


@needs_cooked
def test_the_committed_set_resolves_every_parameter_to_its_carrier_or_its_own_file():
    doc = document_for_set(SET)
    textures = {name: v["texture"] for name, v in doc.values.items()}
    rt = runtime_textures(textures, SET)
    assert set(rt) == set(textures)
    by = {name: (r.path.name, r.channels, r.packed) for name, r in rt.items()}
    assert by["ambient_occlusion"] == ("T_synthetic_ORM.dds", "r", True)
    assert by["specular_roughness"] == ("T_synthetic_ORM.dds", "g", True)
    assert by["base_metalness"] == ("T_synthetic_ORM.dds", "b", True)
    assert by["geometry_opacity"] == ("T_synthetic_BC.dds", "a", True), "the cutout rides in the colour alpha"
    assert by["height"][0] == "T_synthetic_H.dds" and rt["height"].format == "R16_UNORM"
    manifest = manifest_for(SET)
    standalone = individual_for(manifest, SET, "T_synthetic_O.png", "geometry_opacity")
    assert standalone is not None and (standalone.path.name, standalone.packed) == ("T_synthetic_O.dds", False)
    assert locate(manifest, SET, "T_synthetic_O.png").packed is True


@needs_cooked
def test_the_committed_png_are_the_generators_output_and_the_cook_is_of_those_png(tmp_path: Path):
    """
    Two links in one chain: the PNGs under content are what the generator writes now (so the host tests' expectations,
    drawn by ``render_map``, are what the committed DDS were cooked from) and the manifest's recorded hash of each is
    the hash of the file on disk (so the cook is of those files, not of an earlier generation).
    """
    again = tmp_path / "synthetic"
    synthetic.generate(again)
    manifest = manifest_for(SET)
    for spec in synthetic.SPECS:
        committed = SET / f"{spec.stem}.png"
        assert committed.read_bytes() == (again / f"{spec.stem}.png").read_bytes(), spec.stem
        assert manifest["inputs"][committed.name] == input_digest(committed), f"{spec.stem}: cooked from other bytes"
