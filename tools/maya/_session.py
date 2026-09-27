"""
HogShade: what every Maya check script shares: the incremental log, file-node texture binding, light binding,
the settle-then-playblast capture, and the deferred quit. Runs inside Maya's own Python (3.11), so nothing
here imports numpy or the hogshade package.
Package: tools/maya/_session

A check script is a module in this folder with a ``run()`` that the .mel launcher imports:

    python("import os, sys; sys.path.insert(0, os.environ.get('HOGSHADE_ROOT', os.getcwd()) + '/tools/maya'); import ibl_check")

Environment every script honours: HOGSHADE_ROOT (repo root, default the working directory),
HOGSHADE_VERIFICATION (default <root>/Docs/verification/maya).
"""

import os
import time
import traceback

from maya import cmds

ROOT = os.environ.get("HOGSHADE_ROOT", os.getcwd()).replace("\\", "/")
VERIFICATION = os.environ.get("HOGSHADE_VERIFICATION", f"{ROOT}/Docs/verification/maya").replace("\\", "/")
MAYA_VERSION = "2026"


class Log(list):
    """A list that rewrites its file on every append, so a Maya crash still leaves the last step on disk."""

    def __init__(self, path: str, first_lines: list) -> None:
        super().__init__()
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for line in [f"started {time.ctime()}", *first_lines, "log is incremental"]:
            self.append(line)

    def append(self, line: str) -> None:
        super().append(line)
        with open(self.path, "w") as f:
            f.write("\n".join(self) + "\n")


def output_paths(tag: str, env: str = "") -> tuple:
    """(log path, png path) under the verification folder: maya-<version>-<tag>[-<env>].{log,png}."""
    stem = f"{VERIFICATION}/maya-{MAYA_VERSION}-{tag}" + (f"-{env}" if env else "")
    return stem + ".log", stem + ".png"


def load_dx11_shader(node_name: str, fx_path: str, out: Log) -> tuple:
    """A dx11Shader node with its shading group, loading fx_path; returns (node, shading group, techniques)."""
    if not cmds.pluginInfo("dx11Shader", q=True, loaded=True):
        cmds.loadPlugin("dx11Shader")
    # Maya reports effect compile errors only in the Script Editor; mirror its history to a file beside the log
    history = out.path.replace(".log", "-maya-history.log")
    cmds.scriptEditorInfo(historyFilename=history, writeHistory=True)
    out.append(f"HISTORY {history}")
    node = cmds.shadingNode("dx11Shader", asShader=True, name=node_name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=node + "SG")
    cmds.connectAttr(node + ".outColor", sg + ".surfaceShader")
    t0 = time.time()
    cmds.setAttr(node + ".shader", fx_path.replace("\\", "/"), type="string")
    techs = cmds.getAttr(node + ".techniques")
    out.append(f"TECHNIQUES: {techs!r} (shader load {time.time() - t0:.1f} s)")
    return node, sg, techs


def connect_file(node: str, attr: str, path: str, space: str, out: Log) -> bool:
    """dx11Shader texture parameters take a connected file node, not a path string. True when Maya decoded it."""
    if not cmds.attributeQuery(attr, node=node, exists=True):
        out.append(f"MISSING attribute {attr}")
        return False
    tex = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=f"{attr}_file")
    cmds.setAttr(f"{tex}.fileTextureName", path.replace("\\", "/"), type="string")
    cmds.setAttr(f"{tex}.colorSpace", space, type="string")
    cmds.connectAttr(f"{tex}.outColor", f"{node}.{attr}", force=True)
    size = cmds.getAttr(f"{tex}.outSize")  # (0, 0) when Maya could not decode the file
    out.append(f"CONNECTED {tex} ({path}) -> {attr}; loaded size {size}")
    return bool(size and size[0][0] > 0)


def set_attrs(node: str, settings: dict, out: Log) -> None:
    """setAttr each entry that exists on the node; tuples are double3; absent attributes are logged, not errors."""
    for attr, value in settings.items():
        if not cmds.attributeQuery(attr, node=node, exists=True):
            out.append(f"absent attribute {attr} (fine for this shader)")
            continue
        if isinstance(value, tuple):
            cmds.setAttr(f"{node}.{attr}", *value, type="double3")
        else:
            cmds.setAttr(f"{node}.{attr}", value)
        out.append(f"SET {attr} = {value}")


def settings_from_env(defaults: dict, var: str = "HOGSHADE_SET") -> dict:
    """defaults updated from VAR="attr=value,attr=value" (floats, or True/False)."""
    settings = dict(defaults)
    for item in os.environ.get(var, "").split(","):
        if "=" in item:
            key, val = item.split("=", 1)
            settings[key.strip()] = float(val) if val.strip() not in ("True", "False") else val.strip() == "True"
    return settings


def bind_light(node: str, slot: str, light_transform: str, out: Log) -> None:
    """Bind a scene light into a shader light slot ("Light 0"); explicit, since Maya's automatic binding is lazy."""
    try:
        cmds.dx11Shader(node, connectLight=(slot, light_transform))
        out.append(f"LIGHT {slot} <- {light_transform}: {cmds.dx11Shader(node, q=True, lightConnectionStatus=True)}")
    except Exception as e:  # noqa: BLE001 - best effort; the log says what happened
        out.append(f"LIGHT binding {slot} failed: {e!r}")


def focus_viewport(out: Log) -> str:
    panel = cmds.getPanel(withFocus=True)
    if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
        panels = cmds.getPanel(type="modelPanel") or [
            p for p in (cmds.getPanel(allPanels=True) or []) if cmds.getPanel(typeOf=p) == "modelPanel"
        ]
        if not panels:
            raise RuntimeError(f"no model panel in this session; panels: {cmds.getPanel(allPanels=True)!r}")
        panel = panels[0]
    cmds.setFocus(panel)
    cmds.modelEditor(panel, e=True, displayTextures=True, displayLights="all")
    out.append(f"PANEL {panel} renderer={cmds.modelEditor(panel, q=True, rendererName=True)}")
    out.append(f"VP2 engine now: {cmds.ogs(q=True, deviceInformation=True)}")
    return panel


def settle() -> None:
    """VP2 loads textures and rebuilds shader instances asynchronously; give it real time before a capture."""
    for _ in range(3):
        cmds.refresh(force=True)
    cmds.pause(seconds=4)
    for _ in range(3):
        cmds.refresh(force=True)


def capture(path: str, out: Log, size: tuple = (960, 720)) -> None:
    """Playblast one frame of the live viewport (the offscreen path does not draw dx11 effects)."""
    settle()
    cmds.playblast(
        frame=[1],
        format="image",
        compression="png",
        completeFilename=path,
        viewer=False,
        offScreen=False,
        forceOverwrite=True,
        widthHeight=size,
        percent=100,
        showOrnaments=False,
    )
    out.append(f"PNG {path} exists={os.path.exists(path)}")


def capture_debug_modes(node: str, png: str, out: Log, default_modes: str) -> None:
    """One capture per g_DebugMode in HOGSHADE_DEBUG_MODES (default default_modes), then back to 0."""
    modes = [int(m) for m in os.environ.get("HOGSHADE_DEBUG_MODES", default_modes).split(",") if m.strip()]
    if not cmds.attributeQuery("g_DebugMode", node=node, exists=True):
        return
    for mode in modes:
        cmds.setAttr(f"{node}.g_DebugMode", mode)
        capture(png.replace(".png", f"-debug-{mode:02d}.png"), out)
    cmds.setAttr(f"{node}.g_DebugMode", 0)


def finish(out: Log, ok: bool) -> None:
    out.append("RESULT: OK" if ok else "RESULT: FAILED")
    out.append(f"MAYA: {cmds.about(version=True)}")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)


def fail(out: Log) -> None:
    out.append("RESULT: FAILED\n" + traceback.format_exc())
    out.append(f"MAYA: {cmds.about(version=True)}")
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)
