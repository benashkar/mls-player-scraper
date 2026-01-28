"""Database initialization and utilities."""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
DB_PATH = DATA_DIR / "mls_data.db"


def get_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


def init_database():
    """Initialize the database with schema."""
    DATA_DIR.mkdir(exist_ok=True)

    schema_path = CONFIG_DIR / "schema.sql"
    with open(schema_path, "r") as f:
        schema = f.read()

    conn = get_connection()
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")


def log_scrape(source: str, team_slug: str = None, url: str = None,
               status: str = "success", records_found: int = 0, error: str = None):
    """Log a scrape attempt."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO scrape_log (source, team_slug, url, status, records_found, error_message)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source, team_slug, url, status, records_found, error)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_database()
