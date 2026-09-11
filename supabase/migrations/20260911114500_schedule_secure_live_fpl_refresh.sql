-- Run the live FPL refresh within the database so no HTTP credential is stored
-- in a public application or supplied to a scheduled external request.

CREATE EXTENSION IF NOT EXISTS http WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;

CREATE OR REPLACE FUNCTION private.refresh_live_fpl_data()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, extensions
AS $$
DECLARE
    bootstrap_status integer;
    fixtures_status integer;
    bootstrap jsonb;
    fixtures jsonb;
    snapshot_at timestamptz := now();
    current_gameweek integer;
    latest_finished_gameweek integer;
    player_row_count integer;
    fixture_row_count integer;
BEGIN
    SELECT status, content::jsonb
      INTO bootstrap_status, bootstrap
      FROM extensions.http_get(
          'https://fantasy.premierleague.com/api/bootstrap-static/'
      );

    SELECT status, content::jsonb
      INTO fixtures_status, fixtures
      FROM extensions.http_get(
          'https://fantasy.premierleague.com/api/fixtures/'
      );

    IF bootstrap_status <> 200 OR fixtures_status <> 200 THEN
        RAISE EXCEPTION
            'FPL source request failed (bootstrap %, fixtures %)',
            bootstrap_status,
            fixtures_status;
    END IF;

    SELECT COALESCE(
        MAX((event->>'id')::integer)
        FILTER (WHERE COALESCE((event->>'finished')::boolean, false)),
        NULL
    )
      INTO latest_finished_gameweek
      FROM jsonb_array_elements(bootstrap->'events') AS event;

    SELECT (event->>'id')::integer
      INTO current_gameweek
      FROM jsonb_array_elements(bootstrap->'events') AS event
     WHERE COALESCE((event->>'is_current')::boolean, false)
        OR COALESCE((event->>'is_next')::boolean, false)
     ORDER BY CASE WHEN COALESCE((event->>'is_current')::boolean, false)
                   THEN 0 ELSE 1 END
     LIMIT 1;

    INSERT INTO public.players (
        player_id, first_name, second_name, team_id, team_name, position,
        price, total_points, form, selected_by_percent
    )
    SELECT
        player.id,
        player.first_name,
        player.second_name,
        player.team,
        team.name,
        position.singular_name_short,
        player.now_cost / 10.0,
        player.total_points,
        player.form,
        player.selected_by_percent
    FROM jsonb_to_recordset(bootstrap->'elements') AS player(
        id integer,
        first_name text,
        second_name text,
        team integer,
        element_type integer,
        now_cost numeric,
        total_points integer,
        form numeric,
        selected_by_percent numeric
    )
    LEFT JOIN jsonb_to_recordset(bootstrap->'teams') AS team(
        id integer,
        name text
    ) ON team.id = player.team
    LEFT JOIN jsonb_to_recordset(bootstrap->'element_types') AS position(
        id integer,
        singular_name_short text
    ) ON position.id = player.element_type
    ON CONFLICT (player_id) DO UPDATE SET
        first_name = EXCLUDED.first_name,
        second_name = EXCLUDED.second_name,
        team_id = EXCLUDED.team_id,
        team_name = EXCLUDED.team_name,
        position = EXCLUDED.position,
        price = EXCLUDED.price,
        total_points = EXCLUDED.total_points,
        form = EXCLUDED.form,
        selected_by_percent = EXCLUDED.selected_by_percent;

    INSERT INTO public.fpl_live_player_snapshots (
        snapshot_at, player_id, first_name, second_name, web_name, team_id,
        team_name, position, price, total_points, form, selected_by_percent,
        status, chance_of_playing_next_round, news, current_gameweek
    )
    SELECT
        snapshot_at,
        player.id,
        player.first_name,
        player.second_name,
        player.web_name,
        player.team,
        team.name,
        position.singular_name_short,
        player.now_cost / 10.0,
        player.total_points,
        player.form,
        player.selected_by_percent,
        player.status,
        player.chance_of_playing_next_round,
        player.news,
        current_gameweek
    FROM jsonb_to_recordset(bootstrap->'elements') AS player(
        id integer,
        first_name text,
        second_name text,
        web_name text,
        team integer,
        element_type integer,
        now_cost numeric,
        total_points integer,
        form numeric,
        selected_by_percent numeric,
        status text,
        chance_of_playing_next_round integer,
        news text
    )
    LEFT JOIN jsonb_to_recordset(bootstrap->'teams') AS team(
        id integer,
        name text
    ) ON team.id = player.team
    LEFT JOIN jsonb_to_recordset(bootstrap->'element_types') AS position(
        id integer,
        singular_name_short text
    ) ON position.id = player.element_type;

    GET DIAGNOSTICS player_row_count = ROW_COUNT;

    INSERT INTO public.fpl_fixtures (
        fixture_id, gameweek, kickoff_time, started, finished,
        finished_provisional, home_team_id, home_team_name, away_team_id,
        away_team_name, home_difficulty, away_difficulty, updated_at
    )
    SELECT
        fixture.id,
        fixture.event,
        fixture.kickoff_time,
        fixture.started,
        fixture.finished,
        fixture.finished_provisional,
        fixture.team_h,
        home_team.name,
        fixture.team_a,
        away_team.name,
        fixture.team_h_difficulty,
        fixture.team_a_difficulty,
        snapshot_at
    FROM jsonb_to_recordset(fixtures) AS fixture(
        id integer,
        event integer,
        kickoff_time timestamptz,
        started boolean,
        finished boolean,
        finished_provisional boolean,
        team_h integer,
        team_a integer,
        team_h_difficulty integer,
        team_a_difficulty integer
    )
    LEFT JOIN jsonb_to_recordset(bootstrap->'teams') AS home_team(
        id integer,
        name text
    ) ON home_team.id = fixture.team_h
    LEFT JOIN jsonb_to_recordset(bootstrap->'teams') AS away_team(
        id integer,
        name text
    ) ON away_team.id = fixture.team_a
    ON CONFLICT (fixture_id) DO UPDATE SET
        gameweek = EXCLUDED.gameweek,
        kickoff_time = EXCLUDED.kickoff_time,
        started = EXCLUDED.started,
        finished = EXCLUDED.finished,
        finished_provisional = EXCLUDED.finished_provisional,
        home_team_id = EXCLUDED.home_team_id,
        home_team_name = EXCLUDED.home_team_name,
        away_team_id = EXCLUDED.away_team_id,
        away_team_name = EXCLUDED.away_team_name,
        home_difficulty = EXCLUDED.home_difficulty,
        away_difficulty = EXCLUDED.away_difficulty,
        updated_at = EXCLUDED.updated_at;

    GET DIAGNOSTICS fixture_row_count = ROW_COUNT;

    INSERT INTO public.fpl_refresh_runs (
        refresh_type, status, completed_at, source, current_gameweek,
        latest_finished_gameweek, player_snapshot_rows, fixture_rows, message
    )
    VALUES (
        'live_snapshot',
        'completed',
        now(),
        'FPL bootstrap-static + fixtures via protected database job',
        current_gameweek,
        latest_finished_gameweek,
        player_row_count,
        fixture_row_count,
        'Live player snapshot and fixtures refreshed successfully.'
    );

    RETURN jsonb_build_object(
        'ok', true,
        'snapshot_at', snapshot_at,
        'current_gameweek', current_gameweek,
        'latest_finished_gameweek', latest_finished_gameweek,
        'player_snapshot_rows', player_row_count,
        'fixture_rows', fixture_row_count
    );
END;
$$;

REVOKE ALL ON FUNCTION private.refresh_live_fpl_data() FROM PUBLIC;
GRANT USAGE ON SCHEMA private TO postgres;
GRANT EXECUTE ON FUNCTION private.refresh_live_fpl_data() TO postgres;

SELECT cron.schedule(
    'fpl-live-refresh-every-6-hours',
    '17 */6 * * *',
    $$SELECT private.refresh_live_fpl_data();$$
);
