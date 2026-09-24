import streamlit as st
import pandas as pd
from sqlalchemy import text
from collections import Counter


def get_database_connection():

    return st.connection(
        "fpl_db",
        type="sql"
    )


def save_players(players):

    conn = get_database_connection()

    sql = text(
        """
        INSERT INTO players (
            player_id,
            first_name,
            second_name,
            team_id,
            team_name,
            position,
            price,
            total_points,
            form,
            selected_by_percent
        )
        VALUES (
            :player_id,
            :first_name,
            :second_name,
            :team_id,
            :team_name,
            :position,
            :price,
            :total_points,
            :form,
            :selected_by_percent
        )
        ON CONFLICT (player_id)
        DO UPDATE SET
            first_name = EXCLUDED.first_name,
            second_name = EXCLUDED.second_name,
            team_id = EXCLUDED.team_id,
            team_name = EXCLUDED.team_name,
            position = EXCLUDED.position,
            price = EXCLUDED.price,
            total_points = EXCLUDED.total_points,
            form = EXCLUDED.form,
            selected_by_percent = EXCLUDED.selected_by_percent
        """
    )

    with conn.session as session:

        for _, player in players.iterrows():

            session.execute(
                sql,
                {
                    "player_id": int(player["id"]),
                    "first_name": player["first_name"],
                    "second_name": player["second_name"],
                    "team_id": int(player["team"]),
                    "team_name": player["team_name"],
                    "position": player["position"],
                    "price": float(player["price"]),
                    "total_points": int(player["total_points"]),
                    "form": float(player["form"] or 0),
                    "selected_by_percent": float(
                        player["selected_by_percent"] or 0
                    )
                }
            )

        session.commit()


def save_historical_data(records):

    conn = get_database_connection()

    sql = text(
        """
        INSERT INTO player_gameweek (
            season,
            gameweek,
            player_id,
            player_name,
            position,
            team_id,
            team_code,
            team_name,
            fixture_id,
            fixture_code,
            opponent_team_id,
            was_home,
            minutes,
            starts,
            total_points,
            goals_scored,
            assists,
            clean_sheets,
            goals_conceded,
            own_goals,
            penalties_saved,
            penalties_missed,
            saves,
            yellow_cards,
            red_cards,
            bonus,
            bps,
            influence,
            creativity,
            threat,
            ict_index,
            clearances_blocks_interceptions,
            recoveries,
            tackles,
            defensive_contribution,
            expected_goals,
            expected_assists,
            expected_goal_involvements,
            expected_goals_conceded,
            price,
            transfers_balance,
            selected,
            transfers_in,
            transfers_out
        )
        VALUES (
            :season,
            :gameweek,
            :player_id,
            :player_name,
            :position,
            :team_id,
            :team_code,
            :team_name,
            :fixture_id,
            :fixture_code,
            :opponent_team_id,
            :was_home,
            :minutes,
            :starts,
            :total_points,
            :goals_scored,
            :assists,
            :clean_sheets,
            :goals_conceded,
            :own_goals,
            :penalties_saved,
            :penalties_missed,
            :saves,
            :yellow_cards,
            :red_cards,
            :bonus,
            :bps,
            :influence,
            :creativity,
            :threat,
            :ict_index,
            :clearances_blocks_interceptions,
            :recoveries,
            :tackles,
            :defensive_contribution,
            :expected_goals,
            :expected_assists,
            :expected_goal_involvements,
            :expected_goals_conceded,
            :price,
            :transfers_balance,
            :selected,
            :transfers_in,
            :transfers_out
        )
        ON CONFLICT (
            season,
            gameweek,
            player_id,
            fixture_id
        )
        DO UPDATE SET
            player_name = EXCLUDED.player_name,
            position = EXCLUDED.position,
            team_id = EXCLUDED.team_id,
            team_code = EXCLUDED.team_code,
            team_name = EXCLUDED.team_name,
            fixture_code = EXCLUDED.fixture_code,
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
            clearances_blocks_interceptions =
                EXCLUDED.clearances_blocks_interceptions,
            recoveries = EXCLUDED.recoveries,
            tackles = EXCLUDED.tackles,
            defensive_contribution =
                EXCLUDED.defensive_contribution,
            expected_goals = EXCLUDED.expected_goals,
            expected_assists = EXCLUDED.expected_assists,
            expected_goal_involvements =
                EXCLUDED.expected_goal_involvements,
            expected_goals_conceded =
                EXCLUDED.expected_goals_conceded,
            price = EXCLUDED.price,
            transfers_balance = EXCLUDED.transfers_balance,
            selected = EXCLUDED.selected,
            transfers_in = EXCLUDED.transfers_in,
            transfers_out = EXCLUDED.transfers_out
        """
    )

    data = records.to_dict(
        orient="records"
    )

    batch_size = 500
    total = len(data)

    with conn.session as session:

        for start in range(
            0,
            total,
            batch_size
        ):

            batch = data[
                start:start + batch_size
            ]

            session.execute(
                sql,
                batch
            )

            session.commit()

    return total


# The new implementation is deliberately column-driven: adding a feature only
# requires updating this one source of truth, avoiding mismatched INSERT,
# VALUES, and ON CONFLICT lists.
_CORE_PREDICTION_FEATURE_COLUMNS = [
    "season", "gameweek", "player_id", "player_name", "position",
    "team_id", "team_name",
    "next_1gw_fixture_count", "next_1gw_avg_fdr",
    "next_1gw_home_count", "next_1gw_away_count",
    "next_1gw_opponent_avg_5fixture_goals_conceded",
    "next_1gw_opponent_avg_5fixture_clean_sheet_rate",
    "next_1gw_team_avg_5fixture_goals_conceded",
    "next_1gw_team_avg_5fixture_clean_sheet_rate",
    "next_1gw_opponent_avg_5fixture_goals_scored",
    "previous_gw_points", "rolling_3gw_points", "rolling_5gw_points",
    "rolling_10gw_points", "previous_gw_xg", "rolling_3gw_xg",
    "rolling_5gw_xg", "rolling_10gw_xg", "previous_gw_xa",
    "rolling_3gw_xa", "rolling_5gw_xa", "rolling_10gw_xa",
    "previous_gw_xgi", "rolling_3gw_xgi", "rolling_5gw_xgi",
    "rolling_10gw_xgi", "previous_gw_minutes", "rolling_3gw_minutes",
    "rolling_5gw_minutes", "rolling_10gw_minutes", "previous_gw_starts",
    "rolling_3gw_starts", "rolling_5gw_starts", "rolling_10gw_starts",
    "rolling_3gw_start_rate", "rolling_5gw_start_rate",
    "rolling_10gw_start_rate", "previous_gw_played",
    "previous_gw_60_minute_appearance",
    "rolling_3gw_minutes_per_fixture", "rolling_5gw_minutes_per_fixture",
    "rolling_10gw_minutes_per_fixture", "rolling_3gw_play_rate",
    "rolling_5gw_play_rate", "rolling_10gw_play_rate",
    "rolling_3gw_60_minute_appearance_rate",
    "rolling_5gw_60_minute_appearance_rate",
    "rolling_10gw_60_minute_appearance_rate",
    "minutes_trend_3gw_vs_10gw", "start_rate_trend_3gw_vs_10gw",
    "expected_minutes_per_fixture", "expected_minutes_next_gw",
    "next_gw_points",
]
_PLAYER_CONTEXT_METRICS = [
    "goals_scored", "assists", "clean_sheets", "bonus", "threat",
    "creativity", "defensive_contribution",
]
_PLAYER_CONTEXT_FEATURE_COLUMNS = [
    f"previous_gw_{metric}" for metric in _PLAYER_CONTEXT_METRICS
] + [
    f"rolling_{window}gw_{metric}"
    for metric in _PLAYER_CONTEXT_METRICS for window in (3, 5, 10)
] + [
    f"rolling_{window}gw_{metric}_per_90"
    for window in (3, 5)
    for metric in (
        "xgi", "goals_scored", "assists", "threat", "creativity",
        "defensive_contribution",
    )
]
PREDICTION_FEATURE_COLUMNS = (
    _CORE_PREDICTION_FEATURE_COLUMNS[:-1]
    + _PLAYER_CONTEXT_FEATURE_COLUMNS
    + ["next_gw_points"]
)

# These columns are deliberately checked before and after every rebuild.  They
# cover player attacking output, defensive output, and fixture context without
# logging any credentials or sensitive connection details.
PREDICTION_FEATURE_AUDIT_COLUMNS = [
    "previous_gw_goals_scored",
    "rolling_3gw_goals_scored",
    "previous_gw_clean_sheets",
    "rolling_3gw_clean_sheets",
    "previous_gw_threat",
    "rolling_3gw_creativity",
    "rolling_3gw_xgi_per_90",
    "rolling_3gw_defensive_contribution",
    "next_1gw_team_avg_5fixture_goals_conceded",
    "next_1gw_opponent_avg_5fixture_goals_scored",
    "expected_minutes_per_fixture",
    "expected_minutes_next_gw",
]


def save_prediction_features(features):
    """Atomically replace feature rows and verify the saved feature values."""
    missing = [
        column for column in PREDICTION_FEATURE_COLUMNS
        if column not in features.columns
    ]
    if missing:
        raise ValueError(
            f"Prediction features are missing database columns: {missing}"
        )

    records = (
        features[PREDICTION_FEATURE_COLUMNS]
        .astype(object)
        .where(pd.notna(features[PREDICTION_FEATURE_COLUMNS]), None)
        .to_dict(orient="records")
    )
    if not records:
        return 0

    pre_save_counts = {
        column: sum(row[column] is not None for row in records)
        for column in PREDICTION_FEATURE_AUDIT_COLUMNS
    }
    print(
        f"DEBUG: pre-save populated feature counts = {pre_save_counts}",
        flush=True,
    )
    empty_pre_save_columns = [
        column
        for column, count in pre_save_counts.items()
        if count == 0
    ]
    if empty_pre_save_columns:
        raise ValueError(
            "Feature dataframe has no populated values for: "
            f"{empty_pre_save_columns}"
        )

    keys = [(row["season"], row["gameweek"], row["player_id"]) for row in records]
    if len(keys) != len(set(keys)):
        raise ValueError(
            "Feature dataframe contains duplicate (season, gameweek, player_id) keys."
        )

    column_sql = ", ".join(PREDICTION_FEATURE_COLUMNS)
    value_sql = ", ".join(f":{column}" for column in PREDICTION_FEATURE_COLUMNS)
    update_sql = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in PREDICTION_FEATURE_COLUMNS
        if column not in {"season", "gameweek", "player_id"}
    )
    insert_sql = text(
        f"""
        INSERT INTO prediction_features ({column_sql})
        VALUES ({value_sql})
        ON CONFLICT (season, gameweek, player_id)
        DO UPDATE SET {update_sql}
        """
    )
    delete_sql = text(
        "DELETE FROM prediction_features WHERE season = :season"
    )
    seasons = sorted({row["season"] for row in records})
    expected_rows_by_season = Counter(row["season"] for row in records)
    audit_select_list = ", ".join(
        ["COUNT(*) AS total_rows"]
        + [f"COUNT({column}) AS {column}" for column in PREDICTION_FEATURE_AUDIT_COLUMNS]
    )
    audit_sql = text(
        f"""
        SELECT {audit_select_list}
        FROM prediction_features
        WHERE season = :season
        """
    )

    conn = get_database_connection()
    with conn.session as session:
        committed = False
        try:
            print(
                f"DEBUG: replacing prediction features for seasons = {seasons}",
                flush=True,
            )
            for season in seasons:
                session.execute(delete_sql, {"season": season})
            total_batches = (len(records) + 499) // 500
            for start in range(0, len(records), 500):
                batch_number = start // 500 + 1
                print(
                    f"DEBUG: inserting prediction feature batch "
                    f"{batch_number}/{total_batches}",
                    flush=True,
                )
                session.execute(insert_sql, records[start:start + 500])
            session.commit()
            committed = True

            for season in seasons:
                audit = dict(
                    session.execute(
                        audit_sql,
                        {"season": season},
                    ).mappings().one()
                )
                print(
                    f"DEBUG: post-commit feature audit for {season} = {audit}",
                    flush=True,
                )
                missing_saved_columns = [
                    column
                    for column in PREDICTION_FEATURE_AUDIT_COLUMNS
                    if audit[column] == 0
                ]
                if audit["total_rows"] != expected_rows_by_season[season]:
                    raise RuntimeError(
                        f"Post-commit row-count mismatch for {season}: "
                        f"expected {expected_rows_by_season[season]}, "
                        f"saved {audit['total_rows']}."
                    )
                if missing_saved_columns:
                    raise RuntimeError(
                        f"Post-commit audit found blank saved columns for "
                        f"{season}: {missing_saved_columns}."
                    )
        except Exception:
            if not committed:
                session.rollback()
                print(
                    "DEBUG: prediction feature rebuild rolled back",
                    flush=True,
                )
            else:
                print(
                    "DEBUG: prediction feature rebuild committed, but the "
                    "post-commit audit failed",
                    flush=True,
                )
            raise

    return len(records)


def _save_prediction_features_legacy(features):

    conn = get_database_connection()

    print(
        "DEBUG: save_prediction_features started",
        flush=True
    )

    print(
        f"DEBUG: total feature rows = {len(features)}",
        flush=True
    )

    sql = text(
        """
        INSERT INTO prediction_features (
            season,
            gameweek,
            player_id,
            player_name,
            position,
            team_id,
            team_name,
            next_1gw_fixture_count,
            next_1gw_avg_fdr,
            next_1gw_home_count,
            next_1gw_away_count,
            next_1gw_opponent_avg_5fixture_goals_conceded,
            next_1gw_opponent_avg_5fixture_clean_sheet_rate,
            
            previous_gw_points,
            rolling_3gw_points,
            rolling_5gw_points,
            rolling_10gw_points,

            previous_gw_xg,
            rolling_3gw_xg,
            rolling_5gw_xg,
            rolling_10gw_xg,

            previous_gw_xa,
            rolling_3gw_xa,
            rolling_5gw_xa,
            rolling_10gw_xa,

            previous_gw_xgi,
            rolling_3gw_xgi,
            rolling_5gw_xgi,
            rolling_10gw_xgi,

            previous_gw_minutes,
            rolling_3gw_minutes,
            rolling_5gw_minutes,
            rolling_10gw_minutes,

            previous_gw_starts,
            rolling_3gw_starts,
            rolling_5gw_starts,
            rolling_10gw_starts,

            rolling_3gw_start_rate,
            rolling_5gw_start_rate,
            rolling_10gw_start_rate,

            next_gw_points
        )
        VALUES (
            :season,
            :gameweek,
            :player_id,
            :player_name,
            :position,
            :team_id,
            :team_name,
            :next_1gw_fixture_count,
            :next_1gw_avg_fdr,
            :next_1gw_home_count,
            :next_1gw_away_count,
            :next_1gw_opponent_avg_5fixture_goals_conceded,
            :next_1gw_opponent_avg_5fixture_clean_sheet_rate,
            
            :previous_gw_points,
            :rolling_3gw_points,
            :rolling_5gw_points,
            :rolling_10gw_points,

            :previous_gw_xg,
            :rolling_3gw_xg,
            :rolling_5gw_xg,
            :rolling_10gw_xg,

            :previous_gw_xa,
            :rolling_3gw_xa,
            :rolling_5gw_xa,
            :rolling_10gw_xa,

            :previous_gw_xgi,
            :rolling_3gw_xgi,
            :rolling_5gw_xgi,
            :rolling_10gw_xgi,

            :previous_gw_minutes,
            :rolling_3gw_minutes,
            :rolling_5gw_minutes,
            :rolling_10gw_minutes,

            :previous_gw_starts,
            :rolling_3gw_starts,
            :rolling_5gw_starts,
            :rolling_10gw_starts,

            :rolling_3gw_start_rate,
            :rolling_5gw_start_rate,
            :rolling_10gw_start_rate,

            :next_gw_points
        )
        ON CONFLICT (
            season,
            gameweek,
            player_id
        )
        DO UPDATE SET
            player_name = EXCLUDED.player_name,
            position = EXCLUDED.position,
            team_id = EXCLUDED.team_id,
            team_name = EXCLUDED.team_name,

            next_1gw_fixture_count = EXCLUDED.next_1gw_fixture_count,
            next_1gw_avg_fdr = EXCLUDED.next_1gw_avg_fdr,
            next_1gw_home_count = EXCLUDED.next_1gw_home_count,
            next_1gw_away_count = EXCLUDED.next_1gw_away_count,
            next_1gw_opponent_avg_5fixture_goals_conceded = EXCLUDED.next_1gw_opponent_avg_5fixture_goals_conceded,
            next_1gw_opponent_avg_5fixture_clean_sheet_rate = EXCLUDED.next_1gw_opponent_avg_5fixture_clean_sheet_rate,
            previous_gw_points = EXCLUDED.previous_gw_points,
            rolling_3gw_points = EXCLUDED.rolling_3gw_points,
            rolling_5gw_points = EXCLUDED.rolling_5gw_points,
            rolling_10gw_points = EXCLUDED.rolling_10gw_points,

            previous_gw_xg = EXCLUDED.previous_gw_xg,
            rolling_3gw_xg = EXCLUDED.rolling_3gw_xg,
            rolling_5gw_xg = EXCLUDED.rolling_5gw_xg,
            rolling_10gw_xg = EXCLUDED.rolling_10gw_xg,

            previous_gw_xa = EXCLUDED.previous_gw_xa,
            rolling_3gw_xa = EXCLUDED.rolling_3gw_xa,
            rolling_5gw_xa = EXCLUDED.rolling_5gw_xa,
            rolling_10gw_xa = EXCLUDED.rolling_10gw_xa,

            previous_gw_xgi = EXCLUDED.previous_gw_xgi,
            rolling_3gw_xgi = EXCLUDED.rolling_3gw_xgi,
            rolling_5gw_xgi = EXCLUDED.rolling_5gw_xgi,
            rolling_10gw_xgi = EXCLUDED.rolling_10gw_xgi,

            previous_gw_minutes = EXCLUDED.previous_gw_minutes,
            rolling_3gw_minutes = EXCLUDED.rolling_3gw_minutes,
            rolling_5gw_minutes = EXCLUDED.rolling_5gw_minutes,
            rolling_10gw_minutes = EXCLUDED.rolling_10gw_minutes,

            previous_gw_starts = EXCLUDED.previous_gw_starts,
            rolling_3gw_starts = EXCLUDED.rolling_3gw_starts,
            rolling_5gw_starts = EXCLUDED.rolling_5gw_starts,
            rolling_10gw_starts = EXCLUDED.rolling_10gw_starts,

            rolling_3gw_start_rate =
                EXCLUDED.rolling_3gw_start_rate,
            rolling_5gw_start_rate =
                EXCLUDED.rolling_5gw_start_rate,
            rolling_10gw_start_rate =
                EXCLUDED.rolling_10gw_start_rate,

            next_gw_points = EXCLUDED.next_gw_points
        """
    )

    delete_sql = text(
        """
        DELETE FROM prediction_features
        WHERE season = :season
        """
    )

    data = features.to_dict(
        orient="records"
    )

    if not data:
        print(
            "DEBUG: no prediction feature rows to save",
            flush=True
        )
        return 0

    seasons = sorted(
        {
            row["season"]
            for row in data
        }
    )

    keys = [
        (
            row["season"],
            row["gameweek"],
            row["player_id"]
        )
        for row in data
    ]

    key_counts = Counter(keys)

    duplicate_keys = {
        key: count
        for key, count in key_counts.items()
        if count > 1
    }

    duplicate_record_count = sum(
        count - 1
        for count in key_counts.values()
        if count > 1
    )

    print(
        f"DEBUG: rebuilding seasons = {seasons}",
        flush=True
    )

    print(
        f"DEBUG: unique (season, gameweek, player_id) keys = "
        f"{len(key_counts)}",
        flush=True
    )

    print(
        f"DEBUG: duplicate key records = "
        f"{duplicate_record_count}",
        flush=True
    )

    print(
        f"DEBUG: number of duplicated keys = "
        f"{len(duplicate_keys)}",
        flush=True
    )

    if duplicate_keys:
        raise ValueError(
            "Feature dataframe contains duplicate "
            "(season, gameweek, player_id) keys."
        )

    batch_size = 500
    total = len(data)
    total_batches = (
        total + batch_size - 1
    ) // batch_size

    print(
        "DEBUG: attempting to open database session",
        flush=True
    )

    with conn.session as session:

        try:

            print(
                "DEBUG: database session opened",
                flush=True
            )

            for season in seasons:

                print(
                    f"DEBUG: deleting existing "
                    f"prediction features for {season}",
                    flush=True
                )

                session.execute(
                    delete_sql,
                    {"season": season}
                )

            for start in range(
                0,
                total,
                batch_size
            ):

                batch_number = (
                    start // batch_size + 1
                )

                batch = data[
                    start:start + batch_size
                ]

                print(
                    f"DEBUG: inserting batch "
                    f"{batch_number}/{total_batches} "
                    f"({len(batch)} rows)",
                    flush=True
                )

                session.execute(
                    sql,
                    batch
                )

            session.commit()

            print(
                "DEBUG: prediction feature rebuild committed",
                flush=True
            )

        except Exception:

            session.rollback()

            print(
                "DEBUG: prediction feature rebuild rolled back",
                flush=True
            )

            raise

    return total


# ============================================================
# FPL COPILOT — READ-ONLY DATA ACCESS
# ============================================================


_FPL_POSITIONS = {"GKP", "DEF", "MID", "FWD"}
_FORM_METRICS = {
    "points": "rolling_3gw_points",
    "xgi": "rolling_3gw_xgi",
    "minutes": "rolling_3gw_minutes",
    "threat": "rolling_3gw_threat",
    "creativity": "rolling_3gw_creativity",
    "defensive_contribution": "rolling_3gw_defensive_contribution",
}


def _read_dataframe(sql, params=None):
    """Run a parameterised read-only query and return a dataframe."""
    conn = get_database_connection()
    with conn.session as session:
        result = session.execute(text(sql), params or {})
        return pd.DataFrame(result.mappings().all())


def _records(frame):
    """Convert database values to JSON-safe records for the language model."""
    if frame.empty:
        return []
    return (
        frame.astype(object)
        .where(pd.notna(frame), None)
        .to_dict(orient="records")
    )


def search_fpl_players(query, position=None, limit=8):
    """Find a player in the live snapshot, then fall back to historical data."""
    position = position.upper() if position else None
    if position and position not in _FPL_POSITIONS:
        raise ValueError("position must be one of GKP, DEF, MID, or FWD.")

    normalized_query = str(query).strip()
    if not normalized_query:
        raise ValueError("query must contain a player name.")

    limit = max(1, min(int(limit), 10))
    params = {
        "name_pattern": f"%{normalized_query}%",
        "position": position,
        "limit": limit,
    }

    live_rows = _read_dataframe(
        """
        SELECT
            player_id,
            first_name || ' ' || second_name AS player_name,
            team_name,
            position,
            price,
            total_points,
            form,
            selected_by_percent
        FROM public.players
        WHERE (first_name || ' ' || second_name) ILIKE :name_pattern
          AND (:position IS NULL OR position = :position)
        ORDER BY total_points DESC NULLS LAST, form DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )
    if not live_rows.empty:
        return {
            "source": "players (latest imported FPL player snapshot)",
            "rows": _records(live_rows),
        }

    historical_rows = _read_dataframe(
        """
        WITH latest_player_rows AS (
            SELECT DISTINCT ON (player_id)
                player_id,
                player_name,
                team_name,
                position,
                season AS latest_historical_season,
                gameweek AS latest_historical_gameweek
            FROM public.player_gameweek
            WHERE player_name ILIKE :name_pattern
              AND (:position IS NULL OR position = :position)
            ORDER BY player_id, season DESC, gameweek DESC, fixture_id DESC
        )
        SELECT *
        FROM latest_player_rows
        ORDER BY latest_historical_season DESC,
                 latest_historical_gameweek DESC,
                 player_name
        LIMIT :limit
        """,
        params,
    )
    return {
        "source": (
            "player_gameweek (historical player index; "
            "not a current live player snapshot)"
        ),
        "rows": _records(historical_rows),
    }


def get_player_recent_form(player_id, gameweeks=5, window="gameweeks"):
    """Return finalized player form by gameweek totals or individual matches."""
    gameweeks = max(1, min(int(gameweeks), 10))
    window = window if window in {"gameweeks", "matches"} else "gameweeks"

    if window == "matches":
        rows = _read_dataframe(
            """
            WITH latest_season AS (
                SELECT MAX(season) AS season
                FROM public.fpl_completed_gameweek_stats
            )
            SELECT
                history.season,
                history.gameweek,
                history.fixture_id,
                fixtures.kickoff_time,
                history.player_name,
                history.position,
                COALESCE(history.team_name, history.team) AS team_name,
                history.opponent_team_id,
                CASE
                    WHEN history.was_home THEN fixtures.away_team_name
                    ELSE fixtures.home_team_name
                END AS opponent_team_name,
                history.was_home,
                1 AS fixture_count,
                history.minutes,
                history.starts,
                history.total_points,
                history.goals_scored,
                history.assists,
                history.clean_sheets,
                history.goals_conceded,
                history.own_goals,
                history.penalties_saved,
                history.penalties_missed,
                history.saves,
                history.yellow_cards,
                history.red_cards,
                history.bonus,
                history.bps,
                history.defensive_contribution,
                history.expected_goals,
                history.expected_assists,
                history.expected_goal_involvements,
                history.creativity,
                history.threat,
                'completed_fixture' AS data_grain
            FROM public.player_gameweek AS history
            JOIN public.fpl_fixtures AS fixtures
              ON fixtures.fixture_id = history.fixture_id
            INNER JOIN latest_season
              ON history.season = latest_season.season
            WHERE history.player_id = :player_id
              AND fixtures.finished IS TRUE
            ORDER BY fixtures.kickoff_time DESC NULLS LAST,
                     history.season DESC,
                     history.gameweek DESC,
                     history.fixture_id DESC
            LIMIT :limit
            """,
            {"player_id": int(player_id), "limit": gameweeks},
        )
        return {
            "source": "finalized fixture-level FPL data",
            "window": "matches",
            "rows": _records(rows),
        }

    rows = _read_dataframe(
        """
        WITH latest_season AS (
            SELECT MAX(season) AS season
            FROM public.fpl_completed_gameweek_stats
        ),
        completed_gameweeks AS (
            SELECT
                fpl_completed_gameweek_stats.season AS season,
                gameweek,
                player_name,
                position,
                team_name,
                NULL::integer AS opponent_team_id,
                NULL::boolean AS was_home,
                fixture_count,
                minutes,
                starts,
                total_points,
                goals_scored,
                assists,
                clean_sheets,
                goals_conceded,
                own_goals,
                penalties_saved,
                penalties_missed,
                saves,
                yellow_cards,
                red_cards,
                bonus,
                bps,
                defensive_contribution,
                expected_goals,
                expected_assists,
                expected_goal_involvements,
                creativity,
                threat,
                defensive_contribution,
                'completed_gameweek_total' AS data_grain
            FROM public.fpl_completed_gameweek_stats
            INNER JOIN latest_season
                ON fpl_completed_gameweek_stats.season = latest_season.season
            WHERE player_id = :player_id
        ),
        fixture_history AS (
            SELECT
                history.season,
                history.gameweek,
                history.player_name,
                history.position,
                history.team_name,
                history.opponent_team_id,
                history.was_home,
                1 AS fixture_count,
                history.minutes,
                history.starts,
                history.total_points,
                history.goals_scored,
                history.assists,
                history.clean_sheets,
                history.goals_conceded,
                history.own_goals,
                history.penalties_saved,
                history.penalties_missed,
                history.saves,
                history.yellow_cards,
                history.red_cards,
                history.bonus,
                history.bps,
                history.defensive_contribution,
                history.expected_goals,
                history.expected_assists,
                history.expected_goal_involvements,
                history.creativity,
                history.threat,
                history.defensive_contribution,
                'historical_fixture' AS data_grain
            FROM public.player_gameweek AS history
            INNER JOIN latest_season
                ON history.season = latest_season.season
            WHERE history.player_id = :player_id
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.fpl_completed_gameweek_stats AS completed
                  WHERE completed.player_id = history.player_id
                    AND completed.season = history.season
                    AND completed.gameweek = history.gameweek
              )
        )
        SELECT *
        FROM (
            SELECT * FROM completed_gameweeks
            UNION ALL
            SELECT * FROM fixture_history
        ) AS form
        ORDER BY season DESC, gameweek DESC, data_grain
        LIMIT :limit
        """,
        {"player_id": int(player_id), "limit": gameweeks},
    )
    return {
        "source": "finalized current-season gameweek totals",
        "window": "gameweeks",
        "rows": _records(rows),
    }


def get_latest_feature_snapshot(player_id):
    """Return the latest feature row, clearly labelled as a historical snapshot."""
    rows = _read_dataframe(
        """
        SELECT
            season,
            gameweek AS feature_gameweek,
            player_id,
            player_name,
            position,
            team_name,
            next_1gw_fixture_count,
            next_1gw_avg_fdr,
            expected_minutes_next_gw,
            rolling_3gw_points,
            rolling_3gw_minutes,
            rolling_3gw_xgi,
            rolling_3gw_threat,
            rolling_3gw_creativity,
            rolling_3gw_defensive_contribution,
            next_gw_points AS realised_next_gw_points
        FROM public.prediction_features
        WHERE player_id = :player_id
        ORDER BY season DESC, gameweek DESC
        LIMIT 1
        """,
        {"player_id": int(player_id)},
    )
    return {
        "source": (
            "prediction_features (latest historical feature snapshot; "
            "not a live prediction)"
        ),
        "rows": _records(rows),
    }


def get_form_leaderboard(metric="points", position=None, limit=10):
    """Return leaders from the latest available historical feature snapshot."""
    metric = metric.lower()
    if metric not in _FORM_METRICS:
        raise ValueError(f"metric must be one of {sorted(_FORM_METRICS)}.")

    position = position.upper() if position else None
    if position and position not in _FPL_POSITIONS:
        raise ValueError("position must be one of GKP, DEF, MID, or FWD.")

    limit = max(1, min(int(limit), 15))
    metric_column = _FORM_METRICS[metric]
    rows = _read_dataframe(
        f"""
        WITH latest_snapshot AS (
            SELECT season, MAX(gameweek) AS gameweek
            FROM public.prediction_features
            GROUP BY season
            ORDER BY season DESC
            LIMIT 1
        )
        SELECT
            pf.player_id,
            pf.player_name,
            pf.position,
            pf.team_name,
            pf.gameweek AS feature_gameweek,
            pf.{metric_column} AS metric_value,
            pf.rolling_3gw_points,
            pf.rolling_3gw_xgi,
            pf.rolling_3gw_minutes,
            pf.expected_minutes_next_gw,
            pf.next_1gw_fixture_count,
            pf.next_1gw_avg_fdr
        FROM public.prediction_features pf
        INNER JOIN latest_snapshot latest
            ON pf.season = latest.season
           AND pf.gameweek = latest.gameweek
        WHERE (:position IS NULL OR pf.position = :position)
        ORDER BY pf.{metric_column} DESC NULLS LAST, pf.player_name
        LIMIT :limit
        """,
        {"position": position, "limit": limit},
    )
    return {
        "source": (
            "prediction_features (latest historical feature snapshot; "
            "not a live recommendation)"
        ),
        "metric": metric,
        "rows": _records(rows),
    }

# Ranking profiles keep ordinary FPL language position-aware.  They are
# deliberately transparent rather than opaque weighted scores: every profile
# states the first-order metrics used to order the result.
_CURRENT_SEASON_RANKINGS = {
    "attacking": {
        "order_by": (
            "total_xgi DESC NULLS LAST, xgi_per_90 DESC NULLS LAST, "
            "minutes DESC, total_points DESC, player_name"
        ),
        "basis": (
            "Attacking form: total expected goal involvement first, then "
            "xGI per 90 among players who meet the starts threshold."
        ),
    },
    "points": {
        "order_by": "total_points DESC, minutes DESC, player_name",
        "basis": "FPL points leaders among players who meet the starts threshold.",
    },
    "xgi": {
        "order_by": (
            "total_xgi DESC NULLS LAST, xgi_per_90 DESC NULLS LAST, "
            "minutes DESC, player_name"
        ),
        "basis": "Expected goal involvement (xGI), with xGI per 90 as a tiebreaker.",
    },
    "goals": {
        "order_by": "total_goals DESC, minutes DESC, player_name",
        "basis": "Goals scored among players who meet the starts threshold.",
    },
    "assists": {
        "order_by": "total_assists DESC, minutes DESC, player_name",
        "basis": "Assists among players who meet the starts threshold.",
    },
    "threat": {
        "order_by": "total_threat DESC, threat_per_90 DESC NULLS LAST, minutes DESC, player_name",
        "basis": "FPL threat, with threat per 90 as a tiebreaker.",
    },
    "creativity": {
        "order_by": (
            "total_creativity DESC, creativity_per_90 DESC NULLS LAST, "
            "minutes DESC, player_name"
        ),
        "basis": "FPL creativity, with creativity per 90 as a tiebreaker.",
    },
    "defensive": {
        "order_by": (
            "clean_sheet_rate DESC NULLS LAST, "
            "defensive_contribution_per_90 DESC NULLS LAST, "
            "total_clean_sheets DESC, minutes DESC, player_name"
        ),
        "basis": (
            "Defensive form: clean-sheet rate first, then defensive "
            "contribution per 90. Goals and assists do not determine this ranking."
        ),
    },
    "clean_sheets": {
        "order_by": "total_clean_sheets DESC, clean_sheet_rate DESC NULLS LAST, minutes DESC, player_name",
        "basis": "Clean sheets, with clean-sheet rate as a tiebreaker.",
    },
    "defensive_contribution": {
        "order_by": (
            "defensive_contribution_per_90 DESC NULLS LAST, "
            "total_defensive_contribution DESC, minutes DESC, player_name"
        ),
        "basis": "Defensive contribution per 90, then total defensive contribution.",
    },
    "goalkeeping": {
        "order_by": (
            "total_clean_sheets DESC, saves_per_90 DESC NULLS LAST, "
            "goals_conceded_per_90 ASC NULLS LAST, minutes DESC, player_name"
        ),
        "basis": (
            "Goalkeeping form: clean sheets, saves per 90, and fewer goals "
            "conceded per 90. Goals and assists do not determine this ranking."
        ),
    },
}


def compare_fpl_players(player_a_id, player_b_id):
    """Return one comparable live and current-season row for each player."""
    player_a_id = int(player_a_id)
    player_b_id = int(player_b_id)
    if player_a_id == player_b_id:
        raise ValueError("Choose two different FPL players to compare.")

    rows = _read_dataframe(
        """
        WITH latest_live_snapshot AS (
            SELECT MAX(snapshot_at) AS snapshot_at
            FROM public.fpl_live_player_snapshots
        ),
        latest_season AS (
            SELECT MAX(season) AS season
            FROM public.fpl_completed_gameweek_stats
        ),
        season_totals AS (
            SELECT
                player_id,
                SUM(COALESCE(minutes, 0)) AS season_minutes,
                SUM(COALESCE(total_points, 0)) AS season_points,
                SUM(COALESCE(goals_scored, 0)) AS season_goals,
                SUM(COALESCE(assists, 0)) AS season_assists,
                SUM(COALESCE(clean_sheets, 0)) AS season_clean_sheets,
                SUM(COALESCE(bonus, 0)) AS season_bonus,
                SUM(COALESCE(bps, 0)) AS season_bps,
                SUM(COALESCE(defensive_contribution, 0)) AS season_defensive_contribution,
                SUM(COALESCE(saves, 0)) AS season_saves,
                SUM(COALESCE(expected_goal_involvements, 0)) AS season_xgi,
                SUM(COALESCE(expected_goals_conceded, 0)) AS season_xgc
            FROM public.fpl_completed_gameweek_stats
            INNER JOIN latest_season
                ON fpl_completed_gameweek_stats.season = latest_season.season
            WHERE player_id IN (:player_a_id, :player_b_id)
            GROUP BY player_id
        )
        SELECT
            live.player_id,
            COALESCE(live.web_name,
                     CONCAT_WS(' ', live.first_name, live.second_name)) AS player_name,
            live.position,
            live.team_name,
            live.price,
            live.status,
            live.chance_of_playing_next_round,
            live.selected_by_percent,
            live.snapshot_at,
            COALESCE(totals.season_minutes, 0) AS season_minutes,
            COALESCE(totals.season_points, 0) AS season_points,
            COALESCE(totals.season_goals, 0) AS season_goals,
            COALESCE(totals.season_assists, 0) AS season_assists,
            COALESCE(totals.season_clean_sheets, 0) AS season_clean_sheets,
            COALESCE(totals.season_bonus, 0) AS season_bonus,
            COALESCE(totals.season_bps, 0) AS season_bps,
            COALESCE(totals.season_defensive_contribution, 0)
                AS season_defensive_contribution,
            COALESCE(totals.season_saves, 0) AS season_saves,
            COALESCE(totals.season_xgi, 0) AS season_xgi,
            COALESCE(totals.season_xgc, 0) AS season_xgc,
            CASE
                WHEN COALESCE(totals.season_minutes, 0) > 0
                    THEN totals.season_bonus * 90.0 / totals.season_minutes
            END AS season_bonus_per_90,
            CASE
                WHEN COALESCE(totals.season_minutes, 0) > 0
                    THEN totals.season_bps * 90.0 / totals.season_minutes
            END AS season_bps_per_90,
            CASE
                WHEN COALESCE(totals.season_minutes, 0) > 0
                    THEN totals.season_xgi * 90.0 / totals.season_minutes
            END AS season_xgi_per_90,
            CASE
                WHEN COALESCE(totals.season_minutes, 0) > 0
                    THEN totals.season_defensive_contribution * 90.0
                         / totals.season_minutes
            END AS season_defensive_contribution_per_90,
            CASE
                WHEN COALESCE(totals.season_minutes, 0) > 0
                    THEN totals.season_saves * 90.0 / totals.season_minutes
            END AS season_saves_per_90
        FROM public.fpl_live_player_snapshots AS live
        INNER JOIN latest_live_snapshot
            ON live.snapshot_at = latest_live_snapshot.snapshot_at
        LEFT JOIN season_totals AS totals
            ON totals.player_id = live.player_id
        WHERE live.player_id IN (:player_a_id, :player_b_id)
        ORDER BY live.player_id
        """,
        {"player_a_id": player_a_id, "player_b_id": player_b_id},
    )
    return {
        "source": (
            "latest live player snapshot plus finalized current-season "
            "gameweek totals"
        ),
        "rows": _records(rows),
    }


def get_current_season_leaderboard(
    metric="points", position=None, limit=10, minimum_start_rate=0.6
):
    """Rank current-season players using transparent, position-aware profiles."""
    metric = metric.lower()
    if metric not in _CURRENT_SEASON_RANKINGS:
        raise ValueError(
            f"metric must be one of {sorted(_CURRENT_SEASON_RANKINGS)}."
        )

    position = position.upper() if position else None
    if position and position not in _FPL_POSITIONS:
        raise ValueError("position must be one of GKP, DEF, MID, or FWD.")

    limit = max(1, min(int(limit), 15))
    minimum_start_rate = max(0.0, min(float(minimum_start_rate), 1.0))
    profile = _CURRENT_SEASON_RANKINGS[metric]

    rows = _read_dataframe(
        f"""
        WITH latest_season AS (
            SELECT MAX(season) AS season
            FROM public.fpl_completed_gameweek_stats
        ),
        season_context AS (
            SELECT
                stats.season,
                COUNT(DISTINCT stats.gameweek) AS season_completed_gameweeks
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            GROUP BY stats.season
        ),
        totals AS (
            SELECT
                stats.player_id,
                MAX(stats.player_name) AS player_name,
                MAX(stats.position) AS position,
                MAX(stats.team_name) AS team_name,
                COUNT(*) AS completed_gameweeks,
                MAX(season_context.season_completed_gameweeks)
                    AS season_completed_gameweeks,
                SUM(COALESCE(stats.fixture_count, 0)) AS fixtures,
                SUM(COALESCE(stats.minutes, 0)) AS minutes,
                SUM(COALESCE(stats.starts, 0)) AS starts,
                SUM(COALESCE(stats.total_points, 0)) AS total_points,
                SUM(COALESCE(stats.goals_scored, 0)) AS total_goals,
                SUM(COALESCE(stats.assists, 0)) AS total_assists,
                SUM(COALESCE(stats.clean_sheets, 0)) AS total_clean_sheets,
                SUM(COALESCE(stats.bonus, 0)) AS total_bonus,
                SUM(COALESCE(stats.bps, 0)) AS total_bps,
                SUM(COALESCE(stats.goals_conceded, 0)) AS total_goals_conceded,
                SUM(COALESCE(stats.saves, 0)) AS total_saves,
                SUM(COALESCE(stats.defensive_contribution, 0))
                    AS total_defensive_contribution,
                SUM(COALESCE(stats.expected_goal_involvements, 0)) AS total_xgi,
                SUM(COALESCE(stats.expected_goals_conceded, 0)) AS total_xgc,
                SUM(COALESCE(stats.threat, 0)) AS total_threat,
                SUM(COALESCE(stats.creativity, 0)) AS total_creativity
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            INNER JOIN season_context
                ON stats.season = season_context.season
            WHERE (:position IS NULL OR stats.position = :position)
            GROUP BY stats.player_id
        ),
        eligible AS (
            SELECT
                *,
                GREATEST(
                    1,
                    CEIL(season_completed_gameweeks * :minimum_start_rate)
                )::integer AS minimum_starts_required,
                CASE WHEN fixtures > 0
                    THEN total_clean_sheets * 1.0 / fixtures
                END AS clean_sheet_rate,
                CASE WHEN minutes > 0
                    THEN total_defensive_contribution * 90.0 / minutes
                END AS defensive_contribution_per_90,
                CASE WHEN minutes > 0
                    THEN total_saves * 90.0 / minutes
                END AS saves_per_90,
                CASE WHEN minutes > 0
                    THEN total_goals_conceded * 90.0 / minutes
                END AS goals_conceded_per_90,
                CASE WHEN minutes > 0
                    THEN total_xgc * 90.0 / minutes
                END AS xgc_per_90,
                CASE WHEN minutes > 0
                    THEN total_bonus * 90.0 / minutes
                END AS bonus_per_90,
                CASE WHEN minutes > 0
                    THEN total_bps * 90.0 / minutes
                END AS bps_per_90,
                CASE WHEN minutes > 0
                    THEN total_xgi * 90.0 / minutes
                END AS xgi_per_90,
                CASE WHEN minutes > 0
                    THEN total_threat * 90.0 / minutes
                END AS threat_per_90,
                CASE WHEN minutes > 0
                    THEN total_creativity * 90.0 / minutes
                END AS creativity_per_90
            FROM totals
        ),
        ranked AS (
            SELECT *
            FROM eligible
            WHERE starts >= minimum_starts_required
        )
        SELECT *
        FROM ranked
        ORDER BY {profile["order_by"]}
        LIMIT :limit
        """,
        {
            "position": position,
            "limit": limit,
            "minimum_start_rate": minimum_start_rate,
        },
    )
    return {
        "source": (
            "fpl_completed_gameweek_stats (finalized current-season "
            "gameweek totals)"
        ),
        "metric": metric,
        "ranking_basis": profile["basis"],
        "minimum_start_rate": minimum_start_rate,
        "minimum_starts": (
            rows.iloc[0]["minimum_starts_required"] if not rows.empty else None
        ),
        "rows": _records(rows),
    }



def get_fpl_pick_leaderboard(
    position, max_price=None, horizon=5, form_gameweeks=3, limit=10
):
    """Rank non-personal FPL pick candidates from live and finalized data.

    This is a transparent candidate ranking, not personalised transfer advice.
    It requires availability, a minimum recent-starts threshold, and combines
    position-specific finalized form with the team's upcoming FPL difficulty.
    """
    position = str(position).upper()
    profiles = {
        "MID": {
            "order_by": (
                "form_xgi DESC NULLS LAST, form_xgi_per_90 DESC NULLS LAST, "
                "average_fdr ASC NULLS LAST, form_points_per_price DESC NULLS LAST, "
                "price ASC, player_name"
            ),
            "basis": (
                "Midfield picks: recent xGI first, then xGI per 90, easier "
                "upcoming fixtures, and recent points per £m."
            ),
        },
        "DEF": {
            "order_by": (
                "form_clean_sheet_rate DESC NULLS LAST, "
                "form_defensive_contribution_per_90 DESC NULLS LAST, "
                "average_fdr ASC NULLS LAST, form_points_per_price DESC NULLS LAST, "
                "price ASC, player_name"
            ),
            "basis": (
                "Defender picks: recent clean-sheet rate first, then defensive "
                "contribution per 90, easier upcoming fixtures, and recent "
                "points per £m."
            ),
        },
    }
    if position not in profiles:
        raise ValueError("position must be MID or DEF for FPL pick rankings.")

    horizon = max(1, min(int(horizon), 8))
    form_gameweeks = max(1, min(int(form_gameweeks), 10))
    limit = max(1, min(int(limit), 15))
    if max_price is not None:
        max_price = max(3.0, min(float(max_price), 20.0))

    profile = profiles[position]
    rows = _read_dataframe(
        f"""
        WITH latest_live AS (
            SELECT *
            FROM public.fpl_live_player_snapshots
            WHERE snapshot_at = (
                SELECT MAX(snapshot_at)
                FROM public.fpl_live_player_snapshots
            )
        ),
        latest_season AS (
            SELECT MAX(season) AS season
            FROM public.fpl_completed_gameweek_stats
        ),
        recent_gameweeks AS (
            SELECT DISTINCT stats.gameweek
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            ORDER BY stats.gameweek DESC
            LIMIT :form_gameweeks
        ),
        form_stats AS (
            SELECT
                stats.player_id,
                SUM(COALESCE(stats.fixture_count, 0)) AS form_fixtures,
                SUM(COALESCE(stats.minutes, 0)) AS form_minutes,
                SUM(COALESCE(stats.starts, 0)) AS form_starts,
                SUM(COALESCE(stats.total_points, 0)) AS form_points,
                SUM(COALESCE(stats.bonus, 0)) AS form_bonus,
                SUM(COALESCE(stats.expected_goal_involvements, 0)) AS form_xgi,
                SUM(COALESCE(stats.clean_sheets, 0)) AS form_clean_sheets,
                SUM(COALESCE(stats.defensive_contribution, 0))
                    AS form_defensive_contribution
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            INNER JOIN recent_gameweeks
                ON stats.gameweek = recent_gameweeks.gameweek
            GROUP BY stats.player_id
        ),
        season_stats AS (
            SELECT
                stats.player_id,
                SUM(COALESCE(stats.fixture_count, 0)) AS season_fixtures,
                SUM(COALESCE(stats.minutes, 0)) AS season_minutes,
                SUM(COALESCE(stats.starts, 0)) AS season_starts,
                SUM(COALESCE(stats.total_points, 0)) AS season_points,
                SUM(COALESCE(stats.goals_scored, 0)) AS season_goals,
                SUM(COALESCE(stats.assists, 0)) AS season_assists,
                SUM(COALESCE(stats.bonus, 0)) AS season_bonus,
                SUM(COALESCE(stats.expected_goal_involvements, 0)) AS season_xgi
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            GROUP BY stats.player_id
        ),
        live_teams AS (
            SELECT DISTINCT team_id, team_name
            FROM latest_live
        ),
        team_fixtures AS (
            SELECT
                teams.team_id,
                fixtures.kickoff_time,
                fixtures.gameweek,
                fixtures.away_team_name AS opponent_team_name,
                fixtures.home_difficulty AS fixture_difficulty,
                'H' AS venue
            FROM live_teams AS teams
            INNER JOIN public.fpl_fixtures AS fixtures
                ON fixtures.home_team_id = teams.team_id
            WHERE COALESCE(fixtures.finished, false) = false
              AND fixtures.kickoff_time >= now()

            UNION ALL

            SELECT
                teams.team_id,
                fixtures.kickoff_time,
                fixtures.gameweek,
                fixtures.home_team_name AS opponent_team_name,
                fixtures.away_difficulty AS fixture_difficulty,
                'A' AS venue
            FROM live_teams AS teams
            INNER JOIN public.fpl_fixtures AS fixtures
                ON fixtures.away_team_id = teams.team_id
            WHERE COALESCE(fixtures.finished, false) = false
              AND fixtures.kickoff_time >= now()
        ),
        ranked_team_fixtures AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY team_id
                    ORDER BY kickoff_time, gameweek
                ) AS fixture_number
            FROM team_fixtures
        ),
        fixture_horizon AS (
            SELECT
                team_id,
                ROUND(AVG(fixture_difficulty)::numeric, 2) AS average_fdr,
                STRING_AGG(
                    opponent_team_name || ' (' || venue || ')',
                    ', ' ORDER BY kickoff_time
                ) AS upcoming_fixtures
            FROM ranked_team_fixtures
            WHERE fixture_number <= :horizon
            GROUP BY team_id
        ),
        candidates AS (
            SELECT
                live.player_id,
                COALESCE(live.web_name,
                         CONCAT_WS(' ', live.first_name, live.second_name))
                    AS player_name,
                live.team_name,
                live.position,
                live.price,
                live.status,
                live.total_points AS live_total_points,
                live.form AS live_form,
                live.selected_by_percent,
                live.chance_of_playing_next_round,
                season.season_fixtures,
                season.season_minutes,
                season.season_starts,
                season.season_points,
                season.season_goals,
                season.season_assists,
                season.season_bonus,
                season.season_xgi,
                form.form_fixtures,
                form.form_minutes,
                form.form_starts,
                form.form_points,
                form.form_bonus,
                form.form_xgi,
                form.form_clean_sheets,
                form.form_defensive_contribution,
                fixture.average_fdr,
                fixture.upcoming_fixtures,
                CASE WHEN form.form_minutes > 0
                    THEN form.form_xgi * 90.0 / form.form_minutes
                END AS form_xgi_per_90,
                CASE WHEN form.form_fixtures > 0
                    THEN form.form_clean_sheets * 1.0 / form.form_fixtures
                END AS form_clean_sheet_rate,
                CASE WHEN form.form_minutes > 0
                    THEN form.form_defensive_contribution * 90.0 / form.form_minutes
                END AS form_defensive_contribution_per_90,
                CASE WHEN live.price > 0
                    THEN form.form_points * 1.0 / live.price
                END AS form_points_per_price
            FROM latest_live AS live
            INNER JOIN form_stats AS form
                ON form.player_id = live.player_id
            INNER JOIN season_stats AS season
                ON season.player_id = live.player_id
            INNER JOIN fixture_horizon AS fixture
                ON fixture.team_id = live.team_id
            WHERE live.position = :position
              AND COALESCE(live.status, 'a') = 'a'
              AND (:max_price IS NULL OR live.price <= :max_price)
              AND form.form_starts >= LEAST(
                  2, (SELECT COUNT(*) FROM recent_gameweeks)
              )
        )
        SELECT *
        FROM candidates
        ORDER BY {profile["order_by"]}
        LIMIT :limit
        """,
        {
            "position": position,
            "max_price": max_price,
            "horizon": horizon,
            "form_gameweeks": form_gameweeks,
            "limit": limit,
        },
    )
    return {
        "source": (
            "latest stored live player snapshot, finalized current-season "
            "gameweek totals, and stored live fixtures"
        ),
        "position": position,
        "max_price": max_price,
        "horizon": horizon,
        "form_gameweeks": form_gameweeks,
        "ranking_basis": profile["basis"],
        "minimum_recent_starts": min(2, form_gameweeks),
        "rows": _records(rows),
    }

def get_fpl_data_status():
    """Describe historical coverage and the newest stored live FPL snapshot."""
    players = _read_dataframe(
        "SELECT COUNT(*) AS player_count FROM public.players"
    )
    history = _read_dataframe(
        """
        SELECT MAX(season) AS latest_historical_season,
               MAX(gameweek) AS latest_historical_gameweek,
               COUNT(*) AS historical_rows
        FROM public.player_gameweek
        """
    )
    completed_gameweeks = _read_dataframe(
        """
        SELECT MAX(season) AS latest_completed_season,
               MAX(gameweek) AS latest_completed_gameweek,
               COUNT(*) AS completed_gameweek_player_rows
        FROM public.fpl_completed_gameweek_stats
        """
    )
    features = _read_dataframe(
        """
        SELECT MAX(season) AS latest_feature_season,
               MAX(gameweek) AS latest_feature_gameweek,
               COUNT(*) AS feature_rows
        FROM public.prediction_features
        """
    )
    live = _read_dataframe(
        """
        SELECT snapshot_at AS latest_live_snapshot_at,
               current_gameweek,
               COUNT(*) AS player_snapshot_rows
        FROM public.fpl_live_player_snapshots
        WHERE snapshot_at = (
            SELECT MAX(snapshot_at) FROM public.fpl_live_player_snapshots
        )
        GROUP BY snapshot_at, current_gameweek
        """
    )
    fixtures = _read_dataframe(
        """
        SELECT MAX(updated_at) AS latest_fixture_refresh_at,
               COUNT(*) FILTER (WHERE COALESCE(finished, false) = false)
                   AS upcoming_fixture_rows
        FROM public.fpl_fixtures
        """
    )
    refresh = _read_dataframe(
        """
        SELECT status, completed_at, current_gameweek, latest_finished_gameweek,
               player_snapshot_rows, fixture_rows, message
        FROM public.fpl_refresh_runs
        ORDER BY refresh_id DESC
        LIMIT 1
        """
    )
    return {
        "source": "database coverage and live refresh metadata",
        "players": _records(players),
        "historical_data": _records(history),
        "completed_gameweek_data": _records(completed_gameweeks),
        "feature_data": _records(features),
        "live_snapshot": _records(live),
        "live_fixtures": _records(fixtures),
        "latest_refresh": _records(refresh),
    }


# ============================================================
# LIVE FPL SNAPSHOTS AND REFRESH AUDIT
# ============================================================


def _database_records(frame):
    """Convert a dataframe to database-ready records with SQL NULLs."""
    return (
        frame.astype(object)
        .where(pd.notna(frame), None)
        .to_dict(orient="records")
    )


def save_live_fpl_snapshot(players, fixtures, team_names, current_gameweek,
                           latest_finished_gameweek):
    """Save one immutable player snapshot and the current fixture state.

    The mutable players table remains useful for quick lookups; this function
    additionally preserves an as-of snapshot and a refresh audit record.
    """
    snapshot_at = pd.Timestamp.now(tz="UTC").to_pydatetime()
    players = players.copy()
    fixtures = fixtures.copy()

    snapshot_frame = pd.DataFrame({
        "snapshot_at": snapshot_at,
        "player_id": pd.to_numeric(players["id"], errors="coerce"),
        "first_name": players.get("first_name"),
        "second_name": players.get("second_name"),
        "web_name": players.get("web_name"),
        "team_id": pd.to_numeric(players["team"], errors="coerce"),
        "team_name": players.get("team_name"),
        "position": players.get("position"),
        "price": pd.to_numeric(players.get("price"), errors="coerce"),
        "total_points": pd.to_numeric(
            players.get("total_points"), errors="coerce"
        ),
        "form": pd.to_numeric(players.get("form"), errors="coerce"),
        "selected_by_percent": pd.to_numeric(
            players.get("selected_by_percent"), errors="coerce"
        ),
        "status": players.get("status"),
        "chance_of_playing_next_round": pd.to_numeric(
            players.get("chance_of_playing_next_round"), errors="coerce"
        ),
        "news": players.get("news"),
        "current_gameweek": current_gameweek,
    }).dropna(subset=["player_id"])

    fixture_frame = pd.DataFrame({
        "fixture_id": pd.to_numeric(fixtures.get("id"), errors="coerce"),
        "gameweek": pd.to_numeric(fixtures.get("event"), errors="coerce"),
        "kickoff_time": fixtures.get("kickoff_time"),
        "started": fixtures.get("started"),
        "finished": fixtures.get("finished"),
        "finished_provisional": fixtures.get("finished_provisional"),
        "home_team_id": pd.to_numeric(fixtures.get("team_h"), errors="coerce"),
        "home_team_name": fixtures.get("team_h").map(team_names),
        "away_team_id": pd.to_numeric(fixtures.get("team_a"), errors="coerce"),
        "away_team_name": fixtures.get("team_a").map(team_names),
        "home_difficulty": pd.to_numeric(
            fixtures.get("team_h_difficulty"), errors="coerce"
        ),
        "away_difficulty": pd.to_numeric(
            fixtures.get("team_a_difficulty"), errors="coerce"
        ),
    }).dropna(subset=["fixture_id"])

    snapshot_frame["player_id"] = snapshot_frame["player_id"].astype(int)
    fixture_frame["fixture_id"] = fixture_frame["fixture_id"].astype(int)
    fixture_frame["gameweek"] = fixture_frame["gameweek"].astype("Int64")

    snapshot_records = _database_records(snapshot_frame)
    fixture_records = _database_records(fixture_frame)
    conn = get_database_connection()

    snapshot_sql = text(
        """
        INSERT INTO public.fpl_live_player_snapshots (
            snapshot_at, player_id, first_name, second_name, web_name,
            team_id, team_name, position, price, total_points, form,
            selected_by_percent, status, chance_of_playing_next_round, news,
            current_gameweek
        )
        VALUES (
            :snapshot_at, :player_id, :first_name, :second_name, :web_name,
            :team_id, :team_name, :position, :price, :total_points, :form,
            :selected_by_percent, :status, :chance_of_playing_next_round,
            :news, :current_gameweek
        )
        """
    )
    fixture_sql = text(
        """
        INSERT INTO public.fpl_fixtures (
            fixture_id, gameweek, kickoff_time, started, finished,
            finished_provisional, home_team_id, home_team_name, away_team_id,
            away_team_name, home_difficulty, away_difficulty, updated_at
        )
        VALUES (
            :fixture_id, :gameweek, :kickoff_time, :started, :finished,
            :finished_provisional, :home_team_id, :home_team_name,
            :away_team_id, :away_team_name, :home_difficulty,
            :away_difficulty, now()
        )
        ON CONFLICT (fixture_id)
        DO UPDATE SET
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
            updated_at = now()
        """
    )
    run_sql = text(
        """
        INSERT INTO public.fpl_refresh_runs (
            refresh_type, status, completed_at, source, current_gameweek,
            latest_finished_gameweek, player_snapshot_rows, fixture_rows,
            message
        )
        VALUES (
            'live_snapshot', 'completed', now(), :source, :current_gameweek,
            :latest_finished_gameweek, :player_snapshot_rows, :fixture_rows,
            'Live player snapshot and fixtures refreshed successfully.'
        )
        """
    )
    failed_run_sql = text(
        """
        INSERT INTO public.fpl_refresh_runs (
            refresh_type, status, completed_at, source, current_gameweek,
            latest_finished_gameweek, message
        )
        VALUES (
            'live_snapshot', 'failed', now(), 'FPL bootstrap-static + fixtures',
            :current_gameweek, :latest_finished_gameweek, :message
        )
        """
    )

    try:
        # Keep the existing current-player lookup table current as well.
        save_players(players)
        with conn.session as session:
            for start in range(0, len(snapshot_records), 500):
                session.execute(snapshot_sql, snapshot_records[start:start + 500])
            for start in range(0, len(fixture_records), 500):
                session.execute(fixture_sql, fixture_records[start:start + 500])
            session.execute(
                run_sql,
                {
                    "source": "FPL bootstrap-static + fixtures",
                    "current_gameweek": current_gameweek,
                    "latest_finished_gameweek": latest_finished_gameweek,
                    "player_snapshot_rows": len(snapshot_records),
                    "fixture_rows": len(fixture_records),
                },
            )
            session.commit()
    except Exception as error:
        try:
            with conn.session as session:
                session.execute(
                    failed_run_sql,
                    {
                        "current_gameweek": current_gameweek,
                        "latest_finished_gameweek": latest_finished_gameweek,
                        "message": str(error)[:1000],
                    },
                )
                session.commit()
        except Exception:
            pass
        raise

    return {
        "snapshot_at": snapshot_at.isoformat(),
        "player_snapshot_rows": len(snapshot_records),
        "fixture_rows": len(fixture_records),
        "current_gameweek": current_gameweek,
        "latest_finished_gameweek": latest_finished_gameweek,
    }


def get_live_player_profile(player_id):
    """Return the newest stored live snapshot for a player."""
    rows = _read_dataframe(
        """
        WITH latest_season AS (
            SELECT MAX(season) AS season
            FROM public.fpl_completed_gameweek_stats
        ),
        season_totals AS (
            SELECT
                stats.player_id,
                SUM(COALESCE(stats.bonus, 0)) AS season_bonus,
                SUM(COALESCE(stats.bps, 0)) AS season_bps,
                SUM(COALESCE(stats.minutes, 0)) AS season_minutes
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            WHERE stats.player_id = :player_id
            GROUP BY stats.player_id
        )
        SELECT
            live.snapshot_at, live.player_id,
            live.first_name || ' ' || live.second_name AS player_name,
            live.web_name, live.team_name, live.position, live.price,
            live.total_points, live.form, live.selected_by_percent, live.status,
            live.chance_of_playing_next_round, live.news, live.current_gameweek,
            COALESCE(totals.season_bonus, 0) AS season_bonus,
            COALESCE(totals.season_bps, 0) AS season_bps,
            CASE WHEN COALESCE(totals.season_minutes, 0) > 0
                THEN totals.season_bonus * 90.0 / totals.season_minutes
            END AS season_bonus_per_90
        FROM public.fpl_live_player_snapshots AS live
        LEFT JOIN season_totals AS totals
            ON totals.player_id = live.player_id
        WHERE live.player_id = :player_id
        ORDER BY live.snapshot_at DESC
        LIMIT 1
        """,
        {"player_id": int(player_id)},
    )
    return {
        "source": "fpl_live_player_snapshots (latest stored live FPL snapshot)",
        "rows": _records(rows),
    }


def get_player_upcoming_fixtures(player_id, limit=5):
    """Return the next stored fixtures for a player based on the latest snapshot."""
    limit = max(1, min(int(limit), 8))
    rows = _read_dataframe(
        """
        WITH latest_player AS (
            SELECT DISTINCT ON (player_id)
                player_id, team_id, team_name, snapshot_at
            FROM public.fpl_live_player_snapshots
            WHERE player_id = :player_id
            ORDER BY player_id, snapshot_at DESC
        )
        SELECT
            lp.snapshot_at,
            ff.gameweek,
            ff.kickoff_time,
            CASE
                WHEN ff.home_team_id = lp.team_id THEN 'home'
                ELSE 'away'
            END AS venue,
            CASE
                WHEN ff.home_team_id = lp.team_id THEN ff.away_team_name
                ELSE ff.home_team_name
            END AS opponent_team_name,
            CASE
                WHEN ff.home_team_id = lp.team_id THEN ff.home_difficulty
                ELSE ff.away_difficulty
            END AS fixture_difficulty
        FROM latest_player lp
        JOIN public.fpl_fixtures ff
          ON ff.home_team_id = lp.team_id OR ff.away_team_id = lp.team_id
        WHERE COALESCE(ff.finished, false) = false
          AND ff.kickoff_time >= now()
        ORDER BY ff.kickoff_time
        LIMIT :limit
        """,
        {"player_id": int(player_id), "limit": limit},
    )
    return {
        "source": "fpl_fixtures + fpl_live_player_snapshots (stored live data)",
        "rows": _records(rows),
    }


def get_team_fixture_horizon(horizon=5, limit=10):
    """Rank teams by the average FPL difficulty of their next fixtures."""
    horizon = max(1, min(int(horizon), 8))
    limit = max(1, min(int(limit), 15))
    rows = _read_dataframe(
        """
        WITH team_fixtures AS (
            SELECT
                home_team_id AS team_id,
                home_team_name AS team_name,
                gameweek,
                kickoff_time,
                away_team_name AS opponent_team_name,
                home_difficulty AS fixture_difficulty,
                'home' AS venue
            FROM public.fpl_fixtures
            WHERE COALESCE(finished, false) = false
              AND kickoff_time >= now()

            UNION ALL

            SELECT
                away_team_id AS team_id,
                away_team_name AS team_name,
                gameweek,
                kickoff_time,
                home_team_name AS opponent_team_name,
                away_difficulty AS fixture_difficulty,
                'away' AS venue
            FROM public.fpl_fixtures
            WHERE COALESCE(finished, false) = false
              AND kickoff_time >= now()
        ),
        ranked_fixtures AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY team_id
                    ORDER BY kickoff_time, gameweek
                ) AS fixture_number
            FROM team_fixtures
        )
        SELECT
            team_name,
            COUNT(*) AS fixture_count,
            ROUND(AVG(fixture_difficulty)::numeric, 2) AS average_fdr,
            SUM(CASE WHEN venue = 'home' THEN 1 ELSE 0 END) AS home_fixtures,
            SUM(CASE WHEN venue = 'away' THEN 1 ELSE 0 END) AS away_fixtures,
            STRING_AGG(
                opponent_team_name || CASE
                    WHEN venue = 'home' THEN ' (H)'
                    ELSE ' (A)'
                END,
                ', ' ORDER BY kickoff_time
            ) AS upcoming_fixtures
        FROM ranked_fixtures
        WHERE fixture_number <= :horizon
        GROUP BY team_id, team_name
        ORDER BY average_fdr ASC, team_name ASC
        LIMIT :limit
        """,
        {"horizon": horizon, "limit": limit},
    )
    return {
        "source": "fpl_fixtures (stored live fixture schedule)",
        "horizon": horizon,
        "ranking_basis": (
            "lowest average official FPL fixture difficulty over the next "
            f"{horizon} fixtures"
        ),
        "rows": _records(rows),
    }


def get_team_strength_leaderboard(metric="attacking", gameweeks=5, limit=10):
    """Rank current-season teams using finalized player-gameweek totals only."""
    metric = str(metric).lower()
    profiles = {
        "attacking": {
            "order_by": "expected_goals DESC, goals_scored DESC, team_name ASC",
            "basis": "recent attacking form: expected goals first, then goals scored",
        },
        "defensive": {
            "order_by": (
                "clean_sheet_rate DESC, clean_sheets DESC, team_name ASC"
            ),
            "basis": (
                "recent defensive form: clean-sheet rate first, then total "
                "clean sheets"
            ),
        },
    }
    if metric not in profiles:
        raise ValueError("metric must be 'attacking' or 'defensive'")

    gameweeks = max(1, min(int(gameweeks), 10))
    limit = max(1, min(int(limit), 15))
    profile = profiles[metric]
    rows = _read_dataframe(
        f"""
        WITH latest_season AS (
            SELECT season
            FROM public.fpl_completed_gameweek_stats
            ORDER BY season DESC
            LIMIT 1
        ),
        recent_gameweeks AS (
            SELECT DISTINCT stats.gameweek
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            ORDER BY stats.gameweek DESC
            LIMIT :gameweeks
        ),
        team_gameweeks AS (
            SELECT
                stats.team_id,
                MAX(stats.team_name) AS team_name,
                stats.gameweek,
                MAX(COALESCE(stats.fixture_count, 1)) AS fixtures,
                SUM(COALESCE(stats.goals_scored, 0)) AS goals_scored,
                SUM(COALESCE(stats.expected_goals, 0)) AS expected_goals,
                MAX(COALESCE(stats.clean_sheets, 0)) AS clean_sheets
            FROM public.fpl_completed_gameweek_stats AS stats
            INNER JOIN latest_season
                ON stats.season = latest_season.season
            INNER JOIN recent_gameweeks
                ON stats.gameweek = recent_gameweeks.gameweek
            GROUP BY stats.team_id, stats.gameweek
        ),
        team_totals AS (
            SELECT
                team_id,
                MAX(team_name) AS team_name,
                SUM(fixtures) AS fixtures,
                SUM(goals_scored) AS goals_scored,
                SUM(expected_goals) AS expected_goals,
                SUM(clean_sheets) AS clean_sheets
            FROM team_gameweeks
            GROUP BY team_id
        )
        SELECT
            team_name,
            fixtures,
            goals_scored,
            ROUND(expected_goals::numeric, 2) AS expected_goals,
            clean_sheets,
            ROUND(
                clean_sheets * 1.0 / NULLIF(fixtures, 0), 2
            ) AS clean_sheet_rate,
            ROUND(
                goals_scored * 1.0 / NULLIF(fixtures, 0), 2
            ) AS goals_per_fixture,
            ROUND(
                expected_goals * 1.0 / NULLIF(fixtures, 0), 2
            ) AS expected_goals_per_fixture
        FROM team_totals
        ORDER BY {profile["order_by"]}
        LIMIT :limit
        """,
        {"gameweeks": gameweeks, "limit": limit},
    )
    return {
        "source": (
            "fpl_completed_gameweek_stats (finalized current-season "
            "player-gameweek totals)"
        ),
        "metric": metric,
        "gameweeks": gameweeks,
        "ranking_basis": profile["basis"],
        "rows": _records(rows),
    }
