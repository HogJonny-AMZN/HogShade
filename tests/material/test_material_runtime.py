"""
HogShade: a bound texture resolves to its cooked DDS and channel through the manifest (T3): its own file, an
``_ORM`` channel, a carrier's alpha, a standalone height with its format; a set that was not cooked or whose
manifest lacks the map is refused naming the cook command; the Maya binder writes attributes and flags, and a
standard document reaches it through the conversion.
Package: tests/material/test_material_runtime
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pytest

from hogshade.material import MaterialError, bind, convert, from_data, resolve
from hogshade.material.binding import maya_attributes, maya_map_slots
from hogshade.material.generators import host_map
from hogshade.material.runtime import CookedSetError, RuntimeTexture, locate, manifest_for, runtime_textures
from hogshade.texture_cook import cook, png

PROVENANCE = {"origin": "author", "url": "https://example.invalid/t3", "licence": "CC0-1.0", "fetched": "2026-10-04"}


def _write(set_dir: Path, name: str, array: np.ndarray, sidecar: dict | None = None) -> None:
    set_dir.mkdir(parents=True, exist_ok=True)
    png.write_png(set_dir / f"{name}.png", array)
    (set_dir / f"{name}.texture.json").write_text(
        json.dumps({"provenance": PROVENANCE, **(sidecar or {})}), encoding="utf-8"
    )


@pytest.fixture
def family(tmp_path: Path) -> tuple[Path, Path]:
    """A material family directory with a set ``plate`` beside its document: colour with a packed opacity, a
    normal, AO and roughness (into ``_ORM``) with the height in the ORM's alpha, and a metalness."""
    fam = tmp_path / "metal"
    s = fam / "plate"
    s.mkdir(parents=True)
    (s / "LICENSE.md").write_text("# plate\n", encoding="utf-8")
    rng = np.random.default_rng(3)
    h, w = 8, 8
    _write(s, "T_plate_BC", rng.integers(0, 256, (h, w, 3), dtype=np.uint8), {"pack": {"a": "_O"}})
    _write(s, "T_plate_O", rng.integers(0, 256, (h, w, 1), dtype=np.uint8))
    _write(s, "T_plate_N", np.full((h, w, 3), [128, 128, 255], dtype=np.uint8), {"normal_convention": "opengl+y"})
    _write(s, "T_plate_AO", rng.integers(0, 256, (h, w, 1), dtype=np.uint8), {"pack": {"a": "_H"}})
    _write(s, "T_plate_R", rng.integers(0, 256, (h, w, 1), dtype=np.uint8))
    _write(s, "T_plate_M", rng.integers(0, 256, (h, w, 1), dtype=np.uint8))
    _write(s, "T_plate_H", rng.integers(0, 65536, (h, w, 1), dtype=np.uint16))
    return fam, s


BOUND = {
    "base_color": "plate/T_plate_BC.png",
    "geometry_opacity": "plate/T_plate_O.png",
    "geometry_normal": "plate/T_plate_N.png",
    "ambient_occlusion": "plate/T_plate_AO.png",
    "specular_roughness": "plate/T_plate_R.png",
    "base_metalness": "plate/T_plate_M.png",
    "height": "plate/T_plate_H.png",
}


def test_every_home_from_the_manifest(family, caplog):
    fam, s = family
    cook.cook_set(s, compress=False)
    with caplog.at_level(logging.INFO, logger="hogshade.material.runtime"):
        rt = runtime_textures(BOUND, fam)
    assert set(rt) == set(BOUND)
    assert rt["base_color"] == RuntimeTexture(
        "base_color", "T_plate_BC.png", s / "cooked" / "T_plate_BC.dds", "rgb", "R8G8B8A8_UNORM_SRGB", False
    )
    assert (rt["geometry_opacity"].path.name, rt["geometry_opacity"].channels, rt["geometry_opacity"].packed) == (
        "T_plate_BC.dds",
        "a",
        True,
    ), "the opacity rides in the colour's alpha"
    assert (rt["geometry_normal"].path.name, rt["geometry_normal"].channels) == ("T_plate_N.dds", "rg")
    orm = {p: (rt[p].path.name, rt[p].channels) for p in ("ambient_occlusion", "specular_roughness", "base_metalness")}
    assert orm == {
        "ambient_occlusion": ("T_plate_ORM.dds", "r"),
        "specular_roughness": ("T_plate_ORM.dds", "g"),
        "base_metalness": ("T_plate_ORM.dds", "b"),
    }
    assert (rt["height"].path.name, rt["height"].channels, rt["height"].packed) == ("T_plate_ORM.dds", "a", True)
    assert all(r.path.is_file() for r in rt.values())
    assert "runtime set plate: 3 cooked texture(s), compression none" in caplog.text


def test_a_standalone_height_carries_its_format(tmp_path: Path):
    fam = tmp_path / "rough"
    s = fam / "ground"
    s.mkdir(parents=True)
    (s / "LICENSE.md").write_text("# ground\n", encoding="utf-8")
    _write(s, "T_ground_H", np.arange(0, 65536, 1024, dtype=np.uint16).reshape(8, 8)[..., None])
    cook.cook_set(s, compress=False)
    rt = runtime_textures({"height": "ground/T_ground_H.png"}, fam)["height"]
    assert (rt.path.name, rt.channels, rt.format, rt.packed) == ("T_ground_H.dds", "r", "R16_UNORM", False)


def test_an_uncooked_set_and_a_missing_map_are_refused_naming_the_command(family):
    fam, s = family
    with pytest.raises(CookedSetError, match="cook it first .*cook_textures.py cook"):
        runtime_textures({"base_color": "plate/T_plate_BC.png"}, fam)
    cook.cook_set(s, compress=False)
    manifest = manifest_for(s)
    with pytest.raises(CookedSetError, match="has no record of T_plate_E.png"):
        locate(manifest, s, "T_plate_E.png")  # a known-suffix name the cook never saw
    with pytest.raises(CookedSetError, match="not a texture of this repository"):
        locate(manifest, s, "plate_colour.png")
    (s / "cooked" / "manifest.json").write_text("{", encoding="utf-8")
    with pytest.raises(CookedSetError, match="not a readable manifest"):
        manifest_for(s)
    assert issubclass(CookedSetError, MaterialError)


# ------------------------------------------------------------------------------------------ the Maya binder


def _standard(values: dict) -> object:
    return resolve(from_data({"material_type": "hogshade-standard", "material_type_version": 1, "values": values}))


def test_a_standard_document_reaches_maya_through_the_conversion(family):
    fam, s = family
    values = {
        "base_color": {"factor": [0.5, 0.4, 0.3], "texture": "plate/T_plate_BC.png"},
        "base_metalness": {"factor": 1.0, "texture": "plate/T_plate_M.png"},
        "specular_roughness": {"factor": 1.0, "texture": "plate/T_plate_R.png"},
        "geometry_normal": {"texture": "plate/T_plate_N.png"},
        "ambient_occlusion": {"texture": "plate/T_plate_AO.png"},
        "height": {"texture": "plate/T_plate_H.png"},
    }
    res = _standard(values)
    with pytest.raises(MaterialError, match="convert\\(\\) it to legacy v2 first"):
        bind(res, "maya_dx11")
    converted, losses = convert(res, "hogshade-legacy-v2")
    b = bind(resolve(converted), "maya_dx11")
    assert b.host == "maya_dx11" and b.model == "legacy-v2"
    assert b.textures == {
        "base_color": "plate/T_plate_BC.png",
        "metalness": "plate/T_plate_M.png",
        "roughness": "plate/T_plate_R.png",
        "normal_map": "plate/T_plate_N.png",
        "ambient_occlusion_map": "plate/T_plate_AO.png",
        "height_map": "plate/T_plate_H.png",
    }, "the conversion keeps every texture path under the legacy name"
    assert b.fields["materialBaseColor"] == (0.5, 0.4, 0.3)
    assert b.fields["materialMetalness"] == (1.0,) and b.fields["materialRoughness"] == (1.0,)
    flags = {k: v for k, v in b.fields.items() if k.startswith("use") and k.endswith("Map")}
    assert flags["useBaseColorMap"] == (1.0,) and flags["useNormalMap"] == (1.0,) and flags["useHeightMap"] == (1.0,)
    assert flags["useEmissiveMap"] == (0.0,) and flags["useCavityMap"] == (0.0,)
    assert b.fields["NormalCoordsysX"] == (0.0,), "a positive flip component is the shell's choice 0"
    # the slots the job connects, and the runtime files behind them
    slots = maya_map_slots("hogshade-legacy-v2")
    assert slots["normal_map"] == ("baseNormalMap", "useNormalMap") and slots["metalness"] == (
        "metalnessMap",
        "useMetalnessMap",
    )
    cook.cook_set(s, compress=False)
    rt = runtime_textures(b.textures, fam)
    assert rt["metalness"].path.name == "T_plate_ORM.dds" and rt["metalness"].channels == "b"
    assert {u.parameter for u in b.unsupported} == set(), "the Maya map carries every legacy v2 parameter"
    assert all(
        loss.parameter in ("specular_color", "specular_anisotropy", "specular_rotation", "specular_occlusion")
        for loss in losses
    )


def test_an_untextured_document_binds_to_the_values_the_gate_renders():
    res = resolve(from_data({"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": {}}))
    b = bind(res, "maya_dx11")
    assert b.textures == {}
    assert all(v == (0.0,) for k, v in b.fields.items() if k.startswith("use") and k.endswith("Map"))
    defaults = maya_attributes(host_map("maya_dx11"), "hogshade-legacy-v2", {}, {})
    assert set(defaults) == {k for k in b.fields if k.startswith("use") and k.endswith("Map")}, (
        "with no factor nothing but the flags is written; the shell's own defaults stand"
    )


def test_maya_refusals():
    res = resolve(from_data({"material_type": "hogshade-legacy-v2", "material_type_version": 1, "values": {}}))
    with pytest.raises(MaterialError, match="no binder for host"):
        bind(res, "blender")
    lam = resolve(from_data({"material_type": "hogshade-lambert", "material_type_version": 1, "values": {}}))
    with pytest.raises(MaterialError, match="does not carry 'hogshade-lambert'"):
        bind(lam, "maya_dx11")


def test_a_manifest_key_that_is_not_a_dds_under_cooked_is_refused(family):
    _fam, s = family
    cook.cook_set(s, compress=False)
    manifest = manifest_for(s)
    manifest["textures"]["../../outside.dds"] = dict(manifest["textures"]["T_plate_BC.dds"])
    with pytest.raises(CookedSetError, match="is not a .dds file name under cooked/"):
        locate(manifest, s, "T_plate_BC.png")
