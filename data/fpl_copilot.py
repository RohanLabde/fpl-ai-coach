"""Grounded, read-only FPL chat assistant for the Streamlit application."""

import json

import streamlit as st

from data.db import (
    get_fpl_data_status,
    get_form_leaderboard,
    get_latest_feature_snapshot,
    get_player_recent_form,
    search_fpl_players,
)

try:
    from openai import OpenAI
except ImportError:  # Keep the rest of the Streamlit app usable until installed.
    OpenAI = None


DEFAULT_MODEL = "gpt-5-mini"
MAX_TOOL_ROUNDS = 4

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
""".strip()


TOOLS = [
    {
        "type": "function",
        "name": "search_fpl_players",
        "description": "Find current player records by name.",
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
        "description": "Get the most recent historical fixture-level performances for one player.",
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
            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError:
                arguments = {}
            result = _run_tool(call.name, arguments)
            consulted_sources.append(call.name)
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

    first, second, third = st.columns(3)
    prompt = None
    if first.button("Find a player", key="copilot_find_player"):
        prompt = "What data do you have for Mohamed Salah?"
    if second.button("Form leaders", key="copilot_form_leaders"):
        prompt = "Who are the latest midfield form leaders by xGI?"
    if third.button("Data coverage", key="copilot_data_coverage"):
        prompt = "How current is the FPL data you can access?"

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
