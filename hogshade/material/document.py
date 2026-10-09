"""
HogShade: load a material document: parse, confine its paths, check its version, migrate an older one.
Package: hogshade/material/document

``load`` returns a raw ``Document``: the parent is a normalised path not yet followed (``resolve`` follows
it), values are as written. Every path a document names is relative, carries no ``..`` component, and
resolves inside the package root (the directory given, default the document's own), the same rule as
the Maya check's output directory (Docs/standards/failure-modes.md, entry 9). The string half of the rule
(``path_findings``) needs no file system, so ``validate`` applies it to a document built in memory too.
"""

from __future__ import annotations

import json
import logging as _logging
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from hogshade.material.model import Document, MaterialError
from hogshade.material.schema import type_of

_MODULE_NAME = "hogshade.material.document"
__version__ = "0.2.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

_REQUIRED = ("material_type", "material_type_version", "values")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def path_findings(value: Any, what: str) -> list[str]:
    """
    The string rules of a document path, as messages: a non-empty string, not absolute (POSIX root, drive
    letter, UNC), no ``..`` component. Empty when the string is admissible; root confinement needs a base
    directory and is ``confine``'s.
    """
    if not isinstance(value, str) or not value:
        return [f"{what} is a non-empty relative path, got {value!r}"]
    posix = PurePosixPath(value.replace("\\", "/"))
    if posix.is_absolute() or _DRIVE_RE.match(value) or value.startswith(("//", "\\\\")):
        return [f"{what} {value!r} is absolute; paths are relative to the document"]
    if ".." in posix.parts:
        return [f"{what} {value!r} climbs with '..'; paths stay inside the package root"]
    return []


def normalise(value: str) -> str:
    """The canonical spelling of an admissible document path: forward slashes, no ``./``, POSIX."""
    return PurePosixPath(value.replace("\\", "/")).as_posix()


def confine(value: Any, base_dir: Path, root: Path, what: str) -> tuple[str, Path]:
    """
    The normalised spelling and the absolute path a relative reference names, or ``MaterialError``: the
    string rules of ``path_findings``, then the joined path must lie inside ``root``.
    """
    problems = path_findings(value, what)
    if problems:
        raise MaterialError(problems[0])
    spelling = normalise(value)
    joined = (base_dir / Path(*PurePosixPath(spelling).parts)).resolve()
    root = root.resolve()
    if joined != root and root not in joined.parents:
        raise MaterialError(f"{what} {value!r} resolves outside the package root {root}")
    return spelling, joined


def migrate(
    values: dict[str, dict[str, Any]], migrations: tuple[dict[str, Any], ...], from_version: int
) -> dict[str, dict[str, Any]]:
    """
    Apply every migration from ``from_version`` upward to a copy of ``values``. ``rename`` moves a value,
    ``remove`` drops one, ``default`` records that a default changed and touches no value (defaults come
    from the schema at resolve time). The ops' shapes are the meta-check's.
    """
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in values.items()}
    for m in sorted(migrations, key=lambda m: m["from"]):
        if m["from"] < from_version:
            continue
        _LOGGER.debug(f"migrating a document from version {m['from']} to {m['to']} ({len(m['ops'])} ops)")
        for op in m["ops"]:
            kind = op["op"]
            if kind == "rename" and op["from"] in out:
                out[op["to"]] = out.pop(op["from"])
            elif kind == "remove":
                out.pop(op["name"], None)
    return out


def from_data(data: Any, path: Path | None = None, root: Path | None = None) -> Document:
    """
    A raw ``Document`` from parsed JSON. With ``path`` the paths are confined to ``root`` (default the
    document's directory) and stored in their normalised spelling; without one they are only checked as
    strings by ``validate``.
    """
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
        _LOGGER.info(f"{where}: migrated from {name} version {version} to {mtype.version}")
    ext = data.get("ext", {})
    if not isinstance(ext, dict):
        raise MaterialError(f"{where}: ext is an object of namespaces")
    parent = data.get("parent")
    if parent is not None and not isinstance(parent, str):
        raise MaterialError(f"{where}: parent is a relative path")
    for key in ("title", "doc"):
        if key in data and not isinstance(data[key], str):
            raise MaterialError(f"{where}: {key} is a string")
    provenance = data.get("provenance", [])
    if not isinstance(provenance, list):
        raise MaterialError(f"{where}: provenance is a list of {{source, note}} objects")
    doc = Document(
        material_type=name,
        material_type_version=mtype.version,
        parent=parent,
        values={k: (dict(v) if isinstance(v, dict) else v) for k, v in values.items()},
        ext=ext,
        path=path,
        root=root,
        title=data.get("title"),
        doc=data.get("doc"),
        provenance=[dict(p) if isinstance(p, dict) else p for p in provenance],
    )
    if path is not None:
        base_dir = path.parent
        root = (root or base_dir).resolve()
        doc.root = root
        if parent is not None:
            doc.parent, doc.parent_path = confine(parent, base_dir, root, "parent")
        for pname, value in doc.values.items():
            if isinstance(value, dict) and "texture" in value:
                value["texture"], _ = confine(value["texture"], base_dir, root, f"texture of {pname}")
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
    except (OSError, UnicodeDecodeError) as e:
        raise MaterialError(f"{path}: cannot read ({e})") from e
    except json.JSONDecodeError as e:
        raise MaterialError(f"{path}: not JSON ({e.msg} at line {e.lineno})") from e
    return from_data(data, path, Path(root).resolve() if root is not None else None)


if __name__ == "__main__":
    # smoke run: python -m hogshade.material.document <path.material.json> [root]
    _doc = load(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(_doc.material_type, _doc.material_type_version, "parent:", _doc.parent_path)
    for _name, _value in _doc.values.items():
        print(" ", _name, _value)
