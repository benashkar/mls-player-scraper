"""
High School Data Scraper - Grokipedia Edition

Uses Grokipedia (grokipedia.com) to find player high school data.
Searches by player name, optionally with hometown/team context.
"""
import asyncio
import re
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from playwright.async_api import async_playwright
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.db import get_connection, log_scrape

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


@dataclass
class HighSchoolResult:
    """Result from high school search."""
    high_school: str
    city: Optional[str] = None
    state: Optional[str] = None
    source_url: str = ""
    source_name: str = "Grokipedia"


class GrokipediaHighSchoolScraper:
    """Scrapes high school data from Grokipedia."""

    def __init__(self):
        self.browser = None
        self.context = None

    async def start(self):
        """Initialize the browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=HEADLESS)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

    async def stop(self):
        """Close the browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def find_high_school(self, first_name: str, last_name: str,
                                hometown_city: str = "", team: str = "") -> Optional[HighSchoolResult]:
        """Search Grokipedia for player's high school."""
        full_name = f"{first_name} {last_name}"
        print(f"  Searching Grokipedia: {full_name}")

        page = await self.context.new_page()

        try:
            # Build search query with context
            search_terms = [full_name, "soccer"]
            if hometown_city:
                search_terms.append(hometown_city)
            if team:
                search_terms.append(team)

            query = " ".join(search_terms)
            search_url = f"https://grokipedia.com/search?q={quote(query)}"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)

            # Click on the first exact match result
            try:
                result = page.get_by_text(full_name, exact=True).first
                await result.click(timeout=5000)
                await asyncio.sleep(4)
            except Exception:
                # Try partial match
                try:
                    result = page.get_by_text(f"{first_name} {last_name}").first
                    await result.click(timeout=5000)
                    await asyncio.sleep(4)
                except Exception:
                    print(f"    No search result found")
                    return None

            # Check if we landed on an article page
            current_url = page.url
            if "/page/" not in current_url:
                print(f"    Not an article page")
                return None

            # Get article text
            text = await page.inner_text("body")

            # Verify it's about a soccer player
            if not any(term in text.lower() for term in ["soccer", "football", "mls", "midfielder", "forward", "defender", "goalkeeper"]):
                print(f"    Not a soccer player article")
                return None

            # Extract high school
            result = self._extract_high_school(text, current_url)
            if result:
                log_scrape("highschool_grokipedia", None, current_url, "success", 1)
                return result

            print(f"    No high school found in article")

        except Exception as e:
            print(f"    Error: {e}")
        finally:
            await page.close()

        return None

    def _extract_high_school(self, text: str, source_url: str) -> Optional[HighSchoolResult]:
        """Extract high school from Grokipedia article text."""

        # Patterns to find high school
        patterns = [
            # "attended X High School"
            r'attended\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "graduated from X High School"
            r'graduated\s+from\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "played for X High School"
            r'played\s+(?:for|at)\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "competed for X High School"
            r'competed\s+(?:for|at)\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "enrolled at X High School"
            r'enrolled\s+at\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "at X High School"
            r'(?:schooled|educated)\s+at\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "went to X High School"
            r'went\s+to\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "X High School in City"
            r'([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory))\s+in\s+[A-Z][a-z]+',
            # "captained ... at X High School"
            r'at\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # General pattern
            r'([A-Z][a-zA-Z\s\.\-\']{3,40}(?:High School|College Prep|Prep School|Preparatory School|Preparatory|Prep))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                hs_name = match.strip()

                # Clean up whitespace
                hs_name = re.sub(r'\s+', ' ', hs_name)
                hs_name = re.sub(r'^\W+|\W+$', '', hs_name)

                # Strip common prefix phrases that got captured
                prefix_patterns = [
                    r'^(?:He|She)\s+(?:enrolled|attended|went)\s+(?:at|to)\s+',
                    r'^(?:Dotson|He|She)\s+competed\s+for\s+',
                    r'^(?:Transitioning|Moving)\s+to\s+high\s+school\s+at\s+',
                    r'^At\s+',
                ]
                for prefix in prefix_patterns:
                    hs_name = re.sub(prefix, '', hs_name, flags=re.IGNORECASE)

                # Validate length
                if len(hs_name) < 8 or len(hs_name) > 60:
                    continue

                # Skip false positives
                skip_words = ["youth", "academy", "mls", "usl", "college", "university",
                              "national", "team", "club", "fc ", "sc ", "united", "sounders",
                              "stanford", "ucla", "duke", "wake forest", "maryland"]
                if any(word in hs_name.lower() for word in skip_words):
                    continue

                # Must contain school-like term
                if not any(term in hs_name.lower() for term in ["high school", "prep", "preparatory"]):
                    continue

                # Try to extract location
                city, state = self._extract_location(text, hs_name)

                print(f"    Found (Grokipedia): {hs_name}")

                return HighSchoolResult(
                    high_school=hs_name,
                    city=city,
                    state=state,
                    source_url=source_url,
                    source_name="Grokipedia"
                )

        return None

    def _extract_location(self, text: str, hs_name: str) -> tuple:
        """Extract city/state near high school mention."""
        pattern = rf'{re.escape(hs_name)}[,\s]+(?:in\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{{2}}|[A-Z][a-z]+)'
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None, None

    def update_player_high_school(self, player_id: int, result: HighSchoolResult):
        """Update player record with high school data."""
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE players SET
                    high_school = ?,
                    high_school_city = ?,
                    high_school_state = ?,
                    high_school_source_url = ?,
                    high_school_source_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                result.high_school,
                result.city,
                result.state,
                result.source_url,
                result.source_name,
                player_id
            ))
            conn.commit()
        finally:
            conn.close()

    async def process_us_players(self, team_filter: str = None, skip_existing: bool = True):
        """Process US-born players to find high school data from Grokipedia."""
        conn = get_connection()
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()

        query = "SELECT * FROM players WHERE 1=1"
        params = []

        if team_filter:
            query += " AND team LIKE ?"
            params.append(f"%{team_filter}%")

        if skip_existing:
            query += " AND (high_school IS NULL OR high_school = '')"

        # Focus on US players (or players without nationality info who might be US)
        query += """ AND (
            hometown_state LIKE '%USA%'
            OR hometown_city LIKE '%USA%'
            OR birthplace LIKE '%USA%'
            OR hometown_state IS NOT NULL
        )"""
        query += " ORDER BY team, last_name"

        cursor.execute(query, params)
        players = cursor.fetchall()
        conn.close()

        if not players:
            print("No players to process.")
            return

        print(f"Processing {len(players)} players via Grokipedia...")
        print("=" * 60)

        await self.start()
        found_count = 0

        try:
            for i, player in enumerate(players, 1):
                print(f"\n[{i}/{len(players)}] {player['first_name']} {player['last_name']} ({player['team']})")

                result = await self.find_high_school(
                    player["first_name"],
                    player["last_name"],
                    player.get("hometown_city", ""),
                    player["team"]
                )

                if result:
                    self.update_player_high_school(player["id"], result)
                    found_count += 1
                    print(f"    Saved: {result.high_school}")
                    print(f"    URL: {result.source_url}")

                await asyncio.sleep(REQUEST_DELAY)

        finally:
            await self.stop()

        print("\n" + "=" * 60)
        print(f"Complete! Found high school for {found_count}/{len(players)} players via Grokipedia")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scrape high school data from Grokipedia")
    parser.add_argument("--team", help="Filter by team name")
    parser.add_argument("--player", help="Search single player (first last)")
    parser.add_argument("--include-existing", action="store_true")
    args = parser.parse_args()

    scraper = GrokipediaHighSchoolScraper()

    if args.player:
        await scraper.start()
        parts = args.player.split()
        first_name = parts[0]
        last_name = " ".join(parts[1:])

        result = await scraper.find_high_school(first_name, last_name)

        if result:
            print(f"\n{'='*50}")
            print(f"HIGH SCHOOL FOUND")
            print(f"{'='*50}")
            print(f"  School: {result.high_school}")
            print(f"  City: {result.city or 'N/A'}")
            print(f"  State: {result.state or 'N/A'}")
            print(f"  Source: {result.source_name}")
            print(f"  URL: {result.source_url}")
        else:
            print("\nNo high school found.")

        await scraper.stop()
    else:
        await scraper.process_us_players(
            team_filter=args.team,
            skip_existing=not args.include_existing
        )


if __name__ == "__main__":
    asyncio.run(main())
