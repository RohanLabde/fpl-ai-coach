import pandas as pd


FEATURE_WINDOWS = (3, 5, 10)

PERFORMANCE_COLUMNS = [
    "total_points",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "minutes",
    "starts",
    "goals_scored",
    "assists",
    "clean_sheets",
    "bonus",
    "threat",
    "creativity",
    "defensive_contribution",
]


def build_team_gameweek_calendar(fixtures, season=None):
    """
    Build a complete Team × Gameweek calendar.

    fixture_count:
        0 = blank gameweek
        1 = normal gameweek
        2+ = double/multiple gameweek
    """
    fixtures = fixtures.copy()

    required_columns = ["event", "team_h", "team_a"]
    missing = [
        column
        for column in required_columns
        if column not in fixtures.columns
    ]

    if missing:
        raise ValueError(
            "Missing columns required to build the team-gameweek "
            f"calendar: {missing}"
        )

    if season is not None:
        fixtures["season"] = season

    fixtures = fixtures[
        fixtures["event"].notna()
    ].copy()

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
            "away_team_id",
        ]
    ).copy()

    fixtures["gameweek"] = fixtures["gameweek"].astype(int)
    fixtures["home_team_id"] = fixtures["home_team_id"].astype(int)
    fixtures["away_team_id"] = fixtures["away_team_id"].astype(int)

    home = fixtures[
        ["gameweek", "home_team_id"]
    ].rename(
        columns={"home_team_id": "team_id"}
    )

    away = fixtures[
        ["gameweek", "away_team_id"]
    ].rename(
        columns={"away_team_id": "team_id"}
    )

    if "season" in fixtures.columns:
        home["season"] = fixtures["season"].values
        away["season"] = fixtures["season"].values

        team_fixtures = pd.concat(
            [home, away],
            ignore_index=True
        )

        fixture_counts = (
            team_fixtures
            .groupby(
                ["season", "gameweek", "team_id"],
                as_index=False
            )
            .size()
            .rename(columns={"size": "fixture_count"})
        )

        calendar_parts = []

        for current_season in sorted(
            fixture_counts["season"].dropna().unique()
        ):
            season_rows = fixture_counts[
                fixture_counts["season"] == current_season
            ]

            gameweeks = sorted(
                season_rows["gameweek"].unique()
            )

            teams = sorted(
                season_rows["team_id"].unique()
            )

            grid = pd.MultiIndex.from_product(
                [gameweeks, teams],
                names=["gameweek", "team_id"]
            ).to_frame(index=False)

            grid["season"] = current_season
            calendar_parts.append(grid)

        calendar = pd.concat(
            calendar_parts,
            ignore_index=True
        )

        calendar = calendar.merge(
            fixture_counts,
            on=["season", "gameweek", "team_id"],
            how="left",
            validate="one_to_one"
        )

        key_columns = [
            "season",
            "gameweek",
            "team_id",
        ]

        sort_columns = key_columns

    else:
        team_fixtures = pd.concat(
            [home, away],
            ignore_index=True
        )

        fixture_counts = (
            team_fixtures
            .groupby(
                ["gameweek", "team_id"],
                as_index=False
            )
            .size()
            .rename(columns={"size": "fixture_count"})
        )

        gameweeks = sorted(
            fixture_counts["gameweek"].unique()
        )

        teams = sorted(
            fixture_counts["team_id"].unique()
        )

        calendar = pd.MultiIndex.from_product(
            [gameweeks, teams],
            names=["gameweek", "team_id"]
        ).to_frame(index=False)

        calendar = calendar.merge(
            fixture_counts,
            on=["gameweek", "team_id"],
            how="left",
            validate="one_to_one"
        )

        key_columns = [
            "gameweek",
            "team_id",
        ]

        sort_columns = key_columns

    calendar["fixture_count"] = (
        calendar["fixture_count"]
        .fillna(0)
        .astype(int)
    )

    calendar["has_fixture"] = (
        calendar["fixture_count"] > 0
    )

    calendar["gameweek_type"] = "BGW"

    calendar.loc[
        calendar["fixture_count"] == 1,
        "gameweek_type"
    ] = "NORMAL"

    calendar.loc[
        calendar["fixture_count"] >= 2,
        "gameweek_type"
    ] = "DGW"

    calendar = calendar.sort_values(
        sort_columns
    ).reset_index(drop=True)

    duplicate_count = int(
        calendar.duplicated(
            subset=key_columns
        ).sum()
    )

    if duplicate_count:
        raise ValueError(
            "Team-gameweek calendar contains "
            f"{duplicate_count} duplicate keys."
        )

    print(
        "DEBUG calendar rows:",
        len(calendar),
        flush=True
    )

    print(
        "DEBUG normal team-gameweeks:",
        int(
            (
                calendar["gameweek_type"]
                == "NORMAL"
            ).sum()
        ),
        flush=True
    )

    print(
        "DEBUG double-gameweek team rows:",
        int(
            (
                calendar["gameweek_type"]
                == "DGW"
            ).sum()
        ),
        flush=True
    )

    print(
        "DEBUG blank-gameweek team rows:",
        int(
            (
                calendar["gameweek_type"]
                == "BGW"
            ).sum()
        ),
        flush=True
    )

    return calendar


def build_player_gameweek_data(
    historical,
    team_gameweek_calendar
):
    """
    Build one canonical row per season × player × gameweek.

    BGWs are retained as rows with NULL performance values. A normal
    gameweek in which the player did not play is represented as zero
    performance because their team did have a fixture.
    """
    df = historical.copy()
    calendar = team_gameweek_calendar.copy()

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
        "goals_scored",
        "assists",
        "clean_sheets",
        "bonus",
        "threat",
        "creativity",
        "defensive_contribution",
    ]

    missing = [
        column
        for column in required_historical_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Historical data is missing required columns: "
            f"{missing}"
        )

    required_calendar_columns = [
        "gameweek",
        "team_id",
        "fixture_count",
        "gameweek_type",
    ]

    missing = [
        column
        for column in required_calendar_columns
        if column not in calendar.columns
    ]

    if missing:
        raise ValueError(
            "Team-gameweek calendar is missing required "
            f"columns: {missing}"
        )

    historical_seasons = (
        df["season"]
        .dropna()
        .unique()
    )

    if "season" not in calendar.columns:
        if len(historical_seasons) != 1:
            raise ValueError(
                "A multi-season feature build requires a "
                "season-aware Team × Gameweek calendar."
            )

        calendar["season"] = historical_seasons[0]

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
        "goals_scored",
        "assists",
        "clean_sheets",
        "bonus",
        "threat",
        "creativity",
        "defensive_contribution",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    for column in [
        "gameweek",
        "team_id",
        "fixture_count",
    ]:
        calendar[column] = pd.to_numeric(
            calendar[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "season",
            "gameweek",
            "player_id",
            "team_id",
        ]
    ).copy()

    calendar = calendar.dropna(
        subset=[
            "season",
            "gameweek",
            "team_id",
        ]
    ).copy()

    for column in [
        "gameweek",
        "player_id",
        "team_id",
    ]:
        df[column] = df[column].astype(int)

    for column in [
        "gameweek",
        "team_id",
        "fixture_count",
    ]:
        calendar[column] = calendar[column].astype(int)

    aggregation = {
        "minutes": "sum",
        "starts": "sum",
        "total_points": "sum",
        "expected_goals": "sum",
        "expected_assists": "sum",
        "expected_goal_involvements": "sum",
        "goals_scored": "sum",
        "assists": "sum",
        "clean_sheets": "sum",
        "bonus": "sum",
        "threat": "sum",
        "creativity": "sum",
        "defensive_contribution": "sum",
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
        how="left",
        validate="one_to_one"
    )

    team_count_per_player_gw = (
        grouped
        .groupby(
            [
                "season",
                "gameweek",
                "player_id",
            ]
        )["team_id"]
        .nunique()
    )

    transfer_within_gw = (
        team_count_per_player_gw[
            team_count_per_player_gw > 1
        ]
    )

    if len(transfer_within_gw):
        raise ValueError(
            "A player appears for multiple teams in the same "
            "gameweek. Define a transfer-within-GW rule before "
            "building features."
        )

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
        how="left",
        validate="many_to_one"
    )

    if grouped["fixture_count"].isna().any():
        raise ValueError(
            "Observed player rows could not be matched to the "
            "Team × Gameweek calendar."
        )

    player_periods = (
        grouped
        .groupby(
            ["season", "player_id"],
            as_index=False
        )
        .agg(
            first_gameweek=(
                "gameweek",
                "min"
            ),
            last_gameweek=(
                "gameweek",
                "max"
            ),
        )
    )

    skeleton_records = []

    for _, player in player_periods.iterrows():
        for gameweek in range(
            int(player["first_gameweek"]),
            int(player["last_gameweek"]) + 1
        ):
            skeleton_records.append(
                {
                    "season": player["season"],
                    "player_id": int(
                        player["player_id"]
                    ),
                    "gameweek": gameweek,
                }
            )

    skeleton = pd.DataFrame(skeleton_records)

    team_history = grouped[
        [
            "season",
            "player_id",
            "gameweek",
            "team_id",
            "player_name",
            "position",
            "team_name",
        ]
    ].sort_values(
        [
            "season",
            "player_id",
            "gameweek",
        ]
    )

    skeleton = skeleton.merge(
        team_history,
        on=[
            "season",
            "player_id",
            "gameweek",
        ],
        how="left",
        validate="one_to_one"
    )

    metadata_columns = [
        "team_id",
        "player_name",
        "position",
        "team_name",
    ]

    skeleton[metadata_columns] = (
        skeleton
        .groupby(
            ["season", "player_id"]
        )[metadata_columns]
        .ffill()
    )

    skeleton[metadata_columns] = (
        skeleton
        .groupby(
            ["season", "player_id"]
        )[metadata_columns]
        .bfill()
    )

    if skeleton["team_id"].isna().any():
        raise ValueError(
            "Could not infer a team for one or more "
            "player-gameweek rows."
        )

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
        how="left",
        validate="many_to_one"
    )

    if skeleton["fixture_count"].isna().any():
        raise ValueError(
            "An inferred player team is missing from the "
            "Team × Gameweek calendar."
        )

    performance = grouped[
        [
            "season",
            "gameweek",
            "player_id",
            "team_id",
        ] + PERFORMANCE_COLUMNS
    ]

    canonical = skeleton.merge(
        performance,
        on=[
            "season",
            "gameweek",
            "player_id",
            "team_id",
        ],
        how="left",
        validate="one_to_one"
    )

    canonical["has_fixture"] = (
        canonical["fixture_count"] > 0
    )

    canonical["is_blank_gameweek"] = (
        canonical["fixture_count"] == 0
    )

    canonical["is_double_gameweek"] = (
        canonical["fixture_count"] > 1
    )

    normal_fixture_mask = (
        canonical["fixture_count"] > 0
    )

    for column in PERFORMANCE_COLUMNS:
        canonical.loc[
            normal_fixture_mask
            & canonical[column].isna(),
            column
        ] = 0

    canonical = canonical.sort_values(
        [
            "season",
            "player_id",
            "gameweek",
        ]
    ).reset_index(drop=True)

    duplicate_count = int(
        canonical.duplicated(
            subset=[
                "season",
                "gameweek",
                "player_id",
            ]
        ).sum()
    )

    if duplicate_count:
        raise ValueError(
            "Canonical Player × Gameweek data contains "
            f"{duplicate_count} duplicate keys."
        )

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
        ].drop_duplicates().shape[0],
        flush=True
    )

    print(
        "DEBUG duplicate player-gameweek keys:",
        duplicate_count,
        flush=True
    )

    print(
        "DEBUG BGW player-gameweek rows:",
        int(
            canonical[
                "is_blank_gameweek"
            ].sum()
        ),
        flush=True
    )

    print(
        "DEBUG DGW player-gameweek rows:",
        int(
            canonical[
                "is_double_gameweek"
            ].sum()
        ),
        flush=True
    )

    return canonical


def aggregate_player_gameweeks(df):
    """
    Aggregate fixture-level data to one row per
    season × gameweek × player.

    This helper is retained for independent analysis and validation.
    The feature pipeline itself uses build_player_gameweek_data() so it
    can retain explicit BGW rows.
    """
    df = df.copy()

    required_columns = [
        "season",
        "gameweek",
        "player_id",
        "player_name",
        "position",
        "team_id",
        "team_name",
        "fixture_id",
        "total_points",
        "minutes",
        "starts",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "goals_scored",
        "assists",
        "clean_sheets",
        "bonus",
        "threat",
        "creativity",
        "defensive_contribution",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing columns required for Player × Gameweek "
            f"aggregation: {missing}"
        )

    df = df.sort_values(
        [
            "season",
            "player_id",
            "gameweek",
            "fixture_id",
        ]
    ).reset_index(drop=True)

    aggregated = (
        df
        .groupby(
            [
                "season",
                "gameweek",
                "player_id",
            ],
            as_index=False
        )
        .agg(
            player_name=(
                "player_name",
                "first"
            ),
            position=(
                "position",
                "first"
            ),
            team_id=(
                "team_id",
                "first"
            ),
            team_name=(
                "team_name",
                "first"
            ),
            total_points=(
                "total_points",
                "sum"
            ),
            minutes=(
                "minutes",
                "sum"
            ),
            starts=(
                "starts",
                "sum"
            ),
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
            goals_scored=("goals_scored", "sum"),
            assists=("assists", "sum"),
            clean_sheets=("clean_sheets", "sum"),
            bonus=("bonus", "sum"),
            threat=("threat", "sum"),
            creativity=("creativity", "sum"),
            defensive_contribution=("defensive_contribution", "sum"),
            fixture_count=(
                "fixture_id",
                "nunique"
            ),
        )
    )

    duplicate_count = int(
        aggregated.duplicated(
            subset=[
                "season",
                "gameweek",
                "player_id",
            ]
        ).sum()
    )

    if duplicate_count:
        raise ValueError(
            "Player-gameweek aggregation failed. "
            f"Found {duplicate_count} duplicate rows."
        )

    return aggregated


def _add_calendar_previous_features(df):
    """
    Previous-GW features are calendar-based.

    A preceding BGW is intentionally represented as zero. This retains
    the distinction between immediately previous calendar context and
    rolling performance form.
    """
    result = df.copy()

    calendar_values = result[
        PERFORMANCE_COLUMNS
    ].fillna(0)

    for source_column in PERFORMANCE_COLUMNS:
        prefix = {
            "total_points": "points",
            "expected_goals": "xg",
            "expected_assists": "xa",
            "expected_goal_involvements": "xgi",
            "minutes": "minutes",
            "starts": "starts",
            "goals_scored": "goals_scored",
            "assists": "assists",
            "clean_sheets": "clean_sheets",
            "bonus": "bonus",
            "threat": "threat",
            "creativity": "creativity",
            "defensive_contribution": "defensive_contribution",
        }[source_column]

        result[
            f"previous_gw_{prefix}"
        ] = (
            calendar_values[source_column]
            .groupby(
                [
                    result["season"],
                    result["player_id"],
                ]
            )
            .shift(1)
        )

    previous_minutes = calendar_values["minutes"].groupby(
        [result["season"], result["player_id"]]
    )
    result["previous_gw_played"] = previous_minutes.transform(
        lambda values: values.gt(0).shift(1)
    )
    result["previous_gw_60_minute_appearance"] = previous_minutes.transform(
        lambda values: values.ge(60).shift(1)
    )

    return result


def _build_actual_fixture_history_rollups(df):
    """
    Calculate rolling features from actual fixture gameweeks only.

    BGW rows never enter these windows. A DGW remains one observation,
    with its fixture-level values already aggregated into that gameweek.
    """
    history = df[
        df["has_fixture"]
    ].copy()

    history = history.sort_values(
        [
            "season",
            "player_id",
            "gameweek",
        ]
    ).reset_index(drop=True)

    grouped = history.groupby(
        ["season", "player_id"],
        group_keys=False
    )

    metric_prefixes = {
        "total_points": "points",
        "expected_goals": "xg",
        "expected_assists": "xa",
        "expected_goal_involvements": "xgi",
        "minutes": "minutes",
        "starts": "starts",
        "goals_scored": "goals_scored",
        "assists": "assists",
        "clean_sheets": "clean_sheets",
        "bonus": "bonus",
        "threat": "threat",
        "creativity": "creativity",
        "defensive_contribution": "defensive_contribution",
    }

    for source_column, prefix in metric_prefixes.items():
        for window in FEATURE_WINDOWS:
            history[
                f"rolling_{window}gw_{prefix}"
            ] = grouped[source_column].transform(
                lambda values, size=window:
                    values.shift(1).rolling(
                        window=size,
                        min_periods=size
                    ).mean()
            )

    for window in FEATURE_WINDOWS:
        rolling_starts = grouped["starts"].transform(
            lambda values, size=window:
                values.shift(1).rolling(
                    window=size,
                    min_periods=size
                ).sum()
        )

        rolling_fixtures = grouped["fixture_count"].transform(
            lambda values, size=window:
                values.shift(1).rolling(
                    window=size,
                    min_periods=size
                ).sum()
        )

        history[
            f"rolling_{window}gw_start_rate"
        ] = (
            rolling_starts / rolling_fixtures
        )

        rolling_minutes_total = grouped["minutes"].transform(
            lambda values, size=window:
                values.shift(1).rolling(
                    window=size,
                    min_periods=size,
                ).sum()
        )
        history[f"rolling_{window}gw_minutes_per_fixture"] = (
            rolling_minutes_total / rolling_fixtures
        )
        history[f"rolling_{window}gw_play_rate"] = grouped["minutes"].transform(
            lambda values, size=window:
                values.gt(0).shift(1).rolling(
                    window=size,
                    min_periods=size,
                ).mean()
        )
        history[
            f"rolling_{window}gw_60_minute_appearance_rate"
        ] = grouped["minutes"].transform(
            lambda values, size=window:
                values.ge(60).shift(1).rolling(
                    window=size,
                    min_periods=size,
                ).mean()
        )

    # These availability signals combine recent selection behaviour with a
    # longer baseline. They are known before the next gameweek begins.
    history["minutes_trend_3gw_vs_10gw"] = (
        history["rolling_3gw_minutes_per_fixture"]
        - history["rolling_10gw_minutes_per_fixture"]
    )
    history["start_rate_trend_3gw_vs_10gw"] = (
        history["rolling_3gw_start_rate"]
        - history["rolling_10gw_start_rate"]
    )
    history["expected_minutes_per_fixture"] = (
        0.55 * history["rolling_3gw_minutes_per_fixture"]
        + 0.30 * history["rolling_5gw_minutes_per_fixture"]
        + 0.15 * history["rolling_10gw_minutes_per_fixture"]
    )

    # Rates prevent high-minute players from appearing more attacking simply
    # because they played more. All inputs are shifted, so they are known at
    # the end of the current gameweek.
    rate_metrics = {
        "expected_goal_involvements": "xgi",
        "goals_scored": "goals_scored",
        "assists": "assists",
        "threat": "threat",
        "creativity": "creativity",
        "defensive_contribution": "defensive_contribution",
    }

    for window in (3, 5):
        rolling_minutes = grouped["minutes"].transform(
            lambda values, size=window: values.shift(1).rolling(
                window=size,
                min_periods=size,
            ).sum()
        )

        for source_column, prefix in rate_metrics.items():
            rolling_total = grouped[source_column].transform(
                lambda values, size=window: values.shift(1).rolling(
                    window=size,
                    min_periods=size,
                ).sum()
            )
            history[f"rolling_{window}gw_{prefix}_per_90"] = (
                90 * rolling_total / rolling_minutes
            ).where(rolling_minutes.gt(0))

    return history


def build_form_features(
    historical,
    team_gameweek_calendar
):
    """
    Build leakage-safe prediction features.

    Semantics:
    - previous_gw_*: previous calendar gameweek; BGW is zero.
    - rolling_*: previous actual fixture gameweeks; BGWs are skipped.
    - DGWs: one Player × GW observation, with fixture metrics aggregated.
    - next_gw_points: next calendar gameweek target; BGW target is zero.
    """
    df = build_player_gameweek_data(
        historical,
        team_gameweek_calendar
    )

    df = df.sort_values(
        [
            "season",
            "player_id",
            "gameweek",
        ]
    ).reset_index(drop=True)

    df = _add_calendar_previous_features(df)

    history = _build_actual_fixture_history_rollups(df)

    rolling_columns = [
        column
        for column in history.columns
        if column.startswith("rolling_")
    ]
    derived_availability_columns = [
        "minutes_trend_3gw_vs_10gw",
        "start_rate_trend_3gw_vs_10gw",
        "expected_minutes_per_fixture",
    ]
    history_feature_columns = rolling_columns + derived_availability_columns

    df = df.merge(
        history[
            [
                "season",
                "gameweek",
                "player_id",
            ] + history_feature_columns
        ],
        on=[
            "season",
            "gameweek",
            "player_id",
        ],
        how="left",
        validate="one_to_one"
    )

    # BGW rows remain in the calendar dataset. Their rolling form should
    # represent the same pre-fixture history used by the next actual fixture,
    # without filling missing values on ordinary playing gameweeks.
    blank_mask = df["is_blank_gameweek"]

    next_fixture_rollups = (
        df
        .groupby(
            ["season", "player_id"],
            group_keys=False
        )[history_feature_columns]
        .bfill()
    )

    df.loc[
        blank_mask,
        history_feature_columns
    ] = next_fixture_rollups.loc[
        blank_mask,
        history_feature_columns
    ]
    target_source = (
        df["total_points"]
        .where(
            ~df["is_blank_gameweek"],
            0
        )
    )

    df["next_gw_points"] = (
        target_source
        .groupby(
            [
                df["season"],
                df["player_id"],
            ]
        )
        .shift(-1)
    )

    final_gw_rows = int(
        df["next_gw_points"].isna().sum()
    )

    df = df.dropna(
        subset=["next_gw_points"]
    ).copy()

    duplicate_count = int(
        df.duplicated(
            subset=[
                "season",
                "gameweek",
                "player_id",
            ]
        ).sum()
    )

    if duplicate_count:
        raise ValueError(
            "Final prediction-feature data contains "
            f"{duplicate_count} duplicate Player × GW keys."
        )

    required_feature_columns = [
        "season",
        "gameweek",
        "player_id",
        "player_name",
        "position",
        "team_id",
        "team_name",

        "previous_gw_points",
        "rolling_3gw_points",
        "rolling_5gw_points",
        "rolling_10gw_points",

        "previous_gw_xg",
        "rolling_3gw_xg",
        "rolling_5gw_xg",
        "rolling_10gw_xg",

        "previous_gw_xa",
        "rolling_3gw_xa",
        "rolling_5gw_xa",
        "rolling_10gw_xa",

        "previous_gw_xgi",
        "rolling_3gw_xgi",
        "rolling_5gw_xgi",
        "rolling_10gw_xgi",

        "previous_gw_minutes",
        "previous_gw_played",
        "previous_gw_60_minute_appearance",
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

        "rolling_3gw_minutes_per_fixture",
        "rolling_5gw_minutes_per_fixture",
        "rolling_10gw_minutes_per_fixture",
        "rolling_3gw_play_rate",
        "rolling_5gw_play_rate",
        "rolling_10gw_play_rate",
        "rolling_3gw_60_minute_appearance_rate",
        "rolling_5gw_60_minute_appearance_rate",
        "rolling_10gw_60_minute_appearance_rate",
        "minutes_trend_3gw_vs_10gw",
        "start_rate_trend_3gw_vs_10gw",
        "expected_minutes_per_fixture",

        "next_gw_points",
    ]

    additional_metric_prefixes = [
        "goals_scored",
        "assists",
        "clean_sheets",
        "bonus",
        "threat",
        "creativity",
        "defensive_contribution",
    ]
    for prefix in additional_metric_prefixes:
        required_feature_columns.append(f"previous_gw_{prefix}")
        required_feature_columns.extend(
            f"rolling_{window}gw_{prefix}"
            for window in FEATURE_WINDOWS
        )

    required_feature_columns.extend(
        [
            f"rolling_{window}gw_{prefix}_per_90"
            for window in (3, 5)
            for prefix in (
                "xgi",
                "goals_scored",
                "assists",
                "threat",
                "creativity",
                "defensive_contribution",
            )
        ]
    )

    missing = [
        column
        for column in required_feature_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Feature build did not produce required columns: "
            f"{missing}"
        )

    print(
        "DEBUG total canonical Player × GW rows:",
        len(
            build_player_gameweek_data(
                historical,
                team_gameweek_calendar
            )
        ),
        flush=True
    )

    print(
        "DEBUG final-GW rows removed:",
        final_gw_rows,
        flush=True
    )

    print(
        "DEBUG final prediction feature rows:",
        len(df),
        flush=True
    )

    return df[
        required_feature_columns
    ].copy()
