"""
HogShade: bind a resolved material to one host's values through that host's map.
Package: hogshade/material/binding

``bind(resolved, "wgpu")`` writes each bound parameter's factor into the frame field and component the wgpu
host map names, derives the host's model from the material type, lists every bound texture's path, and
reports the parameters the host cannot carry as ``Unbound``. The S3 spec
(Docs/superpowers/specs/s3-wgpu-binding.md) fixes the contract. Named ``binding``, not ``bind``: the package
exports ``bind`` (failure-modes entry 13). Standard library only.
"""

from __future__ import annotations

import logging as _logging
from typing import Any

from hogshade.material.generators import entries_for, host_map
from hogshade.material.model import Binding, MaterialError, Resolved, Unbound
from hogshade.material.schema import type_of
from hogshade.material.validation import validate

_MODULE_NAME = "hogshade.material.binding"
__version__ = "0.1.0"
__updated__ = "2026-10-02"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The wgpu host's model per material type (HOGSHADE_MODEL_* in the core; MODELS in hogshade.wgpu_host).
WGPU_MODELS = {"hogshade-legacy-v2": "legacy-v2", "hogshade-legacy-v1": "legacy-v1", "hogshade-lambert": "lambert"}
#: The model field's x component: the HOGSHADE_MODEL_* id, written by the binder, never by a map entry.
WGPU_MODEL_IDS = {"lambert": 0, "legacy-v1": 1, "legacy-v2": 2}


def _scalar(value: Any) -> float:
    """A float, int, bool or enum index as the frame carries it."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def pack_fields(hmap: dict[str, Any], type_name: str, factors: dict[str, Any]) -> dict[str, list[float]]:
    """
    The host map's fields at full width from a dictionary of parameter name to factor (``None`` writes
    nothing). The one packing path: ``bind()`` and the host's hand-set ``MaterialBinding`` both go through it.
    """
    fields = {name: [0.0] * width for name, width in hmap["fields"].items()}
    mtype = type_of(type_name)
    for pname, entry in entries_for(hmap, type_name).items():
        if "unsupported" in entry:
            continue
        factor = factors.get(pname)
        if factor is None:
            continue
        p = mtype.parameters[pname]
        if p.type == "enum":
            values = [float(list(p.choices).index(factor))]
        elif p.type in ("color3", "vector3"):
            values = [float(v) for v in factor]
        else:
            values = [_scalar(factor)]
        target = fields[entry["field"]]
        for component, value in zip(entry["components"], values):
            target[component] = value
    return fields


def bind(resolved: Resolved, host: str) -> Binding:
    """
    A ``Resolved`` into ``host``'s values through its map. A raw ``Document`` is refused (the caller resolves,
    so the parent chain's file reads stay in ``resolve()``); an unknown host, a type the host does not carry,
    or a material that does not validate is ``MaterialError``.
    """
    if not isinstance(resolved, Resolved):
        raise MaterialError(f"bind() takes a Resolved; resolve() the {type(resolved).__name__} first")
    if host != "wgpu":
        raise MaterialError(f"no binder for host {host!r}; S3 binds 'wgpu'")
    hmap = host_map(host)
    if resolved.material_type not in hmap["types"]:
        hint = (
            " (the standard type's wgpu model arrives with C3)" if resolved.material_type == "hogshade-standard" else ""
        )
        raise MaterialError(
            f"the {host} host does not carry {resolved.material_type!r}{hint}; it carries {hmap['types']}"
        )
    problems = validate(resolved)
    if problems:
        raise MaterialError("cannot bind an invalid material: " + "; ".join(str(f) for f in problems))
    factors = {name: value.get("factor") for name, value in resolved.values.items() if isinstance(value, dict)}
    fields = pack_fields(hmap, resolved.material_type, factors)
    model = WGPU_MODELS[resolved.material_type]
    fields["model"][0] = float(WGPU_MODEL_IDS[model])
    textures = {
        name: value["texture"]
        for name, value in resolved.values.items()
        if isinstance(value, dict) and value.get("texture") is not None
    }
    unsupported = tuple(
        Unbound(pname, entry["unsupported"])
        for pname, entry in entries_for(hmap, resolved.material_type).items()
        if "unsupported" in entry
    )
    return Binding(
        host=host,
        material_type=resolved.material_type,
        model=model,
        fields={name: tuple(values) for name, values in fields.items()},
        textures=textures,
        unsupported=unsupported,
    )
