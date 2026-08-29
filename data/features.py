import pandas as pd

def build_team_gameweek_calendar(fixtures, season=None):
    """
    Build the complete Team × Gameweek fixture calendar.

    The calendar is the authoritative source for whether a team has:
        0 fixtures -> BGW
        1 fixture  -> normal gameweek
        2+ fixtures -> DGW/multiple gameweek

    If ``season`` is supplied, it is attached to every calendar row. If the
    input fixtures already contains a ``season`` column, that column is used.
    """
    fixtures = fixtures.copy()

    required_columns = ["event", "team_h", "team_a"]
    missing_columns = [c for c in required_columns if c not in fixtures.columns]
    if missing_columns:
        raise ValueError(
            "Missing columns required to build team-gameweek calendar: "
            f"{missing_columns}"
        )

    if season is not None:
        fixtures["season"] = season
    elif "season" not in fixtures.columns:
        # A season is optional at this layer. build_player_gameweek_data()
        # will safely attach it when historical data contains one season.
        pass

    fixtures = fixtures[fixtures["event"].notna()].copy()

    fixtures["gameweek"] = pd.to_numeric(fixtures["event"], errors="coerce")
    fixtures["home_team_id"] = pd.to_numeric(fixtures["team_h"], errors="coerce")
    fixtures["away_team_id"] = pd.to_numeric(fixtures["team_a"], errors="coerce")

    fixtures = fixtures.dropna(
        subset=["gameweek", "home_team_id", "away_team_id"]
    ).copy()

    fixtures["gameweek"] = fixtures["gameweek"].astype(int)
    fixtures["home_team_id"] = fixtures["home_team_id"].astype(int)
    fixtures["away_team_id"] = fixtures["away_team_id"].astype(int)

    home = fixtures[["gameweek", "home_team_id"]].rename(
        columns={"home_team_id": "team_id"}
    )
    away = fixtures[["gameweek", "away_team_id"]].rename(
        columns={"away_team_id": "team_id"}
    )

    if "season" in fixtures.columns:
        home["season"] = fixtures["season"].values
        away["season"] = fixtures["season"].values
        team_fixtures = pd.concat([home, away], ignore_index=True)

        fixture_counts = (
            team_fixtures
            .groupby(["season", "gameweek", "team_id"], as_index=False)
            .size()
            .rename(columns={"size": "fixture_count"})
        )

        seasons = sorted(fixture_counts["season"].dropna().unique())
        grid_parts = []
        for current_season in seasons:
            s = fixture_counts[fixture_counts["season"] == current_season]
            gameweeks = sorted(s["gameweek"].unique())
            teams = sorted(s["team_id"].unique())
            grid = pd.MultiIndex.from_product(
                [gameweeks, teams], names=["gameweek", "team_id"]
            ).to_frame(index=False)
            grid["season"] = current_season
            grid_parts.append(grid)
        complete_calendar = pd.concat(grid_parts, ignore_index=True)

        calendar = complete_calendar.merge(
            fixture_counts, on=["season", "gameweek", "team_id"], how="left"
        )
        sort_columns = ["season", "gameweek", "team_id"]
        key_columns = ["season", "gameweek", "team_id"]
        expected_rows = sum(
            len(fixture_counts[fixture_counts["season"] == s]["gameweek"].unique())
            * len(fixture_counts[fixture_counts["season"] == s]["team_id"].unique())
            for s in seasons
        )
    else:
        team_fixtures = pd.concat([home, away], ignore_index=True)
        fixture_counts = (
            team_fixtures
            .groupby(["gameweek", "team_id"], as_index=False)
            .size()
            .rename(columns={"size": "fixture_count"})
        )

        gameweeks = sorted(fixture_counts["gameweek"].unique())
        teams = sorted(fixture_counts["team_id"].unique())
        complete_calendar = pd.MultiIndex.from_product(
            [gameweeks, teams], names=["gameweek", "team_id"]
        ).to_frame(index=False)

        calendar = complete_calendar.merge(
            fixture_counts, on=["gameweek", "team_id"], how="left"
        )
        sort_columns = ["gameweek", "team_id"]
        key_columns = ["gameweek", "team_id"]
        expected_rows = len(gameweeks) * len(teams)

    calendar["fixture_count"] = calendar["fixture_count"].fillna(0).astype(int)
    calendar["has_fixture"] = calendar["fixture_count"] > 0
    calendar["gameweek_type"] = "BGW"
    calendar.loc[calendar["fixture_count"] == 1, "gameweek_type"] = "NORMAL"
    calendar.loc[calendar["fixture_count"] >= 2, "gameweek_type"] = "DGW"
    calendar = calendar.sort_values(sort_columns).reset_index(drop=True)

    if len(calendar) != expected_rows:
        raise ValueError(
            "Team-gameweek calendar has an unexpected number of rows. "
            f"Expected {expected_rows}, got {len(calendar)}."
        )

    duplicate_count = int(calendar.duplicated(subset=key_columns).sum())
    if duplicate_count:
        raise ValueError(
            "Team-gameweek calendar contains "
            f"{duplicate_count} duplicate keys."
        )

    print("DEBUG calendar rows:", len(calendar), flush=True)
    print("DEBUG normal team-gameweeks:", int((calendar["gameweek_type"] == "NORMAL").sum()), flush=True)
    print("DEBUG double-gameweek team rows:", int((calendar["gameweek_type"] == "DGW").sum()), flush=True)
    print("DEBUG blank-gameweek team rows:", int((calendar["gameweek_type"] == "BGW").sum()), flush=True)

    return calendar


def build_player_gameweek_data(historical, team_gameweek_calendar):
    """
    Convert fixture-level player data into exactly one canonical row per
    season × player × gameweek, including player rows for BGWs.

    BGW performance columns deliberately remain NULL in the canonical layer.
    Feature calculations later interpret those NULLs as zero performance,
    while the explicit BGW flags preserve the distinction from a normal GW in
    which a player simply did not play.
    """
    df = historical.copy()
    calendar = team_gameweek_calendar.copy()

    required_historical_columns = [
        "season", "gameweek", "player_id", "player_name", "position",
        "team_id", "team_name", "minutes", "starts", "total_points",
        "expected_goals", "expected_assists", "expected_goal_involvements"
    ]
    missing = [c for c in required_historical_columns if c not in df.columns]
    if missing:
        raise ValueError("Historical data is missing required columns: " + ", ".join(missing))

    required_calendar_columns = ["gameweek", "team_id", "fixture_count", "gameweek_type"]
    missing = [c for c in required_calendar_columns if c not in calendar.columns]
    if missing:
        raise ValueError("Team × Gameweek calendar is missing required columns: " + ", ".join(missing))

    # A single-season calendar produced by the existing Streamlit test does
    # not need to carry season. Multi-season data does.
    historical_seasons = df["season"].dropna().unique()
    if "season" not in calendar.columns:
        if len(historical_seasons) != 1:
            raise ValueError(
                "Team × Gameweek calendar has no season column, but historical "
                "data contains multiple seasons. Build a season-aware calendar."
            )
        calendar["season"] = historical_seasons[0]

    numeric_columns = [
        "gameweek", "player_id", "team_id", "minutes", "starts",
        "total_points", "expected_goals", "expected_assists",
        "expected_goal_involvements"
    ]
    for c in numeric_columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["gameweek", "team_id", "fixture_count"]:
        calendar[c] = pd.to_numeric(calendar[c], errors="coerce")

    df = df.dropna(subset=["season", "gameweek", "player_id", "team_id"]).copy()
    calendar = calendar.dropna(subset=["season", "gameweek", "team_id"]).copy()
    df["gameweek"] = df["gameweek"].astype(int)
    df["player_id"] = df["player_id"].astype(int)
    df["team_id"] = df["team_id"].astype(int)
    calendar["gameweek"] = calendar["gameweek"].astype(int)
    calendar["team_id"] = calendar["team_id"].astype(int)
    calendar["fixture_count"] = calendar["fixture_count"].astype(int)

    # Aggregate fixture-level performance to player × GW × team. This is the
    # correct grain for DGWs and also lets us detect the rare transfer-within-
    # GW case instead of silently producing duplicate player-GW rows.
    aggregation = {
        "minutes": "sum", "starts": "sum", "total_points": "sum",
        "expected_goals": "sum", "expected_assists": "sum",
        "expected_goal_involvements": "sum"
    }
    grouped = (
        df.groupby(["season", "gameweek", "player_id", "team_id"], as_index=False)
        .agg(aggregation)
    )

    metadata = (
        df[["season", "gameweek", "player_id", "team_id", "player_name", "position", "team_name"]]
        .drop_duplicates(subset=["season", "gameweek", "player_id", "team_id"])
    )
    grouped = grouped.merge(
        metadata, on=["season", "gameweek", "player_id", "team_id"], how="left"
    )

    team_count_per_player_gw = (
        grouped.groupby(["season", "gameweek", "player_id"])["team_id"].nunique()
    )
    transfer_within_gw = team_count_per_player_gw[team_count_per_player_gw > 1]
    if len(transfer_within_gw):
        examples = list(transfer_within_gw.index[:5])
        raise ValueError(
            "A player appears for multiple teams in the same gameweek. "
            "This requires an explicit transfer-within-GW rule before feature "
            f"engineering. Example keys: {examples}"
        )

    # Attach calendar to observed player rows.
    grouped = grouped.merge(
        calendar[["season", "gameweek", "team_id", "fixture_count", "gameweek_type"]],
        on=["season", "gameweek", "team_id"], how="left", validate="many_to_one"
    )
    missing_calendar = grouped["fixture_count"].isna().sum()
    if missing_calendar:
        raise ValueError(
            f"{missing_calendar} observed player rows could not be matched to the Team × Gameweek calendar."
        )

    # Player active period: only create rows between first and last observed
    # GW. This avoids inventing records before the player entered or after the
    # player left the dataset.
    player_periods = (
        grouped.groupby(["season", "player_id"], as_index=False)
        .agg(first_gameweek=("gameweek", "min"), last_gameweek=("gameweek", "max"))
    )

    skeleton_records = []
    for _, player in player_periods.iterrows():
        for gw in range(int(player["first_gameweek"]), int(player["last_gameweek"]) + 1):
            skeleton_records.append({
                "season": player["season"],
                "player_id": int(player["player_id"]),
                "gameweek": gw,
            })
    skeleton = pd.DataFrame(skeleton_records)

    # Infer team/metadata through gaps. Exact observed GWs always win; ffill
    # handles a BGW after a known team, while bfill handles an initial gap.
    team_history = grouped[[
        "season", "player_id", "gameweek", "team_id",
        "player_name", "position", "team_name"
    ]].sort_values(["season", "player_id", "gameweek"])

    skeleton = skeleton.merge(
        team_history, on=["season", "player_id", "gameweek"], how="left", validate="one_to_one"
    )

    metadata_columns = ["team_id", "player_name", "position", "team_name"]
    skeleton[metadata_columns] = (
        skeleton.groupby(["season", "player_id"])[metadata_columns].ffill()
    )
    skeleton[metadata_columns] = (
        skeleton.groupby(["season", "player_id"])[metadata_columns].bfill()
    )

    if skeleton["team_id"].isna().any():
        raise ValueError("Could not infer a team for one or more player-gameweek rows.")

    # Attach authoritative team calendar.
    skeleton = skeleton.merge(
        calendar[["season", "gameweek", "team_id", "fixture_count", "gameweek_type"]],
        on=["season", "gameweek", "team_id"], how="left", validate="one_to_one"
    )
    if skeleton["fixture_count"].isna().any():
        raise ValueError(
            "One or more inferred player teams are missing from the Team × Gameweek calendar."
        )

    performance_columns = [
        "minutes", "starts", "total_points", "expected_goals",
        "expected_assists", "expected_goal_involvements"
    ]
    performance = grouped[[
        "season", "gameweek", "player_id", "team_id"
    ] + performance_columns]

    canonical = skeleton.merge(
        performance,
        on=["season", "gameweek", "player_id", "team_id"],
        how="left", validate="one_to_one"
    )

    canonical["has_fixture"] = canonical["fixture_count"] > 0
    canonical["is_blank_gameweek"] = canonical["fixture_count"] == 0
    canonical["is_double_gameweek"] = canonical["fixture_count"] > 1

    # Important semantic distinction:
    # BGW -> NULL performance because no fixture existed.
    # Fixture existed but player did not play -> zero performance.
    normal_fixture_mask = canonical["fixture_count"] > 0
    for c in performance_columns:
        canonical.loc[normal_fixture_mask & canonical[c].isna(), c] = 0

    canonical = canonical.sort_values(
        ["season", "player_id", "gameweek"]
    ).reset_index(drop=True)

    duplicate_count = int(
        canonical.duplicated(subset=["season", "gameweek", "player_id"]).sum()
    )
    if duplicate_count:
        raise ValueError(
            f"Canonical player-gameweek dataset contains {duplicate_count} duplicate rows."
        )

    print("DEBUG player-gameweek rows:", len(canonical), flush=True)
    print(
        "DEBUG unique player-gameweek keys:",
        canonical[["season", "gameweek", "player_id"]].drop_duplicates().shape[0],
        flush=True,
    )
    print("DEBUG duplicate player-gameweek keys:", duplicate_count, flush=True)
    print("DEBUG BGW player-gameweek rows:", int(canonical["is_blank_gameweek"].sum()), flush=True)
    print("DEBUG DGW player-gameweek rows:", int(canonical["is_double_gameweek"].sum()), flush=True)

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


def build_form_features(historical, team_gameweek_calendar):
    """
    Build leakage-safe prediction features from the canonical Player × GW data.

    BGWs remain explicit rows. In the raw canonical layer their performance
    fields are NULL so a BGW cannot be confused with an ordinary fixture in
    which the player simply did not play. For feature calculations, however,
    a BGW contributes zero to the historical series because the player scored
    zero FPL points and recorded zero minutes in that calendar gameweek.
    """
    df = build_player_gameweek_data(historical, team_gameweek_calendar)
    df = df.sort_values(["season", "player_id", "gameweek"]).reset_index(drop=True)

    performance_columns = [
        "total_points", "expected_goals", "expected_assists",
        "expected_goal_involvements", "minutes", "starts"
    ]

    # Preserve the canonical values for target construction before zero-filling.
    # A BGW target is a legitimate 0; only the final observed GW should remain
    # without a target.
    target_source = df["total_points"].copy()
    target_source = target_source.where(~df["is_blank_gameweek"], 0)

    # From this point onward, NULL means BGW only, so zero-filling makes each
    # rolling window represent actual calendar GWs rather than previous
    # appearances.
    for c in performance_columns:
        df[c] = df[c].fillna(0)

    grouped = df.groupby(["season", "player_id"], group_keys=False)

    # ---------------------------------------
    # Form
    # ---------------------------------------

    df["previous_gw_points"] = grouped["total_points"].shift(1)
    df["rolling_3gw_points"] = grouped["total_points"].transform(
        lambda x: x.shift(1).rolling(window=3, min_periods=3).mean()
    )
    df["rolling_5gw_points"] = grouped["total_points"].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=5).mean()
    )
    df["rolling_10gw_points"] = grouped["total_points"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=10).mean()
    )

    # ---------------------------------------
    # Underlying performance
    # ---------------------------------------

    df = add_underlying_performance_features(df)

    # ---------------------------------------
    # Playing time
    # ---------------------------------------

    df = add_playing_time_features(df)

    # ---------------------------------------
    # Next calendar Gameweek target
    # ---------------------------------------

    df["next_gw_points"] = (
        target_source.groupby([df["season"], df["player_id"]]).shift(-1)
    )

    print("DEBUG total player-gameweek rows:", len(df), flush=True)
    print(
        "DEBUG null targets before final-GW removal:",
        int(df["next_gw_points"].isna().sum()),
        flush=True,
    )
    print(
        "DEBUG BGW rows included in feature history:",
        int(df["is_blank_gameweek"].sum()),
        flush=True,
    )
    print(
        "DEBUG zero-point next-GW targets:",
        int((df["next_gw_points"] == 0).sum()),
        flush=True,
    )

    # Remove only rows with no following calendar GW. A BGW target is zero and
    # must not be removed.
    df = df.dropna(subset=["next_gw_points"]).copy()

    duplicate_count = int(
        df.duplicated(subset=["season", "gameweek", "player_id"]).sum()
    )
    if duplicate_count:
        raise ValueError(
            "Final prediction feature dataset contains duplicate player-gameweek "
            f"rows: {duplicate_count}"
        )

    print("DEBUG final feature rows:", len(df), flush=True)

    features = df[[
        "season", "gameweek", "player_id", "player_name", "position",
        "team_id", "team_name",
        "previous_gw_points", "rolling_3gw_points", "rolling_5gw_points",
        "rolling_10gw_points",
        "previous_gw_xg", "rolling_3gw_xg", "rolling_5gw_xg",
        "rolling_10gw_xg",
        "previous_gw_xa", "rolling_3gw_xa", "rolling_5gw_xa",
        "rolling_10gw_xa",
        "previous_gw_xgi", "rolling_3gw_xgi", "rolling_5gw_xgi",
        "rolling_10gw_xgi",
        "previous_gw_minutes", "rolling_3gw_minutes", "rolling_5gw_minutes",
        "rolling_10gw_minutes",
        "previous_gw_starts", "rolling_3gw_starts", "rolling_5gw_starts",
        "rolling_10gw_starts",
        "rolling_3gw_start_rate", "rolling_5gw_start_rate",
        "rolling_10gw_start_rate",
        "next_gw_points"
    ]].copy()

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
