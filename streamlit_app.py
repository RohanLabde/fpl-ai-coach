import streamlit as st
import pandas as pd

HISTORICAL_2025_26_URL = (
    "https://raw.githubusercontent.com/"
    "imadeddine-belkat/Premier-League-Stats/"
    "main/fpl_scraper/fpl_stats/_merged/players/"
    "2025-26_all_players_gw.csv"
)

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

if st.button("📚 Test Historical Data"):

    try:

        with st.spinner("Downloading 2025/26 historical data..."):

            historical = pd.read_csv(
                HISTORICAL_2025_26_URL
            )

        st.success(
            "Historical data downloaded successfully!"
        )

        st.write(
            "Rows:",
            len(historical)
        )

        st.write(
            "Columns:"
        )

        st.write(
            historical.columns.tolist()
        )

        st.dataframe(
            historical.head(10),
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Historical data download failed: {e}"
        )
