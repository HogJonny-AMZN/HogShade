"""
HogShade: the material library: material-type schemas as package data, and load, validate, resolve and
convert over material documents.
Package: hogshade/material

Importable inside Maya's and Blender's Pythons: the standard library only; no MaterialX, no PySide6, no
engine imports (the S1 spec's import test asserts it). The contracts are the S1 spec's
(Docs/superpowers/specs/s1-material-schema.md); the vocabulary is Docs/glossary.md, "Materials".
"""

from __future__ import annotations

from hogshade.material.conversion import check_table, convert, load_table, table_names
from hogshade.material.document import load
from hogshade.material.resolution import resolve
from hogshade.material.schema import check_type_data, type_of, types
from hogshade.material.types import Document, Finding, Loss, MaterialError, MaterialType, ParameterDef, Resolved
from hogshade.material.validation import validate

_MODULE_NAME = "hogshade.material"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

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
    "load",
    "load_table",
    "resolve",
    "table_names",
    "type_of",
    "types",
    "validate",
]
