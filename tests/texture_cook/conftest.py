"""
HogShade: shared builders for the texture cook tests: a scratch authoring set with sidecars and a licence.
Package: tests/texture_cook/conftest
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hogshade.texture_cook import png

PROVENANCE = {"origin": "author", "url": "https://example.invalid/brick", "licence": "CC0-1.0", "fetched": "2026-10-04"}


def write_texture(
    set_dir: Path, name: str, array: np.ndarray, sidecar: dict | None = None, filter_type: int = 0
) -> Path:
    set_dir.mkdir(parents=True, exist_ok=True)
    path = set_dir / f"{name}.png"
    png.write_png(path, array, filter_type)
    (set_dir / f"{name}.texture.json").write_text(
        json.dumps({"provenance": PROVENANCE, **(sidecar or {})}), encoding="utf-8"
    )
    return path


@pytest.fixture
def texture_writer():
    """The ``write_texture`` helper, for tests that build their own sets."""
    return write_texture


@pytest.fixture
def brick(tmp_path: Path) -> Path:
    """A 24x16 set: colour with a packed opacity, a DirectX normal, AO with a packed height, roughness, height."""
    rng = np.random.default_rng(7)
    s = tmp_path / "brick"
    s.mkdir()
    (s / "LICENSE.md").write_text("# brick: a scratch set for the tests\n", encoding="utf-8")
    h, w = 16, 24
    write_texture(s, "T_brick_BC", rng.integers(0, 256, (h, w, 3), dtype=np.uint8), {"pack": {"a": "_O"}})
    write_texture(s, "T_brick_O", rng.integers(0, 256, (h, w, 1), dtype=np.uint8))
    n = np.full((h, w, 3), [128, 64, 255], dtype=np.uint8)  # a tilted normal, so the flip is visible
    write_texture(s, "T_brick_N", n, {"normal_convention": "directx-y"})
    write_texture(s, "T_brick_AO", rng.integers(0, 256, (h, w, 1), dtype=np.uint8), {"pack": {"a": "_H"}})
    write_texture(s, "T_brick_R", rng.integers(0, 256, (h, w, 1), dtype=np.uint8))
    write_texture(s, "T_brick_H", rng.integers(0, 65536, (h, w, 1), dtype=np.uint16))
    return s
