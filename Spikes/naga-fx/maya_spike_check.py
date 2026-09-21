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
# BMP is never compressed: the header gives the pixel-data offset, then raw BGR(A) rows
PNG_A = f"{OUT_DIR}/maya-2026-spike-light-a.bmp"
PNG_B = f"{OUT_DIR}/maya-2026-spike-light-b.bmp"


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
        compression="bmp",
        completeFilename=path,
        viewer=False,
        offScreen=False,
        forceOverwrite=True,
        widthHeight=(960, 720),
        percent=100,
        showOrnaments=False,
    )


def run():
    out = _Log([f"started {time.ctime()}", f"fx {FX}"])
    out.append(f"texture {TEXTURE}")  # first write to disk; anything before this line is Maya startup
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
        # explicit binding of the scene light to the effect's Light 0 group, then Maya's own report of it
        cmds.dx11Shader(node, connectLight=("Light 0", light_xf))
        out.append(f"LIGHT BOUND: {cmds.dx11Shader(node, lightConnectionStatus='Light 0')}")

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

        # Maya's own view of the light binding for the slot, not a getAttr on the annotated parameter
        try:
            binding = cmds.dx11Shader(node, listLightInformation=True)
        except Exception as e:  # noqa: BLE001 - informational
            binding = f"query failed: {e!r}"
        out.append(f"LIGHT BINDING (dx11Shader -listLightInformation): {binding}")

        # Decoded pixels, not file bytes: BMP stores the pixel-data offset at byte 10 and bits per pixel at 28
        def _pixels(path):
            with open(path, "rb") as f:
                raw = f.read()
            offset = int.from_bytes(raw[10:14], "little")
            w = int.from_bytes(raw[18:22], "little", signed=True)
            h = abs(int.from_bytes(raw[22:26], "little", signed=True))
            bpp = int.from_bytes(raw[28:30], "little") // 8
            return raw[offset : offset + w * h * bpp], w, h, bpp

        pa, w, h, bpp = _pixels(PNG_A)
        pb, _, _, _ = _pixels(PNG_B)
        n = min(len(pa), len(pb))
        # the sphere is a small part of the frame: measure change only over pixels that are not background,
        # taking the background colour from the frame's first pixel (the viewport's flat grey)
        bg = pa[0:3]
        on_sphere = 0
        changed = 0
        for i in range(0, n - 3, bpp * 4):  # every fourth pixel, BGR triplet
            a3 = pa[i : i + 3]
            if max(abs(a3[k] - bg[k]) for k in range(3)) > 8 or max(abs(pb[i + k] - bg[k]) for k in range(3)) > 8:
                on_sphere += 1
                if max(abs(a3[k] - pb[i + k]) for k in range(3)) > 16:
                    changed += 1
        fraction = changed / max(on_sphere, 1)
        out.append(
            f"FRAMES {w}x{h}x{bpp}: {on_sphere} sampled non-background pixels, "
            f"{fraction:.1%} of them changed by more than 16/255 when the light rotated"
        )
        ok = bool(techs) and size and size[0][0] > 0 and on_sphere > 200 and fraction > 0.3
        out.append("RESULT: OK" if ok else "RESULT: FAILED")
    except Exception:  # noqa: BLE001 - log whatever Maya throws
        out.append("RESULT: FAILED\n" + traceback.format_exc())
    out.append(f"MAYA: {cmds.about(version=True)}")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)


cmds.evalDeferred(run, lowestPriority=True)
