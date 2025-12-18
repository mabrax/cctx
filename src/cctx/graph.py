"""Graph operations for Living Context dependency management.

Provides functions for:
- Graph generation and persistence (JSON format)
- Graph traversal (transitive dependencies, dependents, cycle detection)
- Graph analysis (topological order, root/leaf systems)

Design decisions:
- Uses iterative algorithms to avoid stack overflow on deep graphs
- Caches database queries where appropriate for efficiency
- Handles cyclic dependencies gracefully (no infinite loops)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cctx.crud import list_systems
from cctx.database import ContextDB


class GraphError(Exception):
    """Base exception for graph-related errors."""


class CyclicDependencyError(GraphError):
    """Raised when a cyclic dependency prevents an operation."""


def _build_adjacency_maps(
    db: ContextDB,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build adjacency maps for dependencies and dependents.

    Performs a single query to get all dependencies, then builds
    both forward (dependencies) and reverse (dependents) adjacency maps.

    Args:
        db: Database connection.

    Returns:
        Tuple of (dependencies_map, dependents_map) where:
        - dependencies_map[system] = list of systems it depends on
        - dependents_map[system] = list of systems that depend on it
    """
    # Get all systems first to ensure all nodes exist in maps
    all_systems = list_systems(db)
    system_paths = {s["path"] for s in all_systems}

    dependencies_map: dict[str, list[str]] = {path: [] for path in system_paths}
    dependents_map: dict[str, list[str]] = {path: [] for path in system_paths}

    # Single query for all dependencies
    results = db.fetchall(
        """
        SELECT system_path, depends_on
        FROM system_dependencies
        ORDER BY system_path, depends_on
        """
    )

    for row in results:
        system_path = row["system_path"]
        depends_on = row["depends_on"]
        if system_path in dependencies_map:
            dependencies_map[system_path].append(depends_on)
        if depends_on in dependents_map:
            dependents_map[depends_on].append(system_path)

    return dependencies_map, dependents_map


def _build_system_names(db: ContextDB) -> dict[str, str]:
    """Build a mapping of system paths to names.

    Args:
        db: Database connection.

    Returns:
        Dictionary mapping system path to system name.
    """
    systems = list_systems(db)
    return {s["path"]: s["name"] for s in systems}


# Graph Generation Functions


def generate_graph(db: ContextDB) -> list[dict[str, Any]]:
    """Generate full dependency graph from database.

    Queries all systems and their dependencies to build a complete
    graph representation suitable for JSON serialization.

    Args:
        db: Database connection.

    Returns:
        List of graph nodes, each containing:
        - system: The system path
        - name: The system name
        - dependencies: List of system paths this system depends on
        - dependents: List of system paths that depend on this system
    """
    dependencies_map, dependents_map = _build_adjacency_maps(db)
    system_names = _build_system_names(db)

    graph: list[dict[str, Any]] = []
    for system_path in sorted(dependencies_map.keys()):
        node: dict[str, Any] = {
            "system": system_path,
            "name": system_names.get(system_path, ""),
            "dependencies": sorted(dependencies_map[system_path]),
            "dependents": sorted(dependents_map[system_path]),
        }
        graph.append(node)

    return graph


def save_graph(graph: list[dict[str, Any]], path: Path) -> None:
    """Save graph to JSON file.

    Args:
        graph: Graph data as returned by generate_graph().
        path: Path to save the JSON file.

    Raises:
        OSError: If file cannot be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Trailing newline


def load_graph(path: Path) -> list[dict[str, Any]]:
    """Load graph from JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Graph data as list of node dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    with path.open("r", encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
    return data


# Graph Traversal Functions


def get_all_dependencies(db: ContextDB, system_path: str) -> set[str]:
    """Get all transitive dependencies of a system.

    Computes the transitive closure of dependencies - all systems
    that this system directly or indirectly depends on.

    Uses iterative BFS to avoid stack overflow on deep graphs
    and handles cycles gracefully.

    Args:
        db: Database connection.
        system_path: Path of the system to query.

    Returns:
        Set of all system paths that system_path depends on
        (directly or transitively). Does not include system_path itself
        unless there's a cycle.
    """
    dependencies_map, _ = _build_adjacency_maps(db)

    if system_path not in dependencies_map:
        return set()

    visited: set[str] = set()
    to_visit: list[str] = list(dependencies_map.get(system_path, []))

    while to_visit:
        current = to_visit.pop()
        if current in visited:
            continue
        visited.add(current)
        # Add dependencies of current to visit queue
        for dep in dependencies_map.get(current, []):
            if dep not in visited:
                to_visit.append(dep)

    return visited


def get_all_dependents(db: ContextDB, system_path: str) -> set[str]:
    """Get all systems that transitively depend on this system.

    Computes the reverse transitive closure - all systems that
    directly or indirectly depend on the given system.

    Uses iterative BFS to avoid stack overflow on deep graphs
    and handles cycles gracefully.

    Args:
        db: Database connection.
        system_path: Path of the system to query.

    Returns:
        Set of all system paths that depend on system_path
        (directly or transitively). Does not include system_path itself
        unless there's a cycle.
    """
    _, dependents_map = _build_adjacency_maps(db)

    if system_path not in dependents_map:
        return set()

    visited: set[str] = set()
    to_visit: list[str] = list(dependents_map.get(system_path, []))

    while to_visit:
        current = to_visit.pop()
        if current in visited:
            continue
        visited.add(current)
        # Add dependents of current to visit queue
        for dep in dependents_map.get(current, []):
            if dep not in visited:
                to_visit.append(dep)

    return visited


def detect_cycles(db: ContextDB) -> list[list[str]]:
    """Find all circular dependencies in the graph.

    Uses Tarjan's algorithm to find strongly connected components (SCCs)
    with more than one node, which represent cycles.

    Args:
        db: Database connection.

    Returns:
        List of cycles, where each cycle is a list of system paths
        forming a circular dependency. Returns empty list if no cycles.
        Self-loops (A depends on A) are also detected.
    """
    dependencies_map, _ = _build_adjacency_maps(db)

    if not dependencies_map:
        return []

    # Tarjan's algorithm for finding strongly connected components
    index_counter = [0]
    stack: list[str] = []
    lowlinks: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        for successor in dependencies_map.get(node, []):
            if successor not in index:
                strongconnect(successor)
                lowlinks[node] = min(lowlinks[node], lowlinks[successor])
            elif on_stack.get(successor, False):
                lowlinks[node] = min(lowlinks[node], index[successor])

        # If node is a root node, pop the stack and generate an SCC
        if lowlinks[node] == index[node]:
            scc: list[str] = []
            while True:
                successor = stack.pop()
                on_stack[successor] = False
                scc.append(successor)
                if successor == node:
                    break
            # Only report SCCs with cycles (size > 1 or self-loop)
            if len(scc) > 1:
                sccs.append(sorted(scc))
            elif len(scc) == 1 and scc[0] in dependencies_map.get(scc[0], []):
                # Self-loop
                sccs.append(scc)

    for node in dependencies_map:
        if node not in index:
            strongconnect(node)

    return sorted(sccs, key=lambda x: (len(x), x[0] if x else ""))


# Graph Analysis Functions


def get_topological_order(db: ContextDB) -> list[str]:
    """Get systems sorted by dependency order (leaf first).

    Returns a topological ordering where systems with no dependencies
    come first, followed by systems that only depend on already-listed
    systems.

    Uses Kahn's algorithm for topological sorting.

    Args:
        db: Database connection.

    Returns:
        List of system paths in topological order (dependencies first).

    Raises:
        CyclicDependencyError: If the graph contains cycles, making
            topological ordering impossible.
    """
    dependencies_map, _ = _build_adjacency_maps(db)

    if not dependencies_map:
        return []

    # Calculate in-degree for each node (number of unresolved dependencies)
    in_degree: dict[str, int] = {node: len(deps) for node, deps in dependencies_map.items()}

    # Start with nodes that have no dependencies (in_degree == 0)
    queue: list[str] = sorted([node for node, degree in in_degree.items() if degree == 0])
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)

        # For each system that depends on this node, reduce its in-degree
        for other_node, deps in dependencies_map.items():
            if node in deps and other_node not in result:
                in_degree[other_node] -= 1
                if in_degree[other_node] == 0 and other_node not in queue:
                    # Insert in sorted order to maintain deterministic output
                    queue.append(other_node)
                    queue.sort()

    if len(result) != len(dependencies_map):
        cycles = detect_cycles(db)
        cycle_info = ", ".join(str(c) for c in cycles) if cycles else "unknown"
        raise CyclicDependencyError(
            f"Cannot compute topological order: graph contains cycles ({cycle_info})"
        )

    return result


def get_root_systems(db: ContextDB) -> list[str]:
    """Get systems with no dependencies.

    Root systems are the foundation of the dependency graph - they
    don't depend on any other systems.

    Args:
        db: Database connection.

    Returns:
        List of system paths that have no dependencies, sorted alphabetically.
    """
    dependencies_map, _ = _build_adjacency_maps(db)
    return sorted([path for path, deps in dependencies_map.items() if not deps])


def get_leaf_systems(db: ContextDB) -> list[str]:
    """Get systems nothing depends on.

    Leaf systems are at the top of the dependency graph - no other
    systems depend on them.

    Args:
        db: Database connection.

    Returns:
        List of system paths that no other system depends on,
        sorted alphabetically.
    """
    _, dependents_map = _build_adjacency_maps(db)
    return sorted([path for path, deps in dependents_map.items() if not deps])
