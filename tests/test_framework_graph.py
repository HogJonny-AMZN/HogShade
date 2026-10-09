"""
HogShade: tests for tools/render_framework_graph.py, on mutated copies of the data and on the committed graph.
Package: tests/test_framework_graph
"""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import render_framework_graph as rfg


@pytest.fixture(scope="module")
def data() -> dict:
    return rfg.load()


def _mutated(data: dict, mutate) -> list[str]:
    copied = copy.deepcopy(data)
    mutate(copied)
    return rfg.problems(copied)


def test_the_committed_graph_is_well_formed(data: dict) -> None:
    assert rfg.problems(data) == []


def test_the_committed_page_is_current() -> None:
    found, diff = rfg.check()
    assert found == [] and diff == "", diff[:2000]


def test_a_declared_relation_that_is_never_used_is_found(data: dict) -> None:
    def drop_reads(d: dict) -> None:
        d["edges"] = [e for e in d["edges"] if e["relation"] != "reads"]

    found = _mutated(data, drop_reads)
    assert "relation 'reads' is declared and never used" in found


def test_the_graph_names_no_project(data: dict) -> None:
    """The graph is project-agnostic: a repository's name belongs in `seen` as a letter, never in the text."""
    text = " ".join(f"{n['id']} {n['label']} {n['summary']}" for n in data["nodes"]).lower()
    for name in ("hogshade", "largeworlds", "spritejammer", "wgpu", "maya", "marmoset", "bats", "job_orchestrator"):
        assert name not in text


def test_a_duplicate_id_is_found(data: dict) -> None:
    found = _mutated(data, lambda d: d["nodes"].append(dict(d["nodes"][0])))
    assert any("duplicate node id" in f for f in found)


def test_an_edge_to_nowhere_is_found(data: dict) -> None:
    found = _mutated(data, lambda d: d["edges"].append({"from": "board", "to": "nowhere", "relation": "links-to"}))
    assert any("not a node" in f for f in found)


def test_an_unknown_relation_is_found(data: dict) -> None:
    found = _mutated(data, lambda d: d["edges"].append({"from": "board", "to": "gate", "relation": "loves"}))
    assert any("unknown relation" in f for f in found)


def test_an_orphan_node_is_found(data: dict) -> None:
    orphan = {"id": "lonely", "kind": "concept", "layer": "state", "label": "Lonely", "seen": "H", "summary": "x"}
    found = _mutated(data, lambda d: d["nodes"].append(orphan))
    assert found == ["node lonely has no edge"]


def test_a_bad_seen_string_is_found(data: dict) -> None:
    found = _mutated(data, lambda d: d["nodes"][0].update(seen="HX"))
    assert any("seen" in f for f in found)
    found = _mutated(data, lambda d: d["nodes"][0].update(seen="HH"))
    assert any("distinct" in f for f in found)


def test_a_self_edge_and_a_duplicate_edge_are_found(data: dict) -> None:
    found = _mutated(data, lambda d: d["edges"].append({"from": "board", "to": "board", "relation": "links-to"}))
    assert any("points at itself" in f for f in found)
    found = _mutated(data, lambda d: d["edges"].append(dict(d["edges"][0])))
    assert any("duplicate edge" in f for f in found)


def test_an_unknown_kind_or_layer_is_found(data: dict) -> None:
    assert any("unknown kind" in f for f in _mutated(data, lambda d: d["nodes"][0].update(kind="gizmo")))
    assert any("unknown layer" in f for f in _mutated(data, lambda d: d["nodes"][0].update(layer="attic")))


def test_a_non_kebab_id_or_a_mermaid_keyword_is_found(data: dict) -> None:
    found = _mutated(data, lambda d: d["nodes"][0].update(id="Entry File"))
    assert any("kebab-case" in f for f in found)
    found = _mutated(data, lambda d: d["nodes"][0].update(id="end"))
    assert any("Mermaid keyword" in f for f in found)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["nodes"].__setitem__(0, "a string"),
        lambda d: d["nodes"].__setitem__(0, None),
        lambda d: d["edges"].__setitem__(0, ["a", "b"]),
        lambda d: d["nodes"][0].update(seen=7),
        lambda d: d["nodes"][0].update(id=["x"]),
        lambda d: d["nodes"][0].update(kind=["artifact"]),
        lambda d: d["nodes"][0].update(label=3),
        lambda d: d["edges"][0].update(relation={"x": 1}),
        lambda d: d["edges"][0].update(**{"from": ["board"]}),
        lambda d: d.update(layers=None),
        lambda d: d.update(relations=None),
        lambda d: d.update(nodes=None),
        lambda d: d.update(edges=5),
        lambda d: d.update(kinds={"gizmo": "a kind the renderer cannot draw"}),
        lambda d: d["relations"].update(loves="a relation with no arrow"),
        lambda d: d["layers"].update(end="a layer named for a Mermaid keyword"),
        lambda d: d["layers"].update(**{"my layer": "a layer with a space"}),
    ],
)
def test_malformed_data_is_reported_never_a_traceback(data: dict, mutate) -> None:
    found = _mutated(data, mutate)
    assert found and all(isinstance(f, str) for f in found)


def test_data_that_is_not_an_object_is_reported() -> None:
    assert rfg.problems([]) == ["the data is not a JSON object"]
    assert rfg.problems("x") == ["the data is not a JSON object"]


def test_a_stale_page_is_a_diff(tmp_path: Path) -> None:
    knowledge = tmp_path / "Docs" / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "ai-first-framework.graph.json").write_text(
        (ROOT / "Docs/knowledge/ai-first-framework.graph.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    found, diff = rfg.check(tmp_path)  # no page yet
    assert found == [] and diff != ""
    rfg.write(tmp_path)
    assert rfg.check(tmp_path) == ([], "")
    page = knowledge / "ai-first-framework-graph.md"
    page.write_text(page.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
    assert rfg.check(tmp_path)[1] != ""


def test_the_page_draws_every_node_and_is_mermaid_safe(data: dict) -> None:
    page = rfg.render(data)
    for n in data["nodes"]:
        assert f"`{n['id']}`" in page  # the table row
        assert rfg._mid(n["id"]) in page
    assert page.count("```mermaid") == len(data["layers"]) + 1  # the overview and one per layer
    assert page.count("```") % 2 == 0
    for word in ("end", "graph", "subgraph", "class", "style", "click", "default"):
        assert not any(rfg._mid(n["id"]) == word for n in data["nodes"]), word


def _graph_in(root: Path, text: str | None = None) -> Path:
    knowledge = root / "Docs" / "knowledge"
    knowledge.mkdir(parents=True)
    source = (ROOT / "Docs/knowledge/ai-first-framework.graph.json").read_text(encoding="utf-8")
    (knowledge / "ai-first-framework.graph.json").write_text(text or source, encoding="utf-8")
    return knowledge


def test_main_exit_codes(tmp_path: Path) -> None:
    assert rfg.main(["--check"]) == 0  # the committed graph and page
    knowledge = _graph_in(tmp_path)
    assert rfg.main(["--check"], root=tmp_path) == 1  # no page yet: stale
    assert rfg.main(["--write"], root=tmp_path) == 0
    assert rfg.main(["--check"], root=tmp_path) == 0
    (knowledge / "ai-first-framework-graph.md").write_bytes(bytes([0xFF, 0xFE]) + b" not utf-8")
    assert rfg.main(["--check"], root=tmp_path) == 1  # an unreadable page is reported, not a traceback


def test_main_reports_a_broken_or_missing_data_file(tmp_path: Path) -> None:
    assert rfg.main(["--check"], root=tmp_path) == 1  # no data file at all
    _graph_in(tmp_path / "bad", '{"layers": {}, "kinds": {}, "relations": {}, "nodes": [], "edges": 5}')
    assert rfg.main(["--check"], root=tmp_path / "bad") == 1
    assert rfg.main(["--write"], root=tmp_path / "bad") == 2


def test_a_crlf_page_is_current(tmp_path: Path) -> None:
    """A Windows working copy checks out CRLF; `--check` must call it current, and a real drift still stale."""
    knowledge = _graph_in(tmp_path)
    rfg.write(tmp_path)
    page = knowledge / "ai-first-framework-graph.md"
    lf, crlf = bytes([10]), bytes([13, 10])
    page.write_bytes(page.read_bytes().replace(lf, crlf))
    assert crlf in page.read_bytes()
    assert rfg.check(tmp_path) == ([], "")
    page.write_bytes(page.read_bytes() + b"drift" + crlf)
    assert rfg.check(tmp_path)[1] != ""
