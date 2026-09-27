"""
HogShade: tools/maya/_session.py's path rules, run without Maya (its ``cmds`` import is stubbed).
Package: tests/tools/test_maya_session
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOGSHADE_ROOT", str(tmp_path))
    monkeypatch.setenv("HOGSHADE_VERIFICATION", str(tmp_path / "verification"))
    maya = types.ModuleType("maya")
    maya.cmds = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "maya", maya)
    monkeypatch.syspath_prepend(str(ROOT / "tools" / "maya"))
    sys.modules.pop("_session", None)
    return importlib.import_module("_session")


def test_output_dir_is_one_directory_per_capture(session, tmp_path: Path) -> None:
    out = session.output_dir("ibl-check", "legacy-v1/studio_small_09")
    assert out == tmp_path / "verification" / "maya-2026" / "ibl-check" / "legacy-v1" / "studio_small_09"
    assert out.is_dir()
    assert session.output_dir("load-check") == tmp_path / "verification" / "maya-2026" / "load-check"


@pytest.mark.parametrize(
    "check, variant", [("ibl-check", "../../../../escape"), ("../check", ""), ("ibl-check", "a/../b")]
)
def test_output_dir_refuses_paths_that_climb(session, tmp_path: Path, check: str, variant: str) -> None:
    with pytest.raises(ValueError, match="escapes"):
        session.output_dir(check, variant)
    assert not (tmp_path / "escape").exists() and not (tmp_path / "check").exists()


def test_maya_path_uses_forward_slashes(session) -> None:
    assert session.maya_path(Path("C:/a") / "b" / "c.png") == "C:/a/b/c.png"
