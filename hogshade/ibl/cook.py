"""
HogShade: the cook itself. Source EXR in an environment folder in; cooked/ out, with manifest and provenance.
Package: hogshade/ibl/cook
"""

from __future__ import annotations

import hashlib
import json
import logging as _logging
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from hogshade import __version__ as HOGSHADE_VERSION
from hogshade.ibl import dds
from hogshade.ibl.cubemap import FACE_CONVENTION, box_downsample, equirect_pyramid
from hogshade.ibl.imageio import preview_srgb8, read_exr_rgb, write_exr_rgb, write_png_rgb8
from hogshade.ibl.irradiance import irradiance_cube, sh9_irradiance, sh9_project
from hogshade.ibl.prefilter import ROUGHNESS_TO_MIP, brdf_lut, prefilter_specular, resolve_backend

_MODULE_NAME = "hogshade.ibl.cook"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SOURCE_NAME = "source_4k.exr"
SOURCE_WIDTH, SOURCE_HEIGHT = 4096, 2048
IRRADIANCE_SOURCE_WIDTH = 128


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def condition(src: Path, dst: Path, width: int = SOURCE_WIDTH) -> dict:
    """Box-downsample an equirect HDR master to a ``width`` x ``width/2`` half-float source. No tonemapping.

    The repo default is 4096; a hero cook may keep 8192 (a cube face of N texels wants a source of
    width 4N for matching density).
    """
    if width < 2 or width % 2:
        raise ValueError(f"width must be even and positive, got {width}")
    height = width // 2
    rgb = read_exr_rgb(src)
    h, w, _ = rgb.shape
    if w != 2 * h:
        raise ValueError(f"{src.name} is {w}x{h}, not 2:1 equirectangular")
    if w % width or (w // width) != (h // height):
        raise ValueError(f"{src.name} is {w}x{h}; need an integer multiple of {width}x{height}")
    factor = w // width
    out = rgb if factor == 1 else box_downsample(rgb, factor)  # one exact box average by the validated factor
    written = out.astype(np.float16)
    dst.parent.mkdir(parents=True, exist_ok=True)
    write_exr_rgb(dst, written, half=True)
    record = {
        "source": str(src),
        "source_sha256": sha256_file(src),
        "source_size": [w, h],
        "output": str(dst),
        "output_size": [width, height],
        "factor": factor,
        "mean_radiance_in": [float(x) for x in rgb.mean(axis=(0, 1), dtype=np.float64)],
        "mean_radiance_box_float32": [float(x) for x in out.mean(axis=(0, 1), dtype=np.float64)],
        "mean_radiance_out_float16": [float(x) for x in written.astype(np.float64).mean(axis=(0, 1))],
        "output_dtype": "float16",
        "tool_version": __version__,
    }
    _LOGGER.info(f"Conditioned {src.name} {w}x{h} -> {dst.name} {width}x{height}")
    return record


def _git_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def cook_environment(
    env_dir: Path,
    base: int = 256,
    samples: int = 1024,
    irradiance_size: int = 32,
    backend: str = "auto",
    source: str = SOURCE_NAME,
) -> dict:
    """Cook ``env_dir/<source>`` into ``env_dir/cooked/``. Returns the deterministic manifest.

    ``backend`` selects the prefilter implementation (``auto``, ``numpy``, ``numba``); the manifest
    records which one ran. ``source`` lets a hero cook read an 8K conditioned file.
    """
    src = env_dir / source
    if not src.exists():
        raise FileNotFoundError(f"{src} is missing; run condition first")
    resolved = resolve_backend(backend)
    started = time.time()
    out_dir = env_dir / "cooked"
    out_dir.mkdir(parents=True, exist_ok=True)

    img = read_exr_rgb(src)
    pyramid = equirect_pyramid(img)
    _LOGGER.info(f"{env_dir.name}: source {img.shape[1]}x{img.shape[0]}, pyramid of {len(pyramid)} levels")

    timings: dict[int, float] = {}
    spec_mips = prefilter_specular(pyramid, base=base, samples=samples, backend=resolved, timings=timings)
    dds.write_cube_rgba16f(out_dir / "specular.dds", spec_mips)

    small = next(lv for lv in pyramid if lv.shape[1] <= IRRADIANCE_SOURCE_WIDTH)
    irr = irradiance_cube(small, irradiance_size)
    dds.write_cube_rgba16f(out_dir / "irradiance.dds", [irr])
    coeffs = sh9_project(small)
    (out_dir / "irradiance_sh9.json").write_text(
        json.dumps(
            {
                "note": "Radiance SH L2 coefficients L_lm, RGB, in the order Y00, Y1-1, Y10, Y11, Y2-2, Y2-1, Y20, Y21, Y22. "
                "Irradiance/pi at normal n = sum_lm A_l L_lm Y_lm(n) / pi with A = (pi, 2pi/3, pi/4).",
                "coefficients": [[float(x) for x in row] for row in coeffs],
                "irradiance_source_width": int(small.shape[1]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    write_png_rgb8(env_dir / "preview.png", preview_srgb8(pyramid[2] if len(pyramid) > 2 else img))

    outputs = ["specular.dds", "irradiance.dds", "irradiance_sh9.json"]
    output_hashes = {name: sha256_file(out_dir / name) for name in outputs}
    output_hashes["../preview.png"] = sha256_file(env_dir / "preview.png")  # display only, but generated, so hashed
    manifest = {
        "tool": "hogshade.ibl.cook",
        "tool_version": __version__,
        "hogshade_version": HOGSHADE_VERSION,
        "source": source,
        "source_sha256": sha256_file(src),
        "backend": resolved,
        "source_size": [int(img.shape[1]), int(img.shape[0])],
        "face_convention": FACE_CONVENTION,
        "roughness_to_mip": ROUGHNESS_TO_MIP,
        "specular": {
            "base": base,
            "mips": len(spec_mips),
            "samples_per_texel": samples,
            "format": "RGBA16F cube, DX10 DDS",
        },
        "irradiance": {
            "size": irradiance_size,
            "source_width": int(small.shape[1]),
            "stores": "E/pi (cosine-convolved radiance over pi)",
            "format": "RGBA16F cube, DX10 DDS",
        },
        "sh9": {"stores": "radiance coefficients L_lm; see irradiance_sh9.json note"},
        "outputs": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    provenance = {
        "cooked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_seconds": round(time.time() - started, 1),
        "machine": platform.node(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "git_hash": _git_hash(),
        "prefilter_seconds_per_mip": {str(k): round(v, 3) for k, v in sorted(timings.items())},
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _LOGGER.info(f"{env_dir.name}: cooked in {provenance['wall_seconds']} s")
    return manifest


def cook_lut(dst: Path, size: int = 256, samples: int = 1024) -> str:
    """Write the split-sum BRDF LUT as a 2D RGBA16F DDS: R = scale, G = bias, B = 0, A = 1.

    Row 0 is the lowest roughness, column 0 the lowest NdotV, matching ``brdf_lut``. Returns the sha256.
    """
    lut = brdf_lut(size, samples)
    rgb = np.concatenate([lut, np.zeros(lut.shape[:2] + (1,), dtype=np.float32)], axis=-1)
    dds.write_2d_rgba16f(dst, rgb)
    return sha256_file(dst)


def furnace(base: int = 32, samples: int = 256, tolerance: float = 0.01) -> dict:
    """Cook a uniform white environment in memory and check every output is white within tolerance."""
    white = np.ones((64, 128, 3), dtype=np.float32)
    pyramid = equirect_pyramid(white)
    spec = prefilter_specular(pyramid, base=base, samples=samples)
    small = next(lv for lv in pyramid if lv.shape[1] <= IRRADIANCE_SOURCE_WIDTH)
    irr = irradiance_cube(small, 8)
    coeffs = sh9_project(white)
    sh_val = sh9_irradiance(coeffs, np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]]))
    report = {
        "specular_mip_max_error": [float(np.abs(m - 1.0).max()) for m in spec],
        "irradiance_max_error": float(np.abs(irr - 1.0).max()),
        "sh9_max_error": float(np.abs(sh_val - 1.0).max()),
        "tolerance": tolerance,
    }
    report["passed"] = bool(
        max(report["specular_mip_max_error"]) <= tolerance
        and report["irradiance_max_error"] <= tolerance
        and report["sh9_max_error"] <= tolerance
    )
    return report


if __name__ == "__main__":
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(furnace(), indent=2))
