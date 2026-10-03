"""
HogShade: the texture conventions as data (T1): the suffix table covers the schema's texturable parameters exactly,
the name grammar accepts and rejects what the standard says, the presets and the sidecar rules hold.
Package: tests/material/test_material_textures
"""

from __future__ import annotations

import pytest

from hogshade.material import type_of
from hogshade.material.textures import (
    PACKED,
    PREFIX,
    STANDARD,
    SUFFIXES,
    check_sidecar,
    check_suffixes,
    parameter_of,
    parse_name,
    preset_for,
)

GOOD_SIDECAR = {
    "provenance": {
        "origin": "polyhaven",
        "url": "https://polyhaven.com/a/x",
        "licence": "CC0-1.0",
        "fetched": "2026-10-03",
    }
}


def test_the_table_covers_the_texturable_parameters_exactly():
    assert check_suffixes() == []
    texturable = {name for name, p in type_of(STANDARD).parameters.items() if p.texturable}
    assert {s.parameter for s in SUFFIXES.values()} == texturable
    assert len(SUFFIXES) == len(texturable) == 14
    assert not set(SUFFIXES) & set(PACKED)
    assert PREFIX == "T_" and "_BC" in SUFFIXES and "_D" not in SUFFIXES, "the owner's answers"
    assert set(PACKED) == {"_ORM", "_DN", "_DH"}


def test_the_table_check_names_each_drift(monkeypatch):
    import hogshade.material.textures as tx

    patched = dict(SUFFIXES)
    del patched["_C"]
    monkeypatch.setattr(tx, "SUFFIXES", patched)
    msgs = [f"{f.parameter}: {f.message}" for f in check_suffixes()]
    assert "cavity: texturable in the schema but has no suffix" in msgs

    patched = dict(SUFFIXES)
    patched["_X"] = tx.Suffix("_X", "base_color", "raw", "bc7")
    monkeypatch.setattr(tx, "SUFFIXES", patched)
    msgs = [f"{f.parameter}: {f.message}" for f in check_suffixes()]
    assert "_X: colour space 'raw' but the schema says 'srgb'" in msgs
    assert "_X: 'base_color' already has the suffix _BC" in msgs

    patched = dict(SUFFIXES)
    patched["_Y"] = tx.Suffix("_Y", "specular_ior", "raw", "bc4")
    monkeypatch.setattr(tx, "SUFFIXES", patched)
    msgs = [f"{f.parameter}: {f.message}" for f in check_suffixes()]
    assert "_Y: 'specular_ior' has no colour space in the schema, so no texture" in msgs


@pytest.mark.parametrize(
    ("stem", "base", "suffix", "variant"),
    [
        ("T_cobblestone_floor_04_BC", "cobblestone_floor_04", "_BC", None),
        ("T_grid_N_01", "grid", "_N", "01"),
        ("T_brick_wall_ORM_damaged", "brick_wall", "_ORM", "damaged"),
    ],
)
def test_names_that_parse(stem, base, suffix, variant):
    name = parse_name(stem)
    assert name is not None and (name.base, name.suffix, name.variant) == (base, suffix, variant) and name.known


@pytest.mark.parametrize(
    "stem", ["cobblestone_BC", "T_Cobblestone_BC", "T_grid_BC_Damaged", "T_grid", "t_grid_BC", "T_grid__BC"]
)
def test_names_that_do_not_parse(stem):
    assert parse_name(stem) is None


def test_an_unknown_suffix_parses_but_is_not_known():
    name = parse_name("T_grid_XX")
    assert name is not None and name.suffix == "_XX" and not name.known
    assert parameter_of("_XX") is None and parameter_of("_ORM") is None and parameter_of("_N") == "geometry_normal"


def test_presets_follow_the_suffix():
    assert preset_for("_N")["normal"] and preset_for("_N")["runtime"] == {"format": "bc5", "container": "dds"}
    assert preset_for("_BC")["colour_space"] == "srgb" and preset_for("_ORM")["preset"] == "orm"
    with pytest.raises(KeyError):
        preset_for("_XX")


def test_sidecar_rules():
    assert check_sidecar(GOOD_SIDECAR, "_BC") == []
    assert check_sidecar({**GOOD_SIDECAR, "normal_convention": "directx-y"}, "_N") == []

    def msgs(data, suffix):
        return [f"{f.parameter}: {f.message}" for f in check_sidecar(data, suffix)]

    assert any(m.startswith("normal_convention: a normal map states") for m in msgs(GOOD_SIDECAR, "_N"))
    assert "normal_convention: only a normal map carries it" in msgs(
        {**GOOD_SIDECAR, "normal_convention": "opengl+y"}, "_BC"
    )
    assert "provenance: required: an object with origin, url, licence, fetched" in msgs({}, "_BC")
    assert "provenance: carries a non-empty 'licence'" in msgs(
        {"provenance": {"origin": "a", "url": "u", "licence": "", "fetched": "f"}}, "_BC"
    )
    assert any("disagrees with the suffix's" in m for m in msgs({**GOOD_SIDECAR, "colour_space": "raw"}, "_BC"))
    assert msgs({**GOOD_SIDECAR, "colour_space": "raw", "override_reason": "a linear colour source"}, "_BC") == []
    assert "foo: unknown sidecar field" in msgs({**GOOD_SIDECAR, "foo": 1}, "_BC")
    assert "resolution: a positive integer, the longer side in pixels" in msgs(
        {**GOOD_SIDECAR, "resolution": "2k"}, "_BC"
    )
    assert check_sidecar([], "_BC")[0].message == "a sidecar is a JSON object"
    assert "resolution: a positive integer, the longer side in pixels" in msgs(
        {**GOOD_SIDECAR, "resolution": True}, "_BC"
    )
    assert msgs({**GOOD_SIDECAR, "runtime": {"format": "bc7"}}, "_BC") == [], "a partial object agrees key by key"
    assert any("runtime:" in m and "disagrees" in m for m in msgs({**GOOD_SIDECAR, "runtime": {"typo": None}}, "_BC"))
    assert any("exceeds the repository budget of 2048" in m for m in msgs({**GOOD_SIDECAR, "resolution": 8192}, "_BC"))
    assert msgs(GOOD_SIDECAR, "_DN") == [], "a derived detail normal is the cook's; no convention required"
    assert check_sidecar(GOOD_SIDECAR, "_XX")[0].message == "suffix '_XX' is not in the tables"
