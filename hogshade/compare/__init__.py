"""
HogShade: the comparison framework: how the project proves that hosts agree.
Package: hogshade/compare

A **capture request** (``request``) says what to render, in the framework's own conventions and with no host in it. An
adapter turns it into a **capture set** (``captureset``) on one host. ``metrics`` measure how close two pictures are,
``verdict`` turns measurements and thresholds into pass, needs-review or fail, ``cases`` is the table of what to check
and ``report`` is what a run writes. The design is ``Docs/design/2026-10-08-comparison-framework.md``; this package
is increment C-2 of it. Numpy and OpenEXR only; nothing here imports a renderer.
"""

from __future__ import annotations

import logging as _logging

_MODULE_NAME = "hogshade.compare"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)
