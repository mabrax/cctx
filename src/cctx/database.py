"""Database connection and transaction management for Living Context.

Provides the ContextDB class for managing SQLite database connections with
proper context manager support and transaction handling.

Design decisions:
- Eager connection: Connection is created on __enter__, not lazily
- Foreign keys enabled via PRAGMA foreign_keys = ON
- Not thread-safe (single-threaded CLI use case)
- Transaction support via nested context managers
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from cctx.schema import init_database

if TYPE_CHECKING:
    from types import TracebackType


class DatabaseError(Exception):
    """Base exception for database-related errors."""


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""


class TransactionError(DatabaseError):
    """Raised when transaction operations fail."""


class ContextDB:
    """Database connection manager for Living Context.

    Provides connection management with context manager protocol and
    transaction support. Connection is created eagerly on __enter__.

    Example usage:
        >>> with ContextDB("/path/to/knowledge.db") as db:
        ...     with db.transaction():
        ...         db.execute("INSERT INTO systems ...")
        ...         # auto-commit on success, auto-rollback on exception

    Attributes:
        db_path: Path to the SQLite database file.
        auto_init: If True, initialize database if it doesn't exist.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        auto_init: bool = True,
    ) -> None:
        """Initialize ContextDB.

        Args:
            db_path: Path to the SQLite database file.
            auto_init: If True, initialize database schema if file doesn't exist.
                       Defaults to True.
        """
        self.db_path = Path(db_path)
        self.auto_init = auto_init
        self._connection: sqlite3.Connection | None = None
        self._in_transaction: bool = False

    def __enter__(self) -> ContextDB:
        """Open database connection.

        Creates the connection and enables foreign key enforcement.

        Returns:
            Self for use in with statement.

        Raises:
            ConnectionError: If connection fails.
        """
        self._open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Close database connection.

        Closes the connection regardless of whether an exception occurred.
        Does not commit or rollback - that's handled by transaction().
        """
        self._close()

    def _open(self) -> None:
        """Open the database connection.

        Raises:
            ConnectionError: If connection fails.
        """
        if self._connection is not None:
            return  # Already open

        # Initialize database if requested and file doesn't exist
        if self.auto_init and not self.db_path.exists():
            try:
                init_database(self.db_path)
            except (sqlite3.Error, OSError) as e:
                raise ConnectionError(f"Failed to initialize database: {e}") from e

        try:
            self._connection = sqlite3.connect(str(self.db_path))
            # Enable foreign key enforcement
            self._connection.execute("PRAGMA foreign_keys = ON")
            # Return rows as Row objects for dict-like access
            self._connection.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    def _close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the underlying SQLite connection.

        Returns:
            The active database connection.

        Raises:
            ConnectionError: If not connected.
        """
        if self._connection is None:
            raise ConnectionError("Database not connected. Use 'with ContextDB(...)' context.")
        return self._connection

    @property
    def is_connected(self) -> bool:
        """Check if database is currently connected.

        Returns:
            True if connected, False otherwise.
        """
        return self._connection is not None

    @property
    def in_transaction(self) -> bool:
        """Check if currently in a transaction block.

        Returns:
            True if inside a transaction() context, False otherwise.
        """
        return self._in_transaction

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Transaction context manager.

        Begins a transaction, commits on success, rolls back on exception.
        Supports simple nesting - inner transactions are no-ops (no savepoints).

        Example:
            >>> with db.transaction():
            ...     db.execute("INSERT INTO ...")
            ...     # auto-commit here
            ...
            >>> with db.transaction():
            ...     db.execute("INSERT INTO ...")
            ...     raise ValueError("oops")
            ...     # auto-rollback due to exception

        Yields:
            None

        Raises:
            ConnectionError: If not connected to database.
            TransactionError: If transaction operations fail.
        """
        if self._connection is None:
            raise ConnectionError("Database not connected. Use 'with ContextDB(...)' context.")

        # Handle nested transactions - inner ones are no-ops
        if self._in_transaction:
            yield
            return

        self._in_transaction = True
        try:
            self.begin_transaction()
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise
        finally:
            self._in_transaction = False

    def begin_transaction(self) -> None:
        """Begin a new transaction explicitly.

        For most use cases, prefer the transaction() context manager.
        This method is provided for cases requiring explicit control.

        Raises:
            ConnectionError: If not connected.
            TransactionError: If BEGIN fails.
        """
        try:
            self.connection.execute("BEGIN")
        except sqlite3.Error as e:
            raise TransactionError(f"Failed to begin transaction: {e}") from e

    def commit(self) -> None:
        """Commit the current transaction.

        For most use cases, prefer the transaction() context manager.
        This method is provided for cases requiring explicit control.

        Raises:
            ConnectionError: If not connected.
            TransactionError: If COMMIT fails.
        """
        try:
            self.connection.commit()
        except sqlite3.Error as e:
            raise TransactionError(f"Failed to commit transaction: {e}") from e

    def rollback(self) -> None:
        """Rollback the current transaction.

        For most use cases, prefer the transaction() context manager.
        This method is provided for cases requiring explicit control.

        Raises:
            ConnectionError: If not connected.
            TransactionError: If ROLLBACK fails.
        """
        try:
            self.connection.rollback()
        except sqlite3.Error as e:
            raise TransactionError(f"Failed to rollback transaction: {e}") from e

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] | dict[str, Any] = (),
    ) -> sqlite3.Cursor:
        """Execute a SQL statement.

        Args:
            sql: SQL statement to execute.
            parameters: Parameters for the SQL statement (tuple or dict).

        Returns:
            Cursor from the executed statement.

        Raises:
            ConnectionError: If not connected.
            sqlite3.Error: If execution fails.
        """
        return self.connection.execute(sql, parameters)

    def executemany(
        self,
        sql: str,
        parameters: list[tuple[Any, ...]] | list[dict[str, Any]],
    ) -> sqlite3.Cursor:
        """Execute a SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement to execute.
            parameters: List of parameter tuples or dicts.

        Returns:
            Cursor from the executed statement.

        Raises:
            ConnectionError: If not connected.
            sqlite3.Error: If execution fails.
        """
        return self.connection.executemany(sql, parameters)

    def executescript(self, sql_script: str) -> sqlite3.Cursor:
        """Execute a SQL script (multiple statements).

        Note: executescript issues a COMMIT before executing the script.

        Args:
            sql_script: SQL script with multiple statements.

        Returns:
            Cursor from the executed script.

        Raises:
            ConnectionError: If not connected.
            sqlite3.Error: If execution fails.
        """
        return self.connection.executescript(sql_script)

    def fetchone(
        self,
        sql: str,
        parameters: tuple[Any, ...] | dict[str, Any] = (),
    ) -> sqlite3.Row | None:
        """Execute SQL and fetch one row.

        Convenience method combining execute() and fetchone().

        Args:
            sql: SQL statement to execute.
            parameters: Parameters for the SQL statement.

        Returns:
            First row of results, or None if no results.

        Raises:
            ConnectionError: If not connected.
            sqlite3.Error: If execution fails.
        """
        cursor = self.execute(sql, parameters)
        result = cursor.fetchone()
        return cast(sqlite3.Row | None, result)

    def fetchall(
        self,
        sql: str,
        parameters: tuple[Any, ...] | dict[str, Any] = (),
    ) -> list[sqlite3.Row]:
        """Execute SQL and fetch all rows.

        Convenience method combining execute() and fetchall().

        Args:
            sql: SQL statement to execute.
            parameters: Parameters for the SQL statement.

        Returns:
            List of all result rows.

        Raises:
            ConnectionError: If not connected.
            sqlite3.Error: If execution fails.
        """
        cursor = self.execute(sql, parameters)
        return cursor.fetchall()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database.

        Args:
            table_name: Name of the table to check.

        Returns:
            True if table exists, False otherwise.

        Raises:
            ConnectionError: If not connected.
        """
        result = self.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return result is not None
