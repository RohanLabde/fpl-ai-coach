import requests


FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"


def get_fpl_data():

    response = requests.get(
        FPL_BOOTSTRAP_URL,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def get_fixtures():

    response = requests.get(
        FPL_FIXTURES_URL,
        timeout=30
    )

    response.raise_for_status()

    return response.json()
