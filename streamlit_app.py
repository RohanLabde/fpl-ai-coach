import streamlit as st

from data.fpl_api import get_fpl_data, get_fixtures
from data.fpl_data import get_players, get_teams, get_fixtures as clean_fixtures


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("FPL Data Explorer")


try:

    # Get main FPL data
    data = get_fpl_data()

    # Get fixtures separately
    fixture_data = get_fixtures()

    # Clean data
    players = get_players(data)
    teams = get_teams(data)
    fixtures = clean_fixtures(fixture_data)

    st.success("FPL data loaded successfully!")

    # Metrics
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

    # Player table
    st.subheader("Players")

    st.dataframe(
        players[
            [
                "id",
                "first_name",
                "second_name",
                "team_name",
                "position",
                "price",
                "total_points",
                "form",
                "selected_by_percent"
            ]
        ],
        use_container_width=True
    )

except Exception as e:

    st.error(
        f"Something went wrong: {e}"
    )
