"""
HogShade: core/constants.wgsl and hogshade/core_constants.py agree (phase 2 plan, task 7).
Package: tests/core/test_constants
"""

from __future__ import annotations

import math
from pathlib import Path

from hogshade import core_constants as cc

ROOT = Path(__file__).resolve().parents[2]


def test_every_python_constant_matches_the_wgsl() -> None:
    parsed = cc.parse_wgsl_constants(ROOT / "core" / "constants.wgsl")
    for name, value in cc.WGSL_NAMES.items():
        assert name in parsed, f"{name} missing from constants.wgsl"
        if isinstance(value, float):
            assert math.isclose(parsed[name], value, rel_tol=1e-9, abs_tol=1e-12), (name, parsed[name], value)
        else:
            assert parsed[name] == value, (name, parsed[name], value)


def test_every_wgsl_constant_is_mirrored() -> None:
    parsed = cc.parse_wgsl_constants(ROOT / "core" / "constants.wgsl")
    missing = set(parsed) - set(cc.WGSL_NAMES)
    assert not missing, f"add to hogshade/core_constants.py: {sorted(missing)}"


def test_model_ids_match_the_dispatch_switch() -> None:
    models = (ROOT / "core" / "models.wgsl").read_text(encoding="utf-8")
    assert f"case {cc.MODEL_LAMBERT}u:" in models
