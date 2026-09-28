"""
HogShade: shared paths and the fake-type helper for the material library tests.
Package: tests/material/conftest
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from hogshade.material.schema import parse_type_data, read_type_data

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def fake_type(monkeypatch):
    """
    Register a variant of a shipped type under its own name for one test: ``fake_type(edit)`` deep-copies the
    standard's data, hands it to ``edit`` to change, parses it and patches ``type_of`` in every module.
    """

    def make(edit, base: str = "hogshade-standard"):
        data = copy.deepcopy(read_type_data(base))
        edit(data)
        mtype = parse_type_data(data, "<fake>")

        def type_of(name: str):
            if name != mtype.name:
                raise AssertionError(f"the fake registry knows only {mtype.name!r}, asked for {name!r}")
            return mtype

        for module in ("document", "validation", "resolution", "conversion"):
            monkeypatch.setattr(f"hogshade.material.{module}.type_of", type_of)
        return mtype

    return make
