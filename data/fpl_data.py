import pandas as pd


def get_players(data):

    return pd.DataFrame(data["elements"])


def get_teams(data):

    return pd.DataFrame(data["teams"])


def get_fixtures(data):

    return pd.DataFrame(data["fixtures"])
