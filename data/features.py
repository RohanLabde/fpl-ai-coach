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


    # ---------------------------------------
    # 6. Actual points in the target GW
    #
    # This is what the model will eventually
    # learn to predict.
    # ---------------------------------------

    df["next_gw_points"] = (
        df["total_points"]
    )


    # ---------------------------------------
    # 7. Keep only the fields we currently need
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

            "previous_gw_points",
            "rolling_3gw_points",
            "rolling_5gw_points",
            "rolling_10gw_points",

            "next_gw_points"
        ]
    ].copy()


    return features
