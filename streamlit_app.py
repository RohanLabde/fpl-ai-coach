import streamlit as st

from data.fpl_api import get_fpl_data
from data.fpl_data import get_players, get_teams, get_fixtures


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("FPL Data Explorer")


try:

    data = get_fpl_data()

    players = get_players(data)
    teams = get_teams(data)
    fixtures = get_fixtures(data)

    st.success("FPL data loaded successfully!")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Players",
        len(players)
    )

    col2.metric(
        "Teams",
        len(teams)
    )

    col3.metric(
        "Fixtures",
        len(fixtures)
    )

    st.subheader("Players")

    st.dataframe(
        players,
        use_container_width=True
    )

except Exception as e:

    st.error(
        f"Something went wrong: {e}"
    )
