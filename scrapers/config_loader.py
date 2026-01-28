"""Load team configuration."""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def load_teams():
    """Load team configuration from JSON."""
    config_path = CONFIG_DIR / "teams.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_team_by_slug(slug: str):
    """Get a single team by its slug."""
    config = load_teams()
    for team in config["teams"]:
        if team["slug"] == slug:
            return team
    return None


def get_all_roster_urls():
    """Get all roster URLs."""
    config = load_teams()
    return [(t["name"], t["roster_url"]) for t in config["teams"]]


def get_all_schedule_urls():
    """Get all schedule URLs."""
    config = load_teams()
    return [(t["name"], t["schedule_url"]) for t in config["teams"]]


if __name__ == "__main__":
    config = load_teams()
    print(f"Loaded {len(config['teams'])} teams for {config['season']} season")
    print(f"Season starts: {config['season_dates']['start']}")
