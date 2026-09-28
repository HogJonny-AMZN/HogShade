"""
HogShade: the material library: material-type schemas as package data, and load, validate, resolve and
convert over material documents.
Package: hogshade/material

Importable inside Maya's and Blender's Pythons: the standard library only; no MaterialX, no PySide6, no
engine imports (the S1 spec's import test asserts it). The contracts are the S1 spec's
(Docs/superpowers/specs/s1-material-schema.md); the vocabulary is Docs/glossary.md, "Materials". No
name exported here is also a submodule's name (a test holds that; failure-modes entry 13).
"""

from __future__ import annotations

import logging as _logging

from hogshade.material.conversion import check_table, convert, load_table, table_names
from hogshade.material.document import from_data, load
from hogshade.material.model import Document, Finding, Loss, MaterialError, MaterialType, ParameterDef, Resolved
from hogshade.material.resolution import resolve
from hogshade.material.schema import check_type_data, type_of, types
from hogshade.material.validation import validate

_MODULE_NAME = "hogshade.material"
__version__ = "0.1.0"
__updated__ = "2026-09-27"
_LOGGER = _logging.getLogger(_MODULE_NAME)

__all__ = [
    "Document",
    "Finding",
    "Loss",
    "MaterialError",
    "MaterialType",
    "ParameterDef",
    "Resolved",
    "check_table",
    "check_type_data",
    "convert",
    "from_data",
    "load",
    "load_table",
    "resolve",
    "table_names",
    "type_of",
    "types",
    "validate",
]
