-- Preserve finalized current-season player results at fixture grain as well as
-- gameweek grain. This makes "last N matches" exact in double gameweeks.

CREATE INDEX IF NOT EXISTS player_gameweek_current_fixture_recent_idx
    ON public.player_gameweek (season, player_id, gameweek DESC, fixture_id DESC);

CREATE OR REPLACE FUNCTION private.import_current_season_fixture_history()
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
    current_season text;
    imported_gameweeks integer := 0;
    imported_fixture_rows integer := 0;
    fixture_rows integer := 0;
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

    FOR event_row IN
        SELECT event
          FROM jsonb_array_elements(bootstrap->'events') AS event
         WHERE COALESCE((event->>'finished')::boolean, false)
         ORDER BY (event->>'id')::integer
    LOOP
        target_gameweek := (event_row->>'id')::integer;

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
                'FPL fixture-history request failed for GW % (%)',
                target_gameweek,
                live_status;
        END IF;

        INSERT INTO public.player_gameweek (
            season, gameweek, player_id, player_name, position, team,
            fixture_id, opponent_team_id, was_home, minutes, starts,
            total_points, goals_scored, assists, clean_sheets, goals_conceded,
            own_goals, penalties_saved, penalties_missed, saves, yellow_cards,
            red_cards, bonus, bps, influence, creativity, threat, ict_index,
            expected_goals, expected_assists, expected_goal_involvements,
            expected_goals_conceded, price, team_id, team_name,
            clearances_blocks_interceptions, recoveries, tackles,
            defensive_contribution
        )
        SELECT
            current_season,
            target_gameweek,
            live_player.id,
            COALESCE(player.web_name,
                     NULLIF(CONCAT_WS(' ', player.first_name, player.second_name), '')),
            position.singular_name_short,
            team.name,
            (fixture_explanation->>'fixture')::integer,
            CASE
                WHEN fixture.home_team_id = player.team THEN fixture.away_team_id
                ELSE fixture.home_team_id
            END,
            fixture.home_team_id = player.team,
            fixture_stats.minutes,
            fixture_stats.starts,
            fixture_stats.total_points,
            fixture_stats.goals_scored,
            fixture_stats.assists,
            fixture_stats.clean_sheets,
            fixture_stats.goals_conceded,
            fixture_stats.own_goals,
            fixture_stats.penalties_saved,
            fixture_stats.penalties_missed,
            fixture_stats.saves,
            fixture_stats.yellow_cards,
            fixture_stats.red_cards,
            fixture_stats.bonus,
            fixture_stats.bps,
            fixture_stats.influence,
            fixture_stats.creativity,
            fixture_stats.threat,
            fixture_stats.ict_index,
            fixture_stats.expected_goals,
            fixture_stats.expected_assists,
            fixture_stats.expected_goal_involvements,
            fixture_stats.expected_goals_conceded,
            player.now_cost / 10.0,
            player.team,
            team.name,
            fixture_stats.clearances_blocks_interceptions,
            fixture_stats.recoveries,
            fixture_stats.tackles,
            fixture_stats.defensive_contribution
        FROM jsonb_to_recordset(live_payload->'elements') AS live_player(
            id integer,
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
        JOIN jsonb_to_recordset(bootstrap->'teams') AS team(
            id integer,
            name text
        ) ON team.id = player.team
        JOIN jsonb_to_recordset(bootstrap->'element_types') AS position(
            id integer,
            singular_name_short text
        ) ON position.id = player.element_type
        CROSS JOIN LATERAL jsonb_array_elements(
            COALESCE(live_player.explain, '[]'::jsonb)
        ) AS fixture_explanation
        JOIN public.fpl_fixtures AS fixture
          ON fixture.fixture_id = (fixture_explanation->>'fixture')::integer
         AND fixture.finished IS TRUE
        CROSS JOIN LATERAL (
            SELECT
                SUM(COALESCE(NULLIF(stat->>'points', '')::integer, 0))
                    AS total_points,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'minutes') AS minutes,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'starts') AS starts,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'goals_scored') AS goals_scored,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'assists') AS assists,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'clean_sheets') AS clean_sheets,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'goals_conceded') AS goals_conceded,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'own_goals') AS own_goals,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'penalties_saved') AS penalties_saved,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'penalties_missed') AS penalties_missed,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'saves') AS saves,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'yellow_cards') AS yellow_cards,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'red_cards') AS red_cards,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'bonus') AS bonus,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'bps') AS bps,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'influence') AS influence,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'creativity') AS creativity,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'threat') AS threat,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'ict_index') AS ict_index,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'expected_goals') AS expected_goals,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'expected_assists') AS expected_assists,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'expected_goal_involvements') AS expected_goal_involvements,
                MAX(NULLIF(stat->>'value', '')::numeric)
                    FILTER (WHERE stat->>'identifier' = 'expected_goals_conceded') AS expected_goals_conceded,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'clearances_blocks_interceptions') AS clearances_blocks_interceptions,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'recoveries') AS recoveries,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'tackles') AS tackles,
                MAX(NULLIF(stat->>'value', '')::integer)
                    FILTER (WHERE stat->>'identifier' = 'defensive_contribution') AS defensive_contribution
            FROM jsonb_array_elements(
                COALESCE(fixture_explanation->'stats', '[]'::jsonb)
            ) AS stat
        ) AS fixture_stats
        ON CONFLICT (season, gameweek, player_id, fixture_id) DO UPDATE SET
            player_name = EXCLUDED.player_name,
            position = EXCLUDED.position,
            team = EXCLUDED.team,
            opponent_team_id = EXCLUDED.opponent_team_id,
            was_home = EXCLUDED.was_home,
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
            price = EXCLUDED.price,
            team_id = EXCLUDED.team_id,
            team_name = EXCLUDED.team_name,
            clearances_blocks_interceptions = EXCLUDED.clearances_blocks_interceptions,
            recoveries = EXCLUDED.recoveries,
            tackles = EXCLUDED.tackles,
            defensive_contribution = EXCLUDED.defensive_contribution;

        GET DIAGNOSTICS fixture_rows = ROW_COUNT;
        imported_gameweeks := imported_gameweeks + 1;
        imported_fixture_rows := imported_fixture_rows + fixture_rows;
    END LOOP;

    RETURN jsonb_build_object(
        'ok', true,
        'season', current_season,
        'imported_gameweeks', imported_gameweeks,
        'imported_fixture_rows', imported_fixture_rows
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
    completed_gameweek_import jsonb;
    fixture_history_import jsonb;
BEGIN
    live_refresh := private.refresh_live_fpl_data();
    completed_gameweek_import := private.import_completed_gameweeks();
    fixture_history_import := private.import_current_season_fixture_history();

    RETURN jsonb_build_object(
        'live_refresh', live_refresh,
        'completed_gameweek_import', completed_gameweek_import,
        'fixture_history_import', fixture_history_import
    );
END;
$$;

REVOKE ALL ON FUNCTION private.import_current_season_fixture_history() FROM PUBLIC;
REVOKE ALL ON FUNCTION private.refresh_fpl_data() FROM PUBLIC;
GRANT USAGE ON SCHEMA private TO postgres;
GRANT EXECUTE ON FUNCTION private.import_current_season_fixture_history() TO postgres;
GRANT EXECUTE ON FUNCTION private.refresh_fpl_data() TO postgres;
