"""
Concept graph parsing and traversal algorithms.
Authoritative contract: Contracts.md Sections C.2, D.2, F.4.
"""
from __future__ import annotations

from typing import Any
from synapse.schemas import (
    CanonicalNote,
    ConceptGraph,
    ConceptNode,
    GraphEdge,
)


def parse_graph(notes: list[CanonicalNote | dict[str, Any]]) -> ConceptGraph:
    """Construct a validated ConceptGraph from canonical notes and their extracted concepts."""
    nodes_map: dict[str, ConceptNode] = {}

    for note in notes:
        extracted = note.extracted_concepts if isinstance(note, CanonicalNote) else note.get("extracted_concepts", [])
        for c in extracted:
            node = ConceptNode.model_validate(c) if isinstance(c, dict) else c
            if node.id not in nodes_map:
                nodes_map[node.id] = node

    # If no extracted concepts, create fallback nodes for the note's concept_id
    if not nodes_map:
        for note in notes:
            cid = note.concept_id if isinstance(note, CanonicalNote) else note.get("concept_id", "core_concept")
            if cid not in nodes_map:
                nodes_map[cid] = ConceptNode(id=cid, name=cid.replace("_", " ").title(), summary=f"Core concept for {cid}")

    # Build clean prerequisites only referencing known nodes
    nodes: list[ConceptNode] = []
    for node in nodes_map.values():
        valid_prereqs = [p for p in node.prerequisites if p in nodes_map and p != node.id]
        clean_node = ConceptNode(
            id=node.id,
            name=node.name,
            summary=node.summary,
            prerequisites=valid_prereqs,
        )
        nodes.append(clean_node)

    # Build edges matching prerequisites exactly as required by ConceptGraph validator
    edges: list[GraphEdge] = []
    for node in nodes:
        for p in node.prerequisites:
            edges.append(
                GraphEdge(
                    from_concept=p,
                    to_concept=node.id,
                    relationship="prerequisite",
                )
            )

    return ConceptGraph(nodes=nodes, edges=edges)


def topological_sort(graph: ConceptGraph) -> list[ConceptNode]:
    """Sort graph nodes in topological order using Kahn's algorithm (dependencies first)."""
    node_map = {n.id: n for n in graph.nodes}
    indegree = {n.id: 0 for n in graph.nodes}
    outgoing: dict[str, list[str]] = {n.id: [] for n in graph.nodes}

    for e in graph.edges:
        if e.relationship == "prerequisite":
            outgoing[e.from_concept].append(e.to_concept)
            indegree[e.to_concept] += 1

    ready = [nid for nid, deg in indegree.items() if deg == 0]
    result: list[ConceptNode] = []

    while ready:
        ready.sort(key=lambda nid: node_map[nid].name)  # Deterministic tie-breaking
        cur = ready.pop(0)
        result.append(node_map[cur])
        for nxt in outgoing[cur]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)

    if len(result) != len(graph.nodes):
        raise ValueError("Cannot topologically sort a graph with cycles.")

    return result


def get_prerequisites(graph: ConceptGraph, concept_id: str) -> list[ConceptNode]:
    """Return all transitive prerequisites needed before learning concept_id."""
    node_map = {n.id: n for n in graph.nodes}
    if concept_id not in node_map:
        return []

    # Map target -> list of prerequisites (incoming edges)
    incoming: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for e in graph.edges:
        if e.relationship == "prerequisite":
            incoming[e.to_concept].append(e.from_concept)

    prereq_ids: set[str] = set()
    stack = list(incoming.get(concept_id, []))

    while stack:
        curr = stack.pop()
        if curr not in prereq_ids and curr in node_map:
            prereq_ids.add(curr)
            stack.extend(incoming.get(curr, []))

    # Return in topological order
    sorted_all = topological_sort(graph)
    return [n for n in sorted_all if n.id in prereq_ids]


def get_learning_path(graph: ConceptGraph, target_concept: str) -> list[ConceptNode]:
    """Return sequence of concepts to learn in topological order to master target_concept."""
    node_map = {n.id: n for n in graph.nodes}
    if target_concept not in node_map:
        return []

    prereqs = get_prerequisites(graph, target_concept)
    return prereqs + [node_map[target_concept]]
