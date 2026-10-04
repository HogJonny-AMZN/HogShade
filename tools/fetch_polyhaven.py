"""
HogShade: fetch one Poly Haven texture set into an authoring set of this repository (T3).
Package: tools/fetch_polyhaven

    uv run tools/fetch_polyhaven.py <asset_id> <set_dir> [--base <name>] [--res 2k] [--maps Diffuse,nor_gl,...]

Reads Poly Haven's public API (``/files/<id>``, ``/info/<id>``), downloads each wanted map at the resolution
as PNG (md5 checked against the API), and writes the set the content standard describes: ``T_<base>_<SUFFIX>.png``
at the suffix table's bit depth and channel count (a 16-bit colour map becomes 8-bit, a grey-alpha roughness
becomes grey, a height keeps 16 bits), a sidecar per map with its provenance (origin, url, licence, fetched, the
download's url and md5), ``normal_convention: opengl+y`` on the normal (Poly Haven's ``nor_gl``), and a
``LICENSE.md`` on the ``content/ibl`` template. Poly Haven is CC0; nothing else is fetched from here. The cook
runs afterwards (``tools/cook_textures.py cook <set_dir>``). Standard library plus numpy through the cook's PNG
reader; no Pillow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging as _logging
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hogshade.material.textures import MAX_RESOLUTION, PREFIX, SUFFIXES, parse_name
from hogshade.texture_cook import colour, png

_MODULE_NAME = "tools.fetch_polyhaven"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

API = "https://api.polyhaven.com"
PAGE = "https://polyhaven.com/a/{asset}"
LICENCE_URL = "https://polyhaven.com/license"
USER_AGENT = "HogShade-content-fetch/1.0 (+https://github.com/HogJonny-AMZN/HogShade)"
#: Poly Haven's map keys to the standard's suffixes (``nor_gl`` is OpenGL +Y, the repository's convention).
MAP_SUFFIX = {"Diffuse": "_BC", "nor_gl": "_N", "Rough": "_R", "AO": "_AO", "Displacement": "_H", "Metal": "_M"}
DEFAULT_MAPS = tuple(MAP_SUFFIX)
#: The channel count the standard's table expects for each runtime kind.
CHANNELS = {"bc7": 3, "bc5": 3, "bc4": 1}


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as r:
        return r.read()


def api(path: str) -> dict[str, Any]:
    """One Poly Haven API call, parsed."""
    return json.loads(_get(f"{API}/{path}").decode("utf-8"))


def plan(files: dict[str, Any], maps: tuple[str, ...], res: str) -> list[dict[str, Any]]:
    """
    The downloads for the wanted maps at ``res`` as PNG from a ``/files`` answer: a row per map present
    (``key``, ``suffix``, ``url``, ``size``, ``md5``); a wanted map the asset lacks is logged and skipped, a
    wanted map with no PNG at that resolution is an error (the asset exists but not in the form the standard
    takes).
    """
    out = []
    for key in maps:
        if key not in MAP_SUFFIX:
            raise ValueError(f"{key!r} is not a Poly Haven map this tool knows: {sorted(MAP_SUFFIX)}")
        if key not in files:
            _LOGGER.info(f"{key}: the asset has no such map; skipped (its keys: {sorted(k for k in files)})")
            continue
        try:
            f = files[key][res]["png"]
        except KeyError as e:
            raise ValueError(f"{key}: no {res} PNG on Poly Haven (available: {sorted(files[key])})") from e
        if not isinstance(f, dict) or not all(isinstance(f.get(k), (str, int)) for k in ("url", "size", "md5")):
            raise ValueError(f"{key}: the API row lacks url, size or md5: {f!r}")
        if not str(f["url"]).startswith("https://"):
            raise ValueError(f"{key}: the download url is not https: {f['url']!r}")
        out.append({"key": key, "suffix": MAP_SUFFIX[key], "url": f["url"], "size": int(f["size"]), "md5": f["md5"]})
    return out


def normalise(image: NDArray, suffix: str) -> NDArray:
    """
    The downloaded samples in the standard's form for ``suffix``: a colour or normal map as 8-bit RGB (an alpha
    dropped, 16 bits reduced), a single-channel map as 8-bit grey (the first channel; grey-alpha loses its
    alpha), a height as 16-bit grey (an 8-bit source stays 8-bit: nothing is invented). Logged when it changes
    anything.
    """
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = arr[..., None]
    kind = SUFFIXES[suffix].runtime
    want = CHANNELS[kind]
    out = arr
    if want == 3:
        if arr.shape[2] == 1:
            out = np.repeat(arr, 3, axis=-1)
        elif arr.shape[2] == 2:
            out = np.repeat(arr[..., :1], 3, axis=-1)
        else:
            out = arr[..., :3]
    else:
        out = arr[..., :1]
    if suffix != "_H" and out.dtype == np.uint16:
        out = colour.to_uint8(colour.to_unit(out))
    if out.shape != arr.shape or out.dtype != arr.dtype:
        _LOGGER.info(
            f"{suffix}: {arr.shape[2]} channel(s) {arr.dtype.name} from Poly Haven -> {out.shape[2]} channel(s) "
            f"{out.dtype.name} (the content table's form)"
        )
    return np.ascontiguousarray(out)


def licence_text(asset: str, info: dict[str, Any], res: str, fetched: str, rows: list[dict[str, Any]]) -> str:
    authors = ", ".join(f"{name} ({role})" for name, role in sorted((info.get("authors") or {}).items())) or (
        "as credited on the Poly Haven page above"
    )
    names = ", ".join(f"`{PREFIX}{{base}}{r['suffix']}.png` from `{r['key']}`" for r in rows)
    return (
        f"# {asset}\n\n"
        f"- **Source:** {PAGE.format(asset=asset)}\n"
        f"- **Author:** {authors}\n"
        f"- **Licence:** CC0 1.0 Universal (public domain dedication), Poly Haven's licence for all its assets:\n"
        f"  {LICENCE_URL}\n"
        f"- **Fetched:** {fetched}, as the {res} PNG downloads (`tools/fetch_polyhaven.py`; each download's url and\n"
        f"  md5 are in the map's sidecar)\n"
        f"- **Role in HogShade:** an authoring set of the content standard (Docs/standards/content.md), bound by the\n"
        f"  material document beside it; its runtime form is `cooked/`, written by `tools/cook_textures.py`.\n"
        f"- **What is in this folder:** {names}, each brought to the suffix table's bit depth and channels at\n"
        f"  fetch (a 16-bit colour map to 8 bits, a grey-alpha mask to grey; height keeps 16 bits), no other\n"
        f"  change. The {res} download is the master; Poly Haven keeps the higher resolutions.\n"
    )


def fetch(
    asset: str, set_dir: Path, base: str | None = None, res: str = "2k", maps: tuple[str, ...] = DEFAULT_MAPS
) -> list[Path]:
    """Fetch and write one set; returns the files written. Logs every download, conversion and file."""
    base = base or asset
    if parse_name(f"{PREFIX}{base}_BC") is None:
        raise ValueError(f"base {base!r} is not snake_case (T_<base>_<SUFFIX> must parse)")
    set_dir = Path(set_dir)
    files = api(f"files/{asset}")
    info = api(f"info/{asset}")
    rows = plan(files, maps, res)
    if not rows:
        raise ValueError(f"{asset}: none of {maps} present")
    fetched = time.strftime("%Y-%m-%d")
    set_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    _LOGGER.info(f"fetching {asset} at {res} into {set_dir}: {len(rows)} map(s), base {base!r}")
    for r in rows:
        _LOGGER.info(f"  {r['key']} <- {r['url']} ({r['size']} bytes)")
        data = _get(r["url"], timeout=600)
        md5 = hashlib.md5(data).hexdigest()
        if md5 != r["md5"]:
            raise ValueError(f"{r['key']}: md5 {md5} does not match Poly Haven's {r['md5']}; refetch")
        tmp = set_dir / f".{asset}_{r['key']}_{res}.png"
        tmp.write_bytes(data)
        try:
            image = png.read_png(tmp)
        finally:
            tmp.unlink()
        if max(image.shape[:2]) > MAX_RESOLUTION:
            raise ValueError(
                f"{r['key']}: {image.shape[1]}x{image.shape[0]} exceeds the repository budget of {MAX_RESOLUTION}"
            )
        out = normalise(image, r["suffix"])
        name = f"{PREFIX}{base}{r['suffix']}"
        path = set_dir / f"{name}.png"
        png.write_png(path, out, filter_type=4)  # Paeth: the smallest file for photographs
        sidecar: dict[str, Any] = {
            "provenance": {
                "origin": "polyhaven",
                "url": PAGE.format(asset=asset),
                "licence": "CC0-1.0",
                "fetched": fetched,
                "download": r["url"],
                "md5": r["md5"],
            }
        }
        if r["suffix"] == "_N":
            sidecar["normal_convention"] = "opengl+y"
        side = set_dir / f"{name}.texture.json"
        side.write_bytes((json.dumps(sidecar, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        written += [path, side]
        _LOGGER.info(f"  wrote {path.name} ({path.stat().st_size} bytes) and {side.name}")
    lic = set_dir / "LICENSE.md"
    lic.write_bytes(licence_text(asset, info, res, fetched, rows).replace("{base}", base).encode("utf-8"))
    written.append(lic)
    _LOGGER.info(f"  wrote {lic.name}; next: uv run tools/cook_textures.py cook {set_dir}")
    return written


def main(argv: list[str] | None = None) -> int:
    """The command line: one asset into one set directory; 0 on success, 2 on a refusal."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("asset", help="the Poly Haven asset id, e.g. brick_wall_001")
    parser.add_argument(
        "set_dir", type=Path, help="the set directory to write, e.g. content/materials/standard/rough/brick_wall_001"
    )
    parser.add_argument("--base", default=None, help="the T_<base> name (default: the asset id)")
    parser.add_argument("--res", default="2k", help="the Poly Haven resolution key (default 2k, the LFS budget)")
    parser.add_argument("--maps", default=",".join(DEFAULT_MAPS), help="comma-separated Poly Haven map keys")
    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        written = fetch(args.asset, args.set_dir, args.base, args.res, tuple(m for m in args.maps.split(",") if m))
    except (ValueError, OSError, png.PngError) as e:
        _LOGGER.error(f"fetch of {args.asset} failed: {type(e).__name__}: {e}")
        return 2
    print(json.dumps([str(p) for p in written], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
