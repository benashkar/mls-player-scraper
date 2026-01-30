"""
Quick-start script to run the MLS scrapers.

Usage:
    # Initialize database and scrape one team (for testing)
    python run_scraper.py --test

    # Scrape all teams
    python run_scraper.py --all

    # Scrape specific team
    python run_scraper.py --team chicago-fire-fc

    # Find high school data for players
    python run_scraper.py --highschool
    python run_scraper.py --highschool --team "Chicago Fire"
    python run_scraper.py --highschool-player "Christopher Cupps"

    # View results
    python run_scraper.py --view
    python run_scraper.py --stats
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scrapers.db import init_database
from scrapers.roster_scraper import RosterScraper
from scrapers.highschool_scraper import HighSchoolScraper
from scrapers.highschool_wikipedia import WikipediaHighSchoolScraper
from scrapers.highschool_grokipedia import GrokipediaHighSchoolScraper
from scrapers.schedule_scraper import ScheduleScraper
from scrapers.transfermarkt_scraper import TransfermarktScraper
from scrapers.view_data import show_players, show_stats


async def test_single_team():
    """Test scraper on Chicago Fire (has good Homegrown data)."""
    init_database()
    scraper = RosterScraper()
    await scraper.scrape_single_team("chicago-fire-fc", with_bios=True)


async def scrape_all():
    """Scrape all 30 teams."""
    init_database()
    scraper = RosterScraper()
    await scraper.scrape_all_rosters(with_bios=True)


async def scrape_team(slug: str):
    """Scrape a specific team."""
    init_database()
    scraper = RosterScraper()
    await scraper.scrape_single_team(slug, with_bios=True)


async def scrape_highschool(team_filter: str = None):
    """Find high school data for players in database."""
    scraper = HighSchoolScraper()
    await scraper.process_all_players(team_filter=team_filter)


async def search_player_highschool(player_name: str):
    """Search for a single player's high school."""
    scraper = HighSchoolScraper()
    await scraper.start()

    parts = player_name.split()
    first_name = parts[0]
    last_name = " ".join(parts[1:])

    result = await scraper.find_high_school(first_name, last_name, "", "mlssoccer.com")

    if result:
        print(f"\nResult for {player_name}:")
        print(f"  High School: {result.high_school}")
        print(f"  City: {result.city or 'N/A'}")
        print(f"  State: {result.state or 'N/A'}")
        print(f"  Source URL: {result.source_url}")
        print(f"  Source: {result.source_name}")
    else:
        print(f"\nNo high school found for {player_name}.")

    await scraper.stop()


async def scrape_schedules(start_date: str = None, end_date: str = None):
    """Scrape full MLS schedule week-by-week."""
    scraper = ScheduleScraper()
    await scraper.scrape_full_schedule(start_date=start_date, end_date=end_date)


async def scrape_highschool_wikipedia(team_filter: str = None):
    """Find high school data via Wikipedia."""
    scraper = WikipediaHighSchoolScraper()
    await scraper.process_us_players(team_filter=team_filter)


async def scrape_highschool_grokipedia(team_filter: str = None):
    """Find high school data via Grokipedia."""
    scraper = GrokipediaHighSchoolScraper()
    await scraper.process_us_players(team_filter=team_filter)


async def scrape_transfermarkt(field: str = "birthdate", team_filter: str = None, limit: int = 100):
    """Fill missing player data from Transfermarkt."""
    scraper = TransfermarktScraper()
    await scraper.process_players_missing_data(field=field, team_filter=team_filter, limit=limit)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="MLS Data Scraper")
    parser.add_argument("--test", action="store_true", help="Test roster scraper with Chicago Fire")
    parser.add_argument("--all", action="store_true", help="Scrape all 30 team rosters")
    parser.add_argument("--team", help="Team filter (slug for roster, name for highschool)")
    parser.add_argument("--highschool", action="store_true", help="Find high school data (club sites)")
    parser.add_argument("--highschool-wiki", action="store_true", help="Find high school data (Wikipedia)")
    parser.add_argument("--highschool-grok", action="store_true", help="Find high school data (Grokipedia)")
    parser.add_argument("--highschool-player", help="Search high school for specific player")
    parser.add_argument("--schedules", action="store_true", help="Scrape match schedules")
    parser.add_argument("--transfermarkt", action="store_true", help="Fill missing data from Transfermarkt")
    parser.add_argument("--field", default="birthdate", help="Field to fill with --transfermarkt (birthdate, birthplace)")
    parser.add_argument("--limit", type=int, default=100, help="Max players to process")
    parser.add_argument("--sched-start", help="Schedule start date YYYY-MM-DD")
    parser.add_argument("--sched-end", help="Schedule end date YYYY-MM-DD")
    parser.add_argument("--view", action="store_true", help="View scraped players")
    parser.add_argument("--stats", action="store_true", help="View statistics")
    args = parser.parse_args()

    if args.test:
        print("Testing roster scraper with Chicago Fire FC...")
        print("This will initialize the DB and scrape one team.\n")
        asyncio.run(test_single_team())
    elif args.all:
        print("Scraping all 30 MLS team rosters...")
        asyncio.run(scrape_all())
    elif args.schedules:
        print("Scraping MLS schedule week-by-week...")
        asyncio.run(scrape_schedules(args.sched_start, args.sched_end))
    elif args.highschool_player:
        print(f"Searching for high school: {args.highschool_player}")
        asyncio.run(search_player_highschool(args.highschool_player))
    elif args.highschool_wiki:
        team = args.team if args.team else None
        print(f"Finding high school data via Wikipedia{' for ' + team if team else ''}...")
        asyncio.run(scrape_highschool_wikipedia(team))
    elif args.highschool_grok:
        team = args.team if args.team else None
        print(f"Finding high school data via Grokipedia{' for ' + team if team else ''}...")
        asyncio.run(scrape_highschool_grokipedia(team))
    elif args.transfermarkt:
        team = args.team if args.team else None
        print(f"Filling {args.field} data from Transfermarkt{' for ' + team if team else ''}...")
        asyncio.run(scrape_transfermarkt(args.field, team, args.limit))
    elif args.highschool:
        team = args.team if args.team else None
        print(f"Finding high school data for players{' in ' + team if team else ''}...")
        asyncio.run(scrape_highschool(team))
    elif args.team and not args.highschool:
        asyncio.run(scrape_team(args.team))
    elif args.view:
        show_players(limit=args.limit)
    elif args.stats:
        show_stats()
    else:
        parser.print_help()
        print("\n\nQuick start:")
        print("  1. Test roster:     python run_scraper.py --test")
        print("  2. View results:    python run_scraper.py --view")
        print("  3. Scrape schedules: python run_scraper.py --schedules")
        print("  4. Find high schools:")
        print("     - Via Wikipedia: python run_scraper.py --highschool-wiki")
        print("     - Via club sites: python run_scraper.py --highschool")
        print("  5. Full scrape:     python run_scraper.py --all")


if __name__ == "__main__":
    main()
