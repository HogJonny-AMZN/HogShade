import time
import traceback

import maya.cmds as cmds

DIR = __import__("os").environ.get("HOGSHADE_LOG_DIR", ".") + "/"
LOG = DIR + "maya_gui_test.log"
MARK = DIR + "maya_gui_test.marker"
SHADER = __import__("os").environ.get("HOGSHADE_SHADER", "legacy/v2.0/uv0bn-pbs_IBLenv.fx")

with open(MARK, "w") as f:
    f.write("script started %s\n" % time.ctime())


def run():
    out = ["started %s" % time.ctime()]
    try:
        out.append("ENGINE: %r" % cmds.optionVar(q="vp2RenderingEngine"))
        if not cmds.pluginInfo("dx11Shader", q=True, loaded=True):
            cmds.loadPlugin("dx11Shader")
        out.append("PLUGIN: loaded=%r" % cmds.pluginInfo("dx11Shader", q=True, loaded=True))
        n = cmds.shadingNode("dx11Shader", asShader=True, name="hogshade_v2")
        cmds.setAttr(n + ".shader", SHADER, type="string")
        techs = cmds.getAttr(n + ".techniques")
        out.append("TECHNIQUES: %r" % techs)
        out.append("TECHNIQUE: %r" % cmds.getAttr(n + ".technique"))
        out.append("RESULT: OK" if techs else "RESULT: NO_TECHNIQUES")
    except Exception:
        out.append("RESULT: FAILED\n" + traceback.format_exc())
    out.append("MAYA: %s" % cmds.about(version=True))
    with open(LOG, "w") as f:
        f.write("\n".join(out) + "\n")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)


cmds.evalDeferred(run, lowestPriority=True)
