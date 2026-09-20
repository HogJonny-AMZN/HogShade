"""
HogShade: the job library for Job_Orchestrator and BATS.
Package: hogshade/jobs

Every reproducible step in this repo is a MODULE-mode job: a module with a ``main(parameters: dict)
-> dict`` entry point, which the orchestrator's Python worker imports and calls
(``job_orchestrator.dcc_workers.python.python_rpc_server``: ``importlib.import_module(module_path)``,
``getattr(module, entry_point or "main")(parameters)``; a returned dict becomes the job's custom
metadata). Each module also carries a ``MANIFEST`` dict written for an agent: what the job does,
its parameters with types and defaults, the worker type, inputs and outputs. ``manifest()`` collects
them so a registry or an MCP tool can list the library without importing anything heavy.
"""

from __future__ import annotations

import importlib
import logging as _logging

_MODULE_NAME = "hogshade.jobs"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

JOB_MODULES = ("hogshade.jobs.cook_ibl",)


def manifest() -> list[dict]:
    """The manifests of every job in the library, in registration order."""
    out = []
    for name in JOB_MODULES:
        module = importlib.import_module(name)
        entry = dict(module.MANIFEST)
        entry["module_path"] = name
        entry["entry_point"] = "main"
        out.append(entry)
    return out
