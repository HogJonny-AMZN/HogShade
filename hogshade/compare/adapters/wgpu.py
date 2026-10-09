"""
HogShade: the wgpu adapter: a capture request becomes a wgpu host scene and a capture set at level L2p.
Package: hogshade/compare/adapters/wgpu

What the host can and cannot do today decides what is refused, by name, before anything renders:

- **Camera:** an explicit ``(eye, target, up)`` and a vertical field of view map directly (``Scene.camera``);
  ``near`` and ``far`` must equal the host's ``NEAR_PLANE`` and ``FAR_PLANE``, since the depth linearisation
  depends on them.
- **Rig:** the cooked environment by name; ``exposure_ev`` becomes ``env_exposure = 2 ** ev``; a request with no
  light is lit by the environment alone (light intensity 0), a request with one gets its direction, intensity and
  colour. ``rotation_deg`` other than 0 is refused: the host has no environment rotation.
- **View:** only ``preview``, the host's placeholder (Reinhard plus sRGB). ``agx`` and ``aces`` wait for the colour
  pipeline (increment C-1).
- **Material:** a document path (a standard document is converted to the legacy v2 model the host carries, as the
  host tests do) or a texture-set directory (the set's generated document), not both.

The set is **L2p**: ``Frames.forward`` is scene-linear float but untagged, and the display picture is the preview
placeholder, so a parity case will refuse it until C-1. The manifest records a hash of everything loaded: the mesh
geometry, the material document, the texture set and the three environment files, so replacing any of them in place
changes the record though the request text is unchanged.
"""

from __future__ import annotations

import hashlib
import logging as _logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from hogshade import wgpu_host
from hogshade.compare import captureset
from hogshade.compare.captureset import Manifest
from hogshade.compare.request import CaptureRequest
from hogshade.ibl import imageio

_MODULE_NAME = "hogshade.compare.adapters.wgpu"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

HOST = "wgpu"
LEVEL = "L2p"
MATERIALS_ROOT = Path("content") / "materials"
NOTES = (
    "scene.exr is the forward path's scene-linear float, untagged (not ACEScg): level L2p",
    "display.png is the host's Reinhard plus sRGB preview placeholder, not the framework's view transform",
)


class UnsupportedRequest(ValueError):
    """A request the wgpu host cannot honour; the message names what and says why."""


def check_supported(request: CaptureRequest) -> None:
    """Refuse, by name, what the host cannot do. Pure: nothing is loaded, so it runs without a GPU."""
    camera = request.camera
    if camera.near != wgpu_host.NEAR_PLANE or camera.far != wgpu_host.FAR_PLANE:
        raise UnsupportedRequest(
            f"camera.near/far: the wgpu host renders with near {wgpu_host.NEAR_PLANE} and far {wgpu_host.FAR_PLANE} "
            f"(its depth linearisation depends on them), the request asks for {camera.near} and {camera.far}"
        )
    if request.rig.rotation_deg != 0.0:
        raise UnsupportedRequest(
            f"rig.rotation_deg: the wgpu host has no environment rotation yet, "
            f"the request asks for {request.rig.rotation_deg}"
        )
    if request.view != "preview":
        raise UnsupportedRequest(
            f"view: the wgpu host supports only 'preview' (a placeholder) until the colour pipeline lands, "
            f"the request asks for {request.view!r}"
        )
    if request.material is not None and request.textures is not None:
        raise UnsupportedRequest(
            "material and textures: name a document or a texture set, not both; "
            "a set is bound through its generated document"
        )
    if request.mesh not in wgpu_host.MESHES:
        raise UnsupportedRequest(f"mesh: the wgpu host has no mesh {request.mesh!r}; it has {sorted(wgpu_host.MESHES)}")


def hash_tree(directory: Path) -> str:
    """SHA-256 over every file under ``directory`` (sorted by relative path): name and content hash for each."""
    digest = hashlib.sha256()
    for path in sorted(p for p in Path(directory).rglob("*") if p.is_file()):
        digest.update(f"{path.relative_to(directory).as_posix()}:{captureset.sha256_file(path)}\n".encode())
    return digest.hexdigest()


def mesh_hash(mesh: wgpu_host.Mesh) -> str:
    """SHA-256 of the geometry the host actually loaded (vertices, indices, and the tangent basis name)."""
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(mesh.vertices, dtype=np.float32).tobytes())
    digest.update(np.ascontiguousarray(mesh.indices, dtype=np.uint32).tobytes())
    digest.update(mesh.tangent_basis.encode())
    return digest.hexdigest()


def input_hashes(
    request: CaptureRequest,
    mesh: wgpu_host.Mesh,
    root: Path | None = None,
    ibl_root: Path | None = None,
) -> dict[str, str]:
    """
    A hash for everything the adapter loads for ``request``: the mesh geometry, the material document, the texture
    set, and the environment's three files. Pure and CPU-only, so a test can replace a file and watch its hash change.
    """
    root = Path(root) if root is not None else wgpu_host.ROOT
    ibl_root = Path(ibl_root) if ibl_root is not None else wgpu_host.IBL_ROOT
    hashes = {"request": request.content_hash(), "mesh": mesh_hash(mesh)}
    if request.material is not None:
        hashes["material"] = captureset.sha256_file(root / request.material)
    if request.textures is not None:
        hashes["textures"] = hash_tree(root / request.textures)
    env = request.rig.environment
    for label, path in (
        (f"environment:{env}/cooked/specular.dds", ibl_root / env / "cooked" / "specular.dds"),
        (f"environment:{env}/cooked/irradiance.dds", ibl_root / env / "cooked" / "irradiance.dds"),
        ("environment:brdf_lut.dds", ibl_root / "brdf_lut.dds"),
    ):
        hashes[label] = captureset.sha256_file(path)
    _LOGGER.debug("input hashes for " + request.id + ": " + ", ".join(f"{k} {v[:12]}" for k, v in hashes.items()))
    return hashes


def bind_request(request: CaptureRequest, root: Path | None = None) -> tuple[Any, dict[str, Any] | None]:
    """
    The material the request names, bound for wgpu, with its runtime textures: ``(binding, textures)``, or
    ``(None, None)`` for a request with neither a document nor a set (the host's default material).
    """
    from hogshade.material import bind, convert, load, resolve, runtime_textures
    from hogshade.material.generators import host_map
    from hogshade.material.sets import document_for_set

    root = Path(root) if root is not None else wgpu_host.ROOT
    if request.material is None and request.textures is None:
        return None, None
    if request.textures is not None:
        doc_dir = root / request.textures
        doc = document_for_set(doc_dir)
        resolved = resolve(doc)
    else:
        path = root / request.material
        doc_dir = path.parent
        resolved = resolve(load(path, root / MATERIALS_ROOT), root / MATERIALS_ROOT)
    carried = host_map("wgpu").get("types") or []
    if carried and resolved.material_type not in carried:
        converted, _losses = convert(resolved, "hogshade-legacy-v2")
        resolved = resolve(converted)
    binding = bind(resolved, "wgpu")
    return binding, runtime_textures(binding.textures, doc_dir)


def scene_for(request: CaptureRequest, binding: Any = None, textures: dict[str, Any] | None = None) -> wgpu_host.Scene:
    """The host scene a (supported) request describes. Pure: nothing is rendered."""
    check_supported(request)
    cam, rig = request.camera, request.rig
    kwargs: dict[str, Any] = {
        "width": request.size[0],
        "height": request.size[1],
        "fov_y_deg": cam.fov_y_deg,
        "camera": (cam.eye, cam.target, cam.up),
        "environment": rig.environment,
        "env_exposure": 2.0**rig.exposure_ev,
        "debug_mode": request.debug_mode,
    }
    if rig.light is None:
        kwargs["light_intensity"] = 0.0
    else:
        kwargs.update(light_dir=rig.light.direction, light_intensity=rig.light.intensity, light_color=rig.light.color)
    if binding is not None:
        kwargs["material"] = binding
    if textures:
        kwargs["textures"] = textures
    return wgpu_host.Scene(**kwargs)


class WgpuAdapter:
    """Renders capture requests on one wgpu device, keeping a renderer per (mesh, environment)."""

    def __init__(self, device: Any = None, device_info: dict[str, Any] | None = None) -> None:
        if device is None:
            adapter, device = wgpu_host.request_device()
            device_info = dict(adapter.info)
        self.device = device
        self.device_info = device_info or {}
        self._renderers: dict[tuple[str, str], wgpu_host.Renderer] = {}

    def versions(self) -> dict[str, str]:
        import wgpu

        out = {"wgpu-py": str(getattr(wgpu, "__version__", "unknown"))}
        for key in ("device", "backend_type"):
            if self.device_info.get(key):
                out[key] = str(self.device_info[key])
        return out

    def renderer(self, mesh_id: str, environment: str) -> wgpu_host.Renderer:
        key = (mesh_id, environment)
        if key not in self._renderers:
            self._renderers[key] = wgpu_host.Renderer(self.device, wgpu_host.load_mesh(mesh_id), environment)
        return self._renderers[key]

    def capture(self, request: CaptureRequest, out_dir: Path, root: Path | None = None) -> captureset.CaptureSet:
        """Render ``request`` and write its capture set into ``out_dir`` at level L2p; the set read back."""
        check_supported(request)
        started = time.perf_counter()
        _LOGGER.info(
            f"capturing {request.id} on wgpu: mesh {request.mesh}, environment {request.rig.environment} "
            f"({request.rig.exposure_ev:+g} EV), {request.size[0]}x{request.size[1]}, debug view {request.debug_mode}, "
            f"material {request.material or 'none'}, textures {request.textures or 'none'}"
        )
        binding, textures = bind_request(request, root)
        renderer = self.renderer(request.mesh, request.rig.environment)
        scene = scene_for(request, binding, textures)
        frames = renderer.render(scene)
        scene_linear = np.asarray(frames.forward, dtype=np.float32)
        covered = float(np.asarray(frames.covered).mean())
        _LOGGER.info(f"rendered {request.id}: {covered:.1%} of the picture covered, level {LEVEL}")
        display = imageio.preview_srgb8(scene_linear)
        manifest = Manifest(
            host=HOST,
            level=LEVEL,
            request_hash=request.content_hash(),
            versions=self.versions(),
            inputs=input_hashes(request, renderer.mesh, root),
            colour_space="unspecified",
            wall_seconds=round(time.perf_counter() - started, 3),
            notes=NOTES,
        )
        captureset.write(
            Path(out_dir), request, manifest, scene_linear, display, np.asarray(frames.covered, dtype=bool)
        )
        return captureset.read(Path(out_dir))
