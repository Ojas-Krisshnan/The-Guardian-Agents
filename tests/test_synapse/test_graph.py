"""
Tests for Concept Graph traversal algorithms and parsing.
Authoritative contract: Contracts.md Sections C.2, D.2, F.4.
"""
import pytest
from synapse.analytics.graph import (
    get_learning_path,
    get_prerequisites,
    parse_graph,
    topological_sort,
)
from synapse.schemas import (
    CanonicalNote,
    ConceptGraph,
    ConceptNode,
    GraphEdge,
)


@pytest.fixture
def sample_graph():
    # A -> B -> C and A -> D
    nodes = [
        ConceptNode(id="A", name="Basics", summary="Fundamental base", prerequisites=[]),
        ConceptNode(id="B", name="Intermediates", summary="Next step", prerequisites=["A"]),
        ConceptNode(id="C", name="Advanced", summary="Final topic", prerequisites=["B"]),
        ConceptNode(id="D", name="Side Topic", summary="Alternative branch", prerequisites=["A"]),
    ]
    edges = [
        GraphEdge(from_concept="A", to_concept="B", relationship="prerequisite"),
        GraphEdge(from_concept="B", to_concept="C", relationship="prerequisite"),
        GraphEdge(from_concept="A", to_concept="D", relationship="prerequisite"),
    ]
    return ConceptGraph(nodes=nodes, edges=edges)


def test_topological_sort(sample_graph):
    """Verify topological sort places dependencies before dependents."""
    ordered = topological_sort(sample_graph)
    assert len(ordered) == 4
    ids = [n.id for n in ordered]
    # A must precede B and D; B must precede C
    assert ids.index("A") < ids.index("B")
    assert ids.index("A") < ids.index("D")
    assert ids.index("B") < ids.index("C")


def test_get_prerequisites(sample_graph):
    """Verify transitive prerequisites are correctly discovered in topological order."""
    prereqs_c = get_prerequisites(sample_graph, "C")
    prereq_ids = [n.id for n in prereqs_c]
    assert prereq_ids == ["A", "B"]

    prereqs_a = get_prerequisites(sample_graph, "A")
    assert prereqs_a == []


def test_get_learning_path(sample_graph):
    """Verify learning path provides complete ordered progression to target."""
    path = get_learning_path(sample_graph, "C")
    path_ids = [n.id for n in path]
    assert path_ids == ["A", "B", "C"]


def test_parse_graph_from_canonical_notes():
    """Verify parse_graph constructs validated ConceptGraph from CanonicalNote records."""
    notes = [
        CanonicalNote(
            concept_id="c_bio",
            markdown="# Biology\nFoundations.",
            extracted_concepts=[
                ConceptNode(id="cell", name="Cell", summary="Cell unit", prerequisites=[]),
                ConceptNode(id="organelle", name="Organelle", summary="Sub-unit", prerequisites=["cell"]),
            ],
            teacher_confirmed=True,
        )
    ]
    graph = parse_graph(notes)
    assert isinstance(graph, ConceptGraph)
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.edges[0].from_concept == "cell"
    assert graph.edges[0].to_concept == "organelle"


def test_cycle_detection():
    """Verify that cycles raise a validation error as required by ConceptGraph schema."""
    nodes = [
        ConceptNode(id="X", name="X", summary="X", prerequisites=["Y"]),
        ConceptNode(id="Y", name="Y", summary="Y", prerequisites=["X"]),
    ]
    edges = [
        GraphEdge(from_concept="Y", to_concept="X", relationship="prerequisite"),
        GraphEdge(from_concept="X", to_concept="Y", relationship="prerequisite"),
    ]
    with pytest.raises(ValueError, match="cycle"):
        ConceptGraph(nodes=nodes, edges=edges)
