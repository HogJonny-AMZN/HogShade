"""
HogShade: regenerate or check the material UI the schema generates: the Maya shell's material block
between its markers, and the docs reference.
Package: tools/generate_material_ui

    uv run tools/generate_material_ui.py --check    # CI: exit 1 with a diff when either output is stale
    uv run tools/generate_material_ui.py --write    # replace the block and the reference

The generators are hogshade.material.generators (the S2 spec); this tool only reads and writes the two
files. Everything outside the shell's markers is untouched.
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
    DOCS_HEADER,
    MAYA_BEGIN,
    MAYA_END,
    between,
    generate,
    replace_between,
)
from hogshade.material.model import MaterialError

_MODULE_NAME = "tools.generate_material_ui"
__version__ = "0.1.0"
__updated__ = "2026-10-01"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SHELL = ROOT / "hosts" / "maya_dx11" / "hogshade.fx"
REFERENCE = ROOT / "Docs" / "reference" / "material-types.md"


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
    return [SHELL, REFERENCE]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="fail when the committed outputs differ from the generators'"
    )
    mode.add_argument("--write", action="store_true", help="regenerate the shell's block and the docs reference")
    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if args.write:
            for path in write():
                _LOGGER.info("wrote %s", _rel(path))
            return 0
        stale = check()
    except MaterialError as e:
        _LOGGER.error("material UI: %s", e)
        return 2
    if stale:
        for diff in stale:
            sys.stdout.write(diff)
        _LOGGER.error("material UI check: %d stale output(s); run tools/generate_material_ui.py --write", len(stale))
        return 1
    _LOGGER.info("material UI check: the Maya block and the docs reference are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
