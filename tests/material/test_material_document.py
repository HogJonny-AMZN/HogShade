"""
HogShade: load(): the good fixtures parse raw, each broken path or version raises, an older document migrates.
Package: tests/material/test_material_document
"""

from __future__ import annotations

import json

import pytest

from hogshade.material import MaterialError, load
from hogshade.material.document import confine, from_data


def test_base_loads_raw(fixtures):
    doc = load(fixtures / "base" / "steel.material.json")
    assert doc.material_type == "hogshade-standard" and doc.material_type_version == 1
    assert doc.parent is None and doc.parent_path is None
    assert doc.values["base_color"] == {"factor": [0.18, 0.21, 0.24]}
    assert doc.ext == {"spritejammer": {"tier_cap": 2, "tag": "base"}}
    assert doc.root == (fixtures / "base").resolve()


def test_child_keeps_parent_as_a_path_not_followed(fixtures):
    doc = load(fixtures / "child.material.json")
    assert doc.parent == "base/steel.material.json"
    assert doc.parent_path == (fixtures / "base" / "steel.material.json").resolve()
    assert "specular_roughness" not in doc.values, "raw: the parent's values are not merged by load()"
    assert doc.values["base_color"]["blend"] == "multiply"


def test_root_overrides_the_document_directory(fixtures):
    doc = load(fixtures / "grandchild.material.json", root=fixtures)
    assert doc.root == fixtures.resolve()


def test_texture_outside_the_given_root_raises(fixtures):
    with pytest.raises(MaterialError, match="outside the package root"):
        load(fixtures / "child.material.json", root=fixtures / "base")


def test_dotdot_path_raises(fixtures):
    with pytest.raises(MaterialError, match=r"climbs with '\.\.'") as e:
        load(fixtures / "broken" / "dotdot_path.material.json")
    assert "../escape.png" in str(e.value) and "geometry_normal" in str(e.value)


@pytest.mark.parametrize(
    "value", ["C:/escape.png", "/escape.png", "//server/share/x.png", "\\\\server\\x.png", "D:\\x.png"]
)
def test_absolute_paths_raise(tmp_path, value):
    with pytest.raises(MaterialError, match="is absolute"):
        confine(value, tmp_path, tmp_path, "texture")


def test_absolute_fixture_raises(fixtures):
    with pytest.raises(MaterialError, match="is absolute"):
        load(fixtures / "broken" / "absolute_path.material.json")


def test_backslashes_normalise_to_posix(tmp_path):
    spelling, joined = confine("textures" + chr(92) + "a.png", tmp_path, tmp_path, "texture")
    assert spelling == "textures/a.png" and joined == (tmp_path / "textures" / "a.png").resolve()


@pytest.mark.parametrize("value", ["", None, 3])
def test_non_string_path_raises(tmp_path, value):
    with pytest.raises(MaterialError, match="non-empty relative path"):
        confine(value, tmp_path, tmp_path, "texture")


def test_newer_version_raises(fixtures):
    with pytest.raises(MaterialError, match="version 99, this library knows 1"):
        load(fixtures / "broken" / "newer_version.material.json")


def test_unknown_type_raises():
    with pytest.raises(MaterialError, match="unknown material type"):
        from_data({"material_type": "hogshade-phong", "material_type_version": 1, "values": {}})


@pytest.mark.parametrize(
    "data", [[], {"material_type": "hogshade-standard"}, {"material_type": 3, "material_type_version": 1, "values": {}}]
)
def test_malformed_document_raises(data):
    with pytest.raises(MaterialError):
        from_data(data)


def test_missing_file_and_bad_json_raise(tmp_path):
    with pytest.raises(MaterialError, match="no such document"):
        load(tmp_path / "nope.material.json")
    bad = tmp_path / "bad.material.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(MaterialError, match="not JSON"):
        load(bad)


def test_older_document_migrates_on_load(tmp_path, fake_type):
    def to_version_2(data):
        data["version"] = 2
        data["migrations"] = [
            {
                "from": 1,
                "to": 2,
                "ops": [
                    {"op": "rename", "from": "roughness", "to": "specular_roughness"},
                    {"op": "remove", "name": "gloss"},
                    {"op": "default", "name": "specular_ior", "value": 1.5},
                ],
            }
        ]

    fake_type(to_version_2)
    path = tmp_path / "old.material.json"
    path.write_text(
        json.dumps(
            {
                "material_type": "hogshade-standard",
                "material_type_version": 1,
                "values": {"roughness": {"factor": 0.3}, "gloss": {"factor": 1.0}, "base_metalness": {"factor": 1.0}},
            }
        ),
        encoding="utf-8",
    )
    doc = load(path)
    assert doc.material_type_version == 2
    assert doc.values == {"specular_roughness": {"factor": 0.3}, "base_metalness": {"factor": 1.0}}


def test_current_document_is_not_migrated(tmp_path, fake_type):
    def to_version_2(data):
        data["version"] = 2
        data["migrations"] = [{"from": 1, "to": 2, "ops": [{"op": "rename", "from": "base_metalness", "to": "metal"}]}]

    fake_type(to_version_2)
    path = tmp_path / "new.material.json"
    path.write_text(
        json.dumps(
            {
                "material_type": "hogshade-standard",
                "material_type_version": 2,
                "values": {"base_metalness": {"factor": 1.0}},
            }
        ),
        encoding="utf-8",
    )
    assert load(path).values == {"base_metalness": {"factor": 1.0}}


def test_loaded_paths_are_stored_normalised(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "steel.material.json").write_text(
        json.dumps({"material_type": "hogshade-standard", "material_type_version": 1, "values": {}}), encoding="utf-8"
    )
    backslashed = "base" + chr(92) + "steel.material.json"
    child = tmp_path / "child.material.json"
    child.write_text(
        json.dumps(
            {
                "material_type": "hogshade-standard",
                "material_type_version": 1,
                "parent": backslashed,
                "values": {"geometry_normal": {"texture": "./textures/n.png"}},
            }
        ),
        encoding="utf-8",
    )
    doc = load(child)
    assert doc.parent == "base/steel.material.json"
    assert doc.values["geometry_normal"]["texture"] == "textures/n.png"


def test_material_type_is_a_registry_name_not_a_path():
    for name in ("../hogshade-standard", "hogshade-standard/../hogshade-lambert", "schema/hogshade-standard"):
        with pytest.raises(MaterialError, match="unknown material type"):
            from_data({"material_type": name, "material_type_version": 1, "values": {}})


def test_unreadable_file_is_a_material_error(tmp_path):
    bad = tmp_path / "latin.material.json"
    bad.write_bytes(b'{"material_type": "hogshade-standard", "x": "\xe9"}')
    with pytest.raises(MaterialError, match="cannot read"):
        load(bad)
    with pytest.raises(MaterialError):
        load(tmp_path)  # a directory


def test_a_migration_is_logged_at_info(tmp_path, fake_type, caplog):
    import logging

    def to_version_2(data):
        data["version"] = 2
        data["migrations"] = [{"from": 1, "to": 2, "ops": [{"op": "remove", "name": "gloss"}]}]

    fake_type(to_version_2)
    path = tmp_path / "old.material.json"
    path.write_text(
        json.dumps({"material_type": "hogshade-standard", "material_type_version": 1, "values": {}}), encoding="utf-8"
    )
    with caplog.at_level(logging.INFO, logger="hogshade.material.document"):
        load(path)
    assert any("migrated from hogshade-standard version 1 to 2" in r.getMessage() for r in caplog.records)
