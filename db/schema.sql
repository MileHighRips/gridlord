-- GridironIQ reference schema (PostgreSQL).
-- SQLAlchemy models are the source of truth (backend/app/models); this file is a
-- readable reference / bootstrap for DBAs. Run `python -m app.seed` to create
-- tables via SQLAlchemy in dev.

CREATE TABLE IF NOT EXISTS leagues (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    provider            VARCHAR(50)  NOT NULL DEFAULT 'manual',
    provider_league_id  VARCHAR(100),
    season              INTEGER      NOT NULL DEFAULT 2026,
    num_teams           INTEGER      NOT NULL DEFAULT 12,
    scoring_type        VARCHAR(20)  NOT NULL DEFAULT 'PPR',
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS league_settings (
    id                       SERIAL PRIMARY KEY,
    league_id                INTEGER REFERENCES leagues(id) ON DELETE CASCADE,
    bench_size               INTEGER DEFAULT 6,
    ir_slots                 INTEGER DEFAULT 2,
    waiver_type              VARCHAR(30) DEFAULT 'rolling',
    faab_budget              INTEGER DEFAULT 100,
    waiver_reset             VARCHAR(20) DEFAULT 'weekly',
    waiver_process_day       VARCHAR(20) DEFAULT 'Tuesday',
    waiver_clear_days        INTEGER DEFAULT 2,
    trade_review             VARCHAR(30) DEFAULT 'commissioner',
    trade_veto_votes         INTEGER DEFAULT 0,
    trade_reject_days        INTEGER DEFAULT 2,
    trade_deadline           VARCHAR(20),
    allow_draft_pick_trades  BOOLEAN DEFAULT FALSE,
    keeper_count             INTEGER DEFAULT 0,
    keeper_cost_rule         VARCHAR(50),
    playoff_teams            INTEGER DEFAULT 6,
    playoff_start_week       INTEGER DEFAULT 15,
    playoff_end_week         INTEGER DEFAULT 17,
    playoff_reseeding        BOOLEAN DEFAULT FALSE,
    fractional_points        BOOLEAN DEFAULT TRUE,
    negative_points          BOOLEAN DEFAULT TRUE,
    play_median              BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS roster_slots (
    id         SERIAL PRIMARY KEY,
    league_id  INTEGER REFERENCES leagues(id) ON DELETE CASCADE,
    position   VARCHAR(10) NOT NULL,
    count      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS scoring_rules (
    id          SERIAL PRIMARY KEY,
    league_id   INTEGER REFERENCES leagues(id) ON DELETE CASCADE,
    stat        VARCHAR(50) NOT NULL,
    points      DOUBLE PRECISION DEFAULT 0,
    min_value   DOUBLE PRECISION,        -- threshold for bonus rules
    applies_to  VARCHAR(20) DEFAULT 'OFF'
);

CREATE TABLE IF NOT EXISTS teams (
    id          SERIAL PRIMARY KEY,
    league_id   INTEGER REFERENCES leagues(id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    owner       VARCHAR(120),
    draft_slot  INTEGER,
    is_me       BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS players (
    id                 SERIAL PRIMARY KEY,
    sleeper_id         VARCHAR(30),
    espn_id            VARCHAR(30),
    yahoo_id           VARCHAR(30),
    name               VARCHAR(120) NOT NULL,
    position           VARCHAR(10)  NOT NULL,
    team               VARCHAR(10),
    bye_week           INTEGER,
    age                DOUBLE PRECISION,
    years_exp          INTEGER,
    injury_status      VARCHAR(30),
    play_probability   DOUBLE PRECISION,
    depth_chart_order  INTEGER,
    active             BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS ix_players_position ON players(position);
CREATE INDEX IF NOT EXISTS ix_players_name ON players(name);

CREATE TABLE IF NOT EXISTS projection_sources (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(80) UNIQUE NOT NULL,
    accuracy_weight  DOUBLE PRECISION DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS projections (
    id              SERIAL PRIMARY KEY,
    player_id       INTEGER REFERENCES players(id),
    source_id       INTEGER REFERENCES projection_sources(id),
    season          INTEGER DEFAULT 2026,
    week            INTEGER DEFAULT 0,       -- 0 = ROS/season
    mean_points     DOUBLE PRECISION DEFAULT 0,
    std_points      DOUBLE PRECISION DEFAULT 0,
    floor_points    DOUBLE PRECISION,
    ceiling_points  DOUBLE PRECISION,
    raw_stats_json  TEXT,
    is_ensemble     BOOLEAN DEFAULT FALSE,
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS adp_entries (
    id            SERIAL PRIMARY KEY,
    player_id     INTEGER REFERENCES players(id),
    source        VARCHAR(50) DEFAULT 'consensus',
    format        VARCHAR(20) DEFAULT 'PPR',
    adp           DOUBLE PRECISION NOT NULL,
    rostered_pct  DOUBLE PRECISION,
    updated_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id          SERIAL PRIMARY KEY,
    league_id   INTEGER REFERENCES leagues(id),
    type        VARCHAR(30) NOT NULL,
    week        INTEGER,
    team_id     INTEGER REFERENCES teams(id),
    player_id   INTEGER REFERENCES players(id),
    faab_bid    INTEGER,
    detail_json TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_items (
    id            SERIAL PRIMARY KEY,
    player_id     INTEGER REFERENCES players(id),
    source        VARCHAR(80) NOT NULL,
    headline      VARCHAR(400) NOT NULL,
    summary       TEXT,
    url           VARCHAR(500),
    tags          VARCHAR(200),
    sentiment     DOUBLE PRECISION,
    published_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS drafts (
    id          SERIAL PRIMARY KEY,
    league_id   INTEGER REFERENCES leagues(id),
    draft_type  VARCHAR(20) DEFAULT 'snake',
    rounds      INTEGER DEFAULT 16,
    my_slot     INTEGER DEFAULT 1,
    status      VARCHAR(20) DEFAULT 'pending',
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS draft_picks (
    id            SERIAL PRIMARY KEY,
    draft_id      INTEGER REFERENCES drafts(id) ON DELETE CASCADE,
    overall_pick  INTEGER NOT NULL,
    round         INTEGER NOT NULL,
    slot          INTEGER NOT NULL,
    player_id     INTEGER REFERENCES players(id),
    is_mine       BOOLEAN DEFAULT FALSE,
    keeper        BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    email            VARCHAR(200) UNIQUE NOT NULL,
    hashed_password  VARCHAR(200) NOT NULL,
    role             VARCHAR(30) DEFAULT 'manager',
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS provider_tokens (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES users(id),
    provider       VARCHAR(30) NOT NULL,
    access_token   VARCHAR(2000) NOT NULL,
    refresh_token  VARCHAR(2000),
    expires_at     TIMESTAMP,
    created_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id           SERIAL PRIMARY KEY,
    action       VARCHAR(80) NOT NULL,
    league_id    INTEGER REFERENCES leagues(id),
    sources      VARCHAR(500),
    detail_json  TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);
