"""
Database Initialization and Utilities
=====================================

This module handles all database operations for the MLS scraper project.
We use SQLite as our database - it's a simple file-based database that
doesn't require a separate server to run.

KEY CONCEPTS FOR JUNIOR DEVELOPERS:
-----------------------------------
1. SQLite stores everything in a single .db file (data/mls_data.db)
2. We use "connections" to talk to the database
3. Always close connections when done to avoid file locks
4. The schema.sql file defines the structure of our tables

COMMON OPERATIONS:
------------------
- get_connection(): Opens a connection to the database
- init_database(): Creates tables if they don't exist
- log_scrape(): Records each scraping attempt for debugging

Example usage:
    from scrapers.db import get_connection

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE team = ?", ("Atlanta United",))
    players = cursor.fetchall()
    conn.close()
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# =============================================================================
# PATH CONFIGURATION
# =============================================================================
# These paths tell Python where to find files relative to this script
# Path(__file__) = the current file (db.py)
# .parent = go up one folder (to /scrapers)
# .parent.parent = go up two folders (to project root)

PROJECT_ROOT = Path(__file__).parent.parent  # Main project folder
DATA_DIR = PROJECT_ROOT / "data"              # Where we store the database
CONFIG_DIR = PROJECT_ROOT / "config"          # Where schema.sql lives
DB_PATH = DATA_DIR / "mls_data.db"            # Full path to our database file


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_connection():
    """
    Open a connection to the SQLite database.

    IMPORTANT: You must close the connection when you're done!

    Returns:
        sqlite3.Connection: A connection object you can use to run queries

    Example:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM players")
        count = cursor.fetchone()[0]
        print(f"Total players: {count}")
        conn.close()  # Don't forget this!

    Alternative (auto-closes):
        with get_connection() as conn:
            cursor = conn.cursor()
            # ... do stuff ...
        # Connection closes automatically here
    """
    return sqlite3.connect(DB_PATH)


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_database():
    """
    Initialize the database by creating all required tables.

    This reads the schema from config/schema.sql and executes it.
    Safe to run multiple times - uses "CREATE TABLE IF NOT EXISTS".

    Tables created:
        - players: All MLS player data (name, team, hometown, etc.)
        - schedules: Match schedule data (dates, teams, venues)
        - high_schools: High school lookup data (currently unused)
        - scrape_log: Tracks each scraping attempt for debugging

    When to call this:
        - First time setting up the project
        - After pulling new schema changes from git
        - If you accidentally delete the database file
    """
    # Create the data folder if it doesn't exist
    # exist_ok=True means "don't error if folder already exists"
    DATA_DIR.mkdir(exist_ok=True)

    # Read the SQL schema file
    schema_path = CONFIG_DIR / "schema.sql"
    with open(schema_path, "r") as f:
        schema = f.read()

    # Execute the schema (creates tables)
    conn = get_connection()
    conn.executescript(schema)  # executescript can run multiple SQL statements
    conn.commit()               # Save changes to disk
    conn.close()                # Release the connection

    print(f"Database initialized at: {DB_PATH}")


# =============================================================================
# SCRAPE LOGGING
# =============================================================================

def log_scrape(source: str, team_slug: str = None, url: str = None,
               status: str = "success", records_found: int = 0, error: str = None):
    """
    Log a scraping attempt to the database for debugging and monitoring.

    This helps us track:
        - Which scrapes succeeded or failed
        - How many records we got from each source
        - Error messages when things go wrong

    Args:
        source: What type of scrape (e.g., "roster", "schedule", "transfermarkt")
        team_slug: The team identifier (e.g., "atlanta-united")
        url: The URL we scraped
        status: "success", "error", or "warning"
        records_found: How many records we got
        error: Error message if something went wrong

    Example:
        # Log a successful scrape
        log_scrape("roster", "chicago-fire-fc",
                   "https://mlssoccer.com/clubs/chicago-fire-fc/roster/",
                   "success", 29)

        # Log a failed scrape
        log_scrape("roster", "atlanta-united", url, "error", 0,
                   "Timeout after 30 seconds")

    To view the log:
        SELECT * FROM scrape_log ORDER BY scraped_at DESC LIMIT 20;
    """
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO scrape_log
            (source, team_slug, url, status, records_found, error_message)
        VALUES
            (?, ?, ?, ?, ?, ?)
        """,
        (source, team_slug, url, status, records_found, error)
    )
    conn.commit()
    conn.close()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_player_count():
    """
    Get the total number of players in the database.

    Returns:
        int: Number of players

    Example:
        count = get_player_count()
        print(f"We have {count} players in the database")
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM players")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_schedule_count():
    """
    Get the total number of scheduled matches in the database.

    Returns:
        int: Number of matches
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM schedules")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # This code runs only when you execute this file directly:
    #   python scrapers/db.py
    #
    # It does NOT run when you import this file:
    #   from scrapers.db import get_connection

    init_database()
    print(f"Players in database: {get_player_count()}")
    print(f"Matches in database: {get_schedule_count()}")
