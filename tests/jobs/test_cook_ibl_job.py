"""
HogShade: the cook_ibl job runs the way the orchestrator's Python worker would call it (E1 plan, task 13).
Package: tests/jobs/test_cook_ibl_job
"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np

from hogshade import jobs
from hogshade.ibl.cubemap import equirect_texel_directions
from hogshade.ibl.imageio import write_exr_rgb


def test_library_manifest_lists_the_job() -> None:
    entries = jobs.manifest()
    assert [e["name"] for e in entries] == ["hogshade.cook_ibl"]
    e = entries[0]
    assert e["module_path"] == "hogshade.jobs.cook_ibl" and e["entry_point"] == "main"
    assert e["worker_type"] == "python" and "env_dir" in e["parameters"]
    assert len(e["description"]) > 200  # written for an agent, not a one-liner


def test_job_runs_like_the_worker_calls_it(tmp_path: Path) -> None:
    env = tmp_path / "env"
    env.mkdir()
    d = equirect_texel_directions(64, 32)
    write_exr_rgb(env / "source_4k.exr", (0.5 + 0.5 * d[..., 1:2]).astype(np.float32).repeat(3, axis=-1))
    module = importlib.import_module("hogshade.jobs.cook_ibl")
    entry = getattr(module, "main")  # noqa: B009 - mirrors the worker
    params = {
        "env_dir": str(env),
        "base": "8",
        "samples": "16",
        "irradiance_size": "4",
        "_job_id": "t",
        "_job_log_file": "",
    }
    result = entry(params)
    assert isinstance(result, dict) and result["specular"]["base"] == 8
    for name in ("specular.dds", "irradiance.dds", "irradiance_sh9.json", "manifest.json", "provenance.json"):
        assert (env / "cooked" / name).exists(), name
    assert (env / "preview.png").exists()
