"""Clean up Grokipedia high school names that have extra prefix text."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.db import get_connection


def clean_names():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, high_school FROM players WHERE high_school IS NOT NULL AND high_school_source_name = 'Grokipedia'")
    rows = cur.fetchall()

    cleaned_count = 0
    for row in rows:
        pid, hs = row
        original = hs

        # Strip prefixes
        hs = re.sub(r'^(?:He|She)\s+(?:enrolled|attended|went)\s+(?:at|to)\s+', '', hs, flags=re.IGNORECASE)
        hs = re.sub(r'^[A-Z][a-z]+\s+(?:competed|played)\s+(?:for|at|varsity soccer at)\s+', '', hs, flags=re.IGNORECASE)
        hs = re.sub(r'^(?:Transitioning|Moving)\s+to\s+high\s+school\s+at\s+', '', hs, flags=re.IGNORECASE)
        hs = re.sub(r'^At\s+', '', hs)
        hs = re.sub(r'^As a high school senior at\s+', '', hs, flags=re.IGNORECASE)
        hs = re.sub(r'^[A-Z][a-z]+\s+completed\s+his\s+early\s+education\s+at\s+', '', hs, flags=re.IGNORECASE)
        hs = re.sub(r'^[A-Z][a-z]+\s+played\s+varsity\s+soccer\s+at\s+', '', hs, flags=re.IGNORECASE)
        hs = re.sub(r'^School\s+and\s+', '', hs, flags=re.IGNORECASE)  # Remove "School and" prefix

        if hs != original:
            print(f'Cleaned: {original} -> {hs}')
            cur.execute('UPDATE players SET high_school = ? WHERE id = ?', (hs, pid))
            cleaned_count += 1

    conn.commit()
    conn.close()
    print(f'\nDone! Cleaned {cleaned_count} high school names.')


if __name__ == "__main__":
    clean_names()
