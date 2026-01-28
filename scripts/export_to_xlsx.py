"""Export database data to Excel/Google Sheets format."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.db import get_connection
import pandas as pd


def export_rosters():
    """Export players to Excel."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM players ORDER BY team, last_name", conn)
    conn.close()

    output_path = Path(__file__).parent.parent / "output" / "major_league_soccer_rosters.xlsx"
    output_path.parent.mkdir(exist_ok=True)
    df.to_excel(output_path, index=False, sheet_name="Players")
    print(f"Exported {len(df)} players to {output_path}")


def export_schedules():
    """Export schedules to Excel."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM schedules ORDER BY match_date", conn)
    conn.close()

    output_path = Path(__file__).parent.parent / "output" / "major_league_soccer_schedules.xlsx"
    output_path.parent.mkdir(exist_ok=True)
    df.to_excel(output_path, index=False, sheet_name="Matches")
    print(f"Exported {len(df)} matches to {output_path}")


if __name__ == "__main__":
    export_rosters()
    export_schedules()
    print("\nExport complete!")
