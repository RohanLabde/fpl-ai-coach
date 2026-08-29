import pandas as pd


def build_team_gameweek_calendar(fixtures):
    """
    Build the complete Team × Gameweek fixture calendar.

    This is the authoritative source for determining whether
    a team has:

        0 fixtures = Blank Gameweek (BGW)
        1 fixture  = Normal Gameweek
        2+ fixtures = Double/Multiple Gameweek

    IMPORTANT:
    This function only builds and validates the calendar.

    It does NOT modify player performance data.
    """

    fixtures = fixtures.copy()

    # ---------------------------------------
    # 1. Validate required columns
    # ---------------------------------------

    required_columns = [
        "event",
        "team_h",
        "team_a"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in fixtures.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing columns required to build "
            f"team-gameweek calendar: {missing_columns}"
        )

    # ---------------------------------------
    # 2. Keep fixtures with a valid gameweek
    # ---------------------------------------

    fixtures = fixtures[
        fixtures["event"].notna()
    ].copy()

    # ---------------------------------------
    # 3. Convert identifiers to numeric
    # ---------------------------------------

    fixtures["gameweek"] = pd.to_numeric(
        fixtures["event"],
        errors="coerce"
    )

    fixtures["home_team_id"] = pd.to_numeric(
        fixtures["team_h"],
        errors="coerce"
    )

    fixtures["away_team_id"] = pd.to_numeric(
        fixtures["team_a"],
        errors="coerce"
    )

    fixtures = fixtures.dropna(
        subset=[
            "gameweek",
            "home_team_id",
            "away_team_id"
        ]
    ).copy()

    fixtures["gameweek"] = (
        fixtures["gameweek"]
        .astype(int)
    )

    fixtures["home_team_id"] = (
        fixtures["home_team_id"]
        .astype(int)
    )

    fixtures["away_team_id"] = (
        fixtures["away_team_id"]
        .astype(int)
    )

    # ---------------------------------------
    # 4. Create one row for every
    #    team participating in a fixture
    #
    # Home fixture:
    #
    # GW | Team
    #
    # Away fixture:
    #
    # GW | Team
    # ---------------------------------------

    home_fixtures = fixtures[
        [
            "gameweek",
            "home_team_id"
        ]
    ].rename(
        columns={
            "home_team_id": "team_id"
        }
    )

    away_fixtures = fixtures[
        [
            "gameweek",
            "away_team_id"
        ]
    ].rename(
        columns={
            "away_team_id": "team_id"
        }
    )

    team_fixtures = pd.concat(
        [
            home_fixtures,
            away_fixtures
        ],
        ignore_index=True
    )

    # ---------------------------------------
    # 5. Count fixtures per team per GW
    # ---------------------------------------

    fixture_counts = (
        team_fixtures
        .groupby(
            [
                "gameweek",
                "team_id"
            ],
            as_index=False
        )
        .size()
        .rename(
            columns={
                "size": "fixture_count"
            }
        )
    )

    # ---------------------------------------
    # 6. Build complete Team × Gameweek grid
    #
    # This is important.
    #
    # groupby() alone cannot show BGWs because
    # a team with zero fixtures does not appear.
    #
    # The complete grid explicitly creates those
    # combinations.
    # ---------------------------------------

    all_gameweeks = sorted(
        fixtures["gameweek"]
        .unique()
    )

    all_teams = sorted(
        pd.concat(
            [
                fixtures["home_team_id"],
                fixtures["away_team_id"]
            ],
            ignore_index=True
        )
        .unique()
    )

    complete_calendar = (
        pd.MultiIndex
        .from_product(
            [
                all_gameweeks,
                all_teams
            ],
            names=[
                "gameweek",
                "team_id"
            ]
        )
        .to_frame(
            index=False
        )
    )

    # ---------------------------------------
    # 7. Join actual fixture counts
    # ---------------------------------------

    calendar = complete_calendar.merge(
        fixture_counts,
        on=[
            "gameweek",
            "team_id"
        ],
        how="left"
    )

    # No fixture = zero fixtures

    calendar["fixture_count"] = (
        calendar["fixture_count"]
        .fillna(0)
        .astype(int)
    )

    # ---------------------------------------
    # 8. Create fixture-status flag
    # ---------------------------------------

    calendar["has_fixture"] = (
        calendar["fixture_count"] > 0
    )

    # ---------------------------------------
    # 9. Classify gameweek type
    # ---------------------------------------

    calendar["gameweek_type"] = "BGW"

    calendar.loc[
        calendar["fixture_count"] == 1,
        "gameweek_type"
    ] = "NORMAL"

    calendar.loc[
        calendar["fixture_count"] >= 2,
        "gameweek_type"
    ] = "DGW"

    # ---------------------------------------
    # 10. Sort
    # ---------------------------------------

    calendar = calendar.sort_values(
        [
            "gameweek",
            "team_id"
        ]
    ).reset_index(
        drop=True
    )

    # ---------------------------------------
    # 11. Validation
    # ---------------------------------------

    expected_rows = (
        len(all_gameweeks)
        * len(all_teams)
    )

    actual_rows = len(calendar)

    if actual_rows != expected_rows:

        raise ValueError(
            "Team-gameweek calendar has an "
            "unexpected number of rows. "
            f"Expected {expected_rows}, "
            f"got {actual_rows}."
        )

    duplicate_count = (
        calendar
        .duplicated(
            subset=[
                "gameweek",
                "team_id"
            ]
        )
        .sum()
    )

    if duplicate_count > 0:

        raise ValueError(
            "Team-gameweek calendar contains "
            f"{duplicate_count} duplicate keys."
        )

    # ---------------------------------------
    # 12. Debug output
    # ---------------------------------------

    print(
        "DEBUG calendar gameweeks:",
        len(all_gameweeks)
    )

    print(
        "DEBUG calendar teams:",
        len(all_teams)
    )

    print(
        "DEBUG calendar rows:",
        len(calendar)
    )

    print(
        "DEBUG normal team-gameweeks:",
        (
            calendar["gameweek_type"] == "NORMAL"
        ).sum()
    )

    print(
        "DEBUG double-gameweek team rows:",
        (
            calendar["gameweek_type"] == "DGW"
        ).sum()
    )

    print(
        "DEBUG blank-gameweek team rows:",
        (
            calendar["gameweek_type"] == "BGW"
        ).sum()
    )

    return calendar

def build_player_gameweek_data(
    historical,
    team_gameweek_calendar
):
    """
    Convert fixture-level player data into one canonical row
    per player per gameweek.

    Rules:

    NORMAL GW
        fixture_count = 1

    DGW
        fixture_count = 2
        Multiple fixture rows are aggregated.

    BGW
        fixture_count = 0
        No fixture-level performance exists, so performance
        fields remain NULL.

    IMPORTANT:
        This function creates one row per PLAYER × GAMEWEEK,
        not one row per fixture.
    """

    df = historical.copy()

    calendar = team_gameweek_calendar.copy()

    # --------------------------------------------------
    # 1. Required columns
    # --------------------------------------------------

    required_historical_columns = [
        "season",
        "gameweek",
        "player_id",
        "player_name",
        "position",
        "team_id",
        "team_name",
        "minutes",
        "starts",
        "total_points",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
    ]

    missing_columns = [
        column
        for column in required_historical_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Historical data is missing required columns: "
            + ", ".join(missing_columns)
        )

    required_calendar_columns = [
        "season",
        "gameweek",
        "team_id",
        "fixture_count",
        "gameweek_type",
    ]

    missing_calendar_columns = [
        column
        for column in required_calendar_columns
        if column not in calendar.columns
    ]

    if missing_calendar_columns:
        raise ValueError(
            "Team × Gameweek calendar is missing required columns: "
            + ", ".join(missing_calendar_columns)
        )

    # --------------------------------------------------
    # 2. Make sure the numeric fields are numeric
    # --------------------------------------------------

    numeric_columns = [
        "gameweek",
        "player_id",
        "team_id",
        "minutes",
        "starts",
        "total_points",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    calendar["gameweek"] = pd.to_numeric(
        calendar["gameweek"],
        errors="coerce"
    )

    calendar["team_id"] = pd.to_numeric(
        calendar["team_id"],
        errors="coerce"
    )

    calendar["fixture_count"] = pd.to_numeric(
        calendar["fixture_count"],
        errors="coerce"
    )

    # --------------------------------------------------
    # 3. Aggregate fixture-level rows
    #
    # DGW example:
    #
    # GW33 Fixture 1 → 6 points
    # GW33 Fixture 2 → 8 points
    #
    # becomes:
    #
    # GW33 → 14 points
    # --------------------------------------------------

    aggregation = {
        "minutes": "sum",
        "starts": "sum",
        "total_points": "sum",
        "expected_goals": "sum",
        "expected_assists": "sum",
        "expected_goal_involvements": "sum",
    }

    grouped = (
        df
        .groupby(
            [
                "season",
                "gameweek",
                "player_id",
                "team_id",
            ],
            as_index=False
        )
        .agg(aggregation)
    )

    # --------------------------------------------------
    # 4. Recover player metadata
    # --------------------------------------------------

    metadata = (
        df[
            [
                "season",
                "gameweek",
                "player_id",
                "team_id",
                "player_name",
                "position",
                "team_name",
            ]
        ]
        .drop_duplicates(
            subset=[
                "season",
                "gameweek",
                "player_id",
                "team_id",
            ]
        )
    )

    grouped = grouped.merge(
        metadata,
        on=[
            "season",
            "gameweek",
            "player_id",
            "team_id",
        ],
        how="left"
    )

    # --------------------------------------------------
    # 5. Determine how many fixtures the team had
    # --------------------------------------------------

    grouped = grouped.merge(
        calendar[
            [
                "season",
                "gameweek",
                "team_id",
                "fixture_count",
                "gameweek_type",
            ]
        ],
        on=[
            "season",
            "gameweek",
            "team_id",
        ],
        how="left"
    )

    # --------------------------------------------------
    # 6. Build player active periods
    #
    # We don't want to manufacture rows for a player
    # before they entered the league or after they left.
    # --------------------------------------------------

    player_periods = (
        grouped
        .groupby(
            [
                "season",
                "player_id",
            ],
            as_index=False
        )
        .agg(
            first_gameweek=("gameweek", "min"),
            last_gameweek=("gameweek", "max")
        )
    )

    # --------------------------------------------------
    # 7. Create player × gameweek skeleton
    # --------------------------------------------------

    skeleton_records = []

    for _, player in player_periods.iterrows():

        gameweeks = range(
            int(player["first_gameweek"]),
            int(player["last_gameweek"]) + 1
        )

        for gameweek in gameweeks:

            skeleton_records.append(
                {
                    "season": player["season"],
                    "player_id": player["player_id"],
                    "gameweek": gameweek,
                }
            )

    skeleton = pd.DataFrame(
        skeleton_records
    )

    # --------------------------------------------------
    # 8. Determine player's team for each gameweek
    #
    # Normally the player already has a fixture row.
    #
    # For a BGW, there is no fixture row, so we infer
    # the team from the surrounding player records.
    # --------------------------------------------------

    team_history = (
        grouped[
            [
                "season",
                "player_id",
                "gameweek",
                "team_id",
                "player_name",
                "position",
                "team_name",
            ]
        ]
        .sort_values(
            [
                "season",
                "player_id",
                "gameweek",
            ]
        )
    )

    skeleton = skeleton.merge(
        team_history,
        on=[
            "season",
            "player_id",
            "gameweek",
        ],
        how="left"
    )

    # Forward fill team information within each player.
    skeleton[
        [
            "team_id",
            "player_name",
            "position",
            "team_name",
        ]
    ] = (
        skeleton
        .groupby(
            [
                "season",
                "player_id",
            ]
        )[
            [
                "team_id",
                "player_name",
                "position",
                "team_name",
            ]
        ]
        .ffill()
    )

    # Backward fill handles a player's first observed
    # gameweek if necessary.
    skeleton[
        [
            "team_id",
            "player_name",
            "position",
            "team_name",
        ]
    ] = (
        skeleton
        .groupby(
            [
                "season",
                "player_id",
            ]
        )[
            [
                "team_id",
                "player_name",
                "position",
                "team_name",
            ]
        ]
        .bfill()
    )

    # --------------------------------------------------
    # 9. Attach the Team × Gameweek calendar
    # --------------------------------------------------

    skeleton = skeleton.merge(
        calendar[
            [
                "season",
                "gameweek",
                "team_id",
                "fixture_count",
                "gameweek_type",
            ]
        ],
        on=[
            "season",
            "gameweek",
            "team_id",
        ],
        how="left"
    )

    # --------------------------------------------------
    # 10. Attach aggregated player performance
    # --------------------------------------------------

    performance_columns = [
        "minutes",
        "starts",
        "total_points",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
    ]

    performance = grouped[
        [
            "season",
            "gameweek",
            "player_id",
            "team_id",
        ]
        + performance_columns
    ]

    canonical = skeleton.merge(
        performance,
        on=[
            "season",
            "gameweek",
            "player_id",
            "team_id",
        ],
        how="left"
    )

    # --------------------------------------------------
    # 11. Identify BGWs
    # --------------------------------------------------

    canonical["has_fixture"] = (
        canonical["fixture_count"] > 0
    )

    canonical["is_blank_gameweek"] = (
        canonical["fixture_count"] == 0
    )

    canonical["is_double_gameweek"] = (
        canonical["fixture_count"] > 1
    )

    # --------------------------------------------------
    # 12. Preserve the important distinction:
    #
    # BGW:
    #   no fixture → performance remains NULL
    #
    # Normal/DGW:
    #   fixture existed but player didn't play →
    #   performance should be zero.
    # --------------------------------------------------

    normal_fixture_mask = (
        canonical["fixture_count"] > 0
    )

    for column in performance_columns:

        canonical.loc[
            normal_fixture_mask & canonical[column].isna(),
            column
        ] = 0

    # --------------------------------------------------
    # 13. Sort final dataset
    # --------------------------------------------------

    canonical = (
        canonical
        .sort_values(
            [
                "season",
                "player_id",
                "gameweek",
            ]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------
    # 14. Diagnostics
    # --------------------------------------------------

    print(
        "DEBUG player-gameweek rows:",
        len(canonical),
        flush=True
    )

    print(
        "DEBUG unique player-gameweek keys:",
        canonical[
            [
                "season",
                "gameweek",
                "player_id",
            ]
        ]
        .drop_duplicates()
        .shape[0],
        flush=True
    )

    duplicate_keys = (
        canonical
        .groupby(
            [
                "season",
                "gameweek",
                "player_id",
            ]
        )
        .size()
    )

    duplicate_count = int(
        (duplicate_keys > 1).sum()
    )

    print(
        "DEBUG duplicate player-gameweek keys:",
        duplicate_count,
        flush=True
    )

    print(
        "DEBUG BGW player-gameweek rows:",
        int(
            canonical["is_blank_gameweek"].sum()
        ),
        flush=True
    )

    print(
        "DEBUG DGW player-gameweek rows:",
        int(
            canonical["is_double_gameweek"].sum()
        ),
        flush=True
    )

    return canonical


def aggregate_player_gameweeks(df):

    """
    Convert fixture-level player data into exactly
    one row per season + gameweek + player.

    Double Gameweeks are therefore consolidated.

    Example:

        Player | GW26 | Fixture A | 5 points
        Player | GW26 | Fixture B | 7 points

    becomes:

        Player | GW26 | 12 points
    """

    df = df.copy()

    # ---------------------------------------
    # 1. Validate required columns
    # ---------------------------------------

    required_columns = [
        "season",
        "gameweek",
        "player_id",
        "player_name",
        "position",
        "team_id",
        "team_name",
        "total_points",
        "minutes",
        "starts",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing columns required for "
            f"player-gameweek aggregation: "
            f"{missing_columns}"
        )

    # ---------------------------------------
    # 2. Sort fixture-level data
    # ---------------------------------------

    df = df.sort_values(
        [
            "season",
            "player_id",
            "gameweek",
            "fixture_id"
        ]
    ).reset_index(
        drop=True
    )

    # ---------------------------------------
    # 3. Aggregate fixture-level statistics
    # ---------------------------------------

    aggregated = (
        df
        .groupby(
            [
                "season",
                "gameweek",
                "player_id"
            ],
            as_index=False
        )
        .agg(
            player_name=("player_name", "first"),
            position=("position", "first"),
            team_id=("team_id", "first"),
            team_name=("team_name", "first"),

            total_points=("total_points", "sum"),
            minutes=("minutes", "sum"),
            starts=("starts", "sum"),

            expected_goals=(
                "expected_goals",
                "sum"
            ),

            expected_assists=(
                "expected_assists",
                "sum"
            ),

            expected_goal_involvements=(
                "expected_goal_involvements",
                "sum"
            ),

            fixture_count=(
                "fixture_id",
                "nunique"
            )
        )
    )

    # ---------------------------------------
    # 4. Validate player-gameweek grain
    # ---------------------------------------

    duplicate_count = (
        aggregated
        .duplicated(
            subset=[
                "season",
                "gameweek",
                "player_id"
            ]
        )
        .sum()
    )

    if duplicate_count > 0:

        raise ValueError(
            "Player-gameweek aggregation failed. "
            f"Found {duplicate_count} duplicate rows."
        )

    # ---------------------------------------
    # 5. Debug information
    # ---------------------------------------

    print(
        "DEBUG player-gameweek rows:",
        len(aggregated)
    )

    print(
        "DEBUG unique player-gameweek keys:",
        aggregated[
            [
                "season",
                "gameweek",
                "player_id"
            ]
        ]
        .drop_duplicates()
        .shape[0]
    )

    print(
        "DEBUG double-gameweek player rows:",
        (
            aggregated["fixture_count"] > 1
        ).sum()
    )

    return aggregated


def build_form_features(historical):

    # ---------------------------------------
    # 1. Aggregate fixture data into
    #    player-gameweek data
    #
    # IMPORTANT:
    # We are NOT adding BGW rows yet.
    #
    # This step only introduces the calendar
    # helper for validation in the next phase.
    # ---------------------------------------

    df = aggregate_player_gameweeks(
        historical
    )

    # ---------------------------------------
    # 2. Sort chronologically
    # ---------------------------------------

    df = df.sort_values(
        [
            "season",
            "player_id",
            "gameweek"
        ]
    ).reset_index(
        drop=True
    )

    # ---------------------------------------
    # 3. Previous Gameweek points
    # ---------------------------------------

    df["previous_gw_points"] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["total_points"]
        .shift(1)
    )

    # ---------------------------------------
    # 4. Rolling 3 GW average
    # ---------------------------------------

    df["rolling_3gw_points"] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["total_points"]
        .transform(
            lambda x:
                x.shift(1)
                .rolling(
                    window=3,
                    min_periods=3
                )
                .mean()
        )
    )

    # ---------------------------------------
    # 5. Rolling 5 GW average
    # ---------------------------------------

    df["rolling_5gw_points"] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["total_points"]
        .transform(
            lambda x:
                x.shift(1)
                .rolling(
                    window=5,
                    min_periods=5
                )
                .mean()
        )
    )

    # ---------------------------------------
    # 6. Rolling 10 GW average
    # ---------------------------------------

    df["rolling_10gw_points"] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["total_points"]
        .transform(
            lambda x:
                x.shift(1)
                .rolling(
                    window=10,
                    min_periods=10
                )
                .mean()
        )
    )

    # ---------------------------------------
    # 7. Underlying performance features
    # ---------------------------------------

    df = add_underlying_performance_features(
        df
    )

    # ---------------------------------------
    # 8. Playing-time features
    # ---------------------------------------

    df = add_playing_time_features(
        df
    )

    # ---------------------------------------
    # 9. Next Gameweek points
    # ---------------------------------------

    df["next_gw_points"] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["total_points"]
        .shift(-1)
    )

    print(
        "DEBUG total player-gameweek rows:",
        len(df)
    )

    print(
        "DEBUG null targets:",
        df["next_gw_points"]
        .isna()
        .sum()
    )

    print(
        "DEBUG players:",
        df[
            [
                "season",
                "player_id"
            ]
        ]
        .drop_duplicates()
        .shape[0]
    )

    # ---------------------------------------
    # 10. Remove rows without target
    # ---------------------------------------

    df = df.dropna(
        subset=[
            "next_gw_points"
        ]
    ).copy()

    # ---------------------------------------
    # 11. Final grain validation
    # ---------------------------------------

    duplicate_count = (
        df
        .duplicated(
            subset=[
                "season",
                "gameweek",
                "player_id"
            ]
        )
        .sum()
    )

    if duplicate_count > 0:

        raise ValueError(
            "Final prediction feature dataset "
            "contains duplicate player-gameweek "
            f"rows: {duplicate_count}"
        )

    print(
        "DEBUG final feature rows:",
        len(df)
    )

    # ---------------------------------------
    # 12. Keep required fields
    # ---------------------------------------

    features = df[
        [
            "season",
            "gameweek",
            "player_id",
            "player_name",
            "position",
            "team_id",
            "team_name",

            # -------------------------
            # Form
            # -------------------------

            "previous_gw_points",
            "rolling_3gw_points",
            "rolling_5gw_points",
            "rolling_10gw_points",

            # -------------------------
            # xG
            # -------------------------

            "previous_gw_xg",
            "rolling_3gw_xg",
            "rolling_5gw_xg",
            "rolling_10gw_xg",

            # -------------------------
            # xA
            # -------------------------

            "previous_gw_xa",
            "rolling_3gw_xa",
            "rolling_5gw_xa",
            "rolling_10gw_xa",

            # -------------------------
            # xGI
            # -------------------------

            "previous_gw_xgi",
            "rolling_3gw_xgi",
            "rolling_5gw_xgi",
            "rolling_10gw_xgi",

            # -------------------------
            # Playing time
            # -------------------------

            "previous_gw_minutes",
            "rolling_3gw_minutes",
            "rolling_5gw_minutes",
            "rolling_10gw_minutes",

            "previous_gw_starts",
            "rolling_3gw_starts",
            "rolling_5gw_starts",
            "rolling_10gw_starts",

            "rolling_3gw_start_rate",
            "rolling_5gw_start_rate",
            "rolling_10gw_start_rate",

            # -------------------------
            # Target
            # -------------------------

            "next_gw_points"
        ]
    ].copy()

    return features


def add_underlying_performance_features(df):

    df = df.copy()

    # ---------------------------------------
    # Sort chronologically
    # ---------------------------------------

    df = df.sort_values(
        [
            "season",
            "player_id",
            "gameweek"
        ]
    ).reset_index(
        drop=True
    )

    # ---------------------------------------
    # Helper function
    # ---------------------------------------

    def add_rolling_features(
        source_column,
        prefix
    ):

        # Previous Gameweek

        df[
            f"previous_gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .shift(1)
        )

        # Rolling 3 Gameweeks

        df[
            f"rolling_3gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .transform(
                lambda x:
                    x.shift(1)
                    .rolling(
                        window=3,
                        min_periods=3
                    )
                    .mean()
            )
        )

        # Rolling 5 Gameweeks

        df[
            f"rolling_5gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .transform(
                lambda x:
                    x.shift(1)
                    .rolling(
                        window=5,
                        min_periods=5
                    )
                    .mean()
            )
        )

        # Rolling 10 Gameweeks

        df[
            f"rolling_10gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .transform(
                lambda x:
                    x.shift(1)
                    .rolling(
                        window=10,
                        min_periods=10
                    )
                    .mean()
            )
        )

    # ---------------------------------------
    # xG
    # ---------------------------------------

    add_rolling_features(
        "expected_goals",
        "xg"
    )

    # ---------------------------------------
    # xA
    # ---------------------------------------

    add_rolling_features(
        "expected_assists",
        "xa"
    )

    # ---------------------------------------
    # xGI
    # ---------------------------------------

    add_rolling_features(
        "expected_goal_involvements",
        "xgi"
    )

    return df


def add_playing_time_features(df):

    df = df.copy()

    # ---------------------------------------
    # Sort chronologically
    # ---------------------------------------

    df = df.sort_values(
        [
            "season",
            "player_id",
            "gameweek"
        ]
    ).reset_index(
        drop=True
    )

    # ---------------------------------------
    # Helper function
    # ---------------------------------------

    def add_rolling_features(
        source_column,
        prefix
    ):

        # Previous Gameweek

        df[
            f"previous_gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .shift(1)
        )

        # Rolling 3 Gameweeks

        df[
            f"rolling_3gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .transform(
                lambda x:
                    x.shift(1)
                    .rolling(
                        window=3,
                        min_periods=3
                    )
                    .mean()
            )
        )

        # Rolling 5 Gameweeks

        df[
            f"rolling_5gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .transform(
                lambda x:
                    x.shift(1)
                    .rolling(
                        window=5,
                        min_periods=5
                    )
                    .mean()
            )
        )

        # Rolling 10 Gameweeks

        df[
            f"rolling_10gw_{prefix}"
        ] = (
            df
            .groupby(
                [
                    "season",
                    "player_id"
                ]
            )[source_column]
            .transform(
                lambda x:
                    x.shift(1)
                    .rolling(
                        window=10,
                        min_periods=10
                    )
                    .mean()
            )
        )

    # ---------------------------------------
    # Minutes
    # ---------------------------------------

    add_rolling_features(
        "minutes",
        "minutes"
    )

    # ---------------------------------------
    # Starts
    # ---------------------------------------

    add_rolling_features(
        "starts",
        "starts"
    )

    # ---------------------------------------
    # Starting rate
    # ---------------------------------------

    df[
        "rolling_3gw_start_rate"
    ] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["starts"]
        .transform(
            lambda x:
                x.shift(1)
                .rolling(
                    window=3,
                    min_periods=3
                )
                .mean()
        )
    )

    df[
        "rolling_5gw_start_rate"
    ] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["starts"]
        .transform(
            lambda x:
                x.shift(1)
                .rolling(
                    window=5,
                    min_periods=5
                )
                .mean()
        )
    )

    df[
        "rolling_10gw_start_rate"
    ] = (
        df
        .groupby(
            [
                "season",
                "player_id"
            ]
        )["starts"]
        .transform(
            lambda x:
                x.shift(1)
                .rolling(
                    window=10,
                    min_periods=10
                )
                .mean()
        )
    )

    return df

