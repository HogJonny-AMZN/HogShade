"""
HogShade: a document built from a set's maps (T3): every map bound under its standard parameter with the
multiplying factors at 1.0, a variant selected, a packed map or two sources refused; it converts and binds for
Maya; the Maya texture check job is registered with its outputs named and refuses a climbing set_dir.
Package: tests/material/test_material_sets
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hogshade.jobs import maya_texture_check as job
from hogshade.material import MaterialError, bind, convert, resolve
from hogshade.material.sets import document_for_set, set_maps
from hogshade.texture_cook import png

PROVENANCE = {"origin": "author", "url": "https://example.invalid/grid", "licence": "CC0-1.0", "fetched": "2026-10-04"}


def _write(set_dir: Path, name: str, channels: int, sidecar: dict | None = None) -> None:
    set_dir.mkdir(parents=True, exist_ok=True)
    png.write_png(set_dir / f"{name}.png", np.full((4, 4, channels), 128, np.uint8))
    (set_dir / f"{name}.texture.json").write_text(json.dumps({"provenance": PROVENANCE, **(sidecar or {})}))


def test_a_document_from_a_set_binds_every_map_and_converts_for_maya(tmp_path: Path):
    s = tmp_path / "grid"
    (s / "LICENSE.md").parent.mkdir()
    (s / "LICENSE.md").write_text("# grid\n")
    for name, ch in (
        ("T_grid_BC", 3),
        ("T_grid_BC_blue", 3),
        ("T_grid_R", 1),
        ("T_grid_M", 1),
        ("T_grid_H", 1),
        ("T_grid_E", 3),
        ("T_grid_C", 1),
    ):
        _write(s, name, ch)
    _write(s, "T_grid_N", 3, {"normal_convention": "opengl+y"})
    (s / "notes.md").write_text("ignored")
    doc = document_for_set(s)
    assert set(doc.values) == {
        "base_color",
        "specular_roughness",
        "base_metalness",
        "height",
        "emission_color",
        "cavity",
        "geometry_normal",
    }, "the unvarianted maps; the blue variant is another document"
    assert doc.values["base_color"] == {"texture": "T_grid_BC.png", "factor": [1.0, 1.0, 1.0]}
    assert doc.values["base_metalness"] == {"texture": "T_grid_M.png", "factor": 1.0}
    assert doc.values["geometry_normal"] == {"texture": "T_grid_N.png"}
    assert doc.root == s and doc.path is None and doc.title.startswith("grid")
    blue = document_for_set(s, variant="blue")
    assert set(blue.values) == {"base_color"} and blue.values["base_color"]["texture"] == "T_grid_BC_blue.png"
    converted, _losses = convert(resolve(doc), "hogshade-legacy-v2")
    b = bind(resolve(converted), "maya_dx11")
    assert b.textures["cavity_map"] == "T_grid_C.png" and b.fields["useCavityMap"] == (1.0,)
    assert b.fields["materialMetalness"] == (1.0,), "the map is seen as authored"


def test_set_maps_refusals(tmp_path: Path):
    with pytest.raises(MaterialError, match="no such set directory"):
        set_maps(tmp_path / "nowhere")
    s = tmp_path / "empty"
    s.mkdir()
    with pytest.raises(MaterialError, match="no authoring map"):
        document_for_set(s)
    _write(s, "T_empty_ORM", 3)
    with pytest.raises(MaterialError, match="packed or derived map"):
        set_maps(s)
    (s / "T_empty_ORM.png").unlink()
    _write(s, "T_empty_R", 1)
    (s / "T_empty_R.exr").write_bytes(b"\x76\x2f\x31\x01")
    with pytest.raises(MaterialError, match="two sources for specular_roughness"):
        set_maps(s)


def test_the_maya_texture_check_job_names_its_outputs():
    assert job.MANIFEST["parameters"]["set_dir"]["required"] is True
    assert any("check.log" in o for o in job.MANIFEST["outputs"]) and any(
        "main.png" in o for o in job.MANIFEST["outputs"]
    )
