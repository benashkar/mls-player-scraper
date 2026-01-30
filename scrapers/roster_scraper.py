"""
MLS Roster Scraper
==================

This module scrapes player roster data from MLS team websites.
It uses Playwright to control a web browser, which is necessary because
MLS websites load their content using JavaScript.

KEY CONCEPTS FOR JUNIOR DEVELOPERS:
-----------------------------------

1. WEB SCRAPING BASICS:
   - We "visit" web pages programmatically using a browser
   - We find elements on the page using CSS selectors (like finding needles in a haystack)
   - We extract text/data from those elements

2. WHY PLAYWRIGHT?
   - Some websites load content with JavaScript AFTER the page loads
   - Simple HTTP requests (like 'requests' library) only get the initial HTML
   - Playwright controls a real browser, so JavaScript runs and we see everything

3. ASYNC/AWAIT:
   - 'async' functions can pause and wait for slow operations (like loading web pages)
   - 'await' is where we pause and wait
   - This lets us handle multiple operations efficiently

4. CSS SELECTORS:
   - These are patterns to find HTML elements
   - Examples:
     - "a" = all links
     - "a[href*='/players/']" = links where href contains '/players/'
     - ".mls-c-club" = elements with class "mls-c-club"

COMMON TASKS:
-------------
- Scrape all teams: python run_scraper.py --all
- Scrape one team:  python run_scraper.py --team chicago-fire-fc
- Test scraper:     python run_scraper.py --test

TROUBLESHOOTING:
----------------
- If scraper finds 0 players: MLS website structure may have changed
- If timeouts occur: Check internet connection, try increasing timeout
- If "headless" fails: Set HEADLESS=false in .env to see what's happening
"""

import asyncio          # For async/await functionality
import re               # Regular expressions for pattern matching in text
import os               # Access environment variables
import sys              # System-level operations
from datetime import datetime
from pathlib import Path

# Playwright is our browser automation library
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

# Load environment variables from .env file
from dotenv import load_dotenv

# Add parent directory to Python path so we can import our modules
# This is needed because we're in a subfolder (scrapers/)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our custom modules
from scrapers.config_loader import load_teams, get_team_by_slug
from scrapers.db import get_connection, log_scrape, init_database
from scrapers.normalize import normalize_high_school, parse_hometown

# Load configuration from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================
# These settings can be changed in the .env file

# How long to wait between requests (in seconds)
# Be respectful to servers - don't hammer them with requests!
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))

# Whether to run browser invisibly (True) or show it (False)
# Set to False when debugging to see what the scraper is doing
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


# =============================================================================
# MAIN SCRAPER CLASS
# =============================================================================

class RosterScraper:
    """
    Scrapes MLS team rosters from mlssoccer.com.

    This class handles:
    1. Opening a browser
    2. Navigating to team roster pages
    3. Finding player links on the page
    4. Visiting each player's bio page for details
    5. Saving everything to the database

    Usage:
        scraper = RosterScraper()
        await scraper.scrape_all_rosters()

    Or for one team:
        scraper = RosterScraper()
        await scraper.scrape_single_team("chicago-fire-fc")
    """

    def __init__(self):
        """
        Initialize the scraper.

        Sets up instance variables but doesn't start the browser yet.
        The browser is started when you call start() or one of the scrape methods.
        """
        # Browser-related variables (set in start())
        self.browser = None     # The browser instance
        self.context = None     # Browser context (like an incognito window)
        self.playwright = None  # Playwright controller

        # Load team configuration from config/teams.json
        self.config = load_teams()
        self.season = self.config["season"]  # Current season year (e.g., 2026)

    # =========================================================================
    # BROWSER MANAGEMENT
    # =========================================================================

    async def start(self):
        """
        Start the browser.

        This must be called before scraping. Creates a Chromium browser instance
        with a realistic user agent to avoid being blocked.

        Why 'async'?
        Starting a browser takes time, so we use async to not block other code.
        """
        # Initialize Playwright
        self.playwright = await async_playwright().start()

        # Launch Chromium browser
        # headless=True means no visible window (faster, uses less resources)
        # headless=False shows the browser (useful for debugging)
        self.browser = await self.playwright.chromium.launch(headless=HEADLESS)

        # Create a browser context with a realistic user agent
        # User agent tells websites what browser we're using
        # Without this, some sites block automated requests
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

    async def stop(self):
        """
        Close the browser and clean up resources.

        Always call this when done scraping to avoid memory leaks!
        """
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # =========================================================================
    # ROSTER SCRAPING
    # =========================================================================

    async def scrape_team_roster(self, team: dict) -> list:
        """
        Scrape a single team's roster page.

        This method:
        1. Opens the team's roster page on mlssoccer.com
        2. Waits for JavaScript to load
        3. Finds all player links
        4. Extracts basic info from each link

        Args:
            team: A dictionary with team info from config/teams.json
                  Must have 'name', 'slug', 'roster_url' keys

        Returns:
            List of player dictionaries with basic info (name, team, bio_url)

        Example team dict:
            {
                "name": "Chicago Fire FC",
                "slug": "chicago-fire-fc",
                "domain": "chicagofirefc.com",
                "roster_url": "https://www.chicagofirefc.com/roster/"
            }
        """
        # Open a new browser tab
        page = await self.context.new_page()
        players = []

        try:
            print(f"  Scraping roster: {team['name']}")

            # Build the MLS.com roster URL
            # MLS.com is more reliable than individual club sites
            mls_roster_url = f"https://www.mlssoccer.com/clubs/{team['slug']}/roster/"
            print(f"    Using MLS.com: {mls_roster_url}")

            # Navigate to the page
            # wait_until="domcontentloaded" = wait for HTML to load (not all images)
            # timeout=45000 = give up after 45 seconds
            await page.goto(mls_roster_url, wait_until="domcontentloaded", timeout=45000)

            # Wait for JavaScript to render the player list
            # MLS.com loads players dynamically, so we need to wait
            await asyncio.sleep(6)  # 6 seconds - increased for reliability

            # Find all player elements on the page
            player_data = await self._find_player_elements(page)

            if not player_data:
                # No players found - this might mean:
                # 1. Website structure changed
                # 2. Page didn't load properly
                # 3. We're being blocked
                print(f"    Warning: No players found for {team['name']}")
                log_scrape("roster", team["slug"], mls_roster_url, "warning", 0, "No players found")
                return []

            # Extract player info from each link
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
            # Page took too long to load
            print(f"    Timeout loading {team['name']} roster")
            log_scrape("roster", team["slug"], team["roster_url"], "error", 0, "Timeout")

        except Exception as e:
            # Something else went wrong
            print(f"    Error scraping {team['name']}: {e}")
            log_scrape("roster", team["slug"], team["roster_url"], "error", 0, str(e))

        finally:
            # Always close the tab, even if there was an error
            await page.close()

        return players

    async def _find_player_elements(self, page: Page):
        """
        Find all player links on a roster page.

        We look for links that contain '/players/' in the URL, then
        filter out duplicates and non-player pages.

        Args:
            page: The Playwright page object

        Returns:
            List of dicts with 'href' and 'link' keys
        """
        # Find all links to player pages
        # CSS selector explanation:
        # - "a" = anchor (link) elements
        # - "[href*='/players/']" = where href attribute contains '/players/'
        all_links = await page.query_selector_all("a[href*='/players/']")

        # Track which URLs we've seen to avoid duplicates
        seen_hrefs = set()
        player_data = []

        for link in all_links:
            # Get the href (URL) from the link
            href = await link.get_attribute("href")

            if not href or "/players/" not in href:
                continue

            # Skip index pages (list of all players, not individual player)
            if href.endswith("/players/") or href.endswith("/players/index") or "/players/index" in href:
                continue

            # Make sure URL is absolute (starts with http)
            if not href.startswith("http"):
                href = "https://www.mlssoccer.com" + href

            # Remove query strings (?foo=bar) and trailing slashes for deduplication
            clean_href = href.split("?")[0].rstrip("/")

            # Only add if we haven't seen this URL before
            if clean_href not in seen_hrefs:
                seen_hrefs.add(clean_href)
                player_data.append({"href": href, "link": link})

        return player_data

    def _extract_player_from_url(self, href: str, team: dict) -> dict:
        """
        Extract player info from their URL.

        Player URLs look like: /players/christopher-cupps/
        We parse the name from the URL slug.

        Args:
            href: The player's profile URL
            team: The team dictionary

        Returns:
            Dictionary with player info
        """
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

        # Extract name from URL using regex
        # Pattern: /players/[name-slug]/
        # Example: /players/christopher-cupps/ -> "christopher-cupps"
        name_match = re.search(r'/players/([^/\?]+)/?', href)

        if name_match:
            name_slug = name_match.group(1)

            # Convert slug to name parts
            # "christopher-cupps" -> ["Christopher", "Cupps"]
            name_parts = name_slug.replace('-', ' ').title().split()

            if len(name_parts) >= 2:
                # First word is first name, rest is last name
                player["first_name"] = name_parts[0]
                player["last_name"] = " ".join(name_parts[1:])
            elif len(name_parts) == 1:
                # Single-name players (like "Artur")
                player["last_name"] = name_parts[0]

        return player

    # =========================================================================
    # PLAYER BIO SCRAPING
    # =========================================================================

    async def scrape_player_bio(self, player: dict, team_domain: str = None) -> dict:
        """
        Scrape detailed info from a player's bio page.

        This gets additional data not on the roster page:
        - Position (Forward, Midfielder, etc.)
        - Height and weight
        - Birthdate and birthplace
        - Hometown info

        We try two sources:
        1. MLS.com player page (primary)
        2. Club website (backup, sometimes has more hometown data)

        Args:
            player: Dictionary with basic player info (must have bio_url)
            team_domain: The club's website domain (e.g., "chicagofirefc.com")

        Returns:
            Updated player dictionary with additional fields
        """
        if not player.get("bio_url"):
            return player

        page = await self.context.new_page()

        try:
            # -----------------------------------------------------------------
            # STEP 1: Scrape MLS.com player page
            # -----------------------------------------------------------------
            await page.goto(player["bio_url"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Get all text from the page for regex searching
            bio_text = await page.inner_text("body")

            # Extract position (Forward, Midfielder, Defender, Goalkeeper)
            pos_match = re.search(r'Position[:\s]+([A-Za-z]+)', bio_text, re.IGNORECASE)
            if pos_match:
                player["position"] = pos_match.group(1).strip()

            # Extract height (e.g., "5' 10"" or "6' 2"")
            # The \u2019 is a fancy apostrophe some sites use
            height_match = re.search(r"Height[:\s]+(\d+['\u2019]\s*\d*\"?)", bio_text, re.IGNORECASE)
            if height_match:
                player["height"] = height_match.group(1).strip()

            # Extract weight (just the number, e.g., 180)
            weight_match = re.search(r'Weight[:\s]+(\d+)', bio_text, re.IGNORECASE)
            if weight_match:
                player["weight"] = int(weight_match.group(1))

            # -----------------------------------------------------------------
            # Extract birthdate - MLS uses multiple formats
            # -----------------------------------------------------------------
            dob_patterns = [
                r'(\d{1,2}\.\d{1,2}\.\d{4})\s*\(\d+\)',     # 6.24.1987 (38)
                r'Date of birth[:\s]+(\d{1,2}\.\d{1,2}\.\d{4})',  # Date of birth: 6.24.1987
                r'Born[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',      # Born: June 24, 1987
                r'DOB[:\s]+(\d{1,2}/\d{1,2}/\d{4})',               # DOB: 6/24/1987
            ]
            for pattern in dob_patterns:
                dob_match = re.search(pattern, bio_text, re.IGNORECASE)
                if dob_match:
                    player["birthdate"] = dob_match.group(1).strip()
                    break

            # -----------------------------------------------------------------
            # Extract birthplace
            # -----------------------------------------------------------------
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
                        # Try to parse city/state from birthplace
                        city, state = parse_hometown(birthplace)
                        if city and not player.get("hometown_city"):
                            player["hometown_city"] = city
                        if state and not player.get("hometown_state"):
                            player["hometown_state"] = state
                    break

            # Try to get headshot image URL
            img = await page.query_selector("img[src*='images.mlssoccer.com']")
            if img:
                src = await img.get_attribute("src")
                if src:
                    player["headshot_url"] = src

            # -----------------------------------------------------------------
            # STEP 2: Try club website for additional data
            # -----------------------------------------------------------------
            if team_domain:
                # Build URL to player page on club site
                name_slug = f"{player.get('first_name', '')}-{player.get('last_name', '')}".lower().replace(' ', '-')
                club_url = f"https://www.{team_domain}/players/{name_slug}/"

                try:
                    await page.goto(club_url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)

                    club_text = await page.inner_text("body")

                    # Extract birthplace from club site (often more detailed)
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
                    # Club site failed - that's okay, we have MLS.com data
                    pass

            log_scrape("player_bio", player.get("team"), player["bio_url"], "success", 1)

        except PlaywrightTimeout:
            print(f"      Timeout loading bio for {player.get('last_name', 'unknown')}")
        except Exception as e:
            print(f"      Error scraping bio: {e}")
        finally:
            await page.close()

        return player

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def save_player(self, player: dict):
        """
        Save a player to the database.

        Uses INSERT ... ON CONFLICT DO UPDATE (upsert):
        - If player doesn't exist: INSERT new row
        - If player exists: UPDATE existing row

        The "conflict" is detected by the unique constraint on
        (team, season, first_name, last_name).

        Args:
            player: Dictionary with player data
        """
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

    # =========================================================================
    # HIGH-LEVEL SCRAPING METHODS
    # =========================================================================

    async def scrape_all_rosters(self, with_bios: bool = True):
        """
        Scrape all 30 MLS team rosters.

        This is the main method for a full scrape. It:
        1. Starts the browser
        2. Loops through all teams in config/teams.json
        3. Scrapes each roster page
        4. Optionally scrapes each player's bio page
        5. Saves everything to the database
        6. Closes the browser

        Args:
            with_bios: If True, also scrape individual player bio pages
                       (slower but gets more data like birthdate, height)
        """
        print(f"Starting roster scrape for {self.season} season")
        print(f"Teams to scrape: {len(self.config['teams'])}")
        print("-" * 50)

        await self.start()  # Start the browser

        try:
            for i, team in enumerate(self.config["teams"], 1):
                print(f"\n[{i}/{len(self.config['teams'])}] {team['name']}")

                # Scrape the roster page
                players = await self.scrape_team_roster(team)

                if with_bios and players:
                    print(f"    Scraping {len(players)} player bios...")
                    for j, player in enumerate(players, 1):
                        if player.get("bio_url"):
                            print(f"      [{j}/{len(players)}] {player.get('first_name', '')} {player.get('last_name', '')}")
                            player = await self.scrape_player_bio(player, team.get("domain"))

                        self.save_player(player)

                # Be nice to the server - wait between teams
                await asyncio.sleep(REQUEST_DELAY * 2)

        finally:
            await self.stop()  # Always close the browser

        print("\n" + "=" * 50)
        print("Roster scrape complete!")
        self._print_summary()

    async def scrape_single_team(self, team_slug: str, with_bios: bool = True):
        """
        Scrape a single team's roster.

        Useful for testing or updating one team's data.

        Args:
            team_slug: The team identifier (e.g., "chicago-fire-fc")
            with_bios: If True, also scrape player bio pages
        """
        # Look up team in config
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


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """Main entry point when running this file directly."""
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
    # This runs when you execute: python scrapers/roster_scraper.py
    asyncio.run(main())
