# MLS Player Scraper - Developer Guide

Welcome! This guide will help you understand and maintain the MLS scraper project.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [How Web Scraping Works](#how-web-scraping-works)
5. [Common Tasks](#common-tasks)
6. [Troubleshooting](#troubleshooting)
7. [Adding New Features](#adding-new-features)
8. [Best Practices](#best-practices)

---

## Project Overview

This project scrapes MLS (Major League Soccer) data from various websites:

| Data | Source | Scraper File |
|------|--------|--------------|
| Player rosters | mlssoccer.com | `roster_scraper.py` |
| Match schedules | mlssoccer.com | `schedule_scraper.py` |
| Birthdates/birthplaces | transfermarkt.us | `transfermarkt_scraper.py` |
| High school info | Wikipedia, Grokipedia | `highschool_wikipedia.py`, `highschool_grokipedia.py` |

**Why multiple sources?** Each website has different data. MLS.com has rosters but limited biographical info. Transfermarkt has detailed player data. Wikipedia has high school information for some players.

---

## Quick Start

### First-Time Setup

```bash
# 1. Clone the repository
git clone https://github.com/benashkar/mls-player-scraper.git
cd mls-player-scraper

# 2. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers (one-time setup)
playwright install chromium

# 5. Copy the environment file
copy .env.example .env

# 6. Initialize the database
python run_scraper.py --test
```

### Running Scrapers

```bash
# Scrape all team rosters (takes ~1 hour)
python run_scraper.py --all

# Scrape one team (for testing)
python run_scraper.py --team chicago-fire-fc

# Scrape match schedules
python run_scraper.py --schedules

# Fill in birthdates from Transfermarkt
python run_scraper.py --transfermarkt --limit 50

# Find high school data from Wikipedia
python run_scraper.py --highschool-wiki

# View current data
python run_scraper.py --stats

# Export to all formats
python scripts/export_all_formats.py
```

---

## Project Structure

```
mls-player-scraper/
├── config/
│   ├── teams.json        # List of all 30 MLS teams with URLs
│   └── schema.sql        # Database table definitions
│
├── data/
│   └── mls_data.db       # SQLite database (created automatically)
│
├── output/               # Exported data files
│   ├── players.csv
│   ├── players.json
│   ├── schedules.csv
│   ├── schedules.json
│   ├── mls_data.sql      # MySQL export
│   └── *.xlsx            # Excel files
│
├── scrapers/             # Main scraping code
│   ├── __init__.py
│   ├── db.py             # Database operations
│   ├── config_loader.py  # Loads teams.json
│   ├── normalize.py      # Data cleaning utilities
│   ├── roster_scraper.py # Player roster scraping
│   ├── schedule_scraper.py
│   ├── transfermarkt_scraper.py
│   ├── highschool_wikipedia.py
│   ├── highschool_grokipedia.py
│   └── view_data.py      # Display utilities
│
├── scripts/              # Utility scripts
│   ├── export_to_xlsx.py
│   └── export_all_formats.py
│
├── run_scraper.py        # Main entry point
├── requirements.txt      # Python dependencies
├── .env.example          # Configuration template
└── README.md
```

---

## How Web Scraping Works

### The Basic Concept

Web scraping is like having a robot visit websites and copy information for you.

```
Your Code → Opens Browser → Visits Website → Finds Data → Saves to Database
```

### Why We Use Playwright

Modern websites load content using JavaScript. When you visit mlssoccer.com, the page loads, THEN JavaScript runs to show the player list. A simple HTTP request would miss this content.

**Playwright** controls a real browser (Chromium), so JavaScript runs and we see everything a human would see.

### The Scraping Process

```python
# 1. Start a browser
browser = await playwright.chromium.launch()

# 2. Open a new tab
page = await browser.new_page()

# 3. Go to a website
await page.goto("https://mlssoccer.com/clubs/atlanta-united/roster/")

# 4. Wait for content to load
await asyncio.sleep(3)

# 5. Find elements using CSS selectors
links = await page.query_selector_all("a[href*='/players/']")

# 6. Extract data
for link in links:
    href = await link.get_attribute("href")
    print(href)

# 7. Close browser
await browser.close()
```

### CSS Selectors Cheat Sheet

| Selector | Meaning | Example |
|----------|---------|---------|
| `a` | All link elements | `<a href="...">` |
| `.class-name` | Elements with class | `<div class="class-name">` |
| `#my-id` | Element with ID | `<div id="my-id">` |
| `a[href*='/players/']` | Links containing '/players/' | `<a href="/players/john-doe">` |
| `div.roster .player` | .player inside div.roster | Nested elements |

---

## Common Tasks

### Updating Player Data

```bash
# Re-scrape all rosters
python run_scraper.py --all

# Re-scrape one team
python run_scraper.py --team atlanta-united
```

### Adding Missing Birthdates

```bash
# Scrape from Transfermarkt (50 players at a time)
python run_scraper.py --transfermarkt --limit 50
```

### Exporting Data

```bash
# Export to all formats (CSV, JSON, MySQL)
python scripts/export_all_formats.py

# Export just Excel files
python scripts/export_to_xlsx.py
```

### Checking Data Quality

```python
# In Python or run as a script:
from scrapers.db import get_connection

conn = get_connection()
cursor = conn.cursor()

# Count players per team
cursor.execute("""
    SELECT team, COUNT(*) as cnt
    FROM players
    GROUP BY team
    ORDER BY cnt
""")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} players")

conn.close()
```

### Viewing the Database

You can use any SQLite viewer:
- **DB Browser for SQLite** (free, recommended)
- **VS Code SQLite extension**
- Command line: `sqlite3 data/mls_data.db`

```sql
-- Show all tables
.tables

-- View first 10 players
SELECT first_name, last_name, team FROM players LIMIT 10;

-- Count players with birthdates
SELECT COUNT(*) FROM players WHERE birthdate IS NOT NULL;
```

---

## Troubleshooting

### "No players found"

**Cause:** Website structure may have changed, or we're being blocked.

**Solutions:**
1. Set `HEADLESS=false` in `.env` to see what's happening
2. Check if the website is down
3. Increase wait time in the scraper
4. Check if CSS selectors need updating

### Timeout Errors

**Cause:** Website is slow or blocking us.

**Solutions:**
1. Increase timeout value in code
2. Add more `await asyncio.sleep()` calls
3. Check internet connection
4. Try again later

### "Browser executable not found"

**Cause:** Playwright browsers not installed.

**Solution:**
```bash
playwright install chromium
```

### Database Locked

**Cause:** Another process has the database open.

**Solutions:**
1. Close any DB Browser or other SQLite tools
2. Restart Python
3. Close any running scrapers

### Import Errors

**Cause:** Virtual environment not activated or dependencies missing.

**Solutions:**
```bash
# Activate virtual environment
venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Adding New Features

### Adding a New Data Source

1. **Create a new scraper file** in `scrapers/`:

```python
# scrapers/my_new_scraper.py
"""
My New Data Scraper
===================
Explain what this scraper does and where it gets data.
"""

import asyncio
from playwright.async_api import async_playwright
from scrapers.db import get_connection, log_scrape

class MyNewScraper:
    def __init__(self):
        self.browser = None

    async def start(self):
        """Start the browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()

    async def stop(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape(self):
        """Main scraping logic goes here."""
        page = await self.browser.new_page()

        try:
            await page.goto("https://example.com")
            # ... scraping logic ...
        finally:
            await page.close()
```

2. **Add to run_scraper.py**:

```python
from scrapers.my_new_scraper import MyNewScraper

# Add argument
parser.add_argument("--my-new", action="store_true", help="Run my new scraper")

# Add handler
if args.my_new:
    scraper = MyNewScraper()
    await scraper.scrape()
```

### Adding a New Database Field

1. **Update schema.sql** in `config/`:

```sql
ALTER TABLE players ADD COLUMN new_field VARCHAR(100);
```

2. **Run the schema update**:

```bash
python -c "from scrapers.db import init_database; init_database()"
```

3. **Update the relevant scraper** to populate the new field.

---

## Best Practices

### Be Respectful to Websites

```python
# Always add delays between requests
await asyncio.sleep(2)  # Wait 2 seconds

# Don't scrape too frequently
# Once per day is usually enough
```

### Handle Errors Gracefully

```python
try:
    await page.goto(url)
except Exception as e:
    print(f"Error loading page: {e}")
    # Log the error but don't crash
    log_scrape("source", team_slug, url, "error", 0, str(e))
```

### Always Close Resources

```python
# Use try/finally to ensure cleanup
try:
    await scraper.start()
    # ... do stuff ...
finally:
    await scraper.stop()  # Always runs, even if error
```

### Test Before Full Scrape

```bash
# Test with one team first
python run_scraper.py --team chicago-fire-fc

# Then run full scrape
python run_scraper.py --all
```

### Git Best Practices

```bash
# Before making changes
git pull

# Create a branch for your feature
git checkout -b feature/my-new-feature

# Commit often with clear messages
git add .
git commit -m "Add support for player jersey numbers"

# Push and create pull request
git push origin feature/my-new-feature
```

---

## Getting Help

1. **Check the code comments** - Every file has detailed explanations
2. **Check the scrape_log table** - Shows what worked and what failed
3. **Set HEADLESS=false** - Watch the browser to see what's happening
4. **Ask questions!** - Better to ask than to guess

## Contact

If you have questions about this codebase, reach out to the team lead.

---

*Last updated: January 2026*
