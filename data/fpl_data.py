import pandas as pd


def get_players(data):

    players = pd.DataFrame(data["elements"])

    teams = pd.DataFrame(data["teams"])
    positions = pd.DataFrame(data["element_types"])

    team_map = dict(
        zip(
            teams["id"],
            teams["name"]
        )
    )

    position_map = dict(
        zip(
            positions["id"],
            positions["singular_name"]
        )
    )

    players["team_name"] = players["team"].map(team_map)

    players["position"] = players["element_type"].map(
        position_map
    )

    players["price"] = players["now_cost"] / 10

    return players


def get_teams(data):

    return pd.DataFrame(data["teams"])


def get_fixtures(data):

    return pd.DataFrame(data)
