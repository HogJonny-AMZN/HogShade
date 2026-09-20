"""
HogShade: Job_Orchestrator job that cooks one IBL environment (E1 plan, task 13).
Package: hogshade/jobs/cook_ibl

MODULE mode: ``module_path = "hogshade.jobs.cook_ibl"``, ``entry_point = "main"``. The worker needs
the HogShade checkout on its import path; the job clone lives wherever BATS puts it, never in this
repository's history.
"""

from __future__ import annotations

import logging as _logging
from pathlib import Path

_MODULE_NAME = "hogshade.jobs.cook_ibl"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

MANIFEST = {
    "name": "hogshade.cook_ibl",
    "version": __version__,
    "worker_type": "python",
    "description": (
        "Cook one HogShade IBL environment. Reads <env_dir>/source_4k.exr (a 4096x2048 linear "
        "equirectangular HDR) and writes <env_dir>/cooked/: specular.dds (GGX-prefiltered RGBA16F cube "
        "with mips, roughness linear in mip), irradiance.dds (cosine-convolved E/pi, 32 cube), "
        "irradiance_sh9.json (radiance SH L2 coefficients), manifest.json (deterministic: parameters, "
        "conventions, sha256 of source and outputs) and provenance.json (volatile: time, machine, git "
        "hash), plus <env_dir>/preview.png. Optionally conditions an 8K master to source_4k.exr first. "
        "Deterministic: same source and tool version give byte-identical outputs and manifest. "
        "Takes about 75 s for a 256 cube at 1024 samples on one CPU core."
    ),
    "parameters": {
        "env_dir": {
            "type": "path",
            "required": True,
            "description": "Environment folder, e.g. content/ibl/studio_small_09",
        },
        "master_exr": {
            "type": "path",
            "required": False,
            "description": "8K equirect EXR to condition into env_dir/source_4k.exr before cooking; omit if the source exists",
        },
        "base": {"type": "int", "default": 256, "description": "Specular cube base size; mips follow"},
        "samples": {"type": "int", "default": 1024, "description": "GGX samples per texel"},
        "irradiance_size": {"type": "int", "default": 32, "description": "Irradiance cube size"},
        "backend": {
            "type": "str",
            "default": "auto",
            "description": "Prefilter implementation: auto (numba if installed), numpy, numba",
        },
    },
    "inputs": ["<env_dir>/source_4k.exr", "(optional) master_exr"],
    "outputs": [
        "<env_dir>/cooked/specular.dds",
        "<env_dir>/cooked/irradiance.dds",
        "<env_dir>/cooked/irradiance_sh9.json",
        "<env_dir>/cooked/manifest.json",
        "<env_dir>/cooked/provenance.json",
        "<env_dir>/preview.png",
    ],
    "returns": "the deterministic manifest dict, plus 'conditioned' when a master was conditioned",
    "spec": "Docs/specs/e1-ibl-cook.md",
}


def main(parameters: dict) -> dict:
    """Entry point the Python worker calls. ``parameters`` are strings from the job request plus ``_job_*`` context."""
    from hogshade.ibl import cook

    env_dir = Path(str(parameters["env_dir"]))
    base = int(parameters.get("base", MANIFEST["parameters"]["base"]["default"]))
    samples = int(parameters.get("samples", MANIFEST["parameters"]["samples"]["default"]))
    irradiance_size = int(parameters.get("irradiance_size", MANIFEST["parameters"]["irradiance_size"]["default"]))
    result: dict = {}
    master = parameters.get("master_exr")
    if master:
        result["conditioned"] = cook.condition(Path(str(master)), env_dir / cook.SOURCE_NAME)
    _LOGGER.info(f"cook_ibl job: {env_dir} base={base} samples={samples} irradiance={irradiance_size}")
    backend = str(parameters.get("backend", "auto"))
    result.update(
        cook.cook_environment(env_dir, base=base, samples=samples, irradiance_size=irradiance_size, backend=backend)
    )
    return result


if __name__ == "__main__":
    import json

    print(json.dumps(MANIFEST, indent=2))
