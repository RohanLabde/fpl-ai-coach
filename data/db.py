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
    """Find current player records by name, with fixed query limits."""
    position = position.upper() if position else None
    if position and position not in _FPL_POSITIONS:
        raise ValueError("position must be one of GKP, DEF, MID, or FWD.")

    limit = max(1, min(int(limit), 10))
    rows = _read_dataframe(
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
        {
            "name_pattern": f"%{query.strip()}%",
            "position": position,
            "limit": limit,
        },
    )
    return {
        "source": "players (latest imported FPL player snapshot)",
        "rows": _records(rows),
    }


def get_player_recent_form(player_id, gameweeks=5):
    """Return the most recent historical gameweeks for one player."""
    gameweeks = max(1, min(int(gameweeks), 10))
    rows = _read_dataframe(
        """
        SELECT
            season,
            gameweek,
            player_name,
            position,
            team_name,
            opponent_team_id,
            was_home,
            minutes,
            total_points,
            goals_scored,
            assists,
            clean_sheets,
            expected_goals,
            expected_assists,
            expected_goal_involvements,
            creativity,
            threat,
            defensive_contribution
        FROM public.player_gameweek
        WHERE player_id = :player_id
        ORDER BY season DESC, gameweek DESC, fixture_id DESC
        LIMIT :limit
        """,
        {"player_id": int(player_id), "limit": gameweeks},
    )
    return {
        "source": "player_gameweek (historical fixture-level data)",
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


def get_fpl_data_status():
    """Describe data freshness so the assistant never implies live coverage."""
    players = _read_dataframe(
        """
        SELECT COUNT(*) AS player_count
        FROM public.players
        """
    )
    history = _read_dataframe(
        """
        SELECT
            MAX(season) AS latest_historical_season,
            MAX(gameweek) AS latest_historical_gameweek,
            COUNT(*) AS historical_rows
        FROM public.player_gameweek
        """
    )
    features = _read_dataframe(
        """
        SELECT
            MAX(season) AS latest_feature_season,
            MAX(gameweek) AS latest_feature_gameweek,
            COUNT(*) AS feature_rows
        FROM public.prediction_features
        """
    )
    return {
        "source": "database coverage metadata",
        "players": _records(players),
        "historical_data": _records(history),
        "feature_data": _records(features),
    }
