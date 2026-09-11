-- Store authoritative completed-gameweek totals separately from live snapshots.
-- FPL's event/{gameweek}/live endpoint reports the exact player total for a
-- gameweek and includes the number of fixtures in the explain array. Keeping
-- this at gameweek grain prevents double-gameweek totals from being split or
-- fabricated across individual fixtures.

CREATE TABLE IF NOT EXISTS public.fpl_completed_gameweek_stats (
    season text NOT NULL,
    gameweek integer NOT NULL CHECK (gameweek > 0),
    player_id integer NOT NULL,
    player_name text,
    position text,
    team_id integer,
    team_name text,
    price numeric,
    fixture_count integer NOT NULL DEFAULT 0 CHECK (fixture_count >= 0),
    minutes integer,
    starts integer,
    total_points integer,
    goals_scored integer,
    assists integer,
    clean_sheets integer,
    goals_conceded integer,
    own_goals integer,
    penalties_saved integer,
    penalties_missed integer,
    saves integer,
    yellow_cards integer,
    red_cards integer,
    bonus integer,
    bps integer,
    influence numeric,
    creativity numeric,
    threat numeric,
    ict_index numeric,
    expected_goals numeric,
    expected_assists numeric,
    expected_goal_involvements numeric,
    expected_goals_conceded numeric,
    clearances_blocks_interceptions integer,
    recoveries integer,
    tackles integer,
    defensive_contribution integer,
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (season, gameweek, player_id)
);

CREATE INDEX IF NOT EXISTS fpl_completed_gameweek_stats_player_recent_idx
    ON public.fpl_completed_gameweek_stats
        (player_id, season DESC, gameweek DESC);

CREATE TABLE IF NOT EXISTS public.fpl_gameweek_imports (
    season text NOT NULL,
    gameweek integer NOT NULL CHECK (gameweek > 0),
    status text NOT NULL CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
    source text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    player_rows integer,
    message text,
    PRIMARY KEY (season, gameweek)
);

ALTER TABLE public.fpl_completed_gameweek_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fpl_gameweek_imports ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.fpl_completed_gameweek_stats FROM anon, authenticated;
REVOKE ALL ON TABLE public.fpl_gameweek_imports FROM anon, authenticated;

CREATE OR REPLACE FUNCTION private.import_completed_gameweeks()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, extensions
AS $$
DECLARE
    bootstrap_status integer;
    live_status integer;
    bootstrap jsonb;
    live_payload jsonb;
    event_row jsonb;
    target_gameweek integer;
    latest_finished_gameweek integer;
    current_season text;
    imported_gameweeks integer := 0;
    imported_player_rows integer := 0;
    gameweek_player_rows integer := 0;
BEGIN
    SELECT status, content::jsonb
      INTO bootstrap_status, bootstrap
      FROM extensions.http_get(
          'https://fantasy.premierleague.com/api/bootstrap-static/'
      );

    IF bootstrap_status <> 200 THEN
        RAISE EXCEPTION 'FPL bootstrap request failed (%)', bootstrap_status;
    END IF;

    current_season :=
        CASE
            WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 6
                THEN EXTRACT(YEAR FROM CURRENT_DATE)::text || '-' ||
                     RIGHT((EXTRACT(YEAR FROM CURRENT_DATE)::integer + 1)::text, 2)
            ELSE (EXTRACT(YEAR FROM CURRENT_DATE)::integer - 1)::text || '-' ||
                 RIGHT(EXTRACT(YEAR FROM CURRENT_DATE)::text, 2)
        END;

    SELECT MAX((event->>'id')::integer)
      INTO latest_finished_gameweek
      FROM jsonb_array_elements(bootstrap->'events') AS event
     WHERE COALESCE((event->>'finished')::boolean, false);

    IF latest_finished_gameweek IS NULL THEN
        RETURN jsonb_build_object(
            'ok', true,
            'season', current_season,
            'imported_gameweeks', 0,
            'message', 'No completed gameweeks are available from FPL yet.'
        );
    END IF;

    FOR event_row IN
        SELECT event
          FROM jsonb_array_elements(bootstrap->'events') AS event
         WHERE COALESCE((event->>'finished')::boolean, false)
           AND (
               (event->>'id')::integer = latest_finished_gameweek
               OR NOT EXISTS (
                   SELECT 1
                     FROM public.fpl_gameweek_imports AS prior
                    WHERE prior.season = current_season
                      AND prior.gameweek = (event->>'id')::integer
                      AND prior.status = 'completed'
               )
           )
         ORDER BY (event->>'id')::integer
    LOOP
        target_gameweek := (event_row->>'id')::integer;

        BEGIN
            INSERT INTO public.fpl_gameweek_imports (
                season, gameweek, status, source, started_at, completed_at,
                player_rows, message
            )
            VALUES (
                current_season,
                target_gameweek,
                'started',
                'FPL event live endpoint via protected database job',
                now(),
                NULL,
                NULL,
                'Import in progress.'
            )
            ON CONFLICT (season, gameweek) DO UPDATE SET
                status = 'started',
                source = EXCLUDED.source,
                started_at = EXCLUDED.started_at,
                completed_at = NULL,
                player_rows = NULL,
                message = EXCLUDED.message;

            SELECT status, content::jsonb
              INTO live_status, live_payload
              FROM extensions.http_get(
                  format(
                      'https://fantasy.premierleague.com/api/event/%s/live/',
                      target_gameweek
                  )
              );

            IF live_status <> 200 THEN
                RAISE EXCEPTION
                    'FPL completed-gameweek request failed for GW % (%)',
                    target_gameweek,
                    live_status;
            END IF;

            INSERT INTO public.fpl_completed_gameweek_stats (
                season, gameweek, player_id, player_name, position, team_id,
                team_name, price, fixture_count, minutes, starts, total_points,
                goals_scored, assists, clean_sheets, goals_conceded, own_goals,
                penalties_saved, penalties_missed, saves, yellow_cards,
                red_cards, bonus, bps, influence, creativity, threat, ict_index,
                expected_goals, expected_assists, expected_goal_involvements,
                expected_goals_conceded, clearances_blocks_interceptions,
                recoveries, tackles, defensive_contribution, imported_at
            )
            SELECT
                current_season,
                target_gameweek,
                live_player.id,
                COALESCE(player.web_name,
                         NULLIF(CONCAT_WS(' ', player.first_name, player.second_name), '')),
                position.singular_name_short,
                player.team,
                team.name,
                player.now_cost / 10.0,
                jsonb_array_length(COALESCE(live_player.explain, '[]'::jsonb)),
                NULLIF(live_player.stats->>'minutes', '')::integer,
                NULLIF(live_player.stats->>'starts', '')::integer,
                NULLIF(live_player.stats->>'total_points', '')::integer,
                NULLIF(live_player.stats->>'goals_scored', '')::integer,
                NULLIF(live_player.stats->>'assists', '')::integer,
                NULLIF(live_player.stats->>'clean_sheets', '')::integer,
                NULLIF(live_player.stats->>'goals_conceded', '')::integer,
                NULLIF(live_player.stats->>'own_goals', '')::integer,
                NULLIF(live_player.stats->>'penalties_saved', '')::integer,
                NULLIF(live_player.stats->>'penalties_missed', '')::integer,
                NULLIF(live_player.stats->>'saves', '')::integer,
                NULLIF(live_player.stats->>'yellow_cards', '')::integer,
                NULLIF(live_player.stats->>'red_cards', '')::integer,
                NULLIF(live_player.stats->>'bonus', '')::integer,
                NULLIF(live_player.stats->>'bps', '')::integer,
                NULLIF(live_player.stats->>'influence', '')::numeric,
                NULLIF(live_player.stats->>'creativity', '')::numeric,
                NULLIF(live_player.stats->>'threat', '')::numeric,
                NULLIF(live_player.stats->>'ict_index', '')::numeric,
                NULLIF(live_player.stats->>'expected_goals', '')::numeric,
                NULLIF(live_player.stats->>'expected_assists', '')::numeric,
                NULLIF(live_player.stats->>'expected_goal_involvements', '')::numeric,
                NULLIF(live_player.stats->>'expected_goals_conceded', '')::numeric,
                NULLIF(live_player.stats->>'clearances_blocks_interceptions', '')::integer,
                NULLIF(live_player.stats->>'recoveries', '')::integer,
                NULLIF(live_player.stats->>'tackles', '')::integer,
                NULLIF(live_player.stats->>'defensive_contribution', '')::integer,
                now()
            FROM jsonb_to_recordset(live_payload->'elements') AS live_player(
                id integer,
                stats jsonb,
                explain jsonb
            )
            JOIN jsonb_to_recordset(bootstrap->'elements') AS player(
                id integer,
                first_name text,
                second_name text,
                web_name text,
                team integer,
                element_type integer,
                now_cost numeric
            ) ON player.id = live_player.id
            LEFT JOIN jsonb_to_recordset(bootstrap->'teams') AS team(
                id integer,
                name text
            ) ON team.id = player.team
            LEFT JOIN jsonb_to_recordset(bootstrap->'element_types') AS position(
                id integer,
                singular_name_short text
            ) ON position.id = player.element_type
            ON CONFLICT (season, gameweek, player_id) DO UPDATE SET
                player_name = EXCLUDED.player_name,
                position = EXCLUDED.position,
                team_id = EXCLUDED.team_id,
                team_name = EXCLUDED.team_name,
                price = EXCLUDED.price,
                fixture_count = EXCLUDED.fixture_count,
                minutes = EXCLUDED.minutes,
                starts = EXCLUDED.starts,
                total_points = EXCLUDED.total_points,
                goals_scored = EXCLUDED.goals_scored,
                assists = EXCLUDED.assists,
                clean_sheets = EXCLUDED.clean_sheets,
                goals_conceded = EXCLUDED.goals_conceded,
                own_goals = EXCLUDED.own_goals,
                penalties_saved = EXCLUDED.penalties_saved,
                penalties_missed = EXCLUDED.penalties_missed,
                saves = EXCLUDED.saves,
                yellow_cards = EXCLUDED.yellow_cards,
                red_cards = EXCLUDED.red_cards,
                bonus = EXCLUDED.bonus,
                bps = EXCLUDED.bps,
                influence = EXCLUDED.influence,
                creativity = EXCLUDED.creativity,
                threat = EXCLUDED.threat,
                ict_index = EXCLUDED.ict_index,
                expected_goals = EXCLUDED.expected_goals,
                expected_assists = EXCLUDED.expected_assists,
                expected_goal_involvements = EXCLUDED.expected_goal_involvements,
                expected_goals_conceded = EXCLUDED.expected_goals_conceded,
                clearances_blocks_interceptions =
                    EXCLUDED.clearances_blocks_interceptions,
                recoveries = EXCLUDED.recoveries,
                tackles = EXCLUDED.tackles,
                defensive_contribution = EXCLUDED.defensive_contribution,
                imported_at = EXCLUDED.imported_at;

            GET DIAGNOSTICS gameweek_player_rows = ROW_COUNT;

            INSERT INTO public.fpl_gameweek_imports (
                season, gameweek, status, source, started_at, completed_at,
                player_rows, message
            )
            VALUES (
                current_season,
                target_gameweek,
                'completed',
                'FPL event live endpoint via protected database job',
                now(),
                now(),
                gameweek_player_rows,
                'Completed-gameweek totals imported successfully.'
            )
            ON CONFLICT (season, gameweek) DO UPDATE SET
                status = EXCLUDED.status,
                source = EXCLUDED.source,
                completed_at = EXCLUDED.completed_at,
                player_rows = EXCLUDED.player_rows,
                message = EXCLUDED.message;

            imported_gameweeks := imported_gameweeks + 1;
            imported_player_rows := imported_player_rows + gameweek_player_rows;
        EXCEPTION WHEN OTHERS THEN
            INSERT INTO public.fpl_gameweek_imports (
                season, gameweek, status, source, started_at, completed_at,
                player_rows, message
            )
            VALUES (
                current_season,
                target_gameweek,
                'failed',
                'FPL event live endpoint via protected database job',
                now(),
                now(),
                NULL,
                SQLERRM
            )
            ON CONFLICT (season, gameweek) DO UPDATE SET
                status = EXCLUDED.status,
                completed_at = EXCLUDED.completed_at,
                player_rows = NULL,
                message = EXCLUDED.message;
        END;
    END LOOP;

    RETURN jsonb_build_object(
        'ok', true,
        'season', current_season,
        'latest_finished_gameweek', latest_finished_gameweek,
        'imported_gameweeks', imported_gameweeks,
        'imported_player_rows', imported_player_rows
    );
END;
$$;

CREATE OR REPLACE FUNCTION private.refresh_fpl_data()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, extensions
AS $$
DECLARE
    live_refresh jsonb;
    historical_import jsonb;
BEGIN
    live_refresh := private.refresh_live_fpl_data();
    historical_import := private.import_completed_gameweeks();

    RETURN jsonb_build_object(
        'live_refresh', live_refresh,
        'completed_gameweek_import', historical_import
    );
END;
$$;

REVOKE ALL ON FUNCTION private.import_completed_gameweeks() FROM PUBLIC;
REVOKE ALL ON FUNCTION private.refresh_fpl_data() FROM PUBLIC;
GRANT USAGE ON SCHEMA private TO postgres;
GRANT EXECUTE ON FUNCTION private.import_completed_gameweeks() TO postgres;
GRANT EXECUTE ON FUNCTION private.refresh_fpl_data() TO postgres;

SELECT cron.unschedule(jobid)
  FROM cron.job
 WHERE jobname = 'fpl-live-refresh-every-6-hours';

SELECT cron.schedule(
    'fpl-live-refresh-every-6-hours',
    '17 */6 * * *',
    $$SELECT private.refresh_fpl_data();$$
);
