"""
HogShade: Maya 2026 check that the cooked IBL cubes light the legacy v2 shader (E1 plan, task 11).
Package: tools/maya_ibl_check.py

Run inside a Maya GUI session (headless mayapy has no DirectX device):

    set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
    set HOGSHADE_ROOT=D:/Depot/Maya-PBR-BRDF-VP2
    maya.exe -script tools/maya_ibl_check.mel

Creates a sphere, assigns the v2 shader, points its environment slots at
content/ibl/studio_small_09/cooked/*.dds, turns useEnvMaps on, frames the sphere, playblasts one
frame to Docs/verification/maya-2026-ibl-studio.png, logs the technique list and the texture
attributes, and quits. The log is the evidence; the PNG is the picture.
"""

import os
import time
import traceback

from maya import cmds

ROOT = os.environ.get("HOGSHADE_ROOT", os.getcwd()).replace("\\", "/")
ENV = os.environ.get("HOGSHADE_ENV", "studio_small_09")
SHADER = f"{ROOT}/legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx"
COOKED = f"{ROOT}/content/ibl/{ENV}/cooked"
OUT_DIR = f"{ROOT}/Docs/verification"
LOG = f"{OUT_DIR}/maya-2026-ibl-{ENV}.log"
PNG = f"{OUT_DIR}/maya-2026-ibl-{ENV}.png"


def run():
    out = [f"started {time.ctime()}", f"shader {SHADER}", f"cooked {COOKED}"]
    try:
        if not cmds.pluginInfo("dx11Shader", q=True, loaded=True):
            cmds.loadPlugin("dx11Shader")
        sphere = cmds.polySphere(radius=1.0, subdivisionsAxis=64, subdivisionsHeight=64)[0]
        node = cmds.shadingNode("dx11Shader", asShader=True, name="hogshade_v2_ibl")
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=node + "SG")
        cmds.connectAttr(node + ".outColor", sg + ".surfaceShader")
        cmds.setAttr(node + ".shader", SHADER, type="string")
        cmds.sets(sphere, e=True, forceElement=sg)
        techs = cmds.getAttr(node + ".techniques")
        out.append(f"TECHNIQUES: {techs!r}")
        # dx11Shader texture parameters take a connected file node, not a path string
        for attr, fname in (("specularEnvTextureCube", "specular.dds"), ("diffuseEnvTextureCube", "irradiance.dds")):
            if cmds.attributeQuery(attr, node=node, exists=True):
                tex = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=f"{attr}_file")
                cmds.setAttr(f"{tex}.fileTextureName", f"{COOKED}/{fname}", type="string")
                cmds.setAttr(f"{tex}.colorSpace", "Raw", type="string")
                cmds.connectAttr(f"{tex}.outColor", f"{node}.{attr}", force=True)
                out.append(f"CONNECTED {tex} ({cmds.getAttr(f'{tex}.fileTextureName')}) -> {attr}")
            else:
                out.append(f"MISSING attribute {attr}")
        # a polished metal ball reflects the cubes, so orientation and mip filtering are visible in the picture
        for attr, value in (
            ("useEnvMaps", True),
            ("useShadows", False),
            ("materialMetalness", 1.0),
            ("materialRoughness", 0.15),
        ):
            if cmds.attributeQuery(attr, node=node, exists=True):
                cmds.setAttr(f"{node}.{attr}", value)
                out.append(f"SET {attr} = {value}")
        cmds.select(sphere)
        cmds.viewFit()
        cmds.select(clear=True)
        cmds.playblast(
            frame=[1],
            format="image",
            compression="png",
            completeFilename=PNG,
            viewer=False,
            offScreen=True,
            forceOverwrite=True,
            widthHeight=(960, 720),
            percent=100,
            showOrnaments=False,
        )
        out.append(f"PNG {PNG} exists={os.path.exists(PNG)}")
        out.append("RESULT: OK" if techs and os.path.exists(PNG) else "RESULT: FAILED")
    except Exception:  # noqa: BLE001 - log whatever Maya throws
        out.append("RESULT: FAILED\n" + traceback.format_exc())
    out.append(f"MAYA: {cmds.about(version=True)}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(LOG, "w") as f:
        f.write("\n".join(out) + "\n")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)


cmds.evalDeferred(run, lowestPriority=True)
