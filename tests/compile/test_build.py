"""
HogShade: the core stitches, validates, translates and compiles; the committed artifacts are current.
Package: tests/compile/test_build

Skips, with a reason, when naga is not installed (Docs/verification/toolchain.md). fxc and dxc are
optional inside the build: present on Windows with the SDK, absent elsewhere.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_shaders as bs

needs_naga = pytest.mark.skipif(bs.find_tool("naga") is None, reason="naga-cli not installed")


def test_manifest_lists_existing_modules_in_order() -> None:
    manifest = bs.load_manifest()
    files = [m["file"] for m in manifest["module"]]
    assert files[0] == "constants.wgsl" and files[1] == "interface.wgsl"
    for f in files:
        assert (bs.CORE / f).exists(), f
    assert (bs.CORE / manifest["validate"]["file"]).exists()


def test_naming_rule_holds_for_the_core() -> None:
    manifest = bs.load_manifest()
    bs.stitch(manifest, with_validate=False)  # raises on a violation


def test_naming_rule_rejects_unprefixed_and_duplicate_names() -> None:
    manifest = bs.load_manifest()
    bad = [("a.wgsl", "a_", "fn a_ok() {}\nfn not_prefixed() {}\n"), ("b.wgsl", "b_", "fn a_ok() {}\n")]
    with pytest.raises(bs.BuildError) as e:
        bs.check_names(manifest, bad)
    assert "not_prefixed" in str(e.value) and "already declared" in str(e.value)


def test_exempt_names_are_the_public_interface() -> None:
    manifest = bs.load_manifest()
    exempt = set(manifest["names"]["exempt"])
    interface = (bs.CORE / "interface.wgsl").read_text(encoding="utf-8")
    for name in ("ShadingInputs", "SurfaceInputs", "ShadingResult", "LightSource", "FixedSlots16", "EnvironmentIBL"):
        assert name in exempt and f"struct {name}" in interface


@needs_naga
def test_build_produces_every_artifact_and_they_compile() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="hogshade_test_build_"))
    hashes = bs.build(tmp)
    assert set(hashes) == {"wgsl", "hlsl_sm5", "hlsl_sm6", "glsl"}
    sm5 = (tmp / "maya_dx11" / "generated" / "hogshade_core_sm5.hlsl").read_text(encoding="utf-8")
    assert "register(" not in sm5 and "space" not in sm5, "the core must not declare bindings"
    assert "TextureCube<float4> specular_cube, SamplerState" in sm5, "resources arrive as parameters"
    assert "hogshade_validate" in sm5
    wgsl = (tmp / "wgpu" / "generated" / "hogshade_core.wgsl").read_text(encoding="utf-8")
    assert "hogshade_validate" not in wgsl, "the validation entry point is not part of the core"
    assert "@group" not in wgsl and "@binding" not in wgsl


@needs_naga
def test_committed_artifacts_are_current() -> None:
    stale = bs.check()
    assert not stale, f"run tools/build_shaders.py and commit: {stale}"
