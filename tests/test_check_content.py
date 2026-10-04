"""
HogShade: tests for tools/check_content.py on a scratch corpus and on the repository.
Package: tests/test_check_content
"""

from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_content

PROVENANCE = {
    "origin": "polyhaven",
    "url": "https://polyhaven.com/a/brick",
    "licence": "CC0-1.0",
    "fetched": "2026-10-03",
}
STANDARD_DOC = {"material_type": "hogshade-standard", "material_type_version": 1}


def _png(path: Path, width: int, height: int) -> None:
    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


def _json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _licence(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "LICENSE.md").write_text("# a set\n", encoding="utf-8")


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A set beside the material that binds it (the standard's placement), and a calibration set no document binds."""
    mats = tmp_path / "content" / "materials" / "standard" / "rough"
    tex = mats / "brick"
    _png(tex / "T_brick_BC.png", 64, 64)
    _json(tex / "T_brick_BC.texture.json", {"provenance": PROVENANCE, "resolution": 64})
    _png(tex / "T_brick_N.png", 64, 64)
    _json(tex / "T_brick_N.texture.json", {"provenance": PROVENANCE, "normal_convention": "opengl+y"})
    _licence(tex)
    _json(mats / "base.material.json", {**STANDARD_DOC, "title": "Rough", "doc": "r", "values": {}})
    _json(
        mats / "brick.material.json",
        {
            **STANDARD_DOC,
            "parent": "base.material.json",
            "title": "Brick",
            "doc": "b",
            "values": {
                "base_color": {"texture": "brick/T_brick_BC.png"},
                "geometry_normal": {"texture": "brick/T_brick_N.png"},
            },
            "provenance": [{"source": "author", "note": "base_color and geometry_normal from the brick set"}],
        },
    )
    cal = tmp_path / "content" / "textures" / "grid"
    _png(cal / "T_grid_BC.png", 16, 16)
    _json(cal / "T_grid_BC.texture.json", {"provenance": PROVENANCE})
    _licence(cal)
    return tmp_path


def _messages(root: Path) -> list[str]:
    return [str(f) for f in check_content.run(root)]


def test_the_repository_passes():
    assert check_content.run(ROOT) == []


def test_a_clean_corpus_passes(corpus: Path):
    assert _messages(corpus) == []
    assert len(check_content.source_textures(corpus)) == 3


def test_a_checkout_under_a_directory_named_cooked_is_not_cooked(tmp_path: Path):
    root = tmp_path / "cooked" / "repo"
    tex = root / "content" / "textures" / "grid"
    _png(tex / "T_grid_BC.png", 8, 8)
    _json(tex / "T_grid_BC.texture.json", {"provenance": PROVENANCE})
    _licence(tex)
    assert _messages(root) == [] and len(check_content.source_textures(root)) == 1


def test_a_misnamed_file_and_an_unknown_suffix_are_found(corpus: Path):
    tex = corpus / "content" / "textures" / "grid"
    _png(tex / "grid_BC.png", 8, 8)
    _png(tex / "T_grid_XX.png", 8, 8)
    msgs = _messages(corpus)
    assert "content-name: content/textures/grid/grid_BC.png: not T_<snake_case>_<SUFFIX>[_<variant>]" in msgs
    assert "content-name: content/textures/grid/T_grid_XX.png: suffix '_XX' is not in the tables" in msgs


def test_a_jpeg_a_webp_and_an_upper_case_png_are_findings(corpus: Path):
    tex = corpus / "content" / "textures" / "grid"
    (tex / "T_grid_R.jpg").write_bytes(b"\xff\xd8\xff")
    (tex / "T_grid_M.webp").write_bytes(b"RIFF")
    _png(tex / "T_grid_AO.PNG", 8, 8)
    _json(tex / "T_grid_AO.texture.json", {"provenance": PROVENANCE})
    msgs = _messages(corpus)
    assert any(
        m.startswith("content-name: content/textures/grid/T_grid_R.jpg: '.jpg' is not an authoring format")
        for m in msgs
    )
    assert any(
        m.startswith("content-name: content/textures/grid/T_grid_M.webp: '.webp' is not an authoring format")
        for m in msgs
    )
    assert (
        "content-name: content/textures/grid/T_grid_AO.PNG: extension '.PNG' is upper-case; "
        "LFS patterns are case-sensitive" in msgs
    )
    assert not any("T_grid_AO.PNG" in m and m.startswith("content-sidecar") for m in msgs), "not a source texture"


def test_a_packed_or_derived_map_outside_cooked_is_a_finding(corpus: Path):
    tex = corpus / "content" / "textures" / "grid"
    _png(tex / "T_grid_ORM.png", 8, 8)
    _json(tex / "T_grid_ORM.texture.json", {"provenance": PROVENANCE})
    msgs = _messages(corpus)
    assert (
        "content-name: content/textures/grid/T_grid_ORM.png: _ORM is the cook's output; "
        "it lives under cooked/, never authored" in msgs
    )
    assert len(check_content.source_textures(corpus)) == 3, "not counted as a source"


def test_a_sidecar_that_is_not_utf8_or_not_an_object_is_a_finding(corpus: Path):
    tex = corpus / "content" / "textures" / "grid"
    _png(tex / "T_grid_R.png", 8, 8)
    (tex / "T_grid_R.texture.json").write_bytes(b"\xff\xfe{}")
    _png(tex / "T_grid_M.png", 8, 8)
    (tex / "T_grid_M.texture.json").write_text("[]", encoding="utf-8")
    msgs = _messages(corpus)
    assert any(m.startswith("content-sidecar: content/textures/grid/T_grid_R.texture.json: not UTF-8") for m in msgs)
    assert "content-sidecar: content/textures/grid/T_grid_M.texture.json: a sidecar is a JSON object, not list" in msgs


def test_a_png_over_the_budget_is_a_finding(corpus: Path):
    tex = corpus / "content" / "textures" / "grid"
    _png(tex / "T_grid_H.png", 4096, 4)
    _json(tex / "T_grid_H.texture.json", {"provenance": PROVENANCE})
    assert (
        "content-sidecar: content/textures/grid/T_grid_H.png: 4096x4 exceeds the repository budget of 2048"
        in _messages(corpus)
    )


def test_a_missing_or_malformed_sidecar_is_found(corpus: Path):
    tex = corpus / "content" / "textures" / "grid"
    _png(tex / "T_grid_R.png", 8, 8)
    _png(tex / "T_grid_M.png", 8, 8)
    (tex / "T_grid_M.texture.json").write_text("{nope", encoding="utf-8")
    msgs = _messages(corpus)
    assert "content-sidecar: content/textures/grid/T_grid_R.png: no sidecar T_grid_R.texture.json beside it" in msgs
    assert any(m.startswith("content-sidecar: content/textures/grid/T_grid_M.texture.json: not JSON") for m in msgs)


def test_sidecar_rules_reach_the_check(corpus: Path):
    tex = corpus / "content" / "materials" / "standard" / "rough" / "brick"
    _json(tex / "T_brick_N.texture.json", {"provenance": PROVENANCE})
    _json(tex / "T_brick_BC.texture.json", {"provenance": PROVENANCE, "colour_space": "raw", "resolution": 32})
    msgs = _messages(corpus)
    where = "content/materials/standard/rough/brick/T_brick_BC.texture.json"
    assert any("T_brick_N.texture.json: normal_convention: a normal map states" in m for m in msgs)
    assert any(f"{where}: colour_space: 'raw' disagrees with the suffix's 'srgb'" in m for m in msgs)
    assert f"content-sidecar: {where}: resolution 32 but the PNG is 64x64" in msgs
    assert any(m.startswith("content-binding:") and "sidecar colour space 'raw'" in m for m in msgs), "the binding too"


def test_an_lfs_pointer_is_logged_not_judged(corpus: Path, caplog: pytest.LogCaptureFixture):
    tex = corpus / "content" / "textures" / "grid"
    (tex / "T_grid_BC.png").write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:0\nsize 1\n")
    _json(tex / "T_grid_BC.texture.json", {"provenance": PROVENANCE, "resolution": 2048})
    with caplog.at_level("INFO", logger=check_content._MODULE_NAME):
        assert _messages(corpus) == []
    assert "resolution of content/textures/grid/T_grid_BC.png unverified: the PNG is an LFS pointer" in caplog.text


def test_a_cooked_file_that_is_not_dds_is_found(corpus: Path):
    cooked = corpus / "content" / "textures" / "grid" / "cooked"
    _png(cooked / "T_grid_ORM.png", 8, 8)
    (cooked / "T_grid_ORM.dds").write_bytes(b"DDS ")
    (cooked / "manifest.json").write_text("{}", encoding="utf-8")
    expected = (
        "content-name: content/textures/grid/cooked/T_grid_ORM.png: a cooked file is dds, or one of "
        "('manifest.json', 'provenance.json')"
    )
    messages = _messages(corpus)
    assert messages[0] == expected
    assert messages[1].startswith("content-runtime: content/textures/grid/cooked/manifest.json: ") and (
        "carries no textures record" in messages[1]
    ), "an empty manifest is a runtime finding too (T3)"
    assert len(messages) == 2


def test_a_directory_without_a_licence_is_found(corpus: Path):
    (corpus / "content" / "textures" / "grid" / "LICENSE.md").unlink()
    assert any(
        m.startswith("content-licence: content/textures/grid: a directory of source textures carries LICENSE.md")
        for m in _messages(corpus)
    )


def test_a_document_of_another_type_is_logged_not_held_to_the_table(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    mats = tmp_path / "content" / "materials" / "legacy-v2"
    tex = mats / "wall"
    _png(tex / "T_wall_R.png", 8, 8)
    _json(tex / "T_wall_R.texture.json", {"provenance": PROVENANCE})
    _licence(tex)
    _json(
        mats / "wall.material.json",
        {
            "material_type": "hogshade-legacy-v2",
            "material_type_version": 1,
            "values": {"roughness": {"texture": "wall/T_wall_R.png"}},
        },
    )
    with caplog.at_level("INFO", logger=check_content._MODULE_NAME):
        assert _messages(tmp_path) == []
    assert "is hogshade-legacy-v2, not hogshade-standard: its 1 bound texture(s) are not held" in caplog.text


def test_bindings_are_held_to_the_suffix_and_the_schema(tmp_path: Path):
    root = tmp_path
    mats = root / "content" / "materials" / "standard" / "rough"
    tex = mats / "tex"
    _png(tex / "T_wall_N.png", 8, 8)
    _json(tex / "T_wall_N.texture.json", {"provenance": PROVENANCE, "normal_convention": "opengl+y"})
    _png(tex / "T_wall_BC.png", 8, 8)
    _json(
        tex / "T_wall_BC.texture.json",
        {"provenance": PROVENANCE, "colour_space": "raw", "override_reason": "linear source"},
    )
    _png(tex / "T_wall_ORM.png", 8, 8)
    _json(tex / "T_wall_ORM.texture.json", {"provenance": PROVENANCE})
    _json(
        mats / "base.material.json",
        {
            **STANDARD_DOC,
            "title": "Wall",
            "doc": "w",
            "values": {
                "base_color": {"texture": "tex/T_wall_N.png"},
                "emission_color": {"texture": "tex/T_wall_BC.png"},
                "ambient_occlusion": {"texture": "tex/T_wall_ORM.png"},
                "cavity": {"texture": "tex/T_wall_C.webp"},
                "height": {"texture": "tex/wall_H.png"},
            },
            "provenance": [{"source": "author", "note": "every value"}],
        },
    )
    all_msgs = _messages(root)
    msgs = [m for m in all_msgs if m.startswith("content-binding")]
    where = "content/materials/standard/rough/base.material.json"
    assert f"content-binding: {where}:base_color: binds a _N map, which is 'geometry_normal', not 'base_color'" in msgs
    assert (
        f"content-binding: {where}:emission_color: binds a _BC map, which is 'base_color', not 'emission_color'" in msgs
    )
    assert (
        f"content-binding: {where}:emission_color: sidecar colour space 'raw' but 'emission_color' is 'srgb' "
        "in the schema"
    ) in msgs
    assert (
        f"content-binding: {where}:ambient_occlusion: binds a _ORM map, which a document never binds directly" in msgs
    )
    assert f"content-binding: {where}:cavity: binds 'tex/T_wall_C.webp', not an authoring format" in msgs
    assert f"content-binding: {where}:cavity: 'tex/T_wall_C.webp' does not exist" in msgs
    assert f"content-binding: {where}:height: binds 'tex/wall_H.png', not a texture of this repository" in msgs
    # a set beside a document is a content root too: the licence rule reaches it
    assert any(m.startswith("content-licence: content/materials/standard/rough/tex:") for m in all_msgs)


# ----------------------------------------------------------------------------------------- content-runtime (T3)


def _cook(set_dir: Path):
    from hogshade.texture_cook.cook import cook_set

    return cook_set(set_dir, compress=False)


def test_a_cooked_set_passes_and_a_missing_record_a_changed_input_and_an_empty_manifest_are_found(corpus: Path):
    tex = corpus / "content" / "materials" / "standard" / "rough" / "brick"
    _cook(tex)
    assert _messages(corpus) == []
    manifest = tex / "cooked" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data["textures"]["T_brick_N.dds"]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _messages(corpus) == [
        (
            "content-runtime: content/materials/standard/rough/brick/cooked/manifest.json: no record of T_brick_N.png; "
            "cook the set again"
        )
    ]
    _cook(tex)
    _png(tex / "T_brick_BC.png", 32, 32)  # the authoring file changed after the cook
    _json(tex / "T_brick_BC.texture.json", {"provenance": PROVENANCE, "resolution": 32})
    found = _messages(corpus)
    assert any("T_brick_BC.png changed since the cook" in m for m in found), found
    assert any("T_brick_BC.texture.json changed since the cook" in m for m in found), found
    manifest.write_text("{", encoding="utf-8")
    assert any("not a readable manifest" in m for m in _messages(corpus))


def test_a_set_without_a_cooked_directory_is_not_held_and_a_pointer_is_logged(corpus: Path, caplog):
    tex = corpus / "content" / "textures" / "grid"
    assert _messages(corpus) == [], "no cooked/ yet: nothing to hold the set to"
    _cook(tex)
    (tex / "T_grid_BC.png").write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:0\nsize 1\n")
    with caplog.at_level("INFO", logger=check_content._MODULE_NAME):
        assert _messages(corpus) == []
    assert "content/textures/grid: 1 input(s) are LFS pointers on this checkout" in caplog.text
