"""
HogShade: resolve a material document: follow the parent chain, apply values child over parent, then the
type's defaults; merge extension blocks child over parent per namespace.
Package: hogshade/material/resolution

The one place the parent chain is followed. A cycle and a parent of another type are ``MaterialError``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hogshade.material.document import load
from hogshade.material.schema import type_of
from hogshade.material.types import Document, MaterialError, MaterialType, Resolved

_MODULE_NAME = "hogshade.material.resolution"
__version__ = "0.1.0"
__updated__ = "2026-09-27"


def defaults_of(mtype: MaterialType) -> dict[str, dict[str, Any]]:
    """Every parameter's value when nothing sets it: the default factor (none for a texture), no texture."""
    out: dict[str, dict[str, Any]] = {}
    for name, p in mtype.parameters.items():
        value: dict[str, Any] = {"factor": None if p.type == "texture" else p.default, "texture": None, "blend": None}
        if p.strength:
            value["strength"] = 1.0
        out[name] = value
    return out


def chain_of(doc: Document, root: Path | None = None) -> list[Document]:
    """The documents from ``doc`` up to the root ancestor, child first."""
    chain = [doc]
    seen: set[Path] = set()
    if doc.path is not None:
        seen.add(doc.path.resolve())
    current = doc
    while current.parent is not None:
        if current.parent_path is None:
            raise MaterialError(f"{current.path or '<document>'}: a parent needs a document path to resolve against")
        parent_path = current.parent_path
        if parent_path in seen:
            raise MaterialError(f"parent cycle through {parent_path}")
        parent = load(parent_path, root or current.root)
        if parent.material_type != doc.material_type:
            raise MaterialError(
                f"{parent_path}: parent is a {parent.material_type}, the child a {doc.material_type}; a chain resolves to one type"
            )
        seen.add(parent_path)
        chain.append(parent)
        current = parent
    return chain


def _merge_value(into: dict[str, Any], value: dict[str, Any]) -> None:
    for key, v in value.items():
        into[key] = v


def resolve(doc: Document, root: Path | None = None) -> Resolved:
    """The full parameter set: defaults, then each ancestor's values from the root ancestor down to ``doc``."""
    mtype = type_of(doc.material_type)
    chain = chain_of(doc, root)
    values = defaults_of(mtype)
    ext: dict[str, Any] = {}
    for d in reversed(chain):
        for name, value in d.values.items():
            if name in values and isinstance(value, dict):
                _merge_value(values[name], value)
            elif name not in values:
                values[name] = dict(value) if isinstance(value, dict) else {"factor": value}  # validate() reports it
        for ns, block in d.ext.items():
            if isinstance(block, dict):
                ext.setdefault(ns, {}).update(block)
            else:
                ext[ns] = block
    paths = tuple(d.path for d in chain if d.path is not None)
    return Resolved(material_type=mtype.name, version=mtype.version, values=values, ext=ext, chain=paths)
