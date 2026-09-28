"""
HogShade: load a material document: parse, confine its paths, check its version, migrate an older one.
Package: hogshade/material/document

``load`` returns a raw ``Document``: the parent is a normalised path not yet followed (``resolve`` follows
it), values are as written. Every path a document names is relative, carries no ``..`` component, and
resolves inside the package root (the directory given, default the document's own), the same rule as
the Maya check's output directory (Docs/standards/failure-modes.md, entry 9).
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from hogshade.material.schema import type_of
from hogshade.material.types import Document, MaterialError

_MODULE_NAME = "hogshade.material.document"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

_REQUIRED = ("material_type", "material_type_version", "values")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def confine(value: Any, base_dir: Path, root: Path, what: str) -> Path:
    """
    The absolute path a relative reference names, or ``MaterialError``: absolute paths, drive letters,
    UNC paths and any ``..`` component are refused, and the joined path must lie inside ``root``.
    """
    if not isinstance(value, str) or not value:
        raise MaterialError(f"{what} is a non-empty relative path, got {value!r}")
    posix = PurePosixPath(value.replace("\\", "/"))
    if posix.is_absolute() or _DRIVE_RE.match(value) or value.startswith(("//", "\\\\")):
        raise MaterialError(f"{what} {value!r} is absolute; paths are relative to the document")
    if ".." in posix.parts:
        raise MaterialError(f"{what} {value!r} climbs with '..'; paths stay inside the package root")
    joined = (base_dir / Path(*posix.parts)).resolve()
    root = root.resolve()
    if joined != root and root not in joined.parents:
        raise MaterialError(f"{what} {value!r} resolves outside the package root {root}")
    return joined


def migrate(
    values: dict[str, dict[str, Any]], migrations: tuple[dict[str, Any], ...], from_version: int
) -> dict[str, dict[str, Any]]:
    """Apply every migration from ``from_version`` upward to a copy of ``values``."""
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in values.items()}
    for m in sorted(migrations, key=lambda m: m["from"]):
        if m["from"] < from_version:
            continue
        for op in m["ops"]:
            kind = op["op"]
            if kind == "rename" and op["from"] in out:
                out[op["to"]] = out.pop(op["from"])
            elif kind == "remove":
                out.pop(op["name"], None)
            elif kind == "default":
                pass  # defaults come from the schema; the op documents that a default changed
    return out


def from_data(data: Any, path: Path | None = None, root: Path | None = None) -> Document:
    """A raw ``Document`` from parsed JSON; the path rules need ``path`` (and ``root``) to check anything."""
    where = str(path) if path else "<document>"
    if not isinstance(data, dict):
        raise MaterialError(f"{where}: a material document is a JSON object")
    for key in _REQUIRED:
        if key not in data:
            raise MaterialError(f"{where}: missing field {key!r}")
    name = data["material_type"]
    if not isinstance(name, str):
        raise MaterialError(f"{where}: material_type is a string")
    mtype = type_of(name)  # MaterialError on an unknown type
    version = data["material_type_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise MaterialError(f"{where}: material_type_version is an integer from 1")
    if version > mtype.version:
        raise MaterialError(f"{where}: written against {name} version {version}, this library knows {mtype.version}")
    values = data["values"]
    if not isinstance(values, dict):
        raise MaterialError(f"{where}: values is an object")
    if version < mtype.version:
        values = migrate(values, mtype.migrations, version)
    ext = data.get("ext", {})
    if not isinstance(ext, dict):
        raise MaterialError(f"{where}: ext is an object of namespaces")
    parent = data.get("parent")
    if parent is not None and not isinstance(parent, str):
        raise MaterialError(f"{where}: parent is a relative path")
    doc = Document(
        material_type=name,
        material_type_version=mtype.version,
        parent=parent,
        values={k: (dict(v) if isinstance(v, dict) else v) for k, v in values.items()},
        ext=ext,
        path=path,
        root=root,
    )
    if path is not None:
        base_dir = path.parent
        root = (root or base_dir).resolve()
        doc.root = root
        if parent is not None:
            doc.parent_path = confine(parent, base_dir, root, "parent")
        for pname, value in doc.values.items():
            if isinstance(value, dict) and "texture" in value:
                confine(value["texture"], base_dir, root, f"texture of {pname}")
    return doc


def load(path: str | Path, root: str | Path | None = None) -> Document:
    """
    Parse a ``*.material.json``, confine its paths, check and migrate its version. Raw: the parent is not
    followed. ``root`` is the package root every path must stay inside; default the document's directory.
    """
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise MaterialError(f"no such document: {path}") from e
    except json.JSONDecodeError as e:
        raise MaterialError(f"{path}: not JSON ({e.msg} at line {e.lineno})") from e
    return from_data(data, path, Path(root).resolve() if root is not None else None)
