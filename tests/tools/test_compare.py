"""
HogShade: tools/compare.py: validate, list and run, with a fake adapter standing in for the GPU.
Package: tests/tools/test_compare
"""

from __future__ import annotations

import dataclasses
import json
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests" / "compare"))  # ideal_frames: the helper that writes captures with no GPU

import compare
import ideal_frames
import numpy as np

from hogshade.compare import captureset, cases, oracles
from hogshade.compare.captureset import Manifest
from hogshade.compare.report import Report
from hogshade.compare.request import CaptureRequest
from hogshade.compare.verdict import AcceptedDifferences, Threshold

SMALL = 128
H = "d" * 64


def _args(*argv: str):
    return compare.build_parser().parse_args(list(argv))


def _write_cases(directory: Path, table: list[cases.Case], name: str = "c.json") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(cases.dump(table), encoding="utf-8")
    return directory


def _small_table() -> list[cases.Case]:
    """The committed cases at 128 px with the pixel-count bounds scaled by area, so a run is quick."""
    out = []
    for case in cases.load(compare.CASES_DIR, oracles.CHECKS):
        request = CaptureRequest.from_dict({**case.request.to_dict(), "size": [SMALL, SMALL]})
        scale = (SMALL / case.request.size[0]) ** 2
        thresholds = tuple(
            Threshold(t.metric, t.pass_at * scale, t.fail_at * scale, t.direction) if t.metric.endswith("pixels") else t
            for t in case.thresholds
        )
        out.append(dataclasses.replace(case, request=request, thresholds=thresholds))
    return out


class FakeAdapter:
    """The wgpu adapter's two methods, writing ideal captures."""

    def capture(self, request, directory):
        ideal = ideal_frames.ideal_for(request)
        manifest = Manifest(host="wgpu", level="L2p", request_hash=request.content_hash(), inputs={"mesh": H})
        captureset.write(
            directory, request, manifest, ideal.scene, np.zeros((*ideal.scene.shape[:2], 3), np.uint8), ideal.coverage
        )
        return captureset.read(directory)

    def versions(self):
        return {"fake": "1"}


# ---- validate and list ----------------------------------------------------------------------------------------------


def test_the_committed_tree_validates() -> None:
    assert compare.main(["validate"]) == 0


def test_list_prints_every_case_and_marks_the_controls(capsys) -> None:
    assert compare.main(["list"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 9 and sum("\tcontrol\t" in line for line in lines) == 4
    assert any(line.startswith("texel-roughness\toracle\tcase\tquad-sphere-texel") for line in lines)


def test_a_broken_case_is_a_finding_naming_the_file_and_the_field(tmp_path: Path, caplog) -> None:
    table = cases.load(compare.CASES_DIR, oracles.CHECKS)[:1]
    data = json.loads(cases.dump(table))
    data["cases"][0]["check"].pop("data_range")
    directory = tmp_path / "cases"
    directory.mkdir()
    (directory / "bad.json").write_text(json.dumps(data), encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        code = compare.main(["validate", "--cases", str(directory), "--accepted", str(tmp_path / "none.json")])
    assert code == 1
    text = caplog.text
    assert "bad.json" in text and "check.data_range" in text and "needs an explicit peak" in text


def test_a_request_the_wgpu_host_cannot_honour_is_a_finding(tmp_path: Path, caplog) -> None:
    case = cases.load(compare.CASES_DIR, oracles.CHECKS)[0]
    rotated = CaptureRequest.from_dict(
        {**case.request.to_dict(), "rig": {"environment": "studio_small_09", "rotation_deg": 30}}
    )
    directory = _write_cases(tmp_path / "cases", [dataclasses.replace(case, request=rotated)])
    with caplog.at_level(logging.ERROR):
        assert compare.main(["validate", "--cases", str(directory), "--accepted", str(tmp_path / "none.json")]) == 1
    assert "cannot honour its request" in caplog.text and "no environment rotation" in caplog.text


def test_an_acceptance_that_names_no_case_is_a_finding(tmp_path: Path, caplog) -> None:
    accepted = AcceptedDifferences()
    accepted.accept("no-such-case", H, H, "reason", "2026-10-08")
    path = tmp_path / "accepted.json"
    accepted.save(path)
    with caplog.at_level(logging.ERROR):
        assert compare.main(["validate", "--accepted", str(path)]) == 1
    assert "'no-such-case' is accepted but no case has that id" in caplog.text


def test_a_stored_report_is_checked_against_its_schema(tmp_path: Path, caplog) -> None:
    good = tmp_path / "good.json"
    good.write_text(Report("wgpu", "L2p").to_json(), encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text('{"version": 9}', encoding="utf-8")
    assert compare.main(["validate", "--report", str(good)]) == 0
    with caplog.at_level(logging.ERROR):
        assert compare.main(["validate", "--report", str(bad)]) == 1
    assert "bad.json" in caplog.text and "unknown field(s)" in caplog.text


def test_an_empty_table_is_a_finding(tmp_path: Path, caplog) -> None:
    (tmp_path / "empty").mkdir()
    with caplog.at_level(logging.ERROR):
        assert compare.main(["validate", "--cases", str(tmp_path / "empty")]) == 1
    assert "an empty table proves nothing" in caplog.text


# ---- run ------------------------------------------------------------------------------------------------------------


def test_run_without_an_adapter_exits_three_or_zero_with_allow_skips(monkeypatch, tmp_path: Path) -> None:
    def no_gpu():
        raise compare.wgpu_adapter.NoAdapter("RuntimeError: no adapter")

    monkeypatch.setattr(compare, "make_adapter", no_gpu)
    out = tmp_path / "out"
    assert compare.main(["run", "--out", str(out)]) == compare.EXIT_NO_ADAPTER
    assert compare.main(["run", "--out", str(out), "--allow-skips"]) == compare.EXIT_OK
    assert not out.exists(), "nothing ran, so nothing was written"


def test_run_refuses_a_table_it_cannot_run_and_an_unknown_only(monkeypatch, tmp_path: Path, caplog) -> None:
    monkeypatch.setattr(compare, "make_adapter", FakeAdapter)
    case = _small_table()[0]
    directory = _write_cases(tmp_path / "cases", [dataclasses.replace(case, id="parity-1", kind="parity")])
    # no C-2 check serves a parity case, so the registry refuses it as a finding at load; runner.check_runnable is the
    # second line of defence for a registry that one day does
    with caplog.at_level(logging.ERROR):
        assert compare.main(["run", "--cases", str(directory), "--out", str(tmp_path / "o")]) == compare.EXIT_FINDINGS
        assert compare.main(["run", "--only", "nope", "--out", str(tmp_path / "o")]) == compare.EXIT_REFUSED
    assert "serves ['oracle'], not kind 'parity'" in caplog.text and "--only names no case: ['nope']" in caplog.text


def test_run_on_ideal_captures_writes_a_valid_passing_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(compare, "make_adapter", FakeAdapter)
    directory = _write_cases(tmp_path / "cases", _small_table())
    out = tmp_path / "out"
    assert compare.main(["run", "--cases", str(directory), "--out", str(out)]) == compare.EXIT_OK
    report = Report.from_json((out / "report.json").read_text(encoding="utf-8"))
    assert report.ok and report.host == "wgpu" and report.level == "L2p" and report.versions == {"fake": "1"}
    assert report.summary["cases"] == 5 and report.summary["controls_ok"] == 4
    assert compare.main(["validate", "--cases", str(directory), "--report", str(out / "report.json")]) == 0


def test_run_only_runs_the_named_case(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(compare, "make_adapter", FakeAdapter)
    directory = _write_cases(tmp_path / "cases", _small_table())
    out = tmp_path / "out"
    assert compare.main(["run", "--cases", str(directory), "--out", str(out), "--only", "texel-roughness"]) == 0
    report = Report.from_json((out / "report.json").read_text(encoding="utf-8"))
    assert [c.id for c in report.cases] == ["texel-roughness"]


def test_run_exits_one_when_a_case_fails(monkeypatch, tmp_path: Path) -> None:
    class Shifted(FakeAdapter):
        def capture(self, request, directory):
            ideal = ideal_frames.ideal_for(request)
            manifest = Manifest(host="wgpu", level="L2p", request_hash=request.content_hash())
            captureset.write(
                directory,
                request,
                manifest,
                np.roll(ideal.scene, 11, axis=1),
                np.zeros((*ideal.scene.shape[:2], 3), np.uint8),
                ideal.coverage,
            )
            return captureset.read(directory)

    monkeypatch.setattr(compare, "make_adapter", Shifted)
    directory = _write_cases(tmp_path / "cases", _small_table())
    assert compare.main(["run", "--cases", str(directory), "--out", str(tmp_path / "out")]) == compare.EXIT_FINDINGS
    assert not Report.from_json((tmp_path / "out" / "report.json").read_text(encoding="utf-8")).ok


def test_the_module_exposes_the_documented_exit_codes() -> None:
    assert (compare.EXIT_OK, compare.EXIT_FINDINGS, compare.EXIT_REFUSED, compare.EXIT_NO_ADAPTER) == (0, 1, 2, 3)


def test_a_broken_adapter_is_a_failure_even_with_allow_skips(monkeypatch, tmp_path: Path) -> None:
    """Only NoAdapter (wgpu absent, or no device found) is a skip. Any other error, RuntimeError included, is a bug."""
    for bug in (TypeError("a typo in the adapter"), RuntimeError("adapter initialization bug"), OSError("disk")):

        def broken(bug=bug):
            raise bug

        monkeypatch.setattr(compare, "make_adapter", broken)
        with pytest.raises(type(bug), match=str(bug)):
            compare.main(["run", "--out", str(tmp_path / "o"), "--allow-skips"])

    def no_gpu():
        raise compare.wgpu_adapter.NoAdapter("ImportError: no wgpu")

    monkeypatch.setattr(compare, "make_adapter", no_gpu)
    assert compare.main(["run", "--out", str(tmp_path / "o"), "--allow-skips"]) == compare.EXIT_OK
    assert compare.main(["run", "--out", str(tmp_path / "o")]) == compare.EXIT_NO_ADAPTER


def test_a_non_utf8_accepted_file_is_a_finding_not_a_crash(tmp_path: Path, caplog) -> None:
    path = tmp_path / "accepted.json"
    path.write_bytes(b"{" + bytes([233, 255]) + b"}")
    with caplog.at_level(logging.ERROR):
        assert compare.main(["validate", "--accepted", str(path)]) == 1
    assert "accepted.json" in caplog.text and "not valid JSON" in caplog.text
