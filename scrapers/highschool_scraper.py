"""
High School Data Scraper

Scrapes high school information for MLS players from multiple sources:
1. Direct club signing announcement URLs (pattern-based)
2. Player bio pages with related news links
3. NCSA recruiting profiles (direct URL construction)
4. DuckDuckGo HTML search fallback

Tracks the source URL for each piece of data found.
"""
import asyncio
import re
import os
import sys
import urllib.parse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

from playwright.async_api import async_playwright, Page
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.db import get_connection, log_scrape
from scrapers.normalize import normalize_high_school, parse_hometown

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
    source_name: str = ""


class HighSchoolScraper:
    """Scrapes high school data from multiple sources."""

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
                                team: str, team_domain: str) -> Optional[HighSchoolResult]:
        """
        Search for player's high school using multiple sources.
        """
        full_name = f"{first_name} {last_name}"
        print(f"  Searching for high school: {full_name}")

        # Strategy 1: Try direct signing announcement URLs
        result = await self._try_direct_signing_urls(first_name, last_name, team_domain)
        if result:
            return result

        await asyncio.sleep(REQUEST_DELAY)

        # Strategy 2: Check player bio page for news links
        result = await self._check_player_bio_page(first_name, last_name, team_domain)
        if result:
            return result

        await asyncio.sleep(REQUEST_DELAY)

        # Strategy 3: Try direct NCSA URL
        result = await self._try_direct_ncsa(first_name, last_name)
        if result:
            return result

        await asyncio.sleep(REQUEST_DELAY)

        # Strategy 4: DuckDuckGo HTML search
        result = await self._search_duckduckgo_html(full_name, team, team_domain)
        if result:
            return result

        print(f"    No high school found for {full_name}")
        return None

    async def _try_direct_signing_urls(self, first_name: str, last_name: str,
                                        team_domain: str) -> Optional[HighSchoolResult]:
        """Try common signing announcement URL patterns."""
        page = await self.context.new_page()

        try:
            # Common URL patterns for signing announcements
            name_slug = f"{first_name}-{last_name}".lower().replace(" ", "-")
            base_url = f"https://www.{team_domain}"

            url_patterns = [
                f"{base_url}/news/{team_domain.split('.')[0].replace('fc', '').replace('sc', '').strip()}-signs-{name_slug}",
                f"{base_url}/news/{name_slug}-signs",
                f"{base_url}/news/chicago-fire-fc-signs-academy-defender-{name_slug}-to-first-team-contract-as-a-homegrown-player",
                f"{base_url}/news/{name_slug}-homegrown",
            ]

            for url in url_patterns:
                try:
                    print(f"    Trying: {url[:60]}...")
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                    if response and response.status == 200:
                        await asyncio.sleep(1)
                        text = await page.inner_text("body")

                        result = self._extract_high_school_from_text(text, url, "Club Signing Announcement")
                        if result:
                            log_scrape("highschool_direct_url", None, url, "success", 1)
                            return result
                except:
                    continue

        except Exception as e:
            print(f"    Direct URL error: {e}")
        finally:
            await page.close()

        return None

    async def _check_player_bio_page(self, first_name: str, last_name: str,
                                      team_domain: str) -> Optional[HighSchoolResult]:
        """Check player's bio page and related news."""
        page = await self.context.new_page()

        try:
            # Try player bio page
            name_slug = f"{first_name}-{last_name}".lower().replace(" ", "-")
            bio_url = f"https://www.{team_domain}/players/{name_slug}/"

            print(f"    Checking bio page: {bio_url[:50]}...")

            await page.goto(bio_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            text = await page.inner_text("body")

            # Check if high school is on the bio page
            result = self._extract_high_school_from_text(text, bio_url, "Player Bio Page")
            if result:
                log_scrape("highschool_bio", None, bio_url, "success", 1)
                return result

            # Look for news links on the page
            news_links = await page.query_selector_all("a[href*='/news/']")

            for link in news_links[:5]:
                href = await link.get_attribute("href")
                link_text = (await link.inner_text()).lower()

                # Look for signing-related links
                if "sign" in link_text or "homegrown" in link_text:
                    if not href.startswith("http"):
                        href = f"https://www.{team_domain}" + href

                    print(f"    Found news link: {href[:50]}...")

                    await page.goto(href, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)

                    text = await page.inner_text("body")
                    result = self._extract_high_school_from_text(text, href, "Club Signing Announcement")
                    if result:
                        log_scrape("highschool_bio_news", None, href, "success", 1)
                        return result

        except Exception as e:
            print(f"    Bio page error: {e}")
        finally:
            await page.close()

        return None

    async def _try_direct_ncsa(self, first_name: str, last_name: str) -> Optional[HighSchoolResult]:
        """Try to find NCSA profile with direct navigation."""
        page = await self.context.new_page()

        try:
            # NCSA search page
            name_query = f"{first_name} {last_name}"
            search_url = f"https://www.ncsasports.org/search?q={urllib.parse.quote(name_query)}"

            print(f"    Searching NCSA: {name_query}")

            await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(3)

            # Look for soccer recruiting profile links
            links = await page.query_selector_all("a[href*='soccer-recruiting']")

            for link in links[:3]:
                href = await link.get_attribute("href")
                if not href:
                    continue

                if not href.startswith("http"):
                    href = "https://www.ncsasports.org" + href

                # Check if this looks like a player profile
                if "/mens-soccer-recruiting/" in href or "/womens-soccer-recruiting/" in href:
                    print(f"    Found NCSA profile: {href[:60]}...")

                    await page.goto(href, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)

                    # Extract high school from URL
                    hs_from_url = self._extract_hs_from_ncsa_url(href)
                    if hs_from_url:
                        city, state = self._extract_location_from_ncsa(href, "")
                        print(f"    Found (NCSA): {hs_from_url}")
                        log_scrape("highschool_ncsa", None, href, "success", 1)

                        return HighSchoolResult(
                            high_school=hs_from_url,
                            city=city,
                            state=state,
                            source_url=href,
                            source_name="NCSA Recruiting Profile"
                        )

                    # Also try to extract from page text
                    text = await page.inner_text("body")
                    hs_match = re.search(r"High School[:\s]+([^\n,]+)", text, re.IGNORECASE)
                    if hs_match:
                        hs_name = hs_match.group(1).strip()
                        if len(hs_name) > 3 and len(hs_name) < 80:
                            city, state = self._extract_location_from_ncsa(href, text)
                            print(f"    Found (NCSA): {hs_name}")
                            log_scrape("highschool_ncsa", None, href, "success", 1)

                            return HighSchoolResult(
                                high_school=hs_name,
                                city=city,
                                state=state,
                                source_url=href,
                                source_name="NCSA Recruiting Profile"
                            )

        except Exception as e:
            print(f"    NCSA error: {e}")
        finally:
            await page.close()

        return None

    async def _search_duckduckgo_html(self, player_name: str, team: str,
                                       team_domain: str) -> Optional[HighSchoolResult]:
        """Search DuckDuckGo HTML version (no JS required)."""
        page = await self.context.new_page()

        try:
            # Use DuckDuckGo HTML-only version
            query = f'{player_name} {team} "high school"'
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

            print(f"    Searching DuckDuckGo HTML...")

            await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2)

            # Get search results
            results = await page.query_selector_all(".result__a")

            for result in results[:5]:
                href = await result.get_attribute("href")
                if not href:
                    continue

                # Extract actual URL from DuckDuckGo redirect
                if "uddg=" in href:
                    href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])

                # Prioritize club sites and news
                if team_domain in href or "mlssoccer.com" in href:
                    print(f"    Checking: {href[:60]}...")

                    try:
                        await page.goto(href, wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(2)

                        text = await page.inner_text("body")
                        result_obj = self._extract_high_school_from_text(text, href, "Web Search Result")
                        if result_obj:
                            log_scrape("highschool_duckduckgo", team, href, "success", 1)
                            return result_obj
                    except:
                        continue

        except Exception as e:
            print(f"    DuckDuckGo error: {e}")
        finally:
            await page.close()

        return None

    def _extract_high_school_from_text(self, text: str, source_url: str,
                                        source_name: str) -> Optional[HighSchoolResult]:
        """Extract high school info from article text."""
        patterns = [
            # Pattern for "High School: [name]" format - capture until newline or next field
            r"High School[:\s]+([A-Za-z\s\.\-']+(?:High School|College Prep|Prep|Academy|HS))",
            r"High School[:\s]+([A-Za-z\s\.\-']+?)(?:\n|Last Club|College|Citizenship|$)",
            # Pattern for "attended [school]" format
            r"(?:attended|attends)\s+([A-Za-z\s\.\-']+(?:High School|College Prep|Prep|Academy))",
            # Pattern for standalone school names
            r"([A-Z][a-zA-Z\s\.\-']+(?:College Prep High School|High School|Prep School|Academy))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                hs_name = match.group(1).strip()
                # Clean up
                hs_name = re.sub(r"\s+", " ", hs_name)
                hs_name = re.sub(r"^\W+|\W+$", "", hs_name)

                # Validate
                if len(hs_name) < 4 or len(hs_name) > 80:
                    continue
                if hs_name.lower() in ["n/a", "none", "unknown"]:
                    continue
                # Skip if it's just generic words
                if hs_name.lower() in ["high school", "prep", "academy"]:
                    continue
                # Skip if it contains action words or team names (false positives from bio text)
                skip_words = ["joined", "signed", "played", "trained", "competed", "fire", "mls",
                              "youth", "u-15", "u-17", "u-19", "development", "road", "against",
                              "red bulls", "sounders", "galaxy", "united", "fc ", "sc "]
                if any(word in hs_name.lower() for word in skip_words):
                    continue

                # Must contain an educational institution term
                school_terms = ["high school", "prep", "preparatory", "college prep"]
                # "Academy" only counts if it's clearly a school (not soccer academy)
                if "academy" in hs_name.lower():
                    # Check if it's a soccer academy (skip) vs school academy (keep)
                    if any(x in hs_name.lower() for x in ["soccer", "football", "fire", "mls", "development"]):
                        continue
                    # Otherwise academy might be a school
                elif not any(term in hs_name.lower() for term in school_terms):
                    continue

                # Must start with a capital letter (proper noun)
                if not hs_name[0].isupper():
                    continue

                # Should be a reasonable length for a school name
                if len(hs_name.split()) < 2:
                    continue

                # Extract location if available
                city, state = None, None
                loc_match = re.search(
                    rf"{re.escape(hs_name)}[,\s]+(?:in\s+)?([A-Za-z\s]+),\s*([A-Z]{{2}})",
                    text, re.IGNORECASE
                )
                if loc_match:
                    city = loc_match.group(1).strip()
                    state = loc_match.group(2).upper()

                print(f"    Found ({source_name}): {hs_name}")

                return HighSchoolResult(
                    high_school=hs_name,
                    city=city,
                    state=state,
                    source_url=source_url,
                    source_name=source_name
                )

        return None

    def _extract_hs_from_ncsa_url(self, url: str) -> Optional[str]:
        """Extract high school name from NCSA URL pattern."""
        match = re.search(r"/([a-z\-]+(?:high-school|prep|academy)[^/]*)/[^/]+/?$", url, re.IGNORECASE)
        if match:
            hs_slug = match.group(1)
            hs_name = hs_slug.replace("-", " ").title()
            return hs_name
        return None

    def _extract_location_from_ncsa(self, url: str, text: str) -> tuple:
        """Extract city/state from NCSA URL or text."""
        url_match = re.search(
            r"/(?:mens|womens)-soccer-recruiting/([a-z\-]+)/([a-z\-]+)/",
            url, re.IGNORECASE
        )
        if url_match:
            state = url_match.group(1).replace("-", " ").title()
            city = url_match.group(2).replace("-", " ").title()

            state_abbrevs = {
                "Illinois": "IL", "California": "CA", "Texas": "TX", "Florida": "FL",
                "New York": "NY", "Ohio": "OH", "Georgia": "GA", "Michigan": "MI",
                "Pennsylvania": "PA", "New Jersey": "NJ", "Virginia": "VA",
                "North Carolina": "NC", "Washington": "WA", "Arizona": "AZ",
                "Massachusetts": "MA", "Colorado": "CO", "Indiana": "IN",
                "Tennessee": "TN", "Missouri": "MO", "Maryland": "MD",
                "Wisconsin": "WI", "Minnesota": "MN", "South Carolina": "SC",
                "Alabama": "AL", "Louisiana": "LA", "Kentucky": "KY",
                "Oregon": "OR", "Oklahoma": "OK", "Connecticut": "CT",
                "Iowa": "IA", "Mississippi": "MS", "Arkansas": "AR",
                "Utah": "UT", "Kansas": "KS", "Nevada": "NV",
                "New Mexico": "NM", "Nebraska": "NE", "West Virginia": "WV",
            }
            state = state_abbrevs.get(state, state[:2].upper() if len(state) >= 2 else state)
            return city, state

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

    async def process_all_players(self, team_filter: str = None, skip_existing: bool = True):
        """Process all players in database to find high school data."""
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

        # Only US-born players (check hometown fields)
        query += " AND (hometown_state LIKE '%USA%' OR hometown_city LIKE '%USA%' OR birthplace LIKE '%USA%')"
        query += " ORDER BY team, last_name"

        cursor.execute(query, params)
        players = cursor.fetchall()
        conn.close()

        if not players:
            print("No players to process.")
            return

        print(f"Processing {len(players)} players for high school data...")
        print("=" * 60)

        await self.start()

        from scrapers.config_loader import load_teams
        teams_config = load_teams()
        team_domains = {t["name"]: t["domain"] for t in teams_config["teams"]}

        found_count = 0

        try:
            for i, player in enumerate(players, 1):
                print(f"\n[{i}/{len(players)}] {player['first_name']} {player['last_name']} ({player['team']})")

                team_domain = team_domains.get(player["team"], "mlssoccer.com")

                result = await self.find_high_school(
                    player["first_name"],
                    player["last_name"],
                    player["team"],
                    team_domain
                )

                if result:
                    self.update_player_high_school(player["id"], result)
                    found_count += 1
                    print(f"    Saved: {result.high_school}")
                    print(f"    Source: {result.source_name}")
                    print(f"    URL: {result.source_url[:70]}...")

                await asyncio.sleep(REQUEST_DELAY)

        finally:
            await self.stop()

        print("\n" + "=" * 60)
        print(f"Complete! Found high school for {found_count}/{len(players)} players")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape high school data for MLS players")
    parser.add_argument("--team", help="Filter by team name")
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--player", help="Search for specific player (first last)")
    parser.add_argument("--domain", default="mlssoccer.com", help="Team domain for single player search")
    args = parser.parse_args()

    scraper = HighSchoolScraper()

    if args.player:
        await scraper.start()
        parts = args.player.split()
        first_name = parts[0]
        last_name = " ".join(parts[1:])

        result = await scraper.find_high_school(first_name, last_name, "", args.domain)

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
        await scraper.process_all_players(
            team_filter=args.team,
            skip_existing=not args.include_existing
        )


if __name__ == "__main__":
    asyncio.run(main())
