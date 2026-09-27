"""
HogShade: Maya 2026 check that a dx11Shader effect loads and exposes techniques (phase 1 plan, task 8).
Package: tools/maya/load_check

    set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
    set HOGSHADE_ROOT=D:/Depot/HogShade
    maya.exe -script tools/maya/load_check.mel

HOGSHADE_FX selects the effect (default hosts/maya_dx11/hogshade.fx; the legacy v2 shader is
legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx). Writes verification/maya-2026/<check>/check.log (default check
name load-check) with the technique list and RESULT: OK, or the traceback.
"""

import os
from pathlib import Path

import _session as s
from maya import cmds

_MODULE_NAME = "tools.maya.load_check"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

SHADER = Path(os.environ.get("HOGSHADE_FX", str(s.ROOT / "hosts" / "maya_dx11" / "hogshade.fx")))
LOG = s.output_dir(os.environ.get("HOGSHADE_CHECK", "load-check")) / "check.log"


def run_check(quit_after: bool = True) -> dict:
    out = s.Log(LOG, [f"shader {SHADER}"])
    result = {"ok": False, "log": str(LOG), "techniques": []}
    try:
        out.append("ENGINE: {!r}".format(cmds.optionVar(q="vp2RenderingEngine")))
        node, _sg, techs = s.load_dx11_shader("hogshade_load", SHADER, out)
        out.append("TECHNIQUE: {!r}".format(cmds.getAttr(node + ".technique")))
        result["techniques"] = list(techs or [])
        result["ok"] = bool(techs)
        s.finish(out, result["ok"], quit_after)
    except Exception:  # noqa: BLE001 - the point of this script is to log whatever Maya throws
        s.fail(out, quit_after)
    return result


def run() -> None:
    run_check(quit_after=True)


if os.environ.get("HOGSHADE_AS_JOB", "") != "1":
    cmds.evalDeferred(run, lowestPriority=True)
