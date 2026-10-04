"""
HogShade: Job_Orchestrator job that renders one cooked texture set on the HogShade shell in Maya (T3).
Package: hogshade/jobs/maya_texture_check

MODULE mode on the ``hogshade_maya_gui`` worker (main thread): the parameters become the environment
``tools/maya/texture_check.py`` reads, the script runs in the resident GUI Maya, and the result names the
capture directory, the log, the picture and what Maya decoded per texture. Runs without the orchestrator
through ``tools/maya/texture_check.mel`` in a GUI Maya.
"""

from __future__ import annotations

import logging as _logging
import os
import sys
from pathlib import Path

_MODULE_NAME = "hogshade.jobs.maya_texture_check"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

ROOT = Path(__file__).resolve().parents[2]

MANIFEST = {
    "name": "hogshade.maya_texture_check",
    "version": __version__,
    "worker_type": "hogshade_maya_gui",
    "execution_mode": "GUI",
    "execute_on_main_thread": True,
    "description": (
        "Render one cooked texture set on the HogShade shell in the resident GUI Maya: the set's document (or one "
        "built from its maps) converted to legacy v2 and bound for the Maya host, every map's cooked DDS connected "
        "to its slot through the set's manifest, the IBL environment and a light, a playblast of the main view and "
        "the texture debug views into verification/maya-2026/<check>/<variant>/ with check.log recording the format "
        "written and the size Maya decoded per texture (the probe for block-compressed DDS), and the menu bar."
    ),
    "parameters": {
        "set_dir": {
            "type": "path",
            "required": True,
            "description": "the set directory, e.g. content/textures/grid ('..' in it is refused)",
        },
        "document": {
            "type": "path",
            "default": "",
            "description": "a standard .material.json beside the set; empty builds one from the set's maps",
        },
        "env": {"type": "str", "default": "studio_small_09", "description": "content/ibl/<env>"},
        "fx": {"type": "path", "default": "", "description": "override the shell (hosts/maya_dx11/hogshade.fx)"},
        "debug_modes": {"type": "str", "default": "1,7,8,9,11", "description": "g_DebugMode captures"},
        "set": {"type": "str", "default": "", "description": "attr=value,... overrides"},
        "check": {"type": "str", "default": "textures", "description": "verification/maya-2026/<check>/"},
        "variant": {"type": "str", "default": "<set name>", "description": "sub-directory under the check"},
    },
    "inputs": [
        "<set_dir>/cooked/*.dds and manifest.json",
        "<document> or <set_dir>/T_*.png (names only)",
        "content/ibl/<env>/cooked/*.dds",
        "content/ibl/brdf_lut.dds",
        "hosts/maya_dx11/hogshade.fx",
    ],
    "outputs": [
        "verification/maya-2026/<check>/<variant>/check.log",
        "verification/maya-2026/<check>/<variant>/main.png",
        "verification/maya-2026/<check>/<variant>/debug-NN.png",
    ],
    "returns": "ok, dir, log, png, decoded (parameter -> format and loaded), techniques",
    "spec": "Docs/superpowers/specs/t3-first-texture-set.md",
}

#: The parameters that name a path; each is screened for a climb before it reaches the check.
PATH_PARAMETERS = tuple(k for k, v in MANIFEST["parameters"].items() if v["type"] == "path")

_ENV_KEYS = {
    "set_dir": "HOGSHADE_SET_DIR",
    "document": "HOGSHADE_DOCUMENT",
    "env": "HOGSHADE_ENV",
    "fx": "HOGSHADE_FX",
    "debug_modes": "HOGSHADE_DEBUG_MODES",
    "set": "HOGSHADE_SET",
    "check": "HOGSHADE_CHECK",
    "variant": "HOGSHADE_VARIANT",
}


def main(parameters: dict) -> dict:
    """Entry point the Maya GUI worker calls. Parameters become the environment the check script reads."""
    raw = str(parameters.get("set_dir", ""))
    if not raw:
        raise ValueError("set_dir is required")
    for key in PATH_PARAMETERS:  # every path-typed parameter: a climb is refused (failure modes 9)
        value = str(parameters.get(key) or "")
        if ".." in Path(value).parts:
            raise ValueError(f"{key} {value!r} climbs with '..'; a job path stays inside the workspace")
    os.environ["HOGSHADE_ROOT"] = str(ROOT).replace("\\", "/")
    os.environ["HOGSHADE_AS_JOB"] = "1"
    for key, var in _ENV_KEYS.items():
        value = parameters.get(key)
        if value:
            os.environ[var] = str(value)
        elif var in os.environ and key != "set_dir":
            del os.environ[var]  # a resident worker: no leak from an earlier job (the board's environment row)
    tools_maya = ROOT / "tools" / "maya"
    if str(tools_maya) not in sys.path:
        sys.path.insert(0, str(tools_maya))
    import importlib

    # a resident worker keeps the library of the previous job imported: drop it, so the check sees this checkout
    for name in [n for n in sys.modules if n == "hogshade.material" or n.startswith("hogshade.material.")]:
        del sys.modules[name]
    for name in ("_session", "texture_check"):
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    import texture_check  # a tools/maya script module, on sys.path above

    _LOGGER.info(f"maya_texture_check job: set={texture_check.SET_DIR} document={texture_check.DOCUMENT or '<built>'}")
    result = texture_check.run_check(quit_after=False)
    _LOGGER.info(
        f"maya_texture_check job done: ok={result.get('ok')}, decoded {result.get('decoded')}, log {result.get('log')}"
    )
    return result


if __name__ == "__main__":
    import json

    print(json.dumps(MANIFEST, indent=2))
