"""Database schema management for Living Context."""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


def get_schema() -> str:
    """Load the database schema from package resources.

    Returns:
        The SQL schema as a string.

    Raises:
        FileNotFoundError: If schema.sql is not found in package resources.
    """
    # Use importlib.resources to load schema.sql from the data package
    try:
        # For Python 3.9+, use files() API
        schema_text = (
            resources.files("cctx.data").joinpath("schema.sql").read_text(encoding="utf-8")
        )
    except (AttributeError, TypeError):
        # Fallback for older Python versions using pkgutil
        import pkgutil

        raw = pkgutil.get_data("cctx.data", "schema.sql")
        if raw is None:
            raise FileNotFoundError("schema.sql not found in package resources") from None
        schema_text = raw.decode("utf-8")

    return schema_text


def init_database(db_path: str | Path) -> None:
    """Initialize a new database from the schema.

    If the database already exists, this function will apply the schema
    (which uses CREATE TABLE IF NOT EXISTS, so existing tables are preserved).

    Args:
        db_path: Path to the SQLite database file.

    Raises:
        sqlite3.Error: If database initialization fails.
    """
    db_path = Path(db_path)

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database and execute schema
    connection = sqlite3.connect(str(db_path))
    try:
        cursor = connection.cursor()
        schema = get_schema()
        cursor.executescript(schema)
        connection.commit()
    finally:
        connection.close()
