# MLS Data Sources Guide for Local News Automation

## Overview
This guide documents the best data sources for scraping MLS rosters (with hometown/high school data) and schedules for your local news automation project.

**2026 Season Key Dates:**
- Season Start: February 21, 2026
- World Cup Break: May 25 - July 16, 2026
- Decision Day: November 7, 2026
- Games per team: 34 (17 home, 17 away)

---

## 1. ROSTERS

### Primary Source: Individual Club Websites (RECOMMENDED)

**Why Club Sites Are Best for Your Use Case:**
- They contain the most complete **hometown** and **high school** data
- Player signing announcements include all biographical details
- Homegrown player signings especially have detailed local info

**URL Pattern:**
```
https://www.[clubdomain].com/roster/
```

**All 30 MLS Club Roster URLs:**

| Team | Roster URL | Official Site |
|------|------------|---------------|
| Atlanta United | https://www.atlutd.com/roster/ | atlutd.com |
| Austin FC | https://www.austinfc.com/roster/ | austinfc.com |
| Charlotte FC | https://www.charlottefootballclub.com/roster/ | charlottefootballclub.com |
| Chicago Fire FC | https://www.chicagofirefc.com/roster/ | chicagofirefc.com |
| FC Cincinnati | https://www.fccincinnati.com/roster/ | fccincinnati.com |
| Colorado Rapids | https://www.coloradorapids.com/roster/ | coloradorapids.com |
| Columbus Crew | https://www.columbuscrew.com/roster/ | columbuscrew.com |
| FC Dallas | https://www.fcdallas.com/roster/ | fcdallas.com |
| D.C. United | https://www.dcunited.com/roster/ | dcunited.com |
| Houston Dynamo FC | https://www.houstondynamofc.com/roster/ | houstondynamofc.com |
| Sporting Kansas City | https://www.sportingkc.com/roster/ | sportingkc.com |
| LA Galaxy | https://www.lagalaxy.com/roster/ | lagalaxy.com |
| LAFC | https://www.lafc.com/roster/ | lafc.com |
| Inter Miami CF | https://www.intermiamicf.com/roster/ | intermiamicf.com |
| Minnesota United FC | https://www.mnufc.com/roster/ | mnufc.com |
| CF Montréal | https://www.cfmontreal.com/roster/ | cfmontreal.com |
| Nashville SC | https://www.nashvillesc.com/roster/ | nashvillesc.com |
| New England Revolution | https://www.revolutionsoccer.net/roster/ | revolutionsoccer.net |
| New York Red Bulls | https://www.newyorkredbulls.com/roster/ | newyorkredbulls.com |
| New York City FC | https://www.newyorkcityfc.com/roster/ | newyorkcityfc.com |
| Orlando City SC | https://www.orlandocitysc.com/roster/ | orlandocitysc.com |
| Philadelphia Union | https://www.philadelphiaunion.com/roster/ | philadelphiaunion.com |
| Portland Timbers | https://www.timbers.com/roster/ | timbers.com |
| Real Salt Lake | https://www.rsl.com/roster/ | rsl.com |
| San Diego FC | https://www.sandiegofc.com/roster/ | sandiegofc.com |
| San Jose Earthquakes | https://www.sjearthquakes.com/roster/ | sjearthquakes.com |
| Seattle Sounders FC | https://www.soundersfc.com/roster/ | soundersfc.com |
| St. Louis CITY SC | https://www.stlcitysc.com/roster/ | stlcitysc.com |
| Toronto FC | https://www.torontofc.ca/roster/ | torontofc.ca |
| Vancouver Whitecaps FC | https://www.whitecapsfc.com/roster/ | whitecapsfc.com |

### Data Fields Available on Club Sites

**From Player Bio Pages (example from Chicago Fire signing announcements):**
```
Name: Christopher Cupps
Position: Defender
Height: 6'1"
Weight: 175 lbs.
Date of Birth: May 26, 2008
Birthplace: Chicago, Illinois
Hometown: Chicago, Illinois
Citizenship: United States of America
High School: Walter Payton College Prep High School
Last club: Chicago Fire Academy
```

**Your Required Fields Mapping:**

| Your Field | Available? | Source Location |
|------------|------------|-----------------|
| Team | ✅ Yes | Page context / URL |
| Season | ✅ Yes | Page context (current roster = current season) |
| First Name | ✅ Yes | Player name field |
| Last Name | ✅ Yes | Player name field |
| Hometown City | ✅ Yes | "Hometown" field in bio |
| High School | ⚠️ Partial | Bio section (mainly for US-born/Homegrown players) |
| Position | ✅ Yes | Position field |
| Number | ✅ Yes | Jersey number field |
| Height | ✅ Yes | Height field |
| Weight | ✅ Yes | Weight field |
| Headshot URL | ✅ Yes | Player image on roster/bio page |

### Secondary Source: MLSsoccer.com Player Pages

**URL Patterns:**
- All Players: `https://www.mlssoccer.com/players/`
- Individual Player: `https://www.mlssoccer.com/players/[player-slug]/`
- Team Roster: `https://www.mlssoccer.com/clubs/[team-slug]/roster/`

**Example Player Profile Data:**
```
Name: Matt Walker
Position: Midfielder
Height: 5'6"
Weight: 150
Born: September 16, 1992 in Cincinnati, Ohio
Hometown: Batavia, OH
Citizenship: United States
```

**Headshot Image CDN:**
```
https://images.mlssoccer.com/image/private/t_thumb_squared/f_auto/prd-league/[image-id].jpg
```

### Strategy for Getting High School Data

**High school data is MOST reliably found in:**
1. **Player signing announcement news articles** on club sites
2. **Homegrown player** bios (these almost always include high school)
3. **MLS SuperDraft** announcement articles

**Search pattern for scraping news articles:**
```
https://www.[clubsite].com/news/[team]-signs-[player-name]
```

**Important Note:** International players will NOT have US high school data. You'll need to handle these as NULL/empty values in your database.

---

## 2. SCHEDULES

### Primary Source: MLSsoccer.com

**Main Schedule URL:**
```
https://www.mlssoccer.com/schedule/scores
```

**By Competition:**
```
https://www.mlssoccer.com/competitions/mls-regular-season/2026/schedule/
```

**By Team:**
```
https://www.mlssoccer.com/clubs/[team-slug]/schedule/
```

**Team Slugs for Schedule URLs:**

| Team | Slug |
|------|------|
| Atlanta United | atlanta-united |
| Austin FC | austin-fc |
| Charlotte FC | charlotte-fc |
| Chicago Fire FC | chicago-fire-fc |
| FC Cincinnati | fc-cincinnati |
| Colorado Rapids | colorado-rapids |
| Columbus Crew | columbus-crew |
| FC Dallas | fc-dallas |
| D.C. United | d-c-united |
| Houston Dynamo FC | houston-dynamo-fc |
| Sporting Kansas City | sporting-kansas-city |
| LA Galaxy | la-galaxy |
| LAFC | los-angeles-football-club |
| Inter Miami CF | inter-miami-cf |
| Minnesota United FC | minnesota-united-fc |
| CF Montréal | cf-montreal |
| Nashville SC | nashville-sc |
| New England Revolution | new-england-revolution |
| New York Red Bulls | new-york-red-bulls |
| New York City FC | new-york-city-football-club |
| Orlando City SC | orlando-city-sc |
| Philadelphia Union | philadelphia-union |
| Portland Timbers | portland-timbers |
| Real Salt Lake | real-salt-lake |
| San Diego FC | san-diego-fc |
| San Jose Earthquakes | san-jose-earthquakes |
| Seattle Sounders FC | seattle-sounders-fc |
| St. Louis CITY SC | st-louis-city-sc |
| Toronto FC | toronto-fc |
| Vancouver Whitecaps FC | vancouver-whitecaps-fc |

### Schedule Data Fields

Typical schedule data includes:
- Match date and time
- Home team
- Away team
- Venue/Stadium
- Competition (Regular Season, Playoffs, etc.)
- Broadcast info
- Match status (scheduled, final, etc.)
- Score (when available)

### Alternative Schedule Sources

**Club Sites:**
Each club has their own schedule page with similar data:
```
https://www.[clubsite].com/schedule/
```

---

## 3. SCRAPING RECOMMENDATIONS FOR CLAUDE CODE

### Technical Notes

1. **Both sites use JavaScript rendering** - The roster pages load player data dynamically. You'll likely need to:
   - Use a headless browser (Puppeteer, Playwright) OR
   - Find the underlying JSON API endpoints the pages use

2. **API Discovery:** Open browser DevTools > Network tab while loading roster pages to find JSON endpoints. Common patterns:
   - `https://stats-api.mlssoccer.com/...`
   - `https://api.mlssoccer.com/...`

3. **Rate Limiting:** Be respectful - add delays between requests (1-2 seconds minimum)

4. **Caching:** Cache roster data and only update weekly during season, daily during transfer windows

### Suggested Scraping Order

**Phase 1: Rosters**
1. Scrape all 30 club roster pages for player lists
2. For each player, scrape their individual bio page
3. Supplement with news article scraping for high school data (especially for Homegrown players)

**Phase 2: Schedules**
1. Scrape the main MLS schedule page for full season
2. Store match IDs for later box score retrieval

### Data Validation

For matching high schools to your Limpar org database:
- Normalize high school names (remove "High School", "HS", etc.)
- Handle variations (e.g., "Walter Payton College Prep" vs "Walter Payton College Prep High School")
- Flag unmatched schools for manual review

---

## 4. FIELD COVERAGE REALITY CHECK

Based on my research, here's what you can realistically expect:

| Field | Coverage | Notes |
|-------|----------|-------|
| Team | 100% | Always available |
| Season | 100% | Derived from page context |
| First Name | 100% | Always available |
| Last Name | 100% | Always available |
| Hometown City | ~70-80% | Good for US players, less for international |
| High School | ~30-40% | Mainly Homegrown/US players in signing news |
| Position | 100% | Always available |
| Number | 100% | Always available |
| Height | 100% | Always available |
| Weight | ~95% | Occasionally missing |
| Headshot URL | 100% | Always available via CDN |

**Important:** High school data will require the most effort. Focus on:
- Homegrown players (best coverage)
- US-born players
- News article mining for signing announcements
