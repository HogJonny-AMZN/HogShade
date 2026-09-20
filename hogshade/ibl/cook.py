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
from hogshade.ibl.prefilter import ROUGHNESS_TO_MIP, brdf_lut, prefilter_specular

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


def condition(src: Path, dst: Path) -> dict:
    """Box-downsample an equirect HDR master to the repo's 4096x2048 half-float source. No tonemapping."""
    rgb = read_exr_rgb(src)
    h, w, _ = rgb.shape
    if w != 2 * h:
        raise ValueError(f"{src.name} is {w}x{h}, not 2:1 equirectangular")
    if w % SOURCE_WIDTH or (w // SOURCE_WIDTH) != (h // SOURCE_HEIGHT):
        raise ValueError(f"{src.name} is {w}x{h}; need an integer multiple of {SOURCE_WIDTH}x{SOURCE_HEIGHT}")
    factor = w // SOURCE_WIDTH
    out = rgb
    while factor > 1:
        out = box_downsample(out, 2)
        factor //= 2
    written = out.astype(np.float16)
    dst.parent.mkdir(parents=True, exist_ok=True)
    write_exr_rgb(dst, written, half=True)
    record = {
        "source": str(src),
        "source_sha256": sha256_file(src),
        "source_size": [w, h],
        "output": str(dst),
        "output_size": [SOURCE_WIDTH, SOURCE_HEIGHT],
        "factor": w // SOURCE_WIDTH,
        "mean_radiance_in": [float(x) for x in rgb.mean(axis=(0, 1), dtype=np.float64)],
        "mean_radiance_box_float32": [float(x) for x in out.mean(axis=(0, 1), dtype=np.float64)],
        "mean_radiance_out_float16": [float(x) for x in written.astype(np.float64).mean(axis=(0, 1))],
        "output_dtype": "float16",
        "tool_version": __version__,
    }
    _LOGGER.info(f"Conditioned {src.name} {w}x{h} -> {dst.name} {SOURCE_WIDTH}x{SOURCE_HEIGHT}")
    return record


def _git_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def cook_environment(env_dir: Path, base: int = 256, samples: int = 1024, irradiance_size: int = 32) -> dict:
    """Cook ``env_dir/source_4k.exr`` into ``env_dir/cooked/``. Returns the deterministic manifest."""
    src = env_dir / SOURCE_NAME
    if not src.exists():
        raise FileNotFoundError(f"{src} is missing; run condition first")
    started = time.time()
    out_dir = env_dir / "cooked"
    out_dir.mkdir(parents=True, exist_ok=True)

    img = read_exr_rgb(src)
    pyramid = equirect_pyramid(img)
    _LOGGER.info(f"{env_dir.name}: source {img.shape[1]}x{img.shape[0]}, pyramid of {len(pyramid)} levels")

    spec_mips = prefilter_specular(pyramid, base=base, samples=samples)
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
    manifest = {
        "tool": "hogshade.ibl.cook",
        "tool_version": __version__,
        "hogshade_version": HOGSHADE_VERSION,
        "source": SOURCE_NAME,
        "source_sha256": sha256_file(src),
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
        "outputs": {name: sha256_file(out_dir / name) for name in outputs},
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
