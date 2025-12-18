"""Tests for cctx.adr_crud module."""

from __future__ import annotations

import sqlite3
import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from cctx.adr_crud import (
    add_tag,
    create_adr,
    delete_adr,
    get_adr,
    get_adrs_by_tag,
    get_adrs_for_system,
    get_systems_for_adr,
    get_tags,
    link_adr_to_system,
    list_adrs,
    remove_tag,
    unlink_adr_from_system,
    update_adr,
)
from cctx.crud import create_system
from cctx.database import ContextDB


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


class TestCreateAdr:
    """Tests for create_adr function."""

    def test_create_adr_basic(self, initialized_db: ContextDB) -> None:
        """Test creating an ADR with required fields."""
        with initialized_db.transaction():
            result = create_adr(
                initialized_db,
                id="ADR-001",
                title="Use SQLite for storage",
                status="proposed",
                file_path="src/systems/data/.ctx/adr/ADR-001.md",
            )

        assert result["id"] == "ADR-001"
        assert result["title"] == "Use SQLite for storage"
        assert result["status"] == "proposed"
        assert result["file_path"] == "src/systems/data/.ctx/adr/ADR-001.md"
        assert result["created_at"] is not None
        assert result["updated_at"] is not None
        assert result["created_at"] == result["updated_at"]

    def test_create_adr_with_all_fields(self, initialized_db: ContextDB) -> None:
        """Test creating an ADR with all optional fields."""
        with initialized_db.transaction():
            result = create_adr(
                initialized_db,
                id="ADR-001",
                title="Use SQLite for storage",
                status="accepted",
                file_path="src/systems/data/.ctx/adr/ADR-001.md",
                context="We need a lightweight database solution.",
                decision="Use SQLite for local storage.",
                consequences="File-based, portable, but single-writer.",
            )

        assert result["context"] == "We need a lightweight database solution."
        assert result["decision"] == "Use SQLite for local storage."
        assert result["consequences"] == "File-based, portable, but single-writer."

    def test_create_adr_duplicate_id_raises(self, initialized_db: ContextDB) -> None:
        """Test creating duplicate ADR raises error."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-001",
                title="First ADR",
                status="proposed",
                file_path="path1.md",
            )

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-001",
                title="Second ADR",
                status="proposed",
                file_path="path2.md",
            )

    def test_create_adr_duplicate_file_path_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with duplicate file_path raises error."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-001",
                title="First ADR",
                status="proposed",
                file_path="same/path.md",
            )

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-002",
                title="Second ADR",
                status="proposed",
                file_path="same/path.md",
            )

    def test_create_adr_valid_statuses(self, initialized_db: ContextDB) -> None:
        """Test creating ADRs with all valid status values."""
        valid_statuses = ["proposed", "accepted", "deprecated", "superseded"]
        for i, status in enumerate(valid_statuses):
            with initialized_db.transaction():
                result = create_adr(
                    initialized_db,
                    id=f"ADR-{i:03d}",
                    title=f"ADR with status {status}",
                    status=status,
                    file_path=f"path{i}.md",
                )
            assert result["status"] == status

    def test_create_adr_persists(self, initialized_db: ContextDB) -> None:
        """Test created ADR persists in database."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-001",
                title="Test ADR",
                status="proposed",
                file_path="test.md",
            )

        result = get_adr(initialized_db, "ADR-001")
        assert result is not None
        assert result["title"] == "Test ADR"


class TestGetAdr:
    """Tests for get_adr function."""

    def test_get_adr_exists(self, initialized_db: ContextDB) -> None:
        """Test getting an existing ADR."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-001",
                title="Test ADR",
                status="accepted",
                file_path="test.md",
            )

        result = get_adr(initialized_db, "ADR-001")
        assert result is not None
        assert result["id"] == "ADR-001"
        assert result["title"] == "Test ADR"
        assert result["status"] == "accepted"

    def test_get_adr_not_found(self, initialized_db: ContextDB) -> None:
        """Test getting non-existent ADR returns None."""
        result = get_adr(initialized_db, "ADR-999")
        assert result is None

    def test_get_adr_returns_dict(self, initialized_db: ContextDB) -> None:
        """Test get_adr returns dict type."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-001",
                title="Test ADR",
                status="proposed",
                file_path="test.md",
            )

        result = get_adr(initialized_db, "ADR-001")
        assert isinstance(result, dict)
        assert "id" in result
        assert "title" in result
        assert "status" in result
        assert "file_path" in result
        assert "created_at" in result
        assert "updated_at" in result


class TestListAdrs:
    """Tests for list_adrs function."""

    def test_list_adrs_empty(self, initialized_db: ContextDB) -> None:
        """Test listing ADRs when none exist."""
        results = list_adrs(initialized_db)
        assert results == []

    def test_list_adrs_single(self, initialized_db: ContextDB) -> None:
        """Test listing with one ADR."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                id="ADR-001",
                title="Test ADR",
                status="proposed",
                file_path="test.md",
            )

        results = list_adrs(initialized_db)
        assert len(results) == 1
        assert results[0]["id"] == "ADR-001"

    def test_list_adrs_multiple(self, initialized_db: ContextDB) -> None:
        """Test listing multiple ADRs."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")
            create_adr(initialized_db, "ADR-002", "Second", "accepted", "2.md")
            create_adr(initialized_db, "ADR-003", "Third", "deprecated", "3.md")

        results = list_adrs(initialized_db)
        assert len(results) == 3

    def test_list_adrs_sorted_by_id(self, initialized_db: ContextDB) -> None:
        """Test ADRs are returned sorted by id."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-003", "Third", "proposed", "3.md")
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")
            create_adr(initialized_db, "ADR-002", "Second", "proposed", "2.md")

        results = list_adrs(initialized_db)
        ids = [r["id"] for r in results]
        assert ids == ["ADR-001", "ADR-002", "ADR-003"]

    def test_list_adrs_filter_by_status(self, initialized_db: ContextDB) -> None:
        """Test listing ADRs filtered by status."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")
            create_adr(initialized_db, "ADR-002", "Second", "accepted", "2.md")
            create_adr(initialized_db, "ADR-003", "Third", "accepted", "3.md")
            create_adr(initialized_db, "ADR-004", "Fourth", "deprecated", "4.md")

        results = list_adrs(initialized_db, status="accepted")
        assert len(results) == 2
        assert all(r["status"] == "accepted" for r in results)

    def test_list_adrs_filter_empty_result(self, initialized_db: ContextDB) -> None:
        """Test filtering returns empty when no matches."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")

        results = list_adrs(initialized_db, status="superseded")
        assert results == []

    def test_list_adrs_returns_list_of_dicts(self, initialized_db: ContextDB) -> None:
        """Test list_adrs returns list of dicts."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        results = list_adrs(initialized_db)
        assert isinstance(results, list)
        assert isinstance(results[0], dict)


class TestUpdateAdr:
    """Tests for update_adr function."""

    def test_update_adr_title(self, initialized_db: ContextDB) -> None:
        """Test updating ADR title."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Original", "proposed", "test.md")

        with initialized_db.transaction():
            result = update_adr(initialized_db, "ADR-001", title="Updated Title")

        assert result is True
        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["title"] == "Updated Title"

    def test_update_adr_status(self, initialized_db: ContextDB) -> None:
        """Test updating ADR status."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = update_adr(initialized_db, "ADR-001", status="accepted")

        assert result is True
        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["status"] == "accepted"

    def test_update_adr_context(self, initialized_db: ContextDB) -> None:
        """Test updating ADR context."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = update_adr(initialized_db, "ADR-001", context="New context")

        assert result is True
        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["context"] == "New context"

    def test_update_adr_decision(self, initialized_db: ContextDB) -> None:
        """Test updating ADR decision."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = update_adr(initialized_db, "ADR-001", decision="New decision")

        assert result is True
        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["decision"] == "New decision"

    def test_update_adr_consequences(self, initialized_db: ContextDB) -> None:
        """Test updating ADR consequences."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = update_adr(initialized_db, "ADR-001", consequences="New consequences")

        assert result is True
        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["consequences"] == "New consequences"

    def test_update_adr_multiple_fields(self, initialized_db: ContextDB) -> None:
        """Test updating multiple ADR fields at once."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = update_adr(
                initialized_db,
                "ADR-001",
                title="New Title",
                status="accepted",
                context="New context",
            )

        assert result is True
        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["title"] == "New Title"
        assert updated["status"] == "accepted"
        assert updated["context"] == "New context"

    def test_update_adr_not_found(self, initialized_db: ContextDB) -> None:
        """Test updating non-existent ADR returns False."""
        with initialized_db.transaction():
            result = update_adr(initialized_db, "ADR-999", title="New Title")

        assert result is False

    def test_update_adr_no_fields(self, initialized_db: ContextDB) -> None:
        """Test updating with no fields returns False."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = update_adr(initialized_db, "ADR-001")

        assert result is False

    def test_update_adr_updates_timestamp(self, initialized_db: ContextDB) -> None:
        """Test that update_adr updates the updated_at timestamp."""
        with initialized_db.transaction():
            created = create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            created_at = created["created_at"]

        # Small delay to ensure timestamps differ
        time.sleep(0.01)

        with initialized_db.transaction():
            update_adr(initialized_db, "ADR-001", title="New Title")

        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["updated_at"] > created_at


class TestDeleteAdr:
    """Tests for delete_adr function."""

    def test_delete_adr_exists(self, initialized_db: ContextDB) -> None:
        """Test deleting an existing ADR."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = delete_adr(initialized_db, "ADR-001")

        assert result is True
        deleted = get_adr(initialized_db, "ADR-001")
        assert deleted is None

    def test_delete_adr_not_found(self, initialized_db: ContextDB) -> None:
        """Test deleting non-existent ADR returns False."""
        with initialized_db.transaction():
            result = delete_adr(initialized_db, "ADR-999")

        assert result is False

    def test_delete_adr_cascade_deletes_tags(self, initialized_db: ContextDB) -> None:
        """Test that deleting an ADR cascade deletes its tags."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")
            add_tag(initialized_db, "ADR-001", "storage")

        with initialized_db.transaction():
            delete_adr(initialized_db, "ADR-001")

        # Verify tags were deleted (query the raw table)
        result = initialized_db.fetchall("SELECT * FROM adr_tags WHERE adr_id = ?", ("ADR-001",))
        assert len(result) == 0

    def test_delete_adr_cascade_deletes_system_links(self, initialized_db: ContextDB) -> None:
        """Test that deleting an ADR cascade deletes its system links."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        with initialized_db.transaction():
            delete_adr(initialized_db, "ADR-001")

        # Verify system links were deleted
        result = initialized_db.fetchall("SELECT * FROM adr_systems WHERE adr_id = ?", ("ADR-001",))
        assert len(result) == 0


class TestLinkAdrToSystem:
    """Tests for link_adr_to_system function."""

    def test_link_adr_to_system_creates_link(self, initialized_db: ContextDB) -> None:
        """Test linking an ADR to a system creates the relationship."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            result = link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        assert result is True

        # Verify via raw query
        links = initialized_db.fetchall("SELECT * FROM adr_systems WHERE adr_id = ?", ("ADR-001",))
        assert len(links) == 1
        assert links[0]["system_path"] == "src/systems/data"

    def test_link_adr_to_system_nonexistent_adr_raises(self, initialized_db: ContextDB) -> None:
        """Test linking non-existent ADR raises error."""
        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            link_adr_to_system(initialized_db, "ADR-999", "src/systems/data")

    def test_link_adr_to_system_duplicate_raises(self, initialized_db: ContextDB) -> None:
        """Test linking duplicate ADR-system raises error."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

    def test_link_adr_to_multiple_systems(self, initialized_db: ContextDB) -> None:
        """Test linking an ADR to multiple systems."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/api")

        links = initialized_db.fetchall("SELECT * FROM adr_systems WHERE adr_id = ?", ("ADR-001",))
        assert len(links) == 2


class TestUnlinkAdrFromSystem:
    """Tests for unlink_adr_from_system function."""

    def test_unlink_adr_from_system_exists(self, initialized_db: ContextDB) -> None:
        """Test unlinking an existing ADR-system link."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        with initialized_db.transaction():
            result = unlink_adr_from_system(initialized_db, "ADR-001", "src/systems/data")

        assert result is True
        links = initialized_db.fetchall("SELECT * FROM adr_systems WHERE adr_id = ?", ("ADR-001",))
        assert len(links) == 0

    def test_unlink_adr_from_system_not_found(self, initialized_db: ContextDB) -> None:
        """Test unlinking non-existent link returns False."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = unlink_adr_from_system(initialized_db, "ADR-001", "src/systems/data")

        assert result is False

    def test_unlink_adr_keeps_other_links(self, initialized_db: ContextDB) -> None:
        """Test unlinking one link doesn't affect others."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/api")

        with initialized_db.transaction():
            unlink_adr_from_system(initialized_db, "ADR-001", "src/systems/data")

        links = initialized_db.fetchall("SELECT * FROM adr_systems WHERE adr_id = ?", ("ADR-001",))
        assert len(links) == 1
        assert links[0]["system_path"] == "src/systems/api"


class TestGetAdrsForSystem:
    """Tests for get_adrs_for_system function."""

    def test_get_adrs_for_system_empty(self, initialized_db: ContextDB) -> None:
        """Test getting ADRs when system has none."""
        adrs = get_adrs_for_system(initialized_db, "src/systems/data")
        assert adrs == []

    def test_get_adrs_for_system_single(self, initialized_db: ContextDB) -> None:
        """Test getting a single ADR for a system."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        adrs = get_adrs_for_system(initialized_db, "src/systems/data")
        assert len(adrs) == 1
        assert adrs[0]["id"] == "ADR-001"

    def test_get_adrs_for_system_multiple(self, initialized_db: ContextDB) -> None:
        """Test getting multiple ADRs for a system."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")
            create_adr(initialized_db, "ADR-002", "Second", "accepted", "2.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-002", "src/systems/data")

        adrs = get_adrs_for_system(initialized_db, "src/systems/data")
        assert len(adrs) == 2

    def test_get_adrs_for_system_sorted(self, initialized_db: ContextDB) -> None:
        """Test ADRs are sorted by id."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-003", "Third", "proposed", "3.md")
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")
            link_adr_to_system(initialized_db, "ADR-003", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        adrs = get_adrs_for_system(initialized_db, "src/systems/data")
        ids = [a["id"] for a in adrs]
        assert ids == ["ADR-001", "ADR-003"]

    def test_get_adrs_for_system_returns_full_adr_info(self, initialized_db: ContextDB) -> None:
        """Test get_adrs_for_system returns full ADR info."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                "ADR-001",
                "Test ADR",
                "accepted",
                "test.md",
                context="Test context",
            )
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        adrs = get_adrs_for_system(initialized_db, "src/systems/data")
        assert adrs[0]["title"] == "Test ADR"
        assert adrs[0]["status"] == "accepted"
        assert adrs[0]["context"] == "Test context"
        assert "created_at" in adrs[0]


class TestGetSystemsForAdr:
    """Tests for get_systems_for_adr function."""

    def test_get_systems_for_adr_empty(self, initialized_db: ContextDB) -> None:
        """Test getting systems when ADR has none linked."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        systems = get_systems_for_adr(initialized_db, "ADR-001")
        assert systems == []

    def test_get_systems_for_adr_single(self, initialized_db: ContextDB) -> None:
        """Test getting a single system for an ADR."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/data", "Data System")
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        systems = get_systems_for_adr(initialized_db, "ADR-001")
        assert len(systems) == 1
        assert systems[0]["path"] == "src/systems/data"
        assert systems[0]["name"] == "Data System"

    def test_get_systems_for_adr_multiple(self, initialized_db: ContextDB) -> None:
        """Test getting multiple systems for an ADR."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/data", "Data System")
            create_system(initialized_db, "src/systems/api", "API System")
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/api")

        systems = get_systems_for_adr(initialized_db, "ADR-001")
        assert len(systems) == 2

    def test_get_systems_for_adr_sorted(self, initialized_db: ContextDB) -> None:
        """Test systems are sorted by path."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/zebra", "Z System")
            create_system(initialized_db, "src/systems/apple", "A System")
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/zebra")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/apple")

        systems = get_systems_for_adr(initialized_db, "ADR-001")
        paths = [s["path"] for s in systems]
        assert paths == ["src/systems/apple", "src/systems/zebra"]

    def test_get_systems_for_adr_returns_full_system_info(self, initialized_db: ContextDB) -> None:
        """Test get_systems_for_adr returns full system info."""
        with initialized_db.transaction():
            create_system(
                initialized_db,
                "src/systems/data",
                "Data System",
                description="Handles data storage",
            )
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")

        systems = get_systems_for_adr(initialized_db, "ADR-001")
        assert systems[0]["name"] == "Data System"
        assert systems[0]["description"] == "Handles data storage"
        assert "created_at" in systems[0]


class TestAddTag:
    """Tests for add_tag function."""

    def test_add_tag_creates_tag(self, initialized_db: ContextDB) -> None:
        """Test adding a tag to an ADR."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            result = add_tag(initialized_db, "ADR-001", "database")

        assert result is True
        tags = get_tags(initialized_db, "ADR-001")
        assert "database" in tags

    def test_add_tag_normalizes_to_lowercase(self, initialized_db: ContextDB) -> None:
        """Test tags are normalized to lowercase."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "DATABASE")
            add_tag(initialized_db, "ADR-001", "Storage")

        tags = get_tags(initialized_db, "ADR-001")
        assert "database" in tags
        assert "storage" in tags
        assert "DATABASE" not in tags
        assert "Storage" not in tags

    def test_add_tag_nonexistent_adr_raises(self, initialized_db: ContextDB) -> None:
        """Test adding tag to non-existent ADR raises error."""
        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            add_tag(initialized_db, "ADR-999", "database")

    def test_add_tag_duplicate_raises(self, initialized_db: ContextDB) -> None:
        """Test adding duplicate tag raises error."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            add_tag(initialized_db, "ADR-001", "database")

    def test_add_tag_duplicate_different_case_raises(self, initialized_db: ContextDB) -> None:
        """Test adding tag with different case is treated as duplicate."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        with pytest.raises(sqlite3.IntegrityError), initialized_db.transaction():
            add_tag(initialized_db, "ADR-001", "DATABASE")

    def test_add_multiple_tags(self, initialized_db: ContextDB) -> None:
        """Test adding multiple tags to same ADR."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")
            add_tag(initialized_db, "ADR-001", "storage")
            add_tag(initialized_db, "ADR-001", "architecture")

        tags = get_tags(initialized_db, "ADR-001")
        assert len(tags) == 3


class TestRemoveTag:
    """Tests for remove_tag function."""

    def test_remove_tag_exists(self, initialized_db: ContextDB) -> None:
        """Test removing an existing tag."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        with initialized_db.transaction():
            result = remove_tag(initialized_db, "ADR-001", "database")

        assert result is True
        tags = get_tags(initialized_db, "ADR-001")
        assert "database" not in tags

    def test_remove_tag_not_found(self, initialized_db: ContextDB) -> None:
        """Test removing non-existent tag returns False."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with initialized_db.transaction():
            result = remove_tag(initialized_db, "ADR-001", "nonexistent")

        assert result is False

    def test_remove_tag_case_insensitive(self, initialized_db: ContextDB) -> None:
        """Test removing tag with different case works."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        with initialized_db.transaction():
            result = remove_tag(initialized_db, "ADR-001", "DATABASE")

        assert result is True
        tags = get_tags(initialized_db, "ADR-001")
        assert len(tags) == 0

    def test_remove_tag_keeps_other_tags(self, initialized_db: ContextDB) -> None:
        """Test removing one tag doesn't affect others."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")
            add_tag(initialized_db, "ADR-001", "storage")

        with initialized_db.transaction():
            remove_tag(initialized_db, "ADR-001", "database")

        tags = get_tags(initialized_db, "ADR-001")
        assert len(tags) == 1
        assert "storage" in tags


class TestGetTags:
    """Tests for get_tags function."""

    def test_get_tags_empty(self, initialized_db: ContextDB) -> None:
        """Test getting tags when ADR has none."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        tags = get_tags(initialized_db, "ADR-001")
        assert tags == []

    def test_get_tags_single(self, initialized_db: ContextDB) -> None:
        """Test getting a single tag."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        tags = get_tags(initialized_db, "ADR-001")
        assert tags == ["database"]

    def test_get_tags_multiple(self, initialized_db: ContextDB) -> None:
        """Test getting multiple tags."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")
            add_tag(initialized_db, "ADR-001", "storage")

        tags = get_tags(initialized_db, "ADR-001")
        assert len(tags) == 2

    def test_get_tags_sorted(self, initialized_db: ContextDB) -> None:
        """Test tags are returned sorted alphabetically."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "zebra")
            add_tag(initialized_db, "ADR-001", "apple")
            add_tag(initialized_db, "ADR-001", "banana")

        tags = get_tags(initialized_db, "ADR-001")
        assert tags == ["apple", "banana", "zebra"]

    def test_get_tags_returns_strings(self, initialized_db: ContextDB) -> None:
        """Test get_tags returns list of strings."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        tags = get_tags(initialized_db, "ADR-001")
        assert isinstance(tags, list)
        assert all(isinstance(t, str) for t in tags)


class TestGetAdrsByTag:
    """Tests for get_adrs_by_tag function."""

    def test_get_adrs_by_tag_empty(self, initialized_db: ContextDB) -> None:
        """Test getting ADRs by tag when none have it."""
        adrs = get_adrs_by_tag(initialized_db, "database")
        assert adrs == []

    def test_get_adrs_by_tag_single(self, initialized_db: ContextDB) -> None:
        """Test getting a single ADR by tag."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        adrs = get_adrs_by_tag(initialized_db, "database")
        assert len(adrs) == 1
        assert adrs[0]["id"] == "ADR-001"

    def test_get_adrs_by_tag_multiple(self, initialized_db: ContextDB) -> None:
        """Test getting multiple ADRs by tag."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")
            create_adr(initialized_db, "ADR-002", "Second", "accepted", "2.md")
            add_tag(initialized_db, "ADR-001", "database")
            add_tag(initialized_db, "ADR-002", "database")

        adrs = get_adrs_by_tag(initialized_db, "database")
        assert len(adrs) == 2

    def test_get_adrs_by_tag_case_insensitive(self, initialized_db: ContextDB) -> None:
        """Test getting ADRs by tag is case insensitive."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        adrs = get_adrs_by_tag(initialized_db, "DATABASE")
        assert len(adrs) == 1
        assert adrs[0]["id"] == "ADR-001"

    def test_get_adrs_by_tag_sorted(self, initialized_db: ContextDB) -> None:
        """Test ADRs are sorted by id."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-003", "Third", "proposed", "3.md")
            create_adr(initialized_db, "ADR-001", "First", "proposed", "1.md")
            add_tag(initialized_db, "ADR-003", "database")
            add_tag(initialized_db, "ADR-001", "database")

        adrs = get_adrs_by_tag(initialized_db, "database")
        ids = [a["id"] for a in adrs]
        assert ids == ["ADR-001", "ADR-003"]

    def test_get_adrs_by_tag_returns_full_adr_info(self, initialized_db: ContextDB) -> None:
        """Test get_adrs_by_tag returns full ADR info."""
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                "ADR-001",
                "Test ADR",
                "accepted",
                "test.md",
                context="Test context",
            )
            add_tag(initialized_db, "ADR-001", "database")

        adrs = get_adrs_by_tag(initialized_db, "database")
        assert adrs[0]["title"] == "Test ADR"
        assert adrs[0]["status"] == "accepted"
        assert adrs[0]["context"] == "Test context"
        assert "created_at" in adrs[0]


class TestInputValidation:
    """Tests for input validation in ADR CRUD functions."""

    def test_create_adr_empty_id_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with empty id raises ValueError."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            create_adr(initialized_db, "", "Test ADR", "proposed", "test.md")

    def test_create_adr_whitespace_only_id_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with whitespace-only id raises ValueError."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            create_adr(initialized_db, "   ", "Test ADR", "proposed", "test.md")

    def test_create_adr_id_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with id exceeding max length raises ValueError."""
        long_id = "a" * 129
        with pytest.raises(ValueError, match="exceeds maximum length"):
            create_adr(initialized_db, long_id, "Test ADR", "proposed", "test.md")

    def test_create_adr_empty_title_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with empty title raises ValueError."""
        with pytest.raises(ValueError, match="title cannot be empty"):
            create_adr(initialized_db, "ADR-001", "", "proposed", "test.md")

    def test_create_adr_whitespace_only_title_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with whitespace-only title raises ValueError."""
        with pytest.raises(ValueError, match="title cannot be empty"):
            create_adr(initialized_db, "ADR-001", "   ", "proposed", "test.md")

    def test_create_adr_title_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with title exceeding max length raises ValueError."""
        long_title = "a" * 513
        with pytest.raises(ValueError, match="exceeds maximum length"):
            create_adr(initialized_db, "ADR-001", long_title, "proposed", "test.md")

    def test_create_adr_empty_file_path_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with empty file_path raises ValueError."""
        with pytest.raises(ValueError, match="file_path cannot be empty"):
            create_adr(initialized_db, "ADR-001", "Test ADR", "proposed", "")

    def test_create_adr_whitespace_only_file_path_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with whitespace-only file_path raises ValueError."""
        with pytest.raises(ValueError, match="file_path cannot be empty"):
            create_adr(initialized_db, "ADR-001", "Test ADR", "proposed", "   ")

    def test_create_adr_file_path_traversal_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with path traversal in file_path raises ValueError."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            create_adr(initialized_db, "ADR-001", "Test ADR", "proposed", "../../../etc/passwd")

    def test_create_adr_file_path_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test creating ADR with file_path exceeding max length raises ValueError."""
        long_path = "a" * 513
        with pytest.raises(ValueError, match="exceeds maximum length"):
            create_adr(initialized_db, "ADR-001", "Test ADR", "proposed", long_path)

    def test_add_tag_empty_tag_raises(self, initialized_db: ContextDB) -> None:
        """Test adding empty tag raises ValueError."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with pytest.raises(ValueError, match="tag cannot be empty"):
            add_tag(initialized_db, "ADR-001", "")

    def test_add_tag_whitespace_only_tag_raises(self, initialized_db: ContextDB) -> None:
        """Test adding whitespace-only tag raises ValueError."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        with pytest.raises(ValueError, match="tag cannot be empty"):
            add_tag(initialized_db, "ADR-001", "   ")

    def test_add_tag_tag_too_long_raises(self, initialized_db: ContextDB) -> None:
        """Test adding tag exceeding max length raises ValueError."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")

        long_tag = "a" * 65
        with pytest.raises(ValueError, match="exceeds maximum length"):
            add_tag(initialized_db, "ADR-001", long_tag)


class TestComplexScenarios:
    """Tests for complex ADR CRUD scenarios."""

    def test_adr_with_systems_and_tags(self, initialized_db: ContextDB) -> None:
        """Test ADR with both system links and tags."""
        with initialized_db.transaction():
            create_system(initialized_db, "src/systems/data", "Data System")
            create_system(initialized_db, "src/systems/api", "API System")
            create_adr(
                initialized_db,
                "ADR-001",
                "Use SQLite",
                "accepted",
                "test.md",
                context="Need local storage",
                decision="Use SQLite",
            )
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/api")
            add_tag(initialized_db, "ADR-001", "database")
            add_tag(initialized_db, "ADR-001", "storage")

        # Verify all relationships
        systems = get_systems_for_adr(initialized_db, "ADR-001")
        tags = get_tags(initialized_db, "ADR-001")

        assert len(systems) == 2
        assert len(tags) == 2

    def test_multiple_adrs_per_system(self, initialized_db: ContextDB) -> None:
        """Test multiple ADRs can be linked to the same system."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "First", "accepted", "1.md")
            create_adr(initialized_db, "ADR-002", "Second", "proposed", "2.md")
            create_adr(initialized_db, "ADR-003", "Third", "deprecated", "3.md")
            link_adr_to_system(initialized_db, "ADR-001", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-002", "src/systems/data")
            link_adr_to_system(initialized_db, "ADR-003", "src/systems/data")

        adrs = get_adrs_for_system(initialized_db, "src/systems/data")
        assert len(adrs) == 3

    def test_shared_tag_across_adrs(self, initialized_db: ContextDB) -> None:
        """Test same tag can be used on multiple ADRs."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "First", "accepted", "1.md")
            create_adr(initialized_db, "ADR-002", "Second", "proposed", "2.md")
            add_tag(initialized_db, "ADR-001", "architecture")
            add_tag(initialized_db, "ADR-002", "architecture")

        adrs = get_adrs_by_tag(initialized_db, "architecture")
        assert len(adrs) == 2

    def test_update_and_delete_sequence(self, initialized_db: ContextDB) -> None:
        """Test sequence of create, update, and delete operations."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Test", "proposed", "test.md")
            add_tag(initialized_db, "ADR-001", "database")

        with initialized_db.transaction():
            update_adr(initialized_db, "ADR-001", status="accepted")

        updated = get_adr(initialized_db, "ADR-001")
        assert updated is not None
        assert updated["status"] == "accepted"

        with initialized_db.transaction():
            delete_adr(initialized_db, "ADR-001")

        deleted = get_adr(initialized_db, "ADR-001")
        assert deleted is None

    def test_adr_supersession_workflow(self, initialized_db: ContextDB) -> None:
        """Test ADR supersession workflow."""
        with initialized_db.transaction():
            create_adr(initialized_db, "ADR-001", "Original decision", "accepted", "1.md")
            add_tag(initialized_db, "ADR-001", "database")

        # Create new ADR that supersedes the first
        with initialized_db.transaction():
            create_adr(
                initialized_db,
                "ADR-002",
                "Updated decision",
                "accepted",
                "2.md",
                context="ADR-001 didn't account for scale",
            )
            add_tag(initialized_db, "ADR-002", "database")

        # Mark old ADR as superseded
        with initialized_db.transaction():
            update_adr(initialized_db, "ADR-001", status="superseded")

        old_adr = get_adr(initialized_db, "ADR-001")
        assert old_adr is not None
        assert old_adr["status"] == "superseded"

        # Both should still be findable by tag
        adrs = get_adrs_by_tag(initialized_db, "database")
        assert len(adrs) == 2
