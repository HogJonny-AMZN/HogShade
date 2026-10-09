"""
HogShade: the capture request: host-neutral, canonical, hashed, and refused by field name when malformed.
Package: tests/compare/test_request
"""

from __future__ import annotations

import copy
import json

import pytest

from hogshade.compare import meshes
from hogshade.compare.request import CaptureRequest, RequestError

GOOD = {
    "id": "quad-sphere-roughness",
    "mesh": "quad-sphere",
    "camera": {
        "eye": [1.6, 1.0, 3.8],
        "target": [0.0, 0.05, 0.0],
        "up": [0.0, 1.0, 0.0],
        "fov_y_deg": 32.0,
        "near": 0.05,
        "far": 50.0,
    },
    "rig": {"environment": "studio_small_09", "rotation_deg": 0, "exposure_ev": 0},
    "size": [512, 512],
    "material": "content/materials/synthetic/default.material.json",
    "textures": "content/textures/synthetic",
    "debug_mode": 8,
    "view": "preview",
}


def _bad(path: str, value) -> dict:
    """GOOD with the dotted ``path`` replaced (or removed when ``value`` is the sentinel ``...``)."""
    data = copy.deepcopy(GOOD)
    node = data
    *head, last = path.split(".")
    for key in head:
        node = node[key]
    if value is ...:
        del node[last]
    else:
        node[last] = value
    return data


def test_a_request_round_trips_through_its_canonical_json() -> None:
    request = CaptureRequest.from_dict(GOOD)
    text = request.to_json()
    assert " " not in text and text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    again = CaptureRequest.from_json(text)
    assert again == request and again.to_json() == text and again.content_hash() == request.content_hash()


def test_integers_and_floats_for_the_same_number_hash_the_same() -> None:
    other = copy.deepcopy(GOOD)
    other["rig"]["rotation_deg"] = 0.0
    other["rig"]["exposure_ev"] = 0.0
    assert CaptureRequest.from_dict(other).content_hash() == CaptureRequest.from_dict(GOOD).content_hash()


def test_a_changed_field_changes_the_hash_and_a_key_order_does_not() -> None:
    base = CaptureRequest.from_dict(GOOD).content_hash()
    for path, value in (
        ("camera.fov_y_deg", 33.0),
        ("debug_mode", 9),
        ("size", [512, 544]),
        ("rig.exposure_ev", 1.0),
        ("material", None),
    ):
        assert CaptureRequest.from_dict(_bad(path, value)).content_hash() != base, path
    shuffled = dict(reversed(list(GOOD.items())))
    assert CaptureRequest.from_dict(shuffled).content_hash() == base


def test_the_request_names_no_host() -> None:
    """The same request is run through every host: a host field is refused as unknown, so none can ride along."""
    for extra in ({"host": "maya"}, {"host_version": "2026.3"}, {"adapter": "wgpu"}):
        with pytest.raises(RequestError, match=r"request: unknown field\(s\)"):
            CaptureRequest.from_dict({**GOOD, **extra})
    assert "host" not in CaptureRequest.from_dict(GOOD).to_json()


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("id", "Has Spaces", "id:"),
        ("id", "", "id:"),
        ("mesh", "polar-sphere", "mesh: one of"),
        ("size", [500, 512], "size: each side a positive multiple of 32"),
        ("size", [512, 8192], "size: each side a positive multiple of 32"),
        ("size", [512], "size: \\[width, height\\]"),
        ("size", [512.0, 512], "size: \\[width, height\\]"),
        ("debug_mode", -1, "debug_mode:"),
        ("debug_mode", True, "debug_mode:"),
        ("view", "linear", "view: one of"),
        ("material", "/abs/path.json", "material:"),
        ("material", "../outside.json", "material:"),
        ("material", "C:/x.json", "material:"),
        ("textures", "a\\\\b", "textures:"),
        ("camera.fov_y_deg", 0.0, "camera.fov_y_deg"),
        ("camera.fov_y_deg", 180.0, "camera.fov_y_deg"),
        ("camera.fov_y_deg", float("nan"), "camera.fov_y_deg: a finite number"),
        ("camera.fov_y_deg", True, "camera.fov_y_deg: a finite number"),
        ("camera.near", 0.0, "camera: 0 < near < far"),
        ("camera.far", 0.01, "camera: 0 < near < far"),
        ("camera.eye", [0.0, 0.05, 0.0], "camera: eye and target coincide"),
        ("camera.eye", [0.0, 3.0, 0.0], "camera.up:"),
        ("camera.up", [0.0, 0.0, 0.0], "camera.up:"),
        ("camera.up", [0.0, 1.0], "camera.up: three numbers"),
        ("camera.eye", [float("inf"), 0.0, 0.0], "camera.eye\\[0\\]: a finite number"),
        ("rig.environment", "Studio Small", "rig.environment:"),
        ("rig.rotation_deg", float("inf"), "rig.rotation_deg: a finite number"),
        ("rig.light", {"direction": [0.0, 0.0, 0.0], "intensity": 1.0, "color": [1, 1, 1]}, "rig.light.direction"),
        ("rig.light", {"direction": [0, 1, 0], "intensity": -1.0, "color": [1, 1, 1]}, "rig.light.intensity"),
        ("rig.light", {"direction": [0, 1, 0], "intensity": 1.0}, r"rig.light: missing field\(s\)"),
    ],
)
def test_a_malformed_field_is_refused_and_named(path: str, value, message: str) -> None:
    with pytest.raises(RequestError, match=message):
        CaptureRequest.from_dict(_bad(path, value))


@pytest.mark.parametrize("path", ["id", "mesh", "camera", "rig", "size", "camera.eye", "rig.environment"])
def test_a_missing_required_field_is_refused(path: str) -> None:
    with pytest.raises(RequestError, match=r"missing field\(s\)"):
        CaptureRequest.from_dict(_bad(path, ...))


def test_unknown_fields_inside_nested_objects_are_refused_too() -> None:
    for path in ("camera.roll", "rig.hdr"):
        data = _bad(path, 1.0)
        with pytest.raises(RequestError, match=r"unknown field\(s\)"):
            CaptureRequest.from_dict(data)


def test_text_that_is_not_json_or_not_an_object_is_refused() -> None:
    with pytest.raises(RequestError, match="not valid JSON"):
        CaptureRequest.from_json("{not json")
    with pytest.raises(RequestError, match="request: an object is expected"):
        CaptureRequest.from_json("[1, 2]")


def test_optional_fields_default_and_the_light_survives_a_round_trip() -> None:
    minimal = {k: GOOD[k] for k in ("id", "mesh", "camera", "rig", "size")}
    request = CaptureRequest.from_dict(minimal)
    assert (request.material, request.textures, request.debug_mode, request.view) == (None, None, 0, "preview")
    lit = copy.deepcopy(GOOD)
    lit["rig"]["light"] = {"direction": [0.45, 0.8, 0.4], "intensity": 3.0, "color": [1, 1, 1]}
    again = CaptureRequest.from_json(CaptureRequest.from_dict(lit).to_json())
    assert again.rig.light is not None and again.rig.light.intensity == 3.0


def test_the_canonical_mesh_ids_are_the_library_s_own() -> None:
    assert set(meshes.MESH_IDS) == {"shader-ball", "quad-sphere"}
    assert meshes.is_mesh_id("quad-sphere") and not meshes.is_mesh_id("polar-sphere") and not meshes.is_mesh_id(None)
    with pytest.raises(TypeError):
        meshes.MESH_IDS["other"] = "x"  # type: ignore[index]
