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
    "rolling_10gw_start_rate", "next_gw_points",
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
