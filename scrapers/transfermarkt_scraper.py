"""
Transfermarkt Player Data Scraper

Scrapes additional player biographical data from Transfermarkt including:
- Birthdate
- Birthplace
- Citizenship
- Height (metric)

Uses this data to fill in gaps from MLS.com scraping.
"""
import asyncio
import re
import os
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.db import get_connection, log_scrape
from scrapers.normalize import parse_hometown

load_dotenv()

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


class TransfermarktScraper:
    """Scrapes player data from Transfermarkt."""

    def __init__(self):
        self.browser = None
        self.context = None

    async def start(self):
        """Initialize the browser."""
        self.playwright = await async_playwright().start()
        # Transfermarkt blocks headless browsers, so we need to use headed mode
        # or use additional stealth settings
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Must be headed for Transfermarkt
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        # Add stealth scripts
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

    async def stop(self):
        """Close the browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def search_player(self, first_name: str, last_name: str, team: str = "") -> dict:
        """Search for a player on Transfermarkt and extract their data."""
        full_name = f"{first_name} {last_name}"
        print(f"  Searching Transfermarkt: {full_name}")

        page = await self.context.new_page()
        result = {}

        try:
            # Search for player (don't add MLS as it breaks results)
            search_query = full_name
            search_url = f"https://www.transfermarkt.us/schnellsuche/ergebnis/schnellsuche?query={quote(search_query)}"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Find first player result link
            player_links = await page.query_selector_all("a[href*='/profil/spieler/']")

            if not player_links:
                print(f"    No results found")
                return result

            href = await player_links[0].get_attribute("href")
            if not href.startswith("http"):
                href = "https://www.transfermarkt.us" + href

            # Go to player profile
            await page.goto(href, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            page_text = await page.inner_text("body")

            # Extract birthdate - format "Jun 24, 1987" or "Date of birth/Age: Jun 24, 1987 (38)"
            dob_match = re.search(r'Date of birth/Age[:\s]+([A-Za-z]{3}\s+\d{1,2},\s+\d{4})', page_text)
            if dob_match:
                result["birthdate"] = dob_match.group(1).strip()

            # Extract birthplace
            bp_match = re.search(r'Place of birth[:\s]+([^\n]+)', page_text)
            if bp_match:
                birthplace = bp_match.group(1).strip()
                birthplace = re.split(r'\s{2,}|Citizenship|Height', birthplace)[0].strip()
                result["birthplace"] = birthplace

            # Extract citizenship
            cit_match = re.search(r'Citizenship[:\s]+([^\n]+)', page_text)
            if cit_match:
                citizenship = cit_match.group(1).strip()
                citizenship = re.split(r'\s{2,}|Height|Position', citizenship)[0].strip()
                result["citizenship"] = citizenship

            # Extract height (metric)
            height_match = re.search(r'Height[:\s]+(\d+[,\.]\d+\s*m)', page_text)
            if height_match:
                result["height_metric"] = height_match.group(1).strip()

            result["source_url"] = href

            if result:
                print(f"    Found: birthdate={result.get('birthdate')}, birthplace={result.get('birthplace')}")
                log_scrape("transfermarkt", None, href, "success", 1)

        except PlaywrightTimeout:
            print(f"    Timeout")
        except Exception as e:
            print(f"    Error: {e}")
        finally:
            await page.close()

        return result

    def update_player(self, player_id: int, data: dict):
        """Update player record with Transfermarkt data."""
        conn = get_connection()
        try:
            updates = []
            params = []

            if data.get("birthdate"):
                updates.append("birthdate = ?")
                params.append(data["birthdate"])

            if data.get("birthplace"):
                updates.append("birthplace = ?")
                params.append(data["birthplace"])
                # Parse hometown from birthplace
                city, state = parse_hometown(data["birthplace"])
                if city:
                    updates.append("hometown_city = COALESCE(hometown_city, ?)")
                    params.append(city)
                if state:
                    updates.append("hometown_state = COALESCE(hometown_state, ?)")
                    params.append(state)

            if data.get("citizenship"):
                updates.append("citizenship = COALESCE(citizenship, ?)")
                params.append(data["citizenship"])

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(player_id)

                sql = f"UPDATE players SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)
                conn.commit()

        finally:
            conn.close()

    async def process_players_missing_data(self, field: str = "birthdate", team_filter: str = None, limit: int = 100):
        """Process players missing specific data."""
        conn = get_connection()
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()

        query = f"SELECT * FROM players WHERE ({field} IS NULL OR {field} = '')"
        params = []

        if team_filter:
            query += " AND team LIKE ?"
            params.append(f"%{team_filter}%")

        query += f" ORDER BY team, last_name LIMIT {limit}"

        cursor.execute(query, params)
        players = cursor.fetchall()
        conn.close()

        if not players:
            print(f"No players missing {field}.")
            return

        print(f"Processing {len(players)} players missing {field}...")
        print("=" * 60)

        await self.start()
        updated_count = 0

        try:
            for i, player in enumerate(players, 1):
                print(f"\n[{i}/{len(players)}] {player['first_name']} {player['last_name']} ({player['team']})")

                data = await self.search_player(
                    player["first_name"],
                    player["last_name"],
                    player["team"]
                )

                if data:
                    self.update_player(player["id"], data)
                    updated_count += 1

                await asyncio.sleep(REQUEST_DELAY)

        finally:
            await self.stop()

        print("\n" + "=" * 60)
        print(f"Complete! Updated {updated_count}/{len(players)} players")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scrape player data from Transfermarkt")
    parser.add_argument("--field", default="birthdate", help="Field to fill (birthdate, birthplace, citizenship)")
    parser.add_argument("--team", help="Filter by team name")
    parser.add_argument("--limit", type=int, default=100, help="Max players to process")
    parser.add_argument("--player", help="Search single player (first last)")
    args = parser.parse_args()

    scraper = TransfermarktScraper()

    if args.player:
        await scraper.start()
        parts = args.player.split()
        first_name = parts[0]
        last_name = " ".join(parts[1:])

        result = await scraper.search_player(first_name, last_name)

        if result:
            print(f"\n{'='*50}")
            print("PLAYER DATA FOUND")
            print(f"{'='*50}")
            for key, value in result.items():
                print(f"  {key}: {value}")
        else:
            print("\nNo data found.")

        await scraper.stop()
    else:
        await scraper.process_players_missing_data(
            field=args.field,
            team_filter=args.team,
            limit=args.limit
        )


if __name__ == "__main__":
    asyncio.run(main())
