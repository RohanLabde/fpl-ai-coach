import pandas as pd


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


def load_historical_data():

    players = pd.read_csv(
        PLAYER_HISTORY_URL
    )

    fixtures = pd.read_csv(
        FIXTURES_URL
    )

    return players, fixtures
