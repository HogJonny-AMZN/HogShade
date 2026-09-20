import time
import traceback

from maya import cmds

DIR = __import__("os").environ.get("HOGSHADE_LOG_DIR", ".") + "/"
LOG = DIR + "maya_gui_test.log"
MARK = DIR + "maya_gui_test.marker"
SHADER = __import__("os").environ.get("HOGSHADE_SHADER", "legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx")

with open(MARK, "w") as f:
    f.write(f"script started {time.ctime()}\n")


def run():
    out = [f"started {time.ctime()}"]
    try:
        out.append("ENGINE: {!r}".format(cmds.optionVar(q="vp2RenderingEngine")))
        if not cmds.pluginInfo("dx11Shader", q=True, loaded=True):
            cmds.loadPlugin("dx11Shader")
        out.append("PLUGIN: loaded={!r}".format(cmds.pluginInfo("dx11Shader", q=True, loaded=True)))
        n = cmds.shadingNode("dx11Shader", asShader=True, name="hogshade_v2")
        cmds.setAttr(n + ".shader", SHADER, type="string")
        techs = cmds.getAttr(n + ".techniques")
        out.append(f"TECHNIQUES: {techs!r}")
        out.append("TECHNIQUE: {!r}".format(cmds.getAttr(n + ".technique")))
        out.append("RESULT: OK" if techs else "RESULT: NO_TECHNIQUES")
    except Exception:  # noqa: BLE001 - the point of this script is to log whatever Maya throws
        out.append("RESULT: FAILED\n" + traceback.format_exc())
    out.append(f"MAYA: {cmds.about(version=True)}")
    with open(LOG, "w") as f:
        f.write("\n".join(out) + "\n")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)


cmds.evalDeferred(run, lowestPriority=True)
