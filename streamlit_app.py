import streamlit as st
import pandas as pd

from data.fixture_engine import (
    get_team_fixture_horizon,
    summarize_fixture_horizon
)

from data.historical import (
    load_historical_data,
    load_team_mapping,
    create_team_mapping,
    prepare_historical_data,
    prepare_database_records
)

from data.db import (
    get_database_connection,
    save_players,
    save_historical_data
)

HISTORICAL_2025_26_URL = (
    "https://raw.githubusercontent.com/"
    "imadeddine-belkat/Premier-League-Stats/"
    "main/fpl_scraper/fpl_stats/_merged/players/"
    "2025-26_all_players_gw.csv"
)

from data.fpl_api import get_fpl_data, get_fixtures
from data.fpl_data import get_players
from data.features import build_form_features


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

st.subheader("Team Mapping Test")


if st.button("🔎 Test Team Mapping"):

    try:

        with st.spinner("Downloading team mapping..."):

            team_data = load_team_mapping()

        teams = create_team_mapping(
            team_data
        )

        st.success(
            f"Successfully loaded {len(teams)} teams!"
        )

        st.dataframe(
            teams,
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Team mapping failed: {e}"
        )

st.subheader("Historical Data Join Test")


if st.button("🔗 Test Player + Fixture Join"):

    try:

        with st.spinner(
            "Downloading historical datasets..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            team_data = load_team_mapping()

            teams = create_team_mapping(
                team_data
            )


        with st.spinner(
            "Joining player, fixture and team data..."
        ):

            historical = prepare_historical_data(
                players,
                fixtures,
                teams
            )


        st.success(
            "Historical data joined successfully!"
        )


        # --------------------------------
        # Validation metrics
        # --------------------------------

        col1, col2, col3, col4 = st.columns(4)


        col1.metric(
            "Player rows",
            len(historical)
        )


        col2.metric(
            "Gameweeks",
            historical["gameweek"].nunique()
        )


        col3.metric(
            "Fixtures",
            historical["fixture_id"].nunique()
        )


        col4.metric(
            "Missing fixtures",
            historical["fixture_id"].isna().sum()
        )


        # --------------------------------
        # Preview
        # --------------------------------

        st.subheader(
            "Historical Data Preview"
        )


        preview_columns = [
            "season",
            "gameweek",
            "player_id",
            "player_name",
            "position",
            "team_id",
            "team_name",
            "fixture_id",
            "opponent_team_id",
            "was_home",
            "fixture_difficulty",
            "minutes",
            "total_points",
            "goals_scored",
            "assists",
            "expected_goals",
            "expected_assists"
        ]


        st.dataframe(
            historical[
                preview_columns
            ].head(20),
            use_container_width=True
        )


    except Exception as e:

        st.error(
            f"Historical join failed: {e}"
        )

st.subheader("Historical Database Import")


if st.button(
    "💾 Import 2025/26 into Supabase"
):

    try:

        with st.spinner(
            "Downloading historical data..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            team_data = load_team_mapping()

            teams = create_team_mapping(
                team_data
            )


        with st.spinner(
            "Preparing historical records..."
        ):

            historical = (
                prepare_historical_data(
                    players,
                    fixtures,
                    teams
                )
            )

            records = (
                prepare_database_records(
                    historical
                )
            )


        st.info(
            f"Ready to import {len(records):,} records."
        )


        with st.spinner(
            "Importing records into Supabase..."
        ):

            imported = save_historical_data(
                records
            )


        st.success(
            f"Successfully imported "
            f"{imported:,} historical records!"
        )


    except Exception as e:

        st.error(
            f"Historical import failed: {e}"
        )

st.subheader("Prediction Feature Test")


if st.button("🧠 Build Form Features"):

    try:

        with st.spinner(
            "Preparing historical data..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            team_data = load_team_mapping()

            teams = create_team_mapping(
                team_data
            )

            historical = (
                prepare_historical_data(
                    players,
                    fixtures,
                    teams
                )
            )


        with st.spinner(
            "Calculating form features..."
        ):

            features = build_form_features(
                historical
            )


        st.success(
            "Form features created successfully!"
        )


        # --------------------------------
        # Basic metrics
        # --------------------------------

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Feature rows",
            len(features)
        )

        col2.metric(
            "Players",
            features["player_id"].nunique()
        )

        col3.metric(
            "Gameweeks",
            features["gameweek"].nunique()
        )


        # --------------------------------
        # Preview
        # --------------------------------

        st.subheader(
            "Prediction Feature Preview"
        )

        st.dataframe(
        features[
            [
                "gameweek",
                "player_name",
                "team_name",
            
                # Form
                "rolling_3gw_points",
                "rolling_5gw_points",
            
                # Underlying performance
                "rolling_3gw_xg",
                "rolling_3gw_xa",
                "rolling_3gw_xgi",
            
                # Playing time
                "previous_gw_minutes",
                "rolling_3gw_minutes",
                "rolling_5gw_minutes",
            
                "previous_gw_starts",
                "rolling_3gw_starts",
                "rolling_5gw_starts",
            
                "rolling_3gw_start_rate",
                "rolling_5gw_start_rate",
            
                # Target
                "next_gw_points"
            ]
        ].head(30),
        use_container_width=True
    )


    except Exception as e:

        st.error(
            f"Feature engineering failed: {e}"
        )

st.divider()

st.header("Fixture Horizon Test")

if st.button("🔮 Test Arsenal Fixture Horizon"):

    test_team_id = 1
    test_current_gameweek = 10

    fixtures = pd.DataFrame(get_fixtures())
    fixture_horizon = get_team_fixture_horizon(
        fixtures,
        team_id=test_team_id,
        current_gameweek=test_current_gameweek,
        horizon=5
    )

    st.subheader("Arsenal — Next 5 Gameweeks")

    st.dataframe(
        fixture_horizon,
        use_container_width=True
    )

    summary = summarize_fixture_horizon(
        fixtures,
        team_id=test_team_id,
        current_gameweek=test_current_gameweek
    )

    st.subheader("Fixture Summary")

    st.json(summary)
