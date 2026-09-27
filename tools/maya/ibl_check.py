"""
HogShade: Maya 2026 check that the cooked IBL cubes light the HogShade shell (phase 2 plan, task 17; E1 task 11).
Package: tools/maya/ibl_check

Run inside a Maya GUI session (headless mayapy has no DirectX device):

    set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
    set HOGSHADE_ROOT=D:/Depot/HogShade
    maya.exe -script tools/maya/ibl_check.mel

Creates a sphere, assigns hosts/maya_dx11/hogshade.fx (HOGSHADE_FX overrides, e.g. the legacy v2
shader), points the environment slots at content/ibl/<env>/cooked/*.dds and the BRDF LUT at
content/ibl/brdf_lut.dds, binds one directional light into slot 0, frames the sphere, playblasts
the main view and a few debug views to Docs/verification/maya/, logs the technique list and the
texture attributes, and quits. The log is the evidence; the PNGs are the picture.

Environment: HOGSHADE_ENV (studio_small_09), HOGSHADE_FX, HOGSHADE_SET="attr=value,...",
HOGSHADE_DEBUG_MODES="18,27,28", HOGSHADE_TAG (output file tag; default "hogshade-ibl").
"""

import os

import _session as s
from maya import cmds

ENV = os.environ.get("HOGSHADE_ENV", "studio_small_09")
SHADER = os.environ.get("HOGSHADE_FX", f"{s.ROOT}/hosts/maya_dx11/hogshade.fx")
COOKED = os.environ.get("HOGSHADE_COOKED", f"{s.ROOT}/content/ibl/{ENV}/cooked").replace("\\", "/")
LUT = f"{s.ROOT}/content/ibl/brdf_lut.dds"
LOG, PNG = s.output_paths(os.environ.get("HOGSHADE_TAG", "hogshade-ibl"), ENV)

# the HogShade shell takes linear values and defaults every map to "unbound"; the legacy shader needs the
# RGBM-era settings instead (envLightingExp exists only there). HOGSHADE_SET="attr=value,..." overrides.
DEFAULTS = {
    "useEnvMaps": True,
    "useShadows": False,
    "envExposure": 1.0,
    "linearSpaceLighting": True,
    "gammaCorrectionValue": 2.2,
    "materialBaseColor": (0.5, 0.5, 0.5),
    "materialMetalness": 0.0,
    "materialRoughness": 0.2,
    "materialSpecular": 1.0,
    "materialIOR": 1.5,
    "envLightingExp": 1.0,
}


def run():
    out = s.Log(LOG, [f"shader {SHADER}", f"cooked {COOKED}"])
    try:
        sphere = cmds.polySphere(radius=1.0, subdivisionsAxis=64, subdivisionsHeight=64)[0]
        node, sg, techs = s.load_dx11_shader("hogshade_ibl", SHADER, out)
        cmds.sets(sphere, e=True, forceElement=sg)

        decoded = set()
        for attr, fname in (("specularEnvTextureCube", "specular.dds"), ("diffuseEnvTextureCube", "irradiance.dds")):
            if s.connect_file(node, attr, f"{COOKED}/{fname}", "Raw", out):
                decoded.add(attr)
        lut_ok = s.connect_file(node, "brdfTextureMap", LUT, "Raw", out)
        s.set_attrs(node, s.settings_from_env(DEFAULTS), out)

        # one directional light into slot 0: the direct highlight beside the environment reflection
        light = cmds.directionalLight(name="key_light", intensity=2.0)
        light_tf = cmds.listRelatives(light, parent=True)[0]
        cmds.setAttr(f"{light_tf}.rotate", -35.0, 40.0, 0.0, type="double3")
        s.bind_light(node, "Light 0", light_tf, out)

        # control: a red Lambert sphere beside it proves the capture shows materials at all
        control = cmds.polySphere(radius=0.5, name="control_lambert")[0]
        cmds.move(1.8, 0, 0, control)
        lam = cmds.shadingNode("lambert", asShader=True, name="control_red")
        cmds.setAttr(lam + ".color", 1.0, 0.0, 0.0, type="double3")
        lam_sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=lam + "SG")
        cmds.connectAttr(lam + ".outColor", lam_sg + ".surfaceShader")
        cmds.sets(control, e=True, forceElement=lam_sg)

        s.focus_viewport(out)
        cmds.select(sphere, control)
        cmds.viewFit()
        cmds.select(clear=True)

        s.capture(PNG, out)
        # 18 specular accumulator, 27 diffuse environment, 28 specular environment (legacy_v2 debug modes)
        s.capture_debug_modes(node, PNG, out, "18,27,28")
        out.append(f"CUBES decoded: {sorted(decoded)}; LUT decoded: {lut_ok}")
        s.finish(out, bool(techs) and os.path.exists(PNG) and len(decoded) == 2 and lut_ok)
    except Exception:  # noqa: BLE001 - log whatever Maya throws
        s.fail(out)


cmds.evalDeferred(run, lowestPriority=True)
