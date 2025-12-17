"""Tests for lctx.crud module."""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from lctx.crud import (
    add_dependency,
    create_system,
    delete_system,
    get_dependencies,
    get_dependents,
    get_system,
    list_systems,
    remove_dependency,
    update_system,
)
from lctx.database import ContextDB


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def initialized_db(temp_db_path: Path) -> Generator[ContextDB, None, None]:
    """Create a connected ContextDB instance."""
    with ContextDB(temp_db_path) as db:
        yield db


class TestCreateSystem:
    """Tests for create_system function."""

    def test_create_system_basic(self, initialized_db: ContextDB) -> None:
        """Test creating a system with required fields."""
        with initialized_db.transaction():
            result = create_system(initialized_db, "src/systems/auth", "Auth System")

        assert result["path"] == "src/systems/auth"
        assert result["name"] == "Auth System"
        assert result["created_at"] is not None
        assert result["updated_at"] is not None
        assert result["created_at"] == result["updated_at"]

    def test_create_system_with_description(self, initialized_db: ContextDB) -> None:
        """Test creating a system with description."""
        with initialized_db.transaction():
            result = create_system(
                initialized_db,
                "src/systems/auth",
                "Auth System",
                description="Handles authentication",
            )

        assert result["path"] == "src/systems/auth"
        assert result["description"] == "Handles authentication"

    def test_create_system_duplicate_raises(self, initialized_db: ContextDB) -> None:
        """Test creating duplicate system raises error."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System 2")

    def test_create_system_persists(self, initialized_db: ContextDB) -> None:
        """Test created system persists in database."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        result = get_system(initialized_db, "src/systems/auth")
        assert result is not None
        assert result["name"] == "Auth System"


class TestGetSystem:
    """Tests for get_system function."""

    def test_get_system_exists(self, initialized_db: ContextDB) -> None:
        """Test getting an existing system."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        result = get_system(initialized_db, "src/systems/auth")
        assert result is not None
        assert result["path"] == "src/systems/auth"
        assert result["name"] == "Auth System"

    def test_get_system_not_found(self, initialized_db: ContextDB) -> None:
        """Test getting non-existent system returns None."""
        result = get_system(initialized_db, "src/systems/nonexistent")
        assert result is None

    def test_get_system_returns_dict(self, initialized_db: ContextDB) -> None:
        """Test get_system returns dict type."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        result = get_system(initialized_db, "src/systems/auth")
        assert isinstance(result, dict)
        assert "path" in result
        assert "name" in result
        assert "created_at" in result
        assert "updated_at" in result


class TestListSystems:
    """Tests for list_systems function."""

    def test_list_systems_empty(self, initialized_db: ContextDB) -> None:
        """Test listing systems when none exist."""
        results = list_systems(initialized_db)
        assert results == []

    def test_list_systems_single(self, initialized_db: ContextDB) -> None:
        """Test listing with one system."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        results = list_systems(initialized_db)
        assert len(results) == 1
        assert results[0]["path"] == "src/systems/auth"

    def test_list_systems_multiple(self, initialized_db: ContextDB) -> None:
        """Test listing multiple systems."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/db", "Database System")

        results = list_systems(initialized_db)
        assert len(results) == 3

    def test_list_systems_sorted(self, initialized_db: ContextDB) -> None:
        """Test systems are returned sorted by path."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/zebra", "Z System")
            create_system(initialized_db, "src/systems/apple", "A System")
            create_system(initialized_db, "src/systems/banana", "B System")

        results = list_systems(initialized_db)
        paths = [r["path"] for r in results]
        assert paths == [
            "src/systems/apple",
            "src/systems/banana",
            "src/systems/zebra",
        ]

    def test_list_systems_returns_list_of_dicts(self, initialized_db: ContextDB) -> None:
        """Test list_systems returns list of dicts."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        results = list_systems(initialized_db)
        assert isinstance(results, list)
        assert isinstance(results[0], dict)


class TestUpdateSystem:
    """Tests for update_system function."""

    def test_update_system_name(self, initialized_db: ContextDB) -> None:
        """Test updating system name."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        with initialized_db.transaction():
            result = update_system(initialized_db, "src/systems/auth", name="Authentication System")

        assert result is True
        updated = get_system(initialized_db, "src/systems/auth")
        assert updated is not None
        assert updated["name"] == "Authentication System"

    def test_update_system_description(self, initialized_db: ContextDB) -> None:
        """Test updating system description."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        with initialized_db.transaction():
            result = update_system(
                initialized_db, "src/systems/auth", description="Handles user authentication"
            )

        assert result is True
        updated = get_system(initialized_db, "src/systems/auth")
        assert updated is not None
        assert updated["description"] == "Handles user authentication"

    def test_update_system_both(self, initialized_db: ContextDB) -> None:
        """Test updating both name and description."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        with initialized_db.transaction():
            result = update_system(
                initialized_db,
                "src/systems/auth",
                name="Authentication",
                description="Auth handling",
            )

        assert result is True
        updated = get_system(initialized_db, "src/systems/auth")
        assert updated is not None
        assert updated["name"] == "Authentication"
        assert updated["description"] == "Auth handling"

    def test_update_system_not_found(self, initialized_db: ContextDB) -> None:
        """Test updating non-existent system returns False."""
        with initialized_db.transaction():
            result = update_system(initialized_db, "src/systems/nonexistent", name="New Name")

        assert result is False

    def test_update_system_no_fields(self, initialized_db: ContextDB) -> None:
        """Test updating with no fields returns False."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        with initialized_db.transaction():
            result = update_system(initialized_db, "src/systems/auth")

        assert result is False

    def test_update_system_updates_timestamp(self, initialized_db: ContextDB) -> None:
        """Test that update_system updates the updated_at timestamp."""
        with initialized_db.transaction():
            created = create_system(initialized_db, "src/systems/auth", "Auth System")
            created_at = created["created_at"]

        # Small delay to ensure timestamps differ
        import time

        time.sleep(0.01)

        with initialized_db.transaction():
            update_system(initialized_db, "src/systems/auth", name="New Name")

        updated = get_system(initialized_db, "src/systems/auth")
        assert updated is not None
        assert updated["updated_at"] > created_at


class TestDeleteSystem:
    """Tests for delete_system function."""

    def test_delete_system_exists(self, initialized_db: ContextDB) -> None:
        """Test deleting an existing system."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        with initialized_db.transaction():
            result = delete_system(initialized_db, "src/systems/auth")

        assert result is True
        deleted = get_system(initialized_db, "src/systems/auth")
        assert deleted is None

    def test_delete_system_not_found(self, initialized_db: ContextDB) -> None:
        """Test deleting non-existent system returns False."""
        with initialized_db.transaction():
            result = delete_system(initialized_db, "src/systems/nonexistent")

        assert result is False

    def test_delete_system_cascade_deletes_dependencies(self, initialized_db: ContextDB) -> None:
        """Test that deleting a system cascade deletes its dependencies."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")
            create_system(initialized_db, "src/systems/api", "API System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        with initialized_db.transaction():
            delete_system(initialized_db, "src/systems/auth")

        # Check that dependency was removed
        deps = get_dependencies(initialized_db, "src/systems/api")
        assert len(deps) == 0


class TestAddDependency:
    """Tests for add_dependency function."""

    def test_add_dependency_creates_link(self, initialized_db: ContextDB) -> None:
        """Test adding a dependency creates the relationship."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            result = add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        assert result is True
        deps = get_dependencies(initialized_db, "src/systems/api")
        assert len(deps) == 1
        assert deps[0]["path"] == "src/systems/auth"

    def test_add_dependency_nonexistent_system_raises(self, initialized_db: ContextDB) -> None:
        """Test adding dependency with non-existent system raises error."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            add_dependency(initialized_db, "src/systems/api", "src/systems/nonexistent")

    def test_add_dependency_duplicate_raises(self, initialized_db: ContextDB) -> None:
        """Test adding duplicate dependency raises error."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

    def test_add_multiple_dependencies(self, initialized_db: ContextDB) -> None:
        """Test adding multiple dependencies to same system."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            create_system(initialized_db, "src/systems/db", "Database System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/api", "src/systems/db")

        deps = get_dependencies(initialized_db, "src/systems/api")
        assert len(deps) == 2
        paths = {d["path"] for d in deps}
        assert paths == {"src/systems/auth", "src/systems/db"}


class TestRemoveDependency:
    """Tests for remove_dependency function."""

    def test_remove_dependency_exists(self, initialized_db: ContextDB) -> None:
        """Test removing an existing dependency."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        with initialized_db.transaction():
            result = remove_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        assert result is True
        deps = get_dependencies(initialized_db, "src/systems/api")
        assert len(deps) == 0

    def test_remove_dependency_not_found(self, initialized_db: ContextDB) -> None:
        """Test removing non-existent dependency returns False."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")

        with initialized_db.transaction():
            result = remove_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        assert result is False

    def test_remove_dependency_keeps_other(self, initialized_db: ContextDB) -> None:
        """Test removing one dependency doesn't affect others."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            create_system(initialized_db, "src/systems/db", "Database System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/api", "src/systems/db")

        with initialized_db.transaction():
            remove_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        deps = get_dependencies(initialized_db, "src/systems/api")
        assert len(deps) == 1
        assert deps[0]["path"] == "src/systems/db"


class TestGetDependencies:
    """Tests for get_dependencies function."""

    def test_get_dependencies_empty(self, initialized_db: ContextDB) -> None:
        """Test getting dependencies when none exist."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")

        deps = get_dependencies(initialized_db, "src/systems/api")
        assert deps == []

    def test_get_dependencies_single(self, initialized_db: ContextDB) -> None:
        """Test getting a single dependency."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        deps = get_dependencies(initialized_db, "src/systems/api")
        assert len(deps) == 1
        assert deps[0]["path"] == "src/systems/auth"

    def test_get_dependencies_multiple(self, initialized_db: ContextDB) -> None:
        """Test getting multiple dependencies."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            create_system(initialized_db, "src/systems/db", "Database System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/api", "src/systems/db")

        deps = get_dependencies(initialized_db, "src/systems/api")
        assert len(deps) == 2

    def test_get_dependencies_sorted(self, initialized_db: ContextDB) -> None:
        """Test dependencies are sorted by path."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/zebra", "Z System")
            create_system(initialized_db, "src/systems/apple", "A System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/zebra")
            add_dependency(initialized_db, "src/systems/api", "src/systems/apple")

        deps = get_dependencies(initialized_db, "src/systems/api")
        paths = [d["path"] for d in deps]
        assert paths == ["src/systems/apple", "src/systems/zebra"]

    def test_get_dependencies_returns_system_info(self, initialized_db: ContextDB) -> None:
        """Test get_dependencies returns full system info."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(
                initialized_db, "src/systems/auth", "Auth System", description="Handles auth"
            )
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        deps = get_dependencies(initialized_db, "src/systems/api")
        assert deps[0]["name"] == "Auth System"
        assert deps[0]["description"] == "Handles auth"
        assert "created_at" in deps[0]


class TestGetDependents:
    """Tests for get_dependents function."""

    def test_get_dependents_empty(self, initialized_db: ContextDB) -> None:
        """Test getting dependents when none exist."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/auth", "Auth System")

        dependents = get_dependents(initialized_db, "src/systems/auth")
        assert dependents == []

    def test_get_dependents_single(self, initialized_db: ContextDB) -> None:
        """Test getting a single dependent."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        dependents = get_dependents(initialized_db, "src/systems/auth")
        assert len(dependents) == 1
        assert dependents[0]["path"] == "src/systems/api"

    def test_get_dependents_multiple(self, initialized_db: ContextDB) -> None:
        """Test getting multiple dependents."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/cli", "CLI System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/cli", "src/systems/auth")

        dependents = get_dependents(initialized_db, "src/systems/auth")
        assert len(dependents) == 2

    def test_get_dependents_sorted(self, initialized_db: ContextDB) -> None:
        """Test dependents are sorted by path."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/zebra", "Z System")
            create_system(initialized_db, "src/systems/apple", "A System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/zebra", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/apple", "src/systems/auth")

        dependents = get_dependents(initialized_db, "src/systems/auth")
        paths = [d["path"] for d in dependents]
        assert paths == ["src/systems/apple", "src/systems/zebra"]

    def test_get_dependents_returns_system_info(self, initialized_db: ContextDB) -> None:
        """Test get_dependents returns full system info."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/api", "API System", description="API layer")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")

        dependents = get_dependents(initialized_db, "src/systems/auth")
        assert dependents[0]["name"] == "API System"
        assert dependents[0]["description"] == "API layer"
        assert "created_at" in dependents[0]


class TestInputValidation:
    """Tests for input validation in CRUD functions."""

    def test_create_system_empty_path_raises(self, initialized_db: ContextDB) -> None:
        """Test creating system with empty path raises ValueError."""
        with pytest.raises(ValueError, match="path cannot be empty"):
            create_system(initialized_db, "", "Test System")

    def test_create_system_whitespace_only_path_raises(self, initialized_db: ContextDB) -> None:
        """Test creating system with whitespace-only path raises ValueError."""
        with pytest.raises(ValueError, match="path cannot be empty"):
            create_system(initialized_db, "   ", "Test System")

    def test_create_system_path_traversal_raises(self, initialized_db: ContextDB) -> None:
        """Test creating system with path traversal raises ValueError."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            create_system(initialized_db, "../../../etc/passwd", "Test System")

    def test_create_system_path_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test creating system with path exceeding max length raises ValueError."""
        long_path = "a" * 513
        with pytest.raises(ValueError, match="exceeds maximum length"):
            create_system(initialized_db, long_path, "Test System")

    def test_create_system_empty_name_raises(self, initialized_db: ContextDB) -> None:
        """Test creating system with empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            create_system(initialized_db, "src/systems/auth", "")

    def test_create_system_whitespace_only_name_raises(self, initialized_db: ContextDB) -> None:
        """Test creating system with whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            create_system(initialized_db, "src/systems/auth", "   ")

    def test_create_system_name_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test creating system with name exceeding max length raises ValueError."""
        long_name = "a" * 257
        with pytest.raises(ValueError, match="exceeds maximum length"):
            create_system(initialized_db, "src/systems/auth", long_name)

    def test_add_dependency_empty_system_path_raises(self, initialized_db: ContextDB) -> None:
        """Test adding dependency with empty system_path raises ValueError."""
        with pytest.raises(ValueError, match="system_path cannot be empty"):
            add_dependency(initialized_db, "", "src/systems/auth")

    def test_add_dependency_empty_depends_on_raises(self, initialized_db: ContextDB) -> None:
        """Test adding dependency with empty depends_on raises ValueError."""
        with pytest.raises(ValueError, match="depends_on cannot be empty"):
            add_dependency(initialized_db, "src/systems/api", "")

    def test_add_dependency_system_path_traversal_raises(self, initialized_db: ContextDB) -> None:
        """Test adding dependency with path traversal in system_path raises ValueError."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            add_dependency(initialized_db, "../../../etc", "src/systems/auth")

    def test_add_dependency_depends_on_traversal_raises(self, initialized_db: ContextDB) -> None:
        """Test adding dependency with path traversal in depends_on raises ValueError."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            add_dependency(initialized_db, "src/systems/api", "../../secret")

    def test_add_dependency_system_path_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test adding dependency with system_path exceeding max length raises ValueError."""
        long_path = "a" * 513
        with pytest.raises(ValueError, match="exceeds maximum length"):
            add_dependency(initialized_db, long_path, "src/systems/auth")

    def test_add_dependency_depends_on_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test adding dependency with depends_on exceeding max length raises ValueError."""
        long_path = "a" * 513
        with pytest.raises(ValueError, match="exceeds maximum length"):
            add_dependency(initialized_db, "src/systems/api", long_path)


class TestComplexScenarios:
    """Tests for complex CRUD scenarios."""

    def test_circular_dependency_allowed(self, initialized_db: ContextDB) -> None:
        """Test that circular dependencies are allowed (no validation)."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            create_system(initialized_db, "src/systems/b", "System B")
            add_dependency(initialized_db, "src/systems/a", "src/systems/b")
            # Circular dependency - should be allowed
            add_dependency(initialized_db, "src/systems/b", "src/systems/a")

        deps_a = get_dependencies(initialized_db, "src/systems/a")
        deps_b = get_dependencies(initialized_db, "src/systems/b")
        assert len(deps_a) == 1
        assert len(deps_b) == 1
        assert deps_a[0]["path"] == "src/systems/b"
        assert deps_b[0]["path"] == "src/systems/a"

    def test_self_dependency_allowed(self, initialized_db: ContextDB) -> None:
        """Test that self-dependencies are allowed (no validation)."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/a", "System A")
            add_dependency(initialized_db, "src/systems/a", "src/systems/a")

        deps = get_dependencies(initialized_db, "src/systems/a")
        assert len(deps) == 1
        assert deps[0]["path"] == "src/systems/a"

    def test_complex_dependency_graph(self, initialized_db: ContextDB) -> None:
        """Test complex multi-level dependency graph."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/ui", "UI System")
            create_system(initialized_db, "src/systems/api", "API System")
            create_system(initialized_db, "src/systems/auth", "Auth System")
            create_system(initialized_db, "src/systems/db", "Database System")

            # UI depends on API
            add_dependency(initialized_db, "src/systems/ui", "src/systems/api")
            # API depends on Auth and DB
            add_dependency(initialized_db, "src/systems/api", "src/systems/auth")
            add_dependency(initialized_db, "src/systems/api", "src/systems/db")

        # Verify relationships
        assert len(get_dependencies(initialized_db, "src/systems/ui")) == 1
        assert len(get_dependencies(initialized_db, "src/systems/api")) == 2
        assert len(get_dependents(initialized_db, "src/systems/auth")) == 1
        assert len(get_dependents(initialized_db, "src/systems/api")) == 1

    def test_update_and_delete_sequence(self, initialized_db: ContextDB) -> None:
        """Test sequence of create, update, and delete operations."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/test", "Test System")

        with initialized_db.transaction():
            update_system(initialized_db, "src/systems/test", name="Updated System")

        updated = get_system(initialized_db, "src/systems/test")
        assert updated is not None
        assert updated["name"] == "Updated System"

        with initialized_db.transaction():
            delete_system(initialized_db, "src/systems/test")

        deleted = get_system(initialized_db, "src/systems/test")
        assert deleted is None
