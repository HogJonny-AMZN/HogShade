"""
HogShade: the content check: every texture under content/ and every texture a material document binds obeys
the content standard (Docs/standards/content.md), before a cook or a host sees it.
Package: tools/check_content

    uv run tools/check_content.py             # CI step "Content": exit 1 with the findings listed

Checks (the T1 spec):

- **content-table**: the suffix table in ``hogshade.material.textures`` covers the schema's texturable
  parameters exactly, with the schema's colour spaces
- **content-name**: every image under the content roots (``content/materials/``, ``content/textures/``) is an
  authoring format named ``T_<snake_case>_<SUFFIX>[_<variant>]`` with a known suffix; a file under a
  ``cooked/`` directory is DDS or a manifest
- **content-sidecar**: every source texture has ``<stem>.texture.json`` beside it, well formed, with its
  provenance, its normal convention when it is a normal map, and no derived field contradicting the suffix
  without a reason; a stated resolution matches the PNG header when the PNG is present (an LFS pointer is
  logged as unverified, which is CI's checkout)
- **content-binding**: every texture a ``hogshade-standard`` document under ``content/materials/`` binds names
  a file whose suffix maps to the bound parameter and whose sidecar's colour space is the schema's; a document
  of another type is logged and not held to the standard's table
- **content-licence**: every directory holding source textures carries a ``LICENSE.md``

A texture a document binds lives beside or below the document (S1 refuses ``..`` in a texture path), so a
set is a sub-directory of the material family that owns it; ``content/textures/`` is for sets no document
binds yet, such as calibration tiles.
"""

from __future__ import annotations

import argparse
import json
import logging as _logging
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hogshade.material import MaterialError, load, type_of
from hogshade.material.library import documents_under
from hogshade.material.textures import (
    AUTHORING_FORMATS,
    IMAGE_FORMATS,
    RUNTIME_CONTAINER,
    STANDARD,
    check_sidecar,
    check_suffixes,
    parameter_of,
    parse_name,
)

_MODULE_NAME = "tools.check_content"
__version__ = "0.2.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: Where textures live: beside the material that binds them, or in a set no document binds yet.
CONTENT_ROOTS = ("content/materials", "content/textures")
MATERIALS = "content/materials"
SIDECAR_SUFFIX = ".texture.json"
COOKED_DIR = "cooked"
COOKED_EXTRA = ("manifest.json", "provenance.json")
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_LFS_MAGIC = b"version https://git-lfs"


@dataclass(frozen=True)
class Finding:
    check: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.check}: {self.where}: {self.message}"


def png_size(path: Path) -> tuple[int, int] | str | None:
    """Width and height from the PNG header; ``"lfs"`` for an unhydrated LFS pointer; ``None`` when not a PNG."""
    with path.open("rb") as fh:
        head = fh.read(24)
    if head.startswith(_LFS_MAGIC):
        return "lfs"
    if len(head) < 24 or not head.startswith(_PNG_MAGIC) or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _is_cooked(path: Path, base: Path) -> bool:
    """Under a ``cooked/`` directory, judged on the path relative to the content root, never the absolute one."""
    return COOKED_DIR in path.relative_to(base).parts


def image_files(root: Path) -> list[Path]:
    """Every image file under the content roots, outside any ``cooked/`` directory, in any image format."""
    out: list[Path] = []
    for rel in CONTENT_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        out += [
            p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_FORMATS and not _is_cooked(p, base)
        ]
    return sorted(out)


def source_textures(root: Path) -> list[Path]:
    """The image files that are in an authoring format and named to the grammar with a known suffix."""
    out = []
    for p in image_files(root):
        name = parse_name(p.stem)
        if p.suffix.lower() in AUTHORING_FORMATS and name is not None and name.known:
            out.append(p)
    return out


def check_table() -> list[Finding]:
    return [
        Finding("content-table", f.path, f"{f.parameter}: {f.message}" if f.parameter else f.message)
        for f in check_suffixes()
    ]


def check_names(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in image_files(root):
        where = _rel(path, root)
        if path.suffix.lower() not in AUTHORING_FORMATS:
            out.append(Finding("content-name", where, f"{path.suffix} is not an authoring format {AUTHORING_FORMATS}"))
        name = parse_name(path.stem)
        if name is None:
            out.append(Finding("content-name", where, "not T_<snake_case>_<SUFFIX>[_<variant>]"))
        elif not name.known:
            out.append(Finding("content-name", where, f"suffix {name.suffix!r} is not in the tables"))
    for rel in CONTENT_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file() and _is_cooked(p, base)):
            if path.suffix.lower() != f".{RUNTIME_CONTAINER}" and path.name not in COOKED_EXTRA:
                out.append(
                    Finding("content-name", _rel(path, root), f"a cooked file is {RUNTIME_CONTAINER}, or the manifest")
                )
    return out


def _read_sidecar(path: Path, root: Path) -> tuple[dict | None, str, list[Finding]]:
    """The parsed sidecar beside a texture, its repo-relative name, and the findings of reading it."""
    sidecar = path.with_name(path.stem + SIDECAR_SUFFIX)
    where = _rel(sidecar, root)
    if not sidecar.is_file():
        return None, where, [Finding("content-sidecar", _rel(path, root), f"no sidecar {sidecar.name} beside it")]
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, where, [Finding("content-sidecar", where, f"not JSON ({e.msg} at line {e.lineno})")]
    return data, where, []


def check_sidecars(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in source_textures(root):
        name = parse_name(path.stem)
        assert name is not None  # source_textures parsed it
        data, where, problems = _read_sidecar(path, root)
        out.extend(problems)
        if data is None:
            continue
        out.extend(
            Finding("content-sidecar", where, f"{f.parameter}: {f.message}" if f.parameter else f.message)
            for f in check_sidecar(data, name.suffix, where)
        )
        stated = data.get("resolution")
        if isinstance(stated, int) and not isinstance(stated, bool) and path.suffix.lower() == ".png":
            size = png_size(path)
            if size == "lfs":
                _LOGGER.info(
                    "resolution of %s unverified: the PNG is an LFS pointer in this checkout", _rel(path, root)
                )
            elif isinstance(size, tuple) and max(size) != stated:
                out.append(Finding("content-sidecar", where, f"resolution {stated} but the PNG is {size[0]}x{size[1]}"))
    return out


def _bound_texture(doc_path: Path, value: str) -> Path:
    """The file a document-relative texture string names (S1 confined it to the root when the document loaded)."""
    return doc_path.parent / Path(*value.replace("\\", "/").split("/"))


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
        bound = {n: v for n, v in doc.values.items() if isinstance(v, dict) and v.get("texture") is not None}
        if not bound:
            continue
        if doc.material_type != STANDARD:
            _LOGGER.info(
                "%s is %s, not %s: its %d bound texture(s) are not held to the standard's suffix table",
                _rel(doc_path, root),
                doc.material_type,
                STANDARD,
                len(bound),
            )
            continue
        mtype = type_of(doc.material_type)
        for pname, value in bound.items():
            where = f"{_rel(doc_path, root)}:{pname}"
            texture = _bound_texture(doc_path, value["texture"])
            name = parse_name(texture.stem)
            if name is None or not name.known:
                out.append(
                    Finding("content-binding", where, f"binds {value['texture']!r}, not a texture of this repository")
                )
                continue
            parameter = parameter_of(name.suffix)
            if parameter is None:
                out.append(
                    Finding(
                        "content-binding", where, f"binds a {name.suffix} map, which a document never binds directly"
                    )
                )
                continue
            if parameter != pname:
                out.append(
                    Finding(
                        "content-binding", where, f"binds a {name.suffix} map, which is {parameter!r}, not {pname!r}"
                    )
                )
            if not texture.is_file():
                out.append(Finding("content-binding", where, f"{value['texture']!r} does not exist"))
                continue
            data, _, problems = _read_sidecar(texture, root)
            out.extend(Finding("content-binding", f.where, f.message) for f in problems)
            p = mtype.parameters.get(pname)
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
    for directory in sorted({p.parent for p in source_textures(root)}):
        if not (directory / "LICENSE.md").is_file():
            out.append(
                Finding(
                    "content-licence",
                    _rel(directory, root),
                    "a directory of source textures carries LICENSE.md "
                    "(source, licence, fetch date, where the master lives)",
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


def _summary(root: Path) -> dict[str, Any]:
    return {"images": len(image_files(root)), "sources": len(source_textures(root))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT, help="the repository root (default: this one)")
    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = args.root.resolve()
    counts = _summary(root)
    _LOGGER.info(
        "checking %d image(s), %d of them source textures, under %s, and the documents under %s",
        counts["images"],
        counts["sources"],
        ", ".join(CONTENT_ROOTS),
        MATERIALS,
    )
    findings = run(root)
    for f in findings:
        _LOGGER.error("%s", f)
    if findings:
        _LOGGER.error("content check: %d finding(s)", len(findings))
        return 1
    _LOGGER.info(
        "content check: the suffix table matches the schema; %d source texture(s) and their bindings obey the standard",
        counts["sources"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
