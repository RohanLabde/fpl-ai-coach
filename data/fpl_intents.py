"""Deterministic routing for common FPL questions.

The router deliberately handles only high-confidence patterns. Questions outside
those patterns continue to the general grounded tool workflow.
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


def _position_from_question(question):
    """Return an FPL position code when the wording is unambiguous."""
    for position, aliases in _POSITION_ALIASES.items():
        if any(re.search(r"\\b" + re.escape(alias) + r"\\b", question) for alias in aliases):
            return position
    return None


def _ranking_metric(question):
    """Map ordinary FPL wording to one transparent leaderboard metric."""
    if "attacking" in question or "xgi" in question or "expected goal involvement" in question:
        return "attacking"
    if "assist" in question:
        return "assists"
    if "goal" in question:
        return "goals"
    if "threat" in question:
        return "threat"
    if "creativity" in question or "creative" in question:
        return "creativity"
    return "points"


def _requested_limit(question):
    """Use an explicitly requested top-N value, otherwise a helpful default."""
    match = re.search(r"\\b(?:top|best)\\s+(\\d{1,2})\\b", question)
    if not match:
        return 10
    return max(1, min(int(match.group(1)), 15))


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

    is_ranking = any(word in normalized for word in _RANKING_WORDS)
    is_current_season = any(
        phrase in normalized for phrase in _CURRENT_SEASON_WORDS
    )
    if is_ranking and is_current_season:
        metric = _ranking_metric(normalized)
        return {
            "intent": "current_season_leaderboard",
            "tool_name": "get_current_season_leaderboard",
            "arguments": {
                "metric": metric,
                "position": _position_from_question(normalized),
                "limit": _requested_limit(normalized),
            },
            "reason": (
                "The question is an explicit current-season FPL ranking with "
                "a supported default metric."
            ),
        }

    return None
