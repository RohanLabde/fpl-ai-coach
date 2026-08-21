import json
import pandas as pd
import requests


PLAYER_HISTORY_URL = (
    "https://raw.githubusercontent.com/"
    "imadeddine-belkat/Premier-League-Stats/"
    "main/fpl_scraper/fpl_stats/_merged/players/"
    "2025-26_all_players_gw.csv"
)

FIXTURES_URL = (
    "https://raw.githubusercontent.com/"
    "imadeddine-belkat/Premier-League-Stats/"
    "main/fpl_scraper/fpl_stats/fixtures/"
    "2025-26_all_fixtures.csv"
)

TEAMS_URL = (
    "https://raw.githubusercontent.com/"
    "imadeddine-belkat/Premier-League-Stats/"
    "main/fpl_scraper/fpl_stats/_index/"
    "_teams_index.json"
)


def load_historical_data():

    players = pd.read_csv(
        PLAYER_HISTORY_URL
    )

    fixtures = pd.read_csv(
        FIXTURES_URL
    )

    return players, fixtures


def load_team_mapping():

    response = requests.get(
        TEAMS_URL,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def create_team_mapping(team_data):

    records = []

    for team_code, seasons in team_data.items():

        if "2025-26" not in seasons:
            continue

        team = seasons["2025-26"]

        records.append({
            "team_code": int(team_code),
            "team_id": int(team["id"]),
            "team_name": team["name"],
            "short_name": team["short_name"]
        })

    return pd.DataFrame(records)

def prepare_historical_data(
    players,
    fixtures,
    teams
):

    # -----------------------------------
    # 1. Prepare fixture data
    # -----------------------------------
    
    fixture_data = fixtures[
        [
            "code",
            "event",
            "id",
            "team_h",
            "team_a",
            "team_h_difficulty",
            "team_a_difficulty"
        ]
    ].copy()
    
    fixture_data = fixture_data.rename(
        columns={
            "code": "fixture_code",
            "event": "gameweek",
            "id": "fixture_id",
            "team_h": "home_team_id",
            "team_a": "away_team_id",
            "team_h_difficulty": "home_fixture_difficulty",
            "team_a_difficulty": "away_fixture_difficulty"
        }
    )
    
    
    # -----------------------------------
    # 2. Map historical team_code
    #    to FPL team_id
    # -----------------------------------
    
    players = players.merge(
        teams[
            [
                "team_code",
                "team_id",
                "team_name",
                "short_name"
            ]
        ],
        on="team_code",
        how="left"
    )
    
    
    # -----------------------------------
    # 3. Join player data with fixtures
    # -----------------------------------
    
    merged = players.merge(
        fixture_data,
        on="fixture_code",
        how="left"
    )
    
    
    # -----------------------------------
    # 4. Determine opponent
    # -----------------------------------
    
    merged["opponent_team_id"] = merged.apply(
        lambda row:
            row["away_team_id"]
            if row["team_id"] == row["home_team_id"]
            else row["home_team_id"],
        axis=1
    )
    
    
    # -----------------------------------
    # 5. Determine home/away
    # -----------------------------------
    
    merged["was_home"] = (
        merged["team_id"] ==
        merged["home_team_id"]
    )
    
    
    # -----------------------------------
    # 6. Determine fixture difficulty
    # -----------------------------------
    
    merged["fixture_difficulty"] = (
        merged["home_fixture_difficulty"]
        .where(
            merged["was_home"],
            merged["away_fixture_difficulty"]
        )
    )
    
    
    # -----------------------------------
    # 7. Rename player identifier
    # -----------------------------------
    
    merged = merged.rename(
        columns={
            "element": "player_id",
            "first_name": "first_name",
            "second_name": "second_name"
        }
    )
    
    
    # -----------------------------------
    # 8. Create player name
    # -----------------------------------
    
    merged["player_name"] = (
        merged["first_name"].fillna("")
        + " "
        + merged["second_name"].fillna("")
    ).str.strip()
    
    
    # -----------------------------------
    # 9. Create season
    # -----------------------------------
    
    merged["season"] = "2025-26"
    
    
    return merged

def prepare_database_records(historical):

    records = historical[
        [
            "season",
            "gameweek",
            "player_id",
            "player_name",
            "position",
            "team_id",
            "team_code",
            "team_name",
            "fixture_id",
            "fixture_code",
            "opponent_team_id",
            "was_home",
            "minutes",
            "starts",
            "total_points",
            "goals_scored",
            "assists",
            "clean_sheets",
            "goals_conceded",
            "own_goals",
            "penalties_saved",
            "penalties_missed",
            "saves",
            "yellow_cards",
            "red_cards",
            "bonus",
            "bps",
            "influence",
            "creativity",
            "threat",
            "ict_index",
            "clearances_blocks_interceptions",
            "recoveries",
            "tackles",
            "defensive_contribution",
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "expected_goals_conceded",
            "value",
            "transfers_balance",
            "selected",
            "transfers_in",
            "transfers_out",
            "fixture_difficulty"
        ]
    ].copy()

    # Convert FPL's price representation.
    # Example: 55 = £5.5m
    records["price"] = (
        pd.to_numeric(
            records["value"],
            errors="coerce"
        ) / 10
    )

    records = records.drop(
        columns=["value"]
    )

    # Convert numeric columns
    numeric_columns = [
        "gameweek",
        "player_id",
        "team_id",
        "team_code",
        "fixture_id",
        "fixture_code",
        "opponent_team_id",
        "minutes",
        "starts",
        "total_points",
        "goals_scored",
        "assists",
        "clean_sheets",
        "goals_conceded",
        "own_goals",
        "penalties_saved",
        "penalties_missed",
        "saves",
        "yellow_cards",
        "red_cards",
        "bonus",
        "bps",
        "influence",
        "creativity",
        "threat",
        "ict_index",
        "clearances_blocks_interceptions",
        "recoveries",
        "tackles",
        "defensive_contribution",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
        "price",
        "transfers_balance",
        "selected",
        "transfers_in",
        "transfers_out"
    ]

    for column in numeric_columns:

        records[column] = pd.to_numeric(
            records[column],
            errors="coerce"
        )

    # Replace pandas NaN values with Python None.
    # PostgreSQL understands None as NULL.
    records = records.astype(object).where(
        pd.notna(records),
        None
    )

    return records
