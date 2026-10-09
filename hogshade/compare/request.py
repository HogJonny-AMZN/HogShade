"""
HogShade: the capture request: everything a host needs to render one picture, and nothing host-specific.
Package: hogshade/compare/request

The same request is run through every host and hashes the same, because it names no host: the host and its version
belong to the adapter invocation and are recorded in the capture set's manifest (owner, 2026-10-08, amending the
comparison framework design). The request holds the material and the textures as repository-relative paths only; the
hash of what an adapter actually loaded goes in the manifest, so a request cannot go stale when a document changes.

Conventions (the design's section 3): metres, Y up, right-handed, vertical field of view in degrees, a bottom-left UV
origin, rotation in degrees about +Y, exposure in EV. Unknown fields are refused, so ``host`` or a typo cannot ride
along unnoticed. ``RequestError`` names the field.
"""

from __future__ import annotations

import hashlib
import json
import logging as _logging
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from hogshade.compare import meshes

_MODULE_NAME = "hogshade.compare.request"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The view transforms a request may name. The wgpu host supports only ``preview`` until the colour pipeline lands.
VIEWS = ("preview", "agx", "aces")

#: Readback alignment every host shares, and a ceiling so a typo cannot ask for a 1 GB frame.
SIZE_MULTIPLE = 32
SIZE_MAX = 4096

_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")

Vec3 = tuple[float, float, float]


class RequestError(ValueError):
    """A request that is malformed; the message names the field."""


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RequestError(f"{field}: a finite number is expected, got {value!r}")
    return float(value)


def _vec3(value: object, field: str) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise RequestError(f"{field}: three numbers are expected, got {value!r}")
    x, y, z = (_number(v, f"{field}[{i}]") for i, v in enumerate(value))
    return (x, y, z)


def _path(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RequestError(f"{field}: a repository-relative path or null is expected, got {value!r}")
    if value.startswith("/") or "\\" in value or re.match(r"^[A-Za-z]:", value) or ".." in value.split("/"):
        raise RequestError(f"{field}: a relative POSIX path without '..' is expected, got {value!r}")
    return value


def _fields(data: object, field: str, required: set[str], optional: set[str]) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise RequestError(f"{field}: an object is expected, got {type(data).__name__}")
    unknown = sorted(set(data) - required - optional)
    if unknown:
        raise RequestError(
            f"{field}: unknown field(s) {unknown}; the request names no host and nothing outside its schema"
        )
    missing = sorted(required - set(data))
    if missing:
        raise RequestError(f"{field}: missing field(s) {missing}")
    return data


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vec3) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


@dataclass(frozen=True)
class Camera:
    """A pinhole camera in the canonical frame: metres, Y up, right-handed."""

    eye: Vec3
    target: Vec3
    up: Vec3
    fov_y_deg: float
    near: float
    far: float

    @classmethod
    def from_dict(cls, data: object) -> Camera:
        d = _fields(data, "camera", {"eye", "target", "up", "fov_y_deg", "near", "far"}, set())
        eye, target, up = (_vec3(d[k], f"camera.{k}") for k in ("eye", "target", "up"))
        fov, near, far = (_number(d[k], f"camera.{k}") for k in ("fov_y_deg", "near", "far"))
        if not 0.0 < fov < 180.0:
            raise RequestError(f"camera.fov_y_deg: between 0 and 180 degrees is expected, got {fov}")
        if near <= 0.0 or far <= near:
            raise RequestError(f"camera: 0 < near < far is expected, got near {near}, far {far}")
        view = (target[0] - eye[0], target[1] - eye[1], target[2] - eye[2])
        if _norm(view) < 1e-9:
            raise RequestError("camera: eye and target coincide, so there is no view direction")
        if _norm(up) < 1e-9 or _norm(_cross(view, up)) < 1e-9 * _norm(view) * _norm(up):
            raise RequestError("camera.up: zero, or parallel to the view direction, so the camera has no roll")
        return cls(eye, target, up, fov, near, far)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eye": list(self.eye),
            "target": list(self.target),
            "up": list(self.up),
            "fov_y_deg": self.fov_y_deg,
            "near": self.near,
            "far": self.far,
        }


@dataclass(frozen=True)
class Light:
    """One directional light: the direction light travels from (towards the light), an intensity and a linear colour."""

    direction: Vec3
    intensity: float
    color: Vec3

    @classmethod
    def from_dict(cls, data: object) -> Light:
        d = _fields(data, "rig.light", {"direction", "intensity", "color"}, set())
        direction = _vec3(d["direction"], "rig.light.direction")
        if _norm(direction) < 1e-9:
            raise RequestError("rig.light.direction: a non-zero direction is expected")
        intensity = _number(d["intensity"], "rig.light.intensity")
        if intensity < 0.0:
            raise RequestError(f"rig.light.intensity: not negative, got {intensity}")
        return cls(direction, intensity, _vec3(d["color"], "rig.light.color"))

    def to_dict(self) -> dict[str, Any]:
        return {"direction": list(self.direction), "intensity": self.intensity, "color": list(self.color)}


@dataclass(frozen=True)
class Rig:
    """The lighting: a named cooked environment, its rotation about +Y in degrees, exposure in EV, an optional light."""

    environment: str
    rotation_deg: float = 0.0
    exposure_ev: float = 0.0
    light: Light | None = None

    @classmethod
    def from_dict(cls, data: object) -> Rig:
        d = _fields(data, "rig", {"environment"}, {"rotation_deg", "exposure_ev", "light"})
        env = d["environment"]
        if not isinstance(env, str) or not _ID.fullmatch(env):
            raise RequestError(f"rig.environment: a name like 'studio_small_09' is expected, got {env!r}")
        light = d.get("light")
        return cls(
            env,
            _number(d.get("rotation_deg", 0.0), "rig.rotation_deg"),
            _number(d.get("exposure_ev", 0.0), "rig.exposure_ev"),
            None if light is None else Light.from_dict(light),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "environment": self.environment,
            "rotation_deg": self.rotation_deg,
            "exposure_ev": self.exposure_ev,
        }
        if self.light is not None:
            out["light"] = self.light.to_dict()
        return out


@dataclass(frozen=True)
class CaptureRequest:
    """One picture to render: a mesh, a material, a rig, a camera, a size and what to show."""

    id: str
    mesh: str
    camera: Camera
    rig: Rig
    size: tuple[int, int]
    material: str | None = None
    textures: str | None = None
    debug_mode: int = 0
    view: str = "preview"

    @classmethod
    def from_dict(cls, data: object) -> CaptureRequest:
        d = _fields(
            data,
            "request",
            {"id", "mesh", "camera", "rig", "size"},
            {"material", "textures", "debug_mode", "view"},
        )
        ident = d["id"]
        if not isinstance(ident, str) or not _ID.fullmatch(ident):
            raise RequestError(f"id: lowercase letters, digits, '.', '_' or '-' are expected, got {ident!r}")
        mesh = d["mesh"]
        if not meshes.is_mesh_id(mesh):
            raise RequestError(f"mesh: one of {sorted(meshes.MESH_IDS)} is expected, got {mesh!r}")
        size = d["size"]
        if (
            not isinstance(size, (list, tuple))
            or len(size) != 2
            or any(isinstance(s, bool) or not isinstance(s, int) for s in size)
        ):
            raise RequestError(f"size: [width, height] as integers is expected, got {size!r}")
        for s in size:
            if s <= 0 or s % SIZE_MULTIPLE or s > SIZE_MAX:
                raise RequestError(
                    f"size: each side a positive multiple of {SIZE_MULTIPLE} up to {SIZE_MAX}, got {size!r}"
                )
        debug = d.get("debug_mode", 0)
        if isinstance(debug, bool) or not isinstance(debug, int) or debug < 0:
            raise RequestError(f"debug_mode: a non-negative integer is expected, got {debug!r}")
        view = d.get("view", "preview")
        if view not in VIEWS:
            raise RequestError(f"view: one of {list(VIEWS)} is expected, got {view!r}")
        return cls(
            id=ident,
            mesh=mesh,
            camera=Camera.from_dict(d["camera"]),
            rig=Rig.from_dict(d["rig"]),
            size=(int(size[0]), int(size[1])),
            material=_path(d.get("material"), "material"),
            textures=_path(d.get("textures"), "textures"),
            debug_mode=debug,
            view=view,
        )

    @classmethod
    def from_json(cls, text: str) -> CaptureRequest:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RequestError(f"request: not valid JSON ({e})") from e
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mesh": self.mesh,
            "camera": self.camera.to_dict(),
            "rig": self.rig.to_dict(),
            "size": list(self.size),
            "material": self.material,
            "textures": self.textures,
            "debug_mode": self.debug_mode,
            "view": self.view,
        }

    def to_json(self) -> str:
        """The canonical form (sorted keys, no whitespace): what the hash is taken over and ``request.json`` holds."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        """SHA-256 of the canonical JSON, hex. Equal for every host, since the request names none."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
