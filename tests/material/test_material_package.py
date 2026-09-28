"""
HogShade: hogshade.material imports without MaterialX, PySide6 or numpy; the wheel ships the schema files.
Package: tests/material/test_material_package
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

EXPECTED_DATA = {
    "hogshade/material/schema/hogshade-standard.material-type.json",
    "hogshade/material/schema/hogshade-legacy-v2.material-type.json",
    "hogshade/material/schema/hogshade-legacy-v1.material-type.json",
    "hogshade/material/schema/hogshade-lambert.material-type.json",
    "hogshade/material/schema/conversions/hogshade-legacy-v2-to-hogshade-standard.json",
    "hogshade/material/schema/conversions/hogshade-legacy-v1-to-hogshade-standard.json",
    "hogshade/material/schema/conversions/hogshade-lambert-to-hogshade-standard.json",
}


def test_import_pulls_in_no_graphics_stack():
    code = (
        "import sys, hogshade.material as m; assert len(m.types()) == 4;"
        "print(','.join(sorted(x for x in ('MaterialX', 'PySide6', 'numpy') if x in sys.modules)))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=REPO)
    assert out.stdout.strip() == "", f"imported: {out.stdout.strip()}"


def test_public_names():
    import hogshade.material as m

    assert {"types", "type_of", "load", "validate", "resolve", "convert", "MaterialError", "Finding", "Loss"} <= set(
        m.__all__
    )


def test_wheel_contains_the_schema_files(tmp_path):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH; the wheel check runs where uv builds")
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path)], check=True, cwd=REPO, capture_output=True, text=True
    )
    wheels = list(tmp_path.glob("hogshade-*.whl"))
    assert len(wheels) == 1, wheels
    with zipfile.ZipFile(wheels[0]) as z:
        names = set(z.namelist())
    missing = EXPECTED_DATA - names
    assert missing == set(), f"missing from the wheel: {sorted(missing)}"
