# Python coding standards

**Status:** Accepted (the standards pass, 2026-09-27; ported from LargeWorlds and SpriteJammer, kept to what applies here)
**Last updated:** 2026-09-27
**Read with:** [wgsl.md](wgsl.md) for the core, [definition-of-done.md](definition-of-done.md), [failure-modes.md](failure-modes.md)

Python in this repository is three things, and the rules differ slightly for each:

| Kind | Where | Runs under |
| --- | --- | --- |
| The library | `hogshade/` (reference twins, the wgpu host, the IBL cook, the jobs) | `uv`'s environment, Python 3.11 to 3.13, numpy |
| Repo tools | `tools/*.py`, `tools/wgpu/`, `tools/bats/` | `uv run` |
| DCC-side scripts | `tools/maya/*.py` (and later `tools/blender/`) | the DCC's own Python; no numpy, no `hogshade` import |

`ruff` is the linter and formatter (`pyproject.toml`: 120 columns, `py311` target). CI runs
`ruff check` and `ruff format --check` on `hogshade`, `tests`, `tools` and `Spikes`.

## Module header

Every module starts with a docstring naming the project and the package path, then the metadata,
then the logger. This is the shape the code already has; keep it.

```python
"""
HogShade: one line saying what the module is for.
Package: hogshade/ibl/cook

More detail if the one line is not enough: what it reads, what it writes, what it must not import.
"""

from __future__ import annotations

import logging as _logging
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from hogshade.ibl import dds

_MODULE_NAME = "hogshade.ibl.cook"  # matches the Package line, with dots
__version__ = "0.1.0"
__updated__ = "2026-09-27"
_LOGGER = _logging.getLogger(_MODULE_NAME)
```

- `from __future__ import annotations` in every module: the library targets 3.11 and uses `X | None`
  and `list[...]` in signatures.
- `_LOGGER` from `_MODULE_NAME`, never `__name__`. A module that never logs still declares it (the
  convention is uniform), but a `logging.basicConfig` belongs only in a script's `main`, and only
  when something logs.
- A DCC-side script keeps the same docstring shape and may drop the metadata block; its header says
  which DCC Python it runs under and what it must not import.

## Imports

Absolute only, no wildcards; stdlib, third-party, project, alphabetical within each. ruff's isort
enforces the order. A DCC-side script imports its sibling helper by bare name (`import _session`)
because the launcher puts the folder on `sys.path`; that is the one relative-looking import allowed.

## Types, docstrings, paths

- Complete type hints on every signature. Arrays are `NDArray[np.float32]` (or the dtype in use),
  never bare `NDArray` when the dtype matters to the caller.
- Docstrings say what a function is for and what it returns; reST fields (`:param:`, `:return:`,
  `:raises:`) where a signature is not self-explanatory. A one-line docstring is fine for a helper.
- `pathlib.Path` for every path, DCC scripts included. `str()` only at the boundary of an API that
  needs it, through one helper when the consumer is fussy (`tools/maya/_session.py`'s `maya_path()`
  gives Maya its forward slashes). `os.environ` reads stay `os.environ`; wrap the result in `Path`
  at once.

## Errors and logging

- Catch specific exceptions. A `# noqa: BLE001` broad catch is allowed only where the point of the
  code is to log whatever a DCC throws and keep going, and the comment says so.
- Two-part messages, context then detail: `f"Failed to decode {path}: {e}"`. No emoji or non-ASCII
  in log text (Maya's console is not UTF-8 safe).
- `print()` only in a script's own entry point (`main`) and in DCC scripts, whose stdout is the
  log. Library code logs.

## Structure

- A job (`hogshade/jobs/*.py`) is a thin adapter over code that also runs without the orchestrator;
  it carries a `MANIFEST` dict and a `main(parameters: dict) -> dict`. A job is never the only way
  to run something.
- A tool's logic lives in a function the tests can call; `main(argv)` parses and dispatches.
- No mutable default arguments; no module-level mutable state (constants are fine).
- Every module keeps an `if __name__ == "__main__":` block where a smoke run makes sense; they are
  a development workflow, not dead code.

## Tests

`tests/` mirrors the code: `tests/core/` (the GPU harness against the NumPy twins), `tests/host/`,
`tests/ibl/`, `tests/jobs/`, `tests/tools/`, `tests/compile/`, plus `tests/test_check_docs.py`. A
test that needs a GPU skips with a reason when there is no adapter; a test that needs LFS payloads
skips when they are not hydrated. A DCC-side helper is tested with the DCC module stubbed
(`tests/tools/test_maya_session.py` is the pattern).

## Hygiene

Before every push: `uv run python tools/check_hygiene.py` is clean (the identifiers and the allowlist
live in that tool; no document repeats them). Personal email on every commit, `-s` for the DCO, no AI attribution. Nothing copied from a
studio tree; Apache-compatible dependencies only.
