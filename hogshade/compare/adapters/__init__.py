"""
HogShade: the capture adapters: one module per host that turns a capture request into a capture set.
Package: hogshade/compare/adapters

An adapter is the only code that knows a host. It maps the request's canonical conventions to the host's scene,
refuses by name what the host cannot honour (rather than rendering something near), renders, and writes a capture set at
the level the host actually reached. The framework itself never launches a host: it reads capture sets.
"""

from __future__ import annotations

import logging as _logging

_MODULE_NAME = "hogshade.compare.adapters"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)
