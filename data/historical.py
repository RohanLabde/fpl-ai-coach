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
