"""
HogShade: Job_Orchestrator job that runs the Maya IBL check inside a resident GUI Maya (phase 2 plan, task 17).
Package: hogshade/jobs/maya_ibl_check

MODULE mode: ``module_path = "hogshade.jobs.maya_ibl_check"``, ``entry_point = "main"``, worker type
``hogshade_maya_gui``, execution mode GUI, on the main thread (the playblast needs the viewport). The worker's
Maya must run with ``MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11`` (HogShade's orchestrator profile
sets it) or the dx11Shader effect will not load. The check itself is ``tools/maya/ibl_check.py``,
shared with the standalone ``.mel`` launcher; this module only adapts it to a job.
"""

from __future__ import annotations

import logging as _logging
import os
import sys
from pathlib import Path

_MODULE_NAME = "hogshade.jobs.maya_ibl_check"
__version__ = "0.1.0"
__updated__ = "2026-09-26"
_LOGGER = _logging.getLogger(_MODULE_NAME)

ROOT = Path(__file__).resolve().parents[2]

MANIFEST = {
    "name": "hogshade.maya_ibl_check",
    "version": __version__,
    "worker_type": "hogshade_maya_gui",
    "execution_mode": "GUI",
    "execute_on_main_thread": True,
    "description": (
        "Load hosts/maya_dx11/hogshade.fx on a sphere in the resident GUI Maya, bind the cooked IBL cubes "
        "and the BRDF LUT from content/ibl, bind one directional light into slot 0, playblast the main view "
        "and the requested debug views into Docs/verification/maya-2026/<check>/<env>/, and write an incremental log with the "
        "technique list, the texture decode sizes and Maya's Script Editor history (where dx11Shader reports "
        "effect compile errors). Returns the log path, the PNG paths and whether the gate passed."
    ),
    "parameters": {
        "env": {"type": "str", "default": "studio_small_09", "description": "content/ibl/<env> to bind"},
        "fx": {"type": "path", "required": False, "description": "effect file; default hosts/maya_dx11/hogshade.fx"},
        "debug_modes": {"type": "str", "default": "18,27,28", "description": "g_DebugMode values to capture"},
        "set": {"type": "str", "required": False, "description": "attr=value,... overrides for the shader"},
        "check": {
            "type": "str",
            "default": "ibl-check",
            "description": "output directory name under Docs/verification/maya-2026/",
        },
    },
    "inputs": ["hosts/maya_dx11/hogshade.fx", "content/ibl/<env>/cooked/*.dds", "content/ibl/brdf_lut.dds"],
    "outputs": [
        "Docs/verification/maya-2026/<check>/<env>/check.log",
        ".../main.png",
        ".../debug-NN.png",
        ".../maya-history.log",
    ],
    "returns": "dict: ok, dir, log, png, techniques",
    "spec": "Docs/plans/phase-2-restructure.md task 17",
}

_ENV_KEYS = {
    "env": "HOGSHADE_ENV",
    "fx": "HOGSHADE_FX",
    "debug_modes": "HOGSHADE_DEBUG_MODES",
    "set": "HOGSHADE_SET",
    "check": "HOGSHADE_CHECK",
}


def main(parameters: dict) -> dict:
    """Entry point the Maya GUI worker calls. Parameters become the environment the check script reads."""
    os.environ["HOGSHADE_ROOT"] = str(ROOT).replace("\\", "/")
    os.environ["HOGSHADE_AS_JOB"] = "1"
    for key, var in _ENV_KEYS.items():
        value = parameters.get(key)
        if value:
            os.environ[var] = str(value)
    tools_maya = str(ROOT / "tools" / "maya")
    if tools_maya not in sys.path:
        sys.path.insert(0, tools_maya)
    import importlib

    for name in ("_session", "ibl_check"):
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    import ibl_check  # a tools/maya script module, on sys.path above

    _LOGGER.info(f"maya_ibl_check job: fx={ibl_check.SHADER} env={ibl_check.ENV}")
    return ibl_check.run_check(quit_after=False)
