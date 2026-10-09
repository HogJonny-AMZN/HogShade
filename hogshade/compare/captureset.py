"""
HogShade: the capture set: the directory a host's adapter writes and the framework reads.
Package: hogshade/compare/captureset

One directory per capture, files named by role (the verification layout rule). Which roles a set must hold depends on
the **level** it declares, so a valid lower-level set is not rejected and a set can never claim more than it holds:

========  =====================================================================================================
Level     Required roles
========  =====================================================================================================
``L2``    ``request.json`` ``scene.exr`` ``display.png`` ``coverage.png`` ``manifest.json``; ACEScg-tagged
``L2p``   the same; the scene-linear float is untagged or not ACEScg (provisional, refused by parity cases)
``L1``    ``request.json`` ``display.png`` ``manifest.json`` (``coverage.png`` optional; no ``scene.exr``)
``L0``    ``request.json`` ``manifest.json`` and at least one log: a host that produced nothing must say why
========  =====================================================================================================

Logs (``*.log``) are optional at every other level and listed in the manifest. Any file that is neither a role of the
level nor a listed log is refused as unknown, so a typo cannot pass for an extra. The manifest holds the host and its
versions (the request names no host), the level actually reached, and the hash of everything the adapter loaded.
"""

from __future__ import annotations

import hashlib
import json
import logging as _logging
import math
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hogshade.compare.request import CaptureRequest, RequestError
from hogshade.ibl import imageio
from hogshade.texture_cook import png

_MODULE_NAME = "hogshade.compare.captureset"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

REQUEST = "request.json"
SCENE = "scene.exr"
DISPLAY = "display.png"
COVERAGE = "coverage.png"
MANIFEST = "manifest.json"

#: The levels, best first.
LEVELS = ("L2", "L2p", "L1", "L0")

#: The working space a set must declare to claim L2.
ACESCG = "ACEScg"

#: Roles each level requires, and the roles it may additionally hold. Logs are handled separately.
REQUIRED: dict[str, frozenset[str]] = {
    "L2": frozenset({REQUEST, SCENE, DISPLAY, COVERAGE, MANIFEST}),
    "L2p": frozenset({REQUEST, SCENE, DISPLAY, COVERAGE, MANIFEST}),
    "L1": frozenset({REQUEST, DISPLAY, MANIFEST}),
    "L0": frozenset({REQUEST, MANIFEST}),
}
OPTIONAL: dict[str, frozenset[str]] = {
    "L2": frozenset(),
    "L2p": frozenset(),
    "L1": frozenset({COVERAGE}),
    "L0": frozenset(),
}

_SHA256 = re.compile(r"[0-9a-f]{64}")
_LOG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.log")


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's bytes, in hex: the value the manifest's ``inputs`` records for what an adapter loaded."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _previous_logs(directory: Path) -> frozenset[str]:
    """The logs a previous capture set in ``directory`` listed in its manifest (none when it has no readable one)."""
    try:
        logs = json.loads((directory / MANIFEST).read_text(encoding="utf-8")).get("logs", [])
    except (OSError, ValueError, AttributeError):  # no manifest, not JSON, not UTF-8, or not an object
        return frozenset()
    return frozenset(name for name in logs if isinstance(name, str) and _LOG.fullmatch(name))


def pixel_hash(directory: Path) -> str:
    """
    SHA-256 of what a capture set shows: the request and whichever pictures it holds, by role. The manifest (a wall
    time, the versions) and the logs are left out, so two captures of one request on one host hash alike when their
    pixels do.
    """
    directory = Path(directory)
    digest = hashlib.sha256()
    for role in (REQUEST, SCENE, DISPLAY, COVERAGE):
        path = directory / role
        if path.is_file():
            digest.update(f"{role}:{sha256_file(path)}\n".encode())
    return digest.hexdigest()


class CaptureSetError(ValueError):
    """A capture set that is malformed, or a write that would make one; the message names the role or file."""


@dataclass(frozen=True)
class Manifest:
    """What produced a capture set and what it actually contains."""

    host: str
    level: str
    request_hash: str
    versions: dict[str, str] = field(default_factory=dict)
    #: A hash for everything actually loaded: ``mesh``, ``material``, ``textures``, one ``environment:<file>`` per file.
    inputs: dict[str, str] = field(default_factory=dict)
    colour_space: str = "unspecified"
    logs: tuple[str, ...] = ()
    wall_seconds: float = 0.0
    notes: tuple[str, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.host, str) or not self.host:
            raise CaptureSetError(f"{MANIFEST}: host: a non-empty name is expected, got {self.host!r}")
        if self.level not in LEVELS:
            raise CaptureSetError(f"{MANIFEST}: level: one of {list(LEVELS)} is expected, got {self.level!r}")
        if not _SHA256.fullmatch(self.request_hash):
            raise CaptureSetError(f"{MANIFEST}: request_hash: a SHA-256 in hex is expected, got {self.request_hash!r}")
        for key, value in self.inputs.items():
            if not _SHA256.fullmatch(value):
                raise CaptureSetError(f"{MANIFEST}: inputs[{key!r}]: a SHA-256 in hex is expected, got {value!r}")
        for name in self.logs:
            if not _LOG.fullmatch(name):
                raise CaptureSetError(f"{MANIFEST}: logs: a file name ending in .log is expected, got {name!r}")
        if self.level == "L2" and self.colour_space != ACESCG:
            raise CaptureSetError(
                f"{MANIFEST}: level L2 claims scene-referred ACEScg but colour_space is {self.colour_space!r}; "
                "a set that is not tagged ACEScg is L2p at best"
            )
        if self.level == "L2p" and self.colour_space == ACESCG:
            raise CaptureSetError(f"{MANIFEST}: level L2p is for sets not tagged ACEScg; a tagged set declares L2")
        if self.level == "L0" and not self.logs:
            raise CaptureSetError(f"{MANIFEST}: level L0 produced nothing and must list the log that says why")
        if (
            isinstance(self.wall_seconds, bool)
            or not isinstance(self.wall_seconds, (int, float))
            or not math.isfinite(self.wall_seconds)
            or self.wall_seconds < 0
        ):
            raise CaptureSetError(f"{MANIFEST}: wall_seconds: a finite non-negative number is expected")

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "level": self.level,
            "request_hash": self.request_hash,
            "versions": dict(self.versions),
            "inputs": dict(self.inputs),
            "colour_space": self.colour_space,
            "logs": list(self.logs),
            "wall_seconds": self.wall_seconds,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: object) -> Manifest:
        known = {"host", "level", "request_hash", "versions", "inputs", "colour_space", "logs", "wall_seconds", "notes"}
        if not isinstance(data, dict):
            raise CaptureSetError(f"{MANIFEST}: an object is expected, got {type(data).__name__}")
        unknown = sorted(set(data) - known)
        if unknown:
            raise CaptureSetError(f"{MANIFEST}: unknown field(s) {unknown}")
        missing = sorted({"host", "level", "request_hash"} - set(data))
        if missing:
            raise CaptureSetError(f"{MANIFEST}: missing field(s) {missing}")
        for name in ("versions", "inputs"):
            value = data.get(name, {})
            if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in value.items()
            ):
                raise CaptureSetError(f"{MANIFEST}: {name}: an object of strings is expected, got {value!r}")
        for name in ("logs", "notes"):
            value = data.get(name, [])
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise CaptureSetError(f"{MANIFEST}: {name}: a list of strings is expected, got {value!r}")
        for name in ("host", "level", "request_hash", "colour_space"):
            if name in data and not isinstance(data[name], str):
                raise CaptureSetError(f"{MANIFEST}: {name}: a string is expected, got {data[name]!r}")
        manifest = cls(
            host=data["host"],
            level=data["level"],
            request_hash=data["request_hash"],
            versions=dict(data.get("versions", {})),
            inputs=dict(data.get("inputs", {})),
            colour_space=data.get("colour_space", "unspecified"),
            logs=tuple(data.get("logs", ())),
            wall_seconds=data.get("wall_seconds", 0.0),
            notes=tuple(data.get("notes", ())),
        )
        manifest.validate()
        return manifest


@dataclass(frozen=True)
class CaptureSet:
    """A capture set read back: the request, the manifest and whichever pictures its level holds."""

    path: Path
    request: CaptureRequest
    manifest: Manifest
    scene: NDArray[np.float32] | None  # (H, W, 3) scene-linear
    display: NDArray[np.uint8] | None  # (H, W, 3)
    coverage: NDArray[np.bool_] | None  # (H, W)

    @property
    def level(self) -> str:
        return self.manifest.level


def _allowed_files(level: str, logs: tuple[str, ...]) -> frozenset[str]:
    return REQUIRED[level] | OPTIONAL[level] | frozenset(logs)


def _check_arrays(
    request: CaptureRequest,
    scene: NDArray | None,
    display: NDArray | None,
    coverage: NDArray | None,
) -> None:
    width, height = request.size
    if scene is not None and (scene.shape != (height, width, 3) or not np.issubdtype(scene.dtype, np.floating)):
        raise CaptureSetError(
            f"{SCENE}: float (H, W, 3) = {(height, width, 3)} is expected, got {scene.dtype} {scene.shape}"
        )
    if display is not None and (display.shape != (height, width, 3) or display.dtype != np.uint8):
        raise CaptureSetError(
            f"{DISPLAY}: uint8 (H, W, 3) = {(height, width, 3)} is expected, got {display.dtype} {display.shape}"
        )
    if coverage is not None and (coverage.shape != (height, width) or coverage.dtype != np.bool_):
        raise CaptureSetError(
            f"{COVERAGE}: bool (H, W) = {(height, width)} is expected, got {coverage.dtype} {coverage.shape}"
        )


def write(
    directory: Path,
    request: CaptureRequest,
    manifest: Manifest,
    scene: NDArray | None = None,
    display: NDArray | None = None,
    coverage: NDArray | None = None,
    logs: dict[str, str] | None = None,
) -> Path:
    """
    Write a capture set into ``directory`` (created if missing). The roles the manifest's level requires must be given,
    the arrays must match the request's size, the manifest must agree with the request, and ``logs`` must be exactly the
    names the manifest lists. A directory holding files that are not a previous capture set's is refused untouched.
    The new set is written beside it first and replaces the old only once it is whole, so a failed write leaves
    the previous capture intact.
    """
    manifest.validate()
    logs = logs or {}
    if manifest.request_hash != request.content_hash():
        raise CaptureSetError(
            f"{MANIFEST}: request_hash does not match the request ({request.id}): it was built from another"
        )
    if set(logs) != set(manifest.logs):
        raise CaptureSetError(f"logs: the manifest lists {sorted(manifest.logs)} but {sorted(logs)} were given")
    given = {REQUEST, MANIFEST}
    for role, value in ((SCENE, scene), (DISPLAY, display), (COVERAGE, coverage)):
        if value is not None:
            given.add(role)
    missing = REQUIRED[manifest.level] - given
    if missing:
        raise CaptureSetError(f"level {manifest.level} requires {sorted(missing)}, which were not given")
    extra = given - _allowed_files(manifest.level, ())
    if extra:
        raise CaptureSetError(
            f"level {manifest.level} holds no {sorted(extra)}: a set cannot carry more than its level"
        )
    _check_arrays(request, scene, display, coverage)
    directory = Path(directory)
    if directory.exists():
        owned = {REQUEST, SCENE, DISPLAY, COVERAGE, MANIFEST} | _previous_logs(directory)
        foreign = sorted(p.name for p in directory.iterdir() if p.name not in owned)
        if foreign:
            raise CaptureSetError(f"{directory}: holds {foreign}, which are not a capture set's; nothing was written")
    staging = directory.parent / f".{directory.name}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        (staging / REQUEST).write_text(request.to_json(), encoding="utf-8")
        if scene is not None:
            imageio.write_exr_rgb(staging / SCENE, np.asarray(scene, dtype=np.float32), half=False)
        if display is not None:
            png.write_png(staging / DISPLAY, display)
        if coverage is not None:
            png.write_png(staging / COVERAGE, coverage.astype(np.uint8) * 255)
        for name, text in logs.items():
            (staging / name).write_text(text, encoding="utf-8")
        manifest_text = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
        (staging / MANIFEST).write_text(manifest_text, encoding="utf-8")
        if directory.exists():  # the previous capture goes only now that its replacement is whole
            shutil.rmtree(directory)
        staging.replace(directory)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    _LOGGER.info(f"wrote capture set {directory} at level {manifest.level} for request {request.id} on {manifest.host}")
    return directory


def read(directory: Path) -> CaptureSet:
    """
    Read and validate a capture set: the manifest first (it names the level), then every role the level requires, the
    sizes against the request, and the request's hash against the manifest's. Anything wrong is a ``CaptureSetError``
    naming the role.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise CaptureSetError(f"{directory}: not a directory")
    manifest_path = directory / MANIFEST
    if not manifest_path.is_file():
        raise CaptureSetError(f"{MANIFEST}: missing from {directory}")
    try:
        manifest = Manifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CaptureSetError(f"{MANIFEST}: not valid JSON ({e})") from e
    present = {p.name for p in directory.iterdir() if p.is_file()}
    missing = REQUIRED[manifest.level] - present
    if missing:
        raise CaptureSetError(f"level {manifest.level} requires {sorted(missing)}, missing from {directory}")
    unknown = sorted(present - _allowed_files(manifest.level, manifest.logs))
    if unknown:
        raise CaptureSetError(f"{directory}: unknown file(s) {unknown} for level {manifest.level}")
    absent_logs = sorted(set(manifest.logs) - present)
    if absent_logs:
        raise CaptureSetError(f"{MANIFEST}: lists log(s) {absent_logs} that are not in {directory}")
    try:
        request = CaptureRequest.from_json((directory / REQUEST).read_text(encoding="utf-8"))
    except (RequestError, UnicodeDecodeError) as e:
        raise CaptureSetError(f"{REQUEST}: {e}") from e
    if request.content_hash() != manifest.request_hash:
        raise CaptureSetError(
            f"{REQUEST}: its hash differs from the manifest's request_hash; the set mixes two captures"
        )
    try:
        scene = imageio.read_exr_rgb(directory / SCENE) if SCENE in present else None
        display = png.read_png(directory / DISPLAY) if DISPLAY in present else None
        coverage_raw = png.read_png(directory / COVERAGE) if COVERAGE in present else None
    except (png.PngError, ValueError, OSError) as e:
        raise CaptureSetError(f"{directory}: a picture cannot be read ({type(e).__name__}: {e})") from e
    if coverage_raw is not None and (coverage_raw.ndim != 3 or coverage_raw.shape[2] != 1):
        raise CaptureSetError(f"{COVERAGE}: a one-channel PNG is expected, got shape {coverage_raw.shape}")
    coverage = None if coverage_raw is None else coverage_raw[..., 0] > 127
    _check_arrays(request, scene, display, coverage)
    return CaptureSet(directory, request, manifest, scene, display, coverage)
