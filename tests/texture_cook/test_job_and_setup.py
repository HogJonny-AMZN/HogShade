"""
HogShade: the cook job is registered and its manifest matches what the cook writes; a climbing set_dir is refused;
the setup story: the encoder's absence is a warning with the command, --compress without it exits 2, --check-setup
reports.
Package: tests/texture_cook/test_job_and_setup
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hogshade.jobs import JOB_MODULES, manifest
from hogshade.jobs import cook_textures as job
from hogshade.texture_cook import cook, encoders

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def test_the_job_is_registered_and_listed():
    assert "hogshade.jobs.cook_textures" in JOB_MODULES
    entry = next(m for m in manifest() if m["name"] == "hogshade.cook_textures")
    assert entry["module_path"] == "hogshade.jobs.cook_textures" and entry["entry_point"] == "main"
    assert entry["spec"] == "Docs/superpowers/specs/t2-texture-cook.md"


def test_the_job_runs_like_the_worker_calls_it_and_matches_its_outputs(brick: Path):
    result = job.main({"set_dir": str(brick), "compress": "no", "separate": "1", "radius": "4", "macro": "8"})
    assert result["set"] == "brick" and "separation" in result
    written = sorted(p.name for p in (brick / "cooked").iterdir())
    for pattern in job.MANIFEST["outputs"]:
        if "manifest.json" in pattern:
            assert "manifest.json" in written
        if "provenance.json" in pattern:
            assert "provenance.json" in written
    assert any(name.endswith(".dds") for name in written)
    sidecar = json.loads((brick / "T_brick_R.texture.json").read_text(encoding="utf-8"))
    assert "derived" in sidecar, "the job filled the derived fields, as the outputs list says"


def test_a_climbing_set_dir_is_refused():
    with pytest.raises(cook.CookError, match="climbs"):
        job.main({"set_dir": "content/../../elsewhere"})


def test_missing_encoder_warns_with_the_command_and_check_setup_reports(brick: Path, monkeypatch, caplog, capsys):
    import cook_textures as tool

    monkeypatch.setattr(
        encoders, "IspcEncoder", lambda: (_ for _ in ()).throw(ImportError("no module named ispc_texcomp"))
    )
    with caplog.at_level("WARNING", logger=encoders._MODULE_NAME):
        assert encoders.default_encoder() is None
    assert "uv sync --extra textures" in caplog.text
    report = encoders.encoder_report()
    assert report["encoder"] is None and "uv sync" in report["hint"]
    assert tool.main(["--check-setup"]) == 1
    assert "hint" in capsys.readouterr().out
    assert tool.main(["cook", str(brick), "--compress"]) == 2
    assert tool.main(["cook", str(brick)]) == 0, "implicit: uncompressed, no error"
    assert (
        json.loads((brick / "cooked" / "manifest.json").read_text(encoding="utf-8"))["compression"]["encoder"] is None
    )


@pytest.mark.skipif(encoders.default_encoder() is None, reason="ispc_texcomp not installed")
def test_check_setup_names_the_encoder_and_the_formats(capsys):
    import cook_textures as tool

    assert tool.main(["--check-setup"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["encoder"] == "ispc_texcomp" and report["formats"] == ["bc7", "bc5", "bc4"] and report["version"]


def test_the_tool_without_a_command_prints_help(capsys):
    import cook_textures as tool

    assert tool.main([]) == 2
