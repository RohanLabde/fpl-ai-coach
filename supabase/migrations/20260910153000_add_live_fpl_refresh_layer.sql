-- Store immutable live snapshots separately from the mutable current player table.
-- The Streamlit server is the only database client; no Data API policies are added.

CREATE TABLE IF NOT EXISTS public.fpl_refresh_runs (
    refresh_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    refresh_type text NOT NULL CHECK (
        refresh_type IN ('live_snapshot', 'post_gameweek')
    ),
    status text NOT NULL CHECK (
        status IN ('started', 'completed', 'failed', 'skipped')
    ),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    source text NOT NULL,
    current_gameweek integer,
    latest_finished_gameweek integer,
    player_snapshot_rows integer NOT NULL DEFAULT 0,
    fixture_rows integer NOT NULL DEFAULT 0,
    message text
);

CREATE INDEX IF NOT EXISTS fpl_refresh_runs_completed_at_idx
    ON public.fpl_refresh_runs (completed_at DESC);

CREATE TABLE IF NOT EXISTS public.fpl_live_player_snapshots (
    snapshot_at timestamptz NOT NULL,
    player_id integer NOT NULL,
    first_name text,
    second_name text,
    web_name text,
    team_id integer,
    team_name text,
    position text,
    price numeric,
    total_points integer,
    form numeric,
    selected_by_percent numeric,
    status text,
    chance_of_playing_next_round integer,
    news text,
    current_gameweek integer,
    PRIMARY KEY (snapshot_at, player_id)
);

CREATE INDEX IF NOT EXISTS fpl_live_player_snapshots_latest_idx
    ON public.fpl_live_player_snapshots (player_id, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS public.fpl_fixtures (
    fixture_id integer PRIMARY KEY,
    gameweek integer,
    kickoff_time timestamptz,
    started boolean,
    finished boolean,
    finished_provisional boolean,
    home_team_id integer,
    home_team_name text,
    away_team_id integer,
    away_team_name text,
    home_difficulty integer,
    away_difficulty integer,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fpl_fixtures_gameweek_idx
    ON public.fpl_fixtures (gameweek, kickoff_time);

ALTER TABLE public.fpl_refresh_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fpl_live_player_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fpl_fixtures ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.fpl_refresh_runs FROM anon, authenticated;
REVOKE ALL ON TABLE public.fpl_live_player_snapshots FROM anon, authenticated;
REVOKE ALL ON TABLE public.fpl_fixtures FROM anon, authenticated;
