"""
HogShade: Job_Orchestrator job that dumps Maya's own tangent frame of an OBJ, the parity fixture for
``hogshade.mikktspace`` (T3b, plan task 1).
Package: hogshade/jobs/maya_mikktspace_dump

MODULE mode on the headless ``hogshade_maya`` worker (mayapy; tangents need no viewport). Imports the OBJ as one
mesh, selects the MikkTSpace tangent basis when the mesh offers it (the ``tangentSpace`` enum names what Maya
2026 computes; the names are recorded either way), reads the per-corner tangent and binormal through the API and
writes ``<out>`` as an ``.npz``: ``face`` and ``vertex`` (the OBJ's face index and 0-based ``v`` index per corner,
which is how a test lines a corner up with ``wgpu_host.load_obj``), ``tangent`` (float16, unit, object space),
``sign`` (int8, +1 when ``cross(normal, tangent)`` points along Maya's binormal), and ``meta`` (a JSON string:
the OBJ, Maya's version, the tangent-space names, the one selected, a digest of the vertex positions in index
order so the test can prove the indexing matches). Runs standalone in mayapy too (the root on ``sys.path``,
then ``maya_mikktspace_dump.main({"obj": "content/shaderball/shaderBall.obj"})``), or through the orchestrator
with ``tools/bats/submit.py --module hogshade.jobs.maya_mikktspace_dump --param obj=<the OBJ>``.

Found on the first run (Maya 2026.3): the mesh's ``tangentSpace`` enum offers detectWindingRightHanded,
rightHanded, detectWindingLeftHanded and leftHanded, no MikkTSpace entry, so the fixture is Maya's default basis
and the parity test says how close that is to MikkTSpace, not that the two are one.
"""

from __future__ import annotations

import hashlib
import json
import logging as _logging
import time
from collections.abc import Sequence
from pathlib import Path

_MODULE_NAME = "hogshade.jobs.maya_mikktspace_dump"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = "tests/host/fixtures/{stem}_mikktspace.npz"

MANIFEST = {
    "name": "hogshade.maya_mikktspace_dump",
    "version": __version__,
    "worker_type": "hogshade_maya",
    "execution_mode": "HEADLESS",
    "execute_on_main_thread": False,
    "description": (
        "Dump Maya's tangent frame of an OBJ (the MikkTSpace basis when the mesh offers it) per face corner into an "
        ".npz under tests/host/fixtures/, the parity fixture hogshade.mikktspace is tested against."
    ),
    "parameters": {
        "obj": {"type": "path", "required": True, "description": "the OBJ, e.g. content/shaderball/shaderBall.obj"},
        "out": {"type": "path", "default": DEFAULT_OUT, "description": "the .npz to write ({stem} is the OBJ's)"},
    },
    "inputs": ["<obj>"],
    "outputs": ["<out>"],
    "returns": "ok, out, corners, tangent_spaces, selected, maya",
    "spec": "Docs/superpowers/specs/t3b-wgpu-textures.md",
}


def _maya_path(path: Path) -> str:
    """The one str() at the Maya boundary, forward slashes (``tools/maya/_session.maya_path``, which a job cannot
    import)."""
    return str(path).replace("\\", "/")


def _positions_digest(points: Sequence[Sequence[float]]) -> str:
    """sha256 of the vertex positions in index order, rounded to 1e-5: the test recomputes it from the OBJ."""
    import numpy as np

    arr = np.round(np.asarray(points, dtype=np.float64), 5).astype(np.float32)
    return hashlib.sha256(arr.tobytes()).hexdigest()


def dump(obj: Path, out: Path) -> dict:
    """The work, inside a Maya interpreter: import, select the basis, read the frame, write the fixture."""
    import maya.api.OpenMaya as om
    import numpy as np
    from maya import cmds

    t0 = time.perf_counter()
    cmds.file(new=True, force=True)
    if not cmds.pluginInfo("objExport", query=True, loaded=True):
        cmds.loadPlugin("objExport")
    # mo=0: one mesh for the whole file, so the OBJ's global v indices and face order survive the import
    cmds.file(_maya_path(obj), i=True, type="OBJ", ignoreVersion=True, options="mo=0", namespace=":")
    shapes = cmds.ls(type="mesh", long=True, noIntermediate=True)
    if len(shapes) != 1:
        raise RuntimeError(f"{obj.name} imported as {len(shapes)} meshes; the dump expects one (mo=0)")
    shape = shapes[0]
    names: list[str] = []
    selected = ""
    if cmds.attributeQuery("tangentSpace", node=shape, exists=True):
        names = (cmds.attributeQuery("tangentSpace", node=shape, listEnum=True) or [""])[0].split(":")
        mikk = [k for k, n in enumerate(names) if "mikk" in n.lower()]
        if mikk:
            cmds.setAttr(f"{shape}.tangentSpace", mikk[0])
        selected = names[cmds.getAttr(f"{shape}.tangentSpace")] if names else ""
    _LOGGER.info(f"{shape}: tangentSpace names {names or 'none'}; selected {selected or 'the default'}")

    sel = om.MSelectionList()
    sel.add(shape)
    dag = sel.getDagPath(0)
    fn = om.MFnMesh(dag)
    tangents = fn.getTangents(om.MSpace.kObject)
    binormals = fn.getBinormals(om.MSpace.kObject)
    normals = fn.getNormals(om.MSpace.kObject)
    points = fn.getPoints(om.MSpace.kObject)
    faces: list[int] = []
    verts: list[int] = []
    tans: list[tuple[float, float, float]] = []
    signs: list[int] = []
    it = om.MItMeshPolygon(dag)
    while not it.isDone():
        f = it.index()
        for k, v in enumerate(it.getVertices()):
            t = tangents[it.tangentIndex(k)]
            b = binormals[it.tangentIndex(k)]
            n = normals[it.normalIndex(k)]
            c = n ^ t  # cross(normal, tangent)
            faces.append(f)
            verts.append(v)
            tans.append((t.x, t.y, t.z))
            signs.append(1 if (c * b) >= 0.0 else -1)
        it.next()
    pts = [(p.x, p.y, p.z) for p in points]
    meta = {
        "obj": str(obj.relative_to(ROOT).as_posix()) if obj.is_relative_to(ROOT) else str(obj),
        "maya": cmds.about(installedVersion=True),
        "tangent_spaces": names,
        "selected": selected,
        "vertices": len(pts),
        "faces": fn.numPolygons,
        "corners": len(faces),
        "positions_sha256": _positions_digest(pts),
        "written": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        face=np.asarray(faces, dtype=np.int32),
        vertex=np.asarray(verts, dtype=np.int32),
        tangent=np.asarray(tans, dtype=np.float32).astype(np.float16),
        sign=np.asarray(signs, dtype=np.int8),
        meta=np.array(json.dumps(meta)),
    )
    _LOGGER.info(
        f"wrote {out} ({out.stat().st_size} bytes): {len(faces)} corners of {fn.numPolygons} faces, "
        f"{sum(1 for s in signs if s < 0)} mirrored, in {time.perf_counter() - t0:.1f} s"
    )
    return {"ok": True, "out": str(out), **{k: meta[k] for k in ("corners", "tangent_spaces", "selected", "maya")}}


def main(parameters: dict) -> dict:
    """Entry point the Maya worker calls."""
    raw = str(parameters.get("obj", ""))
    if not raw:
        raise ValueError("obj is required")
    for key in ("obj", "out"):
        if ".." in Path(str(parameters.get(key) or "")).parts:
            raise ValueError(f"{key} climbs with '..'; a job path stays inside the workspace")
    obj = Path(raw)
    obj = obj if obj.is_absolute() else ROOT / obj
    out_raw = str(parameters.get("out") or DEFAULT_OUT).replace("{stem}", obj.stem)
    out = Path(out_raw)
    out = out if out.is_absolute() else ROOT / out
    if not out.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"out {out_raw!r} resolves outside the workspace {ROOT}; the fixture stays in the repository")
    _LOGGER.info(f"maya_mikktspace_dump: {obj} -> {out}")
    return dump(obj, out)


if __name__ == "__main__":
    print(json.dumps(MANIFEST, indent=2))
