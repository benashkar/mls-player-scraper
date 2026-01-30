"""
MLS Roster Scraper

Scrapes player rosters from all 30 MLS club websites using Playwright
for JavaScript rendering. Extracts player details including hometown
and high school data where available.
"""
import asyncio
import re
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.config_loader import load_teams, get_team_by_slug
from scrapers.db import get_connection, log_scrape, init_database
from scrapers.normalize import normalize_high_school, parse_hometown

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


class RosterScraper:
    """Scrapes MLS team rosters."""

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

    async def scrape_team_roster(self, team: dict) -> list:
        """
        Scrape a single team's roster page.

        Args:
            team: Team config dict with name, roster_url, etc.

        Returns:
            List of player dicts with basic info
        """
        page = await self.context.new_page()
        players = []

        try:
            print(f"  Scraping roster: {team['name']}")

            # Use MLS.com roster URL (more reliable than club sites)
            mls_roster_url = f"https://www.mlssoccer.com/clubs/{team['slug']}/roster/"
            print(f"    Using MLS.com: {mls_roster_url}")

            await page.goto(mls_roster_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(6)  # Let JS render (increased for dynamic content)

            # Try multiple selector strategies (sites vary in structure)
            player_data = await self._find_player_elements(page)

            if not player_data:
                print(f"    Warning: No players found for {team['name']}")
                log_scrape("roster", team["slug"], mls_roster_url, "warning", 0, "No players found")
                return []

            for data in player_data:
                try:
                    player = self._extract_player_from_url(data["href"], team)
                    if player and player.get("last_name"):
                        players.append(player)
                except Exception as e:
                    print(f"    Error extracting player: {e}")
                    continue

            print(f"    Found {len(players)} players")
            log_scrape("roster", team["slug"], team["roster_url"], "success", len(players))

        except PlaywrightTimeout:
            print(f"    Timeout loading {team['name']} roster")
            log_scrape("roster", team["slug"], team["roster_url"], "error", 0, "Timeout")
        except Exception as e:
            print(f"    Error scraping {team['name']}: {e}")
            log_scrape("roster", team["slug"], team["roster_url"], "error", 0, str(e))
        finally:
            await page.close()

        return players

    async def _find_player_elements(self, page: Page):
        """Try multiple selectors to find player cards."""
        # For MLS.com, player links are the most reliable
        all_links = await page.query_selector_all("a[href*='/players/']")

        # Filter to unique player links and extract URLs
        seen_hrefs = set()
        player_data = []

        for link in all_links:
            href = await link.get_attribute("href")
            if not href or "/players/" not in href:
                continue

            # Skip index/list pages
            if href.endswith("/players/") or href.endswith("/players/index") or "/players/index" in href:
                continue

            # Normalize URL
            if not href.startswith("http"):
                href = "https://www.mlssoccer.com" + href

            # Remove query strings and trailing slashes for deduplication
            clean_href = href.split("?")[0].rstrip("/")

            if clean_href not in seen_hrefs:
                seen_hrefs.add(clean_href)
                player_data.append({"href": href, "link": link})

        return player_data

    def _extract_player_from_url(self, href: str, team: dict) -> dict:
        """Extract player info from URL."""
        player = {
            "team": team["name"],
            "season": self.season,
            "first_name": None,
            "last_name": None,
            "position": None,
            "jersey_number": None,
            "headshot_url": None,
            "bio_url": href,
        }

        # Extract name from URL (e.g., /players/christopher-cupps/)
        name_match = re.search(r'/players/([^/\?]+)/?', href)
        if name_match:
            name_slug = name_match.group(1)
            # Handle special characters in names
            name_parts = name_slug.replace('-', ' ').title().split()
            if len(name_parts) >= 2:
                player["first_name"] = name_parts[0]
                player["last_name"] = " ".join(name_parts[1:])
            elif len(name_parts) == 1:
                player["last_name"] = name_parts[0]

        return player

    async def scrape_player_bio(self, player: dict, team_domain: str = None) -> dict:
        """
        Scrape detailed info from a player's bio page.

        First tries MLS.com, then falls back to club site for birthplace data.
        """
        if not player.get("bio_url"):
            return player

        page = await self.context.new_page()

        try:
            # First try MLS.com
            await page.goto(player["bio_url"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            bio_text = await page.inner_text("body")

            # Extract position
            pos_match = re.search(r'Position[:\s]+([A-Za-z]+)', bio_text, re.IGNORECASE)
            if pos_match:
                player["position"] = pos_match.group(1).strip()

            # Extract height
            height_match = re.search(r"Height[:\s]+(\d+['\u2019]\s*\d*\"?)", bio_text, re.IGNORECASE)
            if height_match:
                player["height"] = height_match.group(1).strip()

            # Extract weight
            weight_match = re.search(r'Weight[:\s]+(\d+)', bio_text, re.IGNORECASE)
            if weight_match:
                player["weight"] = int(weight_match.group(1))

            # Extract birthdate - MLS uses format like "6.24.1987 (38)" or "Date of birth: 6.24.1987"
            dob_patterns = [
                r'(\d{1,2}\.\d{1,2}\.\d{4})\s*\(\d+\)',  # 6.24.1987 (38)
                r'Date of birth[:\s]+(\d{1,2}\.\d{1,2}\.\d{4})',  # Date of birth: 6.24.1987
                r'Born[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',  # Born: June 24, 1987
                r'DOB[:\s]+(\d{1,2}/\d{1,2}/\d{4})',  # DOB: 6/24/1987
            ]
            for pattern in dob_patterns:
                dob_match = re.search(pattern, bio_text, re.IGNORECASE)
                if dob_match:
                    player["birthdate"] = dob_match.group(1).strip()
                    break

            # Extract birthplace from MLS page
            birthplace_patterns = [
                r'Birthplace[:\s]+([^\n\r]+)',
                r'Place of birth[:\s]+([^\n\r]+)',
                r'Born in[:\s]+([^\n\r]+)',
            ]
            for pattern in birthplace_patterns:
                bp_match = re.search(pattern, bio_text, re.IGNORECASE)
                if bp_match:
                    birthplace = bp_match.group(1).strip()
                    # Clean up - stop at common delimiters
                    birthplace = re.split(r'\s{2,}|Height|Weight|Position', birthplace)[0].strip()
                    if birthplace and not player.get("birthplace"):
                        player["birthplace"] = birthplace
                        city, state = parse_hometown(birthplace)
                        if city and not player.get("hometown_city"):
                            player["hometown_city"] = city
                        if state and not player.get("hometown_state"):
                            player["hometown_state"] = state
                    break

            # Try to get headshot
            img = await page.query_selector("img[src*='images.mlssoccer.com']")
            if img:
                src = await img.get_attribute("src")
                if src:
                    player["headshot_url"] = src

            # Now try club site for birthplace (more reliable)
            if team_domain:
                name_slug = f"{player.get('first_name', '')}-{player.get('last_name', '')}".lower().replace(' ', '-')
                club_url = f"https://www.{team_domain}/players/{name_slug}/"

                try:
                    await page.goto(club_url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)

                    club_text = await page.inner_text("body")

                    # Extract birthplace from club site
                    birthplace_match = re.search(r'Birthplace[:\s]+([^\n]+)', club_text, re.IGNORECASE)
                    if birthplace_match:
                        birthplace = birthplace_match.group(1).strip()
                        player["birthplace"] = birthplace
                        # Parse city/state
                        city, state = parse_hometown(birthplace)
                        if city:
                            player["hometown_city"] = city
                        if state:
                            player["hometown_state"] = state

                except Exception as e:
                    # Club site failed, that's okay
                    pass

            log_scrape("player_bio", player.get("team"), player["bio_url"], "success", 1)

        except PlaywrightTimeout:
            print(f"      Timeout loading bio for {player.get('last_name', 'unknown')}")
        except Exception as e:
            print(f"      Error scraping bio: {e}")
        finally:
            await page.close()

        return player

    def save_player(self, player: dict):
        """Save a player to the database."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO players (
                    team, season, first_name, last_name, hometown_city, hometown_state,
                    high_school, position, jersey_number, height, weight, birthdate,
                    citizenship, headshot_url, bio_url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team, season, first_name, last_name) DO UPDATE SET
                    hometown_city = excluded.hometown_city,
                    hometown_state = excluded.hometown_state,
                    high_school = excluded.high_school,
                    position = excluded.position,
                    jersey_number = excluded.jersey_number,
                    height = excluded.height,
                    weight = excluded.weight,
                    birthdate = excluded.birthdate,
                    citizenship = excluded.citizenship,
                    headshot_url = excluded.headshot_url,
                    bio_url = excluded.bio_url,
                    updated_at = excluded.updated_at
            """, (
                player.get("team"),
                player.get("season"),
                player.get("first_name"),
                player.get("last_name"),
                player.get("hometown_city"),
                player.get("hometown_state"),
                player.get("high_school"),
                player.get("position"),
                player.get("jersey_number"),
                player.get("height"),
                player.get("weight"),
                player.get("birthdate"),
                player.get("citizenship"),
                player.get("headshot_url"),
                player.get("bio_url"),
                datetime.now().isoformat()
            ))
            conn.commit()
        except Exception as e:
            print(f"      Error saving player: {e}")
        finally:
            conn.close()

    async def scrape_all_rosters(self, with_bios: bool = True):
        """
        Scrape all 30 team rosters.

        Args:
            with_bios: If True, also scrape individual player bio pages
        """
        print(f"Starting roster scrape for {self.season} season")
        print(f"Teams to scrape: {len(self.config['teams'])}")
        print("-" * 50)

        await self.start()

        try:
            for i, team in enumerate(self.config["teams"], 1):
                print(f"\n[{i}/{len(self.config['teams'])}] {team['name']}")

                # Scrape roster page
                players = await self.scrape_team_roster(team)

                if with_bios and players:
                    print(f"    Scraping {len(players)} player bios...")
                    for j, player in enumerate(players, 1):
                        if player.get("bio_url"):
                            print(f"      [{j}/{len(players)}] {player.get('first_name', '')} {player.get('last_name', '')}")
                            player = await self.scrape_player_bio(player, team.get("domain"))

                        self.save_player(player)

                # Delay between teams
                await asyncio.sleep(REQUEST_DELAY * 2)

        finally:
            await self.stop()

        print("\n" + "=" * 50)
        print("Roster scrape complete!")
        self._print_summary()

    async def scrape_single_team(self, team_slug: str, with_bios: bool = True):
        """Scrape a single team's roster."""
        team = get_team_by_slug(team_slug)
        if not team:
            print(f"Team not found: {team_slug}")
            return

        await self.start()

        try:
            print(f"Scraping {team['name']}...")
            players = await self.scrape_team_roster(team)

            if with_bios and players:
                print(f"Scraping {len(players)} player bios...")
                for j, player in enumerate(players, 1):
                    if player.get("bio_url"):
                        print(f"  [{j}/{len(players)}] {player.get('first_name', '')} {player.get('last_name', '')}")
                        player = await self.scrape_player_bio(player, team.get("domain"))
                    self.save_player(player)

        finally:
            await self.stop()

        self._print_summary()

    def _print_summary(self):
        """Print summary statistics from the database."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM players WHERE season = ?", (self.season,))
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM players WHERE season = ? AND hometown_city IS NOT NULL", (self.season,))
        with_hometown = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM players WHERE season = ? AND high_school IS NOT NULL", (self.season,))
        with_hs = cursor.fetchone()[0]

        conn.close()

        print(f"\nSummary for {self.season} season:")
        print(f"  Total players: {total}")
        print(f"  With hometown: {with_hometown} ({100*with_hometown//max(total,1)}%)")
        print(f"  With high school: {with_hs} ({100*with_hs//max(total,1)}%)")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape MLS rosters")
    parser.add_argument("--team", help="Scrape single team by slug (e.g., 'chicago-fire-fc')")
    parser.add_argument("--no-bios", action="store_true", help="Skip individual bio pages")
    parser.add_argument("--init-db", action="store_true", help="Initialize database before scraping")
    args = parser.parse_args()

    if args.init_db:
        init_database()

    scraper = RosterScraper()

    if args.team:
        await scraper.scrape_single_team(args.team, with_bios=not args.no_bios)
    else:
        await scraper.scrape_all_rosters(with_bios=not args.no_bios)


if __name__ == "__main__":
    asyncio.run(main())
