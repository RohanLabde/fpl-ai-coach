"""Live FPL refresh workflow: current snapshot, fixtures, and audit record."""

import pandas as pd

from data.db import save_live_fpl_snapshot
from data.fpl_api import get_fixtures, get_fpl_data
from data.fpl_data import get_players


def _event_numbers(payload):
    """Return the active and last fully finished gameweek from FPL events."""
    events = pd.DataFrame(payload.get("events", []))
    if events.empty:
        return None, None

    current = events.loc[events.get("is_current", False) == True, "id"]
    if current.empty:
        current = events.loc[events.get("is_next", False) == True, "id"]

    finished = events.loc[events.get("finished", False) == True, "id"]
    current_gameweek = int(current.iloc[0]) if not current.empty else None
    latest_finished = int(finished.max()) if not finished.empty else None
    return current_gameweek, latest_finished


def refresh_live_fpl_data():
    """Fetch FPL's current public data and save a queryable, timestamped copy."""
    payload = get_fpl_data()
    fixtures = pd.DataFrame(get_fixtures())
    players = get_players(payload)

    teams = pd.DataFrame(payload.get("teams", []))
    team_names = dict(zip(teams.get("id", []), teams.get("name", [])))
    current_gameweek, latest_finished_gameweek = _event_numbers(payload)

    return save_live_fpl_snapshot(
        players=players,
        fixtures=fixtures,
        team_names=team_names,
        current_gameweek=current_gameweek,
        latest_finished_gameweek=latest_finished_gameweek,
    )
