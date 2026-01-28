# MLS Athletes Data Scraper

Scrapes Major League Soccer player data from all 30 MLS teams, including roster information, hometown data, and high school information for US-born players.

## Quick Start

### One-Click Scripts (Windows)

Double-click any of these batch files to run:

| Script | Description |
|--------|-------------|
| `run_rosters.bat` | Scrape all 30 team rosters |
| `run_highschool.bat` | Find high school data via Wikipedia |
| `run_schedules.bat` | Scrape match schedules |
| `run_view.bat` | View scraped players |
| `run_stats.bat` | Show database statistics |
| `run_export.bat` | Export data to CSV |

### Command Line Usage

```bash
# Initialize database and test with one team
python run_scraper.py --test

# Scrape all 30 team rosters
python run_scraper.py --all

# Scrape specific team
python run_scraper.py --team chicago-fire-fc

# Find high school data (Wikipedia - recommended)
python run_scraper.py --highschool-wiki

# Find high school data (club sites)
python run_scraper.py --highschool

# Search single player's high school
python run_scraper.py --highschool-player "Christopher Cupps"

# Scrape match schedules
python run_scraper.py --schedules

# View results
python run_scraper.py --view
python run_scraper.py --stats
```

## Installation

1. Install Python 3.10+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` and configure if needed

## Data Fields

### Players Table
- `team` - Team name
- `first_name`, `last_name` - Player name
- `position` - Playing position
- `hometown_city`, `hometown_state` - Hometown location
- `high_school` - High school name (if found)
- `high_school_source_url` - Citation URL for high school data
- `high_school_source_name` - Source name (e.g., "Wikipedia")
- `height`, `weight`, `birthdate` - Physical stats
- `headshot_url`, `bio_url` - Profile URLs

## Output

- **Database**: `data/mls_data.db` (SQLite)
- **CSV Export**: `output/players.csv`

## Data Sources

- **Rosters**: MLS.com official club pages
- **High Schools**: Wikipedia player articles
- **Schedules**: MLS.com schedule pages

## Project Structure

```
├── run_scraper.py          # Main CLI entry point
├── run_*.bat               # One-click Windows scripts
├── config/
│   ├── teams.json          # All 30 MLS teams configuration
│   └── schema.sql          # Database schema
├── scrapers/
│   ├── roster_scraper.py   # Roster scraping logic
│   ├── highschool_wikipedia.py  # Wikipedia high school finder
│   ├── highschool_scraper.py    # Club site high school finder
│   ├── schedule_scraper.py # Schedule scraping logic
│   ├── db.py               # Database utilities
│   ├── view_data.py        # Data viewing/export
│   └── normalize.py        # Data normalization
├── data/
│   └── mls_data.db         # SQLite database
└── output/
    └── players.csv         # Exported data
```

## License

MIT
