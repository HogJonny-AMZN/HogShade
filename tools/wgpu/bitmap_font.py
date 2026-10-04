"""
HogShade: a 5x7 bitmap font for labels on verification pictures, with no font rasteriser in the repository.
Package: tools/wgpu/bitmap_font

``draw_text(image, text, x, y)`` paints ``text`` into a float RGB image at an integer scale; letters are upper
case (a lower-case letter maps to its capital), digits and a few marks (space, ``_ - . , ' / : ( )``) are drawn, any
other character is a hollow box so a missing glyph is seen, never silently dropped. ``text_width`` says how
many pixels a string takes, so a caller can truncate. Twenty-six letters, ten digits and the marks are enough
for a family and a title under a contact-sheet cell (the owner, 2026-10-04: "they need context").
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "tools.wgpu.bitmap_font"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

GLYPH_W, GLYPH_H, ADVANCE = 5, 7, 6

#: Each glyph is seven rows of five cells; ``#`` is ink.
_GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    "_": (".....", ".....", ".....", ".....", ".....", ".....", "#####"),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", "..#..", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    ":": (".....", "..#..", ".....", ".....", ".....", "..#..", "....."),
    ",": (".....", ".....", ".....", ".....", "..##.", "..##.", ".#..."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
}
_BOX = ("#####", "#...#", "#...#", "#...#", "#...#", "#...#", "#####")


def glyph(ch: str) -> NDArray[np.bool_]:
    """The ``(7, 5)`` ink mask of one character; a capital for a lower-case letter, a box for the unknown."""
    rows = _GLYPHS.get(ch.upper() if ch.isalpha() else ch, _BOX)
    return np.array([[c == "#" for c in row] for row in rows], dtype=bool)


def text_width(text: str, scale: int = 1) -> int:
    """The pixels a string takes at ``scale`` (five cells and a one-cell gap per character, no trailing gap)."""
    if not text:
        return 0
    return (len(text) * ADVANCE - 1) * scale


def fit(text: str, width: int, scale: int = 1) -> str:
    """``text`` cut to what fits in ``width`` pixels, the cut marked with a trailing dot when it happened."""
    if text_width(text, scale) <= width:
        return text
    per = ADVANCE * scale
    n = max(width // per - 1, 0)
    return text[:n] + "." if n else ""


def draw_text(
    image: NDArray[np.float32],
    text: str,
    x: int,
    y: int,
    scale: int = 2,
    colour: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> None:
    """Paint ``text`` with its top-left at ``(x, y)`` into a float ``(H, W, 3)`` image, in place, clipped to it."""
    h, w = image.shape[:2]
    ink = np.asarray(colour, dtype=np.float32)
    for i, ch in enumerate(text):
        mask = np.repeat(np.repeat(glyph(ch), scale, axis=0), scale, axis=1)
        gx = x + i * ADVANCE * scale
        gy = y
        x0, y0 = max(gx, 0), max(gy, 0)
        x1, y1 = min(gx + mask.shape[1], w), min(gy + mask.shape[0], h)
        if x0 >= x1 or y0 >= y1:
            continue
        sub = mask[y0 - gy : y1 - gy, x0 - gx : x1 - gx]
        region = image[y0:y1, x0:x1]
        region[sub] = ink


if __name__ == "__main__":
    _canvas = np.zeros((20, 200, 3), dtype=np.float32)
    draw_text(_canvas, "metal / Gold 0.9", 2, 3)
    for _row in _canvas[..., 0] > 0.5:
        print("".join("#" if v else "." for v in _row))
