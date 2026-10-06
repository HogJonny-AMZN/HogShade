"""
HogShade: tools/bats/make_profile.py's profile: HogShade's own worker types, each with its environment file, and the
canon's `marmoset` type enabled as `hogshade_marmoset`, defined like the others (T4's baked-maps tier).
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


def test_marmoset_is_defined_like_the_other_hogshade_workers(make_profile) -> None:
    profile = make_profile.build_profile(_canon())
    workers = profile["worker_types"]
    assert set(workers) == {
        "hogshade_maya",
        "hogshade_maya_gui",
        "hogshade_python",
        "hogshade_blender",
        "hogshade_marmoset",
    }
    assert workers["hogshade_marmoset"]["pool_sizes"] == {"headless": 1}, "the canon ships it at 0"
    assert workers["hogshade_marmoset"]["display_name"].startswith("HogShade")
    description = workers["hogshade_marmoset"]["description"]
    assert "inert" not in description.lower() and "pool 0" not in description, "the canon's text contradicts the pool"
    for name in ("hogshade_maya", "hogshade_python", "hogshade_blender", "hogshade_marmoset"):
        assert workers[name]["environment_json_path"].endswith(f"{name}_env.json"), name


def test_a_canon_without_marmoset_leaves_the_profile_as_it_was(make_profile) -> None:
    profile = make_profile.build_profile(_canon(with_marmoset=False))
    assert "hogshade_marmoset" not in profile["worker_types"] and "marmoset" not in profile["worker_types"]
    assert profile["gpu"] == {"enable_vram_admission": False} and "package_paths" not in profile


def test_every_worker_in_the_committed_profile_has_a_committed_environment_file() -> None:
    """The worker process needs the orchestrator host, port and PYTHONPATH; a renamed type gets them from this file."""
    import json

    bats = ROOT / "tools" / "bats"
    committed = json.loads((bats / "orchestrator_config_hogshade.json").read_text(encoding="utf-8"))
    assert "hogshade_marmoset" in committed["worker_types"] and "marmoset" not in committed["worker_types"]
    marmoset = committed["worker_types"]["hogshade_marmoset"]
    assert marmoset["pool_sizes"] == {"headless": 1}
    assert "inert" not in marmoset["description"].lower()
    for name, worker in committed["worker_types"].items():
        env_path = Path(worker["environment_json_path"])
        assert env_path.name.startswith("hogshade_") and env_path.name.endswith("_env.json"), name
        assert (bats / env_path.name).is_file(), f"{name}: {env_path.name} is not committed beside the profile"
        env = json.loads((bats / env_path.name).read_text(encoding="utf-8"))["environment"]
        assert env["variables"]["HOGSHADE_ROOT"] and env["PYTHONPATH"]["prepend"], f"{name}: no HogShade or PYTHONPATH"
    marmoset_env = json.loads((bats / "hogshade_marmoset_env.json").read_text(encoding="utf-8"))["environment"]
    python_env = json.loads((bats / "hogshade_python_env.json").read_text(encoding="utf-8"))["environment"]
    assert marmoset_env == python_env, "the venv-Python worker types share one environment"
    assert marmoset_env["variables"]["ORCHESTRATOR_PORT"], "the worker reaches the orchestrator through this"


def _canon_dir(tmp_path: Path, with_marmoset: bool) -> Path:
    """A throwaway canon config directory: the orchestrator config, the base environment and the three DCC ones."""
    import json

    config = tmp_path / "config"
    config.mkdir()
    canon = _canon(with_marmoset)
    for worker in canon["worker_types"].values():
        worker.pop("environment", None)
    (config / "orchestrator_config.json").write_text(json.dumps(canon), encoding="utf-8")
    env = {"environment": {"variables": {"X": "1"}, "PATH": {}, "PYTHONPATH": {"prepend": ["${WORKSPACE_ROOT}"]}}}
    for name in ("base", "maya", "python", "blender"):
        (config / f"{name}_env.json").write_text(json.dumps(env), encoding="utf-8")
    return config


def test_the_marmoset_environment_says_it_came_from_the_python_one_and_goes_when_the_canon_loses_the_type(
    make_profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(make_profile, "HERE", out)
    monkeypatch.setattr(make_profile, "PROFILE_OUT", out / "profile.json")

    def run(with_marmoset: bool) -> None:
        base = tmp_path / f"canon_{with_marmoset}"
        base.mkdir(exist_ok=True)
        config = _canon_dir(base, with_marmoset)
        monkeypatch.setattr(make_profile, "CONFIG_DIR", config)
        monkeypatch.setattr(make_profile, "CANON", config / "orchestrator_config.json")
        monkeypatch.setattr(make_profile, "BASE_ENV", config / "base_env.json")
        assert make_profile.main() == 0

    run(with_marmoset=True)
    meta = json.loads((out / "hogshade_marmoset_env.json").read_text(encoding="utf-8"))
    assert "base and python environments" in meta["description"], "it was built from the Python environment"
    assert "marmoset" in meta["name"]
    run(with_marmoset=False)
    assert not (out / "hogshade_marmoset_env.json").exists(), "a stale environment is removed"
    assert (out / "hogshade_python_env.json").exists(), "the other environments stay"
