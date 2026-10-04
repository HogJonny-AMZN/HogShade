"""
HogShade: the Maya jobs describe themselves in one vocabulary (worker type, execution mode, main thread), every
path-typed parameter of the texture job is screened for a climb, and the job is registered.
Package: tests/jobs/test_maya_jobs
"""

from __future__ import annotations

import pytest

from hogshade.jobs import JOB_MODULES, manifest, maya_ibl_check, maya_texture_check


def test_the_maya_jobs_share_one_vocabulary():
    for job in (maya_ibl_check, maya_texture_check):
        m = job.MANIFEST
        assert (m["worker_type"], m["execution_mode"], m["execute_on_main_thread"]) == (
            "hogshade_maya_gui",
            "GUI",
            True,
        )
        assert "main_thread" not in m and m["name"].startswith("hogshade.")


def test_the_texture_job_is_registered_and_screens_every_path_parameter():
    assert "hogshade.jobs.maya_texture_check" in JOB_MODULES
    assert "hogshade.maya_texture_check" in {m["name"] for m in manifest()}
    assert set(maya_texture_check.PATH_PARAMETERS) == {"set_dir", "document", "fx"}
    with pytest.raises(ValueError, match="set_dir is required"):
        maya_texture_check.main({})
    for key in maya_texture_check.PATH_PARAMETERS:
        params = {"set_dir": "content/textures/grid", key: "content/../../elsewhere"}
        with pytest.raises(ValueError, match=f"{key} .*climbs"):
            maya_texture_check.main(params)
