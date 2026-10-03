"""
HogShade: the library of materials (S4a): every document loads, validates, resolves, converts to legacy v2
and binds for wgpu; the roster covers every factor-bearing standard parameter; the record fields are checked
for shape and never inherited; the reverse table is complete; the index equals the committed page.
Package: tests/material/test_material_library
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from hogshade.material import (
    MaterialError,
    bind,
    check_table,
    convert,
    coverage,
    documents_under,
    from_data,
    index,
    load,
    load_table,
    resolve,
    type_of,
    validate,
)
from hogshade.material.library import DEFERRED, FAMILY_ORDER, INDEX_HEADER, PARENT_NAME, factor_parameters

REPO = Path(__file__).resolve().parents[2]
LIBRARY = REPO / "content" / "materials" / "standard"
INDEX = REPO / "content" / "materials" / "README.md"
STANDARD, V2 = "hogshade-standard", "hogshade-legacy-v2"
ROSTER = {
    "metal": ["aluminium", "brass", "chrome", "copper", "gold", "iron", "silver", "steel"],
    "dielectric": ["ceramic", "plastic_glossy", "plastic_matte"],
    "coated": ["painted"],
    "rough": ["concrete", "rubber"],
    "emissive": ["panel"],
    "cutout": ["leaf"],
}
DOCUMENTS = documents_under(LIBRARY)


def _rel(p: Path) -> str:
    return p.relative_to(LIBRARY).as_posix()


# ------------------------------------------------------------------------------------------- the roster


def test_the_roster_is_six_families_and_twenty_two_documents():
    names = [_rel(p) for p in DOCUMENTS]
    expected = []
    for family in FAMILY_ORDER:
        expected.append(f"{family}/{PARENT_NAME}")
        expected += [f"{family}/{child}.material.json" for child in ROSTER[family]]
    assert names == expected, names


@pytest.mark.parametrize("path", DOCUMENTS, ids=_rel)
def test_every_document_validates_resolves_converts_and_binds(path: Path):
    doc = load(path, LIBRARY)
    assert doc.material_type == STANDARD
    assert validate(doc) == []
    if path.name != PARENT_NAME:
        assert doc.parent == PARENT_NAME, "a child's parent is base.material.json beside it"
    resolved = resolve(doc, LIBRARY)
    assert validate(resolved) == []
    converted, losses = convert(resolved, V2)
    assert validate(converted) == [] and validate(resolve(converted)) == []
    assert [loss.parameter for loss in losses] == [d["from"] for d in load_table(STANDARD, V2)["dropped"]]
    binding = bind(resolve(converted), "wgpu")
    assert binding.model == "legacy-v2"
    assert converted.title is None and converted.provenance == [], "conversion does not copy the record fields"


@pytest.mark.parametrize("path", DOCUMENTS, ids=_rel)
def test_every_document_carries_a_title_a_doc_and_a_source(path: Path):
    doc = load(path, LIBRARY)
    assert doc.title and doc.doc, "title and doc are written"
    assert doc.provenance, "at least one source"
    sources = " ".join(p["source"] for p in doc.provenance)
    if path.parent.name == "metal" and path.name != PARENT_NAME:
        assert "Lagarde" in sources or "author" in sources, sources


def test_the_roster_covers_every_factor_bearing_standard_parameter():
    cov = coverage(LIBRARY)
    assert sorted(cov) == sorted(factor_parameters(STANDARD))
    assert len(cov) == 13, (
        "the standard's non-texture parameters; a schema addition fails here until a document sets it"
    )
    uncovered = [name for name, docs in cov.items() if not docs]
    assert uncovered == [], uncovered


def test_children_set_only_deltas_and_the_parents_carry_the_family():
    metal_parent = load(LIBRARY / "metal" / PARENT_NAME, LIBRARY)
    assert metal_parent.values["base_metalness"]["factor"] == 1.0
    gold = load(LIBRARY / "metal" / "gold.material.json", LIBRARY)
    assert set(gold.values) == {"base_color"}
    assert resolve(gold, LIBRARY).values["base_metalness"]["factor"] == 1.0
    assert resolve(gold, LIBRARY).values["base_color"]["factor"] == [1.0, 0.77, 0.34]


def test_the_cutout_parent_keeps_opacity_at_one_under_mask():
    res = resolve(load(LIBRARY / "cutout" / PARENT_NAME, LIBRARY), LIBRARY)
    assert res.values["alpha_mode"]["factor"] == "mask" and res.values["geometry_opacity"]["factor"] == 1.0
    converted, _ = convert(res, V2)
    assert converted.values["use_cutout_alpha"]["factor"] is True


def test_the_emissive_panel_converts_nits_through_the_placeholder_scale():
    res = resolve(load(LIBRARY / "emissive" / "panel.material.json", LIBRARY), LIBRARY)
    converted, _ = convert(res, V2)
    assert converted.values["emission_intensity"]["factor"] == pytest.approx(8.0)


# ------------------------------------------------------------------------------------- the reverse table


def test_the_reverse_table_is_complete_and_fans_alpha_mode_out():
    table = load_table(STANDARD, V2)
    assert check_table(table, type_of(STANDARD), type_of(V2)) == []
    whens = sorted(e["when"] for e in table["map"] if e["from"] == "alpha_mode")
    assert whens == ["blend", "mask", "opaque"]


def test_the_reverse_table_names_a_forgotten_parameter_and_a_reasonless_drop():
    table = copy.deepcopy(load_table(STANDARD, V2))
    table["dropped"] = [d for d in table["dropped"] if d["from"] != "specular_occlusion"]
    table["dropped"][0]["reason"] = ""
    msgs = [f"{f.parameter}: {f.message}" for f in check_table(table, type_of(STANDARD), type_of(V2))]
    assert "specular_occlusion: neither mapped, consulted nor dropped" in msgs
    assert "specular_color: a dropped parameter carries a reason" in msgs


# ---------------------------------------------------------------------------------- the record fields


def _data(**extra):
    return {"material_type": STANDARD, "material_type_version": 1, "values": {}, **extra}


def test_record_fields_load_and_validate():
    doc = from_data(_data(title="Gold", doc="Gold.", provenance=[{"source": "Lagarde", "note": "rounded"}]))
    assert (doc.title, doc.doc, doc.provenance) == ("Gold", "Gold.", [{"source": "Lagarde", "note": "rounded"}])
    assert validate(doc) == []
    assert from_data(_data()).title is None and from_data(_data()).provenance == []


@pytest.mark.parametrize(
    ("extra", "fragment"),
    [
        ({"title": 3}, "title is a string"),
        ({"doc": ["x"]}, "doc is a string"),
        ({"provenance": {"source": "x"}}, "provenance is a list"),
    ],
)
def test_record_fields_of_the_wrong_container_are_material_errors(extra, fragment):
    with pytest.raises(MaterialError, match=fragment):
        from_data(_data(**extra))


def test_record_fields_inner_shapes_are_findings():
    doc = from_data(_data(title="  ", provenance=[{"source": "x"}, 5, {"source": "x", "note": "y", "url": "z"}]))
    messages = [f"{f.parameter}: {f.message}" for f in validate(doc)]
    assert "title: title is a non-empty string" in messages
    assert "provenance: entry 0 carries a non-empty 'note'" in messages
    assert "provenance: entry 1 is an object with source and note" in messages
    assert "provenance: entry 2 has an unknown key 'url'" in messages


def test_a_title_is_never_inherited(tmp_path: Path):
    (tmp_path / PARENT_NAME).write_text(json.dumps(_data(title="Parent", doc="p")), encoding="utf-8")
    (tmp_path / "child.material.json").write_text(json.dumps(_data(parent=PARENT_NAME)), encoding="utf-8")
    child = load(tmp_path / "child.material.json", tmp_path)
    assert child.title is None
    resolved = resolve(child, tmp_path)
    assert not hasattr(resolved, "title")


# ------------------------------------------------------------------------------------------- the index


def test_the_index_equals_the_committed_page_and_lists_every_document():
    text = index(LIBRARY)
    assert text.startswith(INDEX_HEADER)
    assert INDEX.read_text(encoding="utf-8") == text, "run tools/generate_material_ui.py --write"
    for p in DOCUMENTS:
        assert f"`{p.name}`" in text
    for name, _ in DEFERRED:
        assert name in text
    assert "`specular_color`" in text and "geometry_normal strength" in text


def test_the_index_refuses_a_library_with_a_finding(tmp_path: Path):
    (tmp_path / "metal").mkdir()
    (tmp_path / "metal" / PARENT_NAME).write_text(
        json.dumps(_data(title="M", doc="m", values={"base_metalness": {"factor": 2.0}})), encoding="utf-8"
    )
    with pytest.raises(MaterialError, match="outside range"):
        index(tmp_path)
    with pytest.raises(MaterialError, match="no such library root"):
        documents_under(tmp_path / "nowhere")


def test_the_index_orders_families_and_parents_first(tmp_path: Path):
    for family in ("cutout", "metal", "zzz"):
        (tmp_path / family).mkdir()
        (tmp_path / family / PARENT_NAME).write_text(json.dumps(_data(title="P", doc="p")), encoding="utf-8")
        (tmp_path / family / "a.material.json").write_text(
            json.dumps(_data(title="A", doc="a", parent=PARENT_NAME)), encoding="utf-8"
        )
    names = [p.relative_to(tmp_path).as_posix() for p in documents_under(tmp_path)]
    assert names == [
        f"metal/{PARENT_NAME}",
        "metal/a.material.json",
        f"cutout/{PARENT_NAME}",
        "cutout/a.material.json",
        f"zzz/{PARENT_NAME}",
        "zzz/a.material.json",
    ]


def test_the_tool_check_covers_the_index():
    sys.path.insert(0, str(REPO / "tools"))
    import generate_material_ui as tool

    assert tool.INDEX == INDEX and tool.check() == []
