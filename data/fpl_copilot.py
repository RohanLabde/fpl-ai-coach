"""Grounded, read-only FPL chat assistant for the Streamlit application."""

import json

import streamlit as st

from data.db import (
    get_fpl_data_status,
    get_form_leaderboard,
    get_latest_feature_snapshot,
    get_live_player_profile,
    get_player_recent_form,
    get_player_upcoming_fixtures,
    search_fpl_players,
)
from data.fpl_live import refresh_live_fpl_data

try:
    from openai import OpenAI
except ImportError:  # Keep the rest of the Streamlit app usable until installed.
    OpenAI = None


DEFAULT_MODEL = "gpt-5-mini"
MAX_TOOL_ROUNDS = 3

SYSTEM_INSTRUCTIONS = """
You are FPL Copilot, a careful Fantasy Premier League research assistant.

Answer only FPL questions. Use the supplied database functions before making
factual claims about a player, form, fixtures, price, or model feature data.
Do not claim that historical data is live. The function output labels each
source: repeat that limitation whenever it is relevant. In particular,
prediction_features contains historical feature snapshots, not a current live
forecast. Do not fabricate injuries, line-ups, future fixtures, rules, prices,
or recommendation rankings when they have not been supplied by a function.

Keep answers concise and practical. Explain uncertainty, distinguish observed
statistics from inference, and never imply that you can execute transfers.
If the data cannot answer a request, say exactly what is missing and suggest a
grounded next question.

Use live snapshot and fixture sources for questions about current price,
availability, ownership, current team, or upcoming fixtures. Use
player_gameweek for completed historical performance. State the snapshot time
when data came from a live snapshot.

Do not call the same function more than once for a single answer. If a player
search returns an empty rows list, immediately explain that the player is not
in the latest imported player snapshot; do not retry alternative spellings
unless the user explicitly asks. Use no more than three data functions, then
answer using the returned evidence.
""".strip()


TOOLS = [
    {
        "type": "function",
        "name": "search_fpl_players",
        "description": "Find a player by name. Searches the current FPL snapshot first, then the historical player index when absent.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Player name or partial name."},
                "position": {
                    "type": ["string", "null"],
                    "enum": ["GKP", "DEF", "MID", "FWD", None],
                    "description": "Optional FPL position.",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query", "position", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_player_recent_form",
        "description": "Get recent finalized form for one player. Completed gameweeks are returned as exact gameweek totals; older history can be fixture-level.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {"type": "integer"},
                "gameweeks": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["player_id", "gameweeks"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_latest_feature_snapshot",
        "description": "Get the latest available historical model feature snapshot for one player. This is not a live prediction.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"player_id": {"type": "integer"}},
            "required": ["player_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_form_leaderboard",
        "description": "Rank players from the latest available historical feature snapshot by a selected form metric. This is not a live recommendation.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["points", "xgi", "minutes", "threat", "creativity", "defensive_contribution"],
                },
                "position": {
                    "type": ["string", "null"],
                    "enum": ["GKP", "DEF", "MID", "FWD", None],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 15},
            },
            "required": ["metric", "position", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_live_player_profile",
        "description": "Get the latest stored live FPL snapshot for a player, including price, availability, ownership and the snapshot timestamp.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"player_id": {"type": "integer"}},
            "required": ["player_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_player_upcoming_fixtures",
        "description": "Get upcoming fixtures from the stored live FPL fixture feed for one player.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "player_id": {"type": "integer"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            "required": ["player_id", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_fpl_data_status",
        "description": "Check database coverage and freshness before answering a time-sensitive question.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
]


TOOL_HANDLERS = {
    "search_fpl_players": search_fpl_players,
    "get_player_recent_form": get_player_recent_form,
    "get_latest_feature_snapshot": get_latest_feature_snapshot,
    "get_live_player_profile": get_live_player_profile,
    "get_player_upcoming_fixtures": get_player_upcoming_fixtures,
    "get_form_leaderboard": get_form_leaderboard,
    "get_fpl_data_status": get_fpl_data_status,
}


def _get_secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except FileNotFoundError:
        return default


def copilot_is_configured():
    """True only when the SDK and a server-side API key are available."""
    return OpenAI is not None and bool(_get_secret("OPENAI_API_KEY"))


def _run_tool(name, arguments):
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown FPL data function: {name}"}
    try:
        return handler(**arguments)
    except Exception as error:
        return {"error": f"Data lookup failed: {error}"}


def _empty_search_answer(arguments):
    """Avoid spending more tool calls when a player is absent from the index."""
    query = arguments.get("query", "that player").strip() or "that player"
    return (
        f"I could not find **{query}** in the latest imported player snapshot. "
        "That does not prove the player has no historical data; it means the "
        "current player index does not contain a matching name. Update the "
        "Player Database, then try again with the player name or FPL player ID."
    )


def answer_fpl_question(messages):
    """Answer a chat question with bounded, read-only tool calls."""
    if not copilot_is_configured():
        raise RuntimeError("FPL Copilot has not been configured yet.")

    client = OpenAI(api_key=_get_secret("OPENAI_API_KEY"))
    model = _get_secret("FPL_COPILOT_MODEL", DEFAULT_MODEL)
    input_items = [
        {"role": message["role"], "content": message["content"]}
        for message in messages[-12:]
    ]
    consulted_sources = []
    used_tools = set()

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=input_items,
            tools=TOOLS,
            parallel_tool_calls=False,
            max_output_tokens=700,
            store=False,
        )
        function_calls = [
            item for item in response.output if item.type == "function_call"
        ]
        if not function_calls:
            return response.output_text, consulted_sources

        input_items.extend(response.output)
        for call in function_calls:
            if call.name in used_tools:
                return (
                    "I already checked that data source for this question and "
                    "will not repeat the lookup. Please try a more specific "
                    "player name or ask a different FPL question.",
                    consulted_sources,
                )
            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError:
                arguments = {}
            result = _run_tool(call.name, arguments)
            used_tools.add(call.name)
            consulted_sources.append(call.name)

            if call.name == "search_fpl_players" and not result.get("rows"):
                return _empty_search_answer(arguments), consulted_sources

            if result.get("error"):
                return (
                    "I could not complete the requested FPL data lookup. "
                    f"The data source returned: {result['error']}",
                    consulted_sources,
                )

            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, default=str),
                }
            )

    return (
        "I could not complete the data lookup within the safety limit. "
        "Please ask a narrower FPL question.",
        consulted_sources,
    )


def render_fpl_copilot():
    """Render the FPL Copilot section and keep chat history in this session."""
    st.header("💬 FPL Copilot")
    st.caption(
        "Ask about players and recent form. Answers use read-only FPL data "
        "tools, and the assistant will flag when the available data is historical."
    )

    if not copilot_is_configured():
        st.info(
            "Copilot is ready to connect. Add OPENAI_API_KEY to Streamlit "
            "Secrets and add the openai package to requirements, then redeploy."
        )
        return

    if "fpl_copilot_messages" not in st.session_state:
        st.session_state["fpl_copilot_messages"] = []

    refresh_column, first, second, third, fourth = st.columns(5)
    prompt = None
    if refresh_column.button("Refresh live FPL data", key="copilot_refresh_live"):
        try:
            with st.spinner("Refreshing the live FPL snapshot..."):
                refresh = refresh_live_fpl_data()
            st.success(
                "Live FPL data refreshed: "
                f"{refresh['player_snapshot_rows']:,} players and "
                f"{refresh['fixture_rows']:,} fixtures."
            )
        except Exception as error:
            st.error(f"Live FPL refresh failed: {error}")
    if first.button("Find a player", key="copilot_find_player"):
        prompt = "What data do you have for Mohamed Salah?"
    if second.button("Form leaders", key="copilot_form_leaders"):
        prompt = "Who are the latest midfield form leaders by xGI?"
    if third.button("Data coverage", key="copilot_data_coverage"):
        prompt = "How current is the FPL data you can access?"
    if fourth.button("Clear chat", key="copilot_clear_chat"):
        st.session_state["fpl_copilot_messages"] = []
        st.rerun()

    for message in st.session_state["fpl_copilot_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("Data tools consulted"):
                    st.write(", ".join(message["sources"]))

    typed_prompt = st.chat_input("Ask an FPL question")
    prompt = typed_prompt or prompt
    if not prompt:
        return

    st.session_state["fpl_copilot_messages"].append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Checking FPL data..."):
            try:
                answer, sources = answer_fpl_question(
                    st.session_state["fpl_copilot_messages"]
                )
                st.markdown(answer)
                if sources:
                    with st.expander("Data tools consulted"):
                        st.write(", ".join(sources))
                st.session_state["fpl_copilot_messages"].append(
                    {"role": "assistant", "content": answer, "sources": sources}
                )
            except Exception as error:
                st.error(f"Copilot could not answer that question: {error}")
