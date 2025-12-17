"""CRUD operations for ADRs (Architecture Decision Records).

Provides create, read, update, and delete operations for:
- ADRs registry
- ADR-System relationships
- ADR tags
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cctx.database import ContextDB


def _validate_id(id: str, field_name: str = "id") -> None:
    """Validate an ADR id field.

    Args:
        id: The id string to validate.
        field_name: The field name for error messages.

    Raises:
        ValueError: If id is empty or exceeds max length.
    """
    if not id or not id.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if len(id) > 128:
        raise ValueError(f"{field_name} exceeds maximum length (128)")


def _validate_title(title: str, field_name: str = "title") -> None:
    """Validate an ADR title field.

    Args:
        title: The title string to validate.
        field_name: The field name for error messages.

    Raises:
        ValueError: If title is empty or exceeds max length.
    """
    if not title or not title.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if len(title) > 512:
        raise ValueError(f"{field_name} exceeds maximum length (512)")


def _validate_file_path(file_path: str, field_name: str = "file_path") -> None:
    """Validate an ADR file path field.

    Args:
        file_path: The file_path string to validate.
        field_name: The field name for error messages.

    Raises:
        ValueError: If file_path is empty, exceeds max length, or contains path traversal.
    """
    if not file_path or not file_path.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if len(file_path) > 512:
        raise ValueError(f"{field_name} exceeds maximum length (512)")
    if ".." in file_path:
        raise ValueError(f"Path traversal not allowed in {field_name}")


def _validate_tag(tag: str, field_name: str = "tag") -> None:
    """Validate a tag field.

    Args:
        tag: The tag string to validate.
        field_name: The field name for error messages.

    Raises:
        ValueError: If tag is empty or exceeds max length.
    """
    if not tag or not tag.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if len(tag) > 64:
        raise ValueError(f"{field_name} exceeds maximum length (64)")


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


# ADRs CRUD Operations


def create_adr(
    db: ContextDB,
    id: str,
    title: str,
    status: str,
    file_path: str,
    context: str | None = None,
    decision: str | None = None,
    consequences: str | None = None,
) -> dict[str, Any]:
    """Create a new ADR.

    Args:
        db: Database connection.
        id: ADR identifier (e.g., "ADR-001").
        title: Human-readable ADR title.
        status: ADR status (proposed, accepted, deprecated, superseded).
        file_path: Path to the ADR markdown file.
        context: Optional context/background for the decision.
        decision: Optional description of the decision made.
        consequences: Optional description of consequences.

    Returns:
        Dictionary with created ADR data.

    Raises:
        ValueError: If id, title, or file_path is invalid.
        sqlite3.IntegrityError: If ADR already exists or status is invalid.
    """
    _validate_id(id, "id")
    _validate_title(title, "title")
    _validate_file_path(file_path, "file_path")

    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """
        INSERT INTO adrs (id, title, status, file_path, context, decision, consequences, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (id, title, status, file_path, context, decision, consequences, now, now),
    )

    result = db.fetchone("SELECT * FROM adrs WHERE id = ?", (id,))
    return _row_to_dict(result)


def get_adr(db: ContextDB, id: str) -> dict[str, Any] | None:
    """Get an ADR by id.

    Args:
        db: Database connection.
        id: ADR identifier to retrieve.

    Returns:
        Dictionary with ADR data, or None if not found.
    """
    result = db.fetchone("SELECT * FROM adrs WHERE id = ?", (id,))
    return _row_to_dict(result) if result is not None else None


def list_adrs(db: ContextDB, status: str | None = None) -> list[dict[str, Any]]:
    """List all ADRs, optionally filtered by status.

    Args:
        db: Database connection.
        status: Optional status filter (proposed, accepted, deprecated, superseded).

    Returns:
        List of ADR dictionaries, sorted by id.
    """
    if status is not None:
        results = db.fetchall(
            "SELECT * FROM adrs WHERE status = ? ORDER BY id",
            (status,),
        )
    else:
        results = db.fetchall("SELECT * FROM adrs ORDER BY id")
    return [_row_to_dict(row) for row in results]


def update_adr(
    db: ContextDB,
    id: str,
    title: str | None = None,
    status: str | None = None,
    context: str | None = None,
    decision: str | None = None,
    consequences: str | None = None,
) -> bool:
    """Update an ADR's fields.

    Args:
        db: Database connection.
        id: ADR identifier to update.
        title: New ADR title (optional).
        status: New ADR status (optional).
        context: New context (optional).
        decision: New decision (optional).
        consequences: New consequences (optional).

    Returns:
        True if row was updated, False if ADR not found.
    """
    # Build SET clause with explicit field names (no dynamic SQL from user input)
    set_clauses: list[str] = []
    params: list[Any] = []

    if title is not None:
        set_clauses.append("title = ?")
        params.append(title)
    if status is not None:
        set_clauses.append("status = ?")
        params.append(status)
    if context is not None:
        set_clauses.append("context = ?")
        params.append(context)
    if decision is not None:
        set_clauses.append("decision = ?")
        params.append(decision)
    if consequences is not None:
        set_clauses.append("consequences = ?")
        params.append(consequences)

    if not set_clauses:
        return False

    now = datetime.now(timezone.utc).isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now)
    params.append(id)  # For WHERE clause

    sql = "UPDATE adrs SET " + ", ".join(set_clauses) + " WHERE id = ?"
    cursor = db.execute(sql, tuple(params))
    return cursor.rowcount > 0


def delete_adr(db: ContextDB, id: str) -> bool:
    """Delete an ADR by id.

    Cascade deletes all associated tags and system links.

    Args:
        db: Database connection.
        id: ADR identifier to delete.

    Returns:
        True if row was deleted, False if ADR not found.
    """
    cursor = db.execute("DELETE FROM adrs WHERE id = ?", (id,))
    return cursor.rowcount > 0


# ADR-System Relationship Operations


def link_adr_to_system(db: ContextDB, adr_id: str, system_path: str) -> bool:
    """Link an ADR to a system.

    Args:
        db: Database connection.
        adr_id: ADR identifier.
        system_path: Path of the system to link.

    Returns:
        True if link was created.

    Raises:
        sqlite3.IntegrityError: If ADR doesn't exist or link already exists.
    """
    db.execute(
        """
        INSERT INTO adr_systems (adr_id, system_path)
        VALUES (?, ?)
        """,
        (adr_id, system_path),
    )
    return True


def unlink_adr_from_system(db: ContextDB, adr_id: str, system_path: str) -> bool:
    """Remove link between an ADR and a system.

    Args:
        db: Database connection.
        adr_id: ADR identifier.
        system_path: Path of the system to unlink.

    Returns:
        True if link was removed, False if not found.
    """
    cursor = db.execute(
        "DELETE FROM adr_systems WHERE adr_id = ? AND system_path = ?",
        (adr_id, system_path),
    )
    return cursor.rowcount > 0


def get_adrs_for_system(db: ContextDB, system_path: str) -> list[dict[str, Any]]:
    """Get all ADRs associated with a system.

    Args:
        db: Database connection.
        system_path: System path to query.

    Returns:
        List of ADR dictionaries for the system, sorted by id.
    """
    results = db.fetchall(
        """
        SELECT a.* FROM adrs a
        JOIN adr_systems ars ON a.id = ars.adr_id
        WHERE ars.system_path = ?
        ORDER BY a.id
        """,
        (system_path,),
    )
    return [_row_to_dict(row) for row in results]


def get_systems_for_adr(db: ContextDB, adr_id: str) -> list[dict[str, Any]]:
    """Get all systems associated with an ADR.

    Args:
        db: Database connection.
        adr_id: ADR identifier to query.

    Returns:
        List of system dictionaries for the ADR, sorted by path.
    """
    results = db.fetchall(
        """
        SELECT s.* FROM systems s
        JOIN adr_systems ars ON s.path = ars.system_path
        WHERE ars.adr_id = ?
        ORDER BY s.path
        """,
        (adr_id,),
    )
    return [_row_to_dict(row) for row in results]


# ADR Tags Operations


def add_tag(db: ContextDB, adr_id: str, tag: str) -> bool:
    """Add a tag to an ADR.

    Tags are normalized to lowercase before storage.

    Args:
        db: Database connection.
        adr_id: ADR identifier.
        tag: Tag to add.

    Returns:
        True if tag was added.

    Raises:
        ValueError: If tag is invalid.
        sqlite3.IntegrityError: If ADR doesn't exist or tag already exists.
    """
    _validate_tag(tag, "tag")

    normalized_tag = tag.lower()
    db.execute(
        """
        INSERT INTO adr_tags (adr_id, tag)
        VALUES (?, ?)
        """,
        (adr_id, normalized_tag),
    )
    return True


def remove_tag(db: ContextDB, adr_id: str, tag: str) -> bool:
    """Remove a tag from an ADR.

    Args:
        db: Database connection.
        adr_id: ADR identifier.
        tag: Tag to remove.

    Returns:
        True if tag was removed, False if not found.
    """
    normalized_tag = tag.lower()
    cursor = db.execute(
        "DELETE FROM adr_tags WHERE adr_id = ? AND tag = ?",
        (adr_id, normalized_tag),
    )
    return cursor.rowcount > 0


def get_tags(db: ContextDB, adr_id: str) -> list[str]:
    """Get all tags for an ADR.

    Args:
        db: Database connection.
        adr_id: ADR identifier to query.

    Returns:
        List of tags for the ADR, sorted alphabetically.
    """
    results = db.fetchall(
        "SELECT tag FROM adr_tags WHERE adr_id = ? ORDER BY tag",
        (adr_id,),
    )
    return [row["tag"] for row in results]


def get_adrs_by_tag(db: ContextDB, tag: str) -> list[dict[str, Any]]:
    """Get all ADRs with a specific tag.

    Args:
        db: Database connection.
        tag: Tag to search for.

    Returns:
        List of ADR dictionaries with the tag, sorted by id.
    """
    normalized_tag = tag.lower()
    results = db.fetchall(
        """
        SELECT a.* FROM adrs a
        JOIN adr_tags at ON a.id = at.adr_id
        WHERE at.tag = ?
        ORDER BY a.id
        """,
        (normalized_tag,),
    )
    return [_row_to_dict(row) for row in results]
