import pandas as pd


NEXT_GW_FIXTURE_COLUMNS = [
    "next_1gw_fixture_count",
    "next_1gw_avg_fdr",
    "next_1gw_home_count",
    "next_1gw_away_count",
]

NEXT_GW_OPPONENT_DEFENCE_COLUMNS = [
    "next_1gw_opponent_avg_5fixture_goals_conceded",
    "next_1gw_opponent_avg_5fixture_clean_sheet_rate",
]


def prepare_fixture_data(fixtures):
    """Normalize raw FPL fixture data for team-level feature engineering."""
    required = [
        "id", "event", "team_h", "team_a", "team_h_difficulty",
        "team_a_difficulty", "finished", "kickoff_time",
    ]
    missing = [column for column in required if column not in fixtures.columns]
    if missing:
        raise ValueError(f"Fixture data is missing required columns: {missing}")

    optional_scores = ["team_h_score", "team_a_score"]
    available = [column for column in optional_scores if column in fixtures.columns]
    result = fixtures[required + available].copy().rename(
        columns={
            "id": "fixture_id",
            "event": "gameweek",
            "team_h": "home_team_id",
            "team_a": "away_team_id",
            "team_h_difficulty": "home_fixture_difficulty",
            "team_a_difficulty": "away_fixture_difficulty",
        }
    )

    for column in optional_scores:
        if column not in result.columns:
            result[column] = pd.NA

    return result


def _team_fixture_rows(fixtures):
    fixture_data = prepare_fixture_data(fixtures).dropna(subset=["gameweek"]).copy()
    fixture_data["gameweek"] = pd.to_numeric(
        fixture_data["gameweek"], errors="raise"
    ).astype(int)

    home = fixture_data[
        ["fixture_id", "gameweek", "home_team_id", "away_team_id", "home_fixture_difficulty", "team_a_score", "kickoff_time", "finished"]
    ].rename(
        columns={
            "home_team_id": "team_id",
            "away_team_id": "opponent_team_id",
            "home_fixture_difficulty": "fixture_difficulty",
            "team_a_score": "goals_conceded",
        }
    )
    home["was_home"] = True

    away = fixture_data[
        ["fixture_id", "gameweek", "away_team_id", "home_team_id", "away_fixture_difficulty", "team_h_score", "kickoff_time", "finished"]
    ].rename(
        columns={
            "away_team_id": "team_id",
            "home_team_id": "opponent_team_id",
            "away_fixture_difficulty": "fixture_difficulty",
            "team_h_score": "goals_conceded",
        }
    )
    away["was_home"] = False

    return pd.concat([home, away], ignore_index=True)


def get_team_fixture_horizon(fixtures, team_id, current_gameweek, horizon=5):
    """Return one team's next fixtures after current_gameweek."""
    rows = _team_fixture_rows(fixtures)
    result = rows[
        rows["team_id"].eq(team_id)
        & rows["gameweek"].gt(current_gameweek)
        & rows["gameweek"].le(current_gameweek + horizon)
    ].copy()

    return result[
        ["fixture_id", "gameweek", "was_home", "fixture_difficulty", "kickoff_time", "finished"]
    ].sort_values(["gameweek", "fixture_id"])


def summarize_fixture_horizon(fixtures, team_id, current_gameweek):
    """Summarize one team's next 1, 3, and 5 calendar gameweeks."""
    rows = _team_fixture_rows(fixtures)
    team_rows = rows[
        rows["team_id"].eq(team_id) & rows["gameweek"].gt(current_gameweek)
    ]

    summary = {}
    for horizon in (1, 3, 5):
        horizon_rows = team_rows[
            team_rows["gameweek"].le(current_gameweek + horizon)
        ]
        summary[f"next_{horizon}gw_fixture_count"] = len(horizon_rows)
        summary[f"next_{horizon}gw_avg_fdr"] = (
            horizon_rows["fixture_difficulty"].mean()
            if not horizon_rows.empty else None
        )
    return summary


def _opponent_defence_as_of(team_rows, current_gameweek, lookback=5):
    """Return a team's defensive record from fixtures completed by current_gw."""
    completed = team_rows[
        team_rows["gameweek"].le(current_gameweek)
        & team_rows["finished"].eq(True)
        & team_rows["goals_conceded"].notna()
    ].sort_values(["gameweek", "fixture_id"])

    recent = completed.tail(lookback)
    if len(recent) < lookback:
        return None, None

    goals_conceded = pd.to_numeric(
        recent["goals_conceded"], errors="coerce"
    )

    return (
        goals_conceded.mean(),
        (goals_conceded.eq(0)).mean(),
    )


def build_fixture_features(fixtures, season=None):
    """Build future-fixture features for every team and current gameweek.

    A row at gameweek t contains only fixtures scheduled in gameweeks after t.
    It is therefore safe to join to a feature row at t when predicting the
    next-calendar-gameweek target.
    """
    team_fixtures = _team_fixture_rows(fixtures)
    teams = sorted(team_fixtures["team_id"].dropna().unique())
    gameweeks = sorted(team_fixtures["gameweek"].dropna().unique())
    rows = []
    team_history = {
        team_id: team_fixtures[team_fixtures["team_id"].eq(team_id)]
        for team_id in teams
    }

    for team_id in teams:
        team_rows = team_fixtures[team_fixtures["team_id"].eq(team_id)]

        for current_gameweek in gameweeks:
            row = {"team_id": int(team_id), "gameweek": int(current_gameweek)}
            if season is not None:
                row["season"] = season

            for horizon in (1, 3, 5):
                horizon_rows = team_rows[
                    team_rows["gameweek"].gt(current_gameweek)
                    & team_rows["gameweek"].le(current_gameweek + horizon)
                ]

                row[f"next_{horizon}gw_fixture_count"] = len(horizon_rows)
                row[f"next_{horizon}gw_avg_fdr"] = (
                    horizon_rows["fixture_difficulty"].mean()
                    if not horizon_rows.empty else None
                )
                row[f"next_{horizon}gw_home_count"] = int(horizon_rows["was_home"].sum())
                row[f"next_{horizon}gw_away_count"] = int((~horizon_rows["was_home"]).sum())

            immediate_opponent_goals_conceded = []
            immediate_opponent_clean_sheet_rates = []

            for opponent_id in team_rows[
                team_rows["gameweek"].eq(current_gameweek + 1)
            ]["opponent_team_id"].dropna().unique():
                goals_conceded, clean_sheet_rate = _opponent_defence_as_of(
                    team_history[int(opponent_id)],
                    current_gameweek,
                )
                if goals_conceded is not None:
                    immediate_opponent_goals_conceded.append(goals_conceded)
                    immediate_opponent_clean_sheet_rates.append(clean_sheet_rate)

            row["next_1gw_opponent_avg_5fixture_goals_conceded"] = (
                sum(immediate_opponent_goals_conceded)
                / len(immediate_opponent_goals_conceded)
                if immediate_opponent_goals_conceded else None
            )
            row["next_1gw_opponent_avg_5fixture_clean_sheet_rate"] = (
                sum(immediate_opponent_clean_sheet_rates)
                / len(immediate_opponent_clean_sheet_rates)
                if immediate_opponent_clean_sheet_rates else None
            )

            rows.append(row)

    result = pd.DataFrame(rows)
    key_columns = ["season", "gameweek", "team_id"] if season is not None else ["gameweek", "team_id"]
    if result.duplicated(subset=key_columns).any():
        raise ValueError("Fixture feature data contains duplicate team-gameweek keys.")
    return result.sort_values(key_columns).reset_index(drop=True)


def attach_fixture_features(prediction_features, fixture_features):
    """Attach next-GW fixture context using season × gameweek × team keys."""
    key_columns = ["season", "gameweek", "team_id"]
    required_prediction = key_columns.copy()
    required_fixture = (
        key_columns
        + NEXT_GW_FIXTURE_COLUMNS
        + NEXT_GW_OPPONENT_DEFENCE_COLUMNS
    )

    missing_prediction = [c for c in required_prediction if c not in prediction_features.columns]
    missing_fixture = [c for c in required_fixture if c not in fixture_features.columns]
    if missing_prediction:
        raise ValueError(f"Prediction features are missing join keys: {missing_prediction}")
    if missing_fixture:
        raise ValueError(f"Fixture features are missing columns: {missing_fixture}")

    result = prediction_features.merge(
        fixture_features[
            key_columns
            + NEXT_GW_FIXTURE_COLUMNS
            + NEXT_GW_OPPONENT_DEFENCE_COLUMNS
        ],
        on=key_columns,
        how="left",
        validate="many_to_one",
    )

    if result[NEXT_GW_FIXTURE_COLUMNS].isna().all(axis=1).any():
        raise ValueError("Some prediction rows have no matching fixture features.")

    return result
