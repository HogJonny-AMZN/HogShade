"""
HogShade: convert a material of one type into a document of another through a conversion table.
Package: hogshade/material/conversion

A table (``schema/conversions/<from>-to-<to>.json``) maps each source parameter to a target parameter with
a transform, or drops it with a reason. ``check_table`` is the coverage rule: every source parameter
appears exactly once, every target exists, every payload matches its transform. Comparison between
models is by conversion, never by a shared type (the design, question 2).
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from hogshade.material.resolution import resolve
from hogshade.material.schema import type_of, value_matches
from hogshade.material.types import Document, Finding, Loss, MaterialError, MaterialType, Resolved

_MODULE_NAME = "hogshade.material.conversion"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

TRANSFORMS = ("identity", "invert", "scale", "clamp", "constant")
_PAYLOAD = {"identity": (), "invert": (), "scale": ("by",), "clamp": ("range",), "constant": ("value",)}
_ENTRY_KEYS = ("from", "to", "transform", "field", "by", "range", "value")


def _tables_dir():
    return resources.files("hogshade.material") / "schema" / "conversions"


def table_names() -> list[str]:
    """The shipped conversion tables, as ``<from>-to-<to>``."""
    return sorted(p.name[: -len(".json")] for p in _tables_dir().iterdir() if p.name.endswith(".json"))


def load_table(from_type: str, to_type: str) -> dict[str, Any]:
    path = _tables_dir() / f"{from_type}-to-{to_type}.json"
    if not path.is_file():
        raise MaterialError(f"no conversion table from {from_type!r} to {to_type!r}; shipped: {table_names()}")
    return json.loads(path.read_text(encoding="utf-8"))


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def check_table(table: dict[str, Any], src: MaterialType, dst: MaterialType, where: str = "<table>") -> list[Finding]:
    """The coverage rule and the payload rule; empty when the table is complete and well formed."""
    out: list[Finding] = []
    if table.get("from") != src.name or table.get("to") != dst.name:
        out.append(
            Finding(
                where,
                "",
                f"table is from {table.get('from')!r} to {table.get('to')!r}, expected {src.name!r} to {dst.name!r}",
            )
        )
    seen: dict[str, int] = {}
    for entry in table.get("map", []):
        for key in entry:
            if key not in _ENTRY_KEYS:
                out.append(Finding(where, entry.get("from", ""), f"unknown entry key {key!r}"))
        name = entry.get("from")
        seen[name] = seen.get(name, 0) + 1
        sp = src.parameters.get(name)
        if sp is None:
            out.append(Finding(where, str(name), f"not a parameter of {src.name}"))
            continue
        tp = dst.parameters.get(entry.get("to"))
        if tp is None:
            out.append(Finding(where, name, f"target {entry.get('to')!r} is not a parameter of {dst.name}"))
            continue
        t = entry.get("transform")
        if t not in TRANSFORMS:
            out.append(Finding(where, name, f"transform {t!r} is not one of {TRANSFORMS}"))
            continue
        for key in _PAYLOAD[t]:
            if key not in entry:
                out.append(Finding(where, name, f"transform {t!r} carries {key!r}"))
        for key in ("by", "range", "value"):
            if key in entry and key not in _PAYLOAD[t]:
                out.append(Finding(where, name, f"transform {t!r} does not carry {key!r}"))
        if t == "scale" and not _is_number(entry.get("by")):
            out.append(Finding(where, name, "by is a number"))
        if t == "clamp":
            rng = entry.get("range")
            if not (isinstance(rng, list) and len(rng) == 2 and all(_is_number(v) for v in rng)):
                out.append(Finding(where, name, "range is [min, max]"))
        if t != "constant" and sp.type in ("bool", "enum"):
            out.append(Finding(where, name, "a bool or enum converts only through 'constant'"))
        if t == "constant" and "value" in entry and not value_matches(tp.type, entry["value"], tp.choices):
            out.append(Finding(where, name, f"constant {entry['value']!r} is not a {tp.type} for {tp.name!r}"))
        field = entry.get("field")
        if field is not None:
            if field != "strength" or not tp.strength:
                out.append(Finding(where, name, f"target {tp.name!r} does not admit field {field!r}"))
        elif t in ("scale", "clamp", "invert") and tp.type not in ("float", "int", "color3", "vector3"):
            out.append(Finding(where, name, f"transform {t!r} needs a numeric target, {tp.name!r} is {tp.type}"))
    for entry in table.get("dropped", []):
        name = entry.get("from")
        seen[name] = seen.get(name, 0) + 1
        if name not in src.parameters:
            out.append(Finding(where, str(name), f"dropped parameter is not a parameter of {src.name}"))
        if not isinstance(entry.get("reason"), str) or not entry.get("reason"):
            out.append(Finding(where, str(name), "a dropped parameter carries a reason"))
    for name in src.parameters:
        n = seen.get(name, 0)
        if n == 0:
            out.append(Finding(where, name, "neither mapped nor dropped"))
        elif n > 1:
            out.append(Finding(where, name, f"appears {n} times"))
    return out


def _apply(t: str, entry: dict[str, Any], factor: Any) -> Any:
    if t == "identity" or factor is None:
        return factor if t != "constant" else entry["value"]
    if t == "constant":
        return entry["value"]
    if t == "invert":
        return [1.0 - v for v in factor] if isinstance(factor, list) else 1.0 - factor
    if t == "scale":
        by = entry["by"]
        return [v * by for v in factor] if isinstance(factor, list) else factor * by
    if t == "clamp":
        lo, hi = entry["range"]
        clampf = lambda v: min(max(v, lo), hi)
        return [clampf(v) for v in factor] if isinstance(factor, list) else clampf(factor)
    raise MaterialError(f"unknown transform {t!r}")


def convert(obj: Document | Resolved, to_type: str) -> tuple[Document, list[Loss]]:
    """
    A raw document of ``to_type`` carrying the converted values, and the losses. A ``Document`` is resolved
    first, so the conversion sees every parameter.
    """
    res = resolve(obj) if isinstance(obj, Document) else obj
    src, dst = type_of(res.material_type), type_of(to_type)
    table = load_table(src.name, dst.name)
    findings = check_table(table, src, dst, f"{src.name}-to-{dst.name}")
    if findings:
        raise MaterialError("malformed conversion table: " + "; ".join(str(f) for f in findings))
    values: dict[str, dict[str, Any]] = {}
    for entry in table["map"]:
        source = res.values.get(entry["from"], {})
        target = values.setdefault(entry["to"], {})
        t = entry["transform"]
        field = entry.get("field")
        if field is not None:
            target[field] = _apply(t, entry, source.get("factor"))
            continue
        factor = _apply(t, entry, source.get("factor"))
        if factor is not None:
            target["factor"] = factor
        if t == "identity" and source.get("texture") is not None and dst.parameters[entry["to"]].texturable:
            target["texture"] = source["texture"]
            if source.get("blend") is not None:
                target["blend"] = source["blend"]
    # a target that received nothing (an unbound source texture, a None factor) or only a strength for an
    # unbound normal map is not written: the target type's default applies
    values = {name: v for name, v in values.items() if v and set(v) != {"strength"}}
    losses = [Loss(d["from"], d["reason"]) for d in table.get("dropped", [])]
    doc = Document(
        material_type=dst.name, material_type_version=dst.version, parent=None, values=values, ext=dict(res.ext)
    )
    return doc, losses
