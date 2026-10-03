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


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    tex = tmp_path / "content" / "textures" / "brick"
    _png(tex / "T_brick_BC.png", 64, 64)
    _json(tex / "T_brick_BC.texture.json", {"provenance": PROVENANCE, "resolution": 64})
    _png(tex / "T_brick_N.png", 64, 64)
    _json(tex / "T_brick_N.texture.json", {"provenance": PROVENANCE, "normal_convention": "opengl+y"})
    (tex / "LICENSE.md").write_text("# brick\n", encoding="utf-8")
    mats = tmp_path / "content" / "materials" / "standard" / "rough"
    _json(
        mats / "base.material.json",
        {
            "material_type": "hogshade-standard",
            "material_type_version": 1,
            "title": "Brick",
            "doc": "b",
            "values": {
                "base_color": {"texture": "../../../textures/brick/T_brick_BC.png"},
                "geometry_normal": {"texture": "../../../textures/brick/T_brick_N.png"},
            },
            "provenance": [{"source": "author", "note": "base_color and geometry_normal from the brick set"}],
        },
    )
    return tmp_path


def _messages(root: Path) -> list[str]:
    return [str(f) for f in check_content.run(root)]


def test_the_repository_passes():
    assert check_content.run(ROOT) == []


def test_a_clean_corpus_passes(corpus: Path):
    # the documents' textures climb with `..`, which S1 refuses: bind inside the root instead
    assert [m for m in _messages(corpus) if not m.startswith("content-binding")] == []


def test_a_misnamed_file_and_an_unknown_suffix_are_found(corpus: Path):
    tex = corpus / "content" / "textures" / "brick"
    _png(tex / "brick_BC.png", 8, 8)
    _png(tex / "T_brick_XX.png", 8, 8)
    msgs = _messages(corpus)
    assert "content-name: content/textures/brick/brick_BC.png: not T_<snake_case>_<SUFFIX>[_<variant>]" in msgs
    assert "content-name: content/textures/brick/T_brick_XX.png: suffix '_XX' is not in the tables" in msgs


def test_a_missing_or_malformed_sidecar_is_found(corpus: Path):
    tex = corpus / "content" / "textures" / "brick"
    _png(tex / "T_brick_R.png", 8, 8)
    _png(tex / "T_brick_M.png", 8, 8)
    (tex / "T_brick_M.texture.json").write_text("{nope", encoding="utf-8")
    msgs = _messages(corpus)
    assert "content-sidecar: content/textures/brick/T_brick_R.png: no sidecar T_brick_R.texture.json beside it" in msgs
    assert any(m.startswith("content-sidecar: content/textures/brick/T_brick_M.texture.json: not JSON") for m in msgs)


def test_sidecar_rules_reach_the_check(corpus: Path):
    tex = corpus / "content" / "textures" / "brick"
    _json(tex / "T_brick_N.texture.json", {"provenance": PROVENANCE})
    _json(tex / "T_brick_BC.texture.json", {"provenance": PROVENANCE, "colour_space": "raw", "resolution": 32})
    msgs = _messages(corpus)
    assert any("T_brick_N.texture.json: normal_convention: a normal map states" in m for m in msgs)
    assert any("T_brick_BC.texture.json: colour_space: 'raw' disagrees with the suffix's 'srgb'" in m for m in msgs)
    assert "content-sidecar: content/textures/brick/T_brick_BC.texture.json: resolution 32 but the PNG is 64x64" in msgs


def test_a_cooked_file_that_is_not_dds_is_found(corpus: Path):
    cooked = corpus / "content" / "textures" / "brick" / "cooked"
    _png(cooked / "T_brick_ORM.png", 8, 8)
    assert (
        "content-name: content/textures/brick/cooked/T_brick_ORM.png: a cooked file is dds, or the manifest"
        in _messages(corpus)
    )


def test_a_set_without_a_licence_is_found(corpus: Path):
    (corpus / "content" / "textures" / "brick" / "LICENSE.md").unlink()
    assert any(
        m.startswith("content-licence: content/textures/brick: a set carries LICENSE.md") for m in _messages(corpus)
    )


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
            "material_type": "hogshade-standard",
            "material_type_version": 1,
            "title": "Wall",
            "doc": "w",
            "values": {
                "base_color": {"texture": "tex/T_wall_N.png"},
                "emission_color": {"texture": "tex/T_wall_BC.png"},
                "ambient_occlusion": {"texture": "tex/T_wall_ORM.png"},
                "cavity": {"texture": "tex/T_wall_C.png"},
                "height": {"texture": "tex/wall_H.png"},
            },
            "provenance": [{"source": "author", "note": "every value"}],
        },
    )
    msgs = [m for m in _messages(root) if m.startswith("content-binding")]
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
    assert f"content-binding: {where}:cavity: 'tex/T_wall_C.png' does not exist" in msgs
    assert f"content-binding: {where}:height: binds 'tex/wall_H.png', not a texture of this repository" in msgs
    # the licence rule and the name rule do not reach textures beside a document; they are the textures directory's
    assert not any(m.startswith("content-licence") for m in _messages(root))
