"""
HogShade: validate a material document (raw) or a resolved material against its type.
Package: hogshade/material/validation

Raw: unknown keys, value shapes and types, ranges, colour spaces, blend, strength, overridable, the string
rules of every path. Resolved: completeness and the cross-parameter rules. Never raises; every problem is
a ``Finding``.
"""

from __future__ import annotations

import logging as _logging
from typing import Any

from hogshade.material.document import path_findings
from hogshade.material.model import BLENDS, VALUE_KEYS, Document, Finding, MaterialError, ParameterDef, Resolved
from hogshade.material.schema import type_of

_MODULE_NAME = "hogshade.material.validation"
__version__ = "0.1.0"
__updated__ = "2026-09-27"
_LOGGER = _logging.getLogger(_MODULE_NAME)

_BLENDABLE_WIDGETS = ("color", "slider")


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _factor_findings(where: str, p: ParameterDef, factor: Any) -> list[Finding]:
    out: list[Finding] = []
    if p.type == "texture":
        return [Finding(where, p.name, "a texture parameter takes no factor")]
    if p.type in ("float", "int"):
        if not _is_number(factor) or (p.type == "int" and not isinstance(factor, int)):
            return [Finding(where, p.name, f"factor {factor!r} is not {p.type}")]
        if p.range is not None and not p.soft and not (p.range[0] <= factor <= p.range[1]):
            out.append(Finding(where, p.name, f"factor {factor!r} outside range {list(p.range)}"))
    elif p.type == "bool":
        if not isinstance(factor, bool):
            out.append(Finding(where, p.name, f"factor {factor!r} is not a bool"))
    elif p.type == "enum":
        if factor not in p.choices:
            out.append(Finding(where, p.name, f"factor {factor!r} is not one of {list(p.choices)}"))
    elif p.type in ("color3", "vector3"):
        if not (isinstance(factor, (list, tuple)) and len(factor) == 3 and all(_is_number(v) for v in factor)):
            out.append(Finding(where, p.name, f"factor {factor!r} is not three numbers"))
        elif p.range is not None and not p.soft and not all(p.range[0] <= v <= p.range[1] for v in factor):
            out.append(Finding(where, p.name, f"a component of {factor!r} is outside range {list(p.range)}"))
    return out


def _value_findings(where: str, p: ParameterDef, value: Any, has_parent: bool) -> list[Finding]:
    if not isinstance(value, dict):
        return [Finding(where, p.name, "a value is an object with factor, texture, blend, strength")]
    out: list[Finding] = []
    for key in value:
        if key not in VALUE_KEYS:
            out.append(Finding(where, p.name, f"unknown value key {key!r}"))
    has_factor, has_texture = "factor" in value, "texture" in value
    if not has_factor and not has_texture:
        out.append(Finding(where, p.name, "a value carries factor, texture or both"))
    if has_factor:
        out.extend(_factor_findings(where, p, value["factor"]))
    if has_texture:
        if not p.texturable:
            out.append(Finding(where, p.name, "not texturable: the schema gives it no colour space"))
        else:
            out.extend(Finding(where, p.name, m) for m in path_findings(value["texture"], "texture"))
    if "blend" in value:
        if not (has_factor and has_texture):
            out.append(Finding(where, p.name, "blend only with both factor and texture"))
        elif p.widget not in _BLENDABLE_WIDGETS:
            out.append(
                Finding(where, p.name, f"blend only on a {_BLENDABLE_WIDGETS[0]} or {_BLENDABLE_WIDGETS[1]} parameter")
            )
        elif value["blend"] not in BLENDS:
            out.append(Finding(where, p.name, f"blend {value['blend']!r} is not one of {BLENDS}"))
    if "strength" in value:
        if not p.strength:
            out.append(Finding(where, p.name, "strength only on a normal-map parameter"))
        elif not has_texture:
            out.append(Finding(where, p.name, "strength only with a texture"))
        elif not _is_number(value["strength"]) or value["strength"] < 0:
            out.append(Finding(where, p.name, "strength is a number at or above 0"))
    if has_parent and not p.overridable:
        out.append(Finding(where, p.name, "not overridable: a child document may not set it"))
    return out


def validate(obj: Document | Resolved) -> list[Finding]:
    """Every finding on a raw document or a resolved material; empty means valid."""
    if isinstance(obj, Document):
        return _validate_document(obj)
    if isinstance(obj, Resolved):
        return _validate_resolved(obj)
    return [Finding("<object>", "", f"cannot validate a {type(obj).__name__}")]


def _validate_document(doc: Document) -> list[Finding]:
    where = str(doc.path) if doc.path else "<document>"
    try:
        mtype = type_of(doc.material_type)
    except MaterialError as e:  # an in-memory Document with an unknown type; validate never raises
        return [Finding(where, "", str(e))]
    out: list[Finding] = []
    if doc.parent is not None:
        out.extend(Finding(where, "", m) for m in path_findings(doc.parent, "parent"))
    for name, value in doc.values.items():
        p = mtype.parameters.get(name)
        if p is None:
            out.append(Finding(where, name, f"not a parameter of {mtype.name}"))
            continue
        out.extend(_value_findings(where, p, value, doc.parent is not None))
    for ns, block in doc.ext.items():
        if not isinstance(ns, str) or not isinstance(block, dict):
            out.append(Finding(where, "ext", f"ext.{ns} is an object"))
    return out


def _validate_resolved(res: Resolved) -> list[Finding]:
    where = str(res.chain[0]) if res.chain else "<resolved>"
    try:
        mtype = type_of(res.material_type)
    except MaterialError as e:
        return [Finding(where, "", str(e))]
    out: list[Finding] = []
    for name, p in mtype.parameters.items():
        value = res.values.get(name)
        if value is None:
            out.append(Finding(where, name, "missing after resolution"))
            continue
        if not isinstance(value, dict):
            out.append(Finding(where, name, "a resolved value is an object with factor, texture, blend"))
            continue
        if p.type != "texture" and value.get("factor") is None:
            out.append(Finding(where, name, "no factor and no default"))
        elif value.get("factor") is not None:
            out.extend(_factor_findings(where, p, value["factor"]))
    for name in res.values:
        if name not in mtype.parameters:
            out.append(Finding(where, name, f"not a parameter of {mtype.name}"))
    # mask cuts coverage at 0.5: with no opacity texture and a constant factor below the cut, nothing renders.
    # A constant at or above the cut is a no-op and stays silent, since mask is the type's default.
    alpha_value = res.values.get("alpha_mode")
    alpha = alpha_value.get("factor") if isinstance(alpha_value, dict) else None
    opacity = res.values.get("geometry_opacity")
    opacity = opacity if isinstance(opacity, dict) else {}
    factor = opacity.get("factor")
    if alpha == "mask" and opacity.get("texture") is None and _is_number(factor) and factor < 0.5:
        out.append(
            Finding(where, "alpha_mode", f"mask with a constant opacity {factor} below the cut: nothing renders")
        )
    return out
