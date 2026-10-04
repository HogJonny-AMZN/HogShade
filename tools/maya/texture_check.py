"""
HogShade: Maya 2026 check that a cooked texture set renders on the HogShade shell (T3, plan tasks 1 and 7).
Package: tools/maya/texture_check

Run inside a Maya GUI session (headless mayapy has no DirectX device) as the Job_Orchestrator job
``hogshade.jobs.maya_texture_check`` on the ``hogshade_maya_gui`` worker, or standalone:

    set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
    set HOGSHADE_ROOT=D:/Depot/HogShade
    set HOGSHADE_SET_DIR=content/textures/grid
    maya.exe -script tools/maya/texture_check.mel

Builds the material: the document named by HOGSHADE_DOCUMENT (a standard document beside its set), or an
in-memory standard document from every map of HOGSHADE_SET_DIR (``hogshade.material.sets``); converts it to
legacy v2 through the reverse table, binds it for the Maya host (attribute values and use-map flags), resolves
every bound map to its cooked DDS and channels through the set's manifest (``hogshade.material.runtime``), and
connects each DDS to the shell's texture slot with the colour space the format says. Then the IBL environment,
one light, the shader ball sphere, a playblast of the main view and the texture debug views into
verification/maya-2026/<check>/<variant>/ (check.log, main.png, debug-NN.png). The log records, per texture,
the format the cook wrote and the size Maya decoded (0x0 when it could not): that line is the probe's answer
for block-compressed DDS in Maya. It also records the main window's menu bar (Job_Orchestrator issue 72).

Environment: HOGSHADE_SET_DIR (required), HOGSHADE_DOCUMENT (optional .material.json), HOGSHADE_ENV
(studio_small_09), HOGSHADE_FX, HOGSHADE_SET="attr=value,...", HOGSHADE_DEBUG_MODES ("1,7,8,9,11": the base
colour texel, metalness, roughness, AO, the normal map), HOGSHADE_CHECK ("textures"), HOGSHADE_VARIANT (the
set's name by default).
"""

import logging as _logging
import os
import sys
from pathlib import Path

import _session as s
from maya import cmds

_MODULE_NAME = "tools.maya.texture_check"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

if str(s.ROOT) not in sys.path:  # the hogshade package (standard library only) for the binding
    sys.path.insert(0, str(s.ROOT))


def _under_root(value: str, default: Path | None = None) -> Path | None:
    """A path parameter as the job spelled it: absolute as given, relative under the repository, never the cwd."""
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else s.ROOT / path


ENV = os.environ.get("HOGSHADE_ENV", "studio_small_09")
SHADER = _under_root(os.environ.get("HOGSHADE_FX", ""), s.ROOT / "hosts" / "maya_dx11" / "hogshade.fx")
IBL = s.ROOT / "content" / "ibl" / ENV / "cooked"
LUT = s.ROOT / "content" / "ibl" / "brdf_lut.dds"
SET_DIR = _under_root(os.environ.get("HOGSHADE_SET_DIR", ""), Path(""))
DOCUMENT = _under_root(os.environ.get("HOGSHADE_DOCUMENT", ""))
OUT = s.output_dir(os.environ.get("HOGSHADE_CHECK", "textures"), os.environ.get("HOGSHADE_VARIANT", SET_DIR.name))
LOG = OUT / "check.log"
PNG = OUT / "main.png"
DEBUG_MODES = "1,7,8,9,11"

DEFAULTS = {
    "useEnvMaps": True,
    "useShadows": False,
    "envExposure": 1.0,
    "linearSpaceLighting": True,
    "gammaCorrectionValue": 2.2,
}


def _space_for(fmt: str) -> str:
    return "sRGB" if fmt.endswith("_SRGB") else "Raw"


def build_material() -> tuple:
    """The Maya binding and the runtime textures of the document or the set; (binding, runtime, doc_dir)."""
    from hogshade.material import bind, convert, load, resolve, runtime_textures
    from hogshade.material.sets import document_for_set

    if DOCUMENT is not None:
        doc = load(DOCUMENT)
        doc_dir = DOCUMENT.parent
    else:
        doc = document_for_set(SET_DIR)
        doc_dir = doc.root
    resolved = resolve(doc)
    converted, losses = convert(resolved, "hogshade-legacy-v2")
    binding = bind(resolve(converted), "maya_dx11")
    runtime = runtime_textures(binding.textures, doc_dir)
    return binding, runtime, doc_dir, [loss.parameter for loss in losses]


def connect_textures(node: str, binding, runtime: dict, out: s.Log) -> dict:
    """Every runtime texture into its shell slot; returns {parameter: (format, loaded)}."""
    from hogshade.material.binding import maya_map_slots, maya_packed_slots

    slots = maya_map_slots(binding.material_type)
    decoded = {}
    done: set = set()
    for key, pm in maya_packed_slots().items():
        members = {p: runtime[p] for p in pm["channels"] if p in runtime}
        files = {rt.path for rt in members.values()}
        if not members or len(files) != 1 or not all(rt.packed for rt in members.values()):
            continue
        path = files.pop()
        fmt = next(iter(members.values())).format
        loaded = s.connect_file(node, pm["name"], path, _space_for(fmt), out)
        cmds.setAttr(f"{node}.{pm['flag']}", True)
        for p, rt in members.items():
            if rt.channels != pm["channels"][p]:
                out.append(
                    f"CHANNEL MISMATCH {p}: the cook put it in {rt.channels}, the shell reads {pm['channels'][p]}"
                )
                loaded = False
            if p in slots:
                cmds.setAttr(f"{node}.{slots[p][1]}", False)  # the separate map's flag off: the packed one is read
            out.append(f"TEXTURE {p}: {path.name} [{rt.channels}] {fmt} -> {pm['name']} ({key}); decoded={loaded}")
            decoded[p] = (fmt, loaded)
            done.add(p)
    for parameter, rt in runtime.items():
        if parameter in done:
            continue
        if parameter not in slots:
            out.append(f"NO SLOT for {parameter} ({rt.path.name}); the shell has no map attribute for it")
            continue
        attr, flag = slots[parameter]
        loaded = s.connect_file(node, attr, rt.path, _space_for(rt.format), out)
        cmds.setAttr(f"{node}.{flag}", True)
        out.append(f"TEXTURE {parameter}: {rt.path.name} [{rt.channels}] {rt.format} -> {attr}; decoded={loaded}")
        decoded[parameter] = (rt.format, loaded)
    return decoded


def log_menus(out: s.Log) -> None:
    """The main window's menu bar, for the startup-health record (Job_Orchestrator issue 72)."""
    try:
        menus = cmds.window("MayaWindow", q=True, menuArray=True) or []
        labels = [cmds.menu(m, q=True, label=True) for m in menus]
        out.append(f"MENUS {len(labels)}: {', '.join(labels)}")
    except Exception as e:  # noqa: BLE001 - a record, not a gate
        out.append(f"MENUS unreadable: {e!r}")


def run_check(quit_after: bool = True) -> dict:
    """The check. Returns a dict for a job caller; quits Maya afterwards when launched standalone."""
    out = s.Log(LOG, [f"shader {SHADER}", f"set {SET_DIR}", f"document {DOCUMENT or '<built from the set>'}"])
    result = {"ok": False, "dir": str(OUT), "log": str(LOG), "png": str(PNG), "decoded": {}, "techniques": []}
    try:
        log_menus(out)
        binding, runtime, _doc_dir, losses = build_material()
        out.append(f"BOUND {binding.material_type} as {binding.model}: {len(runtime)} texture(s); losses {losses}")
        cmds.file(new=True, force=True)
        sphere = cmds.polySphere(radius=1.0, subdivisionsAxis=64, subdivisionsHeight=64)[0]
        node, sg, techs = s.load_dx11_shader("hogshade_textures", SHADER, out)
        cmds.sets(sphere, e=True, forceElement=sg)
        for attr, fname in (("specularEnvTextureCube", "specular.dds"), ("diffuseEnvTextureCube", "irradiance.dds")):
            s.connect_file(node, attr, IBL / fname, "Raw", out)
        s.connect_file(node, "brdfTextureMap", LUT, "Raw", out)
        values = {k: (v if len(v) == 3 else v[0]) for k, v in binding.fields.items()}
        s.set_attrs(node, {**DEFAULTS, **values, **s.settings_from_env({})}, out)
        decoded = connect_textures(node, binding, runtime, out)
        light = cmds.directionalLight(name="key_light", intensity=2.0)
        light_tf = cmds.listRelatives(light, parent=True)[0]
        cmds.setAttr(f"{light_tf}.rotate", -35.0, 40.0, 0.0, type="double3")
        s.bind_light(node, "Light 0", light_tf, out)
        s.focus_viewport(out)
        cmds.select(sphere)
        cmds.viewFit()
        cmds.select(clear=True)
        s.capture(PNG, out)
        s.capture_debug_modes(node, PNG, out, DEBUG_MODES)
        formats = sorted({fmt for fmt, _ in decoded.values()})
        failed = sorted(p for p, (_, ok) in decoded.items() if not ok)
        out.append(f"FORMATS {formats}; decoded {len(decoded) - len(failed)}/{len(decoded)}; failed {failed}")
        result["decoded"] = {p: {"format": f, "loaded": ok} for p, (f, ok) in decoded.items()}
        result["techniques"] = list(techs or [])
        result["ok"] = bool(techs) and PNG.exists() and bool(decoded) and not failed
        s.finish(out, result["ok"], quit_after)
    except Exception:  # noqa: BLE001 - log whatever Maya or the library throws
        s.fail(out, quit_after)
    return result


def run() -> None:
    run_check(quit_after=True)


if os.environ.get("HOGSHADE_AS_JOB", "") != "1":
    cmds.evalDeferred(run, lowestPriority=True)
