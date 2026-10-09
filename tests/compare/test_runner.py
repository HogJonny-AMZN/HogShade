"""
HogShade: the runner on the committed oracle cases, with a fake adapter that writes ideal captures, and with wrong ones.
Package: tests/compare/test_runner

No GPU: the fake adapter writes real capture sets (through ``captureset.write``) holding exactly the frames the oracles
expect, so what is tested is the runner, the verdicts, the controls and the acceptances, end to end. The committed case
table is loaded and its requests are shrunk to 128 px so the run is quick; the real size runs on the owner's machine.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import ideal_frames
import numpy as np
import pytest

from hogshade import wgpu_host
from hogshade.compare import captureset, cases, oracles, runner
from hogshade.compare.adapters import wgpu as wgpu_adapter
from hogshade.compare.captureset import CaptureSet, Manifest
from hogshade.compare.report import Report
from hogshade.compare.request import CaptureRequest
from hogshade.compare.runner import RunnerError
from hogshade.compare.verdict import AcceptedDifferences, Threshold, Verdict

CASES_DIR = wgpu_host.ROOT / "verification" / "cases"
SMALL = 128


def _small(case: cases.Case) -> cases.Case:
    """The case at 128 px: the request shrunk, the pixel-count bounds scaled by the area (the agreement bounds not)."""
    request = CaptureRequest.from_dict({**case.request.to_dict(), "size": [SMALL, SMALL]})
    scale = (SMALL / case.request.size[0]) ** 2
    thresholds = tuple(
        Threshold(t.metric, t.pass_at * scale, t.fail_at * scale, t.direction) if t.metric.endswith("pixels") else t
        for t in case.thresholds
    )
    return dataclasses.replace(case, request=request, thresholds=thresholds)


@pytest.fixture(scope="module")
def committed() -> list[cases.Case]:
    return [_small(c) for c in cases.load(CASES_DIR, oracles.CHECKS)]


class FakeAdapter:
    """Writes the ideal capture of each request; ``mutate`` turns it into a wrong one."""

    def __init__(self, mutate=None) -> None:
        self.calls: list[str] = []
        self.mutate = mutate

    def __call__(self, request: CaptureRequest, directory: Path) -> CaptureSet:
        self.calls.append(request.id)
        ideal = ideal_frames.ideal_for(request)
        scene, coverage = ideal.scene, ideal.coverage
        if self.mutate is not None:
            scene, coverage = self.mutate(scene, coverage)
        manifest = Manifest(host="fake", level="L2p", request_hash=request.content_hash(), inputs={"mesh": "a" * 64})
        display = np.zeros((*scene.shape[:2], 3), dtype=np.uint8)
        captureset.write(directory, request, manifest, scene, display, coverage)
        return captureset.read(directory)


def test_the_committed_case_table_is_valid_and_every_request_is_one_the_wgpu_host_can_honour() -> None:
    table = cases.load(CASES_DIR, oracles.CHECKS)
    assert len(table) == 9 and {c.kind for c in table} == {"oracle"}
    controls = [c for c in table if c.is_control]
    assert sorted(c.id for c in controls) == [
        "normal-green-flipped",
        "normal-red-flipped",
        "texel-colour-v-flipped",
        "texel-metalness-v-flipped",
    ]
    for case in table:
        wgpu_adapter.check_supported(case.request)
        assert case.check.data_range == 1.0 and case.request.textures == "content/textures/synthetic"
    # a control shares its twin's request, so one capture serves both
    by_request = {}
    for case in table:
        by_request.setdefault(case.request.content_hash(), []).append(case.id)
    assert any(len(ids) > 1 for ids in by_request.values()) and len(by_request) == 5


def test_a_run_on_ideal_captures_passes_every_case_and_every_control_fails(committed, tmp_path: Path) -> None:
    adapter = FakeAdapter()
    report = runner.run(committed, adapter, tmp_path, "fake", "L2p", {"fake": "1"})
    assert sorted(adapter.calls) == sorted(set(adapter.calls)) and len(adapter.calls) == 5, "one capture per request"
    assert report.ok, report.to_json()
    assert report.summary == {"cases": 5, "pass": 5, "needs-review": 0, "fail": 0, "controls": 4, "controls_ok": 4}
    for result in report.cases:
        assert result.capture and result.capture_hash and result.reference_hash
        assert all(m.data_range == 1.0 for m in result.measurements)
        if result.is_control:
            assert result.verdict is Verdict.FAIL and result.control_ok
    assert Report.from_json(report.to_json()) == report


def test_a_run_on_wrong_captures_fails_the_cases_it_should(committed, tmp_path: Path) -> None:
    """A host that draws the picture shifted: the ordinary cases fail, and the report says not ok."""
    adapter = FakeAdapter(mutate=lambda scene, cov: (np.roll(scene, 11, axis=1), cov))
    report = runner.run(committed, adapter, tmp_path, "fake", "L2p")
    assert not report.ok and report.summary["fail"] >= 3 and report.summary["pass"] <= 2
    failed = [c for c in report.cases if not c.is_control and c.verdict is Verdict.FAIL]
    assert failed and all(c.notes for c in failed)


def test_a_control_that_passes_makes_the_run_not_ok(tmp_path: Path) -> None:
    """The expectation is wrong on purpose and the check still passes: the instrument is blind, and the run says so."""
    control = _small(cases.load_file(CASES_DIR / "oracle-quad-sphere.json", oracles.CHECKS)[0])
    blind = dataclasses.replace(control, id="blind-control", expect="fail")  # the roughness check has no way to fail
    report = runner.run([blind], FakeAdapter(), tmp_path, "fake", "L2p")
    result = report.cases[0]
    assert result.verdict is Verdict.PASS and result.control_ok is False
    assert not report.ok and report.summary["controls_ok"] == 0


def test_a_check_that_cannot_measure_fails_its_case_with_the_reason(committed, tmp_path: Path) -> None:
    ball = CaptureRequest.from_dict({**committed[0].request.to_dict(), "mesh": "shader-ball"})
    case = dataclasses.replace(committed[0], request=ball)

    def capture(request, directory):
        ideal = ideal_frames.ideal_texel(committed[0].request, "_R", True)
        manifest = Manifest(host="fake", level="L2p", request_hash=request.content_hash())
        captureset.write(
            directory, request, manifest, ideal.scene, np.zeros((SMALL, SMALL, 3), np.uint8), ideal.coverage
        )
        return captureset.read(directory)

    report = runner.run([case], capture, tmp_path, "fake", "L2p")
    result = report.cases[0]
    assert result.verdict is Verdict.FAIL and "need mesh 'quad-sphere'" in (result.error or "") and not report.ok
    assert Report.from_json(report.to_json()).cases[0].error == result.error


def test_a_control_that_cannot_measure_proved_nothing(committed, tmp_path: Path) -> None:
    ball = CaptureRequest.from_dict({**committed[0].request.to_dict(), "mesh": "shader-ball"})
    control = dataclasses.replace(committed[0], request=ball, expect="fail")

    def capture(request, directory):
        ideal = ideal_frames.ideal_texel(committed[0].request, "_R", True)
        manifest = Manifest(host="fake", level="L2p", request_hash=request.content_hash())
        captureset.write(
            directory, request, manifest, ideal.scene, np.zeros((SMALL, SMALL, 3), np.uint8), ideal.coverage
        )
        return captureset.read(directory)

    report = runner.run([control], capture, tmp_path, "fake", "L2p")
    assert report.cases[0].verdict is Verdict.FAIL and report.cases[0].control_ok is False and not report.ok
    assert Report.from_json(report.to_json()) == report  # the schema allows exactly this combination


def _needs_review(case: cases.Case) -> cases.Case:
    """The same case with bounds that put a perfect measurement between pass and fail."""
    return dataclasses.replace(case, thresholds=(Threshold("agreement", 1.5, 0.5),))


def test_an_acceptance_resolves_a_needs_review_only_while_the_hashes_hold(committed, tmp_path: Path) -> None:
    case = _needs_review(committed[0])
    first = runner.run([case], FakeAdapter(), tmp_path / "a", "fake", "L2p")
    result = first.cases[0]
    assert result.verdict is Verdict.NEEDS_REVIEW and not first.ok and not result.accepted

    accepted = AcceptedDifferences()
    accepted.accept(case.id, result.capture_hash, result.reference_hash, "looked at the diff; fine", "2026-10-08")
    second = runner.run([case], FakeAdapter(), tmp_path / "b", "fake", "L2p", accepted=accepted)
    assert second.cases[0].verdict is Verdict.PASS and second.cases[0].accepted and second.ok
    assert any("accepted: looked at the diff" in n for n in second.cases[0].notes)

    # the capture's pixels change (below the tolerance, so the same verdict): the acceptance no longer applies
    nudged = FakeAdapter(mutate=lambda scene, cov: (scene + np.float32(1e-4) * cov[..., None], cov))
    third = runner.run([case], nudged, tmp_path / "c", "fake", "L2p", accepted=accepted)
    assert third.cases[0].verdict is Verdict.NEEDS_REVIEW and not third.cases[0].accepted and not third.ok

    # and so does changing what it was compared against (the check's parameters)
    changed = dataclasses.replace(
        case, check=dataclasses.replace(case.check, params={**case.check.params, "stride": 4})
    )
    assert runner.reference_hash(changed) != runner.reference_hash(case)
    fourth = runner.run([changed], FakeAdapter(), tmp_path / "d", "fake", "L2p", accepted=accepted)
    assert fourth.cases[0].verdict is Verdict.NEEDS_REVIEW


def test_a_fail_is_never_rescued_by_an_acceptance(committed, tmp_path: Path) -> None:
    case = dataclasses.replace(
        committed[0], thresholds=(Threshold("agreement", 2.0, 1.5),)
    )  # 1.0 is below the fail bound
    failing = runner.run([case], FakeAdapter(), tmp_path / "a", "fake", "L2p")
    result = failing.cases[0]
    assert result.verdict is Verdict.FAIL
    accepted = AcceptedDifferences()
    accepted.accept(case.id, result.capture_hash, result.reference_hash, "wishful", "2026-10-08")
    again = runner.run([case], FakeAdapter(), tmp_path / "b", "fake", "L2p", accepted=accepted)
    assert again.cases[0].verdict is Verdict.FAIL and not again.cases[0].accepted


def test_a_table_the_runner_cannot_run_is_refused_by_name_before_any_capture(committed, tmp_path: Path) -> None:
    regression = dataclasses.replace(committed[0], id="reg-1", kind="regression")
    parity = dataclasses.replace(committed[0], id="par-1", kind="parity")
    adapter = FakeAdapter()
    with pytest.raises(RunnerError, match=r"reg-1 \(regression, increment C-3\), par-1 \(parity, increment C-5\)"):
        runner.run([committed[0], regression, parity], adapter, tmp_path, "fake", "L2p")
    assert adapter.calls == [], "nothing was captured for a table that cannot run"
    with pytest.raises(RunnerError, match="an empty table proves nothing"):
        runner.run([], adapter, tmp_path, "fake", "L2p")


def test_captures_land_under_the_output_directory_named_by_request_and_hash(committed, tmp_path: Path) -> None:
    report = runner.run(committed[:1], FakeAdapter(), tmp_path, "fake", "L2p")
    capture = report.cases[0].capture
    assert capture and (tmp_path / capture / "manifest.json").is_file()
    assert capture.startswith(f"{committed[0].request.id}-{committed[0].request.content_hash()[:8]}")
