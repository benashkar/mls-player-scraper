"""
Tests for the database module.
===============================

This module tests database operations including connection handling,
initialization, and query functions.

Run these tests with:
    pytest tests/test_db.py -v

NOTE: These tests use a separate test database to avoid affecting
the production data.
"""

import pytest
import sqlite3
import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import scrapers module
sys.path.insert(0, str(Path(__file__).parent.parent))

# We'll mock the DB_PATH for testing
import scrapers.db as db_module


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_db():
    """
    Create a temporary database for testing.

    This fixture:
    1. Creates a temp file for the database
    2. Patches the DB_PATH to use our temp file
    3. Initializes the database schema
    4. Yields the path for use in tests
    5. Cleans up after the test
    """
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test_mls_data.db"

    # Store original path
    original_db_path = db_module.DB_PATH
    original_data_dir = db_module.DATA_DIR

    # Patch the paths
    db_module.DB_PATH = temp_db_path
    db_module.DATA_DIR = Path(temp_dir)

    # Create the schema
    conn = sqlite3.connect(temp_db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team TEXT,
            season INTEGER,
            first_name TEXT,
            last_name TEXT,
            hometown_city TEXT,
            hometown_state TEXT,
            high_school TEXT,
            high_school_city TEXT,
            high_school_state TEXT,
            high_school_source_url TEXT,
            high_school_source_name TEXT,
            position TEXT,
            jersey_number INTEGER,
            height TEXT,
            weight INTEGER,
            birthdate TEXT,
            birthplace TEXT,
            citizenship TEXT,
            headshot_url TEXT,
            bio_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            UNIQUE(team, season, first_name, last_name)
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT UNIQUE,
            season INTEGER,
            match_date DATE,
            match_time TEXT,
            home_team TEXT,
            away_team TEXT,
            venue TEXT,
            competition TEXT,
            broadcast TEXT,
            status TEXT,
            home_score INTEGER,
            away_score INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            home_team_raw TEXT,
            away_team_raw TEXT,
            match_url TEXT
        );

        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            team_slug TEXT,
            url TEXT,
            status TEXT,
            records_found INTEGER DEFAULT 0,
            error_message TEXT,
            scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

    yield temp_db_path

    # Restore original paths
    db_module.DB_PATH = original_db_path
    db_module.DATA_DIR = original_data_dir

    # Clean up temp files
    if temp_db_path.exists():
        os.remove(temp_db_path)
    os.rmdir(temp_dir)


@pytest.fixture
def sample_player():
    """Return a sample player dictionary for testing."""
    return {
        "team": "Test FC",
        "season": 2026,
        "first_name": "John",
        "last_name": "Doe",
        "hometown_city": "Chicago",
        "hometown_state": "IL",
        "position": "Forward",
        "height": "6' 0\"",
        "weight": 180,
    }


# =============================================================================
# Tests for get_connection()
# =============================================================================

class TestGetConnection:
    """Tests for the get_connection function."""

    def test_returns_connection(self, temp_db):
        """Should return a sqlite3 connection."""
        conn = db_module.get_connection()
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_connection_can_execute_query(self, temp_db):
        """Connection should be able to execute queries."""
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        conn.close()

    def test_connection_sees_tables(self, temp_db):
        """Connection should see the created tables."""
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='players'
        """)
        result = cursor.fetchone()
        assert result is not None
        conn.close()


# =============================================================================
# Tests for log_scrape()
# =============================================================================

class TestLogScrape:
    """Tests for the log_scrape function."""

    def test_logs_successful_scrape(self, temp_db):
        """Should log a successful scrape."""
        db_module.log_scrape(
            source="roster",
            team_slug="test-fc",
            url="https://example.com",
            status="success",
            records_found=25
        )

        # Verify it was logged
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scrape_log WHERE source = 'roster'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None

    def test_logs_error_with_message(self, temp_db):
        """Should log an error with error message."""
        db_module.log_scrape(
            source="roster",
            team_slug="test-fc",
            url="https://example.com",
            status="error",
            records_found=0,
            error="Connection timeout"
        )

        # Verify it was logged
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT error_message FROM scrape_log
            WHERE status = 'error'
        """)
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Connection timeout"

    def test_log_with_none_values(self, temp_db):
        """Should handle None values gracefully."""
        db_module.log_scrape(
            source="test",
            team_slug=None,
            url=None,
            status="success",
            records_found=0
        )

        # Should not raise an error
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scrape_log WHERE source = 'test'")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

    def test_multiple_logs(self, temp_db):
        """Should store multiple log entries."""
        for i in range(5):
            db_module.log_scrape(
                source=f"test_{i}",
                team_slug="test-fc",
                url="https://example.com",
                status="success",
                records_found=i * 10
            )

        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scrape_log")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 5


# =============================================================================
# Tests for get_player_count()
# =============================================================================

class TestGetPlayerCount:
    """Tests for the get_player_count function."""

    def test_returns_zero_for_empty_db(self, temp_db):
        """Should return 0 when no players exist."""
        count = db_module.get_player_count()
        assert count == 0

    def test_counts_inserted_players(self, temp_db, sample_player):
        """Should count inserted players."""
        # Insert some players
        conn = db_module.get_connection()
        cursor = conn.cursor()

        for i in range(5):
            cursor.execute("""
                INSERT INTO players (team, season, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (sample_player["team"], sample_player["season"],
                  f"Player{i}", "Test"))

        conn.commit()
        conn.close()

        count = db_module.get_player_count()
        assert count == 5


# =============================================================================
# Tests for get_schedule_count()
# =============================================================================

class TestGetScheduleCount:
    """Tests for the get_schedule_count function."""

    def test_returns_zero_for_empty_db(self, temp_db):
        """Should return 0 when no schedules exist."""
        count = db_module.get_schedule_count()
        assert count == 0

    def test_counts_inserted_schedules(self, temp_db):
        """Should count inserted schedules."""
        # Insert some schedules
        conn = db_module.get_connection()
        cursor = conn.cursor()

        for i in range(3):
            cursor.execute("""
                INSERT INTO schedules (match_id, season, home_team, away_team)
                VALUES (?, ?, ?, ?)
            """, (f"match_{i}", 2026, "Team A", "Team B"))

        conn.commit()
        conn.close()

        count = db_module.get_schedule_count()
        assert count == 3


# =============================================================================
# Database Schema Tests
# =============================================================================

class TestDatabaseSchema:
    """Tests to verify the database schema is correct."""

    def test_players_table_columns(self, temp_db):
        """Players table should have all required columns."""
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(players)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required_columns = {
            "id", "team", "season", "first_name", "last_name",
            "hometown_city", "hometown_state", "high_school",
            "position", "height", "weight", "birthdate",
            "birthplace", "citizenship", "bio_url"
        }

        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_schedules_table_columns(self, temp_db):
        """Schedules table should have all required columns."""
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(schedules)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required_columns = {
            "id", "match_id", "season", "match_date",
            "home_team", "away_team", "competition", "status"
        }

        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_scrape_log_table_columns(self, temp_db):
        """Scrape log table should have all required columns."""
        conn = db_module.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(scrape_log)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required_columns = {
            "id", "source", "team_slug", "url",
            "status", "records_found", "error_message"
        }

        for col in required_columns:
            assert col in columns, f"Missing column: {col}"


# =============================================================================
# Data Integrity Tests
# =============================================================================

class TestDataIntegrity:
    """Tests for data integrity constraints."""

    def test_player_unique_constraint(self, temp_db):
        """Should enforce unique constraint on player."""
        conn = db_module.get_connection()
        cursor = conn.cursor()

        # Insert first player
        cursor.execute("""
            INSERT INTO players (team, season, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, ("Test FC", 2026, "John", "Doe"))
        conn.commit()

        # Try to insert duplicate - should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO players (team, season, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, ("Test FC", 2026, "John", "Doe"))
            conn.commit()

        conn.close()

    def test_schedule_unique_match_id(self, temp_db):
        """Should enforce unique match_id constraint."""
        conn = db_module.get_connection()
        cursor = conn.cursor()

        # Insert first schedule
        cursor.execute("""
            INSERT INTO schedules (match_id, season, home_team, away_team)
            VALUES (?, ?, ?, ?)
        """, ("match_001", 2026, "Team A", "Team B"))
        conn.commit()

        # Try to insert duplicate - should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO schedules (match_id, season, home_team, away_team)
                VALUES (?, ?, ?, ?)
            """, ("match_001", 2026, "Team C", "Team D"))
            conn.commit()

        conn.close()


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])
