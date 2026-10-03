"""
HogShade: the texture cook: an authoring set (one PNG or EXR per parameter, with sidecars) into its runtime set
(DDS with mips, packed, compressed when an encoder is present) with a deterministic manifest and a volatile
provenance; and the owner's frequency separation as a cook operation.
Package: hogshade/texture_cook

numpy throughout; ``hogshade.material`` (standard library only) is never imported by the material package in
return. The T2 spec (Docs/superpowers/specs/t2-texture-cook.md) fixes the contracts; the suffix table and the
sidecar rules are ``hogshade.material.textures`` (T1).
"""

from __future__ import annotations

import logging as _logging

_MODULE_NAME = "hogshade.texture_cook"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)
