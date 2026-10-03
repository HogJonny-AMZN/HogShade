"""
HogShade: the gallery manifest obeys its rules against the committed pictures, the page is current, and each
rule has a finding that names it.
Package: tests/test_generate_gallery
"""

from __future__ import annotations

import copy
import json
import struct
import sys
import zlib
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_gallery as gg


def _png(path: Path, width: int, height: int) -> None:
    """A minimal valid PNG of the given size (one grey channel, zero-filled)."""
    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


def test_committed_manifest_and_page_are_sound():
    findings, diff = gg.check()
    assert findings == [] and diff == "", (findings, diff[:500])


def test_every_committed_picture_is_within_the_rules():
    manifest = gg.load_manifest()
    rules = manifest["rules"]
    for section in manifest["sections"]:
        for picture in section["pictures"]:
            file = ROOT / picture["path"]
            size = gg.png_size(file)
            assert size is not None and max(size) <= rules["max_side"], picture["path"]
            assert file.stat().st_size <= rules["max_bytes"], picture["path"]


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    _png(tmp_path / "verification" / "a" / "one.png", 64, 32)
    _png(tmp_path / "verification" / "a" / "two.png", 64, 32)
    manifest = {
        "version": 1,
        "rules": {"format": "png", "max_side": 1024, "max_bytes": 1048576},
        "hosts": {"a": "host a"},
        "sections": [
            {
                "title": "T",
                "need": "N",
                "pictures": [
                    {"path": "verification/a/one.png", "host": "a", "feature": "f1", "caption": "c1", "made_by": "m"},
                    {"path": "verification/a/two.png", "host": "a", "feature": "f2", "caption": "c2", "made_by": "m"},
                ],
                "pairs": [{"left": "verification/a/one.png", "right": "verification/a/two.png", "caption": "p"}],
            }
        ],
        "wanted": ["w"],
    }
    (tmp_path / "verification" / "gallery.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "Docs").mkdir()
    return tmp_path


def _findings(corpus: Path, edit: Callable[[dict], None]) -> list[str]:
    manifest = json.loads((corpus / "verification" / "gallery.json").read_text(encoding="utf-8"))
    manifest = copy.deepcopy(manifest)
    edit(manifest)
    return [f.message for f in gg.check_manifest(manifest, corpus)]


def test_clean_corpus_writes_and_checks(corpus: Path):
    page = gg.write(corpus)
    assert page.read_text(encoding="utf-8").startswith(gg.HEADER)
    findings, diff = gg.check(corpus)
    assert findings == [] and diff == ""
    page.write_text("stale", encoding="utf-8")
    findings, diff = gg.check(corpus)
    assert findings == [] and "generated" in diff


def test_rules_each_have_a_finding(corpus: Path):
    def oversized(m):
        _png(corpus / "verification" / "a" / "big.png", 2048, 8)
        m["sections"][0]["pictures"].append(
            {"path": "verification/a/big.png", "host": "a", "feature": "f", "caption": "c", "made_by": "m"}
        )

    assert "2048x8 exceeds 1024 on a side" in _findings(corpus, oversized)

    def too_many_bytes(m):
        m["rules"]["max_bytes"] = 10

    assert any("bytes exceeds 10" in f for f in _findings(corpus, too_many_bytes))

    def missing_file(m):
        m["sections"][0]["pictures"][0]["path"] = "verification/a/none.png"

    assert "no such file" in _findings(corpus, missing_file)

    def not_png(m):
        (corpus / "verification" / "a" / "fake.png").write_bytes(b"not a png at all, just bytes")
        m["sections"][0]["pictures"][0]["path"] = "verification/a/fake.png"

    assert "not a PNG" in _findings(corpus, not_png)

    def outside(m):
        m["sections"][0]["pictures"][0]["path"] = "verification/../Docs/x.png"

    assert "path must lie under verification/, forward slashes only, no '..'" in _findings(corpus, outside)

    def backslash(m):
        m["sections"][0]["pictures"][0]["path"] = "verification/a\\..\\..\\x.png"

    assert "path must lie under verification/, forward slashes only, no '..'" in _findings(corpus, backslash)

    def wrong_extension(m):
        _png(corpus / "verification" / "a" / "one.jpg", 8, 8)
        m["sections"][0]["pictures"][0]["path"] = "verification/a/one.jpg"

    assert "the format is png" in _findings(corpus, wrong_extension)

    def bad_limit(m):
        m["rules"]["max_side"] = "big"

    assert "max_side must be a positive integer, not 'big'" in _findings(corpus, bad_limit)

    def section_not_an_object(m):
        m["sections"].append("a string")

    assert "must be an object, not str" in _findings(corpus, section_not_an_object)

    def rules_not_an_object(m):
        m["rules"] = "png"

    assert _findings(corpus, rules_not_an_object) == ["rules must be an object and sections a list"]

    def wanted_not_a_list(m):
        m["wanted"] = 5

    assert "wanted must be a list of strings" in _findings(corpus, wanted_not_a_list)

    def picture_not_an_object(m):
        m["sections"][0]["pictures"].append("verification/a/one.png")

    assert "must be an object, not str" in _findings(corpus, picture_not_an_object)

    def unknown_host(m):
        m["sections"][0]["pictures"][0]["host"] = "blender"

    assert any("host 'blender' is not one of" in f for f in _findings(corpus, unknown_host))

    def twice(m):
        m["sections"][0]["pictures"].append(dict(m["sections"][0]["pictures"][0]))

    assert "listed twice" in _findings(corpus, twice)

    def pair_unlisted(m):
        m["sections"][0]["pairs"][0]["right"] = "verification/a/three.png"

    assert "right is not a picture listed above it" in _findings(corpus, pair_unlisted)

    def no_caption(m):
        m["sections"][0]["pictures"][0]["caption"] = ""

    assert "missing or empty 'caption'" in _findings(corpus, no_caption)


def test_malformed_manifest_is_a_gallery_error(corpus: Path):
    (corpus / "verification" / "gallery.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(gg.GalleryError, match="not valid JSON at line 1"):
        gg.check(corpus)
    (corpus / "verification" / "gallery.json").write_text("[]", encoding="utf-8")
    with pytest.raises(gg.GalleryError, match="JSON object at the top level"):
        gg.write(corpus)


def test_write_refuses_findings_and_logs_counts(corpus: Path, caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO", logger=gg._MODULE_NAME):
        gg.write(corpus)
    assert "wrote gallery.md: 1 sections, 2 pictures, 1 pairs, 1 wanted" in caplog.text
    manifest = json.loads((corpus / "verification" / "gallery.json").read_text(encoding="utf-8"))
    manifest["sections"][0]["pictures"][0]["path"] = "verification/a/none.png"
    (corpus / "verification" / "gallery.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(gg.GalleryError, match="no such file"):
        gg.write(corpus)


def test_page_links_resolve_from_docs(corpus: Path):
    page = gg.write(corpus)
    text = page.read_text(encoding="utf-8")
    assert "](../verification/a/one.png)" in text and "## Wanted, not yet captured" in text
