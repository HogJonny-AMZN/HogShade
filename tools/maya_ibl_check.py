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
COOKED = os.environ.get("HOGSHADE_COOKED", f"{ROOT}/content/ibl/{ENV}/cooked").replace("\\", "/")
OUT_DIR = f"{ROOT}/Docs/verification"
LOG = f"{OUT_DIR}/maya-2026-ibl-{ENV}.log"
PNG = f"{OUT_DIR}/maya-2026-ibl-{ENV}.png"


class _Log(list):
    """A list that rewrites the log file on every append, so a Maya crash still leaves the last step on disk."""

    def append(self, line: str) -> None:
        super().append(line)
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(LOG, "w") as f:
            f.write("\n".join(self) + "\n")


def run():
    out = _Log([f"started {time.ctime()}", f"shader {SHADER}", f"cooked {COOKED}"])
    out.append("log is incremental")
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
        connected_cubes = set()
        for attr, fname in (("specularEnvTextureCube", "specular.dds"), ("diffuseEnvTextureCube", "irradiance.dds")):
            if cmds.attributeQuery(attr, node=node, exists=True):
                tex = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=f"{attr}_file")
                cmds.setAttr(f"{tex}.fileTextureName", f"{COOKED}/{fname}", type="string")
                cmds.setAttr(f"{tex}.colorSpace", "Raw", type="string")
                cmds.connectAttr(f"{tex}.outColor", f"{node}.{attr}", force=True)
                size = cmds.getAttr(f"{tex}.outSize")  # (0, 0) when Maya could not decode the file
                out.append(f"CONNECTED {tex} ({cmds.getAttr(f'{tex}.fileTextureName')}) -> {attr}; loaded size {size}")
                if size and size[0][0] > 0:
                    connected_cubes.add(attr)
            else:
                out.append(f"MISSING attribute {attr}")
        # the shader samples its 2D maps unconditionally: with nothing bound the base colour is black and a
        # metal ball has F0 = 0, which renders black. Bind flat test textures when a folder is given.
        textures = os.environ.get("HOGSHADE_TEXTURES", "").replace("\\", "/")
        if textures:
            for attr, fname, space in (
                ("baseColorMap", "base_white.png", "sRGB"),
                ("baseNormalMap", "normal_flat.png", "Raw"),
                ("pbrMasksMap", "masks_metal.png", "Raw"),
            ):
                if cmds.attributeQuery(attr, node=node, exists=True):
                    tex = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=f"{attr}_file")
                    cmds.setAttr(f"{tex}.fileTextureName", f"{textures}/{fname}", type="string")
                    cmds.setAttr(f"{tex}.colorSpace", space, type="string")
                    cmds.connectAttr(f"{tex}.outColor", f"{node}.{attr}", force=True)
                    out.append(f"CONNECTED {tex} -> {attr}; loaded size {cmds.getAttr(f'{tex}.outSize')}")
        # Defaults suit the legacy shader's RGBM 8-bit cubes (exposure 5, gamma 2.23); the cooked cubes are linear
        # fp16, so exposure 1 and no gamma. HOGSHADE_SET="attr=value,..." overrides any of these.
        settings = {
            "useEnvMaps": True,
            "useShadows": False,
            "envLightingExp": 1.0,
            "linearSpaceLighting": False,
            "materialMetalness": 1.0,
            "materialRoughness": 0.15,
        }
        for item in os.environ.get("HOGSHADE_SET", "").split(","):
            if "=" in item:
                key, val = item.split("=", 1)
                settings[key.strip()] = float(val) if val.strip() not in ("True", "False") else val.strip() == "True"
        for attr, value in settings.items():
            if cmds.attributeQuery(attr, node=node, exists=True):
                cmds.setAttr(f"{node}.{attr}", value)
                out.append(f"SET {attr} = {value}")
            else:
                out.append(f"MISSING attribute {attr}")
        # control: a red Lambert sphere beside it proves the capture shows materials at all
        control = cmds.polySphere(radius=0.5, name="control_lambert")[0]
        cmds.move(1.8, 0, 0, control)
        lam = cmds.shadingNode("lambert", asShader=True, name="control_red")
        cmds.setAttr(lam + ".color", 1.0, 0.0, 0.0, type="double3")
        lam_sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=lam + "SG")
        cmds.connectAttr(lam + ".outColor", lam_sg + ".surfaceShader")
        cmds.sets(control, e=True, forceElement=lam_sg)
        # what is actually drawing
        panel = cmds.getPanel(withFocus=True)
        if cmds.getPanel(typeOf=panel) != "modelPanel":
            panel = cmds.getPanel(type="modelPanel")[0]
        cmds.setFocus(panel)
        cmds.modelEditor(panel, e=True, displayTextures=True, displayLights="default")
        out.append(f"PANEL {panel} renderer={cmds.modelEditor(panel, q=True, rendererName=True)}")
        out.append(f"VP2 engine now: {cmds.ogs(q=True, deviceInformation=True)}")
        out.append(f"SG members: {cmds.sets(sg, q=True)}")
        cmds.select(sphere, control)
        cmds.viewFit()
        cmds.select(clear=True)

        def settle() -> None:
            # VP2 loads textures and rebuilds shader instances asynchronously; a playblast issued in the
            # same idle tick as the setAttr calls draws the previous state. Give it real time.
            for _ in range(3):
                cmds.refresh(force=True)
            cmds.pause(seconds=4)
            for _ in range(3):
                cmds.refresh(force=True)

        def capture(path: str) -> None:
            settle()
            cmds.playblast(
                frame=[1],
                format="image",
                compression="png",
                completeFilename=path,
                viewer=False,
                offScreen=False,  # the offscreen path did not draw the dx11 effect; capture the live viewport
                forceOverwrite=True,
                widthHeight=(960, 720),
                percent=100,
                showOrnaments=False,
            )
            out.append(f"PNG {path} exists={os.path.exists(path)}")

        capture(PNG)
        # Optional A/B of cooked-cube variants: HOGSHADE_VARIANTS="name=dir;name=dir" re-points the two cube file
        # nodes at each dir and captures the main view and debug 28 (specular environment term) per variant
        variants = [v for v in os.environ.get("HOGSHADE_VARIANTS", "").split(";") if "=" in v]
        for spec in variants:
            vname, vdir = spec.split("=", 1)
            vdir = vdir.replace("\\", "/")
            for attr, fname in (
                ("specularEnvTextureCube", "specular.dds"),
                ("diffuseEnvTextureCube", "irradiance.dds"),
            ):
                cmds.setAttr(f"{attr}_file.fileTextureName", f"{vdir}/{fname}", type="string")
            out.append(f"VARIANT {vname}: {vdir}; specular size {cmds.getAttr('specularEnvTextureCube_file.outSize')}")
            capture(PNG.replace(".png", f"-variant-{vname}.png"))
            if cmds.attributeQuery("g_DebugMode", node=node, exists=True):
                cmds.setAttr(f"{node}.g_DebugMode", 28)
                capture(PNG.replace(".png", f"-variant-{vname}-debug-28.png"))
                cmds.setAttr(f"{node}.g_DebugMode", 0)
        # Debug views prove which paths are alive: 12 is the raw normal (drawn from geometry alone), 1 is the
        # base colour texture, 27 and 28 are the diffuse and specular environment terms (if the cubes loaded)
        modes = [int(m) for m in os.environ.get("HOGSHADE_DEBUG_MODES", "12").split(",") if m.strip()]
        if cmds.attributeQuery("g_DebugMode", node=node, exists=True):
            for mode in modes:
                cmds.setAttr(f"{node}.g_DebugMode", mode)
                capture(PNG.replace(".png", f"-debug-{mode:02d}.png"))
            cmds.setAttr(f"{node}.g_DebugMode", 0)
        ok = bool(techs) and os.path.exists(PNG) and len(connected_cubes) == 2
        out.append(f"CUBES connected and decoded: {sorted(connected_cubes)}")
        out.append("RESULT: OK" if ok else "RESULT: FAILED")
    except Exception:  # noqa: BLE001 - log whatever Maya throws
        out.append("RESULT: FAILED\n" + traceback.format_exc())
    out.append(f"MAYA: {cmds.about(version=True)}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(LOG, "w") as f:
        f.write("\n".join(out) + "\n")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)


cmds.evalDeferred(run, lowestPriority=True)
