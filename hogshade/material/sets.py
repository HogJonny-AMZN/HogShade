"""
HogShade: a material document for a texture set that no document binds yet (T3).
Package: hogshade/material/sets

``document_for_set`` reads a set directory (the calibration tile under ``content/textures/<set>/``, or a set
cooked outside the repository) and returns an in-memory ``hogshade-standard`` document binding every map the
set has, through the suffix table: ``T_<base>_BC.png`` to ``base_color``, ``_N`` to ``geometry_normal`` and so
on, a multiplying parameter's factor set to 1.0 so the map is seen as authored. The Maya texture check renders
such a document for a set without one; nothing is written. Standard library only.
"""

from __future__ import annotations

import logging as _logging
from pathlib import Path

from hogshade.material.model import Document, MaterialError
from hogshade.material.schema import type_of
from hogshade.material.textures import AUTHORING_FORMATS, PACKED, STANDARD, parameter_of, parse_name

_MODULE_NAME = "hogshade.material.sets"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: Standard parameters whose host multiplies the factor by the sample: a bound map needs the factor at 1.0.
MULTIPLIED = {"base_metalness": 1.0, "specular_roughness": 1.0, "base_color": [1.0, 1.0, 1.0]}


def set_maps(set_dir: Path, variant: str | None = None) -> dict[str, Path]:
    """
    The set's authoring maps for one variant (``None`` is the unvarianted maps), keyed by the standard
    parameter each binds; a map whose suffix is packed or derived, or a second source for one parameter, is
    ``MaterialError``.
    """
    set_dir = Path(set_dir)
    if not set_dir.is_dir():
        raise MaterialError(f"no such set directory: {set_dir}")
    out: dict[str, Path] = {}
    parameters = type_of(STANDARD).parameters
    for path in sorted(set_dir.iterdir()):
        if not path.is_file() or path.suffix not in AUTHORING_FORMATS:
            continue
        name = parse_name(path.stem)
        if name is None or not name.known or name.variant != variant:
            continue
        if name.suffix in PACKED:
            raise MaterialError(f"{path.name}: a packed or derived map is the cook's output, not a source")
        pname = parameter_of(name.suffix)
        if pname is None or pname not in parameters:
            raise MaterialError(f"{path.name}: suffix {name.suffix} binds {pname!r}, not a standard parameter")
        if pname in out:
            raise MaterialError(f"{path.name} and {out[pname].name}: two sources for {pname}")
        out[pname] = path
    return out


def document_for_set(set_dir: Path, variant: str | None = None, title: str | None = None) -> Document:
    """
    An in-memory standard document binding every map of the set (paths relative to the set directory, as a
    document beside the set would spell them with ``<set>/`` prefixed: here the document's directory is the
    set itself, so the path is the file name). ``MaterialError`` for a directory with no map.
    """
    set_dir = Path(set_dir)
    maps = set_maps(set_dir, variant)
    if not maps:
        raise MaterialError(f"{set_dir}: no authoring map for variant {variant!r}")
    values: dict[str, dict] = {}
    for pname, path in maps.items():
        value: dict = {"texture": path.name}
        if pname in MULTIPLIED:
            value["factor"] = MULTIPLIED[pname]
        values[pname] = value
    doc = Document(
        material_type=STANDARD,
        material_type_version=type_of(STANDARD).version,
        parent=None,
        values=values,
        path=None,
        root=set_dir,
        title=title or f"{set_dir.name} (the set's own maps)",
        doc=f"Built in memory from the maps of {set_dir.name}; nothing on disk binds this set.",
        provenance=[
            {"source": "author", "note": "every value is the set's map; the factors are 1.0 where a host multiplies"}
        ],
    )
    _LOGGER.info(f"document for set {set_dir.name}: {len(values)} map(s) bound ({', '.join(sorted(values))})")
    return doc


if __name__ == "__main__":
    import json
    import sys

    _doc = document_for_set(Path(sys.argv[1]))
    print(json.dumps(_doc.values, indent=2))
