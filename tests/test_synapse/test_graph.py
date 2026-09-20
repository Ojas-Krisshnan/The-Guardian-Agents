# tests/test_synapse/test_graph.py
"""Unit tests for concept link parsing, graph algorithms, and DAG construction."""
import pytest
from pydantic import ValidationError

from synapse.analytics.graph import (
    build_student_graph,
    get_learning_path,
    get_prerequisites,
    parse_concept_links,
    topological_sort,
)
from synapse.schemas import ConceptGraph, ConceptNode, GraphEdge, NoteVersion


def _make_concept(cid: str, name: str, prereqs: list[str] | None = None) -> ConceptNode:
    return ConceptNode(
        id=cid,
        name=name,
        summary=f"Summary of {name}",
        prerequisites=prereqs or [],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. LINK PARSING TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_parse_single_concept_link():
    """[[Functions]] is parsed accurately."""
    text = "In this lesson, we build upon [[Functions]]."
    assert parse_concept_links(text) == ["Functions"]


def test_parse_multiple_concept_links():
    """Multiple distinct [[...]] links are parsed in text order."""
    text = "To understand [[Recursion]], one must first master [[Functions]] and [[Variables]]."
    assert parse_concept_links(text) == ["Recursion", "Functions", "Variables"]


def test_parse_duplicate_concept_links():
    """Duplicate links are parsed as they occur without crashing or corruption."""
    text = "Review [[Functions]] carefully. Again, recall [[Functions]] in detail."
    assert parse_concept_links(text) == ["Functions", "Functions"]


def test_parse_no_concept_links():
    """Text without wiki links returns empty list."""
    text = "Just regular prose without any bracketed references."
    assert parse_concept_links(text) == []


# ══════════════════════════════════════════════════════════════════════════════
# 2. GRAPH ALGORITHMS TESTS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_dag() -> ConceptGraph:
    """Builds a 4-node DAG:
    Variables -> Functions -> Recursion -> Trees
    Isolated: Ethics
    """
    c_var = _make_concept("c_var", "Variables")
    c_func = _make_concept("c_func", "Functions", ["c_var"])
    c_rec = _make_concept("c_rec", "Recursion", ["c_func"])
    c_trees = _make_concept("c_trees", "Trees", ["c_rec"])
    c_ethics = _make_concept("c_ethics", "Ethics")

    edges = [
        GraphEdge(from_concept="c_var", to_concept="c_func", relationship="prerequisite"),
        GraphEdge(from_concept="c_func", to_concept="c_rec", relationship="prerequisite"),
        GraphEdge(from_concept="c_rec", to_concept="c_trees", relationship="prerequisite"),
    ]
    return ConceptGraph(
        nodes=[c_var, c_func, c_rec, c_trees, c_ethics],
        edges=edges,
    )


def test_get_prerequisites_nearest_first(sample_dag):
    """get_prerequisites returns transitive prerequisites in nearest-first order."""
    # Prerequisites of Trees: nearest is Recursion, then Functions, then Variables
    prereqs = get_prerequisites(sample_dag, "c_trees")
    ids = [n.id for n in prereqs]
    assert ids == ["c_rec", "c_func", "c_var"]


def test_get_prerequisites_leaf_or_isolated(sample_dag):
    """Node with no prerequisites returns empty list."""
    assert get_prerequisites(sample_dag, "c_var") == []
    assert get_prerequisites(sample_dag, "c_ethics") == []


def test_topological_sort(sample_dag):
    """topological_sort returns nodes satisfying all prerequisite constraints."""
    ordered = topological_sort(sample_dag)
    ids = [n.id for n in ordered]

    # Every prerequisite must appear before its dependent
    assert ids.index("c_var") < ids.index("c_func")
    assert ids.index("c_func") < ids.index("c_rec")
    assert ids.index("c_rec") < ids.index("c_trees")
    # Isolated node is included
    assert "c_ethics" in ids


def test_get_learning_path(sample_dag):
    """get_learning_path returns ancestors in dependency order, target last."""
    path = get_learning_path(sample_dag, "c_trees")
    ids = [n.id for n in path]
    assert ids == ["c_var", "c_func", "c_rec", "c_trees"]


def test_get_learning_path_by_name(sample_dag):
    """get_learning_path accepts concept name as target."""
    path = get_learning_path(sample_dag, "Recursion")
    ids = [n.id for n in path]
    assert ids == ["c_var", "c_func", "c_rec"]


def test_cycle_detection():
    """ConceptGraph validator detects prerequisite cycles and raises ValidationError."""
    a = _make_concept("a", "Alpha", ["b"])
    b = _make_concept("b", "Beta", ["a"])
    edges = [
        GraphEdge(from_concept="b", to_concept="a", relationship="prerequisite"),
        GraphEdge(from_concept="a", to_concept="b", relationship="prerequisite"),
    ]
    with pytest.raises(ValidationError):
        ConceptGraph(nodes=[a, b], edges=edges)


# ══════════════════════════════════════════════════════════════════════════════
# 3. BUILD STUDENT GRAPH TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_build_student_graph_valid_links_and_isolated_nodes():
    """Valid links create edges, isolated concepts remain nodes, unknown links dropped."""
    all_concepts = [
        _make_concept("c_rec", "Recursion"),
        _make_concept("c_func", "Functions"),
        _make_concept("c_iso", "IsolatedConcept"),
        _make_concept("c_other", "OtherConcept"),
    ]

    notes = [
        NoteVersion(
            student_id="student_1",
            concept_id="c_rec",
            version=1,
            markdown="Note referencing [[Functions]] and [[NonExistentConcept]].",
        ),
        NoteVersion(
            student_id="student_1",
            concept_id="c_func",
            version=1,
            markdown="Core functions note.",
        ),
        NoteVersion(
            student_id="student_1",
            concept_id="c_iso",
            version=1,
            markdown="Isolated note with no links.",
        ),
        # Student 2 note should not leak into Student 1 graph
        NoteVersion(
            student_id="student_2",
            concept_id="c_other",
            version=1,
            markdown="Student 2 note.",
        ),
    ]

    sg = build_student_graph("student_1", notes, all_concepts)

    node_ids = {n.id for n in sg.nodes}
    # Student 1 has notes for c_rec, c_func, and c_iso
    assert node_ids == {"c_rec", "c_func", "c_iso"}

    # Edge from Functions (prerequisite) -> Recursion
    assert len(sg.edges) == 1
    edge = sg.edges[0]
    assert edge.from_concept == "c_func"
    assert edge.to_concept == "c_rec"
    assert edge.relationship == "prerequisite"

    # NonExistentConcept must be silently dropped (no edge created)
    for e in sg.edges:
        assert "NonExistentConcept" not in (e.from_concept, e.to_concept)


def test_build_student_graph_latest_note_version():
    """Uses the latest note version for parsing links."""
    all_concepts = [
        _make_concept("c_rec", "Recursion"),
        _make_concept("c_func", "Functions"),
        _make_concept("c_var", "Variables"),
    ]

    notes = [
        NoteVersion(
            student_id="student_1",
            concept_id="c_rec",
            version=1,
            markdown="Version 1: only references [[Functions]].",
        ),
        NoteVersion(
            student_id="student_1",
            concept_id="c_rec",
            version=2,
            markdown="Version 2: references both [[Functions]] and [[Variables]].",
        ),
        NoteVersion(
            student_id="student_1",
            concept_id="c_func",
            version=1,
            markdown="Functions.",
        ),
        NoteVersion(
            student_id="student_1",
            concept_id="c_var",
            version=1,
            markdown="Variables.",
        ),
    ]

    sg = build_student_graph("student_1", notes, all_concepts)

    # In version 2, c_rec depends on both c_func and c_var
    target_rec = next(n for n in sg.nodes if n.id == "c_rec")
    assert set(target_rec.prerequisites) == {"c_func", "c_var"}
    assert len(sg.edges) == 2
