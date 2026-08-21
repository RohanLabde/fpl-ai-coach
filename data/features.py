import pandas as pd


def build_form_features(historical):

    df = historical.copy()

    # ---------------------------------------
    # 1. Sort chronologically
    # ---------------------------------------

    df = df.sort_values(
        [
            "season",
            "player_id",
            "gameweek"
        ]
    ).reset_index(drop=True)


    # ---------------------------------------
    # 2. Previous Gameweek points
    #
    # For GW10, this gives GW9 points.
    # ---------------------------------------

    df["previous_gw_points"] = (
        df
        .groupby(
            ["season", "player_id"]
        )["total_points"]
        .shift(1)
    )


    # ---------------------------------------
    # 3. Rolling 3 GW average
    #
    # IMPORTANT:
    # shift(1) happens BEFORE rolling.
    #
    # Therefore GW10 can only see:
    # GW7, GW8, GW9
    # ---------------------------------------

    df["rolling_3gw_points"] = (
        df
        .groupby(
            ["season", "player_id"]
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
    # 4. Rolling 5 GW average
    # ---------------------------------------

    df["rolling_5gw_points"] = (
        df
        .groupby(
            ["season", "player_id"]
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
    # 5. Rolling 10 GW average
    # ---------------------------------------

    df["rolling_10gw_points"] = (
        df
        .groupby(
            ["season", "player_id"]
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


    # Add underlying performance features

    df = add_underlying_performance_features(
        df
    )
    
    # Add playing-time features
    
    df = add_playing_time_features(
        df
    )
    
    # Actual points in target GW
    
    df["next_gw_points"] = df["total_points"]

    # ---------------------------------------
    # 8. Keep only the fields we currently need
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
    ).reset_index(drop=True)


    # ---------------------------------------
    # Helper function
    # ---------------------------------------

    def add_rolling_features(
        source_column,
        prefix
    ):

        # Previous Gameweek
        df[f"previous_gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
            )[source_column]
            .shift(1)
        )


        # Previous 3 Gameweeks
        df[f"rolling_3gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
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


        # Previous 5 Gameweeks
        df[f"rolling_5gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
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


        # Previous 10 Gameweeks
        df[f"rolling_10gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
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
    ).reset_index(drop=True)


    # ---------------------------------------
    # Helper function
    # ---------------------------------------

    def add_rolling_features(
        source_column,
        prefix
    ):

        # Previous Gameweek
        df[f"previous_gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
            )[source_column]
            .shift(1)
        )


        # Rolling 3 Gameweeks
        df[f"rolling_3gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
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
        df[f"rolling_5gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
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
        df[f"rolling_10gw_{prefix}"] = (
            df
            .groupby(
                ["season", "player_id"]
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

    df["rolling_3gw_start_rate"] = (
        df
        .groupby(
            ["season", "player_id"]
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

    df["rolling_5gw_start_rate"] = (
        df
        .groupby(
            ["season", "player_id"]
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

    df["rolling_10gw_start_rate"] = (
        df
        .groupby(
            ["season", "player_id"]
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
