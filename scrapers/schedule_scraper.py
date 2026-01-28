"""
MLS Schedule Scraper

Scrapes the full MLS season schedule from mlssoccer.com/schedule/scores.
Loads the page once, sets the start date via hash navigation, then clicks
the "next week" button to walk through the entire season.
"""
import asyncio
import re
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.config_loader import load_teams
from scrapers.db import get_connection, log_scrape, init_database

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# Maps schedule page short names -> roster table team names.
# This lets us JOIN schedules to players on home_team / away_team.
# The raw page text is kept in home_team_raw / away_team_raw.
TEAM_NAME_MAP = {
    "Atlanta": "Atlanta United",
    "Austin": "Austin FC",
    "Charlotte": "Charlotte FC",
    "Chicago": "Chicago Fire FC",
    "Cincinnati": "FC Cincinnati",
    "Colorado": "Colorado Rapids",
    "Columbus": "Columbus Crew",
    "D.C. United": "D.C. United",
    "Dallas": "FC Dallas",
    "Houston": "Houston Dynamo FC",
    "Kansas City": "Sporting Kansas City",
    "LA Galaxy": "LA Galaxy",
    "LAFC": "LAFC",
    "Miami": "Inter Miami CF",
    "Minnesota": "Minnesota United FC",
    "Montréal": "CF Montréal",
    "Nashville": "Nashville SC",
    "New England": "New England Revolution",
    "New York": "New York Red Bulls",
    "New York City": "New York City FC",
    "Orlando": "Orlando City SC",
    "Philadelphia": "Philadelphia Union",
    "Portland": "Portland Timbers",
    "Salt Lake": "Real Salt Lake",
    "San Diego": "San Diego FC",
    "San Jose": "San Jose Earthquakes",
    "Seattle": "Seattle Sounders FC",
    "St. Louis": "St. Louis CITY SC",
    "Toronto": "Toronto FC",
    "Vancouver": "Vancouver Whitecaps FC",
}

# Abbreviation fallback map (abbr -> short name for lookup in TEAM_NAME_MAP)
ABBR_MAP = {
    "ATL": "Atlanta",
    "ATX": "Austin",
    "CLT": "Charlotte",
    "CHI": "Chicago",
    "CIN": "Cincinnati",
    "COL": "Colorado",
    "CLB": "Columbus",
    "DC": "D.C. United",
    "DAL": "Dallas",
    "HOU": "Houston",
    "SKC": "Kansas City",
    "LA": "LA Galaxy",
    "LAFC": "LAFC",
    "MIA": "Miami",
    "MIN": "Minnesota",
    "MTL": "Montréal",
    "NSH": "Nashville",
    "NE": "New England",
    "RBNY": "New York",
    "NYC": "New York City",
    "ORL": "Orlando",
    "PHI": "Philadelphia",
    "POR": "Portland",
    "RSL": "Salt Lake",
    "SD": "San Diego",
    "SJ": "San Jose",
    "SEA": "Seattle",
    "STL": "St. Louis",
    "TOR": "Toronto",
    "VAN": "Vancouver",
}


def normalize_team(raw_name: str, abbreviation: str = "") -> str:
    """Convert a schedule page team name to the roster-standard name."""
    # Strip Leagues Cup seeding like "(10)" from end of name
    clean = re.sub(r'\s*\(\d+\)\s*$', '', raw_name).strip()

    if clean in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[clean]
    if abbreviation and abbreviation in ABBR_MAP:
        short = ABBR_MAP[abbreviation]
        return TEAM_NAME_MAP.get(short, raw_name)
    # Also try the raw name with "FC" stripped for partial matches
    if raw_name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[raw_name]
    return raw_name


class ScheduleScraper:
    """Scrapes the full MLS season schedule week-by-week."""

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

    async def _get_week_label(self, page) -> str:
        """Read the displayed week range from the header."""
        header = await page.query_selector(".mls-c-schedule__header")
        if header:
            text = await header.inner_text()
            return text.split("\n")[0].strip()
        return ""

    async def _extract_week_matches(self, page) -> list:
        """Extract all matches from the currently loaded week."""
        matches = []

        match_elements = await page.query_selector_all(".mls-c-match-list__match")
        if not match_elements:
            return matches

        for elem in match_elements:
            try:
                match = await self._parse_match_element(elem)
                if match and match.get("home_team") and match.get("away_team"):
                    matches.append(match)
            except Exception:
                continue

        return matches

    async def _parse_match_element(self, elem) -> dict:
        """Parse a single .mls-c-match-list__match element into a dict."""
        match = {
            "season": self.season,
            "match_date": None,
            "match_time": None,
            "home_team": None,
            "away_team": None,
            "home_team_raw": None,
            "away_team_raw": None,
            "venue": None,
            "competition": None,
            "broadcast": None,
            "match_url": None,
            "home_score": None,
            "away_score": None,
            "status": "scheduled",
        }

        # --- Match URL (from the <a> link) ---
        link = await elem.query_selector("a[href*='/matches/']")
        if link:
            href = await link.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = "https://www.mlssoccer.com" + href
                match["match_url"] = href

        # --- Date stamp (e.g. "1/31" or "7/19") ---
        # For completed matches the stamp shows "Final", so also parse from URL
        date_elem = await elem.query_selector("[class*='status-stamp']")
        if date_elem:
            date_text = (await date_elem.inner_text()).strip()
            if date_text.lower() == "final":
                match["status"] = "final"
                # Extract date from match URL instead (e.g., -02-18-2025)
                if match.get("match_url"):
                    url_date = re.search(r'-(\d{2})-(\d{2})-(\d{4})$', match["match_url"].rstrip('/'))
                    if url_date:
                        match["match_date"] = f"{url_date.group(3)}-{url_date.group(1)}-{url_date.group(2)}"
            else:
                match["match_date"] = date_text

        # --- Competition ---
        comp_elem = await elem.query_selector("[class*='match-competition']")
        if comp_elem:
            match["competition"] = (await comp_elem.inner_text()).strip()

        # --- Home team ---
        home_club = await elem.query_selector(".mls-c-club.--home")
        if home_club:
            short = await home_club.query_selector(".mls-c-club__shortname")
            abbr = await home_club.query_selector(".mls-c-club__abbreviation")
            raw_name = (await short.inner_text()).strip() if short else ""
            abbr_text = (await abbr.inner_text()).strip() if abbr else ""
            match["home_team_raw"] = raw_name
            match["home_team"] = normalize_team(raw_name, abbr_text)

        # --- Away team ---
        away_club = await elem.query_selector(".mls-c-club.--away")
        if away_club:
            short = await away_club.query_selector(".mls-c-club__shortname")
            abbr = await away_club.query_selector(".mls-c-club__abbreviation")
            raw_name = (await short.inner_text()).strip() if short else ""
            abbr_text = (await abbr.inner_text()).strip() if abbr else ""
            match["away_team_raw"] = raw_name
            match["away_team"] = normalize_team(raw_name, abbr_text)

        # --- Score / time from scorebug ---
        scorebug = await elem.query_selector("[class*='scorebug']")
        if scorebug:
            bug_text = (await scorebug.inner_text()).strip()

            # Check for a final score like "2\n1" or "2 - 1"
            score_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', bug_text.replace("\n", " "))
            if score_match:
                match["home_score"] = int(score_match.group(1))
                match["away_score"] = int(score_match.group(2))
                match["status"] = "final"
            else:
                # It's a time like "4:00PM" or "7:30 PM ET"
                time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)', bug_text, re.IGNORECASE)
                if time_match:
                    match["match_time"] = time_match.group(1).strip()

        # --- Broadcast ---
        bc_elem = await elem.query_selector("[class*='broadcaster']")
        if bc_elem:
            match["broadcast"] = (await bc_elem.inner_text()).strip()

        return match

    def _resolve_match_date(self, raw_date: str, week_label: str) -> str:
        """Turn a short date like '3/15' into 'YYYY-MM-DD' using week context."""
        if not raw_date:
            return None

        m = re.match(r'(\d{1,2})/(\d{1,2})', raw_date)
        if not m:
            return raw_date

        month = int(m.group(1))
        day = int(m.group(2))

        # Infer year from the week label or season
        year = self.season
        # If we're in a Dec-Jan crossover, handle it
        # The week label like "Dec 29 - Jan 4" can help
        if "Jan" in week_label and month == 12:
            year = self.season - 1
        elif "Dec" in week_label and month == 1:
            year = self.season + 1

        try:
            return f"{year}-{month:02d}-{day:02d}"
        except Exception:
            return None

    def save_match(self, match: dict, week_label: str):
        """Save a match to the database."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            full_date = self._resolve_match_date(match.get("match_date"), week_label)
            if not full_date:
                return False

            # Use match_url slug as the unique ID if available
            match_url = match.get("match_url", "")
            if match_url:
                slug = match_url.rstrip("/").split("/")[-1]
                match_id = slug
            else:
                match_id = (
                    f"{match.get('home_team', '')[:3]}-"
                    f"{match.get('away_team', '')[:3]}-"
                    f"{full_date}"
                )
                match_id = re.sub(r'[^a-zA-Z0-9-]', '', match_id)

            cursor.execute("""
                INSERT INTO schedules (
                    match_id, match_url, season, match_date, match_time,
                    home_team, away_team, home_team_raw, away_team_raw,
                    venue, competition, broadcast, status,
                    home_score, away_score, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    match_time = excluded.match_time,
                    venue = excluded.venue,
                    broadcast = excluded.broadcast,
                    status = excluded.status,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    updated_at = excluded.updated_at
            """, (
                match_id,
                match_url,
                match.get("season"),
                full_date,
                match.get("match_time"),
                match.get("home_team"),
                match.get("away_team"),
                match.get("home_team_raw"),
                match.get("away_team_raw"),
                match.get("venue"),
                match.get("competition"),
                match.get("broadcast"),
                match.get("status"),
                match.get("home_score"),
                match.get("away_score"),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"  Error saving: {e}")
            return False
        finally:
            conn.close()

    async def scrape_full_schedule(self, start_date: str = None, end_date: str = None):
        """
        Scrape the full MLS schedule by loading the page once, jumping to the
        start date via hash, then clicking "next week" until we've covered
        enough weeks to reach end_date.

        Args:
            start_date: Start date as YYYY-MM-DD (default: Feb 1 of season year)
            end_date:   End date as YYYY-MM-DD (default: Dec 15 of season year)
        """
        if not start_date:
            start_date = f"{self.season}-02-01"
        if not end_date:
            end_date = f"{self.season}-12-15"

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        total_weeks = ((end_dt - start_dt).days // 7) + 1

        print(f"Scraping MLS schedule: {start_date} through {end_date} (~{total_weeks} weeks)")
        print("=" * 60)

        await self.start()
        page = await self.context.new_page()

        total_saved = 0
        weeks_scraped = 0

        try:
            # 1. Load the schedule page
            print("Loading schedule page...")
            await page.goto(
                "https://www.mlssoccer.com/schedule/scores",
                wait_until="domcontentloaded",
                timeout=60000
            )
            await asyncio.sleep(6)

            # 2. Jump to start date via hash
            print(f"Jumping to {start_date}...")
            await page.evaluate(
                f'window.location.hash = "#competition=all&club=all&date={start_date}"'
            )
            await asyncio.sleep(5)

            # 3. Walk through weeks by counting
            current_approx = start_dt
            prev_label = None
            stuck_count = 0

            for week_num in range(total_weeks + 1):
                week_label = await self._get_week_label(page)

                # Detect stuck (same label repeated)
                if week_label == prev_label:
                    stuck_count += 1
                    if stuck_count > 3:
                        print(f"  Stuck at '{week_label}', stopping.")
                        break
                else:
                    stuck_count = 0
                prev_label = week_label

                # Extract matches
                matches = await self._extract_week_matches(page)

                week_saved = 0
                for m in matches:
                    if self.save_match(m, week_label):
                        week_saved += 1

                total_saved += week_saved
                weeks_scraped += 1
                approx_str = current_approx.strftime("%Y-%m-%d")
                print(f"  [{weeks_scraped}/{total_weeks}] [{week_label}]  {len(matches)} matches, {week_saved} saved  (total: {total_saved})")

                # Click "next week"
                next_btn = await page.query_selector(".mls-o-buttons__icon--right")
                if not next_btn:
                    print("  No next button found, stopping.")
                    break

                await next_btn.click()
                await asyncio.sleep(4)
                current_approx += timedelta(days=7)

        except Exception as e:
            print(f"\nError during scrape: {e}")
            log_scrape("schedule", "all", "", "error", total_saved, str(e))
        finally:
            await page.close()
            await self.stop()

        print("\n" + "=" * 60)
        print(f"Schedule scrape complete!")
        print(f"  Weeks scraped: {weeks_scraped}")
        print(f"  Total matches saved: {total_saved}")
        log_scrape("schedule", "all", "mlssoccer.com", "success", total_saved)
        self._print_summary()

        return total_saved

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

        cursor.execute("""
            SELECT competition, COUNT(*) as cnt
            FROM schedules WHERE season = ?
            GROUP BY competition ORDER BY cnt DESC
        """, (self.season,))
        by_comp = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(DISTINCT home_team) + COUNT(DISTINCT away_team)
            FROM schedules WHERE season = ?
        """, (self.season,))

        conn.close()

        print(f"\nSummary for {self.season} season:")
        print(f"  Total matches: {total}")
        print(f"  Completed: {completed}")
        print(f"  Upcoming/Scheduled: {upcoming}")
        if by_comp:
            print(f"\n  By competition:")
            for comp, cnt in by_comp:
                print(f"    {comp or 'Unknown'}: {cnt}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape MLS schedule week-by-week")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    args = parser.parse_args()

    if args.init_db:
        init_database()

    scraper = ScheduleScraper()
    await scraper.scrape_full_schedule(start_date=args.start, end_date=args.end)


if __name__ == "__main__":
    asyncio.run(main())
