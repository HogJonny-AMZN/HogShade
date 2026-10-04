"""
HogShade: bind a resolved material to one host's values through that host's map.
Package: hogshade/material/binding

``bind(resolved, "wgpu")`` writes each bound parameter's factor into the frame field and component the wgpu
host map names, derives the host's model from the material type, lists every bound texture's path, and
reports the parameters the host cannot carry as ``Unbound``. The S3 spec
(Docs/superpowers/specs/s3-wgpu-binding.md) fixes the contract. ``bind(resolved, "maya_dx11")`` (T3) writes the
shell's attribute values and ``use<Map>`` flags instead; the texture attributes are connected by the job from
``maya_map_slots`` and ``hogshade.material.runtime``. A standard document reaches either host through
``convert()`` to legacy v2 first. Named ``binding``, not ``bind``: the package exports ``bind`` (failure-modes
entry 13). Standard library only.
"""

from __future__ import annotations

import logging as _logging
from typing import Any

from hogshade.material.generators import MAYA_TYPES, entries_for, host_map
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
        if len(values) != len(entry["components"]):
            raise MaterialError(
                f"{pname}: {len(values)} value(s) for {len(entry['components'])} component(s) of {entry['field']!r}"
            )
        target = fields[entry["field"]]
        for component, value in zip(entry["components"], values):
            target[component] = value
    return fields


def _wgpu_fields(
    hmap: dict[str, Any], type_name: str, factors: dict[str, Any], textures: dict[str, str]
) -> dict[str, list[float]]:
    """The wgpu frame fields, the model id in the binder's slot (S3)."""
    fields = pack_fields(hmap, type_name, factors)
    fields["model"][0] = float(WGPU_MODEL_IDS[HOST_MODELS[type_name]])
    return fields


def maya_attributes(
    hmap: dict[str, Any], type_name: str, factors: dict[str, Any], textures: dict[str, str]
) -> dict[str, list[float]]:
    """
    The Maya shell's attribute values from a type's factors (T3): a scalar, colour, bool or enum entry writes
    its attribute; a vector3 entry writes one attribute per component (the shell's ``Positive:Negative``
    choice: 0 for a positive component, 1 for a negative one, as the generated declarations default); a map
    entry writes its ``use<Map>`` flag, 1.0 when the parameter is textured. The texture attributes themselves
    are the job's to connect (``maya_map_slots``), since a dx11Shader texture takes a file node, not a value.
    """
    out: dict[str, list[float]] = {}
    mtype = type_of(type_name)
    for pname, entry in entries_for(hmap, type_name).items():
        if "unsupported" in entry:
            continue
        p = mtype.parameters[pname]
        if "map" in entry:
            out[entry["map"]["flag"]] = [1.0 if pname in textures else 0.0]
        factor = factors.get(pname)
        if factor is None or p.type == "texture":
            continue
        if "components" in entry:
            for component, value in zip(entry["components"], factor):
                out[component["name"]] = [0.0 if float(value) > 0 else 1.0]
        elif "name" in entry:
            if p.type == "enum":
                out[entry["name"]] = [float(list(p.choices).index(factor))]
            elif p.type in ("color3", "vector3"):
                out[entry["name"]] = [float(v) for v in factor]
            else:
                out[entry["name"]] = [_scalar(factor)]
    return out


def maya_map_slots(type_name: str) -> dict[str, tuple[str, str]]:
    """Per textured parameter of ``type_name``, the Maya shell's texture attribute and its ``use<Map>`` flag."""
    hmap = host_map("maya_dx11")
    return {
        pname: (entry["map"]["name"], entry["map"]["flag"])
        for pname, entry in entries_for(hmap, type_name).items()
        if "map" in entry
    }


#: The host's model per material type, the same names on every host (HOGSHADE_MODEL_* in the core).
HOST_MODELS = {"hogshade-legacy-v2": "legacy-v2", "hogshade-legacy-v1": "legacy-v1", "hogshade-lambert": "lambert"}
#: The binders: host name to the function that turns a type's factors and textures into that host's fields.
BINDERS = {"wgpu": _wgpu_fields, "maya_dx11": maya_attributes}


def bind(resolved: Resolved, host: str) -> Binding:
    """
    A ``Resolved`` into ``host``'s values through its map. A raw ``Document`` is refused (the caller resolves,
    so the parent chain's file reads stay in ``resolve()``); an unknown host, a type the host does not carry,
    or a material that does not validate is ``MaterialError``.
    """
    if not isinstance(resolved, Resolved):
        raise MaterialError(f"bind() takes a Resolved; resolve() the {type(resolved).__name__} first")
    if host not in BINDERS:
        raise MaterialError(f"no binder for host {host!r}; the binders are {tuple(BINDERS)}")
    hmap = host_map(host)
    carried = hmap.get("types") or list(MAYA_TYPES)
    if resolved.material_type not in carried:
        hint = (
            " (the standard type's host model arrives with C3; convert() it to legacy v2 first)"
            if resolved.material_type == "hogshade-standard"
            else ""
        )
        raise MaterialError(f"the {host} host does not carry {resolved.material_type!r}{hint}; it carries {carried}")
    problems = validate(resolved)
    if problems:
        raise MaterialError("cannot bind an invalid material: " + "; ".join(str(f) for f in problems))
    factors = {name: value.get("factor") for name, value in resolved.values.items() if isinstance(value, dict)}
    textures = {
        name: value["texture"]
        for name, value in resolved.values.items()
        if isinstance(value, dict) and value.get("texture") is not None
    }
    model = HOST_MODELS[resolved.material_type]
    fields = BINDERS[host](hmap, resolved.material_type, factors, textures)
    unsupported = tuple(
        Unbound(pname, entry["unsupported"])
        for pname, entry in entries_for(hmap, resolved.material_type).items()
        if "unsupported" in entry
    )
    _LOGGER.info(
        f"bound {resolved.chain[0] if resolved.chain else '<document>'} ({resolved.material_type}) for the {host} "
        f"host as model {model}: {len(textures)} texture(s) carried as paths, "
        f"{len(unsupported)} parameter(s) the host cannot take"
    )
    for u in unsupported:
        _LOGGER.debug(f"  {u.parameter}: {u.reason}")
    return Binding(
        host=host,
        material_type=resolved.material_type,
        model=model,
        fields={name: tuple(values) for name, values in fields.items()},
        textures=textures,
        unsupported=unsupported,
    )


if __name__ == "__main__":
    # smoke run: python -m hogshade.material.binding <path.material.json>
    import sys

    from hogshade.material.document import load
    from hogshade.material.resolution import resolve

    _binding = bind(resolve(load(sys.argv[1])), "wgpu")
    print(_binding.material_type, "->", _binding.model)
    for _name, _values in _binding.fields.items():
        print(f"  {_name}: {_values}")
    for _unbound in _binding.unsupported:
        print(f"  unbound {_unbound.parameter}: {_unbound.reason}")
