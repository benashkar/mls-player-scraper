-- MLS Data Schema

-- Players table
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    season INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    hometown_city TEXT,
    hometown_state TEXT,
    high_school TEXT,
    high_school_city TEXT,
    high_school_state TEXT,
    high_school_source_url TEXT,
    high_school_source_name TEXT,
    position TEXT,
    jersey_number INTEGER,
    height TEXT,
    weight INTEGER,
    birthdate TEXT,
    birthplace TEXT,
    citizenship TEXT,
    headshot_url TEXT,
    bio_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team, season, first_name, last_name)
);

-- Schedules table
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT UNIQUE,
    season INTEGER NOT NULL,
    match_date DATE NOT NULL,
    match_time TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    venue TEXT,
    competition TEXT,
    broadcast TEXT,
    status TEXT,
    home_score INTEGER,
    away_score INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- High schools lookup table (for matching with Limpar org database)
CREATE TABLE IF NOT EXISTS high_schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    city TEXT,
    state TEXT,
    limpar_match_id TEXT,
    match_status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(raw_name)
);

-- Scrape log for tracking
CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    team_slug TEXT,
    url TEXT,
    status TEXT,
    records_found INTEGER,
    error_message TEXT,
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team);
CREATE INDEX IF NOT EXISTS idx_players_hometown ON players(hometown_city, hometown_state);
CREATE INDEX IF NOT EXISTS idx_players_high_school ON players(high_school);
CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(match_date);
CREATE INDEX IF NOT EXISTS idx_schedules_teams ON schedules(home_team, away_team);
