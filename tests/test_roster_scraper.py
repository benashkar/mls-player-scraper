"""
Tests for the roster_scraper module.
====================================

This module tests the helper functions in the roster scraper.
We don't test the actual scraping (that would require network access),
but we test the data extraction and parsing logic.

Run these tests with:
    pytest tests/test_roster_scraper.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path so we can import scrapers module
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.roster_scraper import RosterScraper


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def scraper():
    """Create a RosterScraper instance for testing."""
    return RosterScraper()


@pytest.fixture
def sample_team():
    """Return a sample team dictionary."""
    return {
        "name": "Chicago Fire FC",
        "slug": "chicago-fire-fc",
        "domain": "chicagofirefc.com",
        "roster_url": "https://www.chicagofirefc.com/roster/"
    }


# =============================================================================
# Tests for _extract_player_from_url()
# =============================================================================

class TestExtractPlayerFromUrl:
    """
    Tests for the _extract_player_from_url method.

    This method parses player names from MLS.com player URLs.
    """

    def test_extracts_two_part_name(self, scraper, sample_team):
        """Should extract first and last name from URL."""
        url = "https://www.mlssoccer.com/players/christopher-cupps/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "Christopher"
        assert player["last_name"] == "Cupps"

    def test_extracts_three_part_name(self, scraper, sample_team):
        """Should handle three-part names (last name has space)."""
        url = "https://www.mlssoccer.com/players/john-van-dyke/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "John"
        assert player["last_name"] == "Van Dyke"

    def test_extracts_single_name(self, scraper, sample_team):
        """Should handle single-name players (mononyms)."""
        url = "https://www.mlssoccer.com/players/artur/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] is None
        assert player["last_name"] == "Artur"

    def test_sets_team_name(self, scraper, sample_team):
        """Should set the team name from the team dict."""
        url = "https://www.mlssoccer.com/players/john-doe/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["team"] == "Chicago Fire FC"

    def test_sets_bio_url(self, scraper, sample_team):
        """Should set the bio_url to the player URL."""
        url = "https://www.mlssoccer.com/players/john-doe/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["bio_url"] == url

    def test_sets_season(self, scraper, sample_team):
        """Should set the season from scraper config."""
        url = "https://www.mlssoccer.com/players/john-doe/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["season"] == scraper.season

    def test_handles_url_with_query_string(self, scraper, sample_team):
        """Should extract name ignoring query string."""
        url = "https://www.mlssoccer.com/players/john-doe/?ref=roster"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "John"
        assert player["last_name"] == "Doe"

    def test_handles_url_without_trailing_slash(self, scraper, sample_team):
        """Should work with URLs without trailing slash."""
        url = "https://www.mlssoccer.com/players/john-doe"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "John"
        assert player["last_name"] == "Doe"

    def test_titlecases_names(self, scraper, sample_team):
        """Should title-case the extracted names."""
        url = "https://www.mlssoccer.com/players/john-doe/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "John"  # Not "john"
        assert player["last_name"] == "Doe"    # Not "doe"

    def test_handles_hyphenated_names(self, scraper, sample_team):
        """Should handle properly hyphenated names."""
        # Note: Hyphens in URLs separate name parts, so double-hyphen
        # would be needed for an actual hyphenated name, which is rare
        url = "https://www.mlssoccer.com/players/jean-pierre-smith/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "Jean"
        assert player["last_name"] == "Pierre Smith"


# =============================================================================
# Tests for RosterScraper initialization
# =============================================================================

class TestRosterScraperInit:
    """Tests for RosterScraper initialization."""

    def test_loads_config(self, scraper):
        """Should load team configuration on init."""
        assert scraper.config is not None
        assert "teams" in scraper.config

    def test_sets_season(self, scraper):
        """Should set the season from config."""
        assert scraper.season is not None
        assert isinstance(scraper.season, int)

    def test_browser_initially_none(self, scraper):
        """Browser should be None before starting."""
        assert scraper.browser is None
        assert scraper.context is None
        assert scraper.playwright is None


# =============================================================================
# Tests for player data structure
# =============================================================================

class TestPlayerDataStructure:
    """Tests to verify the player data structure."""

    def test_player_has_required_fields(self, scraper, sample_team):
        """Extracted player should have all required fields."""
        url = "https://www.mlssoccer.com/players/john-doe/"
        player = scraper._extract_player_from_url(url, sample_team)

        required_fields = [
            "team", "season", "first_name", "last_name",
            "position", "jersey_number", "headshot_url", "bio_url"
        ]

        for field in required_fields:
            assert field in player, f"Missing field: {field}"

    def test_optional_fields_are_none(self, scraper, sample_team):
        """Optional fields should be None initially."""
        url = "https://www.mlssoccer.com/players/john-doe/"
        player = scraper._extract_player_from_url(url, sample_team)

        # These are populated later by scrape_player_bio
        assert player["position"] is None
        assert player["jersey_number"] is None
        assert player["headshot_url"] is None


# =============================================================================
# Parameterized URL Tests
# =============================================================================

@pytest.mark.parametrize("url,expected_first,expected_last", [
    ("https://www.mlssoccer.com/players/lionel-messi/", "Lionel", "Messi"),
    ("https://www.mlssoccer.com/players/cristiano-ronaldo/", "Cristiano", "Ronaldo"),
    ("https://www.mlssoccer.com/players/diego-chara/", "Diego", "Chara"),
    ("https://www.mlssoccer.com/players/jozy-altidore/", "Jozy", "Altidore"),
    ("https://www.mlssoccer.com/players/carlos-vela/", "Carlos", "Vela"),
    ("https://www.mlssoccer.com/players/john-smith-jr/", "John", "Smith Jr"),
    ("https://www.mlssoccer.com/players/jean-marc-bosman/", "Jean", "Marc Bosman"),
])
def test_url_parsing_parameterized(url, expected_first, expected_last):
    """Parameterized tests for URL parsing."""
    scraper = RosterScraper()
    team = {"name": "Test FC", "slug": "test-fc", "roster_url": "http://example.com"}
    player = scraper._extract_player_from_url(url, team)

    assert player["first_name"] == expected_first
    assert player["last_name"] == expected_last


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_url_path(self, scraper, sample_team):
        """Should handle URL with empty player name."""
        url = "https://www.mlssoccer.com/players//"
        player = scraper._extract_player_from_url(url, sample_team)

        # Should still return a player dict, even if name is empty
        assert player["team"] == sample_team["name"]

    def test_numeric_suffix_in_name(self, scraper, sample_team):
        """Should handle players with numeric suffixes (Jr, III, etc.)."""
        url = "https://www.mlssoccer.com/players/john-doe-iii/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "John"
        assert "Iii" in player["last_name"]  # Title case converts III to Iii

    def test_very_long_name(self, scraper, sample_team):
        """Should handle very long names."""
        url = "https://www.mlssoccer.com/players/jan-van-der-berg-de-groot/"
        player = scraper._extract_player_from_url(url, sample_team)

        assert player["first_name"] == "Jan"
        assert player["last_name"] == "Van Der Berg De Groot"


# =============================================================================
# Configuration Tests
# =============================================================================

class TestScraperConfiguration:
    """Tests for scraper configuration."""

    def test_config_has_30_teams(self, scraper):
        """Config should have 30 MLS teams."""
        assert len(scraper.config["teams"]) == 30

    def test_season_is_reasonable(self, scraper):
        """Season should be a reasonable year."""
        assert 2020 <= scraper.season <= 2030

    def test_config_has_season_dates(self, scraper):
        """Config should have season dates."""
        assert "season_dates" in scraper.config


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])
