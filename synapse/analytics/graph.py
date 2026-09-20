# synapse/analytics/graph.py
"""Concept graph algorithms, link parsing, and DAG operations for Synapse Cycle.

Algorithms live here as pure functions over ConceptGraph; data models live in synapse.schemas.
"""
from __future__ import annotations

import re
from collections import deque
from typing import Optional

from synapse.schemas import ConceptGraph, ConceptNode, GraphEdge

# Deterministic regex pattern matching wiki-style concept links, e.g. [[Concept Name]]
CONCEPT_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def parse_concept_links(markdown: str) -> list[str]:
    """Extracts all referenced concept names or identifiers inside [[...]] tags.

    Example:
        "Recursion uses [[Functions]] and [[Base Case]]." -> ["Functions", "Base Case"]
    """
    return CONCEPT_LINK_PATTERN.findall(markdown)


def get_prerequisites(graph: ConceptGraph, concept_id: str) -> list[ConceptNode]:
    """Returns all transitive prerequisites for a concept, nearest first.

    Nearest first: direct prerequisites are first, followed by their prerequisites,
    level by level (breadth-first traversal backwards along prerequisite edges).

    Args:
        graph: The validated ConceptGraph DAG.
        concept_id: The ID of the target concept.

    Returns:
        List of ConceptNodes representing transitive prerequisites, nearest first.
    """
    node_map = {n.id: n for n in graph.nodes}
    if concept_id not in node_map:
        return []

    # Map target -> list of direct prerequisite sources
    # In a prerequisite edge from_concept -> to_concept, from_concept is the prerequisite.
    prereq_sources: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for edge in graph.edges:
        if edge.relationship == "prerequisite":
            prereq_sources[edge.to_concept].append(edge.from_concept)

    visited: set[str] = set()
    queue = deque([concept_id])
    result: list[ConceptNode] = []

    while queue:
        current = queue.popleft()
        for prereq_id in prereq_sources.get(current, []):
            if prereq_id not in visited and prereq_id != concept_id:
                visited.add(prereq_id)
                if prereq_id in node_map:
                    result.append(node_map[prereq_id])
                queue.append(prereq_id)

    return result


def topological_sort(graph: ConceptGraph) -> list[ConceptNode]:
    """Returns all concept nodes in a valid topological ordering (Kahn's algorithm).

    If edge A -> B is a prerequisite, A must be learned before B, so A precedes B.

    Args:
        graph: The validated ConceptGraph DAG.

    Returns:
        List of all ConceptNodes sorted in valid learning dependency order.
    """
    node_map = {n.id: n for n in graph.nodes}
    all_ids = [n.id for n in graph.nodes]

    # Calculate indegree considering prerequisite edges (A -> B means B depends on A)
    indegree: dict[str, int] = {i: 0 for i in all_ids}
    outgoing: dict[str, list[str]] = {i: [] for i in all_ids}

    for edge in graph.edges:
        if edge.relationship == "prerequisite":
            outgoing[edge.from_concept].append(edge.to_concept)
            indegree[edge.to_concept] += 1

    # Ready nodes have 0 indegree (sorted for deterministic ordering)
    ready = deque(sorted([i for i, d in indegree.items() if d == 0]))
    ordered_ids: list[str] = []

    while ready:
        cur = ready.popleft()
        ordered_ids.append(cur)
        for nxt in sorted(outgoing[cur]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)

    if len(ordered_ids) != len(all_ids):
        raise ValueError("Cycle detected in ConceptGraph prerequisite edges")

    return [node_map[cid] for cid in ordered_ids]


def get_learning_path(graph: ConceptGraph, target_concept: str) -> list[ConceptNode]:
    """Returns the ordered learning path for a concept: prerequisites in order, target last.

    Args:
        graph: The validated ConceptGraph DAG.
        target_concept: The ID or name of the target concept.

    Returns:
        List of ConceptNodes in prerequisite order, ending with the target concept.
    """
    node_map = {n.id: n for n in graph.nodes}
    name_to_id = {n.name.lower(): n.id for n in graph.nodes}

    target_id = target_concept if target_concept in node_map else name_to_id.get(target_concept.lower())
    if not target_id or target_id not in node_map:
        return []

    # Get all transitive prerequisites
    prereq_nodes = get_prerequisites(graph, target_id)
    prereq_ids = {n.id for n in prereq_nodes}
    prereq_ids.add(target_id)

    # Full topological sort restricted to the target and its ancestors
    full_order = topological_sort(graph)
    subgraph_order = [n for n in full_order if n.id in prereq_ids]

    # Ensure target_node is last
    target_node = node_map[target_id]
    result = [n for n in subgraph_order if n.id != target_id]
    result.append(target_node)
    return result


def build_student_graph(
    student_id: str,
    notes: list[NoteVersion],
    all_concepts: list[ConceptNode],
) -> ConceptGraph:
    """Builds a student's personal ConceptGraph from their note versions.

    Rules:
    - Nodes: concepts the student has notes for (isolated nodes are preserved).
    - Edges: parsed from [[Concept]] links in the student's latest notes.
    - Edges to concepts that the student does not have notes for are silently dropped.
    - Preserves DAG validity and synchronizes node prerequisites.

    Args:
        student_id: The student identifier.
        notes: All note versions for this student.
        all_concepts: Master concept definitions list.

    Returns:
        A validated ConceptGraph.
    """
    # 1. Filter to student's notes and find latest version per concept
    student_notes = [n for n in notes if n.student_id == student_id]
    latest_notes: dict[str, NoteVersion] = {}
    for n in student_notes:
        if n.concept_id not in latest_notes or n.version > latest_notes[n.concept_id].version:
            latest_notes[n.concept_id] = n

    # 2. Match student concepts
    concept_by_id = {c.id: c for c in all_concepts}
    concept_by_name = {c.name.lower(): c for c in all_concepts}

    student_concept_ids = set(latest_notes.keys()) & set(concept_by_id.keys())
    active_concepts = {cid: concept_by_id[cid] for cid in student_concept_ids}

    # 3. Parse links and build candidate edges
    candidate_prereqs: dict[str, set[str]] = {cid: set() for cid in student_concept_ids}
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str]] = set()

    for cid, note in latest_notes.items():
        if cid not in active_concepts:
            continue
        links = parse_concept_links(note.markdown)
        for link in links:
            # Resolve target concept by ID or Name
            target_concept: Optional[ConceptNode] = None
            if link in concept_by_id:
                target_concept = concept_by_id[link]
            elif link.lower() in concept_by_name:
                target_concept = concept_by_name[link.lower()]

            # Only add edge if target concept is owned by student (in student's notes)
            if target_concept and target_concept.id in student_concept_ids and target_concept.id != cid:
                # Direction: from_concept (prerequisite) -> to_concept (dependent)
                # If note on concept cid references [[target]], target is a prerequisite for cid
                from_id = target_concept.id
                to_id = cid
                if (from_id, to_id) not in seen_edges:
                    seen_edges.add((from_id, to_id))
                    edges.append(
                        GraphEdge(
                            from_concept=from_id,
                            to_concept=to_id,
                            relationship="prerequisite",
                        )
                    )
                    candidate_prereqs[to_id].add(from_id)

    # 4. Construct nodes with synchronized prerequisites to satisfy ConceptGraph validator
    nodes = [
        ConceptNode(
            id=c.id,
            name=c.name,
            summary=c.summary,
            prerequisites=sorted(list(candidate_prereqs.get(c.id, set()))),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in active_concepts.values()
    ]

    return ConceptGraph(nodes=nodes, edges=edges)
