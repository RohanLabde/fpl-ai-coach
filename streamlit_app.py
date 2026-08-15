import streamlit as st

from data.fpl_api import get_fpl_data
from data.fpl_data import get_players
from data.db import get_database_connection, save_players


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("FPL Data")


if st.button("🔄 Update Player Database"):

    try:

        with st.spinner("Downloading latest FPL data..."):

            data = get_fpl_data()

        players = get_players(data)

        with st.spinner("Saving players to database..."):

            save_players(players)

        st.success(
            f"Successfully updated {len(players)} players!"
        )

    except Exception as e:

        st.error(
            f"Something went wrong: {e}"
        )


# Read database

try:

    conn = get_database_connection()

    result = conn.query(
        "SELECT COUNT(*) AS player_count FROM players",
        ttl=0
    )

    player_count = result.iloc[0]["player_count"]

    st.metric(
        "Players in database",
        player_count
    )

except Exception as e:

    st.error(
        f"Could not read database: {e}"
    )
