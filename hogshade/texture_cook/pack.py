"""
HogShade: channel packing: the fixed ``_ORM`` (ambient occlusion, roughness, metalness in R, G, B) with neutral fills,
and alpha carriers (a single-channel map riding in a four-channel map's alpha, declared by the carrier's sidecar
``pack`` field).
Package: hogshade/texture_cook/pack

The T2 spec's "Packing": fixed packings are the tables'; a carrier's ``pack.a`` names the suffix of the same set
and base whose map goes into the alpha; the manifest records where every channel lives. A missing ``_ORM``
channel is filled with 1.0, the identity of the ``multiply`` blend (S1's default).
"""

from __future__ import annotations

import logging as _logging
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hogshade.material.textures import PACKED, SUFFIXES

_MODULE_NAME = "hogshade.texture_cook.pack"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The ``_ORM`` channels in order, from the tables.
ORM_SOURCES = ("_AO", "_R", "_M")
ORM_FILL = 1.0
#: The runtime maps whose alpha may carry a single-channel map.
ALPHA_CARRIERS = ("_BC", "_E", "_SC", "_ORM")
#: The suffixes with one channel, the only ones an alpha may carry.
SINGLE_CHANNEL = tuple(s for s, d in SUFFIXES.items() if d.runtime == "bc4")


def check_pack(pack: Any, carrier_suffix: str, available: set[str], where: str = "<sidecar>") -> list[str]:
    """
    The findings of a ``pack`` sidecar field: an object with ``a`` naming a single-channel suffix that exists in
    the set, on a carrier that has a free alpha. Empty when the packing is sound.
    """
    out: list[str] = []
    if not isinstance(pack, dict) or set(pack) != {"a"}:
        return [f"{where}: pack is an object with one key, 'a' (the suffix riding in the alpha)"]
    if carrier_suffix not in ALPHA_CARRIERS:
        out.append(f"{where}: {carrier_suffix} is not an alpha carrier; one of {ALPHA_CARRIERS}")
    a = pack["a"]
    if isinstance(a, dict):
        out.append(f"{where}: pack.a as an operation ({a!r}) is reserved for a later increment; a suffix for now")
    elif a not in SINGLE_CHANNEL:
        out.append(f"{where}: pack.a {a!r} is not a single-channel suffix; one of {SINGLE_CHANNEL}")
    elif a not in available:
        out.append(f"{where}: pack.a names {a}, and the set has no T_<base>{a} map")
    return out


def pack_orm(
    ao: NDArray[np.float32] | None,
    roughness: NDArray[np.float32] | None,
    metalness: NDArray[np.float32] | None,
    shape: tuple[int, int],
) -> tuple[NDArray[np.float32], dict[str, str]]:
    """
    The packed ``(H, W, 4)`` map (alpha 1.0 until a carrier packs it) and the record of each channel: a source
    suffix or ``"filled 1.0"``.
    """
    h, w = shape
    out = np.ones((h, w, 4), dtype=np.float32) * ORM_FILL
    record: dict[str, str] = {}
    for channel, (suffix, source) in enumerate(zip(ORM_SOURCES, (ao, roughness, metalness))):
        name = "RGB"[channel]
        if source is None:
            record[name] = f"filled {ORM_FILL}"
            continue
        if source.shape[:2] != (h, w):
            raise ValueError(f"{suffix} is {source.shape[1]}x{source.shape[0]}, the set is {w}x{h}")
        out[..., channel] = source[..., 0] if source.ndim == 3 else source
        record[name] = suffix
    return out, record


def put_alpha(carrier: NDArray[np.float32], single: NDArray[np.float32]) -> NDArray[np.float32]:
    """The carrier ``(H, W, 4)`` with its alpha replaced by the single-channel map ``(H, W)`` or ``(H, W, 1)``."""
    if carrier.shape[-1] != 4:
        raise ValueError("an alpha carrier has four channels")
    s = single[..., 0] if single.ndim == 3 else single
    if s.shape != carrier.shape[:2]:
        raise ValueError(
            f"the packed map is {s.shape[1]}x{s.shape[0]}, the carrier {carrier.shape[1]}x{carrier.shape[0]}"
        )
    out = np.array(carrier, dtype=np.float32, copy=True)
    out[..., 3] = s
    return out


def is_packed_suffix(suffix: str) -> bool:
    return suffix in PACKED
