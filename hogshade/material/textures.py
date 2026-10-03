"""
HogShade: the texture conventions as data: the file-name grammar, the suffix per texturable parameter, the packed
and derived maps, the presets, and the sidecar rules. The standard's tables are generated from here and the
content check holds files to it.
Package: hogshade/material/textures

Named ``textures``, not ``texture``: the package exports no such name (failure-modes entry 13). The T1 spec
(Docs/superpowers/specs/t1-content-standard.md) fixes the shapes; the design
(Docs/design/2026-10-03-content-conventions.md) carries the owner's answers: the ``T_`` prefix stays, base colour
is ``_BC``, ``_ORM`` is the one packing. Standard library only.
"""

from __future__ import annotations

import logging as _logging
import re
from dataclasses import dataclass
from typing import Any

from hogshade.material.model import Finding
from hogshade.material.schema import type_of

_MODULE_NAME = "hogshade.material.textures"
__version__ = "0.1.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: Every texture file carries it (the owner, 2026-10-03: "yes T_ for texture files").
PREFIX = "T_"
#: The material type whose texturable parameters the suffix table covers.
STANDARD = "hogshade-standard"
#: Source image formats the authoring set may use; the cook writes the runtime set as DDS.
AUTHORING_FORMATS = (".png", ".tif", ".tiff", ".exr")
#: The repository budget for a source texture, the longer side in pixels (the 8K masters stay outside git).
MAX_RESOLUTION = 2048
#: Files beside textures that are not textures: the cook's outputs and the records.
SIDECAR_SUFFIX = ".texture.json"
NON_TEXTURE_SUFFIXES = (SIDECAR_SUFFIX, ".material.json", ".md")
RUNTIME_CONTAINER = "dds"
#: The normal-map conventions a sidecar may name for a source; the cooked output is always the first.
NORMAL_CONVENTIONS = ("opengl+y", "directx-y")
#: The sidecar fields the cook may fill from the suffix, and the ones only an author can know.
SIDECAR_DERIVED = ("preset", "colour_space", "mips", "runtime", "resolution")
SIDECAR_REQUIRED = ("provenance",)
PROVENANCE_FIELDS = ("origin", "url", "licence", "fetched")
SIDECAR_KEYS = SIDECAR_DERIVED + SIDECAR_REQUIRED + ("normal_convention", "override_reason", "derived", "source")


@dataclass(frozen=True)
class Suffix:
    """One suffix of the standard's texturable parameters: what it binds and how the cook treats it."""

    suffix: str
    parameter: str
    colour_space: str
    runtime: str
    mips: str = "linear-box"
    normal: bool = False
    authoring: str = "8-bit"
    note: str = ""


@dataclass(frozen=True)
class Packed:
    """A map a document never binds directly: the cook's packed runtime form or a derived detail map."""

    suffix: str
    what: str
    colour_space: str
    runtime: str
    normal: bool = False
    channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextureName:
    """A parsed texture file stem: ``T_<base>_<SUFFIX>[_<variant>]``."""

    base: str
    suffix: str
    variant: str | None

    @property
    def known(self) -> bool:
        return self.suffix in SUFFIXES or self.suffix in PACKED


SUFFIXES: dict[str, Suffix] = {
    s.suffix: s
    for s in (
        Suffix(
            "_BC", "base_color", "srgb", "bc7", note="the schema's word; never _D, diffuse means something else here"
        ),
        Suffix("_M", "base_metalness", "raw", "bc4", note="metalness only, never a mask"),
        Suffix("_SW", "specular_weight", "raw", "bc4"),
        Suffix("_SC", "specular_color", "raw", "bc7"),
        Suffix("_R", "specular_roughness", "raw", "bc4", note="roughness, never gloss"),
        Suffix("_AX", "specular_anisotropy", "raw", "bc4"),
        Suffix("_AR", "specular_rotation", "raw", "bc4"),
        Suffix("_E", "emission_color", "srgb", "bc7"),
        Suffix("_O", "geometry_opacity", "raw", "bc4", note="or the alpha of _BC when the sidecar packs it"),
        Suffix("_N", "geometry_normal", "raw", "bc5", normal=True, note="OpenGL +Y; two channels, Z reconstructed"),
        Suffix("_AO", "ambient_occlusion", "raw", "bc4"),
        Suffix("_C", "cavity", "raw", "bc4"),
        Suffix("_SO", "specular_occlusion", "raw", "bc4"),
        Suffix("_H", "height", "raw", "bc4", authoring="16-bit", note="R16 when the cook says"),
    )
}

PACKED: dict[str, Packed] = {
    p.suffix: p
    for p in (
        Packed(
            "_ORM",
            "packed: ambient occlusion in R, roughness in G, metalness in B; the runtime form of _AO, _R, _M",
            "raw",
            "bc7",
            channels=("ambient_occlusion", "specular_roughness", "base_metalness"),
        ),
        Packed(
            "_DN", "detail normal, derived by the cook (the high frequency of a normal map)", "raw", "bc5", normal=True
        ),
        Packed("_DH", "detail high-pass colour, derived by frequency separation; mid-grey neutral", "raw", "bc7"),
    )
}

#: ``T_<base>_<SUFFIX>[_<variant>]``: the base is snake_case, the suffix the first all-caps token, the variant
#: lower-case letters and digits. A name that does not match is not a texture of this repository.
NAME_RE = re.compile(r"^T_([a-z0-9]+(?:_[a-z0-9]+)*)_([A-Z]+)(?:_([a-z0-9]+))?$")


def parse_name(stem: str) -> TextureName | None:
    """The parts of a texture file stem, or ``None`` when the grammar is not met (prefix, case, order)."""
    m = NAME_RE.match(stem)
    if m is None:
        return None
    base, suffix, variant = m.groups()
    return TextureName(base=base, suffix=f"_{suffix}", variant=variant)


def preset_for(suffix: str) -> dict[str, Any]:
    """The derived sidecar fields of a suffix; ``KeyError`` for a suffix the tables do not know."""
    if suffix in SUFFIXES:
        s = SUFFIXES[suffix]
        return {
            "preset": s.parameter,
            "colour_space": s.colour_space,
            "mips": s.mips,
            "runtime": {"format": s.runtime, "container": RUNTIME_CONTAINER},
            "normal": s.normal,
        }
    p = PACKED[suffix]
    return {
        "preset": suffix.strip("_").lower(),
        "colour_space": p.colour_space,
        "mips": "linear-box",
        "runtime": {"format": p.runtime, "container": RUNTIME_CONTAINER},
        "normal": p.normal,
    }


def parameter_of(suffix: str) -> str | None:
    """The standard parameter a suffix binds, or ``None`` for a packed or derived map."""
    s = SUFFIXES.get(suffix)
    return s.parameter if s else None


def check_suffixes(type_name: str = STANDARD) -> list[Finding]:
    """
    The suffix table against the schema: every texturable parameter of the type has exactly one suffix, every
    suffix names a parameter of the type with the schema's colour space, and no packed suffix shadows one.
    """
    where = "hogshade.material.textures"
    out: list[Finding] = []
    mtype = type_of(type_name)
    texturable = {name for name, p in mtype.parameters.items() if p.texturable}
    seen: dict[str, str] = {}
    for suffix, s in SUFFIXES.items():
        p = mtype.parameters.get(s.parameter)
        if p is None:
            out.append(Finding(where, suffix, f"names {s.parameter!r}, not a parameter of {type_name}"))
            continue
        if not p.texturable:
            out.append(Finding(where, suffix, f"{s.parameter!r} has no colour space in the schema, so no texture"))
        elif p.colour_space != s.colour_space:
            out.append(
                Finding(where, suffix, f"colour space {s.colour_space!r} but the schema says {p.colour_space!r}")
            )
        if s.parameter in seen:
            out.append(Finding(where, suffix, f"{s.parameter!r} already has the suffix {seen[s.parameter]}"))
        seen[s.parameter] = suffix
        if suffix in PACKED:
            out.append(Finding(where, suffix, "is both a parameter suffix and a packed map"))
    for name in sorted(texturable - set(seen)):
        out.append(Finding(where, name, "texturable in the schema but has no suffix"))
    return out


def _is_str(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _agrees(stated: Any, expected: Any) -> bool:
    """
    A stated derived field agrees with the suffix: equal, or for an object, every stated key one the preset has,
    with the preset's value (an unknown key, even with a null value, is a disagreement).
    """
    if isinstance(stated, dict) and isinstance(expected, dict):
        return all(k in expected and expected[k] == v for k, v in stated.items())
    return stated == expected


def check_sidecar(data: Any, suffix: str, where: str = "<sidecar>") -> list[Finding]:
    """
    A parsed sidecar against its suffix: the required fields present and well formed, a derived field that
    disagrees with the suffix a finding unless ``override_reason`` says why, a normal map's convention stated.
    """
    out: list[Finding] = []
    if not isinstance(data, dict):
        return [Finding(where, "", "a sidecar is a JSON object")]
    if suffix not in SUFFIXES and suffix not in PACKED:
        return [Finding(where, "", f"suffix {suffix!r} is not in the tables")]
    for key in data:
        if key not in SIDECAR_KEYS:
            out.append(Finding(where, key, "unknown sidecar field"))
    prov = data.get("provenance")
    if not isinstance(prov, dict):
        out.append(Finding(where, "provenance", "required: an object with origin, url, licence, fetched"))
    else:
        for key in PROVENANCE_FIELDS:
            if not _is_str(prov.get(key)):
                out.append(Finding(where, "provenance", f"carries a non-empty {key!r}"))
    expected = preset_for(suffix)
    if expected["normal"] and suffix in SUFFIXES:  # a derived _DN is the cook's, always opengl+y
        nc = data.get("normal_convention")
        if nc not in NORMAL_CONVENTIONS:
            out.append(
                Finding(
                    where,
                    "normal_convention",
                    f"a normal map states its source's convention, one of {NORMAL_CONVENTIONS}",
                )
            )
    elif "normal_convention" in data:
        out.append(Finding(where, "normal_convention", "only a normal map carries it"))
    overridden = _is_str(data.get("override_reason"))
    for key in ("preset", "colour_space", "mips", "runtime"):
        if key in data and not _agrees(data[key], expected[key]) and not overridden:
            out.append(
                Finding(
                    where, key, f"{data[key]!r} disagrees with the suffix's {expected[key]!r}; override_reason says why"
                )
            )
    res = data.get("resolution")
    if "resolution" in data and not (isinstance(res, int) and not isinstance(res, bool) and res > 0):
        out.append(Finding(where, "resolution", "a positive integer, the longer side in pixels"))
    elif isinstance(res, int) and not isinstance(res, bool) and res > MAX_RESOLUTION:
        out.append(
            Finding(
                where,
                "resolution",
                f"{res} exceeds the repository budget of {MAX_RESOLUTION}; masters stay outside git",
            )
        )
    if "derived" in data and not (
        isinstance(data["derived"], list) and all(isinstance(d, str) for d in data["derived"])
    ):
        out.append(Finding(where, "derived", "a list of the field names the cook filled"))
    return out


if __name__ == "__main__":
    # smoke run: the table against the schema, and a few names
    for _f in check_suffixes():
        print(_f)
    for _stem in ("T_cobblestone_floor_04_BC", "T_grid_N_01", "cobblestone_BC", "T_Grid_BC"):
        print(_stem, parse_name(_stem))
