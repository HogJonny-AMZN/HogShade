"""
HogShade: the IBL cook. Turns a source HDR environment into the prefiltered data every host loads.
Package: tools/cook_ibl.py

Spec: Docs/specs/e1-ibl-cook.md. Subcommands land in the order the plan lists them; today only
``condition`` exists.

Run without a project:  uv run --no-project --with OpenEXR --with numpy tools/cook_ibl.py condition IN OUT
"""

from __future__ import annotations

import argparse
import hashlib
import logging as _logging
import sys
from pathlib import Path

import numpy as np

_MODULE_NAME = "hogshade.tools.cook_ibl"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SOURCE_WIDTH = 4096
SOURCE_HEIGHT = 2048


def _read_exr_rgb(path: Path) -> np.ndarray:
    """Read an EXR's RGB channels as a float32 (H, W, 3) array in scene-linear units."""
    import OpenEXR  # imported here so ``--help`` works without it

    with OpenEXR.File(str(path)) as f:
        channels = f.channels()
        if "RGB" in channels:
            rgb = channels["RGB"].pixels
        elif "RGBA" in channels:
            rgb = channels["RGBA"].pixels[..., :3]
        else:
            try:
                rgb = np.stack([channels[c].pixels for c in ("R", "G", "B")], axis=-1)
            except KeyError as e:
                raise ValueError(f"EXR {path} has no RGB channels: {list(channels)}") from e
    return np.asarray(rgb, dtype=np.float32)


def _write_exr_rgb(path: Path, rgb: np.ndarray, half: bool = True) -> None:
    """Write an (H, W, 3) array as an RGB EXR, half-float by default, PIZ compressed.

    Callers that report statistics should quantise first and pass the array the file will hold.
    """
    import OpenEXR

    data = rgb.astype(np.float16 if half else np.float32)
    header = {"compression": OpenEXR.PIZ_COMPRESSION, "type": OpenEXR.scanlineimage}
    with OpenEXR.File(header, {"RGB": data}) as f:
        f.write(str(path))


def _box_downsample(rgb: np.ndarray, factor: int) -> np.ndarray:
    """Average ``factor`` x ``factor`` blocks. Exact for integer ratios; no filtering beyond the box."""
    h, w, c = rgb.shape
    if h % factor or w % factor:
        raise ValueError(f"{h}x{w} is not divisible by {factor}")
    return rgb.reshape(h // factor, factor, w // factor, factor, c).mean(axis=(1, 3), dtype=np.float64).astype(np.float32)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def condition(src: Path, dst: Path) -> dict:
    """Downsample an equirectangular HDR master to the repo's 4096x2048 half-float source.

    No tonemapping, no exposure change, no filtering beyond the box average, so the source's
    scene-linear units survive. Returns a small record for the caller to log or write.
    """
    rgb = _read_exr_rgb(src)
    h, w, _ = rgb.shape
    if w != 2 * h:
        raise ValueError(f"{src.name} is {w}x{h}, not 2:1 equirectangular")
    if w % SOURCE_WIDTH or (w // SOURCE_WIDTH) != (h // SOURCE_HEIGHT):
        raise ValueError(f"{src.name} is {w}x{h}; need an integer multiple of {SOURCE_WIDTH}x{SOURCE_HEIGHT}")
    factor = w // SOURCE_WIDTH
    out = rgb if factor == 1 else _box_downsample(rgb, factor)
    written = out.astype(np.float16)  # what the file holds; the record reports this, not the float32
    dst.parent.mkdir(parents=True, exist_ok=True)
    _write_exr_rgb(dst, written, half=True)
    record = {
        "source": str(src),
        "source_sha256": _sha256(src),
        "source_size": [w, h],
        "output": str(dst),
        "output_size": [SOURCE_WIDTH, SOURCE_HEIGHT],
        "factor": factor,
        "mean_radiance_in": [float(x) for x in rgb.mean(axis=(0, 1), dtype=np.float64)],
        "mean_radiance_box_float32": [float(x) for x in out.mean(axis=(0, 1), dtype=np.float64)],
        "mean_radiance_out_float16": [float(x) for x in written.astype(np.float64).mean(axis=(0, 1))],
        "output_dtype": "float16",
        "tool_version": __version__,
    }
    _LOGGER.info(f"Conditioned {src.name} {w}x{h} -> {dst.name} {SOURCE_WIDTH}x{SOURCE_HEIGHT} (factor {factor})")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cook_ibl", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("condition", help="8K master -> 4K half-float source_4k.exr")
    p.add_argument("src", type=Path)
    p.add_argument("dst", type=Path)
    args = parser.parse_args(argv)

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    if args.cmd == "condition":
        record = condition(args.src, args.dst)
        for k, v in record.items():
            print(f"{k}: {v}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
