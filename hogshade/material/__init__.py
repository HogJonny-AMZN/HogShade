"""
HogShade: the material library: material-type schemas as package data, and load, validate, resolve and
convert over material documents; the library's roster and index (S4a).
Package: hogshade/material

Importable inside Maya's and Blender's Pythons: the standard library only; no MaterialX, no PySide6, no
engine imports (the S1 spec's import test asserts it). The contracts are the S1 spec's
(Docs/superpowers/specs/s1-material-schema.md); the vocabulary is Docs/glossary.md, "Materials". No
name exported here is also a submodule's name (a test holds that; failure-modes entry 13).
"""

from __future__ import annotations

import logging as _logging

from hogshade.material.binding import bind
from hogshade.material.conversion import check_table, conditions_of, convert, load_table, table_names
from hogshade.material.document import from_data, load
from hogshade.material.generators import check_host_map, entries_for, generate, host_map, hosts, union_of
from hogshade.material.library import coverage, documents_under, index
from hogshade.material.model import (
    Binding,
    Document,
    Finding,
    Loss,
    MaterialError,
    MaterialType,
    ParameterDef,
    Resolved,
    Unbound,
)
from hogshade.material.resolution import resolve
from hogshade.material.schema import check_type_data, type_of, types
from hogshade.material.validation import validate

_MODULE_NAME = "hogshade.material"
__version__ = "0.2.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

__all__ = [
    "Binding",
    "Document",
    "Finding",
    "Loss",
    "MaterialError",
    "MaterialType",
    "ParameterDef",
    "Resolved",
    "Unbound",
    "bind",
    "check_host_map",
    "check_table",
    "check_type_data",
    "conditions_of",
    "convert",
    "coverage",
    "documents_under",
    "entries_for",
    "from_data",
    "generate",
    "host_map",
    "hosts",
    "index",
    "load",
    "load_table",
    "resolve",
    "table_names",
    "type_of",
    "types",
    "union_of",
    "validate",
]
