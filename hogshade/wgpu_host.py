"""
HogShade: the wgpu host. Loads the shader ball and the E1 environment, renders the legacy v2 model through
the forward pass and through the deferred pair, offscreen, and returns linear float images.
Package: hogshade/wgpu_host

The pass shaders live in hosts/wgpu/ and are stitched here in front of the committed core artifact
(hosts/wgpu/generated/hogshade_core.wgsl). Nothing in this module needs a window: the target is a
texture and the result is read back. tools/wgpu/viewport.py is the command line over it.
"""

from __future__ import annotations

import logging as _logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hogshade import mikktspace
from hogshade.ibl.dds import read_2d_rgba16f, read_cube_rgba16f
from hogshade.material.binding import WGPU_MODEL_IDS, WGPU_MODELS, pack_fields
from hogshade.material.generators import host_map
from hogshade.material.model import Binding
from hogshade.material.runtime import RuntimeTexture
from hogshade.testdata import quad_sphere as _quad_sphere
from hogshade.wgpu_textures import (
    BC_FEATURE,
    SLOTS,
    UNIFORM_BYTES,
    MaterialPlan,
    bind_group_entries,
    material_plan,
    material_sampler,
    neutral_texture,
)

_MODULE_NAME = "hogshade.wgpu_host"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

ROOT = Path(__file__).resolve().parents[1]
HOSTS_WGPU = ROOT / "hosts" / "wgpu"
CORE_WGSL = HOSTS_WGPU / "generated" / "hogshade_core.wgsl"
SHADER_BALL = ROOT / "content" / "shaderball" / "shaderBall.obj"
IBL_ROOT = ROOT / "content" / "ibl"
PASSES = ("lit_mesh", "gbuffer_fill", "deferred_light")
#: The passes that run the material half and so stitch material.wgsl (the texture slots at group 2, T3b).
MATERIAL_PASSES = ("lit_mesh", "gbuffer_fill")

# The host_Frame uniform in hosts/wgpu/common.wgsl, field for field, std140: matrices column-major.
FRAME_DTYPE = np.dtype(
    [
        ("view_proj", np.float32, (16,)),
        ("inv_view_proj", np.float32, (16,)),
        ("camera_ws", np.float32, (4,)),
        ("light_dir_ws", np.float32, (4,)),
        ("light_color", np.float32, (4,)),
        ("base_color", np.float32, (4,)),
        ("material", np.float32, (4,)),
        ("env", np.float32, (4,)),
        ("sky", np.float32, (4,)),
        ("ground", np.float32, (4,)),
        ("up_ws", np.float32, (4,)),
        ("viewport", np.float32, (4,)),
        ("model", np.float32, (4,)),
        ("params_a", np.float32, (4,)),
        ("params_b", np.float32, (4,)),
        ("sh9", np.float32, (9, 4)),
    ]
)
FRAME_BYTES = 480
MODELS = WGPU_MODEL_IDS  # one table: HOGSHADE_MODEL_* ids, owned by the binder
#: The material type each model renders (the inverse of the binder's WGPU_MODELS).
WGPU_TYPES = {model: type_name for type_name, model in WGPU_MODELS.items()}
DEPTH_FORMAT = "depth32float"
COLOR_FORMAT = "rgba16float"
GBUFFER_FORMATS = ("rgba8unorm-srgb", "rgba16float", "rgba8uint", "rg11b10ufloat")


def lfs_hydrated(path: Path) -> bool:
    """False when ``path`` is a Git LFS pointer file rather than the payload (a checkout without LFS)."""
    try:
        with path.open("rb") as fh:
            return not fh.read(64).startswith(b"version https://git-lfs")
    except OSError:
        return False


def stitch_pass(name: str) -> str:
    """
    Core, then common.wgsl, then material.wgsl for a pass that runs the material half, then the pass file: what a
    wgpu pipeline compiles for pass ``name``.
    """
    if name not in PASSES:
        raise ValueError(f"unknown pass {name!r}; one of {PASSES}")
    parts = [CORE_WGSL, HOSTS_WGPU / "common.wgsl"]
    if name in MATERIAL_PASSES:
        parts.append(HOSTS_WGPU / "material.wgsl")
    parts.append(HOSTS_WGPU / f"{name}.wgsl")
    return "\n".join(p.read_text(encoding="utf-8") for p in parts)


# ----------------------------------------------------------------------------- mesh


@dataclass
class Mesh:
    """
    A triangle mesh for the host: ``vertices`` ``(n, 12)`` float32 as position, normal, uv, tangent with its
    handedness sign in the fourth component (``VERTEX_STRIDE`` bytes), ``indices`` ``(m,)`` uint32. The normals
    are the source's (MikkTSpace consumes them as given); the tangents are MikkTSpace's, and ``tangent_basis``
    says so (``mikktspace``), or ``unknown`` when a file carried tangents nobody vouched for (the host logs and
    regenerates), or ``none`` while a mesh has no UVs (the shaders fall back to an arbitrary frame).
    """

    vertices: NDArray[np.float32]
    indices: NDArray[np.uint32]
    tangent_basis: str = "mikktspace"


VERTEX_FLOATS = 12
VERTEX_STRIDE = VERTEX_FLOATS * 4
#: The columns of ``Mesh.vertices``: position, normal, uv, the tangent and its handedness sign.
COL_POSITION, COL_NORMAL, COL_UV, COL_TANGENT = slice(0, 3), slice(3, 6), slice(6, 8), slice(8, 11)
COL_TANGENT_SIGN = 11
#: The scene camera's clip planes (``Scene.view_proj``) and the linear distance a (0, 1) clip depth stands for.
NEAR_PLANE, FAR_PLANE = 0.1, 50.0


def with_tangents(
    positions: NDArray[np.floating],
    normals: NDArray[np.floating],
    uvs: NDArray[np.floating] | None,
    indices: NDArray[np.integer],
    tangents: NDArray[np.floating] | None = None,
    tangent_basis: str = "none",
) -> Mesh:
    """
    The host's mesh from arrays: MikkTSpace tangents generated when UVs are present (the standard's requirement,
    the normals as given), a zero tangent with sign +1 and ``tangent_basis="none"`` when they are not. A source
    that carries tangents passes them as ``(n, 4)`` with the sign in ``w`` and names their basis: ``mikktspace``
    is used as given; ``unknown`` (baked tangents nobody vouched for) is flagged with a WARNING and regenerated,
    the owner's rule; any other basis is a validation failure (``ValueError``), the content standard's. A vertex
    that faces of both handednesses share is split for its mirrored corners before the tangents are generated
    (``mikktspace.split_mixed_handedness``), so the mesh may come back with more vertices than it was given.
    """
    n = positions.shape[0]
    if tangent_basis not in mikktspace.TANGENT_BASES:
        raise ValueError(
            f"tangent basis {tangent_basis!r} is not one of {mikktspace.TANGENT_BASES}; the project requires MikkTSpace"
        )
    if tangents is not None and np.asarray(tangents).shape != (n, 4):
        raise ValueError(f"tangents are (n, 4) with the sign in w; got {np.asarray(tangents).shape} for {n} vertices")
    if uvs is None:
        uv = np.zeros((n, 2), dtype=np.float32)
        tangent = np.zeros((n, 4), dtype=np.float32)
        tangent[:, 3] = 1.0
        basis = "none"
    else:
        uv = np.asarray(uvs, dtype=np.float32)
        if tangents is not None and tangent_basis == "mikktspace":
            given = np.asarray(tangents, dtype=np.float32)
            t, s = given[:, :3], given[:, 3]
        else:
            if tangents is not None:
                _LOGGER.warning(
                    f"{n} vertices carry tangents of {tangent_basis} basis: regenerated as MikkTSpace, the "
                    f"basis every host here assumes (the content standard)"
                )
            positions, normals, uv, indices, n_split = mikktspace.split_mixed_handedness(
                positions, normals, uv, indices
            )
            if n_split:
                _LOGGER.info(f"{n_split} vertex/vertices split for a mirrored seam: {positions.shape[0]} vertices now")
            uv = np.asarray(uv, dtype=np.float32)
            t, s = mikktspace.tangents(positions, normals, uv, indices)
        tangent = np.concatenate([t, s[:, None]], axis=1)
        basis = "mikktspace"
    verts = np.concatenate(
        [np.asarray(positions, dtype=np.float32), np.asarray(normals, dtype=np.float32), uv, tangent], axis=1
    )
    return Mesh(np.ascontiguousarray(verts, dtype=np.float32), np.asarray(indices, dtype=np.uint32).reshape(-1), basis)


@dataclass
class ObjRecords:
    """An OBJ's records as read: the v, vt and vn arrays and each face as its corners' 1-based (v, vt, vn)."""

    positions: list[list[float]]
    texcoords: list[list[float]]
    normals: list[list[float]]
    faces: list[list[tuple[int, int, int]]]


def _floats(line: str, count: int) -> list[float]:
    """The first ``count`` numbers of a v, vt or vn record; fewer is a malformed record."""
    values = [float(x) for x in line.split()[1 : 1 + count]]
    if len(values) < count:
        raise ValueError(f"{count} numbers expected, {len(values)} given")
    return values


def read_obj(path: Path) -> ObjRecords:
    """The v, vt, vn and f (v/vt/vn) records of an OBJ; a malformed record names the file and its line."""
    records = ObjRecords([], [], [], [])
    with Path(path).open(encoding="utf-8", errors="replace") as fh:
        for number, line in enumerate(fh, start=1):
            try:
                if line.startswith("v "):
                    records.positions.append(_floats(line, 3))
                elif line.startswith("vt "):
                    records.texcoords.append(_floats(line, 2))
                elif line.startswith("vn "):
                    records.normals.append(_floats(line, 3))
                elif line.startswith("f "):
                    face: list[tuple[int, int, int]] = []
                    for token in line.split()[1:]:
                        parts = token.split("/")
                        vi = int(parts[0])
                        ti = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                        ni = int(parts[2]) if len(parts) > 2 and parts[2] else 0
                        face.append((vi, ti, ni))
                    records.faces.append(face)
            except (ValueError, IndexError) as e:
                raise ValueError(f"{path}:{number}: malformed OBJ record {line.strip()!r}: {e}") from e
    return records


def _face_hand(face_keys: list[tuple[int, int, int]], texcoords: list[list[float]]) -> int:
    """The UV handedness of an OBJ face (+1, or -1 for a mirrored one), from its polygon's signed UV area; +1
    without UVs. Part of the corner key so a seam vertex both sides share is two vertices, as MikkTSpace wants."""
    if not texcoords or any(ti == 0 for _, ti, _ in face_keys):
        return 1
    uv = [texcoords[ti - 1] for _, ti, _ in face_keys]
    area = 0.0
    for k in range(len(uv)):
        u0, v0 = uv[k]
        u1, v1 = uv[(k + 1) % len(uv)]
        area += u0 * v1 - u1 * v0
    return -1 if area < 0.0 else 1


def load_obj(path: Path) -> Mesh:
    """
    A minimal OBJ reader: v, vt, vn and f (v/vt/vn) records; quads and fans are triangulated; a corner is keyed
    on (v, vt, vn) and its face's UV handedness, the weld MikkTSpace uses with the mirrored side kept apart (a
    seam vertex both sides share becomes two). Tangents are generated (an OBJ carries none); a file without
    ``vt`` gives a mesh with ``tangent_basis="none"``.
    """
    records = read_obj(path)
    positions, texcoords, normals = records.positions, records.texcoords, records.normals
    corners: dict[tuple[int, int, int, int], int] = {}
    vertices: list[tuple[float, ...]] = []
    tris: list[int] = []
    for face_keys in records.faces:
        face: list[int] = []
        hand = _face_hand(face_keys, texcoords)
        for vi, ti, ni in face_keys:
            key = (vi, ti, ni, hand)
            idx = corners.get(key)
            if idx is None:
                idx = len(vertices)
                corners[key] = idx
                p = positions[vi - 1]
                n = normals[ni - 1] if ni else [0.0, 1.0, 0.0]
                t = texcoords[ti - 1] if ti else [0.0, 0.0]
                vertices.append((*p, *n, *t))
            face.append(idx)
        for k in range(1, len(face) - 1):
            tris.extend((face[0], face[k], face[k + 1]))
    verts = np.asarray(vertices, dtype=np.float32)
    if len(verts) == 0:
        raise ValueError(f"no faces in {path}")
    has_uv = bool(texcoords)
    mesh = with_tangents(verts[:, :3], verts[:, 3:6], verts[:, 6:8] if has_uv else None, np.asarray(tris))
    _LOGGER.info(
        f"loaded {path.name}: {len(verts)} corners, {len(tris) // 3} triangles, uvs {'yes' if has_uv else 'no'}, "
        f"tangents {mesh.tangent_basis}"
    )
    return mesh


def normalise_mesh(mesh: Mesh, size: float = 2.0) -> Mesh:
    """Centre the mesh on the origin and scale its longest extent to ``size``; normals renormalised."""
    pos = mesh.vertices[:, :3]
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    centre = (lo + hi) * 0.5
    scale = size / max(float((hi - lo).max()), 1e-6)
    out = mesh.vertices.copy()
    out[:, :3] = (pos - centre) * scale
    n = out[:, 3:6]
    out[:, 3:6] = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-8)
    return Mesh(out, mesh.indices, mesh.tangent_basis)  # uv and tangent columns pass through untouched


# ----------------------------------------------------------------------------- camera


def look_at(eye: NDArray, target: NDArray, up: NDArray) -> NDArray:
    """Right-handed view matrix (camera looks down -Z), row-major, acts on column vectors."""
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def perspective(fov_y_deg: float, aspect: float, near: float, far: float) -> NDArray:
    """Perspective projection with wgpu's (0, 1) clip depth, row-major."""
    f = 1.0 / math.tan(math.radians(fov_y_deg) * 0.5)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = far / (near - far)
    m[2, 3] = near * far / (near - far)
    m[3, 2] = -1.0
    return m


def linear_depth(clip_depth: NDArray) -> NDArray:
    """The view-space distance a ``perspective`` (0, 1) clip depth stands for (``NEAR_PLANE`` to ``FAR_PLANE``)."""
    return NEAR_PLANE * FAR_PLANE / (FAR_PLANE - clip_depth * (FAR_PLANE - NEAR_PLANE))


def orbit_eye(yaw_deg: float, pitch_deg: float, distance: float) -> NDArray:
    cy, sy = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    cp, sp = math.cos(math.radians(pitch_deg)), math.sin(math.radians(pitch_deg))
    return np.array([distance * cp * sy, distance * sp, distance * cp * cy])


# ----------------------------------------------------------------------------- scene


@dataclass
class MaterialBinding:
    """
    The material-owned values the frame carries, in the schema's names. The defaults are the legacy v2
    type's schema defaults (S3: the schema is the one source of a default). ``fields()`` packs them through
    the wgpu host map, the same path ``hogshade.material.bind()`` takes, so a hand-set material and a bound
    document cannot disagree on where a value lands.
    """

    model: str = "legacy-v2"
    base_color: tuple[float, float, float] = (0.6, 0.6, 0.6)
    roughness: float = 0.5
    metalness: float = 0.0
    specular: float = 1.0
    specular_tint: float = 0.0
    ior: float = 1.45
    rough_is_gloss: bool = False
    # legacy v1 Disney lobes
    subsurface: float = 0.0
    anisotropic: float = 0.0
    sheen: float = 0.0
    sheen_tint: float = 0.0
    clearcoat: float = 0.0
    clearcoat_gloss: float = 0.0

    @property
    def material_type(self) -> str:
        if self.model not in WGPU_TYPES:
            raise ValueError(f"model {self.model!r} is not one of {sorted(WGPU_TYPES)}")
        return WGPU_TYPES[self.model]

    def fields(self) -> dict[str, tuple[float, ...]]:
        """The host map's frame fields at full width, the model id in ``model[0]``."""
        factors = {name: getattr(self, name) for name in _BINDING_PARAMETERS}
        factors["base_color"] = list(self.base_color)
        packed = pack_fields(host_map("wgpu"), self.material_type, factors)
        packed["model"][0] = float(MODELS[self.model])
        return {name: tuple(values) for name, values in packed.items()}


#: What ``Scene.material`` accepts: a hand-set material, or the record ``hogshade.material.bind()`` returns.
Material = MaterialBinding | Binding

_BINDING_PARAMETERS = (
    "roughness",
    "metalness",
    "specular",
    "specular_tint",
    "ior",
    "rough_is_gloss",
    "subsurface",
    "anisotropic",
    "sheen",
    "sheen_tint",
    "clearcoat",
    "clearcoat_gloss",
)


def _material_fields(material: Material) -> dict[str, tuple[float, ...]]:
    """The frame fields of either kind of material; a ``Binding`` for another host is refused."""
    if isinstance(material, Binding):
        if material.host != "wgpu":
            raise ValueError(f"a {material.host!r} binding cannot drive the wgpu host")
        return material.fields
    return material.fields()


@dataclass
class Scene:
    """Everything the frame uniform carries, in plain numbers. Colours are linear."""

    width: int = 1024
    height: int = 1024
    yaw_deg: float = 32.0
    pitch_deg: float = 18.0
    distance: float = 4.0
    fov_y_deg: float = 32.0
    material: Material = field(default_factory=MaterialBinding)
    light_dir: tuple[float, float, float] = (0.45, 0.8, 0.4)
    light_intensity: float = 3.0
    light_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    light_shadow: float = 1.0
    env_exposure: float = 1.0
    debug_mode: int = 0
    hemisphere_mode: int = 0
    sky: tuple[float, float, float] = (0.4, 0.5, 0.7)
    ground: tuple[float, float, float] = (0.2, 0.15, 0.1)
    environment: str = "studio_small_09"
    sh9: NDArray = field(default_factory=lambda: np.zeros((9, 3)))
    #: The document's textures in their runtime form (``hogshade.material.runtime.runtime_textures`` of the
    #: binding's ``textures`` against the document's directory); None or empty renders every slot neutral (T3b).
    textures: dict[str, RuntimeTexture] | None = None
    #: An explicit camera ``(eye, target, up)`` in world metres, Y up. None keeps the orbit (``yaw_deg``, ``pitch_deg``,
    #: ``distance`` about a fixed target); the comparison framework's adapter sets it from a capture request.
    camera: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]] | None = None
    _plan: tuple[dict[str, RuntimeTexture], MaterialPlan] | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @property
    def model(self) -> str:
        return self.material.model  # both kinds of material carry it

    def plan(self) -> MaterialPlan:
        """
        The material plan the textures become: bits, selectors and a source per slot; empty when untextured.
        Built once per distinct ``textures`` content (so a scene rendered many times logs its plan once).
        """
        textures = dict(self.textures or {})
        if self._plan is None or self._plan[0] != textures:
            self._plan = (textures, material_plan(textures))
        return self._plan[1]

    def view_proj(self) -> tuple[NDArray, NDArray]:
        if self.camera is None:
            eye = orbit_eye(self.yaw_deg, self.pitch_deg, self.distance)
            target, up = np.array([0.0, 0.05, 0.0]), np.array([0.0, 1.0, 0.0])
        else:
            eye, target, up = (np.asarray(v, dtype=np.float64) for v in self.camera)
        view = look_at(eye, target, up)
        proj = perspective(self.fov_y_deg, self.width / self.height, NEAR_PLANE, FAR_PLANE)
        return proj @ view, eye

    def frame_bytes(self, specular_mip_count: int) -> bytes:
        vp, eye = self.view_proj()
        frame = np.zeros((), dtype=FRAME_DTYPE)
        frame["view_proj"] = vp.T.astype(np.float32).ravel()  # column-major for WGSL
        frame["inv_view_proj"] = np.linalg.inv(vp).T.astype(np.float32).ravel()
        frame["camera_ws"] = (*eye, 1.0)
        ld = np.asarray(self.light_dir, dtype=np.float64)
        ld = ld / np.linalg.norm(ld)
        frame["light_dir_ws"] = (*ld, self.light_intensity)
        frame["light_color"] = (*self.light_color, self.light_shadow)
        for name, values in _material_fields(self.material).items():  # the host map's fields, one loop
            frame[name] = values
        frame["env"] = (
            float(specular_mip_count),
            self.env_exposure,
            float(self.debug_mode),
            float(self.hemisphere_mode),
        )
        frame["sky"] = (*self.sky, 0.0)
        frame["ground"] = (*self.ground, 0.0)
        frame["up_ws"] = (0.0, 1.0, 0.0, 0.0)
        frame["viewport"] = (float(self.width), float(self.height), 0.0, 0.0)
        sh = np.zeros((9, 4), dtype=np.float32)
        sh[:, :3] = np.asarray(self.sh9, dtype=np.float32)[:9]
        frame["sh9"] = sh
        data = frame.tobytes()
        assert len(data) == FRAME_BYTES, len(data)
        return data


@dataclass
class Frames:
    """Linear float images (H, W, 3) from one render: forward, deferred, the deferred depth mask and the depth."""

    forward: NDArray
    deferred: NDArray
    covered: NDArray  # (H, W) bool: pixels the ball covers (depth written)
    depth: NDArray | None = None  # (H, W) float32: the deferred pass's depth buffer, (0, 1) clip depth, 1 where empty

    def difference(self) -> tuple[float, float]:
        """(mean, max) absolute difference between the paths over covered pixels."""
        d = np.abs(self.forward - self.deferred)[self.covered]
        return float(d.mean()) if d.size else 0.0, float(d.max()) if d.size else 0.0


# ----------------------------------------------------------------------------- renderer


class Renderer:
    """Owns a device, the mesh, the environment textures and the three pipelines; renders a Scene."""

    def __init__(self, device, mesh: Mesh, environment: str = "studio_small_09") -> None:
        import wgpu

        self.wgpu = wgpu
        self.device = device
        self.mesh = mesh
        self.gb3_format = GBUFFER_FORMATS[3]
        if "rg11b10ufloat-renderable" not in getattr(device, "features", ()):
            self.gb3_format = "rgba16float"
            _LOGGER.warning("rg11b10ufloat-renderable is unavailable on this device: GB3 falls back to rgba16float")
        self._upload_mesh()
        self.specular_mip_count = self._upload_environment(environment)
        self._build_layouts()
        self._build_pipelines()
        self._targets: dict = {}
        self._texture_cache: dict[str, object] = {}  # DDS path -> texture, shared by every document over a set
        self._material_groups: dict[tuple, object] = {}  # MaterialPlan.key -> bind group
        self._neutral = {slot: neutral_texture(device, slot) for slot in SLOTS}
        self._neutral["sampler"] = material_sampler(device)
        self.bind_material_none = self._material_group(MaterialPlan())
        _LOGGER.info(
            f"wgpu host ready: mesh {len(mesh.vertices)} vertices, environment {environment} "
            f"({self.specular_mip_count} specular mips), GB3 {self.gb3_format}"
        )

    # ---- resources
    def _upload_mesh(self) -> None:
        wgpu = self.wgpu
        self.vertex_buffer = self.device.create_buffer_with_data(
            data=np.ascontiguousarray(self.mesh.vertices, dtype=np.float32).tobytes(), usage=wgpu.BufferUsage.VERTEX
        )
        self.index_buffer = self.device.create_buffer_with_data(
            data=np.ascontiguousarray(self.mesh.indices, dtype=np.uint32).tobytes(), usage=wgpu.BufferUsage.INDEX
        )
        self.index_count = len(self.mesh.indices)

    def _upload_cube(self, mips: list[NDArray]):
        wgpu = self.wgpu
        n = mips[0].shape[1]
        tex = self.device.create_texture(
            size=(n, n, 6),
            mip_level_count=len(mips),
            format=COLOR_FORMAT,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        for level, faces in enumerate(mips):
            m = faces.shape[1]
            for face in range(6):
                data = np.ascontiguousarray(faces[face], dtype=np.float16).tobytes()
                self.device.queue.write_texture(
                    {"texture": tex, "mip_level": level, "origin": (0, 0, face)},
                    data,
                    {"offset": 0, "bytes_per_row": m * 8, "rows_per_image": m},
                    (m, m, 1),
                )
        return tex

    def _upload_environment(self, environment: str) -> int:
        wgpu = self.wgpu
        cooked = IBL_ROOT / environment / "cooked"
        spec = read_cube_rgba16f(cooked / "specular.dds")
        irr = read_cube_rgba16f(cooked / "irradiance.dds")
        lut = read_2d_rgba16f(IBL_ROOT / "brdf_lut.dds")
        self.specular_tex = self._upload_cube(spec)
        self.irradiance_tex = self._upload_cube(irr)
        h, w = lut.shape[:2]
        self.lut_tex = self.device.create_texture(
            size=(w, h, 1), format=COLOR_FORMAT, usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST
        )
        self.device.queue.write_texture(
            {"texture": self.lut_tex, "mip_level": 0, "origin": (0, 0, 0)},
            np.ascontiguousarray(lut, dtype=np.float16).tobytes(),
            {"offset": 0, "bytes_per_row": w * 8, "rows_per_image": h},
            (w, h, 1),
        )
        self.cube_sampler = self.device.create_sampler(
            mag_filter="linear", min_filter="linear", mipmap_filter="linear", max_anisotropy=1
        )
        self.lut_sampler = self.device.create_sampler(
            mag_filter="linear", min_filter="linear", address_mode_u="clamp-to-edge", address_mode_v="clamp-to-edge"
        )
        self.frame_buffer = self.device.create_buffer(
            size=FRAME_BYTES, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST
        )
        return len(spec)

    def _build_layouts(self) -> None:
        wgpu = self.wgpu
        frag = wgpu.ShaderStage.FRAGMENT
        both = wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT
        tex = lambda sample_type, dim: {"sample_type": sample_type, "view_dimension": dim}
        self.layout_frame = self.device.create_bind_group_layout(
            entries=[{"binding": 0, "visibility": both, "buffer": {"type": "uniform"}}]
        )
        self.layout_env = self.device.create_bind_group_layout(
            entries=[
                {"binding": 0, "visibility": frag, "texture": tex("float", "cube")},
                {"binding": 1, "visibility": frag, "texture": tex("float", "cube")},
                {"binding": 2, "visibility": frag, "texture": tex("float", "2d")},
                {"binding": 3, "visibility": frag, "sampler": {"type": "filtering"}},
                {"binding": 4, "visibility": frag, "sampler": {"type": "filtering"}},
            ]
        )
        self.layout_gbuffer = self.device.create_bind_group_layout(
            entries=[
                {"binding": 0, "visibility": frag, "texture": tex("float", "2d")},
                {"binding": 1, "visibility": frag, "texture": tex("float", "2d")},
                {"binding": 2, "visibility": frag, "texture": tex("uint", "2d")},
                {"binding": 3, "visibility": frag, "texture": tex("float", "2d")},
                {"binding": 4, "visibility": frag, "texture": tex("depth", "2d")},
            ]
        )
        # T3b: the material slots (material.wgsl), group 2 of the two passes that run the material half
        self.layout_material = self.device.create_bind_group_layout(
            entries=[{"binding": k, "visibility": frag, "texture": tex("float", "2d")} for k in range(len(SLOTS))]
            + [
                {"binding": 4, "visibility": frag, "sampler": {"type": "filtering"}},
                {"binding": 5, "visibility": frag, "buffer": {"type": "uniform"}},
            ]
        )
        self.bind_frame = self.device.create_bind_group(
            layout=self.layout_frame,
            entries=[{"binding": 0, "resource": {"buffer": self.frame_buffer, "offset": 0, "size": FRAME_BYTES}}],
        )
        self.bind_env = self.device.create_bind_group(
            layout=self.layout_env,
            entries=[
                {"binding": 0, "resource": self.specular_tex.create_view(dimension="cube")},
                {"binding": 1, "resource": self.irradiance_tex.create_view(dimension="cube")},
                {"binding": 2, "resource": self.lut_tex.create_view()},
                {"binding": 3, "resource": self.cube_sampler},
                {"binding": 4, "resource": self.lut_sampler},
            ],
        )

    def _mesh_vertex_state(self, module) -> dict:
        wgpu = self.wgpu
        return {
            "module": module,
            "entry_point": "vs_main",
            "buffers": [
                {
                    "array_stride": VERTEX_STRIDE,
                    "step_mode": wgpu.VertexStepMode.vertex,
                    "attributes": [
                        {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                        {"format": wgpu.VertexFormat.float32x3, "offset": 12, "shader_location": 1},
                        {"format": wgpu.VertexFormat.float32x2, "offset": 24, "shader_location": 2},
                        {"format": wgpu.VertexFormat.float32x4, "offset": 32, "shader_location": 3},
                    ],
                }
            ],
        }

    def _build_pipelines(self) -> None:
        wgpu = self.wgpu
        d = self.device
        modules = {name: d.create_shader_module(code=stitch_pass(name)) for name in PASSES}
        primitive = {
            "topology": wgpu.PrimitiveTopology.triangle_list,
            "cull_mode": wgpu.CullMode.none,
            "front_face": wgpu.FrontFace.ccw,
        }
        depth = {"format": DEPTH_FORMAT, "depth_write_enabled": True, "depth_compare": wgpu.CompareFunction.less}
        self.pipe_forward = d.create_render_pipeline(
            layout=d.create_pipeline_layout(
                bind_group_layouts=[self.layout_frame, self.layout_env, self.layout_material]
            ),
            vertex=self._mesh_vertex_state(modules["lit_mesh"]),
            primitive=primitive,
            depth_stencil=depth,
            fragment={"module": modules["lit_mesh"], "entry_point": "fs_main", "targets": [{"format": COLOR_FORMAT}]},
        )
        gb_formats = list(GBUFFER_FORMATS[:3]) + [self.gb3_format]
        # the fill pass reads no environment, but material.wgsl puts the slots at group 2 for both mesh passes
        self.pipe_fill = d.create_render_pipeline(
            layout=d.create_pipeline_layout(
                bind_group_layouts=[self.layout_frame, self.layout_env, self.layout_material]
            ),
            vertex=self._mesh_vertex_state(modules["gbuffer_fill"]),
            primitive=primitive,
            depth_stencil=depth,
            fragment={
                "module": modules["gbuffer_fill"],
                "entry_point": "fs_main",
                "targets": [{"format": f} for f in gb_formats],
            },
        )
        self.pipe_light = d.create_render_pipeline(
            layout=d.create_pipeline_layout(
                bind_group_layouts=[self.layout_frame, self.layout_env, self.layout_gbuffer]
            ),
            vertex={"module": modules["deferred_light"], "entry_point": "vs_main"},
            primitive=primitive,
            fragment={
                "module": modules["deferred_light"],
                "entry_point": "fs_main",
                "targets": [{"format": COLOR_FORMAT}],
            },
        )

    def _material_group(self, plan: MaterialPlan) -> Any:
        """
        The bind group for a plan, built once per distinct key (two documents over one set that bind different
        subsets get two groups; the DDS uploads behind them are shared by path).
        """
        group = self._material_groups.get(plan.key)
        if group is not None:
            return group
        wgpu = self.wgpu
        uniform = self.device.create_buffer_with_data(data=plan.uniform_bytes(), usage=wgpu.BufferUsage.UNIFORM)
        entries = bind_group_entries(self.device, plan, self._texture_cache, self._neutral)
        entries.append({"binding": 5, "resource": {"buffer": uniform, "offset": 0, "size": UNIFORM_BYTES}})
        group = self.device.create_bind_group(layout=self.layout_material, entries=entries)
        self._material_groups[plan.key] = group
        _LOGGER.info(
            f"material bind group {len(self._material_groups)}: {len(plan.sources)} slot(s) from files "
            f"({', '.join(sorted(plan.sources)) or 'none'}), bits {plan.bound:#x}, "
            f"{len(self._texture_cache)} texture(s) resident"
        )
        return group

    def _ensure_targets(self, width: int, height: int) -> dict:
        wgpu = self.wgpu
        if self._targets.get("size") == (width, height):
            return self._targets
        attach = wgpu.TextureUsage.RENDER_ATTACHMENT
        readable = attach | wgpu.TextureUsage.COPY_SRC
        bindable = attach | wgpu.TextureUsage.TEXTURE_BINDING
        make = lambda fmt, usage: self.device.create_texture(size=(width, height, 1), format=fmt, usage=usage)
        gb_formats = list(GBUFFER_FORMATS[:3]) + [self.gb3_format]
        t = {
            "size": (width, height),
            "forward": make(COLOR_FORMAT, readable),
            "deferred": make(COLOR_FORMAT, readable),
            "depth_forward": make(DEPTH_FORMAT, attach),
            "depth": make(DEPTH_FORMAT, bindable | wgpu.TextureUsage.COPY_SRC),
            "gbuffer": [make(f, bindable) for f in gb_formats],
        }
        t["bind_gbuffer"] = self.device.create_bind_group(
            layout=self.layout_gbuffer,
            entries=[{"binding": k, "resource": t["gbuffer"][k].create_view()} for k in range(4)]
            + [{"binding": 4, "resource": t["depth"].create_view()}],
        )
        self._targets = t
        return t

    # ---- drawing
    def _draw_mesh(self, encoder, pipeline, color_views: list, depth_view, bind_groups: list) -> None:
        wgpu = self.wgpu
        rpass = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": v,
                    "resolve_target": None,
                    "clear_value": (0.0, 0.0, 0.0, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
                for v in color_views
            ],
            depth_stencil_attachment={
                "view": depth_view,
                "depth_clear_value": 1.0,
                "depth_load_op": wgpu.LoadOp.clear,
                "depth_store_op": wgpu.StoreOp.store,
            },
        )
        rpass.set_pipeline(pipeline)
        for k, bg in enumerate(bind_groups):
            rpass.set_bind_group(k, bg)
        rpass.set_vertex_buffer(0, self.vertex_buffer)
        rpass.set_index_buffer(self.index_buffer, wgpu.IndexFormat.uint32)
        rpass.draw_indexed(self.index_count)
        rpass.end()

    def _read_texture(self, texture, width: int, height: int, bytes_per_pixel: int, dtype) -> NDArray:
        wgpu = self.wgpu
        stride = (width * bytes_per_pixel + 255) // 256 * 256
        out = self.device.create_buffer(
            size=stride * height, usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.COPY_SRC
        )
        encoder = self.device.create_command_encoder()
        encoder.copy_texture_to_buffer(
            {"texture": texture, "mip_level": 0, "origin": (0, 0, 0)},
            {"buffer": out, "offset": 0, "bytes_per_row": stride, "rows_per_image": height},
            (width, height, 1),
        )
        self.device.queue.submit([encoder.finish()])
        raw = np.frombuffer(self.device.queue.read_buffer(out), dtype=np.uint8).reshape(height, stride)
        return np.frombuffer(raw[:, : width * bytes_per_pixel].tobytes(), dtype=dtype).reshape(height, -1)

    def render(self, scene: Scene) -> Frames:
        """Render the scene through both paths and read the results back as linear float32 images."""
        w, h = scene.width, scene.height
        if w % 32:
            raise ValueError("width must be a multiple of 32 so the readback rows are 256-byte aligned")
        t = self._ensure_targets(w, h)
        bind_material = self._material_group(scene.plan()) if scene.textures else self.bind_material_none
        self.device.queue.write_buffer(self.frame_buffer, 0, scene.frame_bytes(self.specular_mip_count))
        encoder = self.device.create_command_encoder()
        self._draw_mesh(
            encoder,
            self.pipe_forward,
            [t["forward"].create_view()],
            t["depth_forward"].create_view(),
            [self.bind_frame, self.bind_env, bind_material],
        )
        self._draw_mesh(
            encoder,
            self.pipe_fill,
            [g.create_view() for g in t["gbuffer"]],
            t["depth"].create_view(),
            [self.bind_frame, self.bind_env, bind_material],
        )
        wgpu = self.wgpu
        rpass = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": t["deferred"].create_view(),
                    "resolve_target": None,
                    "clear_value": (0.0, 0.0, 0.0, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ]
        )
        rpass.set_pipeline(self.pipe_light)
        rpass.set_bind_group(0, self.bind_frame)
        rpass.set_bind_group(1, self.bind_env)
        rpass.set_bind_group(2, t["bind_gbuffer"])
        rpass.draw(3)
        rpass.end()
        self.device.queue.submit([encoder.finish()])
        fwd = self._read_texture(t["forward"], w, h, 8, np.float16).reshape(h, w, 4)[..., :3].astype(np.float32)
        dfr = self._read_texture(t["deferred"], w, h, 8, np.float16).reshape(h, w, 4)[..., :3].astype(np.float32)
        depth = self._read_texture(t["depth"], w, h, 4, np.float32).reshape(h, w)
        return Frames(fwd, dfr, depth < 1.0, depth)


def request_device(power_preference: str = "high-performance"):
    """
    An adapter and device with the optional features the adapter has: the G-buffer's rg11b10 target and, for the
    cooked block-compressed sets (T3b), ``texture-compression-bc``.
    """
    import wgpu

    adapter = wgpu.gpu.request_adapter_sync(power_preference=power_preference)
    wanted = ("rg11b10ufloat-renderable", BC_FEATURE)
    features = [f for f in wanted if f in adapter.features]
    missing = [f for f in wanted if f not in adapter.features]
    info = adapter.info
    _LOGGER.info(
        f"adapter {info.get('device')} ({info.get('backend_type')}), features requested: {features or 'none'}"
        + (f"; not offered: {missing}" if missing else "")
    )
    return adapter, adapter.request_device_sync(required_features=features)


def obj_corners(path: Path) -> tuple[NDArray[np.int32], NDArray[np.int32], NDArray[np.int32]]:
    """
    The corners of an OBJ in file order, as ``load_obj`` keys them: ``(face, vertex, index)`` arrays, one entry per
    face corner, where ``face`` is the OBJ face index, ``vertex`` the 0-based ``v`` index and ``index`` the row of
    ``load_obj(path).vertices`` that corner became. What a per-corner fixture from another tool (Maya's tangents,
    ``hogshade.jobs.maya_mikktspace_dump``) lines up against.
    """
    corners: dict[tuple[int, int, int, int], int] = {}
    faces: list[int] = []
    verts: list[int] = []
    rows: list[int] = []
    records = read_obj(path)
    for face_index, face_keys in enumerate(records.faces):  # the same records and keying as load_obj
        hand = _face_hand(face_keys, records.texcoords)
        for vi, ti, ni in face_keys:
            faces.append(face_index)
            verts.append(vi - 1)
            rows.append(corners.setdefault((vi, ti, ni, hand), len(corners)))
    return np.asarray(faces, dtype=np.int32), np.asarray(verts, dtype=np.int32), np.asarray(rows, dtype=np.int32)


def load_shader_ball() -> Mesh:
    return normalise_mesh(load_obj(SHADER_BALL))


def quad_sphere(subdivisions: int | None = None) -> Mesh:
    """
    The quad sphere (``hogshade.testdata.quad_sphere``): six cube faces on a sphere, each face one clean 0 to 1 UV tile,
    the normals the sphere's own, MikkTSpace tangents from the UVs. Nothing is read from disk.
    """
    n = _quad_sphere.SUBDIVISIONS if subdivisions is None else subdivisions
    return with_tangents(*_quad_sphere.build(n))


#: The meshes the tools can render, by the name ``--mesh`` takes.
MESHES: Mapping[str, Callable[[], Mesh]] = MappingProxyType(
    {"shader-ball": load_shader_ball, "quad-sphere": quad_sphere}
)


def load_mesh(name: str) -> Mesh:
    """A mesh by name (``MESHES``): ``ValueError`` naming the choices for any other."""
    if name not in MESHES:
        raise ValueError(f"no mesh named {name!r}; one of {sorted(MESHES)}")
    _LOGGER.info(f"mesh {name}")
    return MESHES[name]()


if __name__ == "__main__":
    m = normalise_mesh(load_obj(SHADER_BALL))
    print(
        "shader ball:", m.vertices.shape, m.indices.shape, "extent", m.vertices[:, :3].min(0), m.vertices[:, :3].max(0)
    )
    print("frame bytes:", len(Scene(width=64, height=64).frame_bytes(9)))
