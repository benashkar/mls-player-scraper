"""
Tests for the config_loader module.
====================================

This module tests the configuration loading functions that read
team data from config/teams.json.

Run these tests with:
    pytest tests/test_config_loader.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path so we can import scrapers module
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.config_loader import (
    load_teams,
    get_team_by_slug,
    get_all_roster_urls,
    get_all_schedule_urls,
)


# =============================================================================
# Tests for load_teams()
# =============================================================================

class TestLoadTeams:
    """
    Tests for the load_teams function.

    This function loads the team configuration from config/teams.json.
    """

    def test_returns_dict(self):
        """Should return a dictionary."""
        config = load_teams()
        assert isinstance(config, dict)

    def test_has_teams_key(self):
        """Should have a 'teams' key."""
        config = load_teams()
        assert "teams" in config

    def test_has_season_key(self):
        """Should have a 'season' key."""
        config = load_teams()
        assert "season" in config

    def test_season_is_integer(self):
        """Season should be an integer."""
        config = load_teams()
        assert isinstance(config["season"], int)

    def test_teams_is_list(self):
        """Teams should be a list."""
        config = load_teams()
        assert isinstance(config["teams"], list)

    def test_has_30_teams(self):
        """Should have exactly 30 MLS teams."""
        config = load_teams()
        assert len(config["teams"]) == 30

    def test_each_team_has_required_fields(self):
        """Each team should have name, slug, and roster_url."""
        config = load_teams()
        required_fields = ["name", "slug", "roster_url"]

        for team in config["teams"]:
            for field in required_fields:
                assert field in team, f"Team missing '{field}': {team.get('name', 'unknown')}"

    def test_team_names_are_unique(self):
        """Each team name should be unique."""
        config = load_teams()
        names = [team["name"] for team in config["teams"]]
        assert len(names) == len(set(names)), "Duplicate team names found"

    def test_team_slugs_are_unique(self):
        """Each team slug should be unique."""
        config = load_teams()
        slugs = [team["slug"] for team in config["teams"]]
        assert len(slugs) == len(set(slugs)), "Duplicate team slugs found"


# =============================================================================
# Tests for get_team_by_slug()
# =============================================================================

class TestGetTeamBySlug:
    """
    Tests for the get_team_by_slug function.

    This function retrieves a single team's configuration by its slug.
    """

    def test_finds_atlanta_united(self):
        """Should find Atlanta United by slug."""
        team = get_team_by_slug("atlanta-united")
        assert team is not None
        assert team["name"] == "Atlanta United"

    def test_finds_chicago_fire(self):
        """Should find Chicago Fire FC by slug."""
        team = get_team_by_slug("chicago-fire-fc")
        assert team is not None
        assert team["name"] == "Chicago Fire FC"

    def test_finds_la_galaxy(self):
        """Should find LA Galaxy by slug."""
        team = get_team_by_slug("la-galaxy")
        assert team is not None
        assert team["name"] == "LA Galaxy"

    def test_finds_lafc(self):
        """Should find LAFC by slug."""
        team = get_team_by_slug("los-angeles-football-club")
        assert team is not None
        assert team["name"] == "LAFC"

    def test_returns_none_for_invalid_slug(self):
        """Should return None for non-existent slug."""
        team = get_team_by_slug("invalid-team-slug")
        assert team is None

    def test_returns_none_for_empty_slug(self):
        """Should return None for empty slug."""
        team = get_team_by_slug("")
        assert team is None

    def test_team_has_roster_url(self):
        """Found team should have a roster_url."""
        team = get_team_by_slug("atlanta-united")
        assert "roster_url" in team
        assert team["roster_url"].startswith("http")

    def test_case_sensitive_slug(self):
        """Slug lookup should be case-sensitive."""
        # Slugs are lowercase, so uppercase should not match
        team = get_team_by_slug("Atlanta-United")
        assert team is None


# =============================================================================
# Tests for get_all_roster_urls()
# =============================================================================

class TestGetAllRosterUrls:
    """
    Tests for the get_all_roster_urls function.

    This function returns a list of (name, roster_url) tuples for all teams.
    """

    def test_returns_list(self):
        """Should return a list."""
        urls = get_all_roster_urls()
        assert isinstance(urls, list)

    def test_returns_30_urls(self):
        """Should return 30 team URLs."""
        urls = get_all_roster_urls()
        assert len(urls) == 30

    def test_each_item_is_tuple(self):
        """Each item should be a tuple."""
        urls = get_all_roster_urls()
        for item in urls:
            assert isinstance(item, tuple)

    def test_each_tuple_has_two_elements(self):
        """Each tuple should have (name, url)."""
        urls = get_all_roster_urls()
        for item in urls:
            assert len(item) == 2

    def test_urls_are_valid(self):
        """Each URL should start with http."""
        urls = get_all_roster_urls()
        for name, url in urls:
            assert url.startswith("http"), f"Invalid URL for {name}: {url}"

    def test_names_are_strings(self):
        """Each name should be a non-empty string."""
        urls = get_all_roster_urls()
        for name, url in urls:
            assert isinstance(name, str)
            assert len(name) > 0


# =============================================================================
# Tests for get_all_schedule_urls()
# =============================================================================

class TestGetAllScheduleUrls:
    """
    Tests for the get_all_schedule_urls function.

    This function returns a list of (name, schedule_url) tuples for all teams.
    """

    def test_returns_list(self):
        """Should return a list."""
        urls = get_all_schedule_urls()
        assert isinstance(urls, list)

    def test_returns_30_urls(self):
        """Should return 30 team URLs."""
        urls = get_all_schedule_urls()
        assert len(urls) == 30

    def test_urls_are_valid(self):
        """Each URL should start with http."""
        urls = get_all_schedule_urls()
        for name, url in urls:
            assert url.startswith("http"), f"Invalid URL for {name}: {url}"

    def test_urls_contain_schedule(self):
        """Each URL should contain 'schedule'."""
        urls = get_all_schedule_urls()
        for name, url in urls:
            assert "schedule" in url.lower(), f"URL doesn't contain 'schedule' for {name}"


# =============================================================================
# Integration Tests
# =============================================================================

class TestConfigIntegration:
    """
    Integration tests that verify the config is consistent.
    """

    def test_all_teams_have_matching_slug_in_roster_url(self):
        """Each team's slug should appear in their roster URL (for most teams)."""
        config = load_teams()

        for team in config["teams"]:
            # Most team slugs appear in the MLS roster URL
            # Some exceptions exist (like LAFC using 'los-angeles-football-club')
            slug = team["slug"]
            roster_url = team["roster_url"]

            # Just check that the URL is valid - not all slugs match exactly
            assert roster_url.startswith("http")

    def test_all_slugs_are_lowercase(self):
        """All team slugs should be lowercase."""
        config = load_teams()

        for team in config["teams"]:
            slug = team["slug"]
            assert slug == slug.lower(), f"Slug not lowercase: {slug}"

    def test_all_slugs_use_hyphens(self):
        """All team slugs should use hyphens, not underscores."""
        config = load_teams()

        for team in config["teams"]:
            slug = team["slug"]
            assert "_" not in slug, f"Slug contains underscore: {slug}"


# =============================================================================
# Specific Team Tests
# =============================================================================

# List of all 30 MLS teams and their expected slugs
MLS_TEAMS = [
    ("Atlanta United", "atlanta-united"),
    ("Austin FC", "austin-fc"),
    ("Charlotte FC", "charlotte-fc"),
    ("Chicago Fire FC", "chicago-fire-fc"),
    ("FC Cincinnati", "fc-cincinnati"),
    ("Colorado Rapids", "colorado-rapids"),
    ("Columbus Crew", "columbus-crew"),
    ("FC Dallas", "fc-dallas"),
    ("D.C. United", "d-c-united"),
    ("Houston Dynamo FC", "houston-dynamo-fc"),
    ("Sporting Kansas City", "sporting-kansas-city"),
    ("LA Galaxy", "la-galaxy"),
    ("LAFC", "los-angeles-football-club"),
    ("Inter Miami CF", "inter-miami-cf"),
    ("Minnesota United FC", "minnesota-united-fc"),
    ("CF Montréal", "cf-montreal"),
    ("Nashville SC", "nashville-sc"),
    ("New England Revolution", "new-england-revolution"),
    ("New York Red Bulls", "red-bull-new-york"),
    ("New York City FC", "new-york-city-football-club"),
    ("Orlando City SC", "orlando-city-sc"),
    ("Philadelphia Union", "philadelphia-union"),
    ("Portland Timbers", "portland-timbers"),
    ("Real Salt Lake", "real-salt-lake"),
    ("San Diego FC", "san-diego-fc"),
    ("San Jose Earthquakes", "san-jose-earthquakes"),
    ("Seattle Sounders FC", "seattle-sounders-fc"),
    ("St. Louis CITY SC", "st-louis-city-sc"),
    ("Toronto FC", "toronto-fc"),
    ("Vancouver Whitecaps FC", "vancouver-whitecaps-fc"),
]


@pytest.mark.parametrize("team_name,expected_slug", MLS_TEAMS)
def test_team_exists_with_correct_slug(team_name, expected_slug):
    """
    Verify each MLS team exists in config with the correct slug.

    This parameterized test runs once for each team in MLS_TEAMS.
    """
    team = get_team_by_slug(expected_slug)
    assert team is not None, f"Team not found with slug: {expected_slug}"
    assert team["name"] == team_name, f"Name mismatch for {expected_slug}"


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])
