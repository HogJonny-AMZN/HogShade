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
from hogshade.material.library import (
    DEFERRED,
    FAMILY_ORDER,
    INDEX_HEADER,
    PARENT_NAME,
    factor_parameters,
    texture_coverage,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "wgpu"))

REPO = Path(__file__).resolve().parents[2]
LIBRARY = REPO / "content" / "materials" / "standard"
INDEX = REPO / "content" / "materials" / "README.md"
STANDARD, V2 = "hogshade-standard", "hogshade-legacy-v2"
ROSTER = {
    "metal": ["aluminium", "brass", "chrome", "copper", "gold", "iron", "metal_plate", "silver", "steel"],
    "dielectric": ["brown_planks_03", "ceramic", "plastic_glossy", "plastic_matte"],
    "coated": ["painted"],
    "rough": ["brick_wall_001", "cobblestone_floor_04", "concrete", "rubber"],
    "emissive": ["panel"],
    "cutout": ["leaf"],
}
#: T3: the texturable parameters a committed document binds, and the one deferred (cavity: only the grid tile
#: has a _C, and no document binds the grid).
TEXTURED = {
    "base_color": 4,
    "specular_roughness": 4,
    "geometry_normal": 4,
    "ambient_occlusion": 4,
    "height": 4,
    "base_metalness": 1,
}
DEFERRED_TEXTURES = {"cavity"}
DOCUMENTS = documents_under(LIBRARY)


def _rel(p: Path) -> str:
    return p.relative_to(LIBRARY).as_posix()


# ------------------------------------------------------------------------------------------- the roster


def test_the_roster_is_six_families_and_twenty_six_documents():
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


CITABLE = ("Lagarde", "refractiveindex.info", "author", "https://")  # a publication, a URL or the author


@pytest.mark.parametrize("path", DOCUMENTS, ids=_rel)
def test_every_document_carries_a_title_a_doc_and_a_source_per_value(path: Path):
    """Every constant has a source: each parameter the document sets is named in a provenance note, and every
    source is a publication, a URL or the author (the spec's rule), never a placeholder."""
    doc = load(path, LIBRARY)
    assert doc.title and doc.doc, "title and doc are written"
    assert doc.provenance, "at least one source"
    for entry in doc.provenance:
        assert any(c in entry["source"] for c in CITABLE), f"not a citable source: {entry['source']!r}"
    notes = " ".join(p["note"] for p in doc.provenance)
    unsourced = [name for name in doc.values if name not in notes]
    assert unsourced == [], f"set without a note naming it: {unsourced}"
    if path.parent.name == "metal" and path.name != PARENT_NAME:
        assert any("Lagarde" in p["source"] or p["source"] == "author" for p in doc.provenance)


def test_the_roster_covers_every_factor_bearing_standard_parameter():
    cov = coverage(LIBRARY)
    assert sorted(cov) == sorted(factor_parameters(STANDARD)), "every non-texture parameter of the schema is a key"
    uncovered = [name for name, docs in cov.items() if not docs]
    assert uncovered == [], uncovered  # a schema addition lands here until a document sets it


def test_the_texture_bindings_cover_the_design_s_parameters_and_say_what_is_deferred():
    cov = texture_coverage(LIBRARY)
    bound = {name: len(docs) for name, docs in cov.items() if docs}
    assert bound == TEXTURED, bound
    texture_only = {n for n, p in type_of(STANDARD).parameters.items() if p.type == "texture"}
    unbound_texture_only = {n for n in texture_only if not cov[n]}
    assert unbound_texture_only == DEFERRED_TEXTURES, (
        "a texture-only parameter no document binds is a deferral to record"
    )
    for name, docs in cov.items():
        for rel in docs:
            doc = load(LIBRARY / rel, LIBRARY)
            texture = doc.values[name]["texture"]
            assert texture.startswith(rel.split("/")[1].removesuffix(".material.json") + "/"), (rel, texture)
            assert (LIBRARY / rel).parent.joinpath(*texture.split("/")).is_file(), (rel, texture)


def test_children_set_only_deltas_and_the_parents_carry_the_family():
    metal_parent = load(LIBRARY / "metal" / PARENT_NAME, LIBRARY)
    assert metal_parent.values["base_metalness"]["factor"] == 1.0
    gold = load(LIBRARY / "metal" / "gold.material.json", LIBRARY)
    assert set(gold.values) == {"base_color"}
    assert resolve(gold, LIBRARY).values["base_metalness"]["factor"] == 1.0
    assert resolve(gold, LIBRARY).values["base_color"]["factor"] == [1.0, 0.77, 0.34]
    # no child restates a value its parent already sets identically; iron is the one exception, titled on purpose
    restated = []
    for path in DOCUMENTS:
        if path.name == PARENT_NAME or path.name == "iron.material.json":
            continue
        parent = load(path.parent / PARENT_NAME, LIBRARY)
        child = load(path, LIBRARY)
        for name, value in child.values.items():
            if parent.values.get(name) == value:
                restated.append(f"{_rel(path)}:{name}")
    assert restated == [], restated


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


@pytest.mark.parametrize(("mode", "cutout"), [("mask", True), ("opaque", False), ("blend", False)])
def test_alpha_mode_fans_out_to_use_cutout_alpha(mode: str, cutout: bool):
    res = resolve(from_data(_data(values={"alpha_mode": {"factor": mode}, "geometry_opacity": {"factor": 1.0}})))
    converted, _ = convert(res, V2)
    assert converted.values["use_cutout_alpha"]["factor"] is cutout
    assert "has_alpha" not in converted.values and "opacity_mask_bias" not in converted.values, "the v2 defaults stand"


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
    (tmp_path / PARENT_NAME).write_text(
        json.dumps(_data(title="Parent", doc="p", provenance=[{"source": "s", "note": "n"}])), encoding="utf-8"
    )
    (tmp_path / "child.material.json").write_text(json.dumps(_data(parent=PARENT_NAME)), encoding="utf-8")
    parent = load(tmp_path / PARENT_NAME, tmp_path)
    child = load(tmp_path / "child.material.json", tmp_path)
    assert parent.title == "Parent" and parent.provenance, "the parent carries the record"
    assert child.title is None and child.doc is None and child.provenance == [], "the child does not"
    resolved = resolve(child, tmp_path)
    assert len(resolved.chain) == 2, "the parent was followed"
    assert "title" not in resolved.values and "provenance" not in resolved.values, "the record is not a value"
    text = index(tmp_path)
    assert "| `child.material.json` (child) |  |  |" in text, "the index shows the child's own empty record"


# ------------------------------------------------------------------------------------------- the index


def test_the_index_equals_the_committed_page_and_lists_every_document():
    text = index(LIBRARY)
    assert text.startswith(INDEX_HEADER)
    assert INDEX.read_text(encoding="utf-8") == text, "run tools/generate_material_ui.py --write"
    for p in DOCUMENTS:
        assert f"`{p.name}`" in text
    for name, _ in DEFERRED:
        assert name in text
    assert "`specular_color`" in text and "geometry_normal strength" in text and "alpha_mode blend" in text
    assert "the mask threshold" in text and "opacity_mask_bias" in text


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
    (tmp_path / "stray.material.json").write_text(json.dumps(_data(title="S", doc="s")), encoding="utf-8")
    names = [p.relative_to(tmp_path).as_posix() for p in documents_under(tmp_path)]
    assert names == [
        "stray.material.json",
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


def test_the_sheet_layout_and_the_command_record():
    import contact_sheet as sheet

    assert sheet.sheet_layout(22, 192) == (1152, 4 * (192 + sheet.LABEL_H))
    assert sheet.sheet_layout(1, 32) == (192, 32 + sheet.LABEL_H)
    width, height = sheet.sheet_layout(26, 160)
    assert (width, height) == (960, 5 * (160 + sheet.LABEL_H)) and max(width, height) <= sheet.MAX_SIDE
    assert sheet.label_for("metal", "Gold", 160) == ("metal", "Gold")
    assert sheet.label_for("dielectric", "Glossy plastic, the long one", 64)[1].endswith(".")
    assert sheet.label_for("metal", "Metal plate", 160)[1] == "Metal plate", "thirteen characters fit at scale 2"
    assert sheet.label_for("rough", "Cobblestone floor", 160)[1] == "Cobblestone.", (
        "a longer title is cut with a dot, no floating space"
    )
    with pytest.raises(ValueError):
        sheet.sheet_layout(0, 192)
    import argparse

    defaults = argparse.Namespace(
        library=sheet.LIBRARY, out_dir=sheet.OUT_DIR, environment="studio_small_09", tile=192, exposure_ev=0.0
    )
    same = argparse.Namespace(**vars(defaults))
    assert sheet.command_line(same, defaults) == "uv run tools/wgpu/contact_sheet.py"
    changed = argparse.Namespace(**{**vars(defaults), "tile": 128, "environment": "citrus_orchard_road_puresky"})
    assert sheet.command_line(changed, defaults) == (
        "uv run tools/wgpu/contact_sheet.py --environment citrus_orchard_road_puresky --tile 128"
    )
    spaced = argparse.Namespace(**{**vars(defaults), "out_dir": sheet.ROOT / "verification" / "my sheet"})
    assert (
        sheet.command_line(spaced, defaults) == "uv run tools/wgpu/contact_sheet.py --out-dir 'verification/my sheet'"
    )


def test_the_sheet_prepares_every_document_before_the_device(tmp_path: Path):
    import contact_sheet as sheet

    prepared, losses = sheet.prepare(LIBRARY)
    assert len(prepared) == len(DOCUMENTS) and losses == [
        "specular_color",
        "specular_anisotropy",
        "specular_rotation",
        "specular_occlusion",
    ]
    assert all(binding.model == "legacy-v2" for _, _, binding, _ in prepared)
    # T3b: the four documents that bind a set carry their runtime textures; the constants-only ones carry none
    textured = {path.name.split(".")[0]: sorted(textures) for path, _, _, textures in prepared if textures}
    assert set(textured) == {"brick_wall_001", "cobblestone_floor_04", "brown_planks_03", "metal_plate"}
    assert "metalness" in textured["metal_plate"] and "metalness" not in textured["brick_wall_001"]
    with pytest.raises(MaterialError, match="nothing to render"):
        sheet.prepare(tmp_path)
    (tmp_path / "bad.material.json").write_text(
        json.dumps(_data(values={"base_metalness": {"factor": 2.0}})), encoding="utf-8"
    )
    with pytest.raises(MaterialError, match="cannot convert an invalid material"):
        sheet.prepare(tmp_path)


def test_the_bitmap_font_draws_every_label_character_and_boxes_the_unknown():
    import numpy as np

    from hogshade import bitmap_font as font

    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.,'/:()?":
        g = font.glyph(ch)
        assert g.shape == (7, 5) and (g.any() or ch == " ")
    assert font.glyph("a").tolist() == font.glyph("A").tolist(), "lower case draws its capital"
    assert font.glyph("%").tolist() == font.glyph("\u00e9").tolist(), "the unknown is one box, never dropped"
    assert font.text_width("abc", 1) == 17 and font.text_width("", 3) == 0
    assert (
        font.fit("metal / aluminium", 40, 1) == "metal."
    )  # six characters, the dot included, are 35 px; seven would be 41
    assert font.fit("abcd", 17, 1) == "ab." and font.fit("abcd", 5, 1) == "." and font.fit("abcd", 4, 1) == ""
    canvas = np.zeros((20, 60, 3), dtype=np.float32)
    font.draw_text(canvas, "AB", 1, 1, scale=1, colour=(1.0, 0.5, 0.0))
    assert canvas[..., 0].sum() > 0 and canvas[1, 2, 0] == 1.0 and canvas[1, 2, 1] == 0.5, (
        "ink lands where the glyph is"
    )
    font.draw_text(canvas, "ZZZZZZZZZZZZZZZZ", 50, 15, scale=2)  # clipped at the edge, no error
    font.draw_text(canvas, "A", -3, -3, scale=1)  # off the top-left corner, no error
    with pytest.raises(ValueError, match="scale is a positive integer"):
        font.draw_text(canvas, "A", 0, 0, scale=0)
