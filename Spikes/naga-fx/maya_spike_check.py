"""
HogShade phase 2 spike (plan PR A, task 3): Maya 2026 draws the naga-derived effect with a bound texture and light.
Package: Spikes/naga-fx/maya_spike_check.py

    set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
    set HOGSHADE_ROOT=D:/Depot/Maya-PBR-BRDF-VP2
    maya.exe -script Spikes/naga-fx/maya_spike_check.mel

Loads ggx.fx on a sphere, connects a file node to baseColorMap, adds a directional light (dx11Shader
binds scene lights to "Light 0" automatically), captures the live viewport and a second frame with
the light rotated, and logs techniques, the decoded texture size and the light binding. Two
different frames prove the light reaches the shader; a textured ball proves the texture does.
"""

import os
import time
import traceback

from maya import cmds

ROOT = os.environ.get("HOGSHADE_ROOT", os.getcwd()).replace("\\", "/")
SPIKE = f"{ROOT}/Spikes/naga-fx"
FX = f"{SPIKE}/ggx.fx"
TEXTURE = os.environ.get("HOGSHADE_TEXTURE", f"{SPIKE}/checker.png").replace("\\", "/")
OUT_DIR = f"{SPIKE}/verification"
LOG = f"{OUT_DIR}/maya-2026-spike.log"
PNG_A = f"{OUT_DIR}/maya-2026-spike-light-a.png"
PNG_B = f"{OUT_DIR}/maya-2026-spike-light-b.png"


class _Log(list):
    def append(self, line: str) -> None:
        super().append(line)
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(LOG, "w") as f:
            f.write("\n".join(self) + "\n")


def _settle() -> None:
    for _ in range(3):
        cmds.refresh(force=True)
    cmds.pause(seconds=3)
    for _ in range(3):
        cmds.refresh(force=True)


def _capture(path: str) -> None:
    _settle()
    cmds.playblast(
        frame=[1],
        format="image",
        compression="png",
        completeFilename=path,
        viewer=False,
        offScreen=False,
        forceOverwrite=True,
        widthHeight=(960, 720),
        percent=100,
        showOrnaments=False,
    )


def run():
    out = _Log([f"started {time.ctime()}", f"fx {FX}", f"texture {TEXTURE}"])
    try:
        if not cmds.pluginInfo("dx11Shader", q=True, loaded=True):
            cmds.loadPlugin("dx11Shader")
        sphere = cmds.polySphere(radius=1.0, subdivisionsAxis=64, subdivisionsHeight=64)[0]
        node = cmds.shadingNode("dx11Shader", asShader=True, name="spike_ggx")
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=node + "SG")
        cmds.connectAttr(node + ".outColor", sg + ".surfaceShader")
        cmds.setAttr(node + ".shader", FX, type="string")
        cmds.sets(sphere, e=True, forceElement=sg)
        techs = cmds.getAttr(node + ".techniques")
        out.append(f"TECHNIQUES: {techs!r}")

        tex = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name="baseColorMap_file")
        cmds.setAttr(tex + ".fileTextureName", TEXTURE, type="string")
        cmds.setAttr(tex + ".colorSpace", "sRGB", type="string")
        cmds.connectAttr(tex + ".outColor", node + ".baseColorMap", force=True)
        size = cmds.getAttr(tex + ".outSize")
        out.append(f"TEXTURE decoded size {size}")

        light = cmds.directionalLight(name="spike_light", intensity=1.5)
        light_xf = cmds.listRelatives(light, parent=True)[0]
        cmds.setAttr(light_xf + ".rotate", -35.0, 30.0, 0.0)
        out.append(
            f"LIGHT {light_xf} created; light0Dir attr exists={cmds.attributeQuery('light0Dir', node=node, exists=True)}"
        )

        panel = cmds.getPanel(withFocus=True)
        if cmds.getPanel(typeOf=panel) != "modelPanel":
            panel = cmds.getPanel(type="modelPanel")[0]
        cmds.setFocus(panel)
        cmds.modelEditor(panel, e=True, displayTextures=True, displayLights="all")
        cmds.select(sphere)
        cmds.viewFit()
        cmds.select(clear=True)

        _capture(PNG_A)
        out.append(f"PNG A {os.path.exists(PNG_A)}; light0Dir now {cmds.getAttr(node + '.light0Dir')}")
        cmds.setAttr(light_xf + ".rotate", -35.0, -120.0, 0.0)
        _capture(PNG_B)
        out.append(f"PNG B {os.path.exists(PNG_B)}; light0Dir now {cmds.getAttr(node + '.light0Dir')}")

        with open(PNG_A, "rb") as fa, open(PNG_B, "rb") as fb:
            same = fa.read() == fb.read()
        out.append(f"FRAMES identical: {same}")
        ok = bool(techs) and size and size[0][0] > 0 and not same
        out.append("RESULT: OK" if ok else "RESULT: FAILED")
    except Exception:  # noqa: BLE001 - log whatever Maya throws
        out.append("RESULT: FAILED\n" + traceback.format_exc())
    out.append(f"MAYA: {cmds.about(version=True)}")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)


cmds.evalDeferred(run, lowestPriority=True)
