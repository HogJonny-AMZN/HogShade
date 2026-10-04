"""
HogShade: from a document's bound texture to the runtime file a host reads, through the set's cooked manifest.
Package: hogshade/material/runtime

A document names the authoring PNG (``<set>/T_<set>_BC.png``); a host reads the cooked DDS under
``<set>/cooked/``; three authoring maps become one ``_ORM`` and a single-channel map may ride in a carrier's
alpha. ``runtime_textures`` resolves each bound texture to its DDS path, the channels that hold it and the
format written, reading ``cooked/manifest.json`` and never guessing a name: a set that was not cooked is
``CookedSetError`` naming the cook command (the content standard: no host converts at load). Standard library
only, so every DCC Python can import it (the T3 spec, section 3).
"""

from __future__ import annotations

import json
import logging as _logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hogshade.material.model import MaterialError
from hogshade.material.textures import PACKED, SUFFIXES, parse_name

_MODULE_NAME = "hogshade.material.runtime"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

COOKED_DIR = "cooked"
MANIFEST_NAME = "manifest.json"
COOK_COMMAND = "uv run tools/cook_textures.py cook <set_dir>"
#: The channels a map of each runtime kind occupies in its own file.
OWN_CHANNELS = {"bc7": "rgb", "bc5": "rg", "bc4": "r"}


class CookedSetError(MaterialError):
    """A set with no usable runtime form: not cooked, or cooked without the map a document binds."""


@dataclass(frozen=True)
class RuntimeTexture:
    """Where one bound map lives at runtime."""

    parameter: str  #: the parameter name the caller bound it under (standard or legacy, as given)
    source: str  #: the authoring file's name, as the manifest records it
    path: Path  #: the cooked DDS
    channels: str  #: ``rgb``, ``rg``, ``r``, ``g``, ``b`` or ``a``: the channels of ``path`` that hold the map
    format: str  #: the DXGI format the cook wrote (``BC7_UNORM_SRGB``, ``R16_UNORM``, ...)
    packed: bool  #: the map shares its file with others (an ``_ORM`` channel or a carrier's alpha)


def manifest_for(set_dir: Path) -> dict[str, Any]:
    """The set's cooked manifest; ``CookedSetError`` naming the command when there is none or it is unreadable."""
    path = Path(set_dir) / COOKED_DIR / MANIFEST_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise CookedSetError(f"{set_dir} has no {COOKED_DIR}/{MANIFEST_NAME}: cook it first ({COOK_COMMAND})") from e
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise CookedSetError(f"{path} is not a readable manifest ({e}); cook the set again ({COOK_COMMAND})") from e
    if not isinstance(data, dict) or not isinstance(data.get("textures"), dict):
        raise CookedSetError(f"{path} carries no textures record; cook the set again ({COOK_COMMAND})")
    return data


def _sources_of(entry: dict[str, Any]) -> list[str]:
    src = entry.get("from")
    return list(src) if isinstance(src, list) else [str(src)]


def _channel_in_packed(entry: dict[str, Any], suffix: str, source: str) -> str | None:
    """The channel letter an ``_ORM`` record gives ``suffix``, or ``a`` when the carrier's alpha names ``source``."""
    packed = entry.get("packed")
    if not isinstance(packed, dict):
        return None
    if packed.get("A") == source:
        return "a"
    for channel in "RGB":
        if packed.get(channel) == suffix:
            return channel.lower()
    return None


def locate(manifest: dict[str, Any], set_dir: Path, source_name: str, parameter: str = "") -> RuntimeTexture:
    """
    Where the authoring file ``source_name`` of the set lives at runtime, from the manifest: its own DDS, a
    channel of ``_ORM``, or a carrier's alpha. ``CookedSetError`` when no record names it.
    """
    name = parse_name(Path(source_name).stem)
    if name is None or not name.known:
        raise CookedSetError(f"{source_name}: not a texture of this repository (T_<base>_<SUFFIX>[_<variant>])")
    cooked = Path(set_dir) / COOKED_DIR
    for dds_name, entry in manifest["textures"].items():
        if not isinstance(entry, dict):
            continue
        dds = parse_name(Path(dds_name).stem)
        dds_suffix = dds.suffix if dds is not None else ""
        fmt = str(entry.get("format", ""))
        if source_name in _sources_of(entry):
            if dds_suffix in PACKED:  # _ORM: the channel the record gives this suffix
                channel = _channel_in_packed(entry, name.suffix, source_name)
                if channel is not None:
                    return RuntimeTexture(parameter, source_name, cooked / dds_name, channel, fmt, True)
            else:  # its own file
                channels = OWN_CHANNELS[SUFFIXES[name.suffix].runtime]
                return RuntimeTexture(parameter, source_name, cooked / dds_name, channels, fmt, False)
        if _channel_in_packed(entry, "", source_name) == "a":  # riding in this carrier's alpha
            return RuntimeTexture(parameter, source_name, cooked / dds_name, "a", fmt, True)
    raise CookedSetError(
        f"{set_dir}/{COOKED_DIR}/{MANIFEST_NAME} has no record of {source_name}; cook the set again ({COOK_COMMAND})"
    )


def runtime_textures(textures: dict[str, str], doc_dir: Path) -> dict[str, RuntimeTexture]:
    """
    Every bound texture of a document (``parameter -> path as the document spells it``, a ``Binding.textures``)
    resolved to its runtime form, the paths relative to ``doc_dir`` as S1 confines them. One manifest read per
    set. Logs one line per set and one per map at DEBUG.
    """
    doc_dir = Path(doc_dir)
    manifests: dict[Path, dict[str, Any]] = {}
    out: dict[str, RuntimeTexture] = {}
    for parameter, texture in textures.items():
        source = doc_dir / Path(*str(texture).replace("\\", "/").split("/"))
        set_dir = source.parent
        if set_dir not in manifests:
            manifests[set_dir] = manifest_for(set_dir)
            _LOGGER.info(
                f"runtime set {set_dir.name}: {len(manifests[set_dir]['textures'])} cooked texture(s), "
                f"compression {manifests[set_dir].get('compression', {}).get('encoder') or 'none'}"
            )
        out[parameter] = locate(manifests[set_dir], set_dir, source.name, parameter)
        rt = out[parameter]
        _LOGGER.debug(f"  {parameter}: {source.name} -> {rt.path.name} [{rt.channels}] {rt.format}")
    return out


if __name__ == "__main__":
    # smoke run: python -m hogshade.material.runtime <path.material.json>
    import sys

    from hogshade.material.document import load
    from hogshade.material.resolution import resolve

    _doc_path = Path(sys.argv[1])
    _res = resolve(load(_doc_path))
    _bound = {n: v["texture"] for n, v in _res.values.items() if isinstance(v, dict) and v.get("texture")}
    for _p, _rt in runtime_textures(_bound, _doc_path.parent).items():
        print(f"{_p}: {_rt.path} [{_rt.channels}] {_rt.format}{' packed' if _rt.packed else ''}")
