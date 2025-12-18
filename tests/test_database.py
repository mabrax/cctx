"""Tests for cctx.database module."""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from cctx.database import (
    ConnectionError,
    ContextDB,
    DatabaseError,
    TransactionError,
)


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


class TestContextDBInit:
    """Tests for ContextDB initialization."""

    def test_init_with_string_path(self, temp_db_path: Path) -> None:
        """Test initialization with string path."""
        db = ContextDB(str(temp_db_path))
        assert db.db_path == temp_db_path
        assert db.auto_init is True

    def test_init_with_path_object(self, temp_db_path: Path) -> None:
        """Test initialization with Path object."""
        db = ContextDB(temp_db_path)
        assert db.db_path == temp_db_path

    def test_init_auto_init_default(self, temp_db_path: Path) -> None:
        """Test auto_init defaults to True."""
        db = ContextDB(temp_db_path)
        assert db.auto_init is True

    def test_init_auto_init_false(self, temp_db_path: Path) -> None:
        """Test auto_init can be disabled."""
        db = ContextDB(temp_db_path, auto_init=False)
        assert db.auto_init is False

    def test_not_connected_initially(self, temp_db_path: Path) -> None:
        """Test database is not connected after init."""
        db = ContextDB(temp_db_path)
        assert not db.is_connected
        assert db._connection is None


class TestContextDBContextManager:
    """Tests for ContextDB context manager protocol."""

    def test_enter_creates_connection(self, temp_db_path: Path) -> None:
        """Test __enter__ creates database connection."""
        db = ContextDB(temp_db_path)
        with db:
            assert db.is_connected
            assert db._connection is not None

    def test_exit_closes_connection(self, temp_db_path: Path) -> None:
        """Test __exit__ closes database connection."""
        db = ContextDB(temp_db_path)
        with db:
            pass
        assert not db.is_connected
        assert db._connection is None

    def test_enter_returns_self(self, temp_db_path: Path) -> None:
        """Test __enter__ returns self."""
        db = ContextDB(temp_db_path)
        with db as context:
            assert context is db

    def test_exit_closes_on_exception(self, temp_db_path: Path) -> None:
        """Test connection is closed even when exception occurs."""
        db = ContextDB(temp_db_path)
        with pytest.raises(ValueError), db:
            assert db.is_connected
            raise ValueError("test error")
        assert not db.is_connected

    def test_auto_init_creates_database(self, temp_db_path: Path) -> None:
        """Test auto_init creates database file if missing."""
        assert not temp_db_path.exists()
        with ContextDB(temp_db_path, auto_init=True) as db:
            # Should have tables from schema
            assert db.table_exists("adrs")
            assert db.table_exists("systems")
        assert temp_db_path.exists()

    def test_auto_init_false_doesnt_create(self, temp_db_path: Path) -> None:
        """Test auto_init=False doesn't create database."""
        assert not temp_db_path.exists()
        # sqlite3 will create an empty file, but schema won't be applied
        with ContextDB(temp_db_path, auto_init=False) as db:
            assert not db.table_exists("adrs")
            assert not db.table_exists("systems")


class TestContextDBConnection:
    """Tests for ContextDB connection properties."""

    def test_connection_property_when_connected(self, initialized_db: ContextDB) -> None:
        """Test connection property returns connection when connected."""
        conn = initialized_db.connection
        assert isinstance(conn, sqlite3.Connection)

    def test_connection_property_when_not_connected(self, temp_db_path: Path) -> None:
        """Test connection property raises when not connected."""
        db = ContextDB(temp_db_path)
        with pytest.raises(ConnectionError, match="not connected"):
            _ = db.connection

    def test_foreign_keys_enabled(self, initialized_db: ContextDB) -> None:
        """Test foreign keys are enabled on connection."""
        result = initialized_db.fetchone("PRAGMA foreign_keys")
        assert result is not None
        assert result[0] == 1

    def test_row_factory_set(self, initialized_db: ContextDB) -> None:
        """Test row_factory is set to Row."""
        assert initialized_db.connection.row_factory == sqlite3.Row


class TestContextDBTransaction:
    """Tests for ContextDB transaction support."""

    def test_transaction_commits_on_success(self, initialized_db: ContextDB) -> None:
        """Test transaction commits when block succeeds."""
        with initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("test/system", "Test System", "2025-01-01", "2025-01-01"),
            )

        # Verify data persisted
        result = initialized_db.fetchone("SELECT * FROM systems WHERE path = ?", ("test/system",))
        assert result is not None
        assert result["name"] == "Test System"

    def test_transaction_rollback_on_exception(self, initialized_db: ContextDB) -> None:
        """Test transaction rolls back when exception occurs."""
        with pytest.raises(ValueError), initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("test/system", "Test System", "2025-01-01", "2025-01-01"),
            )
            raise ValueError("test error")

        # Verify data was rolled back
        result = initialized_db.fetchone("SELECT * FROM systems WHERE path = ?", ("test/system",))
        assert result is None

    def test_nested_transaction_commits_once(self, initialized_db: ContextDB) -> None:
        """Test nested transactions only commit at outer level."""
        with initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("system1", "System 1", "2025-01-01", "2025-01-01"),
            )
            with initialized_db.transaction():
                initialized_db.execute(
                    "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("system2", "System 2", "2025-01-01", "2025-01-01"),
                )

        # Both inserts should be committed
        results = initialized_db.fetchall("SELECT * FROM systems ORDER BY path")
        assert len(results) == 2

    def test_nested_transaction_rollback(self, initialized_db: ContextDB) -> None:
        """Test nested transaction exception rolls back all changes."""
        with pytest.raises(ValueError), initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("system1", "System 1", "2025-01-01", "2025-01-01"),
            )
            with initialized_db.transaction():
                initialized_db.execute(
                    "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("system2", "System 2", "2025-01-01", "2025-01-01"),
                )
                raise ValueError("inner error")

        # Both inserts should be rolled back
        results = initialized_db.fetchall("SELECT * FROM systems")
        assert len(results) == 0

    def test_in_transaction_property(self, initialized_db: ContextDB) -> None:
        """Test in_transaction property reflects transaction state."""
        assert not initialized_db.in_transaction
        with initialized_db.transaction():
            assert initialized_db.in_transaction
        assert not initialized_db.in_transaction

    def test_transaction_without_connection_raises(self, temp_db_path: Path) -> None:
        """Test transaction() raises when not connected."""
        db = ContextDB(temp_db_path)
        with pytest.raises(ConnectionError, match="not connected"), db.transaction():
            pass


class TestContextDBExplicitTransaction:
    """Tests for explicit transaction methods."""

    def test_begin_transaction(self, initialized_db: ContextDB) -> None:
        """Test begin_transaction starts a transaction."""
        initialized_db.begin_transaction()
        initialized_db.execute(
            "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("test/system", "Test", "2025-01-01", "2025-01-01"),
        )
        initialized_db.rollback()

        result = initialized_db.fetchone("SELECT * FROM systems")
        assert result is None

    def test_commit(self, initialized_db: ContextDB) -> None:
        """Test commit persists changes."""
        initialized_db.begin_transaction()
        initialized_db.execute(
            "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("test/system", "Test", "2025-01-01", "2025-01-01"),
        )
        initialized_db.commit()

        result = initialized_db.fetchone("SELECT * FROM systems")
        assert result is not None

    def test_rollback(self, initialized_db: ContextDB) -> None:
        """Test rollback reverts changes."""
        initialized_db.begin_transaction()
        initialized_db.execute(
            "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("test/system", "Test", "2025-01-01", "2025-01-01"),
        )
        initialized_db.rollback()

        result = initialized_db.fetchone("SELECT * FROM systems")
        assert result is None


class TestContextDBExecute:
    """Tests for ContextDB execute methods."""

    def test_execute_with_tuple_params(self, initialized_db: ContextDB) -> None:
        """Test execute with tuple parameters."""
        with initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("test/path", "Test", "2025-01-01", "2025-01-01"),
            )

        result = initialized_db.fetchone("SELECT * FROM systems")
        assert result is not None
        assert result["path"] == "test/path"

    def test_execute_with_dict_params(self, initialized_db: ContextDB) -> None:
        """Test execute with dict parameters."""
        with initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) "
                "VALUES (:path, :name, :created, :updated)",
                {
                    "path": "test/path",
                    "name": "Test",
                    "created": "2025-01-01",
                    "updated": "2025-01-01",
                },
            )

        result = initialized_db.fetchone("SELECT * FROM systems")
        assert result is not None
        assert result["path"] == "test/path"

    def test_execute_returns_cursor(self, initialized_db: ContextDB) -> None:
        """Test execute returns cursor."""
        cursor = initialized_db.execute("SELECT 1")
        assert isinstance(cursor, sqlite3.Cursor)

    def test_executemany(self, initialized_db: ContextDB) -> None:
        """Test executemany with multiple parameter sets."""
        data = [
            ("system1", "System 1", "2025-01-01", "2025-01-01"),
            ("system2", "System 2", "2025-01-01", "2025-01-01"),
            ("system3", "System 3", "2025-01-01", "2025-01-01"),
        ]
        with initialized_db.transaction():
            initialized_db.executemany(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                data,
            )

        results = initialized_db.fetchall("SELECT * FROM systems ORDER BY path")
        assert len(results) == 3

    def test_executescript(self, initialized_db: ContextDB) -> None:
        """Test executescript with multiple statements."""
        script = """
            INSERT INTO systems (path, name, created_at, updated_at) VALUES ('s1', 'S1', '2025-01-01', '2025-01-01');
            INSERT INTO systems (path, name, created_at, updated_at) VALUES ('s2', 'S2', '2025-01-01', '2025-01-01');
        """
        initialized_db.executescript(script)

        results = initialized_db.fetchall("SELECT * FROM systems")
        assert len(results) == 2


class TestContextDBFetch:
    """Tests for ContextDB fetch methods."""

    def test_fetchone_returns_row(self, initialized_db: ContextDB) -> None:
        """Test fetchone returns Row object."""
        with initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("test/path", "Test", "2025-01-01", "2025-01-01"),
            )

        result = initialized_db.fetchone("SELECT * FROM systems WHERE path = ?", ("test/path",))
        assert result is not None
        # Row supports dict-like access
        assert result["path"] == "test/path"
        assert result["name"] == "Test"

    def test_fetchone_returns_none_for_no_results(self, initialized_db: ContextDB) -> None:
        """Test fetchone returns None when no results."""
        result = initialized_db.fetchone("SELECT * FROM systems WHERE path = ?", ("nonexistent",))
        assert result is None

    def test_fetchall_returns_list(self, initialized_db: ContextDB) -> None:
        """Test fetchall returns list of Row objects."""
        with initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("s1", "S1", "2025-01-01", "2025-01-01"),
            )
            initialized_db.execute(
                "INSERT INTO systems (path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("s2", "S2", "2025-01-01", "2025-01-01"),
            )

        results = initialized_db.fetchall("SELECT * FROM systems ORDER BY path")
        assert len(results) == 2
        assert results[0]["path"] == "s1"
        assert results[1]["path"] == "s2"

    def test_fetchall_returns_empty_list(self, initialized_db: ContextDB) -> None:
        """Test fetchall returns empty list when no results."""
        results = initialized_db.fetchall("SELECT * FROM systems")
        assert results == []


class TestContextDBHelpers:
    """Tests for ContextDB helper methods."""

    def test_table_exists_true(self, initialized_db: ContextDB) -> None:
        """Test table_exists returns True for existing table."""
        assert initialized_db.table_exists("systems")
        assert initialized_db.table_exists("adrs")
        assert initialized_db.table_exists("adr_systems")

    def test_table_exists_false(self, initialized_db: ContextDB) -> None:
        """Test table_exists returns False for non-existing table."""
        assert not initialized_db.table_exists("nonexistent_table")
        assert not initialized_db.table_exists("foobar")


class TestDatabaseExceptions:
    """Tests for database exception hierarchy."""

    def test_database_error_is_exception(self) -> None:
        """Test DatabaseError inherits from Exception."""
        assert issubclass(DatabaseError, Exception)

    def test_connection_error_is_database_error(self) -> None:
        """Test ConnectionError inherits from DatabaseError."""
        assert issubclass(ConnectionError, DatabaseError)

    def test_transaction_error_is_database_error(self) -> None:
        """Test TransactionError inherits from DatabaseError."""
        assert issubclass(TransactionError, DatabaseError)


class TestForeignKeyEnforcement:
    """Tests for foreign key constraint enforcement."""

    def test_foreign_key_violation_raises(self, initialized_db: ContextDB) -> None:
        """Test foreign key violations are enforced."""
        # Try to insert an adr_system for a non-existent ADR
        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            initialized_db.execute(
                "INSERT INTO adr_systems (adr_id, system_path) VALUES (?, ?)",
                ("nonexistent-adr", "some/path"),
            )

    def test_cascade_delete(self, initialized_db: ContextDB) -> None:
        """Test cascade delete works correctly."""
        with initialized_db.transaction():
            # Create an ADR
            initialized_db.execute(
                "INSERT INTO adrs (id, title, status, created_at, updated_at, file_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("ADR-001", "Test ADR", "accepted", "2025-01-01", "2025-01-01", "path/to/adr.md"),
            )
            # Add a tag
            initialized_db.execute(
                "INSERT INTO adr_tags (adr_id, tag) VALUES (?, ?)",
                ("ADR-001", "architecture"),
            )

        # Verify tag exists
        tags = initialized_db.fetchall("SELECT * FROM adr_tags WHERE adr_id = ?", ("ADR-001",))
        assert len(tags) == 1

        # Delete the ADR
        with initialized_db.transaction():
            initialized_db.execute("DELETE FROM adrs WHERE id = ?", ("ADR-001",))

        # Verify tag was cascade deleted
        tags = initialized_db.fetchall("SELECT * FROM adr_tags WHERE adr_id = ?", ("ADR-001",))
        assert len(tags) == 0
