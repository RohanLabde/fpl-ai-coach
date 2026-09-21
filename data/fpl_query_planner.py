"""Structured planning for FPL Copilot questions.

The language model may interpret natural language, but it cannot choose arbitrary
database operations.  Its output is constrained to a small query-plan contract
which this module validates before the application executes any read-only tool.
"""

import json
import re


_ALLOWED_INTENTS = {
    "data_status",
    "leaderboard",
    "player_form",
    "player_profile",
    "upcoming_fixtures",
    "compare_players",
    "team_fixture_horizon",
    "team_strength",
    "fpl_picks",
    "unsupported",
}
_ALLOWED_POSITIONS = {"GKP", "DEF", "MID", "FWD", "NONE"}
_ALLOWED_METRICS = {
    "attacking",
    "points",
    "xgi",
    "goals",
    "assists",
    "threat",
    "creativity",
    "defensive",
    "clean_sheets",
    "defensive_contribution",
    "goalkeeping",
    "NONE",
}
_ALLOWED_SCOPES = {
    "performance",
    "attacking_form",
    "defensive_form",
    "goalkeeping_form",
    "fpl_points",
    "player_research",
    "fixture_research",
    "fixture_horizon",
    "team_attacking_form",
    "team_defensive_form",
    "data_coverage",
    "fpl_pick_research",
    "unknown",
}

PLANNER_INSTRUCTIONS = """
You are the query planner for FPL Copilot. Convert the user's FPL question into
one safe, structured plan. Do not answer the question, do not invent facts, do
not call tools, and do not write SQL.

Use these intents only:
- data_status: data coverage, freshness, seasons available.
- leaderboard: a current-season ranking of players.
- player_form: finalized recent form for one named player.
- player_profile: current price, availability, ownership, team, or status for
  one named player.
- upcoming_fixtures: future fixtures for one named player.
- compare_players: comparison of exactly two named players.
- team_fixture_horizon: rank all teams by the difficulty of their next N fixtures.
- team_strength: rank teams by recent attacking or defensive form.
- fpl_picks: transparent, non-personal MID or DEF candidate ranking using
  recent finalized form, upcoming fixture difficulty, price, and starts.
- unsupported: transfer, captaincy, squad, chip, or injury/line-up advice that
  cannot be grounded with the currently available data.

Position-aware ranking defaults:
- DEF + unspecified "best" -> defensive.
- GKP + unspecified "best" -> goalkeeping.
- MID or FWD + unspecified "best" -> attacking.
- No position + unspecified "best" -> points.
Explicit wording such as goals, assists, clean sheets, defensive contribution,
FPL points, threat, creativity, xGI, or attacking always overrides a default.

Use current_season for player rankings. Use team_fixture_horizon for questions
such as "which team has the easiest next five fixtures"; set gameweeks to that
fixture horizon. Use team_strength for "best attacks" or "best defences"; use
attacking or defensive as the metric and gameweeks as the recent form window.
Use recent_form for questions about a player's last N gameweeks, defaulting to
5. Include only names that are explicitly
present in the question or clearly resolved from the supplied conversation
context. Return unsupported rather than guessing a player or claiming the app
can see the user's FPL team.
Use fpl_picks only for midfielders or defenders when the question explicitly
asks for FPL picks/options/value or combines a position with upcoming fixtures.
Set max_price only when the user supplies a budget in £m. This is not transfer
advice: it is a transparent candidate list.
""".strip()

QUERY_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string", "enum": sorted(_ALLOWED_INTENTS)},
        "player_names": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 2,
        },
        "position": {"type": "string", "enum": sorted(_ALLOWED_POSITIONS)},
        "metric": {"type": "string", "enum": sorted(_ALLOWED_METRICS)},
        "scope": {"type": "string", "enum": sorted(_ALLOWED_SCOPES)},
        "gameweeks": {"type": "integer", "minimum": 1, "maximum": 10},
        "limit": {"type": "integer", "minimum": 1, "maximum": 15},
        "max_price": {"type": ["number", "null"], "minimum": 3, "maximum": 20},
        "needs_clarification": {"type": "boolean"},
        "clarification": {"type": "string"},
    },
    "required": [
        "intent",
        "player_names",
        "position",
        "metric",
        "scope",
        "gameweeks",
        "limit",
        "max_price",
        "needs_clarification",
        "clarification",
    ],
}


def _default_metric(position):
    return {
        "DEF": "defensive",
        "GKP": "goalkeeping",
        "MID": "attacking",
        "FWD": "attacking",
    }.get(position, "points")


def _clean_player_names(names):
    cleaned = []
    for name in names if isinstance(names, list) else []:
        text = re.sub(r"\s+", " ", str(name)).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned[:2]


def _bounded_int(value, lower, upper, default):
    try:
        return max(lower, min(int(value), upper))
    except (TypeError, ValueError):
        return default


def _bounded_price(value):
    try:
        return max(3.0, min(float(value), 20.0))
    except (TypeError, ValueError):
        return None


_PROFILE_SIGNAL_WORDS = (
    "price",
    "ownership",
    "owned",
    "availability",
    "available",
    "status",
    "current form",
    "selected by",
)


def _deterministic_profile_plan(question):
    """Handle common possessive player-profile wording without model routing."""
    normalized = " ".join(str(question).lower().split())
    if not any(signal in normalized for signal in _PROFILE_SIGNAL_WORDS):
        return None

    match = re.search(r"\b([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]{1,})[’']s\b", str(question))
    if not match:
        return None

    name = match.group(1)
    if name.casefold() in {"team", "player", "fpl"}:
        return None
    return normalise_query_plan(
        {
            "intent": "player_profile",
            "player_names": [name],
            "position": "NONE",
            "metric": "NONE",
            "scope": "player_research",
            "gameweeks": 5,
            "limit": 10,
            "max_price": None,
            "needs_clarification": False,
            "clarification": "",
        }
    )


_PLAYER_FORM_PATTERN = re.compile(
    r"^\s*how\s+has\s+"
    r"(?P<name>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]*(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]*){0,3})"
    r"\s+performed"
    r"(?:\s+(?:over\s+)?(?:the\s+)?(?:last|recent)\s+"
    r"(?P<gameweeks>\d{1,2})\s+game\s*weeks?)?\s*[?!.]*\s*$",
    re.IGNORECASE,
)


def _deterministic_player_form_plan(question):
    """Route explicit 'How has [player] performed?' form questions locally."""
    match = _PLAYER_FORM_PATTERN.match(str(question))
    if not match:
        return None

    return normalise_query_plan(
        {
            "intent": "player_form",
            "player_names": [match.group("name")],
            "position": "NONE",
            "metric": "NONE",
            "scope": "performance",
            "gameweeks": match.group("gameweeks") or 5,
            "limit": 10,
            "max_price": None,
            "needs_clarification": False,
            "clarification": "",
        }
    )


def normalise_query_plan(raw):
    """Validate a model plan and apply safe, position-aware defaults."""
    raw = raw if isinstance(raw, dict) else {}
    intent = raw.get("intent") if raw.get("intent") in _ALLOWED_INTENTS else "unsupported"
    position = raw.get("position") if raw.get("position") in _ALLOWED_POSITIONS else "NONE"
    metric = raw.get("metric") if raw.get("metric") in _ALLOWED_METRICS else "NONE"
    scope = raw.get("scope") if raw.get("scope") in _ALLOWED_SCOPES else "unknown"
    names = _clean_player_names(raw.get("player_names"))

    if intent == "leaderboard" and metric == "NONE":
        metric = _default_metric(position)
    if intent == "team_strength" and metric not in {"attacking", "defensive"}:
        metric = "attacking"
    clarification = str(raw.get("clarification") or "").strip()
    needs_clarification = bool(raw.get("needs_clarification"))
    if intent == "fpl_picks":
        if position not in {"MID", "DEF"}:
            intent = "unsupported"
            needs_clarification = True
            clarification = (
                "I can currently provide transparent FPL pick candidates for "
                "midfielders or defenders."
            )
        elif scope == "unknown":
            scope = "fpl_pick_research"
    if intent == "leaderboard" and scope == "unknown":
        scope = {
            "DEF": "defensive_form",
            "GKP": "goalkeeping_form",
            "MID": "attacking_form",
            "FWD": "attacking_form",
        }.get(position, "fpl_points")


    required_names = {
        "player_form": 1,
        "player_profile": 1,
        "upcoming_fixtures": 1,
        "compare_players": 2,
    }
    if intent in required_names and len(names) < required_names[intent]:
        intent = "unsupported"
        needs_clarification = True
        clarification = (
            "Please name the player" if required_names.get(raw.get("intent")) == 1
            else "Please name the two players you want to compare."
        )
    elif intent in {"player_form", "player_profile", "upcoming_fixtures"}:
        # A single-player lookup must never silently switch to another name.
        names = names[:1]

    return {
        "intent": intent,
        "player_names": names,
        "position": None if position == "NONE" else position,
        "metric": None if metric == "NONE" else metric,
        "scope": scope,
        "gameweeks": _bounded_int(raw.get("gameweeks"), 1, 10, 5),
        "limit": _bounded_int(raw.get("limit"), 1, 15, 10),
        "max_price": _bounded_price(raw.get("max_price")) if intent == "fpl_picks" else None,
        "needs_clarification": needs_clarification,
        "clarification": clarification,
    }


def plan_fpl_question(client, model, question, conversation_context=""):
    """Ask OpenAI for a constrained plan, then validate it locally."""
    deterministic_profile = _deterministic_profile_plan(question)
    if deterministic_profile:
        return deterministic_profile

    deterministic_player_form = _deterministic_player_form_plan(question)
    if deterministic_player_form:
        return deterministic_player_form

    response = client.responses.create(
        model=model,
        instructions=PLANNER_INSTRUCTIONS,
        input=[
            {
                "role": "user",
                "content": (
                    "Conversation context (may be empty):\n"
                    f"{conversation_context}\n\n"
                    "Current user question:\n"
                    f"{question}"
                ),
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "fpl_query_plan",
                "strict": True,
                "schema": QUERY_PLAN_SCHEMA,
            }
        },
        max_output_tokens=350,
        store=False,
    )
    try:
        return normalise_query_plan(json.loads(response.output_text))
    except (TypeError, ValueError, json.JSONDecodeError):
        return normalise_query_plan({"intent": "unsupported"})
