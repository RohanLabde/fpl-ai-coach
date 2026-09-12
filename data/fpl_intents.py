"""Deterministic routing for common FPL questions.

The router handles only high-confidence patterns.  It maps natural FPL language
to transparent, position-aware ranking profiles; questions outside those
patterns continue to the general grounded tool workflow.
"""

import re


_POSITION_ALIASES = {
    "GKP": ("goalkeeper", "goalkeepers", "keeper", "keepers", "gkp"),
    "DEF": ("defender", "defenders", "defence", "defense", "def", "defs"),
    "MID": ("midfielder", "midfielders", "midfield", "mid", "mids"),
    "FWD": ("forward", "forwards", "striker", "strikers", "fwd", "fwds"),
}

_RANKING_WORDS = ("top", "best", "leader", "leaders", "rank", "highest")
_CURRENT_SEASON_WORDS = ("this season", "current season", "season so far")
_DATA_STATUS_WORDS = (
    "data coverage",
    "what data",
    "which years",
    "how current",
    "data freshness",
    "latest data",
)
_TEAM_FIXTURE_WORDS = ("fixture", "fixtures", "schedule", "run")
_EASY_FIXTURE_WORDS = ("easiest", "easy", "best run", "lowest difficulty")
_TEAM_STRENGTH_WORDS = ("best", "strongest", "top", "leader", "leaders", "rank")

# These are answer-design defaults, not claims that other metrics are irrelevant.
# A request for a different explicit metric always overrides the profile.
_POSITION_DEFAULT_METRICS = {
    "GKP": "goalkeeping",
    "DEF": "defensive",
    "MID": "attacking",
    "FWD": "attacking",
}


def _position_from_question(question):
    """Return an FPL position code when the wording is unambiguous."""
    for position, aliases in _POSITION_ALIASES.items():
        if any(re.search(r"\b" + re.escape(alias) + r"\b", question) for alias in aliases):
            return position
    return None


def _ranking_metric(question, position):
    """Map ordinary FPL wording to a transparent, position-aware metric."""
    # Explicit user intent always has priority over a positional default.
    if "clean sheet" in question:
        return "clean_sheets"
    if "defensive contribution" in question or "defensive form" in question:
        return "defensive_contribution"
    if "goalkeeper" in question or "goalkeeping" in question or "keeper" in question:
        return "goalkeeping"
    if "attacking" in question or "xgi" in question or "expected goal involvement" in question:
        return "attacking"
    if "fpl points" in question or "total points" in question or "points leader" in question:
        return "points"
    if "assist" in question:
        return "assists"
    if "goal" in question:
        return "goals"
    if "threat" in question:
        return "threat"
    if "creativity" in question or "creative" in question:
        return "creativity"
    return _POSITION_DEFAULT_METRICS.get(position, "points")


def _requested_limit(question):
    """Use an explicitly requested top-N value, otherwise a helpful default."""
    match = re.search(r"\b(?:top|best)\s+(\d{1,2})\b", question)
    if not match:
        return 10
    return max(1, min(int(match.group(1)), 15))


def _requested_gameweeks(question, default=5):
    """Extract a next-N fixture or recent-N-gameweek horizon."""
    match = re.search(
        r"\b(?:next|last|recent)\s+(\d{1,2})\s+(?:fixtures?|gameweeks?)\b",
        question,
    )
    if not match:
        return default
    return max(1, min(int(match.group(1)), 10))


def route_fpl_question(question):
    """Return a high-confidence data plan, or None for general tool routing."""
    normalized = " ".join(question.lower().split())

    if any(phrase in normalized for phrase in _DATA_STATUS_WORDS):
        return {
            "intent": "data_status",
            "tool_name": "get_fpl_data_status",
            "arguments": {},
            "reason": "The question asks about available FPL data or freshness.",
        }

    asks_about_team = "team" in normalized or "teams" in normalized
    asks_about_fixtures = any(word in normalized for word in _TEAM_FIXTURE_WORDS)
    if asks_about_team and asks_about_fixtures and any(
        word in normalized for word in _EASY_FIXTURE_WORDS
    ):
        horizon = _requested_gameweeks(normalized)
        return {
            "intent": "team_fixture_horizon",
            "tool_name": "get_team_fixture_horizon",
            "arguments": {"horizon": horizon, "limit": _requested_limit(normalized)},
            "reason": (
                "The question asks for the easiest upcoming team fixture run, "
                "ranked by average official FPL difficulty."
            ),
        }

    if asks_about_team and any(
        word in normalized for word in _TEAM_STRENGTH_WORDS
    ):
        if any(word in normalized for word in ("defence", "defense", "defensive")):
            metric = "defensive"
        elif any(word in normalized for word in ("attack", "attacking", "goals", "xg")):
            metric = "attacking"
        else:
            metric = None
        if metric:
            gameweeks = _requested_gameweeks(normalized)
            return {
                "intent": "team_strength",
                "tool_name": "get_team_strength_leaderboard",
                "arguments": {
                    "metric": metric,
                    "gameweeks": gameweeks,
                    "limit": _requested_limit(normalized),
                },
                "reason": (
                    "The question asks for recent team form, using a transparent "
                    "attacking or defensive ranking profile."
                ),
            }

    is_ranking = any(re.search(r"\b" + re.escape(word) + r"\b", normalized)
                     for word in _RANKING_WORDS)
    is_current_season = any(
        phrase in normalized for phrase in _CURRENT_SEASON_WORDS
    )
    if is_ranking and is_current_season:
        position = _position_from_question(normalized)
        metric = _ranking_metric(normalized, position)
        return {
            "intent": "current_season_leaderboard",
            "tool_name": "get_current_season_leaderboard",
            "arguments": {
                "metric": metric,
                "position": position,
                "limit": _requested_limit(normalized),
            },
            "reason": (
                "The question is an explicit current-season FPL ranking. "
                "The selected ranking profile is position-aware unless the "
                "user supplied a more specific metric."
            ),
        }

    return None
