"""
HogShade: the data model of the material library: a parameter definition, a material type, a document, a
resolved material, a finding, a loss.
Package: hogshade/material/model

Plain dataclasses, numpy-free, so every DCC Python can import them. The shapes are the S1 spec's
(Docs/superpowers/specs/s1-material-schema.md). Named ``model``, not ``types``: the package exports a
``types()`` function, and a module of that name would be shadowed by it (failure-modes entry 13).
"""

from __future__ import annotations

import logging as _logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_MODULE_NAME = "hogshade.material.model"
__version__ = "0.1.0"
__updated__ = "2026-09-27"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: Parameter types a schema may declare.
PARAMETER_TYPES = ("float", "int", "bool", "enum", "color3", "vector3", "texture")
#: Widgets a generator knows how to emit.
WIDGETS = ("slider", "color", "toggle", "dropdown", "texture", "vector")
#: How a factor and a texture combine when a value carries both.
BLENDS = ("multiply", "lerp", "overlay")
#: Colour spaces a texture may declare; never inferred from a file name.
COLOUR_SPACES = ("srgb", "raw")
#: The value keys a document may write for one parameter.
VALUE_KEYS = ("factor", "texture", "blend", "strength")


class MaterialError(ValueError):
    """A document, a type file or a conversion table that cannot be used at all (as opposed to a Finding)."""


@dataclass(frozen=True)
class Finding:
    """One validation result: where, which parameter (or "" for the document), and what is wrong."""

    path: str
    parameter: str
    message: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.parameter}" if self.parameter else self.path
        return f"{where}: {self.message}"


@dataclass(frozen=True)
class Loss:
    """A parameter a conversion dropped, and the table's reason."""

    parameter: str
    reason: str


@dataclass(frozen=True)
class ParameterDef:
    """One parameter of a material type, as the schema file declares it."""

    name: str
    type: str
    group: str
    widget: str
    semantic: str
    overridable: bool
    tier: int | str
    hosts: dict[str, str]
    doc: str
    default: Any = None
    range: tuple[float, float] | None = None
    soft: bool = False
    colour_space: str | None = None
    choices: tuple[str, ...] = ()
    strength: bool = False

    @property
    def texturable(self) -> bool:
        """A value of this parameter may bind a texture: the schema gave it a colour space."""
        return self.colour_space is not None


@dataclass(frozen=True)
class MaterialType:
    """A material type: the contract a document is validated against."""

    name: str
    version: int
    title: str
    groups: tuple[str, ...]
    optional_groups: tuple[str, ...]  # derived: the groups that have a <group>_enabled bool
    parameters: dict[str, ParameterDef]
    migrations: tuple[dict[str, Any], ...]


@dataclass
class Document:
    """A material document as written: raw values, the parent as a path not yet followed."""

    material_type: str
    material_type_version: int
    parent: str | None
    values: dict[str, dict[str, Any]]
    ext: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None
    root: Path | None = None
    parent_path: Path | None = None


@dataclass
class Resolved:
    """A material with its parent chain followed and every default applied."""

    material_type: str
    version: int
    values: dict[str, dict[str, Any]]
    ext: dict[str, Any]
    chain: tuple[Path, ...]
