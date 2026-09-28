"""
HogShade: the material-type schema files: read from package data, checked for shape, registered by name.
Package: hogshade/material/schema

A material-type file is JSON with ``material_type``, ``version``, ``title``, ``groups``, ``parameters`` and
``migrations``; every parameter carries every field the S1 spec lists. An opt-in group is the one whose
``<group>_enabled`` bool exists; ``MaterialType.optional_groups`` is derived from that. ``check_type_data``
is the meta-check (a hundred lines of our own, no JSON Schema dependency); ``type_of`` refuses a file the
meta-check faults.
"""

from __future__ import annotations

import json
import logging as _logging
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

from hogshade.material.model import (
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
_LOGGER = _logging.getLogger(_MODULE_NAME)

SUFFIX = ".material-type.json"
_REQUIRED_TOP = ("material_type", "version", "title", "groups", "parameters", "migrations")
_ENABLED_SUFFIX = "_enabled"
_REQUIRED_PARAM = ("type", "group", "widget", "semantic", "overridable", "tier", "hosts", "doc")
_OPTIONAL_PARAM = ("default", "range", "soft", "colour_space", "choices", "strength")
_NUMERIC = ("float", "int")
#: Migration ops and the keys each carries.
MIGRATION_OPS = {"rename": ("from", "to"), "default": ("name", "value"), "remove": ("name",)}


def _schema_dir() -> Traversable:
    return resources.files("hogshade.material") / "schema"


def types() -> list[str]:
    """The names of the shipped material types, from the package data."""
    return sorted(p.name[: -len(SUFFIX)] for p in _schema_dir().iterdir() if p.name.endswith(SUFFIX))


def read_json(path: Traversable, what: str) -> Any:
    """Parsed JSON from a package-data file; ``MaterialError`` names the file when it is not JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MaterialError(f"{what} {path.name} is not JSON ({e.msg} at line {e.lineno})") from e


def read_type_data(name: str) -> dict[str, Any]:
    """The raw JSON of a shipped type file; ``MaterialError`` when there is no such type."""
    shipped = types()
    if name not in shipped:  # the registry check: a document's material_type never becomes a path
        raise MaterialError(f"unknown material type {name!r}; shipped: {shipped}")
    return read_json(_schema_dir() / f"{name}{SUFFIX}", "material type")


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def value_matches(ptype: str, value: Any, choices: tuple[str, ...] | list[str]) -> bool:
    """Whether a literal (a default, a constant) is a value of the parameter type."""
    if ptype == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if ptype == "float":
        return _is_number(value)
    if ptype == "bool":
        return isinstance(value, bool)
    if ptype == "enum":
        return isinstance(value, str) and value in choices
    if ptype in ("color3", "vector3"):
        return isinstance(value, list) and len(value) == 3 and all(_is_number(v) for v in value)
    return False


def _check_parameter(where: str, name: str, p: dict[str, Any], groups: list[str]) -> list[Finding]:
    out: list[Finding] = []
    for key in _REQUIRED_PARAM:
        if key not in p:
            out.append(Finding(where, name, f"missing field {key!r}"))
    for key in p:
        if key not in _REQUIRED_PARAM and key not in _OPTIONAL_PARAM:
            out.append(Finding(where, name, f"unknown field {key!r}"))
    ptype = p.get("type")
    if ptype not in PARAMETER_TYPES:
        out.append(Finding(where, name, f"type {ptype!r} is not one of {PARAMETER_TYPES}"))
        return out
    if p.get("group") not in groups:
        out.append(Finding(where, name, f"group {p.get('group')!r} is not declared in groups"))
    if p.get("widget") not in WIDGETS:
        out.append(Finding(where, name, f"widget {p.get('widget')!r} is not one of {WIDGETS}"))
    if not isinstance(p.get("semantic"), str) or not p.get("semantic"):
        out.append(Finding(where, name, "semantic is a name"))
    if not isinstance(p.get("overridable"), bool):
        out.append(Finding(where, name, "overridable is a bool"))
    tier = p.get("tier")
    if not ((isinstance(tier, int) and not isinstance(tier, bool)) or (isinstance(tier, str) and tier)):
        out.append(Finding(where, name, "tier is an integer or a named tier"))
    if not isinstance(p.get("soft", False), bool):
        out.append(Finding(where, name, "soft is a bool"))
    hosts = p.get("hosts")
    if not isinstance(hosts, dict) or not all(isinstance(v, str) for v in hosts.values()):
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
    range_ok = isinstance(rng, list) and len(rng) == 2 and all(_is_number(v) for v in rng) and rng[0] <= rng[1]
    default = p.get("default")
    if ptype in _NUMERIC:
        if not range_ok:
            out.append(Finding(where, name, "a numeric parameter carries range [min, max]"))
        elif _is_number(default) and not p.get("soft", False) and not (rng[0] <= default <= rng[1]):
            out.append(Finding(where, name, "default outside range"))
    elif ptype in ("color3", "vector3"):
        if rng is not None and not range_ok:
            out.append(Finding(where, name, "range is [min, max]"))
        elif range_ok and value_matches(ptype, default, []) and not all(rng[0] <= v <= rng[1] for v in default):
            out.append(Finding(where, name, "a default component is outside range"))
    elif rng is not None:
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
    return out


def _check_migration(where: str, i: int, m: Any) -> list[Finding]:
    shape = f"migration {i} is {{from: n, to: n+1, ops: [...]}}"
    if not (isinstance(m, dict) and isinstance(m.get("from"), int) and m.get("to") == m.get("from", 0) + 1):
        return [Finding(where, "", shape)]
    if not isinstance(m.get("ops"), list):
        return [Finding(where, "", shape)]
    out: list[Finding] = []
    for j, op in enumerate(m["ops"]):
        kind = op.get("op") if isinstance(op, dict) else None
        if kind not in MIGRATION_OPS:
            out.append(Finding(where, "", f"migration {i} op {j}: op is one of {sorted(MIGRATION_OPS)}"))
            continue
        for key in MIGRATION_OPS[kind]:
            # a name key is a non-empty string; the default op's value is any JSON value, but present
            missing = key not in op if key == "value" else not (isinstance(op.get(key), str) and op.get(key))
            if missing:
                out.append(Finding(where, "", f"migration {i} op {j}: {kind!r} carries {key!r}"))
    return out


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
        out.extend(_check_parameter(where, name, p, groups))
        # the opt-in rule: a parameter named <group>_enabled is the bool that switches that group on
        if name.endswith(_ENABLED_SUFFIX):
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
            out.extend(_check_migration(where, i, m))
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
    """A shipped material type by name, meta-checked once and cached. Callers never mutate what it returns."""
    return parse_type_data(read_type_data(name), f"{name}{SUFFIX}")


if __name__ == "__main__":
    # smoke run: list the shipped types and meta-check each
    for _name in types():
        _findings = check_type_data(read_type_data(_name), _name)
        _mtype = type_of(_name) if not _findings else None
        print(_name, len(_mtype.parameters) if _mtype else "FAULTY", *(str(f) for f in _findings))
