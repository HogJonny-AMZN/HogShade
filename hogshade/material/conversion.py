"""
HogShade: convert a material of one type into a document of another through a conversion table.
Package: hogshade/material/conversion

A table (``schema/conversions/<from>-to-<to>.json``) maps each source parameter to a target parameter with
a transform, or drops it with a reason. ``check_table`` is the coverage rule: every source parameter is
mapped once, consulted by a ``when`` condition, or dropped; every target exists; every payload matches its
transform; a non-constant transform keeps the type. A conditional ``constant`` carries ``when``: a value
of its own source, or an object of source parameter names to values, all of which must hold; a source may
carry one entry per distinct condition. Comparison between models is by conversion, never by a shared
type (the design, question 2).
"""

from __future__ import annotations

import copy
import itertools
import logging as _logging
from collections.abc import Callable
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

from hogshade.material.model import Document, Finding, Loss, MaterialError, MaterialType, Resolved
from hogshade.material.resolution import resolve
from hogshade.material.schema import read_json, type_of, value_matches
from hogshade.material.validation import validate

_MODULE_NAME = "hogshade.material.conversion"
__version__ = "0.1.1"
__updated__ = "2026-09-28"
_LOGGER = _logging.getLogger(_MODULE_NAME)

TRANSFORMS = ("identity", "invert", "scale", "clamp", "constant")
_PAYLOAD = {"identity": (), "invert": (), "scale": ("by",), "clamp": ("range",), "constant": ("value",)}
_ENTRY_KEYS = ("from", "to", "transform", "field", "by", "range", "value", "when")
_NUMERIC_TARGETS = ("float", "int", "color3", "vector3")


def _tables_dir() -> Traversable:
    return resources.files("hogshade.material") / "schema" / "conversions"


def table_names() -> list[str]:
    """The shipped conversion tables, as ``<from>-to-<to>``."""
    return sorted(p.name[: -len(".json")] for p in _tables_dir().iterdir() if p.name.endswith(".json"))


def load_table(from_type: str, to_type: str) -> dict[str, Any]:
    """The raw JSON of the shipped table for the pair; ``MaterialError`` when there is none."""
    name = f"{from_type}-to-{to_type}"
    shipped = table_names()
    if name not in shipped:  # the registry check: caller strings never become a path
        raise MaterialError(f"no conversion table from {from_type!r} to {to_type!r}; shipped: {shipped}")
    return read_json(_tables_dir() / f"{name}.json", "conversion table")


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _same(a: Any, b: Any) -> bool:
    """Equality that keeps bool and int apart (``1 == True`` in Python; not in a document)."""
    return isinstance(a, bool) == isinstance(b, bool) and a == b


def conditions_of(entry: dict[str, Any]) -> dict[str, Any]:
    """The ``when`` of an entry as source name to value; a bare value conditions the entry's own source."""
    when = entry.get("when")
    if isinstance(when, dict):
        return dict(when)
    return {entry.get("from"): when}


def _check_when(where: str, name: str, entry: dict[str, Any], src: MaterialType) -> list[Finding]:
    out: list[Finding] = []
    when = entry.get("when")
    if isinstance(when, (list, tuple)) or (isinstance(when, dict) and not when):
        return [
            Finding(where, name, "when is a value of the source, or a non-empty object of parameter names to values")
        ]
    if isinstance(when, dict) and name not in when:
        out.append(Finding(where, name, f"a when object names its own source {name!r} among its conditions"))
    for cname, cvalue in conditions_of(entry).items():
        cp = src.parameters.get(cname)
        if cp is None:
            out.append(Finding(where, name, f"when names {cname!r}, not a parameter of {src.name}"))
        elif cp.type == "texture":
            out.append(Finding(where, name, f"when cannot test the texture parameter {cname!r}"))
        elif not value_matches(cp.type, cvalue, cp.choices):
            out.append(Finding(where, name, f"when {cvalue!r} is not a {cp.type} value of {cname!r}"))
    return out


def _check_entry(where: str, entry: Any, src: MaterialType, dst: MaterialType) -> list[Finding]:
    if not isinstance(entry, dict):
        return [Finding(where, "", f"a map entry is an object, got {entry!r}")]
    out: list[Finding] = []
    name = entry.get("from")
    if not isinstance(name, str) or not isinstance(entry.get("to"), str):
        return [Finding(where, "", f"an entry's from and to are parameter names, got {name!r} and {entry.get('to')!r}")]
    for key in entry:
        if key not in _ENTRY_KEYS:
            out.append(Finding(where, name, f"unknown entry key {key!r}"))
    sp = src.parameters.get(name)
    if sp is None:
        return out + [Finding(where, str(name), f"not a parameter of {src.name}")]
    tp = dst.parameters.get(entry.get("to"))
    if tp is None:
        return out + [Finding(where, name, f"target {entry.get('to')!r} is not a parameter of {dst.name}")]
    t = entry.get("transform")
    if t not in TRANSFORMS:
        return out + [Finding(where, name, f"transform {t!r} is not one of {TRANSFORMS}")]
    for key in _PAYLOAD[t]:
        if key not in entry:
            out.append(Finding(where, name, f"transform {t!r} carries {key!r}"))
    for key in ("by", "range", "value", "when"):
        if key in entry and key not in _PAYLOAD[t] and not (key == "when" and t == "constant"):
            out.append(Finding(where, name, f"transform {t!r} does not carry {key!r}"))
    if t == "scale" and not _is_number(entry.get("by")):
        out.append(Finding(where, name, "by is a number"))
    if t == "clamp":
        rng = entry.get("range")
        if not (isinstance(rng, list) and len(rng) == 2 and all(_is_number(v) for v in rng)):
            out.append(Finding(where, name, "range is [min, max]"))
    if t != "constant" and sp.type in ("bool", "enum"):
        out.append(Finding(where, name, "a bool or enum converts only through 'constant'"))
    if t == "constant" and "value" in entry:
        # a constant into a field is the field's type (strength: a float), otherwise the target's
        value_type = "float" if entry.get("field") is not None else tp.type
        if not value_matches(value_type, entry["value"], tp.choices):
            out.append(Finding(where, name, f"constant {entry['value']!r} is not a {value_type} for {tp.name!r}"))
    if "when" in entry:
        out.extend(_check_when(where, name, entry, src))
    field = entry.get("field")
    if field is not None:
        if field != "strength" or not tp.strength:
            out.append(Finding(where, name, f"target {tp.name!r} does not admit field {field!r}"))
        elif t == "identity" and sp.type != "float":
            out.append(Finding(where, name, f"field {field!r} takes a float, {sp.name!r} is {sp.type}"))
    elif t != "constant":
        # a non-constant transform keeps the type: float to float, colour to colour, texture to a texturable
        compatible = sp.type == tp.type or (sp.type == "texture" and tp.texturable)
        if not compatible:
            out.append(Finding(where, name, f"{sp.type} {sp.name!r} cannot map to {tp.type} {tp.name!r} by {t!r}"))
        elif t in ("scale", "clamp", "invert") and tp.type not in _NUMERIC_TARGETS:
            out.append(Finding(where, name, f"transform {t!r} needs a numeric target, {tp.name!r} is {tp.type}"))
    return out


def _domain(p: Any) -> list[Any] | None:
    """The finite values a bool or enum parameter takes; ``None`` for a type a condition set cannot enumerate."""
    if p.type == "bool":
        return [True, False]
    if p.type == "enum":
        return list(p.choices)
    return None


def _check_condition_set(where: str, name: str, conditions: list[dict[str, Any]], src: MaterialType) -> list[Finding]:
    """
    Over the product of the consulted parameters' domains (bool and enum only): every combination is matched
    by exactly one entry. Two entries matching one combination would let table order decide; none would
    let the target's default decide, silently. A set that consults a number is not enumerated.
    """
    names = sorted({cname for c in conditions for cname in c})
    domains = [_domain(src.parameters[n]) if n in src.parameters else None for n in names]
    if not names or any(d is None for d in domains):
        return []
    out: list[Finding] = []
    for combination in itertools.product(*domains):
        point = dict(zip(names, combination))
        matches = [c for c in conditions if all(_same(point.get(k), v) for k, v in c.items())]
        if len(matches) > 1:
            out.append(Finding(where, name, f"{len(matches)} entries match {point}; table order would decide"))
        elif not matches:
            out.append(Finding(where, name, f"no entry matches {point}; the target's default would decide"))
    return out


def check_table(table: dict[str, Any], src: MaterialType, dst: MaterialType, where: str = "<table>") -> list[Finding]:
    """The coverage rule and the payload rule; empty when the table is complete and well formed."""
    out: list[Finding] = []
    if (
        not isinstance(table, dict)
        or not isinstance(table.get("map"), list)
        or not isinstance(table.get("dropped"), list)
    ):
        return [Finding(where, "", "a table is an object with from, to, version, map (a list) and dropped (a list)")]
    if table.get("from") != src.name or table.get("to") != dst.name:
        out.append(
            Finding(
                where,
                "",
                f"table is from {table.get('from')!r} to {table.get('to')!r}, expected {src.name!r} to {dst.name!r}",
            )
        )
    seen: dict[str, int] = {}
    whens: dict[str, list[dict[str, Any]]] = {}
    consulted: set[str] = set()
    for entry in table["map"]:
        out.extend(_check_entry(where, entry, src, dst))
        if not isinstance(entry, dict) or not isinstance(entry.get("from"), str):
            continue  # already a finding; no name to count
        name = entry.get("from")
        if "when" in entry:
            # a source may appear once per distinct condition; those entries count as one appearance
            condition = conditions_of(entry)
            if condition in whens.setdefault(name, []):
                out.append(Finding(where, str(name), f"when {entry['when']!r} appears twice"))
            whens[name].append(condition)
            consulted.update(condition)
            seen[name] = max(seen.get(name, 0), 1)
        else:
            seen[name] = seen.get(name, 0) + 1
    for name, conditions in whens.items():
        if seen.get(name, 0) > 1:
            out.append(Finding(where, name, "mixes conditional and unconditional entries"))
        out.extend(_check_condition_set(where, name, conditions, src))
    for entry in table["dropped"]:
        if not isinstance(entry, dict):
            out.append(Finding(where, "", f"a dropped entry is an object, got {entry!r}"))
            continue
        name = entry.get("from")
        if not isinstance(name, str):
            out.append(Finding(where, "", f"a dropped entry's from is a parameter name, got {name!r}"))
            continue
        seen[name] = seen.get(name, 0) + 1
        if name not in src.parameters:
            out.append(Finding(where, name, f"dropped parameter is not a parameter of {src.name}"))
        elif name in consulted:
            out.append(
                Finding(where, name, "consulted by a when condition; a parameter that shapes the output is not a loss")
            )
        if not isinstance(entry.get("reason"), str) or not entry.get("reason"):
            out.append(Finding(where, str(name), "a dropped parameter carries a reason"))
    for name in src.parameters:
        n = seen.get(name, 0)
        if n == 0 and name not in consulted:
            out.append(Finding(where, name, "neither mapped, consulted nor dropped"))
        elif n > 1:
            out.append(Finding(where, name, f"appears {n} times"))
    return out


def _each(factor: Any, fn: Callable[[float], float]) -> Any:
    """``fn`` over a scalar, or over each component of a triple (list or tuple), returning a list."""
    if isinstance(factor, (list, tuple)):
        return [fn(v) for v in factor]
    return fn(factor)


def _apply(t: str, entry: dict[str, Any], factor: Any) -> Any:
    """
    One transform on one factor. ``None`` (no factor) passes through every transform but ``constant``; a
    factor the transform cannot take is ``MaterialError``.
    """
    if t == "constant":
        return copy.deepcopy(entry["value"])
    if factor is None:
        return None
    if t == "identity":
        return copy.deepcopy(factor)
    try:
        if t == "invert":
            return _each(factor, lambda v: 1.0 - v)
        if t == "scale":
            by = entry["by"]
            return _each(factor, lambda v: v * by)
        if t == "clamp":
            lo, hi = entry["range"]
            return _each(factor, lambda v: min(max(v, lo), hi))
    except TypeError as e:
        raise MaterialError(f"{entry.get('from')}: factor {factor!r} is not numeric for {t!r}") from e
    raise MaterialError(f"unknown transform {t!r}")


def _fires(entry: dict[str, Any], res: Resolved) -> bool:
    """Whether a conditional entry's every condition holds on the resolved source."""
    if "when" not in entry:
        return True
    return all(_same(res.values.get(cname, {}).get("factor"), cvalue) for cname, cvalue in conditions_of(entry).items())


def convert(obj: Document | Resolved, to_type: str) -> tuple[Document, list[Loss]]:
    """
    A raw document of ``to_type`` carrying the converted values, and the losses. A ``Document`` is resolved
    first, so the conversion sees every parameter; a resolved material that does not validate is
    ``MaterialError`` naming its findings. The result has no path: its texture strings are copied as
    written and are relative to the source document's directory.
    """
    res = resolve(obj) if isinstance(obj, Document) else obj
    problems = validate(res)
    if problems:
        raise MaterialError("cannot convert an invalid material: " + "; ".join(str(f) for f in problems))
    src, dst = type_of(res.material_type), type_of(to_type)
    table = load_table(src.name, dst.name)
    findings = check_table(table, src, dst, f"{src.name}-to-{dst.name}")
    if findings:
        raise MaterialError("malformed conversion table: " + "; ".join(str(f) for f in findings))
    values: dict[str, dict[str, Any]] = {}
    for entry in table["map"]:
        if not _fires(entry, res):
            continue  # a conditional constant that does not fire writes nothing; the target's default stands
        source = res.values.get(entry["from"], {})
        target = values.setdefault(entry["to"], {})
        t = entry["transform"]
        field = entry.get("field") or "factor"
        written = _apply(t, entry, source.get("factor"))
        if written is not None:
            if field in target and field != "strength":
                raise MaterialError(
                    f"{entry['to']}.{field} written twice: by {entry['from']!r} after another entry; "
                    "the table must decide"
                )
            target[field] = written
        if field != "factor":
            continue
        tp = dst.parameters[entry["to"]]
        if t == "identity" and source.get("texture") is not None and tp.texturable:
            target["texture"] = source["texture"]
            if source.get("blend") is not None:
                target["blend"] = source["blend"]
            if tp.strength and source.get("strength") is not None:
                target.setdefault("strength", source["strength"])  # a field entry for the target already set it
    # a target that received nothing (an unbound source texture, a None factor) or only a strength for an
    # unbound normal map is not written: the target type's default applies
    values = {name: v for name, v in values.items() if v and set(v) != {"strength"}}
    losses = [Loss(d["from"], d["reason"]) for d in table["dropped"]]
    _LOGGER.info(
        "converted %s to %s: %d value(s) written, %d parameter(s) lost (%s)",
        src.name,
        dst.name,
        len(values),
        len(losses),
        ", ".join(loss.parameter for loss in losses) or "none",
    )
    doc = Document(
        material_type=dst.name,
        material_type_version=dst.version,
        parent=None,
        values=values,
        ext=copy.deepcopy(res.ext),
    )
    return doc, losses
