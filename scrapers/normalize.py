"""Utilities for normalizing data, especially high school names."""
import re


def normalize_high_school(name: str) -> str:
    """
    Normalize high school names for matching.

    Examples:
        "Walter Payton College Prep High School" -> "walter payton college prep"
        "Lincoln HS" -> "lincoln"
        "St. Mary's Catholic High School" -> "st marys catholic"
    """
    if not name:
        return None

    # Lowercase
    name = name.lower().strip()

    # Remove common suffixes
    suffixes = [
        r"\s+high\s+school$",
        r"\s+h\.?s\.?$",
        r"\s+secondary\s+school$",
        r"\s+prep\s+school$",
        r"\s+preparatory$",
        r"\s+academy$",
    ]
    for suffix in suffixes:
        name = re.sub(suffix, "", name, flags=re.IGNORECASE)

    # Normalize punctuation
    name = re.sub(r"['\.]", "", name)  # Remove apostrophes and periods
    name = re.sub(r"\s+", " ", name)   # Collapse multiple spaces

    return name.strip()


def parse_hometown(hometown: str) -> tuple:
    """
    Parse hometown into city and state.

    Examples:
        "Chicago, Illinois" -> ("Chicago", "IL")
        "Batavia, OH" -> ("Batavia", "OH")
    """
    if not hometown:
        return (None, None)

    # State abbreviations mapping
    state_abbrevs = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
        "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
        "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
        "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
        "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
        "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
        "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
        "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
        "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
        "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
        "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
        "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC"
    }

    parts = [p.strip() for p in hometown.split(",")]
    if len(parts) < 2:
        return (hometown.strip(), None)

    city = parts[0]
    state = parts[-1].strip()

    # Convert full state name to abbreviation
    state_lower = state.lower()
    if state_lower in state_abbrevs:
        state = state_abbrevs[state_lower]
    elif len(state) == 2:
        state = state.upper()

    return (city, state)


if __name__ == "__main__":
    # Test normalization
    test_schools = [
        "Walter Payton College Prep High School",
        "Lincoln HS",
        "St. Mary's Catholic High School",
        "De La Salle Academy",
    ]
    for school in test_schools:
        print(f"{school} -> {normalize_high_school(school)}")

    print()

    # Test hometown parsing
    test_hometowns = [
        "Chicago, Illinois",
        "Batavia, OH",
        "Los Angeles, California",
    ]
    for hometown in test_hometowns:
        print(f"{hometown} -> {parse_hometown(hometown)}")
