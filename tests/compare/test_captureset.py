"""
HogShade: the capture set: write and read, the roles each level requires, and every way a set can be malformed.
Package: tests/compare/test_captureset
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hogshade.compare import captureset
from hogshade.compare.captureset import CaptureSetError, Manifest
from hogshade.compare.request import CaptureRequest

SIZE = (64, 32)  # (width, height)
REQUEST = CaptureRequest.from_dict(
    {
        "id": "unit-set",
        "mesh": "quad-sphere",
        "camera": {
            "eye": [0.0, 0.5, 4.0],
            "target": [0.0, 0.0, 0.0],
            "up": [0.0, 1.0, 0.0],
            "fov_y_deg": 32.0,
            "near": 0.05,
            "far": 50.0,
        },
        "rig": {"environment": "studio_small_09"},
        "size": list(SIZE),
    }
)
HASH = "a" * 64


def _manifest(level: str = "L2p", **kw) -> Manifest:
    fields = {
        "host": "wgpu",
        "level": level,
        "request_hash": REQUEST.content_hash(),
        "versions": {"wgpu": "1.0"},
        "inputs": {"mesh": HASH},
        "colour_space": "ACEScg" if level == "L2" else "unspecified",
    }
    fields.update(kw)
    return Manifest(**fields)


def _arrays():
    rng = np.random.default_rng(7)
    w, h = SIZE
    scene = rng.random((h, w, 3), dtype=np.float32) * 12.0  # beyond [0, 1] on purpose: scene-referred
    display = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    coverage = rng.random((h, w)) > 0.5
    return scene, display, coverage


def test_a_full_set_round_trips_exactly(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    out = captureset.write(
        tmp_path / "set", REQUEST, _manifest(logs=("host.log",)), scene, display, coverage, {"host.log": "hello\n"}
    )
    got = captureset.read(out)
    assert got.level == "L2p" and got.request == REQUEST and got.manifest.host == "wgpu"
    np.testing.assert_array_equal(got.scene, scene)  # float32 EXR, not half: nothing quantised
    np.testing.assert_array_equal(got.display, display)
    np.testing.assert_array_equal(got.coverage, coverage)
    assert (out / "host.log").read_text(encoding="utf-8") == "hello\n"
    assert sorted(p.name for p in out.iterdir()) == [
        "coverage.png",
        "display.png",
        "host.log",
        "manifest.json",
        "request.json",
        "scene.exr",
    ]


def test_an_l1_set_without_an_exr_or_a_mask_reads(tmp_path: Path) -> None:
    """A host limited to a display picture (today's Maya playblast) declares L1 and is not rejected."""
    _scene, display, _coverage = _arrays()
    out = captureset.write(tmp_path / "l1", REQUEST, _manifest("L1"), display=display)
    got = captureset.read(out)
    assert got.level == "L1" and got.scene is None and got.coverage is None
    np.testing.assert_array_equal(got.display, display)


def test_an_l1_set_may_carry_a_mask(tmp_path: Path) -> None:
    _scene, display, coverage = _arrays()
    got = captureset.read(
        captureset.write(tmp_path / "l1m", REQUEST, _manifest("L1"), display=display, coverage=coverage)
    )
    np.testing.assert_array_equal(got.coverage, coverage)


def test_an_l0_set_needs_a_log_that_says_why(tmp_path: Path) -> None:
    with pytest.raises(CaptureSetError, match="L0 produced nothing and must list the log"):
        captureset.write(tmp_path / "l0", REQUEST, _manifest("L0"))
    out = captureset.write(
        tmp_path / "l0", REQUEST, _manifest("L0", logs=("why.log",)), logs={"why.log": "no adapter\n"}
    )
    got = captureset.read(out)
    assert got.level == "L0" and got.scene is None and got.display is None


def test_a_level_cannot_claim_more_than_it_holds(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    with pytest.raises(CaptureSetError, match=r"level L2p requires \['scene.exr'\]"):
        captureset.write(tmp_path / "a", REQUEST, _manifest("L2p"), None, display, coverage)
    with pytest.raises(CaptureSetError, match=r"level L2p requires \['coverage.png'\]"):
        captureset.write(tmp_path / "b", REQUEST, _manifest("L2p"), scene, display, None)
    with pytest.raises(CaptureSetError, match=r"level L1 holds no \['scene.exr'\]"):
        captureset.write(tmp_path / "c", REQUEST, _manifest("L1"), scene, display)
    assert not (tmp_path / "a").exists(), "a refused write leaves nothing behind"


def test_l2_must_be_tagged_acescg_and_l2p_must_not_be() -> None:
    with pytest.raises(CaptureSetError, match="claims scene-referred ACEScg but colour_space is 'unspecified'"):
        _manifest("L2", colour_space="unspecified").validate()
    with pytest.raises(CaptureSetError, match="L2p is for sets not tagged ACEScg"):
        _manifest("L2p", colour_space="ACEScg").validate()
    _manifest("L2").validate()


def test_arrays_must_match_the_request_s_size_and_types(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    with pytest.raises(CaptureSetError, match=r"scene.exr: float \(H, W, 3\)"):
        captureset.write(tmp_path / "s", REQUEST, _manifest(), scene[:, :-1], display, coverage)
    with pytest.raises(CaptureSetError, match=r"display.png: uint8 \(H, W, 3\)"):
        captureset.write(tmp_path / "d", REQUEST, _manifest(), scene, display.astype(np.float32), coverage)
    with pytest.raises(CaptureSetError, match=r"coverage.png: bool \(H, W\)"):
        captureset.write(tmp_path / "c", REQUEST, _manifest(), scene, display, coverage.astype(np.uint8))


def test_a_manifest_built_from_another_request_is_refused(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    other = _manifest(request_hash="b" * 64)
    with pytest.raises(CaptureSetError, match="request_hash does not match the request"):
        captureset.write(tmp_path / "x", REQUEST, other, scene, display, coverage)


def test_logs_given_must_be_exactly_the_logs_listed(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    with pytest.raises(CaptureSetError, match="logs: the manifest lists"):
        captureset.write(tmp_path / "x", REQUEST, _manifest(logs=("a.log",)), scene, display, coverage, {})
    with pytest.raises(CaptureSetError, match="a file name ending in .log"):
        _manifest(logs=("../escape.txt",)).validate()


def test_reading_refuses_each_malformed_set_naming_the_role(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()

    def fresh(name: str) -> Path:
        return captureset.write(
            tmp_path / name, REQUEST, _manifest(logs=("h.log",)), scene, display, coverage, {"h.log": "x"}
        )

    missing = fresh("missing")
    (missing / "scene.exr").unlink()
    with pytest.raises(CaptureSetError, match=r"level L2p requires \['scene.exr'\]"):
        captureset.read(missing)

    unknown = fresh("unknown")
    (unknown / "notes.txt").write_text("stray", encoding="utf-8")
    with pytest.raises(CaptureSetError, match=r"unknown file\(s\) \['notes.txt'\]"):
        captureset.read(unknown)

    unlisted = fresh("unlisted")
    (unlisted / "extra.log").write_text("x", encoding="utf-8")
    with pytest.raises(CaptureSetError, match=r"unknown file\(s\) \['extra.log'\]"):
        captureset.read(unlisted)

    gone = fresh("gone")
    (gone / "h.log").unlink()
    with pytest.raises(CaptureSetError, match=r"lists log\(s\) \['h.log'\]"):
        captureset.read(gone)

    no_manifest = fresh("nomanifest")
    (no_manifest / "manifest.json").unlink()
    with pytest.raises(CaptureSetError, match="manifest.json: missing"):
        captureset.read(no_manifest)

    with pytest.raises(CaptureSetError, match="not a directory"):
        captureset.read(tmp_path / "does-not-exist")


def test_a_set_that_mixes_two_captures_is_refused(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    out = captureset.write(tmp_path / "mix", REQUEST, _manifest(), scene, display, coverage)
    tampered = json.loads((out / "request.json").read_text(encoding="utf-8"))
    tampered["debug_mode"] = 9
    (out / "request.json").write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(CaptureSetError, match="its hash differs from the manifest's request_hash"):
        captureset.read(out)


def test_a_picture_of_the_wrong_size_on_disk_is_refused(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    out = captureset.write(tmp_path / "size", REQUEST, _manifest(), scene, display, coverage)
    from hogshade.texture_cook import png

    png.write_png(out / "display.png", display[:, :-2])
    with pytest.raises(CaptureSetError, match=r"display.png: uint8 \(H, W, 3\)"):
        captureset.read(out)


def test_a_manifest_with_unknown_or_bad_fields_is_refused(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    out = captureset.write(tmp_path / "m", REQUEST, _manifest(), scene, display, coverage)
    good = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for change, message in (
        ({"colour": "x"}, r"unknown field\(s\) \['colour'\]"),
        ({"level": "L3"}, "level: one of"),
        ({"request_hash": "xyz"}, "request_hash: a SHA-256"),
        ({"inputs": {"mesh": "short"}}, r"inputs\['mesh'\]: a SHA-256"),
        ({"wall_seconds": -1}, "wall_seconds"),
    ):
        (out / "manifest.json").write_text(json.dumps({**good, **change}), encoding="utf-8")
        with pytest.raises(CaptureSetError, match=message):
            captureset.read(out)
    (out / "manifest.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(CaptureSetError, match="not valid JSON"):
        captureset.read(out)


def test_writing_over_a_previous_capture_replaces_it_whole_but_never_foreign_files(tmp_path: Path) -> None:
    scene, display, coverage = _arrays()
    target = tmp_path / "again"
    captureset.write(target, REQUEST, _manifest(logs=("old.log",)), scene, display, coverage, {"old.log": "x"})
    captureset.write(target, REQUEST, _manifest("L1"), display=display)
    assert sorted(p.name for p in target.iterdir()) == ["display.png", "manifest.json", "request.json"]
    (target / "precious.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(CaptureSetError, match=r"holds \['precious.txt'\], which are not a capture set's"):
        captureset.write(target, REQUEST, _manifest("L1"), display=display)
    assert (target / "precious.txt").read_text(encoding="utf-8") == "keep" and (target / "display.png").exists()


def test_an_input_hash_follows_the_file_s_bytes_while_the_request_hash_stays(tmp_path: Path) -> None:
    """Replacing an environment file in place changes what the manifest records; the request text is unchanged."""
    hdr = tmp_path / "env.hdr"
    hdr.write_bytes(b"first sky")
    before = captureset.sha256_file(hdr)
    hdr.write_bytes(b"second sky")
    after = captureset.sha256_file(hdr)
    assert before != after and len(before) == len(after) == 64
    one = _manifest(inputs={"environment:env.hdr": before})
    two = _manifest(inputs={"environment:env.hdr": after})
    assert one.request_hash == two.request_hash and one.inputs != two.inputs


def test_a_write_that_fails_part_way_leaves_the_previous_capture_intact_and_no_staging_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The verified fault: the old set was deleted before the new one was written, and a failure left half a set."""
    from hogshade.texture_cook import png

    scene, display, coverage = _arrays()
    target = tmp_path / "again"
    captureset.write(target, REQUEST, _manifest(), scene, display, coverage)
    before = {p.name: p.read_bytes() for p in target.iterdir()}

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(png, "write_png", boom)
    with pytest.raises(OSError, match="disk full"):
        captureset.write(target, REQUEST, _manifest("L1"), display=display)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before, "the previous capture is untouched"
    assert captureset.read(target).level == "L2p"
    assert not (tmp_path / ".again.staging").exists(), "the staging directory is cleaned up"
    monkeypatch.undo()
    captureset.write(target, REQUEST, _manifest("L1"), display=display)  # and the next write works
    assert captureset.read(target).level == "L1" and not (tmp_path / ".again.staging").exists()


def test_a_first_write_that_fails_leaves_nothing_behind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hogshade.ibl import imageio

    scene, display, coverage = _arrays()
    monkeypatch.setattr(imageio, "write_exr_rgb", lambda *a, **k: (_ for _ in ()).throw(OSError("no space")))
    with pytest.raises(OSError, match="no space"):
        captureset.write(tmp_path / "new", REQUEST, _manifest(), scene, display, coverage)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"versions": 5}, "versions: an object of strings"),
        ({"versions": {"a": 5}}, "versions: an object of strings"),
        ({"inputs": {"a": 5}}, "inputs: an object of strings"),
        ({"request_hash": 5}, "request_hash: a string is expected"),
        ({"host": ["wgpu"]}, "host: a string is expected"),
        ({"colour_space": 3}, "colour_space: a string is expected"),
        ({"logs": "a.log"}, "logs: a list of strings"),
        ({"notes": [1]}, "notes: a list of strings"),
        ({"wall_seconds": float("nan")}, "wall_seconds: a finite non-negative number"),
        ({"wall_seconds": True}, "wall_seconds: a finite non-negative number"),
        ({"wall_seconds": "fast"}, "wall_seconds: a finite non-negative number"),
    ],
)
def test_a_manifest_field_of_the_wrong_type_is_a_typed_error_not_a_raw_one(change: dict, message: str) -> None:
    good = _manifest().to_dict()
    with pytest.raises(CaptureSetError, match=message):
        Manifest.from_dict({**good, **change})


def test_unreadable_files_in_a_set_are_typed_errors(tmp_path: Path) -> None:
    from hogshade.texture_cook import png

    scene, display, coverage = _arrays()
    out = captureset.write(tmp_path / "bad", REQUEST, _manifest(), scene, display, coverage)
    png.write_png(out / "coverage.png", np.zeros((SIZE[1], SIZE[0], 3), dtype=np.uint8))  # RGB, not one channel
    with pytest.raises(CaptureSetError, match=r"coverage.png: a one-channel PNG is expected, got shape"):
        captureset.read(out)
    out = captureset.write(tmp_path / "bad2", REQUEST, _manifest(), scene, display, coverage)
    (out / "display.png").write_bytes(b"not a png")
    with pytest.raises(CaptureSetError, match="a picture cannot be read"):
        captureset.read(out)
    out = captureset.write(tmp_path / "bad3", REQUEST, _manifest(), scene, display, coverage)
    (out / "manifest.json").write_bytes(b"\xff\xfe\x00 not utf-8")
    with pytest.raises(CaptureSetError, match="manifest.json: not valid JSON"):
        captureset.read(out)
    out = captureset.write(tmp_path / "bad4", REQUEST, _manifest(), scene, display, coverage)
    (out / "request.json").write_bytes(b"\xff\xfe")
    with pytest.raises(CaptureSetError, match="request.json:"):
        captureset.read(out)
