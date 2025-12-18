"""Tests for cctx.graph module."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from cctx.crud import add_dependency, create_system
from cctx.database import ContextDB
from cctx.graph import (
    CyclicDependencyError,
    GraphError,
    detect_cycles,
    generate_graph,
    get_all_dependencies,
    get_all_dependents,
    get_leaf_systems,
    get_root_systems,
    get_topological_order,
    load_graph,
    save_graph,
)


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def initialized_db(temp_db_path: Path) -> Generator[ContextDB, None, None]:
    """Create a connected ContextDB instance."""
    with ContextDB(temp_db_path) as db:
        yield db


@pytest.fixture
def diamond_graph(initialized_db: ContextDB) -> ContextDB:
    """Create a diamond dependency graph.

    Structure:
        ui
       /  \\
      api  cli
       \\  /
        core

    ui depends on api and cli
    api depends on core
    cli depends on core
    """
    with initialized_db.transaction():
        create_system(initialized_db, "src/systems/core", "Core System")
        create_system(initialized_db, "src/systems/api", "API System")
        create_system(initialized_db, "src/systems/cli", "CLI System")
        create_system(initialized_db, "src/systems/ui", "UI System")

        add_dependency(initialized_db, "src/systems/api", "src/systems/core")
        add_dependency(initialized_db, "src/systems/cli", "src/systems/core")
        add_dependency(initialized_db, "src/systems/ui", "src/systems/api")
        add_dependency(initialized_db, "src/systems/ui", "src/systems/cli")

    return initialized_db


@pytest.fixture
def linear_graph(initialized_db: ContextDB) -> ContextDB:
    """Create a linear dependency graph.

    Structure: a -> b -> c -> d
    (a depends on b, b depends on c, c depends on d)
    """
    with initialized_db.transaction():
        create_system(initialized_db, "src/systems/a", "System A")
        create_system(initialized_db, "src/systems/b", "System B")
        create_system(initialized_db, "src/systems/c", "System C")
        create_system(initialized_db, "src/systems/d", "System D")

        add_dependency(initialized_db, "src/systems/a", "src/systems/b")
        add_dependency(initialized_db, "src/systems/b", "src/systems/c")
        add_dependency(initialized_db, "src/systems/c", "src/systems/d")

    return initialized_db


@pytest.fixture
def cyclic_graph(initialized_db: ContextDB) -> ContextDB:
    """Create a graph with a cycle.

    Structure: a -> b -> c -> a (cycle)
    """
    with initialized_db.transaction():
        create_system(initialized_db, "src/systems/a", "System A")
        create_system(initialized_db, "src/systems/b", "System B")
        create_system(initialized_db, "src/systems/c", "System C")

        add_dependency(initialized_db, "src/systems/a", "src/systems/b")
        add_dependency(initialized_db, "src/systems/b", "src/systems/c")
        add_dependency(initialized_db, "src/systems/c", "src/systems/a")

    return initialized_db


class TestGraphExceptions:
    """Tests for graph exception hierarchy."""

    def test_graph_error_is_exception(self) -> None:
        """Test GraphError inherits from Exception."""
        assert issubclass(GraphError, Exception)

    def test_cyclic_dependency_error_is_graph_error(self) -> None:
        """Test CyclicDependencyError inherits from GraphError."""
        assert issubclass(CyclicDependencyError, GraphError)


class TestGenerateGraph:
    """Tests for generate_graph function."""

    def test_generate_graph_empty(self, initialized_db: ContextDB) -> None:
        """Test generating graph with no systems."""
        graph = generate_graph(initialized_db)
        assert graph == []

    def test_generate_graph_single_system(self, initialized_db: ContextDB) -> None:
        """Test generating graph with single system."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        graph = generate_graph(initialized_db)
        assert len(graph) == 1
        assert graph[0]["system"] == "src/systems/auth"
        assert graph[0]["name"] == "Auth System"
        assert graph[0]["dependencies"] == []
        assert graph[0]["dependents"] == []

    def test_generate_graph_with_dependencies(self, initialized_db: ContextDB) -> None:
        """Test generating graph with dependencies."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        graph = generate_graph(initialized_db)
        assert len(graph) == 2

        # Find nodes by system path
        api_node = next(n for n in graph if n["system"] == "src/systems/api")
        auth_node = next(n for n in graph if n["system"] == "src/systems/auth")

        assert api_node["dependencies"] == ["src/systems/auth"]
        assert api_node["dependents"] == []
        assert auth_node["dependencies"] == []
        assert auth_node["dependents"] == ["src/systems/api"]

    def test_generate_graph_diamond(self, diamond_graph: ContextDB) -> None:
        """Test generating diamond-shaped graph."""
        graph = generate_graph(diamond_graph)
        assert len(graph) == 4

        core = next(n for n in graph if n["system"] == "src/systems/core")
        api = next(n for n in graph if n["system"] == "src/systems/api")
        cli = next(n for n in graph if n["system"] == "src/systems/cli")
        ui = next(n for n in graph if n["system"] == "src/systems/ui")

        assert core["dependencies"] == []
        assert sorted(core["dependents"]) == ["src/systems/api", "src/systems/cli"]

        assert api["dependencies"] == ["src/systems/core"]
        assert api["dependents"] == ["src/systems/ui"]

        assert cli["dependencies"] == ["src/systems/core"]
        assert cli["dependents"] == ["src/systems/ui"]

        assert sorted(ui["dependencies"]) == ["src/systems/api", "src/systems/cli"]
        assert ui["dependents"] == []

    def test_generate_graph_sorted_by_path(self, initialized_db: ContextDB) -> None:
        """Test graph nodes are sorted by system path."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/zebra", "Z System")
            create_system(initialized_db, "src/systems/apple", "A System")
            create_system(initialized_db, "src/systems/banana", "B System")

        graph = generate_graph(initialized_db)
        paths = [n["system"] for n in graph]
        assert paths == [
            "src/systems/apple",
            "src/systems/banana",
            "src/systems/zebra",
        ]


class TestSaveGraph:
    """Tests for save_graph function."""

    def test_save_graph_creates_file(self, temp_dir: Path) -> None:
        """Test save_graph creates JSON file."""
        graph = [{"system": "test", "name": "Test", "dependencies": [], "dependents": []}]
        path = temp_dir / "graph.json"

        save_graph(graph, path)

        assert path.exists()

    def test_save_graph_valid_json(self, temp_dir: Path) -> None:
        """Test saved file is valid JSON."""
        graph = [{"system": "test", "name": "Test", "dependencies": ["a"], "dependents": ["b"]}]
        path = temp_dir / "graph.json"

        save_graph(graph, path)

        with path.open() as f:
            loaded = json.load(f)
        assert loaded == graph

    def test_save_graph_creates_parent_dirs(self, temp_dir: Path) -> None:
        """Test save_graph creates parent directories."""
        graph = [{"system": "test", "name": "Test", "dependencies": [], "dependents": []}]
        path = temp_dir / "nested" / "dir" / "graph.json"

        save_graph(graph, path)

        assert path.exists()

    def test_save_graph_indented(self, temp_dir: Path) -> None:
        """Test saved file is indented for readability."""
        graph = [{"system": "test", "name": "Test", "dependencies": [], "dependents": []}]
        path = temp_dir / "graph.json"

        save_graph(graph, path)

        content = path.read_text()
        assert "\n" in content
        assert "  " in content  # 2-space indent

    def test_save_graph_trailing_newline(self, temp_dir: Path) -> None:
        """Test saved file has trailing newline."""
        graph = [{"system": "test", "name": "Test", "dependencies": [], "dependents": []}]
        path = temp_dir / "graph.json"

        save_graph(graph, path)

        content = path.read_text()
        assert content.endswith("\n")


class TestLoadGraph:
    """Tests for load_graph function."""

    def test_load_graph_basic(self, temp_dir: Path) -> None:
        """Test loading a graph file."""
        graph = [{"system": "test", "name": "Test", "dependencies": [], "dependents": []}]
        path = temp_dir / "graph.json"
        path.write_text(json.dumps(graph))

        loaded = load_graph(path)

        assert loaded == graph

    def test_load_graph_nonexistent_raises(self, temp_dir: Path) -> None:
        """Test loading nonexistent file raises FileNotFoundError."""
        path = temp_dir / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            load_graph(path)

    def test_load_graph_invalid_json_raises(self, temp_dir: Path) -> None:
        """Test loading invalid JSON raises JSONDecodeError."""
        path = temp_dir / "invalid.json"
        path.write_text("not valid json")

        with pytest.raises(json.JSONDecodeError):
            load_graph(path)

    def test_load_graph_roundtrip(self, temp_dir: Path, diamond_graph: ContextDB) -> None:
        """Test save/load roundtrip preserves data."""
        graph = generate_graph(diamond_graph)
        path = temp_dir / "graph.json"

        save_graph(graph, path)
        loaded = load_graph(path)

        assert loaded == graph


class TestGetAllDependencies:
    """Tests for get_all_dependencies function."""

    def test_get_all_dependencies_empty(self, initialized_db: ContextDB) -> None:
        """Test with nonexistent system."""
        deps = get_all_dependencies(initialized_db, "nonexistent")
        assert deps == set()

    def test_get_all_dependencies_no_deps(self, initialized_db: ContextDB) -> None:
        """Test system with no dependencies."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        deps = get_all_dependencies(initialized_db, "src/systems/auth")
        assert deps == set()

    def test_get_all_dependencies_direct_only(self, initialized_db: ContextDB) -> None:
        """Test system with only direct dependencies."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            create_system(initialized_db, "src/systems/db", "DB System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/api", "src/systems/db")

        deps = get_all_dependencies(initialized_db, "src/systems/api")
        assert deps == {"src/systems/auth", "src/systems/db"}

    def test_get_all_dependencies_transitive(self, linear_graph: ContextDB) -> None:
        """Test transitive dependency resolution."""
        # a -> b -> c -> d
        deps = get_all_dependencies(linear_graph, "src/systems/a")
        assert deps == {"src/systems/b", "src/systems/c", "src/systems/d"}

    def test_get_all_dependencies_diamond(self, diamond_graph: ContextDB) -> None:
        """Test diamond-shaped transitive dependencies."""
        # ui depends on api, cli; both depend on core
        deps = get_all_dependencies(diamond_graph, "src/systems/ui")
        assert deps == {"src/systems/api", "src/systems/cli", "src/systems/core"}

    def test_get_all_dependencies_handles_cycle(self, cyclic_graph: ContextDB) -> None:
        """Test cycle detection doesn't infinite loop."""
        # a -> b -> c -> a
        deps = get_all_dependencies(cyclic_graph, "src/systems/a")
        assert deps == {"src/systems/a", "src/systems/b", "src/systems/c"}

    def test_get_all_dependencies_self_loop(self, initialized_db: ContextDB) -> None:
        """Test self-referential dependency."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            add_dependency(initialized_db, "src/systems/a", "src/systems/a")

        deps = get_all_dependencies(initialized_db, "src/systems/a")
        assert deps == {"src/systems/a"}


class TestGetAllDependents:
    """Tests for get_all_dependents function."""

    def test_get_all_dependents_empty(self, initialized_db: ContextDB) -> None:
        """Test with nonexistent system."""
        deps = get_all_dependents(initialized_db, "nonexistent")
        assert deps == set()

    def test_get_all_dependents_no_dependents(self, initialized_db: ContextDB) -> None:
        """Test system with no dependents."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        deps = get_all_dependents(initialized_db, "src/systems/auth")
        assert deps == set()

    def test_get_all_dependents_direct_only(self, initialized_db: ContextDB) -> None:
        """Test system with only direct dependents."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/cli", "CLI System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/cli", "src/systems/auth")

        deps = get_all_dependents(initialized_db, "src/systems/auth")
        assert deps == {"src/systems/api", "src/systems/cli"}

    def test_get_all_dependents_transitive(self, linear_graph: ContextDB) -> None:
        """Test transitive dependent resolution."""
        # a -> b -> c -> d
        deps = get_all_dependents(linear_graph, "src/systems/d")
        assert deps == {"src/systems/a", "src/systems/b", "src/systems/c"}

    def test_get_all_dependents_diamond(self, diamond_graph: ContextDB) -> None:
        """Test diamond-shaped transitive dependents."""
        # core is depended on by api, cli; both depended on by ui
        deps = get_all_dependents(diamond_graph, "src/systems/core")
        assert deps == {"src/systems/api", "src/systems/cli", "src/systems/ui"}

    def test_get_all_dependents_handles_cycle(self, cyclic_graph: ContextDB) -> None:
        """Test cycle detection doesn't infinite loop."""
        # a -> b -> c -> a
        deps = get_all_dependents(cyclic_graph, "src/systems/a")
        assert deps == {"src/systems/a", "src/systems/b", "src/systems/c"}

    def test_get_all_dependents_self_loop(self, initialized_db: ContextDB) -> None:
        """Test self-referential dependency."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            add_dependency(initialized_db, "src/systems/a", "src/systems/a")

        deps = get_all_dependents(initialized_db, "src/systems/a")
        assert deps == {"src/systems/a"}


class TestDetectCycles:
    """Tests for detect_cycles function."""

    def test_detect_cycles_empty(self, initialized_db: ContextDB) -> None:
        """Test with empty graph."""
        cycles = detect_cycles(initialized_db)
        assert cycles == []

    def test_detect_cycles_no_cycles(self, diamond_graph: ContextDB) -> None:
        """Test acyclic graph returns empty."""
        cycles = detect_cycles(diamond_graph)
        assert cycles == []

    def test_detect_cycles_linear_no_cycles(self, linear_graph: ContextDB) -> None:
        """Test linear graph has no cycles."""
        cycles = detect_cycles(linear_graph)
        assert cycles == []

    def test_detect_cycles_simple_cycle(self, cyclic_graph: ContextDB) -> None:
        """Test detecting a simple cycle."""
        cycles = detect_cycles(cyclic_graph)
        assert len(cycles) == 1
        assert set(cycles[0]) == {"src/systems/a", "src/systems/b", "src/systems/c"}

    def test_detect_cycles_self_loop(self, initialized_db: ContextDB) -> None:
        """Test detecting self-loop."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            add_dependency(initialized_db, "src/systems/a", "src/systems/a")

        cycles = detect_cycles(initialized_db)
        assert len(cycles) == 1
        assert cycles[0] == ["src/systems/a"]

    def test_detect_cycles_two_node_cycle(self, initialized_db: ContextDB) -> None:
        """Test detecting two-node cycle."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            create_system(initialized_db, "src/systems/b", "System B")
            add_dependency(initialized_db, "src/systems/a", "src/systems/b")
            add_dependency(initialized_db, "src/systems/b", "src/systems/a")

        cycles = detect_cycles(initialized_db)
        assert len(cycles) == 1
        assert set(cycles[0]) == {"src/systems/a", "src/systems/b"}

    def test_detect_cycles_multiple_cycles(self, initialized_db: ContextDB) -> None:
        """Test detecting multiple independent cycles."""
        with initialized_db.transaction():
            # Cycle 1: a <-> b
            create_system(initialized_db, "src/systems/a", "System A")
            create_system(initialized_db, "src/systems/b", "System B")
            add_dependency(initialized_db, "src/systems/a", "src/systems/b")
            add_dependency(initialized_db, "src/systems/b", "src/systems/a")

            # Cycle 2: c <-> d
            create_system(initialized_db, "src/systems/c", "System C")
            create_system(initialized_db, "src/systems/d", "System D")
            add_dependency(initialized_db, "src/systems/c", "src/systems/d")
            add_dependency(initialized_db, "src/systems/d", "src/systems/c")

        cycles = detect_cycles(initialized_db)
        assert len(cycles) == 2


class TestGetTopologicalOrder:
    """Tests for get_topological_order function."""

    def test_get_topological_order_empty(self, initialized_db: ContextDB) -> None:
        """Test with empty graph."""
        order = get_topological_order(initialized_db)
        assert order == []

    def test_get_topological_order_single(self, initialized_db: ContextDB) -> None:
        """Test with single system."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")

        order = get_topological_order(initialized_db)
        assert order == ["src/systems/a"]

    def test_get_topological_order_no_deps(self, initialized_db: ContextDB) -> None:
        """Test systems with no dependencies are sorted alphabetically."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/c", "System C")
            create_system(initialized_db, "src/systems/a", "System A")
            create_system(initialized_db, "src/systems/b", "System B")

        order = get_topological_order(initialized_db)
        assert order == ["src/systems/a", "src/systems/b", "src/systems/c"]

    def test_get_topological_order_linear(self, linear_graph: ContextDB) -> None:
        """Test linear dependency order."""
        # a -> b -> c -> d (a depends on b, etc.)
        order = get_topological_order(linear_graph)
        # d has no deps, then c, then b, then a
        assert order == [
            "src/systems/d",
            "src/systems/c",
            "src/systems/b",
            "src/systems/a",
        ]

    def test_get_topological_order_diamond(self, diamond_graph: ContextDB) -> None:
        """Test diamond-shaped graph."""
        order = get_topological_order(diamond_graph)
        # core has no deps, then api and cli (alphabetical), then ui
        assert order[0] == "src/systems/core"
        assert set(order[1:3]) == {"src/systems/api", "src/systems/cli"}
        assert order[3] == "src/systems/ui"

    def test_get_topological_order_respects_deps(self, diamond_graph: ContextDB) -> None:
        """Test dependencies come before dependents."""
        order = get_topological_order(diamond_graph)

        # For each system, all its dependencies must appear before it
        order_index = {path: i for i, path in enumerate(order)}

        # core must come before api
        assert order_index["src/systems/core"] < order_index["src/systems/api"]
        # core must come before cli
        assert order_index["src/systems/core"] < order_index["src/systems/cli"]
        # api must come before ui
        assert order_index["src/systems/api"] < order_index["src/systems/ui"]
        # cli must come before ui
        assert order_index["src/systems/cli"] < order_index["src/systems/ui"]

    def test_get_topological_order_cycle_raises(self, cyclic_graph: ContextDB) -> None:
        """Test cycle raises CyclicDependencyError."""
        with pytest.raises(CyclicDependencyError, match="contains cycles"):
            get_topological_order(cyclic_graph)


class TestGetRootSystems:
    """Tests for get_root_systems function."""

    def test_get_root_systems_empty(self, initialized_db: ContextDB) -> None:
        """Test with empty graph."""
        roots = get_root_systems(initialized_db)
        assert roots == []

    def test_get_root_systems_all_roots(self, initialized_db: ContextDB) -> None:
        """Test when all systems are roots."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            create_system(initialized_db, "src/systems/b", "System B")

        roots = get_root_systems(initialized_db)
        assert roots == ["src/systems/a", "src/systems/b"]

    def test_get_root_systems_diamond(self, diamond_graph: ContextDB) -> None:
        """Test diamond graph has one root."""
        roots = get_root_systems(diamond_graph)
        assert roots == ["src/systems/core"]

    def test_get_root_systems_linear(self, linear_graph: ContextDB) -> None:
        """Test linear graph has one root."""
        # a -> b -> c -> d
        roots = get_root_systems(linear_graph)
        assert roots == ["src/systems/d"]

    def test_get_root_systems_multiple(self, initialized_db: ContextDB) -> None:
        """Test multiple root systems."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/core", "Core System")
            create_system(initialized_db, "src/systems/utils", "Utils System")
            create_system(initialized_db, "src/systems/api", "API System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/core")
            add_dependency(initialized_db, "src/systems/api", "src/systems/utils")

        roots = get_root_systems(initialized_db)
        assert roots == ["src/systems/core", "src/systems/utils"]

    def test_get_root_systems_sorted(self, initialized_db: ContextDB) -> None:
        """Test roots are sorted alphabetically."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/zebra", "Z System")
            create_system(initialized_db, "src/systems/apple", "A System")

        roots = get_root_systems(initialized_db)
        assert roots == ["src/systems/apple", "src/systems/zebra"]


class TestGetLeafSystems:
    """Tests for get_leaf_systems function."""

    def test_get_leaf_systems_empty(self, initialized_db: ContextDB) -> None:
        """Test with empty graph."""
        leaves = get_leaf_systems(initialized_db)
        assert leaves == []

    def test_get_leaf_systems_all_leaves(self, initialized_db: ContextDB) -> None:
        """Test when all systems are leaves."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            create_system(initialized_db, "src/systems/b", "System B")

        leaves = get_leaf_systems(initialized_db)
        assert leaves == ["src/systems/a", "src/systems/b"]

    def test_get_leaf_systems_diamond(self, diamond_graph: ContextDB) -> None:
        """Test diamond graph has one leaf."""
        leaves = get_leaf_systems(diamond_graph)
        assert leaves == ["src/systems/ui"]

    def test_get_leaf_systems_linear(self, linear_graph: ContextDB) -> None:
        """Test linear graph has one leaf."""
        # a -> b -> c -> d
        leaves = get_leaf_systems(linear_graph)
        assert leaves == ["src/systems/a"]

    def test_get_leaf_systems_multiple(self, initialized_db: ContextDB) -> None:
        """Test multiple leaf systems."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/core", "Core System")
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/cli", "CLI System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/core")
            add_dependency(initialized_db, "src/systems/cli", "src/systems/core")

        leaves = get_leaf_systems(initialized_db)
        assert leaves == ["src/systems/api", "src/systems/cli"]

    def test_get_leaf_systems_sorted(self, initialized_db: ContextDB) -> None:
        """Test leaves are sorted alphabetically."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/zebra", "Z System")
            create_system(initialized_db, "src/systems/apple", "A System")

        leaves = get_leaf_systems(initialized_db)
        assert leaves == ["src/systems/apple", "src/systems/zebra"]


class TestComplexScenarios:
    """Tests for complex graph scenarios."""

    def test_isolated_and_connected_systems(self, initialized_db: ContextDB) -> None:
        """Test graph with both isolated and connected systems."""
        with initialized_db.transaction():
            # Connected component
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/core", "Core System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/core")

            # Isolated system
            create_system(initialized_db, "src/systems/utils", "Utils System")

        graph = generate_graph(initialized_db)
        assert len(graph) == 3

        roots = get_root_systems(initialized_db)
        assert "src/systems/core" in roots
        assert "src/systems/utils" in roots

        leaves = get_leaf_systems(initialized_db)
        assert "src/systems/api" in leaves
        assert "src/systems/utils" in leaves

    def test_deep_graph(self, initialized_db: ContextDB) -> None:
        """Test deeply nested dependency chain."""
        with initialized_db.transaction():
            # Create a chain of 10 systems
            for i in range(10):
                create_system(initialized_db, f"src/systems/s{i}", f"System {i}")
            for i in range(9):
                add_dependency(initialized_db, f"src/systems/s{i}", f"src/systems/s{i + 1}")

        deps = get_all_dependencies(initialized_db, "src/systems/s0")
        assert len(deps) == 9

        order = get_topological_order(initialized_db)
        assert len(order) == 10
        assert order[0] == "src/systems/s9"  # No dependencies
        assert order[-1] == "src/systems/s0"  # Depends on all others

    def test_wide_graph(self, initialized_db: ContextDB) -> None:
        """Test system with many dependencies."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/main", "Main System")
            for i in range(10):
                create_system(initialized_db, f"src/systems/dep{i}", f"Dependency {i}")
                add_dependency(initialized_db, "src/systems/main", f"src/systems/dep{i}")

        deps = get_all_dependencies(initialized_db, "src/systems/main")
        assert len(deps) == 10

        dependents = get_all_dependents(initialized_db, "src/systems/dep0")
        assert dependents == {"src/systems/main"}

        roots = get_root_systems(initialized_db)
        assert len(roots) == 10  # All dep systems are roots

        leaves = get_leaf_systems(initialized_db)
        assert leaves == ["src/systems/main"]
