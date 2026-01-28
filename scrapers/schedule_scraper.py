"""
MLS Schedule Scraper

Scrapes match schedules from MLS.com for all teams.
"""
import asyncio
import re
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.config_loader import load_teams
from scrapers.db import get_connection, log_scrape, init_database

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


class ScheduleScraper:
    """Scrapes MLS schedules."""

    def __init__(self):
        self.browser = None
        self.context = None
        self.config = load_teams()
        self.season = self.config["season"]

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

    async def scrape_full_schedule(self) -> list:
        """Scrape the full MLS season schedule."""
        page = await self.context.new_page()
        matches = []

        try:
            # MLS schedule page
            url = f"https://www.mlssoccer.com/schedule/scores#competition=mls-regular-season&club=all&date={self.season}"
            print(f"Fetching MLS schedule: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)  # Let JS render

            # Try to find match elements
            match_elements = await self._find_match_elements(page)
            print(f"Found {len(match_elements)} match elements")

            for elem in match_elements:
                try:
                    match = await self._extract_match_data(elem)
                    if match and match.get("home_team") and match.get("away_team"):
                        matches.append(match)
                except Exception as e:
                    print(f"  Error extracting match: {e}")
                    continue

            print(f"Extracted {len(matches)} matches")
            log_scrape("schedule", "all", url, "success", len(matches))

        except PlaywrightTimeout:
            print("Timeout loading schedule page")
            log_scrape("schedule", "all", url, "error", 0, "Timeout")
        except Exception as e:
            print(f"Error scraping schedule: {e}")
            log_scrape("schedule", "all", url, "error", 0, str(e))
        finally:
            await page.close()

        return matches

    async def scrape_team_schedule(self, team: dict) -> list:
        """Scrape schedule for a single team."""
        page = await self.context.new_page()
        matches = []

        try:
            url = f"https://www.mlssoccer.com/clubs/{team['slug']}/schedule/"
            print(f"  Scraping: {team['name']}")

            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)

            # Get page content and extract matches
            match_rows = await page.query_selector_all("[class*='match'], [class*='schedule'] tr, [class*='game']")

            for row in match_rows:
                try:
                    match = await self._extract_match_from_row(row, team["name"])
                    if match and match.get("home_team") and match.get("away_team"):
                        matches.append(match)
                except:
                    continue

            # Also try extracting from page text
            if len(matches) < 10:
                text_matches = await self._extract_matches_from_text(page, team["name"])
                matches.extend(text_matches)

            print(f"    Found {len(matches)} matches")
            log_scrape("schedule", team["slug"], url, "success", len(matches))

        except Exception as e:
            print(f"    Error: {e}")
            log_scrape("schedule", team["slug"], "", "error", 0, str(e))
        finally:
            await page.close()

        return matches

    async def _find_match_elements(self, page):
        """Find match elements on the page."""
        selectors = [
            "[class*='MatchCard']",
            "[class*='match-card']",
            "[class*='fixture']",
            "[class*='game-card']",
            "article[class*='match']",
        ]

        for selector in selectors:
            elements = await page.query_selector_all(selector)
            if elements and len(elements) > 0:
                return elements

        return []

    async def _extract_match_data(self, elem) -> dict:
        """Extract match data from an element."""
        match = {
            "season": self.season,
            "match_date": None,
            "match_time": None,
            "home_team": None,
            "away_team": None,
            "venue": None,
            "competition": "MLS Regular Season",
            "home_score": None,
            "away_score": None,
            "status": "scheduled",
        }

        text = await elem.inner_text()
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Try to extract teams
        team_names = []
        for line in lines:
            # Check if line looks like a team name
            if any(t in line for t in ["FC", "SC", "United", "City", "Galaxy", "Sounders", "Timbers", "Fire", "Crew"]):
                team_names.append(line)

        if len(team_names) >= 2:
            match["home_team"] = team_names[0]
            match["away_team"] = team_names[1]

        # Try to extract date
        date_pattern = r'(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})'
        for line in lines:
            date_match = re.search(date_pattern, line)
            if date_match:
                match["match_date"] = date_match.group(1)
                break

        # Try to extract time
        time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)'
        for line in lines:
            time_match = re.search(time_pattern, line)
            if time_match:
                match["match_time"] = time_match.group(1)
                break

        # Try to extract score (if match is completed)
        score_pattern = r'(\d+)\s*[-–]\s*(\d+)'
        for line in lines:
            score_match = re.search(score_pattern, line)
            if score_match:
                match["home_score"] = int(score_match.group(1))
                match["away_score"] = int(score_match.group(2))
                match["status"] = "final"
                break

        return match

    async def _extract_match_from_row(self, row, team_name: str) -> dict:
        """Extract match from a table row or card."""
        match = {
            "season": self.season,
            "match_date": None,
            "match_time": None,
            "home_team": None,
            "away_team": None,
            "venue": None,
            "competition": "MLS Regular Season",
            "home_score": None,
            "away_score": None,
            "status": "scheduled",
        }

        text = await row.inner_text()

        # Extract opponent and home/away
        if " vs " in text.lower() or " v " in text.lower():
            match["home_team"] = team_name
            opponent_match = re.search(r'(?:vs?\.?\s+)([A-Za-z\s\.]+?)(?:\d|$|\n)', text, re.IGNORECASE)
            if opponent_match:
                match["away_team"] = opponent_match.group(1).strip()
        elif " @ " in text or " at " in text.lower():
            match["away_team"] = team_name
            opponent_match = re.search(r'(?:@|at)\s+([A-Za-z\s\.]+?)(?:\d|$|\n)', text, re.IGNORECASE)
            if opponent_match:
                match["home_team"] = opponent_match.group(1).strip()

        # Extract date
        date_pattern = r'(\w{3,9}\s+\d{1,2}(?:,?\s+\d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
        date_match = re.search(date_pattern, text)
        if date_match:
            match["match_date"] = date_match.group(1)

        # Extract time
        time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm|ET|PT|CT)?)'
        time_match = re.search(time_pattern, text)
        if time_match:
            match["match_time"] = time_match.group(1)

        # Extract score
        score_pattern = r'(\d+)\s*[-–]\s*(\d+)'
        score_match = re.search(score_pattern, text)
        if score_match:
            match["home_score"] = int(score_match.group(1))
            match["away_score"] = int(score_match.group(2))
            match["status"] = "final"

        return match

    async def _extract_matches_from_text(self, page, team_name: str) -> list:
        """Extract matches from page text using patterns."""
        matches = []
        text = await page.inner_text("body")

        # Pattern for upcoming matches
        pattern = r'(\w{3,9}\s+\d{1,2})[,\s]+(\d{4})?\s*[\n\r]+\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*[\n\r]+\s*(?:vs\.?\s+)?([A-Za-z\s\.]+)'

        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append({
                "season": self.season,
                "match_date": f"{match.group(1)} {match.group(2) or self.season}",
                "match_time": match.group(3),
                "home_team": team_name,
                "away_team": match.group(4).strip(),
                "competition": "MLS Regular Season",
                "status": "scheduled",
            })

        return matches

    def save_match(self, match: dict):
        """Save a match to the database."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Generate a match ID
            match_id = f"{match.get('home_team', '')[:3]}-{match.get('away_team', '')[:3]}-{match.get('match_date', '')}"
            match_id = re.sub(r'[^a-zA-Z0-9-]', '', match_id)

            cursor.execute("""
                INSERT INTO schedules (
                    match_id, season, match_date, match_time, home_team, away_team,
                    venue, competition, status, home_score, away_score, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    match_time = excluded.match_time,
                    venue = excluded.venue,
                    status = excluded.status,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    updated_at = excluded.updated_at
            """, (
                match_id,
                match.get("season"),
                match.get("match_date"),
                match.get("match_time"),
                match.get("home_team"),
                match.get("away_team"),
                match.get("venue"),
                match.get("competition"),
                match.get("status"),
                match.get("home_score"),
                match.get("away_score"),
                datetime.now().isoformat()
            ))
            conn.commit()
        except Exception as e:
            print(f"  Error saving match: {e}")
        finally:
            conn.close()

    async def scrape_all_team_schedules(self):
        """Scrape schedules for all teams."""
        print(f"Scraping schedules for {self.season} season")
        print("=" * 50)

        await self.start()
        all_matches = []

        try:
            for i, team in enumerate(self.config["teams"], 1):
                print(f"\n[{i}/{len(self.config['teams'])}] {team['name']}")

                matches = await self.scrape_team_schedule(team)

                for match in matches:
                    self.save_match(match)
                    all_matches.append(match)

                await asyncio.sleep(REQUEST_DELAY * 2)

        finally:
            await self.stop()

        print("\n" + "=" * 50)
        print(f"Schedule scrape complete!")
        self._print_summary()

        return all_matches

    def _print_summary(self):
        """Print summary statistics."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM schedules WHERE season = ?", (self.season,))
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM schedules WHERE season = ? AND status = 'final'", (self.season,))
        completed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM schedules WHERE season = ? AND status = 'scheduled'", (self.season,))
        upcoming = cursor.fetchone()[0]

        conn.close()

        print(f"\nSummary for {self.season} season:")
        print(f"  Total matches: {total}")
        print(f"  Completed: {completed}")
        print(f"  Upcoming: {upcoming}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape MLS schedules")
    parser.add_argument("--team", help="Scrape single team by slug")
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    args = parser.parse_args()

    if args.init_db:
        init_database()

    scraper = ScheduleScraper()

    if args.team:
        from scrapers.config_loader import get_team_by_slug
        team = get_team_by_slug(args.team)
        if team:
            await scraper.start()
            matches = await scraper.scrape_team_schedule(team)
            for m in matches:
                scraper.save_match(m)
            await scraper.stop()
            scraper._print_summary()
        else:
            print(f"Team not found: {args.team}")
    else:
        await scraper.scrape_all_team_schedules()


if __name__ == "__main__":
    asyncio.run(main())
