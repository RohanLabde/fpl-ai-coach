import pandas as pd


def prepare_fixture_data(fixtures):
    """
    Prepare the raw FPL fixture data for fixture analysis.
    """

    fixture_data = fixtures[
        [
            "id",
            "event",
            "team_h",
            "team_a",
            "team_h_difficulty",
            "team_a_difficulty",
            "finished",
            "kickoff_time"
        ]
    ].copy()

    fixture_data = fixture_data.rename(
        columns={
            "id": "fixture_id",
            "event": "gameweek",
            "team_h": "home_team_id",
            "team_a": "away_team_id",
            "team_h_difficulty": "home_fixture_difficulty",
            "team_a_difficulty": "away_fixture_difficulty"
        }
    )

    return fixture_data


def get_team_fixture_horizon(
    fixtures,
    team_id,
    current_gameweek,
    horizon=5
):
    """
    Return upcoming fixtures for a team over the next N gameweeks.
    """

    fixture_data = prepare_fixture_data(fixtures)

    # Remove fixtures without a gameweek
    fixture_data = fixture_data.dropna(
        subset=["gameweek"]
    )

    # Only look at future gameweeks
    future_fixtures = fixture_data[
        fixture_data["gameweek"] > current_gameweek
    ].copy()

    # Keep only fixtures involving this team
    team_fixtures = future_fixtures[
        (
            (future_fixtures["home_team_id"] == team_id)
            |
            (future_fixtures["away_team_id"] == team_id)
        )
    ].copy()

    # Only look at the requested horizon
    max_gameweek = current_gameweek + horizon

    team_fixtures = team_fixtures[
        team_fixtures["gameweek"] <= max_gameweek
    ].copy()

    # Determine whether this team is home
    team_fixtures["was_home"] = (
        team_fixtures["home_team_id"] == team_id
    )

    # Select the correct fixture difficulty
    team_fixtures["fixture_difficulty"] = (
        team_fixtures["home_fixture_difficulty"]
        .where(
            team_fixtures["was_home"],
            team_fixtures["away_fixture_difficulty"]
        )
    )

    return team_fixtures[
        [
            "fixture_id",
            "gameweek",
            "was_home",
            "fixture_difficulty",
            "kickoff_time",
            "finished"
        ]
    ].sort_values(
        ["gameweek", "fixture_id"]
    )


def summarize_fixture_horizon(
    fixtures,
    team_id,
    current_gameweek
):
    """
    Create summary fixture features for the next
    1, 3 and 5 gameweeks.
    """

    fixture_data = prepare_fixture_data(fixtures)

    fixture_data = fixture_data.dropna(
        subset=["gameweek"]
    )

    future_fixtures = fixture_data[
        fixture_data["gameweek"] > current_gameweek
    ].copy()

    future_fixtures = future_fixtures[
        (
            (future_fixtures["home_team_id"] == team_id)
            |
            (future_fixtures["away_team_id"] == team_id)
        )
    ].copy()

    future_fixtures["was_home"] = (
        future_fixtures["home_team_id"] == team_id
    )

    future_fixtures["fixture_difficulty"] = (
        future_fixtures["home_fixture_difficulty"]
        .where(
            future_fixtures["was_home"],
            future_fixtures["away_fixture_difficulty"]
        )
    )

    result = {}

    for horizon in [1, 3, 5]:

        horizon_fixtures = future_fixtures[
            future_fixtures["gameweek"]
            <= current_gameweek + horizon
        ]

        result[f"next_{horizon}gw_fixture_count"] = (
            len(horizon_fixtures)
        )

        if len(horizon_fixtures) > 0:
            result[f"next_{horizon}gw_avg_fdr"] = (
                horizon_fixtures["fixture_difficulty"]
                .mean()
            )
        else:
            result[f"next_{horizon}gw_avg_fdr"] = None

    return result

def build_fixture_features(fixtures):
    """
    Build fixture-based prediction features for every
    team and gameweek in the fixture dataset.

    Each row represents:
        team_id + current_gameweek

    Features describe the team's upcoming fixtures
    over the next 1, 3 and 5 gameweeks.
    """

    fixture_data = prepare_fixture_data(fixtures)

    fixture_data = fixture_data.dropna(
        subset=["gameweek"]
    ).copy()

    fixture_data["gameweek"] = (
        fixture_data["gameweek"].astype(int)
    )

    # -----------------------------------
    # Create one row per team per fixture
    # -----------------------------------

    home_fixtures = fixture_data[
        [
            "fixture_id",
            "gameweek",
            "home_team_id",
            "home_fixture_difficulty",
            "kickoff_time",
            "finished"
        ]
    ].copy()

    home_fixtures = home_fixtures.rename(
        columns={
            "home_team_id": "team_id",
            "home_fixture_difficulty": "fixture_difficulty"
        }
    )

    home_fixtures["was_home"] = True

    away_fixtures = fixture_data[
        [
            "fixture_id",
            "gameweek",
            "away_team_id",
            "away_fixture_difficulty",
            "kickoff_time",
            "finished"
        ]
    ].copy()

    away_fixtures = away_fixtures.rename(
        columns={
            "away_team_id": "team_id",
            "away_fixture_difficulty": "fixture_difficulty"
        }
    )

    away_fixtures["was_home"] = False

    team_fixtures = pd.concat(
        [
            home_fixtures,
            away_fixtures
        ],
        ignore_index=True
    )

    # -----------------------------------
    # Create features for every
    # team + current gameweek
    # -----------------------------------

    teams = team_fixtures["team_id"].dropna().unique()
    gameweeks = sorted(
        team_fixtures["gameweek"].dropna().unique()
    )

    rows = []

    for team_id in teams:

        team_data = team_fixtures[
            team_fixtures["team_id"] == team_id
        ].copy()

        for current_gameweek in gameweeks:

            row = {
                "team_id": team_id,
                "gameweek": current_gameweek
            }

            for horizon in [1, 3, 5]:

                horizon_fixtures = team_data[
                    (
                        team_data["gameweek"]
                        > current_gameweek
                    )
                    &
                    (
                        team_data["gameweek"]
                        <= current_gameweek + horizon
                    )
                ]

                # Fixture count
                row[
                    f"next_{horizon}gw_fixture_count"
                ] = len(horizon_fixtures)

                # Average FDR
                if len(horizon_fixtures) > 0:

                    row[
                        f"next_{horizon}gw_avg_fdr"
                    ] = (
                        horizon_fixtures[
                            "fixture_difficulty"
                        ].mean()
                    )

                else:

                    row[
                        f"next_{horizon}gw_avg_fdr"
                    ] = None

                # Home fixtures
                row[
                    f"next_{horizon}gw_home_count"
                ] = int(
                    horizon_fixtures[
                        "was_home"
                    ].sum()
                )

                # Away fixtures
                row[
                    f"next_{horizon}gw_away_count"
                ] = int(
                    (~horizon_fixtures["was_home"]).sum()
                )

            rows.append(row)

    return pd.DataFrame(rows)
