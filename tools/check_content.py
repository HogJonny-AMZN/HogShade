"""
HogShade: the content check: every texture under content/ and every texture a material document binds obeys
the content standard (Docs/standards/content.md), before a cook or a host sees it.
Package: tools/check_content

    uv run tools/check_content.py             # CI step "Content": exit 1 with the findings listed

Checks (the T1 spec):

- **content-table**: the suffix table in ``hogshade.material.textures`` covers the schema's texturable
  parameters exactly, with the schema's colour spaces
- **content-name**: every file under the content roots (``content/materials/``, ``content/textures/``) that is
  not a record (a sidecar, a document, a README, a licence) is an authoring format with a lower-case extension,
  named ``T_<snake_case>_<SUFFIX>[_<variant>]`` with a parameter suffix (a packed or derived suffix is the
  cook's and lives under ``cooked/``); a file under ``cooked/`` is DDS, the manifest or the provenance record
- **content-sidecar**: every source texture has ``<stem>.texture.json`` beside it, well formed, with its
  provenance, its normal convention when it is an authored normal map, and no derived field contradicting the
  suffix without a reason; a stated resolution matches the PNG header when the PNG is present (an LFS pointer
  is logged as unverified, which is CI's checkout); a PNG wider than the 2K budget is a finding
- **content-binding**: every texture a ``hogshade-standard`` document under ``content/materials/`` binds names
  a file in an authoring format whose suffix maps to the bound parameter and whose sidecar's colour space is
  the schema's; a document of another type is logged and not held to the standard's table
- **content-licence**: every directory holding source textures carries a ``LICENSE.md``
- **content-runtime** (T3): every committed set with a ``cooked/`` directory, under either root, has a readable
  ``cooked/manifest.json`` whose records account for every source map of the set (its own entry, an ``_ORM``
  channel or a carrier's alpha), and whose input hashes match the authoring files when the LFS payloads are
  present (a pointer is logged as unverified, like the sidecar's resolution)

A texture a document binds lives beside or below the document (S1 refuses ``..`` in a texture path), so a
set is a sub-directory of the material family that owns it; ``content/textures/`` is for sets no document
binds yet, such as calibration tiles.
"""

from __future__ import annotations

import argparse
import hashlib
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
from hogshade.material.runtime import COOKED_DIR, MANIFEST_NAME, CookedSetError, locate, manifest_for
from hogshade.material.textures import (
    AUTHORING_FORMATS,
    MAX_RESOLUTION,
    NON_TEXTURE_SUFFIXES,
    PACKED,
    RUNTIME_CONTAINER,
    SIDECAR_SUFFIX,
    STANDARD,
    SUFFIXES,
    check_sidecar,
    check_suffixes,
    parameter_of,
    parse_name,
)

_MODULE_NAME = "tools.check_content"
__version__ = "0.3.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: Where textures live: beside the material that binds them, or in a set no document binds yet.
CONTENT_ROOTS = ("content/materials", "content/textures")
MATERIALS = "content/materials"
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


def _is_record(path: Path) -> bool:
    """A file beside textures that is not a texture: a sidecar, a material document, a README or a licence."""
    return path.name.endswith(NON_TEXTURE_SUFFIXES)


def image_files(root: Path) -> list[Path]:
    """
    Every texture candidate under the content roots, outside any ``cooked/`` directory: every file that is not a
    record, whatever its extension, so an unsupported format cannot slip past the checks by being unlisted.
    """
    out: list[Path] = []
    for rel in CONTENT_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        out += [p for p in base.rglob("*") if p.is_file() and not _is_record(p) and not _is_cooked(p, base)]
    return sorted(out)


def _is_source(path: Path) -> bool:
    """An authoring-format file (lower-case extension), named to the grammar, with a parameter suffix (not packed)."""
    name = parse_name(path.stem)
    return path.suffix in AUTHORING_FORMATS and name is not None and name.suffix in SUFFIXES


def source_textures(root: Path) -> list[Path]:
    """The candidates that are source textures: authoring format, the grammar, a parameter suffix."""
    return [p for p in image_files(root) if _is_source(p)]


def check_table() -> list[Finding]:
    return [
        Finding("content-table", f.path, f"{f.parameter}: {f.message}" if f.parameter else f.message)
        for f in check_suffixes()
    ]


def check_names(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in image_files(root):
        where = _rel(path, root)
        if path.suffix not in AUTHORING_FORMATS:
            if path.suffix.lower() in AUTHORING_FORMATS:
                message = f"extension {path.suffix!r} is upper-case; LFS patterns are case-sensitive"
            else:
                message = f"{path.suffix!r} is not an authoring format {AUTHORING_FORMATS}"
            out.append(Finding("content-name", where, message))
        name = parse_name(path.stem)
        if name is None:
            out.append(Finding("content-name", where, "not T_<snake_case>_<SUFFIX>[_<variant>]"))
        elif not name.known:
            out.append(Finding("content-name", where, f"suffix {name.suffix!r} is not in the tables"))
        elif name.suffix in PACKED:
            out.append(
                Finding(
                    "content-name", where, f"{name.suffix} is the cook's output; it lives under cooked/, never authored"
                )
            )
    for rel in CONTENT_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file() and _is_cooked(p, base)):
            if path.suffix.lower() != f".{RUNTIME_CONTAINER}" and path.name not in COOKED_EXTRA:
                out.append(
                    Finding(
                        "content-name",
                        _rel(path, root),
                        f"a cooked file is {RUNTIME_CONTAINER}, or one of {COOKED_EXTRA}",
                    )
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
    except UnicodeDecodeError as e:
        return None, where, [Finding("content-sidecar", where, f"not UTF-8 ({e.reason} at byte {e.start})")]
    except json.JSONDecodeError as e:
        return None, where, [Finding("content-sidecar", where, f"not JSON ({e.msg} at line {e.lineno})")]
    if not isinstance(data, dict):
        return (
            None,
            where,
            [Finding("content-sidecar", where, f"a sidecar is a JSON object, not {type(data).__name__}")],
        )
    return data, where, []


def check_sidecars(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in source_textures(root):
        name = parse_name(path.stem)
        if name is None:  # source_textures parsed it; a guard, not an assertion
            continue
        data, where, problems = _read_sidecar(path, root)
        out.extend(problems)
        if data is None:
            continue
        out.extend(
            Finding("content-sidecar", where, f"{f.parameter}: {f.message}" if f.parameter else f.message)
            for f in check_sidecar(data, name.suffix, where)
        )
        if path.suffix != ".png":
            continue
        size = png_size(path)
        stated = data.get("resolution")
        if size == "lfs":
            _LOGGER.info("resolution of %s unverified: the PNG is an LFS pointer in this checkout", _rel(path, root))
        elif isinstance(size, tuple):
            if max(size) > MAX_RESOLUTION:
                out.append(
                    Finding(
                        "content-sidecar",
                        _rel(path, root),
                        f"{size[0]}x{size[1]} exceeds the repository budget of {MAX_RESOLUTION}",
                    )
                )
            if isinstance(stated, int) and not isinstance(stated, bool) and max(size) != stated:
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
            if texture.suffix not in AUTHORING_FORMATS:
                out.append(Finding("content-binding", where, f"binds {value['texture']!r}, not an authoring format"))
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(40).startswith(b"version https://git-lfs")
    except OSError:
        return False


def check_runtime(root: Path) -> list[Finding]:
    """Every committed set with a ``cooked/`` has a manifest that accounts for its maps and matches its inputs."""
    out: list[Finding] = []
    sets: dict[Path, list[Path]] = {}
    for texture in source_textures(root):
        sets.setdefault(texture.parent, []).append(texture)
    for set_dir, textures in sorted(sets.items()):
        cooked = set_dir / COOKED_DIR
        if not cooked.is_dir():
            continue
        where = _rel(cooked / MANIFEST_NAME, root)
        try:
            manifest = manifest_for(set_dir)
        except CookedSetError as e:
            out.append(Finding("content-runtime", where, str(e)))
            continue
        for texture in sorted(textures):
            try:
                rt = locate(manifest, set_dir, texture.name)
            except CookedSetError as e:
                _LOGGER.debug(f"{where}: {e}")
                out.append(Finding("content-runtime", where, f"no record of {texture.name}; cook the set again"))
                continue
            if not rt.path.is_file():  # an LFS pointer is a file too; a missing output is not
                out.append(Finding("content-runtime", where, f"{rt.path.name} is recorded and not under cooked/"))
        inputs = manifest.get("inputs")
        if not isinstance(inputs, dict):
            out.append(Finding("content-runtime", where, "no inputs record; cook the set again"))
            continue
        expected = {t.name for t in textures} | {f"{t.stem}{SIDECAR_SUFFIX}" for t in textures} | {"LICENSE.md"}
        for missing in sorted(expected - set(inputs)):
            out.append(Finding("content-runtime", where, f"no input hash for {missing}; cook the set again"))
        unverified = 0
        resolved_set = set_dir.resolve()
        for name, digest in sorted(inputs.items()):
            path = (set_dir / name).resolve()
            if path.parent != resolved_set or Path(name).name != name:
                out.append(Finding("content-runtime", where, f"input {name!r} is not a file of the set"))
                continue
            if not path.is_file():
                out.append(Finding("content-runtime", where, f"input {name} is gone"))
                continue
            if _is_lfs_pointer(path):
                unverified += 1
                continue
            if sha256_file(path) != digest:
                out.append(Finding("content-runtime", where, f"{name} changed since the cook; cook the set again"))
        if unverified:
            _LOGGER.info(
                f"{_rel(set_dir, root)}: {unverified} input(s) are LFS pointers on this checkout; "
                "their hashes are unverified"
            )
    return out


def run(root: Path = ROOT) -> list[Finding]:
    findings = check_table()
    findings += check_names(root)
    findings += check_sidecars(root)
    findings += check_bindings(root)
    findings += check_licences(root)
    findings += check_runtime(root)
    return findings


def _summary(root: Path) -> dict[str, Any]:
    return {"candidates": len(image_files(root)), "sources": len(source_textures(root))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT, help="the repository root (default: this one)")
    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = args.root.resolve()
    counts = _summary(root)
    _LOGGER.info(
        "checking %d texture candidate(s), %d of them source textures, under %s, and the documents under %s",
        counts["candidates"],
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
