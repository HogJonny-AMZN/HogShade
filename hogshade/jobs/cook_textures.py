"""
HogShade: Job_Orchestrator job that cooks one texture set (T2 plan, task 5).
Package: hogshade/jobs/cook_textures

MODULE mode: ``module_path = "hogshade.jobs.cook_textures"``, ``entry_point = "main"``, on the ``hogshade_python``
worker, whose environment is the workspace ``.venv`` (``uv sync --all-extras`` gives it the encoder). Runs without
the orchestrator through ``tools/cook_textures.py``.
"""

from __future__ import annotations

import logging as _logging
from pathlib import Path

_MODULE_NAME = "hogshade.jobs.cook_textures"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

MANIFEST = {
    "name": "hogshade.cook_textures",
    "version": __version__,
    "worker_type": "python",
    "description": (
        "Cook one HogShade texture set: every T_<base>_<SUFFIX>.png or .exr in <set_dir> (with its .texture.json "
        "sidecar and the directory's LICENSE.md) to <set_dir>/cooked/: DDS with mips in linear space, normals as "
        "opengl+y, _AO/_R/_M packed into _ORM, any alpha carrier the sidecars declare, BC7/BC5/BC4 through "
        "ispc_texcomp when installed (uncompressed otherwise, logged), manifest.json (deterministic: parameters and "
        "sha256 of inputs and outputs) and provenance.json (volatile). Optionally the owner's frequency separation "
        "(separate=1) writing the detail map and the macro with the reconstruction error in the manifest. "
        "Deterministic: the same set and tool version give byte-identical outputs."
    ),
    "parameters": {
        "set_dir": {
            "type": "path",
            "required": True,
            "description": "the set directory, e.g. content/materials/standard/rough/brick ('..' in it is refused)",
        },
        "compress": {
            "type": "str",
            "default": "auto",
            "description": "auto (when the encoder is installed), yes (required), no",
        },
        "bc7_profile": {"type": "str", "default": "basic", "description": "ultrafast, veryfast, fast, basic, slow"},
        "height": {
            "type": "str",
            "default": "keep",
            "description": "keep the source precision, or normalise a float height to R16_UNORM",
        },
        "separate": {
            "type": "int",
            "default": 0,
            "description": "1 to also run frequency separation on the colour map",
        },
        "radius": {"type": "float", "default": 16.0, "description": "separation radius; sigma = radius / 2"},
        "macro": {"type": "int", "default": 64, "description": "the macro's longer side in texels"},
    },
    "inputs": ["<set_dir>/T_*_*.png|.exr", "<set_dir>/*.texture.json", "<set_dir>/LICENSE.md"],
    "outputs": [
        "<set_dir>/cooked/T_*_*.dds",
        "<set_dir>/cooked/manifest.json",
        "<set_dir>/cooked/provenance.json",
        "<set_dir>/*.texture.json (derived fields filled)",
    ],
    "returns": "the deterministic manifest dict",
    "spec": "Docs/superpowers/specs/t2-texture-cook.md",
}


def main(parameters: dict) -> dict:
    """Entry point the Python worker calls. ``parameters`` are strings from the job request plus ``_job_*`` context."""
    from hogshade.texture_cook.cook import CookError, cook_set, separate_set
    from hogshade.texture_cook.encoders import default_encoder

    raw = str(parameters["set_dir"])
    set_dir = Path(raw)
    if ".." in set_dir.parts:  # the one check: a climb is refused; an absolute path is the worker's to allow
        raise CookError(f"set_dir {raw!r} climbs with '..'; a job path stays inside the workspace")
    compress_param = str(parameters.get("compress", "auto")).lower()
    compress_values = {"auto": None, "yes": True, "true": True, "1": True, "no": False, "false": False, "0": False}
    if compress_param not in compress_values:
        _LOGGER.warning("compress=%r is not one of %s; treated as auto", compress_param, sorted(compress_values))
    compress = compress_values.get(compress_param, None)
    _LOGGER.info(
        "cook_textures job: %s compress=%s bc7=%s height=%s",
        set_dir,
        compress_param,
        parameters.get("bc7_profile", "basic"),
        parameters.get("height", "keep"),
    )
    encoder = None if compress is False else default_encoder()
    if encoder is None and compress is None:
        compress = False  # already warned once by default_encoder(); neither call asks again
    result = cook_set(
        set_dir,
        compress=compress,
        encoder=encoder,
        bc7_profile=str(parameters.get("bc7_profile", "basic")),
        height_normalise=str(parameters.get("height", "keep")) == "normalise",
    )
    manifest = dict(result.manifest)
    if str(parameters.get("separate", "0")) in ("1", "true", "yes"):
        manifest.setdefault("separation", {})["_BC"] = separate_set(
            set_dir,
            radius=float(parameters.get("radius", 16.0)),
            macro_size=int(parameters.get("macro", 64)),
            compress=compress,
            encoder=encoder,
        )
    _LOGGER.info("cook_textures job done: %s, %d texture(s)", set_dir, len(manifest.get("textures", {})))
    return manifest


if __name__ == "__main__":
    import json

    print(json.dumps(MANIFEST, indent=2))
