"""
HogShade: the content check: every texture under content/ and every texture a material document binds obeys
the content standard (Docs/standards/content.md), before a cook or a host sees it.
Package: tools/check_content

    uv run tools/check_content.py             # CI step "Content": exit 1 with the findings listed

Checks (the T1 spec):

- **content-table**: the suffix table in ``hogshade.material.textures`` covers the schema's texturable
  parameters exactly, with the schema's colour spaces
- **content-name**: every source image under ``content/textures/`` is ``T_<snake_case>_<SUFFIX>[_<variant>]``
  with a known suffix; a file under a ``cooked/`` directory is DDS
- **content-sidecar**: every source texture has ``<stem>.texture.json`` beside it, well formed, with its
  provenance, its normal convention when it is a normal map, and no derived field contradicting the suffix
  without a reason; a stated resolution matches the PNG header when the file is a PNG
- **content-binding**: every texture a document under ``content/materials/`` binds names a file whose suffix
  maps to the bound parameter, and whose sidecar's colour space is the schema's for that parameter
- **content-licence**: every set directory under ``content/textures/`` carries a ``LICENSE.md``
"""

from __future__ import annotations

import argparse
import json
import logging as _logging
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hogshade.material import MaterialError, load, type_of
from hogshade.material.library import documents_under
from hogshade.material.textures import (
    AUTHORING_FORMATS,
    RUNTIME_CONTAINER,
    check_sidecar,
    check_suffixes,
    parameter_of,
    parse_name,
)

_MODULE_NAME = "tools.check_content"
__version__ = "0.1.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

TEXTURES = "content/textures"
MATERIALS = "content/materials"
SIDECAR_SUFFIX = ".texture.json"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class Finding:
    check: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.check}: {self.where}: {self.message}"


def png_size(path: Path) -> tuple[int, int] | None:
    """Width and height from the PNG header, or ``None`` when the file is not a PNG."""
    with path.open("rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or not head.startswith(_PNG_MAGIC) or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def source_textures(root: Path) -> list[Path]:
    """Every authoring-format image under the textures directory, outside any ``cooked/``."""
    base = root / TEXTURES
    if not base.is_dir():
        return []
    return sorted(
        p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in AUTHORING_FORMATS and "cooked" not in p.parts
    )


def check_table() -> list[Finding]:
    return [
        Finding("content-table", f.path, f"{f.parameter}: {f.message}" if f.parameter else f.message)
        for f in check_suffixes()
    ]


def check_names(root: Path) -> list[Finding]:
    out: list[Finding] = []
    base = root / TEXTURES
    for path in source_textures(root):
        name = parse_name(path.stem)
        if name is None:
            out.append(Finding("content-name", _rel(path, root), "not T_<snake_case>_<SUFFIX>[_<variant>]"))
        elif not name.known:
            out.append(Finding("content-name", _rel(path, root), f"suffix {name.suffix!r} is not in the tables"))
    if base.is_dir():
        for path in sorted(p for p in base.rglob("*") if p.is_file() and "cooked" in p.parts):
            if path.suffix.lower() != f".{RUNTIME_CONTAINER}" and path.name not in ("manifest.json", "provenance.json"):
                out.append(
                    Finding("content-name", _rel(path, root), f"a cooked file is {RUNTIME_CONTAINER}, or the manifest")
                )
    return out


def _read_sidecar(path: Path, root: Path) -> tuple[dict | None, list[Finding]]:
    sidecar = path.with_name(path.stem + SIDECAR_SUFFIX)
    where = _rel(sidecar, root)
    if not sidecar.is_file():
        return None, [Finding("content-sidecar", _rel(path, root), f"no sidecar {sidecar.name} beside it")]
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, [Finding("content-sidecar", where, f"not JSON ({e.msg} at line {e.lineno})")]
    return data, []


def check_sidecars(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in source_textures(root):
        name = parse_name(path.stem)
        if name is None or not name.known:
            continue  # content-name reports it
        data, problems = _read_sidecar(path, root)
        out.extend(problems)
        if data is None:
            continue
        where = _rel(path.with_name(path.stem + SIDECAR_SUFFIX), root)
        out.extend(
            Finding("content-sidecar", where, f"{f.parameter}: {f.message}" if f.parameter else f.message)
            for f in check_sidecar(data, name.suffix, where)
        )
        if isinstance(data.get("resolution"), int) and path.suffix.lower() == ".png":
            size = png_size(path)
            if size is not None and max(size) != data["resolution"]:
                out.append(
                    Finding(
                        "content-sidecar", where, f"resolution {data['resolution']} but the PNG is {size[0]}x{size[1]}"
                    )
                )
    return out


def check_bindings(root: Path) -> list[Finding]:
    out: list[Finding] = []
    base = root / MATERIALS
    if not base.is_dir():
        return []
    try:
        paths = documents_under(base)
    except MaterialError as e:
        return [Finding("content-binding", MATERIALS, str(e))]
    for doc_path in paths:
        try:
            doc = load(doc_path, base)
        except MaterialError as e:
            out.append(Finding("content-binding", _rel(doc_path, root), str(e)))
            continue
        mtype = type_of(doc.material_type)
        for pname, value in doc.values.items():
            if not isinstance(value, dict) or value.get("texture") is None:
                continue
            where = f"{_rel(doc_path, root)}:{pname}"
            texture = doc_path.parent / Path(*value["texture"].split("/"))
            name = parse_name(texture.stem)
            if name is None or not name.known:
                out.append(
                    Finding("content-binding", where, f"binds {value['texture']!r}, not a texture of this repository")
                )
                continue
            bound = parameter_of(name.suffix)
            if bound is None:
                out.append(
                    Finding(
                        "content-binding", where, f"binds a {name.suffix} map, which a document never binds directly"
                    )
                )
                continue
            if bound != pname:
                out.append(
                    Finding("content-binding", where, f"binds a {name.suffix} map, which is {bound!r}, not {pname!r}")
                )
            p = mtype.parameters.get(pname)
            if not texture.is_file():
                out.append(Finding("content-binding", where, f"{value['texture']!r} does not exist"))
                continue
            data, problems = _read_sidecar(texture, root)
            out.extend(Finding("content-binding", f.where, f.message) for f in problems)
            if isinstance(data, dict) and p is not None and data.get("colour_space") not in (None, p.colour_space):
                out.append(
                    Finding(
                        "content-binding",
                        where,
                        f"sidecar colour space {data.get('colour_space')!r} but {pname!r} is {p.colour_space!r} "
                        "in the schema",
                    )
                )
    return out


def check_licences(root: Path) -> list[Finding]:
    out: list[Finding] = []
    sets = {p.parent for p in source_textures(root)}
    for directory in sorted(sets):
        top = directory
        while top.parent != root / TEXTURES and top != root / TEXTURES:
            top = top.parent
        if not (top / "LICENSE.md").is_file():
            out.append(
                Finding(
                    "content-licence",
                    _rel(top, root),
                    "a set carries LICENSE.md (source, licence, fetch date, where the master lives)",
                )
            )
    return out


def run(root: Path = ROOT) -> list[Finding]:
    findings = check_table()
    findings += check_names(root)
    findings += check_sidecars(root)
    findings += check_bindings(root)
    findings += check_licences(root)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT, help="the repository root (default: this one)")
    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = args.root.resolve()
    textures = source_textures(root)
    _LOGGER.info(
        "checking %d source texture(s) under %s and the documents under %s", len(textures), TEXTURES, MATERIALS
    )
    findings = run(root)
    for f in findings:
        _LOGGER.error("%s", f)
    if findings:
        _LOGGER.error("content check: %d finding(s)", len(findings))
        return 1
    _LOGGER.info(
        "content check: the suffix table matches the schema; %d texture(s) and their bindings obey the standard",
        len(textures),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
