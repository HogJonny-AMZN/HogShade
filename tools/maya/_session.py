"""
HogShade: what every Maya check script shares: the incremental log, file-node texture binding, light binding,
the settle-then-playblast capture, and the deferred quit. Runs inside Maya's own Python (3.11), so nothing
here imports numpy or the hogshade package.
Package: tools/maya/_session

A check script is a module in this folder with a ``run()`` that the .mel launcher imports, or a
``run_check(quit_after=False)`` that a Job_Orchestrator job calls.

Environment every script honours: HOGSHADE_ROOT (repo root, default the working directory),
HOGSHADE_VERIFICATION (default <root>/verification). Paths are pathlib.Path inside; Maya's commands
get str() at the boundary, with forward slashes.
"""

import os
import time
import traceback
from pathlib import Path

from maya import cmds

_MODULE_NAME = "tools.maya._session"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

ROOT = Path(os.environ.get("HOGSHADE_ROOT", os.getcwd()))
VERIFICATION = Path(os.environ.get("HOGSHADE_VERIFICATION", str(ROOT / "verification")))
MAYA_VERSION = "2026"


def maya_path(path: Path) -> str:
    """The string Maya's commands want: forward slashes, no backslash escapes to trip a MEL layer."""
    return str(path).replace("\\", "/")


class Log(list):
    """A list that rewrites its file on every append, so a Maya crash still leaves the last step on disk."""

    def __init__(self, path: Path, first_lines: list) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for line in [f"started {time.ctime()}", *first_lines, "log is incremental"]:
            self.append(line)

    def append(self, line: str) -> None:
        super().append(line)
        self.path.write_text("\n".join(self) + "\n", encoding="utf-8")


def output_dir(check: str, variant: str = "") -> Path:
    """One directory per capture: <verification>/maya-<version>/<check>[/<variant>]; files inside are named
    by role only (check.log, main.png, debug-18.png, maya-history.log). Host, version, check and variant
    are directory levels, never encoded into a file name. A variant may carry sub-levels ("legacy-v1/env")."""
    path = VERIFICATION / f"maya-{MAYA_VERSION}" / check
    if variant:
        path = path.joinpath(*variant.replace("\\", "/").split("/"))
    root = VERIFICATION.resolve()
    resolved = path.resolve()
    # check and variant arrive as job parameters: no ".." component, and the result stays under the root
    if ".." in path.parts or root not in resolved.parents:
        raise ValueError(f"output directory escapes {root}: check={check!r} variant={variant!r}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_dx11_shader(node_name: str, fx_path: Path, out: Log) -> tuple:
    """A dx11Shader node with its shading group, loading fx_path; returns (node, shading group, techniques)."""
    if not cmds.pluginInfo("dx11Shader", q=True, loaded=True):
        cmds.loadPlugin("dx11Shader")
    # Maya reports effect compile errors only in the Script Editor; mirror its history to a file beside the log
    history = out.path.with_name("maya-history.log")
    cmds.scriptEditorInfo(historyFilename=maya_path(history), writeHistory=True)
    out.append(f"HISTORY {history}")
    node = cmds.shadingNode("dx11Shader", asShader=True, name=node_name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=node + "SG")
    cmds.connectAttr(node + ".outColor", sg + ".surfaceShader")
    t0 = time.time()
    cmds.setAttr(node + ".shader", maya_path(Path(fx_path)), type="string")
    techs = cmds.getAttr(node + ".techniques")
    out.append(f"TECHNIQUES: {techs!r} (shader load {time.time() - t0:.1f} s)")
    return node, sg, techs


def connect_file(node: str, attr: str, path: Path, space: str, out: Log) -> bool:
    """dx11Shader texture parameters take a connected file node, not a path string. True when Maya decoded it."""
    if not cmds.attributeQuery(attr, node=node, exists=True):
        out.append(f"MISSING attribute {attr}")
        return False
    tex = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name=f"{attr}_file")
    cmds.setAttr(f"{tex}.fileTextureName", maya_path(Path(path)), type="string")
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


def capture(path: Path, out: Log, size: tuple = (960, 720)) -> None:
    """Playblast one frame of the live viewport (the offscreen path does not draw dx11 effects)."""
    settle()
    path = Path(path)
    cmds.playblast(
        frame=[1],
        format="image",
        compression="png",
        completeFilename=maya_path(path),
        viewer=False,
        offScreen=False,
        forceOverwrite=True,
        widthHeight=size,
        percent=100,
        showOrnaments=False,
    )
    out.append(f"PNG {path} exists={path.exists()}")


def capture_debug_modes(node: str, png: Path, out: Log, default_modes: str) -> None:
    """One capture per g_DebugMode in HOGSHADE_DEBUG_MODES (default default_modes), then back to 0."""
    modes = [int(m) for m in os.environ.get("HOGSHADE_DEBUG_MODES", default_modes).split(",") if m.strip()]
    if not cmds.attributeQuery("g_DebugMode", node=node, exists=True):
        return
    for mode in modes:
        cmds.setAttr(f"{node}.g_DebugMode", mode)
        capture(Path(png).with_name(f"debug-{mode:02d}.png"), out)
    cmds.setAttr(f"{node}.g_DebugMode", 0)


def quit_maya(out: Log) -> None:
    """Quit now, and on the next idle tick as a fallback, so a standalone check never leaves an idle Maya."""
    cmds.evalDeferred("import maya.cmds as c; c.quit(force=True)", lowestPriority=True)
    try:
        cmds.quit(force=True)
    except Exception as e:  # noqa: BLE001 - the deferred quit is the fallback
        out.append(f"direct quit refused, deferred quit pending: {e!r}")


def _stop_history(out: Log) -> None:
    """Stop mirroring the Script Editor: a resident worker otherwise keeps the committed log open and growing."""
    try:
        cmds.scriptEditorInfo(writeHistory=False)
    except Exception as e:  # noqa: BLE001 - never let the log teardown mask the result
        out.append(f"history mirroring not stopped: {e!r}")


def finish(out: Log, ok: bool, quit_after: bool = True) -> None:
    out.append("RESULT: OK" if ok else "RESULT: FAILED")
    out.append(f"MAYA: {cmds.about(version=True)}")
    _stop_history(out)
    if quit_after:
        quit_maya(out)


def fail(out: Log, quit_after: bool = True) -> None:
    out.append("RESULT: FAILED" + "\n" + traceback.format_exc())
    out.append(f"MAYA: {cmds.about(version=True)}")
    _stop_history(out)
    if quit_after:
        quit_maya(out)
