"""CRUD operations for Living Context systems and dependencies.

Provides basic create, read, update, and delete operations for:
- Systems registry
- System dependency relationships
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cctx.database import ContextDB


def _validate_path(path: str, field_name: str = "path") -> None:
    """Validate a system path.

    Args:
        path: The path string to validate.
        field_name: The field name for error messages.

    Raises:
        ValueError: If path is empty, exceeds max length, or contains path traversal.
    """
    if not path or not path.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if len(path) > 512:
        raise ValueError(f"{field_name} exceeds maximum length (512)")
    if ".." in path:
        raise ValueError(f"Path traversal not allowed in {field_name}")


def _validate_name(name: str, field_name: str = "name") -> None:
    """Validate a name field.

    Args:
        name: The name string to validate.
        field_name: The field name for error messages.

    Raises:
        ValueError: If name is empty or exceeds max length.
    """
    if not name or not name.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if len(name) > 256:
        raise ValueError(f"{field_name} exceeds maximum length (256)")


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert sqlite3.Row to dict.

    Args:
        row: A sqlite3.Row object.

    Returns:
        Dictionary representation of the row.
    """
    if row is None:
        return {}
    return dict(row)


# Systems CRUD Operations


def create_system(db: ContextDB, path: str, name: str, description: str | None = None) -> dict[str, Any]:
    """Create a new system.

    Args:
        db: Database connection.
        path: System path (e.g., "src/systems/auth").
        name: Human-readable system name.
        description: Optional system description.

    Returns:
        Dictionary with created system data.

    Raises:
        ValueError: If path or name is invalid.
        sqlite3.IntegrityError: If system already exists.
    """
    _validate_path(path, "path")
    _validate_name(name, "name")

    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """
        INSERT INTO systems (path, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (path, name, description, now, now),
    )

    result = db.fetchone("SELECT * FROM systems WHERE path = ?", (path,))
    return _row_to_dict(result)


def get_system(db: ContextDB, path: str) -> dict[str, Any] | None:
    """Get a system by path.

    Args:
        db: Database connection.
        path: System path to retrieve.

    Returns:
        Dictionary with system data, or None if not found.
    """
    result = db.fetchone("SELECT * FROM systems WHERE path = ?", (path,))
    return _row_to_dict(result) if result is not None else None


def list_systems(db: ContextDB) -> list[dict[str, Any]]:
    """List all systems.

    Args:
        db: Database connection.

    Returns:
        List of system dictionaries, sorted by path.
    """
    results = db.fetchall("SELECT * FROM systems ORDER BY path")
    return [_row_to_dict(row) for row in results]


def update_system(
    db: ContextDB, path: str, name: str | None = None, description: str | None = None
) -> bool:
    """Update a system's name and/or description.

    Args:
        db: Database connection.
        path: System path to update.
        name: New system name (optional).
        description: New system description (optional).

    Returns:
        True if row was updated, False if system not found.
    """
    if name is None and description is None:
        return False

    now = datetime.now(timezone.utc).isoformat()

    if name is not None and description is not None:
        cursor = db.execute(
            "UPDATE systems SET name = ?, description = ?, updated_at = ? WHERE path = ?",
            (name, description, now, path),
        )
    elif name is not None:
        cursor = db.execute(
            "UPDATE systems SET name = ?, updated_at = ? WHERE path = ?",
            (name, now, path),
        )
    else:  # description is not None
        cursor = db.execute(
            "UPDATE systems SET description = ?, updated_at = ? WHERE path = ?",
            (description, now, path),
        )

    return cursor.rowcount > 0


def delete_system(db: ContextDB, path: str) -> bool:
    """Delete a system by path.

    Cascade deletes all dependencies involving this system.

    Args:
        db: Database connection.
        path: System path to delete.

    Returns:
        True if row was deleted, False if system not found.
    """
    cursor = db.execute("DELETE FROM systems WHERE path = ?", (path,))
    return cursor.rowcount > 0


# System Dependencies CRUD Operations


def add_dependency(db: ContextDB, system_path: str, depends_on: str) -> bool:
    """Add a dependency relationship.

    Indicates that system_path depends on depends_on.

    Args:
        db: Database connection.
        system_path: Path of the dependent system.
        depends_on: Path of the system being depended on.

    Returns:
        True if dependency was created.

    Raises:
        ValueError: If system_path or depends_on is invalid.
        sqlite3.IntegrityError: If systems don't exist or dependency already exists.
    """
    _validate_path(system_path, "system_path")
    _validate_path(depends_on, "depends_on")

    db.execute(
        """
        INSERT INTO system_dependencies (system_path, depends_on)
        VALUES (?, ?)
        """,
        (system_path, depends_on),
    )
    return True


def remove_dependency(db: ContextDB, system_path: str, depends_on: str) -> bool:
    """Remove a dependency relationship.

    Args:
        db: Database connection.
        system_path: Path of the dependent system.
        depends_on: Path of the system being depended on.

    Returns:
        True if dependency was removed, False if not found.
    """
    cursor = db.execute(
        "DELETE FROM system_dependencies WHERE system_path = ? AND depends_on = ?",
        (system_path, depends_on),
    )
    return cursor.rowcount > 0


def get_dependencies(db: ContextDB, system_path: str) -> list[dict[str, Any]]:
    """Get systems that a system depends on.

    Returns the systems that system_path explicitly depends on.

    Args:
        db: Database connection.
        system_path: System path to query.

    Returns:
        List of system dictionaries that system_path depends on, sorted by path.
    """
    results = db.fetchall(
        """
        SELECT s.* FROM systems s
        JOIN system_dependencies sd ON s.path = sd.depends_on
        WHERE sd.system_path = ?
        ORDER BY s.path
        """,
        (system_path,),
    )
    return [_row_to_dict(row) for row in results]


def get_dependents(db: ContextDB, system_path: str) -> list[dict[str, Any]]:
    """Get systems that depend on a system.

    Returns systems that explicitly depend on system_path.

    Args:
        db: Database connection.
        system_path: System path to query.

    Returns:
        List of system dictionaries that depend on system_path, sorted by path.
    """
    results = db.fetchall(
        """
        SELECT s.* FROM systems s
        JOIN system_dependencies sd ON s.path = sd.system_path
        WHERE sd.depends_on = ?
        ORDER BY s.path
        """,
        (system_path,),
    )
    return [_row_to_dict(row) for row in results]
