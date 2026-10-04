"""
HogShade: the cook itself: one authoring set in, its runtime set out, with the manifest and the provenance.
Package: hogshade/texture_cook/cook

``cook_set`` reads every source texture of a set (T1's rules applied first, then the shapes: a set with a finding
is refused before anything is written), builds each one's mip chain in the right space, flips a DirectX normal,
packs ``_ORM`` and any alpha carrier the sidecars declare, writes DDS (block-compressed through the encoder seam
when one is present, uncompressed otherwise), and only then writes the sidecars' derived fields, ``manifest.json``
(deterministic) and ``provenance.json`` (volatile) under ``<set>/cooked/``. ``separate_set`` is the owner's
frequency separation. Every artifact written and every decision taken on the caller's behalf is one INFO line.
"""

from __future__ import annotations

import hashlib
import json
import logging as _logging
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hogshade import __version__ as HOGSHADE_VERSION
from hogshade.material.textures import (
    AUTHORING_FORMATS,
    MAX_RESOLUTION,
    PACKED,
    SIDECAR_DERIVED,
    SIDECAR_SUFFIX,
    SUFFIXES,
    check_sidecar,
    parse_name,
    preset_for,
)
from hogshade.texture_cook import colour, dds2d, mips, normals, pack, png
from hogshade.texture_cook import height as height_mod
from hogshade.texture_cook import separate as sep
from hogshade.texture_cook.encoders import BC7_PROFILES, INSTALL_HINT, Encoder, default_encoder

_MODULE_NAME = "hogshade.texture_cook.cook"
__version__ = "0.2.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

COOKED_DIR = "cooked"
MANIFEST_NAME = "manifest.json"
PROVENANCE_NAME = "provenance.json"
TO_TYPE_NOTE = "hogshade-standard suffixes (Docs/standards/content.md)"
#: The suffixes cooked as colour (sRGB, mips in linear) and as plain RGB data.
COLOUR_SUFFIXES = ("_BC", "_E")
DATA_RGB_SUFFIXES = ("_SC",)
BLOCK_NAMES = {"bc7": "BC7_UNORM", "bc5": "BC5_UNORM", "bc4": "BC4_UNORM"}
ORM_CHANNEL_SOURCE = dict(zip("RGB", pack.ORM_SOURCES))


class CookError(ValueError):
    """A set the cook refuses, with the findings in the message."""


@dataclass
class Source:
    """One source texture of a set as read, with its parsed name and its sidecar."""

    path: Path
    base: str
    suffix: str
    variant: str | None
    sidecar_path: Path
    sidecar: dict[str, Any]
    samples: NDArray[np.uint8] | NDArray[np.uint16] | NDArray[np.float16] | NDArray[np.float32]
    """As read: integer ``(H, W, C)`` from a PNG, float ``(H, W)`` from an EXR height."""

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def size(self) -> tuple[int, int]:
        """``(width, height)``."""
        return int(self.samples.shape[1]), int(self.samples.shape[0])

    @property
    def channels(self) -> int:
        return int(self.samples.shape[2]) if self.samples.ndim == 3 else 1


@dataclass
class CookResult:
    """What ``cook_set`` returns: the manifest as written and every file the cook wrote."""

    manifest: dict[str, Any] = field(default_factory=dict)
    written: list[Path] = field(default_factory=list)


@dataclass
class _Oven:
    """The per-cook state the suffix cooks share: where to write, how to compress, what was consumed."""

    sources: list[Source]
    out_dir: Path
    encoder: Encoder | None
    bc7_profile: str
    height_normalise: bool = False
    consumed: set[str] = field(default_factory=set)  # stems packed into another map, never written on their own
    textures: dict[str, Any] = field(default_factory=dict)
    written: list[Path] = field(default_factory=list)

    def pack_target(self, s: Source) -> Source | None:
        """The map a source's ``pack`` field puts in its carrier's alpha, in the source's variant."""
        if "pack" not in s.sidecar:
            return None
        return _single(self.sources, s.sidecar["pack"]["a"], s.variant)


def sha256_file(path: Path) -> str:
    """The hex SHA-256 of a file, read in 1 MiB blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_hash() -> str:
    """The repository's HEAD for the provenance, ``"unknown"`` without git."""
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _dump(data: dict[str, Any]) -> str:
    """The one JSON spelling every record of the cook is written in (LF, written as bytes), so hashes compare."""
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _read_sidecar(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise CookError(f"{path.name}: not a readable JSON sidecar ({e})") from e
    if not isinstance(data, dict):
        raise CookError(f"{path.name}: a sidecar is a JSON object")
    return data


def _read_samples(p: Path, suffix: str, problems: list[str]) -> NDArray | None:
    """The samples of one source, or ``None`` with the finding appended; an EXR is a height map, one channel read."""
    if p.suffix == ".exr":
        if suffix != "_H":
            problems.append(f"{p.name}: an EXR source is a height map (_H) in T2")
            return None
        try:
            samples, _precision = height_mod.read_exr_channel(p)
        except ImportError as e:
            problems.append(f"{p.name}: reading an EXR needs OpenEXR ({e}); uv sync installs it")
            return None
        except (OSError, ValueError, RuntimeError) as e:
            problems.append(f"{p.name}: not a readable EXR ({e})")
            return None
        return samples
    try:
        return png.read_png(p)
    except png.PngError as e:
        problems.append(str(e))
        return None


def _check_shapes(sources: list[Source], problems: list[str]) -> None:
    """
    The shape rules a set must meet before anything is written: every map of one base and variant at one size (a
    pack target or an ``_ORM`` part of another size cannot be packed), one base per directory (the packing matches
    by suffix and variant), the ``_ORM`` alpha declared on at most one of its parts per variant, no grey-alpha
    source where RGB is meant (grey is broadcast, RGBA loses its alpha), and every ``pack`` target present in the
    carrier's own variant.
    """
    by_group: dict[tuple[str, str | None], list[Source]] = {}
    for s in sources:
        by_group.setdefault((s.base, s.variant), []).append(s)
    for _key, group in sorted(by_group.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        if len({s.size for s in group}) > 1:
            listed = ", ".join(f"{s.path.name} {s.size[0]}x{s.size[1]}" for s in group)
            problems.append(f"one size per set and variant (the packing needs it): {listed}")
    bases = sorted({s.base for s in sources})
    if len(bases) > 1:
        problems.append(f"one base per set directory (the packing matches by suffix and variant): {', '.join(bases)}")
    for variant in sorted({s.variant for s in sources if s.suffix in pack.ORM_SOURCES}, key=lambda v: v or ""):
        declared = {
            s.sidecar["pack"]["a"]: s.sidecar_path.name
            for s in sources
            if s.suffix in pack.ORM_SOURCES and s.variant == variant and "pack" in s.sidecar
        }
        if len(declared) > 1:
            problems.append(
                "the _ORM alpha is declared once per variant; "
                + ", ".join(f"{where} names {a}" for a, where in sorted(declared.items()))
            )
    for s in sources:
        if s.suffix in COLOUR_SUFFIXES + DATA_RGB_SUFFIXES + ("_N",) and s.channels == 2:
            problems.append(
                f"{s.path.name}: a grey-alpha PNG is neither a colour map nor a grey one; RGB, RGBA or grey"
            )
        if "pack" in s.sidecar and _single(sources, s.sidecar["pack"]["a"], s.variant) is None:
            where = f"variant {s.variant!r}" if s.variant else "the unvarianted set"
            problems.append(
                f"{s.sidecar_path.name}: pack.a names {s.sidecar['pack']['a']}, and {where} has no such map "
                "(a pack target lives in its carrier's variant)"
            )


def read_sources(set_dir: Path) -> list[Source]:
    """
    Every source texture of a set, read and checked against T1's rules and the shape rules; ``CookError`` listing
    every finding when one exists (a misnamed, unsourced, contradictory or mis-sized texture is never cooked). A
    ``.tif`` is a finding naming the T2 limit.
    """
    set_dir = Path(set_dir)
    if not set_dir.is_dir():
        raise CookError(f"no such set directory: {set_dir}")
    if not (set_dir / "LICENSE.md").is_file():
        raise CookError(
            f"{set_dir.name}: no LICENSE.md (the content standard: a directory of source textures carries one)"
        )
    problems: list[str] = []
    sources: list[Source] = []
    candidates = sorted(
        p for p in set_dir.iterdir() if p.is_file() and not p.name.endswith((SIDECAR_SUFFIX, ".material.json", ".md"))
    )
    for p in candidates:
        if p.suffix.lower() in (".tif", ".tiff"):
            problems.append(f"{p.name}: TIFF is not read in T2; convert to 16-bit PNG (the spec's question 1)")
            continue
        if p.suffix not in AUTHORING_FORMATS:
            problems.append(f"{p.name}: {p.suffix!r} is not an authoring format {AUTHORING_FORMATS}")
            continue
        name = parse_name(p.stem)
        if name is None or not name.known:
            problems.append(f"{p.name}: not T_<snake_case>_<SUFFIX>[_<variant>] with a known suffix")
            continue
        if name.suffix in PACKED:
            problems.append(f"{p.name}: {name.suffix} is the cook's output, never authored")
            continue
        sidecar_path = p.with_name(p.stem + SIDECAR_SUFFIX)
        sidecar = _read_sidecar(sidecar_path)
        if not sidecar:
            problems.append(f"{p.name}: no sidecar {sidecar_path.name} beside it")
            continue
        findings = check_sidecar(sidecar, name.suffix, sidecar_path.name)
        problems.extend(str(f) for f in findings)
        if findings:
            continue
        samples = _read_samples(p, name.suffix, problems)
        if samples is None:
            continue
        if max(samples.shape[:2]) > MAX_RESOLUTION:
            problems.append(
                f"{p.name}: {samples.shape[1]}x{samples.shape[0]} exceeds the repository budget of {MAX_RESOLUTION}"
            )
            continue
        sources.append(Source(p, name.base, name.suffix, name.variant, sidecar_path, sidecar, samples))
    # alpha carriers: the pack field against what the set holds
    available = {s.suffix for s in sources}
    for s in sources:
        if "pack" in s.sidecar:
            # an _AO, _R or _M sidecar declares the _ORM alpha, since _ORM itself has no source
            carrier = "_ORM" if s.suffix in pack.ORM_SOURCES else s.suffix
            problems.extend(pack.check_pack(s.sidecar["pack"], carrier, available, s.sidecar_path.name))
    if not problems:
        _check_shapes(sources, problems)
    if problems:
        raise CookError(f"{set_dir.name} has findings: " + "; ".join(problems))
    if not sources:
        raise CookError(f"{set_dir.name}: no source texture to cook")
    return sources


def _unit(s: Source) -> NDArray[np.float32]:
    """A source's samples as [0, 1] float32 ``(H, W, C)``."""
    return colour.to_unit(s.samples if s.samples.ndim == 3 else s.samples[..., None])


def _rgb(s: Source) -> NDArray[np.float32]:
    """The three colour channels of a source: a grey map broadcast, a fourth channel dropped; both logged."""
    unit = _unit(s)
    if unit.shape[-1] == 1:
        _LOGGER.info("%s: a grey map, broadcast to RGB", s.path.name)
        return np.repeat(unit, 3, axis=-1)
    if unit.shape[-1] > 3:
        if s.suffix == "_N":
            runtime_alpha = "the runtime map has two channels"
        elif "pack" in s.sidecar:
            runtime_alpha = f"the runtime alpha is packed from {s.sidecar['pack']['a']}"
        else:
            runtime_alpha = "the runtime alpha is 1.0"
        _LOGGER.info("%s: the source alpha is dropped (%s)", s.path.name, runtime_alpha)
    return np.ascontiguousarray(unit[..., :3])


def _one_channel(s: Source) -> NDArray[np.float32]:
    """The single channel of a one-channel map ``(H, W, 1)``; the first channel of a wider one, logged."""
    unit = _unit(s)
    if unit.shape[-1] > 1:
        _LOGGER.info("%s: %d channels in a single-channel map; R is taken", s.path.name, unit.shape[-1])
    return np.ascontiguousarray(unit[..., :1])


def _single(sources: list[Source], suffix: str, variant: str | None) -> Source | None:
    for s in sources:
        if s.suffix == suffix and s.variant == variant:
            return s
    return None


def _note_alpha_precision(packed: Source) -> None:
    """A map riding in an 8-bit alpha keeps 8 bits: said once when its source had more."""
    if packed.samples.dtype != np.uint8:
        _LOGGER.info("%s: %s reduced to 8 bits in the alpha", packed.path.name, packed.samples.dtype.name)


def _with_alpha(levels_rgb: list[NDArray[np.float32]], packed: Source | None) -> list[NDArray[np.float32]]:
    """The RGB chain with its alpha: the packed map's own chain, or 1.0."""
    if packed is None:
        return [np.concatenate([lvl, np.ones(lvl.shape[:2] + (1,), np.float32)], axis=-1) for lvl in levels_rgb]
    _note_alpha_precision(packed)
    a_levels = mips.data_chain(_one_channel(packed))
    return [np.concatenate([lvl, a], axis=-1) for lvl, a in zip(levels_rgb, a_levels, strict=True)]


def _write(
    out_path: Path,
    levels_unit: list[NDArray[np.float32]],
    uncompressed: str,
    block: str | None,
    encoder: Encoder | None,
    alpha: bool,
    profile: str,
) -> dict[str, Any]:
    """One texture's DDS: block-compressed when an encoder and a block format are given, else uncompressed."""
    if encoder is not None and block is not None:
        block_mips = [encoder.encode(colour.to_uint8(lvl), block, alpha=alpha, profile=profile) for lvl in levels_unit]
        name = BLOCK_NAMES[block] + ("_SRGB" if block == "bc7" and uncompressed.endswith("_SRGB") else "")
        dds2d.write_2d_blocks(out_path, block_mips, levels_unit[0].shape[1], levels_unit[0].shape[0], name)
        record: dict[str, Any] = {"format": name, "encoder": encoder.name}
        if block == "bc7":
            record["bc7_profile"] = f"alpha_{profile}" if alpha else profile
    else:
        dds2d.write_2d(out_path, [colour.to_uint8(lvl) for lvl in levels_unit], uncompressed)
        record = {"format": uncompressed, "encoder": None}
    _LOGGER.info("wrote %s: %s, %d mip(s)", out_path.name, record["format"], len(levels_unit))
    return record


def _finish(oven: _Oven, out_path: Path, entry: dict[str, Any], levels: int) -> None:
    """The record every written texture gets: the mip count and the hash of the file."""
    entry["mips"] = levels
    entry["sha256"] = sha256_file(out_path)
    oven.textures[out_path.name] = entry
    oven.written.append(out_path)


def _entry(s: Source) -> dict[str, Any]:
    return {"from": s.path.name, "preset": SUFFIXES[s.suffix].parameter, "size": list(s.size)}


def _cook_colour(oven: _Oven, s: Source) -> None:
    """``_BC`` and ``_E`` (sRGB, mips in linear) and ``_SC`` (plain RGB data), with a packed or 1.0 alpha, as BC7."""
    out_path = oven.out_dir / f"{s.stem}.dds"
    entry = _entry(s)
    rgb = _rgb(s)
    packed = oven.pack_target(s)
    srgb = s.suffix in COLOUR_SUFFIXES
    levels = _with_alpha(mips.colour_chain(rgb) if srgb else mips.data_chain(rgb), packed)
    fmt = "R8G8B8A8_UNORM_SRGB" if srgb else "R8G8B8A8_UNORM"
    entry.update(_write(out_path, levels, fmt, "bc7", oven.encoder, packed is not None, oven.bc7_profile))
    if packed is not None:
        entry["packed"] = {"A": packed.path.name}
        _LOGGER.info("%s: %s rides in the alpha", out_path.name, packed.path.name)
    _finish(oven, out_path, entry, len(levels))


def _cook_normal(oven: _Oven, s: Source) -> None:
    """``_N``: decoded, brought to ``opengl+y``, mips renormalised, the X and Y channels as BC5."""
    out_path = oven.out_dir / f"{s.stem}.dds"
    entry = _entry(s)
    convention = s.sidecar["normal_convention"]
    xyz = normals.to_opengl(normals.decode(_rgb(s)), convention)
    if convention != "opengl+y":
        _LOGGER.info("%s: normal convention %s, Y flipped to opengl+y", s.path.name, convention)
    levels = [normals.to_rg(normals.encode(lvl)) for lvl in mips.normal_chain(xyz)]
    entry.update(_write(out_path, levels, "R8G8_UNORM", "bc5", oven.encoder, False, oven.bc7_profile))
    entry["normal_convention_in"] = convention
    entry["flipped_y"] = convention == "directx-y"
    _finish(oven, out_path, entry, len(levels))


def _cook_height(oven: _Oven, s: Source) -> None:
    """``_H`` at the source's precision; BC4 only for an 8-bit source with an encoder; normalised when asked."""
    out_path = oven.out_dir / f"{s.stem}.dds"
    entry = _entry(s)
    h = height_mod.from_array(s.samples)
    if oven.height_normalise:
        h, rng = height_mod.normalise(h)
        if rng:
            entry["normalised"] = rng
    levels = height_mod.chain(h)
    if h.runtime == "R8_UNORM" and oven.encoder is not None:
        block_mips = [oven.encoder.encode(lvl[..., None], "bc4") for lvl in levels]
        dds2d.write_2d_blocks(out_path, block_mips, levels[0].shape[1], levels[0].shape[0], "BC4_UNORM")
        entry.update({"format": "BC4_UNORM", "encoder": oven.encoder.name})
    else:
        dds2d.write_2d(out_path, [lvl[..., None] for lvl in levels], h.runtime)
        entry.update({"format": h.runtime, "encoder": None})
    _LOGGER.info("wrote %s: %s (%s source), %d mip(s)", out_path.name, entry["format"], h.precision, len(levels))
    entry["precision"] = h.precision
    _finish(oven, out_path, entry, len(levels))


def _cook_single(oven: _Oven, s: Source) -> None:
    """A one-channel map on its own: R8, or BC4 with an encoder."""
    out_path = oven.out_dir / f"{s.stem}.dds"
    entry = _entry(s)
    levels = mips.data_chain(_one_channel(s))
    entry.update(_write(out_path, levels, "R8_UNORM", "bc4", oven.encoder, False, oven.bc7_profile))
    _finish(oven, out_path, entry, len(levels))


def _cook_orm(oven: _Oven, variant: str | None) -> None:
    """The fixed packing: ``_ORM`` from ``_AO``, ``_R``, ``_M`` (any present, 1.0 fills the rest), per variant."""
    parts = {suf: _single(oven.sources, suf, variant) for suf in pack.ORM_SOURCES}
    shape_src = next(s for s in parts.values() if s is not None)
    w, h = shape_src.size
    packed, record = pack.pack_orm(
        _one_channel(parts["_AO"]) if parts["_AO"] else None,
        _one_channel(parts["_R"]) if parts["_R"] else None,
        _one_channel(parts["_M"]) if parts["_M"] else None,
        (h, w),
    )
    stem = f"T_{shape_src.base}_ORM" + (f"_{variant}" if variant else "")
    out_path = oven.out_dir / f"{stem}.dds"
    for channel, what in record.items():
        if what.startswith("filled"):
            _LOGGER.info("%s: channel %s %s (no %s source)", out_path.name, channel, what, ORM_CHANNEL_SOURCE[channel])
    levels = mips.data_chain(packed)
    # an _ORM alpha carrier is declared on any of its sources' sidecars as {"pack": {"a": "_H"}}; the first found
    extra = next((oven.pack_target(src) for src in parts.values() if src is not None and "pack" in src.sidecar), None)
    if extra is not None:
        _note_alpha_precision(extra)
        a_levels = mips.data_chain(_one_channel(extra))
        levels = [pack.put_alpha(lvl, a[..., 0]) for lvl, a in zip(levels, a_levels, strict=True)]
        oven.consumed.add(extra.stem)
        _LOGGER.info("%s: %s rides in the alpha", out_path.name, extra.path.name)
    entry = {"from": [p.path.name for p in parts.values() if p is not None], "preset": "orm", "size": [w, h]}
    entry.update(_write(out_path, levels, "R8G8B8A8_UNORM", "bc7", oven.encoder, extra is not None, oven.bc7_profile))
    rec = dict(record)
    if extra is not None:
        rec["A"] = extra.path.name
    entry["packed"] = rec
    _finish(oven, out_path, entry, len(levels))


def _sidecar_fill(s: Source) -> tuple[dict[str, Any], list[str]]:
    """
    The sidecar with the derived fields the cook has authority over filled when absent (authored fields untouched),
    and the keys this cook filled. Nothing is written here.
    """
    data = dict(s.sidecar)
    preset = preset_for(s.suffix)
    fills = {
        "preset": preset["preset"],
        "colour_space": preset["colour_space"],
        "mips": preset["mips"],
        "runtime": preset["runtime"],  # the preset's token; the manifest carries the exact format written
        "resolution": int(max(s.size)),
    }
    filled = [key for key in SIDECAR_DERIVED if key not in data]
    for key in filled:
        data[key] = fills[key]
    if filled:
        data["derived"] = sorted(set(data.get("derived", [])) | set(filled))
    return data, filled


def _keep_separation(out_dir: Path, textures: dict[str, Any]) -> dict[str, Any] | None:
    """
    The earlier ``separate_set`` records (one per separated suffix), each kept when every file it names is still
    there (a re-cook rebuilds the manifest and must not orphan them) and dropped with a warning otherwise; the
    dict is empty when none survives. Other ``.dds`` files under ``cooked/`` that no record names are warned
    about, never deleted.
    """
    manifest_path = out_dir / MANIFEST_NAME
    previous: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            block = loaded.get("separation", {}) if isinstance(loaded, dict) else {}
            previous = block if isinstance(block, dict) and "source" not in block else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            _LOGGER.warning("%s: the earlier manifest is unreadable and is replaced (%s)", manifest_path, e)
    kept: dict[str, Any] = {}
    for suffix, record in sorted(previous.items()):
        outputs = record.get("outputs", {}) if isinstance(record, dict) else {}
        missing = [name for name in outputs if not (out_dir / name).is_file()]
        if missing or not outputs:
            _LOGGER.warning(
                "the earlier %s separation record is dropped: its files are gone (%s)", suffix, ", ".join(missing)
            )
        else:
            kept[suffix] = record
            _LOGGER.info("the earlier %s separation record is kept (%s)", suffix, ", ".join(sorted(outputs)))
    named = set(textures) | {name for record in kept.values() for name in record["outputs"]}
    stale = sorted(p.name for p in out_dir.glob("*.dds") if p.name not in named)
    if stale:
        _LOGGER.warning(
            "%s holds %d .dds file(s) no record names, left alone: %s", out_dir, len(stale), ", ".join(stale)
        )
    return kept


def cook_set(
    set_dir: Path,
    compress: bool | None = None,
    encoder: Encoder | None = None,
    bc7_profile: str = "basic",
    height_normalise: bool = False,
) -> CookResult:
    """
    Cook one set. ``compress`` None means "when an encoder is present"; True requires one (``CookError`` with the
    install hint otherwise); False writes uncompressed. Returns the manifest and the files written. The sidecars'
    derived fields and the manifest are written only after every DDS is, so a failure leaves the authoring set as
    it was.
    """
    started = time.time()
    set_dir = Path(set_dir).resolve()
    if bc7_profile not in BC7_PROFILES:
        raise CookError(f"bc7 profile {bc7_profile!r} is not one of {BC7_PROFILES}")
    sources = read_sources(set_dir)
    if compress is not False and encoder is None:
        encoder = default_encoder()
    if compress is True and encoder is None:
        raise CookError(f"--compress asked for and no encoder is installed; {INSTALL_HINT}")
    if compress is False:
        encoder = None
    out_dir = set_dir / COOKED_DIR
    out_dir.mkdir(exist_ok=True)
    _LOGGER.info(
        "cooking %s: %d source(s), encoder %s, bc7 profile %s",
        set_dir.name,
        len(sources),
        encoder.name if encoder else "none (uncompressed)",
        bc7_profile,
    )
    oven = _Oven(sources, out_dir, encoder, bc7_profile, height_normalise)
    # the sidecars as they will be written, hashed now so the manifest is one whether this cook fills them or not
    sidecars = {s.stem: _sidecar_fill(s) for s in sources}
    inputs = {s.path.name: sha256_file(s.path) for s in sources}
    for s in sources:  # a sidecar this cook rewrites is hashed as it will be written; one it leaves alone, as it is
        data, filled = sidecars[s.stem]
        inputs[s.sidecar_path.name] = (
            _sha256_bytes(_dump(data).encode("utf-8")) if filled else sha256_file(s.sidecar_path)
        )
    inputs["LICENSE.md"] = sha256_file(set_dir / "LICENSE.md")
    for s in sources:
        packed = oven.pack_target(s)
        if packed is not None:
            oven.consumed.add(packed.stem)
    for s in sources:
        if s.stem in oven.consumed or s.suffix in pack.ORM_SOURCES:
            continue  # packed into a carrier's alpha, or into _ORM: the runtime form, no file of its own
        if s.suffix in COLOUR_SUFFIXES + DATA_RGB_SUFFIXES:
            _cook_colour(oven, s)
        elif s.suffix == "_N":
            _cook_normal(oven, s)
        elif s.suffix == "_H":
            _cook_height(oven, s)
        else:
            _cook_single(oven, s)
    for variant in sorted({s.variant for s in sources if s.suffix in pack.ORM_SOURCES}, key=lambda v: v or ""):
        _cook_orm(oven, variant)
    # every DDS is on disk: now the sidecars, the manifest, the provenance
    derived: list[str] = []
    for s in sources:
        data, filled = sidecars[s.stem]
        if filled:
            s.sidecar_path.write_bytes(_dump(data).encode("utf-8"))
            s.sidecar = data
            _LOGGER.info("wrote %s: derived %s", s.sidecar_path.name, ", ".join(filled))
        derived.extend(f"{s.sidecar_path.name}:{k}" for k in data.get("derived", []))
    separations = _keep_separation(out_dir, oven.textures)
    manifest = {
        "tool": _MODULE_NAME,
        "tool_version": __version__,
        "hogshade_version": HOGSHADE_VERSION,
        "set": set_dir.name,
        "suffix_table": TO_TYPE_NOTE,
        "inputs": dict(sorted(inputs.items())),
        "textures": dict(sorted(oven.textures.items())),
        "compression": {"encoder": encoder.name if encoder else None, "bc7_profile": bc7_profile if encoder else None},
        "sidecars_derived": sorted(derived),
        "not_power_of_two": sorted(s.path.name for s in sources if any((d & (d - 1)) for d in s.samples.shape[:2])),
    }
    if separations:
        manifest["separation"] = separations
    (out_dir / MANIFEST_NAME).write_bytes(_dump(manifest).encode("utf-8"))
    _LOGGER.info("wrote %s: %d texture record(s)", MANIFEST_NAME, len(oven.textures))
    provenance = {
        "cooked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_seconds": round(time.time() - started, 2),
        "machine": platform.node(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "git_hash": _git_hash(),
        "encoder_version": encoder.version if encoder else None,
    }
    (out_dir / PROVENANCE_NAME).write_bytes(_dump(provenance).encode("utf-8"))
    _LOGGER.info("wrote %s", PROVENANCE_NAME)
    _LOGGER.info(
        "%s: %d texture(s) written under %s in %.2f s (%d sidecar field(s) derived; %s)",
        set_dir.name,
        len(oven.textures),
        COOKED_DIR,
        provenance["wall_seconds"],
        len(derived),
        manifest["compression"]["encoder"] or "uncompressed",
    )
    return CookResult(manifest=manifest, written=oven.written + [out_dir / MANIFEST_NAME, out_dir / PROVENANCE_NAME])


def _normal_levels(xy_unit: NDArray[np.float32]) -> list[NDArray[np.float32]]:
    """The two-channel runtime chain of an encoded X, Y image: Z reconstructed, mips renormalised."""
    return [normals.to_rg(normals.encode(lvl)) for lvl in mips.normal_chain(normals.reconstruct_z(xy_unit))]


def separate_set(
    set_dir: Path,
    radius: float = 16.0,
    macro_size: int = 64,
    source_suffix: str = "_BC",
    encoder: Encoder | None = None,
    compress: bool | None = None,
    picture_dir: Path | None = None,
    picture_size: int = 512,
) -> dict[str, Any]:
    """
    The owner's frequency separation on one map of the set: writes ``T_<base>_DH.dds`` (the high-pass) and
    ``T_<base>_<SUFFIX>_macro.dds`` (the low-pass at ``macro_size``), and for ``_N`` the detail normal ``_DN`` and
    the macro normal; the manifest's ``separation`` block carries the measured error under the source's suffix
    (a ``_BC`` and an ``_N`` separation coexist). With ``picture_dir`` the
    source, the halves and the recombination are written as PNGs there, halved until the longer side is at most
    ``picture_size`` (the gallery's rule: at most 1024 on a side and 1 MiB; never under content).
    """
    set_dir = Path(set_dir).resolve()
    sources = read_sources(set_dir)
    src = _single(sources, source_suffix, None)
    if src is None:
        raise CookError(f"{set_dir.name}: no {source_suffix} map to separate")
    if compress is not False and encoder is None:
        encoder = default_encoder()
    if compress is False:
        encoder = None
    out_dir = set_dir / COOKED_DIR
    out_dir.mkdir(exist_ok=True)
    unit = _rgb(src)
    if source_suffix == "_N":
        xyz = normals.to_opengl(normals.decode(unit), src.sidecar["normal_convention"])
        result = sep.separate(normals.encode(xyz)[..., :2], radius)  # X and Y about their neutral 0.5
        high_path = out_dir / f"T_{src.base}_DN.dds"
        high_rec = _write(high_path, _normal_levels(result.high), "R8G8_UNORM", "bc5", encoder, False, "basic")
        macro_levels = _normal_levels(sep.macro(result.low, macro_size))
        macro_path = out_dir / f"T_{src.base}_N_macro.dds"
        macro_rec = _write(macro_path, macro_levels, "R8G8_UNORM", "bc5", encoder, False, "basic")
    else:
        result = sep.separate(unit, radius)
        high_path = out_dir / f"T_{src.base}_DH.dds"
        high_levels = _with_alpha(mips.data_chain(result.high), None)
        high_rec = _write(high_path, high_levels, "R8G8B8A8_UNORM", "bc7", encoder, False, "basic")
        macro_levels = _with_alpha(mips.colour_chain(sep.macro(result.low, macro_size)), None)
        macro_path = out_dir / f"T_{src.base}{source_suffix}_macro.dds"
        macro_rec = _write(macro_path, macro_levels, "R8G8B8A8_UNORM_SRGB", "bc7", encoder, False, "basic")
    separation = {
        "source": src.path.name,
        "radius": result.radius,
        "sigma": result.sigma,
        "macro": macro_size,
        "macro_size": [int(macro_levels[0].shape[1]), int(macro_levels[0].shape[0])],
        "error_max": round(result.error_max, 6),
        "error_mean": round(result.error_mean, 8),
        "clipped_texels": result.clipped_texels,
        "blend": "linear light: saturate(low + 2 * high - 1), in the stored encoding; the macro is box-downsampled "
        "in that encoding, its own mips then follow the map's rule",
        "outputs": {
            high_path.name: {**high_rec, "sha256": sha256_file(high_path)},
            macro_path.name: {**macro_rec, "sha256": sha256_file(macro_path)},
        },
    }
    manifest_path = out_dir / MANIFEST_NAME
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {"set": set_dir.name}
    )
    block = manifest.get("separation")
    earlier = block if isinstance(block, dict) and "source" not in block else {}
    manifest["separation"] = {**earlier, source_suffix: separation}
    manifest_path.write_bytes(_dump(manifest).encode("utf-8"))
    _LOGGER.info("wrote %s: the %s separation record", manifest_path.name, source_suffix)
    if picture_dir is not None:
        picture_dir = Path(picture_dir)
        picture_dir.mkdir(parents=True, exist_ok=True)
        for name, arr in (("source", unit), ("low", result.low), ("high", result.high), ("recombined", result.recon)):
            img = arr if arr.shape[-1] == 3 else np.concatenate([arr, np.ones(arr.shape[:2] + (1,), np.float32)], -1)
            path = picture_dir / f"{name}.png"
            png.write_png(path, colour.to_uint8(sep.macro(img[..., :3], picture_size)))
            _LOGGER.info("wrote %s", path)
    _LOGGER.info(
        "%s: separated %s with sigma %.2f (radius %g): error max %.5f mean %.7f over %d clipped texel(s); macro %dx%d",
        set_dir.name,
        src.path.name,
        result.sigma,
        result.radius,
        result.error_max,
        result.error_mean,
        result.clipped_texels,
        separation["macro_size"][0],
        separation["macro_size"][1],
    )
    return separation
