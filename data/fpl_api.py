import requests


FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def get_fpl_data():
    response = requests.get(FPL_BOOTSTRAP_URL, timeout=30)

    response.raise_for_status()

    return response.json()
