"""
High School Data Scraper - Wikipedia Edition

Uses Wikipedia as the primary source for player high school data.
Wikipedia player pages often contain education/youth career info.
"""
import asyncio
import re
import os
import sys
import urllib.parse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import async_playwright
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.db import get_connection, log_scrape

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


@dataclass
class HighSchoolResult:
    """Result from high school search."""
    high_school: str
    city: Optional[str] = None
    state: Optional[str] = None
    source_url: str = ""
    source_name: str = ""


class WikipediaHighSchoolScraper:
    """Scrapes high school data from Wikipedia."""

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
                                team: str = "") -> Optional[HighSchoolResult]:
        """Search Wikipedia for player's high school."""
        full_name = f"{first_name} {last_name}"
        print(f"  Searching Wikipedia: {full_name}")

        page = await self.context.new_page()

        try:
            # Try direct Wikipedia page first
            wiki_slug = f"{first_name}_{last_name}".replace(" ", "_")
            wiki_url = f"https://en.wikipedia.org/wiki/{wiki_slug}"

            result = await self._check_wikipedia_page(page, wiki_url, full_name)
            if result:
                return result

            # Try with "(soccer)" disambiguation
            wiki_url_soccer = f"https://en.wikipedia.org/wiki/{wiki_slug}_(soccer)"
            result = await self._check_wikipedia_page(page, wiki_url_soccer, full_name)
            if result:
                return result

            # Try with "(American soccer)" disambiguation
            wiki_url_am = f"https://en.wikipedia.org/wiki/{wiki_slug}_(American_soccer)"
            result = await self._check_wikipedia_page(page, wiki_url_am, full_name)
            if result:
                return result

            # Try Wikipedia search
            result = await self._search_wikipedia(page, full_name, team)
            if result:
                return result

        except Exception as e:
            print(f"    Error: {e}")
        finally:
            await page.close()

        print(f"    No high school found")
        return None

    async def _check_wikipedia_page(self, page, url: str, player_name: str) -> Optional[HighSchoolResult]:
        """Check a Wikipedia page for high school info."""
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            if not response or response.status != 200:
                return None

            await asyncio.sleep(1)

            # Check if this is the right person (soccer player)
            text = await page.inner_text("body")

            # Verify it's a soccer player
            if not any(term in text.lower() for term in ["soccer", "football", "mls", "midfielder", "forward", "defender", "goalkeeper"]):
                return None

            # Look for high school in infobox or article text
            result = self._extract_high_school(text, url)
            if result:
                log_scrape("highschool_wikipedia", None, url, "success", 1)
                return result

        except Exception as e:
            pass

        return None

    async def _search_wikipedia(self, page, player_name: str, team: str) -> Optional[HighSchoolResult]:
        """Search Wikipedia for the player."""
        try:
            search_query = f"{player_name} soccer"
            if team:
                search_query += f" {team}"

            search_url = f"https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(search_query)}"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)

            # Check if we landed on a page or search results
            current_url = page.url

            if "/wiki/" in current_url and "Special:Search" not in current_url:
                # We landed on an article
                text = await page.inner_text("body")
                result = self._extract_high_school(text, current_url)
                if result:
                    log_scrape("highschool_wikipedia", None, current_url, "success", 1)
                    return result
            else:
                # Search results page - try first result
                first_result = await page.query_selector(".mw-search-result-heading a")
                if first_result:
                    href = await first_result.get_attribute("href")
                    if href:
                        article_url = f"https://en.wikipedia.org{href}"
                        await page.goto(article_url, wait_until="domcontentloaded", timeout=15000)
                        await asyncio.sleep(1)

                        text = await page.inner_text("body")
                        result = self._extract_high_school(text, article_url)
                        if result:
                            log_scrape("highschool_wikipedia", None, article_url, "success", 1)
                            return result

        except Exception as e:
            pass

        return None

    def _extract_high_school(self, text: str, source_url: str) -> Optional[HighSchoolResult]:
        """Extract high school from Wikipedia article text."""

        # Patterns to find high school
        patterns = [
            # "attended X High School"
            r'attended\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "graduated from X High School"
            r'graduated\s+from\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "played for X High School"
            r'played\s+(?:for|at)\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "at X High School"
            r'(?:schooled|educated)\s+at\s+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "High school: X" or "School: X"
            r'(?:High school|School)[:\s]+([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory|Academy))',
            # "X High School in City"
            r'([A-Z][a-zA-Z\s\.\-\']+(?:High School|Prep|Preparatory))\s+in\s+[A-Z][a-z]+',
            # General pattern for school names
            r'([A-Z][a-zA-Z\s\.\-\']{3,40}(?:High School|College Prep|Prep School|Preparatory School))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                hs_name = match.strip()

                # Clean up
                hs_name = re.sub(r'\s+', ' ', hs_name)
                hs_name = re.sub(r'^\W+|\W+$', '', hs_name)

                # Validate
                if len(hs_name) < 8 or len(hs_name) > 60:
                    continue

                # Skip false positives
                skip_words = ["youth", "academy", "mls", "usl", "college", "university",
                              "national", "team", "club", "fc ", "sc ", "united"]
                if any(word in hs_name.lower() for word in skip_words):
                    continue

                # Must contain school-like term
                if not any(term in hs_name.lower() for term in ["high school", "prep", "preparatory"]):
                    continue

                # Try to extract location
                city, state = self._extract_location(text, hs_name)

                print(f"    Found (Wikipedia): {hs_name}")

                return HighSchoolResult(
                    high_school=hs_name,
                    city=city,
                    state=state,
                    source_url=source_url,
                    source_name="Wikipedia"
                )

        return None

    def _extract_location(self, text: str, hs_name: str) -> tuple:
        """Extract city/state near high school mention."""
        # Look for "X High School in City, State" pattern
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
        """Process US-born players to find high school data from Wikipedia."""
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

        # Only US-born players
        query += " AND (hometown_state LIKE '%USA%' OR hometown_city LIKE '%USA%' OR birthplace LIKE '%USA%')"
        query += " ORDER BY team, last_name"

        cursor.execute(query, params)
        players = cursor.fetchall()
        conn.close()

        if not players:
            print("No US players without high school data.")
            return

        print(f"Processing {len(players)} US players via Wikipedia...")
        print("=" * 60)

        await self.start()
        found_count = 0

        try:
            for i, player in enumerate(players, 1):
                print(f"\n[{i}/{len(players)}] {player['first_name']} {player['last_name']} ({player['team']})")

                result = await self.find_high_school(
                    player["first_name"],
                    player["last_name"],
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
        print(f"Complete! Found high school for {found_count}/{len(players)} players via Wikipedia")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scrape high school data from Wikipedia")
    parser.add_argument("--team", help="Filter by team name")
    parser.add_argument("--player", help="Search single player (first last)")
    parser.add_argument("--include-existing", action="store_true")
    args = parser.parse_args()

    scraper = WikipediaHighSchoolScraper()

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
