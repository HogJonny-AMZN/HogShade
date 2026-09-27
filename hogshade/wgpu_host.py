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
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from hogshade.ibl.dds import read_2d_rgba16f, read_cube_rgba16f

_MODULE_NAME = "hogshade.wgpu_host"
__version__ = "0.1.0"
__updated__ = "2026-09-26"
_LOGGER = _logging.getLogger(_MODULE_NAME)

ROOT = Path(__file__).resolve().parents[1]
HOSTS_WGPU = ROOT / "hosts" / "wgpu"
CORE_WGSL = HOSTS_WGPU / "generated" / "hogshade_core.wgsl"
SHADER_BALL = ROOT / "content" / "shaderball" / "shaderBall.obj"
IBL_ROOT = ROOT / "content" / "ibl"
PASSES = ("lit_mesh", "gbuffer_fill", "deferred_light")

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
MODELS = {"lambert": 0, "legacy-v1": 1, "legacy-v2": 2}
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
    """Core, then common.wgsl, then the pass file: what a wgpu pipeline compiles for pass ``name``."""
    if name not in PASSES:
        raise ValueError(f"unknown pass {name!r}; one of {PASSES}")
    parts = [CORE_WGSL, HOSTS_WGPU / "common.wgsl", HOSTS_WGPU / f"{name}.wgsl"]
    return "\n".join(p.read_text(encoding="utf-8") for p in parts)


# ----------------------------------------------------------------------------- mesh


@dataclass
class Mesh:
    vertices: NDArray  # (n, 6) float32: position, normal
    indices: NDArray  # (m,) uint32, triangles


def load_obj(path: Path) -> Mesh:
    """A minimal OBJ reader: v, vn and f (v/vt/vn) records; quads and fans are triangulated."""
    positions: list[list[float]] = []
    normals: list[list[float]] = []
    corners: dict[tuple[int, int], int] = {}
    vertices: list[tuple[float, ...]] = []
    tris: list[int] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                positions.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vn "):
                normals.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("f "):
                face: list[int] = []
                for token in line.split()[1:]:
                    parts = token.split("/")
                    vi = int(parts[0])
                    ni = int(parts[2]) if len(parts) > 2 and parts[2] else 0
                    key = (vi, ni)
                    idx = corners.get(key)
                    if idx is None:
                        idx = len(vertices)
                        corners[key] = idx
                        p = positions[vi - 1]
                        n = normals[ni - 1] if ni else [0.0, 1.0, 0.0]
                        vertices.append((*p, *n))
                    face.append(idx)
                for k in range(1, len(face) - 1):
                    tris.extend((face[0], face[k], face[k + 1]))
    verts = np.asarray(vertices, dtype=np.float32)
    if len(verts) == 0:
        raise ValueError(f"no faces in {path}")
    return Mesh(verts, np.asarray(tris, dtype=np.uint32))


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
    return Mesh(out, mesh.indices)


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


def orbit_eye(yaw_deg: float, pitch_deg: float, distance: float) -> NDArray:
    cy, sy = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    cp, sp = math.cos(math.radians(pitch_deg)), math.sin(math.radians(pitch_deg))
    return np.array([distance * cp * sy, distance * sp, distance * cp * cy])


# ----------------------------------------------------------------------------- scene


@dataclass
class Scene:
    """Everything the frame uniform carries, in plain numbers. Colours are linear."""

    width: int = 1024
    height: int = 1024
    yaw_deg: float = 32.0
    pitch_deg: float = 18.0
    distance: float = 4.0
    fov_y_deg: float = 32.0
    base_color: tuple[float, float, float] = (0.5, 0.5, 0.5)
    roughness: float = 0.2
    metalness: float = 0.0
    specular: float = 1.0
    specular_tint: float = 0.0
    ior: float = 1.5
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
    model: str = "legacy-v2"
    rough_is_gloss: bool = False
    # legacy v1 Disney lobes: subsurface, specular_tint, anisotropic, sheen; sheen_tint, clearcoat, clearcoat_gloss
    subsurface: float = 0.0
    anisotropic: float = 0.0
    sheen: float = 0.0
    sheen_tint: float = 0.0
    clearcoat: float = 0.0
    clearcoat_gloss: float = 0.0
    sh9: NDArray = field(default_factory=lambda: np.zeros((9, 3)))

    def view_proj(self) -> tuple[NDArray, NDArray]:
        eye = orbit_eye(self.yaw_deg, self.pitch_deg, self.distance)
        view = look_at(eye, np.array([0.0, 0.05, 0.0]), np.array([0.0, 1.0, 0.0]))
        proj = perspective(self.fov_y_deg, self.width / self.height, 0.1, 50.0)
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
        frame["base_color"] = (*self.base_color, self.roughness)
        frame["material"] = (self.metalness, self.specular, self.specular_tint, self.ior)
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
        frame["model"] = (float(MODELS[self.model]), 1.0 if self.rough_is_gloss else 0.0, 0.0, 0.0)
        frame["params_a"] = (self.subsurface, self.specular_tint, self.anisotropic, self.sheen)
        frame["params_b"] = (self.sheen_tint, self.clearcoat, self.clearcoat_gloss, 0.0)
        sh = np.zeros((9, 4), dtype=np.float32)
        sh[:, :3] = np.asarray(self.sh9, dtype=np.float32)[:9]
        frame["sh9"] = sh
        data = frame.tobytes()
        assert len(data) == FRAME_BYTES, len(data)
        return data


@dataclass
class Frames:
    """Linear float images (H, W, 3) from one render: forward, deferred, and the deferred depth mask."""

    forward: NDArray
    deferred: NDArray
    covered: NDArray  # (H, W) bool: pixels the ball covers (depth written)

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
                    "array_stride": 24,
                    "step_mode": wgpu.VertexStepMode.vertex,
                    "attributes": [
                        {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                        {"format": wgpu.VertexFormat.float32x3, "offset": 12, "shader_location": 1},
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
            layout=d.create_pipeline_layout(bind_group_layouts=[self.layout_frame, self.layout_env]),
            vertex=self._mesh_vertex_state(modules["lit_mesh"]),
            primitive=primitive,
            depth_stencil=depth,
            fragment={"module": modules["lit_mesh"], "entry_point": "fs_main", "targets": [{"format": COLOR_FORMAT}]},
        )
        gb_formats = list(GBUFFER_FORMATS[:3]) + [self.gb3_format]
        self.pipe_fill = d.create_render_pipeline(
            layout=d.create_pipeline_layout(bind_group_layouts=[self.layout_frame]),
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
        self.device.queue.write_buffer(self.frame_buffer, 0, scene.frame_bytes(self.specular_mip_count))
        encoder = self.device.create_command_encoder()
        self._draw_mesh(
            encoder,
            self.pipe_forward,
            [t["forward"].create_view()],
            t["depth_forward"].create_view(),
            [self.bind_frame, self.bind_env],
        )
        self._draw_mesh(
            encoder,
            self.pipe_fill,
            [g.create_view() for g in t["gbuffer"]],
            t["depth"].create_view(),
            [self.bind_frame],
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
        return Frames(fwd, dfr, depth < 1.0)


def request_device(power_preference: str = "high-performance"):
    """An adapter and device with the optional G-buffer feature when the adapter has it."""
    import wgpu

    adapter = wgpu.gpu.request_adapter_sync(power_preference=power_preference)
    features = ["rg11b10ufloat-renderable"] if "rg11b10ufloat-renderable" in adapter.features else []
    return adapter, adapter.request_device_sync(required_features=features)


def load_shader_ball() -> Mesh:
    return normalise_mesh(load_obj(SHADER_BALL))


if __name__ == "__main__":
    m = normalise_mesh(load_obj(SHADER_BALL))
    print(
        "shader ball:", m.vertices.shape, m.indices.shape, "extent", m.vertices[:, :3].min(0), m.vertices[:, :3].max(0)
    )
    print("frame bytes:", len(Scene(width=64, height=64).frame_bytes(9)))
