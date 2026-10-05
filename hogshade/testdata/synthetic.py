"""
HogShade: the synthetic texture set, T4 tier 1: a map for every suffix the content standard names, generated from
numbers so that every texel has a value a test can assert.
Package: hogshade/testdata/synthetic

The set is an instrument, not a tile and not a material: ramps, patches, bands and checkers whose values are plain
fractions, so a test that reads a texel back (from the cooked DDS, from a debug view of either host) knows what it
must have been. Every map is ``size x size`` (512 by default). Texture space is the repository's: U increases to the
right, V (the OBJ convention) increases toward the top of the picture. A legend strip of ``size // 16`` rows along
the bottom names the map in the bitmap font, so a wrong slot is visible in a render before any number is read; the
content above it is a function of ``(u, v)`` only, with ``v`` rescaled so 0 is the top of the strip and 1 the top of
the picture. Nothing is random: the same ``size`` writes the same bytes.

``generate(set_dir, size)`` writes the PNGs, their sidecars (provenance, the normal convention, the ``pack`` of the
cutout into the colour map's alpha) and ``LICENSE.md``. ``known_points`` lists, for each map, named semantic points
(a band's centre, a patch, the ramp at a quarter) with the pixel and the value the generator put there, computed from
the same functions that draw the maps so the test and the generator cannot drift (no file is written for it: the
content standard allows only textures, sidecars and the licence in a set). ``render_map`` returns one map as an
array without touching the disk.
"""

from __future__ import annotations

import json
import logging as _logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hogshade.bitmap_font import draw_text, fit, glyph
from hogshade.texture_cook import png

_MODULE_NAME = "hogshade.testdata.synthetic"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SIZE = 512
STRIP_DIV = 16
BASE = "synthetic"
VARIANT_SUFFIX, VARIANT = "_BC", "blue"
TODAY = "2026-10-04"

#: The six colour patches of ``_BC`` (sRGB, 8-bit) at (u, content v): greys and primaries, in rows of three.
PATCHES: dict[str, tuple[tuple[float, float], tuple[int, int, int]]] = {
    "white": ((0.25, 0.65), (240, 240, 240)),
    "mid grey": ((0.50, 0.65), (118, 118, 118)),
    "dark grey": ((0.75, 0.65), (52, 52, 52)),
    "red": ((0.25, 0.35), (200, 40, 40)),
    "green": ((0.50, 0.35), (40, 160, 60)),
    "blue": ((0.75, 0.35), (50, 80, 200)),
}
SPECULAR_BANDS = ((255, 64, 64), (64, 255, 64), (64, 64, 255))
EMISSION = (255, 128, 0)
ROUGHNESS_BANDS = 8
CHECKER_BLOCK = 128  # at 512
TILT = 0.5  # sin 30 degrees: the normal quadrants lean this far toward their direction
BUMP_SLOPE = 0.8


class SyntheticError(ValueError):
    """The set cannot be generated: a size the layout does not support."""


@dataclass(frozen=True)
class Frame:
    """The pixel grid every map is a function of: columns, rows, the texture-space coordinates, the strip."""

    size: int
    strip: int
    k: float  # pixel constants are given at 512 and scaled by this
    col: NDArray[np.int_]
    row: NDArray[np.int_]
    u: NDArray[np.float64]
    v: NDArray[np.float64]  # content v: 0 at the top of the strip, 1 at the top of the picture
    in_strip: NDArray[np.bool_]

    def px(self, n: float) -> int:
        """A 512-pixel constant at this size, at least 1."""
        return max(1, round(n * self.k))

    def pixel_of(self, u: float, v: float) -> tuple[int, int]:
        """The ``(col, row)`` whose centre holds texture coordinates ``u`` and content ``v``."""
        v_img = self.strip / self.size + v * (1.0 - self.strip / self.size)
        return min(int(u * self.size), self.size - 1), min(int((1.0 - v_img) * self.size), self.size - 1)


def frame(size: int = SIZE) -> Frame:
    """The grid for a ``size x size`` map: a power of two from 128 (where the legend strip is 8 rows) to 2048."""
    if size < 128 or size > 2048 or size & (size - 1):
        raise SyntheticError(f"size {size} is not a power of two between 128 and 2048")
    strip = size // STRIP_DIV
    col = np.arange(size)[None, :].repeat(size, axis=0)
    row = np.arange(size)[:, None].repeat(size, axis=1)
    u = (col + 0.5) / size
    v_img = 1.0 - (row + 0.5) / size
    v = (v_img - strip / size) / (1.0 - strip / size)
    return Frame(size, strip, size / 512.0, col, row, u, v, row >= size - strip)


def _disc(f: Frame, cx: float, cy: float) -> NDArray[np.float64]:
    """Distance in pixels from the centre ``(cx, cy)`` (columns, rows)."""
    return np.hypot(f.col + 0.5 - cx, f.row + 0.5 - cy)


def _content_centre(f: Frame) -> tuple[float, float]:
    return f.size / 2.0, (f.size - f.strip) / 2.0


def _arrow(
    img: NDArray[np.uint8], f: Frame, tail: tuple[int, int], tip: tuple[int, int], colour: tuple[int, int, int]
) -> None:
    """A shaft with a triangular head, along a row (``+U``, left to right) or a column (``+V``, upward)."""
    w, head = f.px(3), f.px(14)
    (x0, y0), (x1, y1) = tail, tip
    if y0 == y1:  # along U
        img[y0 - w : y0 + w + 1, x0 : x1 - head] = colour
        for i in range(head):
            half = max(0, f.px(10) * (head - i) // head)
            img[y0 - half : y0 + half + 1, x1 - head + i] = colour
    else:  # along V, the tip above the tail
        img[y1 + head : y0, x0 - w : x0 + w + 1] = colour
        for i in range(head):
            half = max(0, f.px(10) * (head - i) // head)
            img[y1 + head - i, x0 - half : x0 + half + 1] = colour


def _arrows(f: Frame) -> dict[str, tuple[tuple[int, int], tuple[int, int], tuple[int, int, int]]]:
    """Where the orientation arrows sit: the U arrow along the bottom of the content, the V arrow up the left."""
    bottom = f.size - f.strip - f.px(30)
    left = f.px(30)
    return {
        "U": ((f.px(40), bottom), (f.px(190), bottom), (255, 255, 0)),
        "V": ((left, f.size - f.strip - f.px(60)), (left, f.px(70)), (0, 255, 255)),
    }


def _colour(f: Frame) -> NDArray[np.uint8]:
    """``_BC``: a UV grid with six colour patches and the two orientation arrows."""
    img = np.full((f.size, f.size, 3), 150, dtype=np.uint8)
    pitch = f.px(64)
    line = (f.col % pitch < f.px(1)) | (f.row % pitch < f.px(1))
    img[line] = 90
    half = f.px(40)
    for (pu, pv), rgb in PATCHES.values():
        cx, cy = f.pixel_of(pu, pv)
        img[cy - half : cy + half, cx - half : cx + half] = rgb
    for label, (tail, tip, rgb) in _arrows(f).items():
        _arrow(img, f, tail, tip, rgb)
        canvas = np.zeros((f.size, f.size, 3), dtype=np.float32)
        tx = tip[0] + f.px(8) if label == "U" else tip[0] + f.px(12)
        ty = tip[1] - f.px(5) if label == "U" else tip[1] + f.px(2)
        draw_text(canvas, label, tx, ty, max(1, f.px(3)))
        img[canvas[..., 0] > 0.5] = (255, 255, 255)
    return img


def _colour_blue(f: Frame) -> NDArray[np.uint8]:
    """``_BC_blue``: the same picture with the channels rotated (R takes G, G takes B, B takes R)."""
    return np.ascontiguousarray(_colour(f)[..., [1, 2, 0]])


def _encode_normal(n: NDArray[np.float64]) -> NDArray[np.uint8]:
    return np.rint(np.clip((n * 0.5 + 0.5) * 255.0, 0, 255)).astype(np.uint8)


def _normal(f: Frame) -> NDArray[np.uint8]:
    """``_N``: four quadrants (flat, toward +U, toward +V, toward -U) around a hemisphere bump; OpenGL +Y."""
    n = np.zeros((f.size, f.size, 3))
    n[..., 2] = 1.0
    right, top = f.u >= 0.5, f.v >= 0.5
    flat_z = (1.0 - TILT**2) ** 0.5
    for mask, (nx, ny) in (
        (right & top, (TILT, 0.0)),  # top right leans toward +U
        (~right & ~top, (0.0, TILT)),  # bottom left toward +V
        (right & ~top, (-TILT, 0.0)),  # bottom right toward -U
    ):
        n[mask] = (nx, ny, flat_z)
    cx, cy = _content_centre(f)
    radius = 0.1 * f.size
    dx = (f.col + 0.5 - cx) / radius
    dy = (cy - (f.row + 0.5)) / radius  # up (+V) is positive
    inside = (dx**2 + dy**2 < 1.0) & ~f.in_strip
    nx, ny = dx * BUMP_SLOPE, dy * BUMP_SLOPE
    nz = np.sqrt(np.clip(1.0 - nx**2 - ny**2, 0.0, 1.0))
    n[inside] = np.stack([nx, ny, nz], axis=-1)[inside]
    return _encode_normal(n)


def _roughness(f: Frame) -> NDArray[np.uint8]:
    """``_R``: eight vertical bands, 0 to 1 in steps of 1/7."""
    band = np.minimum((f.u * ROUGHNESS_BANDS).astype(int), ROUGHNESS_BANDS - 1)
    return np.rint(band / (ROUGHNESS_BANDS - 1) * 255).astype(np.uint8)


def _metalness(f: Frame) -> NDArray[np.uint8]:
    """``_M``: a checker of exact 0 and 1."""
    block = f.px(CHECKER_BLOCK)
    return np.where(((f.col // block) + (f.row // block)) % 2 == 0, 255, 0).astype(np.uint8)


def _radial(f: Frame) -> NDArray[np.float64]:
    """0 at the content centre, 1 at its corners."""
    cx, cy = _content_centre(f)
    return np.clip(_disc(f, cx, cy) / np.hypot(cx, cy), 0.0, 1.0)


def _ambient_occlusion(f: Frame) -> NDArray[np.uint8]:
    """``_AO``: 1.0 at the centre falling to 0.25 at the corners."""
    return np.rint((1.0 - 0.75 * _radial(f)) * 255).astype(np.uint8)


def _specular_occlusion(f: Frame) -> NDArray[np.uint8]:
    """``_SO``: the inverse of the AO, 0.25 at the centre rising to 1.0."""
    return np.rint((0.25 + 0.75 * _radial(f)) * 255).astype(np.uint8)


def _cavity(f: Frame) -> NDArray[np.uint8]:
    """``_C``: thin 0.5 lines on white, a grid."""
    pitch, width = f.px(64), f.px(4)
    line = (f.col % pitch < width) | (f.row % pitch < width)
    return np.where(line, 128, 255).astype(np.uint8)


def _height_values(f: Frame) -> NDArray[np.float64]:
    """A ramp along U, a step of 0.25 at the middle and a cone of height 0.2 and radius 0.15 of the width."""
    h = 0.5 * f.u + np.where(f.u >= 0.5, 0.25, 0.0)
    cx, cy = f.size * 0.75, (f.size - f.strip) / 2.0
    d = _disc(f, cx, cy) / (0.15 * f.size)
    return h + 0.2 * np.clip(1.0 - d, 0.0, 1.0)


def _height(f: Frame) -> NDArray[np.uint16]:
    """``_H``: 16-bit."""
    return np.rint(_height_values(f) * 65535).astype(np.uint16)


def _emission(f: Frame) -> NDArray[np.uint8]:
    """``_E``: the letter E, large, in orange on black."""
    img = np.zeros((f.size, f.size, 3), dtype=np.uint8)
    scale = f.px(36)
    gx = (f.size - 5 * scale) // 2
    gy = (f.size - f.strip - 7 * scale) // 2
    mask = np.repeat(np.repeat(glyph("E"), scale, axis=0), scale, axis=1)
    img[gy : gy + mask.shape[0], gx : gx + mask.shape[1]][mask] = EMISSION
    return img


def _opacity(f: Frame) -> NDArray[np.uint8]:
    """``_O``: a disc of 1 with a soft linear rim 32 pixels wide, 0 outside."""
    cx, cy = _content_centre(f)
    outer, rim = f.px(200), f.px(32)
    d = _disc(f, cx, cy)
    return np.rint(np.clip((outer - d) / rim, 0.0, 1.0) * 255).astype(np.uint8)


def _specular_colour(f: Frame) -> NDArray[np.uint8]:
    """``_SC``: three vertical bands of known colour."""
    band = np.minimum((f.u * 3).astype(int), 2)
    return np.array(SPECULAR_BANDS, dtype=np.uint8)[band]


def _ramp_v(f: Frame) -> NDArray[np.uint8]:
    return np.rint(np.clip(f.v, 0.0, 1.0) * 255).astype(np.uint8)


def _ramp_u(f: Frame) -> NDArray[np.uint8]:
    return np.rint(f.u * 255).astype(np.uint8)


def _ramp_v_down(f: Frame) -> NDArray[np.uint8]:
    return np.rint((1.0 - np.clip(f.v, 0.0, 1.0)) * 255).astype(np.uint8)


@dataclass(frozen=True)
class MapSpec:
    """One map: its suffix and variant, the standard parameter it binds, how it is drawn, what its strip holds."""

    suffix: str
    variant: str | None
    parameter: str
    draw: Callable[[Frame], NDArray]
    kind: str  # rgb8, gray8 or gray16: the dtype and rank ``draw`` must return, checked by ``render_map``
    strip_fill: int | tuple[int, int, int]
    strip_ink: int | tuple[int, int, int]
    sidecar: dict[str, Any]

    @property
    def stem(self) -> str:
        return f"T_{BASE}{self.suffix}" + (f"_{self.variant}" if self.variant else "")


_DARK = (20, 20, 20)
_WHITE = (255, 255, 255)
SPECS: tuple[MapSpec, ...] = (
    MapSpec("_BC", None, "base_color", _colour, "rgb8", _DARK, _WHITE, {"pack": {"a": "_O"}}),
    MapSpec("_BC", VARIANT, "base_color", _colour_blue, "rgb8", _DARK, _WHITE, {}),
    MapSpec("_N", None, "geometry_normal", _normal, "rgb8", (128, 128, 255), _WHITE, {"normal_convention": "opengl+y"}),
    MapSpec("_R", None, "specular_roughness", _roughness, "gray8", 0, 255, {}),
    MapSpec("_M", None, "base_metalness", _metalness, "gray8", 0, 255, {}),
    MapSpec("_AO", None, "ambient_occlusion", _ambient_occlusion, "gray8", 0, 255, {}),
    MapSpec("_SO", None, "specular_occlusion", _specular_occlusion, "gray8", 0, 255, {}),
    MapSpec("_C", None, "cavity", _cavity, "gray8", 0, 255, {}),
    MapSpec("_H", None, "height", _height, "gray16", 0, 40000, {}),
    MapSpec("_E", None, "emission_color", _emission, "rgb8", (0, 0, 0), _WHITE, {}),
    MapSpec("_O", None, "geometry_opacity", _opacity, "gray8", 0, 255, {}),
    MapSpec("_SC", None, "specular_color", _specular_colour, "rgb8", _DARK, _WHITE, {}),
    MapSpec("_SW", None, "specular_weight", _ramp_v, "gray8", 0, 255, {}),
    MapSpec("_AX", None, "specular_anisotropy", _ramp_u, "gray8", 0, 255, {}),
    MapSpec("_AR", None, "specular_rotation", _ramp_v_down, "gray8", 0, 255, {}),
)


def spec_for(suffix: str, variant: str | None = None) -> MapSpec:
    """The spec of ``suffix`` (and ``variant``), ``SyntheticError`` for a map the set does not have."""
    for s in SPECS:
        if s.suffix == suffix and s.variant == variant:
            return s
    raise SyntheticError(f"the synthetic set has no {suffix}{'_' + variant if variant else ''}")


_KINDS: dict[str, tuple[Any, int]] = {"rgb8": (np.uint8, 3), "gray8": (np.uint8, 2), "gray16": (np.uint16, 2)}


def legend_label(spec: MapSpec, size: int = SIZE) -> str:
    """The text of a map's legend strip: ``<suffix> <parameter>``, cut with a dot where it would not fit the width."""
    f = frame(size)
    full = f"{spec.suffix}{'_' + spec.variant if spec.variant else ''} {spec.parameter}"
    return fit(full, size - 2 * f.px(8), max(1, f.px(2)))


def render_map(suffix: str, variant: str | None = None, size: int = SIZE) -> NDArray:
    """One map as an array: ``(size, size, 3)`` uint8 for colour, ``(size, size)`` uint8 or uint16 for the rest."""
    f = frame(size)
    spec = spec_for(suffix, variant)
    img = spec.draw(f)
    dtype, rank = _KINDS[spec.kind]
    if img.dtype != dtype or img.ndim != rank:
        raise SyntheticError(
            f"{spec.stem}: draw returned {img.dtype} rank {img.ndim}; the {spec.kind} kind is "
            f"{np.dtype(dtype).name} rank {rank}"
        )
    strip = f.in_strip
    img[strip] = spec.strip_fill
    canvas = np.zeros((size, size, 3), dtype=np.float32)
    scale = max(1, f.px(2))
    draw_text(canvas, legend_label(spec, size), f.px(8), size - f.strip + (f.strip - 7 * scale) // 2, scale)
    ink = canvas[..., 0] > 0.5
    img[ink & strip] = spec.strip_ink
    return img


def known_points(size: int = SIZE) -> list[dict[str, Any]]:
    """
    The named semantic points of every map with the pixel and the value the generator put there. A point sits at the
    centre of a feature (a band, a patch, a quadrant, a checker block, a ramp position), well inside it, so a block
    compressor's error at an edge does not reach it (the host tests read the compressed set within tolerances; the
    cook tests read an uncompressed one exactly); ``value`` is in the authoring encoding (8-bit, or 16-bit for the
    height).
    """
    f = frame(size)
    maps = {(s.suffix, s.variant): render_map(s.suffix, s.variant, size) for s in SPECS}

    def at_pixel(suffix: str, name: str, col: int, row: int, variant: str | None = None, v: float | None = None):
        value = maps[(suffix, variant)][row, col]
        return {
            "map": suffix,
            "variant": variant,
            "name": name,
            "u": (col + 0.5) / size,
            "v": v,
            "col": col,
            "row": row,
            "value": [int(x) for x in np.atleast_1d(value)],
        }

    def at(suffix: str, name: str, u: float, v: float, variant: str | None = None) -> dict[str, Any]:
        col, row = f.pixel_of(u, v)
        point = at_pixel(suffix, name, col, row, variant, v)
        point["u"] = u
        return point

    pts: list[dict[str, Any]] = []
    for name, ((pu, pv), _rgb) in PATCHES.items():
        pts.append(at("_BC", f"patch {name}", pu, pv))
        pts.append(at("_BC", f"patch {name}", pu, pv, VARIANT))
    for label, (tail, tip, _rgb) in _arrows(f).items():
        pts.append(at_pixel("_BC", f"arrow +{label}", (tail[0] + tip[0]) // 2, (tail[1] + tip[1]) // 2))
    for name, (u, v) in {
        "flat (top left)": (0.25, 0.75),
        "leans +U (top right)": (0.75, 0.75),
        "leans +V (bottom left)": (0.25, 0.25),
        "leans -U (bottom right)": (0.75, 0.25),
    }.items():
        pts.append(at("_N", name, u, v))
    cx, cy = _content_centre(f)
    radius = 0.1 * size
    for name, (dx, dy) in {"bump, half way toward +U": (0.5, 0.0), "bump, half way toward +V": (0.0, 0.5)}.items():
        pts.append(at_pixel("_N", name, int(cx + dx * radius), int(cy - dy * radius)))
    for band in range(ROUGHNESS_BANDS):
        pts.append(at("_R", f"band {band} of {ROUGHNESS_BANDS}", (band + 0.5) / ROUGHNESS_BANDS, 0.5))
    block = f.px(CHECKER_BLOCK) / size
    pts.append(at("_M", "checker block 0,0 (metal)", block * 0.5, 0.9))
    pts.append(at("_M", "checker block 1,0 (dielectric)", block * 1.5, 0.9))
    for suffix in ("_AO", "_SO"):
        pts.append(at(suffix, "centre", 0.5, 0.5))
        pts.append(at(suffix, "near a corner", 0.04, 0.04))
    pts.append(at("_C", "between lines", 0.30, 0.50))
    for u in (0.125, 0.375, 0.625):
        pts.append(at("_H", f"ramp at u={u}", u, 0.9))
    pts.append(at("_H", "cone apex", 0.75, 0.5))
    pts.append(at("_O", "inside the disc", 0.5, 0.5))
    pts.append(at("_O", "outside the disc", 0.02, 0.02))
    for k, name in enumerate(("band 0", "band 1", "band 2")):
        pts.append(at("_SC", name, (k + 0.5) / 3, 0.5))
    for suffix in ("_SW", "_AX", "_AR"):
        for t in (0.25, 0.75):
            pts.append(at(suffix, f"at {t}", t, t))
    scale = f.px(36)
    gx = (size - 5 * scale) // 2
    gy = (size - f.strip - 7 * scale) // 2
    for name, (col, row) in {
        "inside the stem of the E": (gx + scale // 2, gy + 3 * scale),
        "outside the E": (gx // 2, gy + 3 * scale),
    }.items():
        pts.append(at_pixel("_E", name, col, row))
    return pts


def contact_sheet(tile: int = 256, columns: int = 4) -> NDArray[np.uint8]:
    """
    Every map of the set side by side as one 8-bit RGB picture, ``columns`` to a row at ``tile`` pixels (a gray map
    broadcast, the 16-bit height shifted to 8 bits): the picture the gallery shows. Four columns of 256 is 1024 on
    a side, the gallery's limit.
    """
    rows = -(-len(SPECS) // columns)
    sheet = np.zeros((rows * tile, columns * tile, 3), dtype=np.uint8)
    for k, spec in enumerate(SPECS):
        img = render_map(spec.suffix, spec.variant, tile)
        if img.dtype == np.uint16:
            img = (img >> 8).astype(np.uint8)
        if img.ndim == 2:
            img = np.repeat(img[..., None], 3, axis=2)
        r, c = divmod(k, columns)
        sheet[r * tile : (r + 1) * tile, c * tile : (c + 1) * tile] = img
    return sheet


def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


LICENCE = f"""# synthetic

- **Source:** generated by `tools/gen_synthetic_textures.py` (`hogshade.testdata.synthetic`) from numbers; no
  photograph, no scan, no model
- **Author:** the repository (provenance `author`)
- **Licence:** this repository's licence applies
- **Generated:** {TODAY}
- **Role in HogShade:** T4 tier 1: a map for every suffix the content standard names, a known value at every texel,
  the ground truth the generated, local and baked tiers are compared against. An instrument, not a material and not
  a tile (the bottom strip names each map).
- **Regenerate:** `uv run tools/gen_synthetic_textures.py`, then cook the set (`uv run tools/cook_textures.py cook
  content/textures/synthetic --compress`)
"""


def generate(set_dir: Path, size: int = SIZE) -> list[Path]:
    """
    Write the set into ``set_dir``: every map as a PNG with its sidecar, and ``LICENSE.md``. Returns
    the files written. Nothing under ``cooked/`` is touched. Deterministic: the same ``size`` writes the same bytes.
    """
    frame(size)  # validates the size before anything is written (a refused size leaves no directory behind)
    set_dir = Path(set_dir)
    replacing = sum(1 for p in set_dir.glob(f"T_{BASE}_*") if p.suffix in (".png", ".json")) if set_dir.is_dir() else 0
    _LOGGER.info(
        f"generating {len(SPECS)} map(s) at {size}x{size} into {set_dir}"
        + (
            f", replacing {replacing} existing file(s) (the sidecars lose what the cook derived: cook the set again)"
            if replacing
            else ""
        )
    )
    set_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in SPECS:
        image = render_map(spec.suffix, spec.variant, size)
        path = set_dir / f"{spec.stem}.png"
        png.write_png(path, image)
        sidecar = {
            "provenance": {
                "origin": "author",
                "url": "tools/gen_synthetic_textures.py",
                "licence": "the repository's licence",
                "fetched": TODAY,
                "generator": f"{_MODULE_NAME} {__version__}",
            },
            **spec.sidecar,
        }
        sidecar_path = set_dir / f"{spec.stem}.texture.json"
        sidecar_path.write_bytes(_dump(sidecar).encode("utf-8"))
        written += [path, sidecar_path]
        _LOGGER.info(f"wrote {path.name}: {spec.kind} {size}x{size} for {spec.parameter}")
    (set_dir / "LICENSE.md").write_bytes(LICENCE.encode("utf-8"))
    written.append(set_dir / "LICENSE.md")
    _LOGGER.info(f"wrote {len(written)} file(s) under {set_dir}: {len(SPECS)} PNG(s), their sidecars and LICENSE.md")
    return written


if __name__ == "__main__":
    for _s in SPECS:
        _a = render_map(_s.suffix, _s.variant, 128)
        print(f"{_s.stem}: {_a.dtype} {_a.shape} min {_a.min()} max {_a.max()}")
    print(len(known_points(128)), "known points at 128")
