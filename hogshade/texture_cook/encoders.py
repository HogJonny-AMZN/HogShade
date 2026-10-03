"""
HogShade: the encoder seam: block compression behind one protocol, ``IspcEncoder`` (Intel's ISPC Texture Compressor
through ``ispc_texcomp``, the ``textures`` extra) the default, ``TexconvEncoder`` (DirectXTex's CLI) the optional
baseline.
Package: hogshade/texture_cook/encoders

An encoder takes one level's samples and returns the block bytes the DDS writer stores; the cook loops levels.
BC4 is encoded from an R8 surface and BC5 from an RG8 surface (ISPC's contract; fed RGBA they produce nonsense,
found by decoding a block by hand on 2026-10-04); BC7 from RGBA8, with an ``alpha_*`` profile when the alpha
carries data. A level smaller than a block is edge-padded to 4x4.
"""

from __future__ import annotations

import logging as _logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.texture_cook.encoders"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

BLOCK_FORMATS = ("bc7", "bc5", "bc4")
#: The one-line fix a newcomer sees when the encoder is missing.
INSTALL_HINT = "uv sync --extra textures  (or uv sync --all-extras) installs ispc_texcomp, the texture cook's encoder"
BC7_PROFILES = ("ultrafast", "veryfast", "fast", "basic", "slow")


class Encoder(Protocol):
    """One block-compression implementation."""

    name: str
    version: str

    def encode(self, level: NDArray[np.uint8], block_format: str, alpha: bool = False, profile: str = "basic") -> bytes:
        """The block bytes of one ``(H, W, C)`` uint8 level in ``block_format`` (C: 4 for bc7, 2 for bc5, 1 for bc4)."""
        ...


def pad_to_blocks(level: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """A level edge-padded so both sides are multiples of 4 (a 2x2 or 1x1 mip still encodes as one block)."""
    h, w = level.shape[:2]
    ph, pw = (-h) % 4, (-w) % 4
    if not ph and not pw:
        return np.ascontiguousarray(level)
    return np.ascontiguousarray(np.pad(level, ((0, ph), (0, pw)) + ((0, 0),) * (level.ndim - 2), mode="edge"))


@dataclass
class IspcEncoder:
    """Intel's ISPC Texture Compressor through K0lb3's ``ispc_texcomp`` (MIT, PyPI)."""

    name: str = "ispc_texcomp"
    version: str = ""

    def __post_init__(self) -> None:
        import ispc_texcomp

        self._module = ispc_texcomp
        self.version = getattr(ispc_texcomp, "__version__", None) or str(
            getattr(ispc_texcomp, "version", lambda: "?")()
        )

    def encode(self, level: NDArray[np.uint8], block_format: str, alpha: bool = False, profile: str = "basic") -> bytes:
        t = self._module
        padded = pad_to_blocks(level)
        h, w = padded.shape[:2]
        if block_format == "bc7":
            if padded.ndim != 3 or padded.shape[2] != 4:
                raise ValueError("bc7 takes an (H, W, 4) uint8 level")
            if profile not in BC7_PROFILES:
                raise ValueError(f"bc7 profile {profile!r} is not one of {BC7_PROFILES}")
            name = f"alpha_{profile}" if alpha else profile
            if alpha and profile == "veryfast":
                name = "alpha_veryfast"
            surface = t.RGBASurface(padded.tobytes(), w, h, w * 4)
            return t.compress_blocks_bc7(surface, t.BC7EncSettings.from_profile(name))
        if block_format == "bc5":
            if padded.ndim != 3 or padded.shape[2] != 2:
                raise ValueError("bc5 takes an (H, W, 2) uint8 level (X and Y)")
            surface = t.RGBASurface(padded.tobytes(), w, h, w * 2)  # an RG8 surface: ISPC reads two bytes per texel
            return t.compress_blocks_bc5(surface)
        if block_format == "bc4":
            one = padded[..., 0] if padded.ndim == 3 else padded
            surface = t.RGBASurface(np.ascontiguousarray(one).tobytes(), w, h, w)  # an R8 surface: one byte per texel
            return t.compress_blocks_bc4(surface)
        raise ValueError(f"block format {block_format!r} is not one of {BLOCK_FORMATS}")


@dataclass
class TexconvEncoder:
    """DirectXTex's ``texconv`` on ``PATH`` or named by ``HOGSHADE_TEXCONV``: the quality baseline, a subprocess."""

    executable: Path
    name: str = "texconv"
    version: str = "unknown"

    @classmethod
    def find(cls) -> TexconvEncoder | None:
        named = os.environ.get("HOGSHADE_TEXCONV")
        exe = Path(named) if named else (Path(shutil.which("texconv")) if shutil.which("texconv") else None)
        if exe is None or not exe.is_file():
            return None
        return cls(executable=exe)

    def encode(self, level: NDArray[np.uint8], block_format: str, alpha: bool = False, profile: str = "basic") -> bytes:
        raise NotImplementedError(
            "texconv encodes whole DDS files, not levels; the cook calls encode_file() on it, which T2 leaves for the "
            "increment that wants the baseline (ispc_texcomp is the default)"
        )


def default_encoder() -> Encoder | None:
    """The ISPC encoder when the extra is installed, else ``None`` (the cook logs the hint and writes uncompressed)."""
    try:
        return IspcEncoder()
    except ImportError:
        _LOGGER.warning("no block encoder: ispc_texcomp is not installed; %s", INSTALL_HINT)
        return None


def encoder_report() -> dict:
    """What ``--check-setup`` prints: the encoder found, its version and the formats it writes."""
    enc = default_encoder()
    if enc is None:
        return {"encoder": None, "hint": INSTALL_HINT, "formats": []}
    return {
        "encoder": enc.name,
        "version": enc.version,
        "formats": list(BLOCK_FORMATS),
        "bc7_profiles": list(BC7_PROFILES),
    }
