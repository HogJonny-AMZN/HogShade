"""
HogShade: the material-type schema files: read from package data, checked for shape, registered by name.
Package: hogshade/material/schema

A material-type file is JSON with ``material_type``, ``version``, ``title``, ``groups``, ``parameters`` and
``migrations``; every parameter carries every field the S1 spec lists. An opt-in group is the one whose
``<group>_enabled`` bool exists; ``MaterialType.optional_groups`` is derived from that. ``check_type_data`` is the meta-check (a hundred lines of our own, no JSON Schema dependency);
``type_of`` refuses a file the meta-check faults.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

from hogshade.material.types import (
    COLOUR_SPACES,
    PARAMETER_TYPES,
    WIDGETS,
    Finding,
    MaterialError,
    MaterialType,
    ParameterDef,
)

_MODULE_NAME = "hogshade.material.schema"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

SUFFIX = ".material-type.json"
_REQUIRED_TOP = ("material_type", "version", "title", "groups", "parameters", "migrations")
_ENABLED_SUFFIX = "_enabled"
_REQUIRED_PARAM = ("type", "group", "widget", "semantic", "overridable", "tier", "hosts", "doc")
_OPTIONAL_PARAM = ("default", "range", "soft", "colour_space", "choices", "strength")
_NUMERIC = ("float", "int")
_MIGRATION_OPS = ("rename", "default", "remove")


def _schema_dir():
    return resources.files("hogshade.material") / "schema"


def types() -> list[str]:
    """The names of the shipped material types, from the package data."""
    return sorted(p.name[: -len(SUFFIX)] for p in _schema_dir().iterdir() if p.name.endswith(SUFFIX))


def read_type_data(name: str) -> dict[str, Any]:
    """The raw JSON of a shipped type file; ``MaterialError`` when there is no such type."""
    path = _schema_dir() / f"{name}{SUFFIX}"
    if not path.is_file():
        raise MaterialError(f"unknown material type {name!r}; shipped: {types()}")
    return json.loads(path.read_text(encoding="utf-8"))


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def value_matches(ptype: str, value: Any, choices: tuple[str, ...] | list[str]) -> bool:
    """Whether a literal (a default, a constant) is a value of the parameter type."""
    if ptype in _NUMERIC:
        return _is_number(value)
    if ptype == "bool":
        return isinstance(value, bool)
    if ptype == "enum":
        return isinstance(value, str) and value in choices
    if ptype in ("color3", "vector3"):
        return isinstance(value, list) and len(value) == 3 and all(_is_number(v) for v in value)
    return False


def check_type_data(data: dict[str, Any], where: str = "<type>") -> list[Finding]:
    """The meta-check of a material-type file's shape. Empty when the file is well formed."""
    out: list[Finding] = []
    if not isinstance(data, dict):
        return [Finding(where, "", "a material-type file is a JSON object")]
    for key in _REQUIRED_TOP:
        if key not in data:
            out.append(Finding(where, "", f"missing top-level field {key!r}"))
    if out:
        return out
    if not (isinstance(data["version"], int) and not isinstance(data["version"], bool) and data["version"] >= 1):
        out.append(Finding(where, "", "version is an integer from 1"))
    groups = data["groups"]
    if not (isinstance(groups, list) and groups and all(isinstance(g, str) for g in groups)):
        out.append(Finding(where, "", "groups is a non-empty list of names"))
        groups = []
    params = data["parameters"]
    if not isinstance(params, dict) or not params:
        return out + [Finding(where, "", "parameters is a non-empty object")]
    for name, p in params.items():
        if not isinstance(p, dict):
            out.append(Finding(where, name, "a parameter is an object"))
            continue
        for key in _REQUIRED_PARAM:
            if key not in p:
                out.append(Finding(where, name, f"missing field {key!r}"))
        for key in p:
            if key not in _REQUIRED_PARAM and key not in _OPTIONAL_PARAM:
                out.append(Finding(where, name, f"unknown field {key!r}"))
        ptype = p.get("type")
        if ptype not in PARAMETER_TYPES:
            out.append(Finding(where, name, f"type {ptype!r} is not one of {PARAMETER_TYPES}"))
            continue
        if p.get("group") not in groups:
            out.append(Finding(where, name, f"group {p.get('group')!r} is not declared in groups"))
        if p.get("widget") not in WIDGETS:
            out.append(Finding(where, name, f"widget {p.get('widget')!r} is not one of {WIDGETS}"))
        if not isinstance(p.get("overridable"), bool):
            out.append(Finding(where, name, "overridable is a bool"))
        if not isinstance(p.get("hosts"), dict) or not all(isinstance(v, str) for v in p.get("hosts", {}).values()):
            out.append(Finding(where, name, "hosts is an object of host name to note"))
        if not isinstance(p.get("doc"), str) or not p.get("doc"):
            out.append(Finding(where, name, "doc is a sentence"))
        choices = p.get("choices", [])
        if ptype == "enum" and not (isinstance(choices, list) and choices and all(isinstance(c, str) for c in choices)):
            out.append(Finding(where, name, "an enum carries choices"))
        if ptype == "texture":
            if "default" in p:
                out.append(Finding(where, name, "a texture parameter has no default factor"))
        elif "default" not in p:
            out.append(Finding(where, name, "missing field 'default'"))
        elif not value_matches(ptype, p["default"], choices):
            out.append(Finding(where, name, f"default {p['default']!r} does not match type {ptype!r}"))
        rng = p.get("range")
        if ptype in _NUMERIC:
            if not (isinstance(rng, list) and len(rng) == 2 and all(_is_number(v) for v in rng) and rng[0] <= rng[1]):
                out.append(Finding(where, name, "a numeric parameter carries range [min, max]"))
            elif (
                "default" in p
                and _is_number(p["default"])
                and not p.get("soft", False)
                and not (rng[0] <= p["default"] <= rng[1])
            ):
                out.append(Finding(where, name, "default outside range"))
        elif rng is not None and ptype not in ("color3", "vector3"):
            out.append(Finding(where, name, "range only on numbers, colours and vectors"))
        cs = p.get("colour_space")
        if ptype == "texture" and cs is None:
            out.append(Finding(where, name, "a texture parameter carries colour_space"))
        if cs is not None and cs not in COLOUR_SPACES:
            out.append(Finding(where, name, f"colour_space {cs!r} is not one of {COLOUR_SPACES}"))
        if cs is not None and ptype in ("int", "bool", "enum"):
            out.append(Finding(where, name, "an int, bool or enum cannot be textured"))
        if p.get("strength", False) and not (ptype == "texture" and p.get("semantic") == "normal_ts"):
            out.append(Finding(where, name, "strength is only for a normal-map texture"))
    for name, p in params.items():
        # the opt-in rule: a parameter named <group>_enabled is the bool that switches that group on
        if isinstance(p, dict) and name.endswith(_ENABLED_SUFFIX):
            group = name[: -len(_ENABLED_SUFFIX)]
            if group not in groups:
                out.append(Finding(where, name, f"an enabled flag names a declared group; {group!r} is not one"))
            elif p.get("type") != "bool" or p.get("group") != group:
                out.append(Finding(where, name, f"the enabled flag of group {group!r} is a bool in that group"))
    migrations = data["migrations"]
    if not isinstance(migrations, list):
        out.append(Finding(where, "", "migrations is a list"))
    else:
        for i, m in enumerate(migrations):
            ok = isinstance(m, dict) and isinstance(m.get("from"), int) and m.get("to") == m.get("from", 0) + 1
            ok = (
                ok
                and isinstance(m.get("ops"), list)
                and all(isinstance(o, dict) and o.get("op") in _MIGRATION_OPS for o in m.get("ops", []))
            )
            if not ok:
                out.append(
                    Finding(where, "", f"migration {i} is {{from: n, to: n+1, ops: [rename|default|remove ...]}}")
                )
    return out


def parse_type_data(data: dict[str, Any], where: str = "<type>") -> MaterialType:
    """A ``MaterialType`` from well-formed data; ``MaterialError`` listing the findings otherwise."""
    findings = check_type_data(data, where)
    if findings:
        raise MaterialError("malformed material type: " + "; ".join(str(f) for f in findings))
    params: dict[str, ParameterDef] = {}
    for name, p in data["parameters"].items():
        rng = p.get("range")
        params[name] = ParameterDef(
            name=name,
            type=p["type"],
            group=p["group"],
            widget=p["widget"],
            semantic=p["semantic"],
            overridable=p["overridable"],
            tier=p["tier"],
            hosts=dict(p["hosts"]),
            doc=p["doc"],
            default=p.get("default"),
            range=(float(rng[0]), float(rng[1])) if rng is not None else None,
            soft=bool(p.get("soft", False)),
            colour_space=p.get("colour_space"),
            choices=tuple(p.get("choices", [])),
            strength=bool(p.get("strength", False)),
        )
    return MaterialType(
        name=data["material_type"],
        version=data["version"],
        title=data["title"],
        groups=tuple(data["groups"]),
        optional_groups=tuple(
            name[: -len(_ENABLED_SUFFIX)] for name in data["parameters"] if name.endswith(_ENABLED_SUFFIX)
        ),
        parameters=params,
        migrations=tuple(data["migrations"]),
    )


@cache
def type_of(name: str) -> MaterialType:
    """A shipped material type by name, meta-checked once and cached."""
    return parse_type_data(read_type_data(name), f"{name}{SUFFIX}")
