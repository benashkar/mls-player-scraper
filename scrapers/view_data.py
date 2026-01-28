"""Utility to view scraped data from the database."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.db import get_connection


def show_players(team: str = None, limit: int = 20):
    """Show players from database."""
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cursor = conn.cursor()

    query = "SELECT * FROM players"
    params = []

    if team:
        query += " WHERE team LIKE ?"
        params.append(f"%{team}%")

    query += " ORDER BY team, last_name LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    players = cursor.fetchall()
    conn.close()

    if not players:
        print("No players found.")
        return

    print(f"\n{'='*80}")
    print(f"{'PLAYER DATA':^80}")
    print(f"{'='*80}\n")

    for p in players:
        print(f"{p['first_name'] or ''} {p['last_name'] or ''} - {p['team']}")
        print(f"  Position: {p['position'] or 'N/A'} | #{p['jersey_number'] or 'N/A'}")
        print(f"  Hometown: {p['hometown_city'] or 'N/A'}, {p['hometown_state'] or 'N/A'}")
        print(f"  High School: {p.get('high_school') or 'N/A'}")
        if p.get('high_school_source_url'):
            print(f"    Source: {p.get('high_school_source_name', 'Unknown')}")
            print(f"    URL: {p['high_school_source_url'][:70]}...")
        print(f"  Height: {p['height'] or 'N/A'} | Weight: {p['weight'] or 'N/A'}")
        print()


def show_stats():
    """Show summary statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n{'='*60}")
    print(f"{'DATABASE STATISTICS':^60}")
    print(f"{'='*60}\n")

    # Total players
    cursor.execute("SELECT COUNT(*) FROM players")
    print(f"Total players: {cursor.fetchone()[0]}")

    # Players by team
    print("\nPlayers by team:")
    cursor.execute("""
        SELECT team, COUNT(*) as count
        FROM players
        GROUP BY team
        ORDER BY count DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    # Coverage stats
    print("\nData coverage:")
    cursor.execute("SELECT COUNT(*) FROM players WHERE hometown_city IS NOT NULL")
    print(f"  With hometown: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM players WHERE high_school IS NOT NULL")
    print(f"  With high school: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM players WHERE headshot_url IS NOT NULL")
    print(f"  With headshot: {cursor.fetchone()[0]}")

    # Recent scrapes
    print("\nRecent scrape log:")
    cursor.execute("""
        SELECT source, team_slug, status, records_found, scraped_at
        FROM scrape_log
        ORDER BY scraped_at DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  {row[4]} | {row[0]} | {row[1] or 'all'} | {row[2]} | {row[3]} records")

    conn.close()


def export_csv(output_path: str = None):
    """Export players to CSV."""
    import csv
    from pathlib import Path

    if not output_path:
        output_path = Path(__file__).parent.parent / "output" / "players.csv"

    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM players ORDER BY team, last_name")
    players = cursor.fetchall()
    conn.close()

    if not players:
        print("No players to export.")
        return

    Path(output_path).parent.mkdir(exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=players[0].keys())
        writer.writeheader()
        writer.writerows(players)

    print(f"Exported {len(players)} players to {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="View scraped MLS data")
    parser.add_argument("--team", help="Filter by team name")
    parser.add_argument("--limit", type=int, default=20, help="Number of players to show")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--export", action="store_true", help="Export to CSV")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.export:
        export_csv()
    else:
        show_players(team=args.team, limit=args.limit)
