"""
Tests for the normalize module.
================================

This module tests the data normalization functions used to clean
and standardize data from various sources.

Run these tests with:
    pytest tests/test_normalize.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path so we can import scrapers module
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.normalize import normalize_high_school, parse_hometown


# =============================================================================
# Tests for normalize_high_school()
# =============================================================================

class TestNormalizeHighSchool:
    """
    Tests for the normalize_high_school function.

    This function removes common suffixes and standardizes high school names
    so we can match them across different data sources.
    """

    def test_removes_high_school_suffix(self):
        """Should remove 'High School' from the end of names."""
        result = normalize_high_school("Lincoln High School")
        assert result == "lincoln"

    def test_removes_hs_suffix(self):
        """Should remove 'HS' abbreviation from names."""
        result = normalize_high_school("Lincoln HS")
        assert result == "lincoln"

    def test_removes_secondary_school_suffix(self):
        """Should remove 'Secondary School' suffix."""
        result = normalize_high_school("Washington Secondary School")
        assert result == "washington"

    def test_removes_academy_suffix(self):
        """Should remove 'Academy' suffix."""
        result = normalize_high_school("De La Salle Academy")
        assert result == "de la salle"

    def test_removes_prep_school_suffix(self):
        """Should remove 'Prep School' suffix."""
        result = normalize_high_school("Phillips Exeter Prep School")
        assert result == "phillips exeter"

    def test_removes_preparatory_suffix(self):
        """Should remove 'Preparatory' suffix."""
        result = normalize_high_school("Walter Payton College Preparatory")
        assert result == "walter payton college"

    def test_removes_apostrophes(self):
        """Should remove apostrophes from names."""
        result = normalize_high_school("St. Mary's Catholic High School")
        assert result == "st marys catholic"

    def test_removes_periods(self):
        """Should remove periods from names."""
        result = normalize_high_school("St. Thomas H.S.")
        assert result == "st thomas"

    def test_handles_complex_name(self):
        """Should handle a complex school name with multiple elements."""
        result = normalize_high_school("Walter Payton College Prep High School")
        # Note: This removes both "High School" and normalizes
        assert result == "walter payton college prep"

    def test_collapses_multiple_spaces(self):
        """Should collapse multiple spaces into one."""
        result = normalize_high_school("Lincoln    High    School")
        assert result == "lincoln"

    def test_handles_empty_string(self):
        """Should return None for empty string."""
        result = normalize_high_school("")
        assert result is None

    def test_handles_none(self):
        """Should return None for None input."""
        result = normalize_high_school(None)
        assert result is None

    def test_strips_whitespace(self):
        """Should strip leading and trailing whitespace."""
        result = normalize_high_school("  Lincoln High School  ")
        assert result == "lincoln"

    def test_lowercase_output(self):
        """Should return lowercase output."""
        result = normalize_high_school("LINCOLN HIGH SCHOOL")
        assert result == "lincoln"


# =============================================================================
# Tests for parse_hometown()
# =============================================================================

class TestParseHometown:
    """
    Tests for the parse_hometown function.

    This function splits hometown strings like "Chicago, Illinois"
    into city and state components.
    """

    def test_city_and_full_state_name(self):
        """Should parse city and full state name."""
        city, state = parse_hometown("Chicago, Illinois")
        assert city == "Chicago"
        assert state == "IL"

    def test_city_and_state_abbreviation(self):
        """Should handle state abbreviations."""
        city, state = parse_hometown("Batavia, OH")
        assert city == "Batavia"
        assert state == "OH"

    def test_city_and_lowercase_state(self):
        """Should handle lowercase state names."""
        city, state = parse_hometown("Los Angeles, california")
        assert city == "Los Angeles"
        assert state == "CA"

    def test_city_with_spaces(self):
        """Should handle city names with spaces."""
        city, state = parse_hometown("New York City, New York")
        assert city == "New York City"
        assert state == "NY"

    def test_two_word_state(self):
        """Should handle two-word state names."""
        city, state = parse_hometown("Charlotte, North Carolina")
        assert city == "Charlotte"
        assert state == "NC"

    def test_district_of_columbia(self):
        """Should handle District of Columbia."""
        city, state = parse_hometown("Washington, District of Columbia")
        assert city == "Washington"
        assert state == "DC"

    def test_lowercase_state_abbreviation(self):
        """Should uppercase lowercase state abbreviations."""
        city, state = parse_hometown("Austin, tx")
        assert city == "Austin"
        assert state == "TX"

    def test_city_only(self):
        """Should handle city-only input (no comma)."""
        city, state = parse_hometown("Chicago")
        assert city == "Chicago"
        assert state is None

    def test_empty_string(self):
        """Should return (None, None) for empty string."""
        city, state = parse_hometown("")
        assert city is None
        assert state is None

    def test_none_input(self):
        """Should return (None, None) for None input."""
        city, state = parse_hometown(None)
        assert city is None
        assert state is None

    def test_extra_spaces(self):
        """Should handle extra spaces in input."""
        city, state = parse_hometown("  Chicago  ,  Illinois  ")
        assert city == "Chicago"
        assert state == "IL"

    def test_multiple_commas(self):
        """Should use last part as state when multiple commas."""
        city, state = parse_hometown("San Jose, Santa Clara County, California")
        assert city == "San Jose"
        assert state == "CA"

    def test_international_city(self):
        """Should handle international cities (state won't be abbreviated)."""
        city, state = parse_hometown("London, England")
        assert city == "London"
        assert state == "England"  # Not a US state, so not abbreviated

    def test_country_as_state(self):
        """Should handle country names in state position."""
        city, state = parse_hometown("Toronto, Canada")
        assert city == "Toronto"
        assert state == "Canada"


# =============================================================================
# Parameterized Tests
# =============================================================================

@pytest.mark.parametrize("input_school,expected", [
    ("Lincoln High School", "lincoln"),
    ("Lincoln HS", "lincoln"),
    ("Lincoln H.S.", "lincoln"),
    ("De La Salle Academy", "de la salle"),
    ("Phillips Exeter Prep School", "phillips exeter"),
    ("Walter Payton College Preparatory", "walter payton college"),
    ("St. Mary's Catholic High School", "st marys catholic"),
    (None, None),
    ("", None),
])
def test_normalize_high_school_parametrized(input_school, expected):
    """
    Parameterized tests for normalize_high_school.

    This runs the same test logic with multiple input/output pairs,
    making it easy to add new test cases.
    """
    result = normalize_high_school(input_school)
    assert result == expected


@pytest.mark.parametrize("input_hometown,expected_city,expected_state", [
    ("Chicago, Illinois", "Chicago", "IL"),
    ("Los Angeles, California", "Los Angeles", "CA"),
    ("Austin, TX", "Austin", "TX"),
    ("New York City, New York", "New York City", "NY"),
    ("Seattle, Washington", "Seattle", "WA"),
    ("Miami, Florida", "Miami", "FL"),
    ("Boston, Massachusetts", "Boston", "MA"),
    ("Chicago", "Chicago", None),
    (None, None, None),
    ("", None, None),
])
def test_parse_hometown_parametrized(input_hometown, expected_city, expected_state):
    """
    Parameterized tests for parse_hometown.
    """
    city, state = parse_hometown(input_hometown)
    assert city == expected_city
    assert state == expected_state


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for unusual or edge case inputs."""

    def test_high_school_only_suffix(self):
        """Should handle input that is only a suffix."""
        result = normalize_high_school("High School")
        # The function returns the normalized input even if it's just a suffix
        # This is acceptable behavior - edge case where school name equals suffix
        assert result == "high school"

    def test_unicode_characters(self):
        """Should handle unicode characters in names."""
        city, state = parse_hometown("São Paulo, Brazil")
        assert city == "São Paulo"
        assert state == "Brazil"

    def test_very_long_school_name(self):
        """Should handle very long school names."""
        long_name = "The Very Long Name Of A School That Has Many Words High School"
        result = normalize_high_school(long_name)
        assert result == "the very long name of a school that has many words"

    def test_numbers_in_school_name(self):
        """Should preserve numbers in school names."""
        result = normalize_high_school("PS 101 High School")
        assert result == "ps 101"


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])
