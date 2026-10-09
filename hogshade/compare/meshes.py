"""
HogShade: the canonical mesh ids a capture request may name.
Package: hogshade/compare/meshes

A request is host-neutral, so it cannot name a mesh by one host's registry. These ids are the framework's; each adapter
maps an id to its own source (the wgpu adapter to ``wgpu_host.MESHES``) and records the content hash of what it actually
loaded in the capture set's manifest. Adding an id is adding a line here and a mapping in each adapter that supports it.
"""

from __future__ import annotations

import logging as _logging
from collections.abc import Mapping
from types import MappingProxyType

_MODULE_NAME = "hogshade.compare.meshes"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The canonical ids, each with what it is for.
MESH_IDS: Mapping[str, str] = MappingProxyType(
    {
        "shader-ball": "derkreature's ShaderBall (Unlicense), the look-development mesh, normalised to a unit-ish ball",
        "quad-sphere": "a cube mapped onto a sphere, one clean 0 to 1 UV tile per face: the texture oracle mesh",
    }
)


def is_mesh_id(name: object) -> bool:
    """Whether ``name`` is one of the canonical ids."""
    return isinstance(name, str) and name in MESH_IDS
