"""Grounded, read-only FPL chat assistant for the Streamlit application."""

import json

import streamlit as st

from data.db import (
    compare_fpl_players,
    get_current_season_leaderboard,
    get_fpl_data_status,
    get_form_leaderboard,
    get_latest_feature_snapshot,
    get_live_player_profile,
    get_player_recent_form,
    get_player_upcoming_fixtures,
    search_fpl_players,
)
from data.fpl_intents import route_fpl_question
from data.fpl_query_planner import plan_fpl_question

try:
    from openai import OpenAI
except ImportError:  # Keep the rest of the Streamlit app usable until installed.
    OpenAI = None


DEFAULT_MODEL = "gpt-5-mini"
TOOL_HANDLERS = {
    "search_fpl_players": search_fpl_players,
    "compare_fpl_players": compare_fpl_players,
    "get_current_season_leaderboard": get_current_season_leaderboard,
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


COMPOSER_INSTRUCTIONS = """
You are the final-answer writer for FPL Copilot. A deterministic FPL data plan
has already run and the supplied evidence is authoritative for this answer.

Answer the user's question directly and practically. Do not ask for a metric,
position, or other clarification when the plan already selected a standard FPL
default. State the ranking basis in plain language, present a concise numbered
list when the evidence is a leaderboard, and mention the completed-gameweek
coverage. For defensive and goalkeeping profiles, foreground the profile's
defensive statistics and do not frame goals or assists as ranking drivers.
Do not invent statistics, recommendations, injuries, fixtures, or data that
are not in the evidence.
""".strip()


def _latest_user_question(messages):
    """Return the last user prompt from the current chat session."""
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _response_text(response):
    """Extract text from a Responses API result across supported output shapes."""
    answer = (getattr(response, "output_text", "") or "").strip()
    if answer:
        return answer

    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) != "output_text":
                continue
            answer = (getattr(content, "text", "") or "").strip()
            if answer:
                return answer
    return ""


def _format_value(value, decimal_places=1):
    """Format database values safely for a deterministic user-facing fallback."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{decimal_places}f}"
    return str(value)


def _fallback_leaderboard_answer(plan, result):
    """Render verified leaderboard evidence if the answer writer returns no text."""
    rows = result.get("rows", [])
    if not rows:
        return (
            "I found no eligible players for that ranking in the available FPL data."
        )

    metric = result.get("metric") or plan.get("metric") or "points"
    ranking_basis = result.get("ranking_basis") or metric.replace("_", " ")
    completed_gameweeks = rows[0].get("season_completed_gameweeks")
    minimum_starts = result.get("minimum_starts")

    coverage = []
    if completed_gameweeks is not None:
        gameweek_suffix = "" if completed_gameweeks == 1 else "s"
        coverage.append(
            f"Data covers {completed_gameweeks} completed gameweek{gameweek_suffix}."
        )
    if minimum_starts is not None:
        start_suffix = "" if minimum_starts == 1 else "s"
        coverage.append(
            f"Players need at least {minimum_starts} start{start_suffix} to qualify."
        )

    lines = [f"**Ranking basis: {ranking_basis}.**"]
    if coverage:
        lines.append(" ".join(coverage))
    lines.append("")

    for rank, row in enumerate(rows, start=1):
        name = row.get("player_name", "Unknown player")
        team = row.get("team_name", "Unknown team")
        starts = _format_value(row.get("starts"), 0)

        if metric == "defensive":
            detail = (
                f"{_format_value(row.get('total_clean_sheets'), 0)} clean sheets; "
                f"{_format_value(row.get('defensive_contribution_per_90'))} defensive "
                f"contribution per 90; {starts} starts"
            )
        elif metric == "goalkeeping":
            detail = (
                f"{_format_value(row.get('total_clean_sheets'), 0)} clean sheets; "
                f"{_format_value(row.get('saves_per_90'))} saves per 90; "
                f"{starts} starts"
            )
        elif metric in {"attacking", "xgi"}:
            detail = (
                f"{_format_value(row.get('total_xgi'))} xGI; "
                f"{_format_value(row.get('xgi_per_90'))} xGI per 90; "
                f"{starts} starts"
            )
        else:
            detail = (
                f"{_format_value(row.get('total_points'), 0)} FPL points; "
                f"{starts} starts"
            )
        lines.append(f"{rank}. **{name}** ({team}) — {detail}")

    return "\n".join(lines)


def _fallback_evidence_answer(plan, result):
    """Return a useful, fully grounded answer when text generation is empty."""
    if plan.get("tool_name") == "get_current_season_leaderboard" or (
        plan.get("intent") == "leaderboard"
    ):
        return _fallback_leaderboard_answer(plan, result)

    rows = result.get("rows")
    if isinstance(rows, list) and rows:
        preview = rows[:5]
        columns = [
            key for key in (
                "player_name", "team_name", "position", "total_points", "minutes",
                "starts", "price", "gameweek", "points", "opponent_name",
                "difficulty",
            ) if any(key in row for row in preview)
        ]
        if columns:
            header = " | ".join(column.replace("_", " ").title() for column in columns)
            divider = " | ".join("---" for _ in columns)
            body = [
                " | ".join(_format_value(row.get(column)) for column in columns)
                for row in preview
            ]
            return "\n".join(
                ["Here are the verified FPL results:", "", header, divider, *body]
            )

    return (
        "I found the relevant FPL data, but could not format a written answer. "
        "Please try the question again."
    )


def _compose_evidence_answer(client, model, question, plan, result, sources):
    """Write a grounded answer only after the validated read-only lookup."""
    evidence = {
        "question": question,
        "intent": plan.get("intent"),
        "interpretation": plan.get("reason") or plan.get("scope"),
        "data": result,
    }
    response = client.responses.create(
        model=model,
        instructions=COMPOSER_INSTRUCTIONS,
        input=[
            {
                "role": "user",
                "content": (
                    "User question:\n"
                    f"{question}\n\n"
                    "Verified FPL evidence:\n"
                    f"{json.dumps(evidence, default=str)}"
                ),
            }
        ],
        max_output_tokens=700,
        store=False,
    )
    answer = _response_text(response)
    if not answer:
        answer = _fallback_evidence_answer(plan, result)
    return answer, sources


def _answer_routed_question(client, model, question, plan):
    """Run a deterministic high-confidence data plan."""
    result = _run_tool(plan["tool_name"], plan["arguments"])
    if result.get("error"):
        return (
            "I could not complete the requested FPL data lookup. "
            f"The data source returned: {result['error']}",
            [plan["tool_name"]],
        )
    return _compose_evidence_answer(
        client, model, question, plan, result, [plan["tool_name"]]
    )


def _resolve_planned_player(name):
    """Resolve one explicit player name without silently choosing an ambiguity."""
    result = _run_tool(
        "search_fpl_players",
        {"query": name, "position": None, "limit": 8},
    )
    if result.get("error"):
        return None, result, "I could not search the FPL player index right now."

    rows = result.get("rows", [])
    if not rows:
        return (
            None,
            result,
            f"I could not find **{name}** in the current or historical FPL player index.",
        )

    normalized_name = " ".join(name.casefold().split())
    exact = [
        row for row in rows
        if " ".join(str(row.get("player_name", "")).casefold().split())
        == normalized_name
    ]
    if len(exact) == 1:
        return exact[0], result, None
    if len(rows) == 1:
        return rows[0], result, None

    choices = ", ".join(
        f"{row.get('player_name')} ({row.get('team_name', 'unknown team')})"
        for row in rows[:5]
    )
    return None, result, (
        f"I found several matches for **{name}**: {choices}. "
        "Please specify the player's full name or team."
    )


def _conversation_context(messages):
    """Provide the planner with a compact recent conversation, not raw history."""
    recent = messages[-6:]
    lines = [
        f"{message.get('role', 'user')}: {message.get('content', '')}"
        for message in recent
    ]
    return "\n".join(lines)[-4_000:]


def _answer_planned_question(client, model, question, messages):
    """Plan, validate, resolve, then execute only a permitted read-only lookup."""
    plan = plan_fpl_question(
        client,
        model,
        question,
        conversation_context=_conversation_context(messages),
    )

    if plan["intent"] == "unsupported" or plan["needs_clarification"]:
        return (
            plan["clarification"]
            or (
                "I cannot answer that reliably with the FPL data currently "
                "available. Try a player, form, fixture, or current-season "
                "ranking question."
            ),
            [],
        )

    if plan["intent"] == "data_status":
        result = _run_tool("get_fpl_data_status", {})
        sources = ["get_fpl_data_status"]
    elif plan["intent"] == "leaderboard":
        result = _run_tool(
            "get_current_season_leaderboard",
            {
                "metric": plan["metric"] or "points",
                "position": plan["position"],
                "limit": plan["limit"],
            },
        )
        sources = ["get_current_season_leaderboard"]
    elif plan["intent"] in {
        "player_form",
        "player_profile",
        "upcoming_fixtures",
    }:
        player, _search_result, message = _resolve_planned_player(
            plan["player_names"][0]
        )
        if message:
            return message, ["search_fpl_players"]

        tool_by_intent = {
            "player_form": "get_player_recent_form",
            "player_profile": "get_live_player_profile",
            "upcoming_fixtures": "get_player_upcoming_fixtures",
        }
        tool_name = tool_by_intent[plan["intent"]]
        arguments = {"player_id": int(player["player_id"])}
        if tool_name == "get_player_recent_form":
            arguments["gameweeks"] = plan["gameweeks"]
        if tool_name == "get_player_upcoming_fixtures":
            arguments["limit"] = min(plan["limit"], 8)
        result = _run_tool(tool_name, arguments)
        sources = ["search_fpl_players", tool_name]
    elif plan["intent"] == "compare_players":
        first, _first_search, first_message = _resolve_planned_player(
            plan["player_names"][0]
        )
        if first_message:
            return first_message, ["search_fpl_players"]
        second, _second_search, second_message = _resolve_planned_player(
            plan["player_names"][1]
        )
        if second_message:
            return second_message, ["search_fpl_players"]
        result = _run_tool(
            "compare_fpl_players",
            {
                "player_a_id": int(first["player_id"]),
                "player_b_id": int(second["player_id"]),
            },
        )
        sources = ["search_fpl_players", "compare_fpl_players"]
    else:
        return (
            "I could not map that question to a supported FPL data lookup.",
            [],
        )

    if result.get("error"):
        return (
            "I could not complete the requested FPL data lookup. "
            f"The data source returned: {result['error']}",
            sources,
        )
    return _compose_evidence_answer(
        client, model, question, plan, result, sources
    )


def answer_fpl_question(messages):
    """Answer through deterministic routing or a validated structured plan."""
    if not copilot_is_configured():
        raise RuntimeError("FPL Copilot has not been configured yet.")

    client = OpenAI(api_key=_get_secret("OPENAI_API_KEY"))
    model = _get_secret("FPL_COPILOT_MODEL", DEFAULT_MODEL)
    question = _latest_user_question(messages)

    deterministic_plan = route_fpl_question(question)
    if deterministic_plan:
        return _answer_routed_question(
            client, model, question, deterministic_plan
        )
    return _answer_planned_question(client, model, question, messages)


def _data_freshness_caption():
    """Return a small, non-interactive summary of the available FPL data."""
    try:
        status = get_fpl_data_status()
        live = status.get("live_snapshot", [])
        completed = status.get("completed_gameweek_data", [])

        parts = []
        if live:
            snapshot = live[0]
            snapshot_at = snapshot.get("latest_live_snapshot_at")
            player_count = snapshot.get("player_snapshot_rows")
            if snapshot_at and player_count:
                parts.append(
                    f"Live snapshot: {player_count:,} players, updated {snapshot_at}."
                )

        if completed:
            history = completed[0]
            season = history.get("latest_completed_season")
            gameweek = history.get("latest_completed_gameweek")
            if season and gameweek:
                parts.append(f"Finalized results: {season} through GW {gameweek}.")

        return " ".join(parts) or "FPL data is being prepared."
    except Exception:
        return "FPL data refreshes automatically; availability may vary briefly."


def render_fpl_copilot():
    """Render a focused, chat-first FPL Copilot experience."""
    st.title("⚽ FPL Copilot")
    st.caption(
        "Ask about players, current prices, upcoming fixtures, or recent form. "
        "Answers are grounded in the FPL data available to the app."
    )
    st.caption(_data_freshness_caption())

    if not copilot_is_configured():
        st.info(
            "Copilot is ready to connect. Add OPENAI_API_KEY to Streamlit "
            "Secrets and add the openai package to requirements, then redeploy."
        )
        return

    if "fpl_copilot_messages" not in st.session_state:
        st.session_state["fpl_copilot_messages"] = []

    if not st.session_state["fpl_copilot_messages"]:
        with st.chat_message("assistant"):
            st.markdown(
                "Hi — ask me anything about FPL. For example: "
                "**“How has Raya performed in the last three gameweeks?”**"
            )

    for message in st.session_state["fpl_copilot_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                st.caption("Data checked: " + ", ".join(message["sources"]))

    prompt = st.chat_input("Ask an FPL question")
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
                    st.caption("Data checked: " + ", ".join(sources))
                st.session_state["fpl_copilot_messages"].append(
                    {"role": "assistant", "content": answer, "sources": sources}
                )
            except Exception:
                message = (
                    "I could not answer that question right now. Please try "
                    "again in a moment."
                )
                st.error(message)
                st.session_state["fpl_copilot_messages"].append(
                    {"role": "assistant", "content": message}
                )
