import streamlit as st
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


def save_prediction_features(features):

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
