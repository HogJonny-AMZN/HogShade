"""
HogShade: the cook itself: one authoring set in, its runtime set out, with the manifest and the provenance.
Package: hogshade/texture_cook/cook

``cook_set`` reads every source texture of a set (T1's rules applied first; a set with a finding is refused),
builds each one's mip chain in the right space, flips a DirectX normal, packs ``_ORM`` and any alpha carrier the
sidecars declare, writes DDS (block-compressed through the encoder seam when one is present, uncompressed
otherwise), fills the sidecars' derived fields, and writes ``manifest.json`` (deterministic) and
``provenance.json`` (volatile) under ``<set>/cooked/``. ``separate_set`` is the owner's frequency separation.
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
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

COOKED_DIR = "cooked"
TO_TYPE_NOTE = "hogshade-standard suffixes (Docs/standards/content.md)"


class CookError(ValueError):
    """A set the cook refuses, with the findings in the message."""


@dataclass
class Source:
    path: Path
    base: str
    suffix: str
    variant: str | None
    sidecar_path: Path
    sidecar: dict[str, Any]
    samples: NDArray  # as read: uint8/uint16 (H, W, C) or float16/float32 (H, W) for an EXR height

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass
class CookResult:
    manifest: dict[str, Any] = field(default_factory=dict)
    written: list[Path] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


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


def read_sources(set_dir: Path) -> list[Source]:
    """
    Every source texture of a set, read and checked against T1's rules; ``CookError`` listing every finding when
    one exists (a misnamed, unsourced or contradictory texture is never cooked). A ``.tif`` is a finding naming
    the T2 limit.
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
        if p.suffix == ".exr":
            if name.suffix != "_H":
                problems.append(f"{p.name}: an EXR source is a height map (_H) in T2")
                continue
            samples, _precision = height_mod.read_exr_channel(p)
        else:
            try:
                samples = png.read_png(p)
            except png.PngError as e:
                problems.append(str(e))
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
    if problems:
        raise CookError(f"{set_dir.name} has findings: " + "; ".join(problems))
    if not sources:
        raise CookError(f"{set_dir.name}: no source texture to cook")
    return sources


def _unit(s: Source) -> NDArray[np.float32]:
    return colour.to_unit(s.samples if s.samples.ndim == 3 else s.samples[..., None])


def _single(sources: list[Source], suffix: str, variant: str | None) -> Source | None:
    for s in sources:
        if s.suffix == suffix and s.variant == variant:
            return s
    return None


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
        name = {
            "bc7": "BC7_UNORM_SRGB" if uncompressed.endswith("_SRGB") else "BC7_UNORM",
            "bc5": "BC5_UNORM",
            "bc4": "BC4_UNORM",
        }[block]
        dds2d.write_2d_blocks(out_path, block_mips, levels_unit[0].shape[1], levels_unit[0].shape[0], name)
        record = {"format": name, "encoder": encoder.name}
        if block == "bc7":
            record["bc7_profile"] = f"alpha_{profile}" if alpha else profile
        return record
    dds2d.write_2d(out_path, [colour.to_uint8(lvl) for lvl in levels_unit], uncompressed)
    return {"format": uncompressed, "encoder": None}


def _fill_sidecar(s: Source, derived: list[str]) -> None:
    """The derived fields the cook has authority over, filled when absent and listed; authored fields untouched."""
    data = dict(s.sidecar)
    preset = preset_for(s.suffix)
    fills = {
        "preset": preset["preset"],
        "colour_space": preset["colour_space"],
        "mips": preset["mips"],
        "runtime": preset["runtime"],  # the preset's token; the manifest carries the exact format written
        "resolution": int(max(s.samples.shape[:2])),
    }
    filled = []
    for key in SIDECAR_DERIVED:
        if key not in data:
            data[key] = fills[key]
            filled.append(key)
    if filled:
        data["derived"] = sorted(set(data.get("derived", [])) | set(filled))
        s.sidecar_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        s.sidecar = data
    # the manifest lists every derived field the sidecar carries, whether this cook filled it or an earlier one
    # did, so cooking twice gives one manifest
    derived.extend(f"{s.sidecar_path.name}:{k}" for k in data.get("derived", []))


def cook_set(
    set_dir: Path,
    compress: bool | None = None,
    encoder: Encoder | None = None,
    bc7_profile: str = "basic",
    height_normalise: bool = False,
) -> CookResult:
    """
    Cook one set. ``compress`` None means "when an encoder is present"; True requires one (``CookError`` with the
    install hint otherwise); False writes uncompressed. Returns the manifest and the files written.
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
    textures: dict[str, Any] = {}
    written: list[Path] = []
    derived: list[str] = []
    for s in sources:  # every source's sidecar, the packed ones included, before the inputs are hashed
        _fill_sidecar(s, derived)
    inputs = {s.path.name: sha256_file(s.path) for s in sources}
    inputs.update({s.sidecar_path.name: sha256_file(s.sidecar_path) for s in sources})
    inputs["LICENSE.md"] = sha256_file(set_dir / "LICENSE.md")
    consumed: set[str] = set()  # sources packed into another map, not written on their own

    # alpha carriers first, so the packed sources are known
    carriers: dict[str, Source] = {}
    for s in sources:
        if "pack" in s.sidecar:
            packed = _single(sources, s.sidecar["pack"]["a"], s.variant)
            if packed is not None:
                carriers[s.stem] = packed
                consumed.add(packed.stem)

    def alpha_of(s: Source, levels_rgb: list[NDArray[np.float32]]) -> tuple[list[NDArray[np.float32]], str | None]:
        packed = carriers.get(s.stem)
        if packed is None:
            return [
                np.concatenate([lvl, np.ones(lvl.shape[:2] + (1,), np.float32)], axis=-1) for lvl in levels_rgb
            ], None
        a_levels = mips.data_chain(_unit(packed))
        return [np.concatenate([lvl, a[..., :1]], axis=-1) for lvl, a in zip(levels_rgb, a_levels)], packed.path.name

    for s in sources:
        if s.stem in consumed or s.suffix in pack.ORM_SOURCES:
            continue  # packed into a carrier's alpha, or into _ORM: the runtime form, no file of its own
        spec = SUFFIXES[s.suffix]
        out_path = out_dir / f"{s.stem}.dds"
        entry: dict[str, Any] = {
            "from": s.path.name,
            "preset": spec.parameter,
            "size": [int(s.samples.shape[1]), int(s.samples.shape[0])],
        }
        if s.suffix in ("_BC", "_E"):
            unit = _unit(s)[..., :3]
            levels, packed_name = alpha_of(s, mips.colour_chain(unit))
            entry.update(
                _write(out_path, levels, "R8G8B8A8_UNORM_SRGB", "bc7", encoder, packed_name is not None, bc7_profile)
            )
            if packed_name:
                entry["packed"] = {"A": packed_name}
        elif s.suffix == "_SC":
            unit = _unit(s)[..., :3]
            levels, packed_name = alpha_of(s, mips.data_chain(unit))
            entry.update(
                _write(out_path, levels, "R8G8B8A8_UNORM", "bc7", encoder, packed_name is not None, bc7_profile)
            )
            if packed_name:
                entry["packed"] = {"A": packed_name}
        elif s.suffix == "_N":
            convention = s.sidecar["normal_convention"]
            xyz = normals.to_opengl(normals.decode(_unit(s)), convention)
            levels = [normals.to_rg(normals.encode(lvl)) for lvl in mips.normal_chain(xyz)]
            entry.update(_write(out_path, levels, "R8G8_UNORM", "bc5", encoder, False, bc7_profile))
            entry["normal_convention_in"] = convention
            entry["flipped_y"] = convention == "directx-y"
        elif s.suffix == "_H":
            h = height_mod.from_array(s.samples)
            if height_normalise:
                h, rng = height_mod.normalise(h)
                if rng:
                    entry["normalised"] = rng
            levels = height_mod.chain(h)
            if h.runtime == "R8_UNORM" and encoder is not None:
                block_mips = [encoder.encode(lvl[..., None], "bc4") for lvl in levels]
                dds2d.write_2d_blocks(out_path, block_mips, levels[0].shape[1], levels[0].shape[0], "BC4_UNORM")
                entry.update({"format": "BC4_UNORM", "encoder": encoder.name})
            else:
                dds2d.write_2d(out_path, [lvl[..., None] for lvl in levels], h.runtime)
                entry.update({"format": h.runtime, "encoder": None})
            entry["precision"] = h.precision
        else:  # one channel, its own R8 map
            levels = [lvl[..., :1] for lvl in mips.data_chain(_unit(s)[..., :1])]
            entry.update(_write(out_path, levels, "R8_UNORM", "bc4", encoder, False, bc7_profile))
        entry["mips"] = len(levels)
        entry["sha256"] = sha256_file(out_path)
        textures[out_path.name] = entry
        written.append(out_path)

    # the fixed packing: _ORM from _AO, _R, _M (any present), per variant
    variants = sorted({s.variant for s in sources if s.suffix in pack.ORM_SOURCES}, key=lambda v: v or "")
    for variant in variants:
        parts = {suf: _single(sources, suf, variant) for suf in pack.ORM_SOURCES}
        shape_src = next(s for s in parts.values() if s is not None)
        h, w = shape_src.samples.shape[:2]
        try:
            packed, record = pack.pack_orm(
                _unit(parts["_AO"]) if parts["_AO"] else None,
                _unit(parts["_R"]) if parts["_R"] else None,
                _unit(parts["_M"]) if parts["_M"] else None,
                (h, w),
            )
        except ValueError as e:
            raise CookError(f"{set_dir.name}: {e}") from e
        base = shape_src.base
        stem = f"T_{base}_ORM" + (f"_{variant}" if variant else "")
        levels = mips.data_chain(packed)
        packed_name = None
        # an _ORM alpha carrier is declared on any of its sources' sidecars as {"pack": {"a": "_H"}}; the first found
        for suf in pack.ORM_SOURCES:
            src = parts[suf]
            if src is not None and "pack" in src.sidecar and src.sidecar["pack"]["a"] != suf:
                extra = _single(sources, src.sidecar["pack"]["a"], variant)
                if extra is not None:
                    a_levels = mips.data_chain(_unit(extra))
                    levels = [pack.put_alpha(lvl, a[..., 0]) for lvl, a in zip(levels, a_levels)]
                    packed_name = extra.path.name
                    consumed.add(extra.stem)
                    break
        out_path = out_dir / f"{stem}.dds"
        entry = {"from": [p.path.name for p in parts.values() if p is not None], "preset": "orm", "size": [w, h]}
        entry.update(_write(out_path, levels, "R8G8B8A8_UNORM", "bc7", encoder, packed_name is not None, bc7_profile))
        rec = dict(record)
        if packed_name:
            rec["A"] = packed_name
        entry["packed"] = rec
        entry["mips"] = len(levels)
        entry["sha256"] = sha256_file(out_path)
        textures[out_path.name] = entry
        written.append(out_path)

    manifest = {
        "tool": _MODULE_NAME,
        "tool_version": __version__,
        "hogshade_version": HOGSHADE_VERSION,
        "set": set_dir.name,
        "suffix_table": TO_TYPE_NOTE,
        "inputs": dict(sorted(inputs.items())),
        "textures": dict(sorted(textures.items())),
        "compression": {"encoder": encoder.name if encoder else None, "bc7_profile": bc7_profile if encoder else None},
        "sidecars_derived": sorted(derived),
        "not_power_of_two": sorted(s.path.name for s in sources if any((d & (d - 1)) for d in s.samples.shape[:2])),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _LOGGER.info(
        "%s: %d texture(s) written under %s in %.2f s (%d sidecar field(s) derived; %s)",
        set_dir.name,
        len(textures),
        COOKED_DIR,
        provenance["wall_seconds"],
        len(derived),
        manifest["compression"]["encoder"] or "uncompressed",
    )
    return CookResult(manifest=manifest, written=written + [out_dir / "manifest.json", out_dir / "provenance.json"])


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
    the macro normal; the manifest's ``separation`` block carries the measured error. With ``picture_dir`` the
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
    unit = _unit(src)[..., :3]
    if source_suffix == "_N":
        xyz = normals.to_opengl(normals.decode(unit), src.sidecar["normal_convention"])
        enc = normals.encode(xyz)
        result = sep.separate(enc[..., :2], radius)  # X and Y about their neutral 0.5
        detail = np.concatenate([result.high, np.ones(result.high.shape[:2] + (1,), np.float32)], axis=-1)
        high_levels = [normals.to_rg(lvl) for lvl in mips.data_chain(detail)]
        high_path = out_dir / f"T_{src.base}_DN.dds"
        high_rec = _write(high_path, high_levels, "R8G8_UNORM", "bc5", encoder, False, "basic")
        macro_low = sep.macro(result.low, macro_size)
        macro_levels = [
            normals.to_rg(lvl)
            for lvl in mips.data_chain(
                np.concatenate([macro_low, np.ones(macro_low.shape[:2] + (1,), np.float32)], axis=-1)
            )
        ]
        macro_path = out_dir / f"T_{src.base}_N_macro.dds"
        macro_rec = _write(macro_path, macro_levels, "R8G8_UNORM", "bc5", encoder, False, "basic")
    else:
        result = sep.separate(unit, radius)
        high_rgba = [
            np.concatenate([lvl, np.ones(lvl.shape[:2] + (1,), np.float32)], axis=-1)
            for lvl in mips.data_chain(result.high)
        ]
        high_path = out_dir / f"T_{src.base}_DH.dds"
        high_rec = _write(high_path, high_rgba, "R8G8B8A8_UNORM", "bc7", encoder, False, "basic")
        macro_rgb = sep.macro(result.low, macro_size)
        macro_levels = [
            np.concatenate([lvl, np.ones(lvl.shape[:2] + (1,), np.float32)], axis=-1)
            for lvl in mips.colour_chain(macro_rgb)
        ]
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
        "blend": "linear light: saturate(low + 2 * high - 1), in the stored encoding",
        "outputs": {
            high_path.name: {**high_rec, "sha256": sha256_file(high_path)},
            macro_path.name: {**macro_rec, "sha256": sha256_file(macro_path)},
        },
    }
    manifest_path = out_dir / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {"set": set_dir.name}
    )
    manifest["separation"] = separation
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if picture_dir is not None:
        picture_dir = Path(picture_dir)
        picture_dir.mkdir(parents=True, exist_ok=True)
        for name, arr in (("source", unit), ("low", result.low), ("high", result.high), ("recombined", result.recon)):
            img = (
                arr
                if arr.shape[-1] == 3
                else np.concatenate([arr, np.full(arr.shape[:2] + (3 - arr.shape[-1],), 1.0, np.float32)], axis=-1)[
                    ..., :3
                ]
            )
            png.write_png(picture_dir / f"{name}.png", colour.to_uint8(sep.macro(img, picture_size)))
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
