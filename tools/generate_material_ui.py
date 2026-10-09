"""
HogShade: regenerate or check what the material schema, the library and the texture conventions generate: the
Maya shell's material block between its markers, the docs reference, the library's index page, and the content
standard's tables between its markers.
Package: tools/generate_material_ui

    uv run tools/generate_material_ui.py --check    # CI: exit 1 with a diff when any output is stale
    uv run tools/generate_material_ui.py --write    # replace the block, the reference, the index and the tables

The generators are hogshade.material.generators (the S2 spec, the T1 content tables) and
hogshade.material.library (the S4a spec); this tool only reads and writes the four files. Everything outside a
file's markers is untouched.
"""

from __future__ import annotations

import argparse
import difflib
import logging as _logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hogshade.material.generators import (
    CONTENT_BEGIN,
    CONTENT_END,
    DOCS_HEADER,
    MAYA_BEGIN,
    MAYA_END,
    between,
    generate,
    replace_between,
)
from hogshade.material.library import INDEX_HEADER, index
from hogshade.material.model import MaterialError

_MODULE_NAME = "tools.generate_material_ui"
__version__ = "0.2.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SHELL = ROOT / "hosts" / "maya_dx11" / "hogshade.fx"
REFERENCE = ROOT / "Docs" / "reference" / "material-types.md"
LIBRARY = ROOT / "content" / "materials" / "standard"
INDEX = ROOT / "content" / "materials" / "README.md"
STANDARD = ROOT / "Docs" / "standards" / "content.md"


def _rel(path: Path) -> str:
    """The repo-relative spelling, or the path itself when it lies elsewhere (a test points the tool at a copy)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _diff(name: str, committed: str, fresh: str) -> str:
    return "".join(
        difflib.unified_diff(
            committed.splitlines(keepends=True),
            fresh.splitlines(keepends=True),
            f"{name} (committed)",
            f"{name} (generated)",
        )
    )


def check() -> list[str]:
    """The stale outputs as diffs; empty when both are current."""
    stale: list[str] = []
    shell = SHELL.read_text(encoding="utf-8")
    block = between(shell, MAYA_BEGIN, MAYA_END, _rel(SHELL))
    fresh = generate("maya_dx11")
    if block != fresh:
        stale.append(_diff(_rel(SHELL), block, fresh))
    reference = REFERENCE.read_text(encoding="utf-8") if REFERENCE.exists() else ""
    fresh_docs = generate("docs")
    if reference != fresh_docs:
        stale.append(_diff(_rel(REFERENCE), reference, fresh_docs))
    committed_index = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    fresh_index = index(LIBRARY)
    if committed_index != fresh_index:
        stale.append(_diff(_rel(INDEX), committed_index, fresh_index))
    standard = STANDARD.read_text(encoding="utf-8")
    tables = between(standard, CONTENT_BEGIN, CONTENT_END, _rel(STANDARD))
    fresh_tables = generate("content")
    if tables != fresh_tables:
        stale.append(_diff(_rel(STANDARD), tables, fresh_tables))
    return stale


def write() -> list[Path]:
    """Replace the block and the reference; the paths written."""
    shell = SHELL.read_text(encoding="utf-8")
    SHELL.write_text(
        replace_between(shell, MAYA_BEGIN, MAYA_END, generate("maya_dx11"), str(SHELL)), encoding="utf-8", newline="\n"
    )
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    docs = generate("docs")
    if not docs.startswith(DOCS_HEADER):
        raise MaterialError("the docs reference does not start with its generated-file header")
    REFERENCE.write_text(docs, encoding="utf-8", newline="\n")
    page = index(LIBRARY)
    if not page.startswith(INDEX_HEADER):
        raise MaterialError("the library index does not start with its generated-file header")
    INDEX.write_text(page, encoding="utf-8", newline="\n")
    standard = STANDARD.read_text(encoding="utf-8")
    STANDARD.write_text(
        replace_between(standard, CONTENT_BEGIN, CONTENT_END, generate("content"), str(STANDARD)),
        encoding="utf-8",
        newline="\n",
    )
    return [SHELL, REFERENCE, INDEX, STANDARD]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="fail when the committed outputs differ from the generators'"
    )
    mode.add_argument("--write", action="store_true", help="regenerate the shell's block, the reference and the index")
    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if args.write:
            for path in write():
                _LOGGER.info(f"wrote {_rel(path)}")
            return 0
        stale = check()
    except MaterialError as e:
        _LOGGER.error(f"material UI: {e}")
        return 2
    if stale:
        for diff in stale:
            sys.stdout.write(diff)
        _LOGGER.error(f"material UI check: {len(stale)} stale output(s); run tools/generate_material_ui.py --write")
        return 1
    _LOGGER.info(
        "material UI check: the Maya block, the docs reference, the library index and the content tables are current"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
