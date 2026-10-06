"""
HogShade: tools/bats/make_profile.py's profile: HogShade's own worker types, each with its environment file, and the
canon's `marmoset` type enabled under its own name with no environment file (T4's baked-maps tier).
Package: tests/tools/test_make_profile
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def make_profile(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools" / "bats"))
    sys.modules.pop("make_profile", None)
    return importlib.import_module("make_profile")


def _canon(with_marmoset: bool = True) -> dict:
    worker = {"display_name": "x", "description": "d", "enabled": True, "pool_sizes": {"headless": 0}}
    canon = {
        "dcc_paths": {
            "maya": {"mayapy": "C:/m/mayapy.exe", "executable": "C:/m/maya.exe"},
            "blender": {"executable": "C:/b/blender.exe"},
        },
        "worker_types": {k: dict(worker, environment={"variables": {}}) for k in ("maya", "python", "blender")},
        "package_paths": ["x"],
        "gpu": {"enable_vram_admission": False},
    }
    if with_marmoset:
        canon["worker_types"]["marmoset"] = dict(
            worker, display_name="Marmoset Toolbag 4", description="Ships inert (pool 0): a sidecar sets it to 1."
        )
    return canon


def test_marmoset_is_enabled_under_its_own_name_with_no_environment_file(make_profile) -> None:
    profile = make_profile.build_profile(_canon())
    workers = profile["worker_types"]
    assert set(workers) == {"hogshade_maya", "hogshade_maya_gui", "hogshade_python", "hogshade_blender", "marmoset"}
    assert workers["marmoset"]["pool_sizes"] == {"headless": 1}, "the canon ships it at 0"
    assert "environment_json_path" not in workers["marmoset"], "its jobs run in Toolbag's Python, not ours"
    description = workers["marmoset"]["description"]
    assert "inert" not in description.lower() and "pool 0" not in description, "the canon's text contradicts the pool"
    for name in ("hogshade_maya", "hogshade_python", "hogshade_blender"):
        assert workers[name]["environment_json_path"].endswith(f"{name}_env.json"), name


def test_a_canon_without_marmoset_leaves_the_profile_as_it_was(make_profile) -> None:
    profile = make_profile.build_profile(_canon(with_marmoset=False))
    assert "marmoset" not in profile["worker_types"]
    assert profile["gpu"] == {"enable_vram_admission": False} and "package_paths" not in profile


def test_the_committed_profile_names_the_marmoset_type_when_the_canon_has_it() -> None:
    import json

    committed = json.loads((ROOT / "tools" / "bats" / "orchestrator_config_hogshade.json").read_text(encoding="utf-8"))
    assert "marmoset" in committed["worker_types"]
    assert committed["worker_types"]["marmoset"]["pool_sizes"] == {"headless": 1}
    assert "inert" not in committed["worker_types"]["marmoset"]["description"].lower()
