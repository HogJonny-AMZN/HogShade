"""
HogShade: the tangent-dump job's Python half, without Maya: a climbing or escaping path is refused before any Maya
import, and the manifest names the headless worker (T3b).
Package: tests/jobs/test_maya_mikktspace_dump_job
"""

from __future__ import annotations

import sys

import pytest

from hogshade.jobs import maya_mikktspace_dump as job


def test_paths_are_confined_before_maya_is_touched(tmp_path):
    assert job.MANIFEST["worker_type"] == "hogshade_maya" and job.MANIFEST["execution_mode"] == "HEADLESS"
    with pytest.raises(ValueError, match="obj is required"):
        job.main({})
    with pytest.raises(ValueError, match="climbs with"):
        job.main({"obj": "content/shaderball/shaderBall.obj", "out": "../elsewhere.npz"})
    with pytest.raises(ValueError, match="outside the workspace"):
        job.main({"obj": "content/shaderball/shaderBall.obj", "out": str(tmp_path / "fixture.npz")})
    assert "maya" not in sys.modules and "maya.cmds" not in sys.modules
