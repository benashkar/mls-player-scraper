"""Export database to CSV, JSON, and MySQL formats."""
import sqlite3
import csv
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "mls_data.db"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def escape_mysql(val):
    """Escape value for MySQL INSERT."""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    val = str(val).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{val}'"


def export_csv():
    """Export to CSV files."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Players
    cursor.execute("SELECT * FROM players ORDER BY team, last_name")
    players = [dict(row) for row in cursor.fetchall()]

    with open(OUTPUT_DIR / "players.csv", "w", newline="", encoding="utf-8") as f:
        if players:
            writer = csv.DictWriter(f, fieldnames=players[0].keys())
            writer.writeheader()
            writer.writerows(players)
    print(f"Exported {len(players)} players to output/players.csv")

    # Schedules
    cursor.execute("SELECT * FROM schedules ORDER BY match_date")
    schedules = [dict(row) for row in cursor.fetchall()]

    with open(OUTPUT_DIR / "schedules.csv", "w", newline="", encoding="utf-8") as f:
        if schedules:
            writer = csv.DictWriter(f, fieldnames=schedules[0].keys())
            writer.writeheader()
            writer.writerows(schedules)
    print(f"Exported {len(schedules)} schedules to output/schedules.csv")

    conn.close()


def export_json():
    """Export to JSON files."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Players
    cursor.execute("SELECT * FROM players ORDER BY team, last_name")
    players = [dict(row) for row in cursor.fetchall()]

    with open(OUTPUT_DIR / "players.json", "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, default=str)
    print(f"Exported {len(players)} players to output/players.json")

    # Schedules
    cursor.execute("SELECT * FROM schedules ORDER BY match_date")
    schedules = [dict(row) for row in cursor.fetchall()]

    with open(OUTPUT_DIR / "schedules.json", "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2, default=str)
    print(f"Exported {len(schedules)} schedules to output/schedules.json")

    conn.close()


def export_mysql():
    """Export to MySQL SQL file."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    with open(OUTPUT_DIR / "mls_data.sql", "w", encoding="utf-8") as f:
        f.write("-- MLS Data MySQL Export\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n\n")

        # Drop tables
        f.write("DROP TABLE IF EXISTS schedules;\n")
        f.write("DROP TABLE IF EXISTS players;\n\n")

        # Players table schema
        f.write("""CREATE TABLE players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    team VARCHAR(100),
    season INT,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    hometown_city VARCHAR(100),
    hometown_state VARCHAR(100),
    high_school VARCHAR(200),
    high_school_city VARCHAR(100),
    high_school_state VARCHAR(100),
    high_school_source_url TEXT,
    high_school_source_name VARCHAR(100),
    position VARCHAR(50),
    jersey_number INT,
    height VARCHAR(20),
    weight INT,
    birthdate VARCHAR(50),
    birthplace VARCHAR(200),
    citizenship VARCHAR(100),
    headshot_url TEXT,
    bio_url TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE KEY unique_player (team, season, first_name, last_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

""")

        # Schedules table schema
        f.write("""CREATE TABLE schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id VARCHAR(200) UNIQUE,
    season INT,
    match_date DATE,
    match_time VARCHAR(20),
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    venue VARCHAR(200),
    competition VARCHAR(100),
    broadcast VARCHAR(100),
    status VARCHAR(50),
    home_score INT,
    away_score INT,
    created_at DATETIME,
    updated_at DATETIME,
    home_team_raw VARCHAR(100),
    away_team_raw VARCHAR(100),
    match_url TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

""")

        # Players data
        cursor.execute("SELECT * FROM players ORDER BY id")
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]

        f.write("-- Players data\n")
        for row in rows:
            values = ", ".join([escape_mysql(row[col]) for col in cols])
            f.write(f"INSERT INTO players ({', '.join(cols)}) VALUES ({values});\n")

        f.write(f"\n-- Inserted {len(rows)} players\n\n")

        # Schedules data
        cursor.execute("SELECT * FROM schedules ORDER BY id")
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]

        f.write("-- Schedules data\n")
        for row in rows:
            values = ", ".join([escape_mysql(row[col]) for col in cols])
            f.write(f"INSERT INTO schedules ({', '.join(cols)}) VALUES ({values});\n")

        f.write(f"\n-- Inserted {len(rows)} schedules\n")

    conn.close()
    print("Exported MySQL dump to output/mls_data.sql")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("Exporting to all formats...")
    print("=" * 50)

    export_csv()
    export_json()
    export_mysql()

    print("=" * 50)
    print("Export complete!")
